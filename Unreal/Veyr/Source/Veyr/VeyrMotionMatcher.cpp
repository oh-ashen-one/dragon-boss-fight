#include "VeyrMotionMatcher.h"

#include "AssetRegistry/AssetRegistryModule.h"
#include "Animation/AnimSequence.h"
#include "Components/SkeletalMeshComponent.h"
#include "Dom/JsonObject.h"
#include "Misc/CommandLine.h"
#include "Misc/FileHelper.h"
#include "Misc/Parse.h"
#include "PoseSearch/PoseSearchDatabase.h"
#include "PoseSearch/PoseSearchEvent.h"
#include "PoseSearch/PoseSearchHistory.h"
#include "PoseSearch/PoseSearchIndex.h"
#include "PoseSearch/PoseSearchLibrary.h"
#include "PoseSearch/PoseSearchResult.h"
#include "PoseSearch/PoseSearchRole.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "VeyrBoneRoles.h"

namespace
{
    constexpr float Ln2=0.69314718f;
    float DampingFromHalfLife(float HalfLife){return (4.f*Ln2)/FMath::Max(HalfLife,1e-4f);}
    const TCHAR* GateName(EVeyrMotionGate Gate)
    {
        switch(Gate)
        {
            case EVeyrMotionGate::Idle:return TEXT("Idle");
            case EVeyrMotionGate::Start:return TEXT("Start");
            case EVeyrMotionGate::Loop:return TEXT("Loop");
            case EVeyrMotionGate::Stop:return TEXT("Stop");
            case EVeyrMotionGate::Pivot:return TEXT("Pivot");
            case EVeyrMotionGate::TurnInPlace:return TEXT("Turn");
            default:return TEXT("None");
        }
    }
    bool GateFromName(const FString& Name,EVeyrMotionGate& Out)
    {
        for(int32 G=0;G<static_cast<int32>(EVeyrMotionGate::Count);++G)
            if(Name.Equals(GateName(static_cast<EVeyrMotionGate>(G)),ESearchCase::IgnoreCase)){Out=static_cast<EVeyrMotionGate>(G);return true;}
        return false;
    }
    FVector Planar(FVector V){V.Z=0.f;return V;}
}

// ---------------------------------------------------------------- spring (Holden, "Spring-It-On", critically damped)

void FVeyrSpringTrajectory::Reset(const FVector& InPosition,float InYaw)
{
    Position=InPosition;Velocity=Acceleration=FVector::ZeroVector;Yaw=InYaw;YawRate=0.f;
}

void FVeyrSpringTrajectory::Predict(const FVector& DesiredVelocity,float DesiredYaw,float Seconds,FVector& OutPosition,float& OutYaw) const
{
    // Velocity spring: v(t) = vd + (j0 + j1 t) e^{-y t}, integrated in closed form for the position.
    const float Y=DampingFromHalfLife(VelocityHalfLife)/2.f;
    const FVector J0=Velocity-DesiredVelocity;
    const FVector J1=Acceleration+J0*Y;
    const float E=FMath::Exp(-Y*Seconds);
    OutPosition=Position+DesiredVelocity*Seconds+(J1/(Y*Y))+((-J1*Seconds-J0*Y-J1/Y)/Y)*E+J0/Y;
    // Yaw spring toward the shortest-arc desired facing.
    const float Yy=DampingFromHalfLife(YawHalfLife)/2.f;
    const float Error=FMath::FindDeltaAngleDegrees(DesiredYaw,Yaw);
    const float K1=YawRate+Error*Yy;
    OutYaw=DesiredYaw+(Error+K1*Seconds)*FMath::Exp(-Yy*Seconds);
}

