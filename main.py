# -*- coding: utf-8 -*-
"""小宠百问 —— 异宠饲养问答智能体后端服务
FastAPI + 大模型（OpenAI 兼容接口）+ 本地知识库检索增强（RAG）
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
import urllib.parse
import zipfile
from pathlib import Path
from typing import Optional

import geo
import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import (FileResponse, HTMLResponse, JSONResponse, RedirectResponse,
                               Response, StreamingResponse)
from fastapi.staticfiles import StaticFiles

# Brotli 是可选的：装了就用，没装就退回 gzip，不影响启动
try:
    import brotli as _brotli
except Exception:  # noqa: BLE001
    _brotli = None

import analytics
import auth
import backup
import care
import diagnose
import petdex
import usage

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
CONFIG_FILE = DATA_DIR / "config.json"
KNOWLEDGE_FILE = DATA_DIR / "knowledge.json"
FORMULARY_FILE = DATA_DIR / "formulary.json"   # 异宠药典索引：药名 / 类别 / 适用类群 / 书中提示 / 页码
COMPLIANCE_FILE = DATA_DIR / "compliance.json"
NEWS_FILE = DATA_DIR / "news.json"
NEWS_INBOX_FILE = DATA_DIR / "news_inbox.json"
NEWS_LOG_FILE = DATA_DIR / "news_log.json"
USERS_FILE = DATA_DIR / "users.json"
STATS_FILE = DATA_DIR / "stats.json"
TASKS_FILE = DATA_DIR / "tasks.json"
FEEDBACK_FILE = DATA_DIR / "feedback.json"
PETS_FILE = DATA_DIR / "pets.json"
CARELOG_FILE = DATA_DIR / "carelog.json"
CARE_EVENT_FILE = DATA_DIR / "care_events.json"
PETLOG_FILE = DATA_DIR / "petlogs.json"   # 饲养日志：喂食 / 蜕皮 / 排便 / 用药 / 体重 / 观察追踪
DIAG_FILE = DATA_DIR / "diagnoses.json"   # 拍照诊断：结论清单 + 缩略图（原图不留存，省空间也省隐私）
STATIC_DIR = BASE_DIR / "static"

DEFAULT_ADMIN_PASSWORD = "xiaochong2026"  # 默认管理员密码，建议登录后台后修改

# ============ 版本号（前台与后台各自独立迭代，互不联动） ============
APP_VERSION = "2.9.1"      # 附近医院去掉「要去后台填 Key」的提示块，未配 Key 时直接给地图入口
ADMIN_VERSION = "1.13.0"    # 后台管理系统：看板 / 分析 / 用户 / 反馈 / 养护数据 / 资讯 / 配置 / 备份

# 预设大模型厂商（OpenAI 兼容协议）
PROVIDERS = {
    "deepseek": {"name": "DeepSeek", "base_url": "https://api.deepseek.com/v1", "model": "deepseek-chat"},
    "qwen": {"name": "通义千问", "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1", "model": "qwen-plus"},
    "openai": {"name": "OpenAI", "base_url": "https://api.openai.com/v1", "model": "gpt-4o-mini"},
    "zhipu": {"name": "智谱GLM", "base_url": "https://open.bigmodel.cn/api/paas/v4", "model": "glm-4-flash"},
    "moonshot": {"name": "Moonshot Kimi", "base_url": "https://api.moonshot.cn/v1", "model": "moonshot-v1-8k"},
    "custom": {"name": "自定义", "base_url": "", "model": ""},
}

SYSTEM_PROMPT = (
    "你是「小宠百问」的答主。养了十几年异宠，也在论坛上给人回过七八年帖子。"
    "来问你的人多是刚入坑的新手，手里可能就一只兔、一盒守宫，或者一只别人送来的鸟。\n\n"

    "怎么回：\n"
    "- 先把结论摆出来。第一句话就告诉他这事要不要紧、现在该做什么，别铺垫。\n"
    "- 再讲为什么。讲具体的：多少度、几天、喂多少、什么样算不对。"
    "别写「保持适宜温湿度」这种正确但没用的话。\n"
    "- 拿不准就说拿不准。硬答比不答更害人。\n"
    "- 他问一件事就答一件事，别顺带科普三段他没问的。\n"
    "- 语气像回帖：句子可以短，可以一句话一段，可以说「别急着喂」「这个真不行」。"
    "不要客服腔，不要「希望对您有帮助」这类收尾。\n\n"

    "格式：\n"
    "- 默认用短段落说话。判断、排查、讲原因，都写成一句一句的话，不要「第一、第二、第三」，"
    "也不要「按下面这几点排查」这种预告。\n"
    "- 只有真的要教人动手（急救、喂药、布置箱子），才用 1. 2. 3. 列步骤。\n"
    "- 举个例子。别写「第一，检查温度。第二，检查蜕皮。」，"
    "写成「先看温度，热区到 30 度没有？不到就先修温度，喂什么都是白喂。再看是不是要蜕皮，"
    "身上发白就等它蜕完。」\n"
    "- 不要小标题，不要满屏加粗，不要 emoji，不要表格。\n"
    "- 一段能说清就别拆三段。答得短不要紧，答对更重要。\n"
    "- 不用「首先 / 其次 / 最后 / 总之 / 综上」，也不用「需要注意的是」「值得一提的是」这类过渡句。\n"
    "- 别编自己的经历，不要出现「我有个朋友」「之前有个客户」这种故事。就事论事。\n\n"

    "内容边界，这几条不能松：\n"
    "- 只用简体中文。\n"
    "- 手边资料里有对应内容就照着答；没有就用你确实掌握的常识，不要现编数字。\n"
    "- 涉及疾病、中毒、外伤、拒食、呼吸困难、抽搐：说清哪些情况必须马上就医，"
    "不给诊断结论，不推荐人用药，不给剂量。\n"
    "- 手边若有「药典」条目，那是给判断用的：这味药在异宠身上有没有人用过、"
    "书里记了什么风险、在第几页。饲主要是问「喂多少毫克」，就告诉他书里 p.XXX 有按体重的方案，"
    "得让兽医按他那只的体重算，你不报数字，也别帮他换算。\n"
    "- 涉及能不能养：按资料里的法规如实说，分清「可养 / 要办证 / 禁止」三种；"
    "讲不清就让他去问当地林草或农业农村部门。这条不许含糊，也不许给可能导致违法的结论。\n\n"

    "标出处：\n"
    "- 资料条目的标题后面带着书名、章节和页码，比如「异宠药物处方手册（第5版） 第10章 兔 p.726」。\n"
    "- 你用了哪条，就在那句话后面用括号带一下，写（p.726）；"
    "或者整段答完，最后单起一行写：出处：《异宠药物处方手册》第5版，第10章 表10-15，p.726。\n"
    "- 一条回答里用了几条资料就标几次，最多标三条，别堆一长串。\n"
    "- 常识性的东西（兔要吃草、守宫要加热区）不用标。没用到资料就别硬凑出处，更不许编页码。\n"
    "- 资料里有的条目后面没有书名和页码，那就是普通常识，别给它编一个来源，"
    "也不要写「（XX条目）」「（资料显示）」这种伪引用。\n"
)


# ============ 只读数据缓存 ============
# knowledge / compliance / news 这类文件几百 KB，几乎不变，但每个接口都要读。
# 用 (mtime, size) 做失效判断：文件改了自动重载，没改就直接命中内存，省掉反复 JSON 解析。
_json_cache: dict = {}
_json_lock = threading.Lock()


def _cached_json(path: Path, default):
    try:
        st = path.stat()
    except OSError:
        return default
    sig = (st.st_mtime_ns, st.st_size)
    with _json_lock:
        hit = _json_cache.get(str(path))
        if hit and hit[0] == sig:
            return hit[1]
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default
    with _json_lock:
        _json_cache[str(path)] = (sig, data)
    return data


# 云端部署时密钥不该落到仓库里：同名环境变量优先级高于 data/config.json，
# 平台面板里配一次即可，仓库里那份可以留空
ENV_CONFIG_KEYS = {
    "provider": "LLM_PROVIDER",
    "base_url": "LLM_BASE_URL",
    "model": "LLM_MODEL",
    "api_key": "LLM_API_KEY",
    "vision_base_url": "LLM_VISION_BASE_URL",
    "vision_model": "LLM_VISION_MODEL",
    "vision_api_key": "LLM_VISION_API_KEY",
    "support": "XC_SUPPORT",
    "support_hours": "XC_SUPPORT_HOURS",
    "session_secret": "SESSION_SECRET",
    "admin_password": "XC_ADMIN_PASSWORD",
    "wx_appid": "WX_APPID",
    "wx_appsecret": "WX_APPSECRET",
    "wx_redirect_domain": "WX_REDIRECT_DOMAIN",
}


def load_config() -> dict:
    # 配置含密钥且会被后台频繁改写，体量小，不做缓存以免读到旧值
    cfg = {}
    if CONFIG_FILE.exists():
        try:
            cfg = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception:
            cfg = {}
    for key, env in ENV_CONFIG_KEYS.items():
        val = os.environ.get(env, "").strip()
        if val:
            cfg[key] = val
    return cfg


def save_config(cfg: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        backup.snapshot()
    except Exception:
        pass


def load_knowledge() -> dict:
    return _cached_json(KNOWLEDGE_FILE, {"items": []})


def load_formulary() -> dict:
    return _cached_json(FORMULARY_FILE, {"items": [], "drugs": []})


def load_compliance() -> dict:
    return _cached_json(COMPLIANCE_FILE, {"items": [], "categories": [], "stats": {}})


def load_news() -> dict:
    return _cached_json(NEWS_FILE, {"items": []})


def get_admin_password() -> str:
    cfg = load_config()
    return cfg.get("admin_password") or DEFAULT_ADMIN_PASSWORD


def load_users() -> dict:
    if USERS_FILE.exists():
        try:
            return json.loads(USERS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def save_users(users: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    USERS_FILE.write_text(json.dumps(users, ensure_ascii=False, indent=2), encoding="utf-8")


# ============ 用户反馈（客服工单） ============
_fb_lock = threading.Lock()

FEEDBACK_TYPES = {"bug": "功能异常", "content": "内容纠错", "advice": "产品建议", "other": "其他问题"}


def load_feedback() -> list:
    if FEEDBACK_FILE.exists():
        try:
            data = json.loads(FEEDBACK_FILE.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return data
        except Exception:
            pass
    return []


def save_feedback(items: list) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    FEEDBACK_FILE.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        backup.snapshot()
    except Exception:
        pass


# ============ 养护数据：宠物档案 / 温湿度记录 ============
_care_lock = threading.Lock()


def _load_list(path: Path) -> list:
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return data
        except Exception:
            pass
    return []


def _save_list(path: Path, items: list) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        backup.snapshot()
    except Exception:
        pass


def load_pets() -> list:
    return _load_list(PETS_FILE)


def save_pets(items: list) -> None:
    _save_list(PETS_FILE, items)


def load_carelog() -> list:
    return _load_list(CARELOG_FILE)


def save_carelog(items: list) -> None:
    _save_list(CARELOG_FILE, items)


def load_petlogs() -> list:
    return _load_list(PETLOG_FILE)


def save_petlogs(items: list) -> None:
    _save_list(PETLOG_FILE, items)


def load_diagnoses() -> list:
    return _load_list(DIAG_FILE)


def save_diagnoses(items: list) -> None:
    _save_list(DIAG_FILE, items)


def load_care_events() -> list:
    return _load_list(CARE_EVENT_FILE)


def save_care_events(items: list) -> None:
    _save_list(CARE_EVENT_FILE, items)


# ============ 问答数据统计 ============
_stats_lock = threading.Lock()


def cn_date(ts: int = 0) -> str:
    """统一按 UTC+8 取日期，避免服务器时区导致"今日"错位。"""
    return time.strftime("%Y-%m-%d", time.gmtime((ts or time.time()) + 8 * 3600))


def load_stats() -> dict:
    if STATS_FILE.exists():
        try:
            return json.loads(STATS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"records": []}


def save_stats(stats: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    STATS_FILE.write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")


def record_chat(device_id: str, question: str, species_list: list, ref_count: int,
                ok: bool, latency_ms: int, answer_len: int, error: str = "",
                uid: str = "") -> None:
    """记录一次问答（供后台数据看板统计）。任何异常静默处理，不影响主流程。"""
    try:
        with _stats_lock:
            stats = load_stats()
            records = stats.get("records", [])
            now = int(time.time())
            records.append({
                "ts": now,
                "date": cn_date(now),
                "device_id": device_id or "",
                "uid": uid or "",
                "question": (question or "").strip()[:200],
                "species": [s for s in species_list if s][:6],
                "ref_count": ref_count,
                "ok": ok,
                "latency_ms": latency_ms,
                "answer_len": answer_len,
                "error": (error or "")[:200],
            })
            if len(records) > 10000:
                records = records[-10000:]
            stats["records"] = records
            save_stats(stats)
        analytics.record_activity(device_id, "question", uid=uid)
    except Exception:
        pass


# ============ 后台问答任务（客户端退出/断线也继续生成） ============
_tasks_lock = threading.RLock()
_tasks = {}  # task_id -> task dict
TASKS_KEEP = 300


def _load_tasks() -> None:
    """启动时载入已持久化的问答任务，用于用户退出后再进入时接续答案。"""
    if not TASKS_FILE.exists():
        return
    try:
        arr = json.loads(TASKS_FILE.read_text(encoding="utf-8"))
        with _tasks_lock:
            for t in arr:
                if isinstance(t, dict) and t.get("task_id"):
                    _tasks[t["task_id"]] = t
    except Exception:
        pass


def _persist_tasks_locked() -> None:
    """把任务表写盘（仅保留最近 TASKS_KEEP 条）。调用方可持锁（RLock 可重入）。"""
    try:
        with _tasks_lock:
            items = sorted(_tasks.values(), key=lambda x: x.get("ts", 0), reverse=True)[:TASKS_KEEP]
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            TASKS_FILE.write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


def _cleanup_tasks_locked() -> None:
    with _tasks_lock:
        if len(_tasks) <= TASKS_KEEP:
            return
        items = sorted(_tasks.values(), key=lambda x: x.get("ts", 0))
        for t in items[: len(_tasks) - TASKS_KEEP]:
            _tasks.pop(t.get("task_id"), None)


_http_lock = threading.Lock()
_llm_client: Optional[httpx.Client] = None


def _get_llm_client() -> httpx.Client:
    """全局复用的连接池。

    以前每次提问都新建 Client，跨境访问要重新做 TCP + TLS 握手（实测 0.3~1 s），
    高频提问时这段开销白白叠加在首字延迟上。复用后第二次起直接走长连接。
    """
    global _llm_client
    if _llm_client is None:
        with _http_lock:
            if _llm_client is None:
                _llm_client = httpx.Client(
                    timeout=httpx.Timeout(120.0, connect=15.0),
                    limits=httpx.Limits(max_keepalive_connections=24, max_connections=48,
                                        keepalive_expiry=120.0),
                    headers={"User-Agent": "xiaochongbaiwen/1.23"},
                )
    return _llm_client


def _run_chat_task(task_id: str, device_id: str, question: str, full_messages: list,
                   refs: list, species_list: list, api_key: str, base_url: str, model: str,
                   uid: str = "") -> None:
    """后台线程：调用大模型并累积答案。与 HTTP 连接完全解耦，客户端断开仍会跑完。"""
    url = base_url.rstrip("/") + "/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {"model": model, "messages": full_messages, "stream": True, "temperature": 0.7}
    start = time.time()
    answer = ""
    ok = False
    truncated = False
    err = ""
    with _tasks_lock:
        cur = _tasks.get(task_id)
        if cur:
            cur["status"] = "running"
    try:
        client = _get_llm_client()
        with client.stream("POST", url, json=payload, headers=headers) as resp:
            if resp.status_code != 200:
                text = resp.read().decode("utf-8", "ignore")
                err = f"上游接口返回 {resp.status_code}：{text[:300]}"
            else:
                for line in resp.iter_lines():
                    if not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        ok = True
                        break
                    try:
                        obj = json.loads(data)
                        ch = obj["choices"][0]
                        delta = ch["delta"].get("content")
                        if delta:
                            answer += delta
                            with _tasks_lock:
                                cur = _tasks.get(task_id)
                                if cur:
                                    cur["answer"] = answer
                        # 上游按 token 上限截断时要标出来，否则用户看到的是一句没说完的话
                        if ch.get("finish_reason") == "length":
                            truncated = True
                    except Exception:
                        continue
    except Exception as e:  # noqa: BLE001
        err = f"请求失败：{e}"
    finally:
        if truncated and answer:
            answer += "\n\n（回答较长，先讲到这里。可以接着问「继续说」，我往下讲。）"
        latency = int((time.time() - start) * 1000)
        with _tasks_lock:
            cur = _tasks.get(task_id)
            if cur:
                cur["answer"] = answer
                cur["status"] = "done" if (ok or answer) else "error"
                cur["err"] = err
                cur["done_ts"] = int(time.time())
                cur["latency_ms"] = latency
        _persist_tasks_locked()
        record_chat(device_id, question, species_list, len(refs), ok or bool(answer),
                    latency, len(answer), err, uid=uid)


_load_tasks()


# ============ 行业动态每日自动更新 ============
def _news_scheduler_loop() -> None:
    """每天 06:00 自动更新行业动态；失败静默，不影响主服务。"""
    while True:
        try:
            now = time.time()
            # 以 UTC+8 计的当天 06:00 作为下次执行时间
            lt = time.gmtime(now + 8 * 3600)
            today6 = time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, 6, 0, 0, 0, 0, -1)) - 8 * 3600
            next_run = today6 if today6 > now else today6 + 86400
            time.sleep(max(60, next_run - now))
            import news_updater
            news_updater.update_news()
        except Exception:
            time.sleep(3600)


def build_stats(stats: dict) -> dict:
    records = stats.get("records", [])
    now = int(time.time())
    today = cn_date(now)

    total = len(records)
    today_q = sum(1 for r in records if r.get("date") == today)
    visitors = len({r.get("device_id") for r in records if r.get("device_id")})
    today_visitors = len({r.get("device_id") for r in records if r.get("date") == today and r.get("device_id")})

    ok_count = sum(1 for r in records if r.get("ok"))
    hit_count = sum(1 for r in records if r.get("ref_count", 0) > 0)
    success_rate = round(ok_count / total, 4) if total else 0
    knowledge_hit_rate = round(hit_count / total, 4) if total else 0

    latencies = [r.get("latency_ms", 0) for r in records if r.get("latency_ms")]
    avg_latency = round(sum(latencies) / len(latencies)) if latencies else 0

    daily = {}
    for r in records:
        d = r.get("date")
        if d:
            daily[d] = daily.get(d, 0) + 1
    days = []
    for i in range(6, -1, -1):
        d = cn_date(now - i * 86400)
        days.append({"date": d[5:], "full": d, "count": daily.get(d, 0)})

    q_counter = {}
    for r in records:
        q = (r.get("question") or "").strip()
        if q:
            q_counter[q] = q_counter.get(q, 0) + 1
    top_questions = [{"q": q, "count": c} for q, c in sorted(q_counter.items(), key=lambda x: -x[1])[:10]]

    sp_counter = {}
    for r in records:
        for s in (r.get("species") or []):
            if s:
                sp_counter[s] = sp_counter.get(s, 0) + 1
    species_dist = [{"species": s, "count": c} for s, c in sorted(sp_counter.items(), key=lambda x: -x[1])[:15]]

    # 知识盲区：没能命中任何知识条目的问题。这是补知识库最直接的依据。
    gap_counter, gap_last = {}, {}
    for r in records:
        if r.get("ref_count", 0) > 0:
            continue
        q = (r.get("question") or "").strip()
        if not q or len(q) < 4:
            continue
        gap_counter[q] = gap_counter.get(q, 0) + 1
        d = r.get("date") or ""
        if d > gap_last.get(q, ""):
            gap_last[q] = d
    knowledge_gaps = [
        {"q": q, "count": c, "last": gap_last.get(q, "")}
        for q, c in sorted(gap_counter.items(), key=lambda x: -x[1])[:10]
    ]
    gap_total = len(gap_counter)

    recent = []
    for r in sorted(records, key=lambda x: x.get("ts", 0), reverse=True)[:20]:
        recent.append({
            "time": time.strftime("%m-%d %H:%M", time.gmtime(r.get("ts", 0) + 8 * 3600)),
            "question": r.get("question"),
            "species": r.get("species"),
            "ok": r.get("ok"),
            "latency_ms": r.get("latency_ms"),
        })

    result = {
        "totals": {
            "questions": total,
            "today_questions": today_q,
            "visitors": visitors,
            "today_visitors": today_visitors,
            "success_rate": success_rate,
            "knowledge_hit_rate": knowledge_hit_rate,
            "avg_latency_ms": avg_latency,
        },
        "daily": days,
        "top_questions": top_questions,
        "species_dist": species_dist,
        "knowledge_gaps": knowledge_gaps,
        "gap_total": gap_total,
        "recent": recent,
    }
    # 日活 / 月活 / 留存等活跃统计
    try:
        accounts = auth.load_accounts()

        def _label(raw: str) -> str:
            acc = accounts.get(raw)
            if not acc:
                return ""
            phone = acc.get("phone") or ""
            if len(phone) == 11:
                return phone[:3] + "****" + phone[-4:]
            return acc.get("nickname") or ""

        result["analytics"] = analytics.compute(records, user_names=_label, accounts=accounts)
    except Exception as e:  # noqa: BLE001
        result["analytics"] = {"error": str(e)[:200]}
    return result


def get_session_secret() -> str:
    cfg = load_config()
    secret = cfg.get("session_secret") or os.environ.get("SESSION_SECRET", "")
    if not secret:
        secret = secrets.token_hex(32)
        cfg["session_secret"] = secret
        save_config(cfg)
    return secret


def make_session(openid: str, secret: str) -> str:
    payload = {"openid": openid, "exp": int(time.time()) + 30 * 86400}
    data = base64.urlsafe_b64encode(json.dumps(payload, ensure_ascii=False).encode()).decode().rstrip("=")
    sig = hmac.new(secret.encode(), data.encode(), hashlib.sha256).hexdigest()
    return f"{data}.{sig}"


def parse_session(token: str, secret: str) -> Optional[str]:
    try:
        data, sig = token.split(".", 1)
        expected = hmac.new(secret.encode(), data.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, sig):
            return None
        payload = json.loads(base64.urlsafe_b64decode(data + "=" * (-len(data) % 4)))
        if payload.get("exp", 0) > time.time():
            return payload.get("openid")
    except Exception:
        pass
    return None


def get_wx_config() -> dict:
    cfg = load_config()
    return {
        "appid": cfg.get("wx_appid") or os.environ.get("WX_APPID", ""),
        "secret": cfg.get("wx_appsecret") or os.environ.get("WX_APPSECRET", ""),
        "redirect_domain": cfg.get("wx_redirect_domain") or os.environ.get("WX_REDIRECT_DOMAIN", ""),
    }


# 口语同义词 → 标准词，用于查询扩展，提升检索召回
SYNONYMS = {
    "控温": "温度", "恒温": "温度", "保温": "温度", "加热": "温度", "降温": "温度",
    "吃东西": "喂食", "进食": "喂食", "喂什么": "喂食", "怎么喂": "喂食",
    "生病": "疾病", "得病": "疾病", "不舒服": "疾病", "病了": "疾病", "生什么病": "疾病",
    "笼子": "环境", "箱子": "环境", "饲养箱": "环境", "鱼缸": "环境", "居住": "环境",
    "蜕壳": "蜕皮", "换壳": "蜕皮", "换皮": "蜕皮", "脱皮": "蜕皮",
    "幼崽": "幼体", "宝宝": "幼体", "小宝宝": "幼体",
}

# 物种口语名 → 知识库里的物种大类。
# 用户说「鹦鹉」「虎皮」的时候，用药条目挂的 species 是「鸟类」，
# 不扩这一步，问「鹦鹉热用什么药」会先命中「虎皮鹦鹉吃什么」，而不是用药条目。
SPECIES_ALIAS = {
    "爬行动物": ["龟", "乌龟", "陆龟", "水龟", "巴西龟", "草龟", "蛇", "蟒", "守宫", "蜥蜴", "鬣蜥", "巨蜥", "变色龙", "鳄", "鳄龟"],
    "鸟类": ["鹦鹉", "虎皮", "玄凤", "牡丹鹦鹉", "金刚", "非洲灰", "灰机", "雀", "金丝雀", "文鸟", "鸽子", "八哥", "鹩哥", "隼", "猫头鹰", "猛禽", "鹌鹑"],
    "两栖动物": ["蛙", "蟾蜍", "蝾螈", "娃娃鱼", "角蛙", "树蛙", "美西螈"],
    "鱼类": ["鱼", "锦鲤", "金鱼", "龙鱼", "七彩神仙", "孔雀鱼", "斗鱼", "罗汉"],
    "啮齿动物": ["仓鼠", "豚鼠", "荷兰猪", "龙猫", "大鼠", "小鼠", "沙鼠", "花枝"],
    "兔子": ["兔"],
    "雪貂": ["雪貂", "貂"],
    "刺猬": ["刺猬"],
    "蜜袋鼯": ["蜜袋鼯", "蜜袋"],
    "小型猪": ["小型猪", "宠物猪", "香猪"],
    "无脊椎动物": ["蜘蛛", "蝎", "虾", "蟹", "螺", "珊瑚", "甲虫", "螳螂", "蜗牛"],
}


# 药典按「兔」记，知识库按「兔子」记，比较前先归到一套写法上
_SP_NORM = {"兔": "兔子", "家禽": "鸟类", "啮齿": "啮齿动物"}


def _norm_sp(s: str) -> str:
    return _SP_NORM.get(s, s)


def species_of_query(query: str) -> set:
    """问题里提到了哪几类动物。只认大类，不做更细的判断。"""
    q = query or ""
    hit = set()
    for sp, words in SPECIES_ALIAS.items():
        for w in words:
            if w in q:
                hit.add(sp)
                break
    return hit


# 法律合规意图词根：命中这些词的问题，给相关条目更高权重，提升「能不能养」类问题召回
LAW_WORDS = [
    "合法", "法律", "保护动物", "禁止", "禁养", "违禁", "违法", "犯法",
    "能养", "不能养", "不让养", "不许", "买卖", "许可", "手续", "名录",
    "外来", "入侵", "放生", "可养",
]


def retrieve(query: str, items: list, top_k: int = 5) -> list:
    """基于关键词命中的轻量检索：返回与问题最相关的知识条目。"""
    q = query or ""
    # 查询扩展：把口语同义词补充进匹配词集合
    expanded = [q]
    for k, v in SYNONYMS.items():
        if k in q:
            expanded.append(v)

    # 法律合规意图：问题涉及"能不能养/合法/违法/禁止"等时，法律条目优先
    legal_intent = ["能养", "能不能", "可以养", "合法", "违法", "犯法", "禁止", "禁养", "保护动物", "保护吗", "外来", "放生", "许可", "当宠物"]
    has_legal_intent = any(w in q for w in legal_intent)

    q_species = species_of_query(q)

    scored = []
    for it in items:
        score = 0
        species = it.get("species", "")
        # 物种语境：问的是鸟，鸟类的条目就该排在「同名不同类」的条目前面
        if q_species and species in q_species:
            score += 3
        # 物种名命中（且非"通用"）权重高；支持上位词部分命中（如"守宫"命中"豹纹守宫"）
        species_hit = False
        if species and species != "通用":
            if species in q:
                species_hit = True
            else:
                for i in range(len(q) - 1):
                    seg = q[i:i + 2]
                    if seg and seg in species:
                        species_hit = True
                        break
        if species_hit:
            score += 3
        # 关键词命中（对扩展后的查询做匹配，提升口语问题召回）
        for kw in it.get("keywords", []):
            if kw and any(kw in e for e in expanded):
                score += 2 if any(lw in kw for lw in LAW_WORDS) else 1
        if has_legal_intent:
            iid = it.get("id", "")
            # 所有禁养/合法专项条目（*_banned / *_legal / *_invasive）优先，确保合规类问题先命中法律条目
            if "banned" in iid or "legal" in iid or "invasive" in iid:
                score += 4
        scored.append((score, it))

    hits = [pair for pair in scored if pair[0] > 0]
    hits.sort(key=lambda x: -x[0])
    return [it for _, it in hits[:top_k]]


def retrieve_formulary(query: str, top_k: int = 2) -> list:
    """从药典索引里认出问题里提到的药。

    只认完整药名（中文名或英文名），不做词根模糊匹配：「菌素」「沙星」这种两字片段
    会把伊维菌素和泰乐菌素一起拉进来，答非所问比不答更糟。

    还要求物种对得上：问兔的，只在书里写过兔的那几味药才注入。药典的页码是精确到章的，
    拿鱼类章的页码去回答兔的问题，等于给错出处。
    """
    q = query or ""
    if not q:
        return []
    ql = q.lower()
    qsp = species_of_query(q)
    hits = []
    for d in load_formulary().get("drugs", []):
        name = d.get("name", "")
        if not name:
            continue
        if name in q:
            score = 10 + min(len(name), 6)
        elif d.get("en") and len(d["en"]) >= 5 and d["en"].lower() in ql:
            score = 8
        else:
            continue
        if qsp and not (qsp & {_norm_sp(x) for x in (d.get("species") or [])}):
            continue
        if qsp:
            score += 6
        hits.append((score, d))
    hits.sort(key=lambda x: -x[0])
    return [d for _, d in hits[:top_k]]


# 药典页码很多，注入时优先挑跟问题里的动物对得上的那章，其次挑最常见的几章
_REF_PRIORITY = ["兔", "鸟", "爬行", "啮齿", "两栖", "雪貂", "刺猬", "蜜袋鼯", "小型猪", "鱼", "无脊椎", "野生"]
_SP_CH = {
    "兔子": "兔", "鸟类": "鸟", "爬行动物": "爬行", "啮齿动物": "啮齿", "两栖动物": "两栖",
    "鱼类": "鱼", "雪貂": "雪貂", "刺猬": "刺猬", "蜜袋鼯": "蜜袋鼯", "小型猪": "小型猪",
    "无脊椎动物": "无脊椎", "灵长类动物": "灵长", "野生动物": "野生",
}


def _pick_refs(refs: list, n: int = 2, prefer=None) -> list:
    keys = []
    for sp in (prefer or []):
        k = _SP_CH.get(_norm_sp(sp))
        if k:
            keys.append(k)
    keys.extend(_REF_PRIORITY)

    def rank(r):
        ch = r.get("chapter", "")
        for i, k in enumerate(keys):
            if k in ch:
                return i
        return len(keys)
    return sorted(refs, key=rank)[:n]


def _drug_line(d: dict, prefer=None) -> str:
    """把一味药压成一行注入文本。剂量一律不进提示词，只留判断依据和页码。"""
    cls = (d.get("cls") or "").strip()
    if d.get("detail"):
        cls = f"{cls}（{d['detail']}）" if cls else d["detail"]
    parts = []
    if cls:
        parts.append(cls)
    sp = "、".join((d.get("species") or [])[:6])
    if sp:
        more = "等" if len(d.get("species") or []) > 6 else ""
        parts.append(f"书里在{sp}{more}章有记录")
    warn = "；".join((d.get("warnings") or [])[:3])
    if warn:
        parts.append("书中提示：" + warn)
    refs = _pick_refs(d.get("refs") or [], 1, prefer)
    src = "、".join(f"{r.get('chapter', '')} p.{r.get('page', '')}" for r in refs)
    body = "；".join(parts) if parts else "书中收录，无特别提示"
    tail = "。按体重的给药方案在原书，饲主不可据此自行配药。" if d.get("doses") else "。"
    return f"【药典·{d['name']}｜{src}】{body}{tail}"


def build_system_content(query: str):
    """构建系统提示词，并返回命中的参考条目（供前端展示来源）。

    三块内容拼在一起：固定的答主设定、知识库里命中的条目（带书名页码）、
    药典里认出来的药（只给判断依据，不给剂量）。

    长度收敛：单条截到 300 字、知识总量截到 1750 字，药典条目每条一两行不占多少。
    命中条目多数只有一两百字，本来不会触发；但个别长条目会把提示词撑到两三千字，
    直接拖慢首字返回，而尾部的细节对回答帮助有限。
    """
    items = load_knowledge().get("items", [])
    refs = retrieve(query, items)
    drugs = retrieve_formulary(query)

    content = SYSTEM_PROMPT
    lines = []
    budget = 1750
    for r in refs:
        body = (r.get("content", "") or "").strip()
        if len(body) > 300:
            body = body[:300].rstrip("，。、；") + "…"
        src = r.get("source") or {}
        tag = ""
        if src:
            tag = f"｜{src.get('book', '')} {src.get('chapter', '')} p.{src.get('page', '')}"
        if budget - len(body) < 120 and lines:
            break
        budget -= len(body)
        lines.append(f"【{r.get('species', '')}·{r.get('title', '')}{tag}】{body}")

    prefer = species_of_query(query)
    # 同一条页码已经由知识条目讲过了，就不再重复挂一次药典索引
    used_pages = {str((r.get("source") or {}).get("page", "")) for r in refs}
    drugs = [d for d in drugs
             if str((_pick_refs(d.get("refs") or [], 1, prefer) or [{}])[0].get("page", "")) not in used_pages]
    lines.extend(_drug_line(d, prefer) for d in drugs)
    if lines:
        content += "\n\n手边的资料（对得上就用，对不上就按常识答；引用了要标出处）：\n\n" + "\n\n".join(lines)

    ref_labels = []
    for r in refs:
        src = r.get("source") or {}
        ref_labels.append({
            "species": r.get("species", ""),
            "title": r.get("title", ""),
            "book": src.get("book", ""),
            "chapter": src.get("chapter", ""),
            "section": src.get("section", ""),
            "page": src.get("page", ""),
        })
    for d in drugs:
        picked = _pick_refs(d.get("refs") or [], 1, species_of_query(query))
        ref = picked[0] if picked else {}
        # 物种跟着页码走：页码挑的是兔章，卡片上就不能写「鱼类、爬行动物」
        ch_sp = re.sub(r"^第\d+章\s*", "", ref.get("chapter", ""))
        ch_sp = {"兔": "兔子", "鱼类": "鱼类"}.get(ch_sp, ch_sp)
        ref_labels.append({
            "species": ch_sp or "药典",
            "title": f"{d.get('name', '')}（{d.get('cls', '')}）",
            "book": "异宠药物处方手册（第5版）",
            "chapter": ref.get("chapter", ""),
            "section": "",
            "page": ref.get("page", ""),
        })
    return content, ref_labels


def resolve_llm(cfg: dict):
    provider = cfg.get("provider", "deepseek")
    api_key = cfg.get("api_key") or os.environ.get("LLM_API_KEY", "")
    base_url = cfg.get("base_url") or PROVIDERS.get(provider, {}).get("base_url", "")
    model = cfg.get("model") or PROVIDERS.get(provider, {}).get("model", "")
    return api_key, base_url, model


# 各厂商默认的识图模型：主模型大多是纯文本，看图要单独指定
VISION_MODELS = {
    "deepseek": "deepseek-flash",
    "openai": "gpt-4o-mini",
    "qwen": "qwen-vl-plus",
    "zhipu": "glm-4v-flash",
    "moonshot": "moonshot-v1-8k-vision-preview",
}


def resolve_vision(cfg: dict):
    """识图模型：后台可单独指定，没指定就按厂商取默认的视觉模型。"""
    api_key, base_url, model = resolve_llm(cfg)
    v_model = (cfg.get("vision_model") or "").strip()
    v_key = (cfg.get("vision_api_key") or "").strip()
    v_base = (cfg.get("vision_base_url") or "").strip()
    if v_model:
        return (v_key or api_key), (v_base or base_url), v_model
    provider = cfg.get("provider", "deepseek")
    guess = VISION_MODELS.get(provider, "")
    if not guess and "deepseek" in (base_url or "").lower():
        guess = "deepseek-flash"
    return api_key, base_url, (guess or model)


def sse(obj) -> str:
    return "data: " + json.dumps(obj, ensure_ascii=False) + "\n\n"


class BrotliMiddleware:
    """在 gzip 之外再加一层 Brotli。

    同样的首页 gzip 后 95 KB，Brotli(q5) 约 65 KB，弱网下能省半秒左右。
    现代浏览器都声明 br；不支持的客户端原样走 gzip，行为不变。
    实现上等同于 Starlette 的 GZipResponder，只是换了压缩函数，并且
    在命中 br 时把下层的 Accept-Encoding 改成 identity，避免压两遍。
    """

    # 只有文本类才压；图片、字体本来就是压缩格式，再压只会更慢
    TEXT_TYPES = ("text/", "application/json", "application/javascript",
                  "application/xml", "image/svg+xml")

    def __init__(self, app, minimum_size: int = 600, quality: int = 5):
        self.app = app
        self.minimum_size = minimum_size
        self.quality = quality

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or _brotli is None:
            await self.app(scope, receive, send)
            return
        ae = ""
        for k, v in scope["headers"]:
            if k.lower() == b"accept-encoding":
                ae = v.decode("latin-1")
                break
        if "br" not in ae.lower():
            await self.app(scope, receive, send)
            return

        # 屏蔽下层的 gzip，避免二次压缩；原始 Accept-Encoding 留在 scope 里，
        # 视图函数若要自己做预压缩缓存还能看到客户端真实能力
        inner = [(k, v) for k, v in scope["headers"] if k.lower() != b"accept-encoding"]
        inner.append((b"accept-encoding", b"identity"))
        inner_scope = dict(scope, headers=inner, xc_accept_encoding=ae)

        state = {"skip": False, "status": 0, "headers": [], "buf": bytearray()}
        is_head = scope.get("method") == "HEAD"

        async def _send(message):
            if message["type"] == "http.response.start":
                status = message["status"]
                hdrs = list(message.get("headers", []))
                skip = status in (204, 304) or is_head
                if any(k.lower() == b"content-encoding" for k, _ in hdrs):
                    skip = True
                if not skip:
                    ctype = ""
                    for k, v in hdrs:
                        if k.lower() == b"content-type":
                            ctype = v.decode("latin-1").lower()
                            break
                    if not any(t in ctype for t in self.TEXT_TYPES):
                        skip = True
                if skip:
                    state["skip"] = True
                    await send(message)
                    return
                state["status"] = status
                state["headers"] = [(k, v) for k, v in hdrs
                                    if k.lower() not in (b"content-length", b"content-encoding")]
                state["headers"].append((b"content-encoding", b"br"))
                state["headers"].append((b"vary", b"Accept-Encoding"))
                return  # body 收齐了再一起发

            if message["type"] == "http.response.body":
                if state["skip"]:
                    await send(message)
                    return
                state["buf"] += message.get("body", b"")
                if message.get("more_body", False):
                    return
                raw = bytes(state["buf"])
                headers = state["headers"]
                if len(raw) < self.minimum_size:
                    # 太小了，压完可能更大，退回明文
                    headers = [(k, v) for k, v in headers
                               if k.lower() not in (b"content-encoding", b"vary")]
                    headers.append((b"content-length", str(len(raw)).encode()))
                    out = raw
                else:
                    try:
                        out = _brotli.compress(raw, quality=self.quality)
                    except Exception:  # noqa: BLE001
                        headers = [(k, v) for k, v in headers
                                   if k.lower() not in (b"content-encoding", b"vary")]
                        headers.append((b"content-length", str(len(raw)).encode()))
                        out = raw
                await send({"type": "http.response.start", "status": state["status"],
                            "headers": headers})
                await send({"type": "http.response.body", "body": out})
                return

            await send(message)

        await self.app(inner_scope, receive, _send)


app = FastAPI(title="小宠百问", docs_url=None, redoc_url=None)

# 传输压缩：367 KB 的首页压到 96 KB（gzip）/ 约 65 KB（br）。
# 移动端弱网下这是首屏最大的一笔开销。
app.add_middleware(GZipMiddleware, minimum_size=600, compresslevel=6)
app.add_middleware(BrotliMiddleware, minimum_size=600, quality=5)


class CachedStaticFiles(StaticFiles):
    """静态资源带强缓存：图片/字体基本不变，让浏览器直接复用磁盘缓存。

    以前没有 Cache-Control，每次进图鉴、每次切回来都会重新下载 132 张图，
    弱网下滚动一遍要几 MB 流量。带哈希或时间戳的 URL 走长缓存，其余走 7 天。
    """

    async def get_response(self, path: str, scope):
        resp = await super().get_response(path, scope)
        if resp.status_code == 200:
            # 图片可以长缓存；脚本和样式必须每次回源校验。
            # 微信 WebView 会无视 max-age 直接吃旧文件，之前就出现过
            # 「新 HTML + 旧 app.js」的错配（首页时间显示成 --:--）。
            if path.startswith("dex/") or path.endswith((".woff2", ".jpg", ".png", ".webp")):
                resp.headers["Cache-Control"] = "public, max-age=604800"
            elif path.endswith((".js", ".css")):
                resp.headers["Cache-Control"] = "no-cache, must-revalidate, max-age=0"
            else:
                resp.headers["Cache-Control"] = "public, max-age=3600"
        return resp



# ============ 登录鉴权 ============
def require_user(request: Request) -> dict:
    """业务接口统一鉴权：未登录返回 401，前端据此弹出登录页。

    登录态按自然日失效，跨到第二天会返回 day_rollover，
    前端据此提示「已是新的一天」，而不是笼统的「登录已失效」。
    """
    acc, why = auth.session_state(request)
    if not acc:
        raise HTTPException(
            status_code=401,
            detail="day_rollover" if why == "newday" else "login_required",
        )
    return acc


def _set_login_cookie(resp, request: Request, token: str) -> None:
    """双保险：Cookie 给标准浏览器，前端同时把 token 存 localStorage 走 X-Token 头。"""
    secure = (request.headers.get("x-forwarded-proto", "") == "https"
              or request.url.scheme == "https")
    # Cookie 也跟着零点到期：浏览器一关一开、第二天再来时连令牌都不会带上
    left = max(60, auth.day_end() - int(time.time()))
    resp.set_cookie(
        auth.COOKIE_NAME, token,
        max_age=min(left, auth.TOKEN_DAYS * 86400),
        httponly=True, samesite="lax", secure=secure, path="/",
    )


def _user_payload(acc: dict) -> dict:
    """对外返回的用户信息（含实时提问次数）。"""
    user = auth.public_user(acc)
    try:
        recs = load_stats().get("records", [])
        if acc.get("uid"):
            user["questions"] = sum(1 for r in recs if r.get("uid") == acc.get("uid"))
    except Exception:
        pass
    return user


@app.on_event("startup")
async def _on_startup():
    # 数据自愈：账号/配置/反馈若缺失（例如重新部署覆盖），先从最近快照恢复
    try:
        restored = backup.restore_missing()
        if restored:
            print(f"[backup] 已从快照恢复: {restored}", flush=True)
        backup.snapshot(force=True)
    except Exception as e:  # noqa: BLE001
        print(f"[backup] 快照初始化失败: {e}", flush=True)
    # IP 归属地库在后台解压建索引，别让第一个后台请求替它等这 200ms
    try:
        geo.warm()
    except Exception:
        pass
    # 启动行业动态每日定时更新线程（每天 06:00）
    threading.Thread(target=_news_scheduler_loop, daemon=True).start()
    # 把历史问答记录回填为活跃数据，保证日活/月活趋势有历史可看
    threading.Thread(target=lambda: analytics.rebuild_from_records(load_stats().get("records", [])),
                     daemon=True).start()


@app.get("/api/health")
async def health():
    cfg = load_config()
    return {
        "ok": True,
        "name": "小宠百问",
        "app_version": APP_VERSION,      # 前台版本
        "admin_version": ADMIN_VERSION,  # 后台版本
        # 客服联系方式由后台「系统配置」维护，留空则前端不展示
        "support": cfg.get("support", ""),
        "support_hours": cfg.get("support_hours", ""),
        # 图鉴规模，前端「关于」直接引用，免得两处数字对不上
        "dex_keep": len(petdex.SPECIES),
        "dex_no": len(petdex.FORBIDDEN),
    }


@app.post("/api/track")
async def track(request: Request):
    """前端埋点：用户打开页面即记一次活跃（同一设备当天只算一个活跃用户）。"""
    try:
        body = await request.json()
    except Exception:
        body = {}
    device_id = (body.get("device_id") or "").strip()[:64]
    if not device_id:
        return {"ok": False}
    src = (body.get("src") or "").strip()[:32]
    acc = auth.current_account(request)
    analytics.record_activity(device_id, "visit", src=src, uid=(acc or {}).get("uid", ""))
    return {"ok": True}


# ============ 登录 / 注册 ============
@app.get("/api/auth/config")
async def auth_config():
    """登录页可用的登录方式（微信授权仅在管理员配置了公众号后开启）。"""
    c = get_wx_config()
    return {
        "phone_login": True,
        "wechat_login": bool(c["appid"] and c["secret"]),
        "notice": "登录后可保存提问记录、跨设备同步",
    }


@app.post("/api/auth/register")
async def auth_register(request: Request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    device_id = (body.get("device_id") or "").strip()[:64]
    try:
        acc = auth.register(
            phone=body.get("phone", ""),
            password=body.get("password", ""),
            nickname=body.get("nickname", ""),
            src=(body.get("src") or "direct")[:20],
            device_id=device_id,
            ip=auth.client_ip(request),
        )
    except auth.AuthError as e:
        return JSONResponse({"error": e.message}, status_code=e.status)

    token = auth.make_token(acc["uid"], acc.get("phone", ""))
    # day_end：今天夜里 12 点的时间戳，前端据此挂「到期自动登出」的定时器
    resp = JSONResponse({"ok": True, "token": token, "user": _user_payload(acc),
                         "day_end": auth.day_end()})
    _set_login_cookie(resp, request, token)
    usage.mark_login(acc["uid"])
    analytics.record_activity(device_id, "visit", uid=acc["uid"],
                              src=acc.get("source", "direct"))
    return resp


@app.post("/api/auth/login")
async def auth_login(request: Request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    device_id = (body.get("device_id") or "").strip()[:64]
    try:
        acc = auth.login(body.get("phone", ""), body.get("password", ""), device_id,
                         ip=auth.client_ip(request))
    except auth.AuthError as e:
        return JSONResponse({"error": e.message}, status_code=e.status)

    token = auth.make_token(acc["uid"], acc.get("phone", ""))
    # day_end：今天夜里 12 点的时间戳，前端据此挂「到期自动登出」的定时器
    resp = JSONResponse({"ok": True, "token": token, "user": _user_payload(acc),
                         "day_end": auth.day_end()})
    _set_login_cookie(resp, request, token)
    usage.mark_login(acc["uid"])
    analytics.record_activity(device_id, "visit", uid=acc["uid"],
                              src=acc.get("source", "direct"))
    return resp


@app.post("/api/auth/logout")
async def auth_logout():
    resp = JSONResponse({"ok": True})
    resp.delete_cookie(auth.COOKIE_NAME, path="/")
    return resp


@app.get("/api/auth/me")
async def auth_me(request: Request):
    acc, why = auth.session_state(request)
    if not acc:
        # reason 让前端把「过了夜里 12 点」和「令牌失效」分开提示
        return {"logged_in": False, "reason": why}
    payload = _user_payload(acc)
    try:
        # 只在「我的」这一处用到，顺手给个 IP 归属地提示，省得用户自己想填什么
        payload["hint_loc"] = geo.lookup(acc.get("last_ip") or "")
    except Exception:
        payload["hint_loc"] = ""
    return {"logged_in": True, "user": payload,
            "token": auth.make_token(acc["uid"], acc.get("phone", "")),
            "day_end": auth.day_end()}


@app.post("/api/usage/ping")
async def usage_ping(request: Request):
    """前端每隔一分钟报一次「刚才用了多少秒」。

    只在页面可见、且最近三分钟有操作时计时，所以这个数接近真实在线时长，
    不是「开着标签页挂一天」。单次上限 5 分钟，防止前端算错把时长灌爆。
    """
    acc = require_user(request)
    try:
        body = await request.json()
    except Exception:
        body = {}
    sec = usage.add_time(acc["uid"], body.get("seconds") or 0)
    return {"ok": True, "added": sec}


# ============ 附近动物医院（高德周边搜索） ============
# 只在内存里缓存 10 分钟：高德的服务条款不允许把 POI 数据长期留存，
# 这个时长够挡住同一栋楼里反复刷新，重启即清空，不落盘。
_VET_CACHE = {}
_VET_TTL = 600
_VET_MAX = 300
_vet_lock = threading.Lock()

# 高德的周边搜索只认 GCJ-02；前端已经拿浏览器定位转好再传，
# 这里只做范围兜底，防止有人拿经纬度乱传把配额刷光。
_VET_KW = "宠物医院|动物医院|异宠|兽医"

# 每人每分钟最多查 12 次：地图配额是公共的，一个人反复刷新就能把它刷光
_vet_hits = {}
_vet_hit_lock = threading.Lock()


def _vet_throttle(uid: str) -> bool:
    now = time.time()
    with _vet_hit_lock:
        arr = [t for t in _vet_hits.get(uid, []) if now - t < 60]
        if len(arr) >= 12:
            _vet_hits[uid] = arr
            return False
        arr.append(now)
        if len(_vet_hits) > 5000:
            _vet_hits.clear()
        _vet_hits[uid] = arr
    return True


def _vet_cache_get(key):
    now = time.time()
    with _vet_lock:
        hit = _VET_CACHE.get(key)
        if hit and now - hit[0] < _VET_TTL:
            return hit[1]
        if hit:
            _VET_CACHE.pop(key, None)
    return None


def _vet_cache_put(key, items):
    with _vet_lock:
        if len(_VET_CACHE) >= _VET_MAX:
            # 简单粗暴地清掉过期的一半，别让缓存无限长
            now = time.time()
            dead = [k for k, v in _VET_CACHE.items() if now - v[0] > _VET_TTL]
            for k in dead:
                _VET_CACHE.pop(k, None)
            if len(_VET_CACHE) >= _VET_MAX:
                _VET_CACHE.clear()
        _VET_CACHE[key] = (time.time(), items)


# 名字里带这些词的，大概率接异宠。只用来打「可能」的标签，不做承诺——
# 真正的结论还得打电话问，很多医院名字里没有、但医生会看。
_VET_EXOTIC = ("异宠", "爬宠", "爬虫", "两栖", "鸟类", "鸟科", "鹦鹉", "兔", "龙猫",
               "仓鼠", "蜜袋鼯", "刺猬", "蜥蜴", "陆龟", "水龟", "小宠", "特宠",
               "exotic", "reptile")

_REGIONS = {"mtime": 0.0, "data": None}


def _meters_between(lat1: float, lng1: float, lat2: float, lng2: float) -> int:
    """两点直线距离（米）。用于「按区县查」时补上距离——place/text 不返回距离。"""
    from math import radians, sin, cos, asin, sqrt
    dlat = radians(lat2 - lat1)
    dlng = radians(lng2 - lng1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlng / 2) ** 2
    return int(6371000 * 2 * asin(sqrt(a)))


def _vet_clean(p: dict) -> Optional[dict]:
    """把高德返回的一条 POI 裁成前端要用的样子，顺手套掉明显不是医院的。"""
    name = (p.get("name") or "").strip()
    if not name:
        return None
    typ = (p.get("type") or "")
    # 搜「宠物医院」经常把「宠物美容」「宠物殡葬」也带出来，名字里没有医院/诊所的一律不要
    if not any(w in name for w in ("医院", "诊所", "兽医", "动物医疗")) and "动物" not in typ:
        return None
    loc = (p.get("location") or "").split(",")
    if len(loc) != 2:
        return None
    try:
        lng, lat = float(loc[0]), float(loc[1])
    except ValueError:
        return None
    biz = p.get("biz_ext") or {}
    open_txt = ""
    if isinstance(biz, dict):
        open_txt = (biz.get("opentime2") or biz.get("opentime") or "").strip()
    tel = (p.get("tel") or "").strip()
    tel = tel.replace(";", " / ").replace(",", " / ")
    return {
        "id": p.get("id") or "",
        "name": name[:60],
        "addr": (p.get("address") or "").strip()[:120],
        "area": (p.get("adname") or "").strip()[:30],
        "tel": tel[:60],
        "dist": int(float(p.get("distance") or 0)),
        "lat": lat,
        "lng": lng,
        "open": open_txt[:40],
        "exotic": any(w in (name + typ).lower() for w in _VET_EXOTIC),
    }


@app.get("/api/vet/ready")
async def vet_ready(request: Request):
    """前台进页面前先问一句：地图服务配好了没。

    没配就别急着弹定位权限——先把话说明白，用户不用为一次注定没有结果的
    定位授权。
    """
    require_user(request)
    cfg = load_config()
    return {"ready": bool((cfg.get("amap_key") or "").strip())}


@app.get("/api/vet/regions")
async def vet_regions(request: Request):
    """全国省 / 市 / 区县，带中心坐标（含港澳台）。

    只给「换个地方找」用：人在外地、想查老家的医院，或者本地搜出来是空的，
    就按区县中心去查。前端会缓存到 localStorage，每次只请求一遍。
    """
    require_user(request)
    path = os.path.join(DATA_DIR, "regions.json")
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        return {"v": "", "areas": []}
    if _REGIONS["data"] is None or _REGIONS["mtime"] != mtime:
        with open(path, "rb") as f:
            _REGIONS["data"] = json.loads(f.read().decode("utf-8"))
        _REGIONS["mtime"] = mtime
    return _REGIONS["data"]


@app.get("/api/vet/area")
async def vet_area(request: Request, adcode: str = "", lat: float = 0, lng: float = 0):
    """按行政区查该区县的所有动物医院。

    和 around 的区别：around 是画一个圆，边缘会切掉半个区县；这里用
    city + citylimit 让高德只回这个 adcode 里的 POI，一个不漏。
    lat/lng 传用户当前位置，用来算距离；不传就按区县中心算。
    """
    acc = require_user(request)
    cfg = load_config()
    amap_key = (cfg.get("amap_key") or "").strip()
    if not amap_key:
        return {"ok": False, "need_key": True, "items": []}
    if not adcode.strip().isdigit() or len(adcode.strip()) != 6:
        return JSONResponse({"ok": False, "error": "地区编码不对"}, status_code=400)
    if not _vet_throttle(acc.get("uid", "")):
        return JSONResponse({"ok": False, "error": "查得太频繁了，歇一分钟再试"}, status_code=429)

    adcode = adcode.strip()
    ckey = ("area", adcode, round(lat or 0, 2), round(lng or 0, 2))
    cached = _vet_cache_get(ckey)
    if cached is not None:
        return {"ok": True, "items": cached, "cached": True}

    params = {
        "key": amap_key,
        "keywords": _VET_KW,
        "city": adcode,
        "citylimit": "true",
        "offset": 25,
        "page": 1,
        "extensions": "all",
    }
    try:
        async with httpx.AsyncClient(timeout=6.0) as client:
            r = await client.get("https://restapi.amap.com/v3/place/text", params=params)
        data = r.json()
    except Exception as e:  # noqa: BLE001
        print(f"[vet-area] 高德请求失败: {e}", flush=True)
        return JSONResponse({"ok": False, "error": "地图服务暂时连不上，稍后再试"}, status_code=502)

    if str(data.get("status")) != "1":
        info = str(data.get("info") or "未知错误")
        hint = {
            "10001": "高德 Key 无效，请检查后台配置",
            "10003": "高德 Key 今日调用量已用完",
            "10009": "高德 Key 今日调用量已用完",
            "10021": "高德 Key 的平台类型不对，要选「Web服务」",
        }.get(str(data.get("infocode")), "")
        print(f"[vet-area] 高德返回错误 {data.get('infocode')} {info}", flush=True)
        return JSONResponse({"ok": False, "error": hint or f"地图服务返回：{info}"}, status_code=502)

    items = []
    for poi in (data.get("pois") or []):
        it = _vet_clean(poi)
        if not it:
            continue
        if lat and lng:
            it["dist"] = _meters_between(lat, lng, it["lat"], it["lng"])
        items.append(it)
    items.sort(key=lambda x: x["dist"])
    _vet_cache_put(ckey, items)
    return {"ok": True, "items": items, "adcode": adcode}


@app.get("/api/vet/nearby")
async def vet_nearby(request: Request, lat: float = 0, lng: float = 0, radius: int = 5000):
    """按坐标找附近的动物医院。

    need_key=True 表示后台还没填高德 Key，前端据此切成「跳地图」的兜底形态，
    不报错、不白屏。
    """
    acc = require_user(request)
    cfg = load_config()
    amap_key = (cfg.get("amap_key") or "").strip()
    if amap_key and not _vet_throttle(acc.get("uid", "")):
        return JSONResponse({"ok": False, "error": "查得太频繁了，歇一分钟再试"}, status_code=429)
    if not amap_key:
        return {"ok": False, "need_key": True, "items": []}
    # 中国大陆大致范围，超出一律当参数错误，别拿去烧配额
    if not (3.0 < lat < 54.0 and 73.0 < lng < 136.0):
        return JSONResponse({"ok": False, "error": "定位坐标超出范围，请重新定位"}, status_code=400)

    radius = max(1000, min(20000, int(radius or 5000)))
    # 网格化缓存：同一小区的人落在同一个 key 上，一起复用
    ckey = (round(lat, 3), round(lng, 3), radius)
    cached = _vet_cache_get(ckey)
    if cached is not None:
        return {"ok": True, "items": cached, "cached": True, "radius": radius}

    params = {
        "key": amap_key,
        "location": f"{lng:.6f},{lat:.6f}",
        "keywords": _VET_KW,
        "radius": radius,
        "offset": 25,
        "page": 1,
        "extensions": "all",
        "sortrule": "distance",
    }
    try:
        async with httpx.AsyncClient(timeout=6.0) as client:
            r = await client.get("https://restapi.amap.com/v3/place/around", params=params)
        data = r.json()
    except Exception as e:  # noqa: BLE001
        print(f"[vet] 高德请求失败: {e}", flush=True)
        return JSONResponse({"ok": False, "error": "地图服务暂时连不上，稍后再试"}, status_code=502)

    if str(data.get("status")) != "1":
        info = str(data.get("info") or "未知错误")
        # 10009 = 当日配额用尽；10001 = Key 不对；10003 = 日访问量超限
        hint = {
            "10001": "高德 Key 无效，请检查后台配置",
            "10003": "高德 Key 今日调用量已用完",
            "10009": "高德 Key 今日调用量已用完",
            "10021": "高德 Key 的平台类型不对，要选「Web服务」",
        }.get(str(data.get("infocode")), "")
        print(f"[vet] 高德返回错误 {data.get('infocode')} {info}", flush=True)
        return JSONResponse({"ok": False, "error": hint or f"地图服务返回：{info}"}, status_code=502)

    items = []
    for p in data.get("pois") or []:
        if isinstance(p, dict):
            one = _vet_clean(p)
            if one:
                items.append(one)
    items.sort(key=lambda x: x["dist"])
    items = items[:30]

    _vet_cache_put(ckey, items)
    return {"ok": True, "items": items, "cached": False, "radius": radius}


@app.post("/api/auth/password")
async def auth_password(request: Request):
    acc = require_user(request)
    try:
        body = await request.json()
    except Exception:
        body = {}
    try:
        auth.change_password(acc, body.get("old_password", ""), body.get("new_password", ""))
    except auth.AuthError as e:
        return JSONResponse({"error": e.message}, status_code=e.status)
    return {"ok": True}


@app.post("/api/auth/reset")
async def auth_reset(request: Request):
    """忘记密码：手机号 + 新密码直接重设，成功即登录，不用先进设置页。"""
    try:
        body = await request.json()
    except Exception:
        body = {}
    phone = (body.get("phone") or "").strip()
    pwd = body.get("password") or ""
    ip = auth.client_ip(request)
    try:
        auth.reset_password(phone, pwd, ip=ip)
        acc = auth.login(phone, pwd, (body.get("device_id") or "")[:64], ip=ip)
    except auth.AuthError as e:
        return JSONResponse({"error": e.message}, status_code=e.status)

    payload = _user_payload(acc)
    try:
        payload["hint_loc"] = geo.lookup(acc.get("last_ip") or "")
    except Exception:
        payload["hint_loc"] = ""
    return {"ok": True, "user": payload,
            "token": auth.make_token(acc["uid"], acc.get("phone", "")),
            "day_end": auth.day_end()}


@app.post("/api/auth/profile")
async def auth_profile(request: Request):
    """修改个人资料：昵称 / 简介 / 性别 / 所在地。

    只覆盖请求里出现的字段，没传的保持原样，前端可以按需单改一项。
    """
    acc = require_user(request)
    try:
        body = await request.json()
    except Exception:
        body = {}
    accounts = auth.load_accounts()
    cur = accounts.get(acc["uid"])
    if not cur:
        return JSONResponse({"error": "账号不存在"}, status_code=404)

    if "nickname" in body:
        nickname = (body.get("nickname") or "").strip()[:16]
        if not nickname:
            return JSONResponse({"error": "昵称不能为空"}, status_code=400)
        cur["nickname"] = nickname
    if "bio" in body:
        cur["bio"] = (body.get("bio") or "").strip()[:60]
    if "gender" in body:
        g = (body.get("gender") or "").strip()
        if g not in ("", "male", "female", "secret"):
            return JSONResponse({"error": "性别取值不合法"}, status_code=400)
        cur["gender"] = g
    if "location" in body:
        cur["location"] = (body.get("location") or "").strip()[:24]
    if "avatar_color" in body:
        c = (body.get("avatar_color") or "").strip()
        if c in ("", "lamp", "moss", "clay", "slate", "plum"):
            cur["avatar_color"] = c
    if body.get("avatar_clear"):
        # 选了首字头像＝不再用照片，同时把旧文件删掉，别在磁盘上留垃圾
        cur["avatar"] = ""
        old = _avatar_file(cur.get("uid", ""))
        try:
            if old and old.exists():
                old.unlink()
        except Exception:
            pass

    cur["profile_ts"] = int(time.time())
    with auth._lock:
        auth.save_accounts(accounts)
    return {"ok": True, "user": _user_payload(cur)}


AVATAR_DIR = DATA_DIR / "avatars"
AVATAR_RE = re.compile(r"^u[0-9a-f]{16}$")


def _avatar_file(uid: str):
    """uid 只可能是我们自己生成的十六进制串，仍然白名单校验一次，杜绝路径穿越。"""
    return AVATAR_DIR / f"{uid}.jpg" if AVATAR_RE.match(uid or "") else None


@app.post("/api/auth/avatar")
async def auth_avatar(request: Request):
    """上传头像。前端已裁成 1:1 并压到 320px，这里再兜一层：解码、摆正、限边、重编码。"""
    acc = require_user(request)
    try:
        body = await request.json()
    except Exception:
        body = {}
    raw = (body.get("image") or "").strip()
    if not raw:
        return JSONResponse({"error": "没有收到图片"}, status_code=400)
    if "," in raw and raw.startswith("data:"):
        raw = raw.split(",", 1)[1]
    if len(raw) > 4_000_000:
        return JSONResponse({"error": "图片太大，请换一张"}, status_code=413)
    try:
        import io

        from PIL import Image, ImageOps
        data = base64.b64decode(raw)
        im = Image.open(io.BytesIO(data))
        im = ImageOps.exif_transpose(im)
        im = im.convert("RGB")
        w, h = im.size
        s = min(w, h)
        im = im.crop(((w - s) // 2, (h - s) // 2, (w - s) // 2 + s, (h - s) // 2 + s))
        im = im.resize((320, 320), Image.LANCZOS)
        path = _avatar_file(acc["uid"])
        if not path:
            return JSONResponse({"error": "账号标识异常"}, status_code=400)
        AVATAR_DIR.mkdir(parents=True, exist_ok=True)
        im.save(path, "JPEG", quality=84, optimize=True, progressive=True)
    except Exception:
        return JSONResponse({"error": "图片无法识别，请换一张试试"}, status_code=400)

    ts = int(time.time())
    accounts = auth.load_accounts()
    cur = accounts.get(acc["uid"])
    if cur:
        cur["avatar"] = f"/avatar/{acc['uid']}?v={ts}"
        cur["avatar_ts"] = ts
        with auth._lock:
            auth.save_accounts(accounts)
    return {"ok": True, "avatar": f"/avatar/{acc['uid']}?v={ts}", "user": _user_payload(cur or acc)}


@app.get("/avatar/{uid}")
async def avatar_file(uid: str):
    path = _avatar_file(uid)
    if not path or not path.exists():
        raise HTTPException(status_code=404)
    return FileResponse(path, media_type="image/jpeg",
                        headers={"Cache-Control": "public, max-age=604800"})


# ============ 客服：意见反馈 ============
@app.post("/api/feedback")
async def feedback_submit(request: Request):
    """提交一条反馈，进入后台「用户反馈」队列。"""
    acc = require_user(request)
    try:
        body = await request.json()
    except Exception:
        body = {}
    content = (body.get("content") or "").strip()
    if len(content) < 4:
        return JSONResponse({"error": "请把问题描述得再具体一些（至少 4 个字）"}, status_code=400)
    if len(content) > 800:
        content = content[:800]
    ftype = (body.get("type") or "other").strip()
    if ftype not in FEEDBACK_TYPES:
        ftype = "other"

    uid = acc.get("uid", "")
    now = int(time.time())
    today = cn_date(now)
    with _fb_lock:
        items = load_feedback()
        # 简单的防刷：同一账号每天最多 6 条
        mine_today = sum(1 for it in items if it.get("uid") == uid and it.get("date") == today)
        if mine_today >= 6:
            return JSONResponse({"error": "今天提交的次数有点多，明天再来或直接在问答里问我们"}, status_code=429)
        item = {
            "id": "f" + secrets.token_hex(6),
            "uid": uid,
            "phone": acc.get("phone", ""),
            "nickname": acc.get("nickname", ""),
            "type": ftype,
            "type_name": FEEDBACK_TYPES[ftype],
            "content": content,
            "contact": (body.get("contact") or "").strip()[:64],
            "date": today,
            "ts": now,
            "status": "pending",
            "handled_ts": 0,
            "reply": "",       # 客服回复内容（后台填写）
            "reply_ts": 0,     # 回复时间
            "read_ts": 0,      # 用户查看回复的时间，用于「有新回复」红点
        }
        items.append(item)
        if len(items) > 5000:
            items = items[-5000:]
        save_feedback(items)
    return {"ok": True, "id": item["id"]}


@app.get("/api/admin/feedback")
async def admin_feedback(password: str = "", status: str = "", page: int = 1, size: int = 20):
    if password != get_admin_password():
        return JSONResponse({"error": "密码错误"}, status_code=401)
    items = load_feedback()
    total = len(items)
    pending = sum(1 for it in items if it.get("status") == "pending")
    today = cn_date()
    today_new = sum(1 for it in items if it.get("date") == today)
    if status == "pending":
        items = [it for it in items if it.get("status") == "pending"]
    elif status in ("done", "replied"):
        items = [it for it in items if it.get("status") in ("done", "replied")]
    items = sorted(items, key=lambda x: x.get("ts", 0), reverse=True)
    size = max(1, min(100, size))
    page = max(1, page)
    start = (page - 1) * size
    rows = []
    for it in items[start:start + size]:
        rows.append({
            "id": it.get("id", ""),
            "type_name": it.get("type_name") or FEEDBACK_TYPES.get(it.get("type", ""), "其他问题"),
            "content": it.get("content", ""),
            "contact": it.get("contact", ""),
            "phone": (it.get("phone") or "")[:3] + "****" + (it.get("phone") or "")[-4:]
            if len(it.get("phone") or "") == 11 else (it.get("phone") or ""),
            "nickname": it.get("nickname", ""),
            "date": it.get("date", ""),
            "status": it.get("status", "pending"),
            "reply": it.get("reply", ""),
            "reply_ts": it.get("reply_ts", 0),
        })
    return {
        "total": total, "pending": pending, "today": today_new,
        "filtered": len(items), "page": page, "size": size,
        "items": rows,
    }


@app.post("/api/admin/feedback/handle")
async def admin_feedback_handle(request: Request):
    body = await request.json()
    if body.get("password", "") != get_admin_password():
        return JSONResponse({"error": "密码错误"}, status_code=401)
    fid = (body.get("id") or "").strip()
    action = "done" if body.get("action") == "done" else "pending"
    with _fb_lock:
        items = load_feedback()
        hit = False
        for it in items:
            if it.get("id") == fid:
                it["status"] = action
                it["handled_ts"] = int(time.time()) if action == "done" else 0
                hit = True
                break
        if not hit:
            return JSONResponse({"error": "反馈不存在"}, status_code=404)
        save_feedback(items)
    return {"ok": True, "status": action}


@app.post("/api/admin/feedback/reply")
async def admin_feedback_reply(request: Request):
    """后台回复用户反馈。回复内容会出现在前台「我的 → 联系客服 → 我的反馈」里。"""
    body = await request.json()
    if body.get("password", "") != get_admin_password():
        return JSONResponse({"error": "密码错误"}, status_code=401)
    fid = (body.get("id") or "").strip()
    reply = (body.get("reply") or "").strip()
    if not reply:
        return JSONResponse({"error": "回复内容不能为空"}, status_code=400)
    if len(reply) > 1000:
        reply = reply[:1000]
    now = int(time.time())
    with _fb_lock:
        items = load_feedback()
        hit = None
        for it in items:
            if it.get("id") == fid:
                it["reply"] = reply
                it["reply_ts"] = now
                it["status"] = "replied"
                it["handled_ts"] = now
                it["read_ts"] = 0  # 重置已读，让用户端重新出现「新回复」提示
                hit = it
                break
        if not hit:
            return JSONResponse({"error": "反馈不存在"}, status_code=404)
        save_feedback(items)
    return {"ok": True, "reply_ts": now}


@app.get("/api/feedback/mine")
async def feedback_mine(request: Request):
    """当前用户的反馈列表与客服回复（前台「我的反馈」）。"""
    acc = require_user(request)
    uid = acc.get("uid", "")
    items = [it for it in load_feedback() if it.get("uid") == uid]
    items.sort(key=lambda x: x.get("ts", 0), reverse=True)
    unread = sum(1 for it in items
                 if it.get("reply") and it.get("reply_ts", 0) > it.get("read_ts", 0))
    rows = []
    for it in items[:20]:
        rts = it.get("reply_ts", 0)
        rows.append({
            "id": it.get("id", ""),
            "type_name": it.get("type_name") or FEEDBACK_TYPES.get(it.get("type", ""), "其他问题"),
            "content": it.get("content", ""),
            "date": it.get("date", ""),
            "status": it.get("status", "pending"),
            "reply": it.get("reply", ""),
            "reply_time": time.strftime("%m-%d %H:%M", time.gmtime(rts + 8 * 3600)) if rts else "",
            "is_new": bool(it.get("reply")) and rts > it.get("read_ts", 0),
        })
    return {"items": rows, "unread": unread, "total": len(items)}


@app.post("/api/feedback/read")
async def feedback_read(request: Request):
    """用户打开「我的反馈」后，把已回复的记录标记为已读。"""
    acc = require_user(request)
    uid = acc.get("uid", "")
    now = int(time.time())
    with _fb_lock:
        items = load_feedback()
        changed = False
        for it in items:
            if it.get("uid") != uid:
                continue
            if it.get("reply") and it.get("reply_ts", 0) > it.get("read_ts", 0):
                it["read_ts"] = now
                changed = True
        if changed:
            save_feedback(items)
    return {"ok": True}


# ============ 养护接口：宠物档案 / 温湿度记录 ============
@app.get("/api/pets")
async def list_pets(request: Request):
    acc = require_user(request)
    uid = acc.get("uid", "")
    items = [it for it in load_pets() if it.get("uid") == uid]
    items.sort(key=lambda x: x.get("created", 0))
    return {"ok": True, "items": items}


@app.post("/api/pets")
async def upsert_pet(request: Request):
    """新增或修改宠物档案。带 id 为修改，不带为新增。"""
    acc = require_user(request)
    uid = acc.get("uid", "")
    body = await request.json()
    name = (body.get("name") or "").strip()[:20]
    species = (body.get("species") or "").strip()[:30]
    if not name:
        return JSONResponse({"error": "请填写宠物名字"}, status_code=400)
    if not species:
        return JSONResponse({"error": "请选择或填写物种"}, status_code=400)
    payload = {
        "name": name,
        "species": species,
        "sex": (body.get("sex") or "").strip()[:6],
        "birthday": (body.get("birthday") or "").strip()[:10],
        "adopted": (body.get("adopted") or "").strip()[:10],
        "weight": (body.get("weight") or "").strip()[:12],
        "note": (body.get("note") or "").strip()[:300],
    }
    # 头像：不传就不动；传空串表示删掉；传 data URI 就重新压一张
    if "photo" in body:
        photo = body.get("photo")
        if not photo:
            payload["photo"] = ""
        elif isinstance(photo, str):
            try:
                _mime, raw = diagnose.split_data_uri(photo)
                small = _pet_photo(raw)
                if small:
                    payload["photo"] = small
            except diagnose.DiagnoseError:
                payload["photo"] = ""
    now = int(time.time())
    weight_val = 0.0
    try:
        weight_val = round(float(payload.get("weight") or 0), 1)
    except (TypeError, ValueError):
        weight_val = 0.0
    with _care_lock:
        items = load_pets()
        pid = (body.get("id") or "").strip()
        item = None
        if pid:
            for it in items:
                if it.get("id") == pid and it.get("uid") == uid:
                    it.update(payload)
                    it["updated"] = now
                    item = it
                    break
            if not item:
                return JSONResponse({"error": "档案不存在"}, status_code=404)
        else:
            item = dict(payload, id="p" + secrets.token_hex(8), uid=uid, created=now, updated=now)
            items.append(item)
        save_pets(items)
    # 体重有填就顺带落一条体重日志，档案改几次就攒出折线，不用另外记
    if weight_val > 0:
        _append_weight_log(uid, item["id"], weight_val, now)
    return {"ok": True, "item": item}


def _append_weight_log(uid: str, pet_id: str, value: float, ts: int) -> None:
    """写一条体重日志。同一天重复保存只保留最新值，避免曲线出现锯齿。"""
    with _care_lock:
        logs = load_petlogs()
        day = ts - ts % 86400
        for it in logs:
            if (it.get("uid") == uid and it.get("pet_id") == pet_id
                    and it.get("type") == "weight" and int(it.get("ts") or 0) >= day):
                it["ts"] = ts
                it["value"] = value
                save_petlogs(logs)
                return
        logs.append({
            "id": "l" + secrets.token_hex(8),
            "uid": uid,
            "pet_id": pet_id,
            "type": "weight",
            "ts": ts,
            "value": value,
            "note": "档案更新",
        })
        if len(logs) > 50000:
            logs = logs[-50000:]
        save_petlogs(logs)


@app.post("/api/pets/delete")
async def delete_pet(request: Request):
    """删除档案，连带删掉这只宠物的温湿度记录和饲养日志，避免留下孤儿数据。"""
    acc = require_user(request)
    uid = acc.get("uid", "")
    body = await request.json()
    pid = (body.get("id") or "").strip()
    with _care_lock:
        items = load_pets()
        keep = [it for it in items if not (it.get("id") == pid and it.get("uid") == uid)]
        if len(keep) == len(items):
            return JSONResponse({"error": "档案不存在"}, status_code=404)
        save_pets(keep)
        logs = [x for x in load_carelog() if not (x.get("pet_id") == pid and x.get("uid") == uid)]
        save_carelog(logs)
        plogs = [x for x in load_petlogs() if not (x.get("pet_id") == pid and x.get("uid") == uid)]
        save_petlogs(plogs)
    return {"ok": True}


@app.get("/api/pets/timeline")
async def pet_timeline(request: Request, pet_id: str = "", limit: int = 120):
    """一只宠物的一生：喂食、蜕皮、称重、温湿度、诊断，按时间倒序串成一条线。

    前端只负责渲染，聚合在服务端做，省得把四五份数据全拉到手机上再排。
    温湿度一天记多次时只留当天最后一次，避免把时间轴刷屏。
    """
    acc = require_user(request)
    uid = acc.get("uid", "")
    pet_id = (pet_id or "").strip()
    pets = [x for x in load_pets() if x.get("uid") == uid and x.get("id") == pet_id]
    if not pets:
        return JSONResponse({"error": "档案不存在"}, status_code=404)

    TYPE_TXT = {"feed": "喂食", "shed": "蜕皮", "poop": "排便",
                "med": "用药", "weight": "称重", "watch": "观察"}
    ev = []

    for it in load_petlogs():
        if it.get("uid") != uid or it.get("pet_id") != pet_id:
            continue
        typ = it.get("type") or ""
        if typ == "watch":
            continue
        title = TYPE_TXT.get(typ, typ)
        if typ == "weight" and it.get("value"):
            title = "称重 %g g" % float(it["value"])
        ev.append({"kind": typ, "ts": int(it.get("ts") or 0), "title": title,
                   "sub": (it.get("note") or "").strip()[:60], "thumb": ""})

    # 温湿度按天合并：一天只留最后一条
    per_day = {}
    for it in load_carelog():
        if it.get("uid") != uid or it.get("pet_id") != pet_id:
            continue
        ts = int(it.get("ts") or 0)
        day = (ts + 8 * 3600) // 86400
        prev = per_day.get(day)
        if prev is None or ts > prev.get("ts", 0):
            per_day[day] = it
    for it in per_day.values():
        ts = int(it.get("ts") or 0)
        t, h = it.get("temp"), it.get("hum")
        txt = ""
        if t is not None:
            txt = "%.1f℃" % float(t)
        if h is not None:
            txt = (txt + " / %d%%" % round(float(h))) if txt else "%d%%" % round(float(h))
        ev.append({"kind": "env", "ts": ts, "title": "箱内 " + txt,
                   "sub": (it.get("note") or "").strip()[:60], "thumb": ""})

    for it in load_diagnoses():
        if it.get("uid") != uid or it.get("pet_id") != pet_id:
            continue
        lv = int(it.get("level") or 0)
        ev.append({"kind": "diag", "ts": int(it.get("ts") or 0),
                   "title": (it.get("title") or "拍照诊断")[:40],
                   "sub": "AI 初筛 · " + ("急诊" if lv >= 2 else ("就医" if lv == 1 else "观察")),
                   "thumb": it.get("thumb") or "", "level": lv, "id": it.get("id")})

    ev.sort(key=lambda x: x["ts"], reverse=True)
    total = len(ev)
    limit = max(10, min(300, limit))
    return {"ok": True, "items": ev[:limit], "total": total,
            "pet": {k: pets[0].get(k) for k in ("id", "name", "species", "photo", "adopted", "created")}}


@app.get("/api/care/logs")
async def care_logs(request: Request, pet_id: str = "", limit: int = 120):
    acc = require_user(request)
    uid = acc.get("uid", "")
    items = [it for it in load_carelog() if it.get("uid") == uid]
    if pet_id:
        items = [it for it in items if it.get("pet_id") == pet_id]
    items.sort(key=lambda x: x.get("ts", 0), reverse=True)
    limit = max(1, min(300, limit))
    return {"ok": True, "items": items[:limit]}


@app.post("/api/care/logs")
async def add_care_log(request: Request):
    acc = require_user(request)
    uid = acc.get("uid", "")
    body = await request.json()
    try:
        temp = round(float(body.get("temp")), 1)
        hum = round(float(body.get("hum")), 1)
    except (TypeError, ValueError):
        return JSONResponse({"error": "请填写温度与湿度"}, status_code=400)
    if not -20 <= temp <= 60:
        return JSONResponse({"error": "温度请填 -20～60℃"}, status_code=400)
    if not 0 <= hum <= 100:
        return JSONResponse({"error": "湿度请填 0～100%"}, status_code=400)
    now = int(time.time())
    ts = int(body.get("ts") or now)
    if ts > now + 86400 or ts < now - 86400 * 365:
        ts = now  # 时间明显不合理就按当前时间记
    item = {
        "id": "c" + secrets.token_hex(8),
        "uid": uid,
        "pet_id": (body.get("pet_id") or "").strip(),
        "temp": temp,
        "hum": hum,
        "note": (body.get("note") or "").strip()[:100],
        "ts": ts,
    }
    with _care_lock:
        items = load_carelog()
        items.append(item)
        if len(items) > 20000:
            items = items[-20000:]
        save_carelog(items)
    return {"ok": True, "item": item}


@app.post("/api/care/logs/delete")
async def delete_care_log(request: Request):
    acc = require_user(request)
    uid = acc.get("uid", "")
    body = await request.json()
    lid = (body.get("id") or "").strip()
    with _care_lock:
        items = load_carelog()
        keep = [x for x in items if not (x.get("id") == lid and x.get("uid") == uid)]
        if len(keep) == len(items):
            return JSONResponse({"error": "记录不存在"}, status_code=404)
        save_carelog(keep)
    return {"ok": True}


@app.get("/api/qr")
async def make_qr(request: Request, text: str = "", size: int = 320):
    """生成二维码 PNG。分享海报把它贴在角落，扫一下就进站。"""
    require_user(request)
    text = (text or "").strip()[:512]
    if not text:
        text = str(request.base_url).rstrip("/") + "/"
    size = max(120, min(800, size))
    try:
        import qrcode
        from io import BytesIO

        qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_Q,
                           box_size=8, border=2)
        qr.add_data(text)
        qr.make(fit=True)
        box = max(2, size // (qr.modules_count + 4))
        qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_Q,
                           box_size=box, border=2)
        qr.add_data(text)
        qr.make(fit=True)
        img = qr.make_image(fill_color="#152E23", back_color="#FFFFFF")
        buf = BytesIO()
        img.save(buf, format="PNG")
        return Response(buf.getvalue(), media_type="image/png",
                        headers={"Cache-Control": "public, max-age=86400"})
    except Exception as exc:  # 二维码库缺失或编码失败都不该让海报整块崩掉
        print("[qr] 生成失败", exc)
        return JSONResponse({"error": "二维码生成失败"}, status_code=500)


@app.get("/api/petlogs")
async def get_petlogs(request: Request, pet_id: str = "", limit: int = 200):
    """饲养日志：喂食 / 蜕皮 / 排便 / 用药 / 体重 / 观察追踪。

    同时返回每只宠物每类日志的最后一次时间，前端据此算「距上次喂食几天」，
    省得把全量记录拉到手机上再算。体重另给一条按时间正序的折线序列。
    """
    acc = require_user(request)
    uid = acc.get("uid", "")
    items = [it for it in load_petlogs() if it.get("uid") == uid]
    if pet_id:
        items = [it for it in items if it.get("pet_id") == pet_id]
    items.sort(key=lambda x: x.get("ts", 0), reverse=True)
    limit = max(1, min(500, limit))
    summary = {}
    weights = {}
    for it in items:
        pid = it.get("pet_id") or ""
        typ = it.get("type") or ""
        if not pid or not typ:
            continue
        row = summary.setdefault(pid, {})
        ts = int(it.get("ts") or 0)
        if ts > int(row.get(typ) or 0):
            row[typ] = ts
    # 体重曲线：正序、最多 60 个点，同一秒的多条只留最后一条
    for it in reversed(items):
        if it.get("type") != "weight":
            continue
        pid = it.get("pet_id") or ""
        val = it.get("value")
        try:
            val = round(float(val), 1)
        except (TypeError, ValueError):
            continue
        if not pid or val <= 0:
            continue
        arr = weights.setdefault(pid, [])
        if arr and arr[-1]["ts"] == int(it.get("ts") or 0):
            arr[-1] = {"ts": int(it.get("ts") or 0), "v": val}
        else:
            arr.append({"ts": int(it.get("ts") or 0), "v": val})
    for pid in weights:
        weights[pid] = weights[pid][-60:]
    return {"ok": True, "items": items[:limit], "summary": summary,
            "weights": weights, "total": len(items)}


@app.post("/api/petlogs")
async def add_petlog(request: Request):
    acc = require_user(request)
    uid = acc.get("uid", "")
    body = await request.json()
    typ = (body.get("type") or "").strip()
    if typ not in ("feed", "shed", "poop", "med", "weight", "watch"):
        return JSONResponse({"error": "未知的记录类型"}, status_code=400)
    pet_id = (body.get("pet_id") or "").strip()
    # 只能给自己名下的宠物记
    pets = [x for x in load_pets() if x.get("uid") == uid]
    if pet_id and not any(x.get("id") == pet_id for x in pets):
        return JSONResponse({"error": "宠物档案不存在"}, status_code=404)
    now = int(time.time())
    ts = int(body.get("ts") or now)
    if ts > now + 3600 or ts < now - 86400 * 730:
        ts = now
    item = {
        "id": "l" + secrets.token_hex(8),
        "uid": uid,
        "pet_id": pet_id,
        "type": typ,
        "ts": ts,
        "note": (body.get("note") or "").strip()[:100],
    }
    if typ == "weight":
        try:
            val = round(float(body.get("value") or 0), 1)
        except (TypeError, ValueError):
            val = 0
        if not (0 < val <= 100000):
            return JSONResponse({"error": "请填写有效体重（克）"}, status_code=400)
        item["value"] = val
        # 同步到档案上的当前体重，档案卡和曲线保持一致
        with _care_lock:
            all_pets = load_pets()
            for x in all_pets:
                if x.get("id") == pet_id and x.get("uid") == uid:
                    x["weight"] = ("%g" % val)
                    x["updated"] = now
                    save_pets(all_pets)
                    break
    if typ == "watch":
        # 观察追踪：默认 48 小时后到期
        hours = body.get("hours")
        try:
            hours = float(hours or 48)
        except (TypeError, ValueError):
            hours = 48
        hours = max(1, min(168, hours))
        item["until"] = ts + int(hours * 3600)
        item["level"] = int(body.get("level") or 0)
        item["symptoms"] = (body.get("symptoms") or "").strip()[:120]
    with _care_lock:
        items = load_petlogs()
        items.append(item)
        if len(items) > 50000:
            items = items[-50000:]
        save_petlogs(items)
    return {"ok": True, "item": item}


@app.post("/api/petlogs/delete")
async def delete_petlog(request: Request):
    acc = require_user(request)
    uid = acc.get("uid", "")
    body = await request.json()
    lid = (body.get("id") or "").strip()
    with _care_lock:
        items = load_petlogs()
        keep = [x for x in items if not (x.get("id") == lid and x.get("uid") == uid)]
        if len(keep) == len(items):
            return JSONResponse({"error": "记录不存在"}, status_code=404)
        save_petlogs(keep)
    return {"ok": True}


# ============ 拍照诊断 ============
_diag_hits: dict = {}
_diag_lock = threading.Lock()
DIAG_HOUR_LIMIT = 20       # 每人每小时诊断次数上限
DIAG_KEEP_PER_USER = 30    # 每人保留的历史条数


def _diag_rate_ok(uid: str) -> bool:
    now = int(time.time())
    with _diag_lock:
        if len(_diag_hits) > 800:  # 防止长期运行后内存无限增长
            for k in [k for k, v in _diag_hits.items() if not v or now - v[-1] > 7200]:
                _diag_hits.pop(k, None)
        arr = [t for t in _diag_hits.get(uid, []) if now - t < 3600]
        if len(arr) >= DIAG_HOUR_LIMIT:
            _diag_hits[uid] = arr
            return False
        arr.append(now)
        _diag_hits[uid] = arr
    return True


def _pet_photo(raw: bytes) -> str:
    """档案头像：居中裁成正方形，480px，够手机上看清，又不至于把 pets.json 撑大。"""
    try:
        import io

        from PIL import Image, ImageOps
        im = Image.open(io.BytesIO(raw))
        # 手机竖拍常把画面存成横向、靠 EXIF 的 Orientation 标记旋转；
        # 不先按 EXIF 摆正，居中裁切会把脸裁掉、头像还会躺着
        im = ImageOps.exif_transpose(im)
        im = im.convert("RGB")
        w, h = im.size
        s = min(w, h)
        left = (w - s) // 2
        top = (h - s) // 2
        im = im.crop((left, top, left + s, top + s))
        im = im.resize((480, 480), Image.LANCZOS)
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=72, optimize=True)
        return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()
    except Exception:
        return ""


def _diag_thumb(raw: bytes) -> str:
    """只留一张缩略图存档。原图不落盘：诊断只需要看一眼，没必要留存用户相册内容。"""
    try:
        import io

        from PIL import Image, ImageOps
        im = Image.open(io.BytesIO(raw))
        im = ImageOps.exif_transpose(im)
        im = im.convert("RGB")
        im.thumbnail((260, 260))
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=62)
        return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()
    except Exception:
        return ""


@app.post("/api/diagnose")
async def api_diagnose(request: Request):
    """拍照诊断：一张图 + 一句描述 → 结构化清单。"""
    acc = require_user(request)
    uid = acc.get("uid", "")
    body = await request.json()
    img = body.get("image") or ""

    cfg = load_config()
    api_key, base_url, model = resolve_vision(cfg)
    if not (api_key and base_url and model):
        return JSONResponse(
            {"error": "图片识别还没配置好，暂时看不了。可以直接问文字问题，或稍后再试。",
             "code": "not_configured"},
            status_code=503,
        )
    if not _diag_rate_ok(uid):
        return JSONResponse({"error": "今天看得有点多了，休息一会儿再试（每小时 20 次）"}, status_code=429)

    note = (body.get("note") or "").strip()[:200]
    pet_id = (body.get("pet_id") or "").strip()
    species = (body.get("species") or "").strip()[:20]
    pet_name, age = "", ""
    pets = [x for x in load_pets() if x.get("uid") == uid]
    if pet_id:
        pet = next((x for x in pets if x.get("id") == pet_id), None)
        if not pet:
            return JSONResponse({"error": "宠物档案不存在"}, status_code=404)
        pet_name = pet.get("name", "")
        species = species or pet.get("species", "")
        age = pet.get("birthday", "")

    try:
        mime, raw = diagnose.split_data_uri(img)
    except diagnose.DiagnoseError as e:
        return JSONResponse({"error": str(e)}, status_code=400)

    started = time.time()
    try:
        result = await diagnose.run_vision(
            "data:%s;base64,%s" % (mime, base64.b64encode(raw).decode()),
            species, note, pet_name, age, api_key, base_url, model,
        )
    except diagnose.ModelNoVision:
        return JSONResponse(
            {"error": "这个模型看不了图片，换一张或稍后再试。若一直这样，请通过客服反馈。",
             "code": "no_vision", "admin_hint": "在后台「识图模型」配置支持图片输入的模型，如 deepseek-flash"},
            status_code=501,
        )
    except diagnose.DiagnoseError as e:
        return JSONResponse({"error": str(e)}, status_code=400)

    item = {
        "id": "d" + secrets.token_hex(8),
        "uid": uid,
        "pet_id": pet_id,
        "pet_name": pet_name,
        "species": species or result.get("species_guess", ""),
        "note": note,
        "level": result["level"],
        "title": result["title"],
        "summary": result["summary"],
        "detail": {k: v for k, v in result.items() if k != "raw"},
        "thumb": _diag_thumb(raw),
        "model": model,
        "ms": int((time.time() - started) * 1000),
        "ts": int(time.time()),
    }
    with _care_lock:
        items = load_diagnoses()
        items.append(item)
        mine = [x for x in items if x.get("uid") == uid]
        if len(mine) > DIAG_KEEP_PER_USER:
            drop = {x["id"] for x in sorted(mine, key=lambda y: y.get("ts", 0))[:len(mine) - DIAG_KEEP_PER_USER]}
            items = [x for x in items if x.get("id") not in drop]
        items = sorted(items, key=lambda x: x.get("ts", 0))[-600:]
        save_diagnoses(items)
    return {"ok": True, "id": item["id"], "result": item["detail"]}


@app.get("/api/diagnoses")
async def list_diagnoses(request: Request, pet_id: str = "", limit: int = 20):
    acc = require_user(request)
    uid = acc.get("uid", "")
    items = [x for x in load_diagnoses() if x.get("uid") == uid]
    if pet_id:
        items = [x for x in items if x.get("pet_id") == pet_id]
    items.sort(key=lambda x: x.get("ts", 0), reverse=True)
    limit = max(1, min(30, limit))
    return {"ok": True, "items": items[:limit], "total": len(items)}


@app.post("/api/diagnoses/delete")
async def delete_diagnose(request: Request):
    acc = require_user(request)
    uid = acc.get("uid", "")
    body = await request.json()
    did = (body.get("id") or "").strip()
    with _care_lock:
        items = load_diagnoses()
        keep = [x for x in items if not (x.get("id") == did and x.get("uid") == uid)]
        if len(keep) == len(items):
            return JSONResponse({"error": "记录不存在"}, status_code=404)
        save_diagnoses(keep)
    return {"ok": True}


@app.post("/api/care/event")
async def add_care_event(request: Request):
    """记录养护模块的使用行为：分诊评估、急救查看、就医查看。

    只做聚合统计用，不存任何宠物隐私内容之外的字段。
    """
    acc = require_user(request)
    uid = acc.get("uid", "")
    body = await request.json()
    kind = (body.get("kind") or "").strip()
    if kind not in ("triage", "aid", "vet", "diag"):
        return JSONResponse({"error": "未知类型"}, status_code=400)
    level = body.get("level")
    try:
        level = int(level) if level not in (None, "") else 0
    except (TypeError, ValueError):
        level = 0
    if level not in (1, 2, 3):
        level = 0
    symptoms = body.get("symptoms") or []
    if not isinstance(symptoms, list):
        symptoms = []
    symptoms = [str(x)[:20] for x in symptoms][:12]
    item = {
        "id": "e" + secrets.token_hex(6),
        "uid": uid,
        "kind": kind,
        "level": level,
        "species": (body.get("species") or "").strip()[:12],
        "symptoms": symptoms,
        "item": (body.get("item") or "").strip()[:20],
        "ts": int(time.time()),
    }
    with _care_lock:
        items = load_care_events()
        items.append(item)
        if len(items) > 5000:
            items = items[-5000:]
        save_care_events(items)
    return {"ok": True}


@app.get("/api/admin/care")
async def admin_care(password: str = ""):
    """后台「养护数据」：档案、温湿度、分诊、急救、就医的实时汇总。"""
    if password != get_admin_password():
        return JSONResponse({"error": "密码错误"}, status_code=401)
    pets = load_pets()
    logs = load_carelog()
    events = load_care_events()
    accounts = auth.load_accounts()
    return care.build(pets, logs, events, accounts, petlogs=load_petlogs(),
                      diagnoses=load_diagnoses())


@app.get("/api/admin/backup")
async def admin_backup(password: str = ""):
    """后台「数据备份」：账号/配置/反馈的当前状态与最近快照。"""
    if password != get_admin_password():
        return JSONResponse({"error": "密码错误"}, status_code=401)
    st = backup.status()
    st["accounts"] = len(auth.load_accounts())
    return st


@app.post("/api/admin/backup/run")
async def admin_backup_run(request: Request):
    """立即生成一份快照（账号/配置/反馈）。"""
    body = await request.json()
    if body.get("password", "") != get_admin_password():
        return JSONResponse({"error": "密码错误"}, status_code=401)
    name = backup.snapshot(force=True)
    return {"ok": bool(name), "name": name}


_DEX_CREDITS = {}


def _dex_credit(k: str) -> str:
    """图片作者与授权，详情页要标注来源。"""
    if not _DEX_CREDITS:
        try:
            fp = STATIC_DIR / "dex" / "credits.json"
            if fp.exists():
                _DEX_CREDITS.update(json.loads(fp.read_text(encoding="utf-8")))
        except Exception:
            pass
    return _DEX_CREDITS.get(k, "")


def _dex_card(s: dict, full: bool = False) -> dict:
    out = {
        "k": s["k"], "name": s["name"], "group": s["group"],
        "latin": s["latin"], "en": s["en"], "level": s["level"],
        "size": s["size"], "temper": s["temper"],
        "temp": s["temp"], "hum": s["hum"],
        "img": "/static/dex/%s.jpg" % s["k"],
        # 列表卡片只用缩略图（320px / 约 15KB），点开详情才加载原图
        "thumb": "/static/dex/thumbs/%s.jpg" % s["k"],
        "keep": True,
    }
    if full:
        out.update({
            "alias": s.get("alias", []), "life": s["life"],
            "feed": s["feed"], "shed": s["shed"], "tip": s["tip"],
            "ill": s.get("ill", []), "no": s.get("no", ""),
            "legal": s.get("legal", "free"),
            "credit": _dex_credit(s["k"]),
        })
    return out


def _dex_forbidden_card(s: dict, full: bool = False) -> dict:
    """不可饲养条目：不给饲养参数，只给识别特征、法律依据和替代建议。"""
    out = {
        "k": s["k"], "name": s["name"], "group": s["group"],
        "latin": s["latin"], "en": s["en"],
        "img": "/static/dex/%s.jpg" % s["k"],
        "thumb": "/static/dex/thumbs/%s.jpg" % s["k"],
        "keep": False, "law": s.get("law", ""), "short": s.get("short", ""),
    }
    if full:
        alt = petdex.by_key(s.get("instead", ""))
        out.update({
            "alias": s.get("alias", []),
            "why": s.get("why", ""), "risk": s.get("risk", ""),
            "instead": ({"k": alt["k"], "name": alt["name"],
                         "img": "/static/dex/%s.jpg" % alt["k"],
                         "thumb": "/static/dex/thumbs/%s.jpg" % alt["k"]} if alt else None),
            "credit": _dex_credit(s["k"]),
        })
    return out


@app.get("/api/dex")
async def dex_list(request: Request, group: str = "", q: str = "", scope: str = "keep"):
    """异宠图鉴列表。

    scope=keep 可以养的（默认）；scope=no 不能养的。
    图鉴也要求登录：站内所有内容只对已注册用户开放，不做匿名可读。
    """
    require_user(request)
    counts = {"keep": len(petdex.SPECIES), "no": len(petdex.FORBIDDEN)}
    if scope in ("no", "forbidden", "ban"):
        items = petdex.search_forbidden(q, group)
        return {"ok": True, "scope": "no", "groups": petdex.FORBIDDEN_GROUPS,
                "items": [_dex_forbidden_card(s) for s in items],
                "total": len(items), "all": len(petdex.FORBIDDEN), "counts": counts}
    items = petdex.search(q, group)
    return {"ok": True, "scope": "keep", "groups": petdex.GROUPS,
            "items": [_dex_card(s) for s in items],
            "total": len(items), "all": len(petdex.SPECIES), "counts": counts}


@app.get("/api/dex/{k}")
async def dex_detail(k: str, request: Request):
    require_user(request)
    s = petdex.by_key(k)
    if s:
        return {"ok": True, "item": _dex_card(s, full=True),
                "groups": petdex.GROUPS}
    f = petdex.forbidden_by_key(k)
    if f:
        return {"ok": True, "item": _dex_forbidden_card(f, full=True),
                "groups": petdex.FORBIDDEN_GROUPS}
    return JSONResponse({"error": "没有这个物种"}, status_code=404)


@app.get("/api/compliance")
async def compliance(request: Request):
    require_user(request)
    # 只返回合规数据体；行业动态已拆为独立接口 /api/news，
    # 避免每次打开合规页都重复下发十几 KB 资讯（旧版本的历史包袱）。
    return load_compliance()


@app.get("/api/news")
async def news(request: Request):
    require_user(request)
    data = load_news()
    return {
        "sections": data.get("sections", []) or data.get("items", []),
        "updated": data.get("updated", ""),
        "version": data.get("version", ""),
    }


@app.get("/api/admin/status")
async def admin_status(password: str = ""):
    cfg = load_config()
    api_key, base_url, model = resolve_llm(cfg)
    masked = ""
    if api_key:
        masked = api_key[:4] + "****" + api_key[-4:] if len(api_key) > 8 else "****"
    kb = load_knowledge()
    items = kb.get("items", [])
    species_set = {it.get("species") for it in items if it.get("species") and it.get("species") != "通用"}
    data = {
        "configured": bool(api_key and base_url and model),
        "has_key": bool(api_key),
        "knowledge_count": len(items),
        "formulary_count": load_formulary().get("count", 0),
        # 知识库口径：按知识条目的 species 字段去重统计（后台管理看这个数）
        "species_count": len(species_set),
        # 图鉴口径：前台首页/我的/关于统一用这个数，避免两套数字对不上
        "dex_keep": len(petdex.SPECIES),
        "dex_no": len(petdex.FORBIDDEN),
        "dex_total": len(petdex.SPECIES) + len(petdex.FORBIDDEN),
        "knowledge_version": kb.get("version", ""),
    }
    # 只有管理员密码校验通过，才下发模型配置明细，避免前台接口泄露密钥片段
    if password and password == get_admin_password():
        data.update({
            "provider": cfg.get("provider", "deepseek"),
            "provider_name": PROVIDERS.get(cfg.get("provider", "deepseek"), {}).get("name", ""),
            "base_url": base_url,
            "model": model,
            "masked_key": masked,
            "vision_model": cfg.get("vision_model", ""),
            "vision_effective": resolve_vision(cfg)[2],
            "vision_base_url": cfg.get("vision_base_url", ""),
            "vision_has_key": bool(cfg.get("vision_api_key")),
            "default_password": get_admin_password() == DEFAULT_ADMIN_PASSWORD,
            "support": cfg.get("support", ""),
            "support_hours": cfg.get("support_hours", ""),
            "feedback_pending": sum(1 for it in load_feedback() if it.get("status") == "pending"),
            "wx_appid": cfg.get("wx_appid", ""),
            "wx_has_secret": bool(cfg.get("wx_appsecret") or os.environ.get("WX_APPSECRET", "")),
            "wx_redirect_domain": cfg.get("wx_redirect_domain", ""),
            "wx_verify_file": cfg.get("wx_verify_file", ""),
            "wx_verify_text": cfg.get("wx_verify_text", ""),
            "wx_ready": bool((cfg.get("wx_appid") or os.environ.get("WX_APPID"))
                             and (cfg.get("wx_appsecret") or os.environ.get("WX_APPSECRET"))),
            # 高德 Key 只回显前 4 位：够管理员确认填的是哪一个，又不怕被截图带走
            "amap_masked": (cfg.get("amap_key", "")[:4] + "****"
                            if len(cfg.get("amap_key", "")) > 8 else ""),
            "amap_ready": bool((cfg.get("amap_key") or "").strip()),
        })
    return data


@app.post("/api/admin/config")
async def admin_config(request: Request):
    body = await request.json()
    password = body.get("password", "")
    if password != get_admin_password():
        return JSONResponse({"error": "密码错误"}, status_code=401)

    cfg = load_config()
    if "provider" in body:
        cfg["provider"] = body.get("provider")
    if "base_url" in body:
        cfg["base_url"] = (body.get("base_url") or "").strip()
    if "model" in body:
        cfg["model"] = (body.get("model") or "").strip()
    if "api_key" in body:
        key = (body.get("api_key") or "").strip()
        if key:  # 留空表示不修改
            cfg["api_key"] = key
    # 识图模型（拍照诊断用），留空则按主模型厂商自动挑一个默认的视觉模型
    if "vision_model" in body:
        cfg["vision_model"] = (body.get("vision_model") or "").strip()[:60]
    if "vision_base_url" in body:
        cfg["vision_base_url"] = (body.get("vision_base_url") or "").strip()[:200]
    if "vision_api_key" in body:
        vk = (body.get("vision_api_key") or "").strip()
        if vk:
            cfg["vision_api_key"] = vk
    if "new_admin_password" in body:
        new_pwd = (body.get("new_admin_password") or "").strip()
        if new_pwd and len(new_pwd) >= 6:
            cfg["admin_password"] = new_pwd
    if "support" in body:
        cfg["support"] = (body.get("support") or "").strip()[:120]
    if "support_hours" in body:
        cfg["support_hours"] = (body.get("support_hours") or "").strip()[:60]
    # 公众号网页授权：AppSecret 留空表示不修改，避免每次保存都被清掉
    if "wx_appid" in body:
        aid = (body.get("wx_appid") or "").strip()
        # 微信 AppID 固定 wx 开头共 18 位，填错要到点开才发现，这里先挡一道
        if aid and not re.fullmatch(r"wx[0-9a-fA-F]{16}", aid):
            return JSONResponse(
                {"error": "AppID 格式不对：应为 wx 开头共 18 位（如 wx1234567890abcdef）"},
                status_code=400,
            )
        cfg["wx_appid"] = aid[:64]
    if "wx_appsecret" in body:
        sec = (body.get("wx_appsecret") or "").strip()
        if sec:
            if not re.fullmatch(r"[0-9a-zA-Z]{32}", sec):
                return JSONResponse({"error": "AppSecret 应为 32 位字母数字，请到公众号后台重新复制"}, status_code=400)
            cfg["wx_appsecret"] = sec[:128]
    if "wx_redirect_domain" in body:
        # 只留主机名，用户常把 https:// 或路径一起粘进来
        dom = (body.get("wx_redirect_domain") or "").strip()
        dom = re.sub(r"^https?://", "", dom, flags=re.I).split("/")[0].strip()
        cfg["wx_redirect_domain"] = dom[:120]
    # 微信域名校验文件：文件名 + 内容，由 /MP_verify_xxx.txt 路由吐出
    if "wx_verify_file" in body:
        vf = (body.get("wx_verify_file") or "").strip()
        vf = vf.rsplit("/", 1)[-1]          # 用户可能连路径一起粘
        if vf and not vf.endswith(".txt"):
            vf += ".txt"
        if vf and not re.fullmatch(r"MP_verify_[0-9A-Za-z]+\.txt", vf):
            return JSONResponse({"error": "校验文件名格式不对：应为 MP_verify_xxxx.txt"}, status_code=400)
        cfg["wx_verify_file"] = vf[:80]
    if "wx_verify_text" in body:
        cfg["wx_verify_text"] = (body.get("wx_verify_text") or "").strip()[:400]
    # 高德 Web 服务 Key：附近医院搜索用，留空表示不修改（要清空得显式传 clear）
    if "amap_key" in body:
        ak = (body.get("amap_key") or "").strip()
        if ak:
            if len(ak) < 20 or len(ak) > 64 or not re.fullmatch(r"[0-9a-zA-Z]+", ak):
                return JSONResponse({"error": "高德 Key 格式不对：应为 32 位字母数字（Web服务类型）"},
                                    status_code=400)
            cfg["amap_key"] = ak[:64]
    if body.get("amap_key_clear"):
        cfg["amap_key"] = ""

    save_config(cfg)
    return {"ok": True}


@app.get("/api/admin/stats")
async def admin_stats(request: Request, password: str = ""):
    if password != get_admin_password():
        return JSONResponse({"error": "密码错误"}, status_code=401)
    data = build_stats(load_stats())
    try:
        data["accounts"] = auth.stats()
    except Exception:
        data["accounts"] = {}
    return data


# ============ 后台：用户管理 ============
@app.get("/api/admin/whoami")
async def admin_whoami(request: Request, password: str = ""):
    """排查用：回显本次请求里与来源 IP 相关的头，确认反向代理到底传了什么。"""
    if password != get_admin_password():
        return JSONResponse({"error": "密码错误"}, status_code=401)
    keep = ("x-forwarded-for", "x-real-ip", "cf-connecting-ip", "true-client-ip",
            "x-client-ip", "forwarded", "via", "x-forwarded-proto", "user-agent")
    return {
        "resolved": auth.client_ip(request),
        "socket": request.client.host if request.client else "",
        "headers": {k: v for k, v in request.headers.items() if k.lower() in keep},
    }


@app.get("/api/admin/users")
async def admin_users(password: str = "", q: str = "", page: int = 1, size: int = 30):
    if password != get_admin_password():
        return JSONResponse({"error": "密码错误"}, status_code=401)
    items = auth.all_users()
    # 提问次数按问答记录实时汇总，避免账号表里的计数字段与实际不一致
    try:
        qmap = {}
        for r in load_stats().get("records", []):
            u = r.get("uid")
            if u:
                qmap[u] = qmap.get(u, 0) + 1
        for it in items:
            it["questions"] = qmap.get(it["uid"], 0)
    except Exception:
        pass
    # 登录次数与使用时长来自 usage.json，账号表一个字段都不加
    try:
        usg = usage.all_users()
        for it in items:
            u = usg.get(it["uid"]) or {}
            it["logins"] = int(u.get("logins") or 0)
            it["usage_seconds"] = int(u.get("seconds") or 0)
            it["usage_today"] = int(u.get("today_seconds") or 0)
            it["last_seen"] = int(u.get("last_seen") or 0)
            it["usage_tracked"] = bool(u.get("tracked"))
        # 老账号没有时长，但活跃记录里有「来过几天、访问几次」，一并给出来
        devs = analytics.load_activity().get("devices") or {}
        for it in items:
            d = devs.get(it["uid"]) or {}
            it["active_days"] = len(d.get("days") or {})
            it["visits"] = int(d.get("v") or 0)
    except Exception:
        pass
    q = (q or "").strip()
    if q:
        # 支持按 IP 搜：同一 IP 下挂了多个号，是刷号/羊毛党的典型特征
        items = [u for u in items
                 if q in (u.get("phone") or "") or q in (u.get("nickname") or "")
                 or q in (u.get("last_ip") or "") or q in (u.get("reg_ip") or "")]
    # 同一 IP 下挂了几个号：刷号、羊毛党的典型特征，按全量算（不能只看当前页）
    ip_cnt = {}
    for u in items:
        k = u.get("last_ip") or u.get("reg_ip") or ""
        if k:
            ip_cnt[k] = ip_cnt.get(k, 0) + 1
    for u in items:
        k = u.get("last_ip") or u.get("reg_ip") or ""
        u["ip_shared"] = ip_cnt.get(k, 0) if k else 0

    total = len(items)
    page = max(1, page)
    size = min(100, max(10, size))
    start = (page - 1) * size
    rows = items[start:start + size]
    # 只给当前页解析归属地，命中缓存时是纯内存查表
    for u in rows:
        d = geo.detail(u.get("last_ip") or "")
        u["last_ip_loc"] = d["loc"]
        u["last_ip_isp"] = d["isp"]
        u["reg_ip_loc"] = geo.lookup(u.get("reg_ip") or "")
    try:
        usage_summary = usage.summary()
    except Exception:
        usage_summary = {}
    return {
        "total": total,
        "page": page,
        "size": size,
        "items": rows,
        "summary": auth.stats(),
        "usage": usage_summary,
    }


@app.post("/api/admin/users/status")
async def admin_user_status(request: Request):
    body = await request.json()
    if body.get("password", "") != get_admin_password():
        return JSONResponse({"error": "密码错误"}, status_code=401)
    ok = auth.admin_set_status((body.get("uid") or "").strip(), bool(body.get("disabled")))
    if not ok:
        return JSONResponse({"error": "用户不存在"}, status_code=404)
    return {"ok": True}


@app.post("/api/admin/users/delete")
async def admin_user_delete(request: Request):
    """彻底删除账号及其名下数据：档案、温湿度记录、饲养日志、诊断记录。

    用于清理测试号、误注册，以及用户要求注销账号的场景。
    """
    body = await request.json()
    if body.get("password", "") != get_admin_password():
        return JSONResponse({"error": "密码错误"}, status_code=401)
    uid = (body.get("uid") or "").strip()
    if not uid:
        return JSONResponse({"error": "缺少用户 ID"}, status_code=400)
    accounts = auth.load_accounts()
    if uid not in accounts:
        return JSONResponse({"error": "用户不存在"}, status_code=404)

    removed = 0
    with _care_lock:
        pets = load_pets()
        keep_pets = [x for x in pets if x.get("uid") != uid]
        if len(keep_pets) != len(pets):
            removed = len(pets) - len(keep_pets)
            save_pets(keep_pets)
        logs = load_carelog()
        keep_logs = [x for x in logs if x.get("uid") != uid]
        if len(keep_logs) != len(logs):
            save_carelog(keep_logs)
        pl = load_petlogs()
        keep_pl = [x for x in pl if x.get("uid") != uid]
        if len(keep_pl) != len(pl):
            save_petlogs(keep_pl)
        dg = load_diagnoses()
        keep_dg = [x for x in dg if x.get("uid") != uid]
        if len(keep_dg) != len(dg):
            save_diagnoses(keep_dg)

    accounts.pop(uid, None)
    auth.save_accounts(accounts)
    # 活跃记录里还留着这个账号的设备行，不清掉会让渠道统计多出一批「零活跃已删用户」
    try:
        act = analytics.load_activity()
        devs = act.get("devices") or {}
        if uid in devs:
            devs.pop(uid, None)
            analytics.save_activity(act)
    except Exception:
        pass
    try:
        usage.forget(uid)
    except Exception:
        pass
    return {"ok": True, "pets_removed": removed}


@app.post("/api/admin/users/reset")
async def admin_user_reset(request: Request):
    body = await request.json()
    if body.get("password", "") != get_admin_password():
        return JSONResponse({"error": "密码错误"}, status_code=401)
    pwd = (body.get("password_new") or "").strip()
    try:
        ok = auth.admin_reset_password((body.get("uid") or "").strip(), pwd)
    except auth.AuthError as e:
        return JSONResponse({"error": e.message}, status_code=e.status)
    if not ok:
        return JSONResponse({"error": "用户不存在"}, status_code=404)
    return {"ok": True}


@app.post("/api/admin/stats/clear")
async def admin_stats_clear(request: Request):
    body = await request.json()
    if body.get("password", "") != get_admin_password():
        return JSONResponse({"error": "密码错误"}, status_code=401)
    with _stats_lock:
        save_stats({"records": []})
    analytics.clear_activity()
    return {"ok": True}


@app.get("/api/admin/news/status")
async def admin_news_status(password: str = ""):
    if password != get_admin_password():
        return JSONResponse({"error": "密码错误"}, status_code=401)
    news = load_news()
    log = {}
    if NEWS_LOG_FILE.exists():
        try:
            log = json.loads(NEWS_LOG_FILE.read_text(encoding="utf-8"))
        except Exception:
            log = {}
    sections = news.get("sections", [])
    return {
        "updated": news.get("updated", ""),
        "version": news.get("version", ""),
        "sections": [{"name": s.get("name"), "count": len(s.get("items", []))} for s in sections],
        "total": sum(len(s.get("items", [])) for s in sections),
        "last_run": log,
    }


@app.post("/api/admin/news/run")
async def admin_news_run(request: Request):
    """立即执行一次资讯更新（抓取配置源 + 导入投递箱）。"""
    body = await request.json()
    if body.get("password", "") != get_admin_password():
        return JSONResponse({"error": "密码错误"}, status_code=401)
    try:
        import news_updater
        log = news_updater.update_news()
        return {"ok": True, "log": log}
    except Exception as e:  # noqa: BLE001
        return JSONResponse({"error": f"更新失败：{e}"}, status_code=500)


@app.post("/api/admin/news/add")
async def admin_news_add(request: Request):
    """手动新增一条资讯并立即生效。"""
    body = await request.json()
    if body.get("password", "") != get_admin_password():
        return JSONResponse({"error": "密码错误"}, status_code=401)
    title = (body.get("title") or "").strip()
    if not title:
        return JSONResponse({"error": "标题不能为空"}, status_code=400)
    inbox = []
    if NEWS_INBOX_FILE.exists():
        try:
            inbox = json.loads(NEWS_INBOX_FILE.read_text(encoding="utf-8"))
        except Exception:
            inbox = []
    if not isinstance(inbox, list):
        inbox = []
    inbox.append({
        "title": title,
        "summary": (body.get("summary") or "").strip(),
        "source": (body.get("source") or "运营发布").strip(),
        "date": (body.get("date") or cn_date()),
        "section": (body.get("section") or "").strip(),
        "url": (body.get("url") or "").strip()[:500],
    })
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    NEWS_INBOX_FILE.write_text(json.dumps(inbox, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        import news_updater
        log = news_updater.update_news()
        return {"ok": True, "log": log}
    except Exception as e:  # noqa: BLE001
        return JSONResponse({"error": f"已保存，但刷新失败：{e}"}, status_code=500)


@app.post("/api/chat")
async def chat(request: Request):
    """提交问答任务：立即返回 task_id，由后台线程继续生成答案。
    即使客户端关闭页面/断网，后台仍会把答案生成完并保存，重新进入可接续。
    """
    acc = require_user(request)
    body = await request.json()
    messages = body.get("messages") or []
    if not messages:
        return JSONResponse({"error": "缺少消息"}, status_code=400)

    cfg = load_config()
    api_key, base_url, model = resolve_llm(cfg)
    if not (api_key and base_url and model):
        return JSONResponse(
            {"error": "问答服务还没配置好，暂时用不了，请稍后再试或联系客服。",
             "code": "not_configured"},
            status_code=503,
        )

    device_id = (body.get("device_id") or "").strip()[:64]

    last_user = ""
    for m in reversed(messages):
        if m.get("role") == "user":
            last_user = m.get("content", "")
            break

    system_content, refs = build_system_content(last_user)
    full_messages = [{"role": "system", "content": system_content}] + messages

    species_list = []
    for r in refs:
        s = r.get("species", "")
        if s and s != "通用" and s not in species_list:
            species_list.append(s)

    task_id = "t" + secrets.token_hex(8)
    with _tasks_lock:
        _tasks[task_id] = {
            "task_id": task_id,
            "status": "queued",
            "question": last_user,
            "answer": "",
            "refs": refs,
            "err": "",
            "device_id": device_id,
            "uid": acc["uid"],
            "ts": int(time.time()),
            "done_ts": 0,
        }
        _cleanup_tasks_locked()

    threading.Thread(
        target=_run_chat_task,
        args=(task_id, device_id, last_user, full_messages, refs, species_list,
              api_key, base_url, model, acc["uid"]),
        daemon=True,
    ).start()

    return JSONResponse({"task_id": task_id, "status": "queued", "refs": refs})


@app.get("/api/chat/status")
async def chat_status(request: Request, task_id: str = "", device_id: str = ""):
    """查询问答任务进度与已生成内容（供前端轮询、退出后接续）。

    只允许读取本人账号下的任务，避免凭 task_id 猜到别人的问答内容。
    """
    acc = require_user(request)
    uid = acc["uid"]
    with _tasks_lock:
        t = None
        if task_id:
            t = _tasks.get(task_id)
            if t and t.get("uid") and t["uid"] != uid:
                t = None
        elif device_id:
            items = [x for x in _tasks.values()
                     if x.get("uid") == uid or (not x.get("uid") and x.get("device_id") == device_id)]
            items.sort(key=lambda x: x.get("ts", 0), reverse=True)
            t = items[0] if items else None
        if not t:
            return {"found": False}
        return {
            "found": True,
            "task_id": t.get("task_id"),
            "status": t.get("status"),
            "answer": t.get("answer", ""),
            "refs": t.get("refs", []),
            "err": t.get("err", ""),
            "question": t.get("question", ""),
        }


# 微信网页授权登录（可选通道：需已备案域名 + 公众号后台配置网页授权域名）
@app.get("/api/wx/config")
async def wx_config():
    c = get_wx_config()
    return {"enabled": bool(c["appid"] and c["secret"])}


@app.get("/api/wx/me")
async def wx_me(request: Request):
    acc, why = auth.session_state(request)
    if acc:
        return {"logged_in": True, "user": _user_payload(acc),
                "token": auth.make_token(acc["uid"], acc.get("phone", "")),
                "day_end": auth.day_end()}
    return {"logged_in": False, "reason": why}


@app.get("/MP_verify_{code}.txt")
async def wx_verify_file(code: str):
    """微信「网页授权域名」校验文件。

    公众号后台添加域名时会要求放一个 MP_verify_xxx.txt 到域名根目录并抓取校验。
    这个站点是托管部署，没法往根目录扔文件，所以把内容存进配置、由这个路由吐出来。
    """
    cfg = load_config()
    want = (cfg.get("wx_verify_file") or "").strip()
    want_code = ""
    if want.startswith("MP_verify_") and want.endswith(".txt"):
        want_code = want[len("MP_verify_"):-len(".txt")]
    if not want_code or want_code != code:
        raise HTTPException(status_code=404)
    return Response(content=cfg.get("wx_verify_text") or "", media_type="text/plain; charset=utf-8")


@app.get("/api/wx/login")
async def wx_login(request: Request, silent: int = 0):
    """网页授权登录。

    silent=1 走 snsapi_base，不弹授权页、不发昵称头像，只拿 openid 建号，
    适合「扫码即用」的场景；默认仍走 snsapi_userinfo 取昵称头像。
    """
    c = get_wx_config()
    if not (c["appid"] and c["secret"]):
        return JSONResponse({"error": "微信登录未配置"}, status_code=501)
    domain = c["redirect_domain"] or request.headers.get("host", "")
    redirect_uri = f"https://{domain}/api/wx/callback"
    # state 用签名令牌，回调时校验，防止授权回调被伪造（CSRF）
    scope = "snsapi_base" if silent else "snsapi_userinfo"
    state = auth.make_token("wxstateb" if silent else "wxstate", "", days=1)
    url = (
        "https://open.weixin.qq.com/connect/oauth2/authorize"
        f"?appid={c['appid']}"
        f"&redirect_uri={urllib.parse.quote(redirect_uri, safe='')}"
        "&response_type=code"
        f"&scope={scope}"
        f"&state={state}#wechat_redirect"
    )
    return RedirectResponse(url=url)


@app.get("/api/wx/callback")
async def wx_callback(request: Request, code: str = "", state: str = ""):
    c = get_wx_config()
    if not code:
        return RedirectResponse(url="/?login=failed")
    # 这是跳转用的 state，不是登录态，别按「当天有效」判，用它自己的 1 天期限
    st = auth.read_token(state)
    if not st or st.get("uid") not in ("wxstate", "wxstateb"):
        return RedirectResponse(url="/?login=failed")
    silent = st.get("uid") == "wxstateb"
    token_url = (
        "https://api.weixin.qq.com/sns/oauth2/access_token"
        f"?appid={c['appid']}&secret={c['secret']}&code={code}&grant_type=authorization_code"
    )
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get(token_url)
        data = r.json()
        openid = data.get("openid")
        access_token = data.get("access_token")
        if not openid:
            return RedirectResponse(url="/?login=failed")

        nickname, avatar = "", ""
        if access_token and not silent:
            try:
                async with httpx.AsyncClient(timeout=15.0) as client:
                    uinfo = await client.get(
                        "https://api.weixin.qq.com/sns/userinfo"
                        f"?access_token={access_token}&openid={openid}&lang=zh_CN"
                    )
                ud = uinfo.json()
                nickname = ud.get("nickname", "")
                avatar = ud.get("headimgurl", "")
            except Exception:
                pass

        acc = auth.upsert_wechat(openid, nickname, avatar, ip=auth.client_ip(request))
        usage.mark_login(acc["uid"])
        token = auth.make_token(acc["uid"], acc.get("phone", ""))
        resp = RedirectResponse(url="/")
        _set_login_cookie(resp, request, token)
        return resp
    except Exception:
        return RedirectResponse(url="/?login=failed")


@app.get("/api/wx/logout")
async def wx_logout():
    resp = RedirectResponse(url="/")
    resp.delete_cookie(auth.COOKIE_NAME, path="/")
    return resp


# 静态资源
# 图鉴 132 张图 + 缩略图共 265 个文件，网页上传到 GitHub / 空间时会被单次 100 个文件的
# 限制卡住。打包成 static/dex.zip 后只算 1 个文件，磁盘目录仍然优先（本地开发照旧）。
DEX_ZIP = STATIC_DIR / "dex.zip"
_dex_zip = {"fp": None, "zf": None}
_dex_zip_lock = threading.Lock()


def _dex_bytes(rel: str):
    """从 dex.zip 读一张图；没有压缩包或读不到时返回 None。"""
    if not DEX_ZIP.exists():
        return None
    with _dex_zip_lock:
        if _dex_zip["fp"] != DEX_ZIP.stat().st_mtime_ns or _dex_zip["zf"] is None:
            _dex_zip["zf"] = zipfile.ZipFile(DEX_ZIP)
            _dex_zip["fp"] = DEX_ZIP.stat().st_mtime_ns
        zf = _dex_zip["zf"]
    try:
        return zf.read(rel)
    except KeyError:
        return None


@app.get("/static/dex/{rel:path}")
async def dex_image(rel: str):
    if ".." in rel or rel.startswith("/") or "\\" in rel:
        raise HTTPException(status_code=404)
    fp = (STATIC_DIR / "dex" / rel)
    if fp.is_file():
        return FileResponse(fp, headers={"Cache-Control": "public, max-age=604800"})
    data = _dex_bytes(rel)
    if data is None:
        raise HTTPException(status_code=404)
    import mimetypes
    ctype = mimetypes.guess_type(rel)[0] or "application/octet-stream"
    return Response(content=data, media_type=ctype,
                    headers={"Cache-Control": "public, max-age=604800"})


app.mount("/static", CachedStaticFiles(directory=STATIC_DIR), name="static")


# 首页 HTML 只在文件变化时重新读取与替换；命中时按内容哈希回 304，
# 回访用户几乎零传输（此前每次都要重新下载 367 KB）。
_index_cache = {"sig": None, "html": ""}
_index_br = {}
_index_lock = threading.Lock()


@app.get("/")
async def index(request: Request):
    """首页。分享图需要带 sharecode 才能通过平台鉴权，所以在服务端注入完整地址。"""
    try:
        st = (STATIC_DIR / "index.html").stat()
        sig = (st.st_mtime_ns, st.st_size)
    except OSError:
        sig = None

    with _index_lock:
        if sig and _index_cache["sig"] == sig:
            base = _index_cache["html"]
        else:
            base = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
            if sig:
                _index_cache["sig"] = sig
                _index_cache["html"] = base
                _index_br.clear()

    cfg = load_config()
    # URL 上没带时用配置里的固定 sharecode 兜底，海报二维码才不会扫出 403
    sc = request.query_params.get("sharecode") or str(cfg.get("sharecode") or "")
    suffix = f"?sharecode={sc}" if sc else ""
    # 用相对路径，避免反向代理下 request.base_url 指向内部地址；缺 sharecode 时由前端补齐
    html = base.replace("__OG_IMAGE__", f"/static/share.png{suffix}")
    html = html.replace("__SHARE_IMG__", f"/static/share.png{suffix}")
    html = html.replace("__SHARE_CODE__", sc)
    # 脚本外置后带版本号，升级即换 URL，不会读到旧缓存
    html = html.replace("__APP_VER__", APP_VERSION)

    # 没登录的人，第一帧就是登录页：不放启动动画、不铺应用骨架。
    # 以前靠 JS 判断完再切，弱网下会先闪一下启动页；现在服务端直接按 cookie 决定。
    try:
        acc, why = auth.session_state(request)
        logged = bool(acc)
    except Exception:
        logged, why = False, ""
    html = html.replace("__BOOT_CLS__", " booting" if logged else "")
    html = html.replace("__AUTH_CLS__", "" if logged else " show")
    # 昨天登录、今天打开的人，登录页直接告诉他为什么被退出来
    tip = ""
    if not logged:
        tip = {"newday": "已过夜里 12 点，请重新登录",
               "invalid": "登录状态已失效，请重新登录"}.get(why, "")
    html = html.replace("__AUTH_TIP__", tip)

    etag = '"' + hashlib.md5(html.encode("utf-8")).hexdigest() + '"'
    headers = {
        "Cache-Control": "no-cache, must-revalidate, max-age=0",
        "Pragma": "no-cache",
        "Expires": "0",
        "ETag": etag,
    }
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers=headers)

    # 首页是每次访问都要重传的最大一块，Brotli q9 能到 60 KB 出头。
    # 压缩一次缓存起来，之后同 sharecode 的请求直接发字节，不重复耗 CPU。
    ae = (request.scope.get("xc_accept_encoding")
          or request.headers.get("accept-encoding") or "").lower()
    if _brotli is not None and "br" in ae:
        # 登录与否的首帧不一样（骨架 / 登录页），缓存 key 必须带上，
        # 否则已登录的人会拿到压缩好的登录页
        key = (sig, sc, logged, why)
        body = _index_br.get(key)
        if body is None:
            try:
                body = _brotli.compress(html.encode("utf-8"), quality=9)
            except Exception:  # noqa: BLE001
                body = None
            if body is not None:
                with _index_lock:
                    if len(_index_br) > 4:
                        _index_br.clear()
                    _index_br[key] = body
        if body is not None:
            return Response(
                content=body, media_type="text/html; charset=utf-8",
                headers={**headers, "Content-Encoding": "br", "Vary": "Accept-Encoding"},
            )

    return HTMLResponse(html, headers=headers)


@app.get("/admin")
async def admin():
    return FileResponse(
        STATIC_DIR / "admin.html",
        headers={"Cache-Control": "no-cache, must-revalidate"},
    )


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
