# Build 004: duplicate TypeDB metadata investigation

Read-only investigation of Unity 6000.3.20f1, 2026-10-18. No editor, build, cache mutation, process control, or Git operation was performed for this investigation.

**Implementation-owner follow-up:** The owner reported that the owned Unity editor/build 004 had ended, then moved exactly the six numbered metadata files into `Local/cache-quarantine004`, preserving their subdirectories and filenames, with no deletion. Native player 004 uses its own built data. Build 005 is the planned verification; no error-disappearance or runtime-fix result is claimed here.

A subsequent read-only check verified that all six quarantined files retain the SHA-256 hashes recorded below and that zero numbered JSON files remain under `Library/BuildPlayerData`.

## Finding

The four numbered `TypeDb-All` JSON files account for **all 124 reported duplicate registrations, with an exact assembly/class multiset match**. This is stronger evidence than the generic error text suggesting duplicate source classes. A confirming rebuild after isolating these files is still required.

| Folder under `Library/BuildPlayerData` | Metadata file | Type count | Assembly-CSharp | Unity.Multiplayer.Center.Common |
| --- | --- | ---: | ---: | ---: |
| Editor | TypeDb-All 2.json | 28 | 12 | 16 |
| Editor | TypeDb-All 3.json | 34 | 18 | 16 |
| Player | TypeDb-All 2.json | 28 | 12 | 16 |
| Player | TypeDb-All 3.json | 34 | 18 | 16 |
| Editor | TypeDb-All.json (current) | 43 | 27 | 16 |
| Player | TypeDb-All.json (current) | 43 | 27 | 16 |

Every numbered-file type is already present in its folder's canonical file. Combining only the four numbered files yields 60 Assembly-CSharp and 64 Multiplayer Center registrations, exactly matching `Local/build-004.log` and its 124-line extracted `Local/build-messages.txt`. Both multiset differences are empty. Numbered files are older snapshots, not byte-identical copies of the current data.

The Player folder also contains `RuntimeInitializeOnLoads 2.json` and `RuntimeInitializeOnLoads 3.json`. These are byte-identical to each other and contain an older `Encounter.StartGame` registration. The current canonical file has changed. They should be preserved and isolated alongside the numbered TypeDB metadata, rather than remain possible stale initialization inputs.

Log anchors (local logs are private and are not included in this document):

- Line 457 generates `Library/BuildPlayerData/Editor/TypeDb-All.json`; line 458 reports that Bee step succeeded.
- First duplicate error: line 461. Last duplicate error: line 1937. The error stack goes through `BuildPipeline.BuildPlayer` and `VeyrBuild.Build`.
- Line 1948 confirms `BuildOptions.CleanBuildCache` was actually set. All 124 duplicate errors precede this message.
- Line 4946 reports `VEYR_BUILD_RESULT Succeeded errors=124`. A successful BuildReport is not a zero-error report.
- `Assets/Editor/VeyrBuild.cs:37` supplies `BuildOptions.CleanBuildCache`; line 39 extracts errors/exceptions into the messages file.

## Narrow, reversible experiment for the implementation owner

After the owned editor/build has fully exited and no process is writing this project's cache:

1. Preserve build 004, its logs and existing screenshots/video. Record hashes and a manifest of the six files below outside generated cache directories.
2. Move **only** these six files to matching `Editor`/`Player` subfolders under the private `Local/cache-quarantine004` directory. Use explicit filenames, not a wildcard. Refuse to overwrite an existing quarantine destination. Keep the canonical `TypeDb-All.json` and `RuntimeInitializeOnLoads.json` files.

   - `Library/BuildPlayerData/Editor/TypeDb-All 2.json`
   - `Library/BuildPlayerData/Editor/TypeDb-All 3.json`
   - `Library/BuildPlayerData/Player/TypeDb-All 2.json`
   - `Library/BuildPlayerData/Player/TypeDb-All 3.json`
   - `Library/BuildPlayerData/Player/RuntimeInitializeOnLoads 2.json`
   - `Library/BuildPlayerData/Player/RuntimeInitializeOnLoads 3.json`

