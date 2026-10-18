using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Rendering;

/// <summary>
/// Veyr's original, interruptible one-phase encounter. The procedural visual is
/// explicitly temporary; combat targets are independent of its renderers so an
/// authored, licensed rig can replace it without changing combat rules.
/// Local -Z is the dragon's front. Ground danger and damage share one geometry.
/// </summary>
public sealed class DragonBoss : MonoBehaviour
{
    public enum CombatState { Idle, Reposition, Windup, Active, Recovery, Buckle, Collapse, Exposed, Rise, Dead }
    enum Move { None, Stomp, Breath, Tail, Bite, Lunge }

    [SerializeField] float maxHealth = 2800f;
    public float Health { get; private set; }
    public float MaxHealth { get { return maxHealth; } }
    public string StateLabel { get; private set; }
    public Transform HeadTarget { get; private set; }
    public Vector3[] LegPositions { get; private set; } = new Vector3[4];
    public float[] LegStagger { get; private set; } = new float[4];
    public bool IsDead { get { return state == CombatState.Dead; } }
    public bool HeadExposed { get { return state == CombatState.Exposed; } }
    public float HeadWindowRemaining { get { return HeadExposed ? Mathf.Max(0, 7f - stateTime) : 0; } }
    public CombatState CurrentState { get { return state; } }
    public int LastHitRegion { get; private set; } = -1; // 0..3 legs, 4 head, 5 body
    public int CollapseCount { get; private set; }
    public Transform TemporaryVisual { get; private set; }
    public float StateElapsed => stateTime;
    public float StateDuration => duration;
    public string CurrentMoveName => move.ToString();
    public int StruckLegIndex => struckLeg;
    public int StompLegIndex => stompLeg;
    public float VisualClock => poseClock;

    static readonly Vector3[] Feet = {
        new Vector3(-3, .8f, -2), new Vector3(3, .8f, -2),
        new Vector3(-3, .8f, 2), new Vector3(3, .8f, 2)
    };
    static readonly string[] LegNames = { "FRONT LEFT", "FRONT RIGHT", "REAR LEFT", "REAR RIGHT" };
    readonly HashSet<int> acceptedSwings = new HashSet<int>();
    readonly Queue<int> recentSwings = new Queue<int>();
    readonly List<Object> ownedResources = new List<Object>();
    readonly Transform[] upperLeg = new Transform[4], lowerLeg = new Transform[4], foot = new Transform[4];
    readonly Renderer[] legGlow = new Renderer[4];
    readonly Transform[] tail = new Transform[7];
    readonly float[] hitFlash = new float[4];
    readonly MaterialPropertyBlock properties = new MaterialPropertyBlock();
    readonly Vector3[] legLocal = new Vector3[4];
    Transform body, chest, head, jaw, throat, neckA, neckB, leftWing, rightWing, hitSpark;
    Renderer throatRenderer, sparkRenderer;
    Material stone, armor, copper, membrane, hot, indicatorMaterial, indicatorActiveMaterial;
    AudioSource voice;
    AudioClip impactSound, warningSound, fallSound;
    ParticleSystem breathParticles;
    PlayerCombat player;
    CombatState state;
    Move move, lastMove;
    float stateTime, duration, staggerProtection, poseClock, sparkTime, deathStartDown;
    float windup, activeTime, recovery, damage, nearRadius, farRadius, halfAngle;
    Vector3 moveStart, moveEnd, attackOrigin, attackForward, previousPosition;
    Quaternion turnStart, turnEnd;
    int struckLeg, stompLeg, attackCount, repeatCount;
    bool ready, touchedThisAttack, encounterStopped, justRepositioned;
    GroundShape warning, activeShape;
    AuthoredDragonVisual authored;

    public void Initialize(PlayerCombat combatPlayer)
    {
        player = combatPlayer;
        if (!ready)
        {
            BuildVisual();
            warning = new GroundShape("Veyr anticipation outline", transform, indicatorMaterial, ownedResources);
            activeShape = new GroundShape("Veyr active danger", transform, indicatorActiveMaterial, ownedResources);
            ready = true;
        }
        transform.position = new Vector3(0, 0, 5);
        transform.rotation = Quaternion.identity;
        Health = maxHealth;
        acceptedSwings.Clear(); recentSwings.Clear();
        for (int i = 0; i < 4; i++) { LegStagger[i] = 0; hitFlash[i] = 0; }
        LastHitRegion = -1; CollapseCount = 0; attackCount = 0; repeatCount = 0;
        lastMove = Move.None; move = Move.None;
        staggerProtection = 0; poseClock = 0; sparkTime = 0; deathStartDown = 0;
        encounterStopped = false; justRepositioned = false;
        CancelDanger();
        Enter(CombatState.Idle, 2.2f, "VEYR AWAKENS");
        UpdatePose(0);
        if(!authored){authored=gameObject.AddComponent<AuthoredDragonVisual>();authored.Initialize(this);}
    }

    void Update()
    {
        if (!ready) return;
        // The combat clock is scaled with the game, so pause freezes all windows.
        float dt = Time.deltaTime;
        if (dt <= 0) return;
        poseClock += dt;
        staggerProtection = Mathf.Max(0, staggerProtection - dt);
        for (int i = 0; i < 4; i++) hitFlash[i] = Mathf.Max(0, hitFlash[i] - dt * 4);
        sparkTime = Mathf.Max(0, sparkTime - dt);

        if (!IsDead && player != null && player.IsDead && !encounterStopped)
        {
            encounterStopped = true;
            CancelDanger();
            StateLabel = "THE WARDEN ENDURES";
        }
        if (!encounterStopped || IsDead) { stateTime += dt; AdvanceState(dt); }
        UpdatePose(dt);
        UpdateIndicators();
    }

