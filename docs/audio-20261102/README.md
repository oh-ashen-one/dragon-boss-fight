# Owner soundtrack and Fish vocal integration

Owner selected `Untitled.mp3` on 2026-11-02 and requested playback at encounter entry. The decoded score is 149.6 seconds, stereo 48 kHz PCM16, with its arrangement, timing and gain unchanged. Existing music slider still controls it. `-VeyrLegacyAudio` selects the previous music/vocals for matched comparisons.

Fish Drama 3 was called directly using the existing local runtime credential, never a browser or bundled key. A licensed deep bass voice generated one roar/growl take. Fish ASR described a powerful roar followed by a groan; this is content screening, not owner listening approval. Natural silence splits it into Roar (2.5 seconds) and DragonGrowl (3.36 seconds). One separate pain take was trimmed to its first 0.53-second grunt; every player hit uses that one clip, with a short anti-overlap interval. No dialogue, additional soundtrack or extra player vocal set was generated.

Dragon threat calls occur on fire/takeoff windups, growls on bite/stagger/collapse; showcase Roar retains the jaw timing. Existing physical effects remain. Music stays silent before encounter entry, starts from sample zero on entry and starts fresh after restart. Death stops the music.

Reproduce with `tools/audio/prepare_score.py INPUT --output Unreal/Veyr/Content/Audio/OwnerScore20261102/Music.pcm --receipt RECEIPT`, then `tools/audio/prepare_fish_cues.py SOURCE_DIRECTORY --output Unreal/Veyr/Content/Audio/Fish20261102 --receipt RECEIPT`. `fish_cue.py` requires a runtime environment credential or an explicit private key-file input and refuses automatic retry of pending jobs. Raw media is ignored; public source contains only code, prompts/provenance and hashes.

Mac launcher: `tools/unreal/play_shipping.sh`, with `Local/LatestShipping.json` written only after runtime validation. The launcher uses the shared GPU guard; no Windows build is claimed.

Exact generation/ASR estimates are in `fish-spend.json` (not invoice charges). Numeric/ASR checks do not establish subjective listening quality.
