import base64
import json
import os
import pgpy
from taskcluster import slugId


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
    # TODO: load the key once
    """Encrypte and base64 encode message.

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
