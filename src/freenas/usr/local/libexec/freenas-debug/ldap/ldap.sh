#!/bin/sh
NSLCD_CONF=${NSLCD_CONF:-"/etc/nslcd.conf"}
LDAP_CONF=${LDAP_CONF:-"/etc/openldap/ldap.conf"}
ldap_opt() { echo l; }
ldap_help() { echo "Dump LDAP Configuration"; }
ldap_directory() { echo "LDAP"; }
ldap_func()
{
	local CONF=$(midclt call ldap.config | jq 'del(.bindpw)')
	local onoff=$(echo ${CONF} | jq ".enable")
	local has_samba_schema=$(echo ${CONF} | jq ".has_samba_schema")

	enabled="DISABLED"
	if [ "${onoff}" = "true" ]
	then
		enabled="ENABLED"
	fi

	section_header "LDAP Status"
	echo "LDAP is ${enabled}"
	section_footer

	#
	#	dump LDAP configuration
	#
	section_header "LDAP Settings"
	echo ${CONF} | jq
	section_footer

	#
	#	Dump nsswitch.conf
	#
	section_header "${PATH_NS_CONF}"
	sc "${PATH_NS_CONF}"
	section_footer

	#
	#	Dump kerberos configuration
	#
	section_header "${PATH_KRB5_CONFIG}"
	sc "${PATH_KRB5_CONFIG}" 2>/dev/null
	section_footer

	#
	#	List kerberos tickets
	#
	section_header "Kerberos Tickets - 'klist'"
	klist
	section_footer

	#
	#	List kerberos tickets
	#
	section_header "Kerberos keytab system"
	klist -ket
	section_footer

	#
	#	Dump OpenLDAP configuration
	#
	section_header "${LDAP_CONF}"
	sc "${LDAP_CONF}"
	section_footer

	#
	#	Dump NSLCD configuration
	#
	section_header "${NSLCD_CONF}"
	sc "${NSLCD_CONF}" | grep -iv bindpw
	section_footer

	section_header "ROOT DSE"
	midclt call ldap.get_root_DSE | jq
	section_footer

	if [ "${enabled}" = "ENABLED" ] && [ "${has_samba_schema}" = "true" ]
	then
	section_header "sambaDomains"
	midclt call ldap.get_samba_domains | jq
	section_footer
	fi

}
