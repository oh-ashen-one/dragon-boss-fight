// F1-F4 (2026-11-18): dragon clip playback at runtime. Data and switches: VeyrDragonPlayback.h.
#include "VeyrDragon.h"
#include "VeyrDragonPlayback.h"
#include "VeyrSingleNodeInstance.h"
#include "VeyrSkeletalPresentation.h"
#include "VeyrVisualDefinition.h"
#include "Animation/AnimSequence.h"
#include "Dom/JsonObject.h"

namespace
{
    float SmoothStep01(float X){X=FMath::Clamp(X,0.f,1.f);return X*X*(3.f-2.f*X);}
    const TCHAR* const GLegNames[4]={TEXT("FL"),TEXT("FR"),TEXT("HL"),TEXT("HR")};
    // creature.json limbs, UE names: upper, knee/elbow (the hinge), end (wrist/hock). The front right chain has
    // one more toe (tripo__0_Left_Limb_3) below bone_14; it rides the end bone like every toe.
    const TCHAR* const GLegBones[4][3]={
        {TEXT("bone_7"),TEXT("tripo__1_Left_Limb_0"),TEXT("bone_9")},
        {TEXT("tripo__0_Left_Limb_0"),TEXT("tripo__0_Left_Limb_1"),TEXT("bone_14")},
        {TEXT("tripo__1_Right_Limb_1"),TEXT("tripo__1_Right_Limb_2"),TEXT("tripo__1_Right_Limb_3")},
        {TEXT("tripo__0_Right_Limb_1"),TEXT("tripo__0_Right_Limb_2"),TEXT("tripo__0_Right_Limb_3")}};
}

const FVeyrClipPlayback* AVeyrDragon::TempoClip(FName Clip,float& OutRate,float& OutHoldRate) const
{
    OutRate=OutHoldRate=1.f;
    if(!bClipTempo||!Playback.bLoaded)return nullptr;
    FName Phase;
    const FVeyrClipPlayback* C=Playback.Find(Clip,Phase);
    if(C)Playback.RatesFor(*C,Phase,OutRate,OutHoldRate);
    return C;
}

float AVeyrDragon::TempoDuration(FName Clip) const
{
    float Rate=1.f,Hold=1.f;
    const FVeyrClipPlayback* C=TempoClip(Clip,Rate,Hold);
    const FVeyrVisualClip* Config=VisualDefinition?VisualDefinition->Clips.Find(Clip):nullptr;
    if(!C||!Config||!Config->Sequence)return -1.f;
    const float End=Config->EndSeconds<0.f?Config->Sequence->GetPlayLength():Config->EndSeconds;
    return FMath::Max(.05f,FVeyrDragonPlayback::RealSeconds(*C,Config->StartSeconds,End,Rate,Hold));
}

bool AVeyrDragon::TempoTrimmedSeconds(FName Clip,float RealElapsed,float& OutTrimmed) const
{
    float Rate=1.f,Hold=1.f;
    const FVeyrClipPlayback* C=TempoClip(Clip,Rate,Hold);
    const FVeyrVisualClip* Config=VisualDefinition?VisualDefinition->Clips.Find(Clip):nullptr;
    if(!C||!Config||!Config->Sequence||Config->bLoop)return false;
    const float End=Config->EndSeconds<0.f?Config->Sequence->GetPlayLength():Config->EndSeconds;
    OutTrimmed=FVeyrDragonPlayback::BakedAfter(*C,Config->StartSeconds,End,FMath::Max(0.f,RealElapsed),Rate,Hold)-Config->StartSeconds;
    OutTrimmed=FMath::Clamp(OutTrimmed,0.f,End-Config->StartSeconds);
    return true;
}

float AVeyrDragon::ActivePhaseSeconds(float Phase) const
{
    const FName Clip=ImportedMoveClip(Move,Move==EVeyrDragonMove::ClawSwipe?ClawLeg:StompLeg,TEXT("Active"));
    float Rate=1.f,Hold=1.f;
    const FVeyrClipPlayback* C=TempoClip(Clip,Rate,Hold);
    const FVeyrVisualClip* Config=VisualDefinition?VisualDefinition->Clips.Find(Clip):nullptr;
    if(!C||!Config||!Config->Sequence)return Phase*ActiveDuration;
    const float End=Config->EndSeconds<0.f?Config->Sequence->GetPlayLength():Config->EndSeconds;
    return FVeyrDragonPlayback::RealSeconds(*C,Config->StartSeconds,Config->StartSeconds+FMath::Clamp(Phase,0.f,1.f)*(End-Config->StartSeconds),Rate,Hold);
}

