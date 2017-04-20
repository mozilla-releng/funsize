import datetime
import logging
import time
import os
import re
import json
import requests
import yaml
from collections import defaultdict
from kombu import Exchange, Queue
from kombu.mixins import ConsumerMixin
from taskcluster import slugId, stringDate, fromNow, stableSlugId
from taskcluster.exceptions import TaskclusterFailure
# Already importing Queue from kombu, above.
from taskcluster import Queue as tc_Queue
from jinja2 import Template, StrictUndefined
from more_itertools import chunked
from functools import partial


from funsize.utils import properties_to_dict, revision_to_revision_hash, \
    buildbot_to_treeherder, encryptEnvVar_wrapper, sign_task

log = logging.getLogger(__name__)

# TODO: move these to config
PRODUCTION_BRANCHES = ['mozilla-central', 'mozilla-aurora', 'oak']
STAGING_BRANCHES = []
PLATFORMS = ['linux', 'linux64', 'win32', 'win64', 'macosx64']
BUILDERS = [
    r'^WINNT \d+\.\d+ (x86-64 )?{branch} nightly',
    r'^Linux (x86-64 )?{branch} nightly',
    r'^OS X \d+\.\d+ {branch} nightly',
    r'^Firefox {branch} (linux|linux64|win32|win64|macosx64) l10n nightly-\d+',
    r'^Firefox {branch} (linux|linux64|win32|win64|macosx64) l10n nightly',
]


def parse_taskcluster_message(payload):
    """Get the necessary data for funsize, from a TC pulse message

    Args:
        payload (kombu.Message.body): the pulse message payload
    Returns:
        dict: all the task information needed to submit a partial
            mar generation task.

    Funsize listens to for the signing tasks being complete.
    This has the disadvantage that the task information only lists
    the signed artifacts, which doesn't include  balrog_props.json

    balrog_props.json contains data we need to submit to funsize,
    so we examine the current task's dependencies to work out what
    the previous step was, and get that task's artifacts. Among
    those will be balrog_props.json, which will contain the appName,
    platform and branch
    """

    graph_data = dict()
    graph_data['locales'] = list()
    graph_data['mar_urls'] = dict()

    # taskcluster.Queue, not kombu.Queue
    queue = tc_Queue()

    # taskid = payload['status']['taskId']
    taskid = payload.get('status', dict()).get('taskId')

    if not taskid:
        return

    try:
        task_definition = queue.task(taskid)
    except TaskclusterFailure as excp:
        log.exception("Unable to load task definition for %s", taskid)
        return

    previous_task = task_definition['dependencies'][0]

    try:
        previous_definition = queue.task(previous_task)
    except TaskclusterFailure as excp:
        log.exception("Unable to load task definition for %s", taskid)
        return

    # Sadly not available by other means, unless we trust that one of the
    # pulse routes will remain the same.
    graph_data['revision'] = previous_definition[
        'payload']['env']['GECKO_HEAD_REV']

    previous_artifacts = queue.listLatestArtifacts(previous_task)

    # We just need the data from one balrog_props.json, as the
    # fields we want are all the same.
    props_name = next(a['name'] for a in previous_artifacts[
        'artifacts'] if 'balrog_props.json' in a['name'])
    balrog_props = queue.getLatestArtifact(previous_task, props_name)
    log.debug("balrog_props.json: %s", balrog_props)
    try:
        # We don't do Android build partials
        if 'Fennec' in balrog_props['properties']['appName']:
            return
        graph_data['product'] = balrog_props['properties']['appName']

        # en-US signing jobs list platform as 'stage_platform'
        graph_data['platform'] = balrog_props['properties'].get('platform')
        if not graph_data['platform']:
            graph_data['platform'] = balrog_props['properties']['stage_platform']
        graph_data['branch'] = balrog_props['properties']['branch']
        graph_data['mar_signing_format'] = balrog_props[
            'properties'].get('mar_signing_format', 'mar')
    except KeyError as excp:
        # android builds don't appear to have the right fields, so log error but
        # not exception
        log.error("Unable to extract data from balrog_props: %s, %s",
                  excp, balrog_props)
        return

    signing_artifacts = queue.listLatestArtifacts(taskid)

    for artifact in signing_artifacts['artifacts']:

        # skip over the artifacts that aren't relevant
        if 'target.complete.mar' not in artifact['name']:
            continue

        # if the mar url doesn't have a locale inside then
        # it is en-US.  Otherwise, parse for locale. This isn't
        # stored in the task's metadata at the moment.

        # Ideally we should check that an extracted locale
        # is valid before continuing, but the builds produce
        # some that aren't listed in locales.locale_alias, such
        # as 'ast'  ('ast_es' is present in the library)
        if artifact['name'] == 'public/build/update/target.complete.mar':
            mar_locale = 'en-US'
        else:
            try:
                # public/build/<locale name>/target.complete.mar
                mar_locale = artifact['name'].split('/')[-2]
            except IndexError:
                log.error("Unable to extract locale from %s",
                          artifact['name'])
                continue

        # When we upgrade the taskcluster python library to >=0.3.6,
        # use this form:
        # completeMarUrl = queue.buildUrl('getLatestArtifact', replDict={
        #    'taskId': taskid,
        #    'name': artifact['name'],
        # })
        try:
            completeMarUrl = queue.buildUrl(
                'getLatestArtifact',
                taskId=taskid,
                name=artifact['name']
            )
        except TaskclusterFailure as excp:
            log.exception(excp)
            return
        graph_data['locales'].append(mar_locale)
        graph_data['mar_urls'][mar_locale] = completeMarUrl

    return graph_data


