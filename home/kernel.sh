#!/usr/bin/env bash

## Currently uses the deprecated Makefile as `config=configs/zeal8bit.default`
## is unsupported with Cmake

FULLBIN="build/os_with_romdisk.img"
STATBYTES="stat -c %s"
KERNEL_CONFIG="configs/${1}.default"
shift

echo "Zeal 8-bit Kernel Compiler"
echo "Building " $KERNEL_CONFIG "for" $ZEAL_KERNEL_VERSION
cd $ZOS_PATH
make config=$KERNEL_CONFIG
echo -e "\n"
STATSIZE=$($STATBYTES $FULLBIN)


mkdir -p /mnt/roms

if [ "$STATSIZE" -gt 0 ]; then
  ROM_PATH="/mnt/roms/zeal8bit-${ZEAL_KERNEL_VERSION}.img"
  cp "$FULLBIN" "$ROM_PATH"
  echo "Copied to $ROM_PATH"
else
  echo "Build failed: $FULLBIN has size 0"
  exit 1
fi
