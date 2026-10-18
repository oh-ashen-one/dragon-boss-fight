using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using UnityEngine;

/// <summary>
/// Native, real-time input replay. No health writes, teleports, time scaling or
/// direct attack calls. Run with --replay combat|death|victory|avoidance|legregions|healing --capture-dir PATH.
/// Decisions are deterministic; wall-clock timings remain subject to frame rate.
/// </summary>
[DefaultExecutionOrder(-100)]
public sealed class CombatReplay : MonoBehaviour
{
    [Serializable] public sealed class Observation
    {
        public float seconds, playerHealth, stamina, bossHealth;
        public int frame, swings, dodges, hitsTaken, dodgedHits, collapses, lastHitRegion, flasks;
        public string name, state, playerAction, bossMove;
        public Vector3 playerPosition, playerForward, headPosition;
        public float headDistanceFromSwordOrigin, headHorizontalDistance, headVerticalOffset, headFacingDot, headWindowRemaining;
        public bool headExposed;
        public float[] legStagger;
    }
    [Serializable] public sealed class HealingTrial
    {
        public int ordinal, chargesBefore, chargesAfter;
        public float healthBefore, expectedHealth, maximumObservedHealth;
        public Observation request, accepted, completed;
        public string outcome = "in_progress";
        public bool successful, interrupted;
    }
    [Serializable] public sealed class LegRegionContact
    {
        public int intendedRegion, actualRegion;
        public Observation before, after;
        public float[] staggerBefore, staggerAfter;
        public float bossDamage;
        public bool targetMatched, contactedMeterIncreased, otherMetersUnchanged, independentRegionVerified;
    }
    [Serializable] public sealed class AttackTrial
    {
        public string move, footprint, outcome = "in_progress";
        public Observation windup, active, recovery;
        public Vector3 groundOrigin, escapeTarget;
        public float healthAtWindup, minimumHealth, damageTaken, escapeDistance;
        public int hitsAtWindup, hitsTaken;
        public bool windupObserved, activeObserved, recoveryObserved, initiallyThreatened, avoided;
    }
    [Serializable] public sealed class ScreenshotRecord
    {
        public string filename, status = "queued", error = "";
        public Observation originEvent, renderedSnapshot;
        public float capturedSeconds = -1, queueDelaySeconds = -1;
        public int capturedFrame = -1;
    }
    [Serializable] public sealed class InputSample
    {
        public float seconds;
        public Vector3 worldMove;
        public bool attack, dodge, heal;
    }
    [Serializable] public sealed class Assertion
    {
        public string name, status, detail;
    }
    [Serializable] public sealed class Report
    {
        public string mode, runId, status = "running", reason = "", unityVersion, applicationVersion;
        public string method = "Real-time native gameplay through PlayerCombat.SetReplayInput; no health/state writes, teleports or time scaling. State-reactive deterministic policy; frame timing can affect outcomes.";
        public float elapsedSeconds, victoryDurationSeconds = -1;
        public bool victoryDurationInRange;
        public string victoryDurationDefinition = "Real-time seconds from initial encounter binding to observed boss defeat, excluding restart and capture flush. Required range: 180 through 300 inclusive.";
        public int width, height;
        public bool legDamage, buckle, collapse, exposed, headDamage, rise, dodgePerformed, dodgeContact, playerDeath, bossDefeat, restart;
        public string avoidanceMethod = "Movement-only bait and escape, no forced boss attacks. Threat footprint is a source-derived ground model recorded per trial; avoidance also requires actual full attack progression, movement and no damage/hit-count increase.";
        public int initialHealingCharges, successfulHeals, emptyHealInputRequests;
        public bool healingCapObserved, healingHealthNeverExceededCap, emptyChargesRejected;
        public Observation emptyHealStart, emptyHealEnd;
        public List<HealingTrial> healingTrials = new List<HealingTrial>();
        public List<LegRegionContact> legRegionContacts = new List<LegRegionContact>();
        public List<AttackTrial> attackTrials = new List<AttackTrial>();
        public List<Observation> observations = new List<Observation>();
        public List<InputSample> inputs = new List<InputSample>();
        public List<Assertion> assertions = new List<Assertion>();
        public List<ScreenshotRecord> captures = new List<ScreenshotRecord>();
        public List<string> screenshotRequests = new List<string>();
        public List<string> screenshotsWritten = new List<string>();
    }

    static CombatReplay active;
    Report report = new Report();
    PlayerCombat player;
    DragonBoss boss;
    string directory, prefix;
    float started, stateStarted, nextSwing, nextInputSample, nextSave, priorBossHealth;
    DragonBoss.CombatState previousState;
    bool initialized, finishing, restarting, windupDodgeSent, reachedLeg;
    Vector3 fixedStompCenter;
    readonly Queue<ScreenshotRecord> captureQueue = new Queue<ScreenshotRecord>();
    bool captureInProgress;
    int lastCapturedFrame = -1;
    float fightStarted, nextHeadAimObservation;
    static readonly string[] AvoidanceMoves = { "Lunge", "Stomp", "Bite", "Tail", "Breath" };
    readonly HashSet<string> avoidedMoves = new HashSet<string>();
    AttackTrial avoidanceTrial;
    Vector3 avoidanceBossOrigin, avoidanceBossForward, avoidanceBossRight, avoidanceRefuge;
    static readonly int[] LegVisitOrder = { 0, 2, 3, 1 };
    readonly bool[] verifiedLegRegions = new bool[4];
    Observation priorLegObservation;
    int legSwingTarget = -1;
    bool healingInitialized;
    string healingPhase = "bait";
    int healingDamageBaseline;
    float healingPhaseStarted, nextEmptyHealInput, emptyPriorHealth;
    Vector3 healingRefuge;
    HealingTrial healingTrial;
    const float Timeout = 300f;
    float Elapsed => Time.realtimeSinceStartup - started;

    void Awake()
    {
        if (active != null && active != this) { Destroy(gameObject); return; }
        active = this;
        DontDestroyOnLoad(gameObject);
    }

