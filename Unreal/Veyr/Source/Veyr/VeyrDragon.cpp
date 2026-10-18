#include "VeyrDragon.h"
#include "VeyrKnight.h"
#include "VeyrVisualDefinition.h"
#include "Animation/AnimSequence.h"
#include "VeyrSkeletalPresentation.h"
#include "Components/SceneComponent.h"
#include "Components/CapsuleComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "Components/TextRenderComponent.h"
#include "Engine/StaticMesh.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Materials/MaterialInterface.h"
#include "Materials/MaterialParameters.h"
#include "UObject/ConstructorHelpers.h"
#include "Kismet/GameplayStatics.h"

namespace
{
    const FVector RestFeet[4] = { FVector(230,-300,80), FVector(230,300,80), FVector(-280,-300,80), FVector(-280,300,80) };
    float Ease(float T) { T=FMath::Clamp(T,0.f,1.f); return T*T*(3.f-2.f*T); }
    float DistanceToSegment2D(const FVector& P,const FVector& A,const FVector& B)
    {
        const FVector D=B-A;
        const float Alpha=D.SizeSquared()>.01 ? FMath::Clamp(static_cast<float>(FVector::DotProduct(P-A,D)/D.SizeSquared()),0.f,1.f) : 0.f;
        return static_cast<float>(FVector::Dist(P,A+D*Alpha));
    }
    void Tint(UMaterialInstanceDynamic* Material,const FLinearColor& Color)
    {
        if(!Material)return;
        Material->SetVectorParameterValue(TEXT("Color"),Color);
        Material->SetVectorParameterValue(TEXT("BaseColor"),Color);
    }
    int32 MoveIndex(EVeyrDragonMove Move) { return static_cast<int32>(Move); }
}

AVeyrDragon::AVeyrDragon()
{
    PrimaryActorTick.bCanEverTick=true;
    SceneRoot=CreateDefaultSubobject<USceneComponent>(TEXT("DragonRulesRoot")); SetRootComponent(SceneRoot);
    ImportedPresentation=CreateDefaultSubobject<UVeyrSkeletalPresentation>(TEXT("CustomuseDragonPresentation"));
    ImportedPresentation->SetupAttachment(SceneRoot);
    ImportedPresentation->SetVisibility(false);
    AttackPoseProbe=CreateDefaultSubobject<UVeyrSkeletalPresentation>(TEXT("HiddenAttackEnvelopeProbe"));
    AttackPoseProbe->SetupAttachment(SceneRoot);
    AttackPoseProbe->SetVisibility(false);AttackPoseProbe->SetHiddenInGame(true);
    AttackPoseProbe->SetCastShadow(false);AttackPoseProbe->SetRenderInMainPass(false);
    static ConstructorHelpers::FObjectFinderOptional<UVeyrVisualDefinition> ImportedDefinition(TEXT("/Game/Characters/Customuse/Runtime/DA_Dragon.DA_Dragon"));
    VisualDefinition=ImportedDefinition.Get();
    static ConstructorHelpers::FObjectFinder<UStaticMesh> Sphere(TEXT("/Engine/BasicShapes/Sphere.Sphere"));
    static ConstructorHelpers::FObjectFinder<UStaticMesh> Cube(TEXT("/Engine/BasicShapes/Cube.Cube"));
    static ConstructorHelpers::FObjectFinder<UStaticMesh> Cylinder(TEXT("/Engine/BasicShapes/Cylinder.Cylinder"));
    BodyMesh=CreateTemporaryPart(TEXT("TEMP_BasaltBody_RulesOnly"),Sphere.Object,FVector(9.8,6.4,5));
    ChestMesh=CreateTemporaryPart(TEXT("TEMP_ShoulderMass_RulesOnly"),Sphere.Object,FVector(5.8,6.8,5.2));
    HeadMesh=CreateTemporaryPart(TEXT("TEMP_Head_RulesOnly"),Sphere.Object,FVector(3.3,2.2,2.1));
    JawMesh=CreateTemporaryPart(TEXT("TEMP_Jaw_RulesOnly"),Cube.Object,FVector(2.6,1.7,.65));
    // The giant must not collapse the camera arm into the knight. World
    // geometry still blocks the camera; the knight handles local boss occlusion.
    for(UStaticMeshComponent* Mass : {BodyMesh.Get(),ChestMesh.Get(),HeadMesh.Get()})
    {
        Mass->SetCollisionEnabled(ECollisionEnabled::QueryOnly);
        Mass->SetCollisionResponseToAllChannels(ECR_Ignore);
        Mass->SetCollisionResponseToChannel(ECC_Camera,ECR_Ignore);
        Mass->SetGenerateOverlapEvents(false);
    }
    for(int32 I=0;I<4;++I)
    {
        UpperLegMeshes.Add(CreateTemporaryPart(FName(*FString::Printf(TEXT("TEMP_UpperLeg_%d"),I)),Cylinder.Object,FVector::OneVector));
        LowerLegMeshes.Add(CreateTemporaryPart(FName(*FString::Printf(TEXT("TEMP_LowerLeg_%d"),I)),Cylinder.Object,FVector::OneVector));
        FootMeshes.Add(CreateTemporaryPart(FName(*FString::Printf(TEXT("TEMP_Foot_%d"),I)),Cube.Object,FVector(2,1.45,1.2)));
        LegLocal[I]=RestFeet[I]+FVector(0,0,30);
    }
    for(int32 I=0;I<6;++I)
        TailMeshes.Add(CreateTemporaryPart(FName(*FString::Printf(TEXT("TEMP_TailSegment_%d"),I)),Cylinder.Object,FVector::OneVector));
    for(int32 I=0;I<2;++I)
        WingMeshes.Add(CreateTemporaryPart(FName(*FString::Printf(TEXT("TEMP_WingSpar_%d"),I)),Cube.Object,FVector(6.5,.75,.5)));
    WarningLines=CreateDefaultSubobject<UInstancedStaticMeshComponent>(TEXT("GroundAnticipationGeometry"));
    DangerLines=CreateDefaultSubobject<UInstancedStaticMeshComponent>(TEXT("GroundActiveGeometry"));
    for(UInstancedStaticMeshComponent* Lines : {WarningLines.Get(),DangerLines.Get()})
    {
        Lines->SetupAttachment(SceneRoot); Lines->SetAbsolute(true,true,true); Lines->SetStaticMesh(Cube.Object);
        Lines->SetCollisionEnabled(ECollisionEnabled::NoCollision); Lines->SetCastShadow(false);
        Lines->SetCanEverAffectNavigation(false);
    }
    TemporaryLabel=CreateDefaultSubobject<UTextRenderComponent>(TEXT("TemporaryArtDisclosure"));
    TemporaryLabel->SetupAttachment(SceneRoot); TemporaryLabel->SetRelativeLocation(FVector(0,0,1120));
    TemporaryLabel->SetText(FText::FromString(TEXT("TEMPORARY RULE-TEST DRAGON\nNot Customuse art or authored animation")));
    TemporaryLabel->SetHorizontalAlignment(EHorizTextAligment::EHTA_Center);
    TemporaryLabel->SetWorldSize(32); TemporaryLabel->SetTextRenderColor(FColor(235,184,91));
}

UStaticMeshComponent* AVeyrDragon::CreateTemporaryPart(FName Name,UStaticMesh* Mesh,const FVector& Scale)
{
    UStaticMeshComponent* Part=CreateDefaultSubobject<UStaticMeshComponent>(Name);
    Part->SetupAttachment(SceneRoot); Part->SetStaticMesh(Mesh); Part->SetRelativeScale3D(Scale);
    Part->SetCollisionEnabled(ECollisionEnabled::NoCollision); Part->SetCanEverAffectNavigation(false);
    TemporaryParts.Add(Part); return Part;
}

void AVeyrDragon::BeginPlay()
{
    Super::BeginPlay(); Health=MaxHealth;
    UMaterialInterface* Base=LoadObject<UMaterialInterface>(nullptr,TEXT("/Engine/BasicShapes/BasicShapeMaterial.BasicShapeMaterial"));
    if(Base)
    {
        BasaltMaterial=UMaterialInstanceDynamic::Create(Base,this); Tint(BasaltMaterial,FLinearColor(.045,.07,.09));
        CopperMaterial=UMaterialInstanceDynamic::Create(Base,this); Tint(CopperMaterial,FLinearColor(.38,.19,.07));
        HeadMaterial=UMaterialInstanceDynamic::Create(Base,this); Tint(HeadMaterial,FLinearColor(.4,.36,.24));
        WarningMaterial=UMaterialInstanceDynamic::Create(Base,this); Tint(WarningMaterial,FLinearColor(1,.58,.045));
        DangerMaterial=UMaterialInstanceDynamic::Create(Base,this); Tint(DangerMaterial,FLinearColor(1,.055,.015));
        for(UStaticMeshComponent* Part:TemporaryParts)Part->SetMaterial(0,BasaltMaterial);
        HeadMesh->SetMaterial(0,HeadMaterial); JawMesh->SetMaterial(0,CopperMaterial);
        for(int32 I=0;I<4;++I)
        {
            UMaterialInstanceDynamic* Leg=UMaterialInstanceDynamic::Create(Base,this); Tint(Leg,FLinearColor(.16,.2,.23));
            LegMaterials.Add(Leg); LowerLegMeshes[I]->SetMaterial(0,Leg); FootMeshes[I]->SetMaterial(0,Leg);
        }
        for(UStaticMeshComponent* Wing:WingMeshes)Wing->SetMaterial(0,CopperMaterial);
        WarningLines->SetMaterial(0,WarningMaterial); DangerLines->SetMaterial(0,DangerMaterial);
    }
    UpdateTemporaryPresentation(0); EnterState(EVeyrDragonState::Idle,2.2f);
    if(!VisualDefinition)VisualDefinition=LoadObject<UVeyrVisualDefinition>(nullptr,
        TEXT("/Game/Characters/Customuse/Runtime/DA_Dragon.DA_Dragon"),nullptr,LOAD_Quiet|LOAD_NoWarn);
    if(VisualDefinition)ApplyCustomuseVisual(VisualDefinition);
}

