// Data-driven move layer of AVeyrDragon: hurt capsules from boxes.json riding the imported
// skeleton, attack windows from moves.json, console gate lines. Additive to VeyrDragon.cpp:
// with no data the dragon is exactly the hard-coded encounter.

#include "VeyrDragon.h"
#include "VeyrKnight.h"
#include "VeyrMoveData.h"
#include "VeyrSkeletalPresentation.h"
#include "VeyrVisualDefinition.h"
#include "AnimationRuntime.h"
#include "Components/CapsuleComponent.h"
#include "DrawDebugHelpers.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "HAL/IConsoleManager.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"

namespace
{
    /** Lowercase letters and digits only: "tripo::Spine_0" and "tripo__Spine_0" compare equal. */
    FString VeyrMoveDataKey(const FString& In)
    {
        FString Out;Out.Reserve(In.Len());
        for(TCHAR C:In)if(FChar::IsAlnum(C))Out.AppendChar(FChar::ToLower(C));
        return Out;
    }

    void VeyrMoveDataLog(const TArray<FString>& Lines)
    {
        for(const FString& Line:Lines)UE_LOG(LogVeyrMoveData,Display,TEXT("%s"),*Line);
    }

    void VeyrMoveDataDumpCommand(const TArray<FString>& Args, UWorld* World)
    {
        TArray<FString> Lines;int32 Dragons=0;
        if(World)
            for(TActorIterator<AVeyrDragon> It(World);It;++It){It->DescribeMoveData(Lines);++Dragons;}
        if(Dragons==0)
        {
            FBossMoveData Data;
            Data.Load(FBossMoveData::ResolveDirectory());
            Data.Describe(Lines);
            Lines.Add(TEXT("VEYR_MOVEDATA_RUNTIME no AVeyrDragon in this world; file check only"));
        }
        VeyrMoveDataLog(Lines);
    }

    void VeyrMoveDataPlayCommand(const TArray<FString>& Args, UWorld* World)
    {
        if(Args.IsEmpty()){UE_LOG(LogVeyrMoveData,Display,TEXT("usage: veyr.MoveData.Play <move>|none"));return;}
        const FName Move=Args[0].Equals(TEXT("none"),ESearchCase::IgnoreCase)?NAME_None:FName(*Args[0]);
        int32 Dragons=0;
        if(World)
            for(TActorIterator<AVeyrDragon> It(World);It;++It)
            {
                ++Dragons;
                UE_LOG(LogVeyrMoveData,Display,TEXT("VEYR_MOVEDATA_PLAY_REQUEST %s -> %s"),*Args[0],It->PlayDataMove(Move)?TEXT("started"):TEXT("refused"));
            }
        if(Dragons==0)UE_LOG(LogVeyrMoveData,Display,TEXT("veyr.MoveData.Play: no AVeyrDragon in this world"));
    }

    void VeyrMoveDataReloadCommand(const TArray<FString>& Args, UWorld* World)
    {
        int32 Dragons=0;
        if(World)
            for(TActorIterator<AVeyrDragon> It(World);It;++It)
            {
                ++Dragons;
                UE_LOG(LogVeyrMoveData,Display,TEXT("VEYR_MOVEDATA_RELOAD %s"),It->ReloadMoveData()?TEXT("loaded"):TEXT("failed; hard-coded behaviour kept"));
            }
        if(Dragons==0)UE_LOG(LogVeyrMoveData,Display,TEXT("veyr.MoveData.Reload: no AVeyrDragon in this world"));
    }

    FAutoConsoleCommandWithWorldAndArgs GVeyrMoveDataDump(TEXT("veyr.MoveData.Dump"),
        TEXT("Log the loaded dragon moves, attack windows, hurt parts and their runtime binding (the move-data gate line)."),
        FConsoleCommandWithWorldAndArgsDelegate::CreateStatic(&VeyrMoveDataDumpCommand));
    FAutoConsoleCommandWithWorldAndArgs GVeyrMoveDataPlay(TEXT("veyr.MoveData.Play"),
        TEXT("veyr.MoveData.Play <move>|none: play a moves.json move from Idle (lab). Enum-mapped names start the hard-coded attack."),
        FConsoleCommandWithWorldAndArgsDelegate::CreateStatic(&VeyrMoveDataPlayCommand));
    FAutoConsoleCommandWithWorldAndArgs GVeyrMoveDataReload(TEXT("veyr.MoveData.Reload"),
        TEXT("Read Data/dragon/*.json again and rebind the hurt capsules."),
        FConsoleCommandWithWorldAndArgsDelegate::CreateStatic(&VeyrMoveDataReloadCommand));
}

