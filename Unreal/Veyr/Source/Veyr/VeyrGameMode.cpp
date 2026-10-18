#include "VeyrGameMode.h"
#include "VeyrArena.h"
#include "VeyrDragon.h"
#include "VeyrKnight.h"
#include "VeyrHUD.h"
#include "VeyrReplay.h"
#include "VeyrAudio.h"
#include "VeyrDragonEffects.h"
#include "VeyrIdentity.h"
#include "Engine/World.h"
#include "GameFramework/PlayerController.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "Misc/App.h"
#include "Misc/EngineVersion.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"

AVeyrGameMode::AVeyrGameMode()
{
    PrimaryActorTick.bCanEverTick=true;
    DefaultPawnClass=AVeyrKnight::StaticClass();
    HUDClass=AVeyrHUD::StaticClass();
}
void AVeyrGameMode::StartPlay()
{
    Super::StartPlay();
    FActorSpawnParameters Params;
    Params.SpawnCollisionHandlingOverride=ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
    Arena=GetWorld()->SpawnActor<AVeyrArena>(FVector::ZeroVector,FRotator::ZeroRotator,Params);
    Dragon=GetWorld()->SpawnActor<AVeyrDragon>(FVector(500,0,0),FRotator(0,180,0),Params);
    DragonEffects=GetWorld()->SpawnActor<AVeyrDragonEffects>();
    if(DragonEffects)DragonEffects->Initialize(Dragon);
    UE_LOG(LogTemp,Display,TEXT("VEYR_UNREAL_ENCOUNTER_STARTED project=%s engine=%s"),FApp::GetProjectName(),*FEngineVersion::Current().ToString());
    UE_LOG(LogTemp,Display,TEXT("VEYR_SOURCE_ID %s"),VEYR_SOURCE_ID);
}
void AVeyrGameMode::Tick(float DeltaSeconds)
{
    Super::Tick(DeltaSeconds);
    if(!Knight)
    {
        if(APlayerController* PC=GetWorld()->GetFirstPlayerController())Knight=Cast<AVeyrKnight>(PC->GetPawn());
    }
    if(Knight&&!bPawnPositioned)
    {
        Knight->SetActorLocationAndRotation(FVector(-1600,0,125),FRotator::ZeroRotator,false,nullptr,ETeleportType::TeleportPhysics);
        Knight->GetCharacterMovement()->StopMovementImmediately();
        Knight->Boss=Dragon;
        if(Dragon)Dragon->Target=Knight;
        Audio=GetWorld()->SpawnActor<AVeyrAudio>();
        if(Audio)Audio->Initialize(Knight,Dragon);
        bPawnPositioned=true;
        FString ReplayMode,EvidenceDirectory;
        if(FParse::Value(FCommandLine::Get(),TEXT("VeyrReplay="),ReplayMode))
        {
            FParse::Value(FCommandLine::Get(),TEXT("VeyrEvidence="),EvidenceDirectory);
            StartNativeValidation(ReplayMode,EvidenceDirectory);
        }
        else if(AVeyrReplay::GetPendingRestartRequest(ReplayMode,EvidenceDirectory))
        {
            StartNativeValidation(ReplayMode,EvidenceDirectory);
        }
    }
    if(Knight&&Dragon&&Knight->HasEnteredEncounter())
    {
        EncounterSeconds+=DeltaSeconds;
        if(Dragon->IsDead()&&VictorySeconds<0)
        {
            VictorySeconds=EncounterSeconds;
            UE_LOG(LogTemp,Display,TEXT("VEYR_UNREAL_VICTORY seconds=%.3f"),VictorySeconds);
        }
    }
}

bool AVeyrGameMode::StartNativeValidation(const FString& Mode,const FString& EvidenceDirectory)
{
    // One scenario per fresh world. Never replace an active replay or its evidence.
    if(Replay||!bPawnPositioned||!IsValid(Knight)||!IsValid(Dragon))return false;
    FString PendingMode,PendingDirectory;
    const bool bOwnRestart=AVeyrReplay::GetPendingRestartRequest(PendingMode,PendingDirectory)&&
        PendingMode.Equals(Mode,ESearchCase::IgnoreCase)&&PendingDirectory==EvidenceDirectory;
    const bool bFresh=!Knight->HasEnteredEncounter()&&Knight->Action==EVeyrKnightAction::Ready&&
        FMath::IsNearlyEqual(Knight->Health,100.f)&&FMath::IsNearlyEqual(Knight->Stamina,100.f)&&Knight->HealingCharges==4&&
        Knight->LightAttacks==0&&Knight->HeavyAttacks==0&&Knight->Rolls==0&&Knight->HitsTaken==0&&
        Knight->SuccessfulJumps==0&&Knight->SuccessfulHeals==0&&FMath::IsNearlyEqual(Dragon->Health,Dragon->MaxHealth)&&
        Dragon->GetCollapseCount()==0&&Dragon->GetSwordContactCount()==0;
    if(!bOwnRestart&&!bFresh)
    {
        UE_LOG(LogTemp,Warning,TEXT("VEYR_REPLAY_REJECTED start requires a fresh untouched world"));
        return false;
    }
    Replay=GetWorld()->SpawnActor<AVeyrReplay>();
    if(!Replay)return false;
    if(Replay->Initialize(Mode,EvidenceDirectory))return true;
    Replay->Destroy();Replay=nullptr;
    return false;
}
