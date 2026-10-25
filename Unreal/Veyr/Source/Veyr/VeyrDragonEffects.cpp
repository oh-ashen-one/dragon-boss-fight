#include "VeyrDragonEffects.h"
#include "VeyrDragon.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "Components/SceneComponent.h"
#include "Components/PointLightComponent.h"
#include "Engine/StaticMesh.h"
#include "GameFramework/PlayerController.h"
#include "Kismet/GameplayStatics.h"
#include "Materials/MaterialInterface.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "UObject/ConstructorHelpers.h"

AVeyrDragonEffects::AVeyrDragonEffects()
{
    PrimaryActorTick.bCanEverTick=true;PrimaryActorTick.TickGroup=TG_PostUpdateWork;
    SetRootComponent(CreateDefaultSubobject<USceneComponent>(TEXT("DragonEffectsRoot")));
    Core=CreateDefaultSubobject<UInstancedStaticMeshComponent>(TEXT("BreathHotCore"));
    Flame=CreateDefaultSubobject<UInstancedStaticMeshComponent>(TEXT("BreathFlameTongues"));
    Smoke=CreateDefaultSubobject<UInstancedStaticMeshComponent>(TEXT("BreathRisingSmoke"));
    Embers=CreateDefaultSubobject<UInstancedStaticMeshComponent>(TEXT("BreathEmbers"));
    for(UInstancedStaticMeshComponent* Pool:{Core.Get(),Flame.Get(),Smoke.Get(),Embers.Get()})
    {
        Pool->SetupAttachment(GetRootComponent());Pool->SetCollisionEnabled(ECollisionEnabled::NoCollision);
        Pool->SetGenerateOverlapEvents(false);Pool->SetCanEverAffectNavigation(false);
        Pool->SetCastShadow(false);Pool->SetVisibility(false);Pool->SetCullDistances(0,9000);
        Pool->SetNumCustomDataFloats(4); // opacity, independent seed, age, heat
    }
    for(int32 I=0;I<3;++I)
    {
        UPointLightComponent* Light=CreateDefaultSubobject<UPointLightComponent>(*FString::Printf(TEXT("BreathLight%d"),I));
        Light->SetupAttachment(GetRootComponent());Light->SetMobility(EComponentMobility::Movable);
        Light->SetIntensityUnits(ELightUnits::Lumens);
        Light->SetCastShadows(false);Light->SetIntensity(0.f);Light->SetAttenuationRadius(650.f);
        Light->SetLightColor(FLinearColor(1.f,.23f,.025f));Light->SetVisibility(false);
        FireLights.Add(Light);
    }
    static ConstructorHelpers::FObjectFinderOptional<UStaticMesh> Plane(TEXT("/Engine/BasicShapes/Plane.Plane"),LOAD_Quiet|LOAD_NoWarn);
    static ConstructorHelpers::FObjectFinderOptional<UMaterialInterface> Pale(TEXT("/Game/Veyr/FX/v3/M_VeyrBreathCore.M_VeyrBreathCore"),LOAD_Quiet|LOAD_NoWarn);
    static ConstructorHelpers::FObjectFinderOptional<UMaterialInterface> Orange(TEXT("/Game/Veyr/FX/v3/M_VeyrBreathFlame.M_VeyrBreathFlame"),LOAD_Quiet|LOAD_NoWarn);
    static ConstructorHelpers::FObjectFinderOptional<UMaterialInterface> Haze(TEXT("/Game/Veyr/FX/v3/M_VeyrBreathSmoke.M_VeyrBreathSmoke"),LOAD_Quiet|LOAD_NoWarn);
    static ConstructorHelpers::FObjectFinderOptional<UMaterialInterface> Spark(TEXT("/Game/Veyr/FX/v3/M_VeyrBreathEmber.M_VeyrBreathEmber"),LOAD_Quiet|LOAD_NoWarn);
    SpritePlane=Plane.Get();CoreMaterial=Pale.Get();FlameMaterial=Orange.Get();SmokeMaterial=Haze.Get();EmberMaterial=Spark.Get();
}