bool AVeyrDragon::MapDataMoveToEnum(FName MoveName, EVeyrDragonMove& OutMove)
{
    static const TMap<FString,EVeyrDragonMove> Names={
        {TEXT("fire"),EVeyrDragonMove::Fire},{TEXT("bellows"),EVeyrDragonMove::Fire},{TEXT("breath"),EVeyrDragonMove::Fire},
        {TEXT("flight"),EVeyrDragonMove::FlyAway},{TEXT("fly"),EVeyrDragonMove::FlyAway},{TEXT("flyaway"),EVeyrDragonMove::FlyAway},
        {TEXT("claw"),EVeyrDragonMove::ClawSwipe},{TEXT("clawswipe"),EVeyrDragonMove::ClawSwipe},
        {TEXT("stomp"),EVeyrDragonMove::BackStomp},{TEXT("backstomp"),EVeyrDragonMove::BackStomp},
        {TEXT("tail"),EVeyrDragonMove::TailSmack},{TEXT("tailsmack"),EVeyrDragonMove::TailSmack},
        {TEXT("bite"),EVeyrDragonMove::Bite}};
    if(const EVeyrDragonMove* Found=Names.Find(VeyrMoveDataKey(MoveName.ToString()))){OutMove=*Found;return true;}
    return false;
}

bool AVeyrDragon::LoadMoveDataFromDisk()
{
    StopDataMove();
    bMoveDataLoaded=false;DataMoveForEnum.Reset();
    if(!VeyrMoveData::IsEnabled())
    {
        MoveData.Reset();MoveDataDirectory.Reset();
        MoveDataDiagnostic=TEXT("veyr.MoveData.Enable 0: hard-coded behaviour only");
        UE_LOG(LogVeyrMoveData,Display,TEXT("VEYR_MOVEDATA_DISABLED %s"),*MoveDataDiagnostic);
        return false;
    }
    MoveDataDirectory=FBossMoveData::ResolveDirectory();
    UE_LOG(LogVeyrMoveData,Display,TEXT("VEYR_MOVEDATA_DIR %s"),*MoveDataDirectory);
    if(!MoveData.Load(MoveDataDirectory))
    {
        MoveDataDiagnostic=MoveData.Errors.IsEmpty()?TEXT("move data failed to load"):MoveData.Errors[0];
        return false;
    }
    bMoveDataLoaded=true;
    for(FName Name:MoveData.MoveOrder)
    {
        EVeyrDragonMove Enum;
        if(MapDataMoveToEnum(Name,Enum)&&!DataMoveForEnum.Contains(Enum))
        {
            DataMoveForEnum.Add(Enum,Name);
            UE_LOG(LogVeyrMoveData,Display,TEXT("VEYR_MOVEDATA_MAP %s -> EVeyrDragonMove %s"),*Name.ToString(),
                *StaticEnum<EVeyrDragonMove>()->GetNameStringByValue(static_cast<int64>(Enum)));
        }
        else UE_LOG(LogVeyrMoveData,Display,TEXT("VEYR_MOVEDATA_MAP %s -> data-only move"),*Name.ToString());
    }
    MoveDataDiagnostic=FString::Printf(TEXT("%d moves (%d mapped onto hard-coded moves), %d windows, %d parts"),
        MoveData.Moves.Num(),DataMoveForEnum.Num(),MoveData.CountAttacks(),MoveData.Parts.Num());
    return true;
}

bool AVeyrDragon::ReloadMoveData()
{
    LoadMoveDataFromDisk();
    BuildHurtParts();
    UpdateHurtParts();
    return bMoveDataLoaded;
}

void AVeyrDragon::DestroyHurtParts()
{
    for(UCapsuleComponent* Capsule:HurtCapsules)if(IsValid(Capsule))Capsule->DestroyComponent();
    HurtCapsules.Reset();HurtParts.Reset();ActiveDataParts.Reset();
    bHurtPartsReady=false;
}

