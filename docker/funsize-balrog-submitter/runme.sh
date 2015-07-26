#!/bin/bash

set -xe

test $PARENT_TASK_ARTIFACTS_URL_PREFIX
test $BALROG_API_ROOT
test $SIGNING_CERT

curl --location --retry 10 --retry-delay 10 -o /home/worker/manifest.json \
    "$PARENT_TASK_ARTIFACTS_URL_PREFIX/manifest.json"
cat /home/worker/manifest.json
python /home/worker/bin/funsize-balrog-submitter.py \
    --artifacts-url-prefix "$PARENT_TASK_ARTIFACTS_URL_PREFIX" \
    --manifest /home/worker/manifest.json \
    -a "$BALROG_API_ROOT" \
    --signing-cert "/home/worker/keys/${SIGNING_CERT}.pubkey" \
    --verbose \
    $EXTRA_BALROG_SUBMITTER_PARAMS
