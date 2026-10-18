using UnityEngine;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEditor.Build.Reporting;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
public static class VeyrBuild
{
    public static void Build(){
        Directory.CreateDirectory("Assets/Scenes");Directory.CreateDirectory("Builds");
        Directory.CreateDirectory("Assets/Resources/ShaderKeep");
        foreach(var shaderName in new[]{"Standard","Sprites/Default","Unlit/Color","Skybox/Procedural","Skybox/Cubemap","Particles/Standard Unlit","Legacy Shaders/Particles/Additive"}){
            var shader=Shader.Find(shaderName);if(!shader)throw new System.Exception("Required shader missing: "+shaderName);
            string path="Assets/Resources/ShaderKeep/"+shaderName.Replace('/','_')+".mat";
            if(!AssetDatabase.LoadAssetAtPath<Material>(path))AssetDatabase.CreateAsset(new Material(shader),path);
        }
        var standard=AssetDatabase.LoadAssetAtPath<Material>("Assets/Resources/ShaderKeep/Standard.mat");
        standard.EnableKeyword("_NORMALMAP");standard.EnableKeyword("_METALLICGLOSSMAP");EditorUtility.SetDirty(standard);
        var scene=EditorSceneManager.NewScene(NewSceneSetup.EmptyScene,NewSceneMode.Single);
        EditorSceneManager.SaveScene(scene,"Assets/Scenes/Cathedral.unity");
        PlayerSettings.companyName="Veyr";PlayerSettings.productName="Veyr - The Cinder Warden";
        PlayerSettings.SetApplicationIdentifier(UnityEditor.Build.NamedBuildTarget.Standalone,"games.veyr.cinderwarden");
        PlayerSettings.defaultScreenWidth=1280;PlayerSettings.defaultScreenHeight=720;PlayerSettings.fullScreenMode=FullScreenMode.Windowed;
        PlayerSettings.runInBackground=false;PlayerSettings.colorSpace=ColorSpace.Linear;
        var settings=new SerializedObject(AssetDatabase.LoadAllAssetsAtPath("ProjectSettings/ProjectSettings.asset")[0]);
        var input=settings.FindProperty("activeInputHandler");if(input!=null){input.intValue=0;settings.ApplyModifiedPropertiesWithoutUndo();}
        AssetDatabase.SaveAssets();
        using(var sha=SHA256.Create()){
            var entries=Directory.GetFiles("Assets","*",SearchOption.AllDirectories).Where(p=>p.EndsWith(".cs")||p.EndsWith(".fbx")).OrderBy(p=>p).Select(p=>p.Replace('\\','/')+" "+System.BitConverter.ToString(sha.ComputeHash(File.ReadAllBytes(p))).Replace("-","").ToLowerInvariant()).ToArray();
            string manifest=string.Join("\n",entries)+"\n";
            File.WriteAllText("Assets/Resources/SourceManifest.txt",manifest);
            AssetDatabase.Refresh();
            File.WriteAllText("Builds/source-manifest.txt",manifest);
        }
        var result=BuildPipeline.BuildPlayer(new BuildPlayerOptions{scenes=new[]{"Assets/Scenes/Cathedral.unity"},locationPathName="Builds/Veyr.app",target=BuildTarget.StandaloneOSX,options=BuildOptions.None});
        Debug.Log("VEYR_BUILD_RESULT "+result.summary.result+" errors="+result.summary.totalErrors);
        if(result.summary.result!=BuildResult.Succeeded)throw new System.Exception("Native build failed");
    }
}
