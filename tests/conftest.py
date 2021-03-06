import pytest
import sys
import os

thisdir = os.path.dirname(os.path.realpath(__file__))
sys.path.append(thisdir)

pytest_plugins = [
    "fixtures._general",
    "fixtures._compute_resource",
    "fixtures._kachery_server",
    "fixtures._mongodb"
]

def pytest_addoption(parser):
    parser.addoption('--container', action='store_true', dest="container",
                 default=False, help="enable container tests")
    parser.addoption('--remote', action='store_true', dest="remote",
                 default=False, help="enable remote tests")

def pytest_configure(config):
    config.addinivalue_line(
        "markers", "container: test runs jobs in a container"
    )
    config.addinivalue_line(
        "markers", "remote: test runs jobs on remote server"
    )

    markexpr_list = []

    if not config.option.container:
        markexpr_list.append('not container')
    
    if not config.option.remote:
        markexpr_list.append('not remote')
    
    if len(markexpr_list) > 0:
        markexpr = ' and '.join(markexpr_list)
        setattr(config.option, 'markexpr', markexpr)