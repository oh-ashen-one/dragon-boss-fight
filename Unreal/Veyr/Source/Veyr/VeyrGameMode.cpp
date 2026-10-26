#include "VeyrGameMode.h"
#include "VeyrArena.h"
#include "VeyrDragon.h"
#include "VeyrKnight.h"
#include "VeyrHUD.h"
#include "VeyrReplay.h"
#include "VeyrAudio.h"
#include "VeyrDragonEffects.h"
#include "VeyrIdentity.h"
#include "AudioMixerBlueprintLibrary.h"
#include "Misc/Paths.h"
#include "HAL/FileManager.h"
#include "Engine/World.h"
#include "Engine/Engine.h"
#include "GameFramework/PlayerController.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "Components/AudioComponent.h"
#include "Kismet/GameplayStatics.h"
#include "Misc/ConfigCacheIni.h"
#include "Misc/App.h"
#include "Misc/EngineVersion.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"

AVeyrGameMode::AVeyrGameMode()
{
    PrimaryActorTick.bCanEverTick=true;
    PrimaryActorTick.bTickEvenWhenPaused=true;
    bPauseable=true;
    DefaultPawnClass=AVeyrKnight::StaticClass();
    HUDClass=AVeyrHUD::StaticClass();
}
void AVeyrGameMode::StartPlay()
{
    Super::StartPlay();
    // Shipping ignores startup console execution; enforce the delivered frame cap directly.
    if(GEngine)GEngine->SetMaxFPS(60.f);
    // Optional test-only capture records this game's master submix, never
    // the microphone or system audio. Ordinary launches create no recordings.
    if(FParse::Value(FCommandLine::Get(),TEXT("VeyrAudioCapture="),MixCaptureDirectory))
    {
        if(FPaths::IsRelative(MixCaptureDirectory)||!IFileManager::Get().MakeDirectory(*MixCaptureDirectory,true))MixCaptureDirectory.Reset();
        FParse::Value(FCommandLine::Get(),TEXT("VeyrAudioCaptureSeconds="),MixCaptureDuration);
        MixCaptureDuration=FMath::Clamp(MixCaptureDuration,10.f,120.f);
        MixCaptureName=FString::Printf(TEXT("VeyrMix-%lld"),FDateTime::UtcNow().GetTicks());
    }
    if(GConfig)
    {
        GConfig->GetFloat(TEXT("Veyr.UserSettings"),TEXT("MasterVolume"),UserMasterVolume,GGameUserSettingsIni);
        GConfig->GetFloat(TEXT("Veyr.UserSettings"),TEXT("MusicVolume"),UserMusicVolume,GGameUserSettingsIni);
        GConfig->GetFloat(TEXT("Veyr.UserSettings"),TEXT("EffectsVolume"),UserEffectsVolume,GGameUserSettingsIni);
        GConfig->GetFloat(TEXT("Veyr.UserSettings"),TEXT("MouseSensitivity"),UserMouseSensitivity,GGameUserSettingsIni);
    }
    UserMasterVolume=FMath::Clamp(UserMasterVolume,0.f,1.f);
    UserMusicVolume=FMath::Clamp(UserMusicVolume,0.f,1.f);UserEffectsVolume=FMath::Clamp(UserEffectsVolume,0.f,1.f);
    UserMouseSensitivity=FMath::Clamp(UserMouseSensitivity,.25f,2.5f);
    FActorSpawnParameters Params;
    Params.SpawnCollisionHandlingOverride=ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
    Arena=GetWorld()->SpawnActor<AVeyrArena>(FVector::ZeroVector,FRotator::ZeroRotator,Params);
    Dragon=GetWorld()->SpawnActor<AVeyrDragon>(FVector(500,0,0),FRotator(0,180,0),Params);
    if(Arena&&Dragon)Arena->AddTickPrerequisiteActor(Dragon);
    DragonEffects=GetWorld()->SpawnActor<AVeyrDragonEffects>();
    if(DragonEffects)DragonEffects->Initialize(Dragon);
    UE_LOG(LogTemp,Display,TEXT("VEYR_UNREAL_ENCOUNTER_STARTED project=%s engine=%s"),FApp::GetProjectName(),*FEngineVersion::Current().ToString());
    UE_LOG(LogTemp,Display,TEXT("VEYR_SOURCE_ID %s"),VEYR_SOURCE_ID);
}
void AVeyrGameMode::Tick(float DeltaSeconds)
{
    Super::Tick(DeltaSeconds);
    if(MixCaptureStarted>0&&!bMixCaptureFinished&&FPlatformTime::Seconds()-MixCaptureStarted>=MixCaptureDuration)FinishMixCapture();
    // Only the optional bounded recording timer ticks while paused.
    if(UGameplayStatics::IsGamePaused(this))return;
    if(!Knight)
    {
        if(APlayerController* PC=GetWorld()->GetFirstPlayerController())Knight=Cast<AVeyrKnight>(PC->GetPawn());
    }
    if(Knight&&!bPawnPositioned)
    {
        Knight->SetActorLocationAndRotation(FVector(-1600,0,125),FRotator::ZeroRotator,false,nullptr,ETeleportType::TeleportPhysics);
        Knight->GetCharacterMovement()->StopMovementImmediately();
        Knight->Boss=Dragon;
        if(Dragon){Dragon->Target=Knight;Knight->AddTickPrerequisiteActor(Dragon);}
        Audio=GetWorld()->SpawnActor<AVeyrAudio>();
        if(Audio){Audio->MasterVolume=UserMasterVolume;Audio->MusicVolume=UserMusicVolume;Audio->EffectsVolume=UserEffectsVolume;Audio->Initialize(Knight,Dragon);}
        Knight->MouseSensitivity=UserMouseSensitivity;
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
        if(!MixCaptureDirectory.IsEmpty()&&MixCaptureStarted==0&&!bMixCaptureFinished)
        {
            UAudioMixerBlueprintLibrary::StartRecordingOutput(this,MixCaptureDuration+1.f);
            MixCaptureStarted=FPlatformTime::Seconds();
            UE_LOG(LogTemp,Display,TEXT("VEYR_AUDIO_CAPTURE_START wall=%.6f world=%.6f"),MixCaptureStarted,GetWorld()->GetTimeSeconds());
        }
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

bool AVeyrGameMode::SetPauseMenuOpen(bool bOpen)
{
    if(bPauseMenuOpen==bOpen)return true;
    if(!UGameplayStatics::SetGamePaused(this,bOpen))return false;
    bPauseMenuOpen=bOpen;
    UE_LOG(LogTemp,Display,TEXT("VEYR_WORLD_PAUSE open=%d worldTime=%.3f encounter=%.3f"),bOpen,GetWorld()->GetTimeSeconds(),EncounterSeconds);
    return true;
}
void AVeyrGameMode::SetMasterVolume(float Value)
{
    UserMasterVolume=FMath::Clamp(Value,0.f,1.f);
    if(Audio){Audio->MasterVolume=UserMasterVolume;Audio->RefreshMix();}SaveUserSettings();
}
void AVeyrGameMode::SetMusicVolume(float Value)
{
    UserMusicVolume=FMath::Clamp(Value,0.f,1.f);
    if(Audio){Audio->MusicVolume=UserMusicVolume;Audio->RefreshMix();}SaveUserSettings();
}
void AVeyrGameMode::SetEffectsVolume(float Value)
{
    UserEffectsVolume=FMath::Clamp(Value,0.f,1.f);
    if(Audio){Audio->EffectsVolume=UserEffectsVolume;Audio->RefreshMix();}SaveUserSettings();
}
void AVeyrGameMode::SetMouseSensitivity(float Value)
{
    UserMouseSensitivity=FMath::Clamp(Value,.25f,2.5f);
    if(Knight)Knight->MouseSensitivity=UserMouseSensitivity;
    SaveUserSettings();
}
void AVeyrGameMode::SaveUserSettings()
{
    if(!GConfig)return;
    GConfig->SetFloat(TEXT("Veyr.UserSettings"),TEXT("MasterVolume"),UserMasterVolume,GGameUserSettingsIni);
    GConfig->SetFloat(TEXT("Veyr.UserSettings"),TEXT("MusicVolume"),UserMusicVolume,GGameUserSettingsIni);
    GConfig->SetFloat(TEXT("Veyr.UserSettings"),TEXT("EffectsVolume"),UserEffectsVolume,GGameUserSettingsIni);
    GConfig->SetFloat(TEXT("Veyr.UserSettings"),TEXT("MouseSensitivity"),UserMouseSensitivity,GGameUserSettingsIni);
    GConfig->Flush(false,GGameUserSettingsIni);
}

void AVeyrGameMode::FinishMixCapture()
{
    if(MixCaptureStarted<=0||bMixCaptureFinished)return;
    bMixCaptureFinished=true;
    UAudioMixerBlueprintLibrary::StopRecordingOutput(this,EAudioRecordingExportType::WavFile,MixCaptureName,MixCaptureDirectory);
    UE_LOG(LogTemp,Display,TEXT("VEYR_AUDIO_CAPTURE_STOP wall=%.6f name=%s"),FPlatformTime::Seconds(),*MixCaptureName);
}
void AVeyrGameMode::EndPlay(const EEndPlayReason::Type Reason)
{
    FinishMixCapture();Super::EndPlay(Reason);
}
