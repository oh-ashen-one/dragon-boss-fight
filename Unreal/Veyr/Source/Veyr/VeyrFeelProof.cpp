#include "VeyrFeelProof.h"
#include "VeyrDragon.h"
#include "VeyrKnight.h"
#include "VeyrGameMode.h"
#include "VeyrFightFeel.h"
#include "Dom/JsonObject.h"
#include "Dom/JsonValue.h"
#include "Engine/World.h"

bool FVeyrFeelProof::Begin(UWorld* InWorld,AVeyrKnight* InKnight,AVeyrDragon* InDragon,FHooks InHooks)
{
    World=InWorld;Knight=InKnight;Dragon=InDragon;Hooks=MoveTemp(InHooks);
    if(!InWorld||!InKnight||!InDragon)return false;
    if(!InDragon->BeginShowcase()){FailReason=TEXT("dragon could not enter rehearsal");return false;}
    // Walk past, a back stomp, the tail sweep, a flight and landing, then the collapse (head exposed).
    Segments={TEXT("Walk"),TEXT("Stomp2"),TEXT("Tail"),TEXT("Flight"),TEXT("Collapse")};
    SwordContactsAtStart=InDragon->GetSwordContactCount();
    RestUntil=.8;
    return true;
}

void FVeyrFeelProof::Mark(double Elapsed,const FString& Name)
{
    TSharedPtr<FJsonObject> E=MakeShared<FJsonObject>();
    E->SetNumberField(TEXT("seconds"),Elapsed);E->SetStringField(TEXT("event"),Name);
    if(const AVeyrDragon* D=Dragon.Get())
    {
        const FVeyrGroundContactCounters& C=D->GetGroundContactCounters();
        E->SetNumberField(TEXT("contacts"),C.Total);
    }
    Timeline.Add(MakeShared<FJsonValueObject>(E));
    UE_LOG(LogTemp,Display,TEXT("VEYR_FEEL_PROOF %.2f %s"),Elapsed,*Name);
    if(Hooks.Shot)Hooks.Shot(TEXT("feel_")+Name);
}

void FVeyrFeelProof::Drive(double Elapsed,float Dt)
{
    AVeyrKnight* K=Knight.Get();AVeyrDragon* D=Dragon.Get();
    if(bDone||!K||!D)return;
    FVector Move=FVector::ZeroVector;bool bLight=false,bHeavy=false;
    // Dragon sequence.
    if(bInSegment)
    {
        MaxSegmentSeconds=FMath::Max(MaxSegmentSeconds,static_cast<float>(Elapsed-SegmentStart));
        if(D->IsShowcaseSegmentComplete())
        {
            Mark(Elapsed,Segments[SegmentIndex].ToString()+TEXT("_done"));
            D->RestAfterShowcaseSegment();bInSegment=false;RestUntil=Elapsed+.7;
        }
        else if(Elapsed-SegmentStart>30.0)
        {FailReason=TEXT("segment overran: ")+Segments[SegmentIndex].ToString();Finalize(Elapsed);return;}
    }
    else if(Elapsed>=RestUntil&&D->State==EVeyrDragonState::Idle)
    {
        if(++SegmentIndex>=Segments.Num()){Finalize(Elapsed);return;}
        FString Error;
        if(!D->StartFeelSegment(Segments[SegmentIndex],Error)){FailReason=Error;Finalize(Elapsed);return;}
        bInSegment=true;SegmentStart=Elapsed;Mark(Elapsed,Segments[SegmentIndex].ToString());
    }
    // One scripted blow on the knight while the tail sweeps (the rehearsal dragon deals none of its own).
    if(!bScriptedHitDone&&bInSegment&&Segments[SegmentIndex]==FName(TEXT("Tail"))&&Elapsed-SegmentStart>1.2)
    {
        bScriptedHitDone=true;K->ApplyBossDamage(12.f,D->GetHeadLocation(),false);
        if(K->Health<60.f)K->Health=100.f;
        Mark(Elapsed,TEXT("scripted_knight_hit"));
    }
    // Knight: hold back until the collapse, then walk to the head and strike light, light, heavy, heavy.
    const bool bCollapse=bInSegment&&Segments[SegmentIndex]==FName(TEXT("Collapse"));
    if(bCollapse)
    {
        const FVector Head=D->GetHeadLocation();
        const FVector To=FVector(Head-K->GetActorLocation()).GetSafeNormal2D();
        const float Distance=FVector::Dist2D(Head,K->GetActorLocation());
        const float Reach=170.f+40.f*D->BodyScale;
        if(Distance>Reach)Move=To;
        if(D->IsHeadExposed())
        {
            if(FirstExposed<0.0){FirstExposed=Elapsed;Mark(Elapsed,TEXT("head_exposed"));}
            if(Distance<=Reach+60.f&&Elapsed-LastPress>(PressIndex<2?.75:1.25)&&PressIndex<4)
            {
                bLight=PressIndex<2;bHeavy=!bLight;LastPress=Elapsed;++PressIndex;
                Mark(Elapsed,bLight?TEXT("knight_light"):TEXT("knight_heavy"));
            }
        }
    }
    K->SetReplayInput(Move,bLight,bHeavy,false,false,false,false);
}

