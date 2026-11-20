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
#include "HAL/PlatformTime.h"

bool UVeyrCameraBoom::UpdateProxy()
{
    AVeyrDragon* D=Dragon.Get();
    UVeyrSkeletalPresentation* P=D&&D->bUsingCustomuseVisual?D->ImportedPresentation.Get():nullptr;
    if(!Proxy.Update(P,RigProxyMarginCm*DragonScale()))return false;
    // Extents follow the drawn skin this frame (-VeyrRigBoneBoxes keeps the bone-moved boxes only).
    static const bool bBoneOnly=FParse::Param(FCommandLine::Get(),TEXT("VeyrRigBoneBoxes"));
    if(!bBoneOnly)
    {
        FVeyrDragonTrueSkin& True=FVeyrDragonTrueSkin::Get();
        bProxyTight=True.Skin(P)&&True.Tighten(Proxy);
        // A frame the skin cannot be read (pose not yet evaluated, mesh swap): last frame's tight boxes, never the rigid ones.
        if(bProxyTight)LastTightProxy=Proxy;else if(LastTightProxy.IsValid()){Proxy=LastTightProxy;++RigStaleProxyFrames;}
    }
    return true;
}

float UVeyrCameraBoom::RigSweep(const FVector& From,const FVector& To,float Radius) const
{
    const float T=RigDragonSweep(From,To,Radius);
    return T>0.f?T*RigWorldSweep(From,From+(To-From)*T,Radius):T;
}

float UVeyrCameraBoom::RigDragonSweep(const FVector& From,const FVector& To,float Radius) const
{
    float T=Proxy.IsValid()?Proxy.Sweep(From,To,Radius):1.f;
    // Boxes are the broad phase only: where they block, the lens sphere continues against the drawn faces themselves
    // (bent legs and the belly box claim free space). Start inside the boxes = start inside nothing known: the skin
    // decides from 0. -VeyrRigProxySweep keeps the box contact.
    static const bool bBoxOnly=FParse::Param(FCommandLine::Get(),TEXT("VeyrRigProxySweep"));
    if(!bBoxOnly&&bProxyTight&&T<1.f)
    {
        const FVeyrDragonTrueSkin& True=FVeyrDragonTrueSkin::Get();
        const double S0=FPlatformTime::Seconds();int32 Steps=0;
        T=True.SweepSphere(From,To,Radius,T,&Steps);
        RigSkinSweeps++;RigSkinSteps+=Steps;RigSkinSweepSeconds+=FPlatformTime::Seconds()-S0;
    }
    return T;
}

