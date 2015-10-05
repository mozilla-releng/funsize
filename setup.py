from setuptools import setup

setup(
    name="funsize",
    version="0.44",
    description="Funsize Scheduler",
    author="Mozilla Release Engineering",
    packages=["funsize"],
    include_package_data=True,
    # Not zip safe because we have data files in the package
    zip_safe=False,
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
        # PGPy depends on this _specific_ version of cryptography
        "cryptography==0.6",
        "enum34",
        "kombu",
        "more_itertools",
        "PGPy",
        "pycparser",
        "PyHawk-with-a-single-extra-commit",
        "Jinja2",
        "PyYAML",
        "redo",
        # Because taskcluster hard pins this version...
        "requests==2.4.3",
        "singledispatch",
        "six",
        "taskcluster>=0.0.26",
        "wsgiref",
    ],
    tests_require=[
        'hypothesis',
        'pytest',
        'mock',
    ],
)
