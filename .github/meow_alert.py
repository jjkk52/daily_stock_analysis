#!/usr/bin/env python3
"""发送一条自定义 MeoW 告警（供同步/巡检类工作流使用）。

环境变量：
  MEOW_NICKNAME  喵码（必填，未配置则静默跳过）
  MEOW_TITLE     标题，默认「GitHub Actions 告警」
  MEOW_MESSAGE   正文
  MEOW_BASE_URL  默认 https://api.chuckfang.com
"""
from __future__ import annotations

import json
import os
import sys
import urllib.parse
import urllib.request

BASE = os.environ.get("MEOW_BASE_URL", "https://api.chuckfang.com").rstrip("/")
NICK = os.environ.get("MEOW_NICKNAME", "").strip()
TITLE = (os.environ.get("MEOW_TITLE") or "GitHub Actions 告警")[:64]
MSG = os.environ.get("MEOW_MESSAGE") or ""

if not NICK:
    print("MEOW_NICKNAME 未配置，跳过告警")
    sys.exit(0)

payload = json.dumps({"title": TITLE, "msg": MSG[:1800]}, ensure_ascii=False).encode("utf-8")
url = f"{BASE}/{urllib.parse.quote(NICK)}?msgType=text"
req = urllib.request.Request(
    url,
    data=payload,
    headers={"Content-Type": "application/json", "User-Agent": "dsa-github-actions"},
    method="POST",
)

try:
    with urllib.request.urlopen(req, timeout=20) as resp:
        print("MeoW 响应:", resp.status, resp.read().decode("utf-8", "ignore")[:200])
except Exception as exc:  # noqa: BLE001
    print("MeoW 告警失败:", exc)
    sys.exit(1)
