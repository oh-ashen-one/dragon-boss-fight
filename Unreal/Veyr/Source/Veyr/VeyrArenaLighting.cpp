// Phase C relit court (2026-11-18). Design and numbers: Local/quality-goal/C-notes.md.
// Cold moon key and a near-black sky above, warm fire below; lit against dark,
// warm against cold. The lights only have to look good, not to have a visible source.
// -VeyrLegacyRender keeps BuildLighting's original body instead.
#include "VeyrArena.h"
#include "VeyrLook.h"
#include "Camera/PlayerCameraManager.h"
#include "Components/DirectionalLightComponent.h"
#include "Components/ExponentialHeightFogComponent.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "Components/PointLightComponent.h"
#include "Components/PostProcessComponent.h"
#include "Components/SkyLightComponent.h"
#include "Components/SpotLightComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "GameFramework/PlayerController.h"
#include "Materials/MaterialInstanceDynamic.h"

namespace
{
    // Fight-area pools: unmotivated warm spots 14 m up, aimed straight down. They put
    // the candle-pool look where the camera spends the fight and catch both fighters'
    // shadows. Knight spawns at x=-1600, the dragon near x=+500..+1800.
    struct FPool{FVector Location;float Candelas;};
    const FPool Pools[]={{FVector(-1500,650,1400),1400.f},{FVector(500,-1050,1400),1400.f},{FVector(2100,1150,1400),1200.f}};
    const FLinearColor MoonColour(.55f,.68f,1.f),RimColour(.62f,.74f,1.f),PoolColour(1.f,.62f,.32f);
}

