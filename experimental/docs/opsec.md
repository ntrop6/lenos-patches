# lenOS OPSEC additions

These are lenOS-original controls, not GrapheneOS ports. GrapheneOS is a security-hardened
Android; its defaults assume an adversary with physical access, but it does not ship a metadata
sanitizer, a one-tap radio kill switch, or a screen-off clipboard wipe. lenOS adds these as
separate, opt-in tools so they can be evaluated without changing the 1.0 series.

The design rule is the same as the rest of lenOS: local-only, fail closed, no new trust anchors,
and no silent weakening of verified boot, encryption, SELinux or emergency calling.

## OPS-1 — metadata-scrubbing share target

**Problem.** Sharing a photo or screenshot can leak GPS coordinates, capture time, device model,
software version, thumbnail images, XMP history and original file names. Android's share sheet
hands the receiving app the original bytes unless the sending app sanitizes first.

**Implementation.** `LenosOpsec` registers a share target for `image/*` and `image/*` with
`ACTION_SEND` / `ACTION_SEND_MULTIPLE`. It decodes the image with `ImageDecoder`, re-encodes the
pixels with `Bitmap.compress` into a new cache file with a random UUID name, and shares only that
file through a non-exported `FileProvider` with a one-shot read grant. Re-encoding drops EXIF,
GPS, XMP, ICC and file-name metadata; the output name is unrelated to the source. A copy can also
be saved to `Pictures/lenOS` through MediaStore.

**Limits.**

* Re-encoding is not a cryptographic sanitizer. The source app, MediaStore thumbnails, caches and
  the original file may still contain the metadata. The user must delete the source separately.
* JPEG/WebP quality is recompressed (quality 95). A 4096 px longest-edge cap prevents pathological
  memory use; larger images are downsampled.
* Animated GIF is rejected. HEIF/AVIF is decoded and written as JPEG. PDF and video metadata are
  not handled by this tool.
* The app has no `INTERNET` permission and no network code. It cannot phone home, and it does not
  use a cloud OCR/classification service.

**Verification.** Share a geotagged JPEG; run `exiftool` on the received file and confirm there is
no GPS/EXIF/XMP, that the file name is randomized, and that the image still opens. Repeat with a
multi-select share and with the “save sanitized copy” path.

## OPS-2 — one-tap Offline tile

**Problem.** A user who needs to cut connectivity quickly has to open Settings and toggle airplane
mode, Wi-Fi and Bluetooth separately. Each extra step is a window in which a radio can remain
associated with a network.

**Implementation.** `OfflineTileService` is a Quick Settings `TileService` in `LenosOpsec`. On tap
it turns off Wi-Fi and Bluetooth first, then calls `ConnectivityManager.setAirplaneMode(true)`.
The tile is active when airplane mode is on; tapping again turns airplane mode off and leaves
Wi-Fi/Bluetooth off for the user to re-enable deliberately. If the platform call is denied it
falls back to the `AIRPLANE_MODE_ON` setting plus the protected broadcast, and never crashes the
tile.

**Limits.**

* Airplane mode is an Android/telephony policy, not a hardware power cut. It cannot prove the
  baseband, Wi-Fi or Bluetooth firmware has stopped transmitting. A faraday bag is the only
  physical guarantee.
* NFC is not toggled. Some devices keep NFC available in airplane mode.
* The tile needs the platform certificate for `NETWORK_SETTINGS`, `WRITE_SECURE_SETTINGS` and
  `BLUETOOTH_PRIVILEGED`. It is built into the experimental product only.
* The tile does not erase Wi-Fi history, saved networks, eSIMs or accounts. Use the duress/auto-BFU
  controls for destruction.

**Verification.** On a test device, enable Wi-Fi and Bluetooth, tap the tile, and confirm all
three are off and the tile shows active. Tap again and confirm only airplane mode is off. Repeat
while the screen is locked and while a call is active; observe telephony behavior rather than
assuming.

## OPS-3 — clear clipboard on screen off

**Problem.** Android keeps the primary clip after the screen turns off. A locked device prevents
apps from reading it while locked, but the content survives until the app reads it or AOSP's
one-hour auto-clear timer fires. A user who copies a password, recovery phrase or address and then
puts the phone down leaves that content resident.

**Implementation.** A new `Settings.Secure.CLIPBOARD_CLEAR_ON_SCREEN_OFF` key (per user, default 0)
is read by `ClipboardService` when the protected `ACTION_SCREEN_OFF` broadcast arrives. For every
user who opted in, the service clears each clipboard for that user through the existing internal
clear path, which revokes URI grants and notifies listeners. The switch lives in
**Settings → Security & privacy → More security & privacy → Clipboard privacy**.

**Limits.**

* This is off by default. It is a deliberate user choice, not a forced data-loss policy.
* It clears the system clipboard, not copies kept by apps (clipboard managers, password managers,
  some keyboards) or autofill/IME histories.
