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
    return bSplit&&RenderTier()<6;
}

int32 VeyrLook::RenderTier()
{
    static const int32 Tier=[]{int32 T=0;FParse::Value(FCommandLine::Get(),TEXT("VeyrRenderTier="),T);return FMath::Clamp(T,0,10);}();
    return IsLegacy()?0:Tier;
}

bool VeyrLook::BreathShadow()
{
    return !IsLegacy()&&RenderTier()<1;
}

bool VeyrLook::FloorPoolShadows()
{
    return RenderTier()<2;
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
    // Twelve shadowed braziers and three pools can overlap one pixel near the walls.
    SetCVar(TEXT("r.Shadow.Virtual.OnePassProjection.MaxLightsPerPixel"),TEXT("32"));
    const int32 Tier=RenderTier();
    // Cumulative fallback steps, biggest cost per visual loss first (C-notes "Scalability fallback").
    // 1 breath shadow off (BreathShadow), 2 pools unshadowed + 4 nearest braziers
    // (FloorPoolShadows, ShadowedFireBudget) and 6 Lumen split off (SplitInstancesForLumen)
    // are read by the dragon effects and the arena; the rest are cvars.
    if(Tier>=3){SetCVar(TEXT("r.VolumetricFog.GridPixelSize"),TEXT("16"));SetCVar(TEXT("r.VolumetricFog.GridSizeZ"),TEXT("64"));}
    if(Tier>=4){SetCVar(TEXT("r.Lumen.Reflections.DownsampleFactor"),TEXT("2"));SetCVar(TEXT("r.Lumen.Reflections.MaxRoughnessToTraceClamp"),TEXT("0.3"));}
    if(Tier>=5){SetCVar(TEXT("r.Lumen.ScreenProbeGather.DownsampleFactor"),TEXT("32"));SetCVar(TEXT("r.Lumen.ScreenProbeGather.TracingOctahedronResolution"),TEXT("6"));}
    if(Tier>=7){SetCVar(TEXT("sg.GlobalIlluminationQuality"),TEXT("2"));SetCVar(TEXT("sg.ReflectionQuality"),TEXT("2"));SetCVar(TEXT("r.Lumen.Reflections.Allow"),TEXT("0"));}
    if(Tier>=8){SetCVar(TEXT("r.Shadow.Virtual.ResolutionLodBiasDirectional"),TEXT("1"));SetCVar(TEXT("r.Shadow.Virtual.ResolutionLodBiasLocal"),TEXT("1"));}
    if(Tier>=9)SetCVar(TEXT("r.ScreenPercentage"),TEXT("83"));
    if(Tier>=10)SetCVar(TEXT("r.Lumen.FinalGatherMethod"),TEXT("0"));
    UE_LOG(LogTemp,Display,TEXT("VEYR_LOOK legacy=0 tier=%d breathShadow=%d poolShadows=%d fireBudget=%d lumenSplit=%d"),
        Tier,BreathShadow(),FloorPoolShadows(),ShadowedFireBudget(),SplitInstancesForLumen());
}

void VeyrLook::NotifyCameraCut(UWorld* World)
{
    if(!World)return;
    if(APlayerController* PC=World->GetFirstPlayerController())
        if(PC->PlayerCameraManager)PC->PlayerCameraManager->SetGameCameraCutThisFrame();
}
