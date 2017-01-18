from unittest import TestCase, skipUnless
from funsize.worker import FunsizeWorker, STAGING_BRANCHES, PRODUCTION_BRANCHES
from funsize.balrog import BalrogClient
import mock
from . import PVT_KEY


class TestFunsizeWorkerFromTemplate(TestCase):

    def generate_task_graph(self, branch, subchunk=None):
        balrog_client = BalrogClient("api_root",
                                     ["balrog_user", "balrog_password"])
        s3_info = {"s3_bucket": "b",
                   "aws_access_key_id": "keyid",
                   "aws_secret_access_key": "s"}
        w = FunsizeWorker(connection=None,
                          bb_exchange="bb_exchange",
                          tc_exchange="tc_exchange",
                          queue_name="qname", scheduler="scheduler",
                          balrog_client=balrog_client, s3_info=s3_info,
                          th_api_root="https://localhost/api",
                          balrog_worker_api_root="http://balrog/api",
                          pvt_key=PVT_KEY)
        with mock.patch("funsize.worker.revision_to_revision_hash") as m:
            m.return_value = "123123"
            extra = [
                {"locale": "en-CA", "from_mar": "https://from/mar",
                 "to_mar": "https://to/mar"}
            ]
            tg = w.from_template(
                platform="win32", revision="1234", branch=branch,
                update_number=1, chunk_name=1, extra=extra, subchunk=subchunk,
                mar_signing_format="mar_sha384")
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

    def test_subchunk_None(self):
        tg = self.generate_task_graph("branch")
        symbol = tg["tasks"][1]["task"]["extra"]["treeherder"]["symbol"]
        self.assertEqual(symbol, "1s")

    def test_subchunk_not_None(self):
        tg = self.generate_task_graph("branch", 2)
        symbol = tg["tasks"][1]["task"]["extra"]["treeherder"]["symbol"]
        self.assertEqual(symbol, "1.2s")

    def test_mar_signing_format(self):
        """Ensure MAR signing format"""
        tg = self.generate_task_graph("branch")
        assert 'project:releng:signing:format:mar_sha384' in tg["tasks"][1]["task"]["scopes"]
