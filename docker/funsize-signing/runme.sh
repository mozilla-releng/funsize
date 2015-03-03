#!/bin/sh

set -xe

test $PARENT_TASK_ARTIFACTS_URL_PREFIX

ARTIFACTS_DIR="/home/worker/artifacts"
mkdir -p "$ARTIFACTS_DIR"

wget -O /home/worker/manifest.json "$PARENT_TASK_ARTIFACTS_URL_PREFIX/manifest.json"
cat /home/worker/manifest.json

/home/worker/bin/sign_partial_mar.py \
    --artifacts-url-prefix "$PARENT_TASK_ARTIFACTS_URL_PREFIX" \
    --manifest /home/worker/manifest.json \
    --artifacts-dir "$ARTIFACTS_DIR"
