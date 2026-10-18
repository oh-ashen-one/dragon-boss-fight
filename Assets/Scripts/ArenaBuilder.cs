using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Rendering;

/// <summary>
/// Original procedural environment: the Drowned Reliquary. All meshes and materials
/// in this file are authored for this project. This is environment art, not a
/// substitute for the main dragon model. The entire combat floor remains clear.
/// </summary>
public sealed class ArenaBuilder : MonoBehaviour
{
    public static void Build()
    {
        if (GameObject.Find("Drowned Reliquary — original procedural environment")) return;
        new Reliquary().Build();
    }

    sealed class Reliquary
    {
        readonly System.Random random = new System.Random(3187);
        readonly List<Geometry> batches = new List<Geometry>();
        Transform root;
        Geometry stone, paleStone, floorStone, floorLight, darkStone, rubble, bronze, inlay, water;
        Material flame, ember;
        Texture2D basaltAlbedo, basaltNormal, basaltWetness;
        Texture2D masonryAlbedo, masonryNormal, masonryWetness;
        static Texture2D cachedBasaltAlbedo, cachedBasaltNormal, cachedBasaltWetness;
        static Texture2D cachedMasonryAlbedo, cachedMasonryNormal, cachedMasonryWetness;
        static Cubemap cachedStormSky;
        float Rand(float a, float b) { return a + (float)random.NextDouble() * (b - a); }
        static Vector3 Radial(float angle, float radius, float y = 0)
        {
            return new Vector3(Mathf.Sin(angle) * radius, y, Mathf.Cos(angle) * radius);
        }

        Geometry Batch(string name, Color color, float smoothness, float metallic = 0)
        {
            var material = new Material(Shader.Find("Standard"));
            material.name = name + " — original procedural material";
            material.color = color;
            material.SetFloat("_Glossiness", smoothness);
            material.SetFloat("_Metallic", metallic);
            if (basaltAlbedo && metallic < .3f && name != "Black reflecting moat")
            {
                bool masonry = name.Contains("cathedral");
                material.SetTexture("_MainTex", masonry ? masonryAlbedo : basaltAlbedo);
                material.SetTexture("_BumpMap", masonry ? masonryNormal : basaltNormal);
                material.SetFloat("_BumpScale", masonry ? .40f : .35f);
                material.EnableKeyword("_NORMALMAP");
                material.SetTexture("_MetallicGlossMap", masonry ? masonryWetness : basaltWetness);
                material.SetFloat("_GlossMapScale", .9f);
                material.EnableKeyword("_METALLICGLOSSMAP");
            }
            var geometry = new Geometry(name, material);
            batches.Add(geometry);
            return geometry;
        }

        public void Build()
        {
            root = new GameObject("Drowned Reliquary — original procedural environment").transform;
            CreateBasaltTextures();
            CreateMasonryTextures();
            stone = Batch("Rain-dark cathedral ashlar", new Color(.29f, .295f, .29f), .48f, .04f);
            paleStone = Batch("Worn cathedral limestone", new Color(.37f, .365f, .345f), .42f, .04f);
            floorStone = Batch("Rain-polished flagstones", new Color(.235f, .255f, .265f), .72f, .04f);
            floorLight = Batch("Silver flagstone variation", new Color(.285f, .30f, .30f), .72f, .04f);
            darkStone = Batch("Obsidian recesses", new Color(.11f, .13f, .145f), .7f, .05f);
            rubble = Batch("Distant weathered masonry", new Color(.20f, .235f, .25f), .33f);
            bronze = Batch("Tarnished ancient bronze", new Color(.24f, .175f, .075f), .66f, .78f);
            inlay = Batch("Faded moonstone seams", new Color(.16f, .18f, .18f), .58f, .32f);
            water = Batch("Black reflecting moat", new Color(.018f, .032f, .041f), .88f, .18f);
            CreateFloor();
            CreateArchitecture();
            CreateSilhouette();
            CreateLighting();
            foreach (var batch in batches) batch.Finish(root);
            CreateParticles();
            CreateCollision();
        }

        // Original, seamless pixel maps: irregular stone plates, hairline cracks,
        // mineral speckling, pores and rain-polished high spots. World-scaled UVs
        // below keep their density consistent on pavers and monumental masonry.
        void CreateBasaltTextures()
        {
            if (cachedBasaltAlbedo && cachedBasaltNormal && cachedBasaltWetness)
            { basaltAlbedo = cachedBasaltAlbedo; basaltNormal = cachedBasaltNormal; basaltWetness = cachedBasaltWetness; return; }
            const int size = 512;
            float[] heights = new float[size * size];
            Color[] colors = new Color[heights.Length];
            Color[] wetness = new Color[heights.Length];
            for (int y = 0; y < size; y++)
                for (int x = 0; x < size; x++)
                {
                    float u = x / (float)size, v = y / (float)size;
                    float n = TileNoise(u, v, 8, 17.2f);
                    float grain = TileNoise(u, v, 57, 38.4f);
                    float fleck = TileNoise(u, v, 119, 91.7f);
                    float cx = u * 7, cy = v * 7;
                    int ix = Mathf.FloorToInt(cx), iy = Mathf.FloorToInt(cy);
                    float first = 100, second = 100, plate = 0;
                    for (int j = -1; j <= 1; j++)
                        for (int i = -1; i <= 1; i++)
                        {
                            int px = ix + i, py = iy + j;
                            int wx = (px + 7) % 7, wy = (py + 7) % 7;
                            float hx = Hash(wx, wy), hy = Hash(wx + 23, wy + 19);
                            float dx = px + .18f + hx * .64f - cx, dy = py + .18f + hy * .64f - cy;
                            float distance = dx * dx + dy * dy;
                            if (distance < first) { second = first; first = distance; plate = hx; }
                            else if (distance < second) second = distance;
                        }
                    float crack = 1 - Smooth01(0, .027f, second - first);
                    float vein = Mathf.Pow(1 - Mathf.Abs(n * 2 - 1), 18) * .014f;
                    float pit = Smooth01(.67f, .87f, fleck) * .045f;
                    int index = x + y * size;
                    heights[index] = .48f + (n - .5f) * .075f + (grain - .5f) * .035f + plate * .02f - crack * .075f - pit;
                    float tone = .59f + (n - .5f) * .09f + (grain - .5f) * .045f + plate * .035f - crack * .085f - pit + vein;
                    colors[index] = new Color(tone * .96f, tone, tone * 1.015f, 1);
                    float wet = Smooth01(.32f, .69f, TileNoise(u, v, 4, 72.1f));
                    wetness[index] = new Color(.025f, .025f, .025f, Mathf.Lerp(.48f, .89f, wet) * (1 - crack * .2f));
                }
            Color[] normals = new Color[heights.Length];
            for (int y = 0; y < size; y++)
                for (int x = 0; x < size; x++)
                {
                    float dx = heights[(x + 1) % size + y * size] - heights[(x + size - 1) % size + y * size];
                    float dy = heights[x + (y + 1) % size * size] - heights[x + (y + size - 1) % size * size];
                    Vector3 n = new Vector3(-dx * 5, -dy * 5, 1).normalized;
                    normals[x + y * size] = new Color(n.x * .5f + .5f, n.y * .5f + .5f, n.z * .5f + .5f, 1);
                }
            basaltAlbedo = Texture("Original rain-worn basalt albedo", size, colors, false);
            basaltNormal = Texture("Original carved basalt tangent normals", size, normals, true);
            basaltWetness = Texture("Original basalt variable rain polish", size, wetness, true);
            cachedBasaltAlbedo = basaltAlbedo; cachedBasaltNormal = basaltNormal; cachedBasaltWetness = basaltWetness;
        }

