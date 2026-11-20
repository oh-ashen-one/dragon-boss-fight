// F1-F4 (2026-11-18): dragon clip playback at runtime. Data and switches: VeyrDragonPlayback.h.
#include "VeyrDragon.h"
#include "VeyrDragonPlayback.h"
#include "VeyrFightFeel.h"
#include "VeyrGameMode.h"
#include "VeyrSingleNodeInstance.h"
#include "VeyrSkeletalPresentation.h"
#include "VeyrVisualDefinition.h"
#include "Animation/AnimSequence.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "Dom/JsonObject.h"

namespace
{
    float SmoothStep01(float X){X=FMath::Clamp(X,0.f,1.f);return X*X*(3.f-2.f*X);}
    const TCHAR* const GLegNames[4]={TEXT("FL"),TEXT("FR"),TEXT("HL"),TEXT("HR")};
    // creature.json limbs, UE names: upper, knee/elbow (the hinge), end (wrist/hock).
    const TCHAR* const GLegBones[4][3]={
        {TEXT("bone_7"),TEXT("tripo__1_Left_Limb_0"),TEXT("bone_9")},
        {TEXT("tripo__0_Left_Limb_0"),TEXT("tripo__0_Left_Limb_1"),TEXT("bone_14")},
        {TEXT("tripo__1_Right_Limb_1"),TEXT("tripo__1_Right_Limb_2"),TEXT("tripo__1_Right_Limb_3")},
        {TEXT("tripo__0_Right_Limb_1"),TEXT("tripo__0_Right_Limb_2"),TEXT("tripo__0_Right_Limb_3")}};
    // Bones parented to the knee/elbow beside the end bone (GLB hierarchy) that belong to the paw: FL toe, FR toe chain
    // (tripo__0_Left_Limb_3 is its child). The hind toes (Limb_4) are children of the hock end bone already.
    const TCHAR* const GLegRiders[4]={TEXT("tripo__1_Left_Limb_1"),TEXT("tripo__0_Left_Limb_2"),nullptr,nullptr};
}

const FVeyrClipPlayback* AVeyrDragon::TempoClip(FName Clip,float& OutRate,float& OutHoldRate) const
{
    OutRate=OutHoldRate=1.f;
    if(!bClipTempo||!Playback.bLoaded)return nullptr;
    FName Phase;
    const FVeyrClipPlayback* C=Playback.Find(Clip,Phase);
    if(C)Playback.RatesFor(*C,Phase,OutRate,OutHoldRate);
    // Review H4: the wounded boss keeps its phase-two speed-up on every attack phase (fire's sweep excepted), as before.
    if(C&&!Phase.IsNone()&&InSecondPhase()&&!(C->Move==FName(TEXT("fire"))&&Phase==FName(TEXT("Active"))))
    {OutRate=FMath::Min(OutRate*Playback.Phase2Rate,FMath::Max(OutRate,Playback.Phase2MaxRate));OutHoldRate*=Playback.Phase2Rate;}
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
    bTwoClipBlend=Loaded&&!FParse::Param(Cmd,TEXT("VeyrLegacyBlend"));
    bFootLock=Loaded&&!FParse::Param(Cmd,TEXT("VeyrNoFootLock"));
    // Round 2 fairness (coordinator 2026-11-19): wind-up tracking is the goal branch's 195 deg/s late snap by default;
    // -VeyrDragonSlowTrackTurn restores round 1's 90 deg/s turn (-VeyrLegacySnapTurn still forces the snap).
    bSlowSnapTurn=Loaded&&FParse::Param(Cmd,TEXT("VeyrDragonSlowTrackTurn"))&&!FParse::Param(Cmd,TEXT("VeyrLegacySnapTurn"));
    bRootTracks=Loaded&&!FParse::Param(Cmd,TEXT("VeyrNoRootTracks"));
    // Gate 2 (round 2, 18:05): the one-hand sweep on package 11 had a median of 50 pops per fight (22-68) against
    // round 1's 25-47, so inertial blending is opt-in (-VeyrInertialBlend); the default keeps the two-clip fades.
    bInertialBlend=bTwoClipBlend&&FParse::Param(Cmd,TEXT("VeyrInertialBlend"))&&!FParse::Param(Cmd,TEXT("VeyrCrossfadeBlend"));
    // Gate 1 (round 2, 17:10): v3 stepping slid more than round 1's foot lock in turns, walk and wind-ups, so it is
    // opt-in; the default keeps round 1's foot lock. -VeyrNoProceduralSteps stays accepted (and wins).
    bProcSteps=bFootLock&&FParse::Param(Cmd,TEXT("VeyrDragonProceduralSteps"))&&!FParse::Param(Cmd,TEXT("VeyrNoProceduralSteps"));
    bHeadYawLimit=Loaded&&!FParse::Param(Cmd,TEXT("VeyrNoHeadYawLimit"));
    FParse::Value(Cmd,TEXT("VeyrHeadYawMaxDps="),HeadYawMaxDps);HeadYawMaxDps=FMath::Clamp(HeadYawMaxDps,60.f,2000.f);
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
    float Rate=T?T->Rate:1.f;
    // Round 2 (F, band): the measured stride (745 cm/s at body scale 2) walked the dragon 43 % faster over the
    // ground than before playback (160 x 1.25 x scale x pace = 520 cm/s), shortening two-hand fights and closing
    // on the knight sooner. The default keeps the pre-playback ground speed and slows the cadence to match, so the
    // planted feet still hold (the walk phase advances by distance). -VeyrDragonWalkClipSpeed keeps the clip's speed.
    static const bool bClipSpeed=FParse::Param(FCommandLine::Get(),TEXT("VeyrDragonWalkClipSpeed"));
    if(!bClipSpeed&&WalkStrideSpeedCm>0.f)
    {
        const FName Key=VideoClip(TEXT("Walk"));
        const FVeyrVisualClip* Clip=VisualDefinition?VisualDefinition->Clips.Find(Key):nullptr;
        const float Nominal=Clip&&Clip->NominalSpeedCmPerSecond>0.f?Clip->NominalSpeedCmPerSecond:160.f;
        const float Legacy=(Key==FName(TEXT("WalkV2r"))?FMath::Min(Nominal,160.f):Nominal)*1.25f*BodyScale*PaceScale;
        Rate=FMath::Min(Rate,Legacy/WalkStrideSpeedCm);
    }
    return Rate;
}