void AVeyrDragon::Tick(float DeltaSeconds)
{
    Super::Tick(DeltaSeconds);
    if(DeltaSeconds<=0)return;
    if(!IsValid(Target))Target=Cast<AVeyrKnight>(UGameplayStatics::GetPlayerCharacter(this,0));
    // A freshly opened window cannot attack a player who has not clicked to
    // begin. Once engaged, releasing the mouse does not pause the encounter.
    if(IsValid(Target)&&!Target->HasEnteredEncounter())return;
    Clock+=DeltaSeconds; StateElapsed+=DeltaSeconds;
    StaggerProtection=FMath::Max(0.f,StaggerProtection-DeltaSeconds);
    for(float& Flash:LegFlash)Flash=FMath::Max(0.f,Flash-DeltaSeconds*4.f);
    if(!IsDead()&&IsValid(Target)&&Target->IsDead()&&!bEncounterStopped)
    {
        bEncounterStopped=true; EnterState(EVeyrDragonState::Idle,TNumericLimits<float>::Max());
    }
    if(!bEncounterStopped||IsDead())AdvanceState(DeltaSeconds);
    UpdateTemporaryPresentation(DeltaSeconds);
    UpdateImportedPresentation();
    VisualAccumulator+=DeltaSeconds;
    // Active sweep geometry must use the same current clock as damaging contact.
    if(State==EVeyrDragonState::Active||VisualAccumulator>=.04f) { VisualAccumulator=0; UpdateTelegraphs(); }
}

void AVeyrDragon::EnterState(EVeyrDragonState Next,float Duration)
{
    if(Next==EVeyrDragonState::Dead)
    {
        DeathStartDown=GetDownAmount();
        DeathStartBuckle=State==EVeyrDragonState::Buckle?Ease(StateElapsed/StateDuration):
            State==EVeyrDragonState::Collapse?1-Ease(StateElapsed/StateDuration):0.f;
    }
    State=Next; StateElapsed=0; StateDuration=Duration;
    bPreviousContactPoseValid=false;PreviousContacts.Reset();
    if(Next!=EVeyrDragonState::Windup&&Next!=EVeyrDragonState::Active)CommittedWarning.Reset();
    WarningLines->ClearInstances(); DangerLines->ClearInstances(); VisualAccumulator=.04f;bWarningDrawn=false;
}

void AVeyrDragon::AdvanceState(float DeltaSeconds)
{
    switch(State)
    {
        case EVeyrDragonState::Idle:
            if(StateElapsed>=StateDuration&&IsValid(Target)&&!Target->IsDead())ChooseAttack();
            break;
        case EVeyrDragonState::Reposition:
        {
            const float T=Ease(StateElapsed/StateDuration);
            SetActorLocation(FMath::Lerp(MoveStart,MoveEnd,T));
            SetActorRotation(FQuat::Slerp(TurnStart.Quaternion(),TurnEnd.Quaternion(),T));
            if(StateElapsed>=StateDuration){bJustRepositioned=true;EnterState(EVeyrDragonState::Idle,.75f);}
            break;
        }
        case EVeyrDragonState::Windup:
            if(StateElapsed>=StateDuration)
            {
                EnterState(EVeyrDragonState::Active,ActiveDuration);
                // Capture the visible phase-zero contacts immediately so the
                // first active interval participates in the subsequent sweep.
                UpdateImportedPresentation();
                if(bUsingCustomuseVisual)TryDamageTarget();
            }
            break;
        case EVeyrDragonState::Active:
            if(Move==EVeyrDragonMove::FlyAway)
            {
                const float T=FMath::Clamp(StateElapsed/FlightSeconds,0.f,1.f);
                FVector Position=FMath::Lerp(MoveStart,MoveEnd,Ease(T)); Position.Z+=FMath::Sin(T*PI)*1400.f;
                SetActorLocation(Position);
            }
            UpdateImportedPresentation();
            TryDamageTarget();
            if(StateElapsed>=StateDuration)
            {
                if(Move==EVeyrDragonMove::FlyAway)SetActorLocation(MoveEnd);
                EnterState(EVeyrDragonState::Recovery,RecoveryDuration);
            }
            break;
        case EVeyrDragonState::Recovery:
            if(StateElapsed>=StateDuration){++CompletedAttacks[MoveIndex(Move)];EnterState(EVeyrDragonState::Idle,.9f);}
            break;
        case EVeyrDragonState::Buckle:
            if(StateElapsed>=StateDuration)EnterState(EVeyrDragonState::Collapse,1.f);
            break;
        case EVeyrDragonState::Collapse:
            if(StateElapsed>=StateDuration)EnterState(EVeyrDragonState::Exposed,7.f);
            break;
        case EVeyrDragonState::Exposed:
            if(StateElapsed>=StateDuration)EnterState(EVeyrDragonState::Rise,2.f);
            break;
        case EVeyrDragonState::Rise:
            if(StateElapsed>=StateDuration)
            {
                for(float& Stagger:LegStagger)Stagger=0;
                StaggerProtection=1.5f; EnterState(EVeyrDragonState::Idle,.8f);
            }
            break;
        case EVeyrDragonState::Dead:break;
    }
}

void AVeyrDragon::ChooseAttack()
{
    if(bUsingCustomuseVisual)
    {
        if(!bImportedTargetsValid||!bImportedAttackCacheReady)
        {EnterState(EVeyrDragonState::Idle,1.f);return;}
        const int32 Positional=PredictPositionalMove(Target->GetFootLocation());
        if(Positional<0){BeginReposition();return;}
        EVeyrDragonMove Next=static_cast<EVeyrDragonMove>(Positional);
        if(TotalAttacks%6==5)Next=EVeyrDragonMove::FlyAway;
        if(Next==LastMove&&RepeatedMoveCount>=2){BeginReposition();return;}
        if(Next==EVeyrDragonMove::ClawSwipe)
            ClawLeg=CachedWarningContains(ImportedMoveClip(Next,0,TEXT("Active")),Target->GetFootLocation())?0:1;
        BeginAttack(Next);return;
    }
    const FVector Offset=Ground(Target->GetActorLocation()-GetActorLocation());
    const FVector Local=GetActorTransform().InverseTransformVectorNoScale(Offset);
    const float Distance=static_cast<float>(Offset.Size());
    const float FrontDot=FVector::DotProduct(Offset.GetSafeNormal(),GetActorForwardVector());
    if(!bJustRepositioned&&Distance>800&&FrontDot<-.15f&&TotalAttacks%3==2){BeginReposition();return;}
    EVeyrDragonMove Next;
    if(Distance>1750||TotalAttacks%6==5)Next=EVeyrDragonMove::FlyAway;
    else if(Local.X<-350&&Distance<1300)Next=EVeyrDragonMove::TailSmack;
    else if(Local.X<-80&&Distance<850)Next=EVeyrDragonMove::BackStomp;
    else if(Distance<850&&FMath::Abs(Local.Y)>180)Next=EVeyrDragonMove::ClawSwipe;
    else if(Local.X>350&&Local.X<1050&&FMath::Abs(Local.Y)<320)Next=EVeyrDragonMove::Bite;
    else if(FrontDot>.0f)Next=EVeyrDragonMove::Fire;
    else if(Distance<850)Next=EVeyrDragonMove::BackStomp;
    else {BeginReposition();return;}
    if(Next==LastMove&&RepeatedMoveCount>=2){BeginReposition();return;}
    BeginAttack(Next);
}

void AVeyrDragon::BeginReposition()
{
    MoveStart=Ground(GetActorLocation());
    const FVector Toward=Ground(Target->GetActorLocation()-MoveStart).GetSafeNormal();
    const float Distance=static_cast<float>(FVector::Dist2D(Target->GetActorLocation(),MoveStart));
    const float Travel=Distance<450?-350.f:Distance>1250?350.f:0.f;
    MoveEnd=ClampArena(MoveStart+Toward*Travel);
    TurnStart=GetActorRotation();
    const float DesiredYaw=Toward.Rotation().Yaw;
    TurnEnd=FRotator(0,TurnStart.Yaw+FMath::Clamp(FMath::FindDeltaAngleDegrees(TurnStart.Yaw,DesiredYaw),-75.f,75.f),0);
    RepeatedMoveCount=0; EnterState(EVeyrDragonState::Reposition,2.2f);
}

void AVeyrDragon::BeginAttack(EVeyrDragonMove Next)
{
    bJustRepositioned=false; Move=Next; ++TotalAttacks; ++StartedAttacks[MoveIndex(Move)];
    RepeatedMoveCount=Next==LastMove?RepeatedMoveCount+1:1; LastMove=Next;
    bContactConsumed=false; AttackOrigin=Ground(GetActorLocation()); AttackForward=Ground(GetActorForwardVector()).GetSafeNormal();
    MoveStart=Ground(GetActorLocation()); MoveEnd=MoveStart;
    switch(Move)
    {
        case EVeyrDragonMove::Fire:
            WindupDuration=1.75f; ActiveDuration=2.1f; RecoveryDuration=2.f; AttackDamage=30.f;
            AttackOrigin=Ground(GetActorTransform().TransformPosition(FVector(470,0,0))); break;
        case EVeyrDragonMove::FlyAway:
        {
            WindupDuration=1.6f; ActiveDuration=FlightSeconds+.35f; RecoveryDuration=2.3f; AttackDamage=38.f;
            const FVector Side=GetActorRightVector()*(TotalAttacks%2==0?1.f:-1.f);
            MoveEnd=ClampArena(Ground(Target->GetActorLocation())+Side*350.f,2500.f);
            // Fixed from the first anticipation frame, never tracks the target in flight.
            AttackOrigin=MoveEnd; break;
        }
        case EVeyrDragonMove::ClawSwipe:
            WindupDuration=1.15f; ActiveDuration=.48f; RecoveryDuration=1.6f; AttackDamage=29.f;
            AttackOrigin=Ground(GetActorTransform().TransformPosition(FVector(170,0,0))); break;
        case EVeyrDragonMove::BackStomp:
            WindupDuration=1.25f; ActiveDuration=.28f; RecoveryDuration=1.5f; AttackDamage=32.f;
            StompLeg=FVector::DistSquared(Target->GetActorLocation(),GetLegLocation(2))<FVector::DistSquared(Target->GetActorLocation(),GetLegLocation(3))?2:3;
            AttackOrigin=Ground(GetActorTransform().TransformPosition(RestFeet[StompLeg])); break;
        case EVeyrDragonMove::TailSmack:
            WindupDuration=1.45f; ActiveDuration=.65f; RecoveryDuration=1.8f; AttackDamage=30.f;
            AttackForward=-AttackForward; break;
        case EVeyrDragonMove::Bite:
            WindupDuration=1.05f; ActiveDuration=.3f; RecoveryDuration=1.6f; AttackDamage=34.f;
            AttackOrigin=Ground(GetActorTransform().TransformPosition(FVector(300,0,0))); break;
    }
    EnterState(EVeyrDragonState::Windup,WindupDuration);
    if(bUsingCustomuseVisual)CommitImportedWarning();
}

