#!/bin/sh
system_opt() { echo t; }
system_help() { echo "Dump System Information"; }
system_directory() { echo "System"; }
system_func()
{
	section_header "uptime"
	uptime
	section_footer

	section_header "date"
	date
	section_footer

	section_header "ntpq -c rv"
	ntpq -c rv
	section_footer

	section_header "ntpq -pwn"
	ntpq -pwn
	section_footer

	section_header "ps -auxwwf"
	ps -auxwwf
	section_footer

	section_header "mount"
	mount
	section_footer

	section_header "df -T -h"
	df -T -h
	section_footer

	section_header "swapon -s"
	swapon -s
	section_footer

	section_header "lsmod"
	lsmod
	section_footer

	section_header "dmesg -Tx"
	dmesg -Tx
	section_footer

	section_header "vmstat"
	vmstat
	section_footer

	section_header "top -SHbi -d1 -n2"
	top -SHbi -d1 -n2
	section_footer

	section_header "Current Alerts (midclt call alert.list)"
	midclt call alert.list | jq .
	section_footer

	section_header "Core files (midclt call system.coredumps)"
	for row in $(midclt call "system.coredumps" | jq -r ".[] | @base64"); do
		_jq() {
			echo ${row} | base64 --decode | jq -r ${1}
		}

		if [ "$(_jq '.corefile')" = "present" ]; then
			coredumpctl info "$(_jq '.pid')"
			echo
			echo
			echo
		fi
	done
	section_footer

	section_header "Dump configuration (midclt call system.general.config and system.advanced.config)"
	midclt call system.general.config | jq 'del(.ui_certificate.privatekey?, .ui_certificate.signedby.privatekey?, .ui_certificate.issuer.privatekey?)'
	midclt call system.advanced.config | jq 'del(.sed_user, .sed_passwd)'
	section_footer

	section_header "Middleware Jobs - 'midclt call core.get_jobs'"
	midclt call core.get_jobs '[["state", "!=", "SUCCESS"]]' '{"extra": {"raw_result": false}}' | jq .
	section_footer

	section_header "Middleware Websocket Incoming/Outgoing Message(s) - 'midclt call core.get_websocket_messages'"
	midclt call core.get_websocket_messages | jq .
	section_footer

	section_header "Middleware Asyncio Loop Tasks - 'midclt call core.get_tasks'"
	midclt call core.get_tasks | jq .
	section_footer

	section_header "Middleware Threads - 'midclt call core.threads_stacks'"
	midclt call core.threads_stacks | jq .
	section_footer

	if [ -f /data/license ]; then
		section_header "License Information (midclt call system.license)"
		midclt call system.license | jq .
		section_footer
	fi

	ret1=$(midclt call system.is_enterprise)
	if [ "x${ret1}" = "xTrue" ];
	then
		section_header "hactl output"
		hactl
		section_footer
	fi

	section_header "Failed updates /data/update.failed"
	sc /data/update.failed
	section_footer

	section_header "Truecommand connection (midclt call truecommand.connected)"
	midclt call truecommand.connected | jq 'del(.truecommand_ip,.truecommand_url)'
	section_footer
}	
