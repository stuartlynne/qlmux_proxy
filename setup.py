# -*- coding: utf-8 -*-

try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

try:
    import pypandoc
    LDESC = open('README.md', 'r').read()
    LDESC = pypandoc.convert(LDESC, 'rst', format='md')
except (ImportError, IOError, RuntimeError) as e:
    print("Could not create long description:")
    print(str(e))
    LDESC = ''

setup(name='qlmux',
      version = '0.1.dev0',
      description = 'Python package to multiplex port 9100 jobs pools Brother QL label printers',
      long_description = LDESC,
      author = 'Stuart Lynne',
      author_email = 'stuart.lynne@gmail.com',
      url = 'https://bitbucket.org/stuartlynne/qlmux',
      license = 'GPL',
      packages = ['qlmux', ],
      entry_points = {
          'console_scripts': [
              'brother_ql = qlmux:main',
          ],
      },
      include_package_data = False,
      zip_safe = True,
      platforms = 'any',
      install_requires = [
          "snmp",
      ],
      extras_require = {
      },
      keywords = 'Brother QL-710W QL-1060N',
      classifiers = [
          'Development Status :: 4 - Beta',
          'Operating System :: OS Independent',
          'License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)',
          'Programming Language :: Python',
          'Programming Language :: Python :: 3',
          'Topic :: Scientific/Engineering :: Visualization',
          'Topic :: System :: Hardware :: Hardware Drivers',
      ]
)



