#!/bin/sh
db_dump_opt() { echo B; }
db_dump_help() { echo "Dump System Configuration Database"; }
db_dump_directory() { echo "db_dump"; }
db_dump_func()
{

	section_header "System Database Contents"
	${FREENAS_SQLITE_CMD} ${FREENAS_CONFIG} .dump
	section_footer
}
