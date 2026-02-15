#!/bin/bash

SCRIPTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

print_templates()
{
    local prefix="$1"
    # List directories (or scripts) inside SCRIPTS_DIR
    for dir in "$SCRIPTS_DIR"/*/ ; do
        [ -d "$dir" ] || continue  # skip if not a directory
        echo -e "${prefix}$(basename "$dir")"
    done
}

if [ $# -eq 0 ]; then
    echo "# ZDE Create Project"
    echo -e "Usage: zde create <template-name> name=<project-name> [args...]\n"
    echo -e "Available Templates:\n"

    print_templates "    > "
    echo ""
    exit 0
fi

if [ $# -eq 1 ] && [ "$1" = '-t' ]; then
    print_templates "template: "
    exit 0
fi

# activate the python env
. /opt/penv/bin/activate

OUT_DIR="${ZDE_CREATE_OUT:-/tmp}"
printf -v escaped_args "%q " "$@"
CMD="cookiecutter --no-input -f -o $OUT_DIR $escaped_args"
eval $CMD
