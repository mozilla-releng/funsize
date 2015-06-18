import base64
import json
import os
import pgpy
from taskcluster import slugId
import requests
import redo


def properties_to_dict(props):
    """Convert properties tuple into dict"""
    props_dict = {}
    for prop in props:
        props_dict[prop[0]] = prop[1]
    return props_dict


def encrypt_env_var_message(task_id, start_time, end_time, name, value):
    return {
        "messageVersion": "1",
        "taskId": task_id,
        "startTime": start_time,
        "endTime": end_time,
        "name": name,
        "value": value
    }


def encrypt_env_var(task_id, start_time, end_time, name, value):
    message = str(json.dumps(encrypt_env_var_message(task_id, start_time,
                                                     end_time, name, value)))
    return encrypt(message)


def encrypt(message):
    """Encrypt and base64 encode message.

    :type message: str or unicode
    :return: base64 representation of binary (unarmoured) encrypted message
    """
    key_file = os.path.join(os.path.dirname(__file__), "data",
                            "docker-worker-pub.pem")
    key, _ = pgpy.PGPKey.from_file(key_file)
    msg = pgpy.PGPMessage.new(message)
    encrypted = key.encrypt(msg)
    return base64.b64encode(encrypted.__bytes__())


def stable_slugId():
    """Returns a closure which can be used to generate stable slugIds.
    Stable slugIds can be used in a graph to specify task IDs in multiple
    places without regenerating them, e.g. taskId, requires, etc.
    """
    _cache = {}

    def closure(name):
        if name not in _cache:
            _cache[name] = slugId()
        return _cache[name]

    return closure


def buildbot_to_treeherder(platform):
    # Coming from https://github.com/mozilla/treeherder/blob/master/ui/js/values.js
    m = {
        "linux": "linux32",
        "linux64": "linux64",
        "macosx64": "osx-10-10",
        "win32": "windowsxp",
        "win64": "windows8-64",
    }
    return m[platform]


def revision_to_revision_hash(th_api_root, branch, revision):
    url = "{th_api_root}/project/{branch}/revision-lookup".format(
        th_api_root=th_api_root, branch=branch
    )
    # Use short revision for treeherder API
    revision = revision[:12]
    params = {"revision": revision}
    for _ in redo.retrier(sleeptime=5, max_sleeptime=30):
        try:
            r = requests.get(url, params=params)
            return r.json()[revision]["revision_hash"]
        except:
            pass
    else:
        raise RuntimeError("Cannot fetch revision hash for %s %s", branch,
                           revision)