FVeyrDragonFootprint AVeyrDragon::GetWarningFootprint() const
{
    if(bUsingCustomuseVisual){const auto All=GetWarningFootprints();return All.IsEmpty()?FVeyrDragonFootprint():All[0];}
    FVeyrDragonFootprint F;
    if(bEncounterStopped||(State!=EVeyrDragonState::Windup&&State!=EVeyrDragonState::Active))return F;
    F.Origin=AttackOrigin; F.Forward=AttackForward;
    switch(Move)
    {
        case EVeyrDragonMove::Fire:F.Shape=EVeyrDangerShape::Sector;F.InnerRadius=70;F.OuterRadius=1750;F.HalfAngleDegrees=76;break;
        case EVeyrDragonMove::FlyAway:F.Shape=EVeyrDangerShape::Circle;F.OuterRadius=600;break;
        case EVeyrDragonMove::ClawSwipe:F.Shape=EVeyrDangerShape::Sector;F.InnerRadius=110;F.OuterRadius=770;F.HalfAngleDegrees=112;break;
        case EVeyrDragonMove::BackStomp:F.Shape=EVeyrDangerShape::Circle;F.OuterRadius=310;break;
        case EVeyrDragonMove::TailSmack:F.Shape=EVeyrDangerShape::Sector;F.InnerRadius=370;F.OuterRadius=1300;F.HalfAngleDegrees=125;break;
        case EVeyrDragonMove::Bite:F.Shape=EVeyrDangerShape::Sector;F.InnerRadius=40;F.OuterRadius=700;F.HalfAngleDegrees=32;break;
    }
    return F;
}

FVeyrDragonFootprint AVeyrDragon::GetActiveFootprint() const
{
    if(bUsingCustomuseVisual){const auto All=GetActiveFootprints();return All.IsEmpty()?FVeyrDragonFootprint():All[0];}
    FVeyrDragonFootprint F;
    if(State!=EVeyrDragonState::Active||bEncounterStopped)return F;
    if(Move==EVeyrDragonMove::FlyAway&&StateElapsed<FlightSeconds)return F;
    F=GetWarningFootprint(); F.bDamaging=F.Shape!=EVeyrDangerShape::None;
    const float T=FMath::Clamp(StateElapsed/FMath::Max(.001f,ActiveDuration),0.f,1.f);
    float Sweep=0;
    if(Move==EVeyrDragonMove::Fire){Sweep=FMath::Lerp(-64.f,64.f,T);F.HalfAngleDegrees=12;}
    else if(Move==EVeyrDragonMove::ClawSwipe){Sweep=FMath::Lerp(-80.f,80.f,T);F.HalfAngleDegrees=32;}
    else if(Move==EVeyrDragonMove::TailSmack){Sweep=FMath::Lerp(-100.f,100.f,T);F.HalfAngleDegrees=25;}
    F.Forward=F.Forward.RotateAngleAxis(Sweep,FVector::UpVector);
    return F;
}

bool AVeyrDragon::ContainsPoint(const FVeyrDragonFootprint& F,const FVector& Point)
{
    const FVector P=Ground(Point),Delta=P-Ground(F.Origin);
    const float Radius=static_cast<float>(Delta.Size());
    if(F.Shape==EVeyrDangerShape::None)return false;
    if(F.Shape==EVeyrDangerShape::Capsule)return DistanceToSegment2D(P,Ground(F.Origin),Ground(F.End))<=F.OuterRadius;
    if(Radius>F.OuterRadius||Radius<F.InnerRadius)return false;
    if(F.Shape==EVeyrDangerShape::Circle||Radius<.01f)return true;
    const float Cos=FVector::DotProduct(Delta.GetSafeNormal(),Ground(F.Forward).GetSafeNormal());
    return Cos>=FMath::Cos(FMath::DegreesToRadians(F.HalfAngleDegrees));
}

bool AVeyrDragon::IsPointInsideWarning(const FVector& Point) const {return ContainsAny(GetWarningFootprints(),Point);}
bool AVeyrDragon::IsPointInsideActiveDanger(const FVector& Point) const {return ContainsAny(GetActiveFootprints(),Point);}

void AVeyrDragon::TryDamageTarget()
{
    if(bContactConsumed||!IsValid(Target)||Target->IsDead()||IsDead())return;
    if(bUsingCustomuseVisual)
    {
        if(!bImportedTargetsValid||!bImportedAttackCacheReady||!MissingVisualClip.IsNone())return;
        const TArray<FVeyrDragonContact> Contacts=GetImportedContacts();
        bool bHit=false;
        if(Move==EVeyrDragonMove::Fire)
        {
            const FVeyrDragonFlameBeam Beam=GetActiveFlameBeam();bHit=FlameHitsKnight(Beam);
            if(bPreviousContactPoseValid&&PreviousFlame.bDamaging)
                for(int32 Step=1;Step<16&&!bHit;++Step)
                {
                    FVeyrDragonFlameBeam Between=Beam;const float A=Step/16.f;
                    Between.Origin=FMath::Lerp(PreviousFlame.Origin,Beam.Origin,A);
                    Between.Direction=FMath::Lerp(PreviousFlame.Direction,Beam.Direction,A).GetSafeNormal();
                    bHit=FlameHitsKnight(Between);
                }
            PreviousFlame=Beam;
        }
        else if(Move==EVeyrDragonMove::FlyAway)
            bHit=StateElapsed>=FlightSeconds&&ContainsAny(GetActiveFootprints(),Target->GetFootLocation());
        else
        {
            bHit=ImportedContactHitsKnight(Contacts);
            // Sweep sampled bone contacts, not an unrelated proxy arc. Dense
            // bounded intermediate capsules prevent a stalled frame tunnelling.
            if(bPreviousContactPoseValid&&PreviousContacts.Num()==Contacts.Num())
                for(int32 Step=1;Step<16&&!bHit;++Step)
                {
                    TArray<FVeyrDragonContact> Between;
                    for(int32 I=0;I<Contacts.Num();++I)
                    {
                        FVeyrDragonContact C=Contacts[I];const float A=Step/16.f;
                        C.Start=FMath::Lerp(PreviousContacts[I].Start,C.Start,A);
                        C.End=FMath::Lerp(PreviousContacts[I].End,C.End,A);Between.Add(C);
                    }
                    bHit=ImportedContactHitsKnight(Between);
                }
        }
        PreviousContacts=Contacts;bPreviousContactPoseValid=true;
        if(!bHit)return;
        // A committed warning is an absolute promise, including interpolation
        // and transition poses. Fail closed and expose any envelope miss.
        if(!ContainsAny(CommittedWarning,Target->GetFootLocation()))
        {++WarningContainmentFailures;ImportedCombatDiagnostic=TEXT("Active contact escaped committed warning; damage suppressed");return;}
        bContactConsumed=true;++DamageContactCount;const float Before=Target->Health;
        const FVector Source=Move==EVeyrDragonMove::Fire||Move==EVeyrDragonMove::Bite?GetMouthLocation():
            Contacts.IsEmpty()?AttackOrigin:Contacts[0].Start;
        Target->ApplyBossDamage(AttackDamage,Source,false);
        if(Target->Health>=Before-.001f)++AvoidedContactCount;
        return;
    }
    const FVeyrDragonFootprint Footprint=GetActiveFootprint();
    if(!Footprint.bDamaging||!ContainsPoint(Footprint,Target->GetActorLocation()))return;
    bContactConsumed=true; ++DamageContactCount;
    const float Before=Target->Health;
    Target->ApplyBossDamage(AttackDamage,Footprint.Origin,false);
    if(Target->Health>=Before-.001f)++AvoidedContactCount;
}

bool AVeyrDragon::SwordContact(const FVector& Origin,const FVector& Forward,const FVector& Point,float Radius,float& Score)
{
    const FVector Delta=Point-Origin; Score=FMath::Max(0.f,static_cast<float>(Delta.Size())-Radius);
    if(Score>260.f||FMath::Abs(Delta.Z)>260.f)return false;
    const FVector Flat=Ground(Delta);
    return Flat.SizeSquared()<1600.f||FVector::DotProduct(Ground(Forward).GetSafeNormal(),Flat.GetSafeNormal())>=.2f;
}

void AVeyrDragon::ReceiveSword(const FVector& Origin,const FVector& Forward,bool bHeavy,int32 SwingId)
{
    if(IsDead()||bEncounterStopped||IsAirborne()||AcceptedSwings.Contains(SwingId)||Ground(Forward).IsNearlyZero()||
       (bUsingCustomuseVisual&&!bImportedTargetsValid))return;
    int32 Region=-1; float Best=TNumericLimits<float>::Max();
    for(int32 I=0;I<4;++I)
    {
        float Score;
        if(SwordContact(Origin,Forward,GetLegLocation(I),75.f,Score)&&Score<Best){Best=Score;Region=I;}
    }
    float Score;
    if(SwordContact(Origin,Forward,GetHeadLocation(),100.f,Score)&&Score<Best){Best=Score;Region=4;}
    if(Region<0)return;
    ApplySwordRegion(Region,bHeavy,SwingId);
}