void AVeyrDragonEffects::ConfigurePool(UInstancedStaticMeshComponent* Pool,UMaterialInterface* Material,int32 Count)
{
    Pool->ClearInstances();Pool->SetStaticMesh(SpritePlane);Pool->SetMaterial(0,Material);Pool->SetNumCustomDataFloats(4);
    for(int32 I=0;I<Count;++I)
    {
        Pool->AddInstance(FTransform(FQuat::Identity,FVector::ZeroVector,FVector::ZeroVector));
        Pool->SetCustomDataValue(I,0,0.f,false);Pool->SetCustomDataValue(I,1,FMath::Frac(I*.61803399f),false);
        Pool->SetCustomDataValue(I,2,0.f,false);Pool->SetCustomDataValue(I,3,1.f,false);
    }
}

bool AVeyrDragonEffects::Initialize(AVeyrDragon* InDragon)
{
    HideEffects();bEffectsReady=false;LastActiveClock=-100.f;
    if(IsValid(Dragon))RemoveTickPrerequisiteActor(Dragon);Dragon=InDragon;
    if(!IsValid(Dragon)){EffectsDiagnostic=TEXT("No dragon supplied; breath disabled");return false;}
    auto Load=[&](TObjectPtr<UMaterialInterface>& Material,const TCHAR* Name)
    {
        if(!Material)Material=LoadObject<UMaterialInterface>(nullptr,*FString::Printf(TEXT("/Game/Veyr/FX/v3/%s.%s"),Name,Name),nullptr,LOAD_Quiet|LOAD_NoWarn);
    };
    Load(CoreMaterial,TEXT("M_VeyrBreathCore"));Load(FlameMaterial,TEXT("M_VeyrBreathFlame"));
    Load(SmokeMaterial,TEXT("M_VeyrBreathSmoke"));Load(EmberMaterial,TEXT("M_VeyrBreathEmber"));
    if(!SpritePlane||!CoreMaterial||!FlameMaterial||!SmokeMaterial||!EmberMaterial)
    {EffectsDiagnostic=TEXT("FXv3 atlas/density materials are missing; no flat procedural substitute rendered");return false;}
    if(CoreMaterial->GetBlendMode()!=BLEND_Additive||FlameMaterial->GetBlendMode()!=BLEND_Additive||
       SmokeMaterial->GetBlendMode()!=BLEND_Translucent||EmberMaterial->GetBlendMode()!=BLEND_Additive)
    {EffectsDiagnostic=TEXT("FXv3 blend modes do not match flame/smoke contract");return false;}
    // Transient instances tune only this dragon; the imported atlas materials
    // and the arena's brazier users retain their authored defaults.
    auto PresentationMaterial=[&](UMaterialInterface* Parent,const FLinearColor& Tint,float Brightness)
    {
        UMaterialInstanceDynamic* Material=UMaterialInstanceDynamic::Create(Parent,this);
        Material->SetScalarParameterValue(TEXT("Brightness"),Brightness);
        Material->SetVectorParameterValue(TEXT("Tint"),Tint);
        return Material;
    };
    ConfigurePool(Core,PresentationMaterial(CoreMaterial,FLinearColor(1.f,.92f,.72f),3.3f),CoreCount);
    ConfigurePool(Flame,PresentationMaterial(FlameMaterial,FLinearColor(1.f,.60f,.25f),2.2f),FlameCount);
    ConfigurePool(Smoke,PresentationMaterial(SmokeMaterial,FLinearColor(.34f,.32f,.29f),.12f),SmokeCount);
    ConfigurePool(Embers,EmberMaterial,EmberCount);
    AddTickPrerequisiteActor(Dragon);bEffectsReady=true;
    EffectsDiagnostic=TEXT("FXv3 textured turbulent jet, independent hot core, smoke/embers and three local fire lights; native visual acceptance pending");
    return true;
}

void AVeyrDragonEffects::HideEffects()
{
    for(UInstancedStaticMeshComponent* Pool:{Core.Get(),Flame.Get(),Smoke.Get(),Embers.Get()})Pool->SetVisibility(false);
    for(UPointLightComponent* Light:FireLights){Light->SetIntensity(0.f);Light->SetVisibility(false);}
    VisibleSpriteCount=0;
}

