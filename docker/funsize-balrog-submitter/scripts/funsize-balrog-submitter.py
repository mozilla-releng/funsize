#!/usr/bin/env python

import os
import logging
import argparse
import json
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__),
                "/home/worker/tools/lib/python/vendor/requests-0.10.8"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__),
                "/home/worker/tools/lib/python/vendor/certifi-2015.04.28"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__),
                "/home/worker/tools/lib/python/vendor/boto-2.38.0"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__),
                "/home/worker/tools/lib/python"))

from boto.s3.connection import S3Connection
from balrog.submitter.cli import NightlySubmitterV4
from util.retry import retry, retriable
import requests

@retriable(attempts=5, sleeptime=10, max_sleeptime=60)
def copy_to_s3(bucket_name, aws_access_key_id, aws_secret_access_key,
               mar_url, mar_dest):
    conn = S3Connection(aws_access_key_id, aws_secret_access_key)
    bucket = conn.get_bucket(bucket_name)
    key = bucket.get_key(mar_dest)
    r = requests.get(mar_url)
    key.set_contents_from_string(r.content)
    key.set_acl("public-read")
    return key.generate_url(expires_in=0, query_auth=False)


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
