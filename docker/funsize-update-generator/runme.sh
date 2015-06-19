#!/bin/sh

set -xe

test $FROM_MAR
test $TO_MAR
test $PLATFORM
test $LOCALE
test $SIGNING_CERT

ARTIFACTS_DIR="/home/worker/artifacts"
mkdir -p "$ARTIFACTS_DIR"

/home/worker/bin/funsize.py \
    --artifacts-dir "$ARTIFACTS_DIR" \
    --from-mar "$FROM_MAR" \
    --to-mar "$TO_MAR" \
    --platform "$PLATFORM" \
    --locale "$LOCALE" \
    --signing-cert "/home/worker/keys/${SIGNING_CERT}.pubkey"
