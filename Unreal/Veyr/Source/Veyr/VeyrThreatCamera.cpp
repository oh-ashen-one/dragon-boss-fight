#include "VeyrKnight.h"
#include "VeyrDragon.h"
#include "Camera/CameraComponent.h"
#include "Components/CapsuleComponent.h"
#include "GameFramework/SpringArmComponent.h"
#include "Engine/GameViewportClient.h"
#include "Engine/World.h"

void AVeyrKnight::UpdateThreatCameraOptics(float Dt,const FRotator& Look)
{
    bThreatFramingActive=false;
    if(!bThreatCameraFraming)return;
    const bool Auto=bLockedOn&&IsValid(Boss)&&ManualCameraRemaining<=0.f;
    // Keep manual input authoritative. Do not move the lens under a manual pan.
    if(ManualCameraRemaining>0.f)return;
    const bool FollowFall=Auto&&Boss->IsDead()&&Boss->GetStateElapsed()<=Boss->GetStateDuration()+1.1f;
    if(FollowFall)return;
    const bool Flight=Auto&&Boss->Move==EVeyrDragonMove::FlyAway&&
        (Boss->State==EVeyrDragonState::Windup||Boss->State==EVeyrDragonState::Active||Boss->State==EVeyrDragonState::Recovery);
    bThreatFramingActive=Auto&&!Boss->IsDead()&&(Flight||Boss->IsAirborne()||Boss->State==EVeyrDragonState::Rise);
    ThreatFitCooldown=FMath::Max(0.f,ThreatFitCooldown-Dt);
    if(!bThreatFramingActive)
    {ThreatTargetArm=560.f;ThreatTargetFOV=72.f;ThreatFitCooldown=0.f;bThreatFitFound=false;}
    else if(ThreatFitCooldown<=0.f)
    {
        ThreatFitCooldown=.08f;
        FVector2D Size(16,9);if(GetWorld()->GetGameViewport())GetWorld()->GetGameViewport()->GetViewportSize(Size);
        const float Aspect=Size.Y>1?float(Size.X/Size.Y):16.f/9.f;
        const FVector Feet=GetFootLocation();
        const FVector Points[]={Feet,Feet+FVector(0,0,GetCapsuleComponent()->GetScaledCapsuleHalfHeight()*2),Boss->GetHeadLocation()+FVector(0,0,80)};
        struct FCandidate{float Arm,FOV,Cost;FVector Pivot,Origin;};TArray<FCandidate> Candidates;
        for(float Arm=560.f;Arm<=1600.f;Arm+=80.f)for(float FOV:{72.f,78.f,84.f,90.f,94.f})
        {
            const float H=FMath::Tan(FMath::DegreesToRadians(FOV*.5f)),V=H/FMath::Max(.5f,Aspect);
            const float Pitch=FMath::Clamp(FMath::RadiansToDegrees(FMath::Atan(V))-FMath::RadiansToDegrees(FMath::Atan2(90.f,Arm))-3.5f,-5.f,25.f);
            const FRotator Rotation(Pitch,Look.Yaw,0);const FRotationMatrix Basis(Rotation);
            const FVector Forward=Basis.GetUnitAxis(EAxis::X),Right=Basis.GetUnitAxis(EAxis::Y),Up=Basis.GetUnitAxis(EAxis::Z);
            const float R=FMath::DegreesToRadians(Pitch);
            const FVector Pivot=Feet+FVector(0,0,FMath::Max(170.f,90.f+Arm*FMath::Sin(R)-12.f*FMath::Cos(R)));
            const float Shoulder=FMath::GetMappedRangeValueClamped(FVector2D(15,68),FVector2D(42,180),Pitch);
            const FVector Origin=Pivot-Forward*Arm+Right*Shoulder+Up*12.f;
            bool Fits=true;
            for(const FVector& Point:Points)
            {
                const FVector D=Point-Origin;const double Z=FVector::DotProduct(D,Forward);
                if(Z<=1.f||FMath::Abs(FVector::DotProduct(D,Right)/(Z*H))>.88||FMath::Abs(FVector::DotProduct(D,Up)/(Z*V))>.88){Fits=false;break;}
            }
            if(Fits)Candidates.Add({Arm,FOV,FMath::Square((Arm-560.f)/560.f)+.7f*FMath::Square((FOV-72.f)/22.f),Pivot,Origin});
        }
        Candidates.Sort([](const FCandidate& A,const FCandidate& B){return A.Cost<B.Cost;});
        FCollisionQueryParams Query(SCENE_QUERY_STAT(VeyrThreatCameraFit),false,this);
        bThreatFitFound=false;
        for(const FCandidate& Candidate:Candidates)
        {
            FHitResult Hit;
            if(GetWorld()->SweepSingleByChannel(Hit,Candidate.Pivot,Candidate.Origin,FQuat::Identity,ECC_Camera,FCollisionShape::MakeSphere(CameraBoom->ProbeSize),Query))continue;
            ThreatTargetArm=Candidate.Arm;ThreatTargetFOV=Candidate.FOV;bThreatFitFound=true;break;
        }
        // A wall is not permission to pass the camera through it. Keep the
        // current collision-resolved view and expose failure in QA evidence.
        if(!bThreatFitFound){ThreatTargetArm=560.f;ThreatTargetFOV=72.f;}
    }
    ThreatCameraArm=FMath::FInterpTo(ThreatCameraArm,ThreatTargetArm,Dt,ThreatTargetArm>ThreatCameraArm?8.f:3.f);
    ThreatCameraFOV=FMath::FInterpTo(ThreatCameraFOV,ThreatTargetFOV,Dt,ThreatTargetFOV>ThreatCameraFOV?8.f:3.f);
}
