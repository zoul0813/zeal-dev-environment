#!/bin/sh

cd /home/zeal8bit/ZealFS && make
mkdir -p /mnt/eeprom
mkdir -p /mnt/cf
mkdir -p /mnt/sd

cd /home/zeal8bit/Zeal-8-bit-OS/packer && make

cd /src

supervisord -c /etc/supervisord.conf

exec "$@"

