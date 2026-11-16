"""访问活跃统计：日活(DAU) / 月活(MAU) / 留存 / 趋势。

设计要点：
- 以设备(device_id)为"用户"，页面打开即上报一次访问，发问也会计一次活跃；
- 设备维度记录首次访问日、最近访问时间、每天事件次数，因此可算 DAU/MAU/留存；
- 时间统一按 UTC+8，避免容器时区导致"今日"偏移。
"""
import json
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "data"
ACTIVITY_FILE = DATA_DIR / "activity.json"
TZ = timezone(timedelta(hours=8))

_lock = threading.Lock()

# ============ 渠道来源 ============
# key 由前端从 URL 参数（?from=xxx / ?utm_source=xxx）或 referrer/UA 推断
CHANNELS = [
    ("mp_article", "公众号文章"),
    ("wechat", "微信内打开"),
    ("group", "微信群"),
    ("moments", "朋友圈"),
    ("share", "好友分享"),
    ("qrcode", "扫码进入"),
    ("search", "搜索引擎"),
    ("external", "外部链接"),
    ("direct", "直接访问"),
    ("other", "其他来源"),
]
CHANNEL_MAP = dict(CHANNELS)

# 常见别名归一到标准 key
SRC_ALIAS = {
    "wechat_group": "group", "wxgroup": "group", "group_chat": "group",
    "wx": "wechat", "weixin": "wechat", "wechat_mp": "mp_article",
    "mp": "mp_article", "article": "mp_article", "gzh": "mp_article",
    "qr": "qrcode", "qrcode_scan": "qrcode", "scan": "qrcode",
    "timeline": "moments", "friend": "share", "forward": "share",
    "baidu": "search", "sogou": "search", "bing": "search", "google": "search",
    "none": "direct", "": "direct",
}


def normalize_src(src: str) -> str:
    """规范渠道标识：只允许小写字母数字下划线短横，未知但合法的自定义渠道保留。"""
    s = (src or "").strip().lower()
    s = "".join(ch if (ch.isalnum() or ch in "_-") else "" for ch in s)[:20]
    if not s:
        return "direct"
    s = SRC_ALIAS.get(s, s)
    return s[:20]


def channel_name(key: str) -> str:
    if key in CHANNEL_MAP:
        return CHANNEL_MAP[key]
    return key[:12]


def _now() -> datetime:
    return datetime.now(TZ)


