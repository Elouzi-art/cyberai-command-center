import os

import pytest


@pytest.fixture
def rand() -> bytes:
    return os.urandom(4096)  # entropie proche de 8 (pas un secret : donnée de test)