def parse_buildbot_message(payload):
    """Parse incoming buildbot pulse message.

    Args:
        payload (kombu.Message.body): the pulse message payload
    Returns:
        dict: all the task information needed to submit a partial
            mar generation task.

    This is extracted from the previous incarnation, which only
    understood buildbot messages. The relevant details are all
    in the pulse message, so just need to be extracted.
    """
    graph_data = dict()

    buildername = payload["build"]["builderName"]
    if not interesting_buildername(buildername):
        log.debug("Ignoring %s: not interested", buildername)
        return

    job_result = payload["results"]
    if job_result != 0:
        log.debug("Ignoring %s with result %s", buildername, job_result)
        return

    properties = properties_to_dict(payload["build"]["properties"])

    # try to guess chunk number, last digit in the buildername
    try:
        graph_data['chunk_name'] = int(buildername.split("-")[-1])
    except ValueError:
        # undefined (en-US) use 0
        graph_data['chunk_name'] = "en-US"

    if "locales" in properties:
        log.debug("L10N repack detected")
        funsize_info = json.loads(properties['funsize_info'])
        locales = json.loads(properties['locales'])
        graph_data['locales'] = [locale for locale, result in locales.iteritems()
                                 if str(result).lower() == 'success' or
                                 str(result) == '0']
        graph_data['mar_urls'] = funsize_info['completeMarUrls']
        graph_data['platform'] = funsize_info["platform"]
        graph_data['branch'] = funsize_info["branch"]
        graph_data['product'] = funsize_info["appName"]
        graph_data['mar_signing_format'] = funsize_info.get(
            'mar_signing_format', 'mar')
        graph_data['revision'] = properties['revision']
    else:
        graph_data['locales'] = ['en-US']
        graph_data['mar_urls'] = {'en-US': properties['completeMarUrl']}
        graph_data['platform'] = properties['platform']
        graph_data['branch'] = properties['branch']
        graph_data['product'] = properties['appName']
        graph_data['revision'] = properties['revision']
        graph_data['mar_signing_format'] = properties.get(
            'mar_signing_format', 'mar')

    return graph_data