    void AdvanceState(float dt)
    {
        switch (state)
        {
            case CombatState.Idle:
                if (stateTime >= duration && player != null && !player.IsDead) ChooseAction();
                break;
            case CombatState.Reposition:
                float step = Smooth(stateTime / duration);
                transform.position = Vector3.Lerp(moveStart, moveEnd, step);
                transform.rotation = Quaternion.Slerp(turnStart, turnEnd, step);
                if (stateTime >= duration)
                {
                    justRepositioned = true;
                    Enter(CombatState.Idle, .8f, "WATCH THE SHOULDERS");
                }
                break;
            case CombatState.Windup:
                if (stateTime >= duration)
                {
                    previousPosition = transform.position;
                    Enter(CombatState.Active, activeTime, AttackName(move));
                    if (move == Move.Stomp || move == Move.Lunge) Play(impactSound, .6f);
                }
                break;
            case CombatState.Active:
                if (move == Move.Lunge)
                {
                    previousPosition = transform.position;
                    transform.position = Vector3.Lerp(moveStart, moveEnd, Smooth(stateTime / duration));
                }
                TryDamagePlayer();
                if (stateTime >= duration)
                {
                    CancelDanger();
                    Enter(CombatState.Recovery, recovery, "OPENING — STRIKE OR HEAL");
                }
                break;
            case CombatState.Recovery:
                if (stateTime >= duration) Enter(CombatState.Idle, 1f, "VEYR WATCHES");
                break;
            case CombatState.Buckle:
                if (stateTime >= duration) { Play(fallSound, .65f); Enter(CombatState.Collapse, 1f, "THE WARDEN FALLS"); }
                break;
            case CombatState.Collapse:
                if (stateTime >= duration) Enter(CombatState.Exposed, 7f, "HEAD EXPOSED — STRIKE THE IVORY THROAT");
                break;
            case CombatState.Exposed:
                if (stateTime >= duration) Enter(CombatState.Rise, 2f, "VEYR RISES — WITHDRAW");
                break;
            case CombatState.Rise:
                if (stateTime >= duration)
                {
                    for (int i = 0; i < 4; i++) LegStagger[i] = 0;
                    staggerProtection = 2f;
                    Enter(CombatState.Idle, .8f, "VEYR RECOVERS");
                }
                break;
            // Death deliberately has no damaging transition and never restarts itself.
            case CombatState.Dead: break;
        }
    }

    void Enter(CombatState next, float seconds, string label)
    {
        // A lethal head strike must not stand a collapsed dragon up for its death.
        if (next == CombatState.Dead) deathStartDown = PoseDown();
        state = next; stateTime = 0; duration = seconds; StateLabel = label;
    }

    void ChooseAction()
    {
        Vector3 offset = Flat(player.transform.position - transform.position);
        Vector3 local = transform.InverseTransformDirection(offset);
        float distance = offset.magnitude;
        float angle = distance > .01f ? Vector3.Angle(-transform.forward, offset) : 0;
        if (!justRepositioned && ((distance > 12 && angle > 40) || distance > 21 || attackCount % 4 == 3))
        {
            BeginReposition(offset);
            return;
        }

        Move next;
        if (local.z > 2.5f && distance < 11.5f) next = Move.Tail;
        else if (distance < 7.5f && (Mathf.Abs(local.x) > 2 || attackCount % 2 == 0)) next = Move.Stomp;
        else if (local.z < -3 && local.z > -11 && Mathf.Abs(local.x) < 4.5f) next = Move.Bite;
        else if (distance > 13 && angle < 45 && attackCount % 2 == 0) next = Move.Lunge;
        else if (angle < 90) next = Move.Breath;
        else next = Move.Stomp;

        if (next == lastMove && repeatCount >= 2)
        {
            BeginReposition(offset);
            return;
        }
        BeginAttack(next);
    }

    void BeginReposition(Vector3 offset)
    {
        move = Move.None; CancelDanger();
        moveStart = transform.position;
        Vector3 direction = offset.sqrMagnitude > .01f ? offset.normalized : -transform.forward;
        float distance = offset.magnitude;
        float travel = distance > 14 ? Mathf.Min(5, distance - 11) : distance < 4 ? -4 : 0;
        moveEnd = ClampArena(moveStart + direction * travel);
        turnStart = transform.rotation;
        Quaternion desired = Quaternion.LookRotation(-direction, Vector3.up);
        // Bound the turn to a deliberate step; never spin to face the player instantly.
        turnEnd = Quaternion.RotateTowards(turnStart, desired, 70);
        repeatCount = 0;
        Enter(CombatState.Reposition, 2.3f, "REPOSITIONING — FOLLOW THE FOOTFALLS");
    }

    void BeginAttack(Move next)
    {
        justRepositioned = false;
        move = next; attackCount++;
        repeatCount = next == lastMove ? repeatCount + 1 : 1; lastMove = next;
        touchedThisAttack = false;
        attackForward = -transform.forward;
        attackOrigin = Flat(transform.position);
        moveStart = transform.position; moveEnd = moveStart;
        nearRadius = 0; farRadius = 0; halfAngle = 180;
        switch (move)
        {
            case Move.Stomp:
                windup = 1.1f; activeTime = .22f; recovery = 1.35f; damage = 32;
                stompLeg = 0; float closest = float.MaxValue;
                for (int i = 0; i < 4; i++)
                {
                    float d = Flat(player.transform.position - LegPositions[i]).sqrMagnitude;
                    if (d < closest) { closest = d; stompLeg = i; }
                }
                attackOrigin = Flat(authored&&authored.IsReady?authored.GetFootPosition(stompLeg):transform.TransformPoint(Feet[stompLeg]));
                farRadius = 2.6f;
                break;
            case Move.Breath:
                windup = 1.6f; activeTime = 2.1f; recovery = 2f; damage = 30;
                attackOrigin = Flat(transform.TransformPoint(new Vector3(0, 0, -4.4f)));
                nearRadius = .65f; farRadius = 17; halfAngle = 66;
                break;
            case Move.Tail:
                windup = 1.35f; activeTime = .55f; recovery = 1.6f; damage = 28;
                attackForward = transform.forward; nearRadius = 4; farRadius = 10; halfAngle = 100;
                break;
            case Move.Bite:
                windup = .95f; activeTime = .25f; recovery = 1.45f; damage = 34;
                attackOrigin = Flat(transform.TransformPoint(new Vector3(0, 0, -3)));
                nearRadius = .4f; farRadius = 4.6f; halfAngle = 32;
                break;
            case Move.Lunge:
                windup = 1.4f; activeTime = .85f; recovery = 1.9f; damage = 36;
                moveEnd = ClampArena(moveStart + attackForward * 8);
                farRadius = 2.7f;
                break;
        }
        Enter(CombatState.Windup, windup, "READ: " + AttackName(move));
        Play(warningSound, move == Move.Breath ? .55f : .3f);
    }

