using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using UnityEngine;

/// <summary>
/// Native, real-time input replay. No health writes, teleports, time scaling or
/// direct attack calls. Run with --replay combat|death|victory --capture-dir PATH.
/// Decisions are deterministic; wall-clock timings remain subject to frame rate.
/// </summary>
[DefaultExecutionOrder(-100)]
public sealed class CombatReplay : MonoBehaviour
{
    [Serializable] public sealed class Observation
    {
        public float seconds, playerHealth, stamina, bossHealth;
        public int frame, swings, dodges, hitsTaken, dodgedHits, collapses, lastHitRegion;
        public string name, state;
        public Vector3 playerPosition;
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
        public float elapsedSeconds;
        public int width, height;
        public bool legDamage, buckle, collapse, exposed, headDamage, rise, dodgePerformed, dodgeContact, playerDeath, bossDefeat, restart;
        public List<Observation> observations = new List<Observation>();
        public List<InputSample> inputs = new List<InputSample>();
        public List<Assertion> assertions = new List<Assertion>();
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
        if (report.mode != "combat" && report.mode != "death" && report.mode != "victory")
        { Finish(false, "Unknown replay mode; expected combat, death or victory."); return; }
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
        return true;
    }

    void Update()
    {
        if (active != this || finishing) return;
        if (Elapsed >= Timeout) { Finish(false, "Scenario exceeded 300 real-time seconds."); return; }
        if (restarting) return;
        if (!initialized)
        {
            if (!Bind()) return;
            initialized = true; Observe("spawn", true);
        }
        if (player == null || boss == null) { Finish(false, "Encounter objects disappeared unexpectedly."); return; }
        ObserveChanges();
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
            if (!report.bossDefeat) { report.bossDefeat = true; Observe("boss-defeat", true); }
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
        }
        if (boss.Health < priorBossHealth)
        {
            int region = boss.LastHitRegion;
            bool milestone = false;
            if (region >= 0 && region < 4) { milestone = !report.legDamage; report.legDamage = true; }
            if (region == 4 && boss.HeadExposed) { milestone = !report.headDamage; report.headDamage = true; }
            Observe("sword-contact-region-" + region, milestone);
        }
        priorBossHealth = boss.Health;
        if (player.Dodges > 0 && !report.dodgePerformed) { report.dodgePerformed = true; Observe("dodge-input-accepted", true); }
        if (player.DodgedHits > 0 && !report.dodgeContact) { report.dodgeContact = true; Observe("dodge-avoided-contact", true); }
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
        Vector3 move = distance > 1.8f ? toTarget.normalized : distance > .5f ? toTarget.normalized * .06f : Vector3.zero;
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
        yield return new WaitForSecondsRealtime(2);
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

    void Observe(string name, bool screenshot)
    {
        if (player == null || boss == null) return;
        report.observations.Add(new Observation {
            name = name, seconds = Elapsed, frame = Time.frameCount, playerHealth = player.Health, stamina = player.Stamina,
            bossHealth = boss.Health, state = boss.CurrentState.ToString(), playerPosition = player.transform.position,
            swings = player.Swings, dodges = player.Dodges, hitsTaken = player.HitsTaken, dodgedHits = player.DodgedHits,
            collapses = boss.CollapseCount, lastHitRegion = boss.LastHitRegion
        });
        if (screenshot && directory != null)
        {
            string filename = prefix + "-" + report.observations.Count.ToString("D03") + "-" + name + ".png";
            report.screenshotRequests.Add(filename);
            ScreenCapture.CaptureScreenshot(Path.Combine(directory, filename));
        }
    }

    void Finish(bool success, string reason)
    {
        if (finishing) return;
        finishing = true;
        Send(Vector3.zero, false, false, false);
        report.status = success ? "passed" : "failed"; report.reason = reason;
        Observe("final-" + report.status, true);
        report.assertions.Clear();
        if (report.mode != "death")
        {
            AddAssertion("leg_damage", report.legDamage); AddAssertion("buckle", report.buckle);
            AddAssertion("collapse", report.collapse); AddAssertion("head_exposed", report.exposed);
            AddAssertion("exposed_head_damage", report.headDamage); AddAssertion("rise", report.rise);
            AddAssertion("dodge_action", report.dodgePerformed); AddAssertion("dodge_avoided_contact", report.dodgeContact);
        }
        if (report.mode == "death") AddAssertion("player_death", report.playerDeath);
        if (report.mode == "victory") AddAssertion("boss_defeat", report.bossDefeat);
        if (report.mode != "combat") AddAssertion("restart_and_movement", report.restart);
        Save(); StartCoroutine(CompleteAfterCapture(success));
    }

    void AddAssertion(string name, bool value)
    {
        report.assertions.Add(new Assertion { name = name, status = value ? "observed" : "not_observed", detail = "See timestamped observations; an unobserved event is not treated as verified." });
    }

    IEnumerator CompleteAfterCapture(bool success)
    {
        // CaptureScreenshot writes after the frame; leave a bounded flush window.
        yield return new WaitForSecondsRealtime(2);
        Save();
        bool capturesWritten = report.screenshotRequests.Count > 0 &&
            report.screenshotsWritten.Count == report.screenshotRequests.Count;
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
            if (File.Exists(Path.Combine(directory, filename))) report.screenshotsWritten.Add(filename);
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