bool AVeyrDragon::BuildHurtParts()
{
    DestroyHurtParts();
    HurtFrameYawDegrees=0.f;HurtFrameResidualCm=-1.f;
    if(!bMoveDataLoaded)return false;
    UWorld* World=GetWorld();
    if(!World||!World->IsGameWorld())return false;
    USkeletalMesh* Mesh=ImportedPresentation?ImportedPresentation->GetSkeletalMeshAsset():nullptr;
    if(!bUsingCustomuseVisual||!Mesh)
    {
        MoveDataDiagnostic=TEXT("No imported dragon skeleton; data hurt capsules unbound, hard-coded regions only");
        UE_LOG(LogVeyrMoveData,Warning,TEXT("VEYR_MOVEDATA_HURT unbound: %s"),*MoveDataDiagnostic);
        return false;
    }
    const FReferenceSkeleton& Ref=Mesh->GetRefSkeleton();
    TMap<FString,int32> ByKey;
    for(int32 I=0;I<Ref.GetNum();++I)ByKey.Add(VeyrMoveDataKey(Ref.GetBoneName(I).ToString()),I);
    struct FBound{int32 Data;int32 Bone;FTransform RefPose;};
    TArray<FBound> Bound;TArray<FString> Missing;
    for(int32 I=0;I<MoveData.Parts.Num();++I)
    {
        const FBossPart& Part=MoveData.Parts[I];
        int32 Bone=Ref.FindBoneIndex(Part.Bone);
        if(Bone==INDEX_NONE)if(const int32* Found=ByKey.Find(VeyrMoveDataKey(Part.Bone.ToString())))Bone=*Found;
        if(Bone==INDEX_NONE){Missing.Add(Part.Name.ToString()+TEXT("@")+Part.Bone.ToString());continue;}
        Bound.Add({I,Bone,FAnimationRuntime::GetComponentSpaceTransformRefPose(Ref,Bone)});
    }
    if(!Missing.IsEmpty())
        UE_LOG(LogVeyrMoveData,Warning,TEXT("VEYR_MOVEDATA_HURT bones missing on %s: %s"),*Mesh->GetName(),*FString::Join(Missing,TEXT(", ")));
    if(Bound.IsEmpty())
    {
        MoveDataDiagnostic=TEXT("No boxes.json bone exists on the imported skeleton; hard-coded regions only");
        UE_LOG(LogVeyrMoveData,Warning,TEXT("VEYR_MOVEDATA_HURT unbound: %s"),*MoveDataDiagnostic);
        return false;
    }

    // Import frame check. boxes.json a/b are in the Blender rest pose mapped (x, -y, z) x 100 x game_scale;
    // the glTF importer should give the same mesh component frame. Verify instead of trusting it: for each
    // candidate yaw, compare each bone's reference-pose head with the measured distances |a_bone|, |b_bone|.
    const float Scale=FMath::Max(KINDA_SMALL_NUMBER,MoveData.GameScale);
    float BestResidual=TNumericLimits<float>::Max(),BestYaw=0.f;bool bChecked=false;
    FString Candidates;
    for(float Yaw:{0.f,90.f,180.f,270.f})
    {
        const FQuat Q(FVector::UpVector,FMath::DegreesToRadians(Yaw));
        double Sum=0.0;int32 Count=0;
        for(const FBound& B:Bound)
        {
            const FBossPart& Part=MoveData.Parts[B.Data];
            if(!Part.bHasBoneLocal)continue;
            const FVector Head=Q.UnrotateVector(B.RefPose.GetLocation())*Scale;
            Sum+=FMath::Abs(FVector::Dist(Head,Part.A)-Part.ABone.Size())+FMath::Abs(FVector::Dist(Head,Part.B)-Part.BBone.Size());
            Count+=2;
        }
        if(Count==0)break;
        const float Residual=static_cast<float>(Sum/Count);bChecked=true;
        Candidates+=FString::Printf(TEXT(" yaw%.0f=%.1f"),Yaw,Residual);
        if(Residual<BestResidual){BestResidual=Residual;BestYaw=Yaw;}
    }
    HurtFrameYawDegrees=BestYaw;HurtFrameResidualCm=bChecked?BestResidual:-1.f;
    if(bChecked)
        UE_LOG(LogVeyrMoveData,Display,TEXT("VEYR_MOVEDATA_FRAME best yaw %.0f residual %.1f cm (game scale);%s%s"),BestYaw,BestResidual,*Candidates,
            BestResidual>40.f?TEXT(" SUSPECT: capsules may not sit on the mesh; check with veyr.MoveData.Draw 1"):TEXT(""));
    const FQuat Frame(FVector::UpVector,FMath::DegreesToRadians(BestYaw));

    const int32 PawnMode=VeyrMoveData::HurtBlocksPawnMode();
    const float ComponentScale=ImportedPresentation->GetComponentTransform().GetScale3D().GetAbsMax();
    TSet<int32> Legs;
    for(const FBound& B:Bound)
    {
        const FBossPart& Part=MoveData.Parts[B.Data];
        FVeyrHurtPartRuntime Runtime;
        Runtime.DataIndex=B.Data;Runtime.Part=Part.Name;Runtime.Kind=Part.Kind;Runtime.Bone=Ref.GetBoneName(B.Bone);
        Runtime.BoneIndex=B.Bone;Runtime.Leg=Part.Leg;Runtime.DataRadius=Part.Radius;Runtime.Damage=Part.Damage;
        Runtime.LocalA=B.RefPose.InverseTransformPosition(Frame.RotateVector(Part.A)/Scale);
        Runtime.LocalB=B.RefPose.InverseTransformPosition(Frame.RotateVector(Part.B)/Scale);
        Runtime.bBlocksPawn=PawnMode==2||(PawnMode==1&&Part.Kind!=FName(TEXT("wing")));
        UCapsuleComponent* Capsule=NewObject<UCapsuleComponent>(this,*FString::Printf(TEXT("VeyrHurt_%s"),*Part.Name.ToString()));
        Capsule->SetupAttachment(ImportedPresentation,Runtime.Bone);
        // Ride the bone's location and rotation; size stays in world cm.
        Capsule->SetUsingAbsoluteScale(true);Capsule->SetRelativeScale3D(FVector::OneVector);
        const FVector Axis=Runtime.LocalB-Runtime.LocalA;
        Capsule->SetRelativeLocationAndRotation((Runtime.LocalA+Runtime.LocalB)*.5f,
            Axis.IsNearlyZero()?FQuat::Identity:FQuat::FindBetweenNormals(FVector::UpVector,Axis.GetSafeNormal()));
        const float Radius=Part.Radius/Scale*ComponentScale;
        Capsule->SetCapsuleSize(Radius,Radius+static_cast<float>(Axis.Size())*ComponentScale*.5f,false);
        // Same response set as the solid body: the knight (Pawn) cannot walk through a blocking part;
        // camera, visibility and other traces ignore it, so floor traces and the camera arm are unchanged.
        Capsule->SetCollisionObjectType(ECC_WorldDynamic);
        Capsule->SetCollisionResponseToAllChannels(ECR_Ignore);
        if(Runtime.bBlocksPawn)Capsule->SetCollisionResponseToChannel(ECC_Pawn,ECR_Block);
        Capsule->SetCollisionEnabled(Runtime.bBlocksPawn?ECollisionEnabled::QueryOnly:ECollisionEnabled::NoCollision);
        Capsule->SetGenerateOverlapEvents(false);Capsule->SetCanEverAffectNavigation(false);
        Capsule->CanCharacterStepUpOn=ECB_No;Capsule->SetHiddenInGame(true);Capsule->SetVisibility(false);
        Capsule->ComponentTags.Add(FName(*(TEXT("VeyrHurt:")+Part.Name.ToString())));
        Capsule->RegisterComponent();
        HurtCapsules.Add(Capsule);HurtParts.Add(Runtime);
        if(Part.Leg!=INDEX_NONE)Legs.Add(Part.Leg);
    }
    bHurtPartsReady=!HurtParts.IsEmpty();
    int32 Blocking=0;for(const FVeyrHurtPartRuntime& P:HurtParts)Blocking+=P.bBlocksPawn?1:0;
    MoveDataDiagnostic=FString::Printf(TEXT("%d/%d hurt capsules bound on %s (%d legs, %d block the knight), frame yaw %.0f residual %.1f cm"),
        HurtParts.Num(),MoveData.Parts.Num(),*Mesh->GetName(),Legs.Num(),Blocking,HurtFrameYawDegrees,HurtFrameResidualCm);
    UE_LOG(LogVeyrMoveData,Display,TEXT("VEYR_MOVEDATA_HURT %s"),*MoveDataDiagnostic);
    return bHurtPartsReady;
}