const FVeyrMoveTempo* AVeyrDragon::TempoForMove(EVeyrDragonMove Attack,int32 Leg) const
{
    float Rate=1.f,Hold=1.f;
    const FVeyrClipPlayback* C=TempoClip(ImportedMoveClip(Attack,Leg,TEXT("Windup")),Rate,Hold);
    return C?Playback.MoveTempo(*C):nullptr;
}

float AVeyrDragon::SnapTrackRate() const
{
    return bSlowSnapTurn&&Playback.bLoaded?FMath::Max(10.f,Playback.TrackRateDps):TrackRateDegreesPerSecond*PaceScale;
}

float AVeyrDragon::TurnClipSeconds(FName Clip,float LegacySeconds) const
{
    const float Tempo=TempoDuration(VideoClip(Clip));
    return Tempo>0.f?Tempo:LegacySeconds;
}

float AVeyrDragon::MeasureWalkStrideSpeed()
{
    // The walk was cut in place (travel removed from Spine_0): its planted feet slide backwards at the stride speed.
    // Moving the actor at that speed, at the clip's own cadence, keeps them still. Measured on the hidden probe.
    const FName Walk=VideoClip(TEXT("Walk"));
    const FVeyrVisualClip* Config=VisualDefinition?VisualDefinition->Clips.Find(Walk):nullptr;
    if(!AttackPoseProbe||!Config||!Config->Sequence||!Config->bLoop)return 0.f;
    const float End=Config->EndSeconds<0.f?Config->Sequence->GetPlayLength():Config->EndSeconds;
    const float Duration=End-Config->StartSeconds;
    constexpr int32 N=48;
    TArray<FVector> Feet[4];
    AttackPoseProbe->SetComponentSpaceBoneRotations(TMap<FName,FRotator>());
    const FTransform Actor=GetActorTransform();
    for(int32 I=0;I<=N;++I)
    {
        if(!AttackPoseProbe->SampleClipTime(Walk,Duration*I/N))return 0.f;
        for(int32 L=0;L<4;++L)
        {
            FTransform T;
            if(!AttackPoseProbe->GetBoneTargetWorldTransform(FName(*FString::Printf(TEXT("foot%d"),L)),T))return 0.f;
            // Actor-local but in world centimetres (scale kept).
            Feet[L].Add(Actor.GetRotation().UnrotateVector(T.GetLocation()-Actor.GetLocation()));
        }
    }
    double Sum=0.0;int32 Count=0;
    const float Dt=Duration/N;
    for(int32 L=0;L<4;++L)
    {
        float MinZ=TNumericLimits<float>::Max();
        for(const FVector& P:Feet[L])MinZ=FMath::Min(MinZ,static_cast<float>(P.Z));
        for(int32 I=0;I<N;++I)
            if(Feet[L][I].Z<=MinZ+3.f*BodyScale&&Feet[L][I+1].Z<=MinZ+3.f*BodyScale)
            {Sum+=-(Feet[L][I+1].X-Feet[L][I].X)/Dt;++Count;}
    }
    const float Speed=Count>=4?static_cast<float>(Sum/Count):0.f;
    PlaybackDiagnostic+=FString::Printf(TEXT(" walkStride=%.0fcm/s(%d planted samples)"),Speed,Count);
    return Speed>=40.f*BodyScale&&Speed<=1500.f*BodyScale?Speed:0.f;
}

void AVeyrDragon::InitPlayback()
{
    if(bPlaybackInit)return;
    bPlaybackInit=true;
    const TCHAR* Cmd=FCommandLine::Get();
    FString Diagnostic;
    const bool Loaded=Playback.Load(Diagnostic);
    PlaybackDiagnostic=Diagnostic;
    bClipTempo=Loaded&&!FParse::Param(Cmd,TEXT("VeyrLegacyClipTempo"));
    bTwoClipBlend=!FParse::Param(Cmd,TEXT("VeyrLegacyBlend"));
    bFootLock=Loaded&&!FParse::Param(Cmd,TEXT("VeyrNoFootLock"));
    bSlowSnapTurn=Loaded&&!FParse::Param(Cmd,TEXT("VeyrLegacySnapTurn"));
    bRootTracks=Loaded&&!FParse::Param(Cmd,TEXT("VeyrNoRootTracks"));
    UE_LOG(LogTemp,Display,TEXT("VEYR_DRAGON_PLAYBACK loaded=%d tempo=%d blend=%d footlock=%d slowturn=%d roottracks=%d %s"),
        Loaded?1:0,bClipTempo?1:0,bTwoClipBlend?1:0,bFootLock?1:0,bSlowSnapTurn?1:0,bRootTracks?1:0,*PlaybackDiagnostic);
}