float AVeyrDragon::PlaybackPhaseCeiling(FName Clip) const
{
    float Rate=1.f,Hold=1.f;
    FName Phase;
    const FVeyrClipPlayback* C=bClipTempo&&Playback.bLoaded?Playback.Find(Clip,Phase):nullptr;
    const FVeyrMoveTempo* T=C?Playback.MoveTempo(*C):nullptr;
    const FVeyrVisualClip* Config=VisualDefinition?VisualDefinition->Clips.Find(Clip):nullptr;
    if(!C||!Config||!Config->Sequence)return 1.f;
    const float End=Config->EndSeconds<0.f?Config->Sequence->GetPlayLength():Config->EndSeconds;
    const float Length=FMath::Max(.001f,End-Config->StartSeconds);
    // Round 2: a clip that ends in a held span shows its last pose from the hold's first frame on (holds play at
    // hold_rate, so the frozen tail can pass between two sampled frames). -VeyrLegacyShowcaseCeiling restores 1.0.
    float Ceiling=1.f;
    static const bool bLegacyCeiling=FParse::Param(FCommandLine::Get(),TEXT("VeyrLegacyShowcaseCeiling"));
    if(!bLegacyCeiling&&C->InHold(C->SourceFrameAt(End)))
        for(float S=End;S>Config->StartSeconds;S-=1.f/C->OutFps)
            if(!C->InHold(C->SourceFrameAt(S))){Ceiling=FMath::Clamp((S-Config->StartSeconds)/Length,.5f,1.f);break;}
    if(!T||Phase!=FName(TEXT("Recovery"))||(bShowcaseMode&&!bShowcaseGameTiming))return Ceiling;
    const float Full=TempoDuration(Clip);
    float Trimmed=0.f;
    if(Full<=0.f||!TempoTrimmedSeconds(Clip,Full*T->RecoveryExit,Trimmed))return Ceiling;
    return FMath::Min(Ceiling,FMath::Clamp(Trimmed/Length,0.f,1.f));
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
    // Rise's own track (about 200 cm at 2x) stays on, as in round 1: without it the Rise->Idle slide-back doubles.
    // -VeyrNoRiseRootTrack turns only Rise's track off.
    static const bool bRiseTrack=!FParse::Param(FCommandLine::Get(),TEXT("VeyrNoRiseRootTrack"));
    if(Dest&&!bRiseTrack&&Dest->Move==FName(TEXT("rise")))Dest=nullptr;
    const FTransform& Comp=ImportedPresentation->GetComponentTransform();
    auto ToWorld=[&](const FVector2D& D){FVector W=Comp.TransformVector(FVector(D.X,D.Y,0.f));W.Z=0.f;return W;};
    FVector Delta=FVector::ZeroVector,InstPart=FVector::ZeroVector;
    const bool Restart=Dest&&TrackStem==Dest->Stem&&SequenceSeconds<TrackLastBaked-.05f;
    if(!TrackInstStem.IsNone()&&(Restart||!((Dest&&Dest->Stem==TrackInstStem)||(bFadeActive&&FadeTrackStem==TrackInstStem))))CloseTrackInstance();
    if(Dest&&TrackInstStem.IsNone()){TrackInstStem=Dest->Stem;TrackInstKey=PlaybackStatKey(Clip);TrackInstExpected=TrackInstApplied=FVector::ZeroVector;}
    if(Dest)
    {
        // New stem, or the same clip restarted: the track starts again from here.
        if(TrackStem!=Dest->Stem||SequenceSeconds<TrackLastBaked-.05f){TrackStem=Dest->Stem;TrackEntryBaked=TrackLastBaked=SequenceSeconds;}
        const FVector2D Now=Dest->TrackAt(SequenceSeconds),Last=Dest->TrackAt(TrackLastBaked),Entry=Dest->TrackAt(TrackEntryBaked);
        Delta+=ToWorld(Now-Last)*Weight;
        if(Dest->Stem==TrackInstStem){TrackInstExpected+=ToWorld(Now-Last);InstPart+=ToWorld(Now-Last)*Weight;}
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
            if(FadeTrackStem==TrackInstStem){TrackInstExpected+=ToWorld(Now-Last)*(Dest&&Dest->Stem==TrackInstStem?0.f:1.f);InstPart+=ToWorld(Now-Last)*(1.f-Weight);}
            SourceOffset=FVector(Now.X-Entry.X,Now.Y-Entry.Y,0.f);
            FadeTrackLastBaked=FadeSourceSeconds;
        }
    }
    if(!Delta.IsNearlyZero(.001))
    {
        FVector Next=GetActorLocation()+Delta;
        const FVector Clamped=ClampArena(Next,RoamRadius());Next.X=Clamped.X;Next.Y=Clamped.Y;
        TrackTravelWorld+=Next-GetActorLocation();
        // The arena clamp scales what was asked for; the instance's share is scaled the same way.
        const double Asked=Delta.SizeSquared2D();
        if(Asked>1.e-6)TrackInstApplied+=InstPart*static_cast<float>(FVector::DotProduct(Next-GetActorLocation(),Delta)/Asked);
        if(Dest)PlaybackStats.FindOrAdd(PlaybackStatKey(Clip)).TravelWorld+=Next-GetActorLocation();
        SetActorLocation(Next);
    }
    ImportedPresentation->SetRootOffsets(DestOffset,SourceOffset);
}

void AVeyrDragon::CloseTrackInstance()
{
    if(TrackInstStem.IsNone())return;
    FPlaybackStat& S=PlaybackStats.FindOrAdd(TrackInstKey);
    const float Expected=static_cast<float>(TrackInstExpected.Size2D()),Applied=static_cast<float>(TrackInstApplied.Size2D());
    if(Expected>5.f*BodyScale)
    {
        const float Ratio=Applied/Expected;
        ++S.TrackInstances;S.TrackNetExpectedCm+=Expected;S.TrackNetAppliedCm+=Applied;
        S.TrackMinRatio=S.TrackMinRatio<0.f?Ratio:FMath::Min(S.TrackMinRatio,Ratio);S.TrackMaxRatio=FMath::Max(S.TrackMaxRatio,Ratio);
    }
    TrackInstStem=NAME_None;
}

