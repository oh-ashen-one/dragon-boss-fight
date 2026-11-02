# Sprint contact correction — first blind TIE, stopped

**First blind verdict: TIE. Work stopped under the owner's explicit rule. The candidate is not accepted and remains disabled by default.** A was the same-build baseline; B was the opt-in contact correction. The mapping was withheld until the verdict.

All four films use Shipping source `d0656427ab499ab2e839f203459f4e1ede457759e8e164edf5f0c561d0c032ac`. The critic read all 41 anonymous sheets, covering four sequences in both grips and both the side laboratory and ordinary gameplay cameras. No code, chronology or numerical scores were supplied. The full movies remain on the bare comparison page at port 8808. All have verified timestamps and zero failed frames.

The candidate had improved some contact measurements, but residual fidelity gates still failed. The review found no clear improvement in sprint quality: the baseline settles too abruptly, while the candidate freezes the last stride instead of finishing the stop. No further tuning, import, engine launch or second review follows this TIE without owner continuation. This is not a completion claim for the sprint item or full backlog.

The following critic observations are preserved verbatim. They are judgments from sampled images, not proof of continuous motion or human input feel.

I read all 41 sheets. The start, run, turnaround and downshift look effectively the same in A and B. The only consistent difference is how the knight settles after the stop, and each version has its own flaw there, so neither is clearly better.

**Coverage and limits**
- **Sheets read:** sequence.json plus all 41 sheets (A: 21, B: 20). That covers SprintStop and WalkSprintWalk, one-handed (1H) and two-handed (2H), in both the lab and gameplay cameras. Black tiles were padding.
- **Sampling:** gaps between tiles are about 25–435 ms. A and B are often sampled at slightly different moments (offsets up to about 0.07 s, e.g. lab WalkSprintWalk_2H tile 1 at 40.615 vs 40.71), so stride-phase differences between matching tiles are often just sampling.
- **What the samples can't show:** they can't prove continuous smoothness, foot sliding between tiles, input feel, or performance. A pose change between two tiles might be a snap or a quick blend.
- **Lighting:** the gameplay camera is dark and mostly shows the knight from behind, so foot contact is weak evidence there.

**By phase**

*Start and turnaround (lab about 4.68–5.1 s, 16.3–16.7 s, 28.2–28.7 s, 41.9–42.4 s)*
- Both pivot through the same intermediate poses: weapon swing at 4.773/4.775, back-facing push-off at 4.81, first sprint stride at 4.88.
- The only difference is the starting stance. A stands upright with feet together (lab SprintStop_1H 3.408–4.679). B stands with one foot ahead of the other and wider apart (3.41–4.68).
- Neither shows a pinned foot or a pop that A lacks or B lacks.

*Sprint body (lab 5.0–7.1 s, 16.6–18.6 s, 29.2–30.8 s, 42.9–44.5 s)*
- The sprint poses match tile for tile in both grips: deep forward lean, full rear-leg kick, bent support knee, 2H weapon carried high. Examples: lab SprintStop_1H 6.845–6.974; lab SprintStop_2H 17.015–18.344.
- Both read as a convincing heavy sprint with grounded support feet. I found no variant-specific jerk.
- Differences like lab WalkSprintWalk_1H 29.279/29.28 (B's weapon higher) look like sampling-phase offsets, not quality differences.

*Downshift from sprint to walk (lab WalkSprintWalk_1H about 30.8–31.1 s, 2H about 44.5–44.9 s)*
- Both go from sprint crouch to upright walk within about 70–130 ms, with one in-between tile each:
  - A: 30.846 crouch → 30.881 weapon diagonal → 30.916 walk.
  - B: 30.916 crouch → 30.94 in-between → 31.012 walk.
- This is equally abrupt in both. I found no meaningful preference.

*Stop and settle — the only consistent difference*
- **A pulls the feet together into a neutral stance very quickly in the lab view.** A moving stride becomes a closed, narrow stance within one sample gap:
  - lab WalkSprintWalk_2H: 45.511 → 45.583 (72 ms)
  - lab WalkSprintWalk_1H: 31.94 → 32.046
  - lab SprintStop_2H: 18.745 → 18.839

  That may be a foot pop or slide, though the samples can't prove it. The settled pose is then neat and balanced (lab 33.342, 47.059). From the gameplay camera, A's stance reads as a clean, shoulder-width planted stance (game SprintStop_2H 18.736–19.995; game WalkSprintWalk_1H 32.473–33.351).
- **B keeps the feet where the last step left them.** I saw no in-between collapse, which suggests better contact preservation. But the resulting pose is a wide walking stride held frozen:
  - lab WalkSprintWalk_1H: held from 32.176 to 33.386
  - lab WalkSprintWalk_2H: held from 45.583 to 47.132, about 1.5 s

  In the lab view this looks like a stride frozen mid-step, not a finished stop. From the gameplay camera it reads as a narrow, lopsided silhouette with the legs overlapping (game SprintStop_2H 18.744–20.003; game WalkSprintWalk_1H 32.444–33.304; game WalkSprintWalk_2H 45.781–47.034).
- In SprintStop the gap is smaller: both have similar crossed-leg braking poses (7.139/7.153), then A goes narrow and B stays staggered.

**By sequence and camera**

| Sequence | Lab | Gameplay |
|---|---|---|
| SprintStop_1H | Start, run and turnaround identical; A settles narrow, B staggered; no preference | Effectively identical |
| SprintStop_2H | Run identical; A's feet close fast (18.745→18.839); B holds a staggered stance | A's planted stance reads slightly cleaner |
| WalkSprintWalk_1H | Downshift equally abrupt; A's feet close fast (31.94→32.046); B holds a wide stride to 33.386 | A symmetric, B asymmetric; small difference |
| WalkSprintWalk_2H | A's feet close in 72 ms (45.511→45.583); B holds a frozen wide stride 45.583–47.132 | B narrow and overlapping, A planted; small difference |

**Regressions, each relative to the other**
- **A:** feet appear to snap together at the stop in every lab sequence, a likely pop or slide.
- **B:** the stop leaves a held mid-stride stance, a stiff, unresolved stance that looks frozen mid-stride, most visible in lab WalkSprintWalk_2H 45.583–47.132 and lab WalkSprintWalk_1H 32.176–33.386.

**Biggest gap (applies to both)** — make the stop settle visibly over several frames. Testable as follows:
1. In the lab view, from the last stride tile to the settled idle tile, at least two intermediate tiles must show a step-in or weight shift. A currently has none; B never settles at all.
2. The final stance must be a deliberate idle width, not the last walking stride.
3. The settled planted feet must not move against the floor checker pattern across the settle tiles.

**Conclusion:** sprint quality is the same in both. The only difference is a trade-off at the stop: A gets a cleaner final pose but possibly snaps into it; B keeps the feet planted but leaves a frozen stride. Neither is clearly better overall.

TIE
