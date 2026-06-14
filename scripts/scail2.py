#!/usr/bin/env python3
"""
scail2 — SCAIL-2 character motion transfer & replacement, driven by ComfyUI. Two subcommands:

  scail2 animate  --character C.png --motion M.mp4    # C performs M's motion (keeps C's background)
  scail2 replace  --in FOOTAGE.mp4 --with P.png        # swap the person in FOOTAGE with P (keeps FOOTAGE's bg)

Everything else is auto-derived from the two inputs:
  - output aspect  = the BACKGROUND source (character image for animate, footage for replace)
  - output resolution = driver's short side, capped 704 (default) or 512 (--fast); both ÷32; never upscale
  - output length  = the driver, EXACTLY (loop count from the 76-frame step + frame-exact trim, no filler tail)
  - output fps     = loaded_frames / driver_duration, so the frames span the original length
  - SAM3 detection prompt = --detect (what to track), default "a person"
  - Wan-T5 quality prompt  = --describe (scene/appearance), default empty

Requires a running ComfyUI with the SCAIL-2 stack (see ../references/setup.md). Env overrides:
  COMFY_URL (default http://127.0.0.1:8188)   COMFY_DIR (ComfyUI install)   DELIVER_DIR (where --deliver copies)

The node-id map below is bound to scail2_workflow.json shipped beside this script — keep them in sync.
"""
import argparse, json, math, os, re, shutil, subprocess, sys, time, urllib.request, urllib.error

API      = os.environ.get("COMFY_URL", "http://127.0.0.1:8188")
DELIVER  = os.environ.get("DELIVER_DIR", os.path.expanduser("~/Downloads"))

def detect_comfy_dir():
    """COMFY_DIR env wins; else ask the running ComfyUI where it lives (its own main.py path).
    Translates a Windows path to /mnt/<drive> when that exists (WSL driving a Windows ComfyUI)."""
    if os.environ.get("COMFY_DIR"): return os.environ["COMFY_DIR"]
    try:
        main=json.load(urllib.request.urlopen(API+"/system_stats",timeout=5))["system"]["argv"][0]
        m=re.match(r'^([A-Za-z]):[\\/](.+)[\\/][^\\/]+$', main)   # Windows: C:\dir\...\main.py
        if m:
            d="/mnt/"+m.group(1).lower()+"/"+m.group(2).replace("\\","/")   # WSL path
            if os.path.isdir(d): return d
            return f"{m.group(1)}:\\{m.group(2)}"                  # native Windows fallback
        return os.path.dirname(main)                              # POSIX: /home/.../ComfyUI/main.py
    except Exception:
        return os.path.expanduser("~/ComfyUI")

COMFY_DIR= detect_comfy_dir()
INP      = os.path.join(COMFY_DIR, "input")
OUT      = os.path.join(COMFY_DIR, "output")
BASE     = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scail2_workflow.json")
FPS      = 16   # SCAIL-2 working frame rate (the model is tuned around this)

# nodes in scail2_workflow.json
N_IMG="30"; N_VID="33"; N_DETECT="87"; N_POS="3"; N_NEG="4"; N_REPL="188"
N_RES="89"; N_SAM=["85","91"]; N_STEPS="18"

def sh(cmd): return subprocess.run(cmd, capture_output=True, text=True).stdout.strip()
def dims(p): w,h = sh(["ffprobe","-v","error","-select_streams","v:0","-show_entries","stream=width,height","-of","csv=p=0:s=x",p]).split("x"); return int(w),int(h)
def dur(p):  return float(sh(["ffprobe","-v","error","-show_entries","format=duration","-of","csv=p=0",p]))
def nbf(p):  return sh(["ffprobe","-v","error","-select_streams","v:0","-show_entries","stream=nb_frames,duration","-of","csv=p=0",p])

def out_dims(w,h,short):
    snap=lambda x: max(256, int(round(x/32))*32)
    return (snap(short), snap(short*h/w)) if w<=h else (snap(short*w/h), snap(short))

