#!/bin/sh
ssl_opt() { echo s; }
ssl_help() { echo "Dump SSL Configuration"; }
ssl_directory() { echo "SSL"; }
ssl_func()
{
	section_header "/etc/ssl"
	find /etc/ssl -print0 | xargs -0 ls -l
	section_footer

	section_header "/etc/certificates"
	find /etc/certificates -print0 | xargs -0 ls -l
	section_footer

	section_header "/etc/ssl/openssl.cnf"
	sc /etc/ssl/openssl.cnf
	section_footer
}
