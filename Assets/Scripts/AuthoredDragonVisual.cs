using System;
using System.Collections.Generic;
using UnityEngine;

/// <summary>
/// Shows the TEMPORARY original Blender blockout. Tripo replacement remains required.
/// DragonBoss calls EvaluatePose from UpdatePose, before positioning breath VFX.
/// This component owns visuals only: damage and danger timing remain in DragonBoss.
/// </summary>
public sealed class AuthoredDragonVisual : MonoBehaviour
{
    const string ResourcePath = "Art/Veyr_TEMP_Rig";
    static readonly string[] RequiredClips = {
        "Idle", "Walk", "Stomp", "Bite", "Breath", "Tail_Sweep",
        "Buckle_fore_L", "Buckle_fore_R", "Buckle_hind_L", "Buckle_hind_R",
        "Collapse", "Stagger_Loop", "Recover", "Death"
    };
    static readonly string[] LegIds = { "fore_L", "fore_R", "hind_L", "hind_R" };
    readonly Dictionary<string, AnimationClip> clips = new Dictionary<string, AnimationClip>(StringComparer.Ordinal);
    readonly Dictionary<string, Transform> named = new Dictionary<string, Transform>(StringComparer.Ordinal);
    readonly List<Material> ownedMaterials = new List<Material>();
    readonly Transform[] lower = new Transform[4], feet = new Transform[4], upper = new Transform[4];
    readonly string[] mappedLegIds = new string[4];
    readonly Quaternion[] restUpper = new Quaternion[4], restLower = new Quaternion[4];
    Transform fit, modelRoot, head, jaw, rigRoot;
    Vector3 rootRestPosition, authoredRootAxis;
    Transform[] sampledTransforms;
    Vector3[] blendPositions;
    Quaternion[] blendRotations;
    Vector3[] blendScales;
    DragonBoss boss;
    DragonBoss.CombatState previousState;
    bool hasPreviousState, deathWasDown;
    public bool IsReady { get; private set; }
    public string CurrentClipName { get; private set; }
    public float CurrentClipTime { get; private set; }
    public Vector3 MuzzlePosition { get; private set; }

    public bool Initialize(DragonBoss owner)
    {
        if (IsReady) return true;
        boss = owner;
        var prefab = Resources.Load<GameObject>(ResourcePath);
        if (!prefab) return Fail("FBX resource missing; keeping primitive proxy.");
        foreach (var clip in Resources.LoadAll<AnimationClip>(ResourcePath))
        {
            if (clip.name.StartsWith("__preview__", StringComparison.Ordinal)) continue;
            string name = clip.name.Substring(clip.name.LastIndexOf('|') + 1);
            clips[name] = clip;
        }
        foreach (string required in RequiredClips)
            if (!clips.ContainsKey(required) || clips[required].length <= 0)
                return Fail("Required authored clip missing: " + required);

        fit = new GameObject("TEMP authored Veyr — Tripo replacement pending").transform;
        fit.SetParent(transform, false);
        modelRoot = Instantiate(prefab, fit, false).transform;
        modelRoot.name = "TEMP_Veyr_BlendSource";
        foreach (var animation in modelRoot.GetComponentsInChildren<Animation>(true))
        { animation.Stop(); animation.playAutomatically = false; animation.enabled = false; }
        foreach (var animator in modelRoot.GetComponentsInChildren<Animator>(true)) animator.enabled = false;
        foreach (var t in modelRoot.GetComponentsInChildren<Transform>(true)) named[t.name] = t;
        if (!named.TryGetValue("head", out head) || !named.TryGetValue("jaw", out jaw) ||
            !named.TryGetValue("root", out rigRoot) || !named.ContainsKey("body"))
            return Fail("Required head/body bones missing.");
        foreach (string leg in LegIds)
            if (!named.ContainsKey(leg + "_upper") || !named.ContainsKey(leg + "_lower") || !named.ContainsKey(leg + "_foot"))
                return Fail("Required separate leg bones missing: " + leg);
        if (modelRoot.GetComponentsInChildren<SkinnedMeshRenderer>(true).Length == 0)
            return Fail("No skinned mesh renderer found.");

        clips["Idle"].SampleAnimation(modelRoot.gameObject, 0);
        Vector3 restHeadPosition = head.position;
        Vector3 restFootPosition = named["fore_L_foot"].position;
        clips["Stomp"].SampleAnimation(modelRoot.gameObject, Frame(25));
        float sampleMovement = Vector3.Distance(head.position, restHeadPosition) +
            Vector3.Distance(named["fore_L_foot"].position, restFootPosition);
        if (sampleMovement < .01f) return Fail("Clips loaded but sampling did not move the rig; check import bindings.");
        clips["Idle"].SampleAnimation(modelRoot.gameObject, 0);
        // Derive front from the real rest skeleton instead of guessing FBX handedness.
        Vector3 front = fit.InverseTransformVector(head.position - named["body"].position);
        front.y = 0;
        if (front.sqrMagnitude < .01f) return Fail("Invalid rest skeleton forward direction.");
        fit.localRotation = Quaternion.FromToRotation(front.normalized, Vector3.back);
        float footSpan = Vector3.Distance(named["fore_L_foot"].position, named["fore_R_foot"].position);
        if (footSpan < .01f || footSpan > 500) return Fail("Unexpected FBX units/foot span.");
        fit.localScale = Vector3.one * (4.8f / footSpan);

        // Combat indices are negative-X front, positive-X front, negative-X rear,
        // positive-X rear. Derive L/R mapping after axis conversion, not from names.
        BindPair("fore_L", "fore_R", 0);
        BindPair("hind_L", "hind_R", 2);
        for (int i = 0; i < 4; i++)
        { restUpper[i] = upper[i].localRotation; restLower[i] = lower[i].localRotation; }
        // The TEMP Blender author keyed local Z as intended vertical translation,
        // but the root bone's local Y points upward. Discover that exported axis
        // from the known -1.55m Collapse endpoint rather than guessing FBX axes.
        rootRestPosition = rigRoot.localPosition;
        clips["Collapse"].SampleAnimation(modelRoot.gameObject, clips["Collapse"].length);
        authoredRootAxis = (rigRoot.localPosition - rootRestPosition) / -1.55f;
        clips["Idle"].SampleAnimation(modelRoot.gameObject, 0);
        Debug.Log("VEYR_ROOT_TRANSLATION_AXIS worldDirection=" + rigRoot.parent.TransformVector(authoredRootAxis).normalized);
        sampledTransforms = modelRoot.GetComponentsInChildren<Transform>(true);
        blendPositions = new Vector3[sampledTransforms.Length];
        blendRotations = new Quaternion[sampledTransforms.Length];
        blendScales = new Vector3[sampledTransforms.Length];
        ConfigureMaterials();
        IsReady = true;
        EvaluatePose();
        if (boss.TemporaryVisual) boss.TemporaryVisual.gameObject.SetActive(false);
        Debug.Log("VEYR_AUTHORED_VISUAL_READY temporary mesh; 14 clips; four actual leg anchors; head=" + boss.HeadTarget.position);
        return true;
    }

