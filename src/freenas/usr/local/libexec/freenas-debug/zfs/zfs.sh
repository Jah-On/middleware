#!/bin/sh
zfs_opt() { echo z; }
zfs_help() { echo "Dump ZFS Configuration"; }
zfs_directory() { echo "ZFS"; }
zfs_getacl()
{
	local ds="${1}"
	local parameter
	local val
	local mp

	zfs get -H -o property,value mounted,mountpoint,acltype "${ds}" | while read -r s
	do
		parameter=$(echo -n "$s" | awk '{print $1}' | tr -d '\n')
		val=$(echo -n "$s" | awk '{print $2}' | tr -d '\n')
		case "${parameter}" in
		mountpoint)
			if [ "${val}" = "legacy" ] || [ "${val}" = "-" ]; then
				return 0
			fi
			mp=$(echo -n "${val}")
			;;
		mounted)
			if [ "${val}" = "no" ] || [ "${val}" = "-" ]; then
				return 0
			fi
			;;
		acltype)
			echo "Mountpoint ACL: ${ds}"
			if [ ${val} = "nfsv4" ]; then
				nfs4xdr_getfacl "${mp}"
			else
				getfacl "${mp}"
			fi
			;;
		*)
			echo "Unexpected parameter: ${parameter}"
			return 0
			;;
		esac
	done

	return 0
}
zfs_kstat()
{
	local kstat=${1}

	section_header "kstat ${kstat}"
	cat /proc/spl/kstat/zfs/${kstat}
	section_footer
}

zfs_func()
{
	section_header "zfs periodic snapshot tasks"
	${FREENAS_SQLITE_CMD} ${FREENAS_CONFIG} -line "
	SELECT *
	FROM storage_task
	ORDER BY +id"
	section_footer

	section_header "zfs replication tasks"
	${FREENAS_SQLITE_CMD} ${FREENAS_CONFIG} -line "
	SELECT *
	FROM storage_replication
	ORDER BY +id"
	section_footer

	section_header "zfs replication tasks to periodic snapshot tasks"
	${FREENAS_SQLITE_CMD} ${FREENAS_CONFIG} -line "
	SELECT *
	FROM storage_replication_repl_periodic_snapshot_tasks
	ORDER BY +id"
	section_footer

	section_header "zpool scrub"
	${FREENAS_SQLITE_CMD} ${FREENAS_CONFIG} -line "
	SELECT *
	FROM storage_scrub
	WHERE id >= '1'
	ORDER BY +id"
	section_footer
	
	section_header "zpool list -v"
	zpool list -v
	section_footer

	section_header "zfs list -ro space,refer,mountpoint"
	zfs list -ro space,refer,mountpoint
	section_footer

	section_header "zpool status -v"
	zpool status -v
	section_footer

	section_header "zpool history"
	zpool history
	section_footer

	section_header "zpool history -i | tail -n 1000"
	zpool history -i | tail -n 1000
	section_footer

	section_header "zpool get all"
	for pool in $(zpool list -Ho name); do
		section_header "${pool}"
		zpool get all ${pool}
		section_footer
	done
	section_footer

	section_header "zfs list -t snapshot"
	zfs list -t snapshot -o name,used,available,referenced,mountpoint,freenas:state
	section_footer

	section_header "zfs get all"
	zfs list -o name -H | while read -r dataset
	do
		section_header "${dataset}"
		zfs get all "${dataset}"
		zfs_getacl "${dataset}"
		section_footer
	done
	section_footer

	section_header "lsblk -o NAME,FSTYPE,LABEL,UUID,PARTUUID -l -e 230"
	lsblk -o NAME,FSTYPE,LABEL,UUID,PARTUUID -l -e 230
	section_footer
	section_header  "zpool status -v"
	zpool status -v
	section_footer
	section_header  "zpool status -g"
	zpool status -g
	section_footer

	for pool in $(zpool list -Ho name | grep -v -e "$(midclt call boot.pool_name)"); do
		section_header "${pool} Pool Encryption Summary"
		midclt call -job -jp description pool.dataset.encryption_summary "${pool}" | jq .
		section_footer
	done

	section_header "kstat"
	zfs_kstat "fletcher_4_bench"
	zfs_kstat "vdev_raidz_bench"
	zfs_kstat "dbgmsg"
	for pool in $(zpool list -Ho name); do
		zfs_kstat "${pool}/state"
		zfs_kstat "${pool}/multihost"
		zfs_kstat "${pool}/txgs"
	done
	section_footer
}
