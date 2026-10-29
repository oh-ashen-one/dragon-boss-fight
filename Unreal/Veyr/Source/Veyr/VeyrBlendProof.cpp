#include "VeyrBlendProof.h"
#include "VeyrKnight.h"
#include "VeyrDragon.h"
#include "VeyrSkeletalPresentation.h"
#include "Camera/CameraActor.h"
#include "Camera/CameraComponent.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "Components/SceneComponent.h"
#include "Components/CapsuleComponent.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "GameFramework/PlayerController.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Materials/MaterialInterface.h"
#include "Dom/JsonObject.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"
#include "Policies/CondensedJsonPrintPolicy.h"
#include "HAL/FileManager.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"

namespace
{
    // Gate thresholds (documented in docs/knight-complete-20261028/blendproof.md).
    constexpr float GSwordLimitCm=2.f;       // sword-to-hand excess / hand-space error
    constexpr float GSlideLimitCm=2.f;       // planted foot world travel per frame
    constexpr float GPlantedMarginCm=2.5f;   // planted = within this height of the idle-stance foot height
    constexpr float GBlinkMinTravelCm=100.f; // blink root carry
    constexpr float GStrafeMinTravelCm=60.f;
    constexpr float GRollMinTravelCm=1.f;    // "roll travel > 0" with a little measurement margin
    constexpr float GPreIdleSeconds=1.3f, GPostIdleSeconds=1.5f;
    constexpr float GDiveEndSeconds=.17f;    // action-time end of the dive (about 5 frames of the 30 fps source)

    TArray<TSharedPtr<FJsonValue>> Vec(const FVector& V)
    {
        return {MakeShared<FJsonValueNumber>(FMath::RoundToFloat(V.X*100.f)/100.f),MakeShared<FJsonValueNumber>(FMath::RoundToFloat(V.Y*100.f)/100.f),
            MakeShared<FJsonValueNumber>(FMath::RoundToFloat(V.Z*100.f)/100.f)};
    }
    float Median(TArray<float> V)
    {
        if(V.IsEmpty())return 0.f;
        V.Sort();return V[V.Num()/2];
    }
    float Planar(const FVector& A,const FVector& B){return FVector::Dist2D(A,B);}
    FString Num(float V){return FString::Printf(TEXT("%.2f"),V);}
}

const FVeyrBlendProof::FDef& FVeyrBlendProof::Def(int32 Index)
{
    // Name, kind, move direction (0 fwd 1 back 2 left 3 right), sprint, two-handed, action seconds, expected travel (for start offset), clip, camera azimuth.
    static const FDef Defs[]={
        {TEXT("StrafeLeft_1H"),EKind::Strafe,2,false,false,2.4f,420.f,TEXT("StrafeLeft"),35.f},
        {TEXT("StrafeRunLeft_1H"),EKind::Strafe,2,true,false,1.6f,700.f,TEXT("StrafeRunLeft"),35.f},
        {TEXT("BlinkLeft_1H"),EKind::Blink,2,false,false,0.f,320.f,TEXT("BlinkLeft"),35.f},
        {TEXT("StrafeRight_2H"),EKind::Strafe,3,false,true,2.4f,420.f,TEXT("StrafeRightTwoHand"),35.f},
        {TEXT("BlinkRight_2H"),EKind::Blink,3,false,true,0.f,320.f,TEXT("BlinkRightTwoHand"),35.f},
        {TEXT("RollAttack_1H"),EKind::RollAttack,0,false,false,0.f,480.f,TEXT("RollAttack"),90.f},
        {TEXT("BackpedalGuard_1H"),EKind::Strafe,1,false,false,2.4f,240.f,TEXT("BackpedalGuard"),90.f},
        {TEXT("StrafeRunRight_1H"),EKind::Strafe,3,true,false,1.6f,700.f,TEXT("StrafeRunRight"),35.f},
        {TEXT("BlinkRight_1H"),EKind::Blink,3,false,false,0.f,320.f,TEXT("BlinkRight"),35.f},
    };
    return Defs[FMath::Clamp(Index,0,UE_ARRAY_COUNT(Defs)-1)];
}
int32 FVeyrBlendProof::DefCount(){return 9;}

void FVeyrBlendProof::Input(const FVector& Dir,bool bSprint) const
{
    if(AVeyrKnight* K=Knight.Get()){K->SetSprintRequested(bSprint);K->SetReplayInput(Dir,false,false,false,false,false,false);}
}
void FVeyrBlendProof::Neutral() const{Input(FVector::ZeroVector,false);}

FVector FVeyrBlendProof::DirVector(const FDef& D) const
{
    switch(D.Dir){case 0:return Fwd0;case 1:return -Fwd0;case 2:return -Right0;default:return Right0;}
}
FVector FVeyrBlendProof::SequenceStart(const FDef& D) const
{
    return Home-DirVector(D)*(.5f*D.ExpectedTravelCm);
}

bool FVeyrBlendProof::Begin(UWorld* InWorld,AVeyrKnight* InKnight,AVeyrDragon* InDragon,const FString& InRunDirectory,bool bProofFloor,FHooks InHooks)
{
    if(bBegan||!InWorld||!InKnight||!InDragon)return false;
    World=InWorld;Knight=InKnight;Dragon=InDragon;Hooks=MoveTemp(InHooks);RunDirectory=InRunDirectory;
    FramesFile=FPaths::Combine(RunDirectory,TEXT("blendproof-frames.jsonl"));
    IFileManager::Get().Delete(*FramesFile,false,true,true);
    Dragon->bProofPassive=true; // boss breathes, never attacks
    Home=Knight->GetFootLocation();FloorZ=Home.Z;
    Fwd0=(Dragon->GetActorLocation()-Home).GetSafeNormal2D();
    if(Fwd0.IsNearlyZero())Fwd0=FVector::ForwardVector;
    Right0=FVector::CrossProduct(FVector::UpVector,Fwd0).GetSafeNormal();
    if(!Knight->bLockedOn)Knight->ToggleLockOn();
    // Fixed chase camera: an engine camera actor that follows the capsule with a world-fixed orientation.
    FActorSpawnParameters Params;Params.SpawnCollisionHandlingOverride=ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
    ACameraActor* Cam=World->SpawnActor<ACameraActor>(Home+FVector(0,0,190),FRotator::ZeroRotator,Params);
    if(Cam)
    {
        Cam->GetCameraComponent()->bConstrainAspectRatio=false;
        Cam->GetCameraComponent()->SetFieldOfView(45.f);
        Camera=Cam;
        if(APlayerController* PC=Cast<APlayerController>(Knight->GetController())){PC->SetViewTarget(Cam);bCameraApplied=true;}
    }
    ApplyCamera(0.f,true);
    if(bProofFloor)BuildChecker();
    bBegan=true;
    UE_LOG(LogTemp,Display,TEXT("VEYR_BLENDPROOF_BEGIN home=(%.0f,%.0f,%.0f) fwd=(%.2f,%.2f) camera=%d proofFloor=%d checkerInstances=%d sequences=%d"),
        Home.X,Home.Y,Home.Z,Fwd0.X,Fwd0.Y,bCameraApplied?1:0,bProofFloorApplied?1:0,CheckerInstances,DefCount());
    return true;
}

