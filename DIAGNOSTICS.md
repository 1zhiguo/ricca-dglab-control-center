# Ricca real-device diagnostics

For a portable release, extract the entire ZIP and launch its `Ricca-x-DGlab.exe`.
For a source checkout, use `run_native.ps1` after setup; see [CONTRIBUTING.md](CONTRIBUTING.md).
The developer's `public_repo` folder is a publication mirror, not an installation.
Close the old plugin normally before starting the updated one. Updating does not
unlock emergency stop or send test output. See the [user guide](docs/USAGE.md) for
supported builds, pairing and configuration paths.

## Configuration compatibility

Legacy primary values take precedence: strengths, hard cap, waveform choices,
enabled flags and channel settings are not replaced by a preset. Missing newer
fields can be recovered from an existing valid version-2 backup. An explicitly
incomplete tutorial stays incomplete. A missing tutorial flag is recovered only
when that backup explicitly records completion and the primary has a valid saved
hard cap. With no such evidence, finish the tutorial; no completion is invented.

Loading is read-only. On the next settings save, the migrated version-2 data is
written atomically, and exact pre-migration primary/backup text is preserved as
`settings.json.pre-migration` and `settings.json.bak.pre-migration`. Existing
recovery copies are never overwritten. The custom waveform directory is untouched.

## Logs

`%LOCALAPPDATA%/Ricca-x-DGlab/logs/runtime.jsonl`

Each JSON line includes a timestamp with offset, monotonic clock, process ID,
session and sequence number. Files rotate at 4 MiB with three backups. The bounded
asynchronous writer cannot block the output loop; dropped records and write errors
are reported in the existing connection diagnostics. Demo mode does not create
real-user diagnostic logs. Logs stay local and are not included in public builds.
Dialogue/audio content, QR URLs and pairing identities are not recorded.

- `session.start`: exact source checkout and loaded entry point.
- `config.loaded`: effective cap/strengths, onboarding and migration provenance.
- `death.zero_observed`: zero HP observation, previous HP, actor/scene changes and
  whether a death edge was detected (attach-at-zero does not invent a death).
- `death.detected`: HP death edge, event sequence and trigger blockers.
- `death.scheduled`: the configured per-channel death rule snapshots.
- `defeat.transition`: defeat interaction phase changes.
- `output.gate`: current authorization decision and explicit blocker codes.
- `socket.controller_send`: a controller Socket write, failure or blocked command.
- `socket.phone_forward`: the paired phone Socket write, failure or binding error.
- `socket.feedback`: numeric strength feedback when the phone reports it.
- `socket.resume_deferred`: authorization waits for fresh desired output or the
  outstanding zero/clear barrier; this is not a device timeout.
- `socket.watchdog_timeout`: desired-output age and requested strengths when
  the unchanged 500 ms stall watchdog actually fires.

Scene-resume ordering: pause first clears cached output freshness. Asynchronous
resume waits for zero/clear completion, and older resume tasks cannot release a
newer pause. Authorization cannot precede a fresh output snapshot. If the first
snapshot arrives while resume is pending, it is dropped safely and the next
33 ms UI update may authorize output; no old waveform is replayed. This avoids
the former immediate `output_timeout` on entering a valid scene. True stalls
still latch off and require the user's explicit resume. Silent audio frames are
valid fresh snapshots and do not disable the watchdog or invent a pulse.

A successful Socket write only confirms transport handling, not delivery to the
physical stimulator or a perceptible sensation. Frame records include channel,
hexadecimal waveform frames and a checksum; no pairing IDs are retained.

Reproduce from a living player with the updated plugin already running. Restarting
while HP is already zero does not replay the old death penalty. After a failed test,
keep the log files and note the approximate time; do not clear the UI event list
as a substitute for saving logs. Hard cap, fresh supported reads, phone binding and
emergency stop remain enforced. Ordinary pause is deliberately below death priority.

## Catalogued story/gallery loops

`scene_catalog` in the saved settings is an exact-ID allowlist. Fresh installations
include the 34 IDs collected on October 20: 24 Scene3D and 10 SceneANV entries,
listed in `src/ricca_dglab/scene_catalog.py`. Goblin dialogue entry and its device
loop were confirmed; collection of the others does not imply physical validation.
This is not an exhaustive game list, and existing explicit allowlists are not
silently expanded by software updates.
An empty list disables catalogue auto-matching without removing the legacy
witnessed-defeat path. Unknown scenes are logged, never auto-enrolled.