        void CreateMasonryTextures()
        {
            if (cachedMasonryAlbedo && cachedMasonryNormal && cachedMasonryWetness)
            { masonryAlbedo = cachedMasonryAlbedo; masonryNormal = cachedMasonryNormal; masonryWetness = cachedMasonryWetness; return; }
            const int size = 512;
            Color[] colors = new Color[size * size], polish = new Color[size * size], normals = new Color[size * size];
            float[] heights = new float[size * size];
            for (int y = 0; y < size; y++)
                for (int x = 0; x < size; x++)
                {
                    float u = x / (float)size, v = y / (float)size;
                    int row = Mathf.FloorToInt(v * 8);
                    float brickX = u * 5 + (row % 2) * .5f;
                    float bx = Mathf.Repeat(brickX, 1), by = Mathf.Repeat(v * 8, 1);
                    float edge = Mathf.Min(Mathf.Min(bx, 1 - bx) * .6f, Mathf.Min(by, 1 - by));
                    float mortar = 1 - Smooth01(.005f, .032f, edge);
                    float n = TileNoise(u, v, 18, 6.2f), grain = TileNoise(u, v, 97, 52.6f);
                    float block = Hash(Mathf.FloorToInt(brickX) % 5, row);
                    float stain = TileNoise(u, v, 3, 44.1f) * .06f;
                    float tone = .61f + (block - .5f) * .065f + (n - .5f) * .055f + (grain - .5f) * .025f - mortar * .10f - stain;
                    int index = x + y * size;
                    colors[index] = new Color(tone, tone * .98f, tone * .95f, 1);
                    heights[index] = .5f - mortar * .10f + (n - .5f) * .03f + (grain - .5f) * .02f;
                    polish[index] = new Color(.02f, .02f, .02f, .32f + n * .19f - mortar * .12f);
                }
            for (int y = 0; y < size; y++)
                for (int x = 0; x < size; x++)
                {
                    float dx = heights[(x + 1) % size + y * size] - heights[(x + size - 1) % size + y * size];
                    float dy = heights[x + (y + 1) % size * size] - heights[x + (y + size - 1) % size * size];
                    Vector3 n = new Vector3(-dx * 4, -dy * 4, 1).normalized;
                    normals[x + y * size] = new Color(n.x * .5f + .5f, n.y * .5f + .5f, n.z * .5f + .5f, 1);
                }
            masonryAlbedo = Texture("Original restrained cathedral ashlar", size, colors, false);
            masonryNormal = Texture("Original recessed ashlar joints", size, normals, true);
            masonryWetness = Texture("Original rain-dark limestone polish", size, polish, true);
            cachedMasonryAlbedo = masonryAlbedo; cachedMasonryNormal = masonryNormal; cachedMasonryWetness = masonryWetness;
        }

        static Texture2D Texture(string name, int size, Color[] colors, bool linear)
        {
            var texture = new Texture2D(size, size, TextureFormat.RGBA32, true, linear);
            texture.name = name; texture.wrapMode = TextureWrapMode.Repeat;
            texture.filterMode = FilterMode.Trilinear; texture.anisoLevel = 8;
            texture.SetPixels(colors); texture.Apply(true, true);
            return texture;
        }
        static float Hash(int x, int y)
        {
            uint h = unchecked((uint)(x * 374761393 + y * 668265263));
            h = (h ^ (h >> 13)) * 1274126177u;
            return (h & 0x00ffffff) / 16777215f;
        }
        static float Smooth01(float low, float high, float value)
        {
            float t = Mathf.InverseLerp(low, high, value);
            return t * t * (3 - 2 * t);
        }
        static float TileNoise(float u, float v, float scale, float offset)
        {
            float a = Mathf.PerlinNoise(u * scale + offset, v * scale + offset);
            float b = Mathf.PerlinNoise((u - 1) * scale + offset, v * scale + offset);
            float c = Mathf.PerlinNoise(u * scale + offset, (v - 1) * scale + offset);
            float d = Mathf.PerlinNoise((u - 1) * scale + offset, (v - 1) * scale + offset);
            return Mathf.Lerp(Mathf.Lerp(a, b, u), Mathf.Lerp(c, d, u), v);
        }

