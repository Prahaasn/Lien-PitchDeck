#!/usr/bin/env bash
# Build the Subjuntivo / "Party in the U.S.A." parody mix.
# Places each a cappella take at its section cue over the instrumental.
# Re-run after tweaking the OFFSET / TEMPO / VOLUME knobs below.
set -euo pipefail
cd "$(dirname "$0")/audio"
mkdir -p stems output analysis

# --- Tunable knobs --------------------------------------------------------
INST_VOL=0.45          # instrumental level under the vocals
VOX_LUFS=-14           # target loudness per vocal stem
OM_AT=8                # OM section start (s)   -> 0:08
KANAV_AT=78            # Kanav section start    -> 1:18
PRAHAAS_AT=150         # Prahaas bridge start   -> 2:30
ALL3_AT=190            # All-three finale start -> 3:10
PRAHAAS_TEMPO=1.425    # speed-up so Prahaas fits the 40s bridge
# Lead-in trims (silence before each voice starts), seconds:
OM_TRIM=8.0; KANAV_TRIM=5.0; PRAHAAS_TRIM=5.5
ALL3_IN=0.3; ALL3_OUT=15.6          # all-three final chorus span
OUTRO_IN=17.5; OUTRO_OUT=52.6       # OM outro span (not in main mix)
# -------------------------------------------------------------------------

NORM="highpass=f=85,loudnorm=I=${VOX_LUFS}:TP=-1.0:LRA=11"
ff(){ ffmpeg -hide_banner -loglevel error -y "$@"; }

ff -i raw/01-om-part1.m4a    -af "atrim=start=${OM_TRIM},asetpts=PTS-STARTPTS,${NORM}" stems/om.wav
ff -i raw/02-kanav.m4a       -af "atrim=start=${KANAV_TRIM},asetpts=PTS-STARTPTS,${NORM}" stems/kanav.wav
ff -i raw/03-prahaas.m4a     -af "atrim=start=${PRAHAAS_TRIM},asetpts=PTS-STARTPTS,atempo=${PRAHAAS_TEMPO},${NORM}" stems/prahaas.wav
ff -i raw/04-all3-om-end.m4a -af "atrim=start=${ALL3_IN}:end=${ALL3_OUT},asetpts=PTS-STARTPTS,${NORM}" stems/all3.wav
ff -i raw/04-all3-om-end.m4a -af "atrim=start=${OUTRO_IN}:end=${OUTRO_OUT},asetpts=PTS-STARTPTS,${NORM}" stems/om-outro.wav

ff -i raw/instrumental.mp3 -i stems/om.wav -i stems/kanav.wav -i stems/prahaas.wav -i stems/all3.wav \
  -filter_complex "\
   [0:a]aformat=channel_layouts=stereo,volume=${INST_VOL},apad=pad_dur=5[bg]; \
   [1:a]aformat=channel_layouts=stereo,adelay=${OM_AT}s:all=1[a1]; \
   [2:a]aformat=channel_layouts=stereo,adelay=${KANAV_AT}s:all=1[a2]; \
   [3:a]aformat=channel_layouts=stereo,adelay=${PRAHAAS_AT}s:all=1[a3]; \
   [4:a]aformat=channel_layouts=stereo,adelay=${ALL3_AT}s:all=1[a4]; \
   [bg][a1][a2][a3][a4]amix=inputs=5:normalize=0:dropout_transition=0[m]; \
   [m]alimiter=limit=0.95,afade=t=out:st=203:d=3[out]" \
  -map "[out]" -c:a libmp3lame -q:a 2 output/subjuntivo-draft1.mp3

echo "Built output/subjuntivo-draft1.mp3"
ffprobe -v error -show_entries format=duration -of csv=p=0 output/subjuntivo-draft1.mp3
