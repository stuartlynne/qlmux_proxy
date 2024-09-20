# -*- coding: utf-8 -*-


"""setup.py: setuptools control."""


import re
from setuptools import setup


version = re.search(
    '^__version__\s*=\s*"(.*)"',
    open('qlmux/race_proxy.py').read(),
    re.M
    ).group(1)


with open("README.md", "rb") as f:
    long_descr = f.read().decode("utf-8")


setup(
    name = "qlmux",
    packages = ["qlmux",],
    #install_requires = [ "enum34", "easysnmp", "flask", "pysnmp", "yattag", ],
    install_requires = [ "enum34", "easysnmp", "flask", "yattag", ],
    entry_points = {
        "console_scripts": ['race_proxy = qlmux.race_proxy:raceproxymain'],
        },
    package_data = {
        'qlmux': ['static/*/*'],
        },
    version = version,
    description = "RaceDb Proxy for Brother QL Label Printers and Impinj RFID readers",
    long_description = long_descr,
    author = "Stuart Lynne",
    author_email = "stuart.lynne@gmail.com",
    url = "http://bitbucket.org/stuartlynne/qlmux_proxy",
    )
