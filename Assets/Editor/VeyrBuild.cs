using UnityEngine;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEditor.Build.Reporting;
using System.IO;
public static class VeyrBuild
{
    public static void Build(){
        Directory.CreateDirectory("Assets/Scenes");Directory.CreateDirectory("Builds");
        var scene=EditorSceneManager.NewScene(NewSceneSetup.EmptyScene,NewSceneMode.Single);
        EditorSceneManager.SaveScene(scene,"Assets/Scenes/Cathedral.unity");
        PlayerSettings.companyName="Veyr";PlayerSettings.productName="Veyr - The Cinder Warden";
        PlayerSettings.SetApplicationIdentifier(UnityEditor.Build.NamedBuildTarget.Standalone,"games.veyr.cinderwarden");
        PlayerSettings.defaultScreenWidth=1280;PlayerSettings.defaultScreenHeight=720;PlayerSettings.fullScreenMode=FullScreenMode.Windowed;
        PlayerSettings.runInBackground=false;PlayerSettings.colorSpace=ColorSpace.Linear;
        var settings=new SerializedObject(AssetDatabase.LoadAllAssetsAtPath("ProjectSettings/ProjectSettings.asset")[0]);
        var input=settings.FindProperty("activeInputHandler");if(input!=null){input.intValue=0;settings.ApplyModifiedPropertiesWithoutUndo();}
        AssetDatabase.SaveAssets();
        var result=BuildPipeline.BuildPlayer(new BuildPlayerOptions{scenes=new[]{"Assets/Scenes/Cathedral.unity"},locationPathName="Builds/Veyr.app",target=BuildTarget.StandaloneOSX,options=BuildOptions.Development});
        Debug.Log("VEYR_BUILD_RESULT "+result.summary.result+" errors="+result.summary.totalErrors);
        if(result.summary.result!=BuildResult.Succeeded)throw new System.Exception("Native build failed");
    }
}