void FVeyrBlendProof::BuildChecker()
{
    UWorld* W=World.Get();if(!W)return;
    UStaticMesh* Cube=LoadObject<UStaticMesh>(nullptr,TEXT("/Engine/BasicShapes/Cube.Cube"),nullptr,LOAD_Quiet|LOAD_NoWarn);
    UMaterialInterface* Base=LoadObject<UMaterialInterface>(nullptr,TEXT("/Engine/BasicShapes/BasicShapeMaterial.BasicShapeMaterial"),nullptr,LOAD_Quiet|LOAD_NoWarn);
    if(!Cube||!Base){UE_LOG(LogTemp,Warning,TEXT("VEYR_BLENDPROOF_FLOOR_UNAVAILABLE cube=%d material=%d"),Cube?1:0,Base?1:0);return;}
    FActorSpawnParameters Params;Params.SpawnCollisionHandlingOverride=ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
    AActor* Holder=W->SpawnActor<AActor>(FVector::ZeroVector,FRotator::ZeroRotator,Params);
    if(!Holder)return;
    USceneComponent* Root=NewObject<USceneComponent>(Holder,TEXT("ProofFloorRoot"));
    Holder->SetRootComponent(Root);Root->RegisterComponent();
    UInstancedStaticMeshComponent* ISM=NewObject<UInstancedStaticMeshComponent>(Holder,TEXT("ProofChecker25cm"));
    Holder->AddInstanceComponent(ISM);
    ISM->SetupAttachment(Root);
    ISM->SetMobility(EComponentMobility::Static);
    ISM->SetStaticMesh(Cube);
    UMaterialInstanceDynamic* MID=UMaterialInstanceDynamic::Create(Base,Holder,TEXT("ProofCheckerMaterial"));
    MID->SetVectorParameterValue(TEXT("Color"),FLinearColor(.78f,.78f,.72f));
    MID->SetScalarParameterValue(TEXT("Roughness"),.9f);
    ISM->SetMaterial(0,MID);
    ISM->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    ISM->SetCanEverAffectNavigation(false);
    ISM->CastShadow=false;
    ISM->RegisterComponent();
    // 25 cm cells on the world grid. Light cells are laid; the stone shows through the others.
    constexpr float Cell=25.f;
    constexpr int32 Half=64; // +/-16 m around the knight's start
    const int32 CX=FMath::FloorToInt(Home.X/Cell),CY=FMath::FloorToInt(Home.Y/Cell);
    TArray<FTransform> Transforms;
    for(int32 I=CX-Half;I<CX+Half;++I)for(int32 J=CY-Half;J<CY+Half;++J)
    {
        if(((I+J)&1)!=0)continue;
        Transforms.Add(FTransform(FRotator::ZeroRotator,FVector((I+.5f)*Cell,(J+.5f)*Cell,FloorZ+.6f),FVector(Cell/100.f,Cell/100.f,.004f)));
    }
    ISM->AddInstances(Transforms,false);
    CheckerInstances=Transforms.Num();
    Checker=ISM;bProofFloorApplied=true;
}

void FVeyrBlendProof::ApplyCamera(float Dt,bool bSnap)
{
    ACameraActor* Cam=Camera.Get();AVeyrKnight* K=Knight.Get();
    if(!Cam||!K)return;
    const FDef& D=Def(FMath::Min(SeqIndex,DefCount()-1));
    const FVector Target=K->GetActorLocation();
    if(bSnap||!bFocusValid){Focus=Target;bFocusValid=true;}
    else Focus+=(Target-Focus)*FMath::Clamp(Dt*4.f,0.f,1.f);
    const FVector Look(Focus.X,Focus.Y,FloorZ+100.f);
    const float Az=FMath::DegreesToRadians(D.CameraAzimuthDeg);
    const FVector Dir=Fwd0*FMath::Cos(Az)+Right0*FMath::Sin(Az);
    FVector Location=Look+Dir*580.f;Location.Z=FloorZ+190.f;
    Cam->SetActorLocationAndRotation(Location,(Look-Location).Rotation());
    if(!bCameraApplied)
        if(APlayerController* PC=Cast<APlayerController>(K->GetController())){PC->SetViewTarget(Cam);bCameraApplied=true;}
}

void FVeyrBlendProof::EnterPhase(EPhase P,double Elapsed)
{
    Phase=P;SeqPhaseStart=Elapsed;
}

void FVeyrBlendProof::BeginSequence(double Elapsed)
{
    const FDef& D=Def(SeqIndex);
    Frames.Reset();LastSerial=-1;bPendingMid=false;bMidActionShot=false;
    ActionSub=0;ActionTries=0;bActionIssued=bActionTimedOut=bRollUpgradeIssued=bRollUpgradeSeen=bExpectedActionSeen=false;
    ActionSubStart=Elapsed;LastT=Elapsed;
    ApplyCamera(0.f,true);
    EnterPhase(EPhase::PreIdle,Elapsed);
    Hooks.Shot(FString::Printf(TEXT("bp_%02d_%s_begin"),SeqIndex+1,D.Name));
}