        void CreateFloor()
        {
            // Slightly separated blocks reveal dark mortar; collider is a single
            // mathematically flat plane so decorative seams cannot snag the player.
            darkStone.Annulus(Vector3.zero, 0, 38.8f, -.035f, .5f, 128);
            float[] radii = { 0, 3.9f, 6.2f, 8.5f, 11, 13.6f, 16.4f, 19.4f, 22.5f, 25.6f, 28.7f, 31.8f, 34.8f, 37.8f };
            for (int ring = 0; ring < radii.Length - 1; ring++)
            {
                int count = Mathf.Max(12, Mathf.RoundToInt((radii[ring] + radii[ring + 1]) * Mathf.PI / 2.4f));
                float offset = ring % 2 == 0 ? 0 : Mathf.PI / count;
                for (int i = 0; i < count; i++)
                {
                    float a = offset + i * Mathf.PI * 2 / count + .0007f;
                    float b = offset + (i + 1) * Mathf.PI * 2 / count - .0007f;
                    Geometry material = random.NextDouble() < .16 ? floorLight : floorStone;
                    material.Wedge(radii[ring] + .018f, radii[ring + 1] - .018f, a, b, -.008f, .08f, 4);
                }
            }
            // A restrained compass pattern gives orientation without resembling
            // attack telegraphs. No emissive geometry lies on the fighting surface.
            foreach (float r in new[] { 8.5f, 19.4f, 31.8f, 37.9f })
                bronze.Annulus(Vector3.zero, r - .045f, r + .045f, .006f, .015f, 160);
            inlay.Annulus(Vector3.zero, 3.75f, 3.83f, .006f, .015f, 96);
            for (int i = 0; i < 12; i++)
            {
                float a = i * Mathf.PI / 6;
                Vector3 p = Radial(a, 11.9f, .012f);
                bronze.Box(p, new Vector3(.085f, .014f, 7.1f), Quaternion.Euler(0, a * Mathf.Rad2Deg, 0));
                inlay.Box(Radial(a, 4.25f, .009f), new Vector3(.065f, .01f, .46f), Quaternion.Euler(0, a * Mathf.Rad2Deg, 0));
            }
            // Narrow outer curb and deep black water frame the playable circle.
            paleStone.Annulus(Vector3.zero, 38, 39.1f, .18f, .8f, 128);
            bronze.Annulus(Vector3.zero, 38.1f, 38.17f, .19f, .03f, 128);
            water.Annulus(Vector3.zero, 39.12f, 130, -.52f, .1f, 180);
            for (int i = 0; i < 54; i++)
            {
                float a = i * Mathf.PI * 2 / 54;
                float r = Rand(41, 68);
                Vector3 p = Radial(a, r, -.40f);
                darkStone.Box(p, new Vector3(Rand(1, 5), Rand(.15f, .4f), Rand(.5f, 2)), Quaternion.Euler(0, Rand(0, 180), 0));
            }
        }

        void CreateArchitecture()
        {
            // Broken cloister bays establish rhythm, but the surviving transept
            // owns the composition. The open eastern bays frame moon and cliffs.
            const int bays = 12;
            const float radius = 45.5f;
            float step = Mathf.PI * 2 / bays;
            for (int i = 0; i < bays; i++)
            {
                float a = i * step;
                Vector3 p = Radial(a, radius);
                Quaternion q = Quaternion.Euler(0, a * Mathf.Rad2Deg, 0);
                bool broken = i == 1 || i == 4 || i == 8;
                float height = broken ? 6.5f + i * .28f : 13.2f;
                stone.Box(p + Vector3.up * .55f, new Vector3(4, 1.1f, 4), q);
                paleStone.Box(p + Vector3.up * 1.14f, new Vector3(3.45f, .18f, 3.45f), q);
                stone.Cylinder(p + Vector3.up * (height * .5f + 1.25f), 1.1f, .98f, height, 12);
                for (int k = 0; k < 6; k++)
                {
                    Vector3 offset = Radial(k * Mathf.PI / 3, 1.02f);
                    paleStone.Cylinder(p + offset + Vector3.up * (height * .5f + 1.25f), .25f, .22f, height, 8);
                    paleStone.Cylinder(p + offset + Vector3.up * 1.45f, .36f, .30f, .35f, 8);
                    if (!broken) paleStone.Cylinder(p + offset + Vector3.up * (height + 1.1f), .28f, .39f, .48f, 8);
                }
                if (!broken)
                {
                    paleStone.Box(p + Vector3.up * (height + 1.45f), new Vector3(2.7f, .24f, 2.7f), q);
                    stone.Box(p + Vector3.up * (height + 1.85f), new Vector3(2.25f, .48f, 2.25f), q);
                }
                else
                    rubble.Rock(p + Vector3.up * (height + 1), new Vector3(2.2f, .7f, 2.1f), 190 + i);
                stone.Beam(p + Radial(a, 1.5f, 8.2f), p + Radial(a, 5.4f, .6f), 1.25f);
                stone.Box(p + Radial(a, 5.2f, 1.1f), new Vector3(2.3f, 2.2f, 2.8f), q);

                if (i != 0 && i != 1 && i != 4 && i != 8 && i != 11)
                {
                    Vector3 next = Radial(a + step, radius);
                    int left = i == 3 || i == 7 ? 5 : 10;
                    int right = i == 3 || i == 7 ? 2 : 10;
                    Arch(p, next, 14.1f, 29.4f, .95f, left, right, stone);
                    Arch(p + Radial(a, -.7f), next + Radial(a + step, -.7f), 14.1f, 28.7f, .19f, left, right, paleStone);
                    if (i == 2 || i == 5 || i == 9)
                    {
                        for (int bay = 0; bay < 3; bay++)
                        {
                            Vector3 l = Vector3.Lerp(p, next, bay / 3f);
                            Vector3 r = Vector3.Lerp(p, next, (bay + 1) / 3f);
                            Arch(l, r, 4.2f, 9.8f, .48f, 10, 10, stone);
                            paleStone.Cylinder(l + Vector3.up * 2.2f, .3f, .24f, 4.4f, 10);
                        }
                    }
                }
                if (i == 3 || i == 9) Banner(p + Radial(a, -1.3f, 11.6f), q, 1.25f, 5.8f);
            }
            CreateTransept();
            for (int i = 0; i < 8; i++)
            {
                float a = (i + .5f) * Mathf.PI / 4;
                Vector3 p = Radial(a, 39.1f);
                stone.Cylinder(p + Vector3.up * .56f, 1.14f, 1.03f, 1.12f, 12);
                paleStone.Cylinder(p + Vector3.up * 1.14f, 1.1f, 1.16f, .16f, 12);
                bronze.Cylinder(p + Vector3.up * 1.5f, .68f, .95f, .6f, 16);
                darkStone.Cylinder(p + Vector3.up * 1.82f, .8f, .8f, .1f, 16);
                for (int k = 0; k < 6; k++)
                    bronze.Beam(p + Radial(k * Mathf.PI / 3, .75f, 1.4f), p + Radial(k * Mathf.PI / 3, 1.05f, 2.35f), .065f);
            }
        }

