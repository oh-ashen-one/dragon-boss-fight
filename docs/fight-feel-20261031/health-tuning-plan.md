# 150-second fight tuning — in progress

The initial candidate reduces default dragon HP from 2800 to 1200. It is not accepted yet. `-VeyrLegacyBossHealth` restores 2800 only in a fresh victory replay for comparison; it never changes HP during the fight.

The victory gate now requires terminal active wall time >0 and <=150 seconds, preserved across restart. It includes hit-stop and excludes pre-engagement, pauses, death animation and restart verification. `FVeyrFightClock` is shared by the runtime and a compiled C++ test covering start, pause/resume, terminal freeze and backward-sample defense. The obsolete 180–300-second metadata is removed.

First 1200-HP test, inherited rear-leg route: `Evidence/native-victory-20261101T060046Z`, victory at **271.078 active seconds**, correctly FAILED the deadline. First hit arrived at about 54.6 wall seconds. This policy inherited TargetLeg=2 from the core stomp exercise and spent long periods approaching/repositioning. The next policy selects front leg 0 only in victory mode; no movement speeds, collisions, stamina, attack timing, damage, telegraphs, boss choices or health during combat are altered. Both original/tuned health must be remeasured with this same policy. This is a competent input policy correction, not a bypass of the time gate.

Capture allowance: up to 18000 frames / 600 seconds, with a 4-GiB free-space stop. Films can select world 0 so the automated restart test is not presented as part of the victory. Frame timing and manifest safety tests pass; full runtime timing/visual checks remain pending.


Further control audit found the old victory controller called `TryHeavyAttack` directly, while `HeavyPressed` has no key binding in the current game. Physical LMB uses `PressPrimaryAttack` and the light-light-heavy chain. Victory now uses primary press/hold/release, actual chain timing and stamina costs; standalone attack hooks remain only in the existing action-specific labs. It holds through a chain only when the remaining safe window and stamina cover it, and releases when repositioning/healing/dodging. The primary timing/cost calculations are shared with the actual action implementation without changing their values. The front-route-only intermediate package was not used as a valid player timing result. Both health versions will be measured with this physically available attack path.


The first physically bound primary-input run (`native-victory-20261101T064819Z`) won at **217.144 active wall seconds** and correctly failed. Its first stagger + full head chain dealt 656 damage by about 105.5 s. Next candidate is **650 HP**, with the original 2800 baseline still selectable. Victory now calls the actual `CanStartGroundedAction` predicate, which allows the same run-stop interruption available to a human; prior lab readiness omitted that state. No game rules are bypassed or changed by this query.

`-VeyrStopAfterDeadline` can end a failed victory attempt just after 150 active seconds for the comparison film, leaving the living boss as-is. It never grants a win or changes health. Default victory runs continue to their actual result for tuning. Both grips remain to be verified at 650 HP; no target pass is claimed yet.


650 HP one-hand run `native-victory-20261101T072120Z`: **113.383841 active wall seconds**, passed deadline, terminal pose and restart resource/movement/primary-input checks. Both grips and original-health comparison are not yet complete.
