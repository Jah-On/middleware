#!/bin/sh
sysctl_opt() { echo y; }
sysctl_help() { echo "Dump Sysctl Configuration"; }
sysctl_directory() { echo "Sysctl"; }
sysctl_func()
{
	section_header "/etc/sysctl.conf"
	sc "/etc/sysctl.conf"
	section_footer

	section_header "sysctl -a"
	sysctl -a
	section_footer
}