float AVeyrDragon::RepositionTurnPhase() const
{
    const float Linear=RepositionTurnDuration>.001f?FMath::Clamp(StateElapsed/RepositionTurnDuration,0.f,1.f):1.f;
    if(!bClipTempo||!bRepositionAuthoredTurn)return Linear;
    const FName Clip=VideoClip(RepositionTurnClip);
    const float Duration=VisualClipDuration(Clip,0.f);
    float Trimmed=0.f;
    if(Duration<=.001f||!TempoTrimmedSeconds(Clip,StateElapsed,Trimmed))return Linear;
    return FMath::Clamp(Trimmed/Duration,0.f,1.f);
}

float AVeyrDragon::TempoWalkBaseSpeed() const
{
    if(WalkStrideSpeedCm>0.f)return WalkStrideSpeedCm;
    const FName Key=VideoClip(TEXT("Walk"));
    const FVeyrVisualClip* Clip=VisualDefinition?VisualDefinition->Clips.Find(Key):nullptr;
    const float Nominal=Clip&&Clip->NominalSpeedCmPerSecond>0.f?Clip->NominalSpeedCmPerSecond:160.f;
    return (Key==FName(TEXT("WalkV2r"))?FMath::Min(Nominal,160.f):Nominal)*BodyScale;
}

float AVeyrDragon::TempoWalkRate() const
{
    const FVeyrMoveTempo* T=Playback.Moves.Find(TEXT("walk"));
    return T?T->Rate:1.f;
}

float AVeyrDragon::PlaybackPhaseCeiling(FName Clip) const
{
    float Rate=1.f,Hold=1.f;
    FName Phase;
    const FVeyrClipPlayback* C=bClipTempo&&Playback.bLoaded?Playback.Find(Clip,Phase):nullptr;
    const FVeyrMoveTempo* T=C?Playback.MoveTempo(*C):nullptr;
    if(!T||Phase!=FName(TEXT("Recovery"))||(bShowcaseMode&&!bShowcaseGameTiming))return 1.f;
    const FVeyrVisualClip* Config=VisualDefinition?VisualDefinition->Clips.Find(Clip):nullptr;
    const float Full=TempoDuration(Clip);
    float Trimmed=0.f;
    if(!Config||!Config->Sequence||Full<=0.f||!TempoTrimmedSeconds(Clip,Full*T->RecoveryExit,Trimmed))return 1.f;
    const float End=Config->EndSeconds<0.f?Config->Sequence->GetPlayLength():Config->EndSeconds;
    return FMath::Clamp(Trimmed/FMath::Max(.001f,End-Config->StartSeconds),0.f,1.f);
}

FName AVeyrDragon::PlaybackStatKey(FName Clip) const
{
    FString S=Clip.ToString();
    if(S.EndsWith(TEXT("V2r")))S.LeftChopInline(3);
    return FName(*S);
}

