#include "VeyrDragon.h"
#include "VeyrKnight.h"
#include "VeyrVisualDefinition.h"
#include "Animation/AnimSequence.h"
#include "VeyrSkeletalPresentation.h"
#include "Components/SceneComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "Components/TextRenderComponent.h"
#include "Engine/StaticMesh.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Materials/MaterialInterface.h"
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
    WarningLines->ClearInstances(); DangerLines->ClearInstances(); VisualAccumulator=.04f;
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
            if(StateElapsed>=StateDuration)EnterState(EVeyrDragonState::Active,ActiveDuration);
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
}

FVeyrDragonFootprint AVeyrDragon::GetWarningFootprint() const
{
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

bool AVeyrDragon::IsPointInsideWarning(const FVector& Point) const {return ContainsPoint(GetWarningFootprint(),Point);}
bool AVeyrDragon::IsPointInsideActiveDanger(const FVector& Point) const {return ContainsPoint(GetActiveFootprint(),Point);}

void AVeyrDragon::TryDamageTarget()
{
    if(bContactConsumed||!IsValid(Target)||Target->IsDead()||IsDead())return;
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
    if(IsDead()||bEncounterStopped||IsAirborne()||AcceptedSwings.Contains(SwingId)||Ground(Forward).IsNearlyZero())return;
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
    if(IsDead()||bEncounterStopped||IsAirborne()||AcceptedSwings.Contains(SwingId))return false;
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
FVector AVeyrDragon::GetHeadLocation() const {return bImportedTargetsValid?ImportedHeadWorld:GetActorTransform().TransformPosition(HeadLocal);}
FVector AVeyrDragon::GetLegLocation(int32 Index) const {const int32 I=FMath::Clamp(Index,0,3);return bImportedTargetsValid?ImportedFeetWorld[I]:GetActorTransform().TransformPosition(LegLocal[I]);}
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

void AVeyrDragon::DrawFootprint(UInstancedStaticMeshComponent* Lines,const FVeyrDragonFootprint& F,bool bBright)
{
    if(F.Shape==EVeyrDangerShape::None)return;
    const float Width=bBright?22.f:13.f;
    if(F.Shape==EVeyrDangerShape::Capsule)
    {
        const FVector D=Ground(F.End-F.Origin).GetSafeNormal();const FVector Side=FVector::CrossProduct(FVector::UpVector,D)*F.OuterRadius;
        AddGroundLine(Lines,F.Origin+Side,F.End+Side,Width);AddGroundLine(Lines,F.Origin-Side,F.End-Side,Width);
        return;
    }
    const float Half=F.Shape==EVeyrDangerShape::Circle?180.f:F.HalfAngleDegrees;
    const int32 Segments=FMath::Max(12,FMath::CeilToInt(Half*2/6));
    for(int32 I=0;I<Segments;++I)
    {
        const FVector A=F.Forward.RotateAngleAxis(FMath::Lerp(-Half,Half,I/static_cast<float>(Segments)),FVector::UpVector);
        const FVector B=F.Forward.RotateAngleAxis(FMath::Lerp(-Half,Half,(I+1.f)/Segments),FVector::UpVector);
        AddGroundLine(Lines,F.Origin+A*F.OuterRadius,F.Origin+B*F.OuterRadius,Width);
        if(F.InnerRadius>0)AddGroundLine(Lines,F.Origin+A*F.InnerRadius,F.Origin+B*F.InnerRadius,Width);
        if(bBright&&I%2==0)AddGroundLine(Lines,F.Origin+A*F.InnerRadius,F.Origin+A*F.OuterRadius,Width*.65f);
    }
    if(Half<179)
        for(int32 Side=-1;Side<=1;Side+=2)
        {
            const FVector Ray=F.Forward.RotateAngleAxis(Half*Side,FVector::UpVector);
            AddGroundLine(Lines,F.Origin+Ray*F.InnerRadius,F.Origin+Ray*F.OuterRadius,Width);
        }
}

void AVeyrDragon::UpdateTelegraphs()
{
    WarningLines->ClearInstances(); DangerLines->ClearInstances();
    DrawFootprint(WarningLines,GetWarningFootprint(),false);DrawFootprint(DangerLines,GetActiveFootprint(),true);
}

FVector AVeyrDragon::ClampArena(const FVector& V,float Radius)
{
    FVector P=Ground(V);
    if(P.SizeSquared()>Radius*Radius)P=P.GetSafeNormal()*Radius;
    return P;
}


bool AVeyrDragon::ApplyCustomuseVisual(UVeyrVisualDefinition* Definition)
{
    if(!Definition||!ImportedPresentation||!ImportedPresentation->SetVisualDefinition(Definition,false))return false;
    // A valid measured head and four feet are mandatory before hiding proxies.
    FTransform TargetPose;
    for(FName Name:{FName(TEXT("head")),FName(TEXT("leg0")),FName(TEXT("leg1")),FName(TEXT("leg2")),FName(TEXT("leg3"))})
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
    TemporaryLabel->SetText(FText::FromString(TEXT("CUSTOMUSE DRAGON — MOTION INTEGRATION PREVIEW")));
    UpdateImportedPresentation();
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
        case EVeyrDragonState::Dead:Name=TEXT("Death");break;
        default:
        {
            static const TCHAR* Moves[]={TEXT("Fire"),TEXT("Flight"),TEXT("Claw"),TEXT("Stomp"),TEXT("Tail"),TEXT("Bite")};
            Name=Moves[static_cast<int32>(Move)];
            if(Move==EVeyrDragonMove::BackStomp)Name+=FString::FromInt(StompLeg);
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
            bImportedTransitionReady=ImportedPresentation->BeginTransition();
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
    bImportedTargetsValid=true;
}
