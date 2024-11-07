#!/bin/sh

cd /home/zeal8bit/ZealFS \
make
cd /src

supervisord -c /etc/supervisord.conf

exec "$@"