    void Start()
    {
        if (active != this) return;
        started = Time.realtimeSinceStartup;
        report.mode = Argument("--replay", "combat").ToLowerInvariant();
        report.runId = DateTime.UtcNow.ToString("yyyyMMddTHHmmssfffZ");
        report.unityVersion = Application.unityVersion;
        report.applicationVersion = Application.version;
        report.width = Screen.width; report.height = Screen.height;
        directory = Path.GetFullPath(Argument("--capture-dir", Path.Combine(Application.persistentDataPath, "replay-captures")));
        prefix = "replay-" + report.mode + "-" + report.runId;
        try { Directory.CreateDirectory(directory); }
        catch (Exception e) { Debug.LogError("Replay cannot create capture directory: " + e.GetType().Name); Application.Quit(2); enabled = false; return; }
        if (report.mode != "combat" && report.mode != "death" && report.mode != "victory" && report.mode != "avoidance" && report.mode != "legregions" && report.mode != "healing")
        { Finish(false, "Unknown replay mode; expected combat, death, victory, avoidance, legregions or healing."); return; }
        Save();
    }

    static string Argument(string key, string fallback)
    {
        string[] args = Environment.GetCommandLineArgs();
        for (int i = 0; i < args.Length - 1; ++i)
            if (args[i] == key && !args[i + 1].StartsWith("--", StringComparison.Ordinal)) return args[i + 1];
        return fallback;
    }

    bool Bind()
    {
        Encounter encounter = Encounter.Instance;
        if (encounter == null || encounter.Player == null || encounter.Boss == null) return false;
        player = encounter.Player; boss = encounter.Boss; player.ReplayEnabled = true;
        previousState = boss.CurrentState; stateStarted = Time.realtimeSinceStartup;
        priorBossHealth = boss.Health;
        priorLegObservation = Snapshot("leg-region-baseline");
        return true;
    }

    void Update()
    {
        if (active != this || finishing) return;
        if (!restarting && Elapsed >= Timeout) { Finish(false, "Scenario exceeded 300 real-time seconds."); return; }
        if (restarting) return;
        if (!initialized)
        {
            if (!Bind()) return;
            initialized = true; fightStarted = Elapsed; Observe("spawn", true);
        }
        if (player == null || boss == null) { Finish(false, "Encounter objects disappeared unexpectedly."); return; }
        ObserveChanges();
        if (finishing) return;
        if (Elapsed >= nextSave) { nextSave = Elapsed + 2; Save(); }
        if (player.IsDead)
        {
            if (!report.playerDeath) { report.playerDeath = true; Observe("player-death", true); }
            if (report.mode == "death") StartCoroutine(CheckRestart());
            else Finish(false, "Player died before scenario requirements completed.");
            return;
        }
        if (boss.IsDead)
        {
            if (!report.bossDefeat)
            {
                report.bossDefeat = true;
                report.victoryDurationSeconds = Elapsed - fightStarted;
                report.victoryDurationInRange = report.victoryDurationSeconds >= 180 && report.victoryDurationSeconds <= 300;
                Observe("boss-defeat", true);
            }
            if (report.mode == "victory") StartCoroutine(CheckRestart());
            else Finish(CombatPassed(), "Boss defeated while running combat proof.");
            return;
        }
        if (report.mode == "death")
        {
            // Walk to the nearest front leg, then remain exposed. Follow ordinary
            // repositioning so this remains a damage test rather than a timeout.
            Vector3 delta = Flat(boss.LegPositions[0] - player.transform.position);
            Send(delta.magnitude > .65f ? delta.normalized : Vector3.zero, false, false, false);
            return;
        }
        if (report.mode == "avoidance") { DriveAvoidance(); return; }
        if (report.mode == "legregions") { DriveLegRegions(); return; }
        if (report.mode == "healing") { DriveHealing(); return; }
        if (report.mode == "combat" && CombatPassed())
        { Finish(true, "Observed leg damage, buckle, collapse, exposed head damage, rise and a damaging contact avoided by dodge."); return; }
        DriveCombat();
    }

    bool CombatPassed()
    {
        return report.legDamage && report.buckle && report.collapse && report.exposed &&
               report.headDamage && report.rise && report.dodgePerformed && report.dodgeContact;
    }

    void ObserveChanges()
    {
        if (avoidanceTrial != null)
        {
            avoidanceTrial.minimumHealth = Mathf.Min(avoidanceTrial.minimumHealth, player.Health);
            avoidanceTrial.damageTaken = Mathf.Max(0, avoidanceTrial.healthAtWindup - avoidanceTrial.minimumHealth);
            avoidanceTrial.hitsTaken = player.HitsTaken - avoidanceTrial.hitsAtWindup;
        }
        if (boss.CurrentState != previousState)
        {
            previousState = boss.CurrentState; stateStarted = Time.realtimeSinceStartup;
            windupDodgeSent = false;
            if (previousState == DragonBoss.CombatState.Windup)
            {
                int closest = 0;
                for (int i = 1; i < boss.LegPositions.Length; i++)
                    if (Flat(boss.LegPositions[i] - player.transform.position).sqrMagnitude < Flat(boss.LegPositions[closest] - player.transform.position).sqrMagnitude) closest = i;
                fixedStompCenter = Flat(boss.LegPositions[closest]);
            }
            bool milestone = false;
            if (previousState == DragonBoss.CombatState.Buckle) { milestone = !report.buckle; report.buckle = true; }
            if (previousState == DragonBoss.CombatState.Collapse) { milestone = !report.collapse; report.collapse = true; }
            if (previousState == DragonBoss.CombatState.Exposed) { milestone = !report.exposed; report.exposed = true; }
            if (previousState == DragonBoss.CombatState.Rise) { milestone = !report.rise; report.rise = true; }
            Observe("state-" + previousState.ToString().ToLowerInvariant(), milestone);
            ObserveAvoidanceTransition(previousState);
        }
        if (boss.Health < priorBossHealth)
        {
            int region = boss.LastHitRegion;
            bool milestone = false;
            if (region >= 0 && region < 4) { milestone = !report.legDamage; report.legDamage = true; }
            if (region == 4 && boss.HeadExposed) { milestone = !report.headDamage; report.headDamage = true; }
            Observe("sword-contact-region-" + region, milestone);
            RecordLegRegionContact(region);
        }
        priorBossHealth = boss.Health;
        if (boss.HeadExposed && Elapsed >= nextHeadAimObservation)
        {
            nextHeadAimObservation = Elapsed + .5f;
            Observe("exposed-head-aim", false);
        }
        if (player.Dodges > 0 && !report.dodgePerformed) { report.dodgePerformed = true; Observe("dodge-input-accepted", true); }
        if (player.DodgedHits > 0 && !report.dodgeContact) { report.dodgeContact = true; Observe("dodge-avoided-contact", true); }
        if (report.mode == "legregions") priorLegObservation = Snapshot("leg-region-prior-frame");
    }