    void TryDamagePlayer()
    {
        if (touchedThisAttack || player == null || player.IsDead || Health <= 0) return;
        Vector3 point = Flat(player.transform.position);
        bool inside = false;
        switch (move)
        {
            case Move.Stomp: inside = Vector3.Distance(point, attackOrigin) < farRadius - .15f; break;
            case Move.Breath:
                inside = InSector(point, attackOrigin, SweepDirection(), nearRadius + .15f, farRadius - .15f, 12);
                break;
            case Move.Tail:
                inside = InSector(point, attackOrigin, SweepDirection(), nearRadius + .15f, farRadius - .15f, 25);
                break;
            case Move.Bite:
                inside = stateTime >= activeTime * .35f && InSector(point, attackOrigin, attackForward, nearRadius + .15f, farRadius - .15f, halfAngle - 2);
                break;
            case Move.Lunge:
                Vector3 a = Flat(previousPosition) + attackForward * 4.8f;
                Vector3 b = Flat(transform.position) + attackForward * 4.8f;
                inside = DistanceToSegment(point, a, b) < farRadius - .15f;
                break;
        }
        if (!inside) return;
        // A contact during dodge is consumed as an evade: lingering fire cannot
        // damage the player again on the first frame after invulnerability ends.
        touchedThisAttack = true;
        player.TakeDamage(damage, attackOrigin);
    }

    /// <summary>Call during the sword's actual active interval, with a unique swing id.</summary>
    public void ReceiveSword(Vector3 attackerPosition, Vector3 forward, int swingId)
    {
        if (!ready || IsDead || encounterStopped || acceptedSwings.Contains(swingId)) return;
        Vector3 origin = attackerPosition + Vector3.up * 1.1f;
        forward = Flat(forward);
        if (forward.sqrMagnitude < .001f) return;
        forward.Normalize();
        int region = -1;
        float closest = float.MaxValue;
        for (int i = 0; i < 4; i++)
        {
            float d;
            if (SwordContact(origin, forward, LegPositions[i], .75f, out d) && d < closest)
            { closest = d; region = i; }
        }
        float headDistance;
        if (SwordContact(origin, forward, HeadTarget.position, 1f, out headDistance) && headDistance < closest)
        { closest = headDistance; region = 4; }
        // Body is a fallback only: a surrounding body shape cannot steal a leg hit.
        if (region < 0)
        {
            float bodyDistance;
            if (SwordContact(origin, forward, transform.TransformPoint(new Vector3(0, 3.25f, 0)), 1.8f, out bodyDistance)) region = 5;
        }
        if (region < 0) return;
        acceptedSwings.Add(swingId); recentSwings.Enqueue(swingId);
        if (recentSwings.Count > 512) acceptedSwings.Remove(recentSwings.Dequeue());
        LastHitRegion = region;
        float amount = region < 4 ? 24 : region == 4 ? (HeadExposed ? 120 : 36) : 12;
        Health = Mathf.Max(0, Health - amount);
        Vector3 contact = region < 4 ? LegPositions[region] : region == 4 ? HeadTarget.position : origin + forward * 1.7f;
        hitSpark.position = contact; sparkTime = .22f;
        Play(impactSound, HeadExposed && region == 4 ? .75f : .32f);
        if (region < 4) hitFlash[region] = 1;
        if (Health <= 0)
        {
            CancelDanger();
            Enter(CombatState.Dead, 3.4f, "VEYR, THE CINDER WARDEN — FELLED");
            Play(fallSound, .85f);
            return;
        }
        if (region < 4 && CanStagger())
        {
            LegStagger[region] = Mathf.Min(100, LegStagger[region] + 25);
            if (LegStagger[region] >= 100)
            {
                struckLeg = region; CollapseCount++;
                CancelDanger();
                Enter(CombatState.Buckle, .65f, LegNames[region] + " LEG BUCKLES");
                Play(fallSound, .45f);
            }
        }
    }

    bool CanStagger()
    {
        return staggerProtection <= 0 && state != CombatState.Buckle && state != CombatState.Collapse &&
               state != CombatState.Exposed && state != CombatState.Rise && state != CombatState.Dead;
    }

    static bool SwordContact(Vector3 origin, Vector3 facing, Vector3 target, float radius, out float score)
    {
        Vector3 delta = target - origin;
        score = Mathf.Max(0, delta.magnitude - radius);
        if (score > 2.6f || Mathf.Abs(delta.y) > 2.35f + radius) return false;
        Vector3 flat = Flat(delta);
        return flat.sqrMagnitude < .16f || Vector3.Dot(facing, flat.normalized) >= .15f;
    }

    void CancelDanger()
    {
        if (warning != null) warning.Hide();
        if (activeShape != null) activeShape.Hide();
        if (breathParticles != null && breathParticles.isPlaying)
            breathParticles.Stop(true, ParticleSystemStopBehavior.StopEmittingAndClear);
    }

    Vector3 SweepDirection()
    {
        float angle = Mathf.Lerp(-halfAngle, halfAngle, Mathf.Clamp01(stateTime / activeTime));
        return Quaternion.AngleAxis(angle, Vector3.up) * attackForward;
    }