bool AVeyrDragon::ReceiveSwordSweep(const FVector& PreviousBase,const FVector& PreviousTip,
                                  const FVector& CurrentBase,const FVector& CurrentTip,bool bHeavy,int32 SwingId)
{
    if(IsDead()||bEncounterStopped||IsAirborne()||AcceptedSwings.Contains(SwingId)||
       (bUsingCustomuseVisual&&!bImportedTargetsValid))return false;
    if(PreviousBase.ContainsNaN()||PreviousTip.ContainsNaN()||CurrentBase.ContainsNaN()||CurrentTip.ContainsNaN())return false;
    if(FVector::DistSquared(CurrentBase,CurrentTip)<1.f)return false;
    // Two triangles cover the swept blade quadrilateral. A small blade radius
    // complements the measured anatomical target radii; no facing cone is used.
    auto Distance=[&](const FVector& Point)
    {
        float D=FMath::Min(FMath::PointDistToSegment(Point,CurrentBase,CurrentTip),FMath::PointDistToSegment(Point,PreviousBase,PreviousTip));
        D=FMath::Min(D,static_cast<float>(FMath::PointDistToSegment(Point,PreviousBase,CurrentBase)));
        D=FMath::Min(D,static_cast<float>(FMath::PointDistToSegment(Point,PreviousTip,CurrentTip)));
        if(FVector::CrossProduct(CurrentTip-CurrentBase,PreviousTip-CurrentBase).SizeSquared()>1.e-4f)
            D=FMath::Min(D,static_cast<float>(FVector::Dist(Point,FMath::ClosestPointOnTriangleToPoint(Point,CurrentBase,CurrentTip,PreviousTip))));
        if(FVector::CrossProduct(PreviousTip-CurrentBase,PreviousBase-CurrentBase).SizeSquared()>1.e-4f)
            D=FMath::Min(D,static_cast<float>(FVector::Dist(Point,FMath::ClosestPointOnTriangleToPoint(Point,CurrentBase,PreviousTip,PreviousBase))));
        return D;
    };
    int32 Region=-1;float Best=TNumericLimits<float>::Max();
    for(int32 I=0;I<5;++I)
    {
        const float Radius=I<4?75.f:100.f;
        const float D=Distance(I<4?GetLegLocation(I):GetHeadLocation());
        if(D<=Radius+8.f&&D-Radius<Best){Best=D-Radius;Region=I;}
    }
    if(Region<0)return false;
    ApplySwordRegion(Region,bHeavy,SwingId);
    return true;
}

void AVeyrDragon::ApplySwordRegion(int32 Region,bool bHeavy,int32 SwingId)
{
    AcceptedSwings.Add(SwingId); RecentSwings.Add(SwingId);
    if(RecentSwings.Num()>512){AcceptedSwings.Remove(RecentSwings[0]);RecentSwings.RemoveAt(0);}
    LastHitRegion=Region; ++SwordContactCount;
    LastSwordDamage=Region<4?(bHeavy?62.f:28.f):IsHeadExposed()?(bHeavy?270.f:125.f):(bHeavy?75.f:38.f);
    if(Region==4&&IsHeadExposed())++HeadBonusHitCount;
    Health=FMath::Max(0.f,Health-LastSwordDamage);
    if(Region<4)LegFlash[Region]=1;
    if(Health<=0){EnterState(EVeyrDragonState::Dead,3.4f);return;}
    if(Region<4&&CanStagger())
    {
        LegStagger[Region]=FMath::Min(100.f,LegStagger[Region]+(bHeavy?45.f:25.f));
        if(LegStagger[Region]>=100.f){StruckLeg=Region;++CollapseCount;EnterState(EVeyrDragonState::Buckle,.65f);}
    }
}

bool AVeyrDragon::CanStagger() const
{
    return StaggerProtection<=0&&State!=EVeyrDragonState::Buckle&&State!=EVeyrDragonState::Collapse&&State!=EVeyrDragonState::Exposed&&State!=EVeyrDragonState::Rise&&State!=EVeyrDragonState::Dead;
}
FVector AVeyrDragon::GetMouthLocation() const {return bUsingCustomuseVisual?ImportedMouthWorld:GetHeadLocation();}
FVector AVeyrDragon::GetHeadLocation() const {return bUsingCustomuseVisual?ImportedHeadWorld:GetActorTransform().TransformPosition(HeadLocal);}
FVector AVeyrDragon::GetLegLocation(int32 Index) const {const int32 I=FMath::Clamp(Index,0,3);return bUsingCustomuseVisual?ImportedFeetWorld[I]:GetActorTransform().TransformPosition(LegLocal[I]);}
float AVeyrDragon::GetLegStagger(int32 Index) const {return LegStagger[FMath::Clamp(Index,0,3)];}
float AVeyrDragon::GetHeadWindowRemaining() const {return IsHeadExposed()?FMath::Max(0.f,7.f-StateElapsed):0.f;}
bool AVeyrDragon::IsAirborne() const {return State==EVeyrDragonState::Active&&Move==EVeyrDragonMove::FlyAway&&StateElapsed<FlightSeconds;}
int32 AVeyrDragon::GetAttackCount(EVeyrDragonMove Attack) const {const int32 I=MoveIndex(Attack);return I>=0&&I<6?StartedAttacks[I]:0;}
int32 AVeyrDragon::GetCompletedAttackCount(EVeyrDragonMove Attack) const {const int32 I=MoveIndex(Attack);return I>=0&&I<6?CompletedAttacks[I]:0;}

FText AVeyrDragon::GetStateLabel() const
{
    if(bEncounterStopped)return FText::FromString(TEXT("THE WARDEN ENDURES"));
    switch(State)
    {
        case EVeyrDragonState::Buckle:return FText::FromString(TEXT("LEG BUCKLES"));
        case EVeyrDragonState::Collapse:return FText::FromString(TEXT("THE WARDEN FALLS"));
        case EVeyrDragonState::Exposed:return FText::FromString(TEXT("HEAD EXPOSED — STRIKE THE CROWN"));
        case EVeyrDragonState::Rise:return FText::FromString(TEXT("VEYR RISES — WITHDRAW"));
        case EVeyrDragonState::Dead:return FText::FromString(TEXT("CINDER EXTINGUISHED"));
        case EVeyrDragonState::Recovery:return FText::FromString(TEXT("OPENING — STRIKE OR HEAL"));
        case EVeyrDragonState::Reposition:return FText::FromString(TEXT("REPOSITIONING — FOLLOW THE FOOTFALLS"));
        case EVeyrDragonState::Idle:return FText::FromString(TEXT("VEYR WATCHES"));
        default:break;
    }
    const TCHAR* Name=TEXT("FURNACE BITE");
    switch(Move)
    {
        case EVeyrDragonMove::Fire:Name=TEXT("BELLOWS SWEEP");break;
        case EVeyrDragonMove::FlyAway:Name=TEXT("FLIGHT — CLEAR THE LANDING CIRCLE");break;
        case EVeyrDragonMove::ClawSwipe:Name=TEXT("CINDER CLAW");break;
        case EVeyrDragonMove::BackStomp:Name=TEXT("REAR BASALT STOMP");break;
        case EVeyrDragonMove::TailSmack:Name=TEXT("COUNTERWEIGHT TAIL");break;
        default:break;
    }
    return FText::FromString(FString(State==EVeyrDragonState::Windup?TEXT("READ: "):TEXT(""))+Name);
}

float AVeyrDragon::GetDownAmount() const
{
    switch(State)
    {
        case EVeyrDragonState::Collapse:return Ease(StateElapsed/StateDuration);
        case EVeyrDragonState::Exposed:return 1;
        case EVeyrDragonState::Rise:return 1-Ease(StateElapsed/StateDuration);
        case EVeyrDragonState::Dead:return FMath::Lerp(DeathStartDown,1.f,Ease(StateElapsed/2.4f));
        default:return 0;
    }
}

void AVeyrDragon::SetSegment(UStaticMeshComponent* Part,const FVector& A,const FVector& B,float Width)
{
    const FVector Delta=B-A; Part->SetRelativeLocation((A+B)*.5);
    Part->SetRelativeRotation(FQuat::FindBetweenNormals(FVector::UpVector,Delta.GetSafeNormal()));
    Part->SetRelativeScale3D(FVector(Width/100.f,Width/100.f,Delta.Size()/100.f));
}

