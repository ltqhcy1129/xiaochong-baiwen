# -*- coding: utf-8 -*-
"""拍照诊断：把一张照片变成一份可执行的清单。

设计要点：
1. 只让模型做「看图说话 + 分级」，不让它下确诊、不给具体药量和处方；
2. 输出强制 JSON，字段在 normalize() 里做白名单截断，避免前端拿到脏数据；
3. 模型不支持图片（4xx）时抛 ModelNoVision，由上层降级为文字建议，功能不会死。
"""
import json
import re

DIAG_PROMPT = """你是异宠临床分诊助手，服务对象是普通饲主。刚收到一张宠物照片，以及主人的补充描述。

你的任务是：根据照片中**真实可见**的信息，做初步判断，给出一份可以照着做的清单。

严格要求：
1. 只描述照片里确实能看到的东西。看不清、被遮挡、光线不足，就写进 need 让主人重拍，绝不猜测。
2. 不下确诊。可以列「可能原因」并标注可能性，用词是「更像 / 需排除」，不是「就是」。
3. 不给具体药物名称、剂量、注射操作。可以给护理动作（保温、补液方式、隔离、停食等）。
4. 涉及以下表现直接判急诊：呼吸困难/张口呼吸、抽搐、无法站立、出血不止、严重脱水、腹部鼓胀发硬、脱肛、坠蛋、明显骨折、眼睛完全闭合肿胀。
5. 兔子、豚鼠、龙猫这类食草动物超过 12 小时不吃不排便，按急诊处理。
6. 语气克制，不吓人也不安慰。像医生当面说话：短、直，说「先保温」「今天别喂」，不写「建议您」「请注意」。不确定就说不确定。

只输出 JSON，不要 markdown 代码块，不要任何解释文字。结构如下：

{
  "level": 0,
  "title": "八个字以内的结论",
  "summary": "六十字内，说清这是什么情况、要不要紧",
  "species_guess": "从照片推测的物种，不确定填空字符串",
  "see": ["照片里看到的具体表现，一句一条，最多 5 条"],
  "causes": [{"name": "可能原因", "odds": "高", "why": "为什么这样判断，四十字内"}],
  "now": ["现在就能做的事，按顺序，最多 5 条"],
  "avoid": ["现在不要做的事，最多 4 条"],
  "vet": ["出现这些变化就立刻就医，最多 4 条"],
  "need": ["还需要补充的照片或信息，最多 3 条"]
}

level 取值：0 = 居家观察；1 = 24 小时内就医；2 = 立即急诊。
causes 按可能性从高到低排，最多 4 条，odds 只能是 高 / 中 / 低。
所有句子都写短句，单条不超过 40 字，整个 JSON 不超过 900 字。"""

MAX_IMG_BYTES = 4 * 1024 * 1024      # base64 解码后的上限
ALLOW_MIME = ("image/jpeg", "image/jpg", "image/png", "image/webp")


class ModelNoVision(Exception):
    """上游模型不支持图片输入。"""


class DiagnoseError(Exception):
    """诊断失败，message 直接给用户看。"""


def _s(v, n: int) -> str:
    return str(v or "").strip().replace("\n", " ")[:n]


def _arr(v, n: int, each: int = 60) -> list:
    if not isinstance(v, list):
        return []
    out = []
    for x in v:
        t = _s(x, each)
        if t and t not in out:
            out.append(t)
        if len(out) >= n:
            break
    return out


def parse_json(text: str):
    """模型偶尔会裹 ```json，或者前后带一句话，这里尽量捞出来。"""
    t = (text or "").strip()
    if not t:
        return None
    t = re.sub(r"^```(?:json)?\s*", "", t)
    t = re.sub(r"\s*```$", "", t)
    try:
        obj = json.loads(t)
        if isinstance(obj, dict):
            return obj
    except Exception:
        pass
    i, j = t.find("{"), t.rfind("}")
    if i >= 0 and j > i:
        try:
            obj = json.loads(t[i:j + 1])
            if isinstance(obj, dict):
                return obj
        except Exception:
            pass
    return None