void AVeyrDragonEffects::Sprite(UInstancedStaticMeshComponent* Pool,int32 Index,const FVector& Position,
    const FVector& Camera,float Size,float Alpha,float Seed,float Age,float Heat)
{
    const FVector Facing=(Camera-Position).GetSafeNormal();
    const FQuat Rotation=FRotationMatrix::MakeFromZ(Facing.IsNearlyZero()?FVector::UpVector:Facing).ToQuat();
    Pool->UpdateInstanceTransform(Index,FTransform(Rotation,Position,FVector(Size/100.f,Size/100.f,1.f)),true,false,true);
    const float Fade=FMath::Clamp((static_cast<float>(FVector::Distance(Camera,Position))-60.f)/120.f,0.f,1.f);
    Pool->SetCustomDataValue(Index,0,FMath::Clamp(Alpha*Fade,0.f,1.f),false);
    Pool->SetCustomDataValue(Index,1,Seed,false);Pool->SetCustomDataValue(Index,2,Age,false);Pool->SetCustomDataValue(Index,3,Heat,false);
}

void AVeyrDragonEffects::Streak(UInstancedStaticMeshComponent* Pool,int32 Index,const FVector& Position,
    const FVector& Camera,const FVector& Axis,float Along,float Across,float Alpha,float Seed,float Age,float Heat)
{
    FVector Facing=(Camera-Position).GetSafeNormal();if(Facing.IsNearlyZero())Facing=FVector::UpVector;
    const FVector Projected=Axis-Facing*FVector::DotProduct(Axis,Facing);const float Projection=static_cast<float>(Projected.Size());
    const FQuat Rotation=Projection>.001f?FRotationMatrix::MakeFromXZ(Projected/Projection,Facing).ToQuat():FRotationMatrix::MakeFromZ(Facing).ToQuat();
    const float ScreenAlong=FMath::Lerp(Across,Along,FMath::Clamp(Projection,0.f,1.f));
    Pool->UpdateInstanceTransform(Index,FTransform(Rotation,Position,FVector(ScreenAlong/100.f,Across/100.f,1.f)),true,false,true);
    const float Fade=FMath::Clamp((static_cast<float>(FVector::Distance(Camera,Position))-60.f)/120.f,0.f,1.f);
    Pool->SetCustomDataValue(Index,0,FMath::Clamp(Alpha*Fade,0.f,1.f),false);
    Pool->SetCustomDataValue(Index,1,Seed,false);Pool->SetCustomDataValue(Index,2,Age,false);Pool->SetCustomDataValue(Index,3,Heat,false);
}

