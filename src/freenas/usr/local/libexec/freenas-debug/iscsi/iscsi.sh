#!/bin/sh
iscsi_opt() { echo i; }
iscsi_help() { echo "Dump iSCSI Configuration"; }
iscsi_directory() { echo "iSCSI"; }
iscsi_func()
{
    local onoff

    onoff=$(${FREENAS_SQLITE_CMD} ${FREENAS_CONFIG} "
        SELECT
                srv_enable
        FROM
                services_services
        WHERE
                srv_service = 'iscsitarget'
        ORDER BY
                -id
        LIMIT 1
        ")

    enabled="not start on boot."
    if [ "${onoff}" = "1" ]; then
        enabled="will start on boot."
    fi

    section_header "iSCSI Boot Status"
    echo "iSCSI will ${enabled}"
    section_footer

    section_header "iSCSI Run Status"
    systemctl status scst
    section_footer
	
    alua_enabled=$(${FREENAS_SQLITE_CMD} ${FREENAS_CONFIG} "
	SELECT
		iscsi_alua
	FROM
		services_iscsitargetglobalconfiguration
    ")

    if [ "${alua_enabled}" = "0" ]; then
        section_header "iSCSI ALUA Status"
        echo "ALUA is DISABLED"
    fi

    if [ "${alua_enabled}" = "1" ]; then
        section_header "iSCSI ALUA Status"
        echo "ALUA is ENABLED"
    fi

    section_header "/etc/scst.conf"
    sed -e 's/\(IncomingUser.*"\)\(.*\)\("\)/\1\*****\3/#' -e 's/\(OutgoingUser.*"\)\(.*\)\("\)/\1\*****\3/#' /etc/scst.conf
    section_footer

    section_header "SCST Device Handlers"
    scstadmin -list_handler
    section_footer

    section_header "SCST Devices"
    scstadmin -list_device
    section_footer

    section_header "SCST Drivers"
    scstadmin -list_driver
    section_footer

    section_header "SCST iSCSI Targets"
    scstadmin -list_target -driver iscsi
    section_footer

    section_header "SCST Active Sessions"
    scstadmin -list_sessions
    section_footer

    section_header "SCST Core Attributes"
    scstadmin -list_scst_attr
    section_footer
}