void AVeyrDragon::ApplyRootTracks(FName Clip,float SequenceSeconds,float Weight)
{
    // Called before the destination is sampled. Actor travel = blend of both clips' track deltas; each pose has its
    // own track offset removed, so actor + pose is the clip's own world body path (hitboxes unchanged) and nothing
    // slides back when the clip ends or fades.
    FVector DestOffset=FVector::ZeroVector,SourceOffset=FVector::ZeroVector;
    const bool Eligible=bRootTracks&&!IsDead();
    FName Phase;
    const FVeyrClipPlayback* Dest=Eligible&&Playback.bLoaded?Playback.Find(Clip,Phase):nullptr;
    if(Dest){const FVeyrMoveTempo* T=Playback.MoveTempo(*Dest);if(!T||!T->bRootTrack||Dest->TrackCm.IsEmpty())Dest=nullptr;}
    const FTransform& Comp=ImportedPresentation->GetComponentTransform();
    auto ToWorld=[&](const FVector2D& D){FVector W=Comp.TransformVector(FVector(D.X,D.Y,0.f));W.Z=0.f;return W;};
    FVector Delta=FVector::ZeroVector;
    if(Dest)
    {
        // New stem, or the same clip restarted: the track starts again from here.
        if(TrackStem!=Dest->Stem||SequenceSeconds<TrackLastBaked-.05f){TrackStem=Dest->Stem;TrackEntryBaked=TrackLastBaked=SequenceSeconds;}
        const FVector2D Now=Dest->TrackAt(SequenceSeconds),Last=Dest->TrackAt(TrackLastBaked),Entry=Dest->TrackAt(TrackEntryBaked);
        Delta+=ToWorld(Now-Last)*Weight;
        DestOffset=FVector(Now.X-Entry.X,Now.Y-Entry.Y,0.f);
        TrackLastBaked=SequenceSeconds;
        FPlaybackStat& S=PlaybackStats.FindOrAdd(PlaybackStatKey(Clip));
        S.TrackLengthCm+=ToWorld(Now-Last).Size();
    }
    else TrackStem=NAME_None;
    if(bFadeActive&&!FadeTrackStem.IsNone())
    {
        const FVeyrClipPlayback* Src=Playback.Clips.Find(FadeTrackStem);
        if(Src&&!Src->TrackCm.IsEmpty())
        {
            const FVector2D Now=Src->TrackAt(FadeSourceSeconds),Last=Src->TrackAt(FadeTrackLastBaked),Entry=Src->TrackAt(FadeTrackEntryBaked);
            Delta+=ToWorld(Now-Last)*(1.f-Weight);
            SourceOffset=FVector(Now.X-Entry.X,Now.Y-Entry.Y,0.f);
            FadeTrackLastBaked=FadeSourceSeconds;
        }
    }
    if(!Delta.IsNearlyZero(.001))
    {
        FVector Next=GetActorLocation()+Delta;
        const FVector Clamped=ClampArena(Next,RoamRadius());Next.X=Clamped.X;Next.Y=Clamped.Y;
        TrackTravelWorld+=Next-GetActorLocation();
        if(Dest)PlaybackStats.FindOrAdd(PlaybackStatKey(Clip)).TravelWorld+=Next-GetActorLocation();
        SetActorLocation(Next);
    }
    ImportedPresentation->SetRootOffsets(DestOffset,SourceOffset);
}

void AVeyrDragon::ResetFootLock()
{
    for(FFootLockFoot& F:LockFeet)F=FFootLockFoot();
    if(ImportedPresentation)ImportedPresentation->ClearLegLocks();
}

