# -*- coding: utf-8 -*-
"""小宠百问 —— 行业动态自动更新引擎

每天由 main.py 的定时线程调用，也可手动执行：
    python3.11 news_updater.py

更新流程：
1. 读取 data/news.json（现有分板块数据）
2. 读取 data/news_inbox.json（运营/外部程序投递的待发布资讯）
3. 依次抓取 data/news_sources.json 中配置的 RSS/Atom 源
4. 按关键词把新条目自动归类到 7 大板块，按标题归一化去重
5. 合并进各板块（新条目置顶），每板块保留上限
6. 写回 news.json 并更新 updated 字段；清空已导入的 inbox；记录运行日志
"""
import json
import re
import time
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
NEWS_FILE = DATA_DIR / "news.json"
INBOX_FILE = DATA_DIR / "news_inbox.json"
SOURCES_FILE = DATA_DIR / "news_sources.json"
LOG_FILE = DATA_DIR / "news_log.json"

SECTION_LIMIT = 8  # 每个板块最多保留条数

DEFAULT_SECTIONS = [
    ("policy", "政策法规", "⚖️", "禁养名录、海关监管与合法饲养须知"),
    ("market", "市场大盘", "📊", "行业规模、人群画像与消费趋势"),
    ("reptile", "爬宠", "🦎", "蛇、蜥蜴、龟、守宫等爬行动物"),
    ("bird", "鸟类", "🦜", "鹦鹉、文鸟等观赏鸟类"),
    ("mammal", "小型哺乳", "🐹", "兔子、仓鼠、龙猫、豚鼠、蜜袋鼯等"),
    ("arthropod", "节肢·两栖", "🦗", "蜘蛛、蝎子、寄居蟹、蛙、蝾螈、六角恐龙"),
    ("aquatic", "水生·水族", "🐠", "观赏鱼、水族造景与设备"),
]

# 板块关键词（用于自动归类），按命中数打分取最高
SECTION_KEYWORDS = {
    "policy": ["政策", "法规", "名录", "海关", "禁养", "保护动物", "许可", "标识",
               "检疫", "违法", "CITES", "外来物种", "放生", "监管"],
    "market": ["市场", "规模", "增长", "消费", "报告", "白皮书", "融资", "营收",
               "数据", "亿元", "人群", "产业", "品牌"],
    "reptile": ["爬宠", "爬行", "守宫", "蜥蜴", "蛇", "龟", "陆龟", "球蟒", "鬃狮",
                "变色龙", "玉米蛇", "猪鼻蛇", "王蛇"],
    "bird": ["鹦鹉", "鸟类", "玄凤", "虎皮", "牡丹", "文鸟", "八哥", "禽", "金丝雀"],
    "mammal": ["兔", "仓鼠", "龙猫", "豚鼠", "蜜袋鼯", "刺猬", "雪貂", "松鼠",
               "花枝鼠", "沙鼠", "哺乳"],
    "arthropod": ["蜘蛛", "蝎子", "螳螂", "甲虫", "寄居蟹", "蛙", "蝾螈", "六角恐龙",
                  "节肢", "昆虫", "跳蛛", "角蛙"],
    "aquatic": ["观赏鱼", "水族", "鱼缸", "锦鲤", "金鱼", "孔雀鱼", "斗鱼", "珊瑚",
                "海水", "水草", "斑马鱼"],
}


def _load(path, default):
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return default


def _ensure_files():
    if not SOURCES_FILE.exists():
        SOURCES_FILE.write_text(json.dumps({
            "note": "在此配置可用的 RSS/Atom 源（数组），系统每日 06:00 自动抓取；"
                    "留空则仅导入 news_inbox.json 中投递的资讯。",
            "rss": [],
            "source_name": "行业资讯",
        }, ensure_ascii=False, indent=2), encoding="utf-8")
    if not INBOX_FILE.exists():
        INBOX_FILE.write_text("[]", encoding="utf-8")


def _today():
    return time.strftime("%Y-%m-%d")


def _key(title):
    """标题归一化，用于去重。"""
    t = re.sub(r"[\s\u3000，。、！？；：「」“”‘’（）()【】《》,.!?;:\-—_]", "", title or "")
    return t[:30]


def _clean_html(s):
    return re.sub(r"<[^>]+>", "", s or "").strip()


def _extract_date(s):
    m = re.search(r"(\d{4})[-/年](\d{1,2})[-/月](\d{1,2})", s or "")
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    m2 = re.search(r"(\d{4})[-/](\d{1,2})", s or "")
    if m2:
        return f"{m2.group(1)}-{int(m2.group(2)):02d}"
    return _today()


def _classify(text):
    t = text or ""
    best, best_score = None, 0
    for sid, kws in SECTION_KEYWORDS.items():
        score = sum(1 for k in kws if k in t)
        if score > best_score:
            best, best_score = sid, score
    return best


