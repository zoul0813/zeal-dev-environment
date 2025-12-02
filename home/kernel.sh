#!/usr/bin/env bash

## Currently uses the deprecated Makefile as `config=configs/zeal8bit.default`
## is unsupported with Cmake

FULLBIN="build/os_with_romdisk.img"
STATBYTES="stat -c %s"

echo "Zeal 8-bit Kernel Compiler"
cd $ZOS_PATH

SHOW_STAT=1
if [ "$1" = "user" ]; then
  KERNEL_CONFIG=""
  MAKE_CONFIG_ARG=""
elif [ "$1" = "menuconfig" ]; then
  echo "Launching menuconfig"
  MAKE_CONFIG_ARG="menuconfig"
  SHOW_STAT=0
else
  KERNEL_CONFIG="configs/${1}.default"
  MAKE_CONFIG_ARG="config=$KERNEL_CONFIG"
  echo "Building " $KERNEL_CONFIG "for" $ZEAL_KERNEL_VERSION
fi
shift

make $MAKE_CONFIG_ARG

if [ $SHOW_STAT = 1 ]; then
  echo -e "\n"
  STATSIZE=$($STATBYTES $FULLBIN)

  if [ "$STATSIZE" -gt 0 ]; then
    ROM_PATH="/mnt/roms/zeal8bit-${ZEAL_KERNEL_VERSION}.img"
    cp "$FULLBIN" "$ROM_PATH"
    echo "Copied to $ROM_PATH"
  else
    echo "Build failed: $FULLBIN has size 0"
    exit 1
  fi
fi
