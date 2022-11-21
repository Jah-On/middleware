from middlewared.plugins.smb_.registry_base import RegObj, RegistrySchema


FRUIT_CATIA_MAPS = [
    "0x01:0xf001,0x02:0xf002,0x03:0xf003,0x04:0xf004",
    "0x05:0xf005,0x06:0xf006,0x07:0xf007,0x08:0xf008",
    "0x09:0xf009,0x0a:0xf00a,0x0b:0xf00b,0x0c:0xf00c",
    "0x0d:0xf00d,0x0e:0xf00e,0x0f:0xf00f,0x10:0xf010",
    "0x11:0xf011,0x12:0xf012,0x13:0xf013,0x14:0xf014",
    "0x15:0xf015,0x16:0xf016,0x17:0xf017,0x18:0xf018",
    "0x19:0xf019,0x1a:0xf01a,0x1b:0xf01b,0x1c:0xf01c",
    "0x1d:0xf01d,0x1e:0xf01e,0x1f:0xf01f",
    "0x22:0xf020,0x2a:0xf021,0x3a:0xf022,0x3c:0xf023",
    "0x3e:0xf024,0x3f:0xf025,0x5c:0xf026,0x7c:0xf027"
]


class ShareSchema(RegistrySchema):
    def convert_registry_to_schema(self, data_in, data_out):
        """
        This converts existing smb.conf shares into schema used
        by middleware. It is only used in clustered configuration.
        """
        data_aux = {}
        super().convert_registry_to_schema(data_in, data_out)
        for k, v in data_in.items():
            if type(v) != dict:
                continue

            if k in ['vfs objects', 'ea support']:
                continue

            data_aux[k] = v['raw']

        if data_aux and data_out['purpose'] not in ['NO_SHARE', 'DEFAULT_SHARE']:
            preset = self.middleware.call_sync('sharing.smb.presets')
            purpose = preset[data_out['purpose']]
            preset_aux = self.middleware.call_sync('sharing.smb.auxsmbconf_dict', purpose['params']['auxsmbconf'])
            for k, v in preset_aux.items():
                if data_aux[k] == v:
                    data_aux.pop(k)

        data_out['auxsmbconf'] = '\n'.join([f'{k}={v}' if v is not None else k for k, v in data_aux.items()])
        data_out['enabled'] = True
        data_out['locked'] = False

        return

    def convert_schema_to_registry(self, data_in, data_out):
        """
        Convert middleware schema SMB shares to an SMB service definition
        """
        def order_vfs_objects(vfs_objects, is_clustered, fruit_enabled, purpose):
            vfs_objects_special = ('catia', 'fruit', 'streams_xattr', 'shadow_copy_zfs',
                                   'acl_xattr', 'nfs4acl_xattr', 'glusterfs',
                                   'winmsa', 'recycle', 'crossrename', 'zfs_core', 'aio_fbsd', 'io_uring')

            invalid_vfs_objects = ['noacl']
            cluster_safe_objects = ['catia', 'fruit', 'streams_xattr', 'acl_xattr', 'recycle', 'glusterfs', 'io_ring']

            vfs_objects_ordered = []

            if fruit_enabled and 'fruit' not in vfs_objects:
                vfs_objects.append('fruit')

            if is_clustered:
                for obj in vfs_objects.copy():
                    if obj in cluster_safe_objects:
                        continue
                    vfs_objects.remove(obj)

            if 'fruit' in vfs_objects:
                if 'streams_xattr' not in vfs_objects:
                    vfs_objects.append('streams_xattr')

            if purpose == 'ENHANCED_TIMEMACHINE':
                vfs_objects.append('tmprotect')
            elif purpose == 'WORM_DROPBOX':
                vfs_objects.append('worm')

            for obj in vfs_objects:
                if obj in invalid_vfs_objects:
                    raise ValueError(f'[{obj}] is an invalid VFS object')

                if obj not in vfs_objects_special:
                    vfs_objects_ordered.append(obj)

            for obj in vfs_objects_special:
                if obj in vfs_objects:
                    vfs_objects_ordered.append(obj)

            return vfs_objects_ordered

        data_out['vfs objects'] = {"parsed": ["io_uring"]}
        data_out['ea support'] = {"parsed": False}
        data_in['fruit_enabled'] = self.middleware.call_sync("smb.config")['aapl_extensions']
        is_clustered = bool(data_in['cluster_volname'])
        self.middleware.call_sync('sharing.smb.apply_presets', data_in)

        super().convert_schema_to_registry(data_in, data_out)

        ordered_vfs_objects = order_vfs_objects(
            data_out['vfs objects']['parsed'],
            is_clustered,
            data_in['fruit_enabled'],
            data_in['purpose'],
        )
        data_out['vfs objects']['parsed'] = ordered_vfs_objects

        """
        Some presets contain values that users can override via aux
        parameters. Set them prior to aux parameter processing.
        """
        if data_in['purpose'] not in ['NO_SHARE', 'DEFAULT_SHARE']:
            preset = self.middleware.call_sync('sharing.smb.presets')
            purpose = preset[data_in['purpose']]
            for param in purpose['params']['auxsmbconf'].splitlines():
                auxparam, val = param.split('=', 1)
                data_out[auxparam.strip()] = {"raw": val.strip()}

        for param in data_in['auxsmbconf'].splitlines():
            if not param.strip():
                continue
            try:
                auxparam, val = param.split('=', 1)
                """
                vfs_fruit must be added to all shares if fruit is enabled.
                Support for SMB2 AAPL extensions is determined on first tcon
                to server, and so if they aren't appended to any vfs objects
                overrides via auxiliary parameters, then users may experience
                unexpected behavior.
                """
                if auxparam.strip() == "vfs objects":
                    vfsobjects = val.strip().split()
                    if data_in['shadowcopy']:
                        vfsobjects.append('shadow_copy_zfs')
                    data_out['vfs objects'] = {"parsed": order_vfs_objects(vfsobjects, is_clustered, data_in['fruit_enabled'], None)}
                else:
                    data_out[auxparam.strip()] = {"raw": val.strip()}

            except ValueError:
                raise

            except Exception:
                self.middleware.logger.debug(
                    "[%s] contains invalid auxiliary parameter: [%s]",
                    data_in['auxsmbconf'], param
                )

        self._normalize_config(data_out)
        return

    def path_local_get(entry, conf):
        path = conf.get('path', {"raw": ""})
        glusterfs_volume = conf.get('glusterfs:volume', {"raw": ""})
        if not glusterfs_volume['raw']:
            return str(path['raw'])

        return f'CLUSTER:{glusterfs_volume["raw"]}{path["raw"]}'

    def path_local_set(entry, val, data_in, data_out):
        return

    def path_get(entry, conf):
        val = conf.pop(entry.smbconf, entry.default)
        if type(val) != dict:
            return val

        path = val['parsed']
        if path == "":
            """
            Empty path is valid for homes shares.
            """
            return path

        path_suffix = conf.get("tn:path_suffix", {"raw": ""})

        """
        remove any path suffix from path before returning.
        """
        if path_suffix['raw']:
            suffix_len = len(path_suffix['raw'].split('/'))
            path = path.rsplit('/', suffix_len)[0]

        return path

    def path_set(entry, val, data_in, data_out):
        if not val:
            data_out["path"] = {"parsed": ""}
            return

        path_suffix = data_in["path_suffix"]
        if path_suffix:
            path = '/'.join([val, path_suffix])
        else:
            path = val

        data_out['path'] = {"parsed": path}

    def durable_get(entry, conf):
        """
        Durable handles are inverse of "posix locking" parmaeter.
        """
        val = conf.pop(entry.smbconf, entry.default)
        if type(val) != dict:
            return val

        kernel_oplocks = conf.get('kernel oplocks', {'parsed': False})
        if not kernel_oplocks['parsed']:
            conf.pop('kernel oplocks', None)

        kernel_share_modes = conf.get('kernel share modes', {'parsed': True})
        if not kernel_share_modes['parsed']:
            conf.pop('kernel share modes', None)

        return not val['parsed']

    def durable_set(entry, val, data_in, data_out):
        data_out['posix locking'] = {"parsed": not val}
        data_out['kernel share modes'] = {"parsed": not val}
        data_out['kernel oplocks'] = {"parsed": not val}
        return

    def recycle_get(entry, conf):
        """
        Recycle bin has multiple associated parameters, remove them
        so that they don't appear as auxiliary parameters (unless
        they deviate from our defaults).
        """
        vfs_objects = conf.get("vfs objects", [])
        if "recycle" not in vfs_objects['parsed']:
            return False

        conf.pop("recycle:repository", "")
        for parm in ["keeptree", "versions", "touch"]:
            to_check = f"recycle:{parm}"
            if conf[to_check]["parsed"]:
                conf.pop(to_check)

        if conf["recycle:directory_mode"]['raw'] == "0777":
            conf.pop("recycle:directory_mode")

        if conf["recycle:subdir_mode"]['raw'] == "0700":
            conf.pop("recycle:subdir_mode")

        return True

    def recycle_set(entry, val, data_in, data_out):
        if not val:
            return

        ad_enabled = entry.middleware.call_sync("activedirectory.get_state") != "DISABLED"
        data_out.update({
            "recycle:repository": {"parsed": ".recycle/%D/%U" if ad_enabled else ".recycle/%U"},
            "recycle:keeptree": {"parsed": True},
            "recycle:versions": {"parsed": True},
            "recycle:touch": {"parsed": True},
            "recycle:directory_mode": {"parsed": "0777"},
            "recycle:subdir_mode": {"parsed": "0700"},
        })
        data_out['vfs objects']['parsed'].append("recycle")

        return

    def shadowcopy_get(entry, conf):
        vfs_objects = conf.get("vfs objects", [])
        return "shadow_copy_zfs" in vfs_objects

    def shadowcopy_set(entry, val, data_in, data_out):
        if not val:
            return

        data_out['vfs objects']['parsed'].append("shadow_copy_zfs")
        return

    def tmquot_get(entry, conf):
        val = conf.pop(entry.smbconf, entry.default)
        if type(val) != dict:
            return 0

        return int(val['raw'])

    def acl_get(entry, conf):
        conf.pop("nfs4:chown", None)
        val = conf.pop(entry.smbconf, entry.default)
        if type(val) != dict:
            return val

        return val['parsed']

    def acl_set(entry, val, data_in, data_out):
        if not val:
            data_out['nt acl support'] = {"parsed": False}

        if data_in['cluster_volname']:
            data_out['vfs objects']['parsed'].append("acl_xattr")
            return

        try:
            acltype = entry.middleware.call_sync('filesystem.path_get_acltype', data_in['path'])
        except FileNotFoundError:
            entry.middleware.logger.warning(
                "%s: path does not exist. This is unexpected situation and "
                "may indicate a failure of pool import.", data_in["path"]
            )
            raise ValueError(f"{data_in['path']}: path does not exist")
        except OSError:
            entry.middleware.logger.warning(
                "%s: failed to determine acltype for path.",
                data_in['path'], exc_info=True
            )
            acltype = "DISABLED"

        if acltype == "NFS4":
            data_out['vfs objects']['parsed'].append("nfs4acl_xattr")
            data_out.update({
                "nfs4acl_xattr:nfs4_id_numeric": {"parsed": True},
                "nfs4acl_xattr:validate_mode": {"parsed": False},
                "nfs4acl_xattr:xattr_name": {"parsed": "system.nfs4_acl_xdr"},
                "nfs4acl_xattr:encoding": {"parsed": "xdr"},
                "nfs4:chown": {"parsed": True}
            })
        elif acltype == 'POSIX1E':
            data_out['vfs objects']['parsed'].append("acl_xattr")

        else:
            entry.middleware.logger.debug(
                "ACLs are disabled on path %s. Disabling NT ACL support.",
                data_out['path']
            )
            data_out['nt acl support'] = {"parsed": False}

        return

    def fsrvp_get(entry, conf):
        vfs_objects = conf.get("vfs objects", [])
        return "zfs_fsrvp" in vfs_objects

    def fsrvp_set(entry, val, data_in, data_out):
        if not val:
            return

        data_out['vfs objects']['parsed'].append("zfs_fsrvp")
        return

    def streams_get(entry, conf):
        vfs_objects = conf.get("vfs objects", [])
        return "streams_xattr" in vfs_objects

    def streams_set(entry, val, data_in, data_out):
        """
        vfs_fruit requires streams_xattr to be enabled
        """
        if not val and not data_in['fruit_enabled']:
            return

        data_out['vfs objects']['parsed'].append("streams_xattr")
        if not data_in.get("cluster_volname"):
            data_out['smbd max xattr size'] = {"parsed": 2097152}

        if data_in['fruit_enabled']:
            data_out["fruit:metadata"] = {"parsed": "stream"}
            data_out["fruit:resource"] = {"parsed": "stream"}

        return

    def cluster_get(entry, conf):
        val = conf.pop(entry.smbconf, entry.default)
        if type(val) != dict:
            return val

        if not val['parsed']:
            return ''

        conf.pop("glusterfs:logfile", "")
        return val['parsed']

    def cluster_set(entry, val, data_in, data_out):
        """
        Add glusterfs to vfs objects, set cluster volname, and
        set logging path.
        """
        if not val:
            data_out['vfs objects']['parsed'].append("zfs_core")
            return

        data_out['vfs objects']['parsed'].append("glusterfs")
        data_out[entry.smbconf] = {"parsed": val}
        data_out["glusterfs:logfile"] = {"parsed": f'/var/log/samba4/glusterfs-{val}.log'}
        return

    def mangling_get(entry, conf):
        encoding = conf.get("fruit: encoding", None)
        if encoding and encoding['raw'] == "native":
            return True

        mapping = conf.get("catia: mappings", None)
        return bool(mapping)

    def mangling_set(entry, val, data_in, data_out):
        if not val:
            return

        data_out['vfs objects']['parsed'].append("catia")

        fruit_enabled = data_in.get("fruit_enabled")
        if fruit_enabled:
            data_out.update({
                'fruit:encoding': {"parsed": 'native'},
                'mangled names': {"parsed": False},
            })
        else:
            data_out.update({
                'catia:mappings': {"parsed": ','.join(FRUIT_CATIA_MAPS)},
                'mangled names': {"parsed": False},
            })
        return

    def afp_get(entry, conf):
        val = conf.pop(entry.smbconf, entry.default)
        if type(val) != dict:
            return val

        if not val['parsed']:
            return False

        conf.pop('fruit:encoding', None)
        conf.pop('fruit:metadata', None)
        conf.pop('fruit:resource', None)
        conf.pop('streams_xattr:store_prefix', None)
        conf.pop('streams_xattr:store_stream_type', None)
        conf.pop('streams_xattr:xattr_compat', None)
        return True

    def afp_set(entry, val, data_in, data_out):
        if not val:
            return

        if 'fruit' not in data_out['vfs objects']['parsed']:
            data_out['vfs objects']['parsed'].append("fruit")

        if 'catia' not in data_out['vfs objects']['parsed']:
            data_out['vfs objects']['parsed'].append("catia")

        data_out['fruit:encoding'] = {"parsed": 'native'}
        data_out['fruit:metadata'] = {"parsed": 'netatalk'}
        data_out['fruit:resource'] = {"parsed": 'file'}
        data_out['streams_xattr:prefix'] = {"parsed": 'user.'}
        data_out['streams_xattr:store_stream_type'] = {"parsed": False}
        data_out['streams_xattr:xattr_compat'] = {"parsed": True}
        return

    schema = [
        RegObj("purpose", "tn:purpose", ""),
        RegObj("path_local", None, "",
               smbconf_parser=path_local_get, schema_parser=path_local_set),
        RegObj("path", "path", "",
               smbconf_parser=path_get, schema_parser=path_set),
        RegObj("path_suffix", "tn:path_suffix", ""),
        RegObj("home", "tn:home", False),
        RegObj("vuid", "tn:vuid", ''),
        RegObj("comment", "comment", ""),
        RegObj("guestok", "guest ok", False),
        RegObj("hostsallow", "hosts allow", []),
        RegObj("hostsdeny", "hosts deny", []),
        RegObj("abe", "access based share enum", False),
        RegObj("ro", "read only", True),
        RegObj("browsable", "browseable", True),
        RegObj("timemachine", "fruit:time machine", True),
        RegObj("timemachine_quota", "fruit:time machine max size", "",
               smbconf_parser=tmquot_get),
        RegObj("durablehandle", "posix locking", True,
               smbconf_parser=durable_get, schema_parser=durable_set),
        RegObj("recyclebin", None, False,
               smbconf_parser=recycle_get, schema_parser=recycle_set),
        RegObj("shadowcopy", None, True,
               smbconf_parser=shadowcopy_get, schema_parser=shadowcopy_set),
        RegObj("acl", "nt acl support", True,
               smbconf_parser=acl_get, schema_parser=acl_set),
        RegObj("aapl_name_mangling", None, False,
               smbconf_parser=mangling_get, schema_parser=mangling_set),
        RegObj("fsrvp", None, False,
               smbconf_parser=fsrvp_get, schema_parser=fsrvp_set),
        RegObj("streams", None, True,
               smbconf_parser=streams_get, schema_parser=streams_set),
        RegObj("afp", "tn:afp", False,
               smbconf_parser=afp_get, schema_parser=afp_set),
        RegObj("cluster_volname", "glusterfs:volume", "",
               smbconf_parser=cluster_get, schema_parser=cluster_set),
    ]

    def __init__(self, middleware):
        self.middleware = middleware
        for entry in self.schema:
            entry.middleware = middleware

        super().__init__(self.schema)
