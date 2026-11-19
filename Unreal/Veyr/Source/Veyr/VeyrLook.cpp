#include "VeyrLook.h"
#include "Camera/PlayerCameraManager.h"
#include "Components/PrimitiveComponent.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Materials/MaterialInterface.h"
#include "SceneView.h"
#include "SceneViewExtension.h"
#include <atomic>
#include "Engine/World.h"
#include "GameFramework/PlayerController.h"
#include "HAL/IConsoleManager.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"

namespace
{
    std::atomic<float> GLastExposure{0.f},GLastLuminance{0.f};

    /** Reads the game view's eye-adaptation exposure on the render thread (no game-thread access to it). */
    class FVeyrExposureProbe final : public FSceneViewExtensionBase
    {
    public:
        FVeyrExposureProbe(const FAutoRegister& Register):FSceneViewExtensionBase(Register){}
        virtual void PostRenderView_RenderThread(FRDGBuilder& GraphBuilder,FSceneView& View) override
        {
            if(!View.bIsGameView)return;
            const float Exposure=View.GetLastEyeAdaptationExposure();
            if(Exposure>0.f){GLastExposure.store(Exposure,std::memory_order_relaxed);GLastLuminance.store(View.GetLastAverageSceneLuminance(),std::memory_order_relaxed);}
        }
    };
    TSharedPtr<FVeyrExposureProbe,ESPMode::ThreadSafe> GExposureProbe;

    struct FFollower { TWeakObjectPtr<UMaterialInstanceDynamic> Mid; FName Param; float Base=0.f; };
    TArray<FFollower> GFollowers;
    float GAppliedGain=1.f;

    void ApplyFollowers(UWorld* World,ELevelTick,float)
    {
        if(!World||!World->IsGameWorld())return;
        const float Gain=VeyrLook::FxExposureGain();
        if(FMath::Abs(Gain/GAppliedGain-1.f)<.02f)return;
        GAppliedGain=Gain;
        GFollowers.RemoveAll([](const FFollower& F){return !F.Mid.IsValid();});
        for(const FFollower& F:GFollowers)F.Mid->SetScalarParameterValue(F.Param,F.Base*Gain);
    }

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
    // Exposure readback for the reports in both looks; the FX follow only in the new one.
    GExposureProbe=FSceneViewExtensions::NewExtension<FVeyrExposureProbe>();
    FWorldDelegates::OnWorldPostActorTick.AddStatic(&ApplyFollowers);
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
    UE_LOG(LogTemp,Display,TEXT("VEYR_LOOK legacy=0 tier=%d breathShadow=%d poolShadows=%d fireBudget=%d lumenSplit=%d motionBlur=%d fxExposureLock=%.2f"),
        Tier,BreathShadow(),FloorPoolShadows(),ShadowedFireBudget(),SplitInstancesForLumen(),MotionBlur(),FxExposureLock());
}

void VeyrLook::NotifyCameraCut(UWorld* World)
{
    if(!World)return;
    if(APlayerController* PC=World->GetFirstPlayerController())
        if(PC->PlayerCameraManager)PC->PlayerCameraManager->SetGameCameraCutThisFrame();
}

float VeyrLook::Tune(const TCHAR* Key,float Default)
{
    static const TMap<FString,float> Values=[]{
        TMap<FString,float> Out;FString Text;
        if(FParse::Value(FCommandLine::Get(),TEXT("VeyrTune="),Text,false))
        {
            TArray<FString> Items;Text.ParseIntoArray(Items,TEXT(","));
            for(const FString& Item:Items){FString K,V;if(Item.Split(TEXT("="),&K,&V))Out.Add(K.ToLower(),FCString::Atof(*V));}
        }
        return Out;}();
    const float* Found=Values.Find(FString(Key).ToLower());
    const float Value=Found?*Found:Default;
    if(Found)UE_LOG(LogTemp,Display,TEXT("VEYR_LOOK_TUNE %s=%g (default %g)"),Key,Value,Default);
    return Value;
}

bool VeyrLook::MotionBlur()
{
    static const bool bBlur=!FParse::Param(FCommandLine::Get(),TEXT("VeyrNoMotionBlur"));
    return bBlur;
}

