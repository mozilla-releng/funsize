import os


def read_file(path):
    with open(path) as f:
        return f.read()


PVT_KEY = read_file(os.path.join(os.path.dirname(__file__), "id_rsa"))
PUB_KEY = read_file(os.path.join(os.path.dirname(__file__), "id_rsa.pub"))
OTHER_PUB_KEY = read_file(os.path.join(os.path.dirname(__file__),
                                       "id_rsa_other.pub"))