        void CreateTransept()
        {
            Vector3 center = new Vector3(-16, 0, 55);
            // Wide weathered foundations anchor this surviving wall in the moat.
            for (int step = 0; step < 5; step++)
                stone.Box(center + new Vector3(0, step * .32f, -1), new Vector3(37 - step * 1.1f, .45f, 9 - step * .6f), Quaternion.identity);
            for (int side = -1; side <= 1; side += 2)
            {
                Vector3 pier = center + new Vector3(side * 12.5f, 0, 0);
                stone.Box(pier + Vector3.up * 18, new Vector3(3.7f, 36, 3.2f), Quaternion.identity);
                stone.Box(center + new Vector3(side * 8.2f, 4.3f, -.1f), new Vector3(9.2f, 8.6f, 3), Quaternion.identity);
                paleStone.Box(center + new Vector3(side * 8.2f, 8.7f, -.3f), new Vector3(9.5f, .34f, 3.4f), Quaternion.identity);
                for (int flute = -1; flute <= 1; flute++)
                    paleStone.Cylinder(pier + new Vector3(flute * .72f, 18.1f, -1.72f), .19f, .17f, 33.8f, 10);
                for (int level = 0; level < 4; level++)
                {
                    float y = 9.2f + level * 7.2f;
                    paleStone.Box(pier + new Vector3(0, y, -.25f), new Vector3(4.05f, .21f, 3.65f), Quaternion.identity);
                }
                Vector3 tower = center + new Vector3(side * 16.1f, 0, 1.2f);
                float h = side < 0 ? 42 : 30.5f;
                stone.Box(tower + Vector3.up * h * .5f, new Vector3(3.8f, h, 5.4f), Quaternion.identity);
                for (int edge = -1; edge <= 1; edge += 2)
                    paleStone.Cylinder(tower + new Vector3(edge * 1.65f, h * .5f, -2.62f), .22f, .18f, h, 8);
                paleStone.Box(tower + Vector3.up * (h - .4f), new Vector3(4.2f, .32f, 5.8f), Quaternion.identity);
                if (side < 0)
                {
                    stone.Cylinder(tower + Vector3.up * (h + 2.1f), 2.3f, .32f, 4.2f, 8);
                    paleStone.Cylinder(tower + Vector3.up * (h + 4.6f), .12f, .06f, 1.2f, 8);
                }
                else
                    for (int k = 0; k < 6; k++)
                        rubble.Box(tower + new Vector3(Rand(-1.5f, 1.5f), h + Rand(-.4f, .5f), Rand(-2, 2)), new Vector3(.8f, Rand(.4f, 1.1f), .8f), Quaternion.Euler(0, Rand(-20, 20), Rand(-12, 12)));
                // Blind lancet niches and small projecting capitals break scale.
                for (int level = 0; level < (side < 0 ? 4 : 3); level++)
                {
                    float y = 3 + level * 8;
                    Vector3 niche = tower + new Vector3(0, y, -2.76f);
                    darkStone.Box(niche + Vector3.up * 2, new Vector3(1.35f, 4, .06f), Quaternion.identity);
                    Arch(niche + Vector3.left * .83f, niche + Vector3.right * .83f, 3.9f, 5.3f, .15f, 10, 10, paleStone);
                    for (int edge = -1; edge <= 1; edge += 2)
                        paleStone.Cylinder(niche + new Vector3(edge * .83f, 1.95f, -.06f), .12f, .12f, 3.9f, 8);
                }
            }
            Vector3 facade = center + new Vector3(0, 0, -1.9f);
            for (int layer = 0; layer < 3; layer++)
            {
                float half = 10.6f - layer * .57f;
                Arch(facade + Vector3.left * half + Vector3.back * layer * .26f,
                    facade + Vector3.right * half + Vector3.back * layer * .26f,
                    15.5f, 37.5f - layer * .68f, layer == 0 ? 1.05f : .22f, 10, 10, layer == 0 ? stone : paleStone);
            }
            // Front door below the great window, with repeated recessed mouldings.
            for (int layer = 0; layer < 3; layer++)
            {
                float half = 3.4f - layer * .35f;
                Vector3 door = facade + Vector3.back * layer * .18f;
                Arch(door + Vector3.left * half, door + Vector3.right * half, 4.4f, 10.2f - layer * .45f, layer == 0 ? .62f : .16f, 10, 10, paleStone);
                for (int side = -1; side <= 1; side += 2)
                    paleStone.Cylinder(door + new Vector3(side * half, 2.5f, 0), .17f, .17f, 5, 10);
            }
            for (int mullion = -2; mullion <= 2; mullion++)
            {
                float x = mullion * 3.9f;
                float h = mullion == 0 ? 14.5f : 10.7f;
                paleStone.Cylinder(facade + new Vector3(x, 9 + h * .5f, -.25f), .18f, .14f, h, 10);
                if (mullion < 2)
                    Arch(facade + new Vector3(x, 0, -.25f), facade + new Vector3(x + 3.9f, 0, -.25f), 18.8f, 23.4f, .17f, 10, 10, paleStone);
            }
            Vector3 rose = facade + new Vector3(0, 28.25f, -.28f);
            Circle(rose, 5.05f, .25f, paleStone, 72);
            Circle(rose + Vector3.back * .12f, 4.62f, .12f, paleStone, 72);
            Circle(rose, 1.03f, .15f, paleStone, 40);
            for (int i = 0; i < 8; i++)
            {
                float a = i * Mathf.PI / 4;
                Vector3 direction = new Vector3(Mathf.Sin(a), Mathf.Cos(a), 0);
                paleStone.Beam(rose + direction * 1.05f, rose + direction * 4.65f, .13f);
                Circle(rose + direction * 2.67f, 1.55f, .105f, paleStone, 40);
            }
            // One surviving gable side and a fractured opposite edge avoid a
            // pristine symmetric facade. Fragments sit directly on existing wall.
            stone.Beam(facade + new Vector3(-13, 35.2f, .8f), facade + new Vector3(0, 43.2f, .8f), 1.0f);
            paleStone.Beam(facade + new Vector3(-13, 35.8f, .25f), facade + new Vector3(0, 43.8f, .25f), .21f);
            stone.Beam(facade + new Vector3(0, 43.2f, .8f), facade + new Vector3(5.6f, 39.8f, .8f), .95f);
            stone.Quad(facade + new Vector3(-12.5f, 34.8f, .4f), facade + new Vector3(-12.5f, 35.7f, .4f),
                facade + new Vector3(0, 43.2f, .4f), facade + new Vector3(0, 38.1f, .4f));
            stone.Quad(facade + new Vector3(0, 38.1f, .4f), facade + new Vector3(0, 43.2f, .4f),
                facade + new Vector3(5.6f, 39.8f, .4f), facade + new Vector3(5.6f, 36.9f, .4f));
        }