void AVeyrArena::BuildRelitLighting()
{
    auto MakeDirectional=[&](const TCHAR* Name)
    {
        auto* L=NewObject<UDirectionalLightComponent>(this,Name);
        AddInstanceComponent(L);L->SetupAttachment(GetRootComponent());L->SetMobility(EComponentMobility::Movable);
        return L;
    };
    // Cold key: lower than build 16's -42 deg so shadows rake across the paving; the
    // curtain walls now leave dark bands the fires fill. Real shadows through VSM.
    auto* Moon=MakeDirectional(TEXT("RelitColdMoonKey"));
    Moon->SetRelativeRotation(FRotator(VeyrLook::Tune(TEXT("moonpitch"),-34.f),VeyrLook::Tune(TEXT("moonyaw"),-155.f),0));Moon->SetForwardShadingPriority(1);
    Moon->SetIntensity(VeyrLook::Tune(TEXT("moon"),1.6f));Moon->SetLightColor(MoonColour,false);Moon->SetCastShadows(true);
    Moon->SetLightSourceAngle(1.5f);Moon->SetSpecularScale(.8f);Moon->SetVolumetricScatteringIntensity(1.f);
    Moon->RegisterComponent();

    // Rims re-aimed every tick (TickRelitLighting) to shine from behind the subject
    // toward the camera, 25 deg down: silhouettes read in the dark, no flat front fill.
    // Channel 1 = knight, his props and the dragon; channel 2 = dragon only.
    CharacterRim=MakeDirectional(TEXT("RelitCharacterRim"));
    CharacterRim->LightingChannels.bChannel0=false;CharacterRim->LightingChannels.bChannel1=true;CharacterRim->LightingChannels.bChannel2=false;
    CharacterRim->SetIntensity(VeyrLook::Tune(TEXT("rim"),2.2f));CharacterRim->SetLightColor(RimColour,false);CharacterRim->SetCastShadows(false);
    CharacterRim->SetSpecularScale(1.f);CharacterRim->SetAffectGlobalIllumination(false);CharacterRim->SetVolumetricScatteringIntensity(0.f);
    CharacterRim->RegisterComponent();
    DragonRimLight=MakeDirectional(TEXT("RelitDragonBackRim"));
    DragonRimLight->LightingChannels.bChannel0=false;DragonRimLight->LightingChannels.bChannel1=false;DragonRimLight->LightingChannels.bChannel2=true;
    DragonRimLight->SetIntensity(VeyrLook::Tune(TEXT("drim"),2.5f));DragonRimLight->SetLightColor(FLinearColor(.48f,.67f,1.f),false);DragonRimLight->SetCastShadows(false);
    DragonRimLight->SetSpecularScale(.9f);DragonRimLight->SetAffectGlobalIllumination(false);DragonRimLight->SetVolumetricScatteringIntensity(0.f);
    DragonRimLight->RegisterComponent();

    const float PoolScale=VeyrLook::Tune(TEXT("pool"),1.f);
    for(int32 I=0;I<UE_ARRAY_COUNT(Pools);++I)
    {
        auto* Pool=NewObject<USpotLightComponent>(this,FName(*FString::Printf(TEXT("RelitFloorPool%d"),I)));
        AddInstanceComponent(Pool);Pool->SetupAttachment(GetRootComponent());Pool->SetMobility(EComponentMobility::Movable);
        Pool->SetRelativeLocation(Pools[I].Location);Pool->SetRelativeRotation(FRotator(-90.f,0,0));
        Pool->SetIntensityUnits(ELightUnits::Candelas);Pool->SetIntensity(Pools[I].Candelas*PoolScale);
        Pool->SetLightColor(PoolColour,false);Pool->SetAttenuationRadius(2600.f);
        Pool->SetInnerConeAngle(8.f);Pool->SetOuterConeAngle(32.f);Pool->SetSourceRadius(15.f);
        Pool->SetCastShadows(VeyrLook::FloorPoolShadows());Pool->SetVolumetricScatteringIntensity(1.2f);Pool->SetSpecularScale(.8f);
        Pool->RegisterComponent();
        FortressFireLights.Add(Pool);FortressFireIntensities.Add(Pools[I].Candelas*PoolScale);
    }

    if(SkyMesh&&(NightSkyParent||SkyParent))
    {
        auto* Sky=NewObject<UStaticMeshComponent>(this,TEXT("RelitNightSky"));
        AddInstanceComponent(Sky);Sky->SetupAttachment(GetRootComponent());Sky->SetStaticMesh(SkyMesh);
        Sky->SetCollisionEnabled(ECollisionEnabled::NoCollision);Sky->SetCastShadow(false);Sky->SetCanEverAffectNavigation(false);
        Sky->SetAffectDistanceFieldLighting(false);
        Sky->SetRelativeScale3D(FVector(200000.f/FMath::Max(1.f,static_cast<float>(SkyMesh->GetBounds().SphereRadius))));
        auto* Material=UMaterialInstanceDynamic::Create(NightSkyParent?NightSkyParent.Get():SkyParent.Get(),this);
        Materials.Add(Material);
        const FVector MoonDirection=-Moon->GetForwardVector();
        // Same parameters as build 16, darker: the moonlit clouds were the largest bright
        // area of every fight frame. The sky now sits under the lit walls in value.
        Material->SetVectorParameterValue(TEXT("MoonDirection"),FLinearColor(MoonDirection.X,MoonDirection.Y,MoonDirection.Z,0));
        Material->SetScalarParameterValue(TEXT("CloudOpacity"),.95f);
        Material->SetScalarParameterValue(TEXT("CloudSpeed"),.02f);
        Material->SetScalarParameterValue(TEXT("StarBrightness"),.22f);
        Material->SetVectorParameterValue(TEXT("CloudColor"),FLinearColor(.10f,.12f,.16f));
        Material->SetVectorParameterValue(TEXT("HorizonColor"),FLinearColor(.020f,.026f,.038f));
        Material->SetVectorParameterValue(TEXT("Zenith Color"),FLinearColor(.008f,.013f,.028f));
        Material->SetVectorParameterValue(TEXT("Horizon color"),FLinearColor(.025f,.034f,.050f));
        Material->SetVectorParameterValue(TEXT("Cloud color"),FLinearColor(.05f,.06f,.08f));
        Material->SetVectorParameterValue(TEXT("Overall Color"),FLinearColor::White);
        Material->SetVectorParameterValue(TEXT("Light direction"),FLinearColor(.85f,.32f,.25f,0));
        Material->SetVectorParameterValue(TEXT("Sun color"),FLinearColor(.55f,.66f,.82f));
        Material->SetScalarParameterValue(TEXT("Sun brightness"),.5f);
        Material->SetScalarParameterValue(TEXT("Sun Radius"),.018f);
        Material->SetScalarParameterValue(TEXT("Cloud opacity"),.78f);
        Material->SetScalarParameterValue(TEXT("Cloud speed"),.08f);
        Material->SetScalarParameterValue(TEXT("Stars brightness"),.03f);
        Sky->SetMaterial(0,Material);Sky->RegisterComponent();
    }
    auto* Ambient=NewObject<USkyLightComponent>(this,TEXT("RelitColdSkyAmbient"));
    AddInstanceComponent(Ambient);Ambient->SetupAttachment(GetRootComponent());Ambient->SetMobility(EComponentMobility::Movable);
    Ambient->SourceType=SLS_CapturedScene;Ambient->SetRealTimeCapture(false);Ambient->SkyDistanceThreshold=50000.f;
    Ambient->SetIntensity(VeyrLook::Tune(TEXT("sky"),.45f));Ambient->SetLightColor(FLinearColor(.70f,.80f,1.f));
    Ambient->SetLowerHemisphereColor(FLinearColor(0.f,0.f,0.f));Ambient->RegisterComponent();

    // Haze inside the fight (build 16's fog started at 45 m): fires bloom in the air,
    // the moon draws shafts past the towers and silhouettes separate in depth.
    auto* Fog=NewObject<UExponentialHeightFogComponent>(this,TEXT("RelitCourtHaze"));
    AddInstanceComponent(Fog);Fog->SetupAttachment(GetRootComponent());Fog->SetRelativeLocation(FVector(0,0,-150));
    Fog->SetFogDensity(VeyrLook::Tune(TEXT("fog"),.020f));Fog->SetFogHeightFalloff(.30f);Fog->SetStartDistance(0.f);Fog->SetFogMaxOpacity(.97f);
    Fog->SetFogInscatteringColor(FLinearColor(.020f,.025f,.035f)*VeyrLook::Tune(TEXT("fogcolor"),1.f));
    Fog->SetSecondFogDensity(VeyrLook::Tune(TEXT("fog2"),.012f));Fog->SetSecondFogHeightOffset(240.f);Fog->SetSecondFogHeightFalloff(1.2f);
    Fog->SetVolumetricFog(true);Fog->SetVolumetricFogScatteringDistribution(.45f);
    Fog->SetVolumetricFogAlbedo(FColor(230,218,205));Fog->SetVolumetricFogExtinctionScale(VeyrLook::Tune(TEXT("fogext"),.9f));
    Fog->SetVolumetricFogDistance(9000.f);
    Fog->RegisterComponent();

    CourtGrade=NewObject<UPostProcessComponent>(this,TEXT("RelitCandlelitGrade"));
    AddInstanceComponent(CourtGrade);CourtGrade->SetupAttachment(GetRootComponent());CourtGrade->bUnbound=true;
    FPostProcessSettings& S=CourtGrade->Settings;
    // Bounded eye adaptation in EV100 (ExtendDefaultLuminanceRange=True). Metered on the
    // bright end of the histogram so the lit pools set exposure and the shadows stay dark.
    // Min stops a dark corner lifting to grey. Max must sit well above the court so the camera
    // can stop down for the breath (25k lm, +2.6 stops on build 16): at 1 EV100 it could only go
    // 1.6 stops darker than build 16's manual exposure; 3.5 EV100 gives about 4 stops.
    S.bOverride_AutoExposureMethod=true;S.AutoExposureMethod=AEM_Histogram;
    S.bOverride_AutoExposureApplyPhysicalCameraExposure=true;S.AutoExposureApplyPhysicalCameraExposure=false;
    S.bOverride_AutoExposureBias=true;S.AutoExposureBias=VeyrLook::Tune(TEXT("bias"),-.6f);
    S.bOverride_AutoExposureMinBrightness=true;S.AutoExposureMinBrightness=VeyrLook::Tune(TEXT("evmin"),-3.5f);
    S.bOverride_AutoExposureMaxBrightness=true;S.AutoExposureMaxBrightness=VeyrLook::Tune(TEXT("evmax"),3.5f);
    S.bOverride_AutoExposureLowPercent=true;S.AutoExposureLowPercent=VeyrLook::Tune(TEXT("lowpct"),65.f);
    S.bOverride_AutoExposureHighPercent=true;S.AutoExposureHighPercent=VeyrLook::Tune(TEXT("highpct"),97.f);
    S.bOverride_AutoExposureSpeedUp=true;S.AutoExposureSpeedUp=2.f;
    S.bOverride_AutoExposureSpeedDown=true;S.AutoExposureSpeedDown=1.2f;
    S.bOverride_HistogramLogMin=true;S.HistogramLogMin=-8.f;
    S.bOverride_HistogramLogMax=true;S.HistogramLogMax=8.f;
    S.bOverride_LocalExposureHighlightContrastScale=true;S.LocalExposureHighlightContrastScale=VeyrLook::Tune(TEXT("lehc"),.75f);
    S.bOverride_LocalExposureShadowContrastScale=true;S.LocalExposureShadowContrastScale=VeyrLook::Tune(TEXT("lesc"),1.f);
    S.bOverride_BloomIntensity=true;S.BloomIntensity=VeyrLook::Tune(TEXT("bloom"),.45f);
    S.bOverride_VignetteIntensity=true;S.VignetteIntensity=VeyrLook::Tune(TEXT("vignette"),.38f);
    S.bOverride_ColorContrast=true;const float Contrast=VeyrLook::Tune(TEXT("contrast"),1.08f);S.ColorContrast=FVector4(Contrast,Contrast,Contrast,1.f);
    S.bOverride_ColorSaturation=true;const float Saturation=VeyrLook::Tune(TEXT("sat"),.95f);S.ColorSaturation=FVector4(Saturation,Saturation,Saturation,1.f);
    S.bOverride_ColorGainShadows=true;const float Split=VeyrLook::Tune(TEXT("split"),1.f); // 0 = no split tone, 2 = double
    S.ColorGainShadows=FVector4(1.f-.07f*Split,1.f-.03f*Split,1.f+.08f*Split,1.f);
    S.bOverride_ColorGainHighlights=true;S.ColorGainHighlights=FVector4(1.f+.06f*Split,1.f,1.f-.08f*Split,1.f);
    S.bOverride_FilmToe=true;S.FilmToe=VeyrLook::Tune(TEXT("toe"),.60f);
    S.bOverride_MotionBlurAmount=true;S.MotionBlurAmount=VeyrLook::MotionBlur()?VeyrLook::Tune(TEXT("mb"),.35f):0.f; // -VeyrNoMotionBlur
    S.bOverride_MotionBlurMax=true;S.MotionBlurMax=3.f;
    S.bOverride_MotionBlurPerObjectSize=true;S.MotionBlurPerObjectSize=0.f;
    CourtGrade->RegisterComponent();
    Ambient->RecaptureSky();
    UE_LOG(LogTemp,Display,TEXT("VEYR_LOOK_COURT relit pools=%d poolShadows=%d fires=%d braziers=%d brazierShadowBudget=%d"),
        UE_ARRAY_COUNT(Pools),VeyrLook::FloorPoolShadows(),FortressFireLights.Num(),BrazierLights.Num(),FMath::Min(BrazierLights.Num(),VeyrLook::ShadowedFireBudget()));
}

