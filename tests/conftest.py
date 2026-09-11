import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

pytest_plugins = []



@pytest.fixture()
def platform_home(tmp_path):
    """An isolated platform home directory for a test-scoped deployment."""
    home = tmp_path / "platform_home"
    home.mkdir()
    return home


@pytest.fixture()
def settings(platform_home):
    from qsmlops.core.settings import load_settings

    return load_settings(env="testing", overrides={"home": platform_home})


@pytest.fixture()
def container(settings):
    from qsmlops.core.context import ServiceContainer

    c = ServiceContainer(settings)
    c.initialize()
    yield c
    c.close()


@pytest.fixture()
def api_client(container):
    from fastapi.testclient import TestClient

    from qsmlops.app import build_app

    return TestClient(build_app(container))