float UVeyrCameraBoom::RigWorldSweep(const FVector& From,const FVector& To,float Radius) const
{
    float T=1.f;
    if(GetWorld())
    {
        const FVector End=To;
        FHitResult Hit;FCollisionQueryParams Params(SCENE_QUERY_STAT(VeyrRigSweep),false,GetOwner());
        // The dragon is the proxy's job: its gameplay bodies (much fatter than the skin) must not pull the lens in.
        // -VeyrRigSweepDragonBodies restores sweeping them.
        static const bool bSweepDragon=FParse::Param(FCommandLine::Get(),TEXT("VeyrRigSweepDragonBodies"));
        if(!bSweepDragon)if(AActor* D=Dragon.Get()){Params.AddIgnoredActor(D);TArray<AActor*> Attached;D->GetAttachedActors(Attached,true,true);Params.AddIgnoredActors(Attached);}
        if(GetWorld()->SweepSingleByChannel(Hit,From,End,FQuat::Identity,ProbeChannel,FCollisionShape::MakeSphere(Radius),Params))
        {
            T*=FMath::Max(0.f,Hit.Time-.002f);++RigWorldHits;
            if(RigWorldHitNames.Num()<12&&Hit.GetActor())RigWorldHitNames.AddUnique(Hit.GetActor()->GetClass()->GetName()+TEXT(":")+(Hit.GetComponent()?Hit.GetComponent()->GetName():FString()));
        }
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
        // Optional (-VeyrRigSkinLift): let the drawn skin decide the lift. Measured worse and kept off: the unlifted
        // pivot stays beside the leg, the lens sits on the pale toes and the hide rule rises 0 % -> 3.4-3.8 % (film 3).
        static const bool bProxyLift=!FParse::Param(FCommandLine::Get(),TEXT("VeyrRigSkinLift"));
        const FVeyrDragonTrueSkin& TrueLift=FVeyrDragonTrueSkin::Get();
        const bool bSkinClear=!bProxyLift&&bProxyTight&&Proxy.Contains(Pivot,R)&&!TrueLift.InsideVolume(Pivot)&&TrueLift.NearestDistance(Pivot,R+1.f)>=R;
        const float Lift=bSkinClear?0.f:Proxy.FreeAbove(Pivot,R,4000.f*S);
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
    const FVector HighDesired=FVector(Pivot.X,Pivot.Y,FMath::Max(Pivot.Z,Top.Z+static_cast<double>(RigOverheadUpCm)))-Back*RigOverheadBackCm;
    // Under the belly the over-the-head point is inside the body: the same fixed point at hip height, looking level,
    // fits under it. Chosen once when the short arm starts (longer free sweep wins), switched only when the chosen
    // one is blocked and the other is not (-VeyrRigNoLowOverhead keeps the head-high point only).
    static const bool bNoLow=FParse::Param(FCommandLine::Get(),TEXT("VeyrRigNoLowOverhead"));
    const FVector LowDesired=FVector(Pivot.X,Pivot.Y,Foot.Z+110.0)-Back*(RigOverheadBackCm*1.3f);
    if(!bNoLow&&bOverhead)
    {
        const float HighFree=RigSweep(Pivot,HighDesired,R)*static_cast<float>(FVector::Dist(Pivot,HighDesired));
        const float LowFree=RigSweep(Pivot,LowDesired,R)*static_cast<float>(FVector::Dist(Pivot,LowDesired));
        if(OverheadAlpha<=.01f)bOverLow=LowFree>HighFree+40.f;
        else if(bOverLow&&LowFree<80.f&&HighFree>160.f)bOverLow=false;
        else if(!bOverLow&&HighFree<80.f&&LowFree>160.f)bOverLow=true;
    }
    if(!bOverhead&&OverheadAlpha<=.01f)bOverLow=false;
    OverLowAlpha=FMath::FInterpConstantTo(OverLowAlpha,bOverLow?1.f:0.f,Dt,4.f);
    const float LowS=FMath::SmoothStep(0.f,1.f,OverLowAlpha);RigLowFrames+=LowS>.5f;
    const FVector OverDesired=FMath::Lerp(HighDesired,LowDesired,LowS);
    FRotator OverRot(FMath::Lerp(FMath::Min(static_cast<float>(ArmRot.Pitch),RigOverheadPitchDeg),5.f,LowS),static_cast<float>(ArmRot.Yaw),0.f);
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
        RigHideUnderBodyFrames+=Proxy.IsValid()&&Proxy.UnderBody(Top,4000.f*S,0.f);
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
    LastRigLens=Lens;RigFrame=GFrameCounter;RigSkinFrame=FVeyrDragonTrueSkin::Get().SkinFrame();
    return Lens;
}

// Camera fifth pass (2026-11-19, default; -VeyrCameraCollideRig restores the fourth-pass rig above). The camera does
// not fight the boss for space: a steady low third-person arm that collides with the ARENA only, shortens against the
// dragon by a bounded, eased amount, and leaves the rest to the dragon's materials (distance fade near the lens, sight
// fade in front of the knight, back faces clipped; AVeyrDragon::SetCameraFade). Order per frame:
//  1. Pivot at the knight's upper chest (never lifted).
//  2. Direction: player yaw / lock-on line; pitch clamped to [-FadeDownDeg, FadeUpDeg]; turn-rate limited.
//  3. Every positional offset (fight-feel bounce) on the desired point, before the sweeps.
//  4. Arena: swept sphere (dragon ignored), in at once, out eased.
//  5. Dragon: true-skin sweep, shortened (eased) to at most FadeMinArmFraction of the arm and never nearer than his
//     capsule radius + FadeMinGapCm; the lens may then be inside the body; it stays where it is.
//  6. View: the arm rotation; pitch lowered only as far as keeps his feet in frame.
bool UVeyrCameraBoom::FadeRigSwitchedOn()
{
    const TCHAR* C=FCommandLine::Get();
    return !FParse::Param(C,TEXT("VeyrCameraCollideRig"))&&!FParse::Param(C,TEXT("VeyrLegacyCameraBoom"))&&!FParse::Param(C,TEXT("VeyrLegacyCameraFraming"))&&
        !FParse::Param(C,TEXT("VeyrLegacyCameraSafety"))&&!FParse::Param(C,TEXT("VeyrLegacyCameraPlacement"))&&!FParse::Param(C,TEXT("VeyrLegacyCutThrough"));
}

FVector UVeyrCameraBoom::FadeLockChest() const
{
    const AVeyrDragon* D=Dragon.Get();
    if(!D)return FVector::ZeroVector;
    FVector Chest,NeckBase,Pelvis;
    if(D->GetTorsoLocations(Chest,NeckBase,Pelvis))return Chest;
    const FVector Root=D->GetActorLocation(),Head=D->GetHeadLocation();
    return FMath::Lerp(Root+FVector::UpVector*FMath::Max(0.0,(Head.Z-Root.Z)*.5),Head,.25);
}

FVector UVeyrCameraBoom::FadeArm(const FVector& Base,float DeltaTime)
{
    const float S=DragonScale();
    const float Dt=FMath::Clamp(DeltaTime,0.f,.1f);
    FVector KB,KT;float KR=0.f;
    if(!KnightCapsule(KB,KT,KR)){bFramedViewValid=false;return Base;}
    if(bKnightHiddenByCamera)SetKnightHiddenByCamera(false);
    const FVector Foot=KB-FVector::UpVector*KR,Top=KT+FVector::UpVector*KR;
    const float R=RigLensRadiusCm;
    // 1. Pivot.
    const FVector Pivot(KB.X,KB.Y,FMath::Min(Foot.Z+RigPivotHeightCm,Top.Z-10.0));
    // 2. Direction.
    FRotator Want=GetTargetRotation();Want.Roll=0.f;Want.Normalize();
    Want.Pitch=FMath::Clamp(static_cast<float>(Want.Pitch),-FadeDownDeg,FadeUpDeg);
    const FQuat WantQ=Want.Quaternion();
    if(!bRigRot){RigRot=WantQ;bRigRot=true;}
    else
    {
        // Third pass: the steady view turns at most FadeTurnDegPerSec (90 deg/s, about 20 px per 1/30 s at 640 px); -VeyrFadeTurnRate=0 restores 220.
        const float MaxTurn=(FadeTurnDegPerSec>0.f?FadeTurnDegPerSec:RigTurnRateDegPerSec)*FMath::Max(Dt,1.f/240.f);
        const float Turn=FMath::RadiansToDegrees(static_cast<float>(RigRot.AngularDistance(WantQ)));
        RigRot=Turn>MaxTurn?FQuat::Slerp(RigRot,WantQ,MaxTurn/Turn):WantQ;RigRot.Normalize();
    }
    FRotator ArmRot=RigRot.Rotator();ArmRot.Roll=0.f;
    // 6c pull-back (eased below) lengthens the arm while the head and chest cannot be framed from the normal one.
    const float Length=FMath::Max(100.f,TargetArmLength)*(bHeadChestFraming&&bDragonFraming?FramePull:1.f);
    // Upward look keeps the lens near shoulder height by raising the arm origin (arena-swept), as the knight's rule.
    FVector Origin=Pivot;
    if(ArmRot.Pitch>0.f)
    {
        const float Rad=FMath::DegreesToRadians(static_cast<float>(ArmRot.Pitch));
        const float Raise=FMath::Max(0.f,90.f+Length*FMath::Sin(Rad)-12.f*FMath::Cos(Rad)-static_cast<float>(Pivot.Z-Foot.Z));
        if(Raise>1.f)Origin=Pivot+FVector::UpVector*Raise*RigWorldSweep(Pivot,Pivot+FVector::UpVector*Raise,R);
    }
    const FQuat ArmQ=ArmRot.Quaternion();
    // 3. Offsets on the desired point.
    const FVector Desired=Origin-ArmQ.GetForwardVector()*Length+ArmQ.RotateVector(SocketOffset)+ArmQ.RotateVector(FeelLocalOffset);
    const float Span=FMath::Max(1.f,static_cast<float>(FVector::Dist(Origin,Desired)));
    // 4. Arena.
    const float TA=RigWorldSweep(Origin,Desired,R);
    bFadeArenaPull=TA<FadeArenaFraction-.002f;
    if(bFadeArenaPull)FadeArenaFraction=TA;else FadeArenaFraction=FMath::Min(TA,FMath::FInterpTo(FadeArenaFraction,TA,Dt,ReleaseRate));
    // 5. Dragon: bounded, eased shorten.
    const float Floor=FMath::Clamp(FMath::Max(FadeMinArmFraction,(KR+FadeMinGapCm)/Span),0.f,1.f);
    const float TD=Proxy.IsValid()?RigDragonSweep(Origin,Desired,R):1.f;
    const float DragonTarget=TD>=.999f?1.f:FMath::Max(Floor,TD);
    FadeDragonFraction=FMath::FInterpTo(FadeDragonFraction,DragonTarget,Dt,DragonTarget<FadeDragonFraction?FadeShortenRate:ReleaseRate);
    const float Fraction=FMath::Min(FadeArenaFraction,FadeDragonFraction);
    FVector Lens=Origin+(Desired-Origin)*Fraction;
    // 5b. Steady: the lens moves at most FadeMaxStepCm a frame (a blink, a knock-back, a turn); the arena still wins,
    //     and a jump over FadeCutCm (restart) is a cut. -VeyrFadeNoStepLimit restores the unlimited lens.
    if(FadeMaxStepCm>0.f&&!bFadeArenaPull&&RigFrame+1==GFrameCounter)
    {
        const FVector Step=Lens-LastRigLens;const float StepLen=static_cast<float>(Step.Size());
        const float MaxStep=FadeMaxStepCm;
        if(StepLen>MaxStep&&StepLen<FadeCutCm)
        {
            const FVector Limited=LastRigLens+Step*(MaxStep/StepLen);
            if(RigWorldSweep(Origin,Limited,R)>=.999f){Lens=Limited;++FadeStepLimitedFrames;}
        }
    }
    // 6. View: the arm rotation; his feet stay above the bottom edge (vertical half-angle from the lens).
    FRotator VR=ArmRot;
    {
        const UCameraComponent* Camera=nullptr;
        for(USceneComponent* Child:GetAttachChildren())if(const UCameraComponent* C=Cast<UCameraComponent>(Child)){Camera=C;break;}
        const float Fov=Camera?Camera->FieldOfView:78.f;
        const float VHalf=FMath::RadiansToDegrees(FMath::Atan(FMath::Tan(FMath::DegreesToRadians(Fov*.5f))/FMath::Max(.5f,ViewAspect())));
        const float Horizontal=FMath::Max(50.f,static_cast<float>(FVector::Dist2D(Lens,KB)));
        const float FeetBelow=FMath::RadiansToDegrees(FMath::Atan2(static_cast<float>(Lens.Z-(Foot.Z+10.0)),Horizontal));
        VR.Pitch=FMath::Min(static_cast<float>(VR.Pitch),VHalf*.88f-FeetBelow);
        VR.Pitch=FMath::Clamp(static_cast<float>(VR.Pitch),-FadeDownDeg,FadeUpDeg);
        // 6b. The dragon in shot: if no head/torso point is inside the frame, lift the view (pitch first, then a bounded
        //     yaw) toward the nearest one while his feet stay inside the bottom edge (knight in the lower part of the
        //     frame). Eased; the pitch band and the turn clamp still apply. -VeyrNoDragonFraming turns it off.
        const AVeyrDragon* FD=Dragon.Get();
        FRotator LiftTarget=FRotator::ZeroRotator;
        if(bDragonFraming&&FD&&!FD->IsDead())
        {
            const float HalfH=Fov*.5f,Aspect=ViewAspect();
            TArray<FVector,TInlineAllocator<8>> Pts;Pts.Add(FD->GetHeadLocation());
            FVector Chest,NeckBase,Pelvis;
            if(FD->GetTorsoLocations(Chest,NeckBase,Pelvis))
            {
                const FVector Down=-FVector::UpVector*180.f*S;const FVector Mid=(Chest+Pelvis)*.5;
                Pts.Append({Chest,NeckBase,Pelvis,Mid,Chest+Down,Pelvis+Down,Mid+Down});
            }
            if(bHeadChestFraming&&Pts.Num()>1)
            {
                // 6c: head AND chest. Both points need the lift; what the pitch room cannot give becomes pull-back.
                const FVector HC[2]={Pts[0],Pts[1]};
                auto AllIn=[&](const FRotator& R,float M){const FQuat Q=R.Quaternion();for(const FVector& P:HC){float U,V;if(!ProjectToView(P,Lens,Q,HalfH*2.f,Aspect,U,V)||FMath::Abs(U)>M||FMath::Abs(V)>M)return false;}return true;};
                const float PitchMax=FMath::Min(FadeUpDeg,VHalf*.95f-FeetBelow);
                float PitchNeed=0.f,YawLo=-1e3f,YawHi=1e3f;
                for(const FVector& P:HC)
                {
                    const FRotator To=(P-Lens).Rotation();
                    const float DYaw=FMath::FindDeltaAngleDegrees(static_cast<float>(VR.Yaw),static_cast<float>(To.Yaw));
                    YawLo=FMath::Max(YawLo,DYaw-HalfH*.8f);YawHi=FMath::Min(YawHi,DYaw+HalfH*.8f);
                    PitchNeed=FMath::Max(PitchNeed,static_cast<float>(To.Pitch)-VHalf*.8f-static_cast<float>(VR.Pitch));
                }
                const float YawNeed=YawLo>YawHi?0.f:FMath::Clamp(0.f,YawLo,YawHi);
                const float Room=FMath::Max(0.f,PitchMax-static_cast<float>(VR.Pitch));
                const float Unmet=PitchNeed-Room+(YawLo>YawHi||FMath::Abs(YawNeed)>HalfH*.6f?6.f:0.f);
                if(AllIn(VR,.85f))LiftTarget=FRotator::ZeroRotator;
                else if(!AllIn(VR+FadeDragonLift,.92f))LiftTarget=FRotator(FMath::Clamp(PitchNeed,0.f,Room),FMath::Clamp(YawNeed,-HalfH*.6f,HalfH*.6f),0.f);
                else LiftTarget=FadeDragonLift;
                // Pull-back: grow while the lift cannot reach both, relax once they fit with room to spare.
                if(Unmet>0.f){FramePullTarget=FMath::Min(FramePullMax,FMath::Max(FramePullTarget,FramePull)+Unmet/30.f*Dt*4.f);++HeadChestUnmetFrames;}
                else if(Unmet<-4.f)FramePullTarget=FMath::Max(1.f,FramePullTarget-.25f*Dt);
                LiftTarget.Pitch=FMath::Min(static_cast<float>(LiftTarget.Pitch),Room);
            }
            else
            {
            auto AnyIn=[&](const FRotator& R,float M){const FQuat Q=R.Quaternion();for(const FVector& P:Pts){float U,V;if(ProjectToView(P,Lens,Q,HalfH*2.f,Aspect,U,V)&&FMath::Abs(U)<=M&&FMath::Abs(V)<=M)return true;}return false;};
            const bool bInBare=AnyIn(VR,.85f),bIn=bInBare||AnyIn(VR+FadeDragonLift,.92f);
            if(bInBare)LiftTarget=FRotator::ZeroRotator; // in shot without help: settle back
            else if(!bIn)
            {
                const float PitchMax=FMath::Min(FadeUpDeg,VHalf*.95f-FeetBelow);
                float Best=TNumericLimits<float>::Max();
                for(const FVector& P:Pts)
                {
                    const FRotator To=(P-Lens).Rotation();
                    const float DYaw=FMath::FindDeltaAngleDegrees(static_cast<float>(VR.Yaw),static_cast<float>(To.Yaw));
                    const float YawNeed=FMath::Sign(DYaw)*FMath::Max(0.f,FMath::Abs(DYaw)-HalfH*.8f);
                    const float PitchNeed=FMath::Max(0.f,static_cast<float>(To.Pitch)-VHalf*.8f-static_cast<float>(VR.Pitch));
                    if(FMath::Abs(YawNeed)>HalfH*.6f||VR.Pitch+PitchNeed>PitchMax+.01f)continue;
                    const float Cost=PitchNeed+FMath::Abs(YawNeed)*1.5f;
                    if(Cost<Best){Best=Cost;LiftTarget=FRotator(PitchNeed,YawNeed,0.f);}
                }
                if(Best==TNumericLimits<float>::Max())LiftTarget=FadeDragonLift; // nothing reachable: hold
            }
            else LiftTarget=FadeDragonLift; // in shot only with the lift: hold it
            LiftTarget.Pitch=FMath::Min(static_cast<float>(LiftTarget.Pitch),FMath::Max(0.f,FMath::Min(FadeUpDeg,VHalf*.95f-FeetBelow)-static_cast<float>(VR.Pitch)));
            }
        }
        if(!(bHeadChestFraming&&bDragonFraming&&FD&&!FD->IsDead()))FramePullTarget=1.f;
        FramePull=FMath::FInterpTo(FramePull,FramePullTarget,Dt,FramePullTarget>FramePull?1.2f:.6f);FramePullFrames+=FramePull>1.02f;
        FadeDragonLift=FMath::RInterpTo(FadeDragonLift,LiftTarget,Dt,LiftTarget.IsNearlyZero()?1.5f:5.f);
        FadeDragonLiftFrames+=!FadeDragonLift.IsNearlyZero(.5f);
        const float PitchBeforeLift=static_cast<float>(VR.Pitch);
        VR+=FadeDragonLift;
        VR.Pitch=FMath::Min(static_cast<float>(VR.Pitch),FMath::Max(PitchBeforeLift,VHalf*.95f-FeetBelow));
        VR.Pitch=FMath::Clamp(static_cast<float>(VR.Pitch),-FadeDownDeg,FadeUpDeg);
        // 6d safe area: his body inside the central 60 % of the width (the HUD dials sit in the bottom corners).
        if(bKnightSafeArea)
        {
            const float TanH=FMath::Tan(FMath::DegreesToRadians(Fov*.5f));
            const FVector KMid=FMath::Lerp(Foot,Top,.5f);
            const float KYaw=FMath::FindDeltaAngleDegrees(static_cast<float>(VR.Yaw),static_cast<float>((KMid-Lens).Rotation().Yaw));
            const float Lim=FMath::RadiansToDegrees(FMath::Atan(.6f*TanH));
            if(FMath::Abs(KYaw)>Lim){VR.Yaw+=KYaw-FMath::Sign(KYaw)*Lim;++SafeAreaYawFrames;}
        }
    }
    FQuat View=VR.Quaternion();
    if(bSafeLastView)
    {
        const float MaxTurn=((FadeTurnDegPerSec>0.f?FadeTurnDegPerSec:RigTurnRateDegPerSec)+10.f)*FMath::Max(Dt,1.f/240.f);
        const float Turn=FMath::RadiansToDegrees(static_cast<float>(View.AngularDistance(SafeLastView)));
        if(Turn>MaxTurn){View=FQuat::Slerp(SafeLastView,View,MaxTurn/Turn);View.Normalize();++ClampedTurns;}
    }
    SafeLastView=View;bSafeLastView=true;
    FramedView=View;bFramedViewValid=true;FovBoostDeg=0.f;
    BodyFraction=Fraction;SafeFraction=Fraction;RigFraction=Fraction;
    // The dragon gives way: inside its volume -> every back face clipped; skin between lens and knight -> sight fade.
    FVeyrDragonTrueSkin& True=FVeyrDragonTrueSkin::Get();
    bFadeLensInside=bProxyTight&&True.InsideVolume(Lens);
    bool bOccluded=false;
    if(bProxyTight)
        for(const float H:{.3f,.6f,.9f})
            if(True.SegmentBlocked(Lens,FMath::Lerp(Foot,Top,H))){bOccluded=true;break;}
    FadeSight=FMath::FInterpConstantTo(FadeSight,bOccluded?1.f:0.f,Dt,1.f/FMath::Max(.05f,FadeSightEaseSeconds));
    FadeSightFrames+=FadeSight>.01f;FadeInsideFrames+=bFadeLensInside;FadeShortFrames+=FadeDragonFraction<.999f;
    // Coverage fade: rays through a 6x4 grid; skin nearer than the knight that covers 15 % of the frame fades fully
    // (its distance plus the closing speed over a quarter second); eased back out. Distance fade stays the floor.
    float NearUse=FadeNearCm*S,FarUse=FadeFarCm*S;
    CoverUnfadedShare=CoverNearShare=0.f;
    if(bProxyTight)
    {
        const float Range=FMath::Min(550.f*S,static_cast<float>(FVector::Dist(Lens,FMath::Lerp(Foot,Top,.5f)))-KR);
        const float NearSkin=Range>50.f?True.NearestDistance(Lens,Range):Range;
        if(LastNearSkinCm>=0.f&&Dt>0.f&&NearSkin<Range)CoverClosingCmPerSec=FMath::FInterpTo(CoverClosingCmPerSec,(LastNearSkinCm-NearSkin)/Dt,Dt,8.f);
        else CoverClosingCmPerSec=0.f;
        LastNearSkinCm=NearSkin<Range?NearSkin:-1.f;
        float Hits[24];int32 NumHits=0;
        if(Range>50.f&&NearSkin<Range)
        {
            const FQuat VQ=FramedView;
            const UCameraComponent* Camera=nullptr;
            for(USceneComponent* Child:GetAttachChildren())if(const UCameraComponent* C=Cast<UCameraComponent>(Child)){Camera=C;break;}
            const float TanH=FMath::Tan(FMath::DegreesToRadians((Camera?Camera->FieldOfView:78.f)*.5f)),TanV=TanH/FMath::Max(.5f,ViewAspect());
            for(int32 IY=0;IY<4;++IY)for(int32 IX=0;IX<6;++IX)
            {
                const float U=-1.f+(IX+.5f)/3.f,V=-1.f+(IY+.5f)/2.f;
                const FVector Dir=VQ.RotateVector(FVector(1.f,U*TanH,V*TanV)).GetSafeNormal();
                const float T=True.SweepSphere(Lens,Lens+Dir*Range,2.f,0.f);
                if(T<.999f)Hits[NumHits++]=T*Range;
            }
        }
        float Target=0.f;
        if(NumHits>=4)
        {
            for(int32 I=1;I<NumHits;++I){const float X=Hits[I];int32 J=I-1;while(J>=0&&Hits[J]>X){Hits[J+1]=Hits[J];--J;}Hits[J+1]=X;}
            Target=Hits[3]+FMath::Max(0.f,CoverClosingCmPerSec)*.25f+20.f;
        }
        if(!bCoverageFade)Target=0.f;
        CoverNearCm=Target>CoverNearCm?Target:FMath::FInterpConstantTo(CoverNearCm,Target,Dt,400.f);
        if(CoverNearCm>NearUse){NearUse=CoverNearCm;FarUse=FMath::Max(FarUse,CoverNearCm+(FadeFarCm-FadeNearCm)*S*.5f);++CoverageFadeFrames;}
        int32 Unfaded=0;for(int32 I=0;I<NumHits;++I)Unfaded+=Hits[I]>NearUse;
        CoverNearShare=NumHits/24.f;CoverUnfadedShare=Unfaded/24.f;
    }
    AppliedFadeNearCm=NearUse;AppliedFadeFarCm=FarUse;
    if(AVeyrDragon* D=Dragon.Get())
    {
        const float Height=static_cast<float>(Top.Z-Foot.Z);
        bFadeApplied=D->SetCameraFade(Lens,FMath::Lerp(Foot,Top,.55f),NearUse,FarUse,FMath::Max(90.f,Height),
            FMath::SmoothStep(0.f,1.f,FadeSight),FadeSightFloor,bFadeLensInside);
    }
    else bFadeApplied=false;
    LastRigLens=Lens;RigFrame=GFrameCounter;RigSkinFrame=True.SkinFrame();
    return Lens;
}