3. Run one fresh owned Unity process with the same version, source and build settings, preserving old output before this project's fixed build-output path is reused. Keep its new complete log and BuildReport summary.
4. Compare TypeDB error count (target: zero), BuildReport result, initialization/scene behavior, and whether numbered metadata reappears. Run the native player to verify bootstrap happens once and combat/restart remain functional.
5. If numbered files reappear, stop repeating clean builds. Preserve the new files and timestamps. Identify the writer using an authorized project-scoped observation; do not disable sync, alter security settings, or modify unrelated workloads based on an inference.

Do not remove all of `Library`, reset package caches, change the Unity version, remove Multiplayer Center, or rename project classes for this first experiment. If the six-file isolation fails without regenerated numbered files, the next bounded test is a separate source snapshot with its own new Library/output, preserving the original project, package lock, failed artifacts and metadata for comparison.

## Origin remains unproven

The numbered TypeDB snapshots have earlier timestamps and grow from 28 to 34 types; the current file has 43. The build log explicitly names only the canonical output, with no references to the numbered filenames. A read-only filename check found no similarly numbered files under `Assets`, `Packages`, or `ProjectSettings`, but found 207 numbered files under `Library/Bee` in addition to these six metadata files. No broader cache cleanup is justified by that count alone.

This pattern is consistent with copied/versioned generated files, including possible filesystem synchronization, but neither Unity nor a sync service was identified as the writer. File timestamps do not establish provenance. Do not label it a confirmed Unity 6000.3 bug or a confirmed sync failure.

## Primary documentation and research limits

