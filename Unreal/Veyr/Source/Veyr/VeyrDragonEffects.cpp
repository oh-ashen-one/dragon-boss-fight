#include "VeyrDragonEffects.h"
#include "VeyrDragon.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "Components/SceneComponent.h"
#include "Engine/StaticMesh.h"
#include "GameFramework/PlayerController.h"
#include "Kismet/GameplayStatics.h"
#include "Materials/MaterialInterface.h"
#include "UObject/ConstructorHelpers.h"

AVeyrDragonEffects::AVeyrDragonEffects()
{
    PrimaryActorTick.bCanEverTick=true;
    PrimaryActorTick.TickGroup=TG_PostUpdateWork;
    PrimaryActorTick.TickInterval=1.f/30.f;
    SetRootComponent(CreateDefaultSubobject<USceneComponent>(TEXT("DragonEffectsRoot")));
    Core=CreateDefaultSubobject<UInstancedStaticMeshComponent>(TEXT("BreathPaleCore"));
    Flame=CreateDefaultSubobject<UInstancedStaticMeshComponent>(TEXT("BreathOrangeFlame"));
    Smoke=CreateDefaultSubobject<UInstancedStaticMeshComponent>(TEXT("BreathSoftSmoke"));
    for(UInstancedStaticMeshComponent* Pool:{Core.Get(),Flame.Get(),Smoke.Get()})
    {
        Pool->SetupAttachment(GetRootComponent());
        Pool->SetCollisionEnabled(ECollisionEnabled::NoCollision);
        Pool->SetGenerateOverlapEvents(false);Pool->SetCanEverAffectNavigation(false);
        Pool->SetCastShadow(false);Pool->SetVisibility(false);
        Pool->SetCullDistances(0,9000);
        Pool->SetNumCustomDataFloats(2); // alpha, stable noise seed
    }
    static ConstructorHelpers::FObjectFinderOptional<UStaticMesh> Plane(TEXT("/Engine/BasicShapes/Plane.Plane"),LOAD_Quiet|LOAD_NoWarn);
    static ConstructorHelpers::FObjectFinderOptional<UMaterialInterface> Pale(TEXT("/Game/Veyr/FX/v2/M_VeyrBreathCore.M_VeyrBreathCore"),LOAD_Quiet|LOAD_NoWarn);
    static ConstructorHelpers::FObjectFinderOptional<UMaterialInterface> Orange(TEXT("/Game/Veyr/FX/v2/M_VeyrBreathFlame.M_VeyrBreathFlame"),LOAD_Quiet|LOAD_NoWarn);
    static ConstructorHelpers::FObjectFinderOptional<UMaterialInterface> Haze(TEXT("/Game/Veyr/FX/v2/M_VeyrBreathSmoke.M_VeyrBreathSmoke"),LOAD_Quiet|LOAD_NoWarn);
    SpritePlane=Plane.Get();CoreMaterial=Pale.Get();FlameMaterial=Orange.Get();SmokeMaterial=Haze.Get();
}

void AVeyrDragonEffects::ConfigurePool(UInstancedStaticMeshComponent* Pool,UMaterialInterface* Material,int32 Count)
{
    Pool->ClearInstances();Pool->SetStaticMesh(SpritePlane);Pool->SetMaterial(0,Material);
    Pool->SetNumCustomDataFloats(2);
    for(int32 I=0;I<Count;++I)
    {
        Pool->AddInstance(FTransform(FQuat::Identity,FVector::ZeroVector,FVector::ZeroVector));
        Pool->SetCustomDataValue(I,0,0.f,false);
        Pool->SetCustomDataValue(I,1,FMath::Frac(I*.61803399f),false);
    }
}

