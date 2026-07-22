"""算力通 · 健康检查 + 路由集成测试。

使用 TestClient，不依赖真实数据库（通过临时文件 + 依赖注入）。
"""

import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# ── 设置测试数据库路径（必须在导入 app 前） ────────
_tmpdir = tempfile.mkdtemp(prefix="suanlitong_test_")
_test_db_path = str(Path(_tmpdir) / "test.db")
import os as _os  # noqa: E402

_os.environ["DATABASE_URL"] = f"sqlite:///{_test_db_path}"

from src.backend.app.db import get_db, init_db  # noqa: E402
from src.backend.app.main import app  # noqa: E402

# ── SQL 模板 ──────────────────────────

_SQL_INSERT_PRICE = (
    "INSERT INTO price_snapshots"
    " (provider, gpu_type, price_per_hour, spot_price, region)"
    " VALUES (?, ?, ?, ?, ?)"
)

# ── Fixtures ──────────────────────────

@pytest.fixture(autouse=True)
def _clean_db():
    init_db()
    with get_db() as conn:
        for table in ("price_snapshots", "gpu_instances", "users"):
            conn.execute(f"DELETE FROM {table}")


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


# ── 健康检查 ──────────────────────────


class TestHealth:
    def test_health_returns_ok(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["version"] == "0.1.0"

    def test_health_content_type(self, client):
        resp = client.get("/health")
        assert resp.headers["content-type"].startswith("application/json")


# ── 价格 ─────────────────────────


class TestPrices:
    def test_empty_returns_list(self, client):
        resp = client.get("/api/v1/prices")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_filter_by_gpu_type(self, client):
        with get_db() as conn:
            conn.execute(
                _SQL_INSERT_PRICE,
                ("阿里云", "A100", 28.50, 12.80, "cn-beijing"),
            )
            conn.execute(
                _SQL_INSERT_PRICE,
                ("华为云", "H100", 48.00, 24.00, "cn-north-4"),
            )

        resp = client.get("/api/v1/prices?gpu_type=A100")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["provider"] == "阿里云"
        assert data[0]["gpu_type"] == "A100"

    def test_latest_price_only(self, client):
        with get_db() as conn:
            conn.execute(
                _SQL_INSERT_PRICE,
                ("阿里云", "A100", 30.00, 15.00, "cn-beijing"),
            )
            conn.execute(
                _SQL_INSERT_PRICE,
                ("阿里云", "A100", 26.00, 11.00, "cn-beijing"),
            )

        resp = client.get("/api/v1/prices?gpu_type=A100")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["price_per_hour"] == 26.00


# ── 实例 CRUD ─────────────────────────


class TestInstances:
    def test_create_returns_201(self, client):
        resp = client.post(
            "/api/v1/instances",
            json={
                "provider": "阿里云",
                "gpu_type": "A100",
                "image": "ubuntu-22.04",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["provider"] == "阿里云"
        assert data["gpu_type"] == "A100"
        assert data["status"] == "pending"
        assert data["terminated_at"] is None

    def test_list_returns_instances(self, client):
        payload1 = {
            "provider": "阿里云",
            "gpu_type": "A100",
            "image": "img1",
        }
        payload2 = {
            "provider": "华为云",
            "gpu_type": "H100",
            "image": "img2",
        }
        client.post("/api/v1/instances", json=payload1)
        client.post("/api/v1/instances", json=payload2)

        resp = client.get("/api/v1/instances")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_terminate_updates_status(self, client):
        resp = client.post(
            "/api/v1/instances",
            json={
                "provider": "腾讯云",
                "gpu_type": "4090",
                "image": "ubuntu",
            },
        )
        iid = resp.json()["id"]

        resp = client.delete(f"/api/v1/instances/{iid}")
        assert resp.status_code == 200
        assert resp.json()["status"] == "terminated"
        assert resp.json()["terminated_at"] is not None

    def test_terminate_nonexistent_returns_404(self, client):
        resp = client.delete("/api/v1/instances/99999")
        assert resp.status_code == 404

    def test_double_terminate_returns_400(self, client):
        resp = client.post(
            "/api/v1/instances",
            json={
                "provider": "阿里云",
                "gpu_type": "A100",
                "image": "img",
            },
        )
        iid = resp.json()["id"]
        client.delete(f"/api/v1/instances/{iid}")
        resp = client.delete(f"/api/v1/instances/{iid}")
        assert resp.status_code == 400

    def test_terminated_not_in_list(self, client):
        resp = client.post(
            "/api/v1/instances",
            json={
                "provider": "阿里云",
                "gpu_type": "A100",
                "image": "img",
            },
        )
        iid = resp.json()["id"]
        client.delete(f"/api/v1/instances/{iid}")

        resp = client.get("/api/v1/instances")
        assert len(resp.json()) == 0
