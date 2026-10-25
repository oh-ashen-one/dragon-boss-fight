using UnrealBuildTool;
using System.IO;
public class Veyr : ModuleRules
{
    public Veyr(ReadOnlyTargetRules Target) : base(Target)
    {
        PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
        PublicIncludePaths.Add(Path.GetFullPath(Path.Combine(ModuleDirectory, "..", "..", "Intermediate", "VeyrBuild")));
        PublicDependencyModuleNames.AddRange(new string[]{"Core","CoreUObject","Engine","InputCore"});
        PrivateDependencyModuleNames.AddRange(new string[]{"Json","JsonUtilities","RenderCore","RHI","Slate","SlateCore"});
        RuntimeDependencies.Add("$(ProjectDir)/Content/UI/Fonts/CormorantGaramond.ttf", StagedFileType.UFS);
        RuntimeDependencies.Add("$(ProjectDir)/Content/UI/Fonts/OFL-CormorantGaramond.txt", StagedFileType.UFS);
    }
}