void AVeyrDragon::UpdatePoseDeltaStat()
{
    // A pop is a discontinuity: one frame in which a bone moves much faster than in the frames either side of it.
    // Real motion (a claw accelerating into a strike) changes speed smoothly over several frames at 30-60 fps.
    // The pose read here is the last evaluated one, so the middle frame of the three is judged one tick late with the
    // clip key and blend flag it had then. Component space: actor travel and turns are excluded, root offsets are not.
    if(!ImportedPresentation)return;
    const TArray<FTransform>& Cs=ImportedPresentation->GetComponentSpaceTransforms();
    if(Cs.Num()==0)return;
    const float Dt=PoseClock<0.f?0.f:Clock-PoseClock;
    if(PoseClock>=0.f&&Dt<1.e-4f)return;
    const float Scale=ImportedPresentation->GetComponentScale().X;
    {
        // Yaw steps: a head or body turn of more than 20 degrees within one 30 Hz frame (600 deg/s) is a snap.
        const FVeyrVisualBoneTarget* HeadT=VisualDefinition?VisualDefinition->BoneTargets.Find(TEXT("head")):nullptr;
        const FVeyrVisualBoneTarget* NeckT=VisualDefinition?VisualDefinition->BoneTargets.Find(TEXT("gaze_neck")):nullptr;
        const FName Base=NeckT?ImportedPresentation->GetParentBone(NeckT->BoneName):NAME_None;
        if(HeadT&&!Base.IsNone()&&State!=EVeyrDragonState::Dead)
        {
            const FVector Line=ImportedPresentation->GetBoneLocation(HeadT->BoneName)-ImportedPresentation->GetBoneLocation(Base);
            const float HeadYaw=FMath::RadiansToDegrees(FMath::Atan2(static_cast<float>(Line.Y),static_cast<float>(Line.X)));
            const float BodyYaw=GetActorRotation().Yaw;
            const float YDt=YawPrevClock<0.f?0.f:Clock-YawPrevClock;
            const float Flat=static_cast<float>(FVector2D(Line.X,Line.Y).Size()/FMath::Max(1.,Line.Size()));
            if(bYawPrev&&YDt>1.e-4f&&Flat>.3f)
            {
                // Visible swing: yaw change scaled by how level the neck is (a neck pointing down turns its yaw freely).
                // Round 2: scaled by the less level of the two frames. A neck passing near vertical (Exposed, phase
                // 0.58) can turn its yaw by 60+ deg while the head moves little; the round-1 metric (current frame's
                // levelness only) counted that as a step and is still reported as yawStepsCurrentFlat.
                const float DYaw=FMath::Abs(FMath::FindDeltaAngleDegrees(YawPrevHead,HeadYaw))*(1.f/30.f)/YDt;
                const float H=DYaw*FMath::Min(Flat,YawPrevFlat);
                if(DYaw*Flat>20.f)++PlaybackStats.FindOrAdd(PlaybackStatKey(LastImportedClip)).YawStepsCurrentFlat;
                const float B=FMath::Abs(FMath::FindDeltaAngleDegrees(YawPrevBody,BodyYaw))*(1.f/30.f)/YDt;
                FPlaybackStat& St=PlaybackStats.FindOrAdd(PlaybackStatKey(LastImportedClip));
                if(H>St.MaxHeadYawPer30){St.MaxHeadYawPer30=H;St.MaxHeadYawPhase=ImportedPresentation->CurrentPhase;St.MaxHeadYawStateSeconds=StateElapsed;}
                St.MaxBodyYawPer30=FMath::Max(St.MaxBodyYawPer30,B);
                // Round 2 (coordinator 2026-11-19): a step inside the fight-feel hit reaction (the knight's blow swings the
                // downed head, -VeyrLegacyDownFlinch) is an intended reaction, counted apart as yawStepsInHitReaction.
                const AVeyrGameMode* FeelMode=GetWorld()?GetWorld()->GetAuthGameMode<AVeyrGameMode>():nullptr;
                const bool bReacting=FeelMode&&FeelMode->FightFeel&&FeelMode->FightFeel->FlinchDisplacesPose();
                if(H>20.f||B>20.f){if(bReacting)++St.YawStepsInHitReaction;else ++St.YawSteps;}
            }
            // Round 2 (critic F2): a head swing in pitch or roll (the fire ignition drops the head ~90 deg in 4 frames)
            // never shows in the yaw of the neck line. Head turn steps: the head bone's full world rotation change per
            // 30 Hz frame over 20 deg, outside hit reactions, at any levelness.
            FTransform HeadW;
            if(ImportedPresentation->GetBoneTargetWorldTransform(TEXT("head"),HeadW))
            {
                const FQuat Q=HeadW.GetRotation();
                if(bHeadTurnPrev&&YDt>1.e-4f)
                {
                    const float Turn=FMath::RadiansToDegrees(static_cast<float>(HeadTurnPrev.AngularDistance(Q)))*(1.f/30.f)/YDt;
                    FPlaybackStat& St=PlaybackStats.FindOrAdd(PlaybackStatKey(LastImportedClip));
                    const AVeyrGameMode* FeelMode=GetWorld()?GetWorld()->GetAuthGameMode<AVeyrGameMode>():nullptr;
                    const bool bReacting=FeelMode&&FeelMode->FightFeel&&FeelMode->FightFeel->FlinchDisplacesPose();
                    if(!bReacting){St.MaxHeadTurnPer30=FMath::Max(St.MaxHeadTurnPer30,Turn);if(Turn>20.f)++St.HeadTurnSteps;}
                }
                if(YDt>1.e-4f||!bHeadTurnPrev){HeadTurnPrev=Q;bHeadTurnPrev=true;}
            }
            if(YDt>1.e-4f||!bYawPrev){YawPrevHead=HeadYaw;YawPrevBody=BodyYaw;YawPrevClock=Clock;YawPrevFlat=Flat;bYawPrev=true;}
        }
    }
    TArray<float> Speed;
    if(PosePrevCs.Num()==Cs.Num()&&Dt>0.f)
    {
        Speed.SetNumUninitialized(Cs.Num());
        for(int32 B=0;B<Cs.Num();++B)Speed[B]=static_cast<float>(FVector::Dist(Cs[B].GetLocation(),PosePrevCs[B]))*Scale/Dt;
    }
    if(Speed.Num()&&PoseSpeed1.Num()==Speed.Num()&&PoseSpeed2.Num()==Speed.Num()&&!PoseKey1.IsNone())
    {
        constexpr float PopRatio=2.5f,FloorCms=60.f;
        float Worst=0.f;int32 WorstBone=INDEX_NONE;
        for(int32 B=0;B<Speed.Num();++B)
        {
            const float Mid=PoseSpeed1[B],Side=FMath::Max(PoseSpeed2[B],Speed[B]);
            if(Mid<FloorCms||Mid-Side<FloorCms)continue;
            const float Ratio=Mid/FMath::Max(Side,FloorCms*.5f);
            if(Ratio>Worst){Worst=Ratio;WorstBone=B;}
        }
        FPlaybackStat& St=PlaybackStats.FindOrAdd(PoseKey1);
        ++St.PoseFrames;
        if(bPoseBlend1)St.MaxPopRatioInBlend=FMath::Max(St.MaxPopRatioInBlend,Worst);
        if(Worst>St.MaxPopRatio){St.MaxPopRatio=Worst;if(WorstBone!=INDEX_NONE)St.WorstPopBone=ImportedPresentation->GetBoneName(WorstBone);}
        if(Worst>PopRatio){++St.Pops;if(bPoseBlend1)++St.PopsInBlend;}
    }
    PosePrevCs.SetNumUninitialized(Cs.Num());
    for(int32 B=0;B<Cs.Num();++B)PosePrevCs[B]=Cs[B].GetLocation();
    PoseSpeed2=MoveTemp(PoseSpeed1);PoseSpeed1=MoveTemp(Speed);PoseClock=Clock;
    PoseKey1=PlaybackStatKey(LastImportedClip);
    bPoseBlend1=(bImportedTransitionReady&&Clock-ImportedTransitionStarted<ImportedTransitionSeconds+1.f/30.f)||
        (bInertialBlend&&Clock-InertialStartedClock<InertialBlendSeconds+1.f/30.f);
}

