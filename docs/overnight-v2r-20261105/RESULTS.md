# Overnight video2rig pass — results (2026-11-06 ~05:15 ET)

Default in game now (video2rig `<Clip>V2r`, `-VeyrLegacyDragon` restores keyed clips): bite, claw (both forelegs; left is a Blender mirror), front-leg buckle (both), collapse, lying "Exposed" loop, tail smack, rear stomps (both), ground fire, and the idle. Native DragonV3B versions v035videomoves → v036idlewings → v037videowings → v038biteimpact; every import passed the native pose check (v035: 414 poses + 207 transitions, 0 failures).

Idle wings (owner note): the folded idle wings crumpled the membrane. The idle is now the video2rig idle with the wings re-based 55% toward the measured roar-flare spread (`spread_Roar_sd.json`), and every attack uses the same wing re-base so wings stay raised and spread. In-game check: clean raised membrane, no crumple.

Checks on Shipping `veyr-verified-bundle-done0t7e` (source 04cfe678…): showcase before (`-VeyrLegacyDragon`) and after both PASS every segment. Chapter lengths before→after: claw 3.23→2.86 s, tail 3.91→2.99 s, bite 1.80→2.49 s, fire 3.53→4.03 s, stagger cycle 10.66→11.48 s.

**Open regression:** scripted victory run with the new clips 315.99 s (limit 150, 0 hits taken) vs 79.78 s PASS with `-VeyrLegacyDragon` on the same build. Kept default because the owner asked for a harder boss and approved the look, but the 150 s gate fails; diagnose the auto-player's hit opportunities (likely leg/head reach or opening timing with the new clip lengths) before calling balance done.

Not done: walk cycle built (in-place treadmill cycle, 428 cm/s) but opt-in `-VeyrVideoWalk` (it moved the dragon off the showcase turn framing); turn (fit done, needs root-yaw samples); hind-leg buckles and rise keep keyed clips — the Higgsfield workspace ran out of credits (another session's Wan 3.0 jobs) after 315 committed credits, so the hind-stagger retake and the lying-start rise clip could not be generated. Blind Opus review not run.

Tools: `tools/dragon_refine/{cut_v2r_move,mirror_v2r_action,probe_v2r_points,probe_wing_spread,dashboard}.py`, `tools/unreal/prepare_video_moves_plan.py`. Specs/reports: `Local/video2rig/dragon/refine/overnight/`. Dashboard: `python3 tools/dragon_refine/dashboard.py Local/bite-review-20261105/overnight-serve --port 8815`.

## Victory bisect (2026-11-06 ~06:00 ET)

Same-build scripted victories: legacy clips 79.8 s PASS; new attacks + legacy stagger 112.5 s PASS then 192.9 s FAIL (re-run); legacy attacks + new stagger 81.7 s PASS; all new 316 s and 234 s FAIL. The video2rig stagger chain (Buckle/Collapse/Exposed V2r) is now opt-in (`-VeyrVideoStagger`); default = new attacks + raised-wing idle. Showcase and core combat (light/heavy, collapse, head bonus, rise, dodge) PASS on that default build. The auto-player's victory time is noisy with the longer, harder attacks (112–193 s), so the 150 s gate is not reliably met — consistent with the owner's "much harder boss" backlog but needs a deliberate balance pass (HP/openings) rather than reverting the animation. Bisect switch: `-VeyrLegacyClips=Prefix,...`.
