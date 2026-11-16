"""养护模块的后台统计。

后台要看的「用户实时数据」分三类：
1. 存量与活跃：谁建了档案、记录了多少条、今天记了几次、最后一次操作是什么时候；
2. 健康预警：温湿度是否偏离该物种的参考区间，偏离的是哪只、哪条记录；
3. 使用行为：分诊评估了多少次、评出什么级别、哪些症状被勾得最多、急救和就医看了什么。
"""
import time

# 物种 -> 参考温湿度区间（与前端 CARE_ENV 保持一致；成体常规饲养）
ENV_TABLE = [
    {"k": ["睫角", "冠尾"], "n": "睫角守宫", "t": (22, 26), "h": (60, 80)},
    {"k": ["守宫", "豹纹", "肥尾", "瘤尾"], "n": "守宫", "t": (28, 32), "h": (40, 60)},
    {"k": ["变色龙"], "n": "变色龙", "t": (24, 28), "h": (50, 70)},
    {"k": ["鬃狮", "蜥蜴", "蓝舌", "石龙子"], "n": "蜥蜴", "t": (30, 35), "h": (40, 50)},
    {"k": ["蛙", "角蛙", "树蛙"], "n": "蛙类", "t": (24, 28), "h": (70, 85)},
    {"k": ["蛇", "玉米蛇", "球蟒", "王蛇", "猪鼻"], "n": "蛇类", "t": (28, 32), "h": (50, 70)},
    {"k": ["龟", "陆龟", "水龟", "草龟", "巴西"], "n": "龟类", "t": (25, 30), "h": (60, 80)},
    {"k": ["六角", "蝾螈"], "n": "两栖", "t": (16, 22), "h": (60, 80)},
    {"k": ["龙猫"], "n": "龙猫", "t": (18, 22), "h": (40, 55)},
    {"k": ["兔"], "n": "兔子", "t": (18, 25), "h": (40, 60)},
    {"k": ["豚鼠", "荷兰猪"], "n": "豚鼠", "t": (18, 24), "h": (40, 60)},
    {"k": ["仓鼠", "金丝熊", "侏儒"], "n": "仓鼠", "t": (20, 24), "h": (40, 60)},
    {"k": ["蜜袋鼯"], "n": "蜜袋鼯", "t": (24, 28), "h": (50, 60)},
    {"k": ["刺猬"], "n": "刺猬", "t": (24, 28), "h": (40, 60)},
    {"k": ["雪貂"], "n": "雪貂", "t": (18, 24), "h": (40, 60)},
    {"k": ["松鼠", "花枝", "沙鼠", "大鼠", "老鼠"], "n": "小型啮齿", "t": (20, 26), "h": (40, 60)},
    {"k": ["鹦鹉", "玄凤", "虎皮", "牡丹"], "n": "鹦鹉", "t": (20, 28), "h": (40, 60)},
    {"k": ["文鸟", "八哥", "鸟"], "n": "鸟类", "t": (20, 28), "h": (40, 60)},
    {"k": ["蜘蛛", "捕鸟蛛"], "n": "蜘蛛", "t": (25, 30), "h": (60, 75)},
    {"k": ["蝎子"], "n": "蝎子", "t": (26, 32), "h": (50, 70)},
    {"k": ["螳螂", "甲虫", "锹", "兜虫"], "n": "昆虫", "t": (24, 28), "h": (60, 80)},
    {"k": ["虾", "鱼", "锦鲤", "金鱼"], "n": "水族", "t": (22, 26), "h": (0, 0)},
]

GENERIC = {"n": "通用参考", "t": (20, 28), "h": (40, 70)}

LEVEL_NAME = {3: "急诊", 2: "尽快就医", 1: "居家观察"}


def _d(ts: int) -> str:
    """UTC+8 自然日，避免容器时区把「今天」算偏。"""
    return time.strftime("%Y-%m-%d", time.gmtime((ts or 0) + 8 * 3600))


def _hm(ts: int) -> str:
    return time.strftime("%m-%d %H:%M", time.gmtime((ts or 0) + 8 * 3600))


def env_of(species: str) -> dict:
    s = species or ""
    for row in ENV_TABLE:
        for kw in row["k"]:
            if kw in s:
                return row
    return GENERIC


def judge(species: str, temp: float, hum: float) -> list:
    """返回偏离说明，空列表代表在区间内。"""
    env = env_of(species)
    out = []
    t_lo, t_hi = env["t"]
    if temp > t_hi + 0.05:
        out.append("温度偏高 %.1f℃" % (temp - t_hi))
    elif temp < t_lo - 0.05:
        out.append("温度偏低 %.1f℃" % (t_lo - temp))
    h_lo, h_hi = env["h"]
    if h_hi > 0:  # 水族不按湿度判断
        if hum > h_hi + 0.05:
            out.append("湿度偏高 %d%%" % round(hum - h_hi))
        elif hum < h_lo - 0.05:
            out.append("湿度偏低 %d%%" % round(h_lo - hum))
    return out


