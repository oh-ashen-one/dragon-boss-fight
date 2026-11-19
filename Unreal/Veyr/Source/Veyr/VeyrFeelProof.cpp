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
    // Walk in, a back stomp, the tail sweep, the collapse (head exposed, knight strikes), then a flight and landing.
    Segments={TEXT("Walk"),TEXT("Stomp2"),TEXT("Tail"),TEXT("Collapse"),TEXT("Flight")};
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
    // Every floor contact with its game time, for picking film frames.
    {
        static const TCHAR* Parts[6]={TEXT("foot"),TEXT("head"),TEXT("neck"),TEXT("body"),TEXT("tail"),TEXT("wing")};
        static const TCHAR* Classes[4]={TEXT("footfall"),TEXT("stomp"),TEXT("bodyFall"),TEXT("landing")};
        TArray<FVeyrGroundContact> New;LastContactSerial=D->GetGroundContactsSince(LastContactSerial,New);
        for(const FVeyrGroundContact& C:New)
        {
            TSharedPtr<FJsonObject> O=MakeShared<FJsonObject>();
            O->SetNumberField(TEXT("seconds"),Elapsed);O->SetStringField(TEXT("part"),C.PartName.ToString());
            O->SetStringField(TEXT("kind"),Parts[FMath::Clamp(static_cast<int32>(C.Part),0,5)]);
            O->SetStringField(TEXT("class"),Classes[FMath::Clamp(static_cast<int32>(C.Class),0,3)]);
            O->SetNumberField(TEXT("tier"),C.DustTier);O->SetNumberField(TEXT("scaledSpeed"),FMath::RoundToFloat(C.ScaledSpeedMps*100.f)/100.f);
            O->SetNumberField(TEXT("strength"),FMath::RoundToFloat(C.Strength*100.f)/100.f);
            Contacts.Add(MakeShared<FJsonValueObject>(O));
        }
    }
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
    // After the stomp the dragon waits (up to 3 s more) for the knight's heavy blow on a standing foreleg.
    else if(Elapsed>=RestUntil&&D->State==EVeyrDragonState::Idle&&(bLegStrikeDone||SegmentIndex!=1||Elapsed>=RestUntil+3.0))
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
    // Knight: walk in under the dragon from the start; once it stands after the stomp, one heavy blow on the nearest
    // leg (the standing whole-spine flinch). Then hold until the collapse, walk to the head and strike light, light, heavy.
    if(!bLegStrikeDone&&SegmentIndex<=2&&!D->IsAirborne())
    {
        int32 Leg=0;float Near=TNumericLimits<float>::Max();
        for(int32 I=0;I<4;++I){const float L=FVector::Dist2D(D->GetLegLocation(I),K->GetActorLocation());if(L<Near){Near=L;Leg=I;}}
        const float Reach=220.f+75.f*D->BodyScale;
        if(Near>Reach-80.f)Move=FVector(D->GetLegLocation(Leg)-K->GetActorLocation()).GetSafeNormal2D();
        if(!bInSegment&&SegmentIndex==1&&Near<=Reach&&D->State==EVeyrDragonState::Idle&&LegStrikeAt<0.0)
        {
            bHeavy=true;LegStrikeAt=Elapsed;LegStrikeContacts=D->GetSwordContactCount();
            Mark(Elapsed,TEXT("knight_leg_heavy"));
        }
    }
    if(LegStrikeAt>=0.0&&!bLegStrikeDone&&Elapsed-LegStrikeAt>1.2)
    {
        bLegStrikeDone=true;
        Mark(Elapsed,D->GetSwordContactCount()>LegStrikeContacts?TEXT("leg_hit"):TEXT("leg_missed"));
    }
    if(bLegStrikeDone&&SegmentIndex>=1&&SegmentIndex<3)Move=FVector::ZeroVector;
    const bool bCollapse=bInSegment&&Segments[SegmentIndex]==FName(TEXT("Collapse"));
    if(bCollapse)
    {
        const FVector Head=D->GetHeadLocation();
        FVector To=FVector(Head-K->GetActorLocation()).GetSafeNormal2D();
        // From under the body the fallen legs are in the way: go round to the front of the snout first.
        const FVector Fwd=D->GetActorForwardVector().GetSafeNormal2D(),Side=FVector::CrossProduct(FVector::UpVector,Fwd);
        const FVector Rel=K->GetActorLocation()-Head;
        if(FVector::DotProduct(Rel,Fwd)<120.f*D->BodyScale)
        {
            const float Sign=FVector::DotProduct(Rel,Side)>=0.f?1.f:-1.f;
            To=FVector(Head+Fwd*(220.f*D->BodyScale)+Side*(Sign*160.f*D->BodyScale)-K->GetActorLocation()).GetSafeNormal2D();
        }
        const float Distance=FVector::Dist2D(Head,K->GetActorLocation());
        // The head's solid capsule is ~100 cm x BodyScale: the knight stops against it, so reach is measured to its centre.
        const float Reach=200.f+120.f*D->BodyScale;
        if(Distance>Reach-120.f)Move=To;
        if(D->IsHeadExposed()||D->State==EVeyrDragonState::Collapse)
        {
            if(FirstExposed<0.0&&D->IsHeadExposed()){FirstExposed=Elapsed;Mark(Elapsed,TEXT("head_exposed"));}
            if(D->IsHeadExposed()&&Distance<=Reach&&Elapsed-LastPress>(PressIndex<2?.7:1.2)&&PressIndex<4)
            {
                bLight=PressIndex<2;bHeavy=!bLight;LastPress=Elapsed;++PressIndex;
                Mark(Elapsed,bLight?TEXT("knight_light"):TEXT("knight_heavy"));
            }
        }
    }
    K->SetSprintRequested(!Move.IsNearlyZero());
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
    O->SetArrayField(TEXT("timeline"),Timeline);O->SetArrayField(TEXT("contacts"),Contacts);
    O->SetNumberField(TEXT("segmentsStarted"),FMath::Max(0,FMath::Min(SegmentIndex+1,Segments.Num())));
    O->SetNumberField(TEXT("maxSegmentSeconds"),MaxSegmentSeconds);
    O->SetBoolField(TEXT("scriptedKnightHit"),bScriptedHitDone);
    O->SetStringField(TEXT("scriptedKnightHitNote"),TEXT("12 damage applied by the proof (the rehearsal dragon deals no damage)"));
    O->SetNumberField(TEXT("knightPresses"),PressIndex);
    if(const AVeyrDragon* D=Dragon.Get())O->SetNumberField(TEXT("swordContacts"),D->GetSwordContactCount()-SwordContactsAtStart);
    O->SetBoolField(TEXT("done"),bDone);O->SetStringField(TEXT("failReason"),FailReason);
    // Bfeel: what each shake did to the picture (percent of the frame height), so a check is a number beside the clip.
    if(const UWorld* W=World.Get())
        if(const auto* Mode=W->GetAuthGameMode<AVeyrGameMode>())
            if(Mode->FightFeel)O->SetObjectField(TEXT("imageShift"),Mode->FightFeel->ImageShiftEvidence());
    return O;
}