bool AVeyrDragon::HurtPartWorldSegment(const FVeyrHurtPartRuntime& Part, FVector& OutA, FVector& OutB, float& OutRadius) const
{
    if(!ImportedPresentation||Part.BoneIndex==INDEX_NONE||!ImportedPresentation->GetComponentSpaceTransforms().IsValidIndex(Part.BoneIndex))return false;
    const FTransform Bone=ImportedPresentation->GetBoneTransform(Part.BoneIndex);
    OutA=Bone.TransformPosition(Part.LocalA);OutB=Bone.TransformPosition(Part.LocalB);
    OutRadius=Part.DataRadius/FMath::Max(KINDA_SMALL_NUMBER,MoveData.GameScale)*Bone.GetScale3D().GetAbsMax();
    return !OutA.ContainsNaN()&&!OutB.ContainsNaN()&&FMath::IsFinite(OutRadius);
}

void AVeyrDragon::UpdateHurtParts()
{
    if(!bHurtPartsReady)return;
    for(int32 I=0;I<HurtCapsules.Num()&&I<HurtParts.Num();++I)
    {
        UCapsuleComponent* Capsule=HurtCapsules[I];
        if(!IsValid(Capsule))continue;
        // The presentation is sampled explicitly; pull the attached transform now so the
        // knight's movement and the window tests see this frame's pose.
        Capsule->UpdateComponentToWorld();
        FVector A,B;float Radius=0.f;
        if(!HurtPartWorldSegment(HurtParts[I],A,B,Radius))continue;
        const float HalfHeight=Radius+static_cast<float>(FVector::Dist(A,B))*.5f;
        if(!FMath::IsNearlyEqual(Capsule->GetUnscaledCapsuleRadius(),Radius,.5f)||
           !FMath::IsNearlyEqual(Capsule->GetUnscaledCapsuleHalfHeight(),HalfHeight,.5f))Capsule->SetCapsuleSize(Radius,HalfHeight,true);
    }
}

