using UnrealBuildTool;
public class Veyr : ModuleRules
{
    public Veyr(ReadOnlyTargetRules Target) : base(Target)
    {
        PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
        PublicDependencyModuleNames.AddRange(new string[]{"Core","CoreUObject","Engine","InputCore"});
        PrivateDependencyModuleNames.AddRange(new string[]{"Json","JsonUtilities","RenderCore","RHI"});
    }
}
