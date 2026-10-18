using System;
using System.Collections.Generic;
using UnityEngine;

/// <summary>
/// Presentation only for the original TEMP knight. Combat clocks and decisions
/// remain in PlayerCombat. Approved Tripo geometry is still required for final art.
/// </summary>
public sealed class AuthoredKnightVisual : MonoBehaviour
{
    const string ResourcePath = "Art/Knight_TEMP_Rig";
    static readonly string[] RequiredClips = { "Idle", "Locomotion", "Slash_A", "Slash_B", "Dodge", "Heal", "Hit", "Death" };
    static readonly string[] RequiredBones = { "root", "pelvis", "chest", "head", "sword", "flask", "hand_R", "hand_L",
        "thigh_L", "thigh_R", "shin_L", "shin_R", "foot_L", "foot_R", "toe_L", "toe_R" };
    readonly Dictionary<string, AnimationClip> clips = new Dictionary<string, AnimationClip>(StringComparer.Ordinal);
    readonly Dictionary<string, Transform> bones = new Dictionary<string, Transform>(StringComparer.Ordinal);
    readonly List<Material> ownedMaterials = new List<Material>();
    PlayerCombat player;
    Transform fit, modelRoot, swordTip;
    TrailRenderer swordTrail;
    Transform[] sampledTransforms;
    Vector3[] transitionPositions, transitionScales;
    Quaternion[] transitionRotations;
    string previousClip;
    float transitionElapsed, locomotionPhase;
    int previousSwing = -1;
    bool warnedDirectionalMotion;
    public bool IsReady { get; private set; }
    public string CurrentClipName { get; private set; }
    public float CurrentClipTime { get; private set; }
    public Vector3 SwordTipPosition { get { return swordTip ? swordTip.position : transform.position; } }

    public bool Initialize(PlayerCombat owner)
    {
        if (IsReady) return true;
        player = owner;
        try { return LoadAndValidate(); }
        catch (Exception exception)
        {
            return Fail("Initialization exception " + exception.GetType().Name + ": " + exception.Message);
        }
    }

