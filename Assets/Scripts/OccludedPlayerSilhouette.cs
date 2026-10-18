using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Rendering;

/// <summary>
/// Camera-local, depth-correct knight readability through the boss only. No
/// duplicate visual objects, collider approximations, or model-layer changes.
/// DrawRenderer follows both ordinary and skinned player animation directly.
/// </summary>
[RequireComponent(typeof(Camera))]
public sealed class OccludedPlayerSilhouette : MonoBehaviour
{
    public PlayerCombat Player;
    public DragonBoss Boss;
    public int PlayerSubmeshesDrawn { get; private set; }
    public int BossSubmeshesMarked { get; private set; }
    const CameraEvent Event = CameraEvent.BeforeImageEffects;
    Camera view;
    Material material;
    CommandBuffer commands;
    float nextDiscovery;
    PlayerCombat cachedPlayer;
    DragonBoss cachedBoss;
    readonly List<DrawPart> playerParts = new List<DrawPart>();
    readonly List<DrawPart> bossParts = new List<DrawPart>();
    struct DrawPart { public Renderer renderer; public int submesh; }

    void OnEnable()
    {
        view = GetComponent<Camera>();
        nextDiscovery = 0;
        // Resource ownership explicitly retains the shader in standalone builds.
        Shader shader = Resources.Load<Shader>("Shaders/OccludedKnight");
        if (!shader || !shader.isSupported)
        { Debug.LogWarning("VEYR_SILHOUETTE_UNAVAILABLE: retained shader missing or unsupported."); return; }
        material = new Material(shader) { name = "Amber knight through boss occlusion" };
        material.SetColor("_Amber", new Color(1, .59f, .18f, 1));
        commands = new CommandBuffer { name = "Boss-only occluded knight silhouette" };
        view.AddCommandBuffer(Event, commands);
        Debug.Log("VEYR_SILHOUETTE_READY: depth/stencil boss-only mesh and skinned support.");
    }

    void OnPreCull()
    {
        if (commands == null) return;
        commands.Clear();
        PlayerSubmeshesDrawn = BossSubmeshesMarked = 0;
        if (!Player || !Boss || !material) return;
        commands.SetRenderTarget(BuiltinRenderTextureType.CameraTarget);
        if (cachedPlayer != Player || cachedBoss != Boss || Time.unscaledTime >= nextDiscovery)
        {
            cachedPlayer = Player; cachedBoss = Boss;
            nextDiscovery = Time.unscaledTime + .7f;
            Discover(Player.transform, playerParts);
            Discover(Boss.transform, bossParts);
        }
        // Pass 0 writes only stencil bit zero, only where the boss matches the
        // existing visible scene depth. A wall in front of the boss cannot mark.
        foreach (var part in bossParts)
            if (Visible(part.renderer))
            { commands.DrawRenderer(part.renderer, material, part.submesh, 0); BossSubmeshesMarked++; }
        if (BossSubmeshesMarked == 0) return;
        // Pass 1 additionally requires the player fragment to be behind scene
        // depth. Visible limbs retain their real materials without any overlay.
        foreach (var part in playerParts)
            if (Visible(part.renderer))
            { commands.DrawRenderer(part.renderer, material, part.submesh, 1); PlayerSubmeshesDrawn++; }
        // Immediately release our stencil bit before camera image effects.
        foreach (var part in bossParts)
            if (Visible(part.renderer)) commands.DrawRenderer(part.renderer, material, part.submesh, 2);
    }

    bool Visible(Renderer renderer)
    {
        return renderer && renderer.enabled && renderer.gameObject.activeInHierarchy && !renderer.forceRenderingOff &&
            (view.cullingMask & (1 << renderer.gameObject.layer)) != 0;
    }

    static void Discover(Transform root, List<DrawPart> parts)
    {
        parts.Clear();
        foreach (var renderer in root.GetComponentsInChildren<Renderer>(true))
        {
            Mesh mesh = null;
            if (renderer is SkinnedMeshRenderer skin) mesh = skin.sharedMesh;
            else if (renderer is MeshRenderer)
            { var filter = renderer.GetComponent<MeshFilter>(); if (filter) mesh = filter.sharedMesh; }
            if (!mesh) continue; // particles and sword trails are never silhouettes
            var materials = renderer.sharedMaterials;
            int count = Mathf.Min(mesh.subMeshCount, materials.Length);
            for (int i = 0; i < count; i++)
                if (materials[i] && materials[i].renderQueue <= 2500)
                    parts.Add(new DrawPart { renderer = renderer, submesh = i });
        }
    }

    void OnDisable()
    {
        if (view && commands != null) view.RemoveCommandBuffer(Event, commands);
        if (commands != null) { commands.Release(); commands = null; }
        if (material) Destroy(material);
        material = null;
        playerParts.Clear(); bossParts.Clear();
    }
}
