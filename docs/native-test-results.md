# Native Unreal acceptance results

Observed native rendered gameplay from input-only replays. This does not establish physical-key coverage, final-art quality or exclusive performance. Engine 5.8.3; output 1280×720, screen percentage 100, cap 60 FPS. Screenshots/evidence writes and shared workloads affect timing.

| Scenario | Result | Game seconds | Observed outcome |
|---|---|---:|---|
| core | PASS | 37.95 | jump light heavy collapse head bonus completed rise and dodge contact observed |
| death | PASS | 19.63 | death terminal pose, resource reset, movement and attack after restart verified |
| leg0 | PASS | 28.29 | leg 0 isolated light/heavy stagger, correct buckle and collapse observed; other three legs unchanged |
| leg1 | PASS | 30.88 | leg 1 isolated light/heavy stagger, correct buckle and collapse observed; other three legs unchanged |
| leg2 | PASS | 27.55 | leg 2 isolated light/heavy stagger, correct buckle and collapse observed; other three legs unchanged |
| leg3 | PASS | 28.77 | leg 3 isolated light/heavy stagger, correct buckle and collapse observed; other three legs unchanged |
| victory | PASS | 188.09 | victory terminal pose, resource reset, movement and attack after restart verified |

The victory terminal occurred at **182.38 seconds (3:02)**. Total 188.09 seconds includes terminal settling and restart acceptance. This meets the requested 180–300-second fight interval for this replay policy.

Verified source identity: `0431ad5fa32fc53e01c25779b4721bdee61476dcb2493df9a4943100b46cab17`, checkpoint `85686c4`.

These results predate subsequent head-marker, mouse-entry, stronger jump/avoidance coverage, video and audio changes. Those require their own stamped build and native regression. Both main characters remain temporary primitives. Empty-flask, rear-facing guard, guard-break, full per-move avoidance, physical input, final art, acoustic review and continuous video remain open.

## Recorded regression of later source

Source `dfcf89ae79be8a72455f7be5a1fbb843f614704ae1efa3a29ff34d0f4676cf20`: **FAIL** at 180.02 game seconds because no invulnerable dodge contact was observed. Jump, eight collapses, 37 head-bonus hits and boss defeat were recorded; these do not satisfy the missing assertion. Continuous recording saved 979 real native frames with zero failed writes and 500 skipped capture slots. PNG compression/write time was 78.49 seconds over 184.49 wall seconds. The silent variable-frame-rate encode passed per-frame timestamp verification. This is failed-test motion evidence with significant capture overhead, not a performance or visual-completion claim.

The owner subsequently granted standing Veyr launch and spending authorization. The launch hold is superseded; bounded debugging and workload ownership remain in force.

## Repaired packaged app regression

Actual signed/extracted packaged source `c8c59add517853a71c3924153649a855c4b297d3dc35031e1b0c78e3bf9d3871`:

| Scenario | Result | Game seconds | Evidence |
|---|---|---:|---|
| Recorded core | PASS | 40.829 | Actual dodge contact, jump, light/heavy contacts, collapse, head bonus and recovery |
| Controls | PASS | 12.215 | Movement, jump, attacks, roll, stamina recovery, lock, guard contact, heal and full-health rejection |
| Avoidance | PASS | 52.576 | All six naturally selected boss moves threatened the player during windup and recovered without damage |
| Victory/restart | PASS | 191.837 | Defeat at 186.124 seconds (3:06), fresh resources, movement and attack after restart |

Recorded core saved 350 actual native frames, skipped 26 capture slots and had zero failed writes. Pixel copying totaled 0.0767 seconds; PNG compression/writes used 27.12 seconds on a worker over 43.43 wall seconds. This is not an exclusive frame-rate benchmark. Video is silent, timestamp-preserving and contains no synthesized frames.

Later editor source `555a679b9decdec627bde5f9caa0124bc0058bcd6d269deb41aae1a15afbc441` fixes initial physical mouse capture and adds healing/guard boundary tests. Physical PIE capture, movement, light/heavy, jump and lock-on were observed. The new boundary modes and full physical-key coverage remain pending. Both gameplay characters remain primitives; successful standalone gameplay does not establish final animation, art, sound or camera quality.


## Healing boundary regression

Editor-game source `b6cb077f370a3398e6c22b3cacd3276ca7d35ca4f6d3bc01fd3574dea25e6c22` (source checkpoint `3dfca14`) passed the healing boundary scenario. Four actual healing completions each consumed exactly one charge and capped health at 100: 70→100, then three 66→100 recoveries. After another natural injury to 66 HP with zero charges, a heal request left health, completion count and action unchanged for 1.458 seconds. The process exited normally. This validates gameplay rules with primitive presentation; imported-character motion and physical-key acceptance are separate.


The same source passed the guard boundary scenario in 21.389 game seconds. A front Fire contact reduced health by 4.5 and consumed guard stamina. A rear Bite with 42.81 stamina dealt the full 34 damage, with no block or guard break. Later, a front Bite against 1.06 stamina dealt full damage, depleted stamina to zero, incremented guard-break count and entered Stagger. All cases used preceding-frame guard/facing/grounded evidence and actual contact counters; process exit was 0.

## Customuse packaged candidate e54eef34

The signed, freshly extracted standalone app uses source `e54eef347c7382b8e4b0a4a64248c0d00e84cbcd1015d23f4c026f3dbd261412`, Knight v012 and Dragon v006. Both Customuse characters remained active.

| Scenario | Result | Game time | Scope |
| --- | --- | ---: | --- |
| Core | Pass | 44.906 s | Jump, light/heavy leg contacts, collapse, three head bonus hits, completed rise, invulnerable dodge contact |
| Victory/restart | Pass | 260.623 s total | Boss defeat at 254.986 s (4:15), terminal pose, fresh resources, movement and attack after restart |
| Leg 0 | Pass | 27.705 s | Selected leg staggered and buckled; other three unchanged |
| Leg 1 | Pass | 28.308 s | Selected leg staggered and buckled; other three unchanged |
| Leg 2 | Pass | 41.091 s | Selected leg staggered and buckled; other three unchanged |

No warning-containment failure was recorded in these runs. Core video requested 10 FPS: 330 frames saved, zero failed writes and 67 skipped capture slots; worker PNG work totalled 29.826 seconds and pixel copying 0.077 seconds. Victory video requested 8 FPS: 1,645 frames saved, zero failed writes and 82 skipped slots; worker PNG work totalled 149.257 seconds and pixel copying 0.388 seconds. These silent recordings preserve actual wall-clock frame timestamps; capture and shared workloads affect performance.

Rendered review found close/collapse camera floor clearance and sparse fire continuity still needed correction. The mechanical passes are not final visual acceptance. A later camera/marker and fire presentation revision is compiled but not yet accepted in native rendering.
