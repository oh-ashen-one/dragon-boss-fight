using System;
using System.Collections.Generic;
using UnityEditor;
using UnityEngine;

/// <summary>Deterministic non-humanoid import of the explicitly temporary authored rig.</summary>
public sealed class VeyrModelImporter : AssetPostprocessor
{
    const string ModelPath = "Assets/Resources/Art/Veyr_TEMP_Rig.fbx";
    static readonly HashSet<string> Loops = new HashSet<string> { "Idle", "Walk", "Stagger_Loop" };
    bool IsVeyr { get { return string.Equals(assetPath, ModelPath, StringComparison.Ordinal); } }

    void OnPreprocessModel()
    {
        if (!IsVeyr) return;
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
    }

    void OnPreprocessAnimation()
    {
        if (!IsVeyr) return;
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
        if (!IsVeyr) return;
        foreach (var animation in model.GetComponentsInChildren<Animation>(true))
        {
            animation.playAutomatically = false;
            animation.cullingType = AnimationCullingType.AlwaysAnimate;
        }
        foreach (var renderer in model.GetComponentsInChildren<SkinnedMeshRenderer>(true))
            renderer.updateWhenOffscreen = true;
        Debug.Log("VEYR_AUTHORED_MODEL_IMPORTED temporary rig; direct phase sampling; retained bone hierarchy.");
    }
}
