# scail2 — agent handoff

Agent-agnostic guide. Any harness that can run shell commands and read files can drive the engine;
`SKILL.md` is the Claude Code reference but the contract below is harness-neutral. Map tool names to
your harness: "run a shell command" = Bash/exec/shell; "read a file" = Read/cat.

## The contract

1. **Read `SKILL.md` first** — it's the craft, not boilerplate. The load-bearing rules:
   - **FIRST-FRAME MATCH (the rule that decides quality).** Best results come when the reference
     person is framed, scaled, and posed like the subject in the driving clip's **first frame**
     (full-body↔full-body, headshot↔headshot, similar pose/position). A big gap → soft/muddy output;
     the model cannot auto-fix it. Extract the first frame (`ffmpeg -i CLIP.mp4 -frames:v 1 first.png`)
     and pick or generate a matched reference.
   - **Two distinct prompts.** `--detect` is the SAM3 detection prompt (WHAT to track in the clip);
     `--describe` is the diffusion prompt (the RESULTING scene, for fidelity). They are not the same.
   - **Don't set sizing/timing** — output aspect, resolution, length, fps, and which background is kept
     are auto-derived from the two inputs. The output is the driver's **exact** length.
   - **Mode = background source.** `replace` keeps the footage's background (swap into a scene);
     `animate` keeps the reference image's background (the clip is only a motion source).
   - **Multi-character** = one composite reference image with all characters laid out left-to-right to
     match the clip's subjects; `--objects N` (max 6).
2. **Prepare inputs.** A driving video and a reference image. For `replace`, the reference is the new
   person to swap in; for `animate`, it's the character to bring to life. Match the first frame (rule 1).
3. **Run** the engine (see below).
4. **Verify before claiming success** — `ffprobe` the output's duration (must equal the driver's) and
   sample frames: the subject follows the driver's motion through to the **end** (no freeze), identity
   holds, the background is the expected one (footage for `replace`, reference for `animate`).

## Run it

```bash
# swap the person in footage with a new one (keeps the footage's background)
python3 scripts/scail2.py replace  --in FOOTAGE.mp4 --with PERSON.png \
    --detect "the man on the left" --describe "a young man dancing in a kitchen"

# a character image performs a clip's motion (keeps the character's background)
python3 scripts/scail2.py animate  --character CHARACTER.png --motion CLIP.mp4
```

- Inputs may be absolute paths (staged into ComfyUI automatically) or filenames already in ComfyUI's `input/`.
- Result lands in `ComfyUI/output/Wan21/<name>.mp4` (printed as `FINAL=`), copied to the delivery dir unless `--no-deliver`.
- Flags: `--detect` (SAM3 prompt), `--describe` (diffusion prompt), `--objects N` (≤6), `--fast` (512p draft; default 704p), `--steps N` (default 4), `--name PREFIX`.
- The engine **auto-detects the ComfyUI install path** from its API. Override via env: `COMFY_URL`, `COMFY_DIR`, `DELIVER_DIR`.
- Exit is non-zero on connection/node/model errors; the message points at `references/setup.md`.

## Requirements

A running ComfyUI (default `http://127.0.0.1:8188`) with the SCAIL-2 models + native SCAIL-2 / SAM3 nodes
+ supporting node packs installed — exact files, folders, and a forward-port note for older ComfyUI are in
`references/setup.md`. `ffmpeg`/`ffprobe` on PATH. Python 3 stdlib only — no pip installs. Budget ~16 GB
VRAM at 512p / ~28 GB at 704p (fp8); free other large models first.

## Boundaries

- The engine submits a render to ComfyUI and post-processes (trim to exact length) the result; it does not
  judge the output media. Always run a separate verification pass (ffprobe + frame sample).
- It cannot fix a mismatched reference (rule 1) — supply one framed/posed like the clip's first frame.
- Not phoneme-accurate lip-sync. It transfers motion (incl. coarse face); for tight talking-head lip-sync,
  pair with a dedicated lip-sync pass.
