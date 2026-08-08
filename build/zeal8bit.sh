#!/bin/sh

set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPOSITORY=${ZEAL8BIT_REPOSITORY:-https://github.com/TurBoss/z88dk.git}
BRANCH=${ZEAL8BIT_REF:-zeal8bit}
CHECKOUT=${ZEAL8BIT_CHECKOUT:-$SCRIPT_DIR/z88dk}

fetch_sources() {
    if [ ! -d "$CHECKOUT/.git" ]; then
        if [ -e "$CHECKOUT" ]; then
            echo "error: $CHECKOUT exists but is not a Git checkout" >&2
            exit 1
        fi

        git clone --depth 1 --single-branch --branch "$BRANCH" "$REPOSITORY" "$CHECKOUT"
        return
    fi

    if [ -n "$(git -C "$CHECKOUT" status --porcelain)" ]; then
        echo "error: $CHECKOUT has local changes; refusing to update" >&2
        exit 1
    fi

    git -C "$CHECKOUT" fetch origin "$BRANCH"

    current_branch=$(git -C "$CHECKOUT" branch --show-current)
    if [ -z "$current_branch" ]; then
        if ! git -C "$CHECKOUT" switch "$BRANCH"; then
            echo "error: $CHECKOUT has detached HEAD and no local '$BRANCH' branch" >&2
            exit 1
        fi
        current_branch=$BRANCH
    fi

    if [ "$current_branch" != "$BRANCH" ]; then
        echo "error: $CHECKOUT is on branch '$current_branch', expected '$BRANCH'" >&2
        exit 1
    fi

    git -C "$CHECKOUT" merge --ff-only FETCH_HEAD
}

install_target() {
    source_root=${ZEAL8BIT_SOURCE_ROOT:-$CHECKOUT}
    z88dk_root=${Z88DK_ROOT:-/opt/z88dk}
    libsrc_makefile=$z88dk_root/libsrc/Makefile

    if [ ! -f "$source_root/lib/config/zeal8bit.cfg" ]; then
        echo "error: Zeal target config missing below $source_root" >&2
        exit 1
    fi

    if [ ! -f "$z88dk_root/build.sh" ] || [ ! -f "$libsrc_makefile" ]; then
        echo "error: $z88dk_root is not a z88dk source tree" >&2
        exit 1
    fi

    mkdir -p "$z88dk_root/lib/config"
    cp "$source_root/lib/config/zeal8bit.cfg" "$z88dk_root/lib/config/zeal8bit.cfg"

    for relative_dir in lib/target/zeal8bit libsrc/target/zeal8bit; do
        mkdir -p "$z88dk_root/$relative_dir"
        cp -R "$source_root/$relative_dir/." "$z88dk_root/$relative_dir/"
    done

    if ! grep -Fq 'check_target,zeal8bit,' "$libsrc_makefile"; then
        sed -i '/check_target,zx,/i\
TOCREATE += $(call check_target,zeal8bit, zeal8bit_clib.lib)' "$libsrc_makefile"
    fi

    if ! grep -Fq 'include target/zeal8bit/zeal8bit.mak' "$libsrc_makefile"; then
        sed -i '/include target\/zx\/zx.mak/i\
include target/zeal8bit/zeal8bit.mak' "$libsrc_makefile"
    fi

    if ! grep -Fq 'zeal8bit_clib.lib:' "$libsrc_makefile"; then
        sed -i '/^install:/i\
zeal8bit_clib.lib: $(TARGET_CLIB_DEPS) $(ZEAL8BIT_TARGETS)\
\t@echo ""\
\t@echo "--- Building Zeal 8 bit Library ---"\
\t@echo ""\
\t$(call buildgeneric,zeal8bit,"wide")\
\t$(MAKE) -C classic/games TARGET=zeal8bit\
\tTARGET=zeal8bit TYPE=z80 $(LIBLINKER) -mz80 -DFORzeal8bit -DSTANDARDESCAPECHARS -x$(OUTPUT_DIRECTORY)/zeal8bit_clib @$(TARGET_DIRECTORY)/zeal8bit/zeal8bit.lst\
\
' "$libsrc_makefile"
    fi

    make -C "$z88dk_root/libsrc" zeal8bit_clib.lib
    make -C "$z88dk_root/libsrc" install
}

case ${1:-} in
    fetch)
        fetch_sources
        ;;
    install)
        install_target
        ;;
    *)
        echo "usage: $0 fetch|install" >&2
        exit 2
        ;;
esac
