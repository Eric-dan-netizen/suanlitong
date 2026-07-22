"""算力通 · 健康检查 + 路由集成测试。

使用 TestClient，不依赖真实数据库（通过临时文件 + 依赖注入）。
"""

import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# ── 在导入 app 前覆写 DATABASE_URL ──────────────────
_tmpdir = tempfile.mkdtemp(prefix="suanlitong_test_")
_test_db_path = str(Path(_tmpdir) / "test.db")

import src.backend.app.config as _cfg

_cfg.DATABASE_URL = f"sqlite:///{_test_db_path}"

from src.backend.app.db import get_db, init_db  # noqa: E402
from src.backend.app.main import app  # noqa: E402


# ── Fixtures ─────────────────────────────────────────

@pytest.fixture(autouse=True)
def _clean_db():
    """每个测试前清空所有表数据。"""
    init_db()
    with get_db() as conn:
        for table in ("price_snapshots", "gpu_instances", "users"):
            conn.execute(f"DELETE FROM {table}")


@pytest.fixture
def client():
    """每次测试返回独立 TestClient（进入 lifespan 上下文）。"""
    with TestClient(app) as c:
        yield c


# ── 健康检查 ────────────────────────────────────────


class TestHealth:
    """健康检查端点。"""

    def test_health_returns_ok(self, client):
        """GET /health → 200 + status=ok + version。"""
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["version"] == "0.1.0"

    def test_health_content_type(self, client):
        """返回 JSON。"""
        resp = client.get("/health")
        assert resp.headers["content-type"].startswith("application/json")


# ── 价格 ────────────────────────────────────────────


class TestPrices:
    """GET /api/v1/prices。"""

    def test_empty_returns_list(self, client):
        """无数据时返回空列表。"""
        resp = client.get("/api/v1/prices")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_filter_by_gpu_type(self, client):
        """?gpu_type=A100 只返回该型号。"""
        with get_db() as conn:
            conn.execute(
                "INSERT INTO price_snapshots (provider, gpu_type, price_per_hour, spot_price, region) "
                "VALUES ('阿里云', 'A100', 28.50, 12.80, 'cn-beijing')"
            )
            conn.execute(
                "INSERT INTO price_snapshots (provider, gpu_type, price_per_hour, spot_price, region) "
                "VALUES ('华为云', 'H100', 48.00, 24.00, 'cn-north-4')"
            )

        resp = client.get("/api/v1/prices?gpu_type=A100")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["provider"] == "阿里云"
        assert data[0]["gpu_type"] == "A100"

    def test_latest_price_only(self, client):
        """同一 provider+gpu_type 只返回最新数据。"""
        with get_db() as conn:
            conn.execute(
                "INSERT INTO price_snapshots (provider, gpu_type, price_per_hour, spot_price, region) "
                "VALUES ('阿里云', 'A100', 30.00, 15.00, 'cn-beijing')"
            )
            conn.execute(
                "INSERT INTO price_snapshots (provider, gpu_type, price_per_hour, spot_price, region) "
                "VALUES ('阿里云', 'A100', 26.00, 11.00, 'cn-beijing')"
            )

        resp = client.get("/api/v1/prices?gpu_type=A100")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["price_per_hour"] == 26.00


# ── 实例 CRUD ───────────────────────────────────────


class TestInstances:
    """POST / GET / DELETE /api/v1/instances。"""

    def test_create_returns_201(self, client):
        """POST → 201 + status=pending。"""
        resp = client.post(
            "/api/v1/instances",
            json={"provider": "阿里云", "gpu_type": "A100", "image": "ubuntu-22.04"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["provider"] == "阿里云"
        assert data["gpu_type"] == "A100"
        assert data["status"] == "pending"
        assert data["terminated_at"] is None

    def test_list_returns_instances(self, client):
        """GET → 返回所有活跃实例。"""
        client.post("/api/v1/instances", json={"provider": "阿里云", "gpu_type": "A100", "image": "img1"})
        client.post("/api/v1/instances", json={"provider": "华为云", "gpu_type": "H100", "image": "img2"})

        resp = client.get("/api/v1/instances")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_terminate_updates_status(self, client):
        """DELETE → status=terminated + terminated_at 非空。"""
        create = client.post(
            "/api/v1/instances",
            json={"provider": "腾讯云", "gpu_type": "4090", "image": "ubuntu"},
        )
        iid = create.json()["id"]

        resp = client.delete(f"/api/v1/instances/{iid}")
        assert resp.status_code == 200
        assert resp.json()["status"] == "terminated"
        assert resp.json()["terminated_at"] is not None

    def test_terminate_nonexistent_returns_404(self, client):
        """释放不存在实例 → 404。"""
        resp = client.delete("/api/v1/instances/99999")
        assert resp.status_code == 404

    def test_double_terminate_returns_400(self, client):
        """重复释放 → 400。"""
        create = client.post(
            "/api/v1/instances",
            json={"provider": "阿里云", "gpu_type": "A100", "image": "img"},
        )
        iid = create.json()["id"]
        client.delete(f"/api/v1/instances/{iid}")
        resp = client.delete(f"/api/v1/instances/{iid}")
        assert resp.status_code == 400

    def test_terminated_not_in_list(self, client):
        """释放后实例不出现在列表。"""
        create = client.post(
            "/api/v1/instances",
            json={"provider": "阿里云", "gpu_type": "A100", "image": "img"},
        )
        iid = create.json()["id"]
        client.delete(f"/api/v1/instances/{iid}")

        resp = client.get("/api/v1/instances")
        assert len(resp.json()) == 0
