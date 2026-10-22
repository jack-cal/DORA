"""Reserve legacy warning-state filenames; no wallet send restrictions."""

import os
from pathlib import Path

POLICY_NAME = "chain-safety.json"


def policy_filename(database_name='node.sqlite'):
    if (type(database_name) is not str or not database_name
            or Path(database_name).name != database_name):
        raise ValueError('Database name must be a filename without a directory')
    return (POLICY_NAME if os.path.normcase(database_name) == os.path.normcase('node.sqlite')
            else database_name + '.' + POLICY_NAME)