void AVeyrDragon::UpdateFootLock(bool bFading)
{
    const bool Eligible=bFootLock&&Playback.bLoaded&&!IsDead()&&!IsAirborne()&&
        !(Move==EVeyrDragonMove::FlyAway&&(State==EVeyrDragonState::Windup||State==EVeyrDragonState::Active||State==EVeyrDragonState::Recovery));
    if(!Eligible){bool Any=false;for(const auto& F:LockFeet)Any|=F.bLocked||F.bStepping||F.bReleasing;if(Any)ResetFootLock();return;}
    FVeyrSoleSample Anim;
    if(!ImportedPresentation->MeasureSoles(Anim)||!Anim.bValid){FootLockDiagnostic=TEXT("sole model unavailable");return;}
    const float Dt=FootLockClock<0.f?0.f:FMath::Max(0.f,Clock-FootLockClock);
    if(Dt>0.f||FootLockClock<0.f)FootLockClock=Clock;
    const FVeyrFootLockTuning& T=Playback.FootLock;
    const float S=BodyScale;
    FPlaybackStat& Stat=PlaybackStats.FindOrAdd(PlaybackStatKey(LastImportedClip));
    TArray<FVeyrLegLock> Locks;Locks.SetNum(4);
    for(int32 L=0;L<4;++L)
    {
        FFootLockFoot& F=LockFeet[L];
        const FVector Tip=Anim.Lowest[L];
        const float Height=Anim.SoleAboveFloorCm[L];
        if(Dt>0.f)
        {
            const float Speed=F.bHasPrev?static_cast<float>(FVector::Dist2D(Tip,F.PrevTip))/Dt:0.f;
            if(F.bLocked)
            {
                const float Drag=static_cast<float>(FVector::Dist2D(F.Pin,Tip));
                if(Height>T.ReleaseHeightCm*S||(Height>2.f*S&&Drag>T.DragReleaseCm*S))
                {F.bLocked=false;F.bReleasing=true;F.T=0.f;F.From=F.Pin;}
                else if(Drag>T.SlipCm*S)
                {
                    // Dragged past its reach on the floor (a body turn under a planted foot): an eased lifted step.
                    F.bLocked=false;F.bStepping=true;F.T=0.f;F.From=F.Pin;
                    if(Height<T.PlantHeightCm*S)++Stat.Steps;else ++Stat.Slips;
                }
            }
            else if(F.bStepping)
            {
                F.T+=Dt/FMath::Max(.05f,T.StepSeconds);
                if(F.T>=1.f){F.bStepping=false;F.bLocked=Height<T.PlantHeightCm*S;F.Pin=Tip;}
            }
            else if(F.bReleasing)
            {
                F.T+=Dt/FMath::Max(.02f,T.ReleaseSeconds);
                if(F.T>=1.f)F.bReleasing=false;
            }
            // A foot plants only when it is low AND slow in the clip (bFading only marks evidence).
            if(!F.bLocked&&!F.bStepping&&Height<T.PlantHeightCm*S&&Speed<T.PlantSpeedCms*S)
            {F.bLocked=true;F.bReleasing=false;F.Pin=Tip;}
            if(Height<T.PlantHeightCm*S&&F.bHasPrev)
            {Stat.PlantedSeconds[L]+=Dt;Stat.AnimatedSlideCm[L]+=FVector::Dist2D(Tip,F.PrevTip);}
            F.PrevTip=Tip;F.bHasPrev=true;
        }
        FVector Goal=Tip;float Weight=0.f;
        if(F.bLocked){Goal=FVector(F.Pin.X,F.Pin.Y,Tip.Z);Weight=1.f;}
        else if(F.bStepping)
        {
            const float U=SmoothStep01(F.T);
            Goal=FMath::Lerp(F.From,Tip,U);Goal.Z=Tip.Z+FMath::Sin(PI*FMath::Clamp(F.T,0.f,1.f))*T.StepLiftCm*S;Weight=1.f;
        }
        else if(F.bReleasing){Goal=FMath::Lerp(F.From,Tip,SmoothStep01(F.T));Goal.Z=Tip.Z;Weight=1.f;}
        F.Target=Goal;F.Weight=Weight;
        FVeyrLegLock& Lock=Locks[L];
        for(int32 J=0;J<3;++J)Lock.Bones[J]=FName(GLegBones[L][J]);
        Lock.Delta=ImportedPresentation->GetComponentTransform().InverseTransformVector(Goal-Tip);
        Lock.Weight=Weight;Lock.LastBend=F.LastBend;
    }
    if(!ImportedPresentation->SetLegLocks(Locks)){FootLockDiagnostic=ImportedPresentation->LastError;return;}
    const FString Error=ImportedPresentation->GetLegLockError();
    if(!Error.IsEmpty())FootLockDiagnostic=Error;
    for(float Miss:ImportedPresentation->GetLegLockMissCm())
        Stat.MaxIkMissCm=FMath::Max(Stat.MaxIkMissCm,Miss*static_cast<float>(ImportedPresentation->GetComponentTransform().GetScale3D().GetAbsMax()));
    FVeyrSoleSample Drawn;
    if(Dt>0.f&&ImportedPresentation->MeasureSoles(Drawn)&&Drawn.bValid)
        for(int32 L=0;L<4;++L)
        {
            FFootLockFoot& F=LockFeet[L];
            if(F.bLocked&&!F.PrevDrawn.IsZero())Stat.DrawnSlideCm[L]+=FVector::Dist2D(Drawn.Lowest[L],F.PrevDrawn);
            F.PrevDrawn=F.bLocked?Drawn.Lowest[L]:FVector::ZeroVector;
        }
}