        void Circle(Vector3 center, float radius, float thickness, Geometry geometry, int count)
        {
            for (int i = 0; i < count; i++)
            {
                float a = i * Mathf.PI * 2 / count, b = (i + 1) * Mathf.PI * 2 / count;
                geometry.Beam(center + new Vector3(Mathf.Sin(a), Mathf.Cos(a), 0) * radius,
                    center + new Vector3(Mathf.Sin(b), Mathf.Cos(b), 0) * radius, thickness);
            }
        }

        void Banner(Vector3 top, Quaternion rotation, float width, float length)
        {
            // Doubled winding gives visible fabric from inside and outside.
            Vector3[] points = new Vector3[10];
            for (int i = 0; i < 5; i++)
            {
                float x = -width / 2 + width * i / 4;
                points[i] = top + rotation * new Vector3(x, 0, .05f);
                points[i + 5] = top + rotation * new Vector3(x + .25f, -length + (i % 2 == 0 ? .55f : 0), Mathf.Sin(i * 1.7f) * .3f);
            }
            for (int i = 0; i < 4; i++)
            {
                bronze.Quad(points[i], points[i + 1], points[i + 6], points[i + 5]);
                bronze.Quad(points[i + 5], points[i + 6], points[i + 1], points[i]);
            }
        }

        void Arch(Vector3 left, Vector3 right, float spring, float apex, float thickness, int leftCount, int rightCount, Geometry geometry)
        {
            Vector3 axis = (right - left).normalized;
            float half = Vector3.Distance(left, right) * .5f;
            float rise = apex - spring;
            float radius = (half * half + rise * rise) / (2 * half);
            float sweep = Mathf.Atan2(rise, radius - half);
            for (int side = 0; side < 2; side++)
            {
                Vector3 start = (side == 0 ? left : right) + Vector3.up * spring;
                Vector3 toward = side == 0 ? axis : -axis;
                int count = side == 0 ? leftCount : rightCount;
                for (int s = 0; s < count; s++)
                {
                    float t0 = s / 10f * sweep, t1 = (s + 1) / 10f * sweep;
                    Vector3 a = start + toward * (radius * (1 - Mathf.Cos(t0))) + Vector3.up * (radius * Mathf.Sin(t0));
                    Vector3 b = start + toward * (radius * (1 - Mathf.Cos(t1))) + Vector3.up * (radius * Mathf.Sin(t1));
                    geometry.Beam(a, b, thickness);
                }
            }
        }

        void CreateSilhouette()
        {
            // Ground the ruins in an overlapping, uneven shoreline. These masses
            // replace the disconnected square wall panels visible in early builds.
            darkStone.Annulus(Vector3.zero, 51, 68, -.34f, 5, 96);
            for (int i = 0; i < 29; i++)
            {
                float a = i * Mathf.PI * 2 / 29;
                Vector3 p = Radial(a, Rand(56, 65), -1.3f);
                rubble.Rock(p, new Vector3(Rand(10, 17), Rand(2.5f, 5.2f), Rand(8, 15)), i * 13 + 9);
            }
            for (int i = 0; i < 19; i++)
            {
                float a = i * Mathf.PI * 2 / 19 + .03f;
                Vector3 p = Radial(a, Rand(110, 150), -5);
                float h = 20 + 22 * Mathf.PerlinNoise(i * .43f, 7.8f);
                darkStone.Rock(p, new Vector3(Rand(25, 40), h, Rand(24, 36)), 157 + i * 7);
                if (i % 3 == 0)
                    rubble.Rock(p + Radial(a, 13), new Vector3(Rand(14, 21), h * 1.45f, Rand(15, 22)), 91 + i * 11);
            }
            for (int i = 0; i < 9; i++)
            {
                float a = Rand(0, Mathf.PI * 2), r = Rand(92, 145);
                float h = Rand(12, 25);
                Vector3 p = Radial(a, r);
                stone.Box(p + Vector3.up * h * .5f, new Vector3(4, h, 6), Quaternion.Euler(0, a * Mathf.Rad2Deg, 0));
                darkStone.Cylinder(p + Vector3.up * (h + 1.8f), 3.2f, .36f, 3.6f, 8);
                if (i % 3 == 0)
                    paleStone.Cylinder(p + Vector3.up * (h + 4), .10f, .06f, 1.2f, 6);
            }
            // Collapsed arch stones and rubble remain outside the playable curb.
            for (int i = 0; i < 86; i++)
            {
                float a = Rand(0, Mathf.PI * 2), r = Rand(41.5f, 52);
                Vector3 size = new Vector3(Rand(.8f, 2.5f), Rand(.65f, 2.1f), Rand(.7f, 2.4f));
                rubble.Box(Radial(a, r, size.y * .18f - .25f), size, Quaternion.Euler(Rand(-22, 22), Rand(0, 180), Rand(-18, 18)));
            }
        }

