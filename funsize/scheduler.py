import argparse
import logging
import site
import taskcluster
import yaml
import os
from kombu import Connection

site.addsitedir(os.path.join(os.path.dirname(__file__), '..'))
from funsize import BalrogClient, FunsizeWorker

log = logging.getLogger(__name__)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("-c", "--config", required=True,
                        type=argparse.FileType(),
                        help="YAML configuration file")
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
    config = yaml.safe_load(args.config)

    api_root = os.environ.get("BALROG_API_ROOT", config["balrog"]["api_root"])
    auth = (
        os.environ.get("BALROG_USERNAME", config["balrog"]["username"]),
        os.environ.get("BALROG_PASSWORD", config["balrog"]["password"]),
    )
    pulse_user = os.environ.get("PULSE_USERNAME", config["pulse"]["user"])
    pulse_password = os.environ.get("PULSE_PASSWORD",
                                    config["pulse"]["password"])
    queue_name = os.environ.get("PULSE_QUEUE_NAME", config["pulse"]["queue"])
    queue_name = 'queue/{user}/{queue_name}'.format(user=pulse_user,
                                                    queue_name=queue_name)
    if "TASKCLUSTER_CLIENT_ID" in os.environ and \
            "TASKCLUSTER_ACCESS_TOKEN" in os.environ:
        tc_opts = {
            "credentials": {
                "clientId": os.environ["TASKCLUSTER_CLIENT_ID"],
                "accessToken": os.environ["TASKCLUSTER_ACCESS_TOKEN"]
            }
        }
    else:
        tc_opts = config["taskcluster"]

    balrog_client = BalrogClient(api_root=api_root, auth=auth)
    scheduler = taskcluster.Scheduler(tc_opts)

    with Connection(hostname='pulse.mozilla.org', port=5671,
                    userid=pulse_user, password=pulse_password,
                    virtual_host='/', ssl=True) as connection:
        FunsizeWorker(connection=connection, queue_name=queue_name,
                      exchange=config["pulse"]["exchange"],
                      balrog_client=balrog_client,
                      scheduler=scheduler).run()