const FVeyrHurtPartRuntime* AVeyrDragon::FindHurtPart(FName Part) const
{
    return HurtParts.FindByPredicate([Part](const FVeyrHurtPartRuntime& P){return P.Part==Part;});
}

int32 AVeyrDragon::HurtPartRegion(const FVeyrHurtPartRuntime& Part) const
{
    if(Part.Leg>=0&&Part.Leg<4)return Part.Leg;          // per-leg stagger, leg index from boxes.json
    if(Part.Kind==FName(TEXT("head")))return 4;           // exposure bonus
    return 5;                                             // body, scaled by the part's damage share
}

bool AVeyrDragon::GetHurtPartWorld(FName Part, FVector& OutA, FVector& OutB, float& OutRadius) const
{
    const FVeyrHurtPartRuntime* Found=FindHurtPart(Part);
    return Found&&HurtPartWorldSegment(*Found,OutA,OutB,OutRadius);
}

FName AVeyrDragon::ResolveHurtPart(const UPrimitiveComponent* Component) const
{
    for(int32 I=0;I<HurtCapsules.Num()&&I<HurtParts.Num();++I)
        if(Component&&HurtCapsules[I]==Component)return HurtParts[I].Part;
    return NAME_None;
}

bool AVeyrDragon::ReceiveSwordOnPart(FName Part, const FVector& ContactWorld, bool bHeavy, int32 SwingId, float DamageMultiplier)
{
    if(IsDead()||bEncounterStopped||AcceptedSwings.Contains(SwingId)||(bUsingCustomuseVisual&&!bImportedTargetsValid))return false;
    const FVeyrHurtPartRuntime* Found=FindHurtPart(Part);
    if(!Found||ContactWorld.ContainsNaN())return false;
    const int32 Region=HurtPartRegion(*Found);
    LastSwordHurtPart=Part;LastSwordContactWorld=ContactWorld;
    ApplySwordRegion(Region,bHeavy,SwingId,DamageMultiplier,Region==5?Found->Damage:1.f);
    return true;
}

