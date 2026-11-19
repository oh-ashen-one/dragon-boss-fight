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
#include "EngineUtils.h"
#include "VeyrDragon.h"
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
    Moon->SetIntensity(VeyrLook::Tune(TEXT("moon"),.5f));Moon->SetLightColor(MoonColour,false);Moon->SetCastShadows(true);
    Moon->SetLightSourceAngle(VeyrLook::Tune(TEXT("moonangle"),4.f)); // blind review 2: hard stencil edges on the moon patchesMoon->SetSpecularScale(VeyrLook::Tune(TEXT("moonspec"),1.3f));Moon->SetVolumetricScatteringIntensity(1.f);
    Moon->RegisterComponent();

    // Rims re-aimed every tick (TickRelitLighting) to shine from behind the subject
    // toward the camera, 25 deg down: silhouettes read in the dark, no flat front fill.
    // Channel 1 = knight, his props and the dragon; channel 2 = dragon only.
    CharacterRim=MakeDirectional(TEXT("RelitCharacterRim"));
    CharacterRim->LightingChannels.bChannel0=false;CharacterRim->LightingChannels.bChannel1=true;CharacterRim->LightingChannels.bChannel2=false;
    CharacterRim->SetIntensity(VeyrLook::Tune(TEXT("rim"),14.f));CharacterRim->SetLightColor(RimColour,false);CharacterRim->SetCastShadows(false);
    CharacterRim->SetSpecularScale(1.f);CharacterRim->SetAffectGlobalIllumination(false);CharacterRim->SetVolumetricScatteringIntensity(0.f);
    CharacterRim->RegisterComponent();
    DragonRimLight=MakeDirectional(TEXT("RelitDragonBackRim"));
    DragonRimLight->LightingChannels.bChannel0=false;DragonRimLight->LightingChannels.bChannel1=false;DragonRimLight->LightingChannels.bChannel2=true;
    DragonRimLight->SetIntensity(VeyrLook::Tune(TEXT("drim"),7.f));DragonRimLight->SetLightColor(FLinearColor(.48f,.67f,1.f),false);DragonRimLight->SetCastShadows(false);
    DragonRimLight->SetSpecularScale(.9f);DragonRimLight->SetAffectGlobalIllumination(false);DragonRimLight->SetVolumetricScatteringIntensity(0.f);
    DragonRimLight->RegisterComponent();

    // Subject keys (review 2026-11-19: "the boss and the hero are the best-lit things in the frame"). The rims
    // alone left a black shape with a thin edge. Each key lights only its subject (no visible source needed):
    // channel 2 = dragon, channel 1 = knight and props once the dragon leaves channel 1 (SplitDragonLightingChannel).
    // Re-aimed every tick from the camera side and high, so scales, horns, membranes and armour plates read in
    // every view. Unshadowed: no VSM pages, the form comes from the normals. -VeyrNoSubjectKeys turns both off.
    if(!FParse::Param(FCommandLine::Get(),TEXT("VeyrNoSubjectKeys")))
    {
        DragonKeyLight=MakeDirectional(TEXT("RelitDragonKey"));
        DragonKeyLight->LightingChannels.bChannel0=false;DragonKeyLight->LightingChannels.bChannel1=false;DragonKeyLight->LightingChannels.bChannel2=true;
        // Blind review 2: a pale pink flat fill on legs and tail. Cooler, from higher, harder: tops and backs lit, flanks fall off.
        DragonKeyLight->SetIntensity(VeyrLook::Tune(TEXT("dkey"),2.4f));DragonKeyLight->SetLightColor(FLinearColor(.66f,.78f,1.f),false);DragonKeyLight->SetCastShadows(false);
        DragonKeyLight->SetLightSourceAngle(2.f);DragonKeyLight->SetSpecularScale(VeyrLook::Tune(TEXT("dkeyspec"),.9f));DragonKeyLight->SetAffectGlobalIllumination(false);DragonKeyLight->SetVolumetricScatteringIntensity(0.f);
        DragonKeyLight->RegisterComponent();
        KnightKeyLight=MakeDirectional(TEXT("RelitKnightKey"));
        KnightKeyLight->LightingChannels.bChannel0=false;KnightKeyLight->LightingChannels.bChannel1=true;KnightKeyLight->LightingChannels.bChannel2=false;
        KnightKeyLight->SetIntensity(VeyrLook::Tune(TEXT("kkey"),4.f));KnightKeyLight->SetLightColor(FLinearColor(1.f,.87f,.72f),false);KnightKeyLight->SetCastShadows(false);
        KnightKeyLight->SetLightSourceAngle(10.f);KnightKeyLight->SetSpecularScale(VeyrLook::Tune(TEXT("kkeyspec"),1.5f));KnightKeyLight->SetAffectGlobalIllumination(false);KnightKeyLight->SetVolumetricScatteringIntensity(0.f);
        KnightKeyLight->RegisterComponent();
    }

    const float PoolScale=VeyrLook::Tune(TEXT("pool"),2.f);
    // Floor fill (blind review 1: "the floor under the hero is a void"): a wide, cool, unshadowed spot that
    // rides above the camera and looks down at the floor ahead, so the paving in front of the knight never
    // falls to black. Court channel only, low specular so it adds no fake glints. -VeyrTune=floorfill=
    FloorFillLight=NewObject<USpotLightComponent>(this,TEXT("RelitFloorFill"));
    AddInstanceComponent(FloorFillLight);FloorFillLight->SetupAttachment(GetRootComponent());FloorFillLight->SetMobility(EComponentMobility::Movable);
    FloorFillLight->SetIntensityUnits(ELightUnits::Candelas);FloorFillLight->SetIntensity(VeyrLook::Tune(TEXT("floorfill"),25.f));
    FloorFillLight->SetLightColor(FLinearColor(.62f,.72f,1.f),false);FloorFillLight->SetAttenuationRadius(2600.f);
    FloorFillLight->SetInnerConeAngle(20.f);FloorFillLight->SetOuterConeAngle(62.f);FloorFillLight->SetCastShadows(false);
    FloorFillLight->SetSpecularScale(.35f);FloorFillLight->SetAffectGlobalIllumination(false);FloorFillLight->SetVolumetricScatteringIntensity(0.f);
    FloorFillLight->RegisterComponent();
    // Warm up-light under the dragon: the braziers' and the breath's light reaching its belly and legs.
    DragonBellyLight=NewObject<UPointLightComponent>(this,TEXT("RelitDragonBellyGlow"));
    AddInstanceComponent(DragonBellyLight);DragonBellyLight->SetupAttachment(GetRootComponent());DragonBellyLight->SetMobility(EComponentMobility::Movable);
    DragonBellyLight->LightingChannels.bChannel0=false;DragonBellyLight->LightingChannels.bChannel1=false;DragonBellyLight->LightingChannels.bChannel2=true;
    BellyBase=VeyrLook::Tune(TEXT("belly"),180.f);BellyBreath=VeyrLook::Tune(TEXT("bellybreath"),2200.f);BellyLevel=BellyBase;
    DragonBellyLight->SetIntensityUnits(ELightUnits::Candelas);DragonBellyLight->SetIntensity(BellyBase);
    DragonBellyLight->SetLightColor(FLinearColor(1.f,.55f,.25f),false);DragonBellyLight->SetAttenuationRadius(VeyrLook::Tune(TEXT("bellyradius"),1500.f));
    DragonBellyLight->SetSourceRadius(120.f);DragonBellyLight->SetCastShadows(false);DragonBellyLight->SetAffectGlobalIllumination(false);
    DragonBellyLight->SetVolumetricScatteringIntensity(0.f);DragonBellyLight->RegisterComponent();
    // Focal gate behind the dragon's usual ground (east gatehouse): a brighter warm niche the eye goes to.
    {
        auto* Gate=NewObject<USpotLightComponent>(this,TEXT("RelitFocalGate"));
        AddInstanceComponent(Gate);Gate->SetupAttachment(GetRootComponent());Gate->SetMobility(EComponentMobility::Movable);
        const FVector From(3100.f,0.f,1500.f),To(5050.f,0.f,420.f);
        Gate->SetRelativeLocation(From);Gate->SetRelativeRotation((To-From).Rotation());
        Gate->SetIntensityUnits(ELightUnits::Candelas);Gate->SetIntensity(VeyrLook::Tune(TEXT("gate"),2600.f));
        Gate->SetLightColor(FLinearColor(1.f,.62f,.32f),false);Gate->SetAttenuationRadius(4200.f);
        Gate->SetInnerConeAngle(10.f);Gate->SetOuterConeAngle(26.f);Gate->SetCastShadows(false);Gate->SetVolumetricScatteringIntensity(VeyrLook::Tune(TEXT("gatefog"),0.f));
        Gate->RegisterComponent();
    }
    BuildDepthDressing();

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
    Ambient->SetIntensity(VeyrLook::Tune(TEXT("sky"),.5f));Ambient->SetLightColor(FLinearColor(.70f,.80f,1.f));
    Ambient->SetLowerHemisphereColor(FLinearColor(0.f,0.f,0.f));Ambient->RegisterComponent();

    // Haze inside the fight (build 16's fog started at 45 m): fires bloom in the air,
    // the moon draws shafts past the towers and silhouettes separate in depth.
    auto* Fog=NewObject<UExponentialHeightFogComponent>(this,TEXT("RelitCourtHaze"));
    AddInstanceComponent(Fog);Fog->SetupAttachment(GetRootComponent());Fog->SetRelativeLocation(FVector(0,0,-150));
    Fog->SetFogDensity(VeyrLook::Tune(TEXT("fog"),.020f));Fog->SetFogHeightFalloff(.30f);Fog->SetStartDistance(0.f);Fog->SetFogMaxOpacity(.97f);
    Fog->SetFogInscatteringColor(FLinearColor(.020f,.025f,.035f)*VeyrLook::Tune(TEXT("fogcolor"),1.f));
    Fog->SetSecondFogDensity(VeyrLook::Tune(TEXT("fog2"),.02f));Fog->SetSecondFogHeightOffset(240.f);Fog->SetSecondFogHeightFalloff(1.2f);
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
    S.bOverride_AutoExposureBias=true;S.AutoExposureBias=VeyrLook::Tune(TEXT("bias"),-.4f);
    S.bOverride_AutoExposureMinBrightness=true;S.AutoExposureMinBrightness=VeyrLook::Tune(TEXT("evmin"),-3.5f);
    S.bOverride_AutoExposureMaxBrightness=true;S.AutoExposureMaxBrightness=VeyrLook::Tune(TEXT("evmax"),3.5f);
    S.bOverride_AutoExposureLowPercent=true;S.AutoExposureLowPercent=VeyrLook::Tune(TEXT("lowpct"),50.f);
    S.bOverride_AutoExposureHighPercent=true;S.AutoExposureHighPercent=VeyrLook::Tune(TEXT("highpct"),88.f);
    S.bOverride_AutoExposureSpeedUp=true;S.AutoExposureSpeedUp=2.f;
    S.bOverride_AutoExposureSpeedDown=true;S.AutoExposureSpeedDown=1.2f;
    S.bOverride_HistogramLogMin=true;S.HistogramLogMin=-8.f;
    S.bOverride_HistogramLogMax=true;S.HistogramLogMax=8.f;
    S.bOverride_LocalExposureHighlightContrastScale=true;S.LocalExposureHighlightContrastScale=VeyrLook::Tune(TEXT("lehc"),.9f);
    S.bOverride_LocalExposureShadowContrastScale=true;S.LocalExposureShadowContrastScale=VeyrLook::Tune(TEXT("lesc"),.8f);
    S.bOverride_BloomIntensity=true;S.BloomIntensity=VeyrLook::Tune(TEXT("bloom"),.6f);
    S.bOverride_VignetteIntensity=true;S.VignetteIntensity=VeyrLook::Tune(TEXT("vignette"),.38f);
    S.bOverride_ColorContrast=true;const float Contrast=VeyrLook::Tune(TEXT("contrast"),1.18f);S.ColorContrast=FVector4(Contrast,Contrast,Contrast,1.f);
    S.bOverride_ColorSaturation=true;const float Saturation=VeyrLook::Tune(TEXT("sat"),.95f);S.ColorSaturation=FVector4(Saturation,Saturation,Saturation,1.f);
    S.bOverride_ColorGainShadows=true;const float Split=VeyrLook::Tune(TEXT("split"),.3f); // 0 = no split tone, 2 = double
    S.ColorGainShadows=FVector4(1.f-.07f*Split,1.f-.03f*Split,1.f+.08f*Split,1.f);
    S.bOverride_ColorGainHighlights=true;S.ColorGainHighlights=FVector4(1.f+.06f*Split,1.f,1.f-.08f*Split,1.f);
    S.bOverride_FilmToe=true;S.FilmToe=VeyrLook::Tune(TEXT("toe"),.60f);
    S.bOverride_MotionBlurAmount=true;S.MotionBlurAmount=VeyrLook::MotionBlur()?VeyrLook::Tune(TEXT("mb"),.12f):0.f; // -VeyrNoMotionBlur
    S.bOverride_MotionBlurMax=true;S.MotionBlurMax=VeyrLook::Tune(TEXT("mbmax"),1.5f); // blind review: one smeared frame
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
    // Keys travel away from the camera side: dragon from high front-left, knight from front-right, lower.
    static const float DragonKeyPitch=VeyrLook::Tune(TEXT("dkeypitch"),-62.f),DragonKeyYaw=VeyrLook::Tune(TEXT("dkeyyaw"),32.f);
    static const float KnightKeyPitch=VeyrLook::Tune(TEXT("kkeypitch"),-32.f),KnightKeyYaw=VeyrLook::Tune(TEXT("kkeyyaw"),-38.f);
    if(DragonKeyLight)DragonKeyLight->SetWorldRotation(FRotator(DragonKeyPitch,CameraYaw+DragonKeyYaw,0));
    if(KnightKeyLight)KnightKeyLight->SetWorldRotation(FRotator(KnightKeyPitch,CameraYaw+KnightKeyYaw,0));
    if(KnightKeyLight&&!ChannelSplitDragon.IsValid())SplitDragonLightingChannel();
    if(FloorFillLight)
    {
        const FVector Eye=PC->PlayerCameraManager->GetCameraLocation();
        // Blind review 2: near cobbles still crushed in low/close and high-looking-down views. Aim at the floor
        // 3.5 m ahead of the camera (the bottom third of the frame) and hold a constant illuminance there
        // (`floorfilllux`), so it fills the dragon's shadow under the hero whatever the camera height.
        const FVector Ahead=FRotator(0,CameraYaw,0).Vector();
        const FVector Target(Eye.X+Ahead.X*350.f,Eye.Y+Ahead.Y*350.f,0.f);
        const FVector From=Eye+FVector(0,0,500.f)-Ahead*150.f;
        static const float Lux=VeyrLook::Tune(TEXT("floorfilllux"),.9f);
        const float Metres=FVector::Dist(From,Target)/100.f;
        FloorFillLight->SetWorldLocationAndRotation(From,(Target-From).Rotation());
        FloorFillLight->SetIntensity(FMath::Clamp(Lux*Metres*Metres,15.f,140.f));
    }
    if(DragonBellyLight)
        if(const AVeyrDragon* Dragon=Cast<AVeyrDragon>(ChannelSplitDragon.Get()))
        {
            const bool bBreath=Dragon->Move==EVeyrDragonMove::Fire&&Dragon->State==EVeyrDragonState::Active;
            const float Dt=GetWorld()->GetDeltaSeconds();
            BellyLevel=FMath::FInterpTo(BellyLevel,bBreath?BellyBase+BellyBreath:BellyBase,Dt,bBreath?10.f:3.f);
            FVector At=Dragon->GetActorLocation();At.Z=70.f;
            DragonBellyLight->SetWorldLocation(At);DragonBellyLight->SetIntensity(BellyLevel*(1.f+.08f*FMath::Sin(GetWorld()->GetTimeSeconds()*17.f)));
        }
}

