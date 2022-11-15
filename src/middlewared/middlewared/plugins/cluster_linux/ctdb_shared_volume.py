import errno

from glustercli.cli import volume

from middlewared.service import Service, CallError, job
from middlewared.plugins.cluster_linux.utils import CTDBConfig


MOUNT_UMOUNT_LOCK = CTDBConfig.MOUNT_UMOUNT_LOCK.value
CRE_OR_DEL_LOCK = CTDBConfig.CRE_OR_DEL_LOCK.value
CTDB_VOL_NAME = CTDBConfig.CTDB_VOL_NAME.value
CTDB_LOCAL_MOUNT = CTDBConfig.CTDB_LOCAL_MOUNT.value


class CtdbSharedVolumeService(Service):

    class Config:
        namespace = 'ctdb.shared.volume'
        private = True

    async def validate(self):
        filters = [('id', '=', CTDB_VOL_NAME)]
        ctdb = await self.middleware.call('gluster.volume.query', filters)
        if not ctdb:
            # it's expected that ctdb shared volume exists when
            # calling this method
            raise CallError(f'{CTDB_VOL_NAME} does not exist', errno.ENOENT)

        for i in ctdb:
            err_msg = f'A volume named "{CTDB_VOL_NAME}" already exists '
            if i['type'] != 'REPLICATE':
                err_msg += (
                    'but is not a "REPLICATE" type volume. '
                    'Please delete or rename this volume and try again.'
                )
                raise CallError(err_msg)
            elif i['replica'] < 3 or i['num_bricks'] < 3:
                err_msg += (
                    'but is configured in a way that '
                    'could cause data corruption. Please delete '
                    'or rename this volume and try again.'
                )
                raise CallError(err_msg)

    @job(lock=CRE_OR_DEL_LOCK)
    async def create(self, job):
        """
        We no longer have a gluster volume dedicated to ctdb but this
        method has been left for backwards compatibility with TC api.

        This is now a no-op by design. This plugin has always been private
        so no one (ideally) should be consuming it. If they are, well, that's
        the entire point of a private API...it can change without notice.
        """
        return

    @job(lock=CRE_OR_DEL_LOCK)
    async def teardown(self, job):
        """
        If this method is called, it's expected that the end-user knows what they're doing. They
        also expect that this will _PERMANENTLY_ delete all the ctdb shared volume information. We
        also disable the glusterd service since that's what SMB service uses to determine if the
        system is in a "clustered" state. This method _MUST_ be called on each node in the cluster
        to fully "teardown" the cluster config.

        NOTE: THERE IS NO COMING BACK FROM THIS.
        """
        for vol in await self.middleware.call('gluster.volume.query'):
            if vol['name'] != CTDB_VOL_NAME:
                # If someone calls this method, we expect that all other gluster volumes
                # have been destroyed
                raise CallError(f'{vol["name"]!r} must be removed before deleting {CTDB_VOL_NAME!r}')
        else:
            # we have to stop gluster service because it spawns a bunch of child processes
            # for the ctdb shared volume. This also stops ctdb, smb and unmounts all the
            # FUSE mountpoints.
            job.set_progress(50, 'Stopping cluster services')
            await self.middleware.call('service.stop', 'glusterd')

        job.set_progress(75, 'Removing cluster related configuration files and directories.')
        teardown_job = await self.middleware.call('cluster.utils.teardown_cluster')
        await teardown_job.wait()

        job.set_progress(99, 'Disabling cluster service')
        await self.middleware.call('service.update', 'glusterd', {'enable': False})

        job.set_progress(100, 'CTDB shared volume teardown complete.')

    @job(lock=CRE_OR_DEL_LOCK)
    async def delete(self, job):
        """
        Delete and unmount the shared volume used by ctdb daemon.
        """
        # nothing to delete if it doesn't exist
        info = await self.middleware.call('gluster.volume.exists_and_started', CTDB_VOL_NAME)
        if not info['exists']:
            return

        # stop the gluster volume
        if info['started']:
            options = {'args': (CTDB_VOL_NAME,), 'kwargs': {'force': True}}
            job.set_progress(33, f'Stopping gluster volume {CTDB_VOL_NAME!r}')
            await self.middleware.call('gluster.method.run', volume.stop, options)

        # finally, we delete it
        job.set_progress(66, f'Deleting gluster volume {CTDB_VOL_NAME!r}')
        await self.middleware.call('gluster.method.run', volume.delete, {'args': (CTDB_VOL_NAME,)})
        job.set_progress(100, f'Successfully deleted {CTDB_VOL_NAME!r}')
