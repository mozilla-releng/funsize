import argparse
import datetime
import json
import logging
import re
import requests
import taskcluster
import yaml
import time
import os
import pgpy
import pystache
import base64

from kombu import Exchange, Queue, Connection
from kombu.mixins import ConsumerMixin
from taskcluster.utils import slugId, fromNow, stringDate

log = logging.getLogger(__name__)

# TODO: move these to config
BRANCHES = ['mozilla-central', 'mozilla-aurora']
PLATFORMS = ['linux', 'linux64', 'win32', 'win64', 'macosx64']
BUILDERS = [
    r'WINNT \d+\.\d+ (x86-64 )?{branch} nightly',
    r'Linux (x86-64 )?{branch} nightly',
    r'OS X \d+\.\d+ {branch} nightly',
    r'Firefox {branch} (linux|linux64|win32|win64|macosx64) l10n nightly-\d+',
]
PLATFORM_MAP = json.load(open(os.path.join(os.path.dirname(__file__), "data",
                                           "platform_map.json")))


class FunsizeWorker(ConsumerMixin):

    def __init__(self, connection, queue_name, exchange, balrog_client,
                 scheduler):
        self.connection = connection
        # Using passive mode is important, otherwise pulse returns 403
        self.exchange = Exchange(exchange, type='topic', passive=True)
        self.queue_name = queue_name
        self.balrog_client = balrog_client
        self.scheduler = scheduler

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
        try:
            self.dispatch_message(body)
        except Exception:
            log.exception("Cought an error")
        else:
            message.ack()

    def on_consume_ready(self, connection, channel, consumers):
        log.info("Listening...")

    def dispatch_message(self, body):
        payload = body["payload"]
        buildername = payload["build"]["builderName"]
        if not interesting_buildername(buildername):
            log.debug("Ignoring %s: not interested", buildername)
            return
        result = payload["results"]
        if result != 0:
            log.debug("Ignoring %s with result %s", buildername, result)
            return
        properties = properties_to_dict(payload["build"]["properties"])
        if "locales" in properties:
            log.debug("L10N repack detected")
            # TODO: blocked by bug 1146426
            return
            funsize_info = properties["funsize_info"]
            platform = funsize_info["platform"]
            branch = funsize_info["branch"]
            product = funsize_info["appName"]
            for locale, result in properties["locales"]:
                if result.lower() == "success":
                    self.create_partial(product, branch, platform, locale)
                else:
                    log.warn("Ignoring %s with result %s", locale, result)
        else:
            log.debug("en-US build detected")
            self.create_partial(properties["appName"], properties["branch"],
                                properties["platform"], 'en-US')

    def create_partial(self, product, branch, platform, locale):
        # Get last 3 releases, generate partial from -2 to latest
        # TODO: move limit to config
        last_releases = self.balrog_client.get_releases(product, branch,
                                                        limit=3)
        release_to = last_releases[0]
        release_from = last_releases[-1]
        log.debug("From: %s", release_from)
        log.debug("To: %s", release_to)
        build_from = self.balrog_client.get_build(release_from["name"],
                                                  platform, locale)
        log.debug("Build from: %s", build_from)
        build_to = self.balrog_client.get_build(release_to["name"],
                                                platform, locale)
        log.debug("Build to: %s", build_to)
        mar_from = build_from["completes"][0]["fileUrl"]
        mar_to = build_to["completes"][0]["fileUrl"]
        log.info("New Funsize task for %s %s, from %s to %s", platform, locale,
                 mar_from, mar_to)
        create_task_graph(platform, locale, mar_from, mar_to,
                          self.balrog_client, self.scheduler)


