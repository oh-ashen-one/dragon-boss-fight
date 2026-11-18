// B4 (2026-11-18): the dragon's ground contacts, gathered from the evaluated pose every tick.
// Additive to VeyrDragon.cpp; the detector itself is VeyrGroundContacts.cpp.
#include "VeyrDragon.h"
#include "VeyrSkeletalPresentation.h"
#include "VeyrVisualDefinition.h"
#include "VeyrDragonGrounding.h"
#include "Engine/World.h"

bool AVeyrDragon::ContactsDriveShake()
{
    return VeyrFeelSwitches::WeightShake();
}

void AVeyrDragon::UpdateGroundContacts(float DeltaSeconds)
{
    if(!VeyrFeelSwitches::GroundContacts()||!bUsingCustomuseVisual||!ImportedPresentation||!ImportedPresentation->bPoseEvaluated)return;
    if(IsAirborne())LastAirborneClock=Clock;
    static const UEnum* States=StaticEnum<EVeyrDragonState>();
    static TArray<FName> StateNames;
    if(StateNames.IsEmpty()&&States)
        for(int32 I=0;I<=static_cast<int32>(EVeyrDragonState::Dead);++I)StateNames.Add(FName(*States->GetNameStringByValue(I)));
    FVeyrContactContext Context;
    Context.BodyScale=BodyScale;Context.GameTime=GetWorld()?GetWorld()->GetTimeSeconds():0.f;
    Context.StateName=StateNames.IsValidIndex(static_cast<int32>(State))?StateNames[static_cast<int32>(State)]:NAME_None;
    const bool bStrikeState=State==EVeyrDragonState::Windup||State==EVeyrDragonState::Active;
    Context.bFootStrike=bStrikeState&&(Move==EVeyrDragonMove::BackStomp||Move==EVeyrDragonMove::ClawSwipe||Move==EVeyrDragonMove::TailSmack||Move==EVeyrDragonMove::Bite);
    Context.bTailStrike=Move==EVeyrDragonMove::TailSmack&&(bStrikeState||State==EVeyrDragonState::Recovery);
    Context.bHeadStrike=Move==EVeyrDragonMove::Bite&&State==EVeyrDragonState::Active;
    Context.bLanding=(Move==EVeyrDragonMove::FlyAway&&State==EVeyrDragonState::Recovery)||
        Clock-LastAirborneClock<VeyrFeelTuning().LandingWindowSeconds;
    GroundContacts.BeginFrame(DeltaSeconds,Context);

    // Feet: the skinned sole points (same weights as the renderer), floor traced under each foot.
    FVeyrSoleSample Soles;
    float FloorZ=0.f;
    if(ImportedPresentation->MeasureSoles(Soles)&&Soles.bValid)
    {
        FloorZ=TNumericLimits<float>::Max();
        static const FName FootNames[4]={TEXT("foot0"),TEXT("foot1"),TEXT("foot2"),TEXT("foot3")};
        for(int32 I=0;I<4;++I)
        {
            FloorZ=FMath::Min(FloorZ,Soles.FloorZ[I]);
            GroundContacts.Sample(I,FootNames[I],EVeyrGroundContactPart::Foot,I,
                FVector(Soles.Lowest[I].X,Soles.Lowest[I].Y,Soles.FloorZ[I]+Soles.SoleAboveFloorCm[I]),Soles.FloorZ[I]);
        }
    }
    else FloorZ=0.f;

    // Body: the hurt capsules fitted to the mesh. Leg capsules are left to the soles.
    int32 Slot=4;
    for(const FVeyrHurtPartRuntime& Part:HurtParts)
    {
        if(Slot>=FVeyrGroundContactDetector::MaxSlots)break;
        EVeyrGroundContactPart Kind;
        if(Part.Kind==FName(TEXT("leg")))continue;
        else if(Part.Kind==FName(TEXT("head")))Kind=EVeyrGroundContactPart::Head;
        else if(Part.Kind==FName(TEXT("neck")))Kind=EVeyrGroundContactPart::Neck;
        else if(Part.Kind==FName(TEXT("tail")))Kind=EVeyrGroundContactPart::Tail;
        else if(Part.Kind==FName(TEXT("wing")))Kind=EVeyrGroundContactPart::Wing;
        else Kind=EVeyrGroundContactPart::Body;
        FVector A,B;float Radius=0.f;
        const int32 Index=Slot++;
        if(!HurtPartWorldSegment(Part,A,B,Radius))continue;
        const FVector Low=A.Z<B.Z?A:B;
        GroundContacts.Sample(Index,Part.Part,Kind,INDEX_NONE,Low-FVector(0,0,Radius),FloorZ);
    }
    GroundContacts.EndFrame();
    for(const FVeyrGroundContact& C:GroundContacts.ThisFrame())
    {
        UE_LOG(LogTemp,Verbose,TEXT("VEYR_GROUND_CONTACT %d %s class=%d tier=%d speed=%.2f scaled=%.2f"),C.Serial,*C.PartName.ToString(),
            static_cast<int32>(C.Class),C.DustTier,C.SpeedMps,C.ScaledSpeedMps);
        OnGroundContact.Broadcast(this,C);
    }
}

bool AVeyrDragon::StartFeelSegment(FName Segment,FString& Error)
{
    if(!bShowcaseMode||State!=EVeyrDragonState::Idle||!ShowcaseSegment.IsNone())
    {Error=TEXT("Feel segment requires an idle rehearsal actor");return false;}
    if(Segment==FName(TEXT("Collapse")))
    {
        ShowcaseSegment=Segment;ShowcaseOverrideClip=NAME_None;ShowcaseLeg=INDEX_NONE;StruckLeg=0;
        EnterState(EVeyrDragonState::Collapse,VideoStateDuration(TEXT("Collapse"),1.f));
        return true;
    }
    return StartShowcaseSegment(Segment,Error);
}