void AVeyrArena::SplitCourtInstancesForLumen()
{
    // Epic (Lumen Technical Details): "Foliage and Instanced Static Mesh Components can only
    // be supported if the mesh is using Nanite." The court meshes are non-Nanite ISMs, so the
    // walls and paving would have no Lumen surface cache (no bounce, black in reflections).
    // Shadow-casting instances become plain static mesh components; each source ISM stays
    // registered, hidden, for its collision. Distant non-shadow masses stay instanced.
    int32 Batched=0,Parts=0;
    for(UInstancedStaticMeshComponent* Batch:Batches)
    {
        if(!Batch||!Batch->GetStaticMesh()||!Batch->CastShadow||!Batch->IsVisible()||Batch->GetInstanceCount()==0)continue;
        ++Batched;
        for(int32 I=0;I<Batch->GetInstanceCount();++I)
        {
            FTransform World;
            if(!Batch->GetInstanceTransform(I,World,true))continue;
            auto* Part=NewObject<UStaticMeshComponent>(this);
            AddInstanceComponent(Part);Part->SetupAttachment(GetRootComponent());Part->SetMobility(EComponentMobility::Static);
            Part->SetStaticMesh(Batch->GetStaticMesh());
            for(int32 Slot=0;Slot<Batch->GetNumMaterials();++Slot)Part->SetMaterial(Slot,Batch->GetMaterial(Slot));
            Part->SetWorldTransform(World);
            Part->SetForcedLodModel(Batch->ForcedLodModel);
            Part->SetCollisionEnabled(ECollisionEnabled::NoCollision);Part->SetGenerateOverlapEvents(false);Part->SetCanEverAffectNavigation(false);
            Part->LightingChannels=Batch->LightingChannels;
            Part->RegisterComponent();LumenSplitParts.Add(Part);++Parts;
        }
        Batch->SetVisibility(false);
    }
    UE_LOG(LogTemp,Display,TEXT("VEYR_LOOK_LUMEN_SPLIT batches=%d components=%d"),Batched,Parts);
}

