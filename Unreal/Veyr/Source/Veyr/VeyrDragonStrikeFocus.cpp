// Phase D (2026-11-18): what the knight's camera aims at on a giant dragon. Read-only queries.
#include "VeyrDragon.h"

FVector AVeyrDragon::GetChestLocation() const
{
    FVector A,B;float Radius=0.f;
    if(GetHurtPartWorld(TEXT("chest"),A,B,Radius))return (A+B)*.5f;
    // Proxy or unbound parts: a point a little under halfway from the body centre to the head.
    return FMath::Lerp(GetActorLocation(),GetHeadLocation(),.45f);
}

bool AVeyrDragon::GetStrikeFocus(FVector& OutPoint,FName* OutLimb) const
{
    OutPoint=GetActorLocation();
    if(IsDead()||bEncounterStopped)return false;
    const bool bStriking=State==EVeyrDragonState::Windup||State==EVeyrDragonState::Active||
        (State==EVeyrDragonState::Recovery&&StateElapsed<.5f);
    if(!bStriking)return false;
    auto Limb=[OutLimb](const TCHAR* Name){if(OutLimb)*OutLimb=FName(Name);};
    if(Move==EVeyrDragonMove::FlyAway)
    {
        if(!IsFlightHazardActive())return false;
        OutPoint=GetFlightHazardPoint();Limb(TEXT("flight"));return true;
    }
    if(Move==EVeyrDragonMove::Fire)
    {
        const FVeyrDragonFlameBeam Beam=GetActiveFlameBeam();
        OutPoint=Beam.bDamaging?Beam.Origin+Beam.Direction*Beam.Length*.6f:GetMouthLocation();
        Limb(TEXT("fire"));return true;
    }
    if(bUsingCustomuseVisual&&bImportedTargetsValid)
    {
        const TArray<FVeyrDragonContact> Contacts=GetImportedContacts();
        if(!Contacts.IsEmpty())
        {
            if(Move==EVeyrDragonMove::TailSmack)
            {
                // The swinging end of the tail: halfway along the segments from the middle to the tip.
                const FVeyrDragonContact& Last=Contacts.Last();
                const FVeyrDragonContact& Mid=Contacts[Contacts.Num()/2];
                OutPoint=(Mid.Start+Last.End)*.5f;Limb(TEXT("tail"));return true;
            }
            const FVeyrDragonContact& C=Contacts[0];
            OutPoint=Move==EVeyrDragonMove::Bite?C.End:(C.Start+C.End)*.5f;
            Limb(Move==EVeyrDragonMove::Bite?TEXT("mouth"):Move==EVeyrDragonMove::BackStomp?TEXT("stomp"):TEXT("claw"));
            return true;
        }
    }
    switch(Move)
    {
        case EVeyrDragonMove::Bite:OutPoint=GetMouthLocation();Limb(TEXT("mouth"));return true;
        case EVeyrDragonMove::ClawSwipe:OutPoint=GetLegLocation(ClawLeg);Limb(TEXT("claw"));return true;
        case EVeyrDragonMove::BackStomp:OutPoint=GetLegLocation(StompLeg);Limb(TEXT("stomp"));return true;
        case EVeyrDragonMove::TailSmack:
            OutPoint=GetActorLocation()-GetActorForwardVector()*600.f*BodyScale;Limb(TEXT("tail"));return true;
        default:return false;
    }
}