def stage(arg):
    if os.sep in arg or os.path.isabs(arg):
        base=os.path.basename(arg); dst=os.path.join(INP,base)
        if os.path.abspath(arg)!=os.path.abspath(dst): shutil.copy(arg,dst)
        return base
    if not os.path.exists(os.path.join(INP,arg)): sys.exit(f"'{arg}' not found in {INP}")
    return arg

def preflight():
    try: urllib.request.urlopen(API+"/system_stats", timeout=5)
    except Exception: sys.exit(f"ComfyUI not reachable at {API}. Start it / check COMFY_URL (see references/setup.md).")

def post(p):
    req=urllib.request.Request(API+"/prompt", data=json.dumps({"prompt":p,"client_id":"scail2"}).encode(),
                               headers={"Content-Type":"application/json"})
    try: r=json.load(urllib.request.urlopen(req,timeout=30))
    except urllib.error.HTTPError as e: sys.exit("POST /prompt failed: "+e.read().decode()[:1200])
    if r.get("error"): sys.exit("ERROR: "+json.dumps(r["error"])[:600]+"\n(missing node/model? see references/setup.md)")
    if r.get("node_errors"): sys.exit("node_errors: "+json.dumps(r["node_errors"])[:900])
    return r["prompt_id"]

def poll(pid):
    t0=time.time()
    while time.time()-t0<1800:
        try: h=json.load(urllib.request.urlopen(f"{API}/history/{pid}",timeout=10))
        except Exception: h={}
        if h:
            v=list(h.values())[0]; st=v.get("status",{}).get("status_str"); outs=[]
            for nid,o in v.get("outputs",{}).items():
                for k in ("gifs","videos","images"):
                    for f in o.get(k,[]): outs.append((nid,f["filename"],f.get("subfolder","")))
            return st,outs
        time.sleep(6)
    return "timeout",[]

def loaded_frames(video):
    """Frames VHS loads at FPS (it resamples, so this is not exactly dur*FPS)."""
    g={"1":{"class_type":"VHS_LoadVideo","inputs":{"video":video,"force_rate":FPS,"custom_width":0,
            "custom_height":0,"frame_load_cap":0,"skip_first_frames":0,"select_every_nth":1,"format":"Wan"}},
       "2":{"class_type":"VHS_VideoInfoLoaded","inputs":{"video_info":["1",3]}},
       "3":{"class_type":"PreviewAny","inputs":{"source":["2",1]}}}
    pid=post(g); poll(pid)
    v=list(json.load(urllib.request.urlopen(f"{API}/history/{pid}",timeout=10)).values())[0]
    return int(v["outputs"]["3"]["text"][0])

