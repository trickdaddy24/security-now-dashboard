# Contributing

Thanks for helping improve Security Now Dashboard.

## Getting started

```bash
git clone https://github.com/trickdaddy24/security-now-dashboard.git
cd security-now-dashboard
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app:app --reload --port 8787
```

## Pull requests

1. Fork the repo and create a feature branch from `main`.
2. Keep changes focused — one feature or fix per PR.
3. Run the smoke test before opening a PR:

   ```bash
   python test_smoke.py
   ```

4. Update `CHANGELOG.md` under `[Unreleased]` for user-visible changes.
5. Open the PR with a clear description of what changed and why.

## Code style

- Match existing patterns in `grc_downloader/` and `app.py`.
- Prefer small, readable functions over clever one-liners.
- Do not commit downloaded media files or secrets.

## Attribution

This project is a modern fork of the ideas in Seth Leedy's bash downloader. When
borrowing behavior from the upstream script, note the mapping in the PR description.