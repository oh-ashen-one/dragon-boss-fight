#include "VeyrDragon.h"
#include "VeyrKnight.h"
#include "VeyrArena.h"
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
#include "GameFramework/CharacterMovementComponent.h"
#include "Engine/World.h"

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

    /** Exact distance from a limb's capsule axis to one triangle of the blade's
     * swept quadrilateral. Includes interior crossings and degenerate sweeps. */
    float SegmentTriangleDistance(const FVector& Start,const FVector& End,
        const FVector& A,const FVector& B,const FVector& C)
    {
        float Distance=TNumericLimits<float>::Max();
        auto Edge=[&](const FVector& P,const FVector& Q)
        {
            FVector OnLimb,OnEdge;
            FMath::SegmentDistToSegmentSafe(Start,End,P,Q,OnLimb,OnEdge);
            Distance=FMath::Min(Distance,static_cast<float>(FVector::Dist(OnLimb,OnEdge)));
        };
        Edge(A,B);Edge(B,C);Edge(C,A);
        if(FVector::CrossProduct(B-A,C-A).SizeSquared()>1.e-4f)
        {
            FVector Intersection,Normal;
            if(FMath::SegmentTriangleIntersection(Start,End,A,B,C,Intersection,Normal))return 0.f;
            Distance=FMath::Min(Distance,static_cast<float>(FVector::Dist(Start,FMath::ClosestPointOnTriangleToPoint(Start,A,B,C))));
            Distance=FMath::Min(Distance,static_cast<float>(FVector::Dist(End,FMath::ClosestPointOnTriangleToPoint(End,A,B,C))));
        }
        return Distance;
    }
}

AVeyrDragon::AVeyrDragon()
{
    PrimaryActorTick.bCanEverTick=true;
    SceneRoot=CreateDefaultSubobject<USceneComponent>(TEXT("DragonRulesRoot")); SetRootComponent(SceneRoot);
    static const TCHAR* SolidNames[]={TEXT("Torso"),TEXT("Chest"),TEXT("NeckBase"),TEXT("Neck"),TEXT("Head"),
        TEXT("FrontLeftShin"),TEXT("FrontRightShin"),TEXT("HindLeftCalf"),TEXT("HindLeftShin"),
        TEXT("HindRightCalf"),TEXT("HindRightShin"),TEXT("FrontLeftFoot"),TEXT("FrontRightFoot"),
        TEXT("HindLeftFoot"),TEXT("HindRightFoot"),TEXT("TailBase"),TEXT("TailMiddle"),TEXT("TailEnd"),TEXT("TailTip")};
    for(const TCHAR* Name:SolidNames)
    {
        UCapsuleComponent* Part=CreateDefaultSubobject<UCapsuleComponent>(*FString::Printf(TEXT("VeyrSolid_%s"),Name));
        Part->SetupAttachment(SceneRoot);Part->SetAbsolute(true,true,true);
        Part->SetCollisionEnabled(ECollisionEnabled::NoCollision);
        Part->SetCollisionObjectType(ECC_WorldDynamic);
        Part->SetCollisionResponseToAllChannels(ECR_Ignore);Part->SetCollisionResponseToChannel(ECC_Pawn,ECR_Block);
        Part->SetGenerateOverlapEvents(false);Part->SetCanEverAffectNavigation(false);
        Part->CanCharacterStepUpOn=ECB_No;Part->SetHiddenInGame(true);Part->SetVisibility(false);
        SolidBodyCapsules.Add(Part);
    }
    ImportedPresentation=CreateDefaultSubobject<UVeyrSkeletalPresentation>(TEXT("CustomuseDragonPresentation"));
    ImportedPresentation->ConfigureRenderPolicy(false,true);
    ImportedPresentation->SetupAttachment(SceneRoot);
    ImportedPresentation->LightingChannels.bChannel1=true;ImportedPresentation->LightingChannels.bChannel2=true;
    ImportedPresentation->SetVisibility(false);
    AttackPoseProbe=CreateDefaultSubobject<UVeyrSkeletalPresentation>(TEXT("HiddenAttackEnvelopeProbe"));
    AttackPoseProbe->ConfigureRenderPolicy(true,false);
    AttackPoseProbe->SetupAttachment(SceneRoot);
    AttackPoseProbe->SetVisibility(false);AttackPoseProbe->SetHiddenInGame(true);
    AttackPoseProbe->SetCastShadow(false);AttackPoseProbe->SetRenderInMainPass(false);
    static ConstructorHelpers::FObjectFinderOptional<UVeyrVisualDefinition> ImportedDefinition(TEXT("/Game/Characters/Customuse/RuntimePolish/DA_Dragon.DA_Dragon"));
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
    // Data windows (moves.json attack parts). Damage mirrors the hard-coded moves:
    // bite 34, claw 29, tail 30; wings are broad plates, so they hit lighter.
    AttackPartDamage={{TEXT("jaw"),34.f},{TEXT("paw_fl"),29.f},{TEXT("paw_fr"),29.f},{TEXT("paw_hl"),32.f},
        {TEXT("paw_hr"),32.f},{TEXT("tail"),30.f},{TEXT("wing_l"),20.f},{TEXT("wing_r"),20.f}};
    AttackPartCapsule={{TEXT("jaw"),TEXT("head")},{TEXT("paw_fl"),TEXT("leg_fl")},{TEXT("paw_fr"),TEXT("leg_fr")},
        {TEXT("paw_hl"),TEXT("leg_hl")},{TEXT("paw_hr"),TEXT("leg_hr")},{TEXT("tail"),TEXT("tail")},
        {TEXT("wing_l"),TEXT("wing_l")},{TEXT("wing_r"),TEXT("wing_r")}};
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
    WarningArena=Cast<AVeyrArena>(UGameplayStatics::GetActorOfClass(this,AVeyrArena::StaticClass()));
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
    LoadMoveDataFromDisk();
    // CDO construction may precede the owned MCP import; resolve the new asset
    // again at BeginPlay even if an older definition was supplied previously.
    if(UVeyrVisualDefinition* Polish=LoadObject<UVeyrVisualDefinition>(nullptr,
        TEXT("/Game/Characters/Customuse/RuntimePolish/DA_Dragon.DA_Dragon"),nullptr,LOAD_Quiet|LOAD_NoWarn))
    {VisualDefinition=Polish;bUsingPolishDefinition=true;}
    else
    {
        bUsingPolishDefinition=false;
        UE_LOG(LogTemp,Error,TEXT("VEYR_DRAGON_POLISH_DEFINITION_MISSING final polish validation must fail"));
        if(!VisualDefinition)VisualDefinition=LoadObject<UVeyrVisualDefinition>(nullptr,
            TEXT("/Game/Characters/Customuse/RuntimeApproved/DA_Dragon.DA_Dragon"),nullptr,LOAD_Quiet|LOAD_NoWarn);
    }
    if(!VisualDefinition)
    {
        VisualDefinition=LoadObject<UVeyrVisualDefinition>(nullptr,
            TEXT("/Game/Characters/Customuse/Runtime/DA_Dragon.DA_Dragon"),nullptr,LOAD_Quiet|LOAD_NoWarn);
        UE_LOG(LogTemp,Warning,TEXT("VEYR_DRAGON_APPROVED_DEFINITION_MISSING using legacy Runtime definition"));
    }
    if(VisualDefinition)ApplyCustomuseVisual(VisualDefinition);
    if(bMoveDataLoaded&&!bHurtPartsReady)UE_LOG(LogVeyrMoveData,Display,TEXT("VEYR_MOVEDATA_READY windows=%d hurt_capsules=0 (%s)"),MoveData.CountAttacks(),*MoveDataDiagnostic);
    LogMoveDataDumpIfRequested();
}

void AVeyrDragon::Tick(float DeltaSeconds)
{
    Super::Tick(DeltaSeconds);
    if(DeltaSeconds<=0)return;
    if(!IsValid(Target))Target=Cast<AVeyrKnight>(UGameplayStatics::GetPlayerCharacter(this,0));
    // A freshly opened window cannot attack a player who has not clicked to
    // begin. Once engaged, releasing the mouse does not pause the encounter.
    if(IsValid(Target)&&!Target->HasEnteredEncounter())
    {
        // Combat waits for deliberate input; the creature still breathes and
        // shifts its weight while the player studies the opening view.
        Clock+=DeltaSeconds;
        UpdateGaze(DeltaSeconds);
        UpdateTemporaryPresentation(DeltaSeconds);UpdateImportedPresentation();
        UpdateHurtParts();
        UpdateSolidBody();
        DrawMoveDataDebug();
        return;
    }
    Clock+=DeltaSeconds; EncounterClock+=DeltaSeconds; StateElapsed+=DeltaSeconds;
    StaggerProtection=FMath::Max(0.f,StaggerProtection-DeltaSeconds);
    for(float& Flash:LegFlash)Flash=FMath::Max(0.f,Flash-DeltaSeconds*4.f);
    if(!IsDead()&&IsValid(Target)&&Target->IsDead()&&!bEncounterStopped)
    {
        const bool FinishLanding=HasAuthoredFlight()&&IsAirborne();
        bEncounterStopped=true;
        if(FinishLanding)
        {
            // Combat stops immediately, but a flying creature settles through
            // its landing action instead of snapping to a grounded idle.
            MoveEnd=Ground(GetActorLocation());
            TerminalDescentStart=GetActorLocation();bTerminalDescent=true;TerminalDescentElapsed=0.f;
            EnterState(EVeyrDragonState::Recovery,VisualClipDuration(TEXT("FlightRecovery"),1.5f));
        }
        else EnterState(EVeyrDragonState::Idle,TNumericLimits<float>::Max());
    }
    if(!bEncounterStopped||IsDead())AdvanceState(DeltaSeconds);
    else if(State==EVeyrDragonState::Recovery&&Move==EVeyrDragonMove::FlyAway&&StateElapsed>=StateDuration)
        EnterState(EVeyrDragonState::Idle,TNumericLimits<float>::Max());
    if(bTerminalDescent)
    {
        TerminalDescentElapsed+=DeltaSeconds;
        const float T=FMath::Clamp(TerminalDescentElapsed/1.3f,0.f,1.f);
        SetActorLocation(FMath::Lerp(TerminalDescentStart,Ground(TerminalDescentStart),Ease(T)));
        if(T>=1.f)bTerminalDescent=false;
    }
    UpdateGaze(DeltaSeconds);
    UpdateTemporaryPresentation(DeltaSeconds);
    UpdateImportedPresentation();
    UpdateHurtParts();
    // Data windows read the pose just evaluated (same clock as the hard-coded contact).
    UpdateDataMove(DeltaSeconds);
    // Kinematic anatomy can advance into a stationary player. Publish physical
    // blockers after attack contact, then resolve genuine penetration through
    // the native movement component instead of letting the next move tunnel.
    UpdateSolidBody();
    DrawMoveDataDebug();
    VisualAccumulator+=DeltaSeconds;
    // Active sweep geometry must use the same current clock as damaging contact.
    if(State==EVeyrDragonState::Active||IsLandingContactWindow()||VisualAccumulator>=.04f) { VisualAccumulator=0; UpdateTelegraphs(); }
}