class BalrogClient(object):

    def __init__(self, api_root, auth, cert=None):
        self.api_root = api_root
        self.auth = auth
        if cert:
            self.verify = os.path.join(os.path.dirname(__file__), "data", cert)
        else:
            self.verify = True

    def get_releases(self, product, branch, limit=2, include_latest=False,
                     reverse=True):
        # TODO: switch to names_only when filtering
        url = "{}/releases".format(self.api_root)
        params = {"product": product}
        if branch:
            # release names ending with -nightly-2 (e.g.
            # Firefox-mozilla-central-nightly-201505011600) should ignore
            # release releases
            params["name_prefix"] = "{}-{}-nightly-2".format(product, branch)

        log.debug("Connecting to %s", url)
        req = requests.get(url, auth=self.auth, verify=self.verify,
                           params=params)
        req.raise_for_status()
        releases = req.json()["releases"]
        if not include_latest:
            releases = [r for r in releases if not
                        r['name'].endswith("-latest")]
        releases = sorted(releases, key=lambda r: r["name"], reverse=reverse)
        return releases[:limit]

    def get_build(self, release, platform, locale):
        update_platform = PLATFORM_MAP[platform][0]
        url = "{}/releases/{}/builds/{}/{}".format(self.api_root, release,
                                                   update_platform, locale)
        log.debug("Connecting to %s", url)
        req = requests.get(url, auth=self.auth, verify=self.verify)
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
    return encrypt(message)


def encrypt(message):
    # TODO: load the key once
    key_file = os.path.join(os.path.dirname(__file__), "data",
                            "docker-worker-pub.pem")
    key, _ = pgpy.PGPKey.from_file(key_file)
    msg = pgpy.PGPMessage.new(message)
    encrypted = key.encrypt(msg)
    return base64.b64encode(encrypted.__bytes__())


def create_task_graph(platform, locale, from_mar, to_mar, balrog_client,
                      scheduler):
    template = os.path.join(os.path.dirname(__file__), "tasks", "funsize.yml")
    template = open(template).read()
    now = datetime.datetime.utcnow()
    enc_now = int(time.time() * 1000)
    # encrypted variables can be used 24 hours
    enc_deadline = enc_now + 24 * 3600 * 1000
    template_vars = {
        "updateGeneratorTaskId": slugId(),
        "signingTaskId": slugId(),
        "balrogTaskId": slugId(),
        "now": stringDate(now),
        "fromNowJSON": fromNow,
        "platform": platform,
        "locale": locale,
        "fromMAR": from_mar,
        "toMAR": to_mar,
    }
    template_vars["BALROG_USERNAME_ENC_MESSAGE"] = encrypt_env_var(
        template_vars["balrogTaskId"], enc_now, enc_deadline,
        'BALROG_USERNAME', balrog_client.auth[0])
    template_vars["BALROG_PASSWORD_ENC_MESSAGE"] = encrypt_env_var(
        template_vars["balrogTaskId"], enc_now, enc_deadline,
        'BALROG_PASSWORD',  balrog_client.auth[1])
    rendered = pystache.render(template, template_vars)
    task_graph = yaml.safe_load(rendered)
    graph_id = slugId()
    log.info("Submitting a new graph %s", graph_id)
    res = scheduler.createTaskGraph(graph_id, task_graph)
    log.info("Result was: %s", res)


def interesting_buildername(buildername):
    interesting_names = [n.format(branch=b) for b in BRANCHES for n in
                         BUILDERS]
    return any(re.match(n, buildername) for n in interesting_names)


def properties_to_dict(props):
    """Convert properties tuple into dict"""
    props_dict = {}
    for prop in props:
        props_dict[prop[0]] = prop[1]
    return props_dict


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--secrets", required=True, type=argparse.FileType())
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
    balrog_client = BalrogClient(
        api_root=secrets["balrog"]["api_root"],
        auth=(secrets["balrog"]["username"], secrets["balrog"]["password"]),
        # cert="mozilla-root.crt"
    )
    scheduler = taskcluster.Scheduler(secrets["taskcluster"])
    queue_name = 'queue/{user}/{queue_name}'.format(
        user=secrets["pulse"]["user"],
        queue_name=secrets["pulse"]["queue"],
    )
    with Connection(hostname='pulse.mozilla.org', port=5671,
                    userid=secrets["pulse"]["user"],
                    password=secrets["pulse"]["password"],
                    virtual_host='/', ssl=True) as connection:
        FunsizeWorker(connection=connection, queue_name=queue_name,
                      exchange=secrets["pulse"]["exchange"],
                      balrog_client=balrog_client,
                      scheduler=scheduler).run()
