#!/usr/bin/env python3
"""Natural voices: ONE gentle, uniform speed per part (no per-line spikes).

Prahaas sings at natural speed (~1.01x) by extending the instrumental:
the final-chorus section (164-185s) is looped once, adding 21s so the
201s instrumental becomes 222s. Prahaas no longer needs any speedup.
Prahaas vocal boosted to -10 LUFS for clarity.
"""
import os, subprocess

HERE = os.path.dirname(__file__)
RAW  = os.path.join(HERE, "..", "raw")
OUT  = os.path.join(HERE, "..", "output")
TMP  = os.path.join(HERE, "stems"); os.makedirs(TMP, exist_ok=True)
SR = 48000
SONG_LEN = 222.0
INST_VOL = 0.30
VOX_LUFS = -12

# Prahaas given full natural window (tgt1=200) so X≈1.01 — no speedup.
# Instrumental extended by looping 164-185s once (adds 21s: 201→222s).
TAKES = [
  {"name":"om",      "src":"01-om-part1.m4a",    "spans":[(7.5,67.5)],             "tgt0":8,   "tgt1":78},
  {"name":"kanav",   "src":"02-kanav.m4a",       "spans":[(5.7,55.5)],             "tgt0":78,  "tgt1":151},
  {"name":"prahaas", "src":"03-prahaas.m4a",     "spans":[(6.0,44.0),(50.8,62.3)], "tgt0":150, "tgt1":200},
  {"name":"all3",    "src":"04-all3-om-end.m4a", "spans":[(0.11,16.5)],            "tgt0":200, "tgt1":217},
]

def build(take):
    name, spans = take["name"], take["spans"]
    n = len(spans)
    fc = ";".join(f"[0:a]atrim=start={s:.3f}:end={e:.3f},asetpts=PTS-STARTPTS[a{i}]"
                  for i,(s,e) in enumerate(spans))
    fc += ";" + "".join(f"[a{i}]" for i in range(n)) + f"concat=n={n}:v=0:a=1[o]"
    content = os.path.join(TMP, f"{name}.content.wav")
    subprocess.run(["ffmpeg","-hide_banner","-loglevel","error","-y",
                    "-i",os.path.join(RAW,take["src"]),"-filter_complex",fc,
                    "-map","[o]","-ar",str(SR),"-ac","2",content],check=True)
    cdur = float(subprocess.run(["ffprobe","-v","error","-show_entries","format=duration",
                "-of","csv=p=0",content],capture_output=True,text=True).stdout)
    span = take["tgt1"] - take["tgt0"]
    X = span / cdur
    warped = os.path.join(TMP, f"{name}.warped.wav")
    subprocess.run(["rubberband","-t",f"{X:.6f}","-c","6",content,warped],
                   check=True,capture_output=True)
    delay = int(take["tgt0"]*1000)
    lufs = -10 if name == "prahaas" else VOX_LUFS  # extra boost for Prahaas clarity
    stem = os.path.join(TMP, f"{name}.wav")
    subprocess.run(["ffmpeg","-hide_banner","-loglevel","error","-y","-i",warped,
        "-af",f"highpass=f=85,loudnorm=I={lufs}:TP=-1.0:LRA=11,"
              f"afade=t=in:st=0:d=0.03,adelay={delay}|{delay},apad=whole_dur={SONG_LEN}",
        stem],check=True)
    pct = (X-1)*100
    tag = "natural" if abs(pct)<3 else (f"{abs(pct):.0f}% slower" if X>1 else f"{abs(pct):.0f}% faster")
    print(f"  {name:9s} {cdur:.1f}s -> {span:.0f}s   x{X:.3f}  ({tag})")
    return stem

print("Building natural constant-speed parts:")
stems = [build(t) for t in TAKES]

inst = os.path.join(RAW,"instrumental.mp3")
ins  = ["-i",inst]+sum([["-i",s] for s in stems],[])

# Extend instrumental: loop final-chorus section 164-185s once (adds 21s).
# Transitions: 0→164 continuous; 164→185 plays twice; 185→end seamless tail.
inst_ext = (
    "[0:a]atrim=start=0:end=164,asetpts=PTS-STARTPTS[i1];"
    "[0:a]atrim=start=164:end=185,asetpts=PTS-STARTPTS[i2];"
    "[0:a]atrim=start=164:end=185,asetpts=PTS-STARTPTS[i3];"
    "[0:a]atrim=start=185,asetpts=PTS-STARTPTS[i4];"
    f"[i1][i2][i3][i4]concat=n=4:v=0:a=1,"
    f"aformat=channel_layouts=stereo,volume={INST_VOL},apad=whole_dur={SONG_LEN}[bg];"
)
fg = (inst_ext
      +"".join(f"[{i+1}:a]aformat=channel_layouts=stereo[v{i}];" for i in range(len(stems)))
      +"[bg]"+"".join(f"[v{i}]" for i in range(len(stems)))
      +f"amix=inputs={len(stems)+1}:normalize=0:dropout_transition=0,"
       f"alimiter=limit=0.97,afade=t=out:st=219:d=3[out]")
dst = os.path.join(OUT,"subjuntivo-draft7.mp3")
subprocess.run(["ffmpeg","-hide_banner","-loglevel","error","-y",*ins,
    "-filter_complex",fg,"-map","[out]","-c:a","libmp3lame","-q:a","2",dst],check=True)
print(f"\nBuilt {dst}")
print(subprocess.run(["ffprobe","-v","error","-show_entries","format=duration",
    "-of","csv=p=0",dst],capture_output=True,text=True).stdout.strip(),"sec")
