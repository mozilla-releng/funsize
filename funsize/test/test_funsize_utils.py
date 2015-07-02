from unittest import TestCase
from funsize.utils import (properties_to_dict, encrypt,
                           encrypt_env_var_message, stable_slugId)
from hypothesis import given
import hypothesis.strategies as st


class TestPropertiesToDict(TestCase):

    @given(st.lists(elements=st.text(), min_size=3),
           st.lists(elements=st.text(), min_size=3))
    def test_generic(self, l1, l2):
        props = [l1, l2]
        self.assertDictEqual({l1[0]: l1[1], l2[0]: l2[1]},
                             properties_to_dict(props))

    @given(st.lists(elements=st.text(), min_size=2),
           st.lists(elements=st.text(), min_size=2))
    def test_short(self, l1, l2):
        props = [l1, l2]
        self.assertDictEqual({l1[0]: l1[1], l2[0]: l2[1]},
                             properties_to_dict(props))

    @given(st.lists(elements=st.text(), max_size=1),
           st.lists(elements=st.text(), min_size=2))
    def test_truncated(self, l1, l2):
        props = [l1, l2]
        self.assertDictEqual({l2[0]: l2[1]},
                             properties_to_dict(props))


class TestEncryptEnvVarMessage(TestCase):

    @given(st.text(), st.one_of(st.floats(), st.integers()),
           st.one_of(st.floats(), st.integers()), st.text(), st.text())
    def test_message_format(self, taskId, startTime, endTime, name, value):
        self.assertDictEqual(
            encrypt_env_var_message(taskId, startTime, endTime, name, value),
            {
                "messageVersion": "1",
                "taskId": taskId,
                "startTime": startTime,
                "endTime": endTime,
                "name": name,
                "value": value
            }
        )


class TestEncrypt(TestCase):

    @given(st.text())
    def test_generic(self, text):
        self.assertTrue(encrypt(text).startswith("wcB"))


class TestStableSlugIdClosure(TestCase):

    @given(st.text())
    def test_repeat(self, text):
        s = stable_slugId()
        self.assertEqual(s(text), s(text))

    def test_not_equal(self):
        s = stable_slugId()
        self.assertNotEqual(s("first"), s("second"))

    @given(st.text())
    def test_invalidate(self, text):
        s1 = stable_slugId()
        s2 = stable_slugId()
        self.assertNotEqual(s1(text), s2(text))