void FVeyrSpringTrajectory::Step(const FVector& DesiredVelocity,float DesiredYaw,float Dt)
{
    if(Dt<=0.f)return;
    const float Y=DampingFromHalfLife(VelocityHalfLife)/2.f;
    const FVector J0=Velocity-DesiredVelocity;
    const FVector J1=Acceleration+J0*Y;
    const float E=FMath::Exp(-Y*Dt);
    FVector NewPosition;float NewYaw;
    Predict(DesiredVelocity,DesiredYaw,Dt,NewPosition,NewYaw);
    Velocity=E*(J0+J1*Dt)+DesiredVelocity;
    Acceleration=E*(Acceleration-J1*Y*Dt);
    const float Yy=DampingFromHalfLife(YawHalfLife)/2.f;
    const float Error=FMath::FindDeltaAngleDegrees(DesiredYaw,Yaw);
    const float K1=YawRate+Error*Yy;
    YawRate=FMath::Exp(-Yy*Dt)*(YawRate-K1*Yy*Dt);
    Position=NewPosition;Yaw=FRotator::NormalizeAxis(NewYaw);
}

FTransformTrajectory FVeyrSpringTrajectory::BuildTrajectory(const TArray<FTransformTrajectorySample>& Recorded,const FVector& DesiredVelocity,
    float DesiredYaw,TConstArrayView<float> Future) const
{
    FTransformTrajectory Out;
    Out.Samples.Append(Recorded); // TimeInSeconds < 0, oldest first
    FTransformTrajectorySample Now;Now.Position=Position;Now.Facing=FRotator(0.f,Yaw,0.f).Quaternion();Now.TimeInSeconds=0.f;
    Out.Samples.Add(Now);
    for(float T:Future)
    {
        FTransformTrajectorySample S;float SampleYaw=0.f;
        Predict(DesiredVelocity,DesiredYaw,T,S.Position,SampleYaw);
        S.Facing=FRotator(0.f,SampleYaw,0.f).Quaternion();S.TimeInSeconds=T;
        Out.Samples.Add(S);
    }
    return Out;
}

// ---------------------------------------------------------------- fallback feature table

bool FVeyrMotionFeatureTable::LoadJson(const FString& File,FString& OutError)
{
    Rows.Reset();Source=File;
    FString Text;
    if(!FFileHelper::LoadFileToString(Text,*File)){OutError=TEXT("Motion feature table missing: ")+File;return false;}
    TSharedPtr<FJsonObject> Root;
    if(!FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text),Root)||!Root.IsValid()){OutError=TEXT("Motion feature table is not JSON");return false;}
    if(Root->GetStringField(TEXT("schema"))!=TEXT("veyr-motion-features-v1")){OutError=TEXT("Motion feature table schema mismatch");return false;}
    auto ReadVector=[&](const TCHAR* Key,float* Out)->bool
    {
        const TArray<TSharedPtr<FJsonValue>>* A=nullptr;
        if(!Root->TryGetArrayField(Key,A)||A->Num()!=FVeyrMotionFeatures::Num)return false;
        for(int32 I=0;I<FVeyrMotionFeatures::Num;++I)Out[I]=static_cast<float>((*A)[I]->AsNumber());
        return true;
    };
    float Std[FVeyrMotionFeatures::Num];
    if(!ReadVector(TEXT("mean"),Mean)||!ReadVector(TEXT("std"),Std)||!ReadVector(TEXT("weights"),Weights))
    {OutError=TEXT("Motion feature table needs 33-float mean/std/weights");return false;}
    for(int32 I=0;I<FVeyrMotionFeatures::Num;++I)InverseStd[I]=Std[I]>1e-6f?1.f/Std[I]:0.f;
    const TArray<TSharedPtr<FJsonValue>>* RowValues=nullptr;
    if(!Root->TryGetArrayField(TEXT("rows"),RowValues)){OutError=TEXT("Motion feature table has no rows");return false;}
    for(const TSharedPtr<FJsonValue>& V:*RowValues)
    {
        const TSharedPtr<FJsonObject> O=V->AsObject();
        if(!O.IsValid())continue;
        FRow Row;Row.Clip=FName(O->GetStringField(TEXT("clip")));Row.Time=static_cast<float>(O->GetNumberField(TEXT("time")));
        const TArray<TSharedPtr<FJsonValue>>* F=nullptr;const TArray<TSharedPtr<FJsonValue>>* G=nullptr;
        if(!O->TryGetArrayField(TEXT("f"),F)||F->Num()!=FVeyrMotionFeatures::Num){OutError=TEXT("Motion feature row is not 33 floats");Rows.Reset();return false;}
        for(int32 I=0;I<FVeyrMotionFeatures::Num;++I)Row.Features.Values[I]=static_cast<float>((*F)[I]->AsNumber());
        if(O->TryGetArrayField(TEXT("gates"),G))for(const TSharedPtr<FJsonValue>& Gv:*G)
        {EVeyrMotionGate Gate;if(GateFromName(Gv->AsString(),Gate))Row.GateMask|=uint8(1u<<static_cast<uint8>(Gate));}
        Rows.Add(Row);
    }
    if(Rows.IsEmpty()){OutError=TEXT("Motion feature table is empty");return false;}
    return true;
}

