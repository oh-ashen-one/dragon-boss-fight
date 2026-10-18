Shader "Veyr/NativeAtmosphere"
{
    Properties { _MainTex("Source",2D)="white"{} _BloomTex("Glare",2D)="black"{} }
    SubShader
    {
        Cull Off ZWrite Off ZTest Always
        CGINCLUDE
        #include "UnityCG.cginc"
        sampler2D _MainTex, _BloomTex;
        float4 _BlurStep;
        half4 bright(v2f_img i):SV_Target {
            half3 c=tex2D(_MainTex,i.uv).rgb;
            half peak=max(c.r,max(c.g,c.b));
            return half4(c*(max(peak-1.1,0)/max(peak,.001)),1);
        }
        half4 blur(v2f_img i):SV_Target {
            half3 c=tex2D(_MainTex,i.uv).rgb*.227027;
            c+=(tex2D(_MainTex,i.uv+_BlurStep.xy*1.384615).rgb+tex2D(_MainTex,i.uv-_BlurStep.xy*1.384615).rgb)*.316216;
            c+=(tex2D(_MainTex,i.uv+_BlurStep.xy*3.230769).rgb+tex2D(_MainTex,i.uv-_BlurStep.xy*3.230769).rgb)*.070270;
            return half4(c,1);
        }
        half4 grade(v2f_img i):SV_Target {
            half3 c=tex2D(_MainTex,i.uv).rgb+tex2D(_BloomTex,i.uv).rgb*.16;
            c*=.9;
            c=saturate((c*(2.51*c+.03))/(c*(2.43*c+.59)+.14));
            half2 edge=i.uv*(1-i.uv);
            c*=lerp(.91,1,saturate(edge.x*edge.y*20));
            return half4(c,1);
        }
        ENDCG
        Pass { CGPROGRAM
            #pragma vertex vert_img
            #pragma fragment bright
            ENDCG }
        Pass { CGPROGRAM
            #pragma vertex vert_img
            #pragma fragment blur
            ENDCG }
        Pass { CGPROGRAM
            #pragma vertex vert_img
            #pragma fragment grade
            ENDCG }
    }
    Fallback Off
}
