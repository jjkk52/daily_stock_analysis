#!/usr/bin/env python3
"""把「每日股票分析」产出的决策仪表盘推送到 MeoW（喵提醒）。

独立脚本，供 .github/workflows/meow-notify.yml 调用。
接口：POST https://api.chuckfang.com/<喵码>?msgType=text  body={"title":..,"msg":..}
限流：3 秒 1 条 / 15 条每分钟 / 60 条每小时 —— 本脚本每次运行只发 1 条。

推送内容优先取「决策仪表盘」的摘要块 + 每只股票的一句话决策，
拿不到仪表盘时退化为报告正文前 N 字。
设 DRY_RUN=1 只打印不发送，便于本地调试。
"""
from __future__ import annotations

import glob
import json
import os
import re
import sys
import urllib.parse
import urllib.request

BASE = os.environ.get("MEOW_BASE_URL", "https://api.chuckfang.com").rstrip("/")
NICKNAME = os.environ.get("MEOW_NICKNAME", "").strip()
MAX_CHARS = int(os.environ.get("MEOW_MAX_CHARS", "1800"))
CONCLUSION = os.environ.get("RUN_CONCLUSION", "")
RUN_URL = os.environ.get("RUN_URL", "")
DRY_RUN = os.environ.get("DRY_RUN", "").lower() in ("1", "true", "yes")

# 报告文件优先级关键字（命中越靠前越优先）
PRIORITY = ("dashboard", "仪表盘", "决策", "summary", "摘要", "report", "报告")

STOCK_HEADING = re.compile(r"^##\s+([🟢🟡🟠🔴⚪🔵][^\n]*)$", re.M)
ONE_LINER = re.compile(r"\*\*一句话决策\*\*[:：]\s*(.+)")


def pick_report() -> str:
    files = [
        p
        for p in glob.glob("artifacts/**/reports/**/*", recursive=True)
        if os.path.isfile(p) and os.path.getsize(p) > 0
    ]
    if not files:
        return ""

    def score(path: str) -> int:
        name = os.path.basename(path).lower()
        for idx, key in enumerate(PRIORITY):
            if key in name:
                return idx
        return len(PRIORITY)

    files.sort(key=lambda p: (score(p), -os.path.getsize(p), p))
    with open(files[0], encoding="utf-8", errors="ignore") as fh:
        return fh.read()


def build_message(text: str) -> tuple[str, str]:
    """返回 (标题, 正文)。"""
    text = re.sub(r"\r\n?", "\n", text).strip()

    if "决策仪表盘" not in text:
        # 非仪表盘报告：直接取正文
        body = re.sub(r"\n{3,}", "\n\n", text).strip()
        head = next((ln.strip() for ln in body.splitlines() if ln.strip()), "")
        head = re.sub(r"^[#>*\-\s]+", "", head)[:48]
        return (f"股票日报 {head}".strip() if head else "股票日报"), body

    # 1) 仪表盘摘要块：从 "# ... 决策仪表盘" 到第一条分隔线
    m = re.search(r"^#\s.*?决策仪表盘.*?(?=\n---\s*\n)", text, re.S | re.M)
    summary = m.group(0).strip() if m else ""

    # 2) 每只股票的一句话决策
    names = [n.strip() for n in STOCK_HEADING.findall(text)]
    decisions = [d.strip() for d in ONE_LINER.findall(text)]

    points = []
    if names and len(names) == len(decisions):
        for name, dec in zip(names, decisions):
            points.append(f"{name}：{dec}")
    elif decisions:
        points = decisions

    if points:
        body = summary + "\n\n💡 决策要点\n" + "\n".join(f"· {p}" for p in points)
    else:
        body = summary or re.sub(r"\n{3,}", "\n\n", text)

    body = re.sub(r"\n{3,}", "\n\n", body).strip()

    # 标题取仪表盘第一行，如「🎯 2026-10-22 决策仪表盘」
    title = "股票日报"
    first = next((ln for ln in summary.splitlines() if ln.strip()), "")
    if first:
        cleaned = re.sub(r"^[#\s]+", "", first).strip()
        if cleaned:
            title = cleaned
    return title, body


def main() -> int:
    if not NICKNAME:
        print("MEOW_NICKNAME 未配置，跳过推送")
        return 0

    raw = pick_report()
    if raw.strip():
        title, body = build_message(raw)
    else:
        title = "股票分析未产出报告"
        body = f"运行结论: {CONCLUSION or 'unknown'}\n详情: {RUN_URL}"

    title = title[:64]
    if len(body) > MAX_CHARS:
        body = body[:MAX_CHARS] + "\n…(已截断，完整版见 Actions 产物)"

    print(f"标题: {title}")
    print(f"正文长度: {len(body)}")
    if DRY_RUN:
        print("--- DRY RUN ---")
        print(body)
        return 0

    payload = json.dumps({"title": title, "msg": body}, ensure_ascii=False).encode("utf-8")
    url = f"{BASE}/{urllib.parse.quote(NICKNAME)}?msgType=text"
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json", "User-Agent": "dsa-github-actions"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            print("MeoW 响应:", resp.status, resp.read().decode("utf-8", "ignore")[:300])
    except Exception as exc:  # noqa: BLE001
        print("MeoW 推送失败:", exc)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
