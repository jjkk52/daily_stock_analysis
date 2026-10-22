#!/usr/bin/env python3
"""把「每日股票分析」产出的报告推送到 MeoW（喵提醒）。

独立脚本，供 .github/workflows/meow-notify.yml 调用。
接口：POST https://api.chuckfang.com/<喵码>?msgType=text  body={"title":..,"msg":..}
限流：3 秒 1 条 / 15 条每分钟 / 60 条每小时 —— 本脚本每次运行只发 1 条。
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

# 报告文件优先级关键字（命中越靠前越优先）
PRIORITY = ("dashboard", "仪表盘", "决策", "summary", "摘要", "report", "报告")


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


def main() -> int:
    if not NICKNAME:
        print("MEOW_NICKNAME 未配置，跳过推送")
        return 0

    text = pick_report()
    text = re.sub(r"\r\n?", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()

    if not text:
        title = "股票分析未产出报告"
        body = f"运行结论: {CONCLUSION or 'unknown'}\n详情: {RUN_URL}"
    else:
        head = next((ln.strip() for ln in text.splitlines() if ln.strip()), "")
        head = re.sub(r"^[#>*\-\s]+", "", head)[:48]
        title = f"股票日报 {head}".strip() if head else "股票日报"
        body = text

    title = title[:64]
    if len(body) > MAX_CHARS:
        body = body[:MAX_CHARS] + "\n…(已截断，完整版见 Actions 产物)"

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
