import os
import requests
import logging
import json
import redo

log = logging.getLogger(__name__)

PLATFORM_MAP = json.load(open(
    os.path.join(os.path.dirname(__file__), 'data', 'platform_map.json')))


def _retry_on_http_errors(url, auth, verify, params, errors):
    for _ in redo.retrier(sleeptime=5, max_sleeptime=30, attempts=10):
        try:
            req = requests.get(url, auth=auth, verify=verify, params=params)
            req.raise_for_status()
            return req
        except requests.HTTPError as e:
            if e.response.status_code in errors:
                log.exception("Got HTTP %s trying to reach %s",
                              e.response.status_code, url)
            else:
                raise
    else:
        raise


class BalrogClient(object):

    def __init__(self, api_root, auth, cert=None):
        self.api_root = api_root
        self.auth = auth
        if cert:
            self.verify = cert
        else:
            self.verify = True

    def get_releases(self, product, branch):
        """Returns a list of release names from Balrog.

        :param product: product name, AKA appName
        :param branch: branch name, e.g. mozilla-central
        :return: a list of release names
        """
        url = "{}/releases".format(self.api_root)
        params = {
            "product": product,
            # Adding -nightly-2 (2 stands for the beginning of build ID
            # based on date) should filter out release and latest blobs.
            # This should be changed to -nightly-3 in 3000 ;)
            "name_prefix": "{}-{}-nightly-2".format(product, branch),
            "names_only": True
        }
        params_str = "&".join("=".join([k, str(v)])
                              for k, v in params.iteritems())
        log.info("Connecting to %s?%s", url, params_str)
        req = _retry_on_http_errors(
            url=url, auth=self.auth, verify=self.verify, params=params,
            errors=[500])
        releases = req.json()["names"]
        releases = sorted(releases, reverse=True)
        return releases

    def get_build(self, release, platform, locale):
        update_platform = PLATFORM_MAP[platform][0]
        url = "{}/releases/{}/builds/{}/{}".format(self.api_root, release,
                                                   update_platform, locale)
        log.info("Connecting to %s", url)
        req = _retry_on_http_errors(
            url=url, auth=self.auth, verify=self.verify, params=None,
            errors=[500])
        return req.json()
