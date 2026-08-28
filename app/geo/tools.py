"""
GEO 业务工具集

提供企业地理场景常用的原子能力，并注册为 Agent 工具：
1. geocode       —— 地址 -> 经纬度（基于 OpenStreetMap Nominatim，免费、需合规 User-Agent）
2. reverse_geocode—— 经纬度 -> 地址
3. haversine      —— 两点球面距离（km），纯本地计算，无网络依赖
4. bounding_box   —— 以某点为中心生成 N km 矩形范围（用于「周边 POI / 围栏」场景）

反爬/合规说明：Nominatim 公开服务要求每请求间隔 >=1s、带标识性 User-Agent，
本实现已内置限速与 UA，请勿用于高频批量打点。生产可替换为高德/腾讯地图企业 API。
"""
import math
import time

import httpx

from app.core.config import settings
from app.agent.tool import tool
from app.core.logging import get_logger

logger = get_logger("geo")
_NOMINATIM = "https://nominatim.openstreetmap.org"
_last_ts = 0.0


def _throttle():
    global _last_ts
    wait = 1.0 - (time.time() - _last_ts)
    if wait > 0:
        time.sleep(wait)
    _last_ts = time.time()


def _nominatim(path: str, params: dict) -> list[dict]:
    _throttle()
    r = httpx.get(
        f"{_NOMINATIM}{path}",
        params=params,
        headers={"User-Agent": settings.USER_AGENT},
        timeout=settings.REQUEST_TIMEOUT,
    )
    r.raise_for_status()
    return r.json()


@tool(
    name="geo_geocode",
    description="地理编码：把中文/英文地址解析为经纬度坐标。返回 {lat, lon, display_name}。",
    parameters={
        "type": "object",
        "properties": {
            "address": {"type": "string", "description": "地址，如 '北京市朝阳区'"},
            "limit": {"type": "integer", "description": "返回结果数量", "default": 1},
        },
        "required": ["address"],
    },
)
def geo_geocode(address: str, limit: int = 1) -> dict:
    data = _nominatim("/search", {"q": address, "format": "json", "limit": limit})
    if not data:
        return {"error": "未找到坐标"}
    top = data[0]
    return {"lat": float(top["lat"]), "lon": float(top["lon"]), "display_name": top["display_name"]}


@tool(
    name="geo_reverse",
    description="逆地理编码：经纬度 -> 可读地址。",
    parameters={
        "type": "object",
        "properties": {"lat": {"type": "number"}, "lon": {"type": "number"}},
        "required": ["lat", "lon"],
    },
)
def geo_reverse(lat: float, lon: float) -> dict:
    data = _nominatim("/reverse", {"lat": lat, "lon": lon, "format": "json"})
    return {"display_name": data.get("display_name", ""), "raw": data}


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """两点间球面距离（km）。纯数学计算，无需网络。"""
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return round(2 * r * math.asin(math.sqrt(a)), 3)


@tool(
    name="geo_distance",
    description="计算两个经纬度坐标之间的地面距离（km）。",
    parameters={
        "type": "object",
        "properties": {
            "lat1": {"type": "number"}, "lon1": {"type": "number"},
            "lat2": {"type": "number"}, "lon2": {"type": "number"},
        },
        "required": ["lat1", "lon1", "lat2", "lon2"],
    },
)
def geo_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> dict:
    return {"distance_km": haversine(lat1, lon1, lat2, lon2)}


@tool(
    name="geo_bounding_box",
    description="以中心点生成 N km 范围内的经纬度矩形（用于周边检索/地理围栏）。返回 {min_lat,max_lat,min_lon,max_lon}。",
    parameters={
        "type": "object",
        "properties": {
            "lat": {"type": "number"}, "lon": {"type": "number"},
            "radius_km": {"type": "number", "description": "半径", "default": 5},
        },
        "required": ["lat", "lon"],
    },
)
def geo_bounding_box(lat: float, lon: float, radius_km: float = 5) -> dict:
    d_lat = radius_km / 111.0
    d_lon = radius_km / (111.320 * math.cos(math.radians(lat)) or 1)
    return {
        "min_lat": round(lat - d_lat, 6), "max_lat": round(lat + d_lat, 6),
        "min_lon": round(lon - d_lon, 6), "max_lon": round(lon + d_lon, 6),
    }