void FVeyrFeelProof::Finalize(double Elapsed)
{
    if(bDone)return;
    bDone=true;
    const AVeyrDragon* D=Dragon.Get();
    const AVeyrGameMode* Mode=World.IsValid()?World->GetAuthGameMode<AVeyrGameMode>():nullptr;
    const AVeyrFightFeel* Feel=Mode?Mode->FightFeel.Get():nullptr;
    if(FailReason.IsEmpty()&&D)
    {
        const FVeyrGroundContactCounters& C=D->GetGroundContactCounters();
        if(C.ByPart[static_cast<int32>(EVeyrGroundContactPart::Foot)]<4)FailReason=TEXT("fewer than four foot contacts");
        else if(C.ByClass[static_cast<int32>(EVeyrGroundContactClass::BodyFall)]+C.ByClass[static_cast<int32>(EVeyrGroundContactClass::Landing)]<1)
            FailReason=TEXT("no body fall or landing contact");
        else if(D->GetSwordContactCount()-SwordContactsAtStart<2)FailReason=TEXT("fewer than two sword contacts on the exposed head");
        else if(Feel&&Feel->HurtKicks<1)FailReason=TEXT("no hurt kick");
    }
    Mark(Elapsed,FailReason.IsEmpty()?TEXT("finished"):TEXT("failed"));
    if(Hooks.Finish)Hooks.Finish(FailReason.IsEmpty(),FailReason.IsEmpty()?TEXT("feel sequence complete"):FailReason);
}

TSharedPtr<FJsonObject> FVeyrFeelProof::Evidence() const
{
    TSharedPtr<FJsonObject> O=MakeShared<FJsonObject>();
    O->SetArrayField(TEXT("timeline"),Timeline);
    O->SetNumberField(TEXT("segmentsStarted"),FMath::Max(0,FMath::Min(SegmentIndex+1,Segments.Num())));
    O->SetNumberField(TEXT("maxSegmentSeconds"),MaxSegmentSeconds);
    O->SetBoolField(TEXT("scriptedKnightHit"),bScriptedHitDone);
    O->SetStringField(TEXT("scriptedKnightHitNote"),TEXT("12 damage applied by the proof (the rehearsal dragon deals no damage)"));
    O->SetNumberField(TEXT("knightPresses"),PressIndex);
    if(const AVeyrDragon* D=Dragon.Get())O->SetNumberField(TEXT("swordContacts"),D->GetSwordContactCount()-SwordContactsAtStart);
    O->SetBoolField(TEXT("done"),bDone);O->SetStringField(TEXT("failReason"),FailReason);
    return O;
}
