#!/usr/bin/env python

import argparse
import requests
import os
import json
import logging
import tempfile
import shutil

log = logging.getLogger(__name__)


def get_artifact(prefix, artifact, dest):
    url = "{}/{}".format(prefix, artifact)
    log.debug("Downloading %s", url)
    r = requests.get(url)
    with open(dest, 'wb') as fd:
        for chunk in r.iter_content(4096):
            fd.write(chunk)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifacts-url-prefix", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--artifacts-dir", required=True)
    parser.add_argument("-q", "--quiet", dest="log_level",
                        action="store_const", const=logging.WARNING,
                        default=logging.DEBUG)

    args = parser.parse_args()
    logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s",
                        level=args.log_level)
    manifest = json.load(open(args.manifest))
    workdir = tempfile.mkdtemp()
    mar = manifest["mar"]
    mar_dest = os.path.join(workdir, mar)
    get_artifact(args.artifacts_url_prefix, mar, mar_dest)
    # TODO: do the signing
    # TODO: update the manifest with size/hash
    manifest["signed"] = True
    with open(os.path.join(args.artifacts_dir, "manifest.json")) as f:
        json.dump(manifest, f, indent=2, sort_keys=True)
    shutil.copy(mar_dest, args.artifacts_dir)
    shutil.rmtree(workdir)

if __name__ == '__main__':
    main()