    void DriveHealing()
    {
        if (!healingInitialized)
        {
            healingInitialized = true;
            report.initialHealingCharges = player.Flasks;
            healingDamageBaseline = player.HitsTaken;
            report.healingHealthNeverExceededCap = player.Health <= 100.001f;
            if (player.Flasks != 4) { Finish(false, "Healing scenario expected exactly four initial charges."); return; }
        }
        if (player.Health > 100.001f)
        {
            report.healingHealthNeverExceededCap = false;
            Finish(false, "Player health exceeded the 100 HP healing cap."); return;
        }
        if (player.Flasks < 0) { Finish(false, "Healing charges became negative."); return; }
        Vector3 position = Flat(player.transform.position);
        bool danger = boss.CurrentState == DragonBoss.CombatState.Windup || boss.CurrentState == DragonBoss.CombatState.Active;
        if (healingPhase == "bait")
        {
            if (player.HitsTaken > healingDamageBaseline && player.Health < 99.99f)
            {
                healingPhase = "escape";
                healingRefuge = avoidanceTrial != null ? avoidanceRefuge : Flat(boss.transform.TransformPoint(new Vector3(-8, 0, 0)));
                Observe("healing-real-damage-" + report.successfulHeals, true);
            }
            else
            {
                var visual = boss.GetComponent<AuthoredDragonVisual>();
                Vector3 foot = visual != null && visual.IsReady ? visual.GetFootPosition(0) : boss.LegPositions[0];
                Vector3 delta = Flat(foot) - position;
                Send(delta.magnitude > .3f ? delta.normalized : Vector3.zero, false, false, false);
                return;
            }
        }
        if (healingPhase == "escape")
        {
            if (danger && avoidanceTrial != null) healingRefuge = avoidanceRefuge;
            Vector3 escape = healingRefuge - position;
            if (escape.magnitude > .35f || danger || player.ActionLabel != "Ready")
            { Send(escape.magnitude > .35f ? escape.normalized : Vector3.zero, false, false, false); return; }
            if (report.successfulHeals == 4)
            {
                if (player.Flasks != 0) { Finish(false, "Four successful heals did not exhaust all four charges."); return; }
                healingPhase = "empty"; healingPhaseStarted = Elapsed; nextEmptyHealInput = Elapsed;
                emptyPriorHealth = player.Health;
                report.emptyHealStart = Snapshot("healing-empty-start");
                Observe("healing-empty-start", true);
            }
            else
            {
                healingTrial = new HealingTrial {
                    ordinal = report.successfulHeals + 1, request = Snapshot("heal-input-request"),
                    chargesBefore = player.Flasks, healthBefore = player.Health,
                    expectedHealth = Mathf.Min(100, player.Health + 55), maximumObservedHealth = player.Health
                };
                report.healingTrials.Add(healingTrial);
                healingPhase = "healing"; healingPhaseStarted = Elapsed;
                Observe("healing-input-" + healingTrial.ordinal, true);
                Send(Vector3.zero, false, false, true);
                return;
            }
        }
        if (healingPhase == "healing")
        {
            healingTrial.maximumObservedHealth = Mathf.Max(healingTrial.maximumObservedHealth, player.Health);
            healingTrial.chargesAfter = player.Flasks;
            if (player.Flasks != healingTrial.chargesBefore - 1)
            { healingTrial.outcome = "incorrect-charge-decrement"; Finish(false, "A heal input did not consume exactly one charge."); return; }
            if (healingTrial.accepted == null)
            { healingTrial.accepted = Snapshot("heal-charge-consumed"); Observe("healing-charge-consumed-" + healingTrial.ordinal, false); }
            if (player.HitsTaken > healingTrial.request.hitsTaken)
            {
                healingTrial.interrupted = true; healingTrial.outcome = "interrupted-by-damage";
                healingTrial.completed = Snapshot("heal-interrupted");
                Finish(false, "Damage interrupted a planned safe heal; no successful heal credited."); return;
            }
            Vector3 escape = danger && avoidanceTrial != null ? avoidanceRefuge - position : Vector3.zero;
            Send(escape.magnitude > .35f ? escape.normalized : Vector3.zero, false, false, false);
            if (Elapsed - healingPhaseStarted < 1.5f) return;
            healingTrial.completed = Snapshot("heal-complete");
            healingTrial.successful = Mathf.Abs(player.Health - healingTrial.expectedHealth) < .05f &&
                player.Health > healingTrial.healthBefore && player.Flasks == healingTrial.chargesBefore - 1 && player.Health <= 100.001f;
            healingTrial.outcome = healingTrial.successful ? "successful" : "incorrect-health-restoration";
            if (!healingTrial.successful) { Finish(false, "A heal did not restore the expected 55 HP capped at 100."); return; }
            report.successfulHeals++;
            if (healingTrial.healthBefore + 55 > 100 && Mathf.Abs(player.Health - 100) < .05f) report.healingCapObserved = true;
            Observe("healing-complete-" + healingTrial.ordinal, true);
            healingTrial = null; healingPhase = "bait"; healingDamageBaseline = player.HitsTaken;
            return;
        }
        if (healingPhase == "empty")
        {
            if (player.Flasks != 0 || player.Health > emptyPriorHealth + .001f || player.ActionLabel == "Healing")
            { Finish(false, "Healing input with zero charges changed health, charges or entered the healing action."); return; }
            emptyPriorHealth = player.Health;
            Vector3 escape = danger && avoidanceTrial != null ? avoidanceRefuge - position : Vector3.zero;
            bool request = Elapsed >= nextEmptyHealInput;
            if (request) { nextEmptyHealInput = Elapsed + .25f; report.emptyHealInputRequests++; }
            Send(escape.magnitude > .35f ? escape.normalized : Vector3.zero, false, false, request);
            if (Elapsed - healingPhaseStarted < 2) return;
            report.emptyHealEnd = Snapshot("healing-empty-complete");
            report.emptyChargesRejected = report.emptyHealInputRequests >= 4 && player.Flasks == 0 &&
                player.Health <= report.emptyHealStart.playerHealth && report.emptyHealStart.playerHealth < 100;
            Observe("healing-empty-complete", true);
            Finish(report.successfulHeals == 4 && report.healingCapObserved && report.healingHealthNeverExceededCap && report.emptyChargesRejected,
                "Four heals consumed exactly four charges; damaged empty-flask input observed for 2 seconds. See healingTrials and cap/empty-charge assertions.");
        }
    }