void AVeyrDragon::UpdateTemporaryPresentation(float DeltaSeconds)
{
    // These poses explain rules only. They are not authored animation clips or final asset work.
    const float Down=GetDownAmount();
    const float Buckle=State==EVeyrDragonState::Buckle?Ease(StateElapsed/StateDuration):
        State==EVeyrDragonState::Collapse?1-Ease(StateElapsed/StateDuration):
        State==EVeyrDragonState::Dead?DeathStartBuckle*(1-Ease(StateElapsed/2.4f)):0.f;
    const float Breath=IsDead()?0.f:FMath::Sin(Clock*1.8f)*8.f*(1-Down);
    const float Roll=(StruckLeg%2==0?-1.f:1.f)*(Buckle*12.f+Down*14.f);
    const FVector Torso(0,0,490.f-Down*305.f-Buckle*65.f+Breath);
    BodyMesh->SetRelativeLocation(Torso); BodyMesh->SetRelativeRotation(FRotator(Down*-6,0,Roll));
    ChestMesh->SetRelativeLocation(Torso+FVector(200,0,15)); ChestMesh->SetRelativeRotation(BodyMesh->GetRelativeRotation());
    HeadLocal=FVector(FMath::Lerp(650.f,700.f,Down),Down*(StruckLeg%2==0?-55.f:55.f),FMath::Lerp(350.f,130.f,Down)+Breath-Buckle*25.f);
    float HeadYaw=0,JawOpen=0;
    const float P=StateDuration>0?FMath::Clamp(StateElapsed/StateDuration,0.f,1.f):0.f;
    if(Move==EVeyrDragonMove::Fire&&(State==EVeyrDragonState::Windup||State==EVeyrDragonState::Active))
    {
        HeadYaw=State==EVeyrDragonState::Windup?-64.f*Ease(P):FMath::Lerp(-64.f,64.f,P);
        HeadLocal.Y=FMath::Sin(FMath::DegreesToRadians(HeadYaw))*90.f; JawOpen=State==EVeyrDragonState::Windup?P*26:26;
    }
    if(Move==EVeyrDragonMove::Bite)
    {
        if(State==EVeyrDragonState::Windup){HeadLocal.X-=70*Ease(P);JawOpen=32*P;}
        if(State==EVeyrDragonState::Active){HeadLocal.X+=140*Ease(P);HeadLocal.Z-=70*Ease(P);JawOpen=32*(1-P);}
        if(State==EVeyrDragonState::Recovery){HeadLocal.X+=140*(1-Ease(P));HeadLocal.Z-=70*(1-Ease(P));}
    }
    HeadMesh->SetRelativeLocation(HeadLocal); HeadMesh->SetRelativeRotation(FRotator(Down*8,HeadYaw,Roll*.3f));
    JawMesh->SetRelativeLocation(HeadLocal+FVector(60,0,-75)); JawMesh->SetRelativeRotation(FRotator(-JawOpen,HeadYaw,Roll*.3f));
    Tint(HeadMaterial,IsHeadExposed()?FLinearColor(1,.65,.1):FLinearColor(.4,.36,.24));
    for(int32 I=0;I<4;++I)
    {
        const float Side=I%2==0?-1.f:1.f;
        FVector Foot=RestFeet[I]; float Lift=0;
        if(State==EVeyrDragonState::Windup&&Move==EVeyrDragonMove::BackStomp&&I==StompLeg)Lift=Ease(P)*170;
        else if(State==EVeyrDragonState::Active&&Move==EVeyrDragonMove::BackStomp&&I==StompLeg)Lift=(1-Ease(FMath::Min(1.f,P*4)))*170;
        if(Move==EVeyrDragonMove::ClawSwipe&&I<2&&(State==EVeyrDragonState::Windup||State==EVeyrDragonState::Active))
        {
            const float Sweep=State==EVeyrDragonState::Windup?-80*Ease(P):FMath::Lerp(-80.f,80.f,P);
            const FVector Arc=FVector(550,0,0).RotateAngleAxis(Sweep+(I==0?-12:12),FVector::UpVector);
            Foot=FVector(170,0,90)+Arc; Lift=State==EVeyrDragonState::Windup?100*P:60;
        }
        if(State==EVeyrDragonState::Reposition)Lift+=FMath::Max(0.f,FMath::Sin(Clock*6+I*PI*.5f))*60;
        Foot.Z+=Lift;
        if(I==StruckLeg)Foot.Y+=Side*(Buckle*80+Down*95);
        const FVector Hip(I<2?180:-240,Side*185,Torso.Z-25);
        const FVector Knee(Foot.X-40,Side*(310+Down*50),FMath::Lerp(260.f,100.f,Down)-Buckle*(I==StruckLeg?70:15)+Lift*.6f);
        SetSegment(UpperLegMeshes[I],Hip,Knee,110); SetSegment(LowerLegMeshes[I],Knee,Foot,75);
        FootMeshes[I]->SetRelativeLocation(Foot); FootMeshes[I]->SetRelativeRotation(FRotator(0,0,Side*Down*15));
        LegLocal[I]=Foot+FVector(0,0,30);
        if(LegMaterials.IsValidIndex(I))Tint(LegMaterials[I],FMath::Lerp(FLinearColor(.16,.2,.23),FLinearColor(1,.42,.04),FMath::Max(LegFlash[I],LegStagger[I]/150.f)));
    }
    FVector Previous(-350,0,Torso.Z-50);
    float TailYaw=IsDead()?0.f:FMath::Sin(Clock*.9f)*5;
    if(Move==EVeyrDragonMove::TailSmack&&(State==EVeyrDragonState::Windup||State==EVeyrDragonState::Active))TailYaw=State==EVeyrDragonState::Windup?-100*Ease(P):FMath::Lerp(-100.f,100.f,P);
    for(int32 I=0;I<TailMeshes.Num();++I)
    {
        const float T=(I+1.f)/TailMeshes.Num();
        const FVector Direction=FVector(-1,0,0).RotateAngleAxis(TailYaw*T,FVector::UpVector);
        const FVector Next=FVector(-300,0,0)+Direction*(190+I*145)+FVector(0,0,FMath::Lerp(Torso.Z-50,75.f,T));
        SetSegment(TailMeshes[I],Previous,Next,FMath::Lerp(160.f,30.f,T));Previous=Next;
    }
    for(int32 I=0;I<2;++I)
    {
        const float Side=I==0?-1.f:1.f;
        const float Flap=IsAirborne()?FMath::Sin(StateElapsed*8)*35:Down*-35;
        WingMeshes[I]->SetRelativeLocation(FVector(-30,Side*540,Torso.Z+150));
        WingMeshes[I]->SetRelativeRotation(FRotator(0,Side*65,Side*(20+Flap)));
    }
}

void AVeyrDragon::AddGroundLine(UInstancedStaticMeshComponent* Lines,const FVector& A,const FVector& B,float Width)
{
    FVector Start=Ground(A),End=Ground(B);Start.Z=9;End.Z=9;
    const FVector Delta=End-Start;
    if(Delta.SizeSquared()<.01)return;
    Lines->AddInstance(FTransform(Delta.Rotation(),(Start+End)*.5,FVector(Delta.Size()/100,Width/100,6.f/100)),true);
}

void AVeyrDragon::DrawFootprint(UInstancedStaticMeshComponent* Lines,const FVeyrDragonFootprint& F,bool bBright,const TArray<FVeyrDragonFootprint>* Union,int32 OwnIndex)
{
    if(F.Shape==EVeyrDangerShape::None)return;
    const float Width=bBright?22.f:13.f;
    auto Line=[&](const FVector& A,const FVector& B,float W)
    {
        const int32 Pieces=Union&&Union->Num()>1?FMath::Max(1,FMath::CeilToInt(FVector::Dist(A,B)/40.f)):1;
        for(int32 Piece=0;Piece<Pieces;++Piece)
        {
            const FVector Start=FMath::Lerp(A,B,Piece/static_cast<float>(Pieces));
            const FVector End=FMath::Lerp(A,B,(Piece+1.f)/Pieces);bool Interior=false;
            if(Union)for(int32 I=0;I<Union->Num();++I)
                if(I!=OwnIndex&&ContainsPoint((*Union)[I],(Start+End)*.5f)){Interior=true;break;}
            if(!Interior)AddGroundLine(Lines,Start,End,W);
        }
    };
    if(F.Shape==EVeyrDangerShape::Capsule)
    {
        const FVector D=Ground(F.End-F.Origin).GetSafeNormal();const FVector Side=FVector::CrossProduct(FVector::UpVector,D)*F.OuterRadius;
        Line(F.Origin+Side,F.End+Side,Width);Line(F.Origin-Side,F.End-Side,Width);
        const FVector Axis=D.IsNearlyZero()?FVector::ForwardVector:D;
        for(int32 I=0;I<12;++I)
        {
            const float A=-90.f+I*15.f,B=A+15.f;
            Line(F.End+Axis.RotateAngleAxis(A,FVector::UpVector)*F.OuterRadius,
                F.End+Axis.RotateAngleAxis(B,FVector::UpVector)*F.OuterRadius,Width);
            Line(F.Origin-Axis.RotateAngleAxis(A,FVector::UpVector)*F.OuterRadius,
                F.Origin-Axis.RotateAngleAxis(B,FVector::UpVector)*F.OuterRadius,Width);
        }
        return;
    }
    const float Half=F.Shape==EVeyrDangerShape::Circle?180.f:F.HalfAngleDegrees;
    const int32 Segments=FMath::Max(12,FMath::CeilToInt(Half*2/6));
    for(int32 I=0;I<Segments;++I)
    {
        const FVector A=F.Forward.RotateAngleAxis(FMath::Lerp(-Half,Half,I/static_cast<float>(Segments)),FVector::UpVector);
        const FVector B=F.Forward.RotateAngleAxis(FMath::Lerp(-Half,Half,(I+1.f)/Segments),FVector::UpVector);
        Line(F.Origin+A*F.OuterRadius,F.Origin+B*F.OuterRadius,Width);
        if(F.InnerRadius>0)Line(F.Origin+A*F.InnerRadius,F.Origin+B*F.InnerRadius,Width);
        if(bBright&&I%2==0)Line(F.Origin+A*F.InnerRadius,F.Origin+A*F.OuterRadius,Width*.65f);
    }
    if(Half<179)
        for(int32 Side=-1;Side<=1;Side+=2)
        {
            const FVector Ray=F.Forward.RotateAngleAxis(Half*Side,FVector::UpVector);
            Line(F.Origin+Ray*F.InnerRadius,F.Origin+Ray*F.OuterRadius,Width);
        }
}

void AVeyrDragon::UpdateTelegraphs()
{
    DangerLines->ClearInstances();
    if(!bWarningDrawn)
    {
        WarningLines->ClearInstances();const auto Warning=GetWarningFootprints();
        for(int32 I=0;I<Warning.Num();++I)DrawFootprint(WarningLines,Warning[I],false,&Warning,I);
        bWarningDrawn=true;
    }
    const auto Active=GetActiveFootprints();
    for(int32 I=0;I<Active.Num();++I)DrawFootprint(DangerLines,Active[I],true,&Active,I);
}

FVector AVeyrDragon::ClampArena(const FVector& V,float Radius)
{
    FVector P=Ground(V);
    if(P.SizeSquared()>Radius*Radius)P=P.GetSafeNormal()*Radius;
    return P;
}


bool AVeyrDragon::ApplyCustomuseVisual(UVeyrVisualDefinition* Definition)
{
    if(!Definition||!ImportedPresentation)return false;
    ResetCameraOcclusionMaterials();
    if(!ImportedPresentation->SetVisualDefinition(Definition,false))return false;
    // A valid measured head and four feet are mandatory before hiding proxies.
    FTransform TargetPose;
    for(FName Name:{FName(TEXT("head")),FName(TEXT("leg0")),FName(TEXT("leg1")),FName(TEXT("leg2")),FName(TEXT("leg3")),FName(TEXT("mouth")),FName(TEXT("mouth_aim")),FName(TEXT("foot0")),FName(TEXT("foot1")),FName(TEXT("foot2")),FName(TEXT("foot3")),FName(TEXT("tail0")),FName(TEXT("tail1")),FName(TEXT("tail2")),FName(TEXT("tail3")),FName(TEXT("tail_tip"))})
        if(!ImportedPresentation->GetBoneTargetWorldTransform(Name,TargetPose))
        {
            bUsingCustomuseVisual=false;bImportedTargetsValid=false;
            ImportedPresentation->SetVisibility(false);
            for(UStaticMeshComponent* Part:TemporaryParts)if(Part)Part->SetVisibility(true);
            return false;
        }
    VisualDefinition=Definition;bUsingCustomuseVisual=true;
    for(UStaticMeshComponent* Part:TemporaryParts)if(Part)Part->SetVisibility(false);
    ImportedPresentation->SetVisibility(true);
    TemporaryLabel->SetVisibility(false);
    bImportedAttackCacheReady=AttackPoseProbe->SetVisualDefinition(Definition,false)&&CacheImportedAttackWarnings();
    AttackPoseProbe->SetVisibility(false);AttackPoseProbe->SetHiddenInGame(true);
    LastImportedClip=NAME_None;bImportedTransitionReady=false;
    UpdateImportedPresentation();
    InitializeCameraOcclusionMaterials();
    return true;
}

