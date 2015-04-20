from unittest import TestCase
from funsize.utils import properties_to_dict, encrypt, encrypt_env_var_message

class TestPropertiesToDict(TestCase):

    def test_generic(self):
        props = [["a", "b", "c"], ["x", "y", "z"]]
        self.assertDictEqual({"a": "b", "x": "y"}, properties_to_dict(props))


class TestEncryptEnvVarMessage(TestCase):

    def test_message_format(self):
        self.assertDictEqual(
            encrypt_env_var_message("tAsKiD", 1234, 12345, "NaMe", "vAlUe"),
            {
                "messageVersion": "1",
                "taskId": "tAsKiD",
                "startTime": 1234,
                "endTime": 12345,
                "name": "NaMe",
                "value": "vAlUe"
            }
        )


class TestEncrypt(TestCase):

    def test_generic(self):
        self.assertTrue(encrypt("hello").startswith("wcB"))