    bool LoadAndValidate()
    {
        var prefab = Resources.Load<GameObject>(ResourcePath);
        if (!prefab) return Fail("FBX resource missing; primitive knight remains active.");
        foreach (var clip in Resources.LoadAll<AnimationClip>(ResourcePath))
        {
            if (clip.name.StartsWith("__preview__", StringComparison.Ordinal)) continue;
            clips[clip.name.Substring(clip.name.LastIndexOf('|') + 1)] = clip;
        }
        foreach (var name in RequiredClips)
            if (!clips.ContainsKey(name) || clips[name].length < .01f)
                return Fail("Required clip missing or empty: " + name);
        foreach (var name in RequiredClips)
            Debug.Log("KNIGHT_CLIP_RUNTIME name=" + name + " length=" + clips[name].length.ToString("F6") +
                " frameRate=" + clips[name].frameRate.ToString("F3"));
        // Only floating-point tolerance is allowed: do not accept a missing baked
        // frame by shortening the authoritative attack/dodge/heal presentation.
        if (clips["Slash_A"].length < .6499f || clips["Slash_B"].length < .6499f || clips["Dodge"].length < .5799f || clips["Heal"].length < 1.2499f)
            return Fail("Imported clip lengths do not cover the authoritative combat windows. Slash_A=" + clips["Slash_A"].length.ToString("F6") +
                " Slash_B=" + clips["Slash_B"].length.ToString("F6") + " Dodge=" + clips["Dodge"].length.ToString("F6") + " Heal=" + clips["Heal"].length.ToString("F6"));

        fit = new GameObject("TEMP authored knight — approved Tripo replacement pending").transform;
        fit.SetParent(transform, false);
        modelRoot = Instantiate(prefab, fit, false).transform;
        modelRoot.name = "TEMP_Knight_BlendSource";
        foreach (var animation in modelRoot.GetComponentsInChildren<Animation>(true))
        { animation.Stop(); animation.playAutomatically = false; animation.enabled = false; }
        foreach (var animator in modelRoot.GetComponentsInChildren<Animator>(true)) animator.enabled = false;
        foreach (var bone in modelRoot.GetComponentsInChildren<Transform>(true)) bones[bone.name] = bone;
        foreach (var name in RequiredBones) if (!bones.ContainsKey(name)) return Fail("Required bone missing: " + name);
        var skins = modelRoot.GetComponentsInChildren<SkinnedMeshRenderer>(true);
        if (skins.Length == 0) return Fail("No skinned mesh renderer.");
        foreach (var skin in skins) skin.updateWhenOffscreen = true;

        clips["Idle"].SampleAnimation(modelRoot.gameObject, 0);
        Vector3 restSword = bones["sword"].position;
        Quaternion restRotation = bones["sword"].rotation;
        clips["Slash_A"].SampleAnimation(modelRoot.gameObject, .23f);
        if (Vector3.Distance(bones["sword"].position, restSword) < .01f && Quaternion.Angle(bones["sword"].rotation, restRotation) < 3)
            return Fail("Clip sampling did not move the sword. Check FBX take bindings.");
        clips["Idle"].SampleAnimation(modelRoot.gameObject, 0);

        // Toe/ankle positions are reliable under either FBX bone-axis convention.
        Vector3 forward = (bones["toe_L"].position - bones["foot_L"].position) +
                          (bones["toe_R"].position - bones["foot_R"].position);
        forward = fit.InverseTransformVector(forward); forward.y = 0;
        if (forward.sqrMagnitude < .0001f) return Fail("Cannot derive rest-pose facing from feet.");
        Vector3 headDelta = fit.InverseTransformVector(bones["head"].position - bones["root"].position);
        Quaternion unconstrained = Quaternion.FromToRotation(forward.normalized, Vector3.forward);
        Quaternion yawOnly = Quaternion.AngleAxis(Vector3.SignedAngle(forward.normalized, Vector3.forward, Vector3.up), Vector3.up);
        Debug.Log("KNIGHT_ORIENTATION_DIAGNOSTIC sourceForward=" + forward.ToString("F5") + " restHeadDelta=" + headDelta.ToString("F5") +
            " unconstrainedHeadY=" + (unconstrained * headDelta).y.ToString("F5") + " yawOnlyHeadY=" + (yawOnly * headDelta).y.ToString("F5"));
        // Opposite planar forward vectors leave FromToRotation free to choose a
        // pitch/roll axis. Constrain this fitting correction to yaw so up survives.
        fit.localRotation = yawOnly;
        float headHeight = bones["head"].position.y - bones["root"].position.y;
        Debug.Log("KNIGHT_ORIENTATION_APPLIED headHeight=" + headHeight.ToString("F5") + " fitUp=" + fit.up.ToString("F5"));
        if (headHeight < .001f || headHeight > 500) return Fail("Unexpected standing skeleton height/axis: " + headHeight.ToString("F5"));
        // Source head pivot is 1.68m and helmet top 1.96m; fit inside the 1.9m controller.
        fit.localScale = Vector3.one * (1.90f / (headHeight * (1.96f / 1.68f)));
        Vector3 localTip;
        if (!FindWeightedSwordTip(skins, out localTip))
            return Fail("Cannot bind trail to actual sword vertices; check readable mesh and sword weights.");
        if (!ConfigureMaterials()) return Fail("Standard shader unavailable.");
        swordTip = new GameObject("TEMP actual authored blade tip").transform;
        swordTip.SetParent(bones["sword"], false); swordTip.localPosition = localTip;
        swordTrail = swordTip.gameObject.AddComponent<TrailRenderer>();
        swordTrail.time = .16f; swordTrail.startWidth = .13f; swordTrail.endWidth = 0;
        swordTrail.minVertexDistance = .025f; swordTrail.emitting = false;
        var trailShader = Shader.Find("Sprites/Default");
        if (!trailShader) return Fail("Trail shader unavailable.");
        var trailMaterial = new Material(trailShader) { name = "TEMP authored blade trail" };
        ownedMaterials.Add(trailMaterial); swordTrail.sharedMaterial = trailMaterial;
        swordTrail.startColor = new Color(1, .78f, .45f, .75f); swordTrail.endColor = new Color(1, .42f, .1f, 0);
        sampledTransforms = modelRoot.GetComponentsInChildren<Transform>(true);
        transitionPositions = new Vector3[sampledTransforms.Length];
        transitionRotations = new Quaternion[sampledTransforms.Length];
        transitionScales = new Vector3[sampledTransforms.Length];
        IsReady = true;
        EvaluatePose(0);
        if (player.TemporaryVisual) player.TemporaryVisual.gameObject.SetActive(false);
        Debug.Log("KNIGHT_AUTHORED_VISUAL_READY temporary art; clips=8; real weighted blade tip; heightFit=1.9m; contact=0.23s; dodge=0.58s; heal=1.25s");
        return true;
    }