void AVeyrDragon::EnterState(EVeyrDragonState Next,float Duration)
{
    if(Next==EVeyrDragonState::Dead)
    {
        if(GetActorLocation().Z>1.f){TerminalDescentStart=GetActorLocation();bTerminalDescent=true;TerminalDescentElapsed=0.f;}
        DeathStartDown=GetDownAmount();
        DeathStartBuckle=State==EVeyrDragonState::Buckle?Ease(StateElapsed/StateDuration):
            State==EVeyrDragonState::Collapse?1-Ease(StateElapsed/StateDuration):0.f;
    }
    State=Next; StateElapsed=0; StateDuration=Duration;
    bPreviousContactPoseValid=false;PreviousContacts.Reset();
    const bool Landing=Next==EVeyrDragonState::Recovery&&Move==EVeyrDragonMove::FlyAway&&HasAuthoredFlight();
    if(Next!=EVeyrDragonState::Windup&&Next!=EVeyrDragonState::Active&&!Landing)CommittedWarning.Reset();
    WarningLines->ClearInstances(); DangerLines->ClearInstances(); VisualAccumulator=.04f;bWarningDrawn=false;
}

void AVeyrDragon::AdvanceState(float DeltaSeconds)
{
    switch(State)
    {
        case EVeyrDragonState::Idle:
            if(StateElapsed>=StateDuration&&IsValid(Target)&&!Target->IsDead()&&!IsDataOnlyMovePlaying())ChooseAttack();
            break;
        case EVeyrDragonState::Reposition:
        {
            // Separate planted turning from translation. Both presentation
            // phases are measured from the resulting transform below.
            const float TurnT=RepositionTurnDuration>.001f?FMath::Clamp(StateElapsed/RepositionTurnDuration,0.f,1.f):1.f;
            if(bRepositionAuthoredTurn&&StateElapsed<RepositionTurnDuration)
                SetActorTransform(RepositionTurnTransform(TurnT));
            else SetActorRotation(FQuat::Slerp(TurnStart.Quaternion(),TurnEnd.Quaternion(),bRepositionAuthoredTurn?1.f:Ease(TurnT)));
            bRepositionWalking=StateElapsed>=RepositionTurnDuration&&RepositionTravelDuration>.001f;
            const float TravelT=bRepositionWalking?FMath::Clamp((StateElapsed-RepositionTurnDuration)/RepositionTravelDuration,0.f,1.f):0.f;
            if(!bRepositionAuthoredTurn||StateElapsed>=RepositionTurnDuration)
                SetActorLocation(FMath::Lerp(MoveStart,MoveEnd,TravelT));
            if(StateElapsed>=StateDuration){bJustRepositioned=true;EnterState(EVeyrDragonState::Idle,.35f);}
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
                const float T=FMath::Clamp(StateElapsed/(HasAuthoredFlight()?ActiveDuration:FlightSeconds),0.f,1.f);
                const float Travel=T<.35f?.35f*Ease(T/.35f):T<.75f?.35f:.35f+.65f*Ease((T-.75f)/.25f);
                FVector Position=FMath::Lerp(MoveStart,MoveEnd,Travel);
                // New takeoff/hover/landing already contain the approved root
                // altitude. Actor travel supplies only the horizontal route.
                Position.Z+=FMath::Square(FMath::Sin(T*PI))*(HasAuthoredFlight()?850.f:1400.f);
                Position+=AttackForward.RotateAngleAxis(90.f,FVector::UpVector)*FMath::Sin(T*PI)*280.f;
                const FVector Facing=(T>.30f&&T<.75f?AerialFireTarget:MoveEnd)-Position;
                if(Facing.SizeSquared2D()>FMath::Square(250.f))
                    SetActorRotation(FMath::RInterpTo(GetActorRotation(),FRotator(0,Facing.Rotation().Yaw,0),DeltaSeconds,1.8f));
                // Analytic arc returns to the authored endpoints with zero vertical velocity.
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
            if(IsLandingContactWindow()){UpdateImportedPresentation();TryDamageTarget();}
            if(StateElapsed>=StateDuration){++CompletedAttacks[MoveIndex(Move)];EnterState(EVeyrDragonState::Idle,.40f);}
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
        if(EncounterClock>=NextFlightAt){BeginAttack(EVeyrDragonMove::FlyAway);return;}
        if(Positional<0){BeginReposition();return;}
        EVeyrDragonMove Next=static_cast<EVeyrDragonMove>(Positional);
        if(TotalAttacks%4==3&&EncounterClock+6.f>=NextFlightAt)Next=EVeyrDragonMove::FlyAway;
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

float AVeyrDragon::VisualClipDuration(FName ClipName,float Fallback) const
{
    const FVeyrVisualClip* Clip=VisualDefinition?VisualDefinition->Clips.Find(ClipName):nullptr;
    if(!Clip||!Clip->Sequence)return Fallback;
    const float End=Clip->EndSeconds<0.f?Clip->Sequence->GetPlayLength():Clip->EndSeconds;
    return End>Clip->StartSeconds?End-Clip->StartSeconds:Fallback;
}

bool AVeyrDragon::HasAuthoredFlight() const
{
    const FVeyrVisualClip* Clip=VisualDefinition?VisualDefinition->Clips.Find(TEXT("FlightWindup")):nullptr;
    return Clip&&Clip->Sequence&&Clip->ApprovedSourceFile.StartsWith(TEXT("Dragon_Takeoff_"));
}

bool AVeyrDragon::IsLandingContactWindow() const
{
    if(!HasAuthoredFlight()||Move!=EVeyrDragonMove::FlyAway||State!=EVeyrDragonState::Recovery)return false;
    const FVeyrVisualClip* Land=VisualDefinition->Clips.Find(TEXT("FlightRecovery"));
    const float Impact=Land&&Land->ImpactSeconds>=0.f?Land->ImpactSeconds:25.f/30.f;
    return StateElapsed>=Impact&&StateElapsed<Impact+.20f;
}

float AVeyrDragon::WalkCycleDistance() const
{
    const FVeyrVisualClip* Clip=VisualDefinition?VisualDefinition->Clips.Find(TEXT("Walk")):nullptr;
    if(Clip&&Clip->NominalSpeedCmPerSecond>0.f)
        return Clip->NominalSpeedCmPerSecond*VisualClipDuration(TEXT("Walk"),3.2f);
    return 134.f;
}

bool AVeyrDragon::HasGroundTargetBite() const
{
    const FVeyrVisualClip* Clip=VisualDefinition?VisualDefinition->Clips.Find(TEXT("BiteActive")):nullptr;
    return Clip&&Clip->Sequence&&Clip->ApprovedSourceFile.Contains(TEXT("Dragon_Bite_Blender_v2"));
}

TMap<FName,FRotator> AVeyrDragon::BiteGroundRotations(float SourceSeconds,float PitchDegrees) const
{
    TMap<FName,FRotator> Result;
    if(!HasGroundTargetBite()||BiteNeckBase.IsNone()||BiteNeckMiddle.IsNone()||BiteHead.IsNone())return Result;
    const FVeyrVisualClip& Windup=VisualDefinition->Clips.FindChecked(TEXT("BiteWindup"));
    const FVeyrVisualClip& Active=VisualDefinition->Clips.FindChecked(TEXT("BiteActive"));
    const FVeyrVisualClip& Recovery=VisualDefinition->Clips.FindChecked(TEXT("BiteRecovery"));
    const float Finish=Recovery.EndSeconds<0.f?Recovery.Sequence->GetPlayLength():Recovery.EndSeconds;
    const float WindupWeight=Ease((SourceSeconds-Windup.StartSeconds)/FMath::Max(.001f,Active.StartSeconds-Windup.StartSeconds));
    const float RecoveryWeight=1.f-Ease((SourceSeconds-Active.EndSeconds)/FMath::Max(.001f,Finish-Active.EndSeconds));
    const float Pitch=-FMath::Clamp(PitchDegrees,0.f,50.f)*FMath::Min(WindupWeight,RecoveryWeight);
    // Distributed curvature, never a translated/stretched neck or an enlarged
    // invisible hit volume. Each joint stays within the native modifier limits.
    Result.Add(BiteNeckBase,FRotator(Pitch*.4f,0,0));
    Result.Add(BiteNeckMiddle,FRotator(Pitch*.4f,0,0));
    Result.Add(BiteHead,FRotator(Pitch*.2f,0,0));
    return Result;
}

bool AVeyrDragon::CalibrateBiteGroundAim()
{
    bBiteGroundAimReady=false;BiteGroundPitchDegrees=0.f;BiteGroundStrikeMuzzleHeightCm=0.f;
    BiteNeckBase=BiteNeckMiddle=BiteHead=NAME_None;BiteGroundAimDiagnostic.Reset();
    if(!HasGroundTargetBite())return true;
    const FVeyrVisualBoneTarget* Neck=VisualDefinition->BoneTargets.Find(TEXT("gaze_neck"));
    const FVeyrVisualBoneTarget* Head=VisualDefinition->BoneTargets.Find(TEXT("head"));
    if(!Neck||!Head)return false;
    BiteNeckMiddle=Neck->BoneName;BiteHead=Head->BoneName;
    BiteNeckBase=AttackPoseProbe->GetParentBone(BiteNeckMiddle);
    if(BiteNeckBase.IsNone()||BiteNeckBase==BiteNeckMiddle||BiteNeckMiddle==BiteHead)
    {BiteGroundAimDiagnostic=TEXT("Ground bite requires the measured three-joint neck chain");return false;}
    const FVeyrVisualClip& Active=VisualDefinition->Clips.FindChecked(TEXT("BiteActive"));
    const float StrikeSource=Active.ImpactSeconds>=0.f?Active.ImpactSeconds:18.f/30.f;
    const float StrikeTrimmed=FMath::Clamp(StrikeSource-Active.StartSeconds,0.f,VisualClipDuration(TEXT("BiteActive"),.633333f));
    const float HalfHeight=IsValid(Target)?Target->GetCapsuleComponent()->GetScaledCapsuleHalfHeight():122.f;
    const float TorsoHeight=HalfHeight*1.3f;
    auto SampleHeight=[&](float Degrees,float& Height)
    {
        if(!AttackPoseProbe->SetComponentSpaceBoneRotations(BiteGroundRotations(StrikeSource,Degrees))||
           !AttackPoseProbe->SampleClipTime(TEXT("BiteActive"),StrikeTrimmed))return false;
        FTransform Mouth;
        if(!AttackPoseProbe->GetBoneTargetWorldTransform(TEXT("mouth"),Mouth))return false;
        Height=Mouth.GetLocation().Z-GetActorLocation().Z;return FMath::IsFinite(Height);
    };
    float HighHeight=0.f,LowHeight=0.f;
    if(!SampleHeight(0.f,LowHeight)||!SampleHeight(50.f,HighHeight))
    {BiteGroundAimDiagnostic=TEXT("Ground bite native pose calibration failed");return false;}
    if(LowHeight>TorsoHeight)
    {
        float Low=0.f,High=50.f;
        // If the anatomical bound cannot reach torso centre, use its nearest
        // pose only when the unchanged physical jaw capsule reaches the body.
        if(HighHeight<=TorsoHeight)
            for(int32 I=0;I<10;++I)
            {
                const float Mid=(Low+High)*.5f;float Height=0.f;
                if(!SampleHeight(Mid,Height))return false;
                if(Height>TorsoHeight)Low=Mid;else High=Mid;
            }
        BiteGroundPitchDegrees=High;
    }
    if(!SampleHeight(BiteGroundPitchDegrees,BiteGroundStrikeMuzzleHeightCm))return false;
    // The existing bite capsule radius is 100 cm (ReadImportedContactPose).
    bBiteGroundAimReady=BiteGroundStrikeMuzzleHeightCm>=100.f&&
        BiteGroundStrikeMuzzleHeightCm-100.f<=2.f*HalfHeight;
    BiteGroundAimDiagnostic=FString::Printf(TEXT("Ground bite pitch %.2f degrees; strike muzzle %.2f cm; torso target %.2f cm; unchanged jaw radius 100 cm; %s"),
        BiteGroundPitchDegrees,BiteGroundStrikeMuzzleHeightCm,TorsoHeight,bBiteGroundAimReady?TEXT("reachable"):TEXT("outside anatomical reach"));
    AttackPoseProbe->SetComponentSpaceBoneRotations({});
    return bBiteGroundAimReady;
}

bool AVeyrDragon::ReadTurnTrajectory(float SourceSeconds,FVector& Translation,float& YawDegrees) const
{
    const FVeyrVisualClip* Clip=VisualDefinition?VisualDefinition->Clips.Find(RepositionTurnClip):nullptr;
    if(!Clip||!Clip->bRootMotionRemoved||Clip->RootTranslationSamplesCm.Num()<2||
       Clip->RootYawSamplesDegrees.Num()!=Clip->RootTranslationSamplesCm.Num()||Clip->RootSampleRate<=0.f)return false;
    const float Sample=FMath::Clamp((Clip->StartSeconds+SourceSeconds)*Clip->RootSampleRate,0.f,
        static_cast<float>(Clip->RootTranslationSamplesCm.Num()-1));
    const int32 I=FMath::FloorToInt(Sample),J=FMath::Min(I+1,Clip->RootTranslationSamplesCm.Num()-1);
    Translation=FMath::Lerp(Clip->RootTranslationSamplesCm[I],Clip->RootTranslationSamplesCm[J],Sample-I);
    YawDegrees=FMath::Lerp(Clip->RootYawSamplesDegrees[I],Clip->RootYawSamplesDegrees[J],Sample-I);
    return !Translation.ContainsNaN()&&FMath::IsFinite(YawDegrees);
}

FTransform AVeyrDragon::RepositionTurnTransform(float Phase) const
{
    FVector Delta,End;float Yaw=0.f,EndYaw=0.f;
    const float T=FMath::Clamp(Phase,0.f,1.f)*RepositionTurnSourceDuration;
    if(!ReadTurnTrajectory(bRepositionReverseTurn?RepositionTurnSourceDuration-T:T,Delta,Yaw))return RepositionStartTransform;
    FQuat RootRotation(FVector::UpVector,FMath::DegreesToRadians(Yaw));
    if(bRepositionReverseTurn)
    {
        if(!ReadTurnTrajectory(RepositionTurnSourceDuration,End,EndYaw))return RepositionStartTransform;
        const FQuat InverseEnd=FQuat(FVector::UpVector,FMath::DegreesToRadians(EndYaw)).Inverse();
        Delta=InverseEnd.RotateVector(Delta-End);RootRotation=InverseEnd*RootRotation;
    }
    const FTransform& Component=VisualDefinition->MeshRelativeTransform;
    const FQuat ActorDeltaRotation=Component.GetRotation()*RootRotation*Component.GetRotation().Inverse();
    // C*M*C^-1: scale/rotate the displacement and compensate the imported
    // mesh's offset pivot. Adding the offset directly would double translation.
    const FVector ActorDelta=Component.TransformVector(Delta)+Component.GetTranslation()-
        ActorDeltaRotation.RotateVector(Component.GetTranslation());
    FTransform Result=RepositionStartTransform;
    Result.SetLocation(RepositionStartTransform.TransformPosition(ActorDelta));
    Result.SetRotation((RepositionStartTransform.GetRotation()*ActorDeltaRotation).GetNormalized());
    return Result;
}

void AVeyrDragon::BeginReposition()
{
    MoveStart=Ground(GetActorLocation());
    const FVector Toward=Ground(Target->GetActorLocation()-MoveStart).GetSafeNormal();
    const float Distance=static_cast<float>(FVector::Dist2D(Target->GetActorLocation(),MoveStart));
    const float Travel=Distance<450?-350.f:Distance>1250?350.f:Distance>900?120.f:-120.f;
    TurnStart=GetActorRotation();
    const float DesiredYaw=Toward.Rotation().Yaw;
    RepositionYawDelta=FMath::Clamp(FMath::FindDeltaAngleDegrees(TurnStart.Yaw,DesiredYaw),-75.f,75.f);
    TurnEnd=FRotator(0,TurnStart.Yaw+RepositionYawDelta,0);
    bRepositionAuthoredTurn=false;bRepositionReverseTurn=false;RepositionTurnClip=TEXT("TurnLeft");
    RepositionStartTransform=GetActorTransform();RepositionTurnSourceDuration=VisualClipDuration(RepositionTurnClip,0.f);
    FVector RootEnd;float RootYaw=0.f;
    const bool HasRootTurn=ReadTurnTrajectory(RepositionTurnSourceDuration,RootEnd,RootYaw)&&FMath::Abs(RootYaw)>45.f;
    if(HasRootTurn)
    {
        // The approved turn is a complete planted 90-degree step, not a 20-degree
        // loop. Use retained small-turn gait for fine steering; larger errors take
        // one complete step so a partial source frame never leaves feet airborne.
        const float DesiredDelta=FMath::FindDeltaAngleDegrees(TurnStart.Yaw,DesiredYaw);
        if(FMath::Abs(DesiredDelta)>=45.f)
        {
            bRepositionAuthoredTurn=true;bRepositionReverseTurn=DesiredDelta*RootYaw<0.f;
            const FTransform Finish=RepositionTurnTransform(1.f);
            MoveStart=Ground(Finish.GetLocation());TurnEnd=Finish.Rotator();
            RepositionYawDelta=FMath::FindDeltaAngleDegrees(TurnStart.Yaw,TurnEnd.Yaw);
        }
        else
        {
            const FName Fine=DesiredDelta>=0.f?FName(TEXT("TurnRightFine")):FName(TEXT("TurnLeftFine"));
            const FVeyrVisualClip* FineClip=VisualDefinition->Clips.Find(Fine);
            if(FineClip&&FineClip->Sequence)RepositionTurnClip=Fine;
            else
            {
                // Do not silently run part of the 90-degree turn as a tiny loop.
                TurnEnd=TurnStart;RepositionYawDelta=0.f;
                LocomotionDiagnostic=TEXT("Retained fine-turn clip missing: ")+Fine.ToString();
            }
        }
    }
    // Travel along the final facing, including a reverse gait when yielding
    // space. Do not make a forward gait slide sideways toward a distant target.
    MoveEnd=MoveStart+TurnEnd.Vector()*Travel;
    if(MoveEnd.SizeSquared2D()>FMath::Square(2700.f))
    {
        // Shorten along the facing line; radial endpoint projection would
        // introduce a sideways component unsupported by the forward gait.
        float Lo=0.f,Hi=1.f;
        for(int32 I=0;I<16;++I)
        {
            const float Mid=(Lo+Hi)*.5f;
            if(FMath::Lerp(MoveStart,MoveEnd,Mid).SizeSquared2D()<=FMath::Square(2700.f))Lo=Mid;else Hi=Mid;
        }
        MoveEnd=FMath::Lerp(MoveStart,MoveEnd,Lo);
    }
    RepositionTurnDuration=bRepositionAuthoredTurn?RepositionTurnSourceDuration/1.22f:
        FMath::Abs(RepositionYawDelta)>.5f?FMath::Max(.3f,FMath::Abs(RepositionYawDelta)/40.f):0.f;
    const FVeyrVisualClip* Walk=VisualDefinition?VisualDefinition->Clips.Find(TEXT("Walk")):nullptr;
    const float WalkSpeed=Walk&&Walk->NominalSpeedCmPerSecond>0.f?Walk->NominalSpeedCmPerSecond:160.f;
    RepositionTravelDuration=FVector::Dist2D(MoveStart,MoveEnd)/(WalkSpeed*1.25f);
    bRepositionWalking=RepositionTurnDuration<=.001f;
    RepeatedMoveCount=0;
    EnterState(EVeyrDragonState::Reposition,FMath::Max(.35f,RepositionTurnDuration+RepositionTravelDuration));
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
            NextFlightAt=EncounterClock+20.f;bAerialFireConsumed=false;
            AerialFireTarget=Ground(Target->GetFootLocation());
            WindupDuration=1.6f; ActiveDuration=FlightSeconds+.35f; RecoveryDuration=2.3f; AttackDamage=38.f;
            const FVector Side=GetActorRightVector()*(TotalAttacks%2==0?1.f:-1.f);
            MoveEnd=ClampArena(Ground(Target->GetActorLocation())+Side*900.f,2500.f);
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
    if(bUsingCustomuseVisual&&VisualDefinition)
    {
        const FName Windup=ImportedMoveClip(Move,Move==EVeyrDragonMove::ClawSwipe?ClawLeg:StompLeg,TEXT("Windup"));
        const FVeyrVisualClip* Config=VisualDefinition->Clips.Find(Windup);
        if((Move==EVeyrDragonMove::Fire||Move==EVeyrDragonMove::Bite)&&Config&&
           Config->ApprovedSourceFile.StartsWith(TEXT("Dragon_")))
        {
            WindupDuration=VisualClipDuration(Windup,WindupDuration);
            ActiveDuration=VisualClipDuration(ImportedMoveClip(Move,0,TEXT("Active")),ActiveDuration);
            RecoveryDuration=VisualClipDuration(ImportedMoveClip(Move,0,TEXT("Recovery")),RecoveryDuration);
        }
        if(Move==EVeyrDragonMove::FlyAway&&HasAuthoredFlight())
        {
            WindupDuration=VisualClipDuration(TEXT("FlightWindup"),1.5f);
            // Two complete wingbeats return to the same frame-zero pose before
            // Land. A global Clock or partial hover would break that join.
            ActiveDuration=2.f*VisualClipDuration(TEXT("FlightActive"),2.f);
            RecoveryDuration=VisualClipDuration(TEXT("FlightRecovery"),1.5f);
            bHoverAlternateThisFlight=bPreferHoverAlternate||
                (bAlternateHoverVariants&&CompletedAttacks[MoveIndex(Move)]%2==1);
            const FVeyrVisualClip* Alternate=VisualDefinition->Clips.Find(TEXT("FlightHoverAlternate"));
            bHoverAlternateThisFlight&=Alternate&&Alternate->Sequence;
        }
    }
    EnterState(EVeyrDragonState::Windup,WindupDuration);
    if(bUsingCustomuseVisual)CommitImportedWarning();
    if(const FName* DataMove=DataMoveForEnum.Find(Move))BeginDataMove(*DataMove,true);
    else if(bDataMoveFollowsEnum)StopDataMove();
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
    if(!IsValid(Target)||Target->IsDead()||IsDead())return;
    if(Move==EVeyrDragonMove::FlyAway&&State==EVeyrDragonState::Active&&!bEncounterStopped&&!bAerialFireConsumed&&bImportedTargetsValid&&bImportedAttackCacheReady&&MissingVisualClip.IsNone())
    {
        const auto Beam=GetActiveFlameBeam();
        if(Beam.bDamaging&&FVector::Dist2D(Target->GetFootLocation(),AerialFireTarget)<=430.f&&FlameHitsKnight(Beam))
        {
            // Separate one-hit budget from the later landing; guard/dodge rules remain authoritative.
            const float Before=Target->Health;Target->ApplyBossDamage(26.f,Beam.Origin);bAerialFireConsumed=true;++DamageContactCount;
            if(FMath::IsNearlyEqual(Before,Target->Health))++AvoidedContactCount;
        }
    }
    if(bContactConsumed)return;
    if(DataWindowsReplaceContact())return;
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
            bHit=(HasAuthoredFlight()?IsLandingContactWindow():StateElapsed>=FlightSeconds)&&
                ContainsAny(GetActiveFootprints(),Target->GetFootLocation());
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

void AVeyrDragon::ReceiveSword(const FVector& Origin,const FVector& Forward,bool bHeavy,int32 SwingId,float DamageMultiplier)
{
    if(IsDead()||bEncounterStopped||IsAirborne()||AcceptedSwings.Contains(SwingId)||Ground(Forward).IsNearlyZero()||
       (bUsingCustomuseVisual&&!bImportedTargetsValid))return;
    int32 Region=-1; float Best=TNumericLimits<float>::Max();
    for(int32 I=0;I<4;++I)
    {
        float Score;
        if(SwordContact(Origin,Forward,GetLegLocation(I),75.f,Score)&&Score<Best){Best=Score;Region=I;}
        if(bUsingCustomuseVisual&&bAnatomicalLegContactsReady)
        {
            const FVector Knee=GetLegKneeLocation(I),Hock=GetLegHockLocation(I),Ankle=GetLegLocation(I);
            const float Radius=GetLegContactRadius(I);
            for(const FVector& Point:{FMath::ClosestPointOnSegment(Origin,Knee,Hock),FMath::ClosestPointOnSegment(Origin,Hock,Ankle)})
                if(SwordContact(Origin,Forward,Point,Radius,Score)&&Score<Best){Best=Score;Region=I;}
        }
    }
    float Score;
    if(SwordContact(Origin,Forward,GetHeadLocation(),100.f,Score)&&Score<Best){Best=Score;Region=4;}
    if(Region<0)return;
    ApplySwordRegion(Region,bHeavy,SwingId,DamageMultiplier);
}

bool AVeyrDragon::ReceiveSwordSweep(const FVector& PreviousBase,const FVector& PreviousTip,
                                  const FVector& CurrentBase,const FVector& CurrentTip,bool bHeavy,int32 SwingId,float DamageMultiplier,float BladeRadius)
{
    if(IsDead()||bEncounterStopped||AcceptedSwings.Contains(SwingId)||
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
    int32 Region=-1;float Best=TNumericLimits<float>::Max();FVector Anchor=GetHeadLocation();
    for(int32 I=0;I<5;++I)
    {
        const float Radius=I<4?75.f:100.f;
        const float D=Distance(I<4?GetLegLocation(I):GetHeadLocation());
        float SurfaceDistance=D-Radius;
        if(I<4&&bUsingCustomuseVisual&&bAnatomicalLegContactsReady)
        {
            auto LimbDistance=[&](const FVector& A,const FVector& B)
            {
                return FMath::Min(SegmentTriangleDistance(A,B,CurrentBase,CurrentTip,PreviousTip),
                    SegmentTriangleDistance(A,B,CurrentBase,PreviousTip,PreviousBase));
            };
            const FVector Knee=GetLegKneeLocation(I),Hock=GetLegHockLocation(I),Ankle=GetLegLocation(I);
            SurfaceDistance=FMath::Min(SurfaceDistance,
                FMath::Min(LimbDistance(Knee,Hock),LimbDistance(Hock,Ankle))-GetLegContactRadius(I));
        }
        // Keep the existing ankle sphere and head sphere, plus the measured
        // lower-leg axes. One deepest region wins with the measured blade breadth.
        if(SurfaceDistance<=FMath::Clamp(BladeRadius,8.f,42.f)&&SurfaceDistance<Best){Best=SurfaceDistance;Region=I;Anchor=I<4?FMath::ClosestPointOnSegment((CurrentBase+CurrentTip)*.5f,GetLegKneeLocation(I),GetLegLocation(I)):GetHeadLocation();}
    }
    // Damageable anatomy agrees with solid movement geometry. Reachable
    // neck/body/tail contacts work during takeoff and landing as well.
    // Legs and head retain their special stagger/bonus rules.
    for(int32 I=0;I<SolidBodyCapsules.Num();++I)
    {
        if(I>=4&&I<15)continue;
        UCapsuleComponent* Part=SolidBodyCapsules[I];
        if(!Part||!bSolidBodyReady)continue;
        const float Radius=Part->GetScaledCapsuleRadius();
        const float HalfAxis=FMath::Max(0.f,Part->GetScaledCapsuleHalfHeight()-Radius);
        const FVector Axis=Part->GetUpVector()*HalfAxis;
        const FVector A=Part->GetComponentLocation()-Axis,B=Part->GetComponentLocation()+Axis;
        const float D=FMath::Min(SegmentTriangleDistance(A,B,CurrentBase,CurrentTip,PreviousTip),
            SegmentTriangleDistance(A,B,CurrentBase,PreviousTip,PreviousBase))-Radius;
        if(D<=FMath::Clamp(BladeRadius,8.f,42.f)&&Region<0){Region=5;Best=D;Anchor=FMath::ClosestPointOnSegment((CurrentBase+CurrentTip)*.5f,A,B);}
    }
    // Data hurt capsules (boxes.json) answer only blows every hard-coded region missed:
    // thighs, upper neck, belly, hips, wings. Legs keep their leg index for stagger.
    float PartScale=1.f;
    LastSwordHurtPart=NAME_None;
    if(Region<0&&bHurtPartsReady&&VeyrMoveData::SwordPartsEnabled())
        for(const FVeyrHurtPartRuntime& Part:HurtParts)
        {
            FVector A,B;float Radius=0.f;
            if(!HurtPartWorldSegment(Part,A,B,Radius))continue;
            const float D=FMath::Min(SegmentTriangleDistance(A,B,CurrentBase,CurrentTip,PreviousTip),
                SegmentTriangleDistance(A,B,CurrentBase,PreviousTip,PreviousBase))-Radius;
            if(D<=FMath::Clamp(BladeRadius,8.f,42.f)&&D<Best)
            {
                Best=D;Region=HurtPartRegion(Part);LastSwordHurtPart=Part.Part;
                PartScale=Region==5?Part.Damage:1.f;
                Anchor=FMath::ClosestPointOnSegment((CurrentBase+CurrentTip)*.5f,A,B);
            }
        }
    if(Region<0)return false;
    LastSwordContactWorld=FMath::ClosestPointOnSegment(Anchor,CurrentBase,CurrentTip);
    ApplySwordRegion(Region,bHeavy,SwingId,DamageMultiplier,PartScale);
    return true;
}

void AVeyrDragon::ApplySwordRegion(int32 Region,bool bHeavy,int32 SwingId,float DamageMultiplier,float PartDamageScale)
{
    AcceptedSwings.Add(SwingId); RecentSwings.Add(SwingId);
    if(RecentSwings.Num()>512){AcceptedSwings.Remove(RecentSwings[0]);RecentSwings.RemoveAt(0);}
    LastHitRegion=Region; ++SwordContactCount;
    LastSwordDamage=Region<4?(bHeavy?72.f:34.f):Region==5?(bHeavy?65.f:30.f):IsHeadExposed()?(bHeavy?270.f:125.f):(bHeavy?85.f:44.f);
    LastSwordDamage*=FMath::Clamp(DamageMultiplier,1.f,1.55f);
    // boxes.json body-part share (wings 0.5, tail 0.7); 1 for every hard-coded region.
    LastSwordDamage*=FMath::Clamp(PartDamageScale,0.f,2.f);
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
    return !IsAirborne()&&StaggerProtection<=0&&State!=EVeyrDragonState::Buckle&&State!=EVeyrDragonState::Collapse&&State!=EVeyrDragonState::Exposed&&State!=EVeyrDragonState::Rise&&State!=EVeyrDragonState::Dead;
}
FVector AVeyrDragon::GetMouthLocation() const {return bUsingCustomuseVisual?ImportedMouthWorld:GetHeadLocation();}
FVector AVeyrDragon::GetHeadLocation() const {return bUsingCustomuseVisual?ImportedHeadWorld:GetActorTransform().TransformPosition(HeadLocal);}
FVector AVeyrDragon::GetLegLocation(int32 Index) const {const int32 I=FMath::Clamp(Index,0,3);return bUsingCustomuseVisual?ImportedFeetWorld[I]:GetActorTransform().TransformPosition(LegLocal[I]);}
FVector AVeyrDragon::GetLegKneeLocation(int32 Index) const
{
    const int32 I=FMath::Clamp(Index,0,3);
    return bUsingCustomuseVisual&&bAnatomicalLegContactsReady?ImportedKneesWorld[I]:GetLegLocation(I);
}
FVector AVeyrDragon::GetLegHockLocation(int32 Index) const
{
    const int32 I=FMath::Clamp(Index,0,3);
    return bUsingCustomuseVisual&&bAnatomicalLegContactsReady?ImportedHocksWorld[I]:GetLegLocation(I);
}
float AVeyrDragon::GetLegContactRadius(int32 Index) const
{
    // Measured visible lower-leg skin at the native 1050 cm dragon size:
    // FL median58/P90=71, FR median64.5/P90=76.2, hinds median51/P90=61–66.
    // No hip/thigh region is added, and all radii remain <= the old ankle75.
    static constexpr float Radii[]={70.f,75.f,60.f,60.f};
    const float Scale=ImportedPresentation?ImportedPresentation->GetComponentTransform().GetScale3D().GetAbsMax()/21.558172f:1.f;
    return Radii[FMath::Clamp(Index,0,3)]*Scale;
}
float AVeyrDragon::GetLegStagger(int32 Index) const {return LegStagger[FMath::Clamp(Index,0,3)];}
float AVeyrDragon::GetHeadWindowRemaining() const {return IsHeadExposed()?FMath::Max(0.f,7.f-StateElapsed):0.f;}
bool AVeyrDragon::IsAirborne() const
{
    if(Move!=EVeyrDragonMove::FlyAway)return false;
    if(!HasAuthoredFlight())return State==EVeyrDragonState::Active&&StateElapsed<FlightSeconds;
    if(State==EVeyrDragonState::Windup)return StateElapsed>=16.f/30.f;
    if(State==EVeyrDragonState::Active)return true;
    const FVeyrVisualClip* Land=VisualDefinition->Clips.Find(TEXT("FlightRecovery"));
    const float Contact=Land&&Land->ImpactSeconds>=0.f?Land->ImpactSeconds:25.f/30.f;
    return State==EVeyrDragonState::Recovery&&StateElapsed<Contact;
}
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
        case EVeyrDragonState::Recovery:
            if(HasAuthoredFlight()&&Move==EVeyrDragonMove::FlyAway&&(IsAirborne()||IsLandingContactWindow()))
                return FText::FromString(TEXT("LANDING — CLEAR THE CIRCLE"));
            return FText::FromString(TEXT("OPENING — STRIKE OR HEAL"));
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

bool AVeyrDragon::WarningSurfaceHeight(const FVector& Point,float& Height)
{
    // Static terrain only: never project the warning onto the dragon, player,
    // or overhead architecture. Half-centimetre keys retain actual stair edges.
    const FIntPoint Key(FMath::RoundToInt(Point.X*2.f),FMath::RoundToInt(Point.Y*2.f));
    if(const float* Cached=WarningSurfaceHeights.Find(Key)){Height=*Cached;return Height>-10000.f;}
    Height=-100000.f;
    if(!GetWorld())return false;
    FCollisionQueryParams Params(SCENE_QUERY_STAT(VeyrWarningSurface),true,this);
    TArray<FHitResult> Hits;
    const FVector Top(Point.X,Point.Y,MaximumWarningFloorHeightCm+200.f),Bottom(Point.X,Point.Y,-150.f);
    ++WarningSurfaceTraceCount;
    GetWorld()->LineTraceMultiByObjectType(Hits,Top,Bottom,FCollisionObjectQueryParams(ECC_WorldStatic),Params);
    for(const FHitResult& Hit:Hits)
        if(!Hit.bStartPenetrating&&Hit.ImpactNormal.Z>.6f&&Hit.ImpactPoint.Z<=MaximumWarningFloorHeightCm+12.f)
            Height=FMath::Max(Height,static_cast<float>(Hit.ImpactPoint.Z));
    if(WarningSurfaceHeights.Num()<16384)WarningSurfaceHeights.Add(Key,Height);
    return Height>-10000.f;
}

void AVeyrDragon::AddGroundLine(UInstancedStaticMeshComponent* Lines,const FVector& A,const FVector& B,float Width)
{
    const int32 Pieces=FMath::Max(1,FMath::CeilToInt(FVector::Dist2D(A,B)/45.f));
    for(int32 I=0;I<Pieces;++I)
    {
        FVector Start=FMath::Lerp(A,B,static_cast<float>(I)/Pieces),End=FMath::Lerp(A,B,static_cast<float>(I+1)/Pieces);
        float Z0,Z1;if(!WarningSurfaceHeight(Start,Z0)||!WarningSurfaceHeight(End,Z1))continue;
        Start.Z=Z0+9.f;End.Z=Z1+9.f;const FVector Delta=End-Start;
        if(Delta.SizeSquared()<.01)continue;
        Lines->AddInstance(FTransform(Delta.Rotation(),(Start+End)*.5,FVector(Delta.Size()/100,Width/100,1.f/100)),true);
    }
}

void AVeyrDragon::DrawFootprint(UInstancedStaticMeshComponent* Lines,const FVeyrDragonFootprint& F,bool bBright,const TArray<FVeyrDragonFootprint>* Union,int32 OwnIndex)
{
    if(F.Shape==EVeyrDangerShape::None)return;
    const float Width=bBright?9.f:7.f;
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
    if(bWarningDrawn&&HasAuthoredFlight()&&Move==EVeyrDragonMove::FlyAway&&
       State==EVeyrDragonState::Recovery&&!IsAirborne()&&!IsLandingContactWindow())WarningLines->ClearInstances();
    if(!bWarningDrawn||Move==EVeyrDragonMove::FlyAway)
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


bool AVeyrDragon::InitializeAnatomicalLegContacts()
{
    bAnatomicalLegContactsReady=false;LegContactDiagnostic.Reset();
    if(!VisualDefinition||!ImportedPresentation)return false;
    for(int32 I=0;I<4;++I)
    {
        const FVeyrVisualBoneTarget* Ankle=VisualDefinition->BoneTargets.Find(FName(*FString::Printf(TEXT("leg%d"),I)));
        if(!Ankle){LegContactDiagnostic=TEXT("Anatomical ankle target missing");return false;}
        // The measured 51-bone dragon topology has one shin link in front and
        // two calf links behind. Resolve imported/sanitized names through its
        // actual hierarchy; never mistake the existing ankle target for a knee.
        const FName Parent=ImportedPresentation->GetParentBone(Ankle->BoneName);
        ImportedHockBones[I]=I<2?Ankle->BoneName:Parent;
        ImportedKneeBones[I]=I<2?Parent:ImportedPresentation->GetParentBone(Parent);
        if(ImportedKneeBones[I].IsNone()||ImportedHockBones[I].IsNone()||
           ImportedPresentation->GetBoneIndex(ImportedKneeBones[I])==INDEX_NONE||
           ImportedPresentation->GetBoneIndex(ImportedHockBones[I])==INDEX_NONE)
        {LegContactDiagnostic=FString::Printf(TEXT("Anatomical lower-leg hierarchy missing for region %d"),I);return false;}
        LegContactDiagnostic+=FString::Printf(TEXT("leg%d %s -> %s -> %s, radius %.1f cm; "),I,
            *ImportedKneeBones[I].ToString(),*ImportedHockBones[I].ToString(),*Ankle->BoneName.ToString(),GetLegContactRadius(I));
    }
    bAnatomicalLegContactsReady=true;
    return true;
}

bool AVeyrDragon::InitializeSolidBody()
{
    bSolidBodyReady=false;bSolidBodyHasPose=false;SolidBodyDiagnostic.Reset();
    for(UCapsuleComponent* Part:SolidBodyCapsules)if(Part)Part->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    if(!bAnatomicalLegContactsReady||!ImportedPresentation||!VisualDefinition||SolidBodyCapsules.Num()!=19)return false;
    const FVeyrVisualBoneTarget* Head=VisualDefinition->BoneTargets.Find(TEXT("head"));
    if(!Head)return false;
    SolidNeckMiddleBone=ImportedPresentation->GetParentBone(Head->BoneName);
    SolidNeckBaseBone=ImportedPresentation->GetParentBone(SolidNeckMiddleBone);
    SolidChestBone=ImportedPresentation->GetParentBone(SolidNeckBaseBone);
    SolidPelvisBone=ImportedPresentation->GetParentBone(ImportedPresentation->GetParentBone(
        ImportedPresentation->GetParentBone(ImportedKneeBones[2])));
    for(FName Bone:{SolidNeckMiddleBone,SolidNeckBaseBone,SolidChestBone,SolidPelvisBone})
        if(Bone.IsNone()||ImportedPresentation->GetBoneIndex(Bone)==INDEX_NONE)
        {SolidBodyDiagnostic=TEXT("Solid dragon anatomy binding failed; blocker skeleton missing");return false;}
    bSolidBodyReady=true;SolidBodyDiagnostic=TEXT("19 evaluated anatomical Pawn blockers; no camera wall; native overlap validation pending");
    return true;
}

void AVeyrDragon::UpdateSolidBody()
{
    if(!bSolidBodyReady||!bImportedTargetsValid||!ImportedPresentation)return;
    auto Bone=[&](FName Name){return ImportedPresentation->GetBoneTransform(ImportedPresentation->GetBoneIndex(Name)).GetLocation();};
    const float Scale=ImportedPresentation->GetComponentTransform().GetScale3D().GetAbsMax()/21.558172f;
    FVector Starts[19],Ends[19];float Radii[19];
    auto Place=[&](int32 Index,const FVector& A,const FVector& B,float MeasuredRadius)
    {
        Starts[Index]=A;Ends[Index]=B;Radii[Index]=MeasuredRadius*Scale;
    };
    const FVector Pelvis=Bone(SolidPelvisBone),Chest=Bone(SolidChestBone),NeckBase=Bone(SolidNeckBaseBone),NeckMiddle=Bone(SolidNeckMiddleBone);
    // Measured body skin: median radius149 cm, P95 227 cm, torso half-width239.
    // This covers the mass, leaving the visible spaces between individual legs.
    Place(0,Pelvis,Chest,225.f);Place(1,Chest,NeckBase,145.f);
    Place(2,NeckBase,NeckMiddle,110.f);Place(3,NeckMiddle,ImportedHeadWorld,100.f);
    Place(4,ImportedHeadWorld,ImportedMouthWorld,100.f);
    Place(5,ImportedKneesWorld[0],ImportedFeetWorld[0],70.f);
    Place(6,ImportedKneesWorld[1],ImportedFeetWorld[1],75.f);
    Place(7,ImportedKneesWorld[2],ImportedHocksWorld[2],60.f);Place(8,ImportedHocksWorld[2],ImportedFeetWorld[2],60.f);
    Place(9,ImportedKneesWorld[3],ImportedHocksWorld[3],60.f);Place(10,ImportedHocksWorld[3],ImportedFeetWorld[3],60.f);
    for(int32 I=0;I<4;++I)Place(11+I,ImportedFeetWorld[I],ImportedFeetWorld[I],75.f);
    Place(15,ImportedTailWorld[0],ImportedTailWorld[1],110.f);
    Place(16,ImportedTailWorld[1],ImportedTailWorld[2],75.f);Place(17,ImportedTailWorld[2],ImportedTailWorld[3],50.f);
    FTransform Tip;
    if(!ImportedPresentation->GetBoneTargetWorldTransform(TEXT("tail_tip"),Tip))return;
    Place(18,ImportedTailWorld[3],Tip.GetLocation(),25.f);
    float FurthestMove=0.f;
    for(int32 I=0;I<19;++I)
    {
        if(Starts[I].ContainsNaN()||Ends[I].ContainsNaN())return;
        if(bSolidBodyHasPose)FurthestMove=FMath::Max(FurthestMove,static_cast<float>(FMath::Max(
            FVector::Dist(Starts[I],SolidPreviousStarts[I]),FVector::Dist(Ends[I],SolidPreviousEnds[I]))));
    }
    const int32 Steps=FMath::Clamp(FMath::CeilToInt(FurthestMove/40.f),1,32);
    for(int32 Step=1;Step<=Steps;++Step)
    {
        const float T=static_cast<float>(Step)/Steps;
        for(int32 I=0;I<19;++I)
        {
            const FVector A=bSolidBodyHasPose?FMath::Lerp(SolidPreviousStarts[I],Starts[I],T):Starts[I];
            const FVector B=bSolidBodyHasPose?FMath::Lerp(SolidPreviousEnds[I],Ends[I],T):Ends[I];
            UCapsuleComponent* Part=SolidBodyCapsules[I];const FVector Axis=B-A;
            const float Radius=Radii[I],HalfHeight=Radius+static_cast<float>(Axis.Size())*.5f;
            if(!FMath::IsNearlyEqual(Part->GetUnscaledCapsuleRadius(),Radius,.1f)||
               !FMath::IsNearlyEqual(Part->GetUnscaledCapsuleHalfHeight(),HalfHeight,.25f))Part->SetCapsuleSize(Radius,HalfHeight,false);
            const FQuat Rotation=Axis.IsNearlyZero()?FQuat::Identity:FQuat::FindBetweenNormals(FVector::UpVector,Axis.GetSafeNormal());
            Part->SetWorldLocationAndRotation((A+B)*.5,Rotation,false,nullptr,ETeleportType::TeleportPhysics);
            Part->SetCollisionEnabled(ECollisionEnabled::QueryOnly);
        }
        // Resolve along the path, not just at its endpoint: a large frame cannot
        // carry a narrow limb completely past the Knight without a contact query.
        ResolveKnightBodyPenetration();
    }
    for(int32 I=0;I<19;++I){SolidPreviousStarts[I]=Starts[I];SolidPreviousEnds[I]=Ends[I];}
    bSolidBodyHasPose=true;
    // Flight/collapse/death use the same evaluated shapes. Elevated parts do
    // not leave an invisible ground wall; a fallen body remains physically solid.
}

void AVeyrDragon::ResolveKnightBodyPenetration()
{
    SolidBodyPenetrationDepthCm=0.f;
    if(!bSolidBodyReady||!IsValid(Target)||Target->IsDead())return;
    UCapsuleComponent* PlayerCapsule=Target->GetCapsuleComponent();
    UCharacterMovementComponent* Movement=Target->GetCharacterMovement();
    if(!PlayerCapsule||!Movement||!GetWorld())return;
    const FCollisionShape Shape=PlayerCapsule->GetCollisionShape();const FQuat Rotation=PlayerCapsule->GetComponentQuat();
    auto Penetration=[&](const FVector& Point,UCapsuleComponent*& Deepest,FMTDResult& Result)
    {
        float Depth=0.f;Deepest=nullptr;
        TArray<UCapsuleComponent*,TInlineAllocator<40>> Blockers;
        for(UCapsuleComponent* Solid:SolidBodyCapsules)Blockers.Add(Solid);
        for(int32 I=0;I<HurtCapsules.Num()&&I<HurtParts.Num();++I)if(HurtParts[I].bBlocksPawn)Blockers.Add(HurtCapsules[I]);
        for(UCapsuleComponent* Part:Blockers)
        {
            FMTDResult MTD;
            if(Part&&Part->IsQueryCollisionEnabled()&&Part->ComputePenetration(MTD,Shape,Point,Rotation)&&
               FMath::IsFinite(MTD.Distance)&&!MTD.Direction.ContainsNaN()&&MTD.Distance>Depth)
            {Depth=MTD.Distance;Deepest=Part;Result=MTD;}
        }
        return Depth;
    };
    UCapsuleComponent* Deepest=nullptr;FMTDResult MTD;
    const FVector Start=PlayerCapsule->GetComponentLocation();
    const float Depth=Penetration(Start,Deepest,MTD);SolidBodyPenetrationDepthCm=Depth;
    if(Depth<=.5f||!Deepest)return;
    FVector Direction=MTD.Direction.GetSafeNormal2D();
    if(Direction.IsNearlyZero())Direction=(Start-Deepest->GetComponentLocation()).GetSafeNormal2D();
    if(Direction.IsNearlyZero())Direction=GetActorRightVector().GetSafeNormal2D();
    FCollisionQueryParams Params(SCENE_QUERY_STAT(VeyrDragonSolidPush),false,Target);
    Params.AddIgnoredActor(this); // escape the actual overlap, never cross a wall
    for(float Extra:{2.f,30.f,80.f,160.f})
        for(float Angle:{0.f,45.f,-45.f,90.f,-90.f,135.f,-135.f,180.f})
        {
            const FVector Adjustment=Direction.RotateAngleAxis(Angle,FVector::UpVector)*FMath::Min(320.f,Depth+Extra);
            UCapsuleComponent* Other=nullptr;FMTDResult Candidate;
            if(Penetration(Start+Adjustment,Other,Candidate)>.5f)continue;
            FHitResult Wall;
            if(GetWorld()->SweepSingleByChannel(Wall,Start,Start+Adjustment,Rotation,ECC_Pawn,Shape,Params)&&Wall.bBlockingHit)continue;
            FHitResult ActualOverlap(Deepest->GetOwner(),Deepest,Start,MTD.Direction);
            ActualOverlap.bStartPenetrating=true;ActualOverlap.bBlockingHit=true;ActualOverlap.PenetrationDepth=Depth;
            ActualOverlap.TraceStart=Start;ActualOverlap.TraceEnd=Start;
            if(Movement->ResolvePenetration(Adjustment,ActualOverlap,Rotation))
            {
                ++SolidBodyPushCount;LastSolidBodyPushShape=Deepest->GetFName();
                SolidBodyPenetrationDepthCm=Penetration(PlayerCapsule->GetComponentLocation(),Other,Candidate);
                return;
            }
        }
    SolidBodyDiagnostic=FString::Printf(TEXT("Solid dragon penetration %.2f cm could not resolve without crossing world geometry"),Depth);
}

bool AVeyrDragon::ApplyCustomuseVisual(UVeyrVisualDefinition* Definition)
{
    if(!Definition||!ImportedPresentation)return false;
    DestroyHurtParts(); // bone indices belong to the previous mesh; rebound below
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
    bUsingPolishDefinition=Definition->GetPathName().StartsWith(TEXT("/Game/Characters/Customuse/RuntimePolish/"));
    InitializeAnatomicalLegContacts();
    InitializeSolidBody();
    for(UStaticMeshComponent* Part:TemporaryParts)if(Part)Part->SetVisibility(false);
    ImportedPresentation->SetVisibility(true);
    TemporaryLabel->SetVisibility(false);
    bImportedAttackCacheReady=AttackPoseProbe->SetVisualDefinition(Definition,false)&&
        CalibrateBiteGroundAim()&&CacheImportedAttackWarnings();
    if(!bImportedAttackCacheReady&&!BiteGroundAimDiagnostic.IsEmpty())ImportedCombatDiagnostic=BiteGroundAimDiagnostic;
    AttackPoseProbe->SetVisibility(false);AttackPoseProbe->SetHiddenInGame(true);
    LastImportedClip=NAME_None;bImportedTransitionReady=false;
    bPresentationMotionInitialized=false;WalkPhase=TurnPhase=0.f;
    GazeSmoothedYaw=GazeSmoothedPitch=GazeYawDegrees=GazePitchDegrees=0.f;
    UpdateImportedPresentation();
    BuildHurtParts();
    UpdateHurtParts();
    UpdateSolidBody();
    InitializeCameraOcclusionMaterials();
    return true;
}

void AVeyrDragon::UpdateGaze(float DeltaSeconds)
{
    const bool Allowed=!bEncounterStopped&&IsValid(Target)&&!Target->IsDead()&&
        (State==EVeyrDragonState::Idle||State==EVeyrDragonState::Recovery||State==EVeyrDragonState::Reposition)&&
        !(HasAuthoredFlight()&&Move==EVeyrDragonMove::FlyAway&&State==EVeyrDragonState::Recovery);
    float DesiredYaw=0.f,DesiredPitch=0.f,Weight=0.f;
    if(Allowed)
    {
        const FVector Head=bImportedTargetsValid?ImportedHeadWorld:GetActorTransform().TransformPosition(HeadLocal);
        const FVector Direction=GetActorQuat().UnrotateVector(Target->GetFootLocation()+FVector(0,0,150)-Head);
        DesiredYaw=FMath::Clamp(static_cast<float>(FMath::RadiansToDegrees(FMath::Atan2(Direction.Y,Direction.X))),-14.f,14.f);
        DesiredPitch=FMath::Clamp(static_cast<float>(FMath::RadiansToDegrees(FMath::Atan2(Direction.Z,FVector2D(Direction.X,Direction.Y).Size()))),-8.f,5.f);
        // Zero before commitment. No tracking in Windup/Active, no modifiers on
        // the attack-envelope probe, and no target-following committed warnings.
        Weight=Ease(FMath::Min(StateElapsed/.25f,(StateDuration-StateElapsed)/.35f));
        if(State==EVeyrDragonState::Idle&&!Target->HasEnteredEncounter())Weight=Ease(Clock/.25f);
    }
    GazeSmoothedYaw=FMath::FInterpConstantTo(GazeSmoothedYaw,DesiredYaw,DeltaSeconds,24.f);
    GazeSmoothedPitch=FMath::FInterpConstantTo(GazeSmoothedPitch,DesiredPitch,DeltaSeconds,14.f);
    GazeYawDegrees=GazeSmoothedYaw*Weight;GazePitchDegrees=GazeSmoothedPitch*Weight;
}

void AVeyrDragon::UpdateImportedPresentation()
{
    if(!bUsingCustomuseVisual||!VisualDefinition||!ImportedPresentation)return;
    bImportedTargetsValid=false;
    const FVector CurrentLocation=GetActorLocation();
    const float CurrentYaw=GetActorRotation().Yaw;
    if(bPresentationMotionInitialized&&State==EVeyrDragonState::Reposition)
    {
        const FVector Travel=Ground(CurrentLocation-LastPresentationLocation);
        const float SignedTravel=static_cast<float>(FVector::DotProduct(Travel,GetActorForwardVector()));
        if(bRepositionWalking)
        {
            WalkPhase=FMath::Fmod(WalkPhase+SignedTravel/FMath::Max(1.f,WalkCycleDistance()),1.f);
            if(WalkPhase<0.f)WalkPhase+=1.f;
        }
        if(!bRepositionAuthoredTurn)
            TurnPhase=FMath::Fmod(TurnPhase+FMath::Abs(FMath::FindDeltaAngleDegrees(LastPresentationYaw,CurrentYaw))/20.f,1.f);
    }
    LastPresentationLocation=CurrentLocation;LastPresentationYaw=CurrentYaw;bPresentationMotionInitialized=true;
    TMap<FName,FRotator> Gaze;
    const bool GroundBite=HasGroundTargetBite()&&bBiteGroundAimReady&&Move==EVeyrDragonMove::Bite&&
        (State==EVeyrDragonState::Windup||State==EVeyrDragonState::Active||State==EVeyrDragonState::Recovery);
    if((State==EVeyrDragonState::Idle||State==EVeyrDragonState::Recovery||State==EVeyrDragonState::Reposition)&&
       !(HasAuthoredFlight()&&Move==EVeyrDragonMove::FlyAway&&State==EVeyrDragonState::Recovery)&&!GroundBite)
    {
        const FVeyrVisualBoneTarget* Head=VisualDefinition->BoneTargets.Find(TEXT("head"));
        const FVeyrVisualBoneTarget* Neck=VisualDefinition->BoneTargets.Find(TEXT("gaze_neck"));
        const bool SeparateNeck=Neck&&Head&&Neck->BoneName!=Head->BoneName;
        if(SeparateNeck)Gaze.Add(Neck->BoneName,FRotator(GazePitchDegrees*.6f,GazeYawDegrees*.6f,0));
        if(Head)Gaze.Add(Head->BoneName,FRotator(GazePitchDegrees*(SeparateNeck?.4f:1.f),GazeYawDegrees*(SeparateNeck?.4f:1.f),0));
    }
    if(GroundBite)
    {
        const FName BiteClip=ImportedMoveClip(EVeyrDragonMove::Bite,0,
            State==EVeyrDragonState::Windup?TEXT("Windup"):State==EVeyrDragonState::Active?TEXT("Active"):TEXT("Recovery"));
        const FVeyrVisualClip& Config=VisualDefinition->Clips.FindChecked(BiteClip);
        const float Trimmed=FMath::Clamp(StateElapsed/FMath::Max(.001f,StateDuration),0.f,1.f)*VisualClipDuration(BiteClip,0.f);
        Gaze=BiteGroundRotations(Config.StartSeconds+Trimmed,BiteGroundPitchDegrees);
    }
    if(!ImportedPresentation->SetComponentSpaceBoneRotations(Gaze))return;
    FString Name;
    switch(State)
    {
        case EVeyrDragonState::Idle:Name=IsDataOnlyMovePlaying()&&!DataOnlyClip.IsNone()?DataOnlyClip.ToString():FString(TEXT("Idle"));break;
        case EVeyrDragonState::Reposition:
            Name=bRepositionWalking?TEXT("Walk"):(bRepositionAuthoredTurn||RepositionTurnClip==FName(TEXT("TurnLeftFine"))||
                RepositionTurnClip==FName(TEXT("TurnRightFine")))?RepositionTurnClip.ToString():
                RepositionYawDelta>=0.f?TEXT("TurnRight"):TEXT("TurnLeft");
            if(!bRepositionWalking&&(!VisualDefinition->Clips.Contains(FName(*Name))||!VisualDefinition->Clips[FName(*Name)].Sequence))
            {
                LocomotionDiagnostic=TEXT("Optional stepping-turn clip absent; stationary Idle fallback during actor turn: ")+Name;
                Name=TEXT("Idle");
            }
            else LocomotionDiagnostic.Reset();
            break;
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
            if(Move==EVeyrDragonMove::FlyAway&&State==EVeyrDragonState::Active&&HasAuthoredFlight()&&
               bHoverAlternateThisFlight&&StateElapsed>=.2f&&StateElapsed<ActiveDuration-.2f)
                Name=TEXT("FlightHoverAlternate");
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
        const bool Turning=State==EVeyrDragonState::Reposition&&!bRepositionWalking;
        float SampleSeconds=Clip==FName(TEXT("Walk"))?WalkPhase*Duration:Turning?TurnPhase*Duration:Clock;
        const bool AuthoredTurn=State==EVeyrDragonState::Reposition&&!bRepositionWalking&&bRepositionAuthoredTurn;
        if(AuthoredTurn){const float T=FMath::Clamp(StateElapsed/FMath::Max(.001f,RepositionTurnDuration),0.f,1.f);SampleSeconds=(bRepositionReverseTurn?1.f-T:T)*Duration;}
        if(HasAuthoredFlight()&&Move==EVeyrDragonMove::FlyAway&&State==EVeyrDragonState::Active)SampleSeconds=StateElapsed;
        // Authored cyclic curves already close their loop. Freezing/reblending
        // every idle wrap adds a visible hitch and changes the breathing timing.
        if(LastImportedClip!=Clip||LastImportedState!=State)
        {
            const FVeyrVisualClip* Previous=VisualDefinition->Clips.Find(LastImportedClip);
            const bool AliasOnly=Previous&&LastImportedState==State&&Previous->Sequence==Config.Sequence&&
                Previous->MeshOverride==Config.MeshOverride&&Previous->bLoop==Config.bLoop&&
                FMath::IsNearlyEqual(Previous->StartSeconds,Config.StartSeconds)&&FMath::IsNearlyEqual(Previous->EndSeconds,Config.EndSeconds);
            const bool AdjacentAttackTrim=Previous&&Previous->Sequence&&!Config.bLoop&&
                !Config.ApprovedSourceSHA256.IsEmpty()&&Config.ApprovedSourceSHA256==Previous->ApprovedSourceSHA256&&
                Previous->EndSeconds>=0.f&&FMath::IsNearlyEqual(Previous->EndSeconds,Config.StartSeconds,.002f)&&
                ((LastImportedState==EVeyrDragonState::Windup&&State==EVeyrDragonState::Active)||
                 (LastImportedState==EVeyrDragonState::Active&&State==EVeyrDragonState::Recovery));
            // Definition activation starts in the authored pose immediately;
            // do not freeze a blend from the bind pose before encounter input.
            // Adjacent trims are one continuous authored action: another blend
            // would soften the bite's fastest lunge and change its impact time.
            bImportedTransitionReady=!LastImportedClip.IsNone()&&!AdjacentAttackTrim&&!AliasOnly&&ImportedPresentation->BeginTransition();
            // The legacy rise finishes with raised wings; give their fold into
            // the approved resting silhouette weight instead of snapping shut.
            ImportedTransitionSeconds=LastImportedState==EVeyrDragonState::Rise&&State==EVeyrDragonState::Idle?.55f:
                HasAuthoredFlight()&&Move==EVeyrDragonMove::FlyAway&&State==EVeyrDragonState::Active?.2f:.12f;
            ImportedTransitionStarted=Clock;LastImportedClip=Clip;LastImportedState=State;
        }
        const float TransitionSeconds=ImportedTransitionSeconds;
        const float Alpha=bImportedTransitionReady?FMath::Clamp((Clock-ImportedTransitionStarted)/TransitionSeconds,0.f,1.f):1.f;
        const bool Loop=VisualDefinition->Clips[Clip].bLoop;
        if(IsDataOnlyMovePlaying()&&Clip==DataOnlyClip){SampleSeconds=DataMoveClipSeconds;}
        Sampled=Loop||AuthoredTurn||(IsDataOnlyMovePlaying()&&Clip==DataOnlyClip)?ImportedPresentation->SampleClipTimeBlended(Clip,SampleSeconds,Alpha):
            ImportedPresentation->SampleClipPhaseBlended(Clip,StateElapsed/FMath::Max(.001f,StateDuration),Alpha);
    }
    if(Sampled&&Move==EVeyrDragonMove::FlyAway&&State==EVeyrDragonState::Active)
    {
        const float T=StateElapsed/FMath::Max(.01f,ActiveDuration);
        const float AimWeight=Ease((T-.18f)/.22f)*(1.f-Ease((T-.72f)/.15f));
        FTransform M,A;
        const auto* H=VisualDefinition->BoneTargets.Find(TEXT("head"));
        const auto* J=VisualDefinition->BoneTargets.Find(TEXT("jaw"));
        if(AimWeight>0.f&&H&&ImportedPresentation->GetBoneTargetWorldTransform(TEXT("mouth"),M)&&ImportedPresentation->GetBoneTargetWorldTransform(TEXT("mouth_aim"),A))
        {
            const FVector From=ImportedPresentation->GetComponentQuat().UnrotateVector((A.GetLocation()-M.GetLocation()).GetSafeNormal());
            const FVector Toward=ImportedPresentation->GetComponentQuat().UnrotateVector((AerialFireTarget+FVector(0,0,50)-M.GetLocation()).GetSafeNormal());
            FRotator Offset=FQuat::FindBetweenNormals(From,Toward).Rotator();
            Offset.Pitch=FMath::Clamp(Offset.Pitch,-54.f,54.f);Offset.Yaw=FMath::Clamp(Offset.Yaw,-36.f,36.f);Offset.Roll=0.f;
            TMap<FName,FRotator> Aim;
            if(!BiteNeckBase.IsNone()&&!BiteNeckMiddle.IsNone())
            {
                Aim.Add(BiteNeckBase,Offset*(AimWeight/3.f));
                Aim.Add(BiteNeckMiddle,Offset*(AimWeight/3.f));
                Aim.Add(H->BoneName,Offset*(AimWeight/3.f));
            }
            if(J)Aim.Add(J->BoneName,FRotator(-18.f*AimWeight,0,0));
            if(ImportedPresentation->SetComponentSpaceBoneRotations(Aim))ImportedPresentation->SampleClipTime(Clip,StateElapsed);
        }
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
    if(bAnatomicalLegContactsReady)
        for(int32 I=0;I<4;++I)
        {
            const int32 Knee=ImportedPresentation->GetBoneIndex(ImportedKneeBones[I]);
            const int32 Hock=ImportedPresentation->GetBoneIndex(ImportedHockBones[I]);
            if(Knee==INDEX_NONE||Hock==INDEX_NONE)return;
            ImportedKneesWorld[I]=ImportedPresentation->GetBoneTransform(Knee).GetLocation();
            ImportedHocksWorld[I]=ImportedPresentation->GetBoneTransform(Hock).GetLocation();
            if(ImportedKneesWorld[I].ContainsNaN()||ImportedHocksWorld[I].ContainsNaN())return;
        }
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
    if(!bUsingCustomuseVisual||!bImportedTargetsValid||!bImportedAttackCacheReady||bEncounterStopped||!MissingVisualClip.IsNone())return Beam;
    if(Move==EVeyrDragonMove::FlyAway&&State==EVeyrDragonState::Active)
    {
        const float T=StateElapsed/FMath::Max(.01f,ActiveDuration);
        if(T<.48f||T>.72f)return Beam;
        Beam.Origin=ImportedMouthWorld;
        const FVector ToGround=AerialFireTarget+FVector(0,0,50)-Beam.Origin;
        Beam.Direction=ToGround.GetSafeNormal();
        Beam.Length=(ToGround.Size()+150.f)*FMath::Clamp((T-.48f)*ActiveDuration/.18f,0.f,1.f);
        Beam.HalfAngleDegrees=FMath::RadiansToDegrees(FMath::Atan(300.f/FMath::Max(1.f,static_cast<float>(ToGround.Size()))));Beam.bDamaging=Beam.Length>20.f;return Beam;
    }
    if(!bUsingCustomuseVisual||!bImportedTargetsValid||!bImportedAttackCacheReady||
       State!=EVeyrDragonState::Active||Move!=EVeyrDragonMove::Fire||bEncounterStopped||!MissingVisualClip.IsNone())return Beam;
    Beam.Origin=ImportedMouthWorld;Beam.Direction=(ImportedMouthAimWorld-ImportedMouthWorld).GetSafeNormal();
    // The visible jet reaches full range over 0.18 s. Damage uses this same
    // advancing front; no invisible full-length hit precedes the emitted flame.
    Beam.Length*=FMath::Clamp(StateElapsed/.18f,0.f,1.f);
    Beam.bDamaging=Beam.Length>20.f&&!Beam.Direction.IsNearlyZero();return Beam;
}

FVeyrDragonFootprint AVeyrDragon::ProjectFlameToGround(const FVeyrDragonFlameBeam& Beam,float Padding,bool bAllWalkableHeights) const
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
        // Reusable local caches cover every court height. Committed and live
        // geometry use the actual nearby stair/aisle bounds, so raised-floor
        // coverage does not paint a fictitious low hazard across the whole arena.
        const float FloorHeight=bAllWalkableHeights?MaximumWarningFloorHeightCm:
            WarningArena.IsValid()?WarningArena->GetMaximumWalkableHeightNear(P,R):9.f;
        const float Dz=FMath::Max(0.f,FMath::Max(static_cast<float>(Radius-P.Z),
            static_cast<float>(P.Z-(2.f*HalfHeight-Radius+FloorHeight))));
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
                TMap<FName,FRotator> Aim;
                if(Attack==EVeyrDragonMove::Bite&&HasGroundTargetBite()&&bBiteGroundAimReady)
                {
                    const FVeyrVisualClip& Config=VisualDefinition->Clips.FindChecked(Clip);
                    const float SourceSeconds=Config.StartSeconds+VisualClipDuration(Clip,0.f)*I/32.f;
                    Aim=BiteGroundRotations(SourceSeconds,BiteGroundPitchDegrees);
                }
                // Exactly the same pose layer is published for visible motion,
                // live jaw contact and the committed warning envelope.
                if(!AttackPoseProbe->SetComponentSpaceBoneRotations(Aim))
                {ImportedCombatDiagnostic=AttackPoseProbe->LastError;return false;}
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
                    auto F=ProjectFlameToGround(Beam,100.f,true);if(F.Shape!=EVeyrDangerShape::None)Sample.Add(F);
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
    LandingLocalCenter=FVector::ZeroVector;LandingWarningRadius=600.f;
    if(!AttackPoseProbe->SetComponentSpaceBoneRotations({}))return false;
    if(HasAuthoredFlight())
    {
        const FVeyrVisualClip& Land=VisualDefinition->Clips.FindChecked(TEXT("FlightRecovery"));
        const float Impact=Land.ImpactSeconds>=0.f?Land.ImpactSeconds-Land.StartSeconds:.833333f;
        TArray<FVector> Feet;
        for(int32 Sample=0;Sample<=8;++Sample)
        {
            if(!AttackPoseProbe->SampleClipTime(TEXT("FlightRecovery"),Impact+.2f*Sample/8.f))
            {ImportedCombatDiagnostic=TEXT("Landing envelope pose failed");return false;}
            for(int32 Foot=0;Foot<4;++Foot)
            {
                FTransform T;
                if(!AttackPoseProbe->GetBoneTargetWorldTransform(FName(*FString::Printf(TEXT("foot%d"),Foot)),T))
                {ImportedCombatDiagnostic=TEXT("Landing envelope foot missing");return false;}
                Feet.Add(Ground(Actor.InverseTransformPosition(T.GetLocation())));
            }
        }
        for(const FVector& Foot:Feet)LandingLocalCenter+=Foot;
        LandingLocalCenter/=Feet.Num();LandingWarningRadius=0.f;
        // The telegraph and damage share one envelope enclosing every landing paw.
        for(const FVector& Foot:Feet)LandingWarningRadius=FMath::Max(LandingWarningRadius,
            static_cast<float>(FVector::Dist2D(Foot,LandingLocalCenter))+230.f+KnightRadius);
    }
    ImportedCombatDiagnostic=TEXT("Bone attack envelopes cached; native visual/contact verification pending");return true;
}

void AVeyrDragon::CommitImportedWarning()
{
    CommittedWarning.Reset();
    WarningSurfaceHeights.Reset();WarningSurfaceTraceCount=0;
    if(!bImportedAttackCacheReady)return;
    if(Move==EVeyrDragonMove::FlyAway)
    {
        FVeyrDragonFootprint F;F.Shape=EVeyrDangerShape::Circle;
        F.Origin=MoveEnd+GetActorQuat().RotateVector(LandingLocalCenter);F.Origin.Z=MoveEnd.Z;
        F.OuterRadius=LandingWarningRadius;AttackOrigin=F.Origin;CommittedWarning.Add(F);return;
    }
    if(Move==EVeyrDragonMove::Fire)
    {
        // The definition cache is position-independent. Fire commits a tighter
        // world-space envelope against the current court elevations instead.
        if(!AttackPoseProbe->SetComponentSpaceBoneRotations({}))return;
        for(int32 I=0;I<=32;++I)
        {
            if(!AttackPoseProbe->SampleClipPhase(TEXT("FireActive"),I/32.f))
            {ImportedCombatDiagnostic=AttackPoseProbe->LastError;CommittedWarning.Reset();return;}
            TArray<FVeyrDragonContact> Contacts;FVeyrDragonFlameBeam Beam;
            if(!ReadImportedContactPose(AttackPoseProbe,EVeyrDragonMove::Fire,0,Contacts,Beam))
            {ImportedCombatDiagnostic=TEXT("Committed fire pose unavailable");CommittedWarning.Reset();return;}
            auto F=ProjectFlameToGround(Beam,100.f);F.bDamaging=false;
            if(F.Shape!=EVeyrDangerShape::None)CommittedWarning.Add(F);
        }
        if(!CommittedWarning.IsEmpty())AttackOrigin=CommittedWarning[0].Origin;
        return;
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
    {
        const bool Landing=HasAuthoredFlight()&&Move==EVeyrDragonMove::FlyAway&&State==EVeyrDragonState::Recovery&&
            (IsAirborne()||IsLandingContactWindow());
        auto Result=!bEncounterStopped&&(State==EVeyrDragonState::Windup||State==EVeyrDragonState::Active||Landing)?
            CommittedWarning:TArray<FVeyrDragonFootprint>();
        if(!bEncounterStopped&&Move==EVeyrDragonMove::FlyAway&&State==EVeyrDragonState::Active&&StateElapsed/ActiveDuration<=.72f)
        {
            FVeyrDragonFootprint Fire;Fire.Shape=EVeyrDangerShape::Circle;Fire.Origin=AerialFireTarget;
            Fire.OuterRadius=430.f;Result.Add(Fire);
        }
        return Result;
    }
    const auto F=GetWarningFootprint();return F.Shape==EVeyrDangerShape::None?TArray<FVeyrDragonFootprint>():TArray<FVeyrDragonFootprint>{F};
}

TArray<FVeyrDragonFootprint> AVeyrDragon::GetActiveFootprints() const
{
    if(!bUsingCustomuseVisual)
    {const auto F=GetActiveFootprint();return F.Shape==EVeyrDangerShape::None?TArray<FVeyrDragonFootprint>():TArray<FVeyrDragonFootprint>{F};}
    TArray<FVeyrDragonFootprint> Result;
    if((State!=EVeyrDragonState::Active&&!IsLandingContactWindow())||bEncounterStopped||!bImportedTargetsValid||!bImportedAttackCacheReady||!MissingVisualClip.IsNone())return Result;
    if(Move==EVeyrDragonMove::Fire)
    {auto F=ProjectFlameToGround(GetActiveFlameBeam());if(F.Shape!=EVeyrDangerShape::None)Result.Add(F);return Result;}
    if(Move==EVeyrDragonMove::FlyAway)
    {
        const auto Beam=GetActiveFlameBeam();
        if(Beam.bDamaging){auto Fire=ProjectFlameToGround(Beam);if(Fire.Shape!=EVeyrDangerShape::None)Result.Add(Fire);}
        if(HasAuthoredFlight()?IsLandingContactWindow():StateElapsed>=FlightSeconds)
        {Result=CommittedWarning;for(auto& F:Result)F.bDamaging=true;}
        return Result;
    }
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