    bool LegRegionsPassed()
    {
        for (int i = 0; i < 4; i++) if (!verifiedLegRegions[i]) return false;
        return true;
    }

    void RecordLegRegionContact(int region)
    {
        if (report.mode != "legregions" || priorLegObservation == null) return;
        Observation after = Snapshot("leg-region-contact-" + region);
        var contact = new LegRegionContact {
            intendedRegion = legSwingTarget, actualRegion = region,
            before = priorLegObservation, after = after,
            staggerBefore = (float[])priorLegObservation.legStagger.Clone(),
            staggerAfter = (float[])after.legStagger.Clone(),
            bossDamage = priorLegObservation.bossHealth - after.bossHealth,
            targetMatched = legSwingTarget == region
        };
        bool otherMetersUnchanged = true;
        for (int i = 0; i < 4; i++)
            if (i != region && Mathf.Abs(contact.staggerAfter[i] - contact.staggerBefore[i]) > .001f) otherMetersUnchanged = false;
        contact.contactedMeterIncreased = region >= 0 && region < 4 && contact.staggerAfter[region] > contact.staggerBefore[region] + .001f;
        contact.otherMetersUnchanged = otherMetersUnchanged;
        contact.independentRegionVerified = contact.targetMatched && contact.bossDamage > 0 && contact.contactedMeterIncreased && otherMetersUnchanged;
        report.legRegionContacts.Add(contact);
        Observe("leg-region-evidence-" + region, true);
        if (contact.independentRegionVerified) verifiedLegRegions[region] = true;
        if (!otherMetersUnchanged)
            Finish(false, "A sword contact changed a stagger meter belonging to another leg; inspect legRegionContacts before/after arrays.");
        else if (region >= 0 && region < 4 && !contact.contactedMeterIncreased)
            Finish(false, "Leg damage occurred without increasing its stagger meter during the independent-region scenario.");
    }

    void DriveLegRegions()
    {
        if (LegRegionsPassed())
        { Finish(true, "Each of the four intended leg regions took sword damage and increased only its own stagger meter; no collapse required."); return; }
        if (boss.CollapseCount > 0)
        { Finish(false, "Unexpected collapse before all four independent leg regions were verified."); return; }
        for (int i = 0; i < 4; i++)
            if (boss.LegStagger[i] >= 75)
            { Finish(false, "Repeated unintended contacts approached a collapse threshold; stopped rather than resetting the boss or obscuring evidence."); return; }
        Vector3 position = Flat(player.transform.position);
        if ((boss.CurrentState == DragonBoss.CombatState.Windup || boss.CurrentState == DragonBoss.CombatState.Active) && avoidanceTrial != null)
        {
            Vector3 escape = avoidanceRefuge - position;
            Send(escape.magnitude > .25f ? escape.normalized : Vector3.zero, false, false, false);
            return;
        }
        int targetRegion = 0;
        foreach (int region in LegVisitOrder) if (!verifiedLegRegions[region]) { targetRegion = region; break; }
        Vector3 target = Flat(boss.LegPositions[targetRegion]);
        Vector3 outward = Flat(target - boss.transform.position).normalized;
        if (outward.sqrMagnitude < .01f) outward = boss.transform.right * (targetRegion % 2 == 0 ? -1 : 1);
        Vector3 stand = target + outward * 1.6f;
        Vector3 toStand = stand - position;
        Vector3 toLeg = target - position;
        bool atStand = toStand.magnitude < .4f;
        Vector3 movement = !atStand ? toStand.normalized : toLeg.normalized * .06f;
        bool aligned = toLeg.sqrMagnitude < .16f || Vector3.Dot(player.transform.forward, toLeg.normalized) > .85f;
        Vector3 swordOrigin = player.transform.position + Vector3.up * 1.1f;
        float targetScore = Mathf.Max(0, Vector3.Distance(swordOrigin, boss.LegPositions[targetRegion]) - .75f);
        bool uniquelyClosest = true;
        for (int i = 0; i < 4; i++)
            if (i != targetRegion && Mathf.Max(0, Vector3.Distance(swordOrigin, boss.LegPositions[i]) - .75f) <= targetScore + .1f) uniquelyClosest = false;
        if (boss.HeadTarget != null && Mathf.Max(0, Vector3.Distance(swordOrigin, boss.HeadTarget.position) - 1) <= targetScore + .1f) uniquelyClosest = false;
        bool heal = player.Health <= 55 && player.Flasks > 0 && boss.CurrentState == DragonBoss.CombatState.Recovery;
        bool attack = !heal && atStand && aligned && uniquelyClosest && targetScore < 2.5f &&
            player.Stamina >= 22 && player.ActionLabel == "Ready" && Elapsed >= nextSwing;
        if (attack) { nextSwing = Elapsed + .9f; legSwingTarget = targetRegion; Observe("leg-region-input-" + targetRegion, false); }
        Send(movement, attack, false, heal);
    }

