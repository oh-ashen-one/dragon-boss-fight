// B4 (2026-11-18): the dragon's ground contacts, gathered from the evaluated pose every tick.
// Additive to VeyrDragon.cpp; the detector itself is VeyrGroundContacts.cpp.
#include "VeyrDragon.h"
#include "VeyrSkeletalPresentation.h"
#include "VeyrVisualDefinition.h"
#include "VeyrDragonGrounding.h"
#include "VeyrFightFeel.h"
#include "VeyrGameMode.h"
#include "Engine/World.h"

bool AVeyrDragon::ContactsDriveShake() const
{
    // Only when contacts can actually fire and the feel actor will turn them into shake; otherwise the
    // fixed per-move impacts keep shaking (legacy/off switches, or a dragon without the imported pose).
    if(!VeyrFeelSwitches::WeightShake()||!bUsingCustomuseVisual||!ImportedPresentation||!ImportedPresentation->bPoseEvaluated)return false;
    const AVeyrGameMode* Mode=GetWorld()?GetWorld()->GetAuthGameMode<AVeyrGameMode>():nullptr;
    return Mode&&Mode->FightFeel&&Mode->FightFeel->UsesContactFraming();
}

void AVeyrDragon::UpdateGroundContacts(float DeltaSeconds)
{
    if(!VeyrFeelSwitches::GroundContacts())return;
    if(!bUsingCustomuseVisual||!ImportedPresentation||!ImportedPresentation->bPoseEvaluated){GroundContacts.Forget();return;}
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
    Context.bAirborne=IsAirborne();
    Context.bBodyDown=State==EVeyrDragonState::Buckle||State==EVeyrDragonState::Collapse||State==EVeyrDragonState::Exposed||
        State==EVeyrDragonState::Rise||State==EVeyrDragonState::Dead;
    // The hit flinch rocks the pose for presentation; parts it lifts and drops are not the dragon's weight.
    if(const AVeyrGameMode* Mode=GetWorld()?GetWorld()->GetAuthGameMode<AVeyrGameMode>():nullptr)
        if(Mode->FightFeel)Context.bMuted=Mode->FightFeel->FlinchDisplacesPose();
    GroundContacts.BeginFrame(DeltaSeconds,Context);

    // Feet: the skinned sole points (same weights as the renderer), floor traced under each foot.
    FVeyrSoleSample Soles;
    float FloorZ=0.f;
    if(ImportedPresentation->MeasureSoles(Soles)&&Soles.bValid)
    {
        FloorZ=TNumericLimits<float>::Max();
        static const FName FootNames[4]={TEXT("foot0"),TEXT("foot1"),TEXT("foot2"),TEXT("foot3")};
        const float ActorZ=static_cast<float>(GetActorLocation().Z);
        for(int32 I=0;I<4;++I)
        {
            // A missed floor trace reports the actor's own height (17 m up in flight): use the arena floor (Z 0) instead.
            const float Floor=FMath::IsNearlyEqual(Soles.FloorZ[I],ActorZ,.01f)&&ActorZ>1.f?0.f:Soles.FloorZ[I];
            FloorZ=FMath::Min(FloorZ,Floor);
            if(IsFootLockStepping(I))continue; // F3 review M2: a lock step is not the clip's footfall
            GroundContacts.Sample(I,FootNames[I],EVeyrGroundContactPart::Foot,I,
                FVector(Soles.Lowest[I].X,Soles.Lowest[I].Y,Soles.FloorZ[I]+Soles.SoleAboveFloorCm[I]),Floor);
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