void FVeyrBlendProof::Sample(double Elapsed,float Dt)
{
    AVeyrKnight* K=Knight.Get();if(!K)return;
    UVeyrSkeletalPresentation* P=K->ImportedPresentation;
    FFrame F;
    F.Seq=SeqIndex;F.Phase=Phase==EPhase::PreIdle?0:Phase==EPhase::Action?1:2;F.T=Elapsed;F.Dt=Dt;
    F.Clip=K->RequestedPresentationClip;F.From=K->ProofBlendFromClip;F.Alpha=K->ProofBlendAlpha;F.bBlend=K->bProofBlendActive;F.Serial=K->ProofTransitionSerial;
    F.Action=StaticEnum<EVeyrKnightAction>()->GetNameStringByValue(static_cast<int64>(K->Action));
    F.ActionElapsed=K->GetActionElapsed();F.bHidden=K->bBlinkHidden;
    F.Capsule=K->GetActorLocation();F.FloorZ=K->GetFootLocation().Z;
    FTransform HandT,SwordT,T;
    if(P&&P->bPoseEvaluated)
    {
        bool Ok=true;
        const TCHAR* Targets[2]={TEXT("left_foot"),TEXT("right_foot")};
        const TCHAR* Ankles[2]={TEXT("LeftFoot"),TEXT("RightFoot")};
        for(int32 S=0;S<2;++S)
        {
            if(P->GetBoneTargetWorldTransform(Targets[S],T))F.Toe[S]=T.GetLocation();else Ok=false;
            F.Ankle[S]=P->GetBoneLocation(Ankles[S],EBoneSpaces::WorldSpace);
            F.ToeHeight[S]=F.Toe[S].Z-F.FloorZ;F.AnkleHeight[S]=F.Ankle[S].Z-F.FloorZ;
        }
        F.bFeetValid=Ok;
        if(P->GetBoneTargetWorldTransform(TEXT("weapon_hand"),HandT)){F.Hand=HandT.GetLocation();F.bHandValid=true;}
    }
    if(K->GetProofWeaponWorld(SwordT)){F.Sword=SwordT.GetLocation();F.bSwordValid=true;}
    if(F.bHandValid&&F.bSwordValid)
    {
        F.SwordHandCm=FVector::Dist(F.Sword,F.Hand);
        F.SwordLocal=HandT.GetRotation().UnrotateVector(F.Sword-F.Hand);
    }
    if(!Frames.IsEmpty())
    {
        const FFrame& Prev=Frames.Last();
        F.CapsuleTravel=Planar(F.Capsule,Prev.Capsule);
        for(int32 S=0;S<2;++S){F.ToeTravel[S]=Planar(F.Toe[S],Prev.Toe[S]);F.AnkleTravel[S]=Planar(F.Ankle[S],Prev.Ankle[S]);}
    }
    if(F.Clip==FName(Def(SeqIndex).ExpectedClip))bExpectedActionSeen=true;
    if(F.Action.StartsWith(TEXT("RollAttack")))bRollUpgradeSeen=true;
    // Blend midpoint screenshot: first frame at or past alpha 0.5 of each new pose transition.
    if(F.Serial!=LastSerial){LastSerial=F.Serial;bPendingMid=true;MidSerial=F.Serial;MidFrom=F.From;MidTo=F.Clip;}
    if(bPendingMid&&F.Alpha>=.5f)
    {
        bPendingMid=false;
        Hooks.Shot(FString::Printf(TEXT("bp_%02d_%s_blend_%s_to_%s_a%02d"),SeqIndex+1,Def(SeqIndex).Name,*MidFrom.ToString(),*MidTo.ToString(),FMath::RoundToInt(F.Alpha*100.f)));
    }
    Frames.Add(MoveTemp(F));
}

void FVeyrBlendProof::DriveSetup(double Elapsed,float Dt)
{
    AVeyrKnight* K=Knight.Get();const FDef& D=Def(SeqIndex);
    if(SeqSetupStart<0)SeqSetupStart=Elapsed;
    if(!K->bLockedOn)K->ToggleLockOn();
    const bool Ready=K->Action==EVeyrKnightAction::Ready&&K->IsGrounded();
    if(Elapsed-SeqSetupStart>30.0){bSetupTimedOut=true;SetupStable=1.f;}
    if(!Ready){Neutral();SetupStable=0.f;return;}
    if(K->IsTwoHanded()!=D.bTwo)
    {
        Neutral();SetupStable=0.f;
        if(!K->IsChangingGrip())K->ToggleGrip();
        return;
    }
    if(K->Stamina<85.f&&!bSetupTimedOut){Neutral();SetupStable=0.f;return;}
    const FVector Start=SequenceStart(D);
    const FVector Feet=K->GetFootLocation();
    const FVector Delta=FVector(Start.X-Feet.X,Start.Y-Feet.Y,0.f);
    if(Delta.Size2D()>70.f&&!bSetupTimedOut){Input(Delta.GetSafeNormal2D(),false);SetupStable=0.f;return;}
    Neutral();
    if(K->GetPlanarSpeed()<4.f)SetupStable+=Dt;else SetupStable=0.f;
    if(SetupStable>=.9f)BeginSequence(Elapsed);
}