void AVeyrDragon::BeginDataMove(FName MoveName, bool bFollowsEnum)
{
    StopDataMove();
    if(!MoveData.Find(MoveName))return;
    CurrentDataMove=MoveName;bDataMoveFollowsEnum=bFollowsEnum;
    if(!bFollowsEnum&&VisualDefinition)
    {
        // A clip named after the move ("roar" or "Roar") plays while the data-only move runs.
        FString Capitalized=MoveName.ToString();
        if(!Capitalized.IsEmpty())Capitalized[0]=FChar::ToUpper(Capitalized[0]);
        for(const FName Candidate:{MoveName,FName(*Capitalized)})
            if(const FVeyrVisualClip* Clip=VisualDefinition->Clips.Find(Candidate))
                if(Clip->Sequence){DataOnlyClip=Candidate;break;}
    }
    UE_LOG(LogVeyrMoveData,Display,TEXT("VEYR_MOVEDATA_PLAY move=%s follows_enum=%d clip=%s"),*MoveName.ToString(),bFollowsEnum?1:0,
        DataOnlyClip.IsNone()?(bFollowsEnum?TEXT("hard-coded"):TEXT("none (Idle pose; capsules ride the idle)")):*DataOnlyClip.ToString());
}

void AVeyrDragon::StopDataMove()
{
    CurrentDataMove=NAME_None;bDataMoveFollowsEnum=false;DataMoveClipSeconds=0.f;
    SpentDataWindows.Reset();ActiveDataParts.Reset();DataOnlyClip=NAME_None;
}

bool AVeyrDragon::PlayDataMove(FName MoveName)
{
    if(MoveName.IsNone())
    {
        const bool bWasPlaying=IsDataOnlyMovePlaying();
        if(bWasPlaying)StopDataMove();
        if(bWasPlaying&&State==EVeyrDragonState::Idle)EnterState(EVeyrDragonState::Idle,.4f);
        return true;
    }
    if(!bMoveDataLoaded){UE_LOG(LogVeyrMoveData,Warning,TEXT("PlayDataMove %s: no move data loaded (%s)"),*MoveName.ToString(),*MoveDataDiagnostic);return false;}
    const FBossMove* DataMove=MoveData.Find(MoveName);
    if(!DataMove){UE_LOG(LogVeyrMoveData,Warning,TEXT("PlayDataMove %s: not in moves.json"),*MoveName.ToString());return false;}
    if(IsDead()||bEncounterStopped||State!=EVeyrDragonState::Idle||IsDataOnlyMovePlaying())
    {UE_LOG(LogVeyrMoveData,Warning,TEXT("PlayDataMove %s: refused, dragon is busy (state %d)"),*MoveName.ToString(),static_cast<int32>(State));return false;}
    EVeyrDragonMove Enum;
    if(MapDataMoveToEnum(MoveName,Enum))
    {
        // The hard-coded attack owns timing, warnings and contact; BeginAttack attaches the data move.
        if(!IsValid(Target))return false;
        BeginAttack(Enum);
        return true;
    }
    BeginDataMove(MoveName,false);
    // Hold Idle for the move; ChooseAttack is suppressed while a data-only move plays.
    EnterState(EVeyrDragonState::Idle,TNumericLimits<float>::Max());
    return true;
}

bool AVeyrDragon::DataWindowsReplaceContact() const
{
    if(!bDataMoveFollowsEnum||CurrentDataMove.IsNone()||VeyrMoveData::HitsMode()<2||!bHurtPartsReady)return false;
    const FBossMove* DataMove=MoveData.Find(CurrentDataMove);
    return DataMove&&!DataMove->Attacks.IsEmpty();
}

void AVeyrDragon::UpdateDataMove(float DeltaSeconds)
{
    ActiveDataParts.Reset();
    if(CurrentDataMove.IsNone())return;
    const FBossMove* DataMove=MoveData.Find(CurrentDataMove);
    if(!DataMove){StopDataMove();return;}
    const float From=DataMoveClipSeconds;
    if(bDataMoveFollowsEnum)
    {
        // Clip time follows the hard-coded state clock from the start of the wind-up.
        float To;
        if(State==EVeyrDragonState::Windup)To=StateElapsed;
        else if(State==EVeyrDragonState::Active)To=WindupDuration+StateElapsed;
        else if(State==EVeyrDragonState::Recovery)To=WindupDuration+ActiveDuration+StateElapsed;
        else{StopDataMove();return;}
        To=FMath::Clamp(To,From,DataMove->Duration);
        EvaluateDataWindows(*DataMove,From,To,VeyrMoveData::HitsMode()>=2);
        DataMoveClipSeconds=To;
        return;
    }
    if(State!=EVeyrDragonState::Idle||IsDead()||bEncounterStopped){StopDataMove();return;}
    float To=From+DeltaSeconds*DataMove->TempoAt(From);
    bool bFinished=false;
    if(DataMove->bLoop)
    {
        if(To>=DataMove->Duration)
        {
            EvaluateDataWindows(*DataMove,From,DataMove->Duration,false);
            To=FMath::Fmod(To,DataMove->Duration);SpentDataWindows.Reset();
            EvaluateDataWindows(*DataMove,0.f,To,false);
        }
        else EvaluateDataWindows(*DataMove,From,To,false);
    }
    else
    {
        if(To>=DataMove->Duration){To=DataMove->Duration;bFinished=true;}
        EvaluateDataWindows(*DataMove,From,To,VeyrMoveData::HitsMode()>=1);
    }
    DataMoveClipSeconds=To;
    if(bFinished)
    {
        UE_LOG(LogVeyrMoveData,Display,TEXT("VEYR_MOVEDATA_END move=%s hits=%d blocked=%d avoided=%d"),*CurrentDataMove.ToString(),
            DataWindowHitCount,DataWindowBlockedCount,DataWindowAvoidedCount);
        StopDataMove();
        EnterState(EVeyrDragonState::Idle,.4f);
    }
}

