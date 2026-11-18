// Phase D (2026-11-18): the knight's camera for a giant dragon.
//
// The dragon is 6x the knight's height at 2x scale and grows with -VeyrDragonScale, so framing is a camera job:
// - lock-on aims at the chest and slides toward the attacking limb through its wind-up, fitting the pitch so the
//   knight's feet stay in frame and widening the lens / lengthening the arm only as far as the aim point needs;
// - under the belly it looks out toward the head (where bites, fire and the takeoff come from);
// - the mouse looks around the lock instead of dropping it;
// - D2 "life": position lag, pull-back and a wider lens at a sprint, sideways lead, a small lean into turns and a nod
//   on hard stops, strongest free-running and damped while locked on.
// Every distance and angle is a function of S = BodyScale / 2 (1 at the shipped 2x). Lens is authored as a vertical
// field of view and converted with the viewport's aspect. Switches: -VeyrLegacyFraming (whole camera),
// -VeyrNoCameraLife, -VeyrLegacyLockMouse, -VeyrNoStrikeFraming, -VeyrNoBellyFraming; tuning: -VeyrCameraLife=,
// -VeyrCamArm=, -VeyrCamVFov=, -VeyrCamPivot=.
#include "VeyrKnight.h"
#include "VeyrDragon.h"
#include "Camera/CameraComponent.h"
#include "Components/CapsuleComponent.h"
#include "Engine/GameViewportClient.h"
#include "Engine/World.h"
#include "GameFramework/Controller.h"
#include "GameFramework/SpringArmComponent.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"

namespace
{
    float Smooth(float A,float B,float X){return FMath::SmoothStep(A,B,X);}
    float Deg(double Radians){return static_cast<float>(FMath::RadiansToDegrees(Radians));}
}

void AVeyrKnight::InitGiantCamera()
{
    const TCHAR* Cmd=FCommandLine::Get();
    bGiantCamera=!FParse::Param(Cmd,TEXT("VeyrLegacyFraming"));
    bCameraLife=bGiantCamera&&!FParse::Param(Cmd,TEXT("VeyrNoCameraLife"));
    bLegacyLockMouse=FParse::Param(Cmd,TEXT("VeyrLegacyLockMouse"));
    bStrikeFraming=!FParse::Param(Cmd,TEXT("VeyrNoStrikeFraming"));
    bBellyFraming=!FParse::Param(Cmd,TEXT("VeyrNoBellyFraming"));
    float Value=0.f;
    if(FParse::Value(Cmd,TEXT("VeyrCameraLife="),Value)&&FMath::IsFinite(Value))CameraLifeScale=FMath::Clamp(Value,0.f,2.f);
    if(FParse::Value(Cmd,TEXT("VeyrCamArm="),Value)&&FMath::IsFinite(Value))GiantArmOverride=FMath::Clamp(Value,250.f,2000.f);
    if(FParse::Value(Cmd,TEXT("VeyrCamVFov="),Value)&&FMath::IsFinite(Value))GiantVFovOverride=FMath::Clamp(Value,35.f,70.f);
    if(FParse::Value(Cmd,TEXT("VeyrCamPivot="),Value)&&FMath::IsFinite(Value))GiantPivotOverride=FMath::Clamp(Value,80.f,260.f);
    UE_LOG(LogTemp,Display,TEXT("VEYR_GIANT_CAMERA on=%d life=%d(%.2f) legacyLockMouse=%d strikeFraming=%d bellyFraming=%d arm=%.0f vfov=%.1f pivot=%.0f"),
        bGiantCamera?1:0,bCameraLife?1:0,CameraLifeScale,bLegacyLockMouse?1:0,bStrikeFraming?1:0,bBellyFraming?1:0,
        GiantArmOverride,GiantVFovOverride,GiantPivotOverride);
}

float AVeyrKnight::HorizontalFovFromVertical(float VerticalDegrees,float Aspect)
{
    return Deg(2.0*FMath::Atan(FMath::Tan(FMath::DegreesToRadians(VerticalDegrees*.5))*FMath::Max(.5f,Aspect)));
}