float FVeyrMotionFeatureTable::Cost(const FVeyrMotionFeatures& Query,const FRow& Row) const
{
    float Sum=0.f;
    for(int32 I=0;I<FVeyrMotionFeatures::Num;++I)
    {
        const float D=(Query.Values[I]-Row.Features.Values[I])*InverseStd[I];
        Sum+=Weights[I]*D*D;
    }
    return Sum;
}

int32 FVeyrMotionFeatureTable::Search(const FVeyrMotionFeatures& Query,EVeyrMotionGate Gate,float& OutCost) const
{
    const uint8 Bit=uint8(1u<<static_cast<uint8>(Gate));
    int32 Best=INDEX_NONE;OutCost=MAX_flt;
    for(int32 I=0;I<Rows.Num();++I)
    {
        if(!(Rows[I].GateMask&Bit))continue;
        const float C=Cost(Query,Rows[I]);
        if(C<OutCost){OutCost=C;Best=I;}
    }
    return Best;
}

// ---------------------------------------------------------------- gates (reference rules)

bool FVeyrMotionGates::Update(const FVector& Velocity,const FVector& DesiredVelocity,bool bInputHeld,float FacingErrorDegrees)
{
    const EVeyrMotionGate Before=Current;
    const float Speed=Planar(Velocity).Size(),Desired=Planar(DesiredVelocity).Size();
    if(!bInputHeld||Desired<StopSpeedCmPerSecond)
    {
        // Stops only on release; once slow, idle (or a turn on the spot if the facing is far off).
        if(Speed>StopSpeedCmPerSecond)Current=EVeyrMotionGate::Stop;
        else Current=FMath::Abs(FacingErrorDegrees)>=TurnInPlaceDegrees?EVeyrMotionGate::TurnInPlace:EVeyrMotionGate::Idle;
    }
    else if(Speed<StartSpeedCmPerSecond)Current=EVeyrMotionGate::Start;
    else
    {
        const float Angle=FMath::RadiansToDegrees(FMath::Acos(FMath::Clamp(
            static_cast<float>(FVector::DotProduct(Planar(Velocity).GetSafeNormal(),Planar(DesiredVelocity).GetSafeNormal())),-1.f,1.f)));
        Current=Angle>=PivotDegrees?EVeyrMotionGate::Pivot:(Current==EVeyrMotionGate::Pivot&&Angle>45.f?EVeyrMotionGate::Pivot:EVeyrMotionGate::Loop);
    }
    return Current!=Before;
}

// ---------------------------------------------------------------- capsule coupling

FVector FVeyrCapsuleCoupling::Step(const FVector& ClipTravel,const FVector& CapsuleTravel)
{
    // Body moved by the clip; capsule by the spring. The difference accumulates, then is pulled back by at most
    // 20 % of this frame's own clip travel, then hard-clamped to 15 cm.
    BodyOffset+=Planar(ClipTravel)-Planar(CapsuleTravel);
    const float Allowed=MaxCorrectionShare*Planar(ClipTravel).Size();
    const float Size=BodyOffset.Size();
    if(Size>KINDA_SMALL_NUMBER)BodyOffset-=BodyOffset/Size*FMath::Min(Allowed,Size);
    ++Steps;WorstSeparationCm=FMath::Max(WorstSeparationCm,float(BodyOffset.Size()));
    if(BodyOffset.Size()>MaxSeparationCm){BodyOffset=BodyOffset.GetSafeNormal()*MaxSeparationCm;++ClampedSteps;}
    return BodyOffset;
}

