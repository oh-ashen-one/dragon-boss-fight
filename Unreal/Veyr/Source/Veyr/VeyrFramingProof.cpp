#include "VeyrFramingProof.h"
#include "VeyrDragon.h"
#include "VeyrKnight.h"
#include "Dom/JsonObject.h"
#include "Dom/JsonValue.h"
#include "Engine/World.h"
#include "GameFramework/Controller.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"

namespace
{
    constexpr float PhaseEnds[7]={8.f,18.f,26.f,34.f,42.f,52.f,60.f};
    constexpr float Settle=2.f;
}

const TCHAR* FVeyrFramingProof::PhaseName(int32 Index)
{
    static const TCHAR* Names[7]={TEXT("standoff"),TEXT("circle"),TEXT("hug_leg"),TEXT("under_belly"),TEXT("back_off"),TEXT("sprint_away_back"),TEXT("flight_pass")};
    return Names[FMath::Clamp(Index,0,6)];
}

bool FVeyrFramingProof::Begin(UWorld* InWorld,AVeyrKnight* InKnight,AVeyrDragon* InDragon,FHooks InHooks)
{
    World=InWorld;Knight=InKnight;Dragon=InDragon;Hooks=MoveTemp(InHooks);
    if(!InWorld||!InKnight||!InDragon)return false;
    S=FMath::Max(.5f,InDragon->BodyScale*.5f);
    bUnlocked=FParse::Param(FCommandLine::Get(),TEXT("VeyrFramingUnlocked"));
    for(FVeyrFramingMeter& M:Meters)M.Begin(InKnight,InDragon);
    FlightsAtStart=InDragon->GetAttackCount(EVeyrDragonMove::FlyAway);
    return true;
}

void FVeyrFramingProof::Drive(double Elapsed,float Dt)
{
    if(bDone)return;
    AVeyrKnight* K=Knight.Get();AVeyrDragon* D=Dragon.Get();
    if(!K||!D)return;
    if(Start<0.0)Start=Elapsed;
    const float T=static_cast<float>(Elapsed-Start)-Settle;
    if(K->Health<45.f){K->Health=100.f;++HealthRefills;} // same refill as the camp mode, so the route always completes
    if(bUnlocked==K->bLockedOn)K->ToggleLockOn();
    if(T<0.f){K->SetReplayInput(FVector::ZeroVector,false,false,false,false,false,false);return;}
    if(T>=PhaseEnds[6])
    {
        bDone=true;K->SetReplayInput(FVector::ZeroVector,false,false,false,false,false,false);K->SetSprintRequested(false);
        FString Summary;
        for(int32 I=0;I<7;++I)Summary+=FString::Printf(TEXT("%s%s %.2f"),I?TEXT(", "):TEXT(""),PhaseName(I),Meters[I].KnightFullyInFrameShare());
        if(Hooks.Finish)Hooks.Finish(true,TEXT("framing route completed; knight fully in frame by phase: ")+Summary);
        return;
    }
    int32 Now=0;while(Now<6&&T>=PhaseEnds[Now])++Now;
    const FVector Body=D->GetActorLocation();
    const FVector Feet=K->GetFootLocation();
    if(Now!=Phase)
    {
        Phase=Now;
        Away=(Feet-Body).GetSafeNormal2D();if(Away.IsNearlyZero())Away=D->GetActorForwardVector();
        CircleStartYaw=static_cast<float>(Away.Rotation().Yaw);
        Leg=FVector::Dist2D(Feet,D->GetLegLocation(0))<FVector::Dist2D(Feet,D->GetLegLocation(1))?0:1;
        if(Hooks.Shot){Hooks.Shot(FString::Printf(TEXT("framing_%s_start"),PhaseName(Phase)));}
        LastShot=Elapsed;
    }
    else if(Elapsed-LastShot>4.0&&Hooks.Shot){LastShot=Elapsed;Hooks.Shot(FString::Printf(TEXT("framing_%s"),PhaseName(Phase)));}
    Meters[Phase].Sample(Dt);

    const float PhaseT=T-(Phase?PhaseEnds[Phase-1]:0.f);
    FVector Target=Feet;bool bSprint=false,bAttack=false;float Arrive=150.f;
    switch(Phase)
    {
        case 0:Target=Body+Away*1500.f*S;break;                                  // stand-off
        case 1:                                                                  // circle at mid range, half a turn
        {
            const float Yaw=CircleStartYaw+18.f*PhaseT+25.f;
            Target=Body+FRotator(0,Yaw,0).Vector()*950.f*S;Arrive=40.f;break;
        }
        case 2:Target=D->GetLegLocation(Leg);Arrive=220.f;bAttack=true;break;   // hug a front leg and hit it
        case 3:Target=D->GetChestLocation();Target.Z=Feet.Z;Arrive=120.f;break;   // stand under the belly
        case 4:Target=Body+Away*1600.f*S;Arrive=60.f;break;                       // back off (walk) while it strikes
        case 5:Target=PhaseT<5.f?Body+Away*2400.f*S:Body+Away*700.f*S;bSprint=true;Arrive=80.f;break;
        case 6:
        {
            Target=Body+FRotator(0,CircleStartYaw+60.f,0).Vector()*1000.f*S;Arrive=80.f;
            bFlightSeen=bFlightSeen||D->GetAttackCount(EVeyrDragonMove::FlyAway)>FlightsAtStart||D->IsFlightHazardActive();
            if(!bFlightSeen&&!bFlightRequested&&D->State==EVeyrDragonState::Idle&&FlightRequestAttempts<600)
            {
                ++FlightRequestAttempts;
                bFlightRequested=D->PlayDataMove(TEXT("flight"));
            }
            break;
        }
        default:break;
    }
    FVector To=Target-Feet;To.Z=0;
    const bool bArrived=To.Size()<Arrive;
    const bool bSwing=bAttack&&bArrived&&FMath::Fmod(Elapsed,.6)<Dt*1.5;
    K->SetSprintRequested(bSprint&&!bArrived);
    K->SetReplayInput(bArrived?FVector::ZeroVector:To.GetSafeNormal(),bSwing,false,false,false,false,false);
    if(bUnlocked)
        if(AController* C=K->GetController())
        {
            // A player-like look: turn toward the dragon's chest at a human rate, a little upward.
            const FVector Chest=D->GetChestLocation();
            const FRotator Want(8.f,(Chest-K->GetActorLocation()).Rotation().Yaw,0.f);
            const FRotator Current=C->GetControlRotation().GetNormalized();
            C->SetControlRotation(FMath::RInterpConstantTo(Current,FMath::RInterpTo(Current,Want,Dt,3.f),Dt,120.f));
        }
}

TSharedPtr<FJsonObject> FVeyrFramingProof::Evidence() const
{
    TSharedPtr<FJsonObject> O=MakeShared<FJsonObject>();
    O->SetBoolField(TEXT("done"),bDone);O->SetBoolField(TEXT("unlocked"),bUnlocked);
    O->SetNumberField(TEXT("dragonScaleFactor"),S);O->SetNumberField(TEXT("knightHealthRefills"),HealthRefills);
    O->SetBoolField(TEXT("flightSeen"),bFlightSeen);O->SetBoolField(TEXT("flightRequested"),bFlightRequested);
    O->SetNumberField(TEXT("flightRequestAttempts"),FlightRequestAttempts);
    TSharedPtr<FJsonObject> Phases=MakeShared<FJsonObject>();
    for(int32 I=0;I<7;++I)Phases->SetObjectField(PhaseName(I),Meters[I].Evidence());
    O->SetObjectField(TEXT("phases"),Phases);
    return O;
}