void AVeyrDragon::UpdateImportedPresentation()
{
    if(!bUsingCustomuseVisual||!VisualDefinition||!ImportedPresentation)return;
    bImportedTargetsValid=false;
    FString Name;
    switch(State)
    {
        case EVeyrDragonState::Idle:Name=TEXT("Idle");break;
        case EVeyrDragonState::Reposition:Name=TEXT("Walk");break;
        case EVeyrDragonState::Buckle:Name=FString::Printf(TEXT("Buckle%d"),StruckLeg);break;
        case EVeyrDragonState::Collapse:Name=TEXT("Collapse");break;
        case EVeyrDragonState::Exposed:Name=TEXT("Exposed");break;
        case EVeyrDragonState::Rise:Name=TEXT("Rise");break;
        case EVeyrDragonState::Dead:Name=DeathStartDown>.5f?TEXT("DeathDown"):TEXT("Death");break;
        default:
        {
            static const TCHAR* Moves[]={TEXT("Fire"),TEXT("Flight"),TEXT("Claw"),TEXT("Stomp"),TEXT("Tail"),TEXT("Bite")};
            Name=Moves[static_cast<int32>(Move)];
            if(Move==EVeyrDragonMove::BackStomp)Name+=FString::FromInt(StompLeg);
            if(Move==EVeyrDragonMove::ClawSwipe)
                Name=ImportedMoveClip(Move,ClawLeg,TEXT("")).ToString();
            Name+=State==EVeyrDragonState::Windup?TEXT("Windup"):State==EVeyrDragonState::Active?TEXT("Active"):TEXT("Recovery");
            break;
        }
    }
    const FName Clip(*Name);
    bool Sampled=false;
    if(VisualDefinition->Clips.Contains(Clip)&&VisualDefinition->Clips[Clip].Sequence)
    {
        const FVeyrVisualClip& Config=VisualDefinition->Clips[Clip];
        const float End=Config.EndSeconds<0.f?Config.Sequence->GetPlayLength():Config.EndSeconds;
        const float Duration=End-Config.StartSeconds;
        const bool bLoopWrapped=Config.bLoop&&Duration>0.f&&ImportedPresentation->CurrentClip==Clip&&
            FMath::Fmod(Clock,Duration)+.0001f<ImportedPresentation->CurrentTrimmedSeconds;
        if(LastImportedClip!=Clip||LastImportedState!=State||bLoopWrapped)
        {
            // Definition activation starts in the authored pose immediately;
            // do not freeze a blend from the bind pose before encounter input.
            bImportedTransitionReady=!LastImportedClip.IsNone()&&ImportedPresentation->BeginTransition();
            ImportedTransitionStarted=Clock;LastImportedClip=Clip;LastImportedState=State;
        }
        const float Alpha=bImportedTransitionReady?FMath::Clamp((Clock-ImportedTransitionStarted)/.12f,0.f,1.f):1.f;
        const bool Loop=VisualDefinition->Clips[Clip].bLoop;
        Sampled=Loop?ImportedPresentation->SampleClipTimeBlended(Clip,Clock,Alpha):
            ImportedPresentation->SampleClipPhaseBlended(Clip,StateElapsed/FMath::Max(.001f,StateDuration),Alpha);
    }
    MissingVisualClip=Sampled?NAME_None:Clip;
    if(!Sampled)
    {
        LastImportedClip=NAME_None;bImportedTransitionReady=false;
        if(!ImportedPresentation->SampleReferencePose())return;
    }
    FTransform Head,Feet[4];
    if(!ImportedPresentation->GetBoneTargetWorldTransform(TEXT("head"),Head))return;
    for(int32 I=0;I<4;++I)
        if(!ImportedPresentation->GetBoneTargetWorldTransform(FName(*FString::Printf(TEXT("leg%d"),I)),Feet[I]))return;
    ImportedHeadWorld=Head.GetLocation();
    for(int32 I=0;I<4;++I)ImportedFeetWorld[I]=Feet[I].GetLocation();
    FTransform Mouth,Aim,Foot,Tail;
    if(!Sampled||!ImportedPresentation->GetBoneTargetWorldTransform(TEXT("mouth"),Mouth)||
       !ImportedPresentation->GetBoneTargetWorldTransform(TEXT("mouth_aim"),Aim))return;
    ImportedMouthWorld=Mouth.GetLocation();ImportedMouthAimWorld=Aim.GetLocation();
    for(int32 I=0;I<4;++I)
    {
        if(!ImportedPresentation->GetBoneTargetWorldTransform(FName(*FString::Printf(TEXT("foot%d"),I)),Foot)||
           !ImportedPresentation->GetBoneTargetWorldTransform(FName(*FString::Printf(TEXT("tail%d"),I)),Tail))return;
        ImportedContactFeetWorld[I]=Foot.GetLocation();ImportedTailWorld[I]=Tail.GetLocation();
    }
    if(!ImportedPresentation->GetBoneTargetWorldTransform(TEXT("tail_tip"),Tail))return;
    bImportedTargetsValid=!ImportedMouthWorld.Equals(ImportedMouthAimWorld,.01f);
}

FName AVeyrDragon::ImportedMoveClip(EVeyrDragonMove Attack,int32 Leg,const TCHAR* Suffix) const
{
    static const TCHAR* Names[]={TEXT("Fire"),TEXT("Flight"),TEXT("Claw"),TEXT("Stomp"),TEXT("Tail"),TEXT("Bite")};
    FString Name=Names[static_cast<int32>(Attack)];
    if(Attack==EVeyrDragonMove::BackStomp)Name+=FString::FromInt(Leg);
    if(Attack==EVeyrDragonMove::ClawSwipe)
    {
        const FString Numbered=Name+FString::FromInt(Leg);
        if(Leg==1||(VisualDefinition&&VisualDefinition->Clips.Contains(FName(*(Numbered+TEXT("Active"))))))Name=Numbered;
    }
    return FName(*(Name+Suffix));
}

bool AVeyrDragon::ContainsAny(const TArray<FVeyrDragonFootprint>& Footprints,const FVector& Point)
{
    for(const auto& F:Footprints)if(ContainsPoint(F,Point))return true;
    return false;
}

bool AVeyrDragon::ReadImportedContactPose(UVeyrSkeletalPresentation* Presentation,EVeyrDragonMove Attack,int32 Leg,
    TArray<FVeyrDragonContact>& OutContacts,FVeyrDragonFlameBeam& OutBeam) const
{
    OutContacts.Reset();OutBeam.bDamaging=false;
    if(!Presentation||!Presentation->bPoseEvaluated)return false;
    auto Point=[&](const FName Name,FVector& P)
    {FTransform T;if(!Presentation->GetBoneTargetWorldTransform(Name,T))return false;P=T.GetLocation();return true;};
    auto Contact=[&](FVector A,FVector B,float Radius)
    {FVeyrDragonContact C;C.Start=A;C.End=B;C.Radius=Radius;OutContacts.Add(C);};
    FVector A,B;
    switch(Attack)
    {
        case EVeyrDragonMove::Fire:
            if(!Point(TEXT("mouth"),A)||!Point(TEXT("mouth_aim"),B)||(B-A).IsNearlyZero())return false;
            OutBeam.Origin=A;OutBeam.Direction=(B-A).GetSafeNormal();OutBeam.bDamaging=true;return true;
        case EVeyrDragonMove::Bite:
            if(!Point(TEXT("head"),A)||!Point(TEXT("mouth"),B))return false;
            Contact(A,B,100.f);return true;
        case EVeyrDragonMove::ClawSwipe:
        case EVeyrDragonMove::BackStomp:
            if(!Point(FName(*FString::Printf(TEXT("foot%d"),Leg)),A))return false;
            // Stomp includes its visible ground impact; claw follows the actual paw.
            Contact(A,A,Attack==EVeyrDragonMove::BackStomp?230.f:115.f);return true;
        case EVeyrDragonMove::TailSmack:
        {
            const float Radii[]={130.f,95.f,65.f};
            if(!Point(TEXT("tail0"),A))return false;
            for(int32 I=1;I<4;++I)
            {
                if(!Point(FName(*FString::Printf(TEXT("tail%d"),I)),B))return false;
                Contact(A,B,Radii[I-1]);A=B;
            }
            if(!Point(TEXT("tail_tip"),B))return false;
            Contact(A,B,35.f);
            return true;
        }
        case EVeyrDragonMove::FlyAway:return true;
    }
    return false;
}

TArray<FVeyrDragonContact> AVeyrDragon::GetImportedContacts() const
{
    TArray<FVeyrDragonContact> Contacts;FVeyrDragonFlameBeam Beam;
    if(bImportedTargetsValid)ReadImportedContactPose(ImportedPresentation,Move,
        Move==EVeyrDragonMove::ClawSwipe?ClawLeg:StompLeg,Contacts,Beam);
    return Contacts;
}

FVeyrDragonFlameBeam AVeyrDragon::GetActiveFlameBeam() const
{
    FVeyrDragonFlameBeam Beam;
    if(!bUsingCustomuseVisual||!bImportedTargetsValid||!bImportedAttackCacheReady||
       State!=EVeyrDragonState::Active||Move!=EVeyrDragonMove::Fire||bEncounterStopped||!MissingVisualClip.IsNone())return Beam;
    Beam.Origin=ImportedMouthWorld;Beam.Direction=(ImportedMouthAimWorld-ImportedMouthWorld).GetSafeNormal();
    Beam.bDamaging=!Beam.Direction.IsNearlyZero();return Beam;
}

