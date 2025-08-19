FROM z88dk/z88dk:20241014

ENV HOME=/home/zeal8bit

# Dev Tools
RUN echo "Installing prerequisites" \
  && apk update \
  && apk add --no-cache bash git curl python3 py3-pip build-base bison flex zlib-dev boost-dev \
  && apk add --no-cache fuse3 fuse3-libs fuse3-dev pkgconf \
  && apk add --no-cache py3-pillow \
  && python3 -m venv /opt/penv \
  && . /opt/penv/bin/activate \
  && pip3 install kconfiglib \
  && pip3 install cookiecutter

# SDCC
RUN echo "Building SDCC" \
  && mkdir -p /opt/sdcc \
  && curl -L https://sourceforge.net/projects/sdcc/files/sdcc/4.4.0/sdcc-src-4.4.0.tar.bz2/download -o /opt/sdcc/sdcc-4.4.0.tar.bz2 \
  && tar xjf /opt/sdcc/sdcc-4.4.0.tar.bz2 -C /opt/sdcc \
  && cd /opt/sdcc/sdcc-4.4.0 \
  && ./configure \
		--disable-ds390-port --disable-ds400-port \
		--disable-hc08-port --disable-s08-port --disable-mcs51-port \
		--disable-pic-port --disable-pic14-port --disable-pic16-port \
		--disable-tlcs90-port --disable-xa51-port --disable-stm8-port \
		--disable-pdk13-port --disable-pdk14-port \
		--disable-pdk15-port --disable-pdk16-port \
		--disable-mos6502-port --disable-mos65c02-port \
		--disable-r2k-port \
		--disable-non-free \
		--disable-ucsim \
    && make all \
    && ln -s /opt/sdcc/sdcc-4.4.0/bin /opt/sdcc/bin \
    && ln -s /opt/sdcc/sdcc-4.4.0/device/include /opt/sdcc/include \
    && ln -s /opt/sdcc/sdcc-4.4.0/device/lib /opt/sdcc/lib

# --disable-sdcpp --disable-packihx --disable-sdcdb --disable-sdbinutil --disable-device-lib
# => => # /opt/sdcc/src/sdcc-build/bin/sdcc -I./../../include -I. --std-c23  -mr2ka --max-allocs-per-node 25000 -c ../_sint2fs.c -o _sint2fs

ENV \
  ZDE="true" \
  ZOS_PATH="$HOME/Zeal-8-bit-OS" \
  ZVB_SDK_PATH="$HOME/Zeal-VideoBoard-SDK" \
  ZGDK_PATH="$HOME/zeal-game-dev-kit" \
  SDCC_PATH="/opt/sdcc" \
  PYTHON_BIN="/opt/penv/bin"

ENV \
  # CPATH="$SDCC_PATH/include" \
  # LIBRARY_PATH="$SDCC_PATH/lib" \
  PATH="$PATH:$ZOS_PATH/tools:$ZVB_SDK_PATH/tools/zeal2gif:$SDCC_PATH/bin"

# # Zeal 8-bit Repos
# RUN echo "Cloning repos" \
#   && git clone --depth=1 --recurse-submodules --shallow-submodules https://github.com/Zeal8bit/Zeal-Bootloader.git ${HOME}/Zeal-Bootloader \
#   && git clone --depth=1 --recurse-submodules --shallow-submodules https://github.com/Zeal8bit/Zeal-8-bit-OS.git ${HOME}/Zeal-8-bit-OS \
#   && git clone --depth=1 --recurse-submodules --shallow-submodules https://github.com/Zeal8bit/ZealFS.git ${HOME}/ZealFS \
#   && git clone --depth=1 --recurse-submodules --shallow-submodules https://github.com/Zeal8bit/Zeal-VideoBoard-SDK.git ${HOME}/Zeal-VideoBoard-SDK \
#   && git clone --depth=1 --recurse-submodules --shallow-submodules https://github.com/Zeal8bit/Zeal-WebEmulator.git ${HOME}/Zeal-WebEmulator

# ZealFS
RUN echo "Setting up ZealFS" \
  && apk add --no-cache rsync \
  && mkdir -p /media/zealfs

RUN echo "Installing supervisord" \
  && apk add --no-cache nodejs npm supervisor \
  && mkdir -p /var/log/supervisor \
  && mkdir -p /etc/supervisor.d
COPY etc/supervisord.conf /etc/supervisord.conf
COPY etc/supervisor.d/emulator.ini /etc/supervisor.d/emulator.ini
COPY etc/supervisor.d/playground.ini /etc/supervisor.d/playground.ini

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

WORKDIR /src/
ENTRYPOINT ["/entrypoint.sh"]

