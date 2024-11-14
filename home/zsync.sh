#!/bin/sh

IMAGE_NAME=$1
IMAGE_SIZE=$2

echo "Image Name: " $IMAGE_NAME
echo "Image Size: " $IMAGE_SIZE

case $IMAGE_NAME in
  cf)
    echo $@
    ls -l /mnt/cf/**
    /home/zeal8bit/Zeal-8-bit-OS/packer/pack /mnt/$IMAGE_NAME.img /mnt/cf/*.* /mnt/cf/**/*.*
    ;;
  *)
    /home/zeal8bit/ZealFS/zealfs --image=/mnt/$IMAGE_NAME.img --size=$IMAGE_SIZE /media/zealfs/ \
    && rsync -ruLkv --delete /mnt/$IMAGE_NAME/ /media/zealfs/ \
    && umount /media/zealfs/
    ;;
esac

