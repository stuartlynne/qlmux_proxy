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
    packages = ["qlmux",],
    install_requires = [ "enum34", "easysnmp", "json-cfg", "Pillow", "brother_ql", "flask", "pysnmp-lextudio", "yattag", ],
    entry_points = {
        "console_scripts": ['QLLABELS = qlmux.QLLABELS:main', 'race_proxy = qlmux.race_proxy:raceproxymain'],
        },
    version = version,
    description = "RaceDb Proxy for Brother QL Label Printers and Impinj RFID readers",
    long_description = long_descr,
    author = "Stuart Lynne",
    author_email = "stuart.lynne@gmail.com",
    url = "http://bitbucket.org/stuartlynne/qlmux_proxy",
    )
