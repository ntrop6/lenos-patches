# vendor/lenos — lenOS 1.0.0 for the Nothing Phone (3a)/(3a) Pro

lenOS is a privacy/security-hardened LineageOS 23.2 distribution for the
Nothing Phone (3a) and (3a) Pro (codename `asteroids`). This repository is the
product: the LineageOS source tree stays a **pristine copy of the pinned
upstream branches**, and every stable lenOS change is carried by a patch file
in `patches/<project>/` (plus a `series` file that lists the patches in order).
The opt-in experimental series uses the separate `patches-experimental/` root;
its app source lives in `experimental/app/` and is never installed by a default
build.

Nothing is edited into the tree by hand. The only supported way to build lenOS
is: pin the tree → apply the series with `tools/lenos-patch.py` → build.

## Layout

| Path | What |
|---|---|
| `patches/<alias>/series` | Stable 1.0 patch series per upstream project (strict `git apply`, no fuzz) |
| `patches-experimental/<alias>/series` | Opt-in experimental series, applied only **after** `patches/` |
| `experimental/` | Experimental app source, docs, tests and status; never built by default |
| `tools/lenos-patch.py` | Apply/check/reverse/reset patches; `--experimental` selects the opt-in series |
| `tools/mkpatch.sh` | Turn edits in a pinned project into a patch and restore the tree |
| `tools/lenos_projects.py` | Project path ↔ patch directory mapping shared by the tools |
| `tests/` | Test suite; every patch is applied in a sandbox and asserted against |
| `config/lenos.mk` | lenOS product configuration (packages, RROs, product properties) |
| `config/lenos-experimental.mk` | Experimental product fragment, inherited only with `LENOS_EXPERIMENTAL=1` |
| `config/privapp-permissions-*.xml` | Privileged permission allowlist for the security app |
| `rro/` | Input RROs: NTP fallback, SettingsProvider first-boot defaults, connectivity checks |
| `app/LenosSecurity/` | Companion app for controls the stock Settings UI does not have |
| `docs/features.md` | Feature matrix with status and honest limits |
| `docs/experimental.md` | Experimental build flag, apply order, reset and verification workflow |
| `docs/build.md` | Build/flash/verify workflow (VM rules, verification commands) |
| `lenos-1.0-shizuku.sh` | VM driver: `apply` (patchkit) / `build` / `package` / `extract` / `flash-plan` / `lock-gates` |
| `legacy-patches/` | Earlier 1.0.0-shizuku patches, provenance only — do not apply |
| `integrate.sh`, `config/hardwire.py`, `config/lenos.prop`, `LENOS-1.0-BUILD-FLASH-LOCK.md` | Earlier 1.0.0-shizuku "write into the tree" pipeline; kept for reference, **not** used anymore |

## Quick start

```bash
WS="/mnt/sda/AI WORKSPACE/lenos-workspace"                    # pinned tree
PY=/tmp/opencode/lenv/bin/python                              # has tree-sitter

# all patches against the pinned tree
$PY vendor/lenos/tools/lenos-patch.py --tree "$WS" --status
$PY vendor/lenos/tools/lenos-patch.py --tree "$WS" --check

# undo an applied series (restores tracked files, deletes files it created)
$PY vendor/lenos/tools/lenos-patch.py --tree "$WS" --reset

# test suite (needs a pristine tree for the series test)
LENOS_WORKSPACE="$WS" LENOS_PYTHON=$PY bash vendor/lenos/tests/run-tests.sh

# opt-in experimental series (stable first, then experimental; installs LenosOpsec)
LENOS_EXPERIMENTAL=1 ./vendor/lenos/lenos-1.0-shizuku.sh apply
# source-level experimental tests, with the stable base rebuilt in each sandbox
cd vendor/lenos/experimental/tests
LENOS_WORKSPACE="$WS" LENOS_PYTHON=$PY ./run-tests.sh
```

Building: see `docs/build.md`. Flashing/locking rules are binding and live in
`/home/otoka/lenos-drop/BUILD-FLASH-LOCK.md`.

## Experimental series (opt-in, not 1.0)

Implementations that are source-complete but **cannot be built or device-validated** in the
current environment are imported here under `patches-experimental/` and `experimental/`. They are
not part of the default 1.0 product: a normal `apply`/`build` never applies them, and
`LenosOpsec` is not built. They are selected explicitly with `LENOS_EXPERIMENTAL=1`:

```bash
LENOS_EXPERIMENTAL=1 ./lenos-1.0-shizuku.sh apply
LENOS_EXPERIMENTAL=1 ./lenos-1.0-shizuku.sh build
LENOS_EXPERIMENTAL=1 mka bacon        # only if applying/building manually
```

The experimental patches apply **after** the stable series and carry the fs-verity/system-app
update hardening (#20/#21), the screenshot-sound fix (#25), USB-C data-line control (#22), the
on-device crash/ANR viewer (#17), the Setup Wizard unlocked-bootloader warning (#28), the
Seedvault GrapheneOS-prefix port (#27), a global opt-in native-debugging block (partial
#23/ENF-1), and the original OPSEC tools (metadata-scrubbing image share target / text scrubber,
Offline radio tile, opt-in screen-off clipboard wipe, and per-app clipboard access via the
existing AOSP AppOp). The OPSEC app is `experimental/app/LenosOpsec`; its threat model is
[`experimental/docs/opsec.md`](experimental/docs/opsec.md). `experimental/STATUS.md`,
[`experimental/docs/security-review.md`](experimental/docs/security-review.md) and
[`experimental/docs/verification.md`](experimental/docs/verification.md) record what is
static-only. The build flag and reset semantics are in
[`docs/experimental.md`](docs/experimental.md).

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
