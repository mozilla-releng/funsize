import argparse
import datetime
import json
import logging
import re
import requests
import taskcluster
import yaml
import time

from kombu import Exchange, Queue, Connection
from kombu.mixins import ConsumerMixin

from taskcluster.utils import slugId, fromNow, stringDate
from release.platforms import buildbot2updatePlatforms
from mozillapulse.config import PulseConfiguration
from mozillapulse.consumers import BuildConsumer

log = logging.getLogger(__name__)

BRANCHES = ['mozilla-central', 'mozilla-aurora']
PLATFORMS = ['linux', 'linux64', 'win32', 'win64', 'macosx64']


class FunsizeWorker(ConsumerMixin):

    def __init__(self, connection, queue_name):
        self.connection = connection
        self.exchange = Exchange('exchange/build/', type='topic', passive=True)
        self.queue_name = queue_name

    @property
    def routing_keys(self):
        jobs = [
            'build.{branch}-{platform}-nightly.*.finished',
            # TODO: find a better way to specify these
            'build.{branch}-{platform}-l10n-nightly-1.*.finished',
            'build.{branch}-{platform}-l10n-nightly-2.*.finished',
            'build.{branch}-{platform}-l10n-nightly-3.*.finished',
            'build.{branch}-{platform}-l10n-nightly-4.*.finished',
            'build.{branch}-{platform}-l10n-nightly-5.*.finished',
            'build.{branch}-{platform}-l10n-nightly-6.*.finished',
            'build.{branch}-{platform}-l10n-nightly-7.*.finished',
            'build.{branch}-{platform}-l10n-nightly-8.*.finished',
            'build.{branch}-{platform}-l10n-nightly-9.*.finished',
            'build.{branch}-{platform}-l10n-nightly-10.*.finished',
        ]
        return [job.format(branch=branch, platform=platform)
                for job in jobs
                for branch in BRANCHES
                for platform in PLATFORMS]

    @property
    def queues(self):
        return [Queue(name=self.queue_name, exchange=self.exchange,
                      routing_key=routing_key, durable=True, exclusive=False,
                      auto_delete=False)
                for routing_key in self.routing_keys]

    def get_consumers(self, Consumer, channel):
        return [Consumer(queues=self.queues, callbacks=[self.process_message])]

    def process_message(self, body, message):
        print body
        exit(1)

    def on_consume_ready(self, connection, channel, consumers):
        log.info("Listening...")


class BalrogClient(object):
    CA_BUNDLE = "ca-bundle.crt"

    def __init__(self, api_root, auth):
        self.api_root = api_root
        self.auth = auth

    def get_releases(self, product, branch, version=None, limit=2,
                     include_latest=False, reverse=True):
        # TODO: switch to names_only when filtering
        url = "{}/releases".format(self.api_root)
        params = {"product": product}
        if branch:
            params["name_prefix"] = "{}-{}".format(product, branch)
        if version:
            params["version"] = version

        req = requests.get(url, auth=self.auth, verify=self.CA_BUNDLE,
                           params=params)
        req.raise_for_status()
        releases = req.json()["releases"]
        if not include_latest:
            releases = [r for r in releases if not
                        r['name'].endswith("-latest")]
        # TODO: filter out release names not matching
        # {product}-{branch}-nighlty-{biuldid_pattern} for safety
        releases = sorted(releases, key=lambda r: r["name"], reverse=reverse)
        return releases[:limit]

    def get_build(self, release, platform, locale):
        url = "{}/releases/{}/builds/{}/{}".format(self.api_root, release,
                                                   platform, locale)
        req = requests.get(url, auth=self.auth, verify=self.CA_BUNDLE)
        # TODO: report if build is 404
        req.raise_for_status()
        return req.json()


def encrypt_env_var(task_id, start_time, end_time, name, value):
    message = {
        "messageVersion": "1",
        "taskId": task_id,
        "startTime": start_time,
        "endTime": end_time,
        "name": name,
        "value": value
    }
    message = str(json.dumps(message))
    return None  # TODO: use pgpy


