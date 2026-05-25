#!/usr/bin/env python3
"""Tight + smooth beat-lock via Rubber Band time maps.

Per-line anchors (recording onset -> target cue) define a time-warp curve;
Rubber Band interpolates SMOOTHLY between them, so every line locks to its
beat without the choppy, oscillating tempo of piecewise atempo. Vocals are
brought up (-12 LUFS) and the instrumental ducked so the voices sit on top.
"""
import os, subprocess, math

HERE = os.path.dirname(__file__)
RAW  = os.path.join(HERE, "..", "raw")
OUT  = os.path.join(HERE, "..", "output")
TMP  = os.path.join(HERE, "stems"); os.makedirs(TMP, exist_ok=True)
SR = 48000
SONG_LEN = 205.0
INST_VOL = 0.32         # instrumental ducked
VOX_LUFS = -12          # vocals louder

# spans: recorded [start,end] kept (multiple -> concatenated, dropping gaps).
# anchors: (original_recording_time, target_song_time) per line.
TAKES = [
 {"name":"om","src":"01-om-part1.m4a","spans":[(7.5,67.5)],"tgt0":8,
  "anchors":[(7.5,8),(10.0,11),(12.2,14),(15.9,17),(17.9,20),(21.1,23),(22.9,26),
   (25.6,29),(27.7,30),(31.0,34),(33.5,38),(36.0,42),(40.1,46),(42.9,50),(45.4,52),
   (48.1,53.5),(50.8,55.5),(53.1,58),(55.0,62),(57.9,66),(66.1,76),(67.5,78)]},
 {"name":"kanav","src":"02-kanav.m4a","spans":[(5.7,55.5)],"tgt0":78,
  "anchors":[(5.7,78),(7.0,81),(8.1,84),(10.0,87),(12.0,90),(14.0,93),(15.0,96),
   (18.0,99),(20.0,102),(22.8,106),(25.1,110),(28.0,114),(30.0,118),(32.4,120),
   (34.9,122),(37.1,124),(39.8,126),(41.5,130),(43.4,134),(44.9,138),(47.6,142),
   (50.3,145),(51.7,147),(53.1,149),(55.5,151)]},
 {"name":"prahaas","src":"03-prahaas.m4a","spans":[(6.0,44.0),(50.8,62.3)],"tgt0":150,
  "anchors":[(6.0,150),(10.7,152),(15.7,154),(19.9,156),(22.1,158),(27.7,160),
   (30.0,162),(32.6,164),(35.0,166),(37.7,168),(40.1,170),(42.6,172),(44.0,174),
   (50.8,174),(55.1,178),(57.9,182),(60.2,186),(62.3,188)]},
 {"name":"all3","src":"04-all3-om-end.m4a","spans":[(0.11,16.5)],"tgt0":190,
  "anchors":[(0.11,190),(3.25,192),(5.41,194),(7.61,196),(9.67,198),(11.11,200),
   (12.21,201),(14.43,202),(16.5,204)]},
]

def concat_time(spans, t):
    """Map an original recording time to its time in the concatenated content."""
    off = 0.0
    for s,e in spans:
        if s-1e-6 <= t <= e+1e-6:
            return off + (t - s)
        off += e - s
    raise ValueError(f"anchor {t} not in any span")

def build(take):
    spans, name = take["spans"], take["name"]
    # 1) trim+concat kept spans -> content wav
    content = os.path.join(TMP, f"{name}.content.wav")
    n = len(spans)
    fc = ";".join(f"[0:a]atrim=start={s:.3f}:end={e:.3f},asetpts=PTS-STARTPTS[a{i}]"
                  for i,(s,e) in enumerate(spans))
    fc += ";" + "".join(f"[a{i}]" for i in range(n)) + f"concat=n={n}:v=0:a=1[o]"
    subprocess.run(["ffmpeg","-hide_banner","-loglevel","error","-y",
                    "-i",os.path.join(RAW,take["src"]),"-filter_complex",fc,
                    "-map","[o]","-ar",str(SR),"-ac","2",content],check=True)
    cdur = float(subprocess.run(["ffprobe","-v","error","-show_entries","format=duration",
                "-of","csv=p=0",content],capture_output=True,text=True).stdout)
    tgt_span = take["anchors"][-1][1] - take["tgt0"]
    # 2) time map (source_frame target_frame), monotonic
    mp = os.path.join(TMP, f"{name}.timemap.txt")
    lines, prev = ["0 0"], (0,0)
    for rec,tgt in take["anchors"]:
        sf = int(round(concat_time(spans,rec)*SR)); tf = int(round((tgt-take["tgt0"])*SR))
        if sf>prev[0] and tf>prev[1]: lines.append(f"{sf} {tf}"); prev=(sf,tf)
    open(mp,"w").write("\n".join(lines)+"\n")
    X = tgt_span/cdur
    warped = os.path.join(TMP, f"{name}.warped.wav")
    subprocess.run(["rubberband","-t",f"{X:.6f}","--timemap",mp,"-c","6",
                    content,warped],check=True,capture_output=True)
    # 3) level + position
    delay=int(take["tgt0"]*1000)
    stem=os.path.join(TMP,f"{name}.wav")
    subprocess.run(["ffmpeg","-hide_banner","-loglevel","error","-y","-i",warped,
        "-af",f"highpass=f=85,loudnorm=I={VOX_LUFS}:TP=-1.0:LRA=11,"
              f"afade=t=in:st=0:d=0.03,adelay={delay}|{delay},apad=whole_dur={SONG_LEN}",
        stem],check=True)
    print(f"  {name:9s} {len(lines)} anchors  stretch {X:.3f}  ({cdur:.1f}s -> {tgt_span:.0f}s)")
    return stem

print("Building Rubber Band time-warped parts:")
stems=[build(t) for t in TAKES]

inst=os.path.join(RAW,"instrumental.mp3")
ins=["-i",inst]+sum([["-i",s] for s in stems],[])
fg=(f"[0:a]aformat=channel_layouts=stereo,volume={INST_VOL},apad=whole_dur={SONG_LEN}[bg];"
    +"".join(f"[{i+1}:a]aformat=channel_layouts=stereo[v{i}];" for i in range(len(stems)))
    +"[bg]"+"".join(f"[v{i}]" for i in range(len(stems)))
    +f"amix=inputs={len(stems)+1}:normalize=0:dropout_transition=0,"
     f"alimiter=limit=0.97,afade=t=out:st=202:d=3[out]")
dst=os.path.join(OUT,"subjuntivo-draft5.mp3")
subprocess.run(["ffmpeg","-hide_banner","-loglevel","error","-y",*ins,
    "-filter_complex",fg,"-map","[out]","-c:a","libmp3lame","-q:a","2",dst],check=True)
print(f"\nBuilt {dst}")
print(subprocess.run(["ffprobe","-v","error","-show_entries","format=duration",
    "-of","csv=p=0",dst],capture_output=True,text=True).stdout.strip(),"sec")
