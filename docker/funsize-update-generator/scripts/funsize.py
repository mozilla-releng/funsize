#!/usr/bin/env python

import ConfigParser
import argparse
import hashlib
import json
import logging
import os
import shutil
import tempfile

import requests
import sh

log = logging.getLogger(__name__)


def download(url, dest, mode=None):
    log.debug("Downloading %s to %s", url, dest)
    r = requests.get(url)
    with open(dest, 'wb') as fd:
        for chunk in r.iter_content(4096):
            fd.write(chunk)
    if mode:
        log.debug("chmod %o %s", mode, dest)
        os.chmod(dest, mode)


def unpack(work_env, mar, dest_dir):
    os.mkdir(dest_dir)
    unwrap_cmd = sh.Command(os.path.join(work_env.workdir,
                                         "unwrap_full_update.pl"))
    log.debug("Unwrapping %s", mar)
    out = unwrap_cmd(mar, _cwd=dest_dir, _env=work_env.env, _timeout=120,
                     _err_to_out=True)
    if out:
        log.debug(out)


def find_file(directory, filename):
    log.debug("Searching for %s in %s", filename, directory)
    for root, dirs, files in os.walk(directory):
        if filename in files:
            f = os.path.join(root, filename)
            log.debug("Found %s", f)
            return f


def get_option(directory, filename, section, option):
    log.debug("Exctracting [%s]: %s from %s/**/%s", section, option, directory,
              filename)
    f = find_file(directory, filename)
    config = ConfigParser.ConfigParser()
    config.read(f)
    rv = config.get(section, option)
    log.debug("Found %s", rv)
    return rv


def generate_partial(work_env, from_dir, to_dir, dest_mar, channel_ids,
                     version):
    log.debug("Generating partial %s", dest_mar)
    env = work_env.env
    env["MOZ_PRODUCT_VERSION"] = version
    env["MOZ_CHANNEL_ID"] = channel_ids
    make_incremental_update = os.path.join(work_env.workdir,
                                           "make_incremental_update.sh")
    out = sh.bash(make_incremental_update, dest_mar, from_dir, to_dir,
                  _cwd=work_env.workdir, _env=env, _timeout=300,
                  _err_to_out=True)
    if out:
        log.debug(out)


def get_hash(path, hash_type="sha512"):
    h = hashlib.new(hash_type)
    with open(path, "rb") as f:
        for chunk in f.read(4096):
            h.update(chunk)
    return h.hexdigest()


class WorkEnv(object):

    def __init__(self, workdir):
        if workdir:
            self.workdir = workdir
            self._cleanup = False
        else:
            self.workdir = tempfile.mkdtemp()
            self._cleanup = True

    def setup(self):
        self.download_unwrap()
        self.download_martools()

    def download_unwrap(self):
        # unwrap_full_update.pl is not too sensitive to the revision
        url = "https://hg.mozilla.org/mozilla-central/raw-file/default/" \
            "tools/update-packaging/unwrap_full_update.pl"
        download(url, dest=os.path.join(self.workdir, "unwrap_full_update.pl"),
                 mode=0o755)

    def download_buildsystem_bits(self, repo, revision):
        prefix = "{repo}/raw-file/{revision}/tools/update-packaging"
        prefix = prefix.format(repo=repo, revision=revision)
        for f in ("make_incremental_update.sh", "common.sh"):
            url = "{prefix}/{f}".format(prefix=prefix, f=f)
            download(url, dest=os.path.join(self.workdir, f), mode=0o755)

    def download_martools(self):
        # TODO: check if the tools have to be branch specific
        prefix = "https://ftp.mozilla.org/pub/mozilla.org/firefox/nightly/" \
            "latest-mozilla-central/mar-tools/linux64"
        for f in ("mar", "mbsdiff"):
            url = "{prefix}/{f}".format(prefix=prefix, f=f)
            download(url, dest=os.path.join(self.workdir, f), mode=0o755)

    def cleanup(self):
        if self._cleanup:
            shutil.rmtree(self.workdir)

    @property
    def env(self):
        my_env = os.environ.copy()
        my_env['LC_ALL'] = 'C'
        my_env['MAR'] = os.path.join(self.workdir, "mar")
        my_env['MBSDIFF'] = os.path.join(self.workdir, "mbsdiff")
        return my_env


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--from-mar", required=True)
    parser.add_argument("--to-mar", required=True)
    parser.add_argument("--artifacts-dir", required=True)
    parser.add_argument("--platform", required=True,
                        help="Buildbot platform name")
    parser.add_argument("--locale", required=True)
    parser.add_argument("--workdir")
    parser.add_argument("--branch")
    parser.add_argument("-q", "--quiet", dest="log_level",
                        action="store_const", const=logging.WARNING,
                        default=logging.DEBUG)
    args = parser.parse_args()

    logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s",
                        level=args.log_level)

    work_env = WorkEnv(workdir=args.workdir)
    work_env.setup()
    for unpack_dir, f in (("from", args.from_mar), ("to", args.to_mar)):
        dest = os.path.join(work_env.workdir, f.split("/")[-1])
        unpack_dir = os.path.join(work_env.workdir, unpack_dir)
        download(f, dest)
        unpack(work_env, dest, unpack_dir)

    path = os.path.join(work_env.workdir, "to")
    from_path = os.path.join(work_env.workdir, "from")
    mar_data = {
        "ACCEPTED_MAR_CHANNEL_IDS": get_option(
            path, filename="update-settings.ini", section="Settings",
            option="ACCEPTED_MAR_CHANNEL_IDS"),
        "version": get_option(path, filename="application.ini", section="App",
                              option="Version"),
        "to_buildid": get_option(path, filename="application.ini",
                                 section="App", option="BuildID"),
        "from_buildid": get_option(from_path, filename="application.ini",
                                   section="App", option="BuildID"),
        "appName": get_option(from_path, filename="application.ini",
                              section="App", option="Name"),
        # Use Gecko repo and revision from platform.ini, not application.ini
        "repo": get_option(path, filename="platform.ini", section="Build",
                           option="SourceRepository"),
        "revision": get_option(path, filename="platform.ini", section="Build",
                               option="SourceStamp"),
        "from_mar": args.from_mar,
        "to_mar": args.to_mar,
        "platform": args.platform,
        "locale": args.locale,
    }
    mar_data["branch"] = args.branch or \
        mar_data["repo"].rstrip("/").split("/")[-1]
    mar_name = "%(appName)s-%(branch)s-%(version)s-%(platform)s-" \
        "%(from_buildid)s-%(to_buildid)s.partial.mar" % mar_data
    mar_data["mar"] = mar_name
    dest_mar = os.path.join(work_env.workdir, mar_name)
    work_env.download_buildsystem_bits(repo=mar_data["repo"],
                                       revision=mar_data["revision"])
    generate_partial(work_env, from_path, path, dest_mar,
                     mar_data["ACCEPTED_MAR_CHANNEL_IDS"], mar_data["version"])
    mar_data["size"] = os.path.getsize(dest_mar)
    mar_data["hash"] = get_hash(dest_mar)

    manifest_file = os.path.join(work_env.workdir, "manifest.json")
    with open(manifest_file, "w") as fp:
        json.dump(mar_data, fp, indent=2, sort_keys=True)
    shutil.copy(dest_mar, args.artifacts_dir)
    shutil.copy(manifest_file, args.artifacts_dir)
    work_env.cleanup()

if __name__ == '__main__':
    main()
