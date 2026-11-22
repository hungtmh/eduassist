"""COMMIT của dependency db phải xong TRƯỚC khi gửi response.

Mặc định FastAPI chạy phần sau `yield` của dependency SAU khi đã gửi response: commit lỗi (vi phạm ràng buộc khi
COMMIT, mất kết nối...) thì client vẫn nhận 200 cho dữ liệu không được lưu. Vì vậy mọi endpoint phải dùng
Depends(db, scope="function").
"""

import re
from contextlib import contextmanager
from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from eduassist.api import platform

API_DIR = Path(__file__).resolve().parents[1] / "src" / "eduassist" / "api"


def test_every_db_dependency_uses_function_scope():
    offenders = []
    for path in API_DIR.glob("*.py"):
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            for call in re.findall(r"Depends\(\s*db\b[^)]*\)", line):
                if 'scope="function"' not in call:
                    offenders.append(f"{path.name}:{lineno}: {call}")
    assert not offenders, 'Depends(db) thiếu scope="function":\n' + "\n".join(offenders)


class _FailingCommit:
    """Kết nối giả: transaction mở được, nhưng COMMIT (thoát khối transaction) báo lỗi."""

    @contextmanager
    def transaction(self):
        yield
        raise RuntimeError("commit failed")


class _Pool:
    @contextmanager
    def connection(self):
        yield _FailingCommit()


def test_commit_failure_reaches_client(monkeypatch):
    import eduassist.db

    monkeypatch.setattr(eduassist.db, "app_pool", lambda: _Pool())
    monkeypatch.setattr("eduassist.cache.discard_pending", lambda conn: None)

    app = FastAPI()

    @app.post("/write")
    def write(conn=Depends(platform.db, scope="function")):
        return {"ok": True}

    with TestClient(app, raise_server_exceptions=False) as client:
        resp = client.post("/write")
    assert resp.status_code == 500, "commit lỗi mà client vẫn nhận thành công"
