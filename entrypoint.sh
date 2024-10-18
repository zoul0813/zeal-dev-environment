#!/bin/sh

cd /home/zeal8bit/ZealFS \
make
cd /src


exec "$@"