def normalize(raw: dict, species_hint: str = "") -> dict:
    """白名单 + 截断。前端拿到的每个字段都是短的纯文本。"""
    lv = raw.get("level", 0)
    try:
        lv = int(lv)
    except Exception:
        lv = 0
    lv = 2 if lv >= 2 else (1 if lv == 1 else 0)

    causes = []
    for c in (raw.get("causes") or [])[:4]:
        if isinstance(c, dict):
            name = _s(c.get("name"), 24)
            if not name:
                continue
            odds = _s(c.get("odds"), 2)
            if odds not in ("高", "中", "低"):
                odds = "中"
            causes.append({"name": name, "odds": odds, "why": _s(c.get("why"), 48)})
        elif isinstance(c, str) and c.strip():
            causes.append({"name": _s(c, 24), "odds": "中", "why": ""})

    return {
        "level": lv,
        "title": _s(raw.get("title"), 20) or "初步判断",
        "summary": _s(raw.get("summary"), 120),
        "species_guess": _s(raw.get("species_guess"), 12) or _s(species_hint, 12),
        "see": _arr(raw.get("see"), 5),
        "causes": causes,
        "now": _arr(raw.get("now"), 5),
        "avoid": _arr(raw.get("avoid"), 4),
        "vet": _arr(raw.get("vet"), 4),
        "need": _arr(raw.get("need"), 3),
    }


def split_data_uri(uri: str):
    """data:image/jpeg;base64,xxx → (mime, 原始字节)"""
    uri = (uri or "").strip()
    m = re.match(r"^data:(image/[a-zA-Z+]+);base64,(.+)$", uri, re.S)
    if not m:
        raise DiagnoseError("图片格式不对，请重新选择一张照片")
    mime = m.group(1).lower()
    if mime not in ALLOW_MIME:
        raise DiagnoseError("只支持 JPG / PNG / WEBP 格式的照片")
    try:
        raw = _b64decode(m.group(2))
    except Exception:
        raise DiagnoseError("图片读取失败，请重新拍一张")
    if not raw:
        raise DiagnoseError("图片是空的，请重新拍一张")
    if len(raw) > MAX_IMG_BYTES:
        raise DiagnoseError("照片太大，请等图片压缩完成后再试")
    return mime, raw


def _b64decode(s: str) -> bytes:
    import base64
    return base64.b64decode(s + "=" * (-len(s) % 4))


def build_messages(image_uri: str, species: str, note: str, pet_name: str, age: str = "") -> list:
    parts = []
    if species:
        parts.append(f"物种：{species}")
    if pet_name:
        parts.append(f"名字：{pet_name}")
    if age:
        parts.append(f"年龄：{age}")
    if note:
        parts.append(f"主人描述：{note}")
    ctx = "；".join(parts) if parts else "主人没有填写额外信息"
    return [
        {"role": "system", "content": DIAG_PROMPT},
        {"role": "user", "content": [
            {"type": "text", "text": f"这是照片，附带的已知信息：{ctx}。请按要求的 JSON 输出初步判断。"},
            {"type": "image_url", "image_url": {"url": image_uri}},
        ]},
    ]


async def run_vision(image_uri: str, species: str, note: str, pet_name: str,
                     age: str, api_key: str, base_url: str, model: str,
                     timeout: float = 120.0) -> dict:
    """调用 OpenAI 兼容的多模态接口，返回规范化后的清单。"""
    import httpx

    url = base_url.rstrip("/") + "/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": model,
        "messages": build_messages(image_uri, species, note, pet_name, age),
        "temperature": 0.2,
        "max_tokens": 2600,
        "stream": False,
    }
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(timeout, connect=20.0)) as client:
            r = await client.post(url, json=payload, headers=headers)
    except httpx.TimeoutException:
        raise DiagnoseError("看图超时了，换个网络或者稍后再试")
    except Exception as e:  # noqa: BLE001
        raise DiagnoseError(f"连不上模型服务：{e}")

    if r.status_code != 200:
        body = r.text[:300]
        low = body.lower()
        if r.status_code in (400, 422) and ("image" in low or "modality" in low or "vision" in low):
            raise ModelNoVision(body)
        if r.status_code in (400, 404) and "model" in low:
            raise DiagnoseError(f"识图模型 {model} 不可用，请管理员在后台「识图模型」里换一个支持看图的模型")
        if r.status_code in (401, 403):
            raise DiagnoseError("模型 Key 无效或没有权限，请让管理员检查")
        if r.status_code == 429:
            raise DiagnoseError("请求太频繁了，等一分钟再试")
        raise DiagnoseError(f"模型服务返回 {r.status_code}")

    try:
        obj = r.json()
        text = obj["choices"][0]["message"]["content"]
        if isinstance(text, list):
            text = "".join(x.get("text", "") for x in text if isinstance(x, dict))
    except Exception:
        raise DiagnoseError("模型返回的格式看不懂，请重试")

    data = parse_json(text)
    if not data:
        raise DiagnoseError("模型没有给出有效的判断，请换一张更清楚的照片重试")
    out = normalize(data, species)
    out["raw"] = (text or "")[:2000]
    return out