        void CreateLighting()
        {
            RenderSettings.ambientMode = AmbientMode.Trilight;
            RenderSettings.ambientSkyColor = new Color(.205f, .235f, .275f);
            RenderSettings.ambientEquatorColor = new Color(.105f, .12f, .14f);
            RenderSettings.ambientGroundColor = new Color(.045f, .054f, .065f);
            RenderSettings.ambientIntensity = 1;
            RenderSettings.fog = true;
            RenderSettings.fogMode = FogMode.ExponentialSquared;
            RenderSettings.fogColor = new Color(.035f, .052f, .071f);
            RenderSettings.fogDensity = .0068f;
            CreateStormSky();
            var moonlight = Light("Cold moon key", LightType.Directional, new Color(.71f, .81f, .94f), 1.08f, Vector3.zero);
            moonlight.transform.rotation = Quaternion.LookRotation(-new Vector3(.32f, .43f, .91f).normalized);
            moonlight.shadows = LightShadows.Soft;
            moonlight.shadowStrength = .83f;
            moonlight.shadowBias = .035f;
            moonlight.shadowNormalBias = .2f;
            RenderSettings.sun = moonlight;
            var fill = Light("Soft horizon fill", LightType.Directional, new Color(.52f, .59f, .66f), .38f, Vector3.zero);
            fill.transform.rotation = Quaternion.Euler(24, -25, 0);
            fill.shadows = LightShadows.None;
            flame = new Material(Shader.Find("Standard")) { name = "Original ember cores", color = new Color(1, .35f, .06f) };
            flame.EnableKeyword("_EMISSION");
            flame.SetColor("_EmissionColor", new Color(3.6f, .72f, .1f));
            var shaft = Light("Moon opening over the fighting floor", LightType.Spot, new Color(.65f, .77f, .9f), 4.2f, new Vector3(-22, 38, 15));
            shaft.transform.rotation = Quaternion.LookRotation(new Vector3(6, 0, 1) - shaft.transform.position);
            shaft.range = 72; shaft.spotAngle = 65; shaft.innerSpotAngle = 32;
            shaft.shadows = LightShadows.None;
            for (int i = 0; i < 8; i++)
            {
                Vector3 p = Radial((i + .5f) * Mathf.PI / 4, 39.1f, 2.1f);
                var fire = GameObject.CreatePrimitive(PrimitiveType.Sphere);
                fire.name = "Brazier ember bed";
                fire.transform.SetParent(root);
                fire.transform.position = p - Vector3.up * .25f;
                fire.transform.localScale = new Vector3(1.38f, .16f, 1.38f);
                RemoveCollider(fire);
                fire.GetComponent<Renderer>().sharedMaterial = flame;
                var light = Light("Amber brazier " + i, LightType.Point, new Color(1, .46f, .19f), 2.1f, p + Vector3.up * .6f);
                light.range = 12;
                light.shadows = LightShadows.None;
                light.renderMode = LightRenderMode.ForcePixel;
            }
        }

        void CreateStormSky()
        {
            if (cachedStormSky) { ApplyStormSky(cachedStormSky); return; }
            // A generated directional cubemap avoids the daytime atmospheric
            // scattering/white horizon of Unity's procedural daylight skybox.
            const int size = 512;
            var cubemap = new Cubemap(size, TextureFormat.RGBA32, true);
            cubemap.name = "Original painted storm and moon cubemap";
            cubemap.wrapMode = TextureWrapMode.Clamp;
            cubemap.filterMode = FilterMode.Trilinear;
            Vector3 moonDirection = new Vector3(.32f, .19f, .93f).normalized;
            for (int face = 0; face < 6; face++)
            {
                Color[] pixels = new Color[size * size];
                for (int y = 0; y < size; y++)
                    for (int x = 0; x < size; x++)
                    {
                        float u = (x + .5f) / size * 2 - 1, v = (y + .5f) / size * 2 - 1;
                        Vector3 d;
                        switch (face)
                        {
                            case 0: d = new Vector3(1, -v, -u); break;
                            case 1: d = new Vector3(-1, -v, u); break;
                            case 2: d = new Vector3(u, 1, v); break;
                            case 3: d = new Vector3(u, -1, -v); break;
                            case 4: d = new Vector3(u, -v, 1); break;
                            default: d = new Vector3(-u, -v, -1); break;
                        }
                        d.Normalize();
                        Vector3 wind = new Vector3(d.x * 1.2f, d.y * .65f, d.z * 1.2f);
                        float cloud = Cloud(wind * 5.1f) * .62f + Cloud(wind * 12.7f) * .26f + Cloud(wind * 29) * .12f;
                        cloud = Smooth01(.36f, .64f, cloud);
                        float height = Mathf.Clamp01(d.y * 1.3f);
                        Color color = Color.Lerp(new Color(.020f, .033f, .050f), new Color(.006f, .012f, .024f), height);
                        float moonDot = Mathf.Clamp01(Vector3.Dot(d, moonDirection));
                        float halo = Mathf.Pow(moonDot, 65);
                        float silver = Mathf.Pow(cloud, 1.6f);
                        color += new Color(.056f, .067f, .082f) * silver * (.48f + halo * 1.8f);
                        color += new Color(.12f, .15f, .18f) * halo * .26f;
                        float disc = Smooth01(.9971f, .9979f, moonDot);
                        float veil = Mathf.Lerp(.95f, .42f, Smooth01(.46f, .90f, cloud));
                        float crater = disc > 0 ? .78f + Cloud(d * 173) * .22f : 1;
                        color = Color.Lerp(color, new Color(.58f, .65f, .70f) * veil * crater, disc);
                        if (d.y < -.02f) color = Color.Lerp(color, new Color(.014f, .023f, .032f), Mathf.Clamp01(-d.y * 4));
                        pixels[x + y * size] = color;
                    }
                cubemap.SetPixels(pixels, (CubemapFace)face);
            }
            cubemap.Apply(true, true);
            cachedStormSky = cubemap;
            ApplyStormSky(cubemap);
        }

        void ApplyStormSky(Cubemap cubemap)
        {
            var sky = new Material(Shader.Find("Skybox/Cubemap")) { name = "Original drowned cathedral storm sky" };
            sky.SetTexture("_Tex", cubemap); sky.SetColor("_Tint", new Color(.5f, .5f, .5f)); sky.SetFloat("_Exposure", 1);
            RenderSettings.skybox = sky;
            RenderSettings.defaultReflectionMode = DefaultReflectionMode.Custom;
            RenderSettings.customReflectionTexture = cubemap;
            RenderSettings.reflectionIntensity = .65f;
        }

        static float Cloud(Vector3 p)
        {
            return (Mathf.PerlinNoise(p.x + 41.7f, p.y + 13.2f) + Mathf.PerlinNoise(p.y + 9.3f, p.z + 68.5f)
                + Mathf.PerlinNoise(p.z + 81.1f, p.x + 25.6f)) / 3;
        }

        Light Light(string name, LightType type, Color color, float intensity, Vector3 position)
        {
            var go = new GameObject(name);
            go.transform.SetParent(root);
            go.transform.position = position;
            var light = go.AddComponent<Light>();
            light.type = type; light.color = color; light.intensity = intensity;
            return light;
        }