void AVeyrDragonEffects::Tick(float DeltaSeconds)
{
    Super::Tick(DeltaSeconds);EffectsClock+=DeltaSeconds;
    if(!bEffectsReady||!IsValid(Dragon)){HideEffects();return;}
    APlayerController* Player=UGameplayStatics::GetPlayerController(this,0);
    if(!Player){HideEffects();return;}
    FVector Camera;FRotator View;Player->GetPlayerViewPoint(Camera,View);
    const bool FireMove=Dragon->Move==EVeyrDragonMove::Fire&&!Dragon->IsDead()&&!Dragon->IsEncounterStopped();
    const bool Windup=FireMove&&Dragon->State==EVeyrDragonState::Windup;
    const FVeyrDragonFlameBeam Beam=Dragon->GetActiveFlameBeam();
    const bool Active=FireMove&&Dragon->State==EVeyrDragonState::Active&&Beam.bDamaging&&Beam.Length>1.f;
    if(Dragon->bUsingCustomuseVisual&&!Dragon->HasValidImportedCombatPose()){HideEffects();return;}
    const float TailAge=EffectsClock-LastActiveClock;
    if(!Windup&&!Active&&TailAge>=1.2f){HideEffects();return;}
    ++PresentationUpdates;VisibleSpriteCount=0;
    Core->SetVisibility(Windup||Active);Flame->SetVisibility(Active);Embers->SetVisibility(Active);
    if(Windup)
    {
        const float T=FMath::Clamp(Dragon->GetStateElapsed()/FMath::Max(.001f,Dragon->GetStateDuration()),0.f,1.f);
        const FVector Mouth=Dragon->GetMouthLocation();
        for(int32 I=0;I<CoreCount;++I)
        {
            const float Seed=FMath::Frac(I*.618034f),Age=FMath::Frac(EffectsClock*1.5f+Seed);
            const FVector Offset=FVector(FMath::Cos(I*2.4f),FMath::Sin(I*2.4f),.5f)*Age*20.f;
            Sprite(Core,I,Mouth+Offset,Camera,16.f+Age*35.f,(1.f-Age)*T*T*.16f,Seed,Age,1.f);
        }
        Core->MarkRenderStateDirty();VisibleSpriteCount+=CoreCount;
        for(int32 I=0;I<FireLights.Num();++I)
        {
            FireLights[I]->SetVisibility(I==0);FireLights[I]->SetWorldLocation(Mouth);
            FireLights[I]->SetIntensity(I==0?800.f*T*T:0.f);
        }
    }
    if(Active)
    {
        LastBeamOrigin=Beam.Origin;LastBeamDirection=Beam.Direction.GetSafeNormal();LastBeamLength=Beam.Length;
        LastBeamSpread=FMath::Tan(FMath::DegreesToRadians(Beam.HalfAngleDegrees));LastActiveClock=EffectsClock;
        const FVector Axis=LastBeamDirection;
        FVector Side=FVector::CrossProduct(Axis,FVector::UpVector).GetSafeNormal();if(Side.IsNearlyZero())Side=FVector::RightVector;
        const FVector Up=FVector::CrossProduct(Side,Axis).GetSafeNormal();
        const float T=Dragon->GetStateElapsed(),Startup=FMath::Clamp(T/.08f,0.f,1.f);
        auto Point=[&](float U,float Radial,float Angle)
        {
            const float R=Beam.Length*U*LastBeamSpread;
            return Beam.Origin+Axis*(Beam.Length*U)+Side*(FMath::Cos(Angle)*R*Radial)+Up*(FMath::Sin(Angle)*R*Radial);
        };
        auto Length=[&](float U,float Wanted){return FMath::Max(1.f,FMath::Min(Wanted,2.f*Beam.Length*FMath::Min(U,1.f-U)));};
        for(int32 I=0;I<CoreCount;++I)
        {
            const float Seed=FMath::Frac(I*.618034f),U=.012f+.218f*(I+.5f)/CoreCount;
            const float Pulse=.5f+.5f*FMath::Sin(EffectsClock*18.f-Seed*31.f);
            const float Width=18.f+Beam.Length*U*LastBeamSpread*.40f;
            const float CoreLength=FMath::Min(90.f+45.f*Pulse,2.f*Beam.Length*FMath::Min(U,.28f-U));
            Streak(Core,I,Point(U,.10f,EffectsClock*4.f+I),Camera,Axis,CoreLength,Width,
                .095f*(1.f-U/.28f)*Startup*(.65f+.35f*Pulse),Seed,FMath::Frac(T*1.2f+Seed),1.f);
        }
        // Five desynchronised advecting streams fill the volume with textured
        // tongues. Their translucent gaps stay visible; this is not a solid cone.
        for(int32 I=0;I<FlameCount;++I)
        {
            const float Seed=FMath::Frac(I*.618034f),Age=FMath::Frac(T*.85f+(I/5+.5f)/16.f+Seed*.035f);
            const float U=.012f+.976f*Age,R=Beam.Length*U*LastBeamSpread;
            const float Angle=(I%5)*2.f*PI/5.f+T*.8f+U*4.7f;
            const float Curl=FMath::Sin(T*7.5f+Seed*19.f+U*9.f);
            const float Radial=I%5==0?.14f:.48f+.12f*Curl+.07f*Seed;
            const float Life=FMath::Pow(FMath::Max(0.f,FMath::Sin(Age*PI)),.45f);
            const float Width=FMath::Max(24.f,FMath::Min(FMath::Max(70.f,R*1.8f),2.f*R*(1.f-Radial)));
            const float Along=Length(U,FMath::Max(100.f,R*.85f));
            const FVector TongueAxis=(Axis+Side*(Curl*.12f)+Up*(FMath::Cos(T*6.f+Seed*23.f)*.08f)).GetSafeNormal();
            const float ImpactFade=1.f-.45f*FMath::Clamp((U-.62f)/.38f,0.f,1.f);
            Streak(Flame,I,Point(U,Radial,Angle),Camera,TongueAxis,Along,Width,
                (.11f+.055f*Seed)*Life*Startup*ImpactFade,Seed,Age,.90f-Age*.55f);
        }
        for(int32 I=0;I<EmberCount;++I)
        {
            const float Seed=FMath::Frac(I*.618034f),Age=FMath::Frac(T*1.5f+Seed),U=.10f+.88f*Age;
            const float Angle=I*2.399963f+T*1.2f;
            Streak(Embers,I,Point(U,.55f+.2f*Seed,Angle)+FVector::UpVector*(Age*Age*70.f),Camera,Axis,
                Length(U,16.f+30.f*Seed),2.5f+3.f*Seed,(1.f-Age)*.65f*Startup,Seed,Age,1.f);
        }
        for(int32 I=0;I<FireLights.Num();++I)
        {
            const float U=.04f+I*.27f;FVector Position=Beam.Origin+Axis*(Beam.Length*U);
            Position.Z=FMath::Max(Position.Z,Dragon->GetActorLocation().Z+45.f);
            const float Flicker=.85f+.15f*FMath::Sin(EffectsClock*19.f-I*2.f);
            FireLights[I]->SetVisibility(true);FireLights[I]->SetWorldLocation(Position);
            FireLights[I]->SetAttenuationRadius(550.f+I*120.f);
            FireLights[I]->SetIntensity((I==0?4200.f:I==1?3000.f:1800.f)*Flicker*Startup);
        }
        Core->MarkRenderStateDirty();Flame->MarkRenderStateDirty();Embers->MarkRenderStateDirty();
        VisibleSpriteCount+=CoreCount+FlameCount+EmberCount;
    }
    const float SmokeTail=Active?1.f:FMath::Clamp(1.f-TailAge/1.2f,0.f,1.f);
    const bool ShowSmoke=SmokeTail>0.f&&LastBeamLength>1.f;Smoke->SetVisibility(ShowSmoke);
    if(ShowSmoke)
    {
        FVector Side=FVector::CrossProduct(LastBeamDirection,FVector::UpVector).GetSafeNormal();if(Side.IsNearlyZero())Side=FVector::RightVector;
        for(int32 I=0;I<SmokeCount;++I)
        {
            const float Seed=FMath::Frac(I*.618034f),Age=FMath::Frac(EffectsClock*.40f+Seed),U=.60f+.34f*(I+.5f)/SmokeCount;
            const float R=LastBeamLength*U*LastBeamSpread;
            const FVector Behind=(LastBeamOrigin-Camera).GetSafeNormal2D();
            FVector Position=LastBeamOrigin+LastBeamDirection*(LastBeamLength*U)+Side*((Seed-.5f)*R*1.25f)+Behind*(35.f+Age*70.f);
            Position.Z=FMath::Max(Position.Z,Dragon->GetActorLocation().Z+40.f)+70.f+Age*190.f+(Active?0.f:FMath::Max(0.f,TailAge))*100.f;
            const float FadeIn=FMath::Clamp(Age/.12f,0.f,1.f);
            Sprite(Smoke,I,Position,Camera,130.f+R*.85f+Age*90.f,(.065f+.03f*Seed)*FadeIn*(1.f-Age)*SmokeTail,Seed,Age,.5f);
        }
        Smoke->MarkRenderStateDirty();VisibleSpriteCount+=SmokeCount;
    }
    if(!Active&&!Windup)
        for(UPointLightComponent* Light:FireLights){Light->SetIntensity(700.f*FMath::Clamp(1.f-TailAge/.25f,0.f,1.f));Light->SetVisibility(TailAge<.25f);}
}
