#include "VeyrKnight.h"
#include "VeyrBoneRoles.h"
#include "VeyrSkeletalPresentation.h"

// Quality goal E (2026-11-19): Greystone foot lock. Paragon's feet stay 1-4 cm above the floor through stances and
// short steps, so a 0.10 s cross-fade (or the capsule accelerating out of a stance) drags a planted foot. This holds a
// planted foot at its world position and lets it go only when the playing clip lifts it, or when holding it would
// stretch the leg (reach limit), in which case the foot takes a short stepped blend-out instead of a slide.
//
// Plant detection uses Greystone's own foot bones in the playing (raw, pre-IK) pose: ball (left/right_foot target)
// and ankle heights above the floor and the raw ball's world speed. Nothing here uses the KnightB boot calibration.
// -VeyrGreystoneNoFootLock turns it off; -VeyrGreystoneFeet runs the KnightB clean-up instead (VeyrKnight.cpp).
namespace
{
    // Greystone at 244 cm: idle ball 3.5-4.0 cm, idle ankle 14.8-15.1 cm above the floor (trial proof, 2026-11-19).
    constexpr float PlantBallCm=7.f, PlantAnkleCm=21.f;     // at or below: the clip has the foot on the floor
    constexpr float LiftBallCm=10.f, LiftAnkleCm=25.f;      // above: the clip lifts the foot (release, no slide)
    constexpr float PlantSpeedCmPerSecond=40.f;             // a foot the clip itself holds still
    constexpr float ReachCm=25.f;                           // held foot further than this from the clip's foot: step
    constexpr float SettleCm=6.f;                           // clip holds its foot still this far away: step to it
    constexpr float ReleaseSeconds=.12f;                    // blend-out time (smoothstep)
    constexpr float StepLiftMinCm=4.f, StepLiftMaxCm=10.f;  // arc for a foot released while still on the floor
}

bool AVeyrKnight::UpdateGreystoneFootLock(float DeltaSeconds)
{
    if(!ImportedPresentation||!ImportedPresentation->bPoseEvaluated)return true;
    const bool NewTransition=ProofTransitionSerial!=GreystoneLockSerial;GreystoneLockSerial=ProofTransitionSerial;
    const bool Fading=bProofBlendActive||NewTransition;
    if(DeltaSeconds<=0.f||DeltaSeconds>.1f||!IsGrounded())
    {
        for(auto& F:GreystoneFeet)F=FGreystoneFootLock();
        return true;
    }
    const float Floor=GetFootLocation().Z;
    const TCHAR* ToeNames[2]={TEXT("left_foot"),TEXT("right_foot")};
    const FName AnkleNames[2]={VeyrBoneRoles::Resolve(ImportedPresentation,EVeyrBoneRole::LeftAnkle),VeyrBoneRoles::Resolve(ImportedPresentation,EVeyrBoneRole::RightAnkle)};
    TArray<FTransform> Targets;TArray<float> Weights;bool Any=false;
    for(int32 Side=0;Side<2;++Side)
    {
        FGreystoneFootLock& F=GreystoneFeet[Side];
        FTransform ToeT;
        if(!ImportedPresentation->GetBoneTargetWorldTransform(ToeNames[Side],ToeT)||ImportedPresentation->GetBoneIndex(AnkleNames[Side])==INDEX_NONE)
        {F=FGreystoneFootLock();Targets.Add(FTransform::Identity);Weights.Add(0.f);continue;}
        const FVector RawToe=ToeT.GetLocation();
        // Bone, not socket: GetSocketTransform prefers a mesh socket of the same name, and Paragon meshes carry
        // sockets on their foot bones (the KnightB clean-up's GetSocketTransform turned Greystone's feet by
        // ~140 degrees, trial proof 2026-11-19T10:26). The IK target is the ankle's own component-space pose.
        const int32 AnkleIndex=ImportedPresentation->GetBoneIndex(AnkleNames[Side]);
        const FTransform AnkleCS=ImportedPresentation->GetBoneTransform(AnkleIndex,FTransform::Identity);
        const FTransform RawAnkle=AnkleCS*ImportedPresentation->GetComponentTransform();
        const float BallH=RawToe.Z-Floor,AnkleH=RawAnkle.GetLocation().Z-Floor;
        const float RawSpeed=F.bHasPrevious?FVector::Dist2D(RawToe,F.PreviousRawToe)/DeltaSeconds:0.f;
        F.PreviousRawToe=RawToe;F.bHasPrevious=true;
        const bool Low=BallH<=PlantBallCm&&AnkleH<=PlantAnkleCm;
        const bool Lifted=BallH>LiftBallCm||AnkleH>LiftAnkleCm;
        if(Lifted)F.bWasLifted=true;
        if(F.bLocked&&!F.bReleasing)
        {
            const float Reach=FVector::Dist2D(F.Anchor,RawToe);
            // Outside a cross-fade, a clip that holds its foot still somewhere else has re-planted it there (no stale
            // anchors: the foot steps over instead of hovering where an earlier clip put it).
            const bool Replanted=!Fading&&RawSpeed<PlantSpeedCmPerSecond&&Reach>SettleCm;
            if(Lifted||Reach>ReachCm||Replanted)
            {
                F.bReleasing=true;F.ReleaseSeconds=0.f;
                // Clip lifts it: the offset is absorbed in the air. Still on the floor: a small step, not a slide.
                F.ReleaseLiftCm=Lifted?0.f:FMath::Clamp(Reach*.5f,StepLiftMinCm,StepLiftMaxCm);
                F.bWasLifted=Lifted;
            }
        }
        // Engage on a foot the clip plants (low and still), or on any low foot when a cross-fade starts or runs;
        // after a stepped release the foot must have been lifted or come to rest before it can lock again.
        if(!F.bLocked&&Low&&(RawSpeed<PlantSpeedCmPerSecond||(Fading&&F.bWasLifted)))
        {
            F.bLocked=true;F.bReleasing=false;F.Anchor=RawToe;F.Weight=1.f;F.bWasLifted=false;
        }
        if(!F.bLocked){F.Weight=0.f;Targets.Add(FTransform::Identity);Weights.Add(0.f);continue;}
        FVector Desired=F.Anchor;
        if(F.bReleasing)
        {
            F.ReleaseSeconds+=DeltaSeconds;
            const float U=FMath::Clamp(F.ReleaseSeconds/ReleaseSeconds,0.f,1.f),S=FMath::SmoothStep(0.f,1.f,U);
            Desired=FMath::Lerp(F.Anchor,RawToe,S);
            Desired.Z=FMath::Lerp(F.Anchor.Z,RawToe.Z,S)+F.ReleaseLiftCm*FMath::Sin(PI*U);
            F.Weight=1.f-S;
            if(U>=1.f){F.bLocked=F.bReleasing=false;F.Weight=0.f;Targets.Add(FTransform::Identity);Weights.Add(0.f);continue;}
        }
        else Desired.Z=FMath::Max(F.Anchor.Z,RawToe.Z); // a held foot may roll up onto the toe, never sink
        FTransform Target=AnkleCS;Target.AddToTranslation(ImportedPresentation->GetComponentTransform().InverseTransformVector(Desired-RawToe));
        Targets.Add(Target);Weights.Add(1.f);Any=true;
    }
    if(!Any)return true;
    return ImportedPresentation->SetComponentSpaceFootTargets(Targets,Weights);
}
