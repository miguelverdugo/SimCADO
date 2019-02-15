#!/usr/bin/env python3
"""
SimCADO: A python package to simulate MICADO
"""

from datetime import datetime
from distutils.core import setup
import pytest  # not needed, but stops setup being included by sphinx.apidoc

# Version number
MAJOR = 0
MINOR = 5
ATTR = 'dev1'

VERSION = '%d.%d%s' % (MAJOR, MINOR, ATTR)


def write_version_py(filename='simcado/version.py'):
    '''Write a file version.py'''
    cnt = """
# THIS FILE GENERATED BY SIMCADO SETUP.PY
version = '{}'
date    = '{}'
"""
    timestamp = datetime.utcnow().strftime('%Y-%m-%d %T GMT')
    with open(filename, 'w') as fd:
        fd.write(cnt.format(VERSION, timestamp))


def setup_package():
    # Rewrite the version file every time
    write_version_py()

    setup(name = 'SimCADO',
          version = VERSION,
          description = "MICADO Instrument simulator",
          author = "Kieran Leschinski, Oliver Czoske",
          author_email = """kieran.leschinski@unive.ac.at,
                            oliver.czoske@univie.ac.at""",
          url = "http://homepage.univie.ac.at/kieran.leschinski/",
          package_dir={'simcado': 'simcado'},
          packages=['simcado'],
          package_data = {'simcado': ['data/default.conf']},
          )


if __name__ == '__main__':
    setup_package()
