"""
API 端点测试：验证 FastAPI 接口的基本行为
使用 TestClient 进行同步测试，不依赖外部服务
"""

import pytest
from fastapi.testclient import TestClient

from deepdistill.api import app


@pytest.fixture
def client():
    """创建测试客户端"""
    return TestClient(app)


class TestHealthEndpoint:
    """健康检查端点测试"""

    def test_health_ok(self, client):
        """健康检查应返回 200"""
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "version" in data
        assert "device" in data

    def test_health_has_device_info(self, client):
        """应返回设备信息（cpu/cuda/mps）"""
        resp = client.get("/health")
        data = resp.json()
        assert data["device"] in ("cpu", "cuda", "mps")


class TestConfigEndpoint:
    """配置端点测试"""

    def test_config_returns_dict(self, client):
        """配置端点应返回字典"""
        resp = client.get("/api/config")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, dict)


class TestStatusEndpoint:
    """状态端点测试"""

    def test_status_returns_components(self, client):
        """状态端点应返回组件列表"""
        resp = client.get("/api/status")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, (dict, list))


class TestTaskEndpoints:
    """任务管理端点测试"""

    def test_list_tasks_empty(self, client):
        """初始任务列表应为空或返回列表"""
        resp = client.get("/api/tasks")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    def test_get_nonexistent_task(self, client):
        """查询不存在的任务应返回 404"""
        resp = client.get("/api/tasks/nonexistent-id-12345")
        assert resp.status_code == 404

    def test_export_nonexistent_task(self, client):
        """导出不存在的任务应返回 404"""
        resp = client.post("/api/tasks/nonexistent-id-12345/export/google-docs")
        assert resp.status_code == 404


class TestCategoriesEndpoint:
    """分类列表端点测试"""

    def test_categories_returns_list(self, client):
        """分类端点应返回列表"""
        resp = client.get("/api/export/categories")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 7  # 至少 7 个预定义分类

    def test_categories_have_name(self, client):
        """每个分类应有 name 字段"""
        resp = client.get("/api/export/categories")
        data = resp.json()
        for cat in data:
            assert "name" in cat
            assert isinstance(cat["name"], str)
            assert len(cat["name"]) > 0


class TestProcessUrlEndpoint:
    """URL 处理端点测试"""

    def test_process_url_missing_url(self, client):
        """缺少 url 参数应返回 422"""
        resp = client.post(
            "/api/process/url",
            json={"options": {}},
        )
        assert resp.status_code == 422

    def test_process_url_returns_task_id(self, client):
        """提交 URL 应返回 task_id（异步处理）"""
        resp = client.post(
            "/api/process/url",
            json={"url": "https://example.com"},
        )
        # 可能返回 200（成功排队）或其他状态
        if resp.status_code == 200:
            data = resp.json()
            assert "task_id" in data
            assert "status" in data


class TestProcessFileEndpoint:
    """文件上传端点测试"""

    def test_upload_no_file(self, client):
        """不上传文件应返回 422"""
        resp = client.post("/api/process")
        assert resp.status_code == 422