void FVeyrBlendProof::DriveAction(double Elapsed,float Dt)
{
    AVeyrKnight* K=Knight.Get();const FDef& D=Def(SeqIndex);
    const double InAction=Elapsed-SeqPhaseStart;
    if(!bMidActionShot&&InAction>=.9)
    {
        bMidActionShot=true;
        Hooks.Shot(FString::Printf(TEXT("bp_%02d_%s_cycle"),SeqIndex+1,D.Name));
    }
    if(D.Kind==EKind::Strafe)
    {
        if(InAction<D.ActionSeconds){Input(DirVector(D),D.bSprint);return;}
        Neutral();EnterPhase(EPhase::PostIdle,Elapsed);return;
    }
    if(D.Kind==EKind::Blink)
    {
        const FVector Side=DirVector(D);
        if(ActionSub==0)
        {
            if(K->Action!=EVeyrKnightAction::Ready||K->Stamina<30.f){Neutral();if(Elapsed-ActionSubStart>6.0){bActionTimedOut=true;Neutral();EnterPhase(EPhase::PostIdle,Elapsed);}return;}
            Input(Side,false);ActionSub=1;ActionSubStart=Elapsed;return;
        }
        if(ActionSub==1){K->TryDirectionalBlink();Neutral();ActionSub=2;ActionSubStart=Elapsed;return;}
        Neutral();
        const bool bBlinkNow=K->Action==EVeyrKnightAction::BlinkLeft||K->Action==EVeyrKnightAction::BlinkRight;
        if(bBlinkNow){bActionIssued=true;return;}
        if(bActionIssued&&K->Action==EVeyrKnightAction::Ready){EnterPhase(EPhase::PostIdle,Elapsed);return;}
        if(!bActionIssued&&Elapsed-ActionSubStart>.8)
        {
            if(++ActionTries>=3){bActionTimedOut=true;EnterPhase(EPhase::PostIdle,Elapsed);return;}
            ActionSub=0;ActionSubStart=Elapsed;
        }
        return;
    }
    // Roll attack: roll input, then the primary attack inside the roll (upgrades it in place).
    if(ActionSub==0)
    {
        if(K->Action!=EVeyrKnightAction::Ready||K->Stamina<45.f){Neutral();if(Elapsed-ActionSubStart>6.0){bActionTimedOut=true;EnterPhase(EPhase::PostIdle,Elapsed);}return;}
        K->SetSprintRequested(false);K->SetReplayInput(DirVector(D),false,false,true,false,false,false);
        ActionSub=1;ActionSubStart=Elapsed;return;
    }
    Neutral();
    if(K->Action==EVeyrKnightAction::Roll&&!bRollUpgradeIssued&&K->GetActionElapsed()>=.20f)
    {
        K->PressPrimaryAttack();K->ReleasePrimaryAttack();bRollUpgradeIssued=true;return;
    }
    if(K->Action==EVeyrKnightAction::Roll||K->Action==EVeyrKnightAction::RollAttack){bActionIssued=true;return;}
    if(bActionIssued&&K->Action==EVeyrKnightAction::Ready){EnterPhase(EPhase::PostIdle,Elapsed);return;}
    if(!bActionIssued&&Elapsed-ActionSubStart>1.0){bActionTimedOut=true;EnterPhase(EPhase::PostIdle,Elapsed);}
}

void FVeyrBlendProof::Drive(double Elapsed,float Dt)
{
    AVeyrKnight* K=Knight.Get();AVeyrDragon* B=Dragon.Get();
    if(!bBegan||!K||!B){return;}
    B->bProofPassive=true;
    ApplyCamera(Dt,false);
    if(bDone){Neutral();return;}
    if(SeqIndex>=DefCount()){bDone=true;Neutral();return;}
    if(Phase!=EPhase::Setup)Sample(Elapsed,Dt);
    switch(Phase)
    {
    case EPhase::Setup:DriveSetup(Elapsed,Dt);break;
    case EPhase::PreIdle:
        Neutral();
        if(K->Action==EVeyrKnightAction::Ready&&Elapsed-SeqPhaseStart>=GPreIdleSeconds){EnterPhase(EPhase::Action,Elapsed);ActionSubStart=Elapsed;}
        break;
    case EPhase::Action:DriveAction(Elapsed,Dt);break;
    case EPhase::PostIdle:
        Neutral();
        if(K->Action==EVeyrKnightAction::Ready&&Elapsed-SeqPhaseStart>=GPostIdleSeconds){FinalizeSequence(Elapsed);}
        else if(Elapsed-SeqPhaseStart>12.0)FinalizeSequence(Elapsed);
        break;
    }
}

