from unittest import TestCase
import os
from jose import jwt, jws
from jose.constants import ALGORITHMS
from funsize.utils import properties_to_dict, sign_task
from hypothesis import given
import hypothesis.strategies as st
from . import PVT_KEY, PUB_KEY, OTHER_PUB_KEY


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


class TestTaskSigning(TestCase):

    def test_task_id(self):
        token = sign_task("xyz", pvt_key=PVT_KEY)
        claims = jwt.decode(token, PUB_KEY, algorithms=[ALGORITHMS.RS512])
        assert claims["taskId"] == "xyz"

    def test_exp(self):
        token = sign_task("xyz", pvt_key=PVT_KEY)
        claims = jwt.decode(token, PUB_KEY, algorithms=[ALGORITHMS.RS512])
        assert "exp" in claims

    def test_exp_int(self):
        token = sign_task("xyz", pvt_key=PVT_KEY)
        claims = jwt.decode(token, PUB_KEY, algorithms=[ALGORITHMS.RS512])
        assert isinstance(claims["exp"], int)

    def test_verify(self):
        token = sign_task("xyz", pvt_key=PVT_KEY)
        claims = jws.verify(token, PUB_KEY, algorithms=[ALGORITHMS.RS512])
        assert claims["taskId"] == "xyz"

    def test_verify_bad_signature(self):
        token = sign_task("xyz", pvt_key=PVT_KEY)
        self.assertRaises(jws.JWSError, jws.verify, token, OTHER_PUB_KEY,
                          [ALGORITHMS.RS512])