def _fetch_rss(url, timeout=10):
    """抓取并解析 RSS/Atom，返回 [{title, summary, date}]。失败抛异常由调用方处理。"""
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0",
    })
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
    items = []
    try:
        root = ET.fromstring(raw)
    except Exception:
        return items
    for it in root.iter():
        tag = it.tag.split("}")[-1]
        if tag not in ("item", "entry"):
            continue
        title = summary = pub = link = ""
        for ch in it:
            ct = ch.tag.split("}")[-1]
            if ct == "title":
                title = (ch.text or "").strip()
            elif ct in ("description", "summary", "content"):
                summary = (ch.text or "").strip()
            elif ct in ("pubDate", "published", "updated"):
                pub = (ch.text or "").strip()
            elif ct == "link":
                # RSS: <link>https://…</link>；Atom: <link href="https://…"/>
                link = (ch.get("href") or ch.text or "").strip() or link
        if title:
            items.append({"title": title, "summary": summary, "date": pub, "url": link})
    return items


def update_news(verbose=False):
    """执行一次资讯更新，返回运行日志 dict。"""
    _ensure_files()
    news = _load(NEWS_FILE, {"version": "1.0.0", "updated": "", "sections": []})
    sections = news.get("sections") or []

    section_map = {s.get("id"): s for s in sections}
    for sid, name, emoji, desc in DEFAULT_SECTIONS:
        if sid not in section_map:
            sec = {"id": sid, "name": name, "emoji": emoji, "desc": desc, "items": []}
            sections.append(sec)
            section_map[sid] = sec

    existing = set()
    for s in sections:
        for it in s.get("items", []):
            existing.add(_key(it.get("title", "")))

    candidates = []

    # 1) 运营投递箱
    inbox = _load(INBOX_FILE, [])
    if isinstance(inbox, list):
        for it in inbox:
            if not isinstance(it, dict) or not (it.get("title") or "").strip():
                continue
            candidates.append({
                "title": it["title"].strip(),
                "summary": (it.get("summary") or "").strip(),
                "source": (it.get("source") or "运营投递").strip(),
                "date": it.get("date") or _today(),
                "section": (it.get("section") or "").strip(),
                "url": (it.get("url") or "").strip(),
            })

    # 2) RSS/Atom 源
    sources = _load(SOURCES_FILE, {"rss": []})
    errors = []
    source_name = sources.get("source_name") or "行业资讯"
    for url in (sources.get("rss") or []):
        try:
            for item in _fetch_rss(url):
                candidates.append({
                    "title": item["title"],
                    "summary": _clean_html(item.get("summary", ""))[:240],
                    "source": source_name,
                    "date": _extract_date(item.get("date", "")),
                    "section": "",
                    "url": (item.get("url") or "").strip(),
                })
        except Exception as e:  # noqa: BLE001
            errors.append(f"{url} -> {str(e)[:80]}")

    # 3) 归类 + 去重 + 合并
    added = 0
    for c in candidates:
        k = _key(c["title"])
        if not k or k in existing:
            continue
        text = c["title"] + " " + c["summary"]
        sid = c["section"] if c["section"] in section_map else (_classify(text) or "market")
        sec = section_map.get(sid) or section_map["market"]
        item = {
            "id": "auto" + str(int(time.time())) + str(added),
            "date": c["date"],
            "title": c["title"],
            "summary": c["summary"] or c["title"],
            "source": c["source"],
        }
        if c.get("url"):
            item["url"] = c["url"]
        sec.setdefault("items", []).insert(0, item)
        existing.add(k)
        added += 1

    for s in sections:
        s["items"] = (s.get("items") or [])[:SECTION_LIMIT]

    if added:
        news["updated"] = _today()
        try:
            v = (news.get("version") or "1.0.0").split(".")
            v[-1] = str(int(v[-1]) + 1)
            news["version"] = ".".join(v)
        except Exception:
            pass

    news["sections"] = sections
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    NEWS_FILE.write_text(json.dumps(news, ensure_ascii=False, indent=2), encoding="utf-8")

    # 已导入的投递内容清空
    if isinstance(inbox, list) and inbox:
        INBOX_FILE.write_text("[]", encoding="utf-8")

    log = {
        "last_run": int(time.time()),
        "last_run_str": time.strftime("%Y-%m-%d %H:%M:%S"),
        "added": added,
        "candidates": len(candidates),
        "errors": errors[:10],
        "total": sum(len(s.get("items") or []) for s in sections),
        "sections": [{"name": s.get("name"), "count": len(s.get("items") or [])} for s in sections],
    }
    try:
        LOG_FILE.write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass

    if verbose:
        print(json.dumps(log, ensure_ascii=False, indent=2))
    return log


if __name__ == "__main__":
    update_news(verbose=True)
