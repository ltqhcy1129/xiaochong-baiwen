"""登录次数与使用时长。

为什么不写进 accounts.json：老用户的账号档案用户特意交代过不要动。
把「登录了几次、用了多久」记在这份独立文件里，账号表一个字段都不用加，
以后要单独备份、单独回滚也方便。

数据结构（data/usage.json）：
{
  "version": 1,
  "since": 1794585600,            # 开始统计的时间，后台据此说明「自 x 起」
  "users": {
    "u123": {
      "logins": 3,                # 输密码 / 微信授权的次数
      "first_login": 1794585600,
      "last_login": 1794600000,
      "last_seen": 1794603600,    # 最后一次心跳，代表「最近在使用」
      "seconds": 1840,            # 累计使用秒数
      "days": {"2026-11-14": 620} # 按自然日（UTC+8），只留最近 90 天
    }
  }
}

旧账号第一次读这份文件时，会按 accounts.json 里已有的 last_login 补一条
「至少登录过 1 次」的记录；只是新建这一份文件，不改账号档案。
"""

import json
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
USAGE_FILE = DATA_DIR / "usage.json"

CST = timezone(timedelta(hours=8))
KEEP_DAYS = 90
MAX_SECONDS = 300          # 单次心跳能报的最大秒数，防止前端算错把时长灌爆
_lock = threading.Lock()
_cache = {"sig": None, "data": None}


def _now() -> int:
    return int(time.time())


def _day(ts: int = 0) -> str:
    return datetime.fromtimestamp(ts or _now(), CST).strftime("%Y-%m-%d")


def _empty() -> dict:
    return {"version": 1, "since": _now(), "users": {}}


def _seed() -> dict:
    """第一次运行时按账号表补一份底账：有 last_login 的老用户记 1 次登录。

    只读 accounts.json，不写回。使用时长没法凭历史数据还原，留空，
    后台显示「—」，等用户下次打开才开始计。
    """
    data = _empty()
    try:
        import auth
        accounts = auth.load_accounts()
    except Exception:
        accounts = {}
    for uid, acc in (accounts or {}).items():
        last = int(acc.get("last_login") or 0)
        if not last:
            continue
        data["users"][uid] = {
            "logins": 1,
            "first_login": int(acc.get("created") or last),
            "last_login": last,
            "last_seen": 0,
            "seconds": 0,
            "days": {},
            "seeded": True,
        }
    return data


