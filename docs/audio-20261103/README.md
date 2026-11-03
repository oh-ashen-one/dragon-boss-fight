# Dedicated creature-library replacement

Owner rejected the Fish Drama 3 human-bass roar/growl on 2026-11-03. The game now loads Fish only for PlayerPain. Rejected dragon PCM was removed from staged game content; its original take remains private rejected evidence.

Replacement candidates come from SFXMint's pre-existing public CC0 library: Deep Rasping Dragon Roar 03, Territorial Dragon Roar 08, Wounded Dragon Roar 10. The site identifies them as AI-generated **sound effects**, not animal field recordings. No new generation or payment occurred. Downloaded three library files within the site's free allowance. Exact source/license URLs, hashes, cue assignments and unaltered-duration PCM conversion are in dragon-library.json.

The actual source WAV auditions were exposed to the owner during work, and remain on the existing review server at /dragon-replacement/. Source suitability and technical validation do not establish subjective listening acceptance.

Reproduce: tools/audio/prepare_dragon_library.py SOURCE_DIRECTORY --output Unreal/Veyr/Content/Audio/DragonLibrary20261103 --receipt RECEIPT. No voice pitching or human TTS processing is used. The supplied OST hash remains unchanged, as does the single player hit grunt.
