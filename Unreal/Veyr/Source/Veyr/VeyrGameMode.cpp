#include "VeyrGameMode.h"
#include "VeyrArena.h"
#include "VeyrDragon.h"
#include "VeyrKnight.h"
#include "VeyrHUD.h"
#include "Engine/World.h"
#include "GameFramework/PlayerController.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "Misc/App.h"
#include "Misc/EngineVersion.h"

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
    UE_LOG(LogTemp,Display,TEXT("VEYR_UNREAL_ENCOUNTER_STARTED project=%s engine=%s"),FApp::GetProjectName(),*FEngineVersion::Current().ToString());
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
        bPawnPositioned=true;
    }
    if(Knight&&Dragon)
    {
        EncounterSeconds+=DeltaSeconds;
        if(Dragon->IsDead()&&VictorySeconds<0)
        {
            VictorySeconds=EncounterSeconds;
            UE_LOG(LogTemp,Display,TEXT("VEYR_UNREAL_VICTORY seconds=%.3f"),VictorySeconds);
        }
    }
}