def run(mode, image, video, detect, describe, objects, fast, steps, name, deliver):
    preflight()
    img=stage(image); vid=stage(video)
    vpath=os.path.join(INP,vid); ipath=os.path.join(INP,img)
    D=dur(vpath); dvw,dvh=dims(vpath); rw,rh=dims(ipath)
    aw,ah = (dvw,dvh) if mode=="replace" else (rw,rh)          # aspect from the background source
    short = max(384, int(round(min(min(dvw,dvh), 512 if fast else 704)/32))*32)  # never upscale; cap
    W,H = out_dims(aw,ah,short)
    if abs(math.log((rw/rh)/(dvw/dvh))) > 0.35:
        print(f"  ⚠ reference aspect ({rw}x{rh}) differs from the clip ({dvw}x{dvh}) — see the FIRST-FRAME rule "
              f"in references/reference.md; a reference framed/posed like the clip's first frame gives the best results.")
    a = loaded_frames(vid)
    p=json.load(open(BASE))
    p[N_IMG]["inputs"]["image"]=img
    v33=p[N_VID]["inputs"]; v33.update(video=vid, force_rate=FPS, frame_load_cap=0, select_every_nth=1)
    p[N_RES]["inputs"]["width"]=W; p[N_RES]["inputs"]["height"]=H
    p[N_REPL]["inputs"]["value"]=(mode=="replace")
    p[N_DETECT]["inputs"]["text"]=detect
    p[N_POS]["inputs"]["text"]=describe
    for n in N_SAM: p[n]["inputs"]["max_objects"]=objects
    p[N_STEPS]["inputs"]["steps"]=steps
    for nid,node in p.items():                                  # output fps so a frames == driver duration
        if node.get("class_type")=="VHS_VideoCombine":
            node["inputs"]["frame_rate"]=round(a/D,3)
            fp=node["inputs"].get("filename_prefix","")
            if "compare" in fp.lower(): node["inputs"]["filename_prefix"]="Wan21/"+name+"-compare"
            elif fp.startswith("Wan21/") or fp=="SCAIL2": node["inputs"]["filename_prefix"]="Wan21/"+name
    print(f"[{mode}] image={img} video={vid} -> {W}x{H} {D:.2f}s ({a}f) detect={detect!r} objects={objects} steps={steps} {'fast/512' if fast else 'hq/704'}")
    pid=post(p); st,outs=poll(pid); print("status:",st)
    main=next((os.path.join(OUT,sub,fn) for nid,fn,sub in outs if name in fn and fn.endswith(".mp4") and "compare" not in fn), None)
    if not main: print("no main output (status %s)"%st); return
    # frame-exact trim in place: keep the first `a` (pose-driven) frames; drop the forLoop's improvised tail.
    def trim(src):
        tmp=src+".tmp.mp4"
        subprocess.run(["ffmpeg","-nostdin","-loglevel","error","-y","-i",src,"-frames:v",str(a),
            "-an","-c:v","libx264","-crf","16","-pix_fmt","yuv420p",tmp],capture_output=True)
        if os.path.exists(tmp) and os.path.getsize(tmp)>0: os.replace(tmp,src)
    trim(main)
    cmp=os.path.join(OUT,"Wan21",f"{name}-compare_00001.mp4")
    if os.path.exists(cmp): trim(cmp)
    print(f"  output {nbf(main)} (exact, == driver) -> {main}")
    if deliver:
        try:
            os.makedirs(DELIVER, exist_ok=True)
            d=os.path.join(DELIVER,f"{name}.mp4"); shutil.copy(main,d); print("delivered ->",d)
        except Exception:
            print(f"  (deliver skipped — {DELIVER} not writable; set DELIVER_DIR. output is at the path below)")
    print("FINAL="+main)

def main():
    ap=argparse.ArgumentParser(prog="scail2", description="SCAIL-2 character motion transfer & replacement")
    sub=ap.add_subparsers(dest="cmd", required=True)
    def common(s):
        s.add_argument("--detect", default="a person", help="SAM3 detection prompt: WHAT to track in the clip")
        s.add_argument("--describe", default="", help="Wan-T5 prompt: describe the resulting scene (quality)")
        s.add_argument("--objects", type=int, default=1, help="number of subjects to track (cap 6)")
        s.add_argument("--fast", action="store_true", help="512p draft (default is 704p)")
        s.add_argument("--steps", type=int, default=4, help="sampler steps (4 is the lightx2v sweet spot)")
        s.add_argument("--name", default=None, help="output filename prefix")
        s.add_argument("--no-deliver", action="store_true", help="don't copy the result to DELIVER_DIR")
    a=sub.add_parser("animate", help="a character image performs a driving clip's motion (keeps the character's bg)")
    a.add_argument("--character", required=True); a.add_argument("--motion", required=True); common(a)
    r=sub.add_parser("replace", help="swap the person in footage with a new character (keeps the footage's bg)")
    r.add_argument("--in", dest="infile", required=True); r.add_argument("--with", dest="withfile", required=True); common(r)
    x=ap.parse_args()
    if x.objects>6: print("note: >6 identities exceed SCAIL-2's 6-colour mask palette; identity separation degrades.")
    if x.cmd=="animate":
        run("animate", x.character, x.motion, x.detect, x.describe, x.objects, x.fast, x.steps, x.name or "scail2_animate", not x.no_deliver)
    else:
        run("replace", x.withfile, x.infile, x.detect, x.describe, x.objects, x.fast, x.steps, x.name or "scail2_replace", not x.no_deliver)

if __name__=="__main__": main()