void AVeyrArena::TickRelitLighting(float DeltaSeconds)
{
    // Fire flicker: two incommensurate sines plus a fast shimmer per light, +-12 %.
    for(int32 I=0;I<FortressFireLights.Num();++I)if(FortressFireLights[I])
    {
        const float T=AtmosphereClock;
        const float Flicker=.90f+.06f*FMath::Sin(T*2.9f+I*1.9f)+.04f*FMath::Sin(T*7.7f+I*2.3f)+.02f*FMath::Sin(T*17.f+I);
        FortressFireLights[I]->SetIntensity(FortressFireIntensities[I]*Flicker);
    }
    const APlayerController* PC=GetWorld()?GetWorld()->GetFirstPlayerController():nullptr;
    if(!PC||!PC->PlayerCameraManager)return;
    BrazierShadowClock-=DeltaSeconds;
    if(BrazierShadowClock<=0.f){BrazierShadowClock=.5f;UpdateBrazierShadowBudget(PC->PlayerCameraManager->GetCameraLocation());}
}

void AVeyrArena::AimRelitRims()
{
    const APlayerController* PC=GetWorld()?GetWorld()->GetFirstPlayerController():nullptr;
    if(!PC||!PC->PlayerCameraManager)return;
    const float CameraYaw=PC->PlayerCameraManager->GetCameraRotation().Yaw;
    // A directional light's rotation is its travel direction: from behind the subject toward the camera.
    if(CharacterRim)CharacterRim->SetWorldRotation(FRotator(-25.f,CameraYaw+180.f+20.f,0));
    if(DragonRimLight)DragonRimLight->SetWorldRotation(FRotator(-30.f,CameraYaw+180.f-35.f,0));
}