def create_task_graph(platform, locale, from_mar, to_mar, secrets):
    task_1_id = slugId()
    task_2_id = slugId()
    task_3_id = slugId()
    now = stringDate(datetime.datetime.utcnow())
    deadline = fromNow('2h')
    enc_now = int(time.time() * 1000)
    enc_deadline = enc_now + 2 * 3600 * 1000
    artifacts_expire = fromNow('7d')
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
                    "deadline": deadline,
                    "payload": {
                        "image": "rail/funsize-update-generator",
                        "command": ["/runme.sh"],
                        "maxRunTime": 300,
                        "artifacts":{
                            "public/env": {
                                "path": "/home/worker/artifacts/",
                                "type": "directory",
                                "expires": artifacts_expire,
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
                    "deadline": deadline,
                    "payload": {
                        "image": "rail/funsize-signer",
                        "command": ["/runme.sh"],
                        "maxRunTime": 300,
                        "artifacts": {
                            "public/env": {
                                "path": "/home/worker/artifacts/",
                                "type": "directory",
                                "expires": artifacts_expire,
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
                    "deadline": deadline,
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
                        },
                        "encryptedEnv": [
                            encrypt_env_var(task_id=task_3_id,
                                            start_time=enc_now,
                                            end_time=enc_deadline,
                                            name="BALROG_USERNAME",
                                            value=secrets["balrog_username"]),
                            encrypt_env_var(task_id=task_3_id,
                                            start_time=enc_now,
                                            end_time=enc_deadline,
                                            name="BALROG_PASSWORD",
                                            value=secrets["balrog_password"]),
                        ],
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
    log.debug("Task graph: %s", task_graph)
    log.info("Submitting task graph %s", graph_id)
    res = scheduler.createTaskGraph(graph_id, task_graph)
    log.info("Result was: %s", res)


def interesting_buildername(buildername):
    builders = [
        r'WINNT \d+\.\d+ (x86-64 )?${branch} nightly',
        r'Linux (x86-64 )?${branch} nightly',
        r'OS X \d+\.\d+ ${branch} nightly',
        r'Firefox ${branch} (linux|linux64|win32|win64|mac) l10n nightly-\d+',
    ]
    interesting_names = [n.format(branch=b) for b in BRANCHES for n in
                         builders]
    return any(re.match(n, buildername) for n in interesting_names)


def process_message(data, message, balrog_client):
    try:
        do_process_message(data, balrog_client)
    except Exception:
        log.exception("Cought an error")
    finally:
        message.ack()


def properties_to_dict(props):
    """Convert properties tuple into dict"""
    props_dict = {}
    for prop in props:
        props_dict[prop[0]] = prop[1]
    return props_dict


def do_process_message(data, balrog_client):
    buildername = data["payload"]["build"]["builderName"]
    properties = data["payload"]["build"]["properties"]
    properties = properties_to_dict(properties)
    result = data["payload"]["results"]
    if not interesting_buildername(buildername):
        log.debug("Ignoring %s: not interested", buildername)
        return
    if result != 0:
        log.debug("Ignoring %s with result %s", buildername, result)
        return
    locale = properties.get("locale", "en-US")
    platform = properties["platform"]
    branch = properties["branch"]
    product = properties["appName"]  # check Firefox B2G
    update_platform = buildbot2updatePlatforms(platform)[0]

    # Get last 3 releases, generate partial from -2 to latest
    last_releases = balrog_client.get_releases(product, branch, limit=3)
    release_to = last_releases[0]
    release_from = last_releases[-1]
    log.debug("From: %s", release_from)
    log.debug("To: %s", release_to)
    build_from = balrog_client.get_build(release_from["name"],
                                         update_platform, locale)
    log.debug("Build from: %s", build_from)
    build_to = balrog_client.get_build(release_to["name"], update_platform,
                                       locale)
    log.debug("Build to: %s", build_to)
    mar_from = build_from["completes"][0]["fileUrl"]
    mar_to = build_to["completes"][0]["fileUrl"]
    log.info("New Funsize task for %s %s, from %s to %s", platform, locale,
             mar_from, mar_to)
    create_task_graph(platform, locale, mar_from, mar_to, secrets)


def main(api_root, secrets):
    auth = (secrets["balrog_username"], secrets["balrog_password"])
    balrog_client = BalrogClient(api_root, auth)
    pulse_credentials = secrets["pulse"]["credentials"]
    pulse = BuildConsumer(applabel='funsize', connect=False)
    pulse.config = PulseConfiguration(user=pulse_credentials["user"],
                                      password=pulse_credentials["password"])
    # TODO: use durable queues in production
    log.info("Listening for pulse messages")
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
    parser.add_argument("-v", "--verbose", dest="log_level",
                        action="store_const", const=logging.DEBUG,
                        default=logging.INFO)
    args = parser.parse_args()
    logging.basicConfig(
        level=args.log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    logging.getLogger("requests").setLevel(logging.WARN)
    logging.getLogger("taskcluster").setLevel(logging.WARN)
    logging.getLogger("hawk").setLevel(logging.WARN)
    secrets = yaml.safe_load(args.secrets)
    # main(args.balrog_api_root, secrets)
    with Connection(hostname='pulse.mozilla.org', port=5671,
                    userid=secrets["pulse"]["credentials"]["user"],
                    password=secrets["pulse"]["credentials"]["password"],
                    virtual_host='/', ssl=True) as conn:
        queue_name = 'queue/{user}/{queue_name}'.format(
            user=secrets["pulse"]["credentials"]["user"],
            queue_name=secrets["pulse"]["queue_name"],
        )
        FunsizeWorker(conn, queue_name).run()
