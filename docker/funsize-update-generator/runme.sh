#!/bin/sh

set -xe

ART_DIR=/home/worker/artifacts
env
mount
df -h
echo "I will create some artifacts in $ART_DIR"

mkdir -p $ART_DIR
env > $ART_DIR/env.txt
