import os

from middlewared.common.attachment import LockableFSAttachmentDelegate
from middlewared.plugins.zfs_.utils import zvol_name_to_path
from middlewared.utils.path import is_child

from .extents import iSCSITargetExtentService


class ISCSIFSAttachmentDelegate(LockableFSAttachmentDelegate):
    name = 'iscsi'
    title = 'iSCSI Extent'
    service = 'iscsitarget'
    service_class = iSCSITargetExtentService

    async def get_query_filters(self, enabled, options=None):
        return [['type', '=', 'DISK']] + (await super().get_query_filters(enabled, options))

    async def is_child_of_path(self, resource, path):
        dataset_name = os.path.relpath(path, '/mnt')
        full_zvol_path = zvol_name_to_path(dataset_name)
        return is_child(resource[self.path_field], os.path.relpath(full_zvol_path, '/dev'))

    async def delete(self, attachments):
        orphan_targets_ids = set()
        for attachment in attachments:
            for te in await self.middleware.call('iscsi.targetextent.query', [['extent', '=', attachment['id']]]):
                orphan_targets_ids.add(te['target'])
                await self.middleware.call('datastore.delete', 'services.iscsitargettoextent', te['id'])

            await self.middleware.call('datastore.delete', 'services.iscsitargetextent', attachment['id'])
            await self.remove_alert(attachment)

        for te in await self.middleware.call('iscsi.targetextent.query', [['target', 'in', orphan_targets_ids]]):
            orphan_targets_ids.discard(te['target'])
        for target_id in orphan_targets_ids:
            await self.middleware.call('iscsi.target.delete', target_id, True)

        await self._service_change('iscsitarget', 'reload')

    async def restart_reload_services(self, attachments):
        await self._service_change('iscsitarget', 'reload')

    async def stop(self, attachments):
        await self.restart_reload_services(attachments)


async def setup(middleware):
    await middleware.call('pool.dataset.register_attachment_delegate', ISCSIFSAttachmentDelegate(middleware))
