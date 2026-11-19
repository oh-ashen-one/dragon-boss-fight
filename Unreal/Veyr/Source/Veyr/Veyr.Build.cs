using UnrealBuildTool;
using System.IO;
public class Veyr : ModuleRules
{
    public Veyr(ReadOnlyTargetRules Target) : base(Target)
    {
        PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
        PublicIncludePaths.Add(Path.GetFullPath(Path.Combine(ModuleDirectory, "..", "..", "Intermediate", "VeyrBuild")));
        PublicDependencyModuleNames.AddRange(new string[]{"Core","CoreUObject","Engine","InputCore","Niagara","ProceduralMeshComponent"});
        PrivateDependencyModuleNames.AddRange(new string[]{"Json","JsonUtilities","RenderCore","RHI","Slate","SlateCore","AudioMixer","AnimationCore"});
        RuntimeDependencies.Add("$(ProjectDir)/Content/UI/Fonts/CormorantGaramond.ttf", StagedFileType.UFS);
        RuntimeDependencies.Add("$(ProjectDir)/Content/UI/Fonts/OFL-CormorantGaramond.txt", StagedFileType.UFS);
        // Camera fourth pass: the drawn dragon skin for the camera audit and proxy proof (private, git-ignored; written by
        // the VeyrCameraProxyExport commandlet). Staged only where it exists; without it the audit says so.
        string TrueSkin = Path.Combine(ModuleDirectory, "..", "..", "Content", "Characters", "Customuse", "CameraProxy", "DragonTrueSkin.bin");
        if (File.Exists(TrueSkin)) RuntimeDependencies.Add("$(ProjectDir)/Content/Characters/Customuse/CameraProxy/DragonTrueSkin.bin", StagedFileType.UFS);
    }
}
