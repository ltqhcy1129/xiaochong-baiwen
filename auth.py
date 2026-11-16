# -*- coding: utf-8 -*-
"""账号体系：注册 / 登录 / 会话令牌 / 接口鉴权。

成本方案说明：
- 主通道「手机号 + 密码」：完全零成本，不依赖短信服务商，无需任何第三方资质；
- 可选通道「微信网页授权」：公众号内一键静默登录，微信官方免费，但需要已备案域名
  并在公众号后台配置「网页授权域名」，配置后自动出现在登录页；
- 未采用「短信验证码」：运营商按条计费（0.03~0.05 元/条），且需短信服务商资质。
"""
import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import threading
import time
from pathlib import Path
from typing import Optional

DATA_DIR = Path(__file__).resolve().parent / "data"
ACCOUNTS_FILE = DATA_DIR / "accounts.json"
CONFIG_FILE = DATA_DIR / "config.json"

COOKIE_NAME = "xc_token"
TOKEN_DAYS = 30          # 令牌本身最长 30 天；实际每天零点到期，见 token_day()
PBKDF2_ROUNDS = 120_000  # 密码哈希迭代次数
TZ_OFFSET = 8 * 3600     # 业务时区固定东八区，和服务器所在机房无关
PHONE_RE = re.compile(r"^1[3-9]\d{9}$")

_lock = threading.RLock()

# 登录失败限流：同一手机号 10 分钟内失败 6 次则临时锁定，防止撞库
_fails = {}
FAIL_WINDOW = 600
FAIL_LIMIT = 6


class AuthError(Exception):
    """带状态码的业务异常。"""

    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message = message
        self.status = status


# ============ 存取 ============

def _read_json(path: Path, default):
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return default


def _write_json(path: Path, data) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)  # 原子替换，避免并发写坏文件


def load_accounts() -> dict:
    data = _read_json(ACCOUNTS_FILE, {})
    return data if isinstance(data, dict) else {}


def save_accounts(accounts: dict) -> None:
    before = len(load_accounts())
    with _lock:
        _write_json(ACCOUNTS_FILE, accounts)
    # 账号是无法重建的数据：新增账号立即备份，其余变更按节流备份
    try:
        import backup
        backup.snapshot(force=len(accounts) > before)
    except Exception:
        pass


def get_secret() -> str:
    """会话签名密钥，与后台配置共用 config.json。"""
    cfg = _read_json(CONFIG_FILE, {})
    secret = (cfg or {}).get("session_secret") or os.environ.get("SESSION_SECRET", "")
    if not secret:
        secret = secrets.token_hex(32)
        cfg["session_secret"] = secret
        _write_json(CONFIG_FILE, cfg)
    return secret


# ============ 密码 ============

def hash_password(password: str, salt: str = "") -> tuple:
    salt = salt or secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"),
                             PBKDF2_ROUNDS)
    return salt, dk.hex()


def verify_password(password: str, salt: str, expected: str) -> bool:
    try:
        _, got = hash_password(password, salt)
        return hmac.compare_digest(got, expected)
    except Exception:
        return False


def check_password_strength(password: str) -> None:
    if not password or len(password) < 6:
        raise AuthError("密码至少 6 位")
    if len(password) > 32:
        raise AuthError("密码最多 32 位")


# ============ 令牌 ============
# 登录态按自然日失效：今天登录，过了夜里 12 点就要重新登录。
# 令牌里带一个「签发日」day 字段，验签时和服务器当天的日期比一次；
# 比的是东八区日期而不是本机时区，海外机房部署也不会错位一天。

def day_key(ts: Optional[float] = None) -> str:
    """东八区自然日，形如 2026-11-14。"""
    t = time.time() if ts is None else ts
    return time.strftime("%Y-%m-%d", time.gmtime(t + TZ_OFFSET))


def day_end(ts: Optional[float] = None) -> int:
    """今天夜里 24:00 的时间戳，前端拿它挂到期定时器。"""
    t = int(time.time() if ts is None else ts)
    return t - (t + TZ_OFFSET) % 86400 + 86400