    bool AvoidancePassed()
    {
        foreach (string move in AvoidanceMoves) if (!avoidedMoves.Contains(move)) return false;
        return true;
    }

    void ObserveAvoidanceTransition(DragonBoss.CombatState state)
    {
        if (report.mode != "avoidance" && report.mode != "legregions" && report.mode != "healing") return;
        if (state == DragonBoss.CombatState.Windup)
        {
            if (avoidanceTrial != null && !avoidanceTrial.recoveryObserved)
                avoidanceTrial.outcome = "interrupted-before-recovery";
            avoidanceBossOrigin = Flat(boss.transform.position);
            avoidanceBossForward = -boss.transform.forward;
            avoidanceBossRight = boss.transform.right;
            string move = boss.CurrentMoveName;
            avoidanceTrial = new AttackTrial {
                move = move, windup = Snapshot("avoidance-windup-" + move),
                healthAtWindup = player.Health, minimumHealth = player.Health, hitsAtWindup = player.HitsTaken,
                windupObserved = true
            };
            Vector3 position = Flat(player.transform.position);
            Vector3 local = boss.transform.InverseTransformPoint(position);
            Vector3 origin = avoidanceBossOrigin;
            if (move == "Stomp")
            {
                var visual = boss.GetComponent<AuthoredDragonVisual>();
                int leg = boss.StompLegIndex;
                origin = visual != null && visual.IsReady ? Flat(visual.GetFootPosition(leg)) :
                    Flat(boss.transform.TransformPoint(new Vector3(leg % 2 == 0 ? -3 : 3, 0, leg < 2 ? -2 : 2)));
                avoidanceTrial.initiallyThreatened = Vector3.Distance(position, origin) < 2.45f;
                Vector3 away = position - origin;
                if (away.sqrMagnitude < .01f) away = -avoidanceBossRight;
                avoidanceRefuge = origin + away.normalized * 4;
                avoidanceTrial.footprint = "Stomp ground circle radius2.45, live selected foot anchor at observed windup.";
            }
            else if (move == "Bite")
            {
                origin += avoidanceBossForward * 3;
                avoidanceTrial.initiallyThreatened = InsideSector(position, origin, avoidanceBossForward, .55f, 4.45f, 30);
                avoidanceRefuge = position + avoidanceBossRight * (local.x > 0 ? 5 : -5);
                avoidanceTrial.footprint = "Bite ground sector: origin3m forward, radii0.55–4.45m, half-angle30deg.";
            }
            else if (move == "Tail")
            {
                avoidanceTrial.initiallyThreatened = InsideSector(position, origin, -avoidanceBossForward, 4.15f, 9.85f, 125);
                avoidanceRefuge = avoidanceBossOrigin; // The inner safe area is reachable during anticipation.
                avoidanceTrial.footprint = "Tail swept ground union: radii4.15–9.85m, rear half-angle125deg.";
            }
            else if (move == "Breath")
            {
                origin += avoidanceBossForward * 4.4f;
                avoidanceTrial.initiallyThreatened = InsideSector(position, origin, avoidanceBossForward, .8f, 16.85f, 78);
                avoidanceRefuge = avoidanceBossOrigin + avoidanceBossRight * (local.x > 0 ? 8 : -8);
                avoidanceTrial.footprint = "Breath swept ground union: origin4.4m forward, radii0.8–16.85m, half-angle78deg.";
            }
            else if (move == "Lunge")
            {
                Vector3 end = Vector3.ClampMagnitude(avoidanceBossOrigin + avoidanceBossForward * 8, 30) + avoidanceBossForward * 4.8f;
                origin += avoidanceBossForward * 4.8f;
                avoidanceTrial.initiallyThreatened = DistanceToSegment(position, origin, end) < 2.55f;
                avoidanceRefuge = position + avoidanceBossRight * (local.x > 0 ? 5 : -5);
                avoidanceTrial.footprint = "Lunge swept ground capsule radius2.55m from4.8m forward to clamped8m travel+4.8m.";
            }
            avoidanceTrial.groundOrigin = origin;
            avoidanceTrial.escapeTarget = avoidanceRefuge;
            report.attackTrials.Add(avoidanceTrial);
            Observe("avoidance-windup-" + move.ToLowerInvariant(), true);
        }
        else if (state == DragonBoss.CombatState.Active && avoidanceTrial != null)
        {
            avoidanceTrial.activeObserved = true;
            avoidanceTrial.active = Snapshot("avoidance-active-" + avoidanceTrial.move);
        }
        else if (state == DragonBoss.CombatState.Recovery && avoidanceTrial != null)
        {
            avoidanceTrial.recoveryObserved = true;
            avoidanceTrial.recovery = Snapshot("avoidance-recovery-" + avoidanceTrial.move);
            avoidanceTrial.damageTaken = Mathf.Max(0, avoidanceTrial.healthAtWindup - avoidanceTrial.minimumHealth);
            avoidanceTrial.hitsTaken = player.HitsTaken - avoidanceTrial.hitsAtWindup;
            avoidanceTrial.escapeDistance = Flat(player.transform.position - avoidanceTrial.windup.playerPosition).magnitude;
            avoidanceTrial.avoided = avoidanceTrial.initiallyThreatened && avoidanceTrial.activeObserved &&
                avoidanceTrial.hitsTaken == 0 && avoidanceTrial.damageTaken < .001f && avoidanceTrial.escapeDistance > .75f;
            avoidanceTrial.outcome = avoidanceTrial.avoided ? "avoided" : !avoidanceTrial.initiallyThreatened ? "not-threatened-at-windup" : "avoidance-not-proven";
            if (avoidanceTrial.avoided) avoidedMoves.Add(avoidanceTrial.move);
            Observe("avoidance-result-" + avoidanceTrial.move.ToLowerInvariant(), avoidanceTrial.avoided);
            avoidanceTrial = null;
        }
    }