void FVeyrBlendProof::FinalizeSequence(double Elapsed)
{
    const FDef& D=Def(SeqIndex);
    const int32 N=Frames.Num();
    FSequenceResult R;R.Index=SeqIndex+1;R.Name=D.Name;R.GameStart=N?Frames[0].T:Elapsed;R.GameEnd=Elapsed;R.Frames=N;
    R.bCompleted=!bSetupTimedOut&&!bActionTimedOut&&N>10;
    // 1. Idle-stance foot heights (planted reference) from the first idle second, after a short settle.
    float IdleToe[2]={0,0},IdleAnk[2]={0,0};
    for(int32 S=0;S<2;++S)
    {
        TArray<float> T,A;
        for(const FFrame& F:Frames)if(F.Phase==0&&F.bFeetValid&&F.T-R.GameStart>=.3){T.Add(F.ToeHeight[S]);A.Add(F.AnkleHeight[S]);}
        IdleToe[S]=Median(T);IdleAnk[S]=Median(A);
    }
    // 2. Planted flags, per-bone slide, blink exemption (frames touching the hidden window).
    float SlideMax=0.f,SlideMaxPerSecond=0.f,SlideToeMax=0.f,SlideAnkleMax=0.f;
    float SlidePhase[3]={0,0,0};
    int32 SlideFrames=0,PlantedPairs=0;
    FString SlideWorst;
    float RollEnd=.78f,StrikeEnd=1.23f;
    if(D.Kind==EKind::RollAttack&&Knight.IsValid())Knight->GetProofRollAttackTimes(RollEnd,StrikeEnd);
    float RollPhaseSlide[4]={0,0,0,0}; // dive, roll, slash, exit
    auto RollPhase=[&](const FFrame& F){return F.ActionElapsed<GDiveEndSeconds?0:F.ActionElapsed<RollEnd?1:F.ActionElapsed<StrikeEnd?2:3;};
    for(int32 I=0;I<N;++I)
    {
        FFrame& F=Frames[I];
        for(int32 S=0;S<2;++S)
        {
            F.bToePlanted[S]=F.bFeetValid&&F.ToeHeight[S]<=IdleToe[S]+GPlantedMarginCm;
            F.bAnklePlanted[S]=F.bFeetValid&&F.AnkleHeight[S]<=IdleAnk[S]+GPlantedMarginCm;
        }
        if(I==0)continue;
        const FFrame& P=Frames[I-1];
        if(F.bHidden||P.bHidden)continue;
        for(int32 S=0;S<2;++S)
        {
            for(int32 B=0;B<2;++B)
            {
                const bool Planted=B==0?(F.bToePlanted[S]&&P.bToePlanted[S]):(F.bAnklePlanted[S]&&P.bAnklePlanted[S]);
                if(!Planted)continue;
                const float Tr=B==0?F.ToeTravel[S]:F.AnkleTravel[S];
                ++PlantedPairs;
                if(Tr>SlideMax){SlideMax=Tr;SlideWorst=FString::Printf(TEXT("t=%.2f %s %s %s clip=%s"),F.T,S==0?TEXT("L"):TEXT("R"),B==0?TEXT("toe"):TEXT("ankle"),*F.Action,*F.Clip.ToString());}
                if(B==0)SlideToeMax=FMath::Max(SlideToeMax,Tr);else SlideAnkleMax=FMath::Max(SlideAnkleMax,Tr);
                SlideMaxPerSecond=FMath::Max(SlideMaxPerSecond,F.Dt>.001f?Tr/F.Dt:0.f);
                SlidePhase[F.Phase]=FMath::Max(SlidePhase[F.Phase],Tr);
                if(Tr>GSlideLimitCm)++SlideFrames;
                if(F.Action.StartsWith(TEXT("Roll")))RollPhaseSlide[RollPhase(F)]=FMath::Max(RollPhaseSlide[RollPhase(F)],Tr);
            }
        }
    }
    // 3. Sword to hand. Hand-to-grip is about 15 cm in every steady pose, so the gate measures what the blend adds:
    //    scalar excess outside the endpoint range, and the hand-space position error against the expected interpolation.
    float SwordRawMin=1e9f,SwordRawMax=0.f,SwordExcessMax=0.f,SwordLocalErrMax=0.f,SwordBlendExcessMax=0.f,SwordSteadyExcessMax=0.f;
    int32 BlendFrames=0,BlendSegments=0;
    TMap<FName,TArray<float>> SteadyBy;
    for(const FFrame& F:Frames)if(!F.bBlend&&F.bSwordValid&&F.bHandValid)SteadyBy.FindOrAdd(F.Clip).Add(F.SwordHandCm);
    TMap<FName,float> SteadyRef;for(auto& Pair:SteadyBy)SteadyRef.Add(Pair.Key,Median(Pair.Value));
    for(int32 I=0;I<N;)
    {
        FFrame& F=Frames[I];
        if(!(F.bBlend&&F.bSwordValid&&F.bHandValid)){
            if(F.bSwordValid&&F.bHandValid)
            {
                SwordRawMin=FMath::Min(SwordRawMin,F.SwordHandCm);SwordRawMax=FMath::Max(SwordRawMax,F.SwordHandCm);
                const float* Ref=SteadyRef.Find(F.Clip);
                F.SwordExcessCm=Ref?FMath::Abs(F.SwordHandCm-*Ref):0.f;
                SwordSteadyExcessMax=FMath::Max(SwordSteadyExcessMax,F.SwordExcessCm);
            }
            ++I;continue;
        }
        int32 E=I;while(E<N&&Frames[E].bBlend)++E; // [I,E) blend frames
        // Endpoints are the nearest frames with a visible sword (the sword is hidden inside a blink's vanish window).
        int32 BI=FMath::Max(0,I-1);while(BI>0&&!(Frames[BI].bSwordValid&&Frames[BI].bHandValid))--BI;
        int32 AI=FMath::Min(N-1,E);while(AI<N-1&&!(Frames[AI].bSwordValid&&Frames[AI].bHandValid))++AI;
        const FFrame& Before=Frames[BI];
        const FFrame& After=Frames[AI];
        const float D0=Before.SwordHandCm,D1=After.SwordHandCm;
        ++BlendSegments;
        for(int32 J=I;J<E;++J)
        {
            FFrame& G=Frames[J];++BlendFrames;
            if(!(G.bSwordValid&&G.bHandValid))continue;
            SwordRawMin=FMath::Min(SwordRawMin,G.SwordHandCm);SwordRawMax=FMath::Max(SwordRawMax,G.SwordHandCm);
            G.SwordExcessCm=FMath::Max(0.f,FMath::Max(FMath::Min(D0,D1)-G.SwordHandCm,G.SwordHandCm-FMath::Max(D0,D1)));
            const FVector Expected=FMath::Lerp(Before.SwordLocal,After.SwordLocal,G.Alpha);
            G.SwordLocalErrCm=FVector::Dist(G.SwordLocal,Expected);
            SwordBlendExcessMax=FMath::Max(SwordBlendExcessMax,G.SwordExcessCm);
            SwordLocalErrMax=FMath::Max(SwordLocalErrMax,G.SwordLocalErrCm);
        }
        I=E;
    }
    SwordExcessMax=FMath::Max(SwordBlendExcessMax,SwordSteadyExcessMax);
    if(SwordRawMin>1e8f)SwordRawMin=0.f;
    // 4. Capsule travel.
    float CapsulePath=0.f;
    for(const FFrame& F:Frames)CapsulePath+=F.CapsuleTravel;
    const float CapsuleNet=N>1?Planar(Frames[0].Capsule,Frames.Last().Capsule):0.f;
    float HiddenCarry=0.f;int32 HiddenFrames=0;
    for(int32 I=1;I<N;++I){if(Frames[I].bHidden||Frames[I-1].bHidden)HiddenCarry+=Frames[I].CapsuleTravel;if(Frames[I].bHidden)++HiddenFrames;}
    float MaxFrameDt=0.f;for(const FFrame& F:Frames)MaxFrameDt=FMath::Max(MaxFrameDt,F.Dt);
    int32 ClipFrames=0;for(const FFrame& F:Frames)if(F.Clip==FName(D.ExpectedClip))++ClipFrames;
    // Roll attack: capsule travel by phase (dive, roll, slash, exit).
    float RollPath[4]={0,0,0,0},RollNet[4]={0,0,0,0};
    FVector PhaseFirst[4]={FVector::ZeroVector,FVector::ZeroVector,FVector::ZeroVector,FVector::ZeroVector},PhaseLast[4]={FVector::ZeroVector,FVector::ZeroVector,FVector::ZeroVector,FVector::ZeroVector};bool PhaseSeen[4]={false,false,false,false};
    float RollTravelNet=0.f,RollTravelPath=0.f,RollTotalNet=0.f;
    if(D.Kind==EKind::RollAttack)
    {
        int32 FirstRoll=-1,LastRoll=-1;
        for(int32 I=0;I<N;++I)if(Frames[I].Action.StartsWith(TEXT("Roll"))){if(FirstRoll<0)FirstRoll=I;LastRoll=I;}
        if(FirstRoll>=0)
        {
            const int32 Anchor=FMath::Max(0,FirstRoll-1);
            for(int32 I=FirstRoll;I<=LastRoll;++I)
            {
                const int32 Ph=RollPhase(Frames[I]);
                RollPath[Ph]+=Frames[I].CapsuleTravel;
                if(!PhaseSeen[Ph]){PhaseSeen[Ph]=true;PhaseFirst[Ph]=Frames[I==FirstRoll?Anchor:I-1].Capsule;}
                PhaseLast[Ph]=Frames[I].Capsule;
            }
            for(int32 Ph=0;Ph<4;++Ph)if(PhaseSeen[Ph])RollNet[Ph]=Planar(PhaseFirst[Ph],PhaseLast[Ph]);
            RollTravelNet=RollNet[0]+RollNet[1];RollTravelPath=RollPath[0]+RollPath[1];
            RollTotalNet=Planar(Frames[Anchor].Capsule,Frames[LastRoll].Capsule);
        }
    }
    // 5. Gate.
    TArray<FString> Fail;
    if(!R.bCompleted)Fail.Add(TEXT("sequence_incomplete"));
    if(ClipFrames<2)Fail.Add(FString::Printf(TEXT("expected_clip_%s_seen_%d_frames"),D.ExpectedClip,ClipFrames));
    if(SwordExcessMax>GSwordLimitCm)Fail.Add(FString::Printf(TEXT("sword_excess_%.2fcm"),SwordExcessMax));
    if(SwordLocalErrMax>GSwordLimitCm)Fail.Add(FString::Printf(TEXT("sword_hand_space_error_%.2fcm"),SwordLocalErrMax));
    if(SlideMax>GSlideLimitCm)Fail.Add(FString::Printf(TEXT("planted_foot_slide_%.2fcm_per_frame"),SlideMax));
    if(D.Kind==EKind::Blink&&CapsuleNet<GBlinkMinTravelCm)Fail.Add(FString::Printf(TEXT("blink_root_carry_%.0fcm"),CapsuleNet));
    if(D.Kind==EKind::Strafe&&CapsuleNet<GStrafeMinTravelCm)Fail.Add(FString::Printf(TEXT("locomotion_travel_%.0fcm"),CapsuleNet));
    if(D.Kind==EKind::RollAttack)
    {
        if(!bRollUpgradeSeen)Fail.Add(TEXT("roll_attack_never_started"));
        if(RollTravelNet<=GRollMinTravelCm)Fail.Add(FString::Printf(TEXT("roll_travel_%.1fcm"),RollTravelNet));
    }
    R.bPassed=Fail.IsEmpty();
    R.Reason=R.bPassed?TEXT("ok"):FString::Join(Fail,TEXT(","));
    if(R.bPassed)++PassedCount;
    // Result JSON.
    TSharedPtr<FJsonObject> M=MakeShared<FJsonObject>();
    M->SetNumberField(TEXT("index"),R.Index);M->SetStringField(TEXT("name"),R.Name);M->SetStringField(TEXT("expectedClip"),D.ExpectedClip);
    M->SetBoolField(TEXT("passed"),R.bPassed);M->SetStringField(TEXT("reason"),R.Reason);M->SetBoolField(TEXT("completed"),R.bCompleted);
    M->SetNumberField(TEXT("gameStartSeconds"),R.GameStart);M->SetNumberField(TEXT("gameEndSeconds"),R.GameEnd);M->SetNumberField(TEXT("frames"),N);
    M->SetNumberField(TEXT("expectedClipFrames"),ClipFrames);M->SetNumberField(TEXT("maxFrameSeconds"),MaxFrameDt);
    M->SetBoolField(TEXT("setupTimedOut"),bSetupTimedOut);M->SetBoolField(TEXT("actionTimedOut"),bActionTimedOut);
    TSharedPtr<FJsonObject> Sw=MakeShared<FJsonObject>();
    Sw->SetNumberField(TEXT("maxExcessCm"),SwordExcessMax);Sw->SetNumberField(TEXT("maxBlendExcessCm"),SwordBlendExcessMax);Sw->SetNumberField(TEXT("maxSteadyExcessCm"),SwordSteadyExcessMax);
    Sw->SetNumberField(TEXT("maxHandSpaceErrorCm"),SwordLocalErrMax);Sw->SetNumberField(TEXT("rawHandToGripMinCm"),SwordRawMin);Sw->SetNumberField(TEXT("rawHandToGripMaxCm"),SwordRawMax);
    Sw->SetNumberField(TEXT("blendSegments"),BlendSegments);Sw->SetNumberField(TEXT("blendFrames"),BlendFrames);Sw->SetNumberField(TEXT("limitCm"),GSwordLimitCm);
    M->SetObjectField(TEXT("sword"),Sw);
    TSharedPtr<FJsonObject> Ft=MakeShared<FJsonObject>();
    Ft->SetNumberField(TEXT("maxPlantedSlideCmPerFrame"),SlideMax);Ft->SetNumberField(TEXT("maxPlantedSlideCmPerSecond"),SlideMaxPerSecond);
    Ft->SetNumberField(TEXT("maxToeSlideCmPerFrame"),SlideToeMax);Ft->SetNumberField(TEXT("maxAnkleSlideCmPerFrame"),SlideAnkleMax);
    Ft->SetNumberField(TEXT("maxSlidePreIdle"),SlidePhase[0]);Ft->SetNumberField(TEXT("maxSlideAction"),SlidePhase[1]);Ft->SetNumberField(TEXT("maxSlidePostIdle"),SlidePhase[2]);
    Ft->SetNumberField(TEXT("framesOverLimit"),SlideFrames);Ft->SetNumberField(TEXT("plantedBoneFramePairs"),PlantedPairs);Ft->SetStringField(TEXT("worst"),SlideWorst);
    Ft->SetNumberField(TEXT("idleToeHeightCm"),(IdleToe[0]+IdleToe[1])*.5f);Ft->SetNumberField(TEXT("idleAnkleHeightCm"),(IdleAnk[0]+IdleAnk[1])*.5f);
    Ft->SetNumberField(TEXT("plantedMarginCm"),GPlantedMarginCm);Ft->SetNumberField(TEXT("limitCmPerFrame"),GSlideLimitCm);
    Ft->SetStringField(TEXT("exemption"),TEXT("frame pairs touching the blink hidden window [0.18,0.34) s of action time"));
    M->SetObjectField(TEXT("feet"),Ft);
    TSharedPtr<FJsonObject> Cp=MakeShared<FJsonObject>();
    Cp->SetNumberField(TEXT("netTravelCm"),CapsuleNet);Cp->SetNumberField(TEXT("pathTravelCm"),CapsulePath);
    Cp->SetNumberField(TEXT("travelAcrossHiddenWindowCm"),HiddenCarry);Cp->SetNumberField(TEXT("hiddenFrames"),HiddenFrames);
    M->SetObjectField(TEXT("capsule"),Cp);
    if(D.Kind==EKind::RollAttack)
    {
        TSharedPtr<FJsonObject> Ro=MakeShared<FJsonObject>();
        const TCHAR* Names[4]={TEXT("dive"),TEXT("roll"),TEXT("slash"),TEXT("exit")};
        Ro->SetBoolField(TEXT("rollAttackStarted"),bRollUpgradeSeen);Ro->SetNumberField(TEXT("rollPrefixEndSeconds"),RollEnd);Ro->SetNumberField(TEXT("strikeEndSeconds"),StrikeEnd);
        Ro->SetNumberField(TEXT("diveAndRollNetTravelCm"),RollTravelNet);Ro->SetNumberField(TEXT("diveAndRollPathTravelCm"),RollTravelPath);Ro->SetNumberField(TEXT("totalNetTravelCm"),RollTotalNet);
        for(int32 Ph=0;Ph<4;++Ph)
        {
            TSharedPtr<FJsonObject> P=MakeShared<FJsonObject>();
            P->SetNumberField(TEXT("netTravelCm"),RollNet[Ph]);P->SetNumberField(TEXT("pathTravelCm"),RollPath[Ph]);P->SetNumberField(TEXT("maxPlantedFootSlideCmPerFrame"),RollPhaseSlide[Ph]);
            Ro->SetObjectField(Names[Ph],P);
        }
        M->SetObjectField(TEXT("roll"),Ro);
    }
    R.Metrics=M;
    SequenceJson.Add(MakeShared<FJsonValueObject>(M));
    // Per-frame evidence (JSON lines beside the evidence file).
    FString Lines;
    for(const FFrame& F:Frames)
    {
        TSharedRef<FJsonObject> O=MakeShared<FJsonObject>();
        O->SetNumberField(TEXT("seq"),R.Index);O->SetStringField(TEXT("sequence"),R.Name);
        O->SetStringField(TEXT("phase"),F.Phase==0?TEXT("pre_idle"):F.Phase==1?TEXT("action"):TEXT("post_idle"));
        O->SetNumberField(TEXT("t"),F.T);O->SetNumberField(TEXT("dt"),F.Dt);
        O->SetStringField(TEXT("clip"),F.Clip.ToString());O->SetStringField(TEXT("blendFrom"),F.From.ToString());O->SetNumberField(TEXT("blendAlpha"),F.Alpha);
        O->SetBoolField(TEXT("blending"),F.bBlend);O->SetNumberField(TEXT("transition"),F.Serial);O->SetStringField(TEXT("action"),F.Action);O->SetNumberField(TEXT("actionElapsed"),F.ActionElapsed);
        O->SetBoolField(TEXT("blinkHidden"),F.bHidden);
        O->SetArrayField(TEXT("capsule"),Vec(F.Capsule));O->SetNumberField(TEXT("capsuleTravelCm"),F.CapsuleTravel);O->SetNumberField(TEXT("floorZ"),F.FloorZ);
        O->SetArrayField(TEXT("toeL"),Vec(F.Toe[0]));O->SetArrayField(TEXT("toeR"),Vec(F.Toe[1]));
        O->SetArrayField(TEXT("ankleL"),Vec(F.Ankle[0]));O->SetArrayField(TEXT("ankleR"),Vec(F.Ankle[1]));
        O->SetArrayField(TEXT("toeHeightCm"),{MakeShared<FJsonValueNumber>(F.ToeHeight[0]),MakeShared<FJsonValueNumber>(F.ToeHeight[1])});
        O->SetArrayField(TEXT("ankleHeightCm"),{MakeShared<FJsonValueNumber>(F.AnkleHeight[0]),MakeShared<FJsonValueNumber>(F.AnkleHeight[1])});
        O->SetArrayField(TEXT("toePlanted"),{MakeShared<FJsonValueBoolean>(F.bToePlanted[0]),MakeShared<FJsonValueBoolean>(F.bToePlanted[1])});
        O->SetArrayField(TEXT("anklePlanted"),{MakeShared<FJsonValueBoolean>(F.bAnklePlanted[0]),MakeShared<FJsonValueBoolean>(F.bAnklePlanted[1])});
        O->SetArrayField(TEXT("toeTravelCm"),{MakeShared<FJsonValueNumber>(F.ToeTravel[0]),MakeShared<FJsonValueNumber>(F.ToeTravel[1])});
        O->SetArrayField(TEXT("ankleTravelCm"),{MakeShared<FJsonValueNumber>(F.AnkleTravel[0]),MakeShared<FJsonValueNumber>(F.AnkleTravel[1])});
        O->SetArrayField(TEXT("sword"),Vec(F.Sword));O->SetArrayField(TEXT("hand"),Vec(F.Hand));O->SetArrayField(TEXT("swordInHandSpace"),Vec(F.SwordLocal));
        O->SetNumberField(TEXT("swordToHandCm"),F.SwordHandCm);O->SetNumberField(TEXT("swordExcessCm"),F.SwordExcessCm);O->SetNumberField(TEXT("swordHandSpaceErrorCm"),F.SwordLocalErrCm);
        FString Line;
        const TSharedRef<TJsonWriter<TCHAR,TCondensedJsonPrintPolicy<TCHAR>>> W=TJsonWriterFactory<TCHAR,TCondensedJsonPrintPolicy<TCHAR>>::Create(&Line);
        if(FJsonSerializer::Serialize(O,W))Lines+=Line+TEXT("\n");
    }
    FFileHelper::SaveStringToFile(Lines,*FramesFile,FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM,&IFileManager::Get(),FILEWRITE_Append);
    // Gate line.
    FString Extra;
    if(D.Kind==EKind::Blink)Extra=FString::Printf(TEXT(" blinkCarryCm=%s hiddenWindowCarryCm=%s"),*Num(CapsuleNet),*Num(HiddenCarry));
    else if(D.Kind==EKind::RollAttack)Extra=FString::Printf(TEXT(" rollTravelCm=%s diveCm=%s rollCm=%s slashCm=%s exitCm=%s rollSlide=%s exitSlide=%s"),
        *Num(RollTravelNet),*Num(RollNet[0]),*Num(RollNet[1]),*Num(RollNet[2]),*Num(RollNet[3]),*Num(FMath::Max(RollPhaseSlide[0],RollPhaseSlide[1])),*Num(RollPhaseSlide[3]));
    else Extra=FString::Printf(TEXT(" travelCm=%s"),*Num(CapsuleNet));
    UE_LOG(LogTemp,Display,TEXT("VEYR_GATE blendproof seq=%d name=%s %s swordExcessMaxCm=%s swordHandSpaceErrMaxCm=%s swordRawHandToGripCm=%s..%s footSlideMaxCmPerFrame=%s footSlideMaxCmPerSecond=%s%s frames=%d maxFrameSeconds=%s reason=%s"),
        R.Index,*R.Name,R.bPassed?TEXT("PASS"):TEXT("FAIL"),*Num(SwordExcessMax),*Num(SwordLocalErrMax),*Num(SwordRawMin),*Num(SwordRawMax),*Num(SlideMax),*Num(SlideMaxPerSecond),*Extra,N,*Num(MaxFrameDt),*R.Reason);
    Results.Add(R);
    Hooks.Shot(FString::Printf(TEXT("bp_%02d_%s_end_%s"),R.Index,D.Name,R.bPassed?TEXT("pass"):TEXT("fail")));
    Frames.Reset();
    ++SeqIndex;SeqSetupStart=-1;SetupStable=0.f;bSetupTimedOut=false;
    EnterPhase(EPhase::Setup,Elapsed);
    if(SeqIndex>=DefCount())
    {
        bDone=true;Neutral();
        UE_LOG(LogTemp,Display,TEXT("VEYR_GATE blendproof summary passed=%d/%d result=%s"),PassedCount,DefCount(),PassedCount==DefCount()?TEXT("PASS"):TEXT("FAIL"));
        Hooks.Finish(PassedCount==DefCount(),FString::Printf(TEXT("blendproof: %d/%d sequences passed their gates; see VEYR_GATE lines and blendProof in evidence.json"),PassedCount,DefCount()));
    }
}

