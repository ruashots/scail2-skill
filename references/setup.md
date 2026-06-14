# scail2 — setup (models, nodes, environment)

Read this only if a run errors with a missing node/model, or you're installing on a fresh ComfyUI. Once everything below is in place, `scripts/scail2.py` is the only interface you need.

## 1. Models

Download into the ComfyUI install (`COMFY_DIR/models/...`). Filenames matter — the workflow references them by name.

| File | HuggingFace source | Put in |
|---|---|---|
| `wan2.1_14B_SCAIL_2_fp8_scaled.safetensors` (~17.7 GB) | `Comfy-Org/SCAIL-2` → `diffusion_models/` | `models/diffusion_models/` |
| `sam3.1_multiplex_fp16.safetensors` (~1.75 GB) | `Comfy-Org/sam3.1` → `checkpoints/` | `models/checkpoints/` |
| `wan_2.1_vae.safetensors` (~0.25 GB) | `Comfy-Org/Wan_2.1_ComfyUI_repackaged` → `split_files/vae/` | `models/vae/` |
| `umt5_xxl_fp16.safetensors` (~11.4 GB) | `Comfy-Org/Wan_2.1_ComfyUI_repackaged` → `split_files/text_encoders/` | `models/text_encoders/` |
| `clip_vision_h.safetensors` (~1.26 GB) | `Comfy-Org/Wan_2.1_ComfyUI_repackaged` → `split_files/clip_vision/` | `models/clip_vision/` |
| `lightx2v_I2V_14B_480p_cfg_step_distill_rank256_bf16.safetensors` (~2.9 GB) | `Kijai/WanVideo_comfy` → `Lightx2v/` | `models/loras/WanVideo/` |

Notes:
- The SCAIL-2 model is also offered as **fp16** (~33 GB, sharper, needs ~32 GB VRAM) and **GGUF** (lower VRAM). fp8 is the balanced default for a 32 GB card.
- SAM3.1 is **not gated** (the Comfy-Org repackage) — no Meta/`facebook/sam3` access needed.
- The SCAIL-2 checkpoint bundles VAE/T5, but the ComfyUI workflow loads the separate Wan-2.1 VAE/encoder above.
- Download with `hf download <repo> --include "<path>" --local-dir ...` or `curl` from the `resolve/main/<path>` URL.

## 2. Custom node packs

Install via ComfyUI-Manager (or `git clone` into `custom_nodes/`):

- **ComfyUI-KJNodes** — `DiffusionModelLoaderKJ`, `ImageResizeKJv2`, `ColorTransfer`
- **ComfyUI-VideoHelperSuite** — `VHS_LoadVideo`, `VHS_VideoCombine`, `VHS_VideoInfoLoaded`
- **ComfyUI-Easy-Use** — `easy forLoopStart` / `easy forLoopEnd` (the long-video loop)
- **ComfyUI-Custom-Scripts** (pythongosssss) — `MathExpression|pysssss` (the loop counter)

## 3. The SCAIL-2 + SAM3 nodes (ComfyUI core)

`WanSCAILToVideo`, `SCAIL2ColoredMask`, and `SAM3_VideoTrack` are **core** ComfyUI nodes (`comfy_extras/nodes_scail.py`, `nodes_sam3.py`). They landed via ComfyUI PR **#14373** (+ #14415 reference-mask fix), merged June 2026.

- **Recent ComfyUI (master or a release after that merge):** present natively — nothing to do.
- **Older ComfyUI release that lacks `SCAIL2ColoredMask`:** the model node may exist without mask inputs. To add the current nodes without going fully nightly:
  1. Fetch `comfy_extras/nodes_scail.py` from ComfyUI master into your `comfy_extras/`.
  2. Confirm the dependency `comfy/ldm/sam3/tracker.py` exists (ships with recent SAM3 support; if absent, your build is too old — update ComfyUI).
  3. ComfyUI loads `comfy_extras` from an **explicit list** in `nodes.py` (not a glob) — add `"nodes_scail.py"` to that list (near `"nodes_sam3.py"`).
  4. If `nodes_wan.py` defines an older `WanSCAILToVideo`, remove it from that file's extension node list to avoid a duplicate registration.
  5. Restart ComfyUI (`POST /manager/reboot` or relaunch). Verify: `GET /object_info/SCAIL2ColoredMask` returns the node.

  Back up edited files first; this is a forward-port and becomes unnecessary once your ComfyUI release includes the nodes.

## 4. Verify the install

```bash
curl -s http://127.0.0.1:8188/object_info/SCAIL2ColoredMask  # must return the node
curl -s http://127.0.0.1:8188/object_info/WanSCAILToVideo    # required inputs must include pose_video_mask, reference_image_mask
```
Both present → `scripts/scail2.py` is ready. A run that fails with `node_errors` or `missing_node_type` points at the offending node/pack here.

## 5. The workflow template

`scripts/scail2_workflow.json` is the API-format graph the engine drives (a flattened export of the SCAIL-2 ComfyUI workflow). The engine edits it by node id — **the node-id map at the top of `scail2.py` is bound to this file; keep them in sync.** If you regenerate the template from a UI workflow, re-map the ids.