// ---------------------------------------------------------------- matcher

FVeyrMotionMatcher::FVeyrMotionMatcher()=default;
FVeyrMotionMatcher::~FVeyrMotionMatcher()=default;

bool FVeyrMotionMatcher::Initialize(USkeletalMeshComponent* Mesh,const FString& DatabaseFolder,const FString& FallbackTableFile,FString& OutError)
{
    bReady=false;LastError.Reset();
    bForceFallback=FParse::Param(FCommandLine::Get(),TEXT("VeyrMotionFallback"));
    for(auto& Set:Databases)Set.Reset();
    if(!Mesh||!Mesh->GetSkeletalMeshAsset()){OutError=TEXT("Motion matcher needs the Greystone mesh");return false;}
    int32 Found=0;
    if(!bForceFallback)
    {
        // Databases are found by name, so the gate table is data: PSD_GS_<Gate>_*. (GASP: PSD_Dense_Stand_Run_Loops etc.)
        IAssetRegistry& Registry=FModuleManager::LoadModuleChecked<FAssetRegistryModule>(TEXT("AssetRegistry")).Get();
        TArray<FAssetData> Assets;
        Registry.GetAssetsByPath(FName(*DatabaseFolder),Assets,true);
        for(const FAssetData& Asset:Assets)
        {
            if(Asset.AssetClassPath!=UPoseSearchDatabase::StaticClass()->GetClassPathName())continue;
            const FString Name=Asset.AssetName.ToString();
            EVeyrMotionGate Gate;bool Known=false;
            static const TPair<const TCHAR*,EVeyrMotionGate> Keys[]={{TEXT("Idle"),EVeyrMotionGate::Idle},{TEXT("Start"),EVeyrMotionGate::Start},
                {TEXT("Loop"),EVeyrMotionGate::Loop},{TEXT("Stop"),EVeyrMotionGate::Stop},{TEXT("Pivot"),EVeyrMotionGate::Pivot},{TEXT("Turn"),EVeyrMotionGate::TurnInPlace}};
            for(const auto& Key:Keys)if(Name.Contains(Key.Key)){Gate=Key.Value;Known=true;break;}
            if(!Known)continue;
            if(UPoseSearchDatabase* Database=Cast<UPoseSearchDatabase>(Asset.GetAsset()))
            {Databases[static_cast<int32>(Gate)].Emplace(Database);++Found;}
        }
    }
    FString FallbackError;
    const bool HaveFallback=Fallback.LoadJson(FallbackTableFile,FallbackError);
    if(!Found&&!HaveFallback){OutError=TEXT("No motion databases in ")+DatabaseFolder+TEXT(" and ")+FallbackError;return false;}
    History=MakeShared<UE::PoseSearch::FPoseHistory>();
    History->Initialize_AnyThread(64,.04f); // 2.5 s at 25 Hz; schema history samples need well under 1 s
    RecordedRoot.Reset();
    Sim.Reset(Mesh->GetOwner()?Mesh->GetOwner()->GetActorLocation():FVector::ZeroVector,Mesh->GetOwner()?Mesh->GetOwner()->GetActorRotation().Yaw:0.f);
    Current=FVeyrMotionChoice();CurrentGate=EVeyrMotionGate::Idle;Gates=FVeyrMotionGates();Coupling.Reset();
    SinceSearch=SinceSwitch=Clock=0.f;Searches=Switches=FallbackSearches=ForcedSearches=0;bHaveLastFeet=false;
    LastMesh=Mesh;
    bReady=true;
    UE_LOG(LogTemp,Display,TEXT("VEYR_MOTION_MATCHER databases=%d fallbackRows=%d forcedFallback=%d"),Found,Fallback.Rows.Num(),bForceFallback?1:0);
    return true;
}