        void CreateParticles()
        {
            Shader shader = Shader.Find("Particles/Standard Unlit");
            if (!shader) shader = Shader.Find("Legacy Shaders/Particles/Additive");
            ember = new Material(shader) { name = "Soft original ember sprites" };
            var texture = new Texture2D(32, 32, TextureFormat.RGBA32, false);
            texture.name = "Procedurally painted radial particle";
            texture.wrapMode = TextureWrapMode.Clamp;
            for (int y = 0; y < 32; y++)
                for (int x = 0; x < 32; x++)
                {
                    float radius = Vector2.Distance(new Vector2(x, y), new Vector2(15.5f, 15.5f)) / 15.5f;
                    float alpha = Mathf.Pow(Mathf.Clamp01(1 - radius), 2);
                    // Multiplying RGB as well as alpha keeps the sprite soft
                    // under both supported additive particle shader variants.
                    texture.SetPixel(x, y, new Color(alpha, alpha, alpha, alpha));
                }
            texture.Apply();
            ember.mainTexture = texture;
            ember.SetFloat("_Mode", 4);
            ember.SetInt("_SrcBlend", (int)BlendMode.SrcAlpha);
            ember.SetInt("_DstBlend", (int)BlendMode.One);
            ember.SetInt("_ZWrite", 0);
            ember.EnableKeyword("_ALPHABLEND_ON");
            ember.renderQueue = 3000;
            for (int i = 0; i < 8; i++)
            {
                Vector3 p = Radial((i + .5f) * Mathf.PI / 4, 39.1f, 1.95f);
                var ps = Particles("Brazier rising sparks " + i, p, 55, 12, new Color(1, .36f, .055f, .9f), .17f, 2.2f);
                var main = ps.main; main.startSpeed = new ParticleSystem.MinMaxCurve(.6f, 1.6f);
                main.startSize = new ParticleSystem.MinMaxCurve(.07f, .30f);
                var shape = ps.shape; shape.shapeType = ParticleSystemShapeType.Cone; shape.angle = 10; shape.radius = .52f;
                ps.transform.rotation = Quaternion.Euler(-90, 0, 0);
                var velocity = ps.velocityOverLifetime; velocity.enabled = true; velocity.space = ParticleSystemSimulationSpace.World;
                velocity.x = new ParticleSystem.MinMaxCurve(.25f); velocity.y = new ParticleSystem.MinMaxCurve(.6f); velocity.z = new ParticleSystem.MinMaxCurve(.1f);
                ps.Play();
            }
            var dust = Particles("Sparse moonlit drifting motes", new Vector3(0, 5, 0), 170, 12, new Color(.45f, .60f, .70f, .22f), .045f, 12);
            var dustMain = dust.main; dustMain.startSpeed = .12f;
            var dustShape = dust.shape; dustShape.shapeType = ParticleSystemShapeType.Box; dustShape.scale = new Vector3(72, 12, 72);
            var drift = dust.velocityOverLifetime; drift.enabled = true; drift.space = ParticleSystemSimulationSpace.World;
            drift.x = new ParticleSystem.MinMaxCurve(.12f); drift.y = new ParticleSystem.MinMaxCurve(-.08f); drift.z = new ParticleSystem.MinMaxCurve(.05f);
            dust.Play();
        }

        ParticleSystem Particles(string name, Vector3 position, int capacity, float rate, Color color, float size, float lifetime)
        {
            var go = new GameObject(name); go.transform.SetParent(root); go.transform.position = position;
            var ps = go.AddComponent<ParticleSystem>(); ps.Stop(true, ParticleSystemStopBehavior.StopEmittingAndClear);
            var main = ps.main; main.loop = true; main.playOnAwake = false; main.maxParticles = capacity;
            main.simulationSpace = ParticleSystemSimulationSpace.World; main.startLifetime = lifetime; main.startSize = size;
            main.startColor = color; main.startSpeed = 0;
            var emission = ps.emission; emission.rateOverTime = rate;
            var fade = ps.colorOverLifetime; fade.enabled = true;
            var gradient = new Gradient(); gradient.SetKeys(new[] { new GradientColorKey(Color.white, 0), new GradientColorKey(Color.white, 1) },
                new[] { new GradientAlphaKey(0, 0), new GradientAlphaKey(1, .12f), new GradientAlphaKey(0, 1) });
            fade.color = gradient;
            var renderer = ps.GetComponent<ParticleSystemRenderer>(); renderer.sharedMaterial = ember;
            renderer.shadowCastingMode = ShadowCastingMode.Off; renderer.receiveShadows = false;
            return ps;
        }

        void CreateCollision()
        {
            var floor = new GameObject("Flat combat floor collision"); floor.transform.SetParent(root);
            floor.transform.position = new Vector3(0, -.25f, 0);
            var box = floor.AddComponent<BoxCollider>(); box.size = new Vector3(79, .5f, 79);
            for (int i = 0; i < 48; i++)
            {
                float a = (i + .5f) * Mathf.PI * 2 / 48;
                var wall = new GameObject("Arena boundary " + i); wall.transform.SetParent(root);
                wall.transform.position = Radial(a, 39.3f, 4);
                wall.transform.rotation = Quaternion.Euler(0, a * Mathf.Rad2Deg, 0);
                var collider = wall.AddComponent<BoxCollider>(); collider.size = new Vector3(5.3f, 8, 1.1f);
            }
        }

        static void RemoveCollider(GameObject go)
        {
            var collider = go.GetComponent<Collider>();
            if (Application.isPlaying) Object.Destroy(collider); else Object.DestroyImmediate(collider);
        }
    }