float VeyrLook::LastExposure(){return GLastExposure.load(std::memory_order_relaxed);}
float VeyrLook::LastSceneLuminance(){return GLastLuminance.load(std::memory_order_relaxed);}

float VeyrLook::FxExposureLock()
{
    static const float Lock=[]{
        float L=.5f;FParse::Value(FCommandLine::Get(),TEXT("VeyrFxExposureLock="),L);
        if(FParse::Param(FCommandLine::Get(),TEXT("VeyrNoFxExposureFollow")))L=0.f;
        return FMath::Clamp(L,0.f,1.f);}();
    return IsLegacy()?0.f:Lock;
}

float VeyrLook::FxExposureGain()
{
    const float Lock=FxExposureLock(),Exposure=LastExposure();
    if(Lock<=0.f||Exposure<=0.f)return 1.f;
    // Build 16: AEM_Manual, bias 0 -> 1/1.2. -VeyrFxRefExposure= moves the point the FX were tuned at.
    static const float Reference=[]{float R=1.f/1.2f;FParse::Value(FCommandLine::Get(),TEXT("VeyrFxRefExposure="),R);return FMath::Max(.001f,R);}();
    return FMath::Clamp(FMath::Pow(Reference/Exposure,Lock),1.f/16.f,16.f);
}

void VeyrLook::FollowExposure(UMaterialInstanceDynamic* Mid,FName Param,float Base)
{
    if(!Mid||FxExposureLock()<=0.f)return;
    for(FFollower& F:GFollowers)if(F.Mid.Get()==Mid&&F.Param==Param){F.Base=Base;Mid->SetScalarParameterValue(Param,Base*GAppliedGain);return;}
    GFollowers.Add({Mid,Param,Base});
    Mid->SetScalarParameterValue(Param,Base*GAppliedGain);
}

int32 VeyrLook::FollowExposureAuto(UMaterialInstanceDynamic* Mid)
{
    if(!Mid||FxExposureLock()<=0.f||!Mid->GetShadingModels().IsUnlit())return 0;
    TArray<FMaterialParameterInfo> Infos;TArray<FGuid> Ids;
    Mid->GetAllScalarParameterInfo(Infos,Ids);
    int32 Count=0;FString Names;
    for(const FMaterialParameterInfo& Info:Infos)
    {
        const FString Name=Info.Name.ToString().ToLower();
        if(!(Name.Contains(TEXT("emiss"))||Name.Contains(TEXT("intens"))||Name.Contains(TEXT("bright"))||Name.Contains(TEXT("glow"))||Name.Contains(TEXT("hdr"))))continue;
        if(Name.Contains(TEXT("power"))||Name.Contains(TEXT("exponent")))continue; // shape, not strength
        float Base=0.f;
        if(!Mid->GetScalarParameterValue(FHashedMaterialParameterInfo(Info),Base))continue;
        FollowExposure(Mid,Info.Name,Base);++Count;Names+=Info.Name.ToString()+TEXT(" ");
    }
    UE_LOG(LogTemp,Display,TEXT("VEYR_LOOK_FX_FOLLOW %s params=%d %s"),*GetNameSafe(Mid->Parent),Count,*Names);
    return Count;
}

int32 VeyrLook::FollowExposureOnComponent(UPrimitiveComponent* Component,UObject* Outer,TMap<UMaterialInterface*,UMaterialInstanceDynamic*>& Cache)
{
    if(!Component||FxExposureLock()<=0.f)return 0;
    int32 Wired=0;
    for(int32 Slot=0;Slot<Component->GetNumMaterials();++Slot)
    {
        UMaterialInterface* Source=Component->GetMaterial(Slot);
        if(!Source||!Source->GetShadingModels().IsUnlit())continue;
        UMaterialInstanceDynamic* Mid=nullptr;
        if(UMaterialInstanceDynamic** Found=Cache.Find(Source))Mid=*Found;
        else
        {
            Mid=UMaterialInstanceDynamic::Create(Source,Outer);
            if(Mid&&FollowExposureAuto(Mid)==0)Mid=nullptr; // nothing to scale: keep the source material
            Cache.Add(Source,Mid);
        }
        if(Mid){Component->SetMaterial(Slot,Mid);++Wired;}
    }
    return Wired;
}
