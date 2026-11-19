// Camera fourth pass (2026-11-19): one small placement module for the knight's camera.
//
// Per frame, in this order and nothing else (-VeyrLegacyCameraPlacement restores the fifth-pass arm):
//  a. Pivot at the knight's upper chest; inside the dragon proxy -> straight up to the first free point (analytic).
//  b. Direction from the control rotation (player look or lock-on line), turned at most RigTurnRateDegPerSec, with
//     one sticky eased rise (down-look up to RigAssistDownDeg, arm +20 %) while the knight is under or beside the body.
//  c. Positional offsets from other systems (the fight-feel bounce) go on the DESIRED point, before the sweep.
//  d. Swept sphere (near-plane corner + margin) from the pivot against the proxy and the arena: the lens is the sweep
//     result, pulled in at once, let out eased.
//  e. Short arm (nearer than capsule radius + RigShortArmCm): blend (0.25 s, hysteresis) to one over-the-head point
//     looking down; if that is blocked too, the lens sits on top of his head and his meshes are hidden from this view.
#include "VeyrCameraBoom.h"
#include "VeyrDragon.h"
#include "VeyrSkeletalPresentation.h"
#include "Engine/World.h"
#include "GameFramework/PlayerController.h"
#include "GameFramework/Character.h"
#include "Components/CapsuleComponent.h"
#include "Camera/CameraComponent.h"
#include "Misc/CommandLine.h"

bool UVeyrCameraBoom::UpdateProxy()
{
    AVeyrDragon* D=Dragon.Get();
    UVeyrSkeletalPresentation* P=D&&D->bUsingCustomuseVisual?D->ImportedPresentation.Get():nullptr;
    if(!Proxy.Update(P,RigProxyMarginCm*DragonScale()))return false;
    // Extents follow the drawn skin this frame (-VeyrRigBoneBoxes keeps the bone-moved boxes only).
    static const bool bBoneOnly=FParse::Param(FCommandLine::Get(),TEXT("VeyrRigBoneBoxes"));
    if(!bBoneOnly){FVeyrDragonTrueSkin& True=FVeyrDragonTrueSkin::Get();if(True.Skin(P))bProxyTight=True.Tighten(Proxy);}
    return true;
}

float UVeyrCameraBoom::RigSweep(const FVector& From,const FVector& To,float Radius) const
{
    float T=Proxy.IsValid()?Proxy.Sweep(From,To,Radius):1.f;
    if(GetWorld()&&T>0.f)
    {
        const FVector End=From+(To-From)*T;
        FHitResult Hit;FCollisionQueryParams Params(SCENE_QUERY_STAT(VeyrRigSweep),false,GetOwner());
        if(GetWorld()->SweepSingleByChannel(Hit,From,End,FQuat::Identity,ProbeChannel,FCollisionShape::MakeSphere(Radius),Params))
            T*=FMath::Max(0.f,Hit.Time-.002f);
    }
    return T;
}

void UVeyrCameraBoom::SetKnightHiddenByCamera(bool bHide)
{
    AActor* Owner=GetOwner();
    APlayerController* PC=GetWorld()?GetWorld()->GetFirstPlayerController():nullptr;
    if(bHide&&PC&&PC->GetViewTarget()==Owner){PC->HiddenActors.AddUnique(Owner);HiddenFromPC=PC;}
    else if(APlayerController* Old=HiddenFromPC.Get()){Old->HiddenActors.Remove(Owner);HiddenFromPC.Reset();}
    bKnightHiddenByCamera=bHide&&HiddenFromPC.IsValid();
}