void AVeyrArena::BuildDepthDressing()
{
    // Blind review 1: "one flat wall at one distance". Silhouettes in front of the lit walls, all from the
    // project's own Tripo kit, collision off, at the court edges outside the fight (the dragon roams about
    // 20 m round the centre; these stand 35-43 m out). -VeyrNoDepthDressing keeps the open court.
    if(FParse::Param(FCommandLine::Get(),TEXT("VeyrNoDepthDressing")))return;
    auto Load=[](const TCHAR* Name){return LoadObject<UStaticMesh>(nullptr,*FString::Printf(TEXT("/Game/ArtPass/Tripo/%s/SM_%s.SM_%s"),Name,Name,Name),nullptr,LOAD_Quiet|LOAD_NoWarn);};
    UStaticMesh* Arch=Load(TEXT("CathedralArch_v001"));
    UStaticMesh* Buttress=Load(TEXT("PolishCornerButtress_v001"));
    int32 Count=0;
    auto Piece=[&](UStaticMesh* Mesh,const FVector& At,float Height,float Yaw)
    {
        if(!Mesh)return;
        const FBox B=Mesh->GetBoundingBox();const float S=Height/FMath::Max(1.f,static_cast<float>(B.GetSize().Z));
        auto* C=NewObject<UStaticMeshComponent>(this,FName(*FString::Printf(TEXT("RelitDepthPiece%02d"),Count++)));
        AddInstanceComponent(C);C->SetupAttachment(GetRootComponent());C->SetMobility(EComponentMobility::Movable);C->SetStaticMesh(Mesh);
        C->SetCollisionEnabled(ECollisionEnabled::NoCollision);C->SetCanEverAffectNavigation(false);C->SetCastShadow(false); // silhouettes against the lit wall; no extra shadow cost
        const FRotator R(0,Yaw,0);
        C->SetRelativeScale3D(FVector(S));C->SetRelativeRotation(R);
        C->SetRelativeLocation(At-R.RotateVector(FVector(B.GetCenter().X,B.GetCenter().Y,B.Min.Z)*S));
        C->RegisterComponent();
    };
    for(float Side:{-1.f,1.f})
    {
        // Broken arches along the long walls, between the braziers, read as a dark arcade against the lit wall.
        for(float X:{-1550.f,1550.f})Piece(Arch,FVector(X,Side*3550.f,0),VeyrLook::Tune(TEXT("archh"),950.f),Side>0?180.f:0.f);
        // Buttress piers in the four corners.
        for(float X:{-4250.f,4250.f})Piece(Buttress,FVector(X,Side*3650.f,0),1100.f,Side*(X>0?45.f:135.f));
    }
    UE_LOG(LogTemp,Display,TEXT("VEYR_LOOK_DEPTH_PIECES %d"),Count);
}

void AVeyrArena::SplitDragonLightingChannel()
{
    // Channel 1 was "knight, props and dragon". With a knight-only key the dragon must leave it; it keeps
    // channel 0 (the court) and channel 2 (its rim and key). The contact flash adds channel 2 (VeyrFightFeel).
    if(TActorIterator<AVeyrDragon> It(GetWorld());It)
    {
        TArray<UPrimitiveComponent*> Parts;It->GetComponents(Parts);
        for(UPrimitiveComponent* Part:Parts)if(Part&&Part->LightingChannels.bChannel1)
            Part->SetLightingChannels(Part->LightingChannels.bChannel0,false,true);
        ChannelSplitDragon=*It;
        UE_LOG(LogTemp,Display,TEXT("VEYR_LOOK_DRAGON_CHANNELS split=%d parts"),Parts.Num());
    }
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