void AVeyrDragon::ResetFootLock()
{
    for(FFootLockFoot& F:LockFeet)F=FFootLockFoot();
    if(ImportedPresentation)ImportedPresentation->ClearLegLocks();
}

void AVeyrDragon::UpdateFootLock(bool bFading)
{
    // Review M1: standing states only. Down (buckle, collapse, exposed, rise), dead or flying the clip's own feet play.
    const bool Standing=State==EVeyrDragonState::Idle||State==EVeyrDragonState::Reposition||State==EVeyrDragonState::Windup||
        State==EVeyrDragonState::Active||State==EVeyrDragonState::Recovery;
    const bool Measure=Playback.bLoaded&&Standing&&!IsDead()&&!IsAirborne()&&Move!=EVeyrDragonMove::FlyAway;
    const bool Eligible=bFootLock&&Measure;
    if(Measure&&!bFootLock)
    {
        // Evidence only (-VeyrNoFootLock): the clip's own planted-foot slide, nothing pinned.
        FVeyrSoleSample Anim;
        if(!ImportedPresentation->MeasureSoles(Anim)||!Anim.bValid)return;
        const float Dt=FootLockClock<0.f?0.f:FMath::Max(0.f,Clock-FootLockClock);
        if(Dt>0.f||FootLockClock<0.f)FootLockClock=Clock;
        FPlaybackStat& Stat=PlaybackStats.FindOrAdd(PlaybackStatKey(LastImportedClip));
        const FVector ActorNow=GetActorLocation();const FQuat ActorQuatNow=GetActorQuat();
        const FVector PivotPrev=bFootLockActorPrev?FootLockActorPrev:ActorNow;
        const FQuat TurnDelta=bFootLockActorPrev?ActorQuatNow*FootLockActorQuatPrev.Inverse():FQuat::Identity;
        FootLockActorPrev=ActorNow;FootLockActorQuatPrev=ActorQuatNow;bFootLockActorPrev=true;
        for(int32 L=0;L<4&&Dt>0.f;++L)
        {
            FFootLockFoot& F=LockFeet[L];
            const FVector Anchor=ImportedPresentation->GetBoneLocation(FName(GLegBones[L][2]));
            // Same "planted" as the lock's gate: low and still in the clip with the body's turn removed.
            const FVector Predicted=PivotPrev+TurnDelta.RotateVector(F.PrevTip-PivotPrev);
            const bool Slow=F.bHasPrev&&FVector::Dist2D(Anchor,Predicted)/Dt<Playback.FootLock.PlantSpeedCms*BodyScale;
            if(Anim.SoleAboveFloorCm[L]<Playback.FootLock.PlantHeightCm*BodyScale&&F.bHasPrev&&Slow)
            {Stat.PlantedSeconds[L]+=Dt;Stat.AnimatedSlideCm[L]+=FVector::Dist2D(Anchor,F.PrevTip);}
            F.PrevTip=Anchor;F.bHasPrev=true;
        }
        return;
    }
    // A teleport (showcase placement, restart) is not motion: drop the pins and the slide history at once.
    const FVector ActorNow=GetActorLocation();const FQuat ActorQuatNow=GetActorQuat();
    const bool Teleported=bFootLockActorPrev&&FVector::Dist2D(ActorNow,FootLockActorPrev)>250.f*BodyScale;
    // The plant test removes the body's TURN from the foot's world motion (rotate last frame's foot about last frame's
    // pivot by the actor's yaw change) but keeps its travel: a paw still in the clip under a turning body counts as
    // planted, and so does an in-place walk paw that stays put on the floor while the actor walks over it.
    const FVector PivotPrev=bFootLockActorPrev?FootLockActorPrev:ActorNow;
    const FQuat TurnDelta=bFootLockActorPrev?ActorQuatNow*FootLockActorQuatPrev.Inverse():FQuat::Identity;
    FootLockActorPrev=ActorNow;FootLockActorQuatPrev=ActorQuatNow;bFootLockActorPrev=true;
    if(Teleported)
    {
        ++FootLockTeleports;ResetFootLock();
        for(FFootLockFoot& F:LockFeet){F.bHasPrev=F.bHasPrevAny=F.bHasPrevLocal=false;}
        PoseSpeed1.Reset();PoseSpeed2.Reset();
        return;
    }
    bool AnyActive=false;for(const auto& F:LockFeet)AnyActive|=F.bLocked||F.bStepping||F.bReleasing;
    // Leaving the standing states (knock-down, death, flight) eases every held foot back to the clip over the release
    // time instead of dropping the IK in one frame (that drop was the leg pop at buckle).
    const bool ReleaseOnly=!Eligible&&bFootLock&&Playback.bLoaded&&AnyActive;
    if(!Eligible&&!ReleaseOnly)return;
    if(ReleaseOnly&&!bReleaseOnlyLast)++FootLockEaseOuts;
    bReleaseOnlyLast=ReleaseOnly;
    FVeyrSoleSample Anim;
    if(!ImportedPresentation->MeasureSoles(Anim)||!Anim.bValid){FootLockDiagnostic=TEXT("sole model unavailable");return;}
    const float Dt=FootLockClock<0.f?0.f:FMath::Max(0.f,Clock-FootLockClock);
    if(Dt>0.f||FootLockClock<0.f)FootLockClock=Clock;
    const FVeyrFootLockTuning& T=Playback.FootLock;
    const float S=BodyScale;
    FPlaybackStat& Stat=PlaybackStats.FindOrAdd(PlaybackStatKey(LastImportedClip));
    TArray<FVeyrLegLock> Locks;Locks.SetNum(4);
    bool AnyWeight=false;
    if(bProcSteps&&Dt>0.f&&!ReleaseOnly)
    {
        // Round 2: one foot at a time in gait order (HL, FL, HR, FR); a second foot only on the diagonal and only when
        // it is far out. Never two on one side. Side = L&1 (FL 0, FR 1, HL 2, HR 3).
        static const int32 Gait[4]={2,0,3,1};static const int32 Diagonal[4]={3,2,1,0};
        int32 Stepping=0,SteppingLeg=-1;bool SideBusy[2]={false,false};
        for(int32 L=0;L<4;++L){LockFeet[L].bStartStep=false;if(LockFeet[L].bStepping){++Stepping;SteppingLeg=L;SideBusy[L&1]=true;}}
        int32 NextGait=0;for(int32 G=0;G<4;++G)if(Gait[G]==ProcStepLastLeg)NextGait=Gait[(G+1)%4];
        int32 Best=-1;float BestScore=0.f;
        for(int32 L=0;L<4&&Stepping<2;++L)
        {
            FFootLockFoot& F=LockFeet[L];
            if(!F.bLocked||SideBusy[L&1])continue;
            const FVector Anchor=ImportedPresentation->GetBoneLocation(FName(GLegBones[L][2]));
            if(Anim.SoleAboveFloorCm[L]>T.ReleaseHeightCm*S)continue; // the clip lifts it itself
            const float Err=static_cast<float>(FVector::Dist2D(Anchor,F.Pin))/(T.StepTriggerCm*S);
            if(Err<1.f&&!F.bReachMiss)continue;
            if(Stepping==1&&(L!=Diagonal[SteppingLeg]||(Err<1.5f&&!F.bReachMiss)))continue;
            const float Score=Err+(F.bReachMiss?10.f:0.f)+(L==NextGait?.35f:0.f);
            if(Score>BestScore){BestScore=Score;Best=L;}
        }
        if(Best>=0){LockFeet[Best].bStartStep=true;if(Stepping==1)++ProcStepPairs;}
        for(int32 L=0;L<4;++L)
        {
            // The foot's drift: where the clip puts it moves with the body (turn and travel); land ahead of it.
            // Fixed when the step starts (a lead re-estimated every frame made the landing jitter).
            FFootLockFoot& F=LockFeet[L];
            if(!F.bStartStep&&!F.bReachMiss)continue;
            const FVector Anchor=ImportedPresentation->GetBoneLocation(FName(GLegBones[L][2]));
            const FVector Vel=F.bHasPrev?(Anchor-F.PrevTip)/Dt:FVector::ZeroVector;
            F.Lead=(FVector(Vel.X,Vel.Y,0.)*T.StepLeadSeconds).GetClampedToMaxSize(T.StepTriggerCm*S*1.5f);
        }
    }
    for(int32 L=0;L<4;++L)
    {
        FFootLockFoot& F=LockFeet[L];
        // Review H3: the pin is a foot-fixed anchor (the wrist/hock end bone), not whichever sole point is lowest this
        // frame, so a paw rolling heel to toe is not translated by a foot length. The sole only answers "how high".
        const FVector Anchor=ImportedPresentation->GetBoneLocation(FName(GLegBones[L][2]));
        const float Height=Anim.SoleAboveFloorCm[L];
        if(ReleaseOnly&&(F.bLocked||F.bStepping)){F.bLocked=F.bStepping=false;F.bReleasing=true;F.T=0.f;F.From=F.Target;}
        // Foot speed with the body's turn removed (see above). World speed kept turning paws from ever planting.
        const FVector Predicted=PivotPrev+TurnDelta.RotateVector(F.PrevTip-PivotPrev);
        if(Dt>0.f)
        {
            const float Speed=F.bHasPrev?static_cast<float>(FVector::Dist2D(Anchor,Predicted))/Dt:0.f;
            if(F.bLocked&&bProcSteps)
            {
                if(Height>T.ReleaseHeightCm*S){F.bLocked=false;F.bReleasing=true;F.T=0.f;F.From=F.Pin;}
                else if(F.bStartStep||F.bReachMiss)
                {F.bLocked=false;F.bStepping=true;F.bProcStep=true;F.T=0.f;F.From=F.Pin;++Stat.Steps;++ProcStepCount;ProcStepLastLeg=L;}
                F.bStartStep=F.bReachMiss=false;
            }
            else if(F.bLocked)
            {
                const float Drag=static_cast<float>(FVector::Dist2D(F.Pin,Anchor));
                // Lifting in the clip releases. Dragged near the floor (body turn or travel) always takes the lifted step:
                // a flat release there slid the paw 30 cm along the floor in 0.12 s (TurnLeft 557 cm/s, package 5).
                if(Height>T.ReleaseHeightCm*S)
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
                F.T+=Dt/FMath::Max(.05f,F.bProcStep?T.ProcStepSeconds:T.StepSeconds);
                if(F.T>=1.f)
                {
                    F.bStepping=false;F.bLocked=Height<T.PlantHeightCm*S;
                    // A procedural step plants where it landed (its lead included), so the drift has room again.
                    F.Pin=F.bProcStep?FVector(Anchor.X+F.Lead.X,Anchor.Y+F.Lead.Y,Anchor.Z):Anchor;
                    // Landing off the floor (the clip lifted the paw meanwhile): ease back to the clip, no snap.
                    if(F.bProcStep&&!F.bLocked&&!F.Lead.IsNearlyZero()){F.bReleasing=true;F.T=0.f;F.From=F.Pin;}
                    F.bProcStep=false;
                }
            }
            else if(F.bReleasing)
            {
                F.T+=Dt/FMath::Max(.02f,T.ReleaseSeconds);
                if(F.T>=1.f)F.bReleasing=false;
            }
            // A foot plants only when it is low AND slow in the clip (bFading only marks evidence).
            const bool Slow=Speed<T.PlantSpeedCms*S;
            if(!ReleaseOnly&&!F.bLocked&&!F.bStepping&&!F.bReleasing&&Height<T.PlantHeightCm*S&&Slow)
            {F.bLocked=true;F.bReleasing=false;F.Pin=Anchor;}
            // Planted = low in the clip and not in a lock step (a stepping paw is lifted on purpose).
            // The gate's "planted" = low AND still in the clip (with the turn removed): a paw the clip sweeps along the
            // floor is a moving paw, not a planted one. Lock steps are excluded (lifted on purpose).
            F.bLowNow=!ReleaseOnly&&!F.bStepping&&Height<T.PlantHeightCm*S&&(Slow||F.bLocked);
            if(F.bLowNow&&F.bHasPrev)
            {Stat.PlantedSeconds[L]+=Dt;Stat.AnimatedSlideCm[L]+=FVector::Dist2D(Anchor,F.PrevTip);}
            F.PrevTip=Anchor;F.bHasPrev=true;
        }
        FVector Goal=Anchor;float Weight=0.f;
        if(F.bLocked){Goal=FVector(F.Pin.X,F.Pin.Y,Anchor.Z);Weight=1.f;}
        else if(F.bStepping)
        {
            const float U=SmoothStep01(F.T);
            const FVector Land=F.bProcStep?Anchor+F.Lead:Anchor;
            Goal=FMath::Lerp(F.From,Land,U);Goal.Z=Anchor.Z+FMath::Sin(PI*FMath::Clamp(F.T,0.f,1.f))*T.StepLiftCm*S;Weight=1.f;
        }
        else if(F.bReleasing){Goal=FMath::Lerp(F.From,Anchor,SmoothStep01(F.T));Goal.Z=Anchor.Z;Weight=1.f;}
        F.Target=Goal;F.Weight=Weight;AnyWeight|=Weight>0.f&&!Goal.Equals(Anchor,.05);
        FVeyrLegLock& Lock=Locks[L];
        for(int32 J=0;J<3;++J)Lock.Bones[J]=FName(GLegBones[L][J]);
        // Review H2: the front paws' toe bones hang off the elbow beside the end bone; they ride the end bone.
        if(GLegRiders[L])Lock.Riders[0]=FName(GLegRiders[L]);
        Lock.Delta=ImportedPresentation->GetComponentTransform().InverseTransformVector(Goal-Anchor);
        Lock.Weight=Weight;
    }
    // Review L4: nothing pinned this frame -> no second evaluation (the pose was sampled unlocked).
    auto DrawnPlanted=[&]()
    {
        for(int32 L=0;L<4;++L)
        {
            FFootLockFoot& F=LockFeet[L];
            const FVector Drawn=ImportedPresentation->GetBoneLocation(FName(GLegBones[L][2]));
            if(Dt>0.f&&F.bLowNow&&F.bHasPrevAny)
            {
                Stat.DrawnPlantedSlideCm[L]+=FVector::Dist2D(Drawn,F.PrevAny);
                const int32 K=F.bLocked?0:F.bReleasing?1:2;Stat.PlantedByState[L][K]+=Dt;Stat.SlideByState[L][K]+=FVector::Dist2D(Drawn,F.PrevAny);
            }
            if(Dt>0.f||!F.bHasPrevAny){F.PrevAny=Drawn;F.bHasPrevAny=true;}
        }
    };
    if(!AnyWeight){for(FFootLockFoot& F:LockFeet)F.PrevDrawn=FVector::ZeroVector;DrawnPlanted();return;}
    if(!ImportedPresentation->SetLegLocks(Locks)){FootLockDiagnostic=ImportedPresentation->LastError;return;}
    const FString LockError=ImportedPresentation->GetLegLockError();
    if(!LockError.IsEmpty())FootLockDiagnostic=LockError;
    DrawnPlanted();
    for(float Miss:ImportedPresentation->GetLegLockMissCm())
        Stat.MaxIkMissCm=FMath::Max(Stat.MaxIkMissCm,Miss*static_cast<float>(ImportedPresentation->GetComponentTransform().GetScale3D().GetAbsMax()));
    if(Dt>0.f)
        for(int32 L=0;L<4;++L)
        {
            FFootLockFoot& F=LockFeet[L];
            const FVector Drawn=ImportedPresentation->GetBoneLocation(FName(GLegBones[L][2]));
            if(F.bLocked&&!F.PrevDrawn.IsZero()){Stat.DrawnSlideCm[L]+=FVector::Dist2D(Drawn,F.PrevDrawn);Stat.LockedSeconds[L]+=Dt;}
            // Out of reach: the leg cannot hold the pin any more (a fast turn swings the hip away), so the drawn paw is
            // being dragged. Step now from where the paw really is instead of sliding it until the drag threshold.
            if(F.bLocked&&bProcSteps&&FVector::Dist2D(Drawn,F.Pin)>3.f*BodyScale)F.bReachMiss=true; // stepped next frame
            else if(F.bLocked&&FVector::Dist2D(Drawn,F.Pin)>3.f*BodyScale)
            {F.bLocked=false;F.bStepping=true;F.T=0.f;F.From=FVector(Drawn.X,Drawn.Y,F.Pin.Z);++Stat.Steps;++FootLockReachSteps;}
            F.PrevDrawn=F.bLocked?Drawn:FVector::ZeroVector;
        }
}

