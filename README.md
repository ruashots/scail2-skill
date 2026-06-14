# scail2

A dead-simple CLI (and Claude Code / agent skill) for **[SCAIL-2](https://github.com/zai-org/SCAIL-2)** character motion transfer and replacement, driving a local **ComfyUI**. Two commands:

```bash
# swap the person in a clip with a different one (keeps the clip's background)
scail2 replace  --in footage.mp4 --with person.png

# make a character image perform a clip's motion (keeps the character's background)
scail2 animate  --character character.png --motion motion.mp4
```

That's it. Output aspect, resolution, **exact length**, fps, and which background is kept are all **auto-derived from the two inputs** — no dials to set. SCAIL-2 does end-to-end motion transfer via SAM3 colour-mask binding — **no ControlNet, pose skeletons, or depth maps**.

## Why

The community SCAIL-2 ComfyUI workflows expose ~30 knobs that should be *derived*, and they ship a long-video loop that **overshoots the driver and improvises a frozen/garbled tail** (output length ≠ input length). `scail2` wraps the workflow with one job: hand it a video and a person, get back the exact same clip — same length, same background — with a different character.

What it handles for you:
- **Exact output length** — fixes the known length / improvised-tail bug (loop count from the real 76-frame step + frame-exact trim).
- **Output aspect & resolution** — matched to the right source (footage for `replace`, character for `animate`), 704p by default, never upscales a small clip.
- **The two-prompt split** — `--detect` (SAM3: *what to track*) vs `--describe` (the diffusion prompt: *the resulting scene*).
- **Multi-character** — `--objects N` (up to 6), one composite reference.

## Requirements

This is a thin orchestration layer — it needs a working ComfyUI with the SCAIL-2 stack:

- A running **ComfyUI** with a capable GPU (≈16 GB VRAM at 512p, ~28 GB at 704p for the fp8 model; a GGUF build lowers this).
- The **SCAIL-2 models** + **SAM3.1** + supporting models, and the **SCAIL-2 / SAM3 native nodes** plus a few node packs.
- `ffmpeg`/`ffprobe` on PATH; Python 3.

Full, exact setup (every model file, target folder, node pack, and a forward-port note for older ComfyUI) is in **[`references/setup.md`](references/setup.md)**.

## Usage

```bash
python3 scripts/scail2.py replace --in footage.mp4 --with person.png \
    --detect "the man on the left" \
    --describe "a young man in a red jacket dancing in a kitchen"

python3 scripts/scail2.py animate --character character.png --motion dance.mp4
```

| Flag | Default | Meaning |
|---|---|---|
| `--detect "..."` | `"a person"` | SAM3 detection prompt — *what* to track |
| `--describe "..."` | empty | diffusion prompt — describe the *result* (improves fidelity) |
| `--objects N` | `1` | subjects to track (max 6) |
| `--fast` | off (704p) | 512p draft |
| `--steps N` | `4` | sampler steps |

The engine **auto-detects the ComfyUI path** from its API; override with `COMFY_URL`, `COMFY_DIR`, `DELIVER_DIR` if needed.

## The one rule that decides quality

**Match the reference to the driving clip's first frame.** Best results come when the reference person is framed, scaled, and posed like the subject in the clip's **first frame** (full-body↔full-body, headshot↔headshot, similar pose/position). A large gap there yields a soft, muddy result — the model can't auto-fix it. Extract the first frame (`ffmpeg -i clip.mp4 -frames:v 1 first.png`) and pick or generate a matched reference.

More detail — internals, every parameter, the multi-character recipe, and troubleshooting — in **[`references/reference.md`](references/reference.md)**.

## As a Claude Code skill

Drop this folder in your skills directory; `SKILL.md` is the agent entry point. An agent can then run `replace`/`animate` and follow the baked-in rules without prior SCAIL-2 knowledge.

## Credits & license

- **SCAIL-2** by [zai-org](https://github.com/zai-org/SCAIL-2) (the model; Apache-2.0 / MIT weights — commercial use OK).
- Runs on **ComfyUI** with its native SCAIL-2 / SAM3 nodes and community node packs (KJNodes, VideoHelperSuite, Easy-Use, Custom-Scripts).

This wrapper is MIT licensed — see [LICENSE](LICENSE).
