#!/bin/bash

SCRIPTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ $# -eq 0 ]; then
    echo "# ZDE Create Project"
    echo -e "Usage: zde create <template-name> name=<project-name> [args...]\n"
    echo -e "Available Templates:\n"

    # List directories (or scripts) inside SCRIPTS_DIR
    for dir in "$SCRIPTS_DIR"/*/ ; do
        [ -d "$dir" ] || continue  # skip if not a directory
        echo -e "    > $(basename "$dir")"
    done
    echo ""
    exit 0
fi

# activate the python env
. /opt/penv/bin/activate

printf -v escaped_args "%q " "$@"
CMD="cookiecutter --no-input -f -o /tmp $escaped_args"
eval $CMD
