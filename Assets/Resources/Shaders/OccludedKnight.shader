Shader "Veyr/BossOccludedKnight"
{
    Properties { _Amber ("Occluded knight amber", Color) = (1, 0.59, 0.18, 1) }
    SubShader
    {
        Tags { "RenderType"="Opaque" }
        // Preserve all stencil bits except our low bit, then clear it immediately.
        Pass
        {
            Name "VisibleBossMask"
            Cull Back ZWrite Off ZTest LEqual ColorMask 0
            Stencil { Ref 1 ReadMask 1 WriteMask 1 Comp Always Pass Replace }
            CGPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #include "UnityCG.cginc"
            float4 vert(float4 vertex : POSITION) : SV_POSITION { return UnityObjectToClipPos(vertex); }
            fixed4 frag() : SV_Target { return 0; }
            ENDCG
        }
        Pass
        {
            Name "HiddenKnightAmber"
            Cull Back ZWrite Off ZTest Greater
            Blend SrcAlpha OneMinusSrcAlpha
            Stencil { Ref 1 ReadMask 1 WriteMask 0 Comp Equal Pass Keep }
            CGPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #include "UnityCG.cginc"
            fixed4 _Amber;
            struct Input { float4 vertex : POSITION; float3 normal : NORMAL; };
            struct Varying { float4 position : SV_POSITION; float3 normal : TEXCOORD0; float3 view : TEXCOORD1; };
            Varying vert(Input v)
            {
                Varying o;
                o.position = UnityObjectToClipPos(v.vertex);
                float3 world = mul(unity_ObjectToWorld, v.vertex).xyz;
                o.normal = UnityObjectToWorldNormal(v.normal);
                o.view = _WorldSpaceCameraPos.xyz - world;
                return o;
            }
            fixed4 frag(Varying i) : SV_Target
            {
                float rim = pow(1 - saturate(abs(dot(normalize(i.normal), normalize(i.view)))), 1.7);
                // Solid core communicates pose; brighter edges reveal sword
                // direction and dodge rotation against dark or glowing scales.
                float alpha = lerp(.40, .88, rim);
                float3 color = lerp(_Amber.rgb * .72, float3(1, .79, .40), rim);
                return fixed4(color, alpha);
            }
            ENDCG
        }
        Pass
        {
            Name "ReleaseBossMask"
            Cull Back ZWrite Off ZTest LEqual ColorMask 0
            Stencil { Ref 0 ReadMask 1 WriteMask 1 Comp Always Pass Zero }
            CGPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #include "UnityCG.cginc"
            float4 vert(float4 vertex : POSITION) : SV_POSITION { return UnityObjectToClipPos(vertex); }
            fixed4 frag() : SV_Target { return 0; }
            ENDCG
        }
    }
    Fallback Off
}