    void BindPair(string a, string b, int first)
    {
        if (transform.InverseTransformPoint(named[a + "_foot"].position).x > transform.InverseTransformPoint(named[b + "_foot"].position).x)
        { string swap = a; a = b; b = swap; }
        mappedLegIds[first] = a; mappedLegIds[first + 1] = b;
        for (int i = first; i < first + 2; i++)
        {
            upper[i] = named[mappedLegIds[i] + "_upper"];
            lower[i] = named[mappedLegIds[i] + "_lower"];
            feet[i] = named[mappedLegIds[i] + "_foot"];
        }
    }

    bool Fail(string message)
    {
        IsReady = false;
        if (fit) Destroy(fit.gameObject);
        if (boss && boss.TemporaryVisual) boss.TemporaryVisual.gameObject.SetActive(true);
        Debug.LogWarning("VEYR_AUTHORED_VISUAL_FALLBACK " + message);
        return false;
    }

    public Vector3 GetFootPosition(int index)
    {
        return IsReady ? feet[Mathf.Clamp(index, 0, 3)].position : boss.LegPositions[Mathf.Clamp(index, 0, 3)];
    }

    public void EvaluatePose()
    {
        if (!IsReady || !boss) return;
        var state = boss.CurrentState;
        float progress = boss.StateDuration > 0 ? Mathf.Clamp01(boss.StateElapsed / boss.StateDuration) : 0;
        bool changed = !hasPreviousState || state != previousState;
        if (changed)
        {
            if (state == DragonBoss.CombatState.Dead)
                deathWasDown = hasPreviousState && (previousState == DragonBoss.CombatState.Exposed || previousState == DragonBoss.CombatState.Collapse || previousState == DragonBoss.CombatState.Rise);
            for (int i = 0; i < sampledTransforms.Length; i++)
            { blendPositions[i] = sampledTransforms[i].localPosition; blendRotations[i] = sampledTransforms[i].localRotation; blendScales[i] = sampledTransforms[i].localScale; }
        }
        string clipName = "Idle";
        float time = Mathf.Repeat(boss.VisualClock, clips["Idle"].length);
        switch (state)
        {
            case DragonBoss.CombatState.Reposition:
                clipName = "Walk"; time = Mathf.Repeat(boss.StateElapsed, clips["Walk"].length); break;
            case DragonBoss.CombatState.Windup:
            case DragonBoss.CombatState.Active:
            case DragonBoss.CombatState.Recovery:
                MapAttack(boss.CurrentMoveName, state, progress, out clipName, out time); break;
            case DragonBoss.CombatState.Buckle:
                clipName = "Buckle_" + mappedLegIds[Mathf.Clamp(boss.StruckLegIndex, 0, 3)];
                time = Frame(Mathf.Lerp(1, 24, progress)); break; // retain buckle through collapse transition
            case DragonBoss.CombatState.Collapse:
                clipName = "Collapse"; time = Frame(Mathf.Lerp(18, 76, progress)); break;
            case DragonBoss.CombatState.Exposed:
                clipName = "Stagger_Loop"; time = Mathf.Repeat(boss.StateElapsed, clips[clipName].length); break;
            case DragonBoss.CombatState.Rise:
                clipName = "Recover"; time = Frame(Mathf.Lerp(1, 76, progress)); break;
            case DragonBoss.CombatState.Dead:
                clipName = "Death"; time = Frame(Mathf.Lerp(deathWasDown ? 65 : 1, 120, progress)); break;
        }
        CurrentClipName = clipName;
        CurrentClipTime = Mathf.Clamp(time, 0, clips[clipName].length);
        clips[clipName].SampleAnimation(modelRoot.gameObject, CurrentClipTime);

        if (clipName == "Stomp") RetargetStomp(Mathf.Clamp(boss.StompLegIndex, 0, 3));
        CorrectTemporaryRootTranslation();
        // A small transition blend handles interruptions; attack phase boundaries use
        // exact matching authored frames and must not lag the damage clock.
        bool blend = state == DragonBoss.CombatState.Buckle || state == DragonBoss.CombatState.Collapse ||
            state == DragonBoss.CombatState.Dead || state == DragonBoss.CombatState.Idle || state == DragonBoss.CombatState.Reposition;
        float alpha = Mathf.Clamp01(boss.StateElapsed / (state == DragonBoss.CombatState.Dead ? .18f : .10f));
        if (hasPreviousState && blend && alpha < 1)
            for (int i = 0; i < sampledTransforms.Length; i++)
            {
                var t = sampledTransforms[i];
                t.localPosition = Vector3.Lerp(blendPositions[i], t.localPosition, alpha);
                t.localRotation = Quaternion.Slerp(blendRotations[i], t.localRotation, alpha);
                t.localScale = Vector3.Lerp(blendScales[i], t.localScale, alpha);
            }

        // Bind combat to rendered anatomy, never the hidden proxy's fixed points.
        for (int i = 0; i < 4; i++) boss.LegPositions[i] = lower[i].position;
        Vector3 snoutDirection = (jaw.position - head.position).normalized;
        if (snoutDirection.sqrMagnitude < .1f) snoutDirection = -transform.forward;
        boss.HeadTarget.position = head.position + snoutDirection * .75f;
        MuzzlePosition = jaw.position + snoutDirection * 1.25f;
        previousState = state; hasPreviousState = true;
    }