class FunsizeWorker(ConsumerMixin):

    def __init__(self, connection, queue_name, bb_exchange, tc_exchange,
                 balrog_client, scheduler, s3_info, th_api_root,
                 balrog_worker_api_root, pvt_key):
        """Funsize consumer worker
        :type connection: kombu.Connection
        :param queue_name: Full queue name, including queue/<user> prefix
        :type exchange: basestring
        :type balrog_client: funsize.balrog.BalrogClient
        :type scheduler: taskcluster.Scheduler
        """
        self.connection = connection
        # Using passive mode is important, otherwise pulse returns 403
        self.bb_exchange = Exchange(bb_exchange, type='topic', passive=True)
        self.tc_exchange = Exchange(tc_exchange, type='topic', passive=True)
        self.queue_name = queue_name
        self.balrog_client = balrog_client
        self.scheduler = scheduler
        self.s3_info = s3_info
        self.th_api_root = th_api_root
        self.balrog_worker_api_root = balrog_worker_api_root
        self.pvt_key = pvt_key

    @property
    def bb_routing_keys(self):
        """Returns an explicit list of routing patterns.

        Instead of using "build.*.*.finished", which generates a lot of noise,
        FunsizeWorker uses explicit list of routing keys to match builders we
        are interested in.
        """
        jobs = [
            # TODO: move to configs
            'build.{branch}-{platform}-nightly.*.finished',
            # old style l10n repacks
            'build.{branch}-{platform}-l10n-nightly.*.finished',
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
                for branch in PRODUCTION_BRANCHES + STAGING_BRANCHES
                for platform in PLATFORMS]

    @property
    def tc_routing_keys(self):
        """Returns an explicit list of routing patterns for taskcluster builds.

        All the Taskcluster signing jobs publish their announcements
        through the below routes, specifically so that funsize can
        read them without much analysis of what's relevant.
        """

        # TODO: move to configs
        return [
            u'route.index.project.releng.funsize.level-3.mozilla-central',
            u'route.index.project.releng.funsize.level-3.mozilla-aurora',
            u'route.project.releng.funsize.level-3.mozilla-central',
            u'route.project.releng.funsize.level-3.mozilla-aurora',
            u'route.project.releng.funsize.level-3.oak',
        ]

    @property
    def queues(self):
        """List of queues used by worker.
        Multiple queues are used to track multiple routing keys.
        """
        bb_queues = [Queue(name=self.queue_name, exchange=self.bb_exchange,
                           routing_key=routing_key, durable=True,
                           exclusive=False, auto_delete=False)
                     for routing_key in self.bb_routing_keys]
        tc_queues = [Queue(name=self.queue_name, exchange=self.tc_exchange,
                           routing_key=routing_key, durable=True,
                           exclusive=False, auto_delete=False)
                     for routing_key in self.tc_routing_keys]
        return bb_queues + tc_queues

    def get_consumers(self, Consumer, channel):
        """Implement parent's method called to get the list of consumers"""
        # Set prefetch_count to 1 to avoid blocking other workers
        channel.basic_qos(prefetch_size=0, prefetch_count=1, a_global=False)
        return [Consumer(queues=self.queues, callbacks=[self.process_message])]

    def process_message(self, body, message):
        """Top level callback processing pulse messages.
        The callback tries to handle and log all exceptions

        :type body: kombu.Message.body
        :type message: kombu.Message
        """
        try:
            self.dispatch_message(body, message)
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

    def dispatch_message(self, body, message):
        """Dispatches incoming pulse messages.
        If the method detects L10N repacks, it creates multiple Taskcluster
        tasks, otherwise a single en-US task is created.
        :type body: kombu.Message.body
        """

        if self.is_tc_message(message):
            # Useful TC data is in message.payload, unlike
            # Buildbot's which is in body['payload']
            log.debug("Message from Taskcluster: %s (%s)", message.payload, message)
            gdata = parse_taskcluster_message(message.payload)
            log.info("Parsed message from Taskcluster: %s", gdata)
        else:
            # buildbot routes have wildcards in which adds to the
            # overhead of working out whether it's one of ours. Since
            # we were accepting all of them before, continue to do so.
            gdata = parse_buildbot_message(body['payload'])

        if not gdata:
            log.error("No data about the task graph available")
            return

        self.create_partials(
            product=gdata["product"],
            branch=gdata["branch"],
            platform=gdata["platform"],
            locales=gdata['locales'],
            revision=gdata["revision"],
            mar_urls=gdata['mar_urls'],
            chunk_name=gdata.get('chunk_name', 1),
            mar_signing_format=gdata['mar_signing_format'],
        )

    def is_tc_message(self, message):
        """Determine whether this message came from taskcluster.

        Args:
            message (kombu.Message): the message under examination
        Returns:
            bool: True if the message came from a taskcluster route, False otherwise.

        If any of the routes used in the message exist in the
        taskcluster routing keys we're looking at, then it is
        a taskcluster message.
        """

        # some messages we get don't have a CC list
        routes = [message.delivery_info['routing_key']] + \
            message.headers.get('CC', list())

        return any(r in self.tc_routing_keys for r in routes)

    def get_builds(self, product, platform, branch, locale, dest_mar, count=4):
        """Find relevant releases in Balrog
        Not all releases have all platforms and locales, due
        to Taskcluster migration.

        Args:
            product (str): capitalized product name, AKA appName, e.g. Firefox
            branch (str): branch name (mozilla-central)
            platform (str): buildbot/taskcluster platform (linux, macosx64)
            locale (str): locale under investigation
        Returns:
            json object from balrog api
        """
        last_releases = self.balrog_client.get_releases(product, branch)

        builds = list()

        for release in last_releases:
            if len(builds) >= count:
                return builds
            try:
                build_from = self.balrog_client.get_build(
                    release, platform, locale)

                # Balrog may or may not have information about the latest
                # release already. Don't make partials, as the diff
                # won't be useful.
                if build_from['completes'][0]['fileUrl'] != dest_mar:
                    builds.append(build_from)
            except requests.HTTPError as excp:
                log.debug("Build %s/%s/%s not found: %s",
                          release, platform, locale, excp)
                continue

    def create_partials(self, product, branch, platform, locales, revision,
                        mar_urls, mar_signing_format, chunk_name=1):
        """Calculates "from" and "to" MAR URLs and calls create_task_graph().
        Currently "from" MAR is 2 releases behind to avoid duplication of
        existing CI partials.
        :param product: capitalized product name, AKA appName, e.g. Firefox
        :param branch: branch name (mozilla-central)
        :param platform: buildbot/taskcluster platform (linux, macosx64)
        :param locales: list of locales
        :param revision: revision of the "to" build
        :param mar_urls: dictionary of {locale:mar file url} for each locale
        :param chunk_name: chunk name
        """
        # TODO: move limit to config
        partial_limit = 4
        per_chunk = 5

        tasks = defaultdict(list)

        for locale in locales:
            to_mar = mar_urls.get(locale)
            log.info("Build to: %s", to_mar)
            latest_releases = self.get_builds(
                product, platform, branch, locale, to_mar, partial_limit)
            for update_number, build_from in enumerate(latest_releases, start=1):
                log.info("Build from: %s", build_from)
                try:
                    from_mar = build_from['completes'][0]['fileUrl']
                except ValueError as excp:
                    log.error("Unable to extract fileUrl from %s: %s",
                              build_from, excp)
                    continue

                tasks[update_number].append({
                    "locale": locale,
                    "from_mar": from_mar,
                    "to_mar": to_mar,
                })

        for update_number in tasks:
            for subchunk, extra in enumerate(chunked(tasks[update_number], per_chunk), start=1):
                all_locales = [e["locale"] for e in extra]
                log.info("New Funsize task for %s", all_locales)
                self.submit_task_graph(
                    branch=branch, revision=revision, platform=platform,
                    update_number=update_number, chunk_name=chunk_name,
                    extra=extra, subchunk=subchunk,
                    mar_signing_format=mar_signing_format)

    def submit_task_graph(self, branch, revision, platform, update_number,
                          chunk_name, subchunk, extra, mar_signing_format):
        graph_id = slugId()
        log.info("Submitting a new graph %s", graph_id)
        task_graph = self.from_template(
            extra=extra, update_number=update_number, platform=platform,
            chunk_name=chunk_name, subchunk=subchunk, revision=revision,
            branch=branch, mar_signing_format=mar_signing_format)
        log.debug("Graph definition: %s", task_graph)
        res = self.scheduler.createTaskGraph(graph_id, task_graph)
        log.info("Result was: %s", res)
        return graph_id

    def from_template(self, platform, revision, branch, update_number,
                      chunk_name, subchunk, extra, mar_signing_format):
        """Reads and populates graph template.

        :param platform: buildbot platform (linux, macosx64)
        :param locale: en-US, de, ka, etc.
        :param from_mar: "from" MAR URL
        :param to_mar: "to" MAR URL
        :return: graph definition dictionary
        """
        template_file = os.path.join(os.path.dirname(__file__), "tasks",
                                     "funsize.yml")
        extra_balrog_submitter_params = None
        if branch in STAGING_BRANCHES:
            extra_balrog_submitter_params = "--dummy"

        template_vars = {
            # Stable slugId
            "stableSlugId": stableSlugId(),
            # Now in ISO format
            "now": stringDate(datetime.datetime.utcnow()),
            # Now in ms
            "now_ms": time.time() * 1000,
            "fromNow": fromNow,
            "platform": platform,
            "s3_bucket": self.s3_info["s3_bucket"],
            "aws_access_key_id": self.s3_info["aws_access_key_id"],
            "aws_secret_access_key": self.s3_info["aws_secret_access_key"],
            "balrog_api_root": self.balrog_worker_api_root,
            "balrog_username": self.balrog_client.auth[0],
            "balrog_password": self.balrog_client.auth[1],
            "encryptEnvVar": encryptEnvVar_wrapper,
            "revision": revision,
            "branch": branch,
            "treeherder_platform": buildbot_to_treeherder(platform),
            "revision_hash": revision_to_revision_hash(self.th_api_root,
                                                       branch, revision),
            "update_number": update_number,
            "extra_balrog_submitter_params": extra_balrog_submitter_params,
            "extra": extra,
            "chunk_name": chunk_name,
            "subchunk": subchunk,
            "sign_task": partial(sign_task, pvt_key=self.pvt_key),
            "mar_signing_format": mar_signing_format,
        }
        with open(template_file) as f:
            template = Template(f.read(), undefined=StrictUndefined)
        rendered = template.render(**template_vars)
        return yaml.safe_load(rendered)


def interesting_buildername(buildername):
    """Matches related builder names

    :type buildername: str or unicode
    :return: boolean
    """
    interesting_names = [n.format(branch=b) for b in
                         PRODUCTION_BRANCHES + STAGING_BRANCHES
                         for n in BUILDERS]
    return any(re.match(n, buildername) for n in interesting_names)
