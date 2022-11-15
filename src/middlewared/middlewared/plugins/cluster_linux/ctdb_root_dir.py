import errno
import os

import pyglfs
from middlewared.service import Service, CallError, job
from .utils import CTDBConfig

LOCK = 'ctdb-setup-lock'
ROOT_DIR_NAME = 'ctdb-root-dir'


class CtdbRootDirService(Service):

    class Config:
        namespace = 'ctdb.root_dir'
        private = True

    def create_dir_and_set_perms(self, gvol_name):
        root_handle = pyglfs.Volume({
            'volume_name': gvol_name,
            'volfile_servers': [{'host': '127.0.0.1', 'proto': 'tcp', 'port': 0}]
        }).get_root_handle()

        # create the root dir
        try:
            root_handle.mkdir(ROOT_DIR_NAME)
        except pyglfs.GLFSError as e:
            if e.errno != errno.EEXIST:
                raise CallError(f'Failed to create {ROOT_DIR_NAME!r}: {e}')

        # set perms
        dir_fd = root_handle.lookup(ROOT_DIR_NAME).open(os.O_DIRECTORY)
        stat = dir_fd.fstat()
        if stat.st_mode & 0o700 != 0:
            try:
                dir_fd.fchmod(0o700)
            except Exception:
                # this isn't fatal but still need to log something
                self.logger.warning('Failed to change permissions on %r', ROOT_DIR_NAME, exc_info=True)

        # change user/group owner to root/root (-1 means leave unchanged)
        uid = 0 if stat.st_uid != 0 else -1
        gid = 0 if stat.st_gid != 0 else -1
        if uid == 0 or gid == 0:
            dir_fd.fchown(uid, gid)

    @job(lock=LOCK)
    def setup(self, job, gvol_name, peers):
        """
        This method will initialize the ctdb directory responsible for storing
        files used by ctdb daemon for cluster operations. Without this directory,
        ctdb daemon and therefore SMB active-active shares will not work.

        We use the native gluster file I/O API via the pyglfs module. This means
        we don't need to go through a local fuse mount.

        Also, since this directory is stored at the root of the gluster volume, it's
        imperative that we protect this directory via permissions. We lock this down
        to only root user and nobody else may access it.
        """
        # create the top level dir and set perms appropriately
        self.create_dir_and_set_perms(gvol_name)

        # The peers in the TSP could be using dns names while ctdb
        # only accepts IP addresses. This means we need to resolve
        # the hostnames of the peers in the TSP to their respective
        # IP addresses so we can write them to the ctdb private ip file.
        ips = self.middleware.call_sync('cluster.utils.resolve_hostnames', peers)
        if len(peers) != len(ips):
            # this means the gluster peers hostnames resolved to the same
            # ip address which is bad....in theory, this shouldn't occur
            # since adding gluster peers has it's own validation and would
            # cause it to fail way before this gets called but it's better
            # to be safe than sorry
            raise CallError('Duplicate gluster peer IP addresses detected.')

        # everything below here requires the local FUSE mount to be functional
        # so let's be sure to wait for it if it's currently running
        fuse_mount_job = self.middleware.call_sync('core.get_jobs', [
            ('method', '=', 'gluster.fuse.mount'),
            ('arguments.0.name', '=', gvol_name),
            ('state', '=', 'RUNNING')
        ])
        if fuse_mount_job:
            self.middleware.call_sync('core.job_wait', fuse_mount_job[0]['id']).wait_sync()

        # ctdb daemon needs, minimally, private ips to be added to it's config
        # before the service will start. This does a few things underneath the hood
        #   1. adds private ips to the /etc/ctdb/nodes file
        #   2. symlinks /etc/ctdb/nodes to /cluster/`gvol_name`/nodes
        for peer in peers:
            peer_job = await self.middleware.call('ctdb.private.ips.create', {'ip': peer})
            await peer_job.wait()

        # Initialize clustered secrets
        if not self.middleware.call_sync('clpwenc.check'):
            self.logger.debug('Generating clustered pwenc secret')
            self.middleware.call_sync('clpwenc.generate_secret')

        # finally, we need to send an event telling all peers in the TSP (including this system)
        # to start the ctdb service
        data = {'event': 'CTDB_START', 'name': gvol_name, 'forward': True}
        await self.middleware.call('gluster.localevents.send', data)

    def set_location(self, gvol_name):
        """
        This will create a file that stores the `gvol_name` for which we've created
        and stored the ctdb daemon configuration.
        """
        with open(CTDBConfig.CTDB_ROOT_DIR_LOCATION.value, 'w') as f:
            f.write(gvol_name)

    def get_location(self):
        try:
            with open(CTDBConfig.CTDB_ROOT_DIR_LOCATION.value) as f:
                gvol_name = f.read().strip()
        except FileNotFoundError:
            return None
        else:
            return gvol_name
