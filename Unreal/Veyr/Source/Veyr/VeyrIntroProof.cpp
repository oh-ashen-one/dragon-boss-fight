#include "VeyrReplay.h"
#include "VeyrArenaTour.h"
#include "VeyrGameMode.h"
#include "VeyrKnight.h"
#include "VeyrDragon.h"
#include "VeyrAudio.h"
#include "GameFramework/PlayerController.h"
#include "Engine/World.h"

void AVeyrReplay::TickArenaIntroProof()
{
    AVeyrGameMode* Mode=GetWorld()->GetAuthGameMode<AVeyrGameMode>();
    if(!Mode||!Mode->Audio){Finish(false,TEXT("Intro proof requires the production mode and audio"));return;}
    if(Mode->IsArenaIntroActive())
    {
        if(!bIntroObserved)IntroInitialOrigin=Knight->GetFootLocation();
        bIntroObserved=true;
        Knight->SetReplayInput(Elapsed>.5f?FVector::ForwardVector:FVector::ZeroVector,false,false,false,false,false,false);
        if(!bIntroInputProbeIssued&&Elapsed>.5f)
        {
            Knight->PressPrimaryAttack();Knight->ReleasePrimaryAttack();Knight->TryRoll();
            bIntroInputProbeIssued=true;Event(TEXT("intro_attack_roll_inputs_probed"),false);
        }
        if(Knight->HasEnteredEncounter()||Knight->Health!=100.f||Knight->Stamina!=100.f||Knight->HealingCharges!=4||
           Knight->LightAttacks||Knight->HeavyAttacks||Knight->Rolls||Dragon->Health!=Dragon->MaxHealth||Dragon->State!=EVeyrDragonState::Idle||
           FVector::Dist2D(IntroInitialOrigin,Knight->GetFootLocation())>5.f||
           Mode->Audio->MusicStarts!=0||Mode->GetFightWallSeconds()>.001||Mode->EncounterSeconds>0.f)
        {Finish(false,TEXT("Combat, resources, music or fight clock advanced during intro"));return;}
        if(IntroObservedShot!=Mode->ArenaIntroShot)
        {IntroObservedShot=Mode->ArenaIntroShot;Event(FString(TEXT("intro_"))+VeyrArenaTour::ShotName(IntroObservedShot));}
        if(IntroSkipAfter>0.f&&!bIntroSkipIssued&&Elapsed>=IntroSkipAfter)
        {bIntroSkipIssued=Mode->SkipArenaIntro();Event(TEXT("intro_skip_requested"),false);}
        return;
    }
    if(!bIntroObserved||!Mode->bArenaIntroCompleted)
    {Finish(false,TEXT("Production intro did not complete"));return;}
    if(IntroHandoffAt<0.f)
    {
        if(Mode->bArenaIntroSkipped!=bIntroSkipIssued||(!bIntroSkipIssued&&Mode->ArenaIntroShotsSeen!=VeyrArenaTour::ShotCount()))
        {Finish(false,TEXT("Intro shot coverage or skip result mismatch"));return;}
        APlayerController* PC=GetWorld()->GetFirstPlayerController();
        if(!PC||PC->GetViewTarget()!=Knight.Get()){Finish(false,TEXT("Intro did not return the view to the player"));return;}
        IntroHandoffAt=Elapsed;IntroHandoffOrigin=Knight->GetFootLocation();Event(TEXT("intro_handoff_complete"));
    }
    if(Mode->Audio->MusicStarts>1){Finish(false,TEXT("Soundtrack restarted during intro handoff"));return;}
    if(Elapsed-IntroHandoffAt>8.f){Finish(false,TEXT("Player movement/attack or soundtrack did not start after intro"));return;}
    const bool Moved=FVector::Dist2D(IntroHandoffOrigin,Knight->GetFootLocation())>=90.f;
    Knight->SetReplayInput(Moved?FVector::ZeroVector:FVector::ForwardVector,false,false,false,false,false,false);
    if(Moved&&!bIntroAttackIssued&&Knight->Action==EVeyrKnightAction::Ready&&Knight->GetPlanarSpeed()<10.f)
    {Knight->PressPrimaryAttack();Knight->ReleasePrimaryAttack();bIntroAttackIssued=true;Event(TEXT("intro_handoff_primary_requested"),false);}
    if(Moved&&bIntroAttackIssued&&Knight->LightAttacks>0&&Knight->HasEnteredEncounter()&&Mode->Audio->MusicStarts==1&&Mode->Audio->bOwnerScoreLoaded)
        Finish(true,TEXT("Production intro/skip isolated combat and music; player view,90cm ordinary movement,primary input and one soundtrack start verified"));
}