An active ADV asset matching a listed ID starts the existing per-channel
`defeat_interaction` loop after three fresh valid samples, from the dialogue
onward. Gallery/recollection and attaching inside a listed scene also qualify.
Interactive animation controls are not required. Story engine pause flags alone
do not mute this loop; plugin pause and explicit game-menu pause do. Leaving the
ID, loading, stale/invalid reads or emergency stop block it immediately. Switching
to another listed ID requires three fresh matching samples again.

Loop strength and waveform reuse the user's existing channel rule, respecting
disabled rules/channels and hard cap. Gallery entry never fabricates a death cue.
The large overview button pauses/resumes loops and ordinary output; as previously
requested, death punishment has higher priority than ordinary pause. Use emergency
stop to stop everything.

`scene.observed` logs the active resource path and ID on changes, including unknown
IDs. It records no dialogue. Use these records to document additional scenes,
then add their exact IDs to `scene_catalog` with the plugin closed. Settings saves
retain the catalogue; a read-only launch does not automatically rewrite settings.

## Scene recording UI (3D and ANV)

Open **剧情信号 → 场景记录库**. **记录当前场景** captures a single active scene;
**开启自动收集** records new scene/script/cut combinations while playing. Automatic
collection is off on each launch and does not enable output. It records only
scenes actually visited, not all assets installed with the game. Choice prompts
and candidate strings alone are not valid active scenes.

Records persist independently at `%LOCALAPPDATA%/Ricca-x-DGlab/scenes.json` with
IDs, first/last record times, script paths, cut names and optional notes. No game
dialogue/audio or device pairing information is included. Repeated IDs merge rather
than duplicate. A corrupt existing library is preserved and writing is refused.
The UI's **打开记录目录** locates the JSON for backup or sharing; it is not uploaded.

Use **启用循环** on a recorded row and confirm to add it to the output allowlist.
For the collected October 20 set, use **登记已收集的 34 个场景** on the story page
or **登记 34 个场景** inside the library. This updates the running process and saves
its actual profile, preserving strengths, waves and manual pause. The UI shows the
actual allowlist count, independently of how many records are visible in the library.
This is preferred over editing settings externally, which does not update an already
running process. `config.loaded` logs the loaded list/count; `output.gate` records
the current root, whether it is registered, and the actual list count.
Stopping automatic collection does not stop already-enabled scene output; use the
large pause button or emergency stop. **停用循环** disables that scene even if the
legacy defeat tracker subsequently witnesses a death. Collecting an unlisted scene
never authorizes it. Existing enabled catalogue entries stay enabled when recorded.

The collector and allowlist recognise both `Scene3D_*` and `SceneANV_*`, including
the newly observed `SceneANV_RiccaClaretMp`. ANV output still requires an enabled
exact ID, valid supported telemetry, fresh samples and the usual device gates.

## Updated fresh-install presets

