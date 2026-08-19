#!/bin/sh
set -eu

mkdir -p /opt/libredwg
cp -a /opt/libredwg-dist/. /opt/libredwg/

exec "$@"