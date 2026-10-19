#include "VeyrDragonEffects.h"
#include "VeyrDragon.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "Components/SceneComponent.h"
#include "Engine/StaticMesh.h"
#include "GameFramework/PlayerController.h"
#include "Kismet/GameplayStatics.h"
#include "Materials/MaterialInterface.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Materials/MaterialParameters.h"
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
    // Owned transient overrides retain the original FXv2 shaders. Their pale
    // six-times-emissive default overwhelmed the orange body after overlap was
    // fixed; reserve a subdued amber core rather than an unbroken white stripe.
    for(UMaterialInterface* Material:{CoreMaterial.Get(),FlameMaterial.Get()})
    {
        float Brightness=0;FLinearColor Tint;
        if(!Material->GetScalarParameterValue(FHashedMaterialParameterInfo(TEXT("Brightness")),Brightness)||
           !Material->GetVectorParameterValue(FHashedMaterialParameterInfo(TEXT("Tint")),Tint))
        {EffectsDiagnostic=TEXT("Original FXv2 Tint/Brightness parameters missing; effects disabled");return false;}
    }
    WarmCoreMaterial=UMaterialInstanceDynamic::Create(CoreMaterial,this);
    WarmFlameMaterial=UMaterialInstanceDynamic::Create(FlameMaterial,this);
    if(!WarmCoreMaterial||!WarmFlameMaterial){EffectsDiagnostic=TEXT("Transient flame material creation failed");return false;}
    WarmCoreMaterial->SetFlags(RF_Transient);WarmFlameMaterial->SetFlags(RF_Transient);
    WarmCoreMaterial->SetVectorParameterValue(TEXT("Tint"),FLinearColor(1.f,.45f,.045f,1.f));
    WarmCoreMaterial->SetScalarParameterValue(TEXT("Brightness"),1.6f);
    WarmFlameMaterial->SetVectorParameterValue(TEXT("Tint"),FLinearColor(1.f,.18f,.008f,1.f));
    WarmFlameMaterial->SetScalarParameterValue(TEXT("Brightness"),2.6f);
    ConfigurePool(Core,WarmCoreMaterial,CoreCount);ConfigurePool(Flame,WarmFlameMaterial,FlameCount);ConfigurePool(Smoke,SmokeMaterial,SmokeCount);
    AddTickPrerequisiteActor(Dragon);
    bEffectsReady=true;EffectsDiagnostic=TEXT("Original 176-sprite orange turbulent cone with subdued amber core; native visual acceptance pending");
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

void AVeyrDragonEffects::Streak(UInstancedStaticMeshComponent* Pool,int32 Index,const FVector& Position,
    const FVector& Camera,const FVector& Axis,float Along,float Across,float Alpha,float Seed)
{
    FVector Facing=(Camera-Position).GetSafeNormal();
    if(Facing.IsNearlyZero())Facing=FVector::UpVector;
    const FVector Projected=Axis-Facing*FVector::DotProduct(Axis,Facing);
    const float Projection=static_cast<float>(Projected.Size());
    const FQuat Rotation=Projection>.001f?FRotationMatrix::MakeFromXZ(Projected/Projection,Facing).ToQuat():
        FRotationMatrix::MakeFromZ(Facing).ToQuat();
    // Axial ellipses overlap along the projected beam. End-on views retain
    // a round cross-section instead of a long camera-facing ribbon.
    const float ScreenAlong=FMath::Min(FMath::Lerp(Across,Along,FMath::Clamp(Projection,0.f,1.f)),
        Along/FMath::Max(.001f,Projection));
    Pool->UpdateInstanceTransform(Index,FTransform(Rotation,Position,FVector(ScreenAlong/100.f,Across/100.f,1.f)),true,false,true);
    const float CameraFade=FMath::Clamp((static_cast<float>(FVector::Distance(Camera,Position))-70.f)/130.f,0.f,1.f);
    Pool->SetCustomDataValue(Index,0,FMath::Clamp(Alpha*CameraFade,0.f,1.f),false);
    Pool->SetCustomDataValue(Index,1,Seed,false);
}

