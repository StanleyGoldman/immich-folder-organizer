import pytest

from immich_folder_organizer.immich_client import ImmichClient
from tests.fake_immich import FakeImmich


@pytest.fixture
def server():
    fake = FakeImmich()
    fake.start()
    yield fake
    fake.stop()


@pytest.fixture
def client(server):
    return ImmichClient(server.base_url, "test-key")
