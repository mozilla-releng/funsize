import argparse
import datetime
import re
import requests
import taskcluster
import yaml

from taskcluster.utils import slugId, fromNow
from release.platforms import buildbot2updatePlatforms
from mozillapulse.config import PulseConfiguration
from mozillapulse.consumers import BuildConsumer

# TODO: add logging (to file too?)


class BalrogClient(object):
    CA_BUNDLE = "ca-bundle.crt"

    def __init__(self, api_root, auth):
        self.api_root = api_root
        self.auth = auth

    def get_releases(self, product, branch=None, version=None, limit=2,
                     include_latest=False, reverse=True):
        # Params will be working after Bug 1137367 is deployed
        url = "{}/releases".format(self.api_root)
        params = {"product": product}
        if branch:
            params["name_prefix"] = "{}-{}".format(product, branch)
        if version:
            params["version"] = version

        # TODO: switch to names_only when filtering
        req = requests.get(url, auth=self.auth, verify=self.CA_BUNDLE,
                           params=params)
        releases = req.json()["releases"]
        releases = self.legacy_filter(releases, product, branch, version)
        if not include_latest:
            releases = [r for r in releases if not
                        r['name'].endswith("-latest")]
        releases = sorted(releases, key=lambda r: r["name"], reverse=reverse)
        return releases[:limit]

    @staticmethod
    def legacy_filter(releases, product, branch=None, version=None):
        # TODO: to be removed
        # Filter internally for now, can be removed when Bug 1137367 is landed
        releases = [r for r in releases if r['product'] == product]
        if branch:
            releases = [r for r in releases if
                        r['name'].startswith("{}-{}".format(product, branch))]
        if version:
            releases = [r for r in releases if r['version'] == version]
        return releases

    def get_build(self, release, platform, locale):
        url = "{}/releases/{}/builds/{}/{}".format(self.api_root, release,
                                                   platform, locale)
        req = requests.get(url, auth=self.auth, verify=self.CA_BUNDLE)
        return req.json()


def create_task_graph(platform, locale, from_mar, to_mar, secrets):
    task_1_id = slugId()
    task_2_id = slugId()
    task_3_id = slugId()
    now = datetime.datetime.utcnow()
    # TODO: move the graph to a yaml template
    task_graph = {
        "scopes": ['queue:*', 'docker-worker:*', 'scheduler:*'],
        "tasks": [
            {
                "taskId": task_1_id,
                "requires": [],
                "task":{
                    "provisionerId": "aws-provisioner",
                    "workerType": "b2gtest",
                    "created": now,
                    "deadline": fromNow('1h'),
                    "payload": {
                        "image": "rail/funsize-update-generator",
                        "command": ["/runme.sh"],
                        "maxRunTime": 300,
                        "artifacts":{
                            "public/env": {
                                "path": "/home/worker/artifacts/",
                                "type": "directory",
                                "expires": fromNow('1h')
                            }
                        },
                        "env": {
                            "FROM_MAR": from_mar,
                            "TO_MAR": to_mar,
                            "PLATFORM": platform,
                            "LOCALE": locale,
                        }
                    },
                    "metadata": {
                        "name": "Funsize update generator task",
                        "description": "Funsize update generator task",
                        "owner": "release+funsize@mozilla.com",
                        "source": "https://github.com/rail/funsize-taskcluster"
                    }
                }
            },
            {
                "taskId": task_2_id,
                "requires": [task_1_id],
                "task": {
                    "provisionerId": "aws-provisioner",
                    "workerType": "b2gtest",
                    "created": now,
                    "deadline": fromNow('1h'),
                    "payload": {
                        "image": "rail/funsize-signer",
                        "command": ["/runme.sh"],
                        "maxRunTime": 300,
                        "artifacts": {
                            "public/env": {
                                "path": "/home/worker/artifacts/",
                                "type": "directory",
                                "expires": fromNow('1h'),
                            }
                        },
                        "env": {
                            "PARENT_TASK_ARTIFACTS_URL_PREFIX":
                                "https://queue.taskcluster.net/v1/task/" +
                                task_1_id + "/artifacts/public/env",
                        }
                    },
                    "metadata": {
                        "name": "Funsize signing task",
                        "description": "Funsize signing task",
                        "owner": "release+funsize@mozilla.com",
                        "source": "https://github.com/rail/funsize-taskcluster"
                    }
                }
            },
            {
                "taskId": task_3_id,
                "requires": [task_2_id],
                "task": {
                    "provisionerId": "aws-provisioner",
                    "workerType": "b2gtest",
                    "created": now,
                    "deadline": fromNow('1h'),
                    "payload": {
                        "image": "rail/funsize-balrog-submitter",
                        "command": ["/runme.sh"],
                        "maxRunTime": 300,
                        "env": {
                            "PARENT_TASK_ARTIFACTS_URL_PREFIX":
                                "https://queue.taskcluster.net/v1/task/" +
                                task_2_id + "/artifacts/public/env",
                            "BALROG_API_ROOT":
                                "https://aus4-admin-dev.allizom.org/api",
                            "BALROG_USERNAME": "TO_BE_ENCRYPTED",
                            "BALROG_PASSWORD": "TO_BE_ENCRYPTED",
                        }
                    },
                    "metadata": {
                        "name": "Funsize balrog submitter task",
                        "description": "Funsize balrog submitter task",
                        "owner": "release+funsize@mozilla.com",
                        "source": "https://github.com/rail/funsize-taskcluster"
                    }
                }
            },
        ],
        "metadata": {
            "name": "Funsize",
            "description": "Funsize is **fun**!",
            "owner": "rail@mozilla.com",
            "source": "http://rail.merail.ca"
        }
    }
    graph_id = slugId()
    scheduler = taskcluster.Scheduler(secrets["taskcluster"])
    print "about to create a graph", graph_id
    res = scheduler.createTaskGraph(graph_id, task_graph)
    print res