void FVeyrMotionMatcher::RecordShownPose(const USkeletalMeshComponent* Mesh,float Dt)
{
    if(!bReady||!Mesh||!History.IsValid()||Dt<=0.f)return;
    LastDt=Dt;Clock+=Dt;
    // Root history for the trajectory (world space, times relative to now).
    for(FTransformTrajectorySample& S:RecordedRoot)S.TimeInSeconds-=Dt;
    FTransformTrajectorySample Now;Now.Position=Mesh->GetComponentLocation();Now.Facing=Mesh->GetComponentQuat();Now.TimeInSeconds=0.f;
    RecordedRoot.RemoveAll([](const FTransformTrajectorySample& S){return S.TimeInSeconds< -1.f;});
    // Keep samples at about 0.1 s spacing; the newest one becomes history next frame.
    if(RecordedRoot.IsEmpty()||RecordedRoot.Last().TimeInSeconds<=-.1f)RecordedRoot.Add(Now);
    if(!RecordedRoot.IsEmpty()&&RecordedRoot.Last().TimeInSeconds>=0.f)RecordedRoot.Last().TimeInSeconds=-Dt;
PRAGMA_DISABLE_EXPERIMENTAL_WARNINGS
    UE::PoseSearch::FSKMCComponentSpacePoseProvider Provider(Mesh);
PRAGMA_ENABLE_EXPERIMENTAL_WARNINGS
    const USkeleton* Skeleton=Provider.GetSkeletonAsset();
    if(!Skeleton)return;
    TArray<FBoneIndexType> Required;
    const int32 Count=Skeleton->GetReferenceSkeleton().GetNum();
    Required.Reserve(Count);
    for(int32 I=0;I<Count;++I)Required.Add(static_cast<FBoneIndexType>(I));
    History->EvaluateComponentSpace_AnyThread(Dt,Provider,false,0.f,1.f,1.f,false,false,Required,FBlendedCurve(),TConstArrayView<FName>()
#if WITH_EDITORONLY_DATA
        ,Mesh->GetComponentTransform()
#endif
    );
}

bool FVeyrMotionMatcher::SearchPoseSearch(UAnimInstance* AnimContext,EVeyrMotionGate Gate,FVeyrMotionChoice& Out)
{
    using namespace UE::PoseSearch;
    const auto& Set=Databases[static_cast<int32>(Gate)];
    if(Set.IsEmpty()||!AnimContext||!History.IsValid())return false;
    TArray<const UObject*> Assets;for(const auto& D:Set)if(D.IsValid())Assets.Add(D.Get());
    const UObject* Contexts[1]={AnimContext};
    const FRole Roles[1]={DefaultRole};
    const IPoseHistory* Histories[1]={History.Get()};
    FPoseSearchContinuingProperties Continuing;
    Continuing.PlayingAsset=Current.Sequence;
    Continuing.PlayingAssetAccumulatedTime=Current.Time;
    Continuing.bIsPlayingAssetMirrored=Current.bMirrored;
    const FSearchResult Result=UPoseSearchLibrary::MotionMatch(MakeArrayView(Contexts),MakeArrayView(Roles),MakeArrayView(Histories),
        MakeArrayView(Assets),Continuing,FPoseSearchFutureProperties(),FPoseSearchEvent());
    if(!Result.IsValid())return false;
    Out.Sequence=Cast<UAnimSequence>(Result.GetCurrentResultAnimationAsset());
    if(!Out.Sequence)return false; // blend spaces are not used by our sampler
    Out.Time=Result.IsAssetTimeValid()?Result.GetAssetTime():0.f;
    const FSearchIndexAsset* IndexAsset=Result.GetSearchIndexAsset();
    Out.bMirrored=IndexAsset&&IndexAsset->IsMirrored();
    Out.Cost=Result.PoseCost;
    Out.bFromFallback=false;Out.FallbackClip=NAME_None;
    // A continuing result means "keep playing": never counts as a switch.
    Out.bSwitched=!Result.bIsContinuingPoseSearch;
    return true;
}

