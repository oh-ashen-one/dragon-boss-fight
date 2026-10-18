using UnityEngine;

// Small native post stack: restrained glare and a bounded filmic response.
// This processes gameplay's actual camera; it never substitutes rendered frames.
[RequireComponent(typeof(Camera))]
public sealed class NativeAtmosphere : MonoBehaviour
{
    Material material;
    void Awake(){var shader=Resources.Load<Shader>("VeyrAtmosphere");if(shader&&shader.isSupported)material=new Material(shader);}
    void OnRenderImage(RenderTexture source,RenderTexture destination)
    {
        if(!material){Graphics.Blit(source,destination);return;}
        int w=Mathf.Max(1,source.width/4),h=Mathf.Max(1,source.height/4);
        var a=RenderTexture.GetTemporary(w,h,0,RenderTextureFormat.DefaultHDR);
        var b=RenderTexture.GetTemporary(w,h,0,RenderTextureFormat.DefaultHDR);
        a.filterMode=b.filterMode=FilterMode.Bilinear;
        Graphics.Blit(source,a,material,0);
        material.SetVector("_BlurStep",new Vector4(1f/w,0,0,0));Graphics.Blit(a,b,material,1);
        material.SetVector("_BlurStep",new Vector4(0,1f/h,0,0));Graphics.Blit(b,a,material,1);
        material.SetTexture("_BloomTex",a);Graphics.Blit(source,destination,material,2);
        RenderTexture.ReleaseTemporary(a);RenderTexture.ReleaseTemporary(b);
    }
    void OnDestroy(){if(material)Destroy(material);}
}
