#!/usr/bin/env bash

# set -x

FULLBIN="build/os_with_romdisk.img"
STATBYTES="stat -c %s"

echo "Zeal 8-bit Kernel Compiler"
cd $ZOS_PATH

SHOW_STAT=1
KERNEL_CONFIG=""
CONFIG_ARG=""
if [ "$1" = "user" ]; then
  KERNEL_CONFIG=""
  MAKE_CONFIG_ARG=""
elif [ "$1" = "default" ]; then
  echo "Creating default config"
  rm -rf $ZOS_PATH/os.conf
  BUILD_ARG="--target alldefconfig"
  SHOW_STAT=0
elif [ "$1" = "menuconfig" ]; then
  echo "Launching menuconfig"
  BUILD_ARG="--target menuconfig"
  SHOW_STAT=0
else
  KERNEL_CONFIG="configs/${1}.default"
  CONFIG_ARG="-Dconfig=$KERNEL_CONFIG"
  echo "Building " $KERNEL_CONFIG "for" $ZEAL_KERNEL_VERSION
fi
shift


cmake -B build $CONFIG_ARG
cmake --build build $BUILD_ARG

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