bool AVeyrDragonEffects::Initialize(AVeyrDragon* InDragon)
{
    HideEffects();bEffectsReady=false;
    if(IsValid(Dragon))RemoveTickPrerequisiteActor(Dragon);
    Dragon=InDragon;
    if(!IsValid(Dragon)){EffectsDiagnostic=TEXT("No dragon supplied; effects disabled");return false;}
    // A native authoring pass can create these after the CDO was constructed.
    // Explicit initialization may retry their exact owned paths quietly.
    if(!CoreMaterial)CoreMaterial=LoadObject<UMaterialInterface>(nullptr,TEXT("/Game/Veyr/FX/v2/M_VeyrBreathCore.M_VeyrBreathCore"),nullptr,LOAD_Quiet|LOAD_NoWarn);
    if(!FlameMaterial)FlameMaterial=LoadObject<UMaterialInterface>(nullptr,TEXT("/Game/Veyr/FX/v2/M_VeyrBreathFlame.M_VeyrBreathFlame"),nullptr,LOAD_Quiet|LOAD_NoWarn);
    if(!SmokeMaterial)SmokeMaterial=LoadObject<UMaterialInterface>(nullptr,TEXT("/Game/Veyr/FX/v2/M_VeyrBreathSmoke.M_VeyrBreathSmoke"),nullptr,LOAD_Quiet|LOAD_NoWarn);
    if(!SpritePlane||!CoreMaterial||!FlameMaterial||!SmokeMaterial)
    {EffectsDiagnostic=TEXT("Authored breath material/plane missing; no untextured substitute rendered");return false;}
    if(CoreMaterial->GetBlendMode()!=BLEND_Additive||FlameMaterial->GetBlendMode()!=BLEND_Additive||SmokeMaterial->GetBlendMode()!=BLEND_Translucent)
    {EffectsDiagnostic=TEXT("Unexpected breath material blend mode; effects disabled");return false;}
    ConfigurePool(Core,CoreMaterial,CoreCount);ConfigurePool(Flame,FlameMaterial,FlameCount);ConfigurePool(Smoke,SmokeMaterial,SmokeCount);
    AddTickPrerequisiteActor(Dragon);
    bEffectsReady=true;EffectsDiagnostic=TEXT("Original 128-sprite breath presentation; native visual acceptance pending");
    return true;
}

void AVeyrDragonEffects::HideEffects()
{
    Core->SetVisibility(false);Flame->SetVisibility(false);Smoke->SetVisibility(false);
    VisibleSpriteCount=0;
}

void AVeyrDragonEffects::Sprite(UInstancedStaticMeshComponent* Pool,int32 Index,const FVector& Position,
    const FVector& Camera,float Size,float Alpha,float Seed)
{
    const FVector Facing=(Camera-Position).GetSafeNormal();
    const FQuat Rotation=FRotationMatrix::MakeFromZ(Facing.IsNearlyZero()?FVector::UpVector:Facing).ToQuat();
    // Engine plane is 100cm square with local +Z normal. World-space instance
    // transforms prevent double application of the effects actor transform.
    Pool->UpdateInstanceTransform(Index,FTransform(Rotation,Position,FVector(Size/100.f,Size/100.f,1.f)),true,false,true);
    const float CameraFade=FMath::Clamp((static_cast<float>(FVector::Distance(Camera,Position))-70.f)/130.f,0.f,1.f);
    Pool->SetCustomDataValue(Index,0,FMath::Clamp(Alpha*CameraFade,0.f,1.f),false);
    Pool->SetCustomDataValue(Index,1,Seed,false);
}

