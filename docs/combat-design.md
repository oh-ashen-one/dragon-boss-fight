# Veyr, the Cinder Warden — combat specification

Status: original design proposal, not measured gameplay or an implemented-feature claim. Reference access and research limitations are recorded in [references.md](references.md). Ship one excellent phase before adding another.

## Identity and arena

Veyr is a quadrupedal furnace dragon with broad basalt armor, copper seams, two torn sail wings and a low, forked crown. Four weight-bearing legs remain visually distinct. Its exposed throat burns warm ivory; it has no copied silhouette, move animation, sound, character asset, or lore from the reference games.

The drowned basalt cathedral is a single roughly 60 m diameter combat space. Broken roof ribs frame a moonlit aperture; shallow water reflects the dragon's ember light. Keep the central 44 m clear. Columns, rubble and stairs stay outside the combat ring. Cosmetic water never hides telegraphs or changes collision height. No cliffs or unintended invisible-wall kills.

## Core loop and initial values

Read the dragon, evade one committed attack, land one or two sword cuts on a leg, then reposition. Exploit a collapsed head for the large reward. Target a learned-player victory of 180–300 seconds; tune from recorded real input sessions, never from a scripted damage loop alone.

| Setting | Starting value | Purpose |
|---|---:|---|
| Player health / stamina | 100 / 100 | Three substantial mistakes usually kill |
| Sword total / active interval | 0.72 s / 0.23–0.38 s | Visible contact governs damage |
| Sword stamina / damage | 20 / 24 leg, 12 body, 36 normal head | Legs are strategically useful |
| Exposed-head sword damage | 120 | Obvious major reward |
| Dodge total / invulnerability | 0.62 s / 0.08–0.35 s | Start and finish remain punishable |
| Dodge cost / travel | 28 / 4.1 m | Two attacks plus two dodges is nearly a full bar |
| Stamina recovery | 24/s after 0.7 s | Brief recovery between exchanges |
| Healing | 3 charges, 55 health, 1.35 s commitment | No instant or unlimited heal |
| Boss health | 2800 | Provisional; tune against 3–5 minute real play |

Queue one action within 0.12 s of recovery end. Reject insufficient-stamina actions without consuming stamina or entering a stuck state. A sword swing damages at most one boss region once; select the closest valid contact, preferring a leg/head over the enclosing body. No damage through idle sword overlap.

## Four separate leg regions and collapse

Each leg has its own 0–100 stagger meter. Every confirmed sword hit contributes 25 to that leg only. No passive decay in the first version. Four hits on one leg cause that specific leg to buckle; four independent regions does **not** mean requiring all four legs to break first. Make the struck joint glow and flinch, with a small world-space meter only while targeted/recently struck. Front-left means the dragon's left.

1. At threshold, cancel the current attack and all of its damage volumes immediately. Play that leg's 0.65 s buckle with a clear knee fold and shoulder/hip drop.
2. Play a 1.0 s whole-body collapse, planting the head on a reachable patch of ground. Collapse itself does not damage or imprison the player. Permit escape through the descending torso; do not push the player into walls.
3. Start the **7.0 s head vulnerability** only when the jaw reaches sword height. Show ivory throat light, a distinct sound, and `HEAD EXPOSED`. Head hits deal 5× leg damage. Other regions retain ordinary damage but add no stagger.
4. Telegraph the last 1.0 s with inhalation and fading throat light, then stand over 2.0 s without damage. Reset leg meters, grant 2.0 s stagger protection, and wait at least 0.8 s before the next windup. Preserve boss health and player agency.

Aim for 3–5 collapse opportunities during a learned victory. Do not force the player to exploit them to finish. Starting values are subject to measured tuning; the duration target is not yet validated.

## Attack grammar

All seconds below are original target timings, not measured timings from other games. Freeze aiming in the final 0.35 s of windup. No instant pivots, hitbox on idle limbs, invisible follow-ups, or full-body contact damage.