void AVeyrDragon::EvaluateDataWindows(const FBossMove& DataMove, float FromSeconds, float ToSeconds, bool bMayHurt)
{
    for(int32 I=0;I<DataMove.Attacks.Num();++I)
    {
        const FBossAttack& Attack=DataMove.Attacks[I];
        if(ToSeconds<Attack.T0||FromSeconds>Attack.T1)continue;
        ActiveDataParts.Add(Attack.Part);
        // Loops never hurt (blueprint rule); one hit per window.
        if(!bMayHurt||DataMove.bLoop||SpentDataWindows.Contains(I)||!bHurtPartsReady)continue;
        if(!IsValid(Target)||Target->IsDead()||IsDead()||bEncounterStopped)continue;
        const FName* CapsuleName=AttackPartCapsule.Find(Attack.Part);
        const FVeyrHurtPartRuntime* Part=FindHurtPart(CapsuleName?*CapsuleName:Attack.Part);
        FVector A,B;float Radius=0.f;
        if(!Part||!HurtPartWorldSegment(*Part,A,B,Radius))continue;
        const UCapsuleComponent* Knight=Target->GetCapsuleComponent();
        if(!Knight)continue;
        const FVector Center=Knight->GetComponentLocation();
        const float KnightRadius=Knight->GetScaledCapsuleRadius();
        const float KnightAxis=FMath::Max(0.f,Knight->GetScaledCapsuleHalfHeight()-KnightRadius);
        FVector OnPart,OnKnight;
        FMath::SegmentDistToSegmentSafe(A,B,Center-FVector(0,0,KnightAxis),Center+FVector(0,0,KnightAxis),OnPart,OnKnight);
        if(FVector::Dist(OnPart,OnKnight)>Radius+KnightRadius)continue;
        // A pillar or wall between the part and the knight blocks the blow; the window stays open.
        FCollisionQueryParams Query(SCENE_QUERY_STAT(VeyrDragonDataWindow),false,this);
        Query.AddIgnoredActor(Target);
        FHitResult Wall;
        if(GetWorld()&&GetWorld()->LineTraceSingleByChannel(Wall,OnPart,Center,ECC_Visibility,Query)&&Wall.bBlockingHit)
        {++DataWindowBlockedCount;continue;}
        SpentDataWindows.Add(I);++DataWindowHitCount;LastDataHitPart=Attack.Part;
        const float* Table=AttackPartDamage.Find(Attack.Part);
        const float Damage=Table?*Table:30.f;
        const float Before=Target->Health;
        Target->ApplyBossDamage(Damage,OnPart,false);
        if(Target->Health>=Before-.001f)++DataWindowAvoidedCount;
        UE_LOG(LogVeyrMoveData,Display,TEXT("VEYR_MOVEDATA_HIT move=%s window=%d part=%s capsule=%s clip=%.3f damage=%.1f dealt=%.1f"),
            *CurrentDataMove.ToString(),I,*Attack.Part.ToString(),*Part->Part.ToString(),ToSeconds,Damage,Before-Target->Health);
    }
}