    void DriveAvoidance()
    {
        if (AvoidancePassed())
        { Finish(true, "All five attacks observed through windup, active and recovery; escaped each initial threat footprint without taking damage."); return; }
        Vector3 position = Flat(player.transform.position);
        bool danger = boss.CurrentState == DragonBoss.CombatState.Windup || boss.CurrentState == DragonBoss.CombatState.Active;
        if (danger && avoidanceTrial != null)
        {
            Vector3 escape = avoidanceRefuge - position;
            Send(escape.magnitude > .25f ? escape.normalized : Vector3.zero, false, false, false);
            return;
        }
        string desired = "Lunge";
        foreach (string move in AvoidanceMoves) if (!avoidedMoves.Contains(move)) { desired = move; break; }
        Vector3 localTarget;
        switch (desired)
        {
            case "Stomp":
                var visual = boss.GetComponent<AuthoredDragonVisual>();
                Vector3 foot = visual != null && visual.IsReady ? visual.GetFootPosition(0) : boss.LegPositions[0];
                Vector3 toFoot = Flat(foot) - position;
                Send(toFoot.magnitude > .3f ? toFoot.normalized : Vector3.zero, false, false,
                    player.Health <= 55 && boss.CurrentState == DragonBoss.CombatState.Recovery);
                return;
            case "Bite": localTarget = new Vector3(0, 0, -6.5f); break;
            case "Tail": localTarget = new Vector3(0, 0, 6); break;
            case "Breath": localTarget = new Vector3(-6, 0, -8); break;
            default: localTarget = new Vector3(0, 0, -15); break;
        }
        Vector3 delta = Flat(boss.transform.TransformPoint(localTarget)) - position;
        bool heal = player.Health <= 55 && player.Flasks > 0 && boss.CurrentState == DragonBoss.CombatState.Recovery;
        Send(delta.magnitude > .3f ? delta.normalized : Vector3.zero, false, false, heal);
    }

    static bool InsideSector(Vector3 point, Vector3 origin, Vector3 forward, float inner, float outer, float halfAngle)
    {
        Vector3 delta = Flat(point - origin);
        return delta.magnitude >= inner && delta.magnitude <= outer && Vector3.Angle(forward, delta) <= halfAngle;
    }
    static float DistanceToSegment(Vector3 point, Vector3 a, Vector3 b)
    {
        Vector3 delta = b - a;
        float t = delta.sqrMagnitude > .0001f ? Mathf.Clamp01(Vector3.Dot(point - a, delta) / delta.sqrMagnitude) : 0;
        return Vector3.Distance(point, a + delta * t);
    }

    void DriveCombat()
    {
        DragonBoss.CombatState state = boss.CurrentState;
        float inState = Time.realtimeSinceStartup - stateStarted;
        Vector3 position = Flat(player.transform.position);
        Vector3 leg = Flat(boss.LegPositions[0]);
        Vector3 legDelta = leg - position;
        bool falling = state == DragonBoss.CombatState.Buckle || state == DragonBoss.CombatState.Collapse;
        bool head = boss.HeadExposed || falling;
        if (legDelta.magnitude < 2) reachedLeg = true;

        // First deliberately test an iframe against a readable stomp. Stop close
        // to its fixed origin, then roll through it just before impact.
        bool seekDodge = !report.dodgeContact && reachedLeg;
        bool stomp = boss.StateLabel.IndexOf("STOMP", StringComparison.Ordinal) >= 0;
        if (seekDodge && state == DragonBoss.CombatState.Windup && stomp)
        {
            Vector3 toCenter = fixedStompCenter - position;
            Vector3 movement = toCenter.magnitude > .35f ? toCenter.normalized : Vector3.zero;
            bool dodge = !windupDodgeSent && inState >= .94f && player.Stamina >= 25;
            if (dodge)
            {
                windupDodgeSent = true;
                movement = toCenter.magnitude > .1f ? toCenter.normalized : -boss.transform.right;
            }
            Send(movement, false, dodge, false);
            return;
        }
        if (seekDodge && !head && state != DragonBoss.CombatState.Active)
        {
            Send(legDelta.magnitude > .35f ? legDelta.normalized : Vector3.zero, false, false,
                player.Health <= 45 && state == DragonBoss.CombatState.Recovery);
            return;
        }

        if (state == DragonBoss.CombatState.Windup || state == DragonBoss.CombatState.Active)
        {
            Vector3 evade;
            if (stomp)
            {
                evade = position - fixedStompCenter;
                if (evade.sqrMagnitude < .01f) evade = -boss.transform.right;
                // Moving out of the circle is sufficient: do not consume rolls
                // that cannot establish a real invulnerable contact.
                if (evade.magnitude >= 3.5f) evade = Vector3.zero;
            }
            else
            {
                // Head attacks face local -Z; the side/rear of the left foreleg
                // is outside their front cone and lunge corridor.
                Vector3 refuge = Flat(boss.transform.TransformPoint(new Vector3(-7, 0, 0)));
                evade = refuge - position;
                if (evade.magnitude < .5f) evade = Vector3.zero;
            }
            Send(evade.normalized, false, false, false);
            return;
        }
        Vector3 target = head ? Flat(boss.HeadTarget.position) : leg;
        Vector3 toTarget = target - position;
        float distance = toTarget.magnitude;
        bool safeHeal = player.Health <= 55 && player.Flasks > 0 &&
            (state == DragonBoss.CombatState.Recovery || falling || state == DragonBoss.CombatState.Rise);
        // Stay inside sword range, with a small movement to establish facing
        // using precisely the same turn response as ordinary movement input.
        Vector3 move = distance > 1.8f ? toTarget.normalized : distance > .05f ? toTarget.normalized * .06f : Vector3.zero;
        bool aligned = distance < .4f || Vector3.Dot(player.transform.forward, toTarget.normalized) > .85f;
        bool attack = !safeHeal && !falling && distance < 2.8f && aligned &&
            player.Stamina >= (boss.HeadExposed ? 22 : 28) && Elapsed >= nextSwing;
        if (attack) nextSwing = Elapsed + .78f;
        Send(move, attack, false, safeHeal);
    }

