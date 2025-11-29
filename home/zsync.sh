#!/bin/sh

IMAGE_NAME=$1
IMAGE_SIZE=$2

echo "Image Name: " $IMAGE_NAME
echo "Image Size: " $IMAGE_SIZE

if [ ! -f /home/zeal8bit/ZealFS/zealfs ]; then
  echo "Building ZealFS"
  ZEALFS_HOME=/home/zeal8bit/ZealFS
  cmake -S $ZEALFS_HOME -B $ZEALFS_HOME/build && cmake --build $ZEALFS_HOME/build \
  && mv $ZEALFS_HOME/build/zealfs $ZEALFS_HOME/zealfs \
  && rm -rf $ZEALFS_HOME/build
fi

mkdir -p /mnt/eeprom
mkdir -p /mnt/cf
mkdir -p /mnt/sd

case $IMAGE_NAME in
  cf)
    echo $@
    ls -l /mnt/cf/**
    /home/zeal8bit/Zeal-8-bit-OS/packer/pack /mnt/$IMAGE_NAME.img /mnt/cf/*.* /mnt/cf/**/*.*
    ;;
  *)
    set -- -v2 --image=/mnt/$IMAGE_NAME.img --size=$IMAGE_SIZE
    if [ "$IMAGE_NAME" = "tf" ]; then
      set -- "$@" --mbr
    fi
    sudo /home/zeal8bit/ZealFS/zealfs "$@" /media/zealfs/ \
    && sudo rsync -ruLkv --temp-dir=/tmp --no-perms --whole-file --delete /mnt/$IMAGE_NAME/ /media/zealfs/ \
    && sudo umount /media/zealfs/
    ;;
esac

