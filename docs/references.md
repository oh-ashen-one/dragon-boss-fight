# Gameplay reference register

Research date: 2026-10-18. These links are design references, not shipped assets or asset licenses. FromSoftware characters, footage, music, textures, models and animation are not licensed for redistribution by linking them. Veyr and its arena use original art and motion; code and asset licenses must be recorded separately in the project's license/credits files.

## Evidence status

Public search returned the video listings below. Direct browser playback could not be inspected: the supported in-app browser reported unavailable, and browser discovery returned no browsers. Web opens of the GameFAQs listings were restricted and the YouTube watch URL was throttled. Therefore **no video timestamps, exact animation timing, or visual gameplay observation is claimed**. Directly watching all three fights remains a research acceptance item. The combat specification contains original hypotheses to test, not purported measurements from these games.

## Public gameplay to inspect

| Boss | Public source and attribution | Verified in this research / still pending |
|---|---|---|
| Kalameet | [Dark Souls Platinum Trophy Guide 27 — Black Dragon Kalameet, Ivan Drago, GameFAQs video listing](https://gamefaqs.gamespot.com/xboxone/230461-dark-souls-remastered/videos/124156) | Search index identified title, creator and 15m28s listing duration. Playback, fight start and move timestamps unverified. |
| Sinh | [Creator-linked livestream, Ordinary_Nebula_7991](https://www.youtube.com/watch?v=hy_yx8BpR7k&t=1840s), linked by its creator in [this discussion](https://www.reddit.com/r/DarkSouls2/comments/1niibj8/sinhs_fight_was_a_lot_of_fun_but_apparently/) | Creator's public comment says fight begins at 30:40; timestamp is creator-reported, not independently observed. Video playback unverified. |
| Midir | [Dark Souls 3 Ringed City — Darkeater Midir Boss Guide, That Anarchist Nuub, GameFAQs video listing](https://gamefaqs.gamespot.com/ps4/204592-dark-souls-iii-the-ringed-city/videos/167323) | Search index identified a solo NG+7 guide and named creator. Playback and move timestamps unverified. |

These are discovery links with attributable public metadata; they are not a claim that the footage is complete, currently playable, or optimal for analysis. Prefer the creator's original player when browser access returns. Do not substitute boss-versus-boss mods for player-combat reference.

## Accessible textual evidence and design implications

The first-person [Midir Guide (no shield, no summon), Steam Community, 27 May 2021](https://steamcommunity.com/sharedfiles/filedetails/?id=2499684703) describes a front-of-head position that exposes tells, difficulty seeing tells underneath, a raised-body downward breath, long initial slam anticipation followed by a faster second strike, a mouth-open bite cue, a roar preceding a jumping bite, rear tail punishment, and recovery opportunities. It is a player's guide, not official frame data. This supports testing leg-access camera framing and distinct cues; it does not establish exact durations or hitbox behavior.

The [Sinh player's public thread](https://www.reddit.com/r/DarkSouls2/comments/1niibj8/sinhs_fight_was_a_lot_of_fun_but_apparently/) includes disagreement about ankle-focused combat and how much of the dragon remains visible. Treat this as subjective user feedback, not a mechanical fact. It motivates testing the camera from every leg instead of assuming a distant cinematic frame works during play.

The [Kalameet player discussion](https://www.reddit.com/r/darksouls/comments/18o38pu/black_dragon_kalameet_is_impossible/) reports difficulty executing intended responses even after learning the moves. This is one player's experience; it is not evidence that an attack is unavoidable. Veyr therefore requires recorded successful evasions for every implemented attack.

## Visual study checklist when playback becomes available

For each source, record exact watch URL, creator, video timestamp interval and what is actually visible. Separate observation from interpretation. Inspect one breath sweep, stomp/slam, tail response, bite, reposition and punish window if present; never invent a move absent from the footage. Record the silhouette before impact, camera angle, player escape route, planted feet, acceleration/deceleration, and the visible point where recovery ends. Timing should be approximate video observation until measured frame by frame.

Extract principles of anticipation, weight, commitment and recovery. Veyr's leg-collapse loop, timings, water-light telegraphs, visuals, arena and animations are original proposals. No source game's character mesh, rig, clip, sound or other proprietary asset belongs in the repository.
