#include "VeyrGroundContacts.h"

FVeyrGroundContactDetector::FVeyrGroundContactDetector()
{
    Frame.Reserve(MaxSlots);
}

void FVeyrGroundContactDetector::Reset()
{
    for(FSlot& S:Slots)S=FSlot();
    Frame.Reset();
}

void FVeyrGroundContactDetector::Forget()
{
    bool Any=false;
    for(FSlot& S:Slots){Any|=S.bSeen;S.bSeen=false;S.PeakDown=0.f;}
    if(Any)++Count.Resets;
    Frame.Reset();
}

void FVeyrGroundContactDetector::BeginFrame(float GameDelta,const FVeyrContactContext& Context)
{
    Delta=FMath::Max(0.f,GameDelta);Ctx=Context;Frame.Reset();
    for(FSlot& S:Slots){S.bSampledThisFrame=false;S.SinceEvent+=Delta;}
}

void FVeyrGroundContactDetector::Sample(int32 Index,FName Name,EVeyrGroundContactPart Part,int32 Leg,const FVector& LowestPoint,float FloorZ)
{
    if(Index<0||Index>=MaxSlots||LowestPoint.ContainsNaN()||!FMath::IsFinite(FloorZ))return;
    const FVeyrFeelTuning& T=VeyrFeelTuning();
    const FVeyrFeelTuning::FPart& P=Part==EVeyrGroundContactPart::Foot?T.Foot:Part==EVeyrGroundContactPart::Head?T.Head:
        Part==EVeyrGroundContactPart::Neck?T.Neck:Part==EVeyrGroundContactPart::Tail?T.Tail:Part==EVeyrGroundContactPart::Wing?T.Wing:T.Body;
    const float Scale=FMath::Max(.1f,Ctx.BodyScale);
    FSlot& S=Slots[Index];
    const float Clearance=static_cast<float>(LowestPoint.Z)-FloorZ;
    S.bSampledThisFrame=true;S.Name=Name;S.Part=Part;S.Leg=Leg;
    S.Point=FVector(LowestPoint.X,LowestPoint.Y,FloorZ+1.f);
    if(Ctx.bAirborne&&Part==EVeyrGroundContactPart::Foot)S.bPendingLanding=true;
    float& Lowest=MinClearance.FindOrAdd(Ctx.StateName).FindOrAdd(Name,TNumericLimits<float>::Max());
    Lowest=FMath::Min(Lowest,Clearance);
    // First sight, or a jump no pose can make in one frame (a teleport, a mesh swap): seed, no event.
    if(!S.bSeen||FMath::Abs(Clearance-S.Clearance)>400.f*Scale)
    {
        S.bSeen=true;S.Clearance=Clearance;S.PeakDown=0.f;S.bArmed=Clearance>P.LiftCm*Scale;return;
    }
    if(Delta>1e-5f)
    {
        const float Down=(S.Clearance-Clearance)/Delta; // cm/s into the floor
        // Peak of the recent descent: the speed at the moment of contact, not the stopped frame after it.
        S.PeakDown=FMath::Max(Down,S.PeakDown*FMath::Exp(-Delta/FMath::Max(.01f,T.PeakTimeConstant)));
    }
    const float Touch=P.TouchCm*Scale,Lift=P.LiftCm*Scale;
    if(S.bArmed&&Clearance<=Touch)
    {
        S.bArmed=false;
        const float Speed=FMath::Max(0.f,S.PeakDown);
        if(Ctx.bMuted)++Count.Muted;
        else if(Speed/100.f/Scale>=P.MinSpeedMps&&S.SinceEvent>=T.MinEventInterval)Emit(S,Speed);
        else ++Count.Rejected;
        if(!Ctx.bAirborne)S.bPendingLanding=false; // only the first touchdown after flight is the landing
    }
    else if(!S.bArmed&&Clearance>=Lift)S.bArmed=true;
    S.Clearance=Clearance;
}

void FVeyrGroundContactDetector::EndFrame()
{
    // A part the pose did not give this frame cannot be trusted next frame either.
    for(FSlot& S:Slots)if(!S.bSampledThisFrame)S.bSeen=false;
}

