#!/bin/sh

. /opt/penv/bin/activate

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

supervisord -c /etc/supervisord.conf

cd /src

HOST_UID=${HOST_UID:-1000}
HOST_GID=${HOST_GID:-1000}
USERNAME=zeal8bit

# 1. Check if a group with the desired GID exists
EXISTING_GROUP=$(getent group $HOST_GID | cut -d: -f1)

if [ -z "$EXISTING_GROUP" ]; then
    # No existing group with that GID → create one
    GROUPNAME=$USERNAME
    addgroup -g $HOST_GID $GROUPNAME
else
    # Use the existing group name
    GROUPNAME=$EXISTING_GROUP
fi

# 2. Create the user if it doesn't exist
if ! id -u $USERNAME >/dev/null 2>&1; then
    adduser -u $HOST_UID -G $GROUPNAME -D $USERNAME
fi

if [ "$1" = "/bin/bash" ]; then
    if [ -f /home/zeal8bit/motd.txt ]; then
        cat /home/zeal8bit/motd.txt
    fi
fi

export PS1="($CONTAINER_ID_SHORT) \u:\w\$ "

chown $HOST_UID:$HOST_GID /home/zeal8bit

# If no command is passed, default to bash
if [ $# -eq 0 ]; then
    exec su-exec "$USERNAME" /bin/bash
else
    # Run arbitrary command safely
    exec su-exec "$USERNAME" "$@"
fi