TSharedPtr<FJsonObject> AVeyrDragon::PlaybackEvidence() const
{
    TSharedPtr<FJsonObject> O=MakeShared<FJsonObject>();
    O->SetBoolField(TEXT("clipTempo"),bClipTempo);O->SetBoolField(TEXT("twoClipBlend"),bTwoClipBlend);
    O->SetBoolField(TEXT("footLock"),bFootLock);O->SetBoolField(TEXT("slowSnapTurn"),bSlowSnapTurn);O->SetBoolField(TEXT("rootTracks"),bRootTracks);
    O->SetStringField(TEXT("data"),PlaybackDiagnostic);O->SetStringField(TEXT("footLockDiagnostic"),FootLockDiagnostic);
    O->SetNumberField(TEXT("snapTrackRateDps"),SnapTrackRate());O->SetNumberField(TEXT("walkStrideSpeedCmPerSec"),WalkStrideSpeedCm);
    O->SetNumberField(TEXT("trackTravelWorldCm"),TrackTravelWorld.Size2D());
    float WorstRate=0.f,WorstSlide=0.f;FString WorstRateKey,WorstSlideKey;
    TSharedPtr<FJsonObject> Clips=MakeShared<FJsonObject>();
    for(const auto& E:PlaybackStats)
    {
        const FPlaybackStat& S=E.Value;
        TSharedPtr<FJsonObject> C=MakeShared<FJsonObject>();
        C->SetNumberField(TEXT("frames"),S.Frames);C->SetNumberField(TEXT("realSeconds"),S.RealSeconds);
        C->SetNumberField(TEXT("meanSourceRate"),S.RealSeconds>0?S.SourceSeconds/S.RealSeconds:0.);
        C->SetNumberField(TEXT("meanSourceRateOutsideHolds"),S.RealNonHold>0?S.SourceNonHold/S.RealNonHold:0.);
        C->SetNumberField(TEXT("maxFrameSourceRateOutsideHolds"),S.MaxRateNonHold);
        TSharedPtr<FJsonObject> B=MakeShared<FJsonObject>();for(const auto& K:S.Blends)B->SetNumberField(K.Key,K.Value);C->SetObjectField(TEXT("blends"),B);
        TSharedPtr<FJsonObject> Feet=MakeShared<FJsonObject>();
        float MoveWorst=0.f;
        for(int32 L=0;L<4;++L)
        {
            TSharedPtr<FJsonObject> F=MakeShared<FJsonObject>();
            F->SetNumberField(TEXT("plantedSeconds"),S.PlantedSeconds[L]);
            const double Animated=S.PlantedSeconds[L]>0?S.AnimatedSlideCm[L]/S.PlantedSeconds[L]:0.,Drawn=S.PlantedSeconds[L]>0?S.DrawnSlideCm[L]/S.PlantedSeconds[L]:0.;
            F->SetNumberField(TEXT("animatedSlideCmPerSec"),Animated);F->SetNumberField(TEXT("drawnSlideCmPerSec"),Drawn);
            Feet->SetObjectField(GLegNames[L],F);
            if(S.PlantedSeconds[L]>.2)MoveWorst=FMath::Max(MoveWorst,static_cast<float>(bFootLock?Drawn:Animated));
        }
        C->SetObjectField(TEXT("feet"),Feet);C->SetNumberField(TEXT("worstPlantedSlideCmPerSec"),MoveWorst);
        C->SetNumberField(TEXT("steps"),S.Steps);C->SetNumberField(TEXT("slips"),S.Slips);C->SetNumberField(TEXT("maxIkMissCm"),S.MaxIkMissCm);
        C->SetNumberField(TEXT("travelWorldCm"),S.TravelWorld.Size2D());C->SetNumberField(TEXT("trackPathWorldCm"),S.TrackLengthCm);
        Clips->SetObjectField(E.Key.ToString(),C);
        if(S.MaxRateNonHold>WorstRate&&S.Frames>3){WorstRate=S.MaxRateNonHold;WorstRateKey=E.Key.ToString();}
        if(MoveWorst>WorstSlide){WorstSlide=MoveWorst;WorstSlideKey=E.Key.ToString();}
    }
    O->SetObjectField(TEXT("clips"),Clips);
    O->SetNumberField(TEXT("worstFrameSourceRateOutsideHolds"),WorstRate);O->SetStringField(TEXT("worstRateClip"),WorstRateKey);
    O->SetNumberField(TEXT("worstPlantedSlideCmPerSec"),WorstSlide);O->SetStringField(TEXT("worstSlideClip"),WorstSlideKey);
    O->SetBoolField(TEXT("gateRateAtMost1_25"),WorstRate<=1.25f+.02f);O->SetBoolField(TEXT("gateSlideUnder5"),WorstSlide<5.f);
    return O;
}
