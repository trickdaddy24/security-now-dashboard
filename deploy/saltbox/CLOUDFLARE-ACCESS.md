# Optional: Cloudflare Access in front of Security Now

Use this **in addition to** Authelia if you want a second gate (e.g. allow only your email, or require a device posture check).

## When to use

| Layer | Protects |
|-------|----------|
| **Authelia** (current) | SSO for `*.aaa.stunna.xyz` — already on `sn.aaa.stunna.xyz` |
| **Cloudflare Access** | Extra policy at the Cloudflare edge (good if DNS is proxied) |

Saltbox DNS for `aaa.stunna.xyz` is **DNS-only** (not proxied), so Access only applies if you switch `sn.aaa` to proxied orange-cloud or put Access on `sn.e4z.xyz` health URL (not recommended).

## Setup (Zero Trust dashboard)

1. Open [Cloudflare Zero Trust](https://one.dash.cloudflare.com/) → **Access** → **Applications** → **Add an application**.
2. Type: **Self-hosted**.
3. Application domain: `sn.aaa.stunna.xyz` (or `sn.e4z.xyz` if proxied).
4. Identity provider: your choice (one-time PIN, Google, GitHub, etc.).
5. Policy: **Allow** → include your email (or a group).
6. Save.

## Traefik / Authelia interaction

- With **DNS-only** (current): traffic hits your server directly; Authelia handles auth. Cloudflare Access is **not** in the path unless you proxy the record.
- With **proxied** DNS: enable Access on the hostname, then either:
  - Disable Authelia on that router (Access only), or
  - Keep both (double login — usually overkill).

## Health checks

Public paths without auth (by design):

- `https://sn.e4z.xyz/health`
- `https://sn.aaa.stunna.xyz/health`

Do **not** put Cloudflare Access on those paths if Uptime Kuma should stay unauthenticated.