    bool FindWeightedSwordTip(SkinnedMeshRenderer[] skins, out Vector3 localTip)
    {
        localTip = Vector3.zero;
        var sword = bones["sword"];
        var candidates = new List<Vector3>();
        float farthest = 0;
        foreach (var skin in skins)
        {
            var mesh = skin.sharedMesh;
            if (!mesh || !mesh.isReadable) continue;
            int boneIndex = Array.IndexOf(skin.bones, sword);
            if (boneIndex < 0) continue;
            var vertices = mesh.vertices;
            var weights = mesh.boneWeights;
            var bindposes = mesh.bindposes;
            if (weights.Length != vertices.Length || boneIndex >= bindposes.Length) continue;
            // Bindpose transforms mesh coordinates directly into bone-local space;
            // this remains correct after outer fitting and rest-pose sampling.
            for (int i = 0; i < vertices.Length; i++)
            {
                var w = weights[i];
                float weight = (w.boneIndex0 == boneIndex ? w.weight0 : 0) + (w.boneIndex1 == boneIndex ? w.weight1 : 0) +
                               (w.boneIndex2 == boneIndex ? w.weight2 : 0) + (w.boneIndex3 == boneIndex ? w.weight3 : 0);
                if (weight < .9f) continue;
                Vector3 point = bindposes[boneIndex].MultiplyPoint3x4(vertices[i]);
                candidates.Add(point); farthest = Mathf.Max(farthest, point.magnitude);
            }
        }
        if (candidates.Count < 4 || farthest < .01f) return false;
        int count = 0;
        foreach (var point in candidates)
            if (point.magnitude >= farthest * .985f) { localTip += point; count++; }
        if (count == 0) return false;
        localTip /= count;
        float worldLength = sword.TransformVector(localTip).magnitude;
        Debug.Log("KNIGHT_BLADE_BIND vertices=" + candidates.Count + " worldLength=" + worldLength.ToString("F3"));
        return worldLength > .75f && worldLength < 1.8f;
    }

    public void EvaluatePose(float dt)
    {
        if (!IsReady || !player) return;
        try { SamplePose(Mathf.Max(0, dt)); }
        catch (Exception exception) { Fail("Sampling exception " + exception.GetType().Name + ": " + exception.Message); }
    }