FVector UVeyrCameraBoom::RigArm(const FVector& Base,float DeltaTime)
{
    const float S=DragonScale();
    const float Dt=FMath::Clamp(DeltaTime,0.f,.1f);
    FVector KB,KT;float KR=0.f;
    if(!KnightCapsule(KB,KT,KR)){bFramedViewValid=false;return Base;}
    const FVector Foot=KB-FVector::UpVector*KR,Top=KT+FVector::UpVector*KR;
    const float R=RigLensRadiusCm;
    // a. Pivot at the upper chest, lifted straight up out of the proxy when the body is on him.
    FVector Pivot(KB.X,KB.Y,FMath::Min(Foot.Z+RigPivotHeightCm,Top.Z-10.0));
    if(Proxy.IsValid())
    {
        const float Lift=Proxy.FreeAbove(Pivot,R,4000.f*S);
        if(Lift>0.f){Pivot.Z+=Lift;++RigPivotLiftFrames;}
    }
    // b. Direction: control rotation (or lock-on line), sticky eased rise near the body, turn-rate limited.
    FRotator Control=GetTargetRotation();Control.Roll=0.f;Control.Normalize();
    // Footprint: the vertical line over his feet meets the body (boxes grown sideways by RigFootprintCm x scale).
    const bool bNearBody=Proxy.IsValid()&&Proxy.UnderBody(Foot+FVector::UpVector*30.f,4000.f*S,RigFootprintCm*S);
    if(bNearBody){AssistClearSeconds=0.f;bAssist=true;}
    else if(bAssist&&(AssistClearSeconds+=Dt)>1.f)bAssist=false;
    AssistAlpha=FMath::FInterpConstantTo(AssistAlpha,bAssist?1.f:0.f,Dt,1.f/.6f);
    const float AssistS=FMath::SmoothStep(0.f,1.f,AssistAlpha);
    FRotator Want=Control;
    const float ControlPitch=static_cast<float>(Want.Pitch);
    Want.Pitch=FMath::Max(FMath::Min(ControlPitch,FMath::Lerp(ControlPitch,-RigAssistDownDeg,AssistS)),-RigMaxDownDeg);
    // Looking up (lock-on at a high or flying dragon) stops where his body would leave the bottom of the frame.
    Want.Pitch=FMath::Min(static_cast<float>(Want.Pitch),RigMaxUpDeg);
    const FQuat WantQ=Want.Quaternion();
    if(!bRigRot){RigRot=WantQ;bRigRot=true;}
    else
    {
        const float MaxTurn=RigTurnRateDegPerSec*FMath::Max(Dt,1.f/240.f);
        const float Turn=FMath::RadiansToDegrees(static_cast<float>(RigRot.AngularDistance(WantQ)));
        RigRot=Turn>MaxTurn?FQuat::Slerp(RigRot,WantQ,MaxTurn/Turn):WantQ;RigRot.Normalize();
    }
    FRotator ArmRot=RigRot.Rotator();ArmRot.Roll=0.f;
    const float Length=TargetArmLength*(1.f+.2f*AssistS);
    // Upward look keeps the lens near shoulder height (the knight's own rule), by raising the arm origin, swept.
    FVector Origin=Pivot;
    if(ArmRot.Pitch>0.f)
    {
        const float Rad=FMath::DegreesToRadians(static_cast<float>(ArmRot.Pitch));
        const float Raise=FMath::Max(0.f,90.f+Length*FMath::Sin(Rad)-12.f*FMath::Cos(Rad)-static_cast<float>(Pivot.Z-Foot.Z));
        if(Raise>1.f)Origin=Pivot+FVector::UpVector*Raise*RigSweep(Pivot,Pivot+FVector::UpVector*Raise,R);
    }
    const FQuat ArmQ=ArmRot.Quaternion();
    const FVector ArmDesired=Origin-ArmQ.GetForwardVector()*Length+ArmQ.RotateVector(SocketOffset);
    // e (decision). The plain arm's swept result decides whether the over-the-head blend is wanted (hysteresis).
    const float ArmT=RigSweep(Origin,ArmDesired,R);
    const float ArmGap=static_cast<float>(FMath::PointDistToSegment(Origin+(ArmDesired-Origin)*ArmT,KB,KT))-KR;
    if(ArmGap<RigShortArmCm){bOverhead=true;OverheadClearSeconds=0.f;}
    else if(bOverhead&&ArmGap>RigShortArmCm+60.f&&(OverheadClearSeconds+=Dt)>.5f)bOverhead=false;
    else if(bOverhead&&ArmGap<=RigShortArmCm+60.f)OverheadClearSeconds=0.f;
    OverheadAlpha=FMath::FInterpConstantTo(OverheadAlpha,bOverhead?1.f:0.f,Dt,4.f);
    const float OverS=FMath::SmoothStep(0.f,1.f,OverheadAlpha);
    const FVector Back=FRotator(0.f,static_cast<float>(ArmRot.Yaw),0.f).Vector();
    const FVector OverDesired=FVector(Pivot.X,Pivot.Y,FMath::Max(Pivot.Z,Top.Z+static_cast<double>(RigOverheadUpCm)))-Back*RigOverheadBackCm;
    FRotator OverRot(FMath::Min(static_cast<float>(ArmRot.Pitch),RigOverheadPitchDeg),static_cast<float>(ArmRot.Yaw),0.f);
    FQuat View=FQuat::Slerp(ArmQ,OverRot.Quaternion(),OverS);View.Normalize();
    // c. Every positional offset goes on the desired point, before the sweep.
    const FVector From=FMath::Lerp(Origin,Pivot,OverS);
    const FVector Desired=FMath::Lerp(ArmDesired,OverDesired,OverS)+View.RotateVector(FeelLocalOffset);
    // d. The lens is the sweep result: in at once, out eased (any fraction below T lies on the free segment).
    const float T=RigSweep(From,Desired,R);
    if(T<RigFraction){if(RigFraction>=.999f&&T<.999f)++PullInEvents;RigFraction=T;}
    else RigFraction=FMath::Min(T,FMath::FInterpTo(RigFraction,T,Dt,ReleaseRate));
    FVector Lens=From+(Desired-From)*RigFraction;
    // e (last resort). Lens inside his capsule (plus near plane): top of his head, his meshes hidden from this view.
    const float Gap=static_cast<float>(FMath::PointDistToSegment(Lens,KB,KT))-KR;
    if(Gap<RigHideCm){bRigHide=true;HideClearSeconds=0.f;}
    else if(bRigHide&&Gap>RigHideCm+30.f&&(HideClearSeconds+=Dt)>.3f)bRigHide=false;
    else if(bRigHide&&Gap<=RigHideCm+30.f)HideClearSeconds=0.f;
    if(bRigHide)
    {
        Lens=FVector(KB.X,KB.Y,Top.Z+15.0);
        if(Proxy.IsValid()&&Proxy.Contains(Lens,R))Lens.Z+=Proxy.FreeAbove(Lens,R,4000.f*S);
        ++RigHiddenFrames;
    }
    SetKnightHiddenByCamera(bRigHide);
    if(OverS>.01f)++FramingSearches;
    // View: turn-rate limited again after the blends, never steeper than RigMaxDownDeg.
    FRotator VR=View.Rotator();VR.Roll=0.f;VR.Pitch=FMath::Clamp(static_cast<float>(VR.Pitch),-RigMaxDownDeg,RigMaxUpDeg);View=VR.Quaternion();
    if(bSafeLastView)
    {
        const float MaxTurn=(RigTurnRateDegPerSec+10.f)*FMath::Max(Dt,1.f/240.f);
        const float Turn=FMath::RadiansToDegrees(static_cast<float>(View.AngularDistance(SafeLastView)));
        if(Turn>MaxTurn){View=FQuat::Slerp(SafeLastView,View,MaxTurn/Turn);View.Normalize();++ClampedTurns;}
    }
    SafeLastView=View;bSafeLastView=true;
    FramedView=View;bFramedViewValid=true;FovBoostDeg=0.f;
    BodyFraction=RigFraction;SafeFraction=RigFraction;
    if(Proxy.IsValid()&&Proxy.Contains(Lens,0.f))++ResultInsideFrames;
    return Lens;
}
