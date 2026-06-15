# scail2 — reference (internals, parameters, multi-character, troubleshooting)

## Pipeline

SCAIL-2 conditions a Wan-2.1 14B diffusion model on **colour masks** instead of pose skeletons. For each input:

1. **SAM3 tracking** (`SAM3_VideoTrack`, one instance for the driver, one for the reference) detects + tracks the subject(s) named by the `--detect` text prompt. `detection_threshold` (0.3 in the template) gates which detections spawn tracks.
2. **`SCAIL2ColoredMask`** paints each tracked identity a fixed colour (palette order: blue, red, green, magenta, cyan, yellow), applying the **same ordering** (`sort_by=left_to_right`) to both the driver and the reference, so identity K is the same colour on both sides.
3. **`WanSCAILToVideo`** consumes `pose_video` + `pose_video_mask` (driver) and `reference_image` + `reference_image_mask`, and binds driver-colour-K's motion onto reference-colour-K. `replacement_mode` flips the mask background convention: in replacement the reference is matted to its mask (background comes from the driver footage); in animation the whole reference is kept (background comes from the reference).
4. **Long video:** the model works in 81-frame chunks with a 76-frame step (5-frame overlap). Clips longer than 81 frames loop (`easy forLoop`), carrying the previous chunk's colour palette forward to reduce colour drift.

The engine handles all I/O sizing and timing automatically (below).

## How the engine auto-derives everything

- **Aspect** = the background source (footage for `replace`, character image for `animate`). The driver/reference are center-crop-resized to the generation rectangle, so an aspect that doesn't match the background source crops away background → regeneration; matching it preserves the background. This is why `replace` output aspect follows the footage.
- **Resolution** = the driver's short side, snapped to ÷32, capped at 704 (default) or 512 (`--fast`); never upscales a smaller clip. 704 is meaningfully sharper than 512; steps barely affect sharpness.
- **Length / fps / no-filler:** the loop count is `ceil(max(0, a−81)/76)` where `a` = frames the driver loads at 16 fps (the workflow computes this in-graph). The combine fps is set to `a / driver_duration`, then the output is **frame-trimmed to the first `a` frames** — the pose-driven ones. The chunk size is 81 but the last chunk can extend past the driver; those trailing frames have no driving motion and would otherwise improvise/freeze (a known SCAIL-2 length bug). Trimming removes them. Result: output length == driver length, exactly.

## Parameters in depth

- **`--detect` (SAM3 detection prompt).** Open-vocabulary; tells SAM3 *what to segment/track*. Be specific for multi-subject clips: `"the man on the left"`, `"the two boxers"`, `"the dog"`. This is the prompt that most affects *whether the right subject is picked up*.
- **`--describe` (Wan-T5 diffusion prompt).** Describe the *result* (not an instruction): e.g. `"a young man in a red jacket dancing in a kitchen"`. Empty works but a detailed description improves fidelity — recommended for `replace`. (The official CLI ships a Gemini prompt-enhancer for this; here it's manual.)
- **`--objects N`.** Cap on tracked subjects, applied to both the driver and reference tracks. Set to the exact subject count. **Hard ceiling 6** — the mask palette has 6 colours; beyond that, identities share colours and separation collapses.
- **`--steps`.** lightx2v distillation runs at very low steps (cfg 1). 4 is the sweet spot; 6–8 is marginal; high steps don't help and slow things down.
- **`--fast`.** 512p draft. Default (omit) is 704p — use it for finals.

## Multi-character recipe

1. **One composite reference image** containing all N characters, laid out **left-to-right to match their positions in the driving clip's first frame** (the mask ordering is left-to-right on both sides). Generate or compose this single image — there is no per-character reference input.
2. `--objects N` and a `--detect` prompt naming the group (`"the two men"`) or being specific per side.
3. The driver must have N clearly separable subjects. A synthetic side-by-side of two single-person clips works well for a clean two-shot.
4. Each reference character must roughly match the scale/position/framing of the corresponding driver subject at frame 1 (the first-frame rule, per character).

`animate` (keep reference scene) and `replace` (swap into footage) both support multi-character.

## Quality rules (and why they hold)

- **First-frame match (dominant rule — both modes).** The reference subject should be framed/scaled/posed like the driver subject in **frame 1**. For `replace`, that subject is the **person being swapped out**; for `animate`, it's the **motion subject** whose frame-1 pose the character starts from. The bigger the gap, the more the model must reconcile and the softer/muddier the result. The engine cannot auto-fix this — supply a matched reference (extract `ffmpeg -i CLIP.mp4 -frames:v 1 first.png`, then match/generate against it; `ideogram4` can generate a matched portrait).
- **Aspect = background source** (handled automatically; the reason the engine reads dimensions from the footage in `replace` and the character in `animate`).
- **704p** for finals; **detailed `--describe`** for `replace` fidelity.

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `ComfyUI not reachable` | Start ComfyUI; check `COMFY_URL`. |
| `missing_node_type` / `node_errors` | A node/pack or model is missing → `setup.md`. |
| Soft / muddy output | Reference doesn't match the driver's first frame (framing/scale/pose). Supply a matched reference. Also confirm not `--fast`. |
| Output blurry but framing fine | You used `--fast` (512p). Drop it for 704p. |
| Wrong subject animated / nothing tracked | Tighten `--detect` (name the subject/position); the default `"a person"` may grab the wrong one in a busy clip. |
| Multi-char: characters do the same motion or swap identities | Reference layout doesn't match the driver positions, or palette/ordering mismatch — match left-to-right at frame 1; keep `--objects` == subject count; ≤6. |
| Replacement regenerates the background instead of keeping it | The engine matches output aspect to the footage automatically; if you bypass the engine, set output aspect == footage aspect. |
| Output length wrong / frozen tail | Use the engine (it fixes this). A raw ComfyUI run leaves the improvised tail. |
| OOM | Free other models' VRAM; use `--fast` (512p) or the GGUF model variant. |
