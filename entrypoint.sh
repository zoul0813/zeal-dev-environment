#!/bin/sh

. /opt/penv/bin/activate

if [ ! -f /home/zeal8bit/ZealFS/zealfs ]; then
  echo "Building ZealFS"
  cd /home/zeal8bit/ZealFS && make
fi

mkdir -p /mnt/eeprom
mkdir -p /mnt/cf
mkdir -p /mnt/sd

cd /src

if [ "$(id -u)" = "0" ]; then
  supervisord -c /etc/supervisord.conf
fi

cat /home/zeal8bit/motd.txt

exec "$@"

