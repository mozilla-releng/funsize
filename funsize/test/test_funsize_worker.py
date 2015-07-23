from unittest import TestCase, skipUnless
from funsize.worker import FunsizeWorker, STAGING_BRANCHES, PRODUCTION_BRANCHES
from funsize.balrog import BalrogClient
import mock


class TestFunsizeWorkerFromTemplate(TestCase):

    def generate_task_graph(self, branch):
        balrog_client = BalrogClient("api_root",
                                     ["balrog_user", "balrog_password"])
        s3_info = {"s3_bucket": "b",
                   "aws_access_key_id": "keyid",
                   "aws_secret_access_key": "s"}
        w = FunsizeWorker(connection=None, exchange="exchange",
                          queue_name="qname", scheduler="scheduler",
                          balrog_client=balrog_client, s3_info=s3_info,
                          th_api_root="https://localhost/api",
                          balrog_worker_api_root="http://balrog/api")
        with mock.patch("funsize.worker.revision_to_revision_hash") as m:
            m.return_value = "123123"
            tg = w.from_template("win32", "uk", "https://from_mar/",
                                 "http://to_mar/s", "1234", branch, 3)
            return tg

    def test_deps1(self):
        """Second task should require first task"""
        tg = self.generate_task_graph("branch")
        self.assertEqual(tg["tasks"][1]["requires"][0],
                         tg["tasks"][0]["taskId"])

    def test_deps2(self):
        """Third task should require second task"""
        tg = self.generate_task_graph("branch")
        self.assertEqual(tg["tasks"][2]["requires"][0],
                         tg["tasks"][1]["taskId"])

    @skipUnless(STAGING_BRANCHES, "No staging branches")
    def test_staging_branch(self):
        branch = STAGING_BRANCHES[0]
        tg = self.generate_task_graph(branch)
        payload = tg["tasks"][2]["task"]["payload"]
        self.assertEqual(
            payload["env"]["EXTRA_BALROG_SUBMITTER_PARAMS"],
            "--dummy"
        )

    @skipUnless(PRODUCTION_BRANCHES, "No production branches")
    def test_production_branch(self):
        branch = PRODUCTION_BRANCHES[0]
        tg = self.generate_task_graph(branch)
        payload = tg["tasks"][2]["task"]["payload"]
        self.assertIsNone(payload["env"].get("EXTRA_BALROG_SUBMITTER_PARAMS"))