void AVeyrArena::UpdateBrazierShadowBudget(const FVector& Camera)
{
    const int32 Budget=VeyrLook::ShadowedFireBudget();
    if(Budget>=BrazierLights.Num())return; // tiers 0-1: every brazier keeps its shadow
    // Rank by distance to the camera; a lit brazier gets a 20 % head start so two at
    // nearly equal range do not swap shadows (and drop their VSM cache) every half second.
    TArray<TPair<double,int32>> Order;
    for(int32 I=0;I<BrazierLights.Num();++I)if(BrazierLights[I])
    {
        double D=FVector::DistSquared(BrazierLights[I]->GetComponentLocation(),Camera);
        if(BrazierLights[I]->CastShadows)D*=.64;
        Order.Emplace(D,I);
    }
    Order.Sort([](const TPair<double,int32>& A,const TPair<double,int32>& B){return A.Key<B.Key;});
    for(int32 Rank=0;Rank<Order.Num();++Rank)
    {
        UPointLightComponent* Light=BrazierLights[Order[Rank].Value];
        const bool bWant=Rank<Budget;
        if(Light->CastShadows!=bWant)Light->SetCastShadows(bWant);
    }
}

int32 AVeyrArena::CountShadowedCourtLights() const
{
    int32 Count=0;
    for(const UPointLightComponent* Light:FortressFireLights)Count+=Light&&Light->CastShadows&&Light->IsVisible();
    return Count;
}