void AVeyrDragonEffects::Tick(float DeltaSeconds)
{
    Super::Tick(DeltaSeconds);
    if(!bEffectsReady||!IsValid(Dragon)||Dragon->IsDead()||Dragon->IsEncounterStopped()||Dragon->Move!=EVeyrDragonMove::Fire)
    {HideEffects();return;}
    const bool bWindup=Dragon->State==EVeyrDragonState::Windup;
    const FVeyrDragonFootprint Footprint=Dragon->GetActiveFootprint();
    const bool bActive=Dragon->State==EVeyrDragonState::Active&&Footprint.bDamaging&&Footprint.Shape==EVeyrDangerShape::Sector;
    if(!bWindup&&!bActive){HideEffects();return;}
    APlayerController* Player=UGameplayStatics::GetPlayerController(this,0);
    if(!Player){HideEffects();return;}
    FVector Camera;FRotator View;Player->GetPlayerViewPoint(Camera,View);
    const FVector Mouth=Dragon->GetHeadLocation();
    const float Clock=Dragon->GetStateElapsed();
    Core->SetVisibility(true);Flame->SetVisibility(bActive);Smoke->SetVisibility(bActive);
    ++PresentationUpdates;
    if(bWindup)
    {
        const float Anticipation=FMath::Clamp(Clock/FMath::Max(.001f,Dragon->GetStateDuration()),0.f,1.f);
        for(int32 I=0;I<CoreCount;++I)
        {
            const float Phase=FMath::Frac(Clock*1.6f+I*.618034f);
            const float Angle=I*2.399963f;
            const FVector Offset=FVector(FMath::Cos(Angle),FMath::Sin(Angle),Phase)*FMath::Lerp(18.f,75.f,Phase);
            Sprite(Core,I,Mouth+Offset,Camera,9.f+Phase*13.f,I<16?(1.f-Phase)*(.16f+.30f*Anticipation):0.f,Phase);
        }
        Core->MarkRenderStateDirty();VisibleSpriteCount=16;return;
    }
    const FVector Forward=Footprint.Forward.GetSafeNormal2D();
    const FVector Side=FVector::CrossProduct(FVector::UpVector,Forward);
    const float Inner=FMath::Max(0.f,Footprint.InnerRadius),Outer=Footprint.OuterRadius;
    if(Forward.IsNearlyZero()||Outer<=Inner){HideEffects();return;}
    auto BeamPoint=[&](float U,float AngularFraction,float Lift)
    {
        const FVector Direction=Forward.RotateAngleAxis(AngularFraction*Footprint.HalfAngleDegrees,FVector::UpVector);
        FVector Point=Footprint.Origin+Direction*FMath::Lerp(Inner,Outer,U);
        Point.Z=FMath::Lerp(Mouth.Z,Footprint.Origin.Z+65.f,U)+Lift;
        return Point;
    };
    const FVector ConnectorEnd=BeamPoint(.10f,0.f,0.f);
    for(int32 I=0;I<CoreCount;++I)
    {
        const float Seed=FMath::Frac(I*.618034f);
        const float U=I<8?I/7.f:(I-8+.5f)/24.f;
        const FVector Position=I<8?FMath::Lerp(Mouth,ConnectorEnd,U):BeamPoint(U,.10f*FMath::Sin(Clock*14.f+I),0.f);
        Sprite(Core,I,Position,Camera,I<8?32.f:42.f+U*23.f,.20f+.10f*FMath::Sin(Clock*18.f+I),Seed);
    }
    for(int32 I=0;I<FlameCount;++I)
    {
        const float U=(I+.5f)/FlameCount,Seed=FMath::Frac(I*.618034f);
        const float Flutter=FMath::Sin(Clock*15.f+I*2.399963f);
        const FVector Position=BeamPoint(U,(Seed-.5f)*1.5f,Flutter*24.f);
        Sprite(Flame,I,Position,Camera,65.f+85.f*U,.12f+.12f*FMath::Square(Flutter),Seed);
    }
    for(int32 I=0;I<SmokeCount;++I)
    {
        const float U=.25f+.75f*(I+.5f)/SmokeCount,Seed=FMath::Frac(I*.618034f);
        const float Drift=FMath::Frac(Clock*.8f+Seed);
        const FVector Position=BeamPoint(U,(Seed-.5f)*1.1f,70.f+Drift*130.f)+Side*FMath::Sin(Clock+I)*20.f;
        Sprite(Smoke,I,Position,Camera,95.f+95.f*Drift,.035f*(1.f-Drift),Seed);
    }
    Core->MarkRenderStateDirty();Flame->MarkRenderStateDirty();Smoke->MarkRenderStateDirty();
    VisibleSpriteCount=CoreCount+FlameCount+SmokeCount;
}
