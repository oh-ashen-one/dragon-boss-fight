# Recorded sound set (quality goal B1)

The owner asked for real recordings in place of the beeps and dings. This folder holds the receipt for a set of CC0 Freesound recordings, cut and levelled for the game. Nothing here is wired into the game yet. The final PCM set is staged outside the Unreal project at `Local/AudioSources20261118/staged/Recorded20261118/` (not committed; `recorded-set.json` carries the SHA-256 of every file); the wiring builder copies it to `Unreal/Veyr/Content/Audio/Recorded20261118/` while it holds the engine and plays the variants.

## What it replaces

- Code-generated tones in `VeyrAudio.cpp` `BuildSamples`: Heal, Exposed (collapse), Victory, Death. The other cues load from `Content/Audio/Overhaul` (licensed, ignored by git) and are replaced here by recordings with several variants each.
- Cues the game never had, now with variants: dragon footstep, dragon limb and tail whoosh, bite, armour hit, dragon breath in and out, low growl, snort, debris, and ten single knight footsteps on stone.
- Kept untouched: the three dragon roar files (`DragonLibrary20261103`), the owner's music, the player pain grunt.

Every cue has between 3 and 10 variants (footsteps 10, dragon steps 6). `recorded-set.json` lists, per variant: file, seconds, peak and event RMS in dB, the checks measured on the cut, the Freesound page, author, title, licence, licence re-check date and SHA-256 of source and PCM. Per cue it lists the shared event RMS (`levelRmsDb`), the spread between variants (all within 1.5 dB), the level of the sound the game plays today (`oldGameLevelRmsDb`) and `volumeToMatchOldLevel`, the multiplier that gives the same loudness as today's sound. `pitchFactor` is below 1 for big creatures (see processing). The fire roar (`Fire`) is cross-faded so it loops.

## Sources

Freesound public search, Creative Commons 0 filter, no account. Each page was re-read to confirm "Creative Commons 0" (`verify_licenses.py`). Raw downloads and candidates stay in `Local/AudioSources20261118/` and are never committed. CC0 needs no credit; authors and pages are in the receipt anyway.

## Processing

Cut from the best moment of each file, head silence trimmed, 3 ms fade in and an eased fade out, DC removed, 24 kHz mono 16-bit PCM (what `AVeyrAudio` reads), gain to the cue's shared level with a soft limiter above the cue's peak ceiling. Big-creature cues (`DragonStep` 0.7, `DragonSwing` 0.8, `Bite` 0.85, `Wing` 0.85) are played slower so they sound larger; this is a recording slowed, not generated audio. No synthesis, no voices, no models make sound.

Each cut is checked by Earshot (CPU-local; a content check only, not a listening approval) and by our own measurements: attack time and peak position, head silence, cut-off tails, clipping, noise floor, low-frequency-only energy, several events in one cut, flat compressed bodies. Creature cues also reject cuts that sound like a human voice. Rejected cut counts per cue are in the receipt.

## Reproduce

```
python3 tools/audio/freesound_candidates.py tools/audio/recorded_set_plan.json --out Local/AudioSources20261118
python3 tools/audio/render_code_tones.py Local/AudioSources20261118/_code_tones
~/.cache/earshot/venv/bin/python tools/audio/prepare_recorded_set.py Local/AudioSources20261118 \
    --output Local/AudioSources20261118/staged/Recorded20261118 --audio-root Unreal/Veyr/Content/Audio \
    --receipt docs/audio-20261118/recorded-set.json
python3 tools/audio/verify_licenses.py docs/audio-20261118/recorded-set.json
~/.cache/earshot/venv/bin/python tools/audio/qc_sheet.py Local/AudioSources20261118/staged/Recorded20261118 OUT_DIR
python3 tools/audio/build_audition.py --receipt docs/audio-20261118/recorded-set.json \
    --audio-root Unreal/Veyr/Content/Audio --recorded Local/AudioSources20261118/staged/Recorded20261118 --code-tones Local/AudioSources20261118/_code_tones --out Local/playtest-goal-review
```

`recorded_set_plan.json` holds the search queries per cue and the `exclude` list of Freesound ids rejected after looking at the waveforms. `render_code_tones.py` is a port of `BuildSamples` so the audition page plays what the code-generated cues sound like today. The audition page is `Local/playtest-goal-review/audio.html` (old next to every new variant, source title linked).

## Cue names for wiring

`Swing HeavySwing Contact Guard ArmorHit Impact DragonStep DragonSwing Bite Breath Fire Wing Roll Footstep Blink Break Debris Exposed Death Heal Victory DragonBreathIn DragonBreathOut DragonGrowlLow DragonSnort`. Files are `<Cue>_<n>.pcm`, n from 1. Footstep (knight, on stone), DragonStep, breath in/out and the growl and snort sets are new.

The cuts are CC0 and may be committed like `DragonLibrary20261103`; they are left out of this commit only because the packaging builder owns `Content` while it holds the engine.
