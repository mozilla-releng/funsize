#!/usr/bin/env python

import argparse
import requests
import os
import json
import logging
import tempfile
import shutil

log = logging.getLogger(__name__)


def artifact_url(task_id, artifact):
    return "https://queue.taskcluster.net/v1/task/{}/artifacts/{}".format(
        task_id, artifact)


def get_artifact(task_id, prefix, artifact, dest):
    artifact = "{}/{}".format(prefix, artifact)
    url = artifact_url(task_id, artifact)
    log.debug("Downloading %s", url)
    r = requests.get(url)
    with open(dest, 'wb') as fd:
        for chunk in r.iter_content(4096):
            fd.write(chunk)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--parent-task-id", required=True)
    parser.add_argument("--artifacts-dir", required=True)
    parser.add_argument("--parent-artifacts-prefix", required=True)
    parser.add_argument("-q", "--quiet", dest="log_level",
                        action="store_const", const=logging.WARNING,
                        default=logging.DEBUG)

    args = parser.parse_args()
    logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s",
                        level=args.log_level)
    manifest_file = "manifest.json"
    workdir = tempfile.mkdtemp()
    manifest_dest = os.path.join(workdir, manifest_file)
    get_artifact(args.parent_task_id, args.parent_artifacts_prefix,
                 manifest_file, manifest_dest)
    with open(manifest_dest) as f:
        manifest = json.load(f)
    log.debug(manifest)

    mar = manifest["mar"]
    mar_dest = os.path.join(workdir, mar)
    get_artifact(args.parent_task_id, args.parent_artifacts_prefix,
                 mar, mar_dest)
    # TODO: do the signing
    # TODO: update the manifest with size/hash
    shutil.copy(manifest_dest, args.artifacts_dir)
    shutil.copy(mar_dest, args.artifacts_dir)

if __name__ == '__main__':
    main()
