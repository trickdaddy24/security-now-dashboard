#!/usr/bin/env bash
set -euo pipefail
base="https://pscrb.fm/rss/p/mgln.ai/e/294/cdn.twit.tv/video/sn"
for ep in 1086 1080; do
  for suffix in h264m_1920x1080 h264m_1280x720 h264m_640x360 hq hd lq; do
    url="${base}/sn${ep}/sn${ep}_${suffix}.mp4"
    code=$(curl -sI -L "$url" -o /dev/null -w "%{http_code}")
    echo "sn${ep}_${suffix}: $code"
  done
done