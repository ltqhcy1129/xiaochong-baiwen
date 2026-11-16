# -*- coding: utf-8 -*-
"""数据快照与自愈。

解决的问题：账号、后台配置、用户反馈这类「无法重建」的数据，一旦因为重新部署、
误删、写坏文件而丢失，用户就得重新注册，后台密码也会被重置回默认值。

做法：
1. 每次关键数据变更后，节流生成快照（默认 10 分钟内最多一次）；
2. 同时写入项目内 data/backups 与项目外 ../xc_data_backups 两处，
   即使整个项目目录被覆盖，项目外那份仍然保留；
3. 启动时若主文件缺失或为空，自动从最近一份快照恢复；
4. 快照只保留最近 MAX_SNAPSHOTS 份，避免无限增长。
"""
import json
import shutil
import threading
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
BACKUP_DIRS = [DATA_DIR / "backups", BASE_DIR.parent / "xc_data_backups"]

# 需要保护的数据文件：丢了就得重来
CRITICAL_FILES = ["accounts.json", "config.json", "feedback.json", "pets.json", "carelog.json", "petlogs.json", "diagnoses.json"]

# 这些文件「内容为空」是合法状态（用户可能主动删光档案/记录/诊断），不能拿旧快照盖回去，
# 否则会出现「我明明删了，重启又冒出来」这种最伤信任的事
ALLOW_EMPTY = {"pets.json", "carelog.json", "petlogs.json", "diagnoses.json"}

SNAPSHOT_GAP = 600       # 两次快照最小间隔（秒）
MAX_SNAPSHOTS = 40       # 每个目录保留的快照份数

_lock = threading.Lock()
_last_snapshot = 0.0


def _stamp(ts: float = 0) -> str:
    return time.strftime("%Y%m%d-%H%M%S", time.localtime(ts or time.time()))


def _iter_snapshots(backup_dir: Path):
    """按时间倒序列出某目录下的快照文件夹。"""
    if not backup_dir.exists():
        return []
    items = [p for p in backup_dir.iterdir() if p.is_dir()]
    items.sort(key=lambda p: p.name, reverse=True)
    return items


def _prune(backup_dir: Path) -> None:
    for old in _iter_snapshots(backup_dir)[MAX_SNAPSHOTS:]:
        try:
            shutil.rmtree(old, ignore_errors=True)
        except Exception:
            pass


def snapshot(force: bool = False) -> str:
    """生成一份快照，返回快照名（失败返回空串）。异常全程静默。"""
    global _last_snapshot
    now = time.time()
    with _lock:
        if not force and (now - _last_snapshot) < SNAPSHOT_GAP:
            return ""
        _last_snapshot = now

        name = _stamp(now)
        saved = 0
        for bdir in BACKUP_DIRS:
            try:
                target = bdir / name
                target.mkdir(parents=True, exist_ok=True)
                for fn in CRITICAL_FILES:
                    src = DATA_DIR / fn
                    if src.exists() and src.stat().st_size > 2:
                        shutil.copy2(src, target / fn)
                        saved += 1
                _prune(bdir)
            except Exception:
                continue
        return name if saved else ""


def _needs_restore(fn: str, path: Path) -> bool:
    """判断主文件是否真的需要从快照恢复。

    只在「文件不存在」或「内容坏了读不出来」时恢复。文件存在且是合法的空数组，
    说明用户就是删光了，属于正常状态——早期版本把空数组也当成丢失，
    结果用户删完记录、服务一重启，删掉的东西又回来了。
    """
    if not path.exists():
        return True
    try:
        raw = path.read_text(encoding="utf-8").strip()
    except Exception:
        return True
    if not raw:
        return fn not in ALLOW_EMPTY
    try:
        data = json.loads(raw)
    except Exception:
        return True
    if fn in ALLOW_EMPTY:
        return False
    return data in ({}, [])


def restore_missing() -> dict:
    """主文件缺失/损坏时，从最近的快照恢复。返回 {文件名: 来源快照名}。"""
    restored = {}
    for fn in CRITICAL_FILES:
        main = DATA_DIR / fn
        if not _needs_restore(fn, main):
            continue
        # 项目外优先（更不容易被部署覆盖），再退回项目内
        for bdir in reversed(BACKUP_DIRS):
            for snap in _iter_snapshots(bdir):
                cand = snap / fn
                # 取最近一份「包含该文件」的快照即可。跳过空的候选会让人退回到更早的旧数据，
                # 反而把用户已经删掉的内容带回来。
                if not cand.exists():
                    continue
                try:
                    DATA_DIR.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(cand, main)
                    restored[fn] = snap.name
                    break
                except Exception:
                    continue
            if fn in restored:
                break
    return restored


def status() -> dict:
    """给后台展示：各文件的当前大小、最新快照时间与份数。"""
    files = {}
    for fn in CRITICAL_FILES:
        p = DATA_DIR / fn
        files[fn] = p.stat().st_size if p.exists() else 0
    latest, count = "", 0
    for bdir in BACKUP_DIRS:
        snaps = _iter_snapshots(bdir)
        if snaps:
            count = max(count, len(snaps))
            if not latest or snaps[0].name > latest:
                latest = snaps[0].name
    return {"files": files, "latest": latest, "count": count,
            "dirs": [str(d) for d in BACKUP_DIRS]}
