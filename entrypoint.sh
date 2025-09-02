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

supervisord -c /etc/supervisord.conf

echo "Welcome to Zeal Dev Environment"

exec "$@"

