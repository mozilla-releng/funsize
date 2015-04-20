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