def _load() -> dict:
    """读文件，带 mtime 缓存。文件不存在时按账号表生成并落盘。"""
    global _cache
    try:
        st = USAGE_FILE.stat()
        sig = (st.st_mtime_ns, st.st_size)
        if _cache["data"] is not None and _cache["sig"] == sig:
            return _cache["data"]
        data = json.loads(USAGE_FILE.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or not isinstance(data.get("users"), dict):
            raise ValueError("bad usage file")
    except FileNotFoundError:
        data = _seed()
        _write(data)
        st = USAGE_FILE.stat()
        sig = (st.st_mtime_ns, st.st_size)
    except Exception:
        # 文件写坏了：不抛错，重建一份底账，旧文件留个 .bad 备份方便排查
        try:
            USAGE_FILE.replace(USAGE_FILE.with_suffix(".json.bad"))
        except Exception:
            pass
        data = _seed()
        _write(data)
        st = USAGE_FILE.stat()
        sig = (st.st_mtime_ns, st.st_size)

    _cache = {"sig": sig, "data": data}
    return data


def _write(data: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp = USAGE_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(USAGE_FILE)


def _save(data: dict) -> None:
    _write(data)
    try:
        st = USAGE_FILE.stat()
        _cache["sig"] = (st.st_mtime_ns, st.st_size)
    except FileNotFoundError:
        _cache["sig"] = None
    _cache["data"] = data


def _trim_days(rec: dict) -> None:
    days = rec.get("days") or {}
    if len(days) <= KEEP_DAYS:
        return
    keep = sorted(days)[-KEEP_DAYS:]
    rec["days"] = {k: days[k] for k in keep}


def mark_login(uid: str, ts: int = 0) -> None:
    """登录成功时调一次。注册也算一次登录，不然新号的后台全是 0。"""
    uid = (uid or "").strip()
    if not uid:
        return
    now = ts or _now()
    with _lock:
        data = _load()
        rec = data["users"].setdefault(uid, {
            "logins": 0, "first_login": now, "last_login": 0,
            "last_seen": 0, "seconds": 0, "days": {},
        })
        rec["logins"] = int(rec.get("logins") or 0) + 1
        rec["last_login"] = now
        rec.setdefault("first_login", now)
        rec["seeded"] = False
        _save(data)


def add_time(uid: str, seconds: int, ts: int = 0) -> int:
    """累加一次心跳的使用时长，返回实际记下的秒数。"""
    uid = (uid or "").strip()
    try:
        sec = int(seconds)
    except Exception:
        sec = 0
    sec = max(0, min(MAX_SECONDS, sec))
    if not uid or sec <= 0:
        return 0
    now = ts or _now()
    with _lock:
        data = _load()
        rec = data["users"].setdefault(uid, {
            "logins": 0, "first_login": now, "last_login": 0,
            "last_seen": 0, "seconds": 0, "days": {},
        })
        rec["seconds"] = int(rec.get("seconds") or 0) + sec
        rec["last_seen"] = now
        days = rec.setdefault("days", {})
        d = _day(now)
        days[d] = int(days.get(d) or 0) + sec
        _trim_days(rec)
        _save(data)
    return sec


def forget(uid: str) -> None:
    """删号时一并清掉统计，别让已删用户留在后台的分母里。"""
    uid = (uid or "").strip()
    if not uid:
        return
    with _lock:
        data = _load()
        if (data.get("users") or {}).pop(uid, None) is not None:
            _save(data)


def get(uid: str) -> dict:
    data = _load()
    rec = (data.get("users") or {}).get(uid) or {}
    return _view(rec)


def _view(rec: dict) -> dict:
    days = rec.get("days") or {}
    return {
        "logins": int(rec.get("logins") or 0),
        "first_login": int(rec.get("first_login") or 0),
        "last_login": int(rec.get("last_login") or 0),
        "last_seen": int(rec.get("last_seen") or 0),
        "seconds": int(rec.get("seconds") or 0),
        "today_seconds": int(days.get(_day()) or 0),
        "days": len(days),
        "seeded": bool(rec.get("seeded")),
        "tracked": bool(rec.get("last_seen")),
    }


def all_users() -> dict:
    data = _load()
    return {uid: _view(rec) for uid, rec in (data.get("users") or {}).items()}


def since() -> int:
    return int(_load().get("since") or 0)


def summary(accounts: dict = None, window_days: int = 7) -> dict:
    """新老用户分开统计。

    新用户 = 注册不满 window_days 天；老用户 = 其余。
    登录次数、使用时长都按这个口径分两档给出，后台直接显示。
    """
    if accounts is None:
        try:
            import auth
            accounts = auth.load_accounts()
        except Exception:
            accounts = {}
    now = _now()
    cut = now - window_days * 86400
    usage = all_users()

    out = {
        "since": since(),
        "new": {"users": 0, "logins": 0, "seconds": 0, "today_seconds": 0},
        "old": {"users": 0, "logins": 0, "seconds": 0, "today_seconds": 0},
        "logins": 0, "seconds": 0, "today_seconds": 0,
        "active_today": 0, "tracked_users": 0,
    }
    for uid, acc in (accounts or {}).items():
        bucket = out["new"] if int(acc.get("created") or 0) >= cut else out["old"]
        bucket["users"] += 1
        u = usage.get(uid) or {}
        logins = int(u.get("logins") or 0)
        secs = int(u.get("seconds") or 0)
        today = int(u.get("today_seconds") or 0)
        bucket["logins"] += logins
        bucket["seconds"] += secs
        bucket["today_seconds"] += today
        out["logins"] += logins
        out["seconds"] += secs
        out["today_seconds"] += today
        if u.get("tracked"):
            out["tracked_users"] += 1
        if int(u.get("last_seen") or 0) >= _day_start():
            out["active_today"] += 1
    out["window_days"] = window_days
    return out


def _day_start(ts: int = 0) -> int:
    dt = datetime.fromtimestamp(ts or _now(), CST)
    return int(dt.replace(hour=0, minute=0, second=0, microsecond=0).timestamp())