    void UpdateIndicators()
    {
        if (encounterStopped || (state != CombatState.Windup && state != CombatState.Active)) { CancelDanger(); return; }
        float progress = state == CombatState.Windup ? Mathf.Clamp01(stateTime / windup) : 1;
        Color anticipation = Color.Lerp(new Color(.72f, .30f, .055f, .55f), new Color(1, .75f, .25f, .95f), progress);
        warning.Color(anticipation);
        activeShape.Color(new Color(1, .19f, .025f, .7f));
        if (move == Move.Lunge)
        {
            Vector3 a = Flat(moveStart) + attackForward * 4.8f;
            Vector3 b = Flat(moveEnd) + attackForward * 4.8f;
            warning.Corridor(a, b, farRadius, false);
            if (state == CombatState.Active)
                activeShape.Sector(Flat(transform.position) + attackForward * 4.8f, attackForward, 0, farRadius, 180, true);
            else activeShape.Hide();
        }
        else
        {
            // The full intended swept area stays outlined; only the bright moving
            // wedge is dangerous during a sweep. Both use this same origin/direction.
            float fullAngle = move == Move.Breath ? halfAngle + 12 : move == Move.Tail ? halfAngle + 25 : halfAngle;
            warning.Sector(attackOrigin, attackForward, nearRadius, farRadius, fullAngle, false);
            if (state == CombatState.Active)
            {
                bool sweeping = move == Move.Breath || move == Move.Tail;
                activeShape.Sector(attackOrigin, sweeping ? SweepDirection() : attackForward,
                    nearRadius, farRadius, move == Move.Breath ? 12 : move == Move.Tail ? 25 : halfAngle, true);
            }
            else activeShape.Hide();
        }
    }

    void UpdatePose(float dt)
    {
        float progress = duration > 0 ? Mathf.Clamp01(stateTime / duration) : 0;
        float down = PoseDown();
        float buckle = state == CombatState.Buckle ? Smooth(progress) : 0;
        float breathe = IsDead ? 0 : Mathf.Sin(poseClock * 1.8f) * .09f * (1 - down);
        float roll = (struckLeg % 2 == 0 ? 1 : -1) * (buckle * 11 + down * 17);
        Vector3 torso = new Vector3(0, 5 + breathe - down * 3.2f - buckle * .65f, 0);
        if (state == CombatState.Windup && move == Move.Lunge) torso.y -= progress * .5f;
        body.localPosition = torso;
        body.localRotation = Quaternion.Euler(down * -7, 0, roll);
        chest.localPosition = torso + new Vector3(0, .3f, -1.8f);
        chest.localRotation = body.localRotation;

        Vector3 headLocal = new Vector3(down * .75f, Mathf.Lerp(3.5f, 1.12f, down) + breathe - buckle * .25f, Mathf.Lerp(-4.9f, -6.0f, down));
        float neckYaw = 0, jawAngle = 0;
        if ((state == CombatState.Windup || state == CombatState.Active) && move == Move.Breath)
        {
            float sweep = state == CombatState.Windup ? -halfAngle * Smooth(progress) : Mathf.Lerp(-halfAngle, halfAngle, progress);
            neckYaw = sweep;
            headLocal.x -= Mathf.Sin(sweep * Mathf.Deg2Rad) * 1.25f;
            headLocal.y += state == CombatState.Windup ? Smooth(progress) * .65f : .35f;
            jawAngle = state == CombatState.Windup ? progress * 28 : 36;
        }
        if ((state == CombatState.Windup || state == CombatState.Active || state == CombatState.Recovery) && move == Move.Bite)
        {
            if (state == CombatState.Windup) { headLocal.z += Smooth(progress) * .9f; headLocal.y += .35f * progress; jawAngle = progress * 36; }
            else if (state == CombatState.Active) { headLocal.z += Mathf.Lerp(.9f, -1.8f, Smooth(progress)); headLocal.y += Mathf.Lerp(.35f, -.9f, Smooth(progress)); jawAngle = 36 * (1 - progress); }
            else { headLocal.z -= (1 - Smooth(progress)) * 1.8f; headLocal.y -= .9f * (1 - progress); }
        }
        if (state == CombatState.Windup && move == Move.Lunge) headLocal.y -= progress * .5f;
        head.localPosition = headLocal;
        head.localRotation = Quaternion.Euler(down * 5, neckYaw, roll * .3f);
        jaw.localRotation = Quaternion.Euler(jawAngle, 0, 0);
        HeadTarget.position = transform.TransformPoint(headLocal + new Vector3(0, -.1f, -.5f));
        Segment(neckA, torso + new Vector3(0, .2f, -2.1f), Vector3.Lerp(torso, headLocal, .6f) + Vector3.up * .35f, 1.35f);
        Segment(neckB, Vector3.Lerp(torso, headLocal, .6f) + Vector3.up * .35f, headLocal, 1.05f);

        for (int i = 0; i < 4; i++)
        {
            float side = i % 2 == 0 ? -1 : 1;
            Vector3 ankle = Feet[i];
            float footLift = 0;
            if (state == CombatState.Reposition)
            {
                float gait = Mathf.Sin(progress * Mathf.PI * 4 + (i == 0 || i == 3 ? 0 : Mathf.PI));
                ankle.z += gait * .4f;
                footLift = Mathf.Max(0, gait) * .55f;
            }
            if (move == Move.Stomp && i == stompLeg)
            {
                if (state == CombatState.Windup)
                    footLift += progress < .7f ? Smooth(progress / .7f) * 2.4f : (1 - Smooth((progress - .7f) / .3f)) * 2.4f;
            }
            ankle.y += footLift;
            ankle.x += side * down * .55f;
            Vector3 hip = torso + new Vector3(side * 1.8f, -.3f, i < 2 ? -1.7f : 1.7f);
            Vector3 knee = Vector3.Lerp(hip, ankle, .5f) + new Vector3(side * .75f, .15f, i < 2 ? -.6f : .7f);
            if (i == struckLeg)
            {
                knee.y -= buckle * 1.2f; knee.z += buckle * .75f;
            }
            knee.y = Mathf.Max(.7f, knee.y);
            Segment(upperLeg[i], hip, knee, 1.1f);
            Segment(lowerLeg[i], knee, ankle, .72f);
            foot[i].localPosition = ankle + new Vector3(0, -.4f, -.3f);
            foot[i].localRotation = Quaternion.Euler(0, side * 10, down * side * 12);
            legLocal[i] = ankle;
            LegPositions[i] = transform.TransformPoint(ankle);
            Color glow = Color.Lerp(new Color(.19f, .065f, .025f), new Color(1, .48f, .055f), LegStagger[i] / 100f);
            glow = Color.Lerp(glow, Color.white, hitFlash[i]);
            SetGlow(legGlow[i], glow, .4f + LegStagger[i] / 55f + hitFlash[i] * 2);
        }

        float spread = down * -24;
        if (state == CombatState.Reposition) spread += Mathf.Sin(progress * Mathf.PI * 2) * 9;
        if (state == CombatState.Windup && (move == Move.Breath || move == Move.Lunge)) spread += progress * 18;
        leftWing.localPosition = torso + new Vector3(-1.6f, .7f, -.9f);
        rightWing.localPosition = torso + new Vector3(1.6f, .7f, -.9f);
        float wingIdle = IsDead ? 0 : Mathf.Sin(poseClock * .8f) * 1.5f;
        leftWing.localRotation = Quaternion.Euler(0, -8, -spread + wingIdle);
        rightWing.localRotation = Quaternion.Euler(0, 8, spread - wingIdle);
        float tailSwing = IsDead ? 0 : Mathf.Sin(poseClock * .75f) * 7;
        if (move == Move.Tail)
        {
            if (state == CombatState.Windup) tailSwing = -100 * Smooth(progress);
            else if (state == CombatState.Active) tailSwing = Mathf.Lerp(-100, 100, progress);
            else if (state == CombatState.Recovery) tailSwing = 100 * (1 - Smooth(progress));
        }
        Vector3 tailStart = torso + new Vector3(0, -.3f, 2.4f);
        for (int i = 0; i < tail.Length; i++)
        {
            float yaw = tailSwing * (i + 1f) / tail.Length;
            Vector3 direction = Quaternion.Euler(0, yaw, 0) * Vector3.forward;
            Vector3 tailEnd = tailStart + direction * 1.18f;
            tailEnd.y = Mathf.Max(.4f, torso.y - 1 - i * .43f - down * .1f);
            Segment(tail[i], tailStart, tailEnd, Mathf.Lerp(1.05f, .16f, i / 6f));
            tailStart = tailEnd;
        }
        float heat = HeadExposed ? (HeadWindowRemaining < 1 ? HeadWindowRemaining : 1) : state == CombatState.Windup && move == Move.Breath ? progress : .15f;
        SetGlow(throatRenderer, IsDead ? new Color(.045f, .02f, .01f) : Color.Lerp(new Color(.9f, .16f, .015f), new Color(1, .88f, .55f), heat), IsDead ? 0 : .8f + heat * 3);
        hitSpark.gameObject.SetActive(sparkTime > 0);
        if (sparkTime > 0)
        {
            float age = 1 - sparkTime / .22f;
            hitSpark.localScale = Vector3.one * Mathf.Lerp(.25f, 1.1f, age);
            SetGlow(sparkRenderer, Color.Lerp(Color.white, new Color(1, .26f, .02f), age), (1 - age) * 4);
        }
        if(authored&&authored.IsReady)authored.EvaluatePose();
        if (state == CombatState.Active && move == Move.Breath && !encounterStopped)
        {
            Vector3 muzzle = authored&&authored.IsReady?authored.MuzzlePosition:head.TransformPoint(new Vector3(0, -.2f, -1.5f));
            Vector3 destination = attackOrigin + SweepDirection() * farRadius + Vector3.up * .3f;
            breathParticles.transform.position = muzzle;
            breathParticles.transform.rotation = Quaternion.LookRotation(destination - muzzle);
            if (!breathParticles.isPlaying) breathParticles.Play();
        }
    }

