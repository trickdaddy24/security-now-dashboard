#!/usr/bin/env bash
# Merge Telegram credentials from ~/notifier/.env into .env.production (no quotes).
set -euo pipefail
cd /opt/security-now-dashboard
python3 <<'PY'
import re
from pathlib import Path

def parse_env(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.is_file():
        return out
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        out[key] = val.strip().strip("'").strip('"')
    return out

src = parse_env(Path.home() / "notifier/.env")
prod = Path(".env.production")
lines = prod.read_text().splitlines() if prod.is_file() else []
updates = {
    "SN_TELEGRAM_BOT_TOKEN": src.get("TELEGRAM_BOT_TOKEN", ""),
    "SN_TELEGRAM_CHAT_ID": src.get("TELEGRAM_CHAT_ID", ""),
    "SN_TELEGRAM_ON_JOB_COMPLETE": "1",
    "SN_HEARTBEAT_INTERVAL_HOURS": "6",
}
seen: set[str] = set()
out_lines: list[str] = []
for line in lines:
    if "=" in line:
        key = line.split("=", 1)[0]
        if key in updates:
            out_lines.append(f"{key}={updates[key]}")
            seen.add(key)
            continue
    out_lines.append(line)
for key, val in updates.items():
    if key not in seen:
        out_lines.append(f"{key}={val}")
prod.write_text("\n".join(out_lines) + "\n")
print(f"synced telegram chat_id={updates['SN_TELEGRAM_CHAT_ID']} token_len={len(updates['SN_TELEGRAM_BOT_TOKEN'])}")
PY