    void Send(Vector3 movement, bool attack, bool dodge, bool heal)
    {
        if (player == null) return;
        player.SetReplayInput(movement, attack, dodge, heal);
        if (Elapsed >= nextInputSample || attack || dodge || heal)
        {
            nextInputSample = Elapsed + .1f;
            report.inputs.Add(new InputSample { seconds = Elapsed, worldMove = movement, attack = attack, dodge = dodge, heal = heal });
        }
    }

    IEnumerator CheckRestart()
    {
        restarting = true; Send(Vector3.zero, false, false, false); Save();
        float terminalHealth=player.Health;
        yield return new WaitForSecondsRealtime(boss.IsDead ? 3.65f : 2.2f);
        if(Mathf.Abs(player.Health-terminalHealth)>.001f)
        {Finish(false,"Player health changed after the terminal encounter state.");yield break;}
        Observe("terminal-settled-pose",true);
        float poseCaptureDeadline=Time.realtimeSinceStartup+3;
        while((captureQueue.Count>0||captureInProgress)&&Time.realtimeSinceStartup<poseCaptureDeadline)yield return null;
        int oldPlayerId = player.GetInstanceID();
        Encounter.Instance.RestartEncounter();
        float until = Time.realtimeSinceStartup + 10;
        while (Time.realtimeSinceStartup < until)
        {
            if (Encounter.Instance != null && Encounter.Instance.Player != null &&
                Encounter.Instance.Player.GetInstanceID() != oldPlayerId) break;
            yield return null;
        }
        if (!Bind() || player.GetInstanceID() == oldPlayerId)
        { Finish(false, "Restart did not construct a fresh encounter within 10 seconds."); yield break; }
        bool reset = !player.IsDead && !boss.IsDead && player.Health >= 99.9f && player.Stamina >= 99.9f &&
            player.Swings == 0 && player.Dodges == 0 && boss.CollapseCount == 0 && Mathf.Abs(boss.Health - boss.MaxHealth) < .1f;
        Observe("restart-fresh-state", true);
        Vector3 before = player.transform.position;
        float moveUntil = Time.realtimeSinceStartup + .65f;
        while (Time.realtimeSinceStartup < moveUntil)
        { Send(Vector3.left, false, false, false); yield return null; }
        Send(Vector3.zero, false, false, false);
        report.restart = reset && Flat(player.transform.position - before).magnitude > .5f;
        Observe("restart-input-response", true);
        bool goal = report.mode == "death" ? report.playerDeath : report.bossDefeat && report.legDamage && report.headDamage;
        Finish(goal && report.restart, report.restart ? "Terminal state and fresh input-responsive restart observed." : "Restart state or input-response assertion failed.");
    }

    Observation Snapshot(string name)
    {
        if (player == null || boss == null) return null;
        Vector3 headPosition = boss.HeadTarget != null ? boss.HeadTarget.position : boss.transform.position;
        Vector3 headDelta = headPosition - (player.transform.position + Vector3.up * 1.1f);
        Vector3 flatHeadDelta = Flat(headDelta);
        return new Observation {
            name = name, seconds = Elapsed, frame = Time.frameCount, playerHealth = player.Health, stamina = player.Stamina,
            bossHealth = boss.Health, state = boss.CurrentState.ToString(), playerPosition = player.transform.position,
            swings = player.Swings, dodges = player.Dodges, hitsTaken = player.HitsTaken, dodgedHits = player.DodgedHits,
            collapses = boss.CollapseCount, lastHitRegion = boss.LastHitRegion, flasks = player.Flasks,
            bossMove = boss.CurrentMoveName, playerAction = player.ActionLabel, playerForward = player.transform.forward, headPosition = headPosition,
            headDistanceFromSwordOrigin = headDelta.magnitude, headHorizontalDistance = flatHeadDelta.magnitude,
            headVerticalOffset = headDelta.y, headFacingDot = flatHeadDelta.sqrMagnitude > .0001f ? Vector3.Dot(player.transform.forward, flatHeadDelta.normalized) : 1,
            headWindowRemaining = boss.HeadWindowRemaining, headExposed = boss.HeadExposed,
            legStagger = (float[])boss.LegStagger.Clone()
        };
    }

    void Observe(string name, bool screenshot)
    {
        Observation observation = Snapshot(name);
        if (observation == null) return;
        report.observations.Add(observation);
        if (screenshot && directory != null)
        {
            string filename = prefix + "-" + report.observations.Count.ToString("D03") + "-" + name + ".png";
            var request = new ScreenshotRecord { filename = filename, originEvent = observation };
            report.screenshotRequests.Add(filename);
            report.captures.Add(request);
            captureQueue.Enqueue(request);
        }
    }

    void LateUpdate()
    {
        // Remains active during finalization and scene restart. Consume at most
        // one semantic request per rendered frame, including simultaneous events.
        if (active == this && captureQueue.Count > 0 && !captureInProgress && lastCapturedFrame != Time.frameCount)
        {
            captureInProgress = true;
            StartCoroutine(CaptureRenderedFrame());
        }
    }

    IEnumerator CaptureRenderedFrame()
    {
        yield return new WaitForEndOfFrame();
        ScreenshotRecord request = captureQueue.Dequeue();
        lastCapturedFrame = Time.frameCount;
        request.capturedFrame = Time.frameCount;
        request.capturedSeconds = Elapsed;
        request.queueDelaySeconds = request.capturedSeconds - request.originEvent.seconds;
        request.renderedSnapshot = Snapshot("render-for-" + request.originEvent.name);
        Texture2D pixels = null;
        try
        {
            // Read the completed native frame directly. Unlike deferred filename
            // requests, this cannot be replaced by Encounter's periodic captures.
            pixels = ScreenCapture.CaptureScreenshotAsTexture();
            if (pixels == null) throw new InvalidOperationException("Native frame readback returned no pixels.");
            byte[] png = pixels.EncodeToPNG();
            if (png == null || png.Length == 0) throw new InvalidOperationException("Native frame PNG encoding returned no bytes.");
            File.WriteAllBytes(Path.Combine(directory, request.filename), png);
            request.status = "written";
        }
        catch (Exception e)
        {
            request.status = "failed"; request.error = e.GetType().Name;
            Debug.LogError("Replay milestone capture failed: " + request.error);
        }
        finally
        {
            if (pixels != null) Destroy(pixels);
            captureInProgress = false;
        }
        Save();
    }