float AVeyrKnight::ViewportAspect() const
{
    FVector2D Size(16.f,9.f);
    if(const UGameViewportClient* Viewport=GetWorld()?GetWorld()->GetGameViewport():nullptr)Viewport->GetViewportSize(Size);
    return Size.X>1.f&&Size.Y>1.f?static_cast<float>(Size.X/Size.Y):16.f/9.f;
}

void AVeyrKnight::UpdateCameraLifeState(float DeltaSeconds)
{
    // Real (undilated) time, so hit-stop does not freeze or spike the motion.
    const float R=FMath::Max(1e-4f,GetWorld()&&GetWorld()->DeltaRealTimeSeconds>0.f?GetWorld()->DeltaRealTimeSeconds:DeltaSeconds);
    const FVector Velocity=GetVelocity();
    const float Speed=static_cast<float>(Velocity.Size2D());
    const float Sprint=580.f*MovePace;
    const float Run=IsGrounded()?Smooth(260.f*MovePace,540.f*MovePace,Speed):0.f;
    LifePace=FMath::FInterpTo(LifePace,Run,R,Run>LifePace?1.4f:2.2f);
    const FVector Right=CombatCamera->GetRightVector().GetSafeNormal2D();
    const float Across=Speed>30.f?static_cast<float>(FVector::DotProduct(Velocity.GetSafeNormal2D(),Right))*FMath::Min(Speed/Sprint,1.f):0.f;
    LifeLead=FMath::FInterpTo(LifeLead,Across,R,2.f);
    float Turn=0.f;
    if(Speed>30.f)
    {
        const float Heading=Deg(FMath::Atan2(Velocity.Y,Velocity.X));
        Turn=Speed>150.f&&LifeLastSpeed>30.f?FMath::Clamp(FMath::FindDeltaAngleDegrees(LifeLastHeading,Heading)/R,-720.f,720.f):0.f;
        LifeLastHeading=Heading;
    }
    LifeLean=FMath::FInterpTo(LifeLean,FMath::Clamp(Turn*FMath::Min(Speed/Sprint,1.f)*.010f,-2.f,2.f),R,4.f);
    const float Decel=(LifeLastSpeed-Speed)/R;
    if(Decel>900.f&&LifeLastSpeed>.5f*Sprint&&LifeStopAge>.8f){LifeStopAge=0.f;LifeStopAmp=FMath::Clamp(LifeLastSpeed/Sprint,.3f,1.f);}
    LifeLastSpeed=Speed;LifeStopAge+=R;
    LifeNod=LifeStopAge<.6f?LifeStopAmp*FMath::Exp(-LifeStopAge/.14f)*FMath::Cos(LifeStopAge*2.f*PI*2.f):0.f;
}