Default durations now use half-second steps, based on the saved October 20 A/B
strategy (e.g. 2.1 → 2.0, 2.4 → 2.5). A uses both HP/action, 1/2/2.5 second damage
tiers, bouncy sustained struggle, and the new built-in **死亡惩罚·渐强** waveform
(the user's 16-point, 72 Hz custom envelope). A scene loop uses low tier, B medium;
B retains its action-oriented strategy. Death cues default to 3 seconds.

These are fresh-install / confirmed-reset defaults, not an automatic rewrite of
saved policies. Existing custom waveform files, exact saved durations/tiers, global
strength levels and device hard cap are retained. The conservative initial hard cap
remains 30; copying a user's waveform never copies their device authorization.

## Custom story Pulse queues

The story page now replaces the large scene-recording card with a per-channel
queue editor. **场景记录** opens the existing library, collection and registration
tools without a permanently expanded card.

In **通道策略 → CG · 剧情循环**, select **自定义队列 → 剧情（保存并跳转）**.
This explicitly saves that channel's strategy and opens its queue editor. Ordinary
wave choices still use the original single-wave loop; their saved waveform is
retained when switching to/from queue playback. Existing users default to single
wave playback and are never silently opted into queues.

Each A/B queue has 1–16 steps, independently saved in `story_queues` in settings.
Each step selects a waveform (including saved custom waves or silent rest), a tier
or custom 0–100 intensity, and 0.5–30 seconds. The editor's time slider uses half
seconds. Steps can be added, removed or reordered. **保存并应用** persists the queue
and chosen playback mode, restarting that channel's queue from its first step;
unsaved edits do not affect the running output. Failed saves leave the prior plan
and clock intact. A disabled channel/CG rule remains disabled.

Once a registered scene is confirmed, queues repeat from the beginning after the
last step. Plugin pause, explicit game-menu pause, blocked device state, stale reads
or higher-priority death cues freeze their clocks. They never catch up through a
long telemetry gap. Leaving/re-entering a scene restarts the queue; changing script
or dialogue within the same root does not. A rest step forces that channel to zero
instead of falling through to audio. Missing custom-wave files also produce silence.
Strength is still clamped by the hard cap after the existing armor multiplier.
No queue bypasses emergency stop, binding, build verification or fresh-read gates.

`story.queue_saved` logs plan saves; `story.queue_step` logs active/step transitions,
including missing-wave silence. The editor shows the current step and remaining
seconds. Queue clocks and step tokens reset waveform phase at boundaries so an old
wave cannot carry over as a queued multi-frame burst. This does not constitute a
physical-device delivery acknowledgement.

## Default A/B roles and audio-modulated story queues

Fresh-install and confirmed-reset defaults are **A = HP + action**, **B = action /
story audio queue** (`action_audio`). Existing explicit channel modes, strengths,
waveforms and caps are not overwritten by an update. To adopt only B's new role,
select **动作＋剧情音频队列** in its strategy; to adopt both defaults, confirm the
workbench's reset. Reset does not change the audio master switch or hard cap.

In gameplay, hybrid B accepts action/capture feedback but ignores audio entirely.
In valid ADV/ATD/ANV stories, its action feedback is replaced by audio-modulated
playback of the selected B story queue. This path requires a real ADV asset but
does not depend on an HP edge or the defeat-scene catalogue; menu choices that
remain gameplay/other do not qualify. Stage loading, invalid builds and stale
telemetry remain blocked. Existing independent A CG rules are unchanged.

The queue determines waveform, order, time and per-step base intensity. RMS audio
is converted to a noise-gated, sensitivity-adjusted, smoothed factor in 0–1; it
does not create waveform frames or change the queue's frequency/timing. The safe
step base is multiplied by this factor, then by the usual armor multiplier, and
finally clipped to the hard cap. Below the noise gate output is zero, but fresh
silent samples keep the queue timeline moving. Audio older than 350 ms, master
off, explicit user pause or a higher-priority death cue freezes the queue and
stops this audio output. Entering a story clears previous battle/menu audio and
waits for a new sample. Automatic story-engine pause flags alone do not block a
valid hybrid story; explicit plugin/game-menu pause does.

Disabling the custom queue on a hybrid channel uses its saved single-wave loop
with the same audio intensity modulation, not an unmodulated fallback. Disabling
the underlying CG loop rule silences it. Old pure-audio (`audio`) envelope mode is
retained for compatibility. The master audio capture switch remains off by default;
no update opens a microphone or enables listening automatically.

The audio page previews the queue waveform and effective audio-channel intensity,
and links to B's story queue editor. System loopback contains BGM, sound effects
and other applications, not isolated character voice. This implementation does
not identify speech, speakers or particular vocalisations, or record raw audio.

## Unified capture hold and death cue

`struggle` is the single configurable continuous-capture rule: no duration,
valid capture telemetry renews it until escape, pause, or invalid/stale reads.
`capture_start` remains a diagnostic event, not a separate timed pulse. Old-only
capture-start settings migrate to the hold; explicit hold settings win.

Death (`player_down`) accepts 0.1–10 seconds and armor-break feedback accepts
0.1–5 seconds. Other timed events remain 0.1–3 seconds. Existing saved durations,
waveforms, strengths and hard caps are retained, not automatically increased.
The separate `defeat_scene_enter` penalty rule and its scene-entry timer are
removed. Old-only entry-penalty settings migrate to death; an explicit death rule
wins when both exist. Scene-entry diagnostic events still use the same event name.

A validated positive-to-zero HP edge schedules one death cue, including across
CG transitions and ordinary pause; emergency stop and device/read/build/cap
safety gates still apply. Gallery entry alone never manufactures a death cue.
After it finishes, A's independently enabled CG wave/queue and B's configured
audio-modulated queue resume. Channel mode `off` disables that channel entirely.

## Independent per-channel story strategy

Each channel can save an explicit `story_mode`: `fixed`, `queue`, `audio`,
`fixed_audio`, `queue_audio`, or `off`. Battle `mode` is not changed by this
choice. Fixed repeats the rule's saved waveform/intensity; queue repeats its
saved segment plan. Audio generates live envelope frames, bounded by the rule's
intensity and hard cap. The two combined modes modulate the fixed/queue base
intensity by audio level (multiply, never add). Audio off/stale/below gate means
silence, not fallback to an unmodulated fixed/queue pulse.

Explicit story-off leaves battle feedback and the independent death rule intact;
channel-wide `mode=off` still disables everything. Old profiles without
`story_mode` retain legacy inference from mode and playback until edited.
Saving a queue switches fixed/queue selection while retaining audio modulation.
No update enables audio capture, device binding, or output permissions.

The battle-source picker no longer exposes legacy audio or action/audio choices.
Opening those profiles maps their battle draft to `none` or `action`, respectively,
and retains their inferred/explicit story audio strategy; disk settings change
only on save. `none` stops ordinary HP/action/capture feedback, not the independent
story or death rule. Channel-wide `off` remains a full stop.

Battle filters are display-only: HP = damage bands; action = hit/knockdown/wall/
capture rules; high-intensity punishment = death and armor break. They do not
change tiers, intensities, enabled switches, or the draft/persisted settings.

## Native UI resource smoke test

Run `tests/measure_performance.py --seconds-per-phase 12` with `src` on PYTHONPATH.
It uses temporary configuration/logs, disables the real telemetry worker, never
starts Socket/audio capture, and uses a non-recording no-op bridge. Telemetry,
audio levels and device eligibility are synthetic. The six phases cover offline
idle, hits, continuous capture, story audio queues, fast page/dialog switching,
and idle recovery. Output goes to `artifacts/performance-ui.json`; the avatar
overview screenshot is `artifacts/rounded-avatar-overview.png`.

The report distinguishes CPU percentage of one logical core from percentage of
the whole machine, and resident working set from committed private memory. GUI
heartbeat lateness is not render FPS or physical-device latency. Capture/combat/
story phases assert that simulated previews actually become nonzero. Queue size,
log errors/drops, UI heartbeat gaps and backend-drain times are also recorded.

The pre-memory-optimization 2026-10-20 77-second smoke test on this 32-logical-CPU host averaged
0.22% CPU offline, 2.53% in synthetic combat, 0.97% captured, 2.22% with story
audio, and 3.09% during rapid switching. Resident memory was roughly 295–377 MiB;
private commit about 1.0–1.1 GiB, dropping after switching stopped. Non-startup
heartbeat gaps peaked at 169 ms; startup reached 356 ms. No crash/hang or growing
message backlog was observed. This is not a long-duration leak proof, a low-end
hardware benchmark, a live game read-path benchmark, or a real Socket/audio/device
integration test. Existing-process passive samples are separately stored locally
in `artifacts/performance-live.json` and are not included in public source.

## Memory optimization (2026-10-20)

Fresh-process layer measurements pinpointed NumPy's OpenBLAS initialization:
private commit rose from 19 MiB after Qt imports to 772 MiB after NumPy, spawning
23 extra threads. SoundCard/backend imports were small by comparison. The audio
module now defaults process-local `OPENBLAS_NUM_THREADS=1` before importing either
library. Explicit environment settings are preserved; system/user environment is
not changed. The audio path uses elementwise RMS/peak/16-bin reductions, not BLAS
matrix multiplication. This does not restrict the game, telemetry or Socket threads.

Guide thumbnails now decode to 320x720 rather than each original 851x1849 image;
the enlarged preview uses 720x1600 and originals remain untouched. Waveform
metadata is cached rather than decoding preset frame amplitudes/frequencies on
every QML notification; custom-library edits, additions and removals invalidate it.
Actual waveform frames, damage rules, safe caps, pause/death arbitration and
75 ms telemetry / 33 ms output / 50 ms audio cadence remain unchanged.

Fresh renderer-settled measurements: private commit 1023 -> 268 MiB (-73.8%),
resident working set 284 -> 264 MiB (-7.2%). Commit is not resident RAM. Most
remaining resident memory is the Qt/native rendering/UI stack, not saved settings
or pulse queues. Synthetic switching can still warm caches to about 334 MiB
resident / 321 MiB private in the final short run.

Serial six-phase comparisons show backend-drain P95 at 12.4 ms in combat,
10.4 ms captured and 7.8 ms in story audio (reference roughly 27-29 ms). Audio
block features and mapped intensities are exactly equal with 1 vs 24 math threads;
250-block probes measured roughly 0.1 ms P95 against the unchanged 50 ms block
period. 146 unit tests plus connection, channel and queue UI checks passed.
No real device delivery timing, multi-hour soak or game-load benchmark is implied.

Reproduce with `tests/profile_memory_layers.py --production --tag optimized`
and `tests/measure_performance.py --seconds-per-phase 12`. Import-layer comparison
uses a fresh process each time; do not preload NumPy before the production audio
module. Local reports: `artifacts/memory-optimization-comparison.json`,
`artifacts/memory-layers-*.json`, `artifacts/performance-ui-memory-optimized.json`.
Restart the Control Center to apply native-library initialization changes;
the running user's process and JSON settings are not modified by these tests.
