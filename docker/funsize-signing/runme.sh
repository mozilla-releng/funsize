#!/bin/sh

set -xe

test $PARENT_TASK_ID
test $PARENT_ARTIFACTS_PREFIX

ARTIFACTS_DIR=/home/worker/artifacts
mkdir -p $ARTIFACTS_DIR

/home/worker/bin/sign_partial_mar.py \
    --artifacts-dir "$ARTIFACTS_DIR" \
    --parent-task-id "$PARENT_TASK_ID" \
    --parent-artifacts-prefix "$PARENT_ARTIFACTS_PREFIX"