    static float Frame(float frame) { return (frame - 1) / 30f; }

    void CorrectTemporaryRootTranslation()
    {
        if (authoredRootAxis.sqrMagnitude < .000001f || !rigRoot.parent) return;
        Vector3 animatedOffset = rigRoot.localPosition - rootRestPosition;
        float meters = Vector3.Dot(animatedOffset, authoredRootAxis) / authoredRootAxis.sqrMagnitude;
        Vector3 importedUp = rigRoot.parent.TransformVector(authoredRootAxis).normalized;
        Vector3 correctedOffset = Quaternion.FromToRotation(importedUp, Vector3.up) * rigRoot.parent.TransformVector(animatedOffset);
        // Version 2 sources already have vertical displacement, so this rotation
        // is identity and their intentional horizontal anticipation is preserved.
        Vector3 newRootPosition = rigRoot.parent.TransformPoint(rootRestPosition) + correctedOffset;
        rigRoot.position = newRootPosition;
        if (meters > -.35f || !named.ContainsKey("neck_01") || !named.ContainsKey("neck_02")) return;

        // Lowering the torso correctly must not drive the long neck/skull under
        // the floor. Bend the actual two neck joints to retain an accessible head;
        // targets are read only after this deformation, so no invisible weakpoint.
        Vector3 target = head.position;
        float minimumHeight = transform.position.y + 1.65f;
        if (target.y >= minimumHeight) return;
        target.y = minimumHeight;
        Quaternion headOrientation = head.rotation;
        for (int pass = 0; pass < 6; pass++)
        {
            LiftNeckJoint(named["neck_02"], target);
            LiftNeckJoint(named["neck_01"], target);
        }
        head.rotation = headOrientation;
    }