TSharedPtr<FJsonObject> FVeyrBlendProof::CurrentState() const
{
    TSharedPtr<FJsonObject> O=MakeShared<FJsonObject>();
    O->SetNumberField(TEXT("sequenceIndex"),SeqIndex+1);
    if(SeqIndex<DefCount())O->SetStringField(TEXT("sequence"),Def(SeqIndex).Name);
    O->SetStringField(TEXT("phase"),Phase==EPhase::Setup?TEXT("setup"):Phase==EPhase::PreIdle?TEXT("pre_idle"):Phase==EPhase::Action?TEXT("action"):TEXT("post_idle"));
    if(const AVeyrKnight* K=Knight.Get())
    {
        O->SetStringField(TEXT("clip"),K->RequestedPresentationClip.ToString());O->SetStringField(TEXT("blendFrom"),K->ProofBlendFromClip.ToString());
        O->SetNumberField(TEXT("blendAlpha"),K->ProofBlendAlpha);O->SetBoolField(TEXT("blending"),K->bProofBlendActive);O->SetNumberField(TEXT("transition"),K->ProofTransitionSerial);
    }
    return O;
}

TSharedPtr<FJsonObject> FVeyrBlendProof::Evidence() const
{
    TSharedPtr<FJsonObject> O=MakeShared<FJsonObject>();
    O->SetBoolField(TEXT("done"),bDone);O->SetNumberField(TEXT("sequencesPassed"),PassedCount);O->SetNumberField(TEXT("sequencesTotal"),DefCount());
    O->SetBoolField(TEXT("allPassed"),bDone&&PassedCount==DefCount());
    O->SetStringField(TEXT("framesFile"),TEXT("blendproof-frames.jsonl"));
    TSharedPtr<FJsonObject> Setup=MakeShared<FJsonObject>();
    Setup->SetBoolField(TEXT("bossPassive"),Dragon.IsValid()&&Dragon->bProofPassive);Setup->SetBoolField(TEXT("proofCameraApplied"),bCameraApplied);
    Setup->SetBoolField(TEXT("proofFloorApplied"),bProofFloorApplied);Setup->SetNumberField(TEXT("checkerCellCm"),25);Setup->SetNumberField(TEXT("checkerInstances"),CheckerInstances);
    Setup->SetArrayField(TEXT("home"),Vec(Home));Setup->SetArrayField(TEXT("forwardToBoss"),Vec(Fwd0));Setup->SetNumberField(TEXT("cameraDistanceCm"),580);Setup->SetNumberField(TEXT("cameraFovDegrees"),45);
    Setup->SetBoolField(TEXT("weaponGripLockEnabled"),Knight.IsValid()&&Knight->bWeaponGripLockEnabled);
    O->SetObjectField(TEXT("setup"),Setup);
    TSharedPtr<FJsonObject> G=MakeShared<FJsonObject>();
    G->SetNumberField(TEXT("swordExcessAndHandSpaceErrorLimitCm"),GSwordLimitCm);G->SetNumberField(TEXT("plantedFootSlideLimitCmPerFrame"),GSlideLimitCm);
    G->SetNumberField(TEXT("plantedHeightMarginCm"),GPlantedMarginCm);G->SetNumberField(TEXT("blinkMinRootCarryCm"),GBlinkMinTravelCm);
    G->SetNumberField(TEXT("locomotionMinTravelCm"),GStrafeMinTravelCm);G->SetNumberField(TEXT("rollMinTravelCm"),GRollMinTravelCm);
    O->SetObjectField(TEXT("gateThresholds"),G);
    O->SetArrayField(TEXT("sequences"),SequenceJson);
    return O;
}
