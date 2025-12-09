FROM z88dk/z88dk:20250825

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

RUN echo "Cleaning up" \
  && rm -rf /opt/sdcc/sdcc-4.4.0.tar.bz2 \
  && rm -rf /opt/sdcc/sdcc-4.4.0 \
  && rm -rf /opt/gnu-as/binutils-2.41.tar.gz \
  && rm -rf /opt/gnu-as/binutils-2.41 \
  && find /opt/z88dk -mindepth 1 -maxdepth 1 ! -path '/opt/z88dk/bin' ! -path '/opt/z88dk/lib' ! -path '/opt/z88dk/include' -exec rm -rf {} +

RUN echo "Stripping" \
  && find /opt/sdcc/bin /opt/gnu-as/bin /opt/z88dk/bin -type f -executable -exec sh -c 'file "$1" | grep -q ELF && strip --strip-unneeded "$1"' _ {} \; 2>/dev/null || true