    void LiftNeckJoint(Transform joint, Vector3 target)
    {
        Vector3 current = head.position - joint.position;
        Vector3 desired = target - joint.position;
        if (current.sqrMagnitude < .001f || desired.sqrMagnitude < .001f) return;
        Quaternion adjustment = Quaternion.FromToRotation(current, desired);
        adjustment = Quaternion.RotateTowards(Quaternion.identity, adjustment, 8);
        joint.rotation = adjustment * joint.rotation;
    }

    static void MapAttack(string move, DragonBoss.CombatState state, float p, out string clip, out float time)
    {
        // Boundaries reference the authored contact poses, not whole-clip playback.
        // Windup ends at anticipation, Active ends at contact/sweep completion,
        // and Recovery consumes the authored release and return-to-rest frames.
        float anticipation, impact, end;
        switch (move)
        {
            // Stomp damage starts immediately in Active, so its contact frame must
            // already be reached at that boundary (the drop finishes the windup).
            case "Stomp": clip = "Stomp"; anticipation = 43; impact = 55; end = 80; break;
            case "Breath": clip = "Breath"; anticipation = 43; impact = 105; end = 130; break;
            case "Tail": clip = "Tail_Sweep"; anticipation = 39; impact = 53; end = 100; break;
            case "Bite": clip = "Bite"; anticipation = 24; impact = 43; end = 72; break;
            // Lunge currently reuses the authored bite's gathering/extension; root
            // translation is entirely controlled by the boss. No nonexistent clip.
            case "Lunge": clip = "Bite"; anticipation = 24; impact = 43; end = 72; break;
            default: clip = "Idle"; anticipation = 1; impact = 1; end = 91; break;
        }
        if (state == DragonBoss.CombatState.Windup) time = Frame(Mathf.Lerp(1, anticipation, p));
        else if (state == DragonBoss.CombatState.Active) time = Frame(Mathf.Lerp(anticipation, impact, p));
        else time = Frame(Mathf.Lerp(impact, end, p));
    }

    void RetargetStomp(int selected)
    {
        int source = Array.IndexOf(mappedLegIds, "fore_L");
        if (source < 0 || source == selected) return;
        Quaternion upDelta = Quaternion.Inverse(restUpper[source]) * upper[source].localRotation;
        Quaternion lowDelta = Quaternion.Inverse(restLower[source]) * lower[source].localRotation;
        upper[source].localRotation = restUpper[source]; lower[source].localRotation = restLower[source];
        upper[selected].localRotation = restUpper[selected] * upDelta;
        lower[selected].localRotation = restLower[selected] * lowDelta;
    }

    void ConfigureMaterials()
    {
        var shader = Shader.Find("Standard");
        if (!shader) return;
        var replacements = new Dictionary<Material, Material>();
        foreach (var renderer in modelRoot.GetComponentsInChildren<Renderer>(true))
        {
            var materials = renderer.sharedMaterials;
            for (int i = 0; i < materials.Length; i++)
            {
                if (!materials[i]) continue;
                Material replacement;
                if (!replacements.TryGetValue(materials[i], out replacement))
                {
                    string name = materials[i].name.ToLowerInvariant();
                    Color color = new Color(.075f, .095f, .105f);
                    float metallic = .12f, smoothness = .3f, glow = 0;
                    if (name.Contains("obsidian")) { color = new Color(.15f, .20f, .22f); metallic = .3f; smoothness = .6f; }
                    else if (name.Contains("horn")) color = new Color(.43f, .40f, .30f);
                    else if (name.Contains("membrane")) { color = new Color(.24f, .12f, .075f); smoothness = .15f; }
                    else if (name.Contains("fissure")) { color = new Color(1, .19f, .025f); glow = 2; }
                    else if (name.Contains("eyes")) { color = new Color(1, .63f, .08f); glow = 4; }
                    replacement = new Material(shader) { name = "TEMP authored " + materials[i].name, color = color };
                    replacement.SetFloat("_Metallic", metallic); replacement.SetFloat("_Glossiness", smoothness);
                    if (glow > 0) { replacement.EnableKeyword("_EMISSION"); replacement.SetColor("_EmissionColor", color * glow); }
                    replacements.Add(materials[i], replacement); ownedMaterials.Add(replacement);
                }
                materials[i] = replacement;
            }
            renderer.sharedMaterials = materials;
        }
    }

    void OnDestroy()
    {
        foreach (var material in ownedMaterials) if (material) Destroy(material);
    }
}