def _mask_phone(p: str) -> str:
    p = (p or "").strip()
    if len(p) >= 7:
        return p[:3] + "****" + p[-4:]
    return p


def build(pets: list, logs: list, events: list, accounts: dict, petlogs: list = None,
          diagnoses: list = None, now: int = None, days: int = 14) -> dict:
    now = int(now or time.time())
    today = _d(now)
    day_start = now - ((now + 8 * 3600) % 86400)  # 北京时间当天 0 点

    pet_by_id = {p.get("id"): p for p in pets}
    uid_name = {}
    uid_phone = {}
    for k, v in (accounts or {}).items():
        uid = v.get("uid") or k
        uid_name[uid] = v.get("nickname") or ""
        uid_phone[uid] = v.get("phone") or ""

    # ---------- 存量 ----------
    pet_users = len({p.get("uid") for p in pets if p.get("uid")})
    log_users = len({x.get("uid") for x in logs if x.get("uid")})
    logs_today = sum(1 for x in logs if (x.get("ts") or 0) >= day_start)
    logs_24h = sum(1 for x in logs if (x.get("ts") or 0) >= now - 86400)
    logs_7d = sum(1 for x in logs if (x.get("ts") or 0) >= now - 7 * 86400)

    # ---------- 温湿度预警（近 24 小时） ----------
    abnormal = []
    for x in logs:
        ts = x.get("ts") or 0
        if ts < now - 86400:
            continue
        pet = pet_by_id.get(x.get("pet_id")) or {}
        tag = judge(pet.get("species", ""), x.get("temp") or 0, x.get("hum") or 0)
        if not tag:
            continue
        abnormal.append({
            "pet": pet.get("name") or "未绑定宠物",
            "species": pet.get("species") or "—",
            "temp": x.get("temp"),
            "hum": x.get("hum"),
            "tag": "、".join(tag),
            "time": _hm(ts),
            "ts": ts,
            "uid": x.get("uid") or "",
            "user": uid_name.get(x.get("uid") or "") or _mask_phone(uid_phone.get(x.get("uid") or "")),
        })
    abnormal.sort(key=lambda a: a["ts"], reverse=True)
    abnormal_24h = len(abnormal)

    # ---------- 物种分布（档案） ----------
    sp_map = {}
    for p in pets:
        n = env_of(p.get("species", ""))["n"]
        sp_map.setdefault(n, {"name": n, "pets": 0, "logs": 0})
        sp_map[n]["pets"] += 1
    pet_species = {(p.get("id")): env_of(p.get("species", ""))["n"] for p in pets}
    for x in logs:
        n = pet_species.get(x.get("pet_id"))
        if n and n in sp_map:
            sp_map[n]["logs"] += 1
    species = sorted(sp_map.values(), key=lambda s: (-s["pets"], -s["logs"], s["name"]))[:10]

    # ---------- 使用行为 ----------
    ev_today = [e for e in events if (e.get("ts") or 0) >= day_start]
    tri_all = [e for e in events if e.get("kind") == "triage"]
    aid_all = [e for e in events if e.get("kind") == "aid"]
    vet_all = [e for e in events if e.get("kind") == "vet"]

    lv_cnt = {1: 0, 2: 0, 3: 0}
    sym_cnt = {}
    tri_sp = {}
    for e in tri_all:
        lv = int(e.get("level") or 0)
        if lv in lv_cnt:
            lv_cnt[lv] += 1
        for s in e.get("symptoms") or []:
            sym_cnt[s] = sym_cnt.get(s, 0) + 1
        sp = (e.get("species") or "").strip()
        if sp:
            tri_sp[sp] = tri_sp.get(sp, 0) + 1

    aid_cnt = {}
    for e in aid_all:
        it = (e.get("item") or "").strip()
        if it:
            aid_cnt[it] = aid_cnt.get(it, 0) + 1

    # ---------- 近 N 天趋势 ----------
    trend_map = {}
    for i in range(days - 1, -1, -1):
        d = _d(now - i * 86400)
        trend_map[d] = {"d": d[5:].replace("-", "/"), "logs": 0, "triage": 0}
    for x in logs:
        d = _d(x.get("ts") or 0)
        if d in trend_map:
            trend_map[d]["logs"] += 1
    for e in tri_all:
        d = _d(e.get("ts") or 0)
        if d in trend_map:
            trend_map[d]["triage"] += 1
    trend = [trend_map[d] for d in sorted(trend_map)]

    # ---------- 用户明细（用过养护的人） ----------
    ustat = {}

    def touch(uid, field, ts):
        if not uid:
            return
        u = ustat.setdefault(uid, {"uid": uid, "pets": 0, "logs": 0, "triage": 0, "aid": 0, "vet": 0, "last": 0})
        if field:
            u[field] += 1
        if ts and ts > u["last"]:
            u["last"] = ts

    for p in pets:
        touch(p.get("uid"), "pets", p.get("updated") or p.get("created") or 0)
    for x in logs:
        touch(x.get("uid"), "logs", x.get("ts") or 0)
    for e in events:
        k = e.get("kind")
        touch(e.get("uid"), k if k in ("triage", "aid", "vet") else "", e.get("ts") or 0)

    users = []
    for uid, u in ustat.items():
        users.append({
            "user": uid_name.get(uid) or "—",
            "phone": _mask_phone(uid_phone.get(uid, "")),
            "pets": u["pets"], "logs": u["logs"],
            "triage": u["triage"], "aid": u["aid"], "vet": u["vet"],
            "last": _hm(u["last"]) if u["last"] else "—",
            "last_ts": u["last"],
        })
    users.sort(key=lambda x: (-x["last_ts"], -x["logs"]))
    care_users_today = len({u["uid"] for u in ustat.values() if u["last"] >= day_start})

    # 饲养日志（喂食 / 蜕皮 / 排便 / 用药）：不含观察追踪
    pl = [x for x in (petlogs or []) if (x.get("type") or "") not in ("", "watch")]
    pl_today = [x for x in pl if _d(x.get("ts")) == today]
    pl_type = {}
    for x in pl:
        k = x.get("type") or ""
        pl_type[k] = pl_type.get(k, 0) + 1
    TYPE_NAME = {"feed": "喂食", "shed": "蜕皮", "poop": "排便", "med": "用药", "weight": "体重"}
    pl_users = len({x.get("uid") for x in pl if x.get("uid")})

    # 拍照诊断：看用量、看分级分布，判断这个功能是不是真被用起来了
    dg = diagnoses or []
    dg_today = [x for x in dg if _d(x.get("ts")) == today]
    dg_lv = {0: 0, 1: 0, 2: 0}
    for x in dg:
        lv = x.get("level")
        dg_lv[lv if lv in dg_lv else 0] += 1
    dg_top = {}
    for x in dg:
        sp = (x.get("species") or "未填").strip() or "未填"
        dg_top[sp] = dg_top.get(sp, 0) + 1

    return {
        "now": now,
        "overview": {
            "pets": len(pets),
            "pet_users": pet_users,
            "pets_per_user": round(len(pets) / pet_users, 1) if pet_users else 0,
            "logs": len(logs),
            "log_users": log_users,
            "logs_today": logs_today,
            "logs_24h": logs_24h,
            "logs_7d": logs_7d,
            "abnormal_24h": abnormal_24h,
            "triage_total": len(tri_all),
            "triage_today": sum(1 for e in ev_today if e.get("kind") == "triage"),
            "aid_total": len(aid_all),
            "aid_today": sum(1 for e in ev_today if e.get("kind") == "aid"),
            "vet_total": len(vet_all),
            "vet_today": sum(1 for e in ev_today if e.get("kind") == "vet"),
            "care_users_today": care_users_today,
        },
        "species": species,
        "trend": trend,
        "abnormal": abnormal[:20],
        "triage": {
            "levels": [{"level": lv, "name": LEVEL_NAME[lv], "n": lv_cnt[lv]} for lv in (3, 2, 1)],
            "symptoms": sorted(
                [{"name": k, "n": v} for k, v in sym_cnt.items()],
                key=lambda x: -x["n"]
            )[:10],
            "species": sorted(
                [{"name": k, "n": v} for k, v in tri_sp.items()],
                key=lambda x: -x["n"]
            ),
        },
        "petlogs": {
            "total": len(pl),
            "today": len(pl_today),
            "users": pl_users,
            "by_type": [{"k": k, "name": TYPE_NAME.get(k, k), "n": v}
                        for k, v in sorted(pl_type.items(), key=lambda kv: -kv[1])],
        },
        "aid": sorted([{"name": k, "n": v} for k, v in aid_cnt.items()], key=lambda x: -x["n"])[:10],
        "diag": {
            "total": len(dg),
            "today": len(dg_today),
            "users": len({x.get("uid") for x in dg if x.get("uid")}),
            "levels": [{"lv": k, "n": dg_lv[k]} for k in (0, 1, 2)],
            "species": sorted([{"name": k, "n": v} for k, v in dg_top.items()],
                              key=lambda x: -x["n"])[:8],
        },
        "users": users[:50],
    }
