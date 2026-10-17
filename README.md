# vendor/lenos — lenOS 1.0.0 for the Nothing Phone (3a)/(3a) Pro

lenOS is a privacy/security-hardened LineageOS 23.2 distribution for the
Nothing Phone (3a) and (3a) Pro (codename `asteroids`). This repository is the
product: the LineageOS source tree stays a **pristine copy of the pinned
upstream branches**, and every lenOS change is carried by a patch file in
`patches/<project>/` (plus a `series` file that lists the patches in order).

Nothing is edited into the tree by hand. The only supported way to build lenOS
is: pin the tree → apply the series with `tools/lenos-patch.py` → build.

## Layout

| Path | What |
|---|---|
| `patches/<alias>/series` | Ordered patch series per upstream project (strict `git apply`, no fuzz) |
| `tools/lenos-patch.py` | Apply/check/reverse patches; `--status` reports applied state |
| `tools/mkpatch.sh` | Turn edits in a pinned project into a patch and restore the tree |
| `tools/lenos_projects.py` | Project path ↔ patch directory mapping shared by the tools |
| `tests/` | Test suite; every patch is applied in a sandbox and asserted against |
| `config/lenos.mk` | lenOS product configuration (packages, RROs, product properties) |
| `config/privapp-permissions-*.xml` | Privileged permission allowlist for the security app |
| `rro/` | Input RROs: NTP fallback, SettingsProvider first-boot defaults, connectivity checks |
| `app/LenosSecurity/` | Companion app for controls the stock Settings UI does not have |
| `docs/features.md` | Feature matrix with status and honest limits |
| `docs/build.md` | Build/flash/verify workflow (VM rules, verification commands) |
| `legacy-patches/` | Earlier 1.0.0-shizuku patches, provenance only — do not apply |
| `integrate.sh`, `lenos-1.0-shizuku.sh`, `LENOS-1.0-BUILD-FLASH-LOCK.md` | Earlier "write into the tree" pipeline; kept for reference, **not** used anymore (its `hardwire.py` lives only in the prior-work drop `/home/otoka/lenos-drop/vendor-lenos/`) |

## Quick start

```bash
WS="/mnt/sda/AI WORKSPACE/lenos-workspace"                    # pinned tree
PY=/tmp/opencode/lenv/bin/python                              # has tree-sitter

# all patches against the pinned tree
$PY vendor/lenos/tools/lenos-patch.py --tree "$WS" --status
$PY vendor/lenos/tools/lenos-patch.py --tree "$WS" --check

# test suite (needs a pristine tree for the series test)
LENOS_WORKSPACE="$WS" LENOS_PYTHON=$PY bash vendor/lenos/tests/run-tests.sh
```

Building: see `docs/build.md`. Flashing/locking rules are binding and live in
`/home/otoka/lenos-drop/BUILD-FLASH-LOCK.md`.

## Design rules

* **Identity stays stock.** Build fingerprint, `ro.product.*` and attestation
  behaviour are untouched; lenOS only adds `ro.lenos.*` properties.
* **Defaults, not mandates.** Privacy hardening is applied as first-boot
  defaults (user-changeable, never rewritten) or as documented toggles. Nothing
  silently weakens encryption, SELinux, verified boot, emergency calling or
  recovery.
* **Fail closed.** Where a privacy default needs a fallback value in code
  (e.g. the DHCP hostname restriction), the fallback is the private setting,
  not the permissive one.
* **No new trust anchors.** Changed endpoints (NTP, connectivity checks) must
  not point at Google; the current choices are documented in `docs/features.md`
  together with their costs.