    float PoseDown()
    {
        float progress = duration > 0 ? Mathf.Clamp01(stateTime / duration) : 0;
        if (state == CombatState.Collapse) return Smooth(progress);
        if (state == CombatState.Exposed) return 1;
        if (state == CombatState.Rise) return 1 - Smooth(progress);
        if (state == CombatState.Dead) return Mathf.Lerp(deathStartDown, 1, Smooth(stateTime / 2.2f));
        return 0;
    }

    void SetGlow(Renderer renderer, Color color, float emission)
    {
        properties.Clear(); properties.SetColor("_Color", color); properties.SetColor("_EmissionColor", color * emission);
        renderer.SetPropertyBlock(properties);
    }

    void BuildVisual()
    {
        TemporaryVisual = new GameObject("TEMPORARY dragon proxy — replace with Tripo and Blender rig").transform;
        TemporaryVisual.SetParent(transform, false);
        HeadTarget = new GameObject("Head target — independent combat anchor").transform;
        HeadTarget.SetParent(transform, false);
        stone = Material("Temporary Veyr basalt", new Color(.105f, .125f, .15f), .58f, .25f);
        armor = Material("Temporary Veyr armor", new Color(.22f, .25f, .27f), .69f, .55f);
        copper = Material("Temporary Veyr copper edges", new Color(.39f, .24f, .105f), .62f, .8f);
        membrane = Material("Temporary Veyr sail wings", new Color(.15f, .055f, .035f), .25f, .1f);
        hot = Material("Original ivory furnace emission", new Color(1, .36f, .025f), .4f, .1f);
        hot.EnableKeyword("_EMISSION"); hot.SetColor("_EmissionColor", new Color(2, .6f, .04f));
        indicatorMaterial = OverlayMaterial("Original amber anticipation", new Color(1, .55f, .1f, .8f));
        indicatorActiveMaterial = OverlayMaterial("Original active cinder hazard", new Color(1, .17f, .02f, .65f));
        body = Primitive("Basalt torso", PrimitiveType.Sphere, TemporaryVisual, Vector3.zero, new Vector3(5, 3.3f, 6), stone);
        chest = Primitive("Powerful shoulder mantle", PrimitiveType.Sphere, TemporaryVisual, Vector3.zero, new Vector3(5.7f, 3.5f, 3.4f), armor);
        neckA = Primitive("Neck base", PrimitiveType.Capsule, TemporaryVisual, Vector3.zero, Vector3.one, stone);
        neckB = Primitive("Neck crest", PrimitiveType.Capsule, TemporaryVisual, Vector3.zero, Vector3.one, armor);
        head = new GameObject("Temporary crown and jaw").transform; head.SetParent(TemporaryVisual, false);
        Primitive("Crowned skull", PrimitiveType.Sphere, head, Vector3.zero, new Vector3(2.35f, 1.65f, 2.7f), armor);
        Primitive("Blunt armored muzzle", PrimitiveType.Cube, head, new Vector3(0, -.1f, -1.15f), new Vector3(1.7f, .7f, 1.45f), stone);
        jaw = new GameObject("Hinged lower jaw").transform; jaw.SetParent(head, false); jaw.localPosition = new Vector3(0, -.48f, .05f);
        Primitive("Lower jaw", PrimitiveType.Cube, jaw, new Vector3(0, -.07f, -.8f), new Vector3(1.5f, .35f, 2.25f), copper);
        throat = Primitive("Ivory throat weakpoint", PrimitiveType.Sphere, head, new Vector3(0, -.56f, -1.03f), new Vector3(1.1f, .42f, 1.2f), hot);
        throatRenderer = throat.GetComponent<Renderer>();
        for (int side = -1; side <= 1; side += 2)
        {
            Primitive("Ember eye", PrimitiveType.Sphere, head, new Vector3(side * 1.03f, .25f, -.65f), new Vector3(.22f, .2f, .38f), hot);
            Cone("Forked crown horn", head, new Vector3(side * .8f, .6f, .2f), new Vector3(side * 1.5f, 2.15f, 1.5f), .38f, copper);
            Cone("Cheek horn", head, new Vector3(side * 1, -.05f, .6f), new Vector3(side * 1.9f, .3f, 1.65f), .25f, armor);
        }
        for (int i = 0; i < 8; i++)
        {
            float z = -2.2f + i * .62f;
            // Children inherit torso scale, so convert the ridge dimensions to its unit space.
            Cone("Basalt dorsal ridge", body, new Vector3(0, .43f, z / 6), new Vector3(0, .78f, (z + .4f) / 6), .07f, copper);
        }
        for (int i = 0; i < 4; i++)
        {
            upperLeg[i] = Primitive(LegNames[i] + " upper", PrimitiveType.Capsule, TemporaryVisual, Vector3.zero, Vector3.one, stone);
            lowerLeg[i] = Primitive(LegNames[i] + " shin", PrimitiveType.Capsule, TemporaryVisual, Vector3.zero, Vector3.one, armor);
            foot[i] = Primitive(LegNames[i] + " foot", PrimitiveType.Sphere, TemporaryVisual, Vector3.zero, new Vector3(1.65f, .85f, 2.1f), stone);
            Transform band = Primitive("Leg stagger fissure", PrimitiveType.Sphere, foot[i], new Vector3(0, .35f, 0), new Vector3(.63f, .25f, .55f), hot);
            legGlow[i] = band.GetComponent<Renderer>();
            for (int claw = -1; claw <= 1; claw++)
                Cone("Copper talon", foot[i], new Vector3(claw * .3f, -.1f, -.3f), new Vector3(claw * .4f, -.25f, -.82f), .12f, copper);
        }
        leftWing = BuildWing(-1); rightWing = BuildWing(1);
        for (int i = 0; i < tail.Length; i++) tail[i] = Primitive("Tail counterweight " + i, PrimitiveType.Capsule, TemporaryVisual, Vector3.zero, Vector3.one, i % 2 == 0 ? armor : stone);
        hitSpark = Primitive("Original sword contact flare", PrimitiveType.Sphere, transform, Vector3.zero, Vector3.one, hot);
        sparkRenderer = hitSpark.GetComponent<Renderer>();
        hitSpark.gameObject.SetActive(false);
        voice = gameObject.AddComponent<AudioSource>(); voice.spatialBlend = .4f; voice.rolloffMode = AudioRolloffMode.Linear;
        voice.minDistance = 8; voice.maxDistance = 45; voice.playOnAwake = false;
        impactSound = Synth("Original basalt impact", .24f, 75, 11);
        warningSound = Synth("Original furnace anticipation", .85f, 46, 17);
        fallSound = Synth("Original heavy collapse", 1.15f, 38, 23);
        BuildBreath();
    }