FVeyrDragonFootprint AVeyrDragon::ProjectFlameToGround(const FVeyrDragonFlameBeam& Beam,float Padding) const
{
    FVeyrDragonFootprint F;
    if(!Beam.bDamaging)return F;
    const float Radius=IsValid(Target)?Target->GetCapsuleComponent()->GetScaledCapsuleRadius():40.f;
    const float HalfHeight=IsValid(Target)?Target->GetCapsuleComponent()->GetScaledCapsuleHalfHeight():122.f;
    const float K=FMath::Tan(FMath::DegreesToRadians(Beam.HalfAngleDegrees));
    // Cover the finite cone by bounded axial balls. Each ball includes the
    // interval between samples, so this conservative ground projection has no
    // sampling holes. Intersect height with the actual upright knight capsule.
    const int32 Steps=32;const float Step=Beam.Length/Steps;
    bool Found=false;float MaximumRadius=0.f;
    for(int32 I=0;I<=Steps;++I)
    {
        const float Along=I*Step;const FVector P=Beam.Origin+Beam.Direction*Along;
        const float R=Along*K+Radius+Padding+Step*.5f*(1.f+K);
        const float Dz=FMath::Max(0.f,FMath::Max(static_cast<float>(Radius-P.Z),static_cast<float>(P.Z-(2.f*HalfHeight-Radius))));
        if(Dz>R)continue;
        const float GroundRadius=FMath::Sqrt(FMath::Max(0.f,R*R-Dz*Dz));
        if(!Found){F.Origin=Ground(P);Found=true;}
        F.End=Ground(P);MaximumRadius=FMath::Max(MaximumRadius,GroundRadius);
    }
    if(Found){F.Shape=EVeyrDangerShape::Capsule;F.Forward=Beam.Direction.GetSafeNormal2D();F.OuterRadius=MaximumRadius;F.bDamaging=true;}
    return F;
}

bool AVeyrDragon::CacheImportedAttackWarnings()
{
    LocalAttackWarnings.Reset();
    const FTransform Actor=GetActorTransform();
    const float KnightRadius=IsValid(Target)?Target->GetCapsuleComponent()->GetScaledCapsuleRadius():40.f;
    for(EVeyrDragonMove Attack:{EVeyrDragonMove::Fire,EVeyrDragonMove::ClawSwipe,EVeyrDragonMove::BackStomp,EVeyrDragonMove::TailSmack,EVeyrDragonMove::Bite})
    {
        const int32 First=Attack==EVeyrDragonMove::BackStomp?2:0;
        const int32 Count=Attack==EVeyrDragonMove::BackStomp||Attack==EVeyrDragonMove::ClawSwipe?2:1;
        for(int32 Leg=First;Leg<First+Count;++Leg)
        {
            const FName Clip=ImportedMoveClip(Attack,Leg,TEXT("Active"));
            if(!VisualDefinition->Clips.Contains(Clip))
            {
                if(Attack==EVeyrDragonMove::ClawSwipe&&Leg==1)continue;
                ImportedCombatDiagnostic=TEXT("Attack envelope clip missing: ")+Clip.ToString();return false;
            }
            TArray<FVeyrDragonFootprint> Envelope;
            TArray<FVeyrDragonContact> Previous;
            // Computed once per definition on a hidden non-ticking CPU pose
            // component. No gameplay actor pose/state/physics is changed.
            for(int32 I=0;I<=32;++I)
            {
                if(!AttackPoseProbe->SampleClipPhase(Clip,I/32.f))
                {ImportedCombatDiagnostic=AttackPoseProbe->LastError;return false;}
                TArray<FVeyrDragonContact> Contacts;FVeyrDragonFlameBeam Beam;
                if(!ReadImportedContactPose(AttackPoseProbe,Attack,Leg,Contacts,Beam))
                {ImportedCombatDiagnostic=TEXT("Attack envelope semantic target missing");return false;}
                TArray<FVeyrDragonFootprint> Sample;
                if(Attack==EVeyrDragonMove::Fire)
                {
                    // Adjacent fire yaw steps are4 degrees. Extra100cm covers
                    // the far-edge chord and mouth translation between poses.
                    auto F=ProjectFlameToGround(Beam,100.f);if(F.Shape!=EVeyrDangerShape::None)Sample.Add(F);
                }
                else for(int32 J=0;J<Contacts.Num();++J)
                {
                    const auto& C=Contacts[J];FVeyrDragonFootprint F;
                    F.Shape=EVeyrDangerShape::Capsule;F.Origin=Ground(C.Start);F.End=Ground(C.End);
                    F.OuterRadius=C.Radius+KnightRadius+35.f;
                    if(Previous.IsValidIndex(J))F.OuterRadius+=FMath::Max(FVector::Dist(C.Start,Previous[J].Start),FVector::Dist(C.End,Previous[J].End));
                    Sample.Add(F);
                }
                for(auto& F:Sample)
                {
                    F.Origin=Actor.InverseTransformPosition(F.Origin);F.End=Actor.InverseTransformPosition(F.End);
                    F.Forward=Actor.InverseTransformVectorNoScale(F.Forward);F.bDamaging=false;
                    // Stationary bite/stomp samples need no duplicated rings.
                    bool Duplicate=false;
                    for(const auto& Existing:Envelope)
                        if(Existing.Shape==F.Shape&&Existing.Origin.Equals(F.Origin,2.f)&&Existing.End.Equals(F.End,2.f)&&FMath::IsNearlyEqual(Existing.OuterRadius,F.OuterRadius,2.f)){Duplicate=true;break;}
                    if(!Duplicate)Envelope.Add(F);
                }
                Previous=Contacts;
            }
            if(Envelope.IsEmpty()){ImportedCombatDiagnostic=TEXT("Attack has no reachable ground warning: ")+Clip.ToString();return false;}
            LocalAttackWarnings.Add(Clip,MoveTemp(Envelope));
        }
    }
    ImportedCombatDiagnostic=TEXT("Bone attack envelopes cached; native visual/contact verification pending");return true;
}

void AVeyrDragon::CommitImportedWarning()
{
    CommittedWarning.Reset();
    if(!bImportedAttackCacheReady)return;
    if(Move==EVeyrDragonMove::FlyAway)
    {
        FVeyrDragonFootprint F;F.Shape=EVeyrDangerShape::Circle;F.Origin=MoveEnd;F.OuterRadius=600.f;CommittedWarning.Add(F);return;
    }
    const auto* Local=LocalAttackWarnings.Find(ImportedMoveClip(Move,Move==EVeyrDragonMove::ClawSwipe?ClawLeg:StompLeg,TEXT("Active")));
    if(!Local)return;
    const FTransform Committed=GetActorTransform();
    for(auto F:*Local)
    {
        F.Origin=Committed.TransformPosition(F.Origin);F.End=Committed.TransformPosition(F.End);
        F.Forward=Committed.TransformVectorNoScale(F.Forward);CommittedWarning.Add(F);
    }
    if(!CommittedWarning.IsEmpty())AttackOrigin=CommittedWarning[0].Origin;
}

TArray<FVeyrDragonFootprint> AVeyrDragon::GetWarningFootprints() const
{
    if(bUsingCustomuseVisual)
        return !bEncounterStopped&&(State==EVeyrDragonState::Windup||State==EVeyrDragonState::Active)?CommittedWarning:TArray<FVeyrDragonFootprint>();
    const auto F=GetWarningFootprint();return F.Shape==EVeyrDangerShape::None?TArray<FVeyrDragonFootprint>():TArray<FVeyrDragonFootprint>{F};
}

TArray<FVeyrDragonFootprint> AVeyrDragon::GetActiveFootprints() const
{
    if(!bUsingCustomuseVisual)
    {const auto F=GetActiveFootprint();return F.Shape==EVeyrDangerShape::None?TArray<FVeyrDragonFootprint>():TArray<FVeyrDragonFootprint>{F};}
    TArray<FVeyrDragonFootprint> Result;
    if(State!=EVeyrDragonState::Active||bEncounterStopped||!bImportedTargetsValid||!bImportedAttackCacheReady||!MissingVisualClip.IsNone())return Result;
    if(Move==EVeyrDragonMove::Fire)
    {auto F=ProjectFlameToGround(GetActiveFlameBeam());if(F.Shape!=EVeyrDangerShape::None)Result.Add(F);return Result;}
    if(Move==EVeyrDragonMove::FlyAway)
    {if(StateElapsed>=FlightSeconds){Result=CommittedWarning;for(auto& F:Result)F.bDamaging=true;}return Result;}
    const float KnightRadius=IsValid(Target)?Target->GetCapsuleComponent()->GetScaledCapsuleRadius():40.f;
    for(const auto& C:GetImportedContacts())
    {
        FVeyrDragonFootprint F;F.Shape=EVeyrDangerShape::Capsule;F.Origin=Ground(C.Start);F.End=Ground(C.End);
        F.OuterRadius=C.Radius+KnightRadius;F.bDamaging=true;Result.Add(F);
    }
    return Result;
}

bool AVeyrDragon::CachedWarningContains(FName Clip,const FVector& WorldPoint) const
{
    const auto* Shapes=LocalAttackWarnings.Find(Clip);
    return Shapes&&ContainsAny(*Shapes,GetActorTransform().InverseTransformPosition(WorldPoint));
}

int32 AVeyrDragon::PredictPositionalMove(const FVector& Point) const
{
    const FVector Local=GetActorTransform().InverseTransformPosition(Point);const float Distance=Local.Size2D();
    if(!bUsingCustomuseVisual)
    {
        if(Distance>1750)return 1;
        if(Local.X<-350&&Distance<1300)return 4;
        if(Local.X<-80&&Distance<850)return 3;
        if(Distance<850&&FMath::Abs(Local.Y)>180)return 2;
        if(Local.X>350&&Local.X<1050&&FMath::Abs(Local.Y)<320)return 5;
        if(Local.X>0)return 0;
        return Distance<850?3:-1;
    }
    if(!bImportedAttackCacheReady)return -1;
    // Nearest anatomical zone wins: rear foot3 is ahead of the old X=-80
    // proxy cutoff, and neither front paw may threaten the opposite leg.
    const float Rear=FMath::Min(FVector::Dist2D(Point,GetLegLocation(2)),FVector::Dist2D(Point,GetLegLocation(3)));
    const float Front=FMath::Min(FVector::Dist2D(Point,GetLegLocation(0)),FVector::Dist2D(Point,GetLegLocation(1)));
    auto Reach=[&](EVeyrDragonMove Attack,int32 Leg=0){return CachedWarningContains(ImportedMoveClip(Attack,Leg,TEXT("Active")),Point);};
    if(Rear<Front&&(Reach(EVeyrDragonMove::BackStomp,2)||Reach(EVeyrDragonMove::BackStomp,3)))return 3;
    if(Reach(EVeyrDragonMove::ClawSwipe,0)||Reach(EVeyrDragonMove::ClawSwipe,1))return 2;
    if(Reach(EVeyrDragonMove::Bite))return 5;
    if(Reach(EVeyrDragonMove::TailSmack))return 4;
    if(Reach(EVeyrDragonMove::BackStomp,2)||Reach(EVeyrDragonMove::BackStomp,3))return 3;
    if(Reach(EVeyrDragonMove::Fire))return 0;
    return Distance>1750?1:-1;
}

