from unittest import TestCase
from funsize.utils import properties_to_dict
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
