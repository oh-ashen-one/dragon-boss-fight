#include "VeyrLook.h"
#include "Camera/PlayerCameraManager.h"
#include "Engine/World.h"
#include "GameFramework/PlayerController.h"
#include "HAL/IConsoleManager.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"

namespace
{
    void SetCVar(const TCHAR* Name,const TCHAR* Value)
    {
        if(IConsoleVariable* Var=IConsoleManager::Get().FindConsoleVariable(Name))
        {
            Var->Set(Value,ECVF_SetByCode);
            UE_LOG(LogTemp,Display,TEXT("VEYR_LOOK_CVAR %s=%s now=%s"),Name,Value,*Var->GetString());
        }
        else UE_LOG(LogTemp,Warning,TEXT("VEYR_LOOK_CVAR_MISSING %s"),Name);
    }
}

bool VeyrLook::IsLegacy()
{
    static const bool bLegacy=FParse::Param(FCommandLine::Get(),TEXT("VeyrLegacyRender"));
    return bLegacy;
}

bool VeyrLook::SplitInstancesForLumen()
{
    static const bool bSplit=!IsLegacy()&&!FParse::Param(FCommandLine::Get(),TEXT("VeyrNoLumenSplit"));
    return bSplit;
}

int32 VeyrLook::RenderTier()
{
    static const int32 Tier=[]{int32 T=0;FParse::Value(FCommandLine::Get(),TEXT("VeyrRenderTier="),T);return FMath::Clamp(T,0,8);}();
    return IsLegacy()?0:Tier;
}

int32 VeyrLook::ShadowedFireBudget()
{
    return RenderTier()>=2?4:1000;
}

void VeyrLook::ApplyRenderer()
{
    static bool bApplied=false;
    if(bApplied)return;
    bApplied=true;
    if(IsLegacy())
    {
        // The ini turns these on for the new look. Build 16 had all of them off.
        // r.GenerateMeshDistanceFields is read-only: the cooked distance fields stay,
        // so the two distance-field consumers that would change the old picture are off.
        SetCVar(TEXT("r.DynamicGlobalIlluminationMethod"),TEXT("0"));
        SetCVar(TEXT("r.ReflectionMethod"),TEXT("0"));
        SetCVar(TEXT("r.Shadow.Virtual.Enable"),TEXT("0"));
        SetCVar(TEXT("r.DistanceFieldAO"),TEXT("0"));
        SetCVar(TEXT("r.DistanceFieldShadowing"),TEXT("0"));
        UE_LOG(LogTemp,Display,TEXT("VEYR_LOOK legacy=1 tier=0"));
        return;
    }
    SetCVar(TEXT("r.DynamicGlobalIlluminationMethod"),TEXT("1"));
    SetCVar(TEXT("r.ReflectionMethod"),TEXT("1"));
    SetCVar(TEXT("r.Shadow.Virtual.Enable"),TEXT("1"));
    // Ten shadowed fires and three pools can overlap one pixel near the walls.
    SetCVar(TEXT("r.Shadow.Virtual.OnePassProjection.MaxLightsPerPixel"),TEXT("32"));
    const int32 Tier=RenderTier();
    // Cumulative fallback steps, cheapest visual loss first (C-notes "Scalability fallback").
    if(Tier>=1){SetCVar(TEXT("r.VolumetricFog.GridPixelSize"),TEXT("16"));SetCVar(TEXT("r.VolumetricFog.GridSizeZ"),TEXT("64"));}
    // Tier 2 is the shadowed-fire budget (ShadowedFireBudget), read by the arena.
    if(Tier>=3){SetCVar(TEXT("r.Lumen.Reflections.DownsampleFactor"),TEXT("2"));SetCVar(TEXT("r.Lumen.Reflections.MaxRoughnessToTraceClamp"),TEXT("0.3"));}
    if(Tier>=4){SetCVar(TEXT("r.Lumen.ScreenProbeGather.DownsampleFactor"),TEXT("32"));SetCVar(TEXT("r.Lumen.ScreenProbeGather.TracingOctahedronResolution"),TEXT("6"));}
    if(Tier>=5){SetCVar(TEXT("sg.GlobalIlluminationQuality"),TEXT("2"));SetCVar(TEXT("sg.ReflectionQuality"),TEXT("2"));SetCVar(TEXT("r.Lumen.Reflections.Allow"),TEXT("0"));}
    if(Tier>=6){SetCVar(TEXT("r.Shadow.Virtual.ResolutionLodBiasDirectional"),TEXT("1"));SetCVar(TEXT("r.Shadow.Virtual.ResolutionLodBiasLocal"),TEXT("1"));}
    if(Tier>=7)SetCVar(TEXT("r.ScreenPercentage"),TEXT("83"));
    if(Tier>=8)SetCVar(TEXT("r.Lumen.FinalGatherMethod"),TEXT("0"));
    UE_LOG(LogTemp,Display,TEXT("VEYR_LOOK legacy=0 tier=%d lumenSplit=%d"),Tier,SplitInstancesForLumen());
}

void VeyrLook::NotifyCameraCut(UWorld* World)
{
    if(!World)return;
    if(APlayerController* PC=World->GetFirstPlayerController())
        if(PC->PlayerCameraManager)PC->PlayerCameraManager->SetGameCameraCutThisFrame();
}