    // Batched, flat-shaded masonry keeps hundreds of authored architectural forms
    // to nine static renderers, with no Update methods or per-block GameObjects.
    sealed class Geometry
    {
        readonly string name; readonly Material material;
        readonly List<Vector3> vertices = new List<Vector3>();
        readonly List<Vector3> normals = new List<Vector3>();
        readonly List<Vector2> uv = new List<Vector2>();
        readonly List<int> indices = new List<int>();
        public Geometry(string name, Material material) { this.name = name; this.material = material; }
        public void Quad(Vector3 a, Vector3 b, Vector3 c, Vector3 d) { Quad(a, b, c, d, Vector3.Cross(b - a, c - a).normalized); }
        public void Quad(Vector3 a, Vector3 b, Vector3 c, Vector3 d, Vector3 normal)
        {
            int index = vertices.Count;
            vertices.Add(a); vertices.Add(b); vertices.Add(c); vertices.Add(d);
            for (int k = 0; k < 4; k++) normals.Add(normal);
            uv.Add(ProjectUV(a, normal)); uv.Add(ProjectUV(b, normal));
            uv.Add(ProjectUV(c, normal)); uv.Add(ProjectUV(d, normal));
            indices.Add(index); indices.Add(index + 1); indices.Add(index + 2);
            indices.Add(index); indices.Add(index + 2); indices.Add(index + 3);
        }
        static Vector2 ProjectUV(Vector3 p, Vector3 normal)
        {
            if (Mathf.Abs(normal.y) > .6f) return new Vector2(p.x, p.z) * .22f;
            if (Mathf.Abs(normal.x) > Mathf.Abs(normal.z)) return new Vector2(p.z, p.y) * .22f;
            return new Vector2(p.x, p.y) * .22f;
        }
        public void Box(Vector3 center, Vector3 size, Quaternion rotation)
        {
            Vector3 h = size * .5f;
            Vector3[] p = new Vector3[8];
            for (int i = 0; i < 8; i++) p[i] = center + rotation * new Vector3((i & 1) == 0 ? -h.x : h.x, (i & 2) == 0 ? -h.y : h.y, (i & 4) == 0 ? -h.z : h.z);
            Quad(p[0], p[2], p[3], p[1]); Quad(p[4], p[5], p[7], p[6]);
            Quad(p[0], p[4], p[6], p[2]); Quad(p[1], p[3], p[7], p[5]);
            Quad(p[2], p[6], p[7], p[3]); Quad(p[0], p[1], p[5], p[4]);
        }
        public void Beam(Vector3 start, Vector3 end, float thickness)
        {
            Vector3 delta = end - start;
            Box((start + end) * .5f, new Vector3(thickness, delta.magnitude + .09f, thickness), Quaternion.FromToRotation(Vector3.up, delta.normalized));
        }
        public void Rock(Vector3 basePosition, Vector3 size, int seed)
        {
            const int sides = 13, levels = 6;
            float[] profiles = { 1, .96f, .82f, .78f, .64f, .43f };
            Vector3[,] rings = new Vector3[levels, sides];
            for (int ring = 0; ring < levels; ring++)
                for (int i = 0; i < sides; i++)
                {
                    float angle = i * Mathf.PI * 2 / sides;
                    float irregularity = .87f + .13f * Mathf.Sin(seed * .71f + i * 2.17f + ring * .53f);
                    float profile = profiles[ring];
                    float height = ring / 5f * .92f;
                    float offset = Mathf.Sin(seed + ring * .8f) * .12f;
                    rings[ring, i] = basePosition + new Vector3(
                        (Mathf.Sin(angle) * profile * irregularity + offset) * size.x * .5f,
                        (height + (ring == 0 ? 0 : Mathf.Sin(i * 2.7f + seed + ring * .4f) * .045f)) * size.y,
                        (Mathf.Cos(angle) * profile * irregularity - offset) * size.z * .5f);
                }
            for (int ring = 0; ring < levels - 1; ring++)
                for (int i = 0; i < sides; i++)
                {
                    int next = (i + 1) % sides;
                    Quad(rings[ring, i], rings[ring, next], rings[ring + 1, next], rings[ring + 1, i]);
                }
            Vector3 summit = basePosition + new Vector3(size.x * .025f, size.y * .94f, -size.z * .025f);
            for (int i = 0; i < sides; i++)
                Quad(rings[levels - 1, i], rings[levels - 1, (i + 1) % sides], summit, summit);
        }
        public void Cylinder(Vector3 center, float bottomRadius, float topRadius, float height, int sides)
        {
            Vector3 bottom = center - Vector3.up * height / 2, top = center + Vector3.up * height / 2;
            for (int i = 0; i < sides; i++)
            {
                float a = i * Mathf.PI * 2 / sides, b = (i + 1) * Mathf.PI * 2 / sides;
                Vector3 va = new Vector3(Mathf.Sin(a), 0, Mathf.Cos(a)), vb = new Vector3(Mathf.Sin(b), 0, Mathf.Cos(b));
                Quad(bottom + va * bottomRadius, bottom + vb * bottomRadius, top + vb * topRadius, top + va * topRadius);
                Quad(top, top + va * topRadius, top + vb * topRadius, top, Vector3.up);
                Quad(bottom, bottom + vb * bottomRadius, bottom + va * bottomRadius, bottom, Vector3.down);
            }
        }
        public void Annulus(Vector3 center, float inner, float outer, float y, float depth, int sides)
        {
            for (int i = 0; i < sides; i++) Wedge(inner, outer, i * Mathf.PI * 2 / sides, (i + 1) * Mathf.PI * 2 / sides, y, depth, 1, center);
        }
        public void Wedge(float inner, float outer, float start, float end, float y, float depth, int subdivisions, Vector3 center = default(Vector3))
        {
            for (int i = 0; i < subdivisions; i++)
            {
                float a = Mathf.Lerp(start, end, i / (float)subdivisions), b = Mathf.Lerp(start, end, (i + 1f) / subdivisions);
                Vector3 ai = center + new Vector3(Mathf.Sin(a) * inner, y, Mathf.Cos(a) * inner);
                Vector3 ao = center + new Vector3(Mathf.Sin(a) * outer, y, Mathf.Cos(a) * outer);
                Vector3 bi = center + new Vector3(Mathf.Sin(b) * inner, y, Mathf.Cos(b) * inner);
                Vector3 bo = center + new Vector3(Mathf.Sin(b) * outer, y, Mathf.Cos(b) * outer);
                Vector3 down = Vector3.down * depth;
                Quad(ai, ao, bo, bi, Vector3.up);
                Quad(bo, ao, ao + down, bo + down);
                if (inner > 0) Quad(ai, bi, bi + down, ai + down);
                if (i == 0) Quad(ao, ai, ai + down, ao + down);
                if (i == subdivisions - 1) Quad(bi, bo, bo + down, bi + down);
            }
        }
        public void Finish(Transform parent)
        {
            var go = new GameObject(name); go.transform.SetParent(parent); go.isStatic = true;
            var mesh = new Mesh { name = name + " authored mesh", indexFormat = IndexFormat.UInt32 };
            mesh.SetVertices(vertices); mesh.SetNormals(normals); mesh.SetUVs(0, uv); mesh.SetTriangles(indices, 0);
            mesh.RecalculateBounds(); mesh.RecalculateTangents();
            go.AddComponent<MeshFilter>().sharedMesh = mesh;
            go.AddComponent<MeshRenderer>().sharedMaterial = material;
        }
    }
}
