#!/bin/sh
nfs_opt() { echo N; }
nfs_help() { echo "Dump NFS Configuration"; }
nfs_directory() { echo "NFS"; }
nfs_func()
{

	local onoff

        onoff=$(${FREENAS_SQLITE_CMD} ${FREENAS_CONFIG} "
        SELECT
                srv_enable
        FROM
                services_services
        WHERE
                srv_service = 'nfs'
        ORDER BY
                -id
        LIMIT 1
        ")

        enabled="not start on boot."
        if [ "${onoff}" = "1" ]
        then
                enabled="start on boot."
        fi

        section_header "NFS Boot Status"
        echo "NFS will ${enabled}"
        section_footer

	section_header "NFS Service Status"
	systemctl status nfs-server
	section_footer

	section_header "RPC Statd Status"
	systemctl status rpc-statd
	section_footer

	section_header "RPC GSSD Status"
	systemctl status rpc-gssd
	section_footer

	section_header "rpcinfo -p"
	rpcinfo -p
	section_footer

	section_header "NFS Config (/etc/default/nfs-common)"
	sc "/etc/default/nfs-common"
	section_footer

	section_header "NFS Config (/etc/default/nfs-kernel-server)"
	sc "/etc/default/nfs-kernel-server"
	section_footer

	section_header "NFS Config (/etc/exports)"
	sc "/etc/exports"
	section_footer

	section_header "NFS Service Configuration"
	midclt call nfs.config | jq
	section_footer

	sectio_header "NFS Shares Configuration"
	midclt call sharing.nfs.query | jq
	section_footer
}
