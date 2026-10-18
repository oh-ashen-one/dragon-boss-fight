# Gameplay reference register

Research date: 2026-10-18. These links are design references, not shipped assets or asset licenses. FromSoftware characters, footage, music, textures, models and animation are not licensed for redistribution by linking them. Veyr and its arena use original art and motion; code and asset licenses must be recorded separately in the project's license/credits files.

## Evidence status and method

Public gameplay from **all three fights was opened and sampled visually in native Chrome**. The observations below come from paused video frames and their displayed seek times, not search snippets. Seeking can update the displayed time before decoding the new frame; the cited follow-up samples were checked with a separate screenshot after seeking. Video audio was muted. No third-party footage or screenshots were downloaded into this repository.

This is a sampled visual study, not a full move catalogue or frame-data analysis. Source titles claim no-hit/no-damage runs; this research did not independently verify every frame of those claims. Veyr's timings and mechanics are original design choices, not measurements of the reference games.

## Inspected public sources

All three recordings are by [Esoterickk](https://www.youtube.com/@Esoterickk), as identified on their YouTube pages.

| Boss | Public original | Player duration displayed |
|---|---|---|
| Kalameet | [Black Dragon Kalameet Boss Fight (No Hits Taken / Melee Only) — Dark Souls Remastered on PS5](https://www.youtube.com/watch?v=5bKmtJK8QGM) | 5:16; includes setup before combat |
| Sinh | [Sinh, the Slumbering Dragon Boss Fight (No Hits Taken / Melee Only) — Dark Souls 2 on PS5](https://www.youtube.com/watch?v=ysWa3sgjW7c) | 2:09 |
| Midir | [Darkeater Midir Boss Fight (No Damage / Melee Only) — Dark Souls 3 PS5](https://www.youtube.com/watch?v=1jHbUWx3sPc) | 3:42 |

## Observations and original adaptations

| Source sample | Directly visible observation | Veyr adaptation / inference |
|---|---|---|
| [Kalameet 4:12](https://www.youtube.com/watch?v=5bKmtJK8QGM&t=252s) | Player is beside a foot, sword extended; a 222 damage number is visible. The dragon's torso fills the upper image. | Make each leg an identifiable target and give immediate local hit feedback. The source frame does not establish separate leg-stagger mechanics. |
| [Kalameet 4:17](https://www.youtube.com/watch?v=5bKmtJK8QGM&t=257s) | The horned head is low and close above the player; 444 damage is displayed. | A lowered head creates a readable focal point. Veyr's timed collapse/head bonus is an original mechanic, not a copied source rule. |
| [Kalameet 4:27](https://www.youtube.com/watch?v=5bKmtJK8QGM&t=267s), [4:32](https://www.youtube.com/watch?v=5bKmtJK8QGM&t=272s), [4:37](https://www.youtube.com/watch?v=5bKmtJK8QGM&t=277s) | First there is frontal distance and a readable whole-body silhouette; later the player is close beneath the torso and legs. Dust is visible around the feet in the close samples. | Give repositioning a visible body/foot transition and use short grounded dust/splash accents for weight. The sampled spacing changes do not measure charge speed or prove a particular named attack. |
| [Sinh 0:33](https://www.youtube.com/watch?v=ysWa3sgjW7c&t=33s) | Dragon is farther ahead with lowered head and raised wings; player and intervening arena floor remain visible. | Preserve a frontal view in which silhouette and escape space can both be read. This still alone cannot establish a landing's timing. |
| [Sinh 0:38](https://www.youtube.com/watch?v=ysWa3sgjW7c&t=38s), [0:48](https://www.youtube.com/watch?v=ysWa3sgjW7c&t=48s) | The earlier view is dominated by the overhead wing/body and upward camera angle. At 0:48 the dragon is airborne above the player, with much less ground visible. | Avoid mandatory sustained flight in the first version; the camera must preserve ground danger and the player under a giant. |
| [Sinh 1:03](https://www.youtube.com/watch?v=ysWa3sgjW7c&t=63s) | At close leg range, dragon geometry obscures much of the player and the head. | Explicitly test every leg angle and use camera distance/occluder handling rather than judging only a distant hero shot. |
| [Midir 0:39](https://www.youtube.com/watch?v=1jHbUWx3sPc&t=39s) | Wide open jaws project toward the foreground while the player is displaced laterally in a low evasive pose. | Give Veyr's bite a clear open-jaw/neck silhouette and a lateral escape route. Exact anticipation and invulnerability frames are not measured here. |
| [Midir 0:44](https://www.youtube.com/watch?v=1jHbUWx3sPc&t=44s), [0:59](https://www.youtube.com/watch?v=1jHbUWx3sPc&t=59s) | Bright fire occupies a large area to the right; the player remains visible on the unlit left/front ground. | Keep an unmistakable safe side to the breath sweep; prevent fire particles from hiding that route. Veyr additionally uses original ground outlines. |
| [Midir 0:49](https://www.youtube.com/watch?v=1jHbUWx3sPc&t=49s), [0:54](https://www.youtube.com/watch?v=1jHbUWx3sPc&t=54s) | The head crosses close to the camera; prominent water spray reinforces near-ground contact. | Match impact VFX to contact and keep their lifetime short enough to preserve the next tell. These samples do not establish collision extents. |
| [Midir 1:04](https://www.youtube.com/watch?v=1jHbUWx3sPc&t=64s) | The head is down directly ahead of the player; a sword-strike pose and 376 damage number are visible. | Support an evade-then-punish rhythm with a physically reachable head and a distinct recovery pose. The five-second gap from the fire sample is not the recovery duration. |

## Textual corroboration and remaining limits

The first-person [Midir Guide (no shield, no summon), Steam Community, 27 May 2021](https://steamcommunity.com/sharedfiles/filedetails/?id=2499684703) describes long initial slam anticipation, a quicker second slam, open-mouth bite cues, a roar before a jumping bite, rear tail punishment, and short recovery opportunities. These are a player's written reports, not observations or official frame data from this sampled pass. In particular, **a complete stomp/slam sequence and tail-sweep sequence were not isolated here**. Do not cite them as visually verified or infer exact invulnerability from the stills.

Before making source-specific timing claims, inspect contiguous anticipation/contact/recovery frames of that exact move. Veyr still needs its own input-driven avoidance, camera and duration tests; reference footage cannot validate our implementation.

## Superseded discovery and access record

Initial in-app browser discovery returned no browser and web fetches of GameFAQs video listings failed. Native Chrome later worked; the earlier blanket statement that visual study was unavailable is superseded by the samples above. The previously proposed Sinh video `hy_yx8BpR7k` was subsequently found **private** in the browser by the integration owner and is removed as an active reference. Search-index metadata alone was insufficient to establish accessibility.

Veyr's leg-collapse loop, timings, water-light telegraphs, dragon, cathedral and animations remain original proposals/implementation. No reference game's character mesh, rig, clip, texture, music or sound belongs in the repository. Public source links confer no asset redistribution license.
