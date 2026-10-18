using System;
using System.Collections.Generic;
using UnityEditor;
using UnityEngine;

/// <summary>Deterministic non-humanoid import of the explicitly temporary authored rig.</summary>
public sealed class VeyrModelImporter : AssetPostprocessor
{
    const string ModelPath = "Assets/Resources/Art/Veyr_TEMP_Rig.fbx";
    const string KnightPath = "Assets/Resources/Art/Knight_TEMP_Rig.fbx";
    static readonly HashSet<string> Loops = new HashSet<string> { "Idle", "Walk", "Stagger_Loop", "Locomotion" };
    bool IsVeyr { get { return string.Equals(assetPath, ModelPath, StringComparison.Ordinal); } }
    bool IsKnight { get { return string.Equals(assetPath, KnightPath, StringComparison.Ordinal); } }
    bool IsAuthoredRig { get { return IsVeyr || IsKnight; } }

    /// <summary>Read-only batch diagnosis; does not build or mutate clip data.</summary>
    public static void InspectKnightClips()
    {
        int count = 0;
        foreach (var asset in AssetDatabase.LoadAllAssetsAtPath(KnightPath))
        {
            var clip = asset as AnimationClip;
            if (!clip || clip.name.StartsWith("__preview__", StringComparison.Ordinal)) continue;
            count++;
            Debug.Log("KNIGHT_CLIP_INSPECT name=" + clip.name + " length=" + clip.length.ToString("F6") +
                " frameRate=" + clip.frameRate.ToString("F3") + " legacy=" + clip.legacy);
        }
        Debug.Log("KNIGHT_CLIP_INSPECT_COUNT " + count);
        if (count == 0) throw new InvalidOperationException("Knight FBX contains no imported animation clips.");
    }

    /// <summary>Inspect real imported anatomy and compare unconstrained/yaw-only fit.</summary>
    public static void InspectKnightRig()
    {
        InspectKnightClips();
        var prefab = AssetDatabase.LoadAssetAtPath<GameObject>(KnightPath);
        if (!prefab) throw new InvalidOperationException("Knight prefab unavailable.");
        var wrapper = new GameObject("Knight read-only import inspection") { hideFlags = HideFlags.HideAndDontSave };
        try
        {
            var model = UnityEngine.Object.Instantiate(prefab, wrapper.transform, false);
            foreach (var animation in model.GetComponentsInChildren<Animation>(true))
            { animation.Stop(); animation.playAutomatically = false; animation.enabled = false; }
            foreach (var animator in model.GetComponentsInChildren<Animator>(true)) animator.enabled = false;
            AnimationClip idle = null;
            foreach (var asset in AssetDatabase.LoadAllAssetsAtPath(KnightPath))
            {
                var clip = asset as AnimationClip;
                if (clip && clip.name.Substring(clip.name.LastIndexOf('|') + 1) == "Idle") idle = clip;
            }
            if (!idle) throw new InvalidOperationException("Idle clip unavailable for anatomy inspection.");
            idle.SampleAnimation(model, 0);
            var bones = new Dictionary<string, Transform>(StringComparer.Ordinal);
            foreach (var t in model.GetComponentsInChildren<Transform>(true)) bones[t.name] = t;
            foreach (var name in new[] { "root", "head", "pelvis", "chest", "foot_L", "foot_R", "toe_L", "toe_R", "sword" })
            {
                Transform bone;
                if (!bones.TryGetValue(name, out bone)) throw new InvalidOperationException("Missing inspection bone: " + name);
                Debug.Log("KNIGHT_BONE_INSPECT name=" + name + " world=" + bone.position.ToString("F5") +
                    " local=" + bone.localPosition.ToString("F5") + " localEuler=" + bone.localEulerAngles.ToString("F3") +
                    " localScale=" + bone.localScale.ToString("F5") + " up=" + bone.up.ToString("F5") + " parent=" + (bone.parent ? bone.parent.name : "none"));
            }
            foreach (var parent in new[] { model.transform, bones["root"].parent })
                if (parent) Debug.Log("KNIGHT_PREFAB_AXES name=" + parent.name + " position=" + parent.position.ToString("F5") +
                    " forward=" + parent.forward.ToString("F5") + " up=" + parent.up.ToString("F5") + " scale=" + parent.lossyScale.ToString("F5"));
            foreach (var skin in model.GetComponentsInChildren<SkinnedMeshRenderer>(true))
                Debug.Log("KNIGHT_MESH_INSPECT name=" + skin.name + " worldCenter=" + skin.bounds.center.ToString("F5") +
                    " worldSize=" + skin.bounds.size.ToString("F5") + " localCenter=" + skin.localBounds.center.ToString("F5") +
                    " localSize=" + skin.localBounds.size.ToString("F5") + " readable=" + (skin.sharedMesh && skin.sharedMesh.isReadable));
            Vector3 forward = (bones["toe_L"].position - bones["foot_L"].position) + (bones["toe_R"].position - bones["foot_R"].position);
            forward.y = 0;
            if (forward.sqrMagnitude < .0001f) throw new InvalidOperationException("Foot forward vector is degenerate.");
            float before = bones["head"].position.y - bones["root"].position.y;
            wrapper.transform.localRotation = Quaternion.FromToRotation(forward.normalized, Vector3.forward);
            float unconstrained = bones["head"].position.y - bones["root"].position.y;
            wrapper.transform.localRotation = Quaternion.AngleAxis(Vector3.SignedAngle(forward.normalized, Vector3.forward, Vector3.up), Vector3.up);
            float yawOnly = bones["head"].position.y - bones["root"].position.y;
            Debug.Log("KNIGHT_FIT_COMPARISON sourceForward=" + forward.ToString("F5") + " beforeHeadY=" + before.ToString("F5") +
                " unconstrainedHeadY=" + unconstrained.ToString("F5") + " yawOnlyHeadY=" + yawOnly.ToString("F5") + " yawFitUp=" + wrapper.transform.up.ToString("F5"));
            if (yawOnly < .001f || wrapper.transform.up.y < .999f)
                throw new InvalidOperationException("Yaw-only fit did not preserve upright anatomy; inspect source asset.");
        }
        finally { UnityEngine.Object.DestroyImmediate(wrapper); }
    }