    void BuildBreath()
    {
        var go = new GameObject("Original temporary furnace breath particles"); go.transform.SetParent(transform, false);
        breathParticles = go.AddComponent<ParticleSystem>();
        breathParticles.Stop(true, ParticleSystemStopBehavior.StopEmittingAndClear);
        var main = breathParticles.main;
        main.playOnAwake = false; main.loop = true; main.maxParticles = 220;
        main.startLifetime = new ParticleSystem.MinMaxCurve(.55f, .9f);
        main.startSpeed = new ParticleSystem.MinMaxCurve(17, 23);
        main.startSize = new ParticleSystem.MinMaxCurve(.45f, 1.15f);
        main.simulationSpace = ParticleSystemSimulationSpace.World;
        main.startColor = new Color(1, .55f, .1f, .8f);
        var emission = breathParticles.emission; emission.rateOverTime = 100;
        var shape = breathParticles.shape; shape.shapeType = ParticleSystemShapeType.Cone; shape.angle = 7; shape.radius = .25f;
        var size = breathParticles.sizeOverLifetime; size.enabled = true;
        size.size = new ParticleSystem.MinMaxCurve(1, AnimationCurve.Linear(0, .4f, 1, 2));
        var fade = breathParticles.colorOverLifetime; fade.enabled = true;
        var gradient = new Gradient();
        gradient.SetKeys(new[] { new GradientColorKey(new Color(1, .95f, .6f), 0), new GradientColorKey(new Color(1, .22f, .015f), .45f), new GradientColorKey(new Color(.22f, .035f, .005f), 1) },
            new[] { new GradientAlphaKey(0, 0), new GradientAlphaKey(.8f, .12f), new GradientAlphaKey(0, 1) });
        fade.color = gradient;
        Texture2D texture = new Texture2D(32, 32, TextureFormat.RGBA32, false); texture.name = "Original radial fire sprite";
        for (int y = 0; y < 32; y++) for (int x = 0; x < 32; x++)
        {
            float r = Vector2.Distance(new Vector2(x, y), new Vector2(15.5f, 15.5f)) / 15.5f;
            texture.SetPixel(x, y, new Color(1, 1, 1, Mathf.Pow(Mathf.Clamp01(1 - r), 1.7f)));
        }
        texture.Apply(); ownedResources.Add(texture);
        var material = new Material(Shader.Find("Sprites/Default")); material.name = "Original soft fire sprite material"; material.mainTexture = texture; ownedResources.Add(material);
        var renderer = breathParticles.GetComponent<ParticleSystemRenderer>(); renderer.sharedMaterial = material;
        renderer.shadowCastingMode = ShadowCastingMode.Off; renderer.receiveShadows = false;
    }

