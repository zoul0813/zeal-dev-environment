#!/bin/sh

if [ ! -f /home/zeal8bit/ZealFS/zealfs ]; then
  echo "Building ZealFS"
  cd /home/zeal8bit/ZealFS && make
fi

mkdir -p /mnt/eeprom
mkdir -p /mnt/cf
mkdir -p /mnt/sd

if [ ! -f /home/zeal8bit/Zeal-8-bit-OS/packer/pack ]; then
  echo "Building Packer"
  cd /home/zeal8bit/Zeal-8-bit-OS/packer && make
fi

cd /src

supervisord -c /etc/supervisord.conf

exec "$@"

