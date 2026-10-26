# Asset sourcing and rights — October26 overhaul

Existing approved private Tripo and Customuse art is retained. The owner authorized generated-provider credits for this pass; no paid animation acquisition was needed. Restricted motion/model files stay out of the public code repository.

## Architecture

The main environment reuses the acquired twelve-piece Tripo cathedral kit. Provenance and original generation jobs are in `Local/ArtPass20261025/Tripo/jobs.json` and the earlier private release receipts. New layout alters placement, scale and structural grouping, not source authorship.

Unused acquisition experiment: **Chandelier**, Mikhail Kadilnikov, https://www.fab.com/listings/8205433d-52b5-40ae-add1-577e769655f5 . Signed-in listing and download dialog explicitly identify **Creative Commons Attribution4.0**, https://creativecommons.org/licenses/by/4.0/ . The free GLB was downloaded through Fab's UI into `Local/FabRigTesting/Source/chandelier.glb`, then copied into this pass. Retain creator, source and license if this unused asset is ever selected. Changes: apply/bake transforms, resize textures to2K, normalize scale, remove the fabric lampshade while retaining the original scrollwork/candles/chain. Editable adaptation and SHA-256 are recorded in `chandelier-provenance.json`.

3DAssets.dev CC0 chandelier/vault candidates were inspected but their CDN returned403/was blocked in Chrome. They are not acquired or included. ThreeJS's chandelier was paid and excluded; free collection was not a strong Gothic fit. NVIDIA SimReady catalogue was predominantly industrial; no suitable Gothic module established. These access/fit findings are not claims that the entire providers lack suitable art.

A Tripo chandelier was also generated through the authorized browser workspace for65 credits, after initial acquisition difficulties. The generated model remains in the account; its export was blocked. It is not used in this game. See `generation-receipt.json`.

## Animation

Four preferred sources were checked directly: Mixamo, Fab, NVIDIA SimReady and ThreeJS Assets; Quaternius UAL/UAL2 were considered more broadly. Existing locally acquired Mixamo Sword and Shield Pack contains the suitable fast lateral strafe bases. Public Mixamo preview search requires JS/login; the local source files have the earlier acquisition record. Fab VanillaLoop free sample includes the approved forward roll but not a verified upright dodge. SimReady/ThreeJS free catalogue evidence did not establish a suitable character dodge. Quaternius Standard is free; its paid Pro/Source versions are excluded.

The new blink uses the acquired `sword and shield strafe (3).fbx` and `(4).fbx`, retargeted onto the same knight and fitted using Blender-native arm IK and the retained sword-grip references. Source identity is stored beside each exported GLB. No new whole-body motion was authored from scratch. The runtime supplies disappearance/reappearance and swept collision.

Dragon hover is the previously reviewed dangling-limb source; takeoff and landing are adaptations of retained approved clips. Required limb and helper-joint local transforms ease toward/from the hover endpoint in Blender. Full source `.blend` scenes remain private; dragon native versions are additive v028; native-axis-correct knight blink is v029, with unaffected clips inherited by reference.

## Audio — all selected source pages offer CC0

- **Determined Pursuit**, Emma_MA: https://opengameart.org/content/determined-pursuit-epic-orchestra-loop . Original CC0 release, not a later remix. Direct source: https://opengameart.org/sites/default/files/determined_pursuit_loop.wav
- **Loopable Dungeon Ambience**, JaggedStone: https://opengameart.org/content/loopable-dungeon-ambience . https://opengameart.org/sites/default/files/dungeon_ambient_1_0.ogg
- **Footsteps: leather, cloth, armor**, HaelDB: https://opengameart.org/content/footsteps-leather-cloth-armor . Choose its CC0 option. https://opengameart.org/sites/default/files/footsteps.zip
- **80 CC0 Creature SFX**, rubberduck: https://opengameart.org/content/80-cc0-creature-sfx . https://opengameart.org/sites/default/files/80-CC0-creature-SFX_0.zip
- **75 CC0 Breaking/Falling/Hit SFX**, rubberduck: https://opengameart.org/content/75-cc0-breaking-falling-hit-sfx . https://opengameart.org/sites/default/files/sfx_breaking_and_falling.zip
- **Fire Staff Sound Effects**, LEGIT Audio: https://opengameart.org/content/fire-staff-sound-effects . https://opengameart.org/sites/default/files/legit_audio_fire_staff_-_free_0.zip
- **Medieval Sound Effects: Weapon Textures**, Ben Jaszczak and Brian Nelson: https://opengameart.org/content/medieval-sound-effects-weapon-textures . CC0 source with creator statement preserved by OGA. https://opengameart.org/sites/default/files/medieval_sfx_textures_1_of_2.7z . Selected recording: Katana Swing.wav.

Conversion: recorded events are cropped, faded, peak-normalized and selectively pitch-shifted to24kHz mono PCM. Music and ambience retain their full loops. `tools/art/prepare_overhaul_audio.py` records source and output hashes, durations and transformations in `Local/Overhaul20261026/audio/prepared.json`. The existing synthesized heal, exposed-state and terminal tones remain intentional supplementary cues. Prepared files and playback code alone do not establish audible quality; the actual native master recording contains nonzero audio with no clipped samples. Acoustic listening quality remains for owner review.

## Superseding owner direction during this pass

The owner stopped further free-3D sourcing and explicitly chose Tripo/Meshy generation for new models, while retaining source-first animation. The Fab chandelier above is an unused experiment and is not selected for native import. Meshy7.1 generated and textured `GeneratedChandelier`, `GeneratedVault` and `GeneratedRibSpan`, with PBR2K maps and roughly50k triangles. Each preview consumed20 credits and each refine10: **90 Meshy credits total**, in addition to the earlier65 Tripo credits. The selected files were downloaded directly by API with no Finder/Save dialog. Exact prompts, task IDs, hashes and credits are in the three Generated*-receipt.json files. Result URLs and credentials are deliberately omitted. Structural normalization preserves topology and texture bytes. The open rib span was additionally fitted to12m width and5m rise; clearance measurements and source hashes are recorded in rib-asset-validation.json.
