from unittest import TestCase
from funsize.utils import (properties_to_dict, encrypt,
                           encrypt_env_var_message, stable_slugId)


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


class TestStableSlugIdClosure(TestCase):

    def test_repeat(self):
        s = stable_slugId()
        self.assertEqual(s("first"), s("first"))

    def test_not_equal(self):
        s = stable_slugId()
        self.assertNotEqual(s("first"), s("second"))

    def test_invalidate(self):
        s1 = stable_slugId()
        s2 = stable_slugId()
        self.assertNotEqual(s1("first"), s2("first"))
