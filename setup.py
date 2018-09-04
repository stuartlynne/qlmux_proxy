# -*- coding: utf-8 -*-


"""setup.py: setuptools control."""


import re
from setuptools import setup


version = re.search(
    '^__version__\s*=\s*"(.*)"',
    open('qlmux/qlmuxd.py').read(),
    re.M
    ).group(1)


with open("README.md", "rb") as f:
    long_descr = f.read().decode("utf-8")


setup(
    name = "qlmux",
    packages = ["qlmux"],
    entry_points = {
        "console_scripts": ['qlmuxd = qlmux.qlmuxd:main']
        },
    version = version,
    description = "Python command line application bare bones template.",
    long_description = long_descr,
    author = "Stuart Lynne",
    author_email = "stuart.lynne@gmail.com",
    url = "http://gehrcke.de/2014/02/distributing-a-python-command-line-application",
    )