void FVeyrGroundContactDetector::Emit(FSlot& S,float SpeedCmS)
{
    const FVeyrFeelTuning& T=VeyrFeelTuning();
    const float Scale=FMath::Max(.1f,Ctx.BodyScale);
    FVeyrGroundContact C;
    C.Part=S.Part;C.PartName=S.Name;C.Leg=S.Leg;C.World=S.Point;
    C.SpeedMps=SpeedCmS/100.f;C.ScaledSpeedMps=C.SpeedMps/Scale;C.GameTime=Ctx.GameTime;
    const bool bFoot=S.Part==EVeyrGroundContactPart::Foot;
    if(bFoot)
        C.Class=Ctx.bLanding&&S.bPendingLanding?EVeyrGroundContactClass::Landing:
            (Ctx.bFootStrike&&C.ScaledSpeedMps>=T.StompMinSpeed)?EVeyrGroundContactClass::Stomp:EVeyrGroundContactClass::Footfall;
    else if(S.Part==EVeyrGroundContactPart::Tail)
        C.Class=Ctx.bTailStrike?EVeyrGroundContactClass::Stomp:Ctx.bBodyDown?EVeyrGroundContactClass::BodyFall:EVeyrGroundContactClass::Footfall;
    else if(S.Part==EVeyrGroundContactPart::Wing)
        C.Class=Ctx.bBodyDown?EVeyrGroundContactClass::BodyFall:EVeyrGroundContactClass::Footfall; // a wing tip grazing in a turn
    else if(S.Part==EVeyrGroundContactPart::Head&&Ctx.bHeadStrike)C.Class=EVeyrGroundContactClass::Stomp;
    // Head, neck or trunk: a fall when the body is going down or the touch is fast; a slow graze shakes like a step.
    else C.Class=Ctx.bBodyDown||C.ScaledSpeedMps>=T.BodyCloudMinSpeed?EVeyrGroundContactClass::BodyFall:EVeyrGroundContactClass::Footfall;
    C.Strength=T.ClassStrength(static_cast<EVeyrFeelClass>(C.Class),C.ScaledSpeedMps);
    switch(C.Class)
    {
        case EVeyrGroundContactClass::Landing:C.DustTier=4;break;
        // Only a real fall throws the big cloud; a slower settle gets the ordinary medium or large dust.
        case EVeyrGroundContactClass::BodyFall:C.DustTier=C.ScaledSpeedMps>=T.BodyCloudMinSpeed?3:C.ScaledSpeedMps<T.DustTierMaxSpeed[1]?1:2;break;
        default:C.DustTier=C.ScaledSpeedMps<T.DustTierMaxSpeed[0]?0:C.ScaledSpeedMps<T.DustTierMaxSpeed[1]?1:2;
            if(C.Class==EVeyrGroundContactClass::Stomp)C.DustTier=FMath::Max(C.DustTier,1);break;
    }
    C.Serial=++Serial;
    Frame.Add(C);Ring[C.Serial%RingSize]=C;
    S.SinceEvent=0.f;
    ++Count.Total;++Count.ByPart[static_cast<int32>(C.Part)];++Count.ByClass[static_cast<int32>(C.Class)];
    ++Count.ByTier[FMath::Clamp(C.DustTier,0,4)];if(bFoot&&C.Leg>=0&&C.Leg<4)++Count.Feet[C.Leg];
    Count.MaxSpeedMps=FMath::Max(Count.MaxSpeedMps,C.SpeedMps);Count.MaxScaledSpeedMps=FMath::Max(Count.MaxScaledSpeedMps,C.ScaledSpeedMps);
}

int32 FVeyrGroundContactDetector::CopySince(int32 AfterSerial,TArray<FVeyrGroundContact>& Out) const
{
    Out.Reset();
    for(int32 I=FMath::Max(AfterSerial+1,Serial-RingSize+1);I<=Serial;++I)Out.Add(Ring[I%RingSize]);
    return Serial;
}