float AVeyrKnight::UpdateGiantCamera(float DeltaSeconds,float FlightEase,bool bFollowFall)
{
    const float PreviousShoulder=CameraBoom->SocketOffset.Y;
    const float S=IsValid(Boss)?FMath::Max(.5f,Boss->BodyScale*.5f):1.f;
    const float Aspect=ViewportAspect();
    const bool bLock=bLockedOn&&IsValid(Boss)&&(!Boss->IsDead()||bFollowFall);
    GiantLockBlend=FMath::FInterpTo(GiantLockBlend,bLock?1.f:0.f,DeltaSeconds,4.f);
    UpdateCameraLifeState(DeltaSeconds);
    LifeFree=bCameraLife?CameraLifeScale*(1.f-.65f*GiantLockBlend):0.f;

    // Unlocked distance and lens for this scale; the lock adds a little of both.
    const float ArmFree=GiantArmOverride>0.f?GiantArmOverride:600.f+80.f*(S-1.f);
    const float VFree=GiantVFovOverride>0.f?GiantVFovOverride:52.f+3.f*(S-1.f);
    const float PivotBase=GiantPivotOverride>0.f?GiantPivotOverride:150.f;
    float Arm=ArmFree+60.f*S*GiantLockBlend;
    float V=VFree+2.f*GiantLockBlend;
    const float LensExtraMax=10.f+4.f*(S-1.f);

    // Measured from the real camera of the previous frame (first frame: the arm's nominal pose).
    const FVector Feet=GetFootLocation();
    const FVector Camera=bGiantLastCameraValid?GiantLastCamera:Feet+FVector(0,0,PivotBase)-GetActorForwardVector()*Arm;
    const float CamFlat=FMath::Max(50.f,static_cast<float>(FVector::Dist2D(Camera,Feet)));
    const float FeetAngle=Deg(FMath::Atan2(Camera.Z-Feet.Z,CamFlat));

    FGiantCameraEvidence Evidence;
    if(!Controller){GiantEvidence=Evidence;return Arm;}
    FRotator Look=Controller->GetControlRotation().GetNormalized();
    float PitchMax=V*.5f-FeetAngle-3.f;
    float LensNeedTarget=0.f,ArmNeedTarget=0.f;

    if(bLock&&ManualCameraRemaining<=0.f)
    {
        if(!bGiantLockRotValid){GiantLockRot=FRotator(Look.Pitch,Look.Yaw,0.f);bGiantLockRotValid=true;}
        if(bFollowFall&&DeathCameraSide==0.f)
        {
            const FVector Right=FRotationMatrix(FRotator(0,Look.Yaw,0)).GetUnitAxis(EAxis::Y);
            DeathCameraSide=FVector::DotProduct(Boss->GetHeadLocation()-GetActorLocation(),Right)>10.f?1.f:-1.f;
        }
        const FVector Head=Boss->GetHeadLocation();
        const FVector Chest=Boss->GetChestLocation();
        FVector Strike;FName Limb;
        const bool bStrike=bStrikeFraming&&!bFollowFall&&Boss->GetStrikeFocus(Strike,&Limb);
        float WantWeight=0.f;
        if(bStrike)
        {
            GiantLastStrike=Strike;bGiantLastStrikeValid=true;
            const float T=Boss->GetStateElapsed(),D=FMath::Max(.05f,Boss->GetStateDuration());
            WantWeight=Boss->State==EVeyrDragonState::Windup?.65f*Smooth(.25f,.75f,T/D):
                Boss->State==EVeyrDragonState::Active?.65f:.65f*(1.f-Smooth(0.f,.5f,T));
        }
        GiantStrikeWeight=FMath::FInterpTo(GiantStrikeWeight,bGiantLastStrikeValid?WantWeight:0.f,DeltaSeconds,6.f);
        FVector Aim=bGiantLastStrikeValid?FMath::Lerp(Chest,GiantLastStrike,GiantStrikeWeight):Chest;
        if(bFollowFall)Aim=FMath::Lerp(Boss->GetActorLocation()+FVector(0,0,100),Head,.7f);
        // In flight the danger is where the jet or the landing meets the ground: lean the view there.
        if(FlightEase>0.f)Aim=FMath::Lerp(Aim,FMath::Lerp(Head,Boss->GetFlightHazardPoint()+FVector(0,0,150),.35f),FlightEase);

        // Under the belly nothing above can be shown: face where the danger comes from.
        const bool bUnder=bBellyFraming&&!bFollowFall&&!Boss->IsAirborne()&&!Boss->IsDead()&&
            (Boss->IsPointUnderBody(Feet)||FVector::Dist2D(Feet,Chest)<150.f*S);
        GiantUnderBelly=FMath::FInterpTo(GiantUnderBelly,bUnder?1.f:0.f,DeltaSeconds,3.f);
        FVector HeadGround=Head;HeadGround.Z=Feet.Z+200.f*S;
        const FVector UnderAim=bGiantLastStrikeValid?FMath::Lerp(HeadGround,GiantLastStrike,FMath::Clamp(GiantStrikeWeight/.65f,0.f,1.f)):HeadGround;
        Aim=FMath::Lerp(Aim,UnderAim,GiantUnderBelly*(1.f-FlightEase));

        // Lens and arm only as far as the aim point needs to clear the top edge with the feet held at the bottom.
        const float AimFlat=FMath::Max(1.f,static_cast<float>(FVector::Dist2D(Aim,Camera)));
        const float Elevation=Deg(FMath::Atan2(Aim.Z-Camera.Z,AimFlat));
        const float Need=Elevation+6.f+FeetAngle-V;
        LensNeedTarget=FMath::Max(FMath::Clamp(Need,0.f,LensExtraMax),LensExtraMax*GiantUnderBelly);
        ArmNeedTarget=FMath::Clamp(25.f*(Need-LensExtraMax),0.f,250.f*S)*(1.f-GiantUnderBelly);
        GiantLensExtra=FMath::FInterpTo(GiantLensExtra,LensNeedTarget,DeltaSeconds,LensNeedTarget>GiantLensExtra?5.f:3.f);
        GiantArmExtra=FMath::FInterpTo(GiantArmExtra,ArmNeedTarget,DeltaSeconds,ArmNeedTarget>GiantArmExtra?3.f:2.f);
        const float VLock=V+GiantLensExtra;
        PitchMax=VLock*.5f-FeetAngle-3.f;
        if(FlightEase>0.f)PitchMax=FMath::Max(PitchMax,FMath::Lerp(PitchMax,32.f,FlightEase));
        float PitchWant=Elevation-.30f*VLock;
        PitchWant=FMath::Lerp(PitchWant,6.f,GiantUnderBelly*(1.f-FlightEase));
        const float Pitch=FMath::Clamp(PitchWant,-14.f,FMath::Max(-14.f,PitchMax));
        // Ease like the reference warden: 95 % in a third of a second, slower and capped when the aim is close overhead.
        const FVector FromFeet=Aim-Feet;
        const float Flat=static_cast<float>(FromFeet.Size2D());
        const float Close=FMath::Clamp(Flat/(250.f*S),.15f,1.f);
        const float K=1.f-FMath::Exp(-DeltaSeconds*9.f*Close);
        if(Flat>60.f*S)
        {
            const float Turn=FMath::FindDeltaAngleDegrees(static_cast<float>(GiantLockRot.Yaw),Deg(FMath::Atan2(FromFeet.Y,FromFeet.X)));
            const float MaxStep=420.f*FMath::Max(Close,.35f)*DeltaSeconds;
            GiantLockRot.Yaw=FRotator::NormalizeAxis(GiantLockRot.Yaw+FMath::Clamp(Turn*K,-MaxStep,MaxStep));
        }
        GiantLockRot.Pitch+=(Pitch-GiantLockRot.Pitch)*K;GiantLockRot.Roll=0.f;
        // The mouse looks around the lock; released, the view springs back.
        GiantMouseIdle+=DeltaSeconds;
        GiantMouseYaw=FMath::Clamp(GiantMouseYaw,-40.f,40.f);GiantMousePitch=FMath::Clamp(GiantMousePitch,-20.f,25.f);
        if(GiantMouseIdle>.5f){const float Decay=FMath::Exp(-2.5f*DeltaSeconds);GiantMouseYaw*=Decay;GiantMousePitch*=Decay;}
        Look=FRotator(GiantLockRot.Pitch+GiantMousePitch,GiantLockRot.Yaw+GiantMouseYaw,0.f);
        V=VLock;
        Evidence.bLockSolve=true;Evidence.bStrikeFocus=bStrike;Evidence.PitchWant=PitchWant;Evidence.LensNeed=Need;
    }
    else
    {
        bGiantLockRotValid=false;GiantMouseYaw=GiantMousePitch=0.f;
        GiantStrikeWeight=0.f;bGiantLastStrikeValid=false;
        GiantUnderBelly=FMath::FInterpTo(GiantUnderBelly,0.f,DeltaSeconds,3.f);
        GiantLensExtra=FMath::FInterpTo(GiantLensExtra,0.f,DeltaSeconds,3.f);
        GiantArmExtra=FMath::FInterpTo(GiantArmExtra,0.f,DeltaSeconds,2.f);
        V+=GiantLensExtra;
    }
    // Airborne dragon: looking up stops at 40 degrees and the lens opens to about 90 degrees horizontal.
    Look.Pitch=FMath::Clamp(FRotator::NormalizeAxis(Look.Pitch),-55.f,FMath::Lerp(68.f,40.f,FlightEase));Look.Roll=0.f;
    V=FMath::Lerp(V,FMath::Max(V,59.f+2.f*(S-1.f)),FlightEase);
    Controller->SetControlRotation(Look);

    // D2 pace: draw back and widen at a sprint; lag the arm's origin a little.
    Arm+=GiantArmExtra+80.f*LifePace*LifeFree;
    V=FMath::Min(V*(1.f+.07f*LifePace*LifeFree),68.f);
    CombatCamera->SetFieldOfView(HorizontalFovFromVertical(V,Aspect));
    CameraDistance=Arm;CameraBoom->TargetArmLength=Arm;
    CameraPitchCeiling=PitchMax;AutoLockPitchCeiling=PitchMax;
    CameraBoom->bEnableCameraLag=bCameraLife&&CameraLifeScale>0.f;
    CameraBoom->CameraLagSpeed=FMath::Lerp(9.f,15.f,GiantLockBlend);
    CameraBoom->CameraLagMaxDistance=45.f;
    CameraBoom->bEnableCameraRotationLag=false;
    // A shoulder-height pivot that rises with upward look so the camera never orbits into the floor.
    const float R=FMath::DegreesToRadians(Look.Pitch);
    const float Pivot=FMath::Max(PivotBase,70.f+Arm*FMath::Sin(R)-12.f*FMath::Cos(R));
    CameraBoom->SetRelativeLocation(FVector(0,0,Pivot-GetCapsuleComponent()->GetScaledCapsuleHalfHeight()));
    float Shoulder=FMath::GetMappedRangeValueClamped(FVector2D(15,68),FVector2D(42,180),Look.Pitch)+28.f*LifeLead*LifeFree;
    if(IsValid(Boss)&&Boss->UsesFinisherRevision()&&Boss->IsDead())
        Shoulder=FMath::FInterpTo(PreviousShoulder,bFollowFall&&bLockedOn?DeathCameraSide*280.f:Shoulder,DeltaSeconds,4.f);
    CameraBoom->SocketOffset=FVector(0,Shoulder,12.f);

    LifeRotation=FRotator(-1.f*LifeNod*LifeFree,0.f,LifeLean*LifeFree);
    LifeLocation=FVector(14.f*LifeNod*LifeFree,0.f,0.f);
    Evidence.VerticalFov=V;Evidence.ArmCm=Arm;Evidence.PitchMax=PitchMax;Evidence.FeetAngle=FeetAngle;
    Evidence.StrikeWeight=GiantStrikeWeight;Evidence.UnderBelly=GiantUnderBelly;Evidence.LockBlend=GiantLockBlend;
    Evidence.Pace=LifePace;Evidence.Lean=LifeLean*LifeFree;Evidence.Nod=LifeNod*LifeFree;
    Evidence.MouseYaw=GiantMouseYaw;Evidence.MousePitch=GiantMousePitch;
    GiantEvidence=Evidence;
    return Arm;
}

void AVeyrKnight::ApplyCameraLife(bool bShakeApplied)
{
    // Runs after the fight-feel shake, which rewrites the camera's relative pose every frame; without it, reset here.
    if(!bShakeApplied){CombatCamera->SetRelativeRotation(FRotator::ZeroRotator);CombatCamera->SetRelativeLocation(FVector::ZeroVector);}
    if(bCameraLife&&(!LifeRotation.IsNearlyZero(1e-3f)||!LifeLocation.IsNearlyZero(1e-2f)))
    {
        CombatCamera->AddRelativeRotation(LifeRotation);
        CombatCamera->AddRelativeLocation(LifeLocation);
    }
    GiantLastCamera=CombatCamera->GetComponentLocation();bGiantLastCameraValid=true;
}