* A lock without screen-off (for example, an app calling `lockNow()` while the display stays on)
  does not trigger the wipe. The feature is bound to screen-off because that is the reliable
  system broadcast.
* The AOSP one-hour auto-clear remains in place. A user setting a shorter timer is not part of this
  batch; the screen-off wipe is the OPSEC control.

**Verification.** Enable the switch; copy text, an image URI and a text URI; turn the screen off
and on; confirm `getPrimaryClip` is empty and URI grants are revoked for a test app. Confirm the
setting is per-user and survives a reboot.

## OPS-4 / Secure Paste stage 2 — per-app clipboard read control

**Problem.** The 1.0 Secure Paste control is a single global default. A user who wants to keep
paste working for a trusted password manager or notes app must allow clipboard reads for every
third-party app, or turn the global control off entirely. Android already has a per-app AppOp for
this (`android:read_clipboard`, `OP_READ_CLIPBOARD`), but no Settings surface for it.

**Implementation.** `ClipboardAppAccessSettings` is a Settings-only feature. It enumerates
user-installed apps, shows a switch per package, and writes `MODE_ALLOWED` / `MODE_IGNORED` through
`AppOpsManager.setMode`. `ClipboardService` already checks this AppOp after its focus and
system-service exemptions, so no framework patch, new permission or new AppOp is added. The screen
excludes system apps, updated system apps and disabled packages, and warns when an app shares a UID
with other packages. It is independent of the global Secure Paste switch: the global block wins,
and a per-app allow cannot override it.

**Limits.** Only user-installed apps are offered; blocking system apps or enabled keyboards is not a
supported path because it can break paste. Shared-UID packages share the mode. The screen uses a
simple preference list (no search provider) and is not a cryptographic capability boundary: an app
with a root compromise or a system service can still read what the system exposes. It does not
stop an app from writing to the clipboard.

## OPS-5 — tracking-parameter scrubber for shared text

**Problem.** Sharing a link often shares the sender's campaign source, ad click ID, referrer and
other tracking parameters. The receiving app can correlate the share with an advertising profile
even when the URL itself looks ordinary.

**Implementation.** `ScrubTextActivity` registers a `text/plain` share target in `LenosOpsec`. It
extracts `http`/`https` URLs with a local regex, removes known tracking parameters while preserving
the path, non-tracking query parameters and fragment, and lets the user inspect the result before
sharing or copying it. The parameter list is conservative: `utm_*`, `pk_*`, `mtm_*`, `hsa_*`,
`vero_*`, `oly_*`, `fbclid`, `gclid`, `dclid`, `msclkid`, `yclid`, `twclid`, `igshid`, `mc_cid`,
`mc_eid`, `_ga`, `_gl`, `gclsrc`, `srsltid`, `gad_source`, `wbraid`, `gbraid`, `mkt_tok`,
`elqTrackId`, `elqTrack`, `sc_cid`, `si`, and referrer fields. Links are never opened, resolved or
sent to a service.

**Limits.** This is not a URL safety scanner. It does not detect phishing, shortened-link targets,
tracking encoded in path segments or fragments, or unique identifiers in the remaining functional
parameters. It preserves parameters such as `source` and search queries because they may be needed
for the link to work. A site can still fingerprint the browser after the link is opened. The user
must review the cleaned text before sharing.

**Verification.** Share a URL containing `utm_source`, `fbclid`, `gclid`, a functional `id` and a
fragment; confirm only the tracking parameters are removed and the function/fragment survive.
Repeat with multiple URLs and plain text without links. Confirm the app has no network permission
and that “Copy cleaned text” produces the same string.

## Future OPSEC backlog (not implemented)

| Idea | Why it is not in this batch |
|---|---|
| Tor-only / Orbot routing | Requires an external Tor daemon/VpnService and a product decision about supported apps; not a source-only framework patch |
| Screenshot redaction / secure-screen automation | Needs a per-app policy and window-manager coordination; high risk of breaking banking/DRM apps |
| File timestamp and filesystem metadata scrubbing | Needs a privileged file manager and careful handling of media sync; not a share-sheet-sized feature |
| Panic destruction beyond duress/auto-BFU | Already covered by the 1.0 duress credential and auto-BFU timer; a new panic path needs a hardware/UX decision and is dangerous to add without device testing |
| Browser choice and update channel | Product decision; the experimental series deliberately ships no browser |

## Threat model summary

These controls are aimed at:

* a device that is about to be handed to another person or left unattended;
* metadata leakage when sharing media;
* radio persistence after the user believes connectivity is off;
* clipboard remnants after the user copies a secret.

They do **not** defend against a compromised OS, a malicious app with root, a hardware implant, or
an adversary who can image the storage before the wipe. They are not a substitute for verified
boot, full-disk encryption, the duress credential, or the auto-BFU timer.