    void Finish(bool success, string reason)
    {
        if (finishing) return;
        finishing = true;
        if (avoidanceTrial != null && !avoidanceTrial.recoveryObserved)
            avoidanceTrial.outcome = "scenario-ended-before-recovery";
        Send(Vector3.zero, false, false, false);
        if (report.mode == "victory" && report.bossDefeat && !report.victoryDurationInRange)
        {
            success = false;
            reason += " Measured victory duration " + report.victoryDurationSeconds.ToString("F2", System.Globalization.CultureInfo.InvariantCulture) + "s is outside the required 180–300s range.";
        }
        report.status = success ? "passed" : "failed"; report.reason = reason;
        Observe("final-" + report.status, true);
        report.assertions.Clear();
        if (report.mode == "combat" || report.mode == "victory")
        {
            AddAssertion("leg_damage", report.legDamage); AddAssertion("buckle", report.buckle);
            AddAssertion("collapse", report.collapse); AddAssertion("head_exposed", report.exposed);
            AddAssertion("exposed_head_damage", report.headDamage); AddAssertion("rise", report.rise);
            AddAssertion("dodge_action", report.dodgePerformed); AddAssertion("dodge_avoided_contact", report.dodgeContact);
        }
        if (report.mode == "death") AddAssertion("player_death", report.playerDeath);
        if (report.mode == "victory")
        {
            AddAssertion("boss_defeat", report.bossDefeat);
            report.assertions.Add(new Assertion {
                name = "victory_duration_180_to_300_seconds", status = !report.bossDefeat ? "not_observed" : report.victoryDurationInRange ? "passed" : "failed",
                detail = report.bossDefeat ? "Measured spawn-to-defeat duration: " + report.victoryDurationSeconds.ToString("F2", System.Globalization.CultureInfo.InvariantCulture) + " seconds." : "No boss defeat observed; no victory duration inferred."
            });
        }
        if (report.mode == "death" || report.mode == "victory") AddAssertion("restart_and_movement", report.restart);
        if (report.mode == "avoidance")
        {
            foreach (string move in AvoidanceMoves)
                report.assertions.Add(new Assertion {
                    name = "avoidance_" + move.ToLowerInvariant(), status = avoidedMoves.Contains(move) ? "observed" : "not_observed",
                    detail = "Requires windup/active/recovery, inside modeled threat at windup, escape movement >0.75m, no health loss and no hit-counter increase. See attackTrials."
                });
        }
        if (report.mode == "legregions")
        {
            for (int i = 0; i < 4; i++)
                report.assertions.Add(new Assertion {
                    name = "independent_leg_region_" + i, status = verifiedLegRegions[i] ? "observed" : "not_observed",
                    detail = "Requires intended and actual sword region match, boss health decreases, corresponding stagger meter increases and the other three remain unchanged. See legRegionContacts."
                });
            AddAssertion("legregions_no_collapse", boss != null && boss.CollapseCount == 0);
        }
        if (report.mode == "healing")
        {
            AddAssertion("healing_four_initial_charges", report.initialHealingCharges == 4);
            AddAssertion("healing_four_successful_exact_decrements", report.successfulHeals == 4);
            AddAssertion("healing_overflow_capped_at_100", report.healingCapObserved);
            AddAssertion("healing_health_never_exceeded_100", report.healingHealthNeverExceededCap);
            AddAssertion("healing_empty_charges_rejected_while_damaged", report.emptyChargesRejected);
        }
        Save(); StartCoroutine(CompleteAfterCapture(success));
    }

    void AddAssertion(string name, bool value)
    {
        report.assertions.Add(new Assertion { name = name, status = value ? "observed" : "not_observed", detail = "See timestamped observations; an unobserved event is not treated as verified." });
    }

    IEnumerator CompleteAfterCapture(bool success)
    {
        // Drain every semantic request, still at one per rendered frame. Bound
        // this separately from the fight so a terminal event cannot lose evidence.
        float flushDeadline = Time.realtimeSinceStartup + 10;
        while ((captureQueue.Count > 0 || captureInProgress) && Time.realtimeSinceStartup < flushDeadline)
            yield return null;
        Save();
        bool capturesWritten = captureQueue.Count == 0 && !captureInProgress && report.screenshotRequests.Count > 0 &&
            report.screenshotsWritten.Count == report.screenshotRequests.Count;
        foreach (ScreenshotRecord capture in report.captures)
            if (capture.status != "written") capturesWritten = false;
        AddAssertion("milestone_screenshots_written", capturesWritten);
        if (!capturesWritten)
        {
            success = false; report.status = "failed";
            report.reason += " One or more native milestone screenshots were not written within the capture flush window.";
        }
        Save();
        Debug.Log("REPLAY " + report.status.ToUpperInvariant() + ": " + report.reason);
        Application.Quit(success ? 0 : 1);
    }

    void Save()
    {
        if (directory == null) return;
        report.elapsedSeconds = Elapsed;
        report.screenshotsWritten.Clear();
        foreach (string filename in report.screenshotRequests)
        {
            string path = Path.Combine(directory, filename);
            if (File.Exists(path) && new FileInfo(path).Length > 0) report.screenshotsWritten.Add(filename);
        }
        try { File.WriteAllText(Path.Combine(directory, prefix + "-results.json"), JsonUtility.ToJson(report, true)); }
        catch (Exception e) { Debug.LogError("Replay result write failed: " + e.GetType().Name); }
    }

    void OnApplicationQuit()
    {
        if (active != this) return;
        if (!finishing) { report.status = "interrupted"; report.reason = "Application exited before the scenario completed."; }
        Save();
    }
    void OnDestroy() { if (active == this) active = null; }
    static Vector3 Flat(Vector3 value) { value.y = 0; return value; }
}