bool AVeyrDragon::IsFootLockStepping(int32 Leg) const
{
    return Leg>=0&&Leg<4&&bFootLock&&LockFeet[Leg].bStepping;
}

float AVeyrDragon::PlaybackAttackPhaseSeconds(EVeyrDragonMove Attack,int32 Leg,const TCHAR* Phase,float Fallback) const
{
    if(!bClipTempo||Attack==EVeyrDragonMove::FlyAway)return Fallback;
    float W=0.f,A=0.f,R=0.f,D=0.f;
    BaseAttackTiming(Attack,Leg,W,A,R,D);
    return FCString::Strcmp(Phase,TEXT("Windup"))==0?W:FCString::Strcmp(Phase,TEXT("Active"))==0?A:FCString::Strcmp(Phase,TEXT("Recovery"))==0?R:Fallback;
}

TSharedPtr<FJsonObject> AVeyrDragon::PlaybackEvidence() const
{
    TSharedPtr<FJsonObject> O=MakeShared<FJsonObject>();
    O->SetBoolField(TEXT("clipTempo"),bClipTempo);O->SetBoolField(TEXT("twoClipBlend"),bTwoClipBlend);
    O->SetBoolField(TEXT("footLock"),bFootLock);O->SetBoolField(TEXT("slowSnapTurn"),bSlowSnapTurn);O->SetBoolField(TEXT("rootTracks"),bRootTracks);O->SetBoolField(TEXT("riseRootTrack"),bRootTracks&&!FParse::Param(FCommandLine::Get(),TEXT("VeyrNoRiseRootTrack")));
    O->SetStringField(TEXT("data"),PlaybackDiagnostic);O->SetStringField(TEXT("footLockDiagnostic"),FootLockDiagnostic);
    O->SetNumberField(TEXT("snapTrackRateDps"),SnapTrackRate());O->SetNumberField(TEXT("walkStrideSpeedCmPerSec"),WalkStrideSpeedCm);O->SetNumberField(TEXT("walkRate"),TempoWalkRate());O->SetNumberField(TEXT("walkGroundSpeedCmPerSec"),TempoWalkBaseSpeed()*TempoWalkRate());
    O->SetNumberField(TEXT("trackTravelWorldCm"),TrackTravelWorld.Size2D());
    O->SetNumberField(TEXT("footLockTeleports"),FootLockTeleports);O->SetNumberField(TEXT("footLockEaseOuts"),FootLockEaseOuts);
    O->SetNumberField(TEXT("footLockReachSteps"),FootLockReachSteps);
    O->SetBoolField(TEXT("inertialBlend"),bInertialBlend);
    O->SetBoolField(TEXT("headYawLimit"),bHeadYawLimit);O->SetNumberField(TEXT("headYawMaxDps"),HeadYawMaxDps);
    O->SetNumberField(TEXT("headYawLimitedFrames"),HeadYawLimitedFrames);O->SetNumberField(TEXT("headYawMaxCorrectionDeg"),HeadYawMaxCorr);
    O->SetBoolField(TEXT("proceduralSteps"),bProcSteps);O->SetNumberField(TEXT("proceduralStepCount"),ProcStepCount);
    O->SetNumberField(TEXT("proceduralStepDiagonalPairs"),ProcStepPairs);O->SetNumberField(TEXT("stepCarryDps"),Playback.FootLock.CarryDps);
    if(ImportedPresentation){int32 Starts=0;float Deg=0.f,Cm=0.f;ImportedPresentation->GetInertialStats(Starts,Deg,Cm);
        O->SetNumberField(TEXT("inertialStarts"),Starts);O->SetNumberField(TEXT("inertialMaxOffsetDegrees"),Deg);O->SetNumberField(TEXT("inertialMaxOffsetCm"),Cm);}
    O->SetStringField(TEXT("dragonSkin"),ImportedPresentation?ImportedPresentation->SkinDiagnostic:FString(TEXT("no presentation")));
    int32 YawSteps=0,YawStepsCurrentFlat=0,YawStepsInHitReaction=0,HeadTurnSteps=0;float WorstTurn=0.f;FString WorstTurnKey;float WorstYaw=0.f;FString WorstYawKey;
    float WorstRate=0.f,WorstSlide=0.f,WorstPop=0.f;FString WorstRateKey,WorstSlideKey,WorstPopKey;int32 Pops=0,PopsInBlend=0;
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
            F->SetNumberField(TEXT("plantedSeconds"),S.PlantedSeconds[L]);F->SetNumberField(TEXT("lockedSeconds"),S.LockedSeconds[L]);
            F->SetNumberField(TEXT("drawnSlideCmPerLockedSec"),S.LockedSeconds[L]>0?S.DrawnSlideCm[L]/S.LockedSeconds[L]:0.);
            const double Animated=S.PlantedSeconds[L]>0?S.AnimatedSlideCm[L]/S.PlantedSeconds[L]:0.,Drawn=S.PlantedSeconds[L]>0?S.DrawnSlideCm[L]/S.PlantedSeconds[L]:0.;
            F->SetNumberField(TEXT("animatedSlideCmPerSec"),Animated);F->SetNumberField(TEXT("drawnSlideCmPerSec"),Drawn);
            const double DrawnAll=S.PlantedSeconds[L]>0?S.DrawnPlantedSlideCm[L]/S.PlantedSeconds[L]:0.;
            F->SetNumberField(TEXT("drawnPlantedSlideCmPerSec"),DrawnAll);
            for(int32 K=0;K<3;++K)
            {
                static const TCHAR* Names[3]={TEXT("Locked"),TEXT("Releasing"),TEXT("Free")};
                F->SetNumberField(FString(TEXT("planted"))+Names[K]+TEXT("Seconds"),S.PlantedByState[L][K]);
                F->SetNumberField(FString(TEXT("slide"))+Names[K]+TEXT("Cm"),S.SlideByState[L][K]);
            }
            Feet->SetObjectField(GLegNames[L],F);
            // Gate number: drawn end-bone travel over every low-foot frame (locked, stepping or free) per low second.
            if(S.PlantedSeconds[L]>.2)MoveWorst=FMath::Max(MoveWorst,static_cast<float>(bFootLock?DrawnAll:Animated));
        }
        C->SetObjectField(TEXT("feet"),Feet);C->SetNumberField(TEXT("worstPlantedSlideCmPerSec"),MoveWorst);
        C->SetNumberField(TEXT("steps"),S.Steps);C->SetNumberField(TEXT("slips"),S.Slips);C->SetNumberField(TEXT("maxIkMissCm"),S.MaxIkMissCm);
        C->SetNumberField(TEXT("travelWorldCm"),S.TravelWorld.Size2D());C->SetNumberField(TEXT("trackPathWorldCm"),S.TrackLengthCm);
        C->SetNumberField(TEXT("trackInstances"),S.TrackInstances);C->SetNumberField(TEXT("trackNetExpectedCm"),S.TrackNetExpectedCm);
        C->SetNumberField(TEXT("trackNetAppliedCm"),S.TrackNetAppliedCm);C->SetNumberField(TEXT("trackMinRatio"),S.TrackMinRatio);C->SetNumberField(TEXT("trackMaxRatio"),S.TrackMaxRatio);
        C->SetNumberField(TEXT("poseFrames"),S.PoseFrames);C->SetNumberField(TEXT("pops"),S.Pops);C->SetNumberField(TEXT("popsInBlend"),S.PopsInBlend);
        C->SetNumberField(TEXT("maxPopRatio"),S.MaxPopRatio);C->SetNumberField(TEXT("maxPopRatioInBlend"),S.MaxPopRatioInBlend);
        C->SetNumberField(TEXT("yawSteps"),S.YawSteps);C->SetNumberField(TEXT("yawStepsInHitReaction"),S.YawStepsInHitReaction);C->SetNumberField(TEXT("headTurnSteps"),S.HeadTurnSteps);C->SetNumberField(TEXT("maxHeadTurnDegPer30Hz"),S.MaxHeadTurnPer30);C->SetNumberField(TEXT("maxHeadYawDegPer30Hz"),S.MaxHeadYawPer30);C->SetNumberField(TEXT("maxBodyYawDegPer30Hz"),S.MaxBodyYawPer30);
        C->SetNumberField(TEXT("maxHeadYawClipPhase"),S.MaxHeadYawPhase);C->SetNumberField(TEXT("maxHeadYawStateSeconds"),S.MaxHeadYawStateSeconds);
        YawSteps+=S.YawSteps;YawStepsCurrentFlat+=S.YawStepsCurrentFlat;YawStepsInHitReaction+=S.YawStepsInHitReaction;HeadTurnSteps+=S.HeadTurnSteps;if(S.MaxHeadTurnPer30>WorstTurn){WorstTurn=S.MaxHeadTurnPer30;WorstTurnKey=E.Key.ToString();}if(S.MaxHeadYawPer30>WorstYaw){WorstYaw=S.MaxHeadYawPer30;WorstYawKey=E.Key.ToString();}
        C->SetStringField(TEXT("worstPopBone"),S.WorstPopBone.ToString());
        Pops+=S.Pops;PopsInBlend+=S.PopsInBlend;
        if(S.MaxPopRatio>WorstPop){WorstPop=S.MaxPopRatio;WorstPopKey=E.Key.ToString()+TEXT(" ")+S.WorstPopBone.ToString();}
        Clips->SetObjectField(E.Key.ToString(),C);
        if(S.MaxRateNonHold>WorstRate&&S.Frames>3){WorstRate=S.MaxRateNonHold;WorstRateKey=E.Key.ToString();}
        if(MoveWorst>WorstSlide){WorstSlide=MoveWorst;WorstSlideKey=E.Key.ToString();}
    }
    O->SetObjectField(TEXT("clips"),Clips);
    O->SetNumberField(TEXT("worstFrameSourceRateOutsideHolds"),WorstRate);O->SetStringField(TEXT("worstRateClip"),WorstRateKey);
    O->SetNumberField(TEXT("worstPlantedSlideCmPerSec"),WorstSlide);O->SetStringField(TEXT("worstSlideClip"),WorstSlideKey);
    O->SetNumberField(TEXT("poseDeltaPops"),Pops);O->SetNumberField(TEXT("poseDeltaPopsInBlend"),PopsInBlend);
    O->SetNumberField(TEXT("worstPopRatio"),WorstPop);O->SetStringField(TEXT("worstPopClipBone"),WorstPopKey);
    O->SetBoolField(TEXT("gateNoBlendPops"),PopsInBlend==0);
    O->SetNumberField(TEXT("yawSteps"),YawSteps);O->SetNumberField(TEXT("yawStepsCurrentFlat"),YawStepsCurrentFlat);O->SetNumberField(TEXT("yawStepsInHitReaction"),YawStepsInHitReaction);O->SetNumberField(TEXT("headTurnSteps"),HeadTurnSteps);O->SetNumberField(TEXT("worstHeadTurnDegPer30Hz"),WorstTurn);O->SetStringField(TEXT("worstHeadTurnClip"),WorstTurnKey);O->SetNumberField(TEXT("yawStepsAll"),YawSteps+YawStepsInHitReaction);O->SetNumberField(TEXT("worstHeadYawDegPer30Hz"),WorstYaw);O->SetStringField(TEXT("worstHeadYawClip"),WorstYawKey);
    O->SetBoolField(TEXT("gateRateAtMost1_25"),WorstRate<=1.25f+.02f);O->SetBoolField(TEXT("gateSlideUnder5"),WorstSlide<5.f);
    return O;
}