def _dstr(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d")


def load_activity() -> dict:
    if ACTIVITY_FILE.exists():
        try:
            return json.loads(ACTIVITY_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"devices": {}}


def save_activity(act: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    act["updated"] = int(time.time())
    ACTIVITY_FILE.write_text(json.dumps(act, ensure_ascii=False), encoding="utf-8")


def record_activity(device_id: str, kind: str = "visit", ts: int = 0, src: str = "",
                    uid: str = "") -> None:
    """记录一次活跃。kind: visit(打开页面) / question(提问)。异常静默。

    src: 本次访问的来源渠道；设备首次出现时写入 first_src，作为该用户的来源归因。
    uid: 登录账号 id。有账号时以账号为统计主体，同一用户换设备不会重复计人。
    """
    dev = (uid or device_id or "").strip()[:64]
    if not dev:
        return
    dt = datetime.fromtimestamp(ts, TZ) if ts else _now()
    day = _dstr(dt)
    try:
        with _lock:
            act = load_activity()
            devices = act.setdefault("devices", {})
            item = devices.get(dev)
            is_new = item is None
            if is_new:
                item = {"first": day, "last": dt.timestamp(), "days": {}, "q": 0, "v": 0,
                        "src": normalize_src(src), "uid": uid or ""}
                devices[dev] = item
            elif src and not item.get("src"):
                item["src"] = normalize_src(src)
            if uid and not item.get("uid"):
                item["uid"] = uid
            item["last"] = max(item.get("last", 0), dt.timestamp())
            if day < item.get("first", day):
                item["first"] = day
            days = item.setdefault("days", {})
            days[day] = int(days.get(day, 0)) + 1
            if kind == "question":
                item["q"] = int(item.get("q", 0)) + 1
            else:
                item["v"] = int(item.get("v", 0)) + 1
            if len(days) > 420:  # 控制文件体积
                keep = sorted(days)[-400:]
                item["days"] = {k: days[k] for k in keep}

            # 按天按渠道累计访问次数与新增用户数
            key = normalize_src(src) if src else (item.get("src") or "direct")
            daily = act.setdefault("daily_src", {})
            cell = daily.setdefault(day, {}).setdefault(key, {"pv": 0, "new": 0})
            cell["pv"] = int(cell.get("pv", 0)) + 1
            if is_new:
                cell["new"] = int(cell.get("new", 0)) + 1
            if len(daily) > 200:
                for k in sorted(daily)[:-180]:
                    daily.pop(k, None)

            save_activity(act)
    except Exception:
        pass


def clear_activity() -> None:
    """清空活跃记录（后台"清空统计数据"时一并调用）。"""
    try:
        with _lock:
            save_activity({"devices": {}})
    except Exception:
        pass


def rebuild_from_records(records: list) -> None:
    """把历史问答记录回填成活跃数据，避免上线后历史趋势一片空白。"""
    try:
        act = load_activity()
        devices = act.setdefault("devices", {})
        changed = False
        for r in records or []:
            dev = (r.get("uid") or r.get("device_id") or "").strip()
            ts = r.get("ts")
            if not dev or not ts:
                continue
            dt = datetime.fromtimestamp(ts, TZ)
            day = _dstr(dt)
            item = devices.get(dev)
            if not item:
                item = {"first": day, "last": ts, "days": {}, "q": 0, "v": 0, "src": "direct"}
                devices[dev] = item
                changed = True
            if day not in item.setdefault("days", {}):
                item["days"][day] = 1
                item["q"] = int(item.get("q", 0)) + 1
                item["last"] = max(item.get("last", 0), ts)
                changed = True
        if changed:
            save_activity(act)
    except Exception:
        pass


# ============ 统计计算 ============

def _active_on(devices: dict, day: str) -> int:
    n = 0
    for it in devices.values():
        if day in (it.get("days") or {}):
            n += 1
    return n


def _active_in_range(devices: dict, start: str, end: str) -> int:
    n = 0
    for it in devices.values():
        days = it.get("days") or {}
        if any(start <= d <= end for d in days):
            n += 1
    return n


def _new_on(devices: dict, day: str) -> int:
    return sum(1 for it in devices.values() if it.get("first") == day)


def _mask(dev: str) -> str:
    n = len(dev)
    if n <= 6:
        return dev
    if n <= 12:
        return dev[:3] + "***" + dev[-3:]
    return dev[:5] + "***" + dev[-4:]


def compute(records: list, user_names=None, accounts=None) -> dict:
    act = load_activity()
    devices = act.get("devices", {}) or {}
    # 账号被删除或合并后，活跃记录里会留下没有对应账号的键。
    # 这类「幽灵用户」会让渠道用户数、日活、月活都比真实注册数还多，统计前先剔除。
    reg_ts = {}
    if accounts is not None:
        valid = set(accounts.keys())
        devices = {k: v for k, v in devices.items()
                   if not ((v.get("uid") or "") == k and k not in valid)}
        reg_ts = {k: int((v or {}).get("created") or 0) for k, v in accounts.items()}
        # 注册后没打开过页面的账号不会留下活跃记录，补一条零活跃记录，
        # 否则「渠道用户数」会比「注册用户」少，看着像丢了人
        for uid, acc in accounts.items():
            if uid in devices:
                continue
            c = int((acc or {}).get("created") or 0)
            devices[uid] = {
                "first": _dstr(datetime.fromtimestamp(c, TZ)) if c else "",
                "last": 0, "days": {}, "q": 0, "v": 0,
                "src": normalize_src((acc or {}).get("source") or ""),
                "uid": uid,
            }
    now = _now()
    today = _dstr(now)
    yesterday = _dstr(now - timedelta(days=1))

    dau = _active_on(devices, today)
    dau_y = _active_on(devices, yesterday)
    d7_start = _dstr(now - timedelta(days=6))
    d30_start = _dstr(now - timedelta(days=29))
    wau = _active_in_range(devices, d7_start, today)
    mau = _active_in_range(devices, d30_start, today)

    # 上一个 30 天窗口（30~59 天前）作为环比基数
    prev_end = _dstr(now - timedelta(days=30))
    prev_start = _dstr(now - timedelta(days=59))
    mau_prev = _active_in_range(devices, prev_start, prev_end)

    def _first_day(dev: str, it: dict) -> str:
        """用户「新增」的口径：有账号按注册日，纯访客按首次访问日。"""
        if dev in reg_ts and reg_ts[dev]:
            return _dstr(datetime.fromtimestamp(reg_ts[dev], TZ))
        return it.get("first") or ""

    total_devices = len(devices)
    new_today = sum(1 for k, it in devices.items() if _first_day(k, it) == today)
    new_7d = sum(1 for k, it in devices.items() if _first_day(k, it) >= d7_start)
    new_30d = sum(1 for k, it in devices.items() if _first_day(k, it) >= d30_start)

    # 次日 / 7 日留存
    d1_base = d1_keep = 0
    d7_base = d7_keep = 0
    for it in devices.values():
        first = it.get("first") or ""
        fdt = None
        try:
            fdt = datetime.strptime(first, "%Y-%m-%d").replace(tzinfo=TZ)
        except Exception:
            continue
        age = (now.date() - fdt.date()).days
        days = it.get("days") or {}
        if 2 <= age <= 30:
            d1_base += 1
            nxt = _dstr(fdt + timedelta(days=1))
            if nxt in days:
                d1_keep += 1
        if 8 <= age <= 30:
            d7_base += 1
            if any(_dstr(fdt + timedelta(days=i)) in days for i in range(1, 8)):
                d7_keep += 1

    # 提问数
    questions_total = len(records)
    questions_today = sum(1 for r in records if r.get("date") == today)
    q_per_user = round(questions_total / mau, 2) if mau else 0

    # 近 30 天日活趋势
    q_by_day = {}
    for r in records:
        d = r.get("date")
        if d:
            q_by_day[d] = q_by_day.get(d, 0) + 1
    dau_trend = []
    for i in range(29, -1, -1):
        dt = now - timedelta(days=i)
        d = _dstr(dt)
        dau_trend.append({
            "date": d,
            "label": dt.strftime("%m-%d"),
            "dau": _active_on(devices, d),
            "new": sum(1 for k, it in devices.items() if _first_day(k, it) == d),
            "questions": q_by_day.get(d, 0),
        })

    # 近 6 个自然月月活
    mau_trend = []
    cur = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    months = []
    for i in range(5, -1, -1):
        y = cur.year
        m = cur.month - i
        while m <= 0:
            m += 12
            y -= 1
        months.append((y, m))
    for y, m in months:
        start = f"{y:04d}-{m:02d}-01"
        if m == 12:
            end = f"{y + 1:04d}-01-01"
        else:
            end = f"{y:04d}-{m + 1:02d}-01"
        nxt = datetime.strptime(end, "%Y-%m-%d").replace(tzinfo=TZ)
        end_day = _dstr(nxt - timedelta(days=1))
        last_day = _dstr(nxt - timedelta(days=1))
        mau_trend.append({
            "month": f"{y:04d}-{m:02d}",
            "label": f"{m}月",
            "mau": _active_in_range(devices, start, min(end_day, last_day)),
        })

    # 活跃分层
    tier = [
        {"name": "今日活跃", "count": _active_in_range(devices, today, today)},
        {"name": "近 7 天", "count": wau},
        {"name": "近 30 天", "count": mau},
        {"name": "30 天未活跃", "count": max(0, total_devices - mau)},
    ]

    # 提问时段分布（UTC+8）
    hour_dist = [{"hour": h, "count": 0} for h in range(24)]
    for r in records:
        ts = r.get("ts")
        if not ts:
            continue
        h = datetime.fromtimestamp(ts, TZ).hour
        hour_dist[h]["count"] += 1

    # 活跃用户 TOP（只排真正打开过页面的，补入的零活跃账号不进榜）
    active_items = [(k, v) for k, v in devices.items() if v.get("days")]
    top = sorted(active_items, key=lambda kv: (len(kv[1].get("days") or {}), kv[1].get("q", 0)), reverse=True)[:10]
    top_devices = []
    for dev, it in top:
        label = _mask(dev)
        if user_names:
            try:
                label = user_names(dev) or label
            except Exception:
                pass
        top_devices.append({
            "device": label,
            "days": len(it.get("days") or {}),
            "questions": it.get("q", 0),
            "first": it.get("first"),
            "last": _dstr(datetime.fromtimestamp(it.get("last", 0), TZ)) if it.get("last") else "-",
        })

    def pct(a, b):
        return round((a - b) / b * 100, 1) if b else (100.0 if a else 0.0)

    # 渠道来源（按用户首访归因，UV 口径）
    daily_src = act.get("daily_src", {}) or {}
    agg = {}

    def _bucket(key):
        return agg.setdefault(key, {"uv": 0, "new_7d": 0, "new_30d": 0, "q": 0, "pv": 0,
                                    "q_users": 0, "q2_users": 0})

    for dev, it in devices.items():
        a = _bucket(it.get("src") or "direct")
        a["uv"] += 1
        qn = int(it.get("q", 0) or 0)
        a["q"] += qn
        if qn >= 1:
            a["q_users"] += 1
        if qn >= 2:
            a["q2_users"] += 1
        first = _first_day(dev, it)
        if first >= d7_start:
            a["new_7d"] += 1
        if first >= d30_start:
            a["new_30d"] += 1
    for day, cells in daily_src.items():
        for key, c in (cells or {}).items():
            _bucket(key)["pv"] += int(c.get("pv", 0) or 0)
    if not daily_src:  # 老数据没有渠道明细时用设备访问次数兜底
        for dev, it in devices.items():
            _bucket(it.get("src") or "direct")["pv"] += int(it.get("v", 0) or 0)

    ch_list = []
    for key, a in agg.items():
        ch_list.append({
            "key": key,
            "name": channel_name(key),
            "uv": a["uv"],
            "new_7d": a["new_7d"],
            "new_30d": a["new_30d"],
            "q": a["q"],
            "pv": a["pv"],
            "q_users": a["q_users"],
            "q2_users": a["q2_users"],
            "q_rate": round(a["q"] / a["uv"], 2) if a["uv"] else 0,
            "ask_rate": round(a["q_users"] / a["uv"] * 100, 1) if a["uv"] else 0,
            "multi_rate": round(a["q2_users"] / a["uv"] * 100, 1) if a["uv"] else 0,
        })
    ch_list.sort(key=lambda x: (-x["uv"], -x["new_30d"]))
    channels = ch_list[:8]
    if len(ch_list) > 8:
        rest = ch_list[8:]
        rest_uv = sum(x["uv"] for x in rest)
        rest_q1 = sum(x["q_users"] for x in rest)
        rest_q2 = sum(x["q2_users"] for x in rest)
        channels.append({
            "key": "other", "name": "其他来源",
            "uv": rest_uv,
            "new_7d": sum(x["new_7d"] for x in rest),
            "new_30d": sum(x["new_30d"] for x in rest),
            "q": sum(x["q"] for x in rest),
            "pv": sum(x["pv"] for x in rest),
            "q_users": rest_q1,
            "q2_users": rest_q2,
            "q_rate": round(sum(x["q"] for x in rest) / rest_uv, 2) if rest_uv else 0,
            "ask_rate": round(rest_q1 / rest_uv * 100, 1) if rest_uv else 0,
            "multi_rate": round(rest_q2 / rest_uv * 100, 1) if rest_uv else 0,
        })

    # 转化漏斗：进入 → 提问 → 多次提问 → 高频提问 → 回访
    def _q(it):
        return int(it.get("q", 0) or 0)

    f_visit = total_devices
    f_q1 = sum(1 for it in devices.values() if _q(it) >= 1)
    f_q2 = sum(1 for it in devices.values() if _q(it) >= 2)
    f_q5 = sum(1 for it in devices.values() if _q(it) >= 5)
    f_back = sum(1 for it in devices.values() if len(it.get("days") or {}) >= 2)

    def _rate(cur, prev):
        return round(cur / prev * 100, 1) if prev else 0.0

    # 严格递减的漏斗（每一层是上一层的子集）
    funnel = [
        {"key": "visit", "name": "访问进入", "count": f_visit, "step": 100.0,
         "total": 100.0, "desc": "打开过小宠百问"},
        {"key": "ask1", "name": "提过问题", "count": f_q1, "step": _rate(f_q1, f_visit),
         "total": _rate(f_q1, f_visit), "desc": "至少问过 1 个问题"},
        {"key": "ask2", "name": "问 2 次以上", "count": f_q2, "step": _rate(f_q2, f_q1),
         "total": _rate(f_q2, f_visit), "desc": "说明第一次回答有价值"},
        {"key": "ask5", "name": "问 5 次以上", "count": f_q5, "step": _rate(f_q5, f_q2),
         "total": _rate(f_q5, f_visit), "desc": "高频使用者"},
    ]
    # 回访与上面的层级不是包含关系，单独作为补充指标展示
    funnel_note = {
        "name": "隔天回访",
        "count": f_back,
        "rate": _rate(f_back, f_visit),
        "back_rate": _rate(f_back, f_q1),
    }

    return {
        "overview": {
            "dau": dau,
            "dau_yesterday": dau_y,
            "dau_change": pct(dau, dau_y),
            "wau": wau,
            "mau": mau,
            "mau_prev": mau_prev,
            "mau_change": pct(mau, mau_prev),
            "stickiness": round(dau / mau * 100, 1) if mau else 0,
            "total_devices": total_devices,
            "new_today": new_today,
            "new_7d": new_7d,
            "new_30d": new_30d,
            "questions_today": questions_today,
            "questions_total": questions_total,
            "q_per_user": q_per_user,
            "retention_d1": round(d1_keep / d1_base * 100, 1) if d1_base else 0,
            "retention_d7": round(d7_keep / d7_base * 100, 1) if d7_base else 0,
            "d1_base": d1_base,
            "d7_base": d7_base,
        },
        "dau_trend": dau_trend,
        "mau_trend": mau_trend,
        "tier": tier,
        "hour_dist": hour_dist,
        "funnel": funnel,
        "funnel_note": funnel_note,
        "channels": channels,
        "top_devices": top_devices,
    }
