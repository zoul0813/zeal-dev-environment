#!/bin/bash

# activate the python env
. /opt/penv/bin/activate

printf -v escaped_args "%q " "$@"
CMD="cookiecutter --no-input -f -o /tmp $escaped_args"
eval $CMD
