#!/usr/bin/env bash
# Move flat sn-XXXX.* files into sn-XXXX/ subfolders (one folder per episode).
set -euo pipefail
ROOT="${1:-/mnt/local/Media/grc}"
cd "$ROOT"
shopt -s nullglob
for f in sn-*; do
  [[ -f "$f" ]] || continue
  [[ "$f" == sn-*.meta.json ]] && ep="${f#sn-}" && ep="${ep%.meta.json}" || true
  if [[ "$f" =~ ^sn-([0-9]{4}) ]]; then
    ep="${BASH_REMATCH[1]}"
    dir="sn-${ep}"
    mkdir -p "$dir"
    if [[ ! -e "$dir/$f" ]]; then
      mv "$f" "$dir/"
      echo "moved $f -> $dir/"
    fi
  fi
done
echo "migrate_ok"