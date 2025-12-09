FROM zoul0813/zde-builder:latest as builder
FROM alpine:latest
COPY --from=builder /opt /opt

ENV \
  HOME=/home/zeal8bit \
  Z88DK_PATH="/opt/z88dk" \
  SDCC_PATH="/opt/sdcc" \
  GNUAS_PATH="/opt/gnu-as"

# Dev Tools
RUN echo "Installing prerequisites" \
  && apk update \
  && apk add --no-cache \
    bash \
    git \
    curl \
    python3 \
    py3-pip \
    build-base \
    cmake \
    su-exec \
    sudo \
    fuse3 \
    fuse3-libs \
    fuse3-dev \
    pkgconf \
    rsync \
  && python3 -m venv /opt/penv \
  && . /opt/penv/bin/activate \
  && pip3 install kconfiglib \
  && pip3 install cookiecutter \
  && pip3 install pillow \
  && pip3 install --upgrade "setuptools<81" supervisor \
  && mkdir -p /var/log/supervisor

ENV \
  ZDE="true" \
  ZCCCFG="${Z88DK_PATH}/lib/config/" \
  ZOS_PATH="$HOME/Zeal-8-bit-OS" \
  ZVB_SDK_PATH="$HOME/Zeal-VideoBoard-SDK" \
  ZGDK_PATH="$HOME/zeal-game-dev-kit" \
  PYTHON_BIN="/opt/penv/bin" \
  PATH="$PATH:${Z88DK_PATH}/bin:${PATH}:${SDCC_PATH}/bin:${GNUAS_PATH}/bin:${HOME}/Zeal-8-bit-OS/tools:${HOME}/Zeal-VideoBoard-SDK/tools/zeal2gif"

COPY etc/ /etc/


# ZealFS
RUN echo "Configuring" \
  && mkdir -p /media/zealfs \
  && chmod 777 /media/zealfs \
  && echo "zeal8bit ALL=(ALL) NOPASSWD: ALL" > /etc/sudoers.d/zeal8bit \
  && chmod 0440 /etc/sudoers.d/zeal8bit

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

WORKDIR /src/
ENTRYPOINT ["/entrypoint.sh"]

