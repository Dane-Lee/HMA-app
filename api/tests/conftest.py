from __future__ import annotations

import shutil
import time
import gc
from pathlib import Path
from uuid import uuid4

import pytest


@pytest.fixture
def tmp_path():
    base = Path.cwd() / "test-runs"
    base.mkdir(exist_ok=True)
    path = base / uuid4().hex
    path.mkdir()
    try:
        yield path
    finally:
        try:
            path.resolve().relative_to(base.resolve())
        except ValueError:
            return
        gc.collect()
        for _ in range(5):
            shutil.rmtree(path, ignore_errors=True)
            if not path.exists():
                break
            time.sleep(0.1)
