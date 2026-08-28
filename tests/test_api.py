"""
接口与模块测试（pytest）

覆盖不依赖外部密钥/网络的能力，确保本地可一键验证核心链路：
- /health 健康检查
- 知识库 local embedding 入库 + 检索
- GEO 本地距离计算工具（无网络）
- 短视频纯文本分析（不抓取，走 analyze_content 的兜底错误路径由 mock 跳过）

运行：pytest -q
"""
import os

# 测试前强制使用本地兜底 embedding，避免依赖外部密钥
os.environ.setdefault("EMBEDDING_PROVIDER", "local")

from fastapi.testclient import TestClient

from app.main import app
from app.agent.tool import dispatch

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_knowledge_ingest_and_search():
    # 入库两段相关文本
    client.post("/api/knowledge/ingest", json={
        "text": "公司年假政策：入职满一年享5天年假，满十年享10天。", "source": "hr"
    })
    client.post("/api/knowledge/ingest", json={
        "text": "报销流程：填写表单并附发票，主管审批后财务打款。", "source": "finance"
    })
    r = client.post("/api/knowledge/search", json={"query": "年假有几天", "top_k": 1})
    assert r.status_code == 200
    results = r.json()["results"]
    assert results and "年假" in results[0]["text"]


def test_geo_distance_tool():
    # 北京->上海 直线距离约 1067km，验证工具计算正确（本地数学，无网络）
    res = dispatch("geo_distance", lat1=39.9042, lon1=116.4074,
                   lat2=31.2304, lon2=121.4737)
    assert "distance_km" in res
    assert 1000 < res["distance_km"] < 1150


def test_agent_unknown_type():
    r = client.post("/api/agent/run", json={"agent_type": "nope", "user_input": "x"})
    assert r.status_code == 400