    void OnPreprocessModel()
    {
        if (!IsAuthoredRig) return;
        var model = (ModelImporter)assetImporter;
        // Legacy is intentional: direct sampling makes the combat clock authoritative
        // and preserves all 28 authored transforms without an Animator controller.
        model.animationType = ModelImporterAnimationType.Legacy;
        model.importAnimation = true;
        model.animationCompression = ModelImporterAnimationCompression.Off;
        model.resampleCurves = true;
        model.optimizeGameObjects = false;
        model.bakeAxisConversion = true;
        model.globalScale = 1;
        model.useFileScale = true;
        model.importCameras = false;
        model.importLights = false;
        model.materialImportMode = ModelImporterMaterialImportMode.ImportStandard;
        // One small read-only scan derives the blade tip from actual sword-weighted
        // mesh vertices. This avoids guessing Blender/FBX bone-local axes.
        if (IsKnight) model.isReadable = true;
    }

    void OnPreprocessAnimation()
    {
        if (!IsAuthoredRig) return;
        var model = (ModelImporter)assetImporter;
        var clips = model.defaultClipAnimations;
        foreach (var clip in clips)
        {
            // Keep takeName untouched: it identifies the actual FBX action.
            int separator = clip.name.LastIndexOf('|');
            if (separator >= 0) clip.name = clip.name.Substring(separator + 1);
            clip.loopTime = Loops.Contains(clip.name);
            clip.loopPose = false;
            clip.wrapMode = clip.loopTime ? WrapMode.Loop : WrapMode.ClampForever;
        }
        model.clipAnimations = clips;
    }

    void OnPostprocessModel(GameObject model)
    {
        if (!IsAuthoredRig) return;
        foreach (var animation in model.GetComponentsInChildren<Animation>(true))
        {
            animation.playAutomatically = false;
            animation.cullingType = AnimationCullingType.AlwaysAnimate;
        }
        foreach (var renderer in model.GetComponentsInChildren<SkinnedMeshRenderer>(true))
            renderer.updateWhenOffscreen = true;
        Debug.Log((IsKnight ? "KNIGHT" : "VEYR") + "_AUTHORED_MODEL_IMPORTED temporary rig; direct phase sampling; retained bone hierarchy.");
    }
}