    void SamplePose(float dt)
    {
        bool victory = player.Boss && player.Boss.IsDead;
        Vector3 velocity = player.PlanarVelocity;
        Vector3 localVelocity = transform.InverseTransformDirection(velocity);
        string clipName;
        float time;
        if (player.IsDead) { clipName = "Death"; time = player.DeathElapsed; }
        else if (victory) { clipName = "Idle"; time = Mathf.Repeat(player.VisualClock, clips["Idle"].length); }
        else if (player.DodgeElapsed >= 0) { clipName = "Dodge"; time = player.DodgeElapsed; }
        else if (player.AttackElapsed >= 0) { clipName = player.Swings % 2 == 1 ? "Slash_A" : "Slash_B"; time = player.AttackElapsed; }
        else if (player.HealElapsed >= 0) { clipName = "Heal"; time = player.HealElapsed; }
        // A hit never replaces the visible active sword/dodge timing. Healing is
        // already cancelled by gameplay; only otherwise-free movement recoils.
        else if (player.HurtRemaining > 0) { clipName = "Hit"; time = .65f - player.HurtRemaining; }
        else if (velocity.magnitude > .12f)
        {
            clipName = "Locomotion";
            locomotionPhase += dt * velocity.magnitude / 5.8f * (localVelocity.z < -.1f ? -1 : 1);
            time = Mathf.Repeat(locomotionPhase, clips["Locomotion"].length);
        }
        else { clipName = "Idle"; time = Mathf.Repeat(player.VisualClock, clips["Idle"].length); }

        bool changed = previousClip != clipName || (clipName.StartsWith("Slash", StringComparison.Ordinal) && previousSwing != player.Swings);
        if (changed)
        {
            transitionElapsed = 0;
            for (int i = 0; i < sampledTransforms.Length; i++)
            {
                transitionPositions[i] = sampledTransforms[i].localPosition;
                transitionRotations[i] = sampledTransforms[i].localRotation;
                transitionScales[i] = sampledTransforms[i].localScale;
            }
            if (swordTrail) { swordTrail.emitting = false; swordTrail.Clear(); }
        }
        else transitionElapsed += dt;
        CurrentClipName = clipName; CurrentClipTime = Mathf.Clamp(time, 0, clips[clipName].length);
        clips[clipName].SampleAnimation(modelRoot.gameObject, CurrentClipTime);

        if (clipName == "Locomotion" && localVelocity.sqrMagnitude > .02f)
        {
            Vector3 direction = localVelocity.z < -.1f ? -localVelocity : localVelocity;
            float yaw = Mathf.Clamp(Mathf.Atan2(direction.x, direction.z) * Mathf.Rad2Deg, -80, 80);
            // Turn the planted legs into travel while retaining the chest's combat
            // facing. Backward travel reverses the gait; dedicated directional art
            // remains a refinement, not a claim that this is a final strafe set.
            Quaternion chestRotation = bones["chest"].rotation;
            bones["pelvis"].rotation = Quaternion.AngleAxis(yaw, Vector3.up) * bones["pelvis"].rotation;
            bones["chest"].rotation = chestRotation;
            if (!warnedDirectionalMotion && Mathf.Abs(yaw) > 35)
            { warnedDirectionalMotion = true; Debug.Log("KNIGHT_TEMP_DIRECTIONAL_GAIT active: anatomical yaw adaptation; dedicated strafe clips pending."); }
        }
        float blendLength = clipName == "Dodge" ? .045f : clipName == "Death" ? .12f : .08f;
        float alpha = Mathf.Clamp01(transitionElapsed / blendLength);
        if (previousClip != null && alpha < 1)
            for (int i = 0; i < sampledTransforms.Length; i++)
            {
                var t = sampledTransforms[i];
                t.localPosition = Vector3.Lerp(transitionPositions[i], t.localPosition, alpha);
                t.localRotation = Quaternion.Slerp(transitionRotations[i], t.localRotation, alpha);
                t.localScale = Vector3.Lerp(transitionScales[i], t.localScale, alpha);
            }
        swordTrail.emitting = !player.IsDead && !victory && player.AttackElapsed > .17f && player.AttackElapsed < .39f;
        previousClip = clipName; previousSwing = player.Swings;
    }

    bool ConfigureMaterials()
    {
        var shader = Shader.Find("Standard");
        if (!shader) return false;
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
                    Color color = new Color(.22f, .28f, .31f);
                    float metal = .8f, smooth = .66f, glow = 0;
                    if (name.Contains("silver")) { color = new Color(.55f, .60f, .61f); metal = .85f; smooth = .7f; }
                    else if (name.Contains("cloth")) { color = new Color(.045f, .052f, .055f); metal = 0; smooth = .06f; }
                    else if (name.Contains("leather")) { color = new Color(.12f, .045f, .027f); metal = 0; smooth = .23f; }
                    else if (name.Contains("brass")) { color = new Color(.42f, .28f, .09f); metal = .7f; smooth = .56f; }
                    else if (name.Contains("flask")) { color = new Color(.64f, .18f, .03f); metal = .1f; glow = .7f; }
                    replacement = new Material(shader) { name = "TEMP authored " + materials[i].name, color = color };
                    replacement.SetFloat("_Metallic", metal); replacement.SetFloat("_Glossiness", smooth);
                    if (glow > 0) { replacement.EnableKeyword("_EMISSION"); replacement.SetColor("_EmissionColor", color * glow); }
                    replacements.Add(materials[i], replacement); ownedMaterials.Add(replacement);
                }
                materials[i] = replacement;
            }
            renderer.sharedMaterials = materials;
        }
        return true;
    }

    bool Fail(string reason)
    {
        IsReady = false;
        if (swordTrail) { swordTrail.emitting = false; swordTrail.Clear(); }
        if (fit) { fit.gameObject.SetActive(false); Destroy(fit.gameObject); }
        if (player && player.TemporaryVisual)
        { player.TemporaryVisual.localRotation = Quaternion.identity; player.TemporaryVisual.gameObject.SetActive(true); }
        Debug.LogWarning("KNIGHT_AUTHORED_VISUAL_FALLBACK " + reason);
        return false;
    }

    void OnDestroy()
    {
        foreach (var material in ownedMaterials) if (material) Destroy(material);
    }
}