    Transform BuildWing(int side)
    {
        var pivot = new GameObject(side < 0 ? "Temporary left sail wing" : "Temporary right sail wing").transform;
        pivot.SetParent(TemporaryVisual, false);
        Vector3 shoulder = Vector3.zero;
        Vector3 elbow = new Vector3(side * 4.1f, 2.9f, .5f);
        Vector3 tip = new Vector3(side * 9.8f, 1.3f, 2.1f);
        Vector3 rear = new Vector3(side * 2.1f, -.35f, 4.4f);
        var mesh = new Mesh { name = "Original temporary sail silhouette" };
        ownedResources.Add(mesh);
        Vector3[] vertices = { shoulder, elbow, tip, new Vector3(side * 7.4f, .05f, 3.4f), new Vector3(side * 5.8f, .6f, 4.2f), new Vector3(side * 4.5f, -.4f, 4.4f), rear };
        var triangles = new List<int>();
        for (int i = 1; i < vertices.Length - 1; i++) { triangles.AddRange(new[] { 0, i, i + 1, 0, i + 1, i }); }
        mesh.vertices = vertices; mesh.SetTriangles(triangles, 0); mesh.RecalculateNormals(); mesh.RecalculateBounds();
        var surface = new GameObject("Temporary authored sail mesh"); surface.transform.SetParent(pivot, false);
        surface.AddComponent<MeshFilter>().sharedMesh = mesh; surface.AddComponent<MeshRenderer>().sharedMaterial = membrane;
        Transform a = Primitive("Wing arm", PrimitiveType.Capsule, pivot, Vector3.zero, Vector3.one, armor); Segment(a, shoulder, elbow, .5f);
        Transform b = Primitive("Wing leading edge", PrimitiveType.Capsule, pivot, Vector3.zero, Vector3.one, copper); Segment(b, elbow, tip, .24f);
        for (int i = 3; i < vertices.Length; i++)
        {
            Transform rib = Primitive("Wing radial spar", PrimitiveType.Capsule, pivot, Vector3.zero, Vector3.one, stone); Segment(rib, elbow, vertices[i], .14f);
        }
        return pivot;
    }

    Material Material(string name, Color color, float gloss, float metal)
    {
        var material = new Material(Shader.Find("Standard")); material.name = name; material.color = color;
        material.SetFloat("_Glossiness", gloss); material.SetFloat("_Metallic", metal); ownedResources.Add(material); return material;
    }

    Material OverlayMaterial(string name, Color color)
    {
        Shader shader = Shader.Find("Sprites/Default");
        if (shader == null) shader = Shader.Find("Unlit/Color");
        var material = new Material(shader); material.name = name; material.color = color;
        material.SetInt("_ZWrite", 0); material.SetInt("_Cull", (int)CullMode.Off);
        material.renderQueue = 3050; ownedResources.Add(material); return material;
    }

    Transform Primitive(string name, PrimitiveType shape, Transform parent, Vector3 position, Vector3 scale, Material material)
    {
        GameObject go = GameObject.CreatePrimitive(shape); go.name = name; go.transform.SetParent(parent, false);
        go.transform.localPosition = position; go.transform.localScale = scale;
        Collider collider = go.GetComponent<Collider>(); collider.enabled = false; Destroy(collider);
        go.GetComponent<Renderer>().sharedMaterial = material; return go.transform;
    }

    void Cone(string name, Transform parent, Vector3 from, Vector3 to, float radius, Material material)
    {
        Vector3 direction = to - from;
        const int sides = 7;
        var vertices = new Vector3[sides + 2]; vertices[0] = Vector3.up * direction.magnitude;
        for (int i = 0; i < sides; i++) vertices[i + 1] = new Vector3(Mathf.Cos(i * Mathf.PI * 2 / sides) * radius, 0, Mathf.Sin(i * Mathf.PI * 2 / sides) * radius);
        var triangles = new int[sides * 6];
        for (int i = 0; i < sides; i++)
        {
            int j = (i + 1) % sides + 1;
            triangles[i * 6] = 0; triangles[i * 6 + 1] = j; triangles[i * 6 + 2] = i + 1;
            triangles[i * 6 + 3] = sides + 1; triangles[i * 6 + 4] = i + 1; triangles[i * 6 + 5] = j;
        }
        Mesh mesh = new Mesh { name = name + " original mesh" }; mesh.vertices = vertices; mesh.triangles = triangles; mesh.RecalculateNormals(); mesh.RecalculateBounds(); ownedResources.Add(mesh);
        var go = new GameObject(name); go.transform.SetParent(parent, false); go.transform.localPosition = from;
        go.transform.localRotation = Quaternion.FromToRotation(Vector3.up, direction.normalized);
        go.AddComponent<MeshFilter>().sharedMesh = mesh; go.AddComponent<MeshRenderer>().sharedMaterial = material;
    }

    static void Segment(Transform segment, Vector3 from, Vector3 to, float width)
    {
        Vector3 delta = to - from;
        segment.localPosition = (from + to) * .5f;
        segment.localRotation = Quaternion.FromToRotation(Vector3.up, delta.normalized);
        segment.localScale = new Vector3(width, delta.magnitude * .5f, width);
    }

    AudioClip Synth(string name, float seconds, float frequency, int seed)
    {
        const int rate = 22050;
        float[] samples = new float[Mathf.CeilToInt(seconds * rate)];
        var random = new System.Random(seed);
        float filtered = 0;
        for (int i = 0; i < samples.Length; i++)
        {
            float t = i / (float)rate, n = i / (float)samples.Length;
            filtered = Mathf.Lerp(filtered, (float)random.NextDouble() * 2 - 1, .1f);
            float envelope = Mathf.Min(1, t * 65) * Mathf.Pow(1 - n, 2);
            samples[i] = (Mathf.Sin(t * frequency * Mathf.PI * 2 * (1 - n * .15f)) * .35f + filtered * .65f) * envelope * .65f;
        }
        AudioClip clip = AudioClip.Create(name, samples.Length, 1, rate, false); clip.SetData(samples, 0); ownedResources.Add(clip); return clip;
    }

