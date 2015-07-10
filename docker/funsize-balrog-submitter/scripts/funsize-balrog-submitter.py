#!/usr/bin/env python

import os
import logging
import argparse
import json
import sys
import hashlib
import requests
from boto.s3.connection import S3Connection

sys.path.insert(0, os.path.join(
    os.path.dirname(__file__), "/home/worker/tools/lib/python"))

from balrog.submitter.cli import NightlySubmitterV4
from util.retry import retry


log = logging.getLogger(__name__)


def get_hash(content, hash_type="md5"):
    h = hashlib.new(hash_type)
    h.update(content)
    return h.hexdigest()


def copy_to_s3(bucket_name, aws_access_key_id, aws_secret_access_key,
               mar_url, mar_dest):
    conn = S3Connection(aws_access_key_id, aws_secret_access_key)
    bucket = conn.get_bucket(bucket_name)
    r = requests.get(mar_url)
    for name in possible_names(mar_dest, 10):
        log.info("Checking if %s already exists", name)
        key = bucket.get_key(name)
        if not key:
            log.info("Uploading to %s...", name)
            key = bucket.new_key(name)
            # There is a chance for race condition here. To avoid it we check
            # the return value with replace=False. It should be not None.
            length = key.set_contents_from_string(r.content, replace=False)
            if length is None:
                log.warn("Name race condition using %s, trying again...", name)
                continue
            else:
                # key.make_public() may lead to race conditions, because
                # it doesn't pass version_id, so it may not set permissions
                bucket.set_canned_acl(acl_str='public-read', key_name=name,
                                      version_id=key.version_id)
                # Use explicit version_id to avoid using "latest" version
                return key.generate_url(expires_in=0, query_auth=False,
                                        version_id=key.version_id)
        else:
            if get_hash(key.get_contents_as_string()) == get_hash(r.content):
                log.info("%s has the same MD5 checksum, not uploading...")
                return key.generate_url(expires_in=0, query_auth=False,
                                        version_id=key.version_id)
            log.info("%s already exists with different checksum, "
                     "trying another one...", name)

    raise RuntimeError("Cannot generate a unique name for %s", mar_dest)


def possible_names(initial_name, amount):
    """Generate names appending counter before extension"""
    prefix, ext = os.path.splitext(initial_name)
    return [initial_name] + ["{}-{}{}".format(prefix, n, ext) for n in
                             range(1, amount + 1)]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifacts-url-prefix", required=True,
                        help="URL prefix for MAR")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("-a", "--api-root", required=True,
                        help="Balrog API root")
    parser.add_argument("-d", "--dummy", action="store_true",
                        help="Add '-dummy' suffix to branch name")
    parser.add_argument("-v", "--verbose", action="store_const",
                        dest="loglevel", const=logging.DEBUG,
                        default=logging.INFO)
    args = parser.parse_args()
    logging.basicConfig(level=args.loglevel, format="%(message)s")
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("boto").setLevel(logging.WARNING)

    balrog_username = os.environ.get("BALROG_USERNAME")
    balrog_password = os.environ.get("BALROG_PASSWORD")
    if not balrog_username and not balrog_password:
        raise RuntimeError("BALROG_USERNAME and BALROG_PASSWORD environment "
                           "variables should be set")

    s3_bucket = os.environ.get("S3_BUCKET")
    aws_access_key_id = os.environ.get("AWS_ACCESS_KEY_ID")
    aws_secret_access_key = os.environ.get("AWS_SECRET_ACCESS_KEY")
    if not (s3_bucket and aws_access_key_id and aws_secret_access_key):
        raise RuntimeError("Define AWS bucket and credentials")

    manifest = json.load(open(args.manifest))
    auth = (balrog_username, balrog_password)
    submitter = NightlySubmitterV4(args.api_root, auth, args.dummy)
    for entry in manifest:
        partial_mar_url = "{}/{}".format(args.artifacts_url_prefix,
                                         entry["mar"])
        complete_mar_url = entry["to_mar"]
        dest_prefix = "{branch}/{buildid}".format(
            branch=entry["branch"], buildid=entry["to_buildid"])
        partial_mar_dest = "{}/{}".format(dest_prefix, entry["mar"])
        complete_mar_filename = complete_mar_url.split("/")[-1]
        complete_mar_dest = "{}/{}".format(dest_prefix, complete_mar_filename)

        final_partial_mar_url = copy_to_s3(
            s3_bucket, aws_access_key_id, aws_secret_access_key,
            partial_mar_url, partial_mar_dest)
        final_complete_mar_url = copy_to_s3(
            s3_bucket, aws_access_key_id, aws_secret_access_key,
            complete_mar_url, complete_mar_dest)

        partial_info = None
        complete_info = None

        partial_info = [
            {
                "url": final_partial_mar_url,
                "hash": entry["hash"],
                "from_buildid": entry["from_buildid"],
                "size": entry["size"],
            }
        ]
        complete_info = [
            {
                "url": final_complete_mar_url,
                "hash": entry["to_hash"],
                "size": entry["to_size"],
            }
        ]

        retry(lambda: submitter.run(
            platform=entry["platform"], buildID=entry["to_buildid"],
            productName=entry["appName"], branch=entry["branch"],
            appVersion=entry["version"], locale=entry["locale"],
            hashFunction='sha512', extVersion=entry["version"],
            partialInfo=partial_info, completeInfo=complete_info)
            )


if __name__ == '__main__':
    main()