bool FVeyrMotionMatcher::SearchFallback(const USkeletalMeshComponent* Mesh,EVeyrMotionGate Gate,const FVector& DesiredVelocity,float DesiredYaw,FVeyrMotionChoice& Out)
{
    if(Fallback.Rows.IsEmpty()||!Mesh)return false;
    // Query in capsule space: x forward, y right, z up (the baker uses the same frame).
    const AActor* Owner=Mesh->GetOwner();
    if(!Owner)return false;
    const FTransform Frame(FRotator(0.f,Sim.Yaw,0.f),Mesh->GetComponentLocation()); // sole level, like the baker's root bone
    FVeyrMotionFeatures Q;int32 K=0;
    auto Push=[&](const FVector& V){Q.Values[K++]=V.X;Q.Values[K++]=V.Y;Q.Values[K++]=V.Z;};
    const FName Feet[2]={VeyrBoneRoles::Resolve(Mesh,EVeyrBoneRole::LeftAnkle),VeyrBoneRoles::Resolve(Mesh,EVeyrBoneRole::RightAnkle)};
    const FName Hands[2]={VeyrBoneRoles::Resolve(Mesh,EVeyrBoneRole::LeftHand),VeyrBoneRoles::Resolve(Mesh,EVeyrBoneRole::RightHand)};
    const FName Hips=VeyrBoneRoles::Resolve(Mesh,EVeyrBoneRole::Pelvis);
    FVector FeetNow[2],HipsNow=Frame.InverseTransformPosition(Mesh->GetBoneLocation(Hips));
    for(int32 S=0;S<2;++S){FeetNow[S]=Frame.InverseTransformPosition(Mesh->GetBoneLocation(Feet[S]));Push(FeetNow[S]);}
    for(int32 S=0;S<2;++S)Push(Frame.InverseTransformPosition(Mesh->GetBoneLocation(Hands[S])));
    const float Dt=FMath::Max(LastDt,1e-3f);
    for(int32 S=0;S<2;++S)Push(bHaveLastFeet?(FeetNow[S]-LastFeet[S])/Dt:FVector::ZeroVector);
    Push(bHaveLastFeet?(HipsNow-LastHips)/Dt:FVector::ZeroVector);
    LastFeet[0]=FeetNow[0];LastFeet[1]=FeetNow[1];LastHips=HipsNow;bHaveLastFeet=true;
    FVector P[3];float Y[3];
    for(int32 I=0;I<3;++I)Sim.Predict(DesiredVelocity,DesiredYaw,FutureTimes[I],P[I],Y[I]);
    for(int32 I=0;I<3;++I){const FVector L=Frame.InverseTransformPosition(P[I]);Q.Values[K++]=L.X;Q.Values[K++]=L.Y;}
    for(int32 I=0;I<3;++I){const FVector F=Frame.InverseTransformVectorNoScale(FRotator(0.f,Y[I],0.f).Vector());Q.Values[K++]=F.X;Q.Values[K++]=F.Y;}
    check(K==FVeyrMotionFeatures::Num);
    float BestCost=MAX_flt;
    const int32 Best=Fallback.Search(Q,Gate,BestCost);
    ++FallbackSearches;
    if(Best==INDEX_NONE)return false;
    // Current cost: the row nearest the current clip time, same clip.
    float CurrentCost=MAX_flt;
    if(Current.bFromFallback)for(const auto& Row:Fallback.Rows)
        if(Row.Clip==Current.FallbackClip&&FMath::Abs(Row.Time-Current.Time)<.05f)CurrentCost=FMath::Min(CurrentCost,Fallback.Cost(Q,Row));
    Out=FVeyrMotionChoice();
    Out.FallbackClip=Fallback.Rows[Best].Clip;Out.Time=Fallback.Rows[Best].Time;Out.Cost=BestCost;Out.bFromFallback=true;
    // Reference hysteresis: switch only if the current pose is clearly worse.
    Out.bSwitched=!(Current.bFromFallback&&CurrentCost<=SwitchCostRatio*BestCost+SwitchCostBias);
    return true;
}