def interesting_buildername(buildername):
    # TODO: update the list with real patterns
    interesting_names = [
        r"en us nightly build",
        r"l10n nightly repack",
    ]
    return any(re.match(n, buildername) for n in interesting_names)


def process_message(data, message, balrog_client):
    try:
        do_process_message(data, balrog_client)
    finally:
        message.ack()


def do_process_message(data, balrog_client):
    buildername = data["payload"]["build"]["builderName"]
    properties = data["payload"]["build"]["properties"]
    result = data["payload"]["results"]
    if result != 0:
        return
    if not interesting_buildername(buildername):
        return
    locale = properties["locale"]
    platform = properties["platform"]
    branch = properties["branch"]
    product = properties["product"]  # check Firefox B2G
    update_platform = buildbot2updatePlatforms(platform)[0]

    release_to, release_from = balrog_client.get_releases(product, branch)
    build_from = balrog_client.get_build(release_from["name"],
                                         update_platform, locale)
    build_to = balrog_client.get_build(release_to["name"], update_platform,
                                       locale)
    create_task_graph(platform, locale, build_from["completes"][0]["fileUrl"],
                      build_to["completes"][0]["fileUrl"], secrets)


def main(api_root, secrets):
    auth = (secrets["balrog_username"], secrets["balrog_password"])
    balrog_client = BalrogClient(api_root, auth)
    pulse_credentials = secrets["pulse"]["credentials"]
    pulse = BuildConsumer(applabel='funsize', connect=False)
    pulse.config = PulseConfiguration(user=pulse_credentials["user"],
                                      password=pulse_credentials["password"])
    # TODO: use durable queues in production
    pulse.configure(
        topic="build.#.finished",
        callback=lambda d, m: process_message(d, m, balrog_client))
    # TODO: handle connection failures (reconnect or restart the script)
    pulse.listen()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--secrets", required=True, type=argparse.FileType())
    parser.add_argument("--balrog-api-root",
                        default="https://aus4-admin.mozilla.org/api")
    args = parser.parse_args()
    secrets = yaml.safe_load(args.secrets)
    main(args.balrog_api_root, secrets)

# TODO: encrypt credentials
