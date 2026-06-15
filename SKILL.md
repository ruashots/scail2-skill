---
name: scail2
description: Replace or animate a person/character in a video using SCAIL-2 (local, ComfyUI). Use when asked to swap/replace the person or actor in a clip with a different one, put a character into existing footage, animate a still character with a driving motion clip, or transfer motion from one video onto a character — keeping length and background intact. Two subcommands — `replace` (swap the person in footage, keep its background) and `animate` (a character image performs a clip's motion, keep the character's background). No ControlNet/pose/depth. Drives a local ComfyUI instance with the SCAIL-2 stack installed.
---

# scail2 — character motion transfer & replacement (SCAIL-2)

SCAIL-2 transfers the motion of a driving video onto a character, end-to-end (SAM3 mask-binding — no pose skeletons, ControlNet, or depth maps). One engine, two subcommands:

| Subcommand | You give it | You get | Background kept from |
|---|---|---|---|
| **`replace`** | existing **footage** + a new **person** | the footage with the person swapped, same motion/scene | the **footage** |
| **`animate`** | a **character** image + a **motion** clip | the character performing that motion | the **character** image |

Use `replace` for "put this person into this clip / swap the actor". Use `animate` for "make this character do this dance / move like this clip".

## Run it

```bash
python3 scripts/scail2.py replace  --in FOOTAGE.mp4 --with PERSON.png   [opts]
python3 scripts/scail2.py animate  --character CHAR.png --motion CLIP.mp4 [opts]
```

Inputs may be absolute paths (staged into ComfyUI automatically) or filenames already in ComfyUI's `input/`. The result lands in `ComfyUI/output/Wan21/<name>.mp4` (path printed as `FINAL=`) and is copied to the delivery dir unless `--no-deliver`.

**Everything below is auto-derived from the two inputs — do not set them manually:** output aspect, resolution, length, fps, and which background is kept. The output is the **exact length** of the driver, no filler.

### Options

| Flag | Default | What it does |
|---|---|---|
| `--detect "..."` | `"a person"` | **SAM3 detection prompt** — what to track in the clip (e.g. `"the man on the left"`, `"two boxers"`). Steers *which* subject(s) get the motion. |
| `--describe "..."` | empty | **Wan-T5 quality prompt** — describe the *resulting* scene (e.g. `"a young man dancing in a kitchen"`). Improves fidelity; optional but recommended for `replace`. |
| `--objects N` | `1` | How many subjects to track. Set to the number of characters. **Hard ceiling 6** (mask palette). |
| `--fast` | off (704p) | Render at 512p draft instead of the 704p default. |
| `--steps N` | `4` | Sampler steps. 4 is the lightx2v sweet spot; more rarely helps. |
| `--name PREFIX` | `scail2_<mode>` | Output filename prefix. |

## The rules that decide quality — read before running

1. **FIRST-FRAME MATCH (the #1 rule — both modes).** Results are best when the reference person is **framed and posed like the subject in the driving clip's FIRST FRAME** — same scale (full-body↔full-body, headshot↔headshot), same rough position/pose. For `replace`, match the **person being swapped out**; for `animate`, match the **motion subject's frame-1 pose** (so the motion starts cleanly instead of snapping). A big gap at frame 1 = a soft, muddy result. The engine warns on gross aspect mismatch but cannot fix framing — supply a matched reference: extract the first frame (`ffmpeg -i CLIP.mp4 -frames:v 1 first.png`) and pick/generate a reference matched to it (the `ideogram4` skill can generate a pose/framing-matched reference).
2. **Two different prompts.** `--detect` (SAM3) decides *who/what to track*; `--describe` (Wan-T5) describes *the output scene* for fidelity. They are separate — don't conflate them.
3. **Quality = 704p (default).** 512p (`--fast`) is visibly softer; use it only for quick drafts.
4. **Multi-character:** one **single composite reference image** containing all characters, positioned left-to-right to match the clip's subjects; set `--objects N` and a `--detect` prompt that names them (e.g. `"the two men"`). Max 6 identities. See `references/reference.md`.
5. **Background:** `replace` keeps the *footage's* background (composites the new character in); `animate` keeps the *reference image's* background (the clip is only a motion source).

## How it works (so results are reproducible)

Per chunk of 81 frames (76-frame step): SAM3 tracks the requested subject(s) in both the reference and the driver → `SCAIL2ColoredMask` paints each identity a fixed colour on both sides → `WanSCAILToVideo` binds driver-colour-K's motion to reference-colour-K. Clips longer than 81 frames loop with colour-palette carry-over for consistency. The engine sets output fps and frame-trims so the result is the driver's **exact** length with no improvised tail (a known SCAIL-2 length bug, handled here).

## Verify a result

Sample frames (or use the `watch-video` skill) and confirm: the subject follows the driver's motion through to the **end** (no freeze), identity holds, the background is the expected one, and the duration matches the driver.

## Requirements & setup

Needs a running ComfyUI (default `http://127.0.0.1:8188`) with the SCAIL-2 models + native mask nodes + SAM3 + supporting nodes installed. If a run errors with a missing node/model, or you're setting up on a fresh ComfyUI → **`references/setup.md`** (exact model files, target folders, and the node availability note). Full parameter/internals/troubleshooting reference → **`references/reference.md`**.

SCAIL-2 is a 14B model — budget roughly 16 GB VRAM at 512p / up to ~28 GB at 704p (fp8; a GGUF build lowers this). Free other large models from VRAM before a run. The engine **auto-detects the ComfyUI install path** from its API; override with env if needed: `COMFY_URL`, `COMFY_DIR`, `DELIVER_DIR` (where `--deliver` copies, default `~/Downloads`).

SCAIL-2 weights are Apache-2.0 / MIT (commercial use OK).
