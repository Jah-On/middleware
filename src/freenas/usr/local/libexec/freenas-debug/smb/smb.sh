#!/bin/sh
SMBCONF=${SAMBA_CONF:-"/etc/smb4.conf"}
SMBSHARECONF=${SAMBA_SHARE_CONF:-"/etc/smb4_share.conf"}
smb_opt() { echo C; }
smb_help() { echo "Dump SMB Configuration"; }
smb_directory() { echo "SMB"; }
smb_func()
{
	local workgroup
	local netbiosname
	local adminname
	local domainname
	local dcname
	local pamfiles
	local onoff


	onoff=$(${FREENAS_SQLITE_CMD} ${FREENAS_CONFIG} "
	SELECT
		srv_enable
	FROM
		services_services
	WHERE
		srv_service = 'cifs'
	ORDER BY
		-id
	LIMIT 1
	")

	enabled="not start on boot."
	if [ "${onoff}" = "1" ]
	then
		enabled="start on boot."
	fi

	section_header "SMB Boot Status"
	echo "SMB will ${enabled}"
	section_footer

	#
	#	Dump samba version
	#
	section_header "smbd -V"
	smbd -V
	section_footer


	#
	#	Dump samba configuration
	#
	section_header "${SMBCONF}"
	sc "${SMBCONF}"
	section_footer

	section_header "GLOBAL configuration"
	net conf showshare global
	section_footer

	#
	#	Dump SMB shares
	#
	section_header "SMB Shares & Permissions"
	SHARES=$(midclt call sharing.smb.query)
	echo ${SHARES} | jq -c '.[]' | while read i; do
		cifs_path=$(echo ${i} | jq -r '.path')
		cifs_name=$(echo ${i} | jq -r '.name')
		section_header "${cifs_name}:${cifs_path}"
		net conf showshare ${cifs_name}
		printf "\n"
		ls -ld "${cifs_path}"
		printf "\n"
		acltype=$(midclt call filesystem.getacl "${cifs_path}" true | jq -r '.acltype')
		if [ ${acltype} = "NFS4" ]
		then
			nfs4xdr_getfacl "${cifs_path}"
		else
			getfacl -n "${cifs_path}"
		fi
		printf "\n"
		df -T "${cifs_path}"
		printf "\n"
	done
	section_footer

	#
	#	Dump samba build options
	#
	section_header "smbd -b"
	smbd -b
	section_footer

	section_header "testparm -s"
	testparm -s
	section_footer

	section_header "net getlocalsid"
	net getlocalsid
	section_footer
	section_header "net getdomainsid"
	net getdomainsid
	section_footer
	section_header "middleware groupmap list"
	midclt call smb.groupmap_list | jq
	section_footer

	section_header "net status sessions"
	net status sessions | head -50
	section_footer
	section_header "net status shares"
	net status shares
	section_footer

	section_header "Lock information"
	smbstatus -L | head -50
	section_footer
	
	section_header "ACLs - 'midclt call smb.sharesec.query'"
	midclt call smb.sharesec.query | jq
	section_footer

	section_header "Local users in passdb.tdb"
	midclt call smb.passdb_list true | jq
	section_footer

	section_header "Database Dump"
	midclt call smb.config | jq
	midclt call sharing.smb.query | jq
	section_footer
}