bool AVeyrDragon::ImportedContactHitsKnight(const TArray<FVeyrDragonContact>& Contacts) const
{
    if(!IsValid(Target))return false;
    const UCapsuleComponent* Capsule=Target->GetCapsuleComponent();
    const float R=Capsule->GetScaledCapsuleRadius(),Half=Capsule->GetScaledCapsuleHalfHeight();
    const FVector Center=Capsule->GetComponentLocation(),Up=Capsule->GetUpVector();
    const FVector A=Center-Up*(Half-R),B=Center+Up*(Half-R);
    for(const auto& C:Contacts)
    {
        FVector P,Q;FMath::SegmentDistToSegmentSafe(A,B,C.Start,C.End,P,Q);
        if(FVector::DistSquared(P,Q)<=FMath::Square(C.Radius+R))return true;
    }
    return false;
}

bool AVeyrDragon::FlameHitsKnight(const FVeyrDragonFlameBeam& Beam) const
{
    if(!Beam.bDamaging||!IsValid(Target))return false;
    const UCapsuleComponent* Capsule=Target->GetCapsuleComponent();
    const float R=Capsule->GetScaledCapsuleRadius(),Half=Capsule->GetScaledCapsuleHalfHeight();
    const FVector A=Capsule->GetComponentLocation()-Capsule->GetUpVector()*(Half-R);
    const FVector B=Capsule->GetComponentLocation()+Capsule->GetUpVector()*(Half-R);
    const double K=FMath::Tan(FMath::DegreesToRadians(Beam.HalfAngleDegrees));
    // Rotational symmetry reduces point-to-finite-solid-cone distance to the
    // axial/radial triangle. Minimize this convex distance along capsule spine.
    auto Distance=[&](double T)
    {
        const FVector P=FMath::Lerp(A,B,T)-Beam.Origin;const double X=FVector::DotProduct(P,Beam.Direction);
        const double Y=(P-Beam.Direction*X).Size(),L=Beam.Length;
        if(X>=0&&X<=L&&Y<=X*K)return 0.;
        auto Segment=[&](double X0,double Y0,double X1,double Y1)
        {
            const double Dx=X1-X0,Dy=Y1-Y0;
            const double U=FMath::Clamp(((X-X0)*Dx+(Y-Y0)*Dy)/(Dx*Dx+Dy*Dy),0.,1.);
            return FMath::Square(X-X0-U*Dx)+FMath::Square(Y-Y0-U*Dy);
        };
        return FMath::Min(Segment(0,0,L,L*K),Segment(L,0,L,L*K));
    };
    double Lo=0,Hi=1;
    for(int32 I=0;I<32;++I)
    {const double T1=Lo+(Hi-Lo)/3,T2=Hi-(Hi-Lo)/3;if(Distance(T1)<Distance(T2))Hi=T2;else Lo=T1;}
    const double D=FMath::Min(Distance((Lo+Hi)*.5),FMath::Min(Distance(0),Distance(1)));
    return D<=R*R;
}


void AVeyrDragon::ResetCameraOcclusionMaterials()
{
    bCameraOcclusionReady=false;bCameraOcclusionEnabled=false;
    for(int32 Slot=0;Slot<CameraOcclusionMaterials.Num();++Slot)
        if(UMaterialInstanceDynamic* Material=CameraOcclusionMaterials[Slot])
        {
            Material->SetScalarParameterValue(TEXT("VeyrOcclusionEnabled"),0.f);
            // Remove only our own overrides. A later definition must resolve
            // its own mesh material, not inherit an old actor-owned MID.
            if(ImportedPresentation&&ImportedPresentation->GetMaterial(Slot)==Material)
                ImportedPresentation->SetMaterial(Slot,nullptr);
        }
    CameraOcclusionMaterials.Reset();
    CameraOcclusionDiagnostic=TEXT("Camera occlusion material parameters are not bound");
}

bool AVeyrDragon::InitializeCameraOcclusionMaterials()
{
    bCameraOcclusionReady=false;bCameraOcclusionEnabled=false;
    if(!bUsingCustomuseVisual||!ImportedPresentation||ImportedPresentation->GetNumMaterials()<1)
    {CameraOcclusionDiagnostic=TEXT("Imported mesh has no camera-occlusion material slots");return false;}
    TArray<UMaterialInterface*> Parents;
    // Validate every slot before assigning any MID. An opaque or partial
    // shader must not be reported as a functioning visibility tunnel.
    for(int32 Slot=0;Slot<ImportedPresentation->GetNumMaterials();++Slot)
    {
        UMaterialInterface* Parent=ImportedPresentation->GetMaterial(Slot);
        FString Missing;
        if(!Parent)Missing=TEXT("material");
        else if(Parent->GetBlendMode()!=BLEND_Masked)Missing=TEXT("masked surface shader");
        else
        {
            for(const TCHAR* Name:{TEXT("VeyrOcclusionRadius"),TEXT("VeyrProtectedHeadRadius"),TEXT("VeyrOcclusionEnabled")})
            {float Value=0;if(!Parent->GetScalarParameterValue(FHashedMaterialParameterInfo(Name),Value)){Missing=Name;break;}}
            if(Missing.IsEmpty())
                for(const TCHAR* Name:{TEXT("VeyrCameraStart"),TEXT("VeyrPlayerFocus"),TEXT("VeyrProtectedHead")})
                {FLinearColor Value;if(!Parent->GetVectorParameterValue(FHashedMaterialParameterInfo(Name),Value)){Missing=Name;break;}}
        }
        if(!Missing.IsEmpty())
        {
            CameraOcclusionDiagnostic=FString::Printf(TEXT("Camera occlusion unavailable: slot %d missing %s; camera fade disabled"),Slot,*Missing);
            UE_LOG(LogTemp,Warning,TEXT("VEYR_CAMERA_OCCLUSION_UNAVAILABLE %s"),*CameraOcclusionDiagnostic);return false;
        }
        Parents.Add(Parent);
    }
    for(UMaterialInterface* Parent:Parents)
    {
        UMaterialInstanceDynamic* Material=UMaterialInstanceDynamic::Create(Parent,this);
        if(!Material)
        {ResetCameraOcclusionMaterials();CameraOcclusionDiagnostic=TEXT("Camera occlusion transient MID creation failed");return false;}
        Material->SetFlags(RF_Transient);
        Material->SetScalarParameterValue(TEXT("VeyrOcclusionEnabled"),0.f);
        Material->SetScalarParameterValue(TEXT("VeyrOcclusionRadius"),100.f);
        Material->SetScalarParameterValue(TEXT("VeyrProtectedHeadRadius"),180.f);
        CameraOcclusionMaterials.Add(Material);
    }
    for(int32 Slot=0;Slot<CameraOcclusionMaterials.Num();++Slot)
        ImportedPresentation->SetMaterial(Slot,CameraOcclusionMaterials[Slot]);
    bCameraOcclusionReady=true;
    CameraOcclusionDiagnostic=TEXT("All camera-occlusion parameters bound; disabled until a valid view update; rendered verification pending");
    return true;
}

bool AVeyrDragon::SetViewOcclusion(const FVector& CameraWorld,const FVector& FocusWorld,bool bEnabled)
{
    auto Disable=[&]()
    {
        for(UMaterialInstanceDynamic* Material:CameraOcclusionMaterials)
            if(Material)Material->SetScalarParameterValue(TEXT("VeyrOcclusionEnabled"),0.f);
        bCameraOcclusionEnabled=false;
    };
    if(!bCameraOcclusionReady||!ImportedPresentation){Disable();return false;}
    if(ImportedPresentation->GetNumMaterials()!=CameraOcclusionMaterials.Num())
    {
        Disable();bCameraOcclusionReady=false;
        CameraOcclusionDiagnostic=TEXT("Camera occlusion disabled: material slot count changed after binding");return false;
    }
    for(int32 Slot=0;Slot<CameraOcclusionMaterials.Num();++Slot)
        if(!CameraOcclusionMaterials[Slot]||ImportedPresentation->GetMaterial(Slot)!=CameraOcclusionMaterials[Slot])
        {
            Disable();bCameraOcclusionReady=false;
            CameraOcclusionDiagnostic=TEXT("Camera occlusion disabled: material slot changed after binding");return false;
        }
    const FVector HeadWorld=GetHeadLocation();
    if(CameraWorld.ContainsNaN()||FocusWorld.ContainsNaN()||HeadWorld.ContainsNaN()||
       !FMath::IsFinite(CameraOcclusionRadius)||!FMath::IsFinite(CameraProtectedHeadRadius)||
       !bUsingCustomuseVisual||!bImportedTargetsValid)
    {
        Disable();CameraOcclusionDiagnostic=TEXT("Camera occlusion disabled: invalid view, radius or evaluated head pose");return false;
    }
    const bool Enable=bEnabled&&FVector::DistSquared(CameraWorld,FocusWorld)>1.f;
    const FLinearColor Camera(CameraWorld.X,CameraWorld.Y,CameraWorld.Z,0.f);
    const FLinearColor Focus(FocusWorld.X,FocusWorld.Y,FocusWorld.Z,0.f);
    const FLinearColor Head(HeadWorld.X,HeadWorld.Y,HeadWorld.Z,0.f);
    for(UMaterialInstanceDynamic* Material:CameraOcclusionMaterials)
    {
        Material->SetVectorParameterValue(TEXT("VeyrCameraStart"),Camera);
        Material->SetVectorParameterValue(TEXT("VeyrPlayerFocus"),Focus);
        Material->SetVectorParameterValue(TEXT("VeyrProtectedHead"),Head);
        Material->SetScalarParameterValue(TEXT("VeyrOcclusionRadius"),FMath::Max(1.f,CameraOcclusionRadius));
        Material->SetScalarParameterValue(TEXT("VeyrProtectedHeadRadius"),FMath::Max(0.f,CameraProtectedHeadRadius));
        Material->SetScalarParameterValue(TEXT("VeyrOcclusionEnabled"),Enable?1.f:0.f);
    }
    bCameraOcclusionEnabled=Enable;
    CameraOcclusionDiagnostic=Enable?TEXT("View parameters applied to transient MIDs; native rendered acceptance pending"):
        TEXT("Camera occlusion disabled; transient MIDs remain bound");
    return true;
}
