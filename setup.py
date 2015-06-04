from setuptools import setup

setup(
    name="funsize",
    version=".5",
    description="Funsize Scheduler",
    author="Mozilla Release Engineering",
    packages=["funsize"],
    include_package_data=True,
    entry_points={
        "console_scripts": [
            "funsize-scheduler = funsize.scheduler:main",
        ],
    },
    install_requires=[
        "amqp",
        "anyjson",
        "argparse",
        "cffi",
        "cryptography",
        "enum34",
        "kombu",
        "PGPy",
        "pycparser",
        "PyHawk-with-a-single-extra-commit",
        "pystache",
        "PyYAML",
        # Because taskcluster hard pins this version...
        "requests==2.4.3",
        "singledispatch",
        "six",
        "taskcluster>=0.0.16",
        "wsgiref",
    ],
)
