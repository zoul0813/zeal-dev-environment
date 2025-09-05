FROM z88dk/z88dk:20250825

ENV HOME=/home/zeal8bit

# Dev Tools
RUN echo "Installing prerequisites" \
  && apk update \
  && apk add --no-cache bash git curl python3 py3-pip build-base cmake bison flex zlib-dev boost-dev \
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
    --prefix=/opt/sdcc \
  && make all \
  && make install

# --disable-sdcpp --disable-packihx --disable-sdcdb --disable-sdbinutil --disable-device-lib
# => => # /opt/sdcc/src/sdcc-build/bin/sdcc -I./../../include -I. --std-c23  -mr2ka --max-allocs-per-node 25000 -c ../_sint2fs.c -o _sint2fs

# GNU AS
RUN echo "Building GNU AS" \
  && mkdir -p /opt/gnu-as \
  && curl -L https://ftp.gnu.org/gnu/binutils/binutils-2.41.tar.gz -o /opt/gnu-as/binutils-2.41.tar.gz \
  && tar xzf /opt/gnu-as/binutils-2.41.tar.gz -C /opt/gnu-as \
  && cd /opt/gnu-as/binutils-2.41 \
  && mkdir build && cd build \
  && ../configure --target=z80-elf --host=x86_64-linux-musl --prefix=/opt/gnu-as --disable-nls \
  && make MAKEINFO=true -j$(nproc) \
  && make MAKEINFO=true install

# ZealFS
RUN echo "Setting up ZealFS" \
  && apk add --no-cache rsync \
  && mkdir -p /media/zealfs

ENV \
  ZDE="true" \
  ZOS_PATH="$HOME/Zeal-8-bit-OS" \
  ZVB_SDK_PATH="$HOME/Zeal-VideoBoard-SDK" \
  ZGDK_PATH="$HOME/zeal-game-dev-kit" \
  SDCC_PATH="/opt/sdcc" \
  GNUAS_PATH="/opt/gnu-as" \
  PYTHON_BIN="/opt/penv/bin" \
  PATH="$PATH:/opt/sdcc/bin:/opt/gnu-as/bin:/home/zeal8bit/Zeal-8-bit-OS/tools:/home/zeal8bit/Zeal-VideoBoard-SDK/tools/zeal2gif"


RUN echo "Installing supervisord" \
  && apk add --no-cache nodejs npm \
  && . /opt/penv/bin/activate \
  && pip3 install --upgrade "setuptools<81" supervisor \
  && mkdir -p /var/log/supervisor \
  && mkdir -p /etc/supervisor.d
COPY etc/supervisord.conf /etc/supervisord.conf
COPY etc/supervisor.d/emulator.ini /etc/supervisor.d/emulator.ini
COPY etc/supervisor.d/playground.ini /etc/supervisor.d/playground.ini

RUN echo "Installing python modules" \
  && . /opt/penv/bin/activate \
  && pip3 install pillow

RUN echo "Installing su-exec" \
  && apk add --no-cache su-exec

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

WORKDIR /src/
ENTRYPOINT ["/entrypoint.sh"]