| Attack | Windup / active / recovery | Readable anticipation and safe response | Damage |
|---|---|---|---:|
| Bellows sweep | 1.6 / 2.1 / 2.0 s | Chest fills, throat lights, head draws to starting flank; water sparks show the swept fan. Run to the unswept flank or behind the shoulder. Sweep rotates once, not homing. | 30 per attack maximum |
| Basalt stomp | 1.1 / 0.22 / 1.35 s | One named foot lifts high; a 2.6 m disk brightens beneath it. Leave the disk or time a dodge. Opposite legs remain punishable. | 32 |
| Counterweight tail | 1.35 / 0.55 / 1.6 s | Hip rotates away, tail rises and draws back; rear crescent appears. Dodge through the sweep or move to the front flank. No damage ahead of chest. | 28 |
| Furnace bite | 0.95 / 0.25 / 1.45 s | Neck coils, jaws separate and hold; short front wedge marks reach. Dodge sideways; head remains low in recovery. | 34 |
| Processional lunge | 1.4 / 0.85 / 1.9 s | Dragon crouches, wings spread; a straight corridor appears. Sidestep out of the committed lane. No turning during travel; stops before arena boundary. | 36 |
| Ash retreat | 1.15 / 0 / 1.6 s | Backward two-step and wing brace move the dragon 6 m. No damage. Leave head/forelegs reachable at completion. | 0 |

Ground indicators use shape, motion and brightness, not color alone: outline = anticipation, filled hot area = active, fully extinguished = safe. Match damage geometry exactly to indicators, apart from a 0.15 m safe margin inside the visual boundary. Breath may use several volumes but may hit a given player only once per execution. Lingering artistic embers do no damage.

Select attacks from valid distance/angle bands; never choose a rear tail swipe against a frontal target. Do not repeat an attack more than twice or reposition twice consecutively. Require at least 1.0 s neutral breathing after recovery; use it to turn with planted steps. Reserve a clear escape route at arena edges. No second phase until acceptance below passes.

## Camera and readability

Free camera is default; optional lock-on targets a low chest point (about 3 m), switching smoothly toward the exposed head. Mouse/stick can override lock, and unlock never snaps. Desired distance 8–11 m, vertical field of view 62–70°, player offset 1.7 m. Pull back gradually near the dragon; avoid framing the sky because the chest is overhead. Sphere-cast against arena geometry, excluding dragon and player; fade occluding dragon parts if necessary. Keep the player, current foot telegraph, and safe direction visible while under the torso. Camera shake is brief and bounded, with an off option; hit pause cannot lengthen damaging intervals.

## Suggested interfaces

`HitRegion { FrontLeft, FrontRight, RearLeft, RearRight, Head, Body }` with a stable root combat receiver. `DamageHit(swingId, region, amount, stagger)` deduplicates across overlapping colliders. `AttackStarted(id)`, `AttackActive(id, bool)`, `LegBuckled(region)`, `HeadWindowChanged(bool, seconds)`, and `EncounterEnded(result)` separate combat state, animation, VFX and HUD. Each attack owns a cancellation token/serial so stale callbacks cannot re-enable damage after collapse, death or restart. Treat death as the highest-priority state; reset all timers, hit registries, effects and meters on restart.

## Acceptance evidence required before polished handoff

| Test using actual player inputs | Pass condition |
|---|---|
| Strike each leg separately | Only the struck meter changes; one swing cannot double-hit neighboring colliders |
| Trigger collapse during windup and active attack | Correct leg buckles; old damage stops; head becomes reachable; exposure lasts 7.0 s ± one simulation tick |
| Strike normal body, normal head and exposed head | Health deltas match settings; exposed head has the intended major reward |
| Dodge every attack and deliberately mistime it | At least one repeatable safe response per attack; early/late errors can take damage; one execution cannot multi-hit |
| Exhaust stamina and use all healing | No negative values, input lock or extra charge; resources recover as designed |
| Fight near all edges and underneath | No lost player, camera penetration, trapping, unseen attacks or unreachable head |
| Die, restart, win, restart | Correct terminal state; no simultaneous win/death ambiguity, stray damage or duplicated HUD; clean initial state |
| Complete three learned fights | Report each duration, frame settings, actual frame-time measurement and failure notes; median target 180–300 s |

Save native rendered gameplay, matching-build screenshots, and a source commit/build identifier beside the recordings. Developer console checks and compilation support these tests but cannot replace them. Label temporary models until the Tripo/Blender asset and animation pipeline is actually integrated and visually reviewed.