void AVeyrDragon::DescribeMoveData(TArray<FString>& OutLines) const
{
    if(MoveData.bLoaded||!MoveData.Errors.IsEmpty())MoveData.Describe(OutLines);
    else OutLines.Add(FString::Printf(TEXT("VEYR_MOVEDATA dir=%s loaded=0 (%s)"),*MoveDataDirectory,*MoveDataDiagnostic));
    for(FName Name:MoveData.MoveOrder)
    {
        EVeyrDragonMove Enum;
        OutLines.Add(FString::Printf(TEXT("VEYR_MOVEDATA_MAP %s -> %s"),*Name.ToString(),MapDataMoveToEnum(Name,Enum)?
            *StaticEnum<EVeyrDragonMove>()->GetNameStringByValue(static_cast<int64>(Enum)):TEXT("data-only")));
    }
    OutLines.Add(FString::Printf(TEXT("VEYR_MOVEDATA_RUNTIME dragon=%s loaded=%d hurt_ready=%d parts=%d/%d frame_yaw=%.0f residual_cm=%.1f hits_mode=%d sword_parts=%d current=%s follows_enum=%d clip=%.3f window_hits=%d blocked=%d avoided=%d diag=%s"),
        *GetName(),bMoveDataLoaded?1:0,bHurtPartsReady?1:0,HurtParts.Num(),MoveData.Parts.Num(),HurtFrameYawDegrees,HurtFrameResidualCm,
        VeyrMoveData::HitsMode(),VeyrMoveData::SwordPartsEnabled()?1:0,*CurrentDataMove.ToString(),bDataMoveFollowsEnum?1:0,DataMoveClipSeconds,
        DataWindowHitCount,DataWindowBlockedCount,DataWindowAvoidedCount,*MoveDataDiagnostic));
    for(const FVeyrHurtPartRuntime& Part:HurtParts)
    {
        FVector A,B;float Radius=0.f;const bool bPose=HurtPartWorldSegment(Part,A,B,Radius);
        OutLines.Add(FString::Printf(TEXT("VEYR_MOVEDATA_CAPSULE %s bone=%s leg=%d region=%d blocks_pawn=%d radius=%.1f world_a=%s world_b=%s"),
            *Part.Part.ToString(),*Part.Bone.ToString(),Part.Leg,HurtPartRegion(Part),Part.bBlocksPawn?1:0,Radius,
            bPose?*A.ToCompactString():TEXT("n/a"),bPose?*B.ToCompactString():TEXT("n/a")));
    }
}

void AVeyrDragon::DrawMoveDataDebug() const
{
#if ENABLE_DRAW_DEBUG
    if(VeyrMoveData::DrawMode()<=0||!GetWorld())return;
    TSet<FName> Hot;
    for(FName AttackPart:ActiveDataParts){const FName* C=AttackPartCapsule.Find(AttackPart);Hot.Add(C?*C:AttackPart);}
    for(const FVeyrHurtPartRuntime& Part:HurtParts)
    {
        FVector A,B;float Radius=0.f;
        if(!HurtPartWorldSegment(Part,A,B,Radius))continue;
        const FVector Axis=B-A;
        const FColor Color=Hot.Contains(Part.Part)?FColor::Red:Part.bBlocksPawn?FColor::Green:FColor::Cyan;
        DrawDebugCapsule(GetWorld(),(A+B)*.5f,Radius+static_cast<float>(Axis.Size())*.5f,Radius,
            Axis.IsNearlyZero()?FQuat::Identity:FQuat::FindBetweenNormals(FVector::UpVector,Axis.GetSafeNormal()),Color,false,-1.f,0,Hot.Contains(Part.Part)?6.f:2.f);
    }
    FString Label=CurrentDataMove.IsNone()?FString(TEXT("data move: none")):
        FString::Printf(TEXT("data move: %s %.2fs%s"),*CurrentDataMove.ToString(),DataMoveClipSeconds,bDataMoveFollowsEnum?TEXT(" (enum)"):TEXT(""));
    for(FName AttackPart:ActiveDataParts)Label+=TEXT(" | hot ")+AttackPart.ToString();
    Label+=FString::Printf(TEXT(" | hits %d blocked %d"),DataWindowHitCount,DataWindowBlockedCount);
    DrawDebugString(GetWorld(),GetActorLocation()+FVector(0,0,1250),Label,nullptr,FColor::White,0.f,true,1.2f);
#endif
}

void AVeyrDragon::LogMoveDataDumpIfRequested() const
{
    if(!FParse::Param(FCommandLine::Get(),TEXT("VeyrMoveDataDump")))return;
    TArray<FString> Lines;DescribeMoveData(Lines);VeyrMoveDataLog(Lines);
}
