from unittest import TestCase
from funsize.worker import FunsizeWorker
from funsize.balrog import BalrogClient


class TestFunsizeWorkerFromTemplate(TestCase):

    def setUp(self):
        balrog_client = BalrogClient("api_root",
                                     ["balrog_user", "balrog_password"])
        w = FunsizeWorker(connection=None, exchange="exchange",
                          queue_name="qname", scheduler="scheduler",
                          balrog_client=balrog_client)
        self.tg = w.from_template("win32", "uk", "https://from_mar/",
                                  "http://to_mar/s")

    def test_deps1(self):
        """Second task should require first task"""
        self.assertEqual(self.tg["tasks"][1]["requires"][0],
                         self.tg["tasks"][0]["taskId"])

    def test_deps2(self):
        """Third task should require second task"""
        self.assertEqual(self.tg["tasks"][2]["requires"][0],
                         self.tg["tasks"][1]["taskId"])
