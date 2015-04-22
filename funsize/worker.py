import datetime
import logging
import time
from kombu import Exchange, Queue
from kombu.mixins import ConsumerMixin
import os
import pystache
import re
from taskcluster import slugId, stringDate, fromNow
import yaml
import json

from funsize.utils import properties_to_dict, encrypt_env_var

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


class FunsizeWorker(ConsumerMixin):

    def __init__(self, connection, queue_name, exchange, balrog_client,
                 scheduler):
        """Funsize consumer worker
        :type connection: kombu.Connection
        :param queue_name: Full queue name, including queue/<user> prefix
        :type exchange: kombu.Exchange
        :type balrog_client: funsize.balrog.BalrogClient
        :type scheduler: tascluster.Scheduler
        """
        self.connection = connection
        # Using passive mode is important, otherwise pulse returns 403
        self.exchange = Exchange(exchange, type='topic', passive=True)
        self.queue_name = queue_name
        self.balrog_client = balrog_client
        self.scheduler = scheduler

    @property
    def routing_keys(self):
        """Returns an explicit list of routing patterns.

        Instead of using "build.*.*.finished", which generates a lot of noise,
        FunsizeWorker uses explicit list of routing keys to match builders we
        are interested in.
        """
        jobs = [
            # TODO: move to configs
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
        """List of queues used by worker.
        Multiple queues are used to track multiple routing keys.
        """
        return [Queue(name=self.queue_name, exchange=self.exchange,
                      routing_key=routing_key, durable=True, exclusive=False,
                      auto_delete=False)
                for routing_key in self.routing_keys]

    def get_consumers(self, Consumer, channel):
        """Implement parent's method called to get the list of consumers"""
        return [Consumer(queues=self.queues, callbacks=[self.process_message])]

    def process_message(self, body, message):
        """Top level callback processing pulse messages.
        The callback tries to handle and log all exceptions

        :type body: kombu.Message.body
        :type message: kombu.Message
        """
        try:
            self.dispatch_message(body)
        except Exception:
            log.exception("Failed to process message")
        finally:
            # TODO: figure out what to do with failed tasks
            message.ack()

    def on_consume_ready(self, connection, channel, consumers, **kwargs):
        """Overrides parent's stub method. Called when ready to consume pulse
         messages.
        """
        log.info('Listening...')

    def on_connection_error(self, exc, interval):
        log.exception("connection error")
        super(FunsizeWorker, self).on_connection_error(exc, interval)

    def dispatch_message(self, body):
        """Dispatches incoming pulse messages.
        If the method detects L10N repacks, it creates multiple Taskcluster
        tasks, otherwise a single en-US task is created.
        :type body: kombu.Message.body
        """
        payload = body["payload"]
        buildername = payload["build"]["builderName"]
        if not interesting_buildername(buildername):
            log.debug("Ignoring %s: not interested", buildername)
            return
        job_result = payload["results"]
        if job_result != 0:
            log.debug("Ignoring %s with result %s", buildername, job_result)
            return
        properties = properties_to_dict(payload["build"]["properties"])
        if "locales" in properties:
            log.debug("L10N repack detected")
            funsize_info = json.loads(properties["funsize_info"])
            locales = json.loads(properties["locales"])
            platform = funsize_info["platform"]
            branch = funsize_info["branch"]
            product = funsize_info["appName"]
            for locale, result in locales.iteritems():
                if result.lower() == "success":
                    self.create_partial(product, branch, platform,
                                        locale)
                else:
                    log.warn("Ignoring %s with result %s", locale, result)
        else:
            log.debug("en-US build detected")
            self.create_partial(properties["appName"], properties["branch"],
                                properties["platform"], 'en-US')

    def create_partial(self, product, branch, platform, locale):
        """Calculates "from" and "to" MAR URLs and calls  create_task_graph().
        Currently "from" MAR is 2 releases behind to avoid duplication of
        existing CI partials.

        :param product: capitalized product name, AKA appName, e.g. Firefox
        :param branch: branch name (mozilla-central)
        :param platform: buildbot platform (linux, macosx64)
        :param locale: en-US or locale
        """
        # TODO: move limit to config
        # Get last 3 releases, generate partial from -2 to latest
        last_releases = self.balrog_client.get_releases(product, branch)[:3]
        release_to = last_releases[0]
        release_from = last_releases[-1]
        log.debug("From: %s", release_from)
        log.debug("To: %s", release_to)
        build_from = self.balrog_client.get_build(release_from,
                                                  platform, locale)
        log.debug("Build from: %s", build_from)
        build_to = self.balrog_client.get_build(release_to, platform, locale)
        log.debug("Build to: %s", build_to)
        mar_from = build_from["completes"][0]["fileUrl"]
        mar_to = build_to["completes"][0]["fileUrl"]
        log.info("New Funsize task for %s %s, from %s to %s", platform, locale,
                 mar_from, mar_to)
        self.submit_task_graph(platform, locale, mar_from, mar_to)

    def submit_task_graph(self, platform, locale, from_mar, to_mar):
        graph_id = slugId()
        log.info("Submitting a new graph %s", graph_id)
        task_graph = self.from_template(platform, locale, from_mar, to_mar)
        res = self.scheduler.createTaskGraph(graph_id, task_graph)
        log.info("Result was: %s", res)
        return graph_id

    def from_template(self, platform, locale, from_mar, to_mar):
        """Reads and populates graph template.

        :param platform: buildbot platform (linux, macosx64)
        :param locale: en-US, de, ka, etc.
        :param from_mar: "from" MAR URL
        :param to_mar: "to" MAR URK
        :return: graph definition dictionary
        """
        template_file = os.path.join(os.path.dirname(__file__), "tasks",
                                     "funsize.yml")
        template = open(template_file).read()
        now = stringDate(datetime.datetime.utcnow())
        now_ms = int(time.time() * 1000)
        encryption_deadline = now_ms + 24 * 3600 * 1000  # 24 hours
        balrog_task_id = slugId()
        template_vars = {
            "update_generator_task_id": slugId(),
            "signing_task_id": slugId(),
            "balrog_task_id": balrog_task_id,
            "now": now,
            "fromNow": fromNow,  # dynamic function call
            "platform": platform,
            "locale": locale,
            "from_MAR": from_mar,
            "to_MAR": to_mar,
            "BALROG_USERNAME_ENC_MESSAGE": encrypt_env_var(
                balrog_task_id, now_ms, encryption_deadline, 'BALROG_USERNAME',
                self.balrog_client.auth[0]),
            "BALROG_PASSWORD_ENC_MESSAGE": encrypt_env_var(
                balrog_task_id, now_ms, encryption_deadline, 'BALROG_PASSWORD',
                self.balrog_client.auth[1])
        }
        rendered = pystache.render(template, template_vars)
        return yaml.safe_load(rendered)


def interesting_buildername(buildername):
    """Matches related builder names

    :type buildername: str or unicode
    :return: boolean
    """
    interesting_names = [n.format(branch=b) for b in BRANCHES for n in
                         BUILDERS]
    return any(re.match(n, buildername) for n in interesting_names)