    void Play(AudioClip clip, float volume) { if (voice != null && clip != null) voice.PlayOneShot(clip, volume); }
    static string AttackName(Move value)
    {
        switch (value)
        {
            case Move.Stomp: return "BASALT STOMP";
            case Move.Breath: return "BELLOWS SWEEP";
            case Move.Tail: return "COUNTERWEIGHT TAIL";
            case Move.Bite: return "FURNACE BITE";
            case Move.Lunge: return "PROCESSIONAL LUNGE";
            default: return "VEYR WATCHES";
        }
    }
    static Vector3 Flat(Vector3 value) { value.y = 0; return value; }
    static Vector3 ClampArena(Vector3 value) { return Vector3.ClampMagnitude(Flat(value), 30); }
    static float Smooth(float value) { value = Mathf.Clamp01(value); return value * value * (3 - 2 * value); }
    static float DistanceToSegment(Vector3 p, Vector3 a, Vector3 b)
    {
        Vector3 d = b - a;
        float t = d.sqrMagnitude > .0001f ? Mathf.Clamp01(Vector3.Dot(p - a, d) / d.sqrMagnitude) : 0;
        return Vector3.Distance(p, a + d * t);
    }
    static bool InSector(Vector3 point, Vector3 origin, Vector3 forward, float inner, float outer, float angle)
    {
        Vector3 d = Flat(point - origin);
        float radius = d.magnitude;
        return radius >= inner && radius <= outer && (radius < .001f || Vector3.Angle(forward, d) <= angle);
    }

    void OnDisable() { CancelDanger(); }
    void OnDestroy()
    {
        foreach (Object resource in ownedResources) if (resource != null) Destroy(resource);
        ownedResources.Clear();
    }

    /// <summary>Reusable meshes; no colliders, coroutines, or per-frame GameObjects.</summary>
    sealed class GroundShape
    {
        readonly GameObject go;
        readonly Mesh mesh;
        readonly MeshRenderer renderer;
        readonly MaterialPropertyBlock block = new MaterialPropertyBlock();
        readonly List<Vector3> vertices = new List<Vector3>(512);
        readonly List<int> triangles = new List<int>(1024);
        public GroundShape(string name, Transform parent, Material material, List<Object> resources)
        {
            go = new GameObject(name); go.transform.SetParent(parent, false);
            mesh = new Mesh { name = name + " mesh" }; mesh.MarkDynamic(); resources.Add(mesh);
            go.AddComponent<MeshFilter>().sharedMesh = mesh;
            renderer = go.AddComponent<MeshRenderer>(); renderer.sharedMaterial = material;
            renderer.shadowCastingMode = ShadowCastingMode.Off; renderer.receiveShadows = false;
            go.SetActive(false);
        }
        public void Hide() { if (go != null) go.SetActive(false); }
        public void Color(Color value) { block.SetColor("_Color", value); renderer.SetPropertyBlock(block); }
        void Begin()
        {
            go.SetActive(true);
            // Vertices are world ground coordinates; inverse parent transform keeps
            // the telegraph fixed even while the lunge moves its owner.
            go.transform.position = Vector3.zero; go.transform.rotation = Quaternion.identity;
            vertices.Clear(); triangles.Clear();
        }
        void Quad(Vector3 a, Vector3 b, Vector3 c, Vector3 d)
        {
            const float height = .065f;
            a.y = height; b.y = height; c.y = height; d.y = height;
            int start = vertices.Count; vertices.Add(a); vertices.Add(b); vertices.Add(c); vertices.Add(d);
            triangles.Add(start); triangles.Add(start + 2); triangles.Add(start + 1);
            triangles.Add(start); triangles.Add(start + 3); triangles.Add(start + 2);
        }
        void Finish()
        {
            mesh.Clear(); mesh.SetVertices(vertices); mesh.SetTriangles(triangles, 0); mesh.RecalculateBounds();
        }
        public void Sector(Vector3 center, Vector3 direction, float inner, float outer, float half, bool filled)
        {
            Begin();
            int count = Mathf.Max(12, Mathf.CeilToInt(half * 2 / 6));
            const float width = .12f;
            for (int i = 0; i < count; i++)
            {
                Vector3 a = Quaternion.AngleAxis(Mathf.Lerp(-half, half, i / (float)count), Vector3.up) * direction;
                Vector3 b = Quaternion.AngleAxis(Mathf.Lerp(-half, half, (i + 1f) / count), Vector3.up) * direction;
                if (filled) Quad(center + a * inner, center + a * outer, center + b * outer, center + b * inner);
                else
                {
                    Quad(center + a * (outer - width), center + a * outer, center + b * outer, center + b * (outer - width));
                    if (inner > .1f) Quad(center + a * inner, center + a * (inner + width), center + b * (inner + width), center + b * inner);
                }
            }
            if (!filled && half < 179)
            {
                for (int s = -1; s <= 1; s += 2)
                {
                    Vector3 ray = Quaternion.AngleAxis(half * s, Vector3.up) * direction;
                    Vector3 edge = Vector3.Cross(Vector3.up, ray) * width * .5f;
                    Quad(center + ray * inner - edge, center + ray * outer - edge, center + ray * outer + edge, center + ray * inner + edge);
                }
            }
            Finish();
        }
        public void Corridor(Vector3 from, Vector3 to, float radius, bool filled)
        {
            Begin();
            Vector3 forward = Flat(to - from).normalized;
            if (forward.sqrMagnitude < .01f) forward = Vector3.forward;
            Vector3 right = Vector3.Cross(Vector3.up, forward);
            Vector3 a = from - forward * radius, b = to + forward * radius;
            if (filled) Quad(a - right * radius, b - right * radius, b + right * radius, a + right * radius);
            else
            {
                const float edge = .12f;
                Quad(a - right * radius, b - right * radius, b - right * (radius - edge), a - right * (radius - edge));
                Quad(a + right * (radius - edge), b + right * (radius - edge), b + right * radius, a + right * radius);
                Quad(a - right * radius, a + right * radius, a + right * radius + forward * edge, a - right * radius + forward * edge);
                Quad(b - right * radius - forward * edge, b + right * radius - forward * edge, b + right * radius, b - right * radius);
            }
            Finish();
        }
    }
}