void AVeyrDragonEffects::Tick(float DeltaSeconds)
{
    Super::Tick(DeltaSeconds);
    if(!bEffectsReady||!IsValid(Dragon)||Dragon->IsDead()||Dragon->IsEncounterStopped()||Dragon->Move!=EVeyrDragonMove::Fire)
    {HideEffects();return;}
    if(Dragon->bUsingCustomuseVisual&&!Dragon->HasValidImportedCombatPose()){HideEffects();return;}
    const bool bWindup=Dragon->State==EVeyrDragonState::Windup;
    const FVeyrDragonFootprint Footprint=Dragon->GetActiveFootprint();
    const FVeyrDragonFlameBeam Beam=Dragon->GetActiveFlameBeam();
    const bool bImported=Dragon->bUsingCustomuseVisual;
    const bool bActive=Dragon->State==EVeyrDragonState::Active&&
        (bImported?Beam.bDamaging:(Footprint.bDamaging&&Footprint.Shape==EVeyrDangerShape::Sector));
    if(!bWindup&&!bActive){HideEffects();return;}
    APlayerController* Player=UGameplayStatics::GetPlayerController(this,0);
    if(!Player){HideEffects();return;}
    FVector Camera;FRotator View;Player->GetPlayerViewPoint(Camera,View);
    const FVector Mouth=Dragon->GetMouthLocation();
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
    if(bImported)
    {
        // This is the same finite 3D cone used against the knight capsule.
        // Every flame/core position starts at the actual muzzle and travels
        // forward; no connector can run back toward the actor origin.
        const FVector Axis=Beam.Direction.GetSafeNormal();
        FVector Side=FVector::CrossProduct(Axis,FVector::UpVector).GetSafeNormal();
        if(Side.IsNearlyZero())Side=FVector::RightVector;
        const FVector Up=FVector::CrossProduct(Side,Axis).GetSafeNormal();
        const float Spread=FMath::Tan(FMath::DegreesToRadians(Beam.HalfAngleDegrees));
        auto Point=[&](float U,float SideAmount,float UpAmount)
        {
            const float Distance=Beam.Length*U,Radius=Distance*Spread;
            return Beam.Origin+Axis*Distance+Side*(SideAmount*Radius)+Up*(UpAmount*Radius);
        };
        const float CoreStep=Beam.Length/CoreCount,BodyStep=Beam.Length/FlameBodyCount;
        auto BoundedLength=[&](float U,float Desired)
        {
            // The finite cone is never connected backward to a proxy origin,
            // and even elongated cards end at the muzzle/beam endpoint.
            return FMath::Max(1.f,FMath::Min(Desired,2.f*Beam.Length*FMath::Min(U,1.f-U)));
        };
        for(int32 I=0;I<CoreCount;++I)
        {
            const float U=(I+.5f)/CoreCount,Radius=Beam.Length*U*Spread,Seed=FMath::Frac(I*.618034f);
            const float Pulse=FMath::Square(FMath::Sin(Clock*15.f-U*39.f));
            const float Across=(28.f+Radius*.92f)*(.80f+.30f*Pulse);
            const float Along=BoundedLength(U,FMath::Max(CoreStep*4.5f,Across));
            const float Density=FMath::Clamp(CoreStep*2.2f/FMath::Max(CoreStep,Along),.16f,.54f);
            Streak(Core,I,Point(U,.18f*FMath::Sin(Clock*12.f-U*29.f),.13f*FMath::Cos(Clock*15.f-U*37.f)),
                Camera,Axis,Along,Across,Density*.28f*(.45f+.55f*Pulse),Seed);
        }
        // Broad, overlapping orange ellipses provide the actual flame body.
        // FXv2's radial power has a soft edge:2.8*radius card width puts the
        // damaging cone rim inside that visible feather rather than outside
        // a tiny155cm puff (the far cone is roughly744cm in diameter).
        for(int32 I=0;I<FlameBodyCount;++I)
        {
            const float U=(I+.5f)/FlameBodyCount,Radius=Beam.Length*U*Spread,Seed=FMath::Frac(I*.618034f);
            const float Bulge=.94f+.12f*FMath::Square(FMath::Sin(Clock*11.f-U*27.f));
            const float Across=FMath::Max(40.f,Radius*2.8f)*Bulge;
            const float Along=BoundedLength(U,FMath::Max(BodyStep*4.f,Across*.48f));
            const float Density=FMath::Clamp(BodyStep*1.8f/FMath::Max(BodyStep,Along),.075f,.48f);
            Streak(Flame,I,Point(U,.09f*FMath::Sin(Clock*11.f-U*27.f),.09f*FMath::Cos(Clock*9.f-U*25.f)),
                Camera,Axis,Along,Across,Density,Seed);
        }
        // A separate downstream-moving layer breaks up the body silhouette;
        // it is not responsible for continuity and cannot leave gaps in it.
        for(int32 I=0;I<FlameTurbulenceCount;++I)
        {
            const int32 Index=FlameBodyCount+I;
            const float U=FMath::Frac((I+.5f)/FlameTurbulenceCount+Clock*.65f);
            const float Radius=Beam.Length*U*Spread,Seed=FMath::Frac(I*.618034f);
            const float Angle=I*2.399963f-Clock*7.f+U*9.f,Radial=.55f+.25f*Seed;
            const float Flicker=FMath::Square(FMath::Sin(Clock*16.f-I*1.73f));
            const float Across=(50.f+Radius*1.05f)*(.80f+.40f*Flicker);
            const float Along=BoundedLength(U,FMath::Max(100.f,Across*1.15f));
            const float Fade=FMath::Clamp(U/.06f,0.f,1.f)*FMath::Clamp((1.f-U)/.15f,0.f,1.f);
            Streak(Flame,Index,Point(U,FMath::Cos(Angle)*Radial,FMath::Sin(Angle)*Radial),
                Camera,Axis,Along,Across,(.18f+.10f*Flicker)*Fade,Seed);
        }
        const int32 EmberCount=FlameCount-FlameBodyCount-FlameTurbulenceCount;
        for(int32 I=0;I<EmberCount;++I)
        {
            const float U=FMath::Frac((I+.5f)/EmberCount+Clock*.9f),Seed=FMath::Frac(I*.618034f);
            const float Angle=I*2.399963f+Clock*2.f;
            Streak(Flame,FlameBodyCount+FlameTurbulenceCount+I,
                Point(U,FMath::Cos(Angle)*.82f,FMath::Sin(Angle)*.82f),Camera,Axis,
                BoundedLength(U,40.f+35.f*Seed),7.f+5.f*Seed,.55f*FMath::Sin(U*PI),Seed);
        }
        for(int32 I=0;I<SmokeCount;++I)
        {
            const float U=.25f+.75f*(I+.5f)/SmokeCount,Seed=FMath::Frac(I*.618034f);
            const float Drift=FMath::Frac(Clock*.8f+Seed),Radius=Beam.Length*U*Spread;
            const FVector Position=Point(U,(Seed-.5f)*.9f,.25f)+FVector::UpVector*(60.f+Drift*140.f);
            Streak(Smoke,I,Position,Camera,Axis,220.f+Radius*1.2f,130.f+Radius*1.1f,
                .035f*(1.f-Drift),Seed);
        }
        Core->MarkRenderStateDirty();Flame->MarkRenderStateDirty();Smoke->MarkRenderStateDirty();
        VisibleSpriteCount=CoreCount+FlameCount+SmokeCount;return;
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
        const float U=I<8?I/7.f:(I-8+.5f)/(CoreCount-8.f);
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