def _b64e(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _b64d(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def make_token(uid: str, phone: str = "", days: int = TOKEN_DAYS) -> str:
    now = int(time.time())
    payload = {"uid": uid, "phone": phone, "iat": now,
               "exp": now + days * 86400, "day": day_key(now)}
    data = _b64e(json.dumps(payload, separators=(",", ":")).encode())
    sig = hmac.new(get_secret().encode(), data.encode(), hashlib.sha256).hexdigest()
    return f"{data}.{sig}"


def read_token(token: str) -> Optional[dict]:
    """只验签名与 30 天总有效期，不判日期。"""
    if not token or "." not in token:
        return None
    try:
        data, sig = token.rsplit(".", 1)
        expected = hmac.new(get_secret().encode(), data.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, sig):
            return None
        payload = json.loads(_b64d(data))
        if int(payload.get("exp", 0)) < time.time():
            return None
        if not payload.get("uid"):
            return None
        return payload
    except Exception:
        return None


def token_day(payload: dict) -> str:
    """令牌的签发日。

    旧令牌没有 day 字段，退回按 iat 推算——升级这一刻还在用的人不会被
    集体踢下线，但昨天签发的一样会在今天失效。
    """
    return payload.get("day") or day_key(payload.get("iat") or 0)


def parse_token(token: str) -> Optional[dict]:
    payload = read_token(token)
    if not payload:
        return None
    if token_day(payload) != day_key():
        return None
    return payload


def token_from_request(request) -> str:
    """兼容三种携带方式：Cookie / X-Token / Authorization: Bearer。"""
    token = ""
    try:
        token = request.cookies.get(COOKIE_NAME) or ""
    except Exception:
        token = ""
    if not token:
        token = (request.headers.get("x-token") or "").strip()
    if not token:
        auth = request.headers.get("authorization", "")
        if auth.lower().startswith("bearer "):
            cand = auth[7:].strip()
            # 只认自己签发的：云端网关 / 反向代理会往上游塞 Authorization，
            # 拿它当登录令牌会把没登录的游客判成「登录已失效」。
            # read_token 只验签名，昨天签发的仍能读出来，跨天提示不会丢。
            if read_token(cand):
                token = cand
    return token


def session_state(request) -> tuple:
    """取当前登录用户，并说明会话为什么没了。

    返回 (账号 or None, 原因)：
      ""         未带令牌（就是没登录）
      "newday"   昨天登录的，过了夜里 12 点要重登
      "invalid"  令牌无效、被停用或超 30 天
    """
    token = token_from_request(request)
    if not token:
        return None, ""
    payload = read_token(token)
    if not payload:
        return None, "invalid"
    accounts = load_accounts()
    acc = accounts.get(payload["uid"])
    if not acc or acc.get("status", "active") != "active":
        return None, "invalid"
    if token_day(payload) != day_key():
        return None, "newday"
    _touch_ip(acc, accounts, request)
    return acc, ""


def current_account(request) -> Optional[dict]:
    acc, _ = session_state(request)
    return acc


# ============ 客户端 IP ============
# 云端一般套着反向代理，request.client.host 拿到的是内网地址，
# 真实来源要看 X-Forwarded-For / X-Real-IP 这些头。
_PRIVATE_RE = re.compile(
    r"^(10\.|127\.|0\.|192\.168\.|172\.(1[6-9]|2\d|3[01])\.|169\.254\.|::1$|f[cd][0-9a-f]{2}:|fe80:)",
    re.I,
)
_ip_mark = {}          # uid -> (ip, ts)，用于给写盘节流
IP_REFRESH = 1800      # 同一 IP 半小时内不重复写盘


def client_ip(request) -> str:
    """取真实客户端 IP，取不到返回空串。"""
    if request is None:
        return ""
    cands = []
    try:
        for h in ("cf-connecting-ip", "x-real-ip", "x-forwarded-for"):
            v = request.headers.get(h) or ""
            if v:
                cands.extend([x.strip() for x in v.split(",") if x.strip()])
    except Exception:
        pass
    try:
        if request.client and request.client.host:
            cands.append(request.client.host)
    except Exception:
        pass
    for ip in cands:
        if ip and not _PRIVATE_RE.match(ip):
            return ip[:45]
    return (cands[0] if cands else "")[:45]


def _touch_ip(acc: dict, accounts: dict, request) -> None:
    """记录最近一次访问 IP。写盘按 (uid, ip) 节流，避免每个请求都落盘。"""
    ip = client_ip(request)
    if not ip:
        return
    uid = acc.get("uid") or ""
    if not uid:
        return
    now = int(time.time())
    if ip == acc.get("last_ip") and now - int(acc.get("last_ip_ts") or 0) < IP_REFRESH:
        return
    mark = _ip_mark.get(uid)
    if mark and mark[0] == ip and now - mark[1] < IP_REFRESH:
        return
    _ip_mark[uid] = (ip, now)
    acc["last_ip"] = ip
    acc["last_ip_ts"] = now
    accounts[uid] = acc
    try:
        save_accounts(accounts)
    except Exception:
        pass


def public_user(acc: dict) -> dict:
    phone = acc.get("phone", "")
    masked = phone[:3] + "****" + phone[-4:] if len(phone) == 11 else (phone or "微信用户")
    return {
        "uid": acc.get("uid", ""),
        "phone": phone,
        "phone_masked": masked,
        "nickname": acc.get("nickname") or ("宠友" + phone[-4:] if phone else "宠友"),
        "avatar": acc.get("avatar", ""),
        "avatar_color": acc.get("avatar_color", ""),
        "bio": acc.get("bio", ""),
        "gender": acc.get("gender", ""),
        "location": acc.get("location", ""),
        "created": acc.get("created", 0),
        "last_login": acc.get("last_login", 0),
        "questions": acc.get("questions", 0),
        "source": acc.get("source", "direct"),
        "bind_wechat": bool(acc.get("openid")),
    }


# ============ 限流 ============

def _fail_key(phone: str) -> str:
    return f"p:{phone}"


def _check_locked(phone: str) -> None:
    now = time.time()
    arr = [t for t in _fails.get(_fail_key(phone), []) if now - t < FAIL_WINDOW]
    _fails[_fail_key(phone)] = arr
    if len(arr) >= FAIL_LIMIT:
        wait = int((FAIL_WINDOW - (now - arr[0])) / 60) + 1
        raise AuthError(f"密码错误次数过多，请 {wait} 分钟后再试", 429)


def _mark_fail(phone: str) -> None:
    _fails.setdefault(_fail_key(phone), []).append(time.time())


def _clear_fail(phone: str) -> None:
    _fails.pop(_fail_key(phone), None)


# ============ 注册 / 登录 ============

def _find_by_phone(accounts: dict, phone: str) -> Optional[dict]:
    for acc in accounts.values():
        if acc.get("phone") == phone:
            return acc
    return None


def _new_uid() -> str:
    return "u" + secrets.token_hex(8)


def register(phone: str, password: str, nickname: str = "", src: str = "",
             device_id: str = "", ip: str = "") -> dict:
    phone = (phone or "").strip().replace(" ", "").replace("-", "")
    if not PHONE_RE.match(phone):
        raise AuthError("请输入正确的手机号")
    check_password_strength(password)

    with _lock:
        accounts = load_accounts()
        if _find_by_phone(accounts, phone):
            raise AuthError("该手机号已注册，请直接登录；忘记密码可联系客服重置", 409)
        salt, pwd = hash_password(password)
        uid = _new_uid()
        now = int(time.time())
        acc = {
            "uid": uid,
            "phone": phone,
            "salt": salt,
            "pwd": pwd,
            "nickname": (nickname or "").strip()[:20] or ("宠友" + phone[-4:]),
            "avatar": "",
            "created": now,
            "last_login": now,
            "reg_ip": (ip or "")[:45],
            "last_ip": (ip or "")[:45],
            "last_ip_ts": now,
            "status": "active",
            "source": (src or "direct")[:20],
            "devices": [device_id] if device_id else [],
            "questions": 0,
            "openid": "",
        }
        accounts[uid] = acc
        save_accounts(accounts)
    return acc


def login(phone: str, password: str, device_id: str = "", ip: str = "") -> dict:
    phone = (phone or "").strip().replace(" ", "").replace("-", "")
    if not PHONE_RE.match(phone):
        raise AuthError("请输入正确的手机号")
    _check_locked(phone)

    with _lock:
        accounts = load_accounts()
        acc = _find_by_phone(accounts, phone)
        if not acc:
            _mark_fail(phone)
            raise AuthError("手机号或密码错误", 401)
        if acc.get("status") == "disabled":
            raise AuthError("该账号已被停用，请联系客服", 403)
        if not verify_password(password, acc.get("salt", ""), acc.get("pwd", "")):
            _mark_fail(phone)
            raise AuthError("手机号或密码错误", 401)
        _clear_fail(phone)
        acc["last_login"] = int(time.time())
        if ip:
            acc["last_ip"] = ip[:45]
            acc["last_ip_ts"] = acc["last_login"]
        if device_id:
            devs = acc.setdefault("devices", [])
            if device_id not in devs:
                devs.append(device_id)
                acc["devices"] = devs[-10:]
        accounts[acc["uid"]] = acc
        save_accounts(accounts)
    return acc


def change_password(acc: dict, old: str, new: str) -> None:
    if not verify_password(old, acc.get("salt", ""), acc.get("pwd", "")):
        raise AuthError("原密码不正确", 401)
    check_password_strength(new)
    with _lock:
        accounts = load_accounts()
        cur = accounts.get(acc.get("uid", ""))
        if not cur:
            raise AuthError("账号不存在", 404)
        salt, pwd = hash_password(new)
        cur["salt"] = salt
        cur["pwd"] = pwd
        save_accounts(accounts)


# 忘记密码：没有短信通道，只能「手机号 + 新密码」直接重设，
# 所以限流做严一点，避免有人拿一个号码反复试探性重置。
_reset_by_phone: dict = {}
_reset_by_ip: dict = {}


def _reset_throttle(bucket: dict, key: str, limit: int, window: int) -> None:
    now = time.time()
    hits = [t for t in bucket.get(key, []) if now - t < window]
    if len(hits) >= limit:
        raise AuthError("操作过于频繁，请 15 分钟后再试", 429)
    hits.append(now)
    if len(bucket) > 5000:
        bucket.clear()
    bucket[key] = hits


def reset_password(phone: str, new_password: str, ip: str = "") -> dict:
    phone = (phone or "").strip().replace(" ", "").replace("-", "")
    if not PHONE_RE.match(phone):
        raise AuthError("请输入正确的手机号")
    check_password_strength(new_password)
    _reset_throttle(_reset_by_phone, phone, 5, 900)
    if ip:
        _reset_throttle(_reset_by_ip, ip, 12, 900)
    with _lock:
        accounts = load_accounts()
        acc = _find_by_phone(accounts, phone)
        if not acc:
            raise AuthError("该手机号还没有注册，请先注册", 404)
        if acc.get("status") == "disabled":
            raise AuthError("该账号已被停用，请联系客服", 403)
        salt, pwd = hash_password(new_password)
        acc["salt"] = salt
        acc["pwd"] = pwd
        acc["pwd_ts"] = int(time.time())
        acc["pwd_resets"] = int(acc.get("pwd_resets", 0) or 0) + 1
        _clear_fail(phone)
        save_accounts(accounts)
    return acc


def upsert_wechat(openid: str, nickname: str, avatar: str, ip: str = "") -> dict:
    """微信授权登录：openid 首次出现时自动建号，之后直接登录。"""
    uid = "wx" + hashlib.md5(openid.encode()).hexdigest()[:14]
    with _lock:
        accounts = load_accounts()
        acc = accounts.get(uid)
        now = int(time.time())
        if not acc:
            acc = {
                "uid": uid, "phone": "", "salt": "", "pwd": "",
                "nickname": nickname or "微信用户", "avatar": avatar or "",
                "created": now, "last_login": now, "status": "active",
                "source": "wechat", "devices": [], "questions": 0, "openid": openid,
                "reg_ip": (ip or "")[:45], "last_ip": (ip or "")[:45], "last_ip_ts": now,
            }
        else:
            acc["last_login"] = now
            if ip:
                acc["last_ip"] = ip[:45]
                acc["last_ip_ts"] = now
            if nickname:
                acc["nickname"] = nickname
            if avatar:
                acc["avatar"] = avatar
        accounts[uid] = acc
        save_accounts(accounts)
    return acc


def all_users() -> list:
    """后台用户列表（按注册时间倒序）。"""
    accounts = load_accounts()
    items = [
        public_user(a) | {
            "disabled": a.get("status") == "disabled",
            # 登录 IP 与注册 IP 分开给：换了网络能看出来，同 IP 多号也一眼可见
            "last_ip": a.get("last_ip", ""),
            "last_ip_ts": a.get("last_ip_ts", 0),
            "reg_ip": a.get("reg_ip", ""),
        }
        for a in accounts.values()
    ]
    items.sort(key=lambda x: x.get("created", 0), reverse=True)
    return items


def admin_set_status(uid: str, disabled: bool) -> bool:
    with _lock:
        accounts = load_accounts()
        acc = accounts.get(uid)
        if not acc:
            return False
        acc["status"] = "disabled" if disabled else "active"
        save_accounts(accounts)
    return True


def admin_reset_password(uid: str, new_password: str) -> bool:
    check_password_strength(new_password)
    with _lock:
        accounts = load_accounts()
        acc = accounts.get(uid)
        if not acc:
            return False
        salt, pwd = hash_password(new_password)
        acc["salt"] = salt
        acc["pwd"] = pwd
        save_accounts(accounts)
    return True


def stats() -> dict:
    accounts = load_accounts()
    now = int(time.time())
    day_start = now - (now + 8 * 3600) % 86400
    today = sum(1 for a in accounts.values() if a.get("created", 0) >= day_start)
    active_today = sum(1 for a in accounts.values() if a.get("last_login", 0) >= day_start)
    week = sum(1 for a in accounts.values() if a.get("last_login", 0) >= now - 7 * 86400)
    month = sum(1 for a in accounts.values() if a.get("last_login", 0) >= now - 30 * 86400)
    return {
        "total": len(accounts),
        "new_today": today,
        "active_today": active_today,
        "active_7d": week,
        "active_30d": month,
        "wechat_users": sum(1 for a in accounts.values() if a.get("openid")),
        "disabled": sum(1 for a in accounts.values() if a.get("status") == "disabled"),
    }