[Unity 6.3 CleanBuildCache API](https://docs.unity3d.com/6000.3/Documentation/ScriptReference/BuildOptions.CleanBuildCache.html) specifies rebuilding cached scripts and player data. The local log proves the option was used; it does not promise removal of arbitrarily named stale JSON files. The ordering and exact duplicate membership explain why repeatedly applying that option is a poor next experiment.

Unity Issue Tracker searches were attempted for TypeDB/duplicate-registration errors. The search endpoint could not be retrieved through the available web tool, and search results did not yield a verifiable matching issue. No issue number, official fix, or known-bug claim is asserted. The recommended six-file isolation is based on directly inspected project metadata, not an unverified forum workaround.

## Hashes before isolation

| Relative path under `Library/BuildPlayerData` | SHA-256 |
| --- | --- |
| Editor/TypeDb-All 2.json | `568e450cf5b09887419dc260ce65d45d15b1ce0650f3f040029c1060490b8b48` |
| Editor/TypeDb-All 3.json | `327bdd22e47ae73c19fc1407c681bdf5c9ec7b322287f58f3f6e0ea30ce642c5` |
| Player/TypeDb-All 2.json | `6f698f99cd9681c09392b5729642348e9d31bc53adf175b66a7d3b9fb98e1262` |
| Player/TypeDb-All 3.json | `a6a03a6fd8cbb2b96208d6a4ca55061490547b7745dec31d33a75395bb8ac806` |
| Player/RuntimeInitializeOnLoads 2.json | `5fccc43a6ffcfc1eaf2ed3001914bd31a7e82a09a1a0fd2bd7887f5ed29e91c6` |
| Player/RuntimeInitializeOnLoads 3.json | `5fccc43a6ffcfc1eaf2ed3001914bd31a7e82a09a1a0fd2bd7887f5ed29e91c6` |

## Build 008 follow-up: recurrence and exact accounting

Read-only follow-up on 2026-10-18. The build 004 observations above are historical. Numbered metadata has since reappeared; this follow-up did not move, delete or regenerate any cache file, launch an engine, or inspect processes.

`Local/build-008.log:5823` reports `VEYR_BUILD_RESULT Succeeded errors=182`. All **182** extracted messages are duplicate TypeDB registrations. The complete assembly/class multiset matches the four numbered TypeDB files exactly, with no unmatched entries in either direction. `Local/build-messages.txt` has the same error multiset. The errors comprise **118 Assembly-CSharp** and **64 Unity.Multiplayer.Center.Common** registrations, across 46 distinct types.

| Metadata snapshot | Editor types | Player types | Combined duplicate registrations |
| --- | ---: | ---: | ---: |
| TypeDb-All 2.json | 45 (29 game + 16 package) | 45 (29 game + 16 package) | 90 |
| TypeDb-All 3.json | 46 (30 game + 16 package) | 46 (30 game + 16 package) | 92 |
| Total numbered files | 91 | 91 | 182 |

Each folder's canonical `TypeDb-All.json` contains 46 types. Every numbered type is already in that canonical file. In both folders the only type added from snapshot 2 to snapshot 3 is `CombatReplay+HealingTrial`. Both snapshot-3 TypeDB files are **byte-identical to their respective current canonical files**. All three Player `RuntimeInitializeOnLoads` JSON files are also byte-identical. This accounts for the larger error total without attributing the recurrence to duplicated source definitions.

All six reappeared numbered files have different SHA-256 hashes from the corresponding preserved build-004 quarantine files. Consequently, these are not simply the original quarantined bytes returned unchanged. This does not identify who wrote or copied them. Modification times are older than the current canonical generation; times below are explicitly UTC and should not be confused with a shell/UI local-time display.

| Reappeared path under Library/BuildPlayerData | Modification time UTC | SHA-256 |
| --- | --- | --- |
| Editor/TypeDb-All 2.json | 2026-10-18T04:16:19+00:00 | `f1c3ccf96f856ddb0ddf2ba884968f1d639bc0bdbfcbb0a5d549a2857eb6b73f` |
| Editor/TypeDb-All 3.json | 2026-10-18T04:21:29+00:00 | `a5052fdc1f90aba839041d6723094f3b6048d9463165ab166396c173b6dc2a36` |
| Player/RuntimeInitializeOnLoads 2.json | 2026-10-18T04:16:21+00:00 | `d90e1bc7ca67be33cb81ee3b1bb967e9519022e06ee7306db7f887a9f9942862` |
| Player/RuntimeInitializeOnLoads 3.json | 2026-10-18T04:21:30+00:00 | `d90e1bc7ca67be33cb81ee3b1bb967e9519022e06ee7306db7f887a9f9942862` |
| Player/TypeDb-All 2.json | 2026-10-18T04:16:21+00:00 | `d1d7512cb58219dce83aa50552ffc94b9bce8e821135f2efb598fff60b579e8f` |
| Player/TypeDb-All 3.json | 2026-10-18T04:21:30+00:00 | `1f5569f43c86063be25a04dd8a45c6dbce7fc28a58ff69bfe9b8c28292a41bcf` |

Private evidence is preserved in `Local/type-db-008-evidence.json`: nanosecond modification/change times, birth times where available, sizes, hashes, per-file type membership, quarantine comparisons, complete error multiplicities, log hashes and line numbers. A second read verified that all nine inspected metadata hashes remained unchanged during this investigation. The manifest contains no copied raw log text beyond the build-result line and is intended to remain local.

Build-008 log anchors: canonical Editor metadata generation at line 694; first duplicate at 698; canonical Player initialization metadata generation at 1820; last duplicate at 2812; `CleanBuildCache` message at 2823; successful-but-182-error summary at 5823. The named generator outputs are canonical paths; these log lines do not establish a writer for numbered files.

### Next bounded verification

The implementation owner is preparing a separate clean source snapshot under `/tmp`, with its own generated Library and build output, after the owned native build-008 test completes. This is the appropriate changed experiment after recurrence: preserve the original project, its cache/quarantine, build 008 and evidence; do not repeat deletion/rebuild cycles in the same cache. Copy only the intended source/configuration and preserve the package lock and Unity version. The snapshot must not inherit Library, Temp, Obj, old build output or private Local evidence.

For the new build, record the source snapshot identity, Unity version, options and result; enumerate generated metadata and compare duplicate error count. Zero errors and no numbered files would show that the isolated source snapshot builds cleanly under those conditions, **not** identify the original writer. Reappearance in the isolated snapshot would be a distinct reproducible observation to preserve before further changes. Separately verify native bootstrap/combat/restart; a clean BuildReport cannot establish playability. No build-009 outcome is asserted by this follow-up.