FVeyrMotionChoice FVeyrMotionMatcher::Step(UAnimInstance* AnimContext,const FVector& CapsuleLocation,float CapsuleYaw,const FVector& DesiredVelocity,
    float DesiredYaw,bool bInputHeld,bool bActionPlaying,float Dt)
{
    FVeyrMotionChoice Result=Current;Result.bSwitched=false;
    if(!bReady||Dt<=0.f)return Result;
    SinceSearch+=Dt;SinceSwitch+=Dt;
    // The capsule is authoritative (owner-fixed hitboxes): the spring starts from where the capsule really is.
    Sim.Position=CapsuleLocation;
    Sim.Step(DesiredVelocity,DesiredYaw,Dt);
    if(bActionPlaying){SinceSearch=SearchInterval;return Result;} // actions are a separate clip class: never searched
    if(History.IsValid())History->SetTrajectory(Sim.BuildTrajectory(RecordedRoot,DesiredVelocity,DesiredYaw,MakeArrayView(FutureTimes)));
    const bool Forced=Gates.Update(Sim.Velocity,DesiredVelocity,bInputHeld,FMath::FindDeltaAngleDegrees(CapsuleYaw,DesiredYaw));
    if(Forced)++ForcedSearches;
    if(!Forced&&SinceSearch<SearchInterval)return Result;
    SinceSearch=0.f;++Searches;
    FVeyrMotionChoice Found;
    const bool Ok=(!bForceFallback&&SearchPoseSearch(AnimContext,Gates.Current,Found))||
        SearchFallback(LastMesh.Get(),Gates.Current,DesiredVelocity,DesiredYaw,Found);
    if(!Ok)return Result;
    if(Found.bSwitched&&(Forced||SinceSwitch>=MinSecondsBetweenSwitches))
    {
        Found.bSwitched=true;Current=Found;CurrentGate=Gates.Current;SinceSwitch=0.f;++Switches;
        return Found;
    }
    return Result;
}

void FVeyrMotionMatcher::AdvanceCurrent(float SourceSeconds)
{
    if(FMath::IsFinite(SourceSeconds)&&SourceSeconds>=0.f)Current.Time=SourceSeconds;
}

FVeyrInertialSwitch FVeyrMotionMatcher::SwitchFor(EVeyrMotionGate From,EVeyrMotionGate To) const
{
    // Reference half-lives: 0.10 s default; legs 0.06 s in pivots; torso 0.35 s into steady cycles.
    FVeyrInertialSwitch S;
    if(To==EVeyrMotionGate::Pivot)S.LegsHalfLife=.06f;
    if(To==EVeyrMotionGate::Loop&&From!=EVeyrMotionGate::Loop)S.TorsoHalfLife=.35f;
    return S;
}

TSharedRef<FJsonObject> FVeyrMotionMatcher::Evidence() const
{
    TSharedRef<FJsonObject> O=MakeShared<FJsonObject>();
    O->SetBoolField(TEXT("ready"),bReady);
    O->SetBoolField(TEXT("forcedFallback"),bForceFallback);
    int32 Count=0;for(const auto& Set:Databases)Count+=Set.Num();
    O->SetNumberField(TEXT("databases"),Count);
    O->SetNumberField(TEXT("fallbackRows"),Fallback.Rows.Num());
    O->SetNumberField(TEXT("searches"),Searches);
    O->SetNumberField(TEXT("forcedSearches"),ForcedSearches);
    O->SetNumberField(TEXT("fallbackSearches"),FallbackSearches);
    O->SetNumberField(TEXT("switches"),Switches);
    O->SetNumberField(TEXT("couplingSteps"),Coupling.Steps);
    O->SetNumberField(TEXT("couplingClampedSteps"),Coupling.ClampedSteps);
    O->SetNumberField(TEXT("couplingWorstSeparationCm"),Coupling.WorstSeparationCm);
    O->SetStringField(TEXT("gate"),GateName(Gates.Current));
    O->SetNumberField(TEXT("bodyOffsetCm"),Coupling.BodyOffset.Size());
    if(!LastError.IsEmpty())O->SetStringField(TEXT("error"),LastError);
    return O;
}
