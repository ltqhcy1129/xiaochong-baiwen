# -*- coding: utf-8 -*-
"""IP 归属地：把 154.8.209.152 变成「北京」，把 112.96.103.7 变成「广东·广州」。

用 ip2region 离线库，不联网、不调第三方接口、没有配额限制。
数据文件 xz 压到 2.6 MB，首次查询时解到内存（约 11 MB），之后只走内存二分。
库或数据缺失时静默降级为空串，后台照旧显示原始 IP，不影响任何功能。
"""
import ipaddress
import lzma
import threading

from pathlib import Path

XDB = Path(__file__).resolve().parent / "data" / "ip2region" / "v4.xdb.xz"

_lock = threading.Lock()
_state = {"searcher": None, "tried": False}
_ready = threading.Event()
_cache = {}
_CACHE_MAX = 8192

# 库里境外国家是英文，中文界面只翻常见的几个；剩下的原样显示
_COUNTRY_CN = {
    "China": "中国", "United States": "美国", "Japan": "日本", "South Korea": "韩国",
    "Singapore": "新加坡", "Malaysia": "马来西亚", "Thailand": "泰国", "Vietnam": "越南",
    "Philippines": "菲律宾", "Indonesia": "印度尼西亚", "India": "印度",
    "United Kingdom": "英国", "Germany": "德国", "France": "法国", "Russia": "俄罗斯",
    "Canada": "加拿大", "Australia": "澳大利亚", "New Zealand": "新西兰",
    "Netherlands": "荷兰", "Spain": "西班牙", "Italy": "意大利", "Brazil": "巴西",
    "Hong Kong": "中国香港", "Macao": "中国澳门", "Taiwan": "中国台湾",
}

# 「广东省」→「广东」，直辖市原样（北京市 就留 北京）
_PROV_DROP = ("维吾尔自治区", "壮族自治区", "回族自治区", "自治区", "特别行政区", "省", "市")


def _short(name: str) -> str:
    name = (name or "").strip()
    if name in ("", "0"):
        return ""
    for suf in _PROV_DROP:
        if name.endswith(suf) and len(name) > len(suf):
            return name[: -len(suf)]
    return name


def _load() -> None:
    """解压并建索引。只在第一次调用时做，失败就不再重试。"""
    with _lock:
        if _state["tried"]:
            return
        _state["tried"] = True
        try:
            from ip2region import searcher, util
            raw = lzma.decompress(XDB.read_bytes()) if XDB.exists() else b""
            if raw:
                _state["searcher"] = searcher.new_with_buffer(util.IPv4, raw)
        except Exception:
            _state["searcher"] = None
        finally:
            _ready.set()


def warm() -> None:
    """启动时后台预热，避免第一个后台请求卡在解压上。"""
    threading.Thread(target=_load, daemon=True).start()


def _parse(raw: str) -> tuple:
    """『中国|广东省|深圳市|电信|CN』→ (『广东·深圳』, 『电信』)"""
    parts = (raw or "").split("|")
    if len(parts) < 4:
        return "", ""
    country, prov, city, isp = parts[0].strip(), parts[1].strip(), parts[2].strip(), parts[3].strip()
    if country in ("", "0", "Reserved"):
        return "", ""
    if isp in ("0", "Reserved"):
        isp = ""

    # 库里的国家字段中文版是「中国」，英文版是「China」，两种都要认
    if country not in ("China", "中国"):
        # 境外只到国家，细到州/市对国内用户没意义
        return _COUNTRY_CN.get(country, country), isp

    p, c = _short(prov), _short(city)
    if not c or c == p:
        return p, isp
    # 直辖市：北京市/北京市 已在上一步并掉；个别库写作 北京市/北京 也兜住
    if p and c.startswith(p):
        return p, isp
    return f"{p}·{c}" if p else c, isp


def detail(ip: str) -> dict:
    """返回 {'loc': '广东·深圳', 'isp': '电信'}，查不到给空串。"""
    ip = (ip or "").strip()
    if not ip:
        return {"loc": "", "isp": ""}
    if ip in _cache:
        return _cache[ip]

    loc, isp = "", ""
    try:
        addr = ipaddress.ip_address(ip)
        if addr.is_global:
            if not _state["tried"]:
                _load()
            s = _state["searcher"]
            if s is not None:
                loc, isp = _parse(str(s.search(ip)))
    except Exception:
        loc, isp = "", ""

    out = {"loc": loc, "isp": isp}
    if len(_cache) > _CACHE_MAX:
        _cache.clear()
    _cache[ip] = out
    return out


def lookup(ip: str) -> str:
    """只要归属地文本，用作列表展示。"""
    return detail(ip).get("loc", "")
