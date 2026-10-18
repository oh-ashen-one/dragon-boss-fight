using UnrealBuildTool;
public class VeyrEditorTarget : TargetRules
{
    public VeyrEditorTarget(TargetInfo Target) : base(Target)
    {
        Type = TargetType.Editor;
        DefaultBuildSettings = BuildSettingsVersion.Latest;
        IncludeOrderVersion = EngineIncludeOrderVersion.Latest;
        ExtraModuleNames.Add("Veyr");
    }
}
