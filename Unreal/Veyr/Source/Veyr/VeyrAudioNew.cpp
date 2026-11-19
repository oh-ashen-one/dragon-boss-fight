// Quality goal B1-B3 (2026-11-18): recorded set with variants, dragon footfalls / body falls from ground contacts,
// dragon breathing and growls between attacks, per-clip timed dragon sounds (Data/dragon/sounds.json), knight steps
// from foot contacts, layered armour hits, mixing budget. The previous behaviour lives in VeyrAudio.cpp and is
// restored whole by -VeyrLegacyAudio (this file is then never reached).
#include "VeyrAudio.h"
#include "VeyrKnight.h"
#include "VeyrDragon.h"
#include "VeyrMoveData.h"
#include "VeyrSkeletalPresentation.h"
#include "VeyrVisualDefinition.h"
#include "Components/AudioComponent.h"
#include "Sound/SoundWaveProcedural.h"
#include "Engine/World.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Misc/CommandLine.h"
#include "HAL/FileManager.h"
#include "HAL/PlatformTime.h"
#include "Dom/JsonObject.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonReader.h"
#include "Algo/Sort.h"
#include <cmath>

namespace
{
#include "VeyrAudioDefaultSounds.inl"
    constexpr double AudioEps=1e-4;
}

float AVeyrAudio::TargetLevelDb(ECue Cue)
{
    // Gated RMS (dBFS) a cue should have at Volume 1.0. Where the old game had a level, this keeps its balance
    // (receipt docs/audio-20261118/recorded-set.json "oldGameLevelRmsDb"); the others are set for weight.
    switch(Cue)
    {
        case ECue::Swing:return -11.f;         case ECue::HeavySwing:return -10.5f;
        case ECue::Contact:return -20.f;       case ECue::Guard:return -20.f;
        case ECue::ArmorHit:return -15.f;      case ECue::Impact:return -15.f;
        case ECue::DragonStep:return -13.f;    case ECue::DragonSwing:return -12.f;
        case ECue::Bite:return -16.f;          case ECue::Breath:return -17.f;
        case ECue::Fire:return -17.f;          case ECue::Wing:return -14.5f;
        case ECue::Roll:return -20.f;          case ECue::Footstep:return -13.f;
        case ECue::Blink:return -18.f;         case ECue::Break:return -20.f;
        case ECue::Debris:return -17.f;        case ECue::Exposed:return -15.f;
        case ECue::Death:return -15.f;         case ECue::Heal:return -19.f;
        case ECue::Victory:return -17.f;       case ECue::DragonBreathIn:return -15.f;
        case ECue::DragonBreathOut:return -15.f; case ECue::DragonGrowlLow:return -17.f;
        case ECue::DragonSnort:return -19.f;
        default:return 0.f; // 0 = leave at the file's own level (the three roar files and the pain cue)
    }
}

bool AVeyrAudio::IsVocal(ECue Cue)
{
    // No random pitch: voices, breaths and the melodic stings keep their character.
    switch(Cue)
    {
        case ECue::Roar:case ECue::DragonGrowl:case ECue::DragonPain:case ECue::PlayerPain:
        case ECue::DragonGrowlLow:case ECue::DragonSnort:case ECue::DragonBreathIn:case ECue::DragonBreathOut:
        case ECue::Breath:case ECue::Fire:case ECue::Death:case ECue::Heal:case ECue::Victory:
            return true;
        default:return false;
    }
}

static bool BytesToSamples(const TArray<uint8>& Bytes,TArray<int16>& Out)
{
    if(Bytes.Num()<=2||Bytes.Num()%2!=0)return false;
    Out.SetNumUninitialized(Bytes.Num()/2);
    FMemory::Memcpy(Out.GetData(),Bytes.GetData(),Bytes.Num());
    return true;
}

void AVeyrAudio::SetBankFromSingle(ECue Cue,const TArray<uint8>& Bytes,bool bNormalize)
{
    TArray<int16> S;
    if(!BytesToSamples(Bytes,S))return;
    FCueBank& B=Banks[static_cast<int32>(Cue)];
    B.Variants.Reset();B.Gains.Reset();
    B.Variants.Add(MoveTemp(S));B.Gains.Add(1.f);
    (void)bNormalize;
}

void AVeyrAudio::LoadCueSources()
{
    // Per-cue choice of recorded files (<Cue>_<n>.pcm), generated ones (<Cue>_g<n>.pcm) or both. Compiled default: mixed for
    // every cue. Data/dragon/audio_sources.json overrides it when the folder is found (dev runs; packaged builds have no Data/).
    DefaultSource=ESourceMode::Mixed;CueSource.Reset();SourcesDiagnostic=TEXT("compiled default: mixed");
    const FString File=FPaths::Combine(FBossMoveData::ResolveDirectory(),TEXT("audio_sources.json"));
    FString Text;TSharedPtr<FJsonObject> Root;
    if(!FPaths::FileExists(File)||!FFileHelper::LoadFileToString(Text,*File))return;
    if(!FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text),Root)||!Root.IsValid())
    {SourcesDiagnostic=TEXT("audio_sources.json does not parse; compiled default: mixed");return;}
    auto Parse=[](const FString& V,ESourceMode& Out)
    {
        if(V.Equals(TEXT("recorded"),ESearchCase::IgnoreCase))Out=ESourceMode::Recorded;
        else if(V.Equals(TEXT("generated"),ESearchCase::IgnoreCase))Out=ESourceMode::Generated;
        else if(V.Equals(TEXT("mixed"),ESearchCase::IgnoreCase))Out=ESourceMode::Mixed;
        else return false;
        return true;
    };
    FString Def;
    if(Root->TryGetStringField(TEXT("default"),Def))Parse(Def,DefaultSource);
    const TSharedPtr<FJsonObject>* Cues=nullptr;
    int32 N=0;
    if(Root->TryGetObjectField(TEXT("cues"),Cues)&&Cues&&Cues->IsValid())
        for(const auto& E:(*Cues)->Values)
        {
            FString V;ESourceMode M;
            if(E.Value.IsValid()&&E.Value->TryGetString(V)&&Parse(V,M)){CueSource.Add(FName(*FString(*E.Key)),M);++N;}
        }
    SourcesDiagnostic=FString::Printf(TEXT("%s: default %d, %d cue overrides"),*File,int32(DefaultSource),N);
}

void AVeyrAudio::LoadBank(ECue Cue,const FString& Dir)
{
    const int32 Index=static_cast<int32>(Cue);
    FCueBank& B=Banks[Index];
    B.Variants.Reset();B.Gains.Reset();B.Last=-1;
    TArray<FString> Files;
    IFileManager::Get().FindFiles(Files,*(Dir/(FString(CueName(Index))+TEXT("_*.pcm"))),true,false);
    // Name after the underscore: "<n>" = recorded, "g<n>" = generated supplement.
    auto Number=[](const FString& F,bool& bGenerated)->int32
    {
        int32 U=INDEX_NONE;F.FindLastChar('_',U);
        FString Tail=U==INDEX_NONE?FString():F.Mid(U+1);Tail.RemoveFromEnd(TEXT(".pcm"));
        bGenerated=Tail.StartsWith(TEXT("g"));
        if(bGenerated)Tail.RightChopInline(1);
        return FCString::Atoi(*Tail);
    };
    TArray<FString> Recorded,Generated;
    for(const FString& F:Files){bool bG=false;Number(F,bG);(bG?Generated:Recorded).Add(F);}
    auto ByNumber=[&Number](const FString& A,const FString& B2){bool g=false;return Number(A,g)<Number(B2,g);};
    Algo::Sort(Recorded,ByNumber);Algo::Sort(Generated,ByNumber);
    const ESourceMode* Override=CueSource.Find(FName(CueName(Index)));
    ESourceMode Mode=Override?*Override:DefaultSource;
    if(Mode==ESourceMode::Recorded&&Recorded.IsEmpty()&&!Generated.IsEmpty()){UE_LOG(LogTemp,Warning,TEXT("VEYR_AUDIO_SOURCE %s: recorded-only but none recorded; using generated"),CueName(Index));Mode=ESourceMode::Mixed;}
    if(Mode==ESourceMode::Generated&&Generated.IsEmpty()&&!Recorded.IsEmpty()){UE_LOG(LogTemp,Warning,TEXT("VEYR_AUDIO_SOURCE %s: generated-only but none generated; using recorded"),CueName(Index));Mode=ESourceMode::Mixed;}
    TArray<FString> Use;
    if(Mode!=ESourceMode::Generated)Use.Append(Recorded);
    if(Mode!=ESourceMode::Recorded)Use.Append(Generated);
    const float TargetDb=TargetLevelDb(Cue);
    for(const FString& File:Use)
    {
        if(B.Variants.Num()>=MaxVariants)break;
        TArray<uint8> Bytes;TArray<int16> S;
        if(!FFileHelper::LoadFileToArray(Bytes,*(Dir/File))||!BytesToSamples(Bytes,S))continue;
        double Sum=0;int64 N=0;float Peak=1e-4f;
        for(int16 V:S)
        {
            const float X=std::abs(float(V))/32768.f;
            Peak=FMath::Max(Peak,X);
            if(X>.01f){Sum+=double(X)*X;++N;}
        }
        const double Rms=N>0?std::sqrt(Sum/double(N)):1e-4;
        const float MeasuredDb=float(20.0*std::log10(FMath::Max(Rms,1e-5)));
        float Gain=TargetDb<0.f?FMath::Pow(10.f,(TargetDb-MeasuredDb)/20.f):1.f;
        Gain=FMath::Clamp(Gain,.4f,2.6f);
        Gain=FMath::Min(Gain,1.6f/Peak); // peak x gain x the .65 voice level stays under full scale
        B.Variants.Add(MoveTemp(S));B.Gains.Add(Gain);
    }
}

void AVeyrAudio::LoadNewSet()
{
    // Music and cathedral ambience are untouched: the same files, the same owner score, the same levels.
    for(int32 I=0;I<2;++I)
        FFileHelper::LoadFileToArray(BedPCM[I],*(FPaths::ProjectContentDir()/TEXT("Audio/Overhaul")/(I==0?TEXT("Music.pcm"):TEXT("Ambience.pcm"))));
    // -VeyrLegacyAudio keeps its pre-goal meaning: older music and vocals (no owner score, no pain cue, no dragon library).
    const bool bOlderVocals=FParse::Param(FCommandLine::Get(),TEXT("VeyrLegacyAudio"));
    if(!bOlderVocals)
    {
        TArray<uint8> Score;
        if(FFileHelper::LoadFileToArray(Score,*(FPaths::ProjectContentDir()/TEXT("Audio/OwnerScore20261102/Music.pcm")))&&Score.Num()>4&&Score.Num()%4==0)
        {BedPCM[0]=MoveTemp(Score);BedSampleRates[0]=48000;BedChannels[0]=2;bOwnerScoreLoaded=true;}
    }
    LoadCueSources();
    {
        TArray<FString> G;IFileManager::Get().FindFiles(G,*(FPaths::ProjectContentDir()/TEXT("Audio/Recorded20261118/*_g*.pcm")),true,false);
        GeneratedFiles=G.Num();
        if(G.IsEmpty())UE_LOG(LogTemp,Warning,TEXT("VEYR_AUDIO_GENERATED_MISSING no <Cue>_g<n>.pcm supplement in Audio/Recorded20261118 (git-ignored; restore per docs/audio-20261118/README.md); playing the recorded takes only"));
    }
    const FString Dir=FPaths::ProjectContentDir()/TEXT("Audio/Recorded20261118");
    int32 Loaded=0;TArray<FString> Missing;
    for(int32 I=0;I<CueCount;++I)
    {
        const ECue Cue=static_cast<ECue>(I);
        if(Cue==ECue::Roar||Cue==ECue::DragonGrowl||Cue==ECue::DragonPain||Cue==ECue::PlayerPain)continue; // fixed files below
        LoadBank(Cue,Dir);
        if(Banks[I].Variants.IsEmpty())Missing.Add(CueName(I));else Loaded+=Banks[I].Variants.Num();
    }
    // The three dragon roar files and the single human pain cue stay exactly as they are.
    if(bOlderVocals)
    {
        // The pre-goal vocals: whatever Audio/Overhaul holds for these four (no tone is generated when a file is absent).
        TArray<uint8> Bytes;
        for(ECue Cue:{ECue::Roar,ECue::DragonGrowl,ECue::DragonPain,ECue::PlayerPain})
            if(FFileHelper::LoadFileToArray(Bytes,*(FPaths::ProjectContentDir()/TEXT("Audio/Overhaul")/(FString(CueName(static_cast<int32>(Cue)))+TEXT(".pcm")))))
            {SetBankFromSingle(Cue,Bytes,false);if(!Banks[static_cast<int32>(Cue)].Variants.IsEmpty())++Loaded;}
        bDragonLibraryLoaded=false;
    }
    else
    {
        TArray<uint8> Bytes;
        if(FFileHelper::LoadFileToArray(Bytes,*(FPaths::ProjectContentDir()/TEXT("Audio/Fish20261102/PlayerPain.pcm"))))
        {SetBankFromSingle(ECue::PlayerPain,Bytes,false);if(!Banks[static_cast<int32>(ECue::PlayerPain)].Variants.IsEmpty())++Loaded;}
        int32 Creature=0;
        for(ECue Cue:{ECue::Roar,ECue::DragonGrowl,ECue::DragonPain})
            if(FFileHelper::LoadFileToArray(Bytes,*(FPaths::ProjectContentDir()/TEXT("Audio/DragonLibrary20261103")/(FString(CueName(static_cast<int32>(Cue)))+TEXT(".pcm")))))
            {SetBankFromSingle(Cue,Bytes,false);if(!Banks[static_cast<int32>(Cue)].Variants.IsEmpty()){++Loaded;++Creature;}}
        bDragonLibraryLoaded=Creature==3;
    }
    RecordedCuesLoaded=Loaded;bMusicLoaded=!BedPCM[0].IsEmpty();bAmbienceLoaded=!BedPCM[1].IsEmpty();
    for(const FString& M:Missing)UE_LOG(LogTemp,Warning,TEXT("VEYR_AUDIO_CUE_MISSING %s has no recorded file in Recorded20261118: it stays silent (no code-generated tone)"),*M);
    LoadTimedSounds(true);
    UE_LOG(LogTemp,Display,TEXT("VEYR_RECORDED_AUDIO newSet=1 samples=%d missingCues=%d musicBytes=%d ambienceBytes=%d timedClips=%d (%s)"),
        Loaded,Missing.Num(),BedPCM[0].Num(),BedPCM[1].Num(),TimedClips.Num(),*SoundsDiagnostic);
}

// ---------------------------------------------------------------- timed sounds file

void AVeyrAudio::ParseTimedSounds(const FString& Text,const TCHAR* Origin)
{
    TSharedPtr<FJsonObject> Root;
    if(!FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text),Root)||!Root.IsValid())
    {SoundsDiagnostic=FString::Printf(TEXT("%s does not parse; keeping the previous table (%d clips)"),Origin,TimedClips.Num());return;}
    const TSharedPtr<FJsonObject>* Clips=nullptr;
    if(!Root->TryGetObjectField(TEXT("clips"),Clips)||!Clips||!Clips->IsValid())
    {SoundsDiagnostic=FString::Printf(TEXT("%s has no \"clips\" object; keeping the previous table"),Origin);return;}
    TMap<FName,TArray<FTimedEvent>> Table;
    int32 Events=0,Bad=0;
    for(const auto& Entry:(*Clips)->Values)
    {
        const TArray<TSharedPtr<FJsonValue>>* List=nullptr;
        const FString KeyText(*Entry.Key);
        if(KeyText.StartsWith(TEXT("_"))||!Entry.Value.IsValid()||!Entry.Value->TryGetArray(List)||!List)continue;
        TArray<FTimedEvent>& Out=Table.FindOrAdd(FName(*KeyText));
        for(const TSharedPtr<FJsonValue>& V:*List)
        {
            const TSharedPtr<FJsonObject>* E=nullptr;
            if(!V.IsValid()||!V->TryGetObject(E)||!E||!E->IsValid()){++Bad;continue;}
            FString CueText,WhereText;double Phase=0,Time=0,Level=1;
            (*E)->TryGetStringField(TEXT("cue"),CueText);(*E)->TryGetStringField(TEXT("where"),WhereText);
            (*E)->TryGetNumberField(TEXT("level"),Level);
            FTimedEvent Ev;Ev.Level=float(Level);Ev.Where=WhereText.IsEmpty()?FName(TEXT("head")):FName(*WhereText);
            if((*E)->TryGetNumberField(TEXT("phase"),Phase)){Ev.bPhase=true;Ev.Pos=float(Phase);}
            else if((*E)->TryGetNumberField(TEXT("time"),Time)){Ev.bPhase=false;Ev.Pos=float(Time);}
            else {++Bad;continue;}
            Ev.Cue=ECue::Count;
            for(int32 I=0;I<CueCount;++I)if(CueText.Equals(CueName(I),ESearchCase::IgnoreCase)){Ev.Cue=static_cast<ECue>(I);break;}
            if(Ev.Cue==ECue::Count){++Bad;continue;}
            Out.Add(Ev);++Events;
        }
        Out.Sort([](const FTimedEvent& A,const FTimedEvent& B){return A.Pos<B.Pos;});
    }
    TimedClips=MoveTemp(Table);
    SoundsDiagnostic=FString::Printf(TEXT("%s: %d clips, %d events, %d bad"),Origin,TimedClips.Num(),Events,Bad);
}

void AVeyrAudio::LoadTimedSounds(bool bForce)
{
    const double Wall=FPlatformTime::Seconds();
    if(!bForce&&Wall<SoundsCheckWall+1.0)return;
    SoundsCheckWall=Wall;
    if(SoundsFile.IsEmpty())SoundsFile=FPaths::Combine(FBossMoveData::ResolveDirectory(),TEXT("sounds.json"));
    const bool bFile=FPaths::FileExists(SoundsFile);
    const FDateTime Stamp=bFile?IFileManager::Get().GetTimeStamp(*SoundsFile):FDateTime::MinValue();
    if(!bForce&&Stamp==SoundsStamp)return;
    FString Text;
    if(bFile&&FFileHelper::LoadFileToString(Text,*SoundsFile))
    {
        SoundsStamp=Stamp;ParseTimedSounds(Text,*SoundsFile);
        if(!bForce){++SoundsReloads;UE_LOG(LogTemp,Display,TEXT("VEYR_SOUNDS_RELOAD %s"),*SoundsDiagnostic);}
    }
    else if(bForce)
    {
        SoundsStamp=Stamp;
        ParseTimedSounds(FString(UTF8_TO_TCHAR(GVeyrDefaultSoundsJson)),TEXT("compiled default table"));
    }
}

// ---------------------------------------------------------------- playing

bool AVeyrAudio::ResolvePart(FName Where,FVector& Out) const
{
    const AVeyrDragon* D=Dragon.Get();
    if(!D)return false;
    if(Where.IsNone()||Where==FName(TEXT("head"))||Where==FName(TEXT("mouth"))){Out=D->GetMouthLocation();return true;}
    if(Where==FName(TEXT("body"))){Out=D->GetActorLocation();return true;}
    FVector A,B;float R=0.f;
    if(D->GetHurtPartWorld(Where,A,B,R)){Out=(A+B)*.5f;return true;}
    Out=D->GetMouthLocation();
    return false;
}

void AVeyrAudio::UpdateVoiceFollow()
{
    const AVeyrDragon* D=Dragon.Get();
    if(!D)return;
    for(int32 I=0;I<TotalVoices;++I)
    {
        if(VoiceEndTimes[I]<=0||!IsValid(Voices[I])||VoiceFollowMode[I]==0)continue;
        FVector P;
        switch(VoiceFollowMode[I])
        {
            case 1:P=D->GetMouthLocation();break;
            case 2:P=D->GetActorLocation();break;
            default:if(!ResolvePart(VoicePart[I],P))P=D->GetMouthLocation();break;
        }
        Voices[I]->SetWorldLocation(P);
    }
}

void AVeyrAudio::DefaultRadius(ECue Cue,float& Inner,float& Falloff)
{
    switch(Cue)
    {
        case ECue::DragonStep:case ECue::Exposed:case ECue::Impact:case ECue::Debris:Inner=1500.f;Falloff=13000.f;break;
        case ECue::DragonSwing:case ECue::Bite:Inner=1100.f;Falloff=10000.f;break;
        case ECue::DragonBreathIn:case ECue::DragonBreathOut:case ECue::DragonSnort:Inner=800.f;Falloff=7000.f;break;
        case ECue::DragonGrowlLow:Inner=1000.f;Falloff=10000.f;break;
        case ECue::Footstep:case ECue::Roll:Inner=600.f;Falloff=5000.f;break;
        default:Inner=900.f;Falloff=9000.f;break;
    }
}

bool AVeyrAudio::PickVariant(ECue Cue,float Volume,FChosen& C,int32 Force)
{
    const int32 Index=static_cast<int32>(Cue);
    FCueBank& Bank=Banks[Index];
    if(Bank.Variants.IsEmpty())return false;
    int32 V=0;
    if(Force>=0)V=FMath::Min(Force,Bank.Variants.Num()-1);
    else if(!bNoVariants&&Bank.Variants.Num()>1){do{V=Rand.RandRange(0,Bank.Variants.Num()-1);}while(V==Bank.Last);}
    Bank.Last=V;
    C.V=V;
    C.Seconds0=float(Bank.Variants[V].Num())/SampleRate;
    const bool bVocal=IsVocal(Cue);
    float Pitch=1.f,LevelJitter=1.f;
    if(!bVocal&&!bNoVariants&&Force<0)
    {
        Pitch=1.f+Rand.FRandRange(-.05f,.05f);
        LevelJitter=FMath::Pow(10.f,Rand.FRandRange(-1.5f,1.5f)/20.f);
    }
    if(Cue==ECue::DragonStep||Cue==ECue::Exposed)Pitch*=FMath::Lerp(1.07f,.9f,FMath::Clamp(Volume,0.f,1.f)); // heavier = lower
    C.Pitch=Pitch;
    C.Seconds=C.Seconds0/FMath::Max(.5f,Pitch);
    C.Level=.65f*Headroom*FMath::Clamp(Volume,0.f,1.5f)*Bank.Gains[V]*LevelJitter;
    return true;
}

bool AVeyrAudio::PlayCueEx(ECue Cue,float Volume,EPlace Place,const FVector& World,FName Part,float Inner,float Falloff)
{
    if(!GetWorld()||MasterVolume<=0.f||!FMath::IsFinite(MasterVolume))return false;
    const int32 Index=static_cast<int32>(Cue);
    FCueBank& Bank=Banks[Index];
    if(Bank.Variants.IsEmpty())
    {
        if(!Bank.bMissingLogged){Bank.bMissingLogged=true;UE_LOG(LogTemp,Warning,TEXT("VEYR_AUDIO_CUE_SILENT %s has no recorded file; no tone is generated"),CueName(Index));}
        ++CueSilent[Index];
        return false;
    }
    const double Now=AudioNow(); // real time: hit-stop and slow tails do not stretch cue gaps or voice lifetimes
    const bool bStep=Cue==ECue::Footstep||Cue==ECue::DragonStep;
    if(Cue==ECue::PlayerPain&&Now-LastCueTimes[Index]<.8)return false;
    if((Cue==ECue::DragonGrowl||Cue==ECue::DragonPain)&&Now-LastCueTimes[Index]<2.0)return false;
    if((Cue==ECue::DragonGrowlLow||Cue==ECue::DragonSnort)&&Now-LastCueTimes[Index]<1.5)return false;
    if(Now-LastCueTimes[Index]<(bStep?.025:.06))return false;
    if(bAudioPolish&&(Cue==ECue::Contact||Cue==ECue::Impact||Cue==ECue::Roar||Cue==ECue::Guard||Cue==ECue::ArmorHit||Cue==ECue::Exposed))MusicDuckUntil=GetWorld()->GetTimeSeconds()+.35; // the duck is read against game time in RefreshMix
    const int32 Lo=bStep?VoiceCount:0,Hi=bStep?TotalVoices:VoiceCount;
    int32 Slot=INDEX_NONE;
    for(int32 I=Lo;I<Hi;++I)if(VoiceEndTimes[I]<=0){Slot=I;break;}
    if(Slot==INDEX_NONE)
    {
        const bool bLow=Cue==ECue::DragonBreathIn||Cue==ECue::DragonBreathOut||Cue==ECue::Debris||Cue==ECue::DragonSnort||Cue==ECue::Wing||Cue==ECue::Footstep;
        if(bLow){++CuesDropped;return false;}
        Slot=Lo;for(int32 I=Lo+1;I<Hi;++I)if(VoiceEndTimes[I]<VoiceEndTimes[Slot])Slot=I;
        Voices[Slot]->Stop();VoiceWaves[Slot]=nullptr;VoiceEndTimes[Slot]=0;ActiveVoices=FMath::Max(0,ActiveVoices-1);
    }
    UAudioComponent* Voice=Voices[Slot];
    if(!IsValid(Voice))return false;

    FChosen C;
    if(!PickVariant(Cue,Volume,C))return false; // never the variant played last; random pitch and level off vocal cues
    const int32 V=C.V;const float Pitch=C.Pitch,Seconds=C.Seconds,Seconds0=C.Seconds0;
    const TArray<int16>& PCM=Bank.Variants[V];
    float Level=C.Level;
    float Load=0.f;
    for(int32 I=0;I<TotalVoices;++I)if(VoiceEndTimes[I]>0)Load+=VoiceLevels[I];
    if(Load+Level>MaxLoad)Level=FMath::Max(Level*.4f,MaxLoad-Load); // limiter-safe headroom: the sum of voices stays bounded

    USoundWaveProcedural* Wave=NewObject<USoundWaveProcedural>(this);
    Wave->SetSampleRate(SampleRate);Wave->NumChannels=1;Wave->Duration=Seconds0;Wave->bLooping=false;Wave->SoundGroup=SOUNDGROUP_Effects;
    Wave->QueueAudio(reinterpret_cast<const uint8*>(PCM.GetData()),PCM.Num()*sizeof(int16));
    VoiceWaves[Slot]=Wave;Voice->SetSound(Wave);
    VoiceLevels[Slot]=Level;
    Voice->SetVolumeMultiplier(Level*MasterVolume*EffectsVolume);
    Voice->SetPitchMultiplier(Pitch);

    // Placement. Knight cues without a world position stay flat (as before).
    VoiceFollowsDragon[Slot]=false;VoiceFollowMode[Slot]=0;VoicePart[Slot]=NAME_None;
    if(Place==EPlace::Flat||!Dragon.IsValid())
    {
        Voice->bAllowSpatialization=false;Voice->bOverrideAttenuation=false;
    }
    else
    {
        FVector P=World;
        switch(Place)
        {
            case EPlace::Head:P=Dragon->GetMouthLocation();VoiceFollowMode[Slot]=1;break;
            case EPlace::Body:P=Dragon->GetActorLocation();VoiceFollowMode[Slot]=2;break;
            case EPlace::Part:if(!ResolvePart(Part,P))P=Dragon->GetMouthLocation();VoiceFollowMode[Slot]=3;VoicePart[Slot]=Part;break;
            default:break;
        }
        if(Inner<=0.f||Falloff<=0.f)DefaultRadius(Cue,Inner,Falloff);
        Voice->bAllowSpatialization=true;Voice->bOverrideAttenuation=true;
        Voice->SetWorldLocation(P);
        Voice->AttenuationOverrides.bAttenuate=true;Voice->AttenuationOverrides.bSpatialize=true;
        Voice->AttenuationOverrides.AttenuationShapeExtents=FVector(Inner,0,0);Voice->AttenuationOverrides.FalloffDistance=Falloff;
    }
    Voice->Play();
    if(bTap&&!bAudition)
    {
        FVector TapPos=World;
        if(Place!=EPlace::Flat&&Dragon.IsValid())TapPos=Voice->GetComponentLocation();
        float In=Inner,Fo=Falloff;if(In<=0.f||Fo<=0.f)DefaultRadius(Cue,In,Fo);
        TapAdd(Cue,PCM,V,Volume,Level,Pitch,Place,TapPos,In,Fo,Now-TapT0);
    }
    VoiceEndTimes[Slot]=Now+Seconds+.15;
    VoiceCue[Slot]=Index;
    LastCueTimes[Index]=Now;
    DurationLastPlayed=Seconds;
    ++CuesStarted;++ActiveVoices;++CueCounts[Index];++VariantPlays[Index][FMath::Min(V,MaxVariants-1)];
    if(Cue==ECue::PlayerPain)++PlayerPainCues;
    if(Cue==ECue::Roar||Cue==ECue::DragonGrowl||Cue==ECue::DragonPain)++DragonVocalCues;
    if(bLogCues)UE_LOG(LogTemp,Display,TEXT("VEYR_CUE t=%.2f %s v=%d vol=%.2f lvl=%.2f pitch=%.3f place=%d part=%s"),Now,CueName(Index),V,Volume,Level,Pitch,int32(Place),*Part.ToString());
    return true;
}

void AVeyrAudio::QueueCue(float Delay,ECue Cue,float Volume,EPlace Place,const FVector& World,FName Part,float Inner,float Falloff)
{
    if(!GetWorld())return;
    FPending P;P.At=AudioNow()+Delay;P.Cue=Cue;P.Volume=Volume;P.Place=Place;P.World=World;P.Part=Part;P.Inner=Inner;P.Falloff=Falloff;
    Pending.Add(P);
}

void AVeyrAudio::UpdatePending()
{
    if(Pending.IsEmpty()||!GetWorld())return;
    const double Now=AudioNow();
    for(int32 I=Pending.Num()-1;I>=0;--I)
    {
        if(Pending[I].At>Now)continue;
        const FPending P=Pending[I];Pending.RemoveAtSwap(I);
        PlayCueEx(P.Cue,P.Volume,P.Place,P.World,P.Part,P.Inner,P.Falloff);
    }
}

void AVeyrAudio::StopCueVoices(ECue A,ECue B)
{
    for(int32 I=0;I<TotalVoices;++I)
    {
        if(VoiceEndTimes[I]<=0)continue;
        const ECue C=static_cast<ECue>(VoiceCue[I]);
        if(C!=A&&C!=B)continue;
        if(IsValid(Voices[I])){Voices[I]->Stop();Voices[I]->SetSound(nullptr);}
        VoiceWaves[I]=nullptr;VoiceEndTimes[I]=0;VoiceLevels[I]=0.f;ActiveVoices=FMath::Max(0,ActiveVoices-1);
    }
}

// ---------------------------------------------------------------- dragon: contacts

void AVeyrAudio::ArmExpect(int32 Slot,float Seconds,ECue Cue,float Volume,ECue Second,float SecondVolume)
{
    if(!ContactAudioActive()||!GetWorld())
    {
        // No contact events: the old state-change guess plays at once.
        PlayCueEx(Cue,Volume,EPlace::Body);
        if(Second!=ECue::Count)PlayCueEx(Second,SecondVolume,EPlace::Body);
        return;
    }
    FExpect& E=Expect[Slot];
    E.bActive=true;E.Deadline=AudioNow()+Seconds;E.Cue=Cue;E.Volume=Volume;E.Second=Second;E.SecondVolume=SecondVolume;
}

bool AVeyrAudio::ContactAudioActive() const
{
    // Contacts exist only while the detector runs: not under -VeyrNoGroundContacts / -VeyrLegacyFeel, and only on the imported dragon.
    const AVeyrDragon* D=Dragon.Get();
    return bContactAudio&&D&&VeyrFeelSwitches::GroundContacts()&&D->bUsingCustomuseVisual&&D->ImportedPresentation;
}

void AVeyrAudio::SatisfyExpect(int32 Slot){Expect[Slot].bActive=false;}

void AVeyrAudio::UpdateExpectations()
{
    if(!GetWorld())return;
    const double Now=AudioNow();
    for(FExpect& E:Expect)
    {
        if(!E.bActive||Now<E.Deadline)continue;
        E.bActive=false;++ContactFallbacks;
        PlayCueEx(E.Cue,E.Volume,EPlace::Body);
        if(E.Second!=ECue::Count)PlayCueEx(E.Second,E.SecondVolume,EPlace::Body);
    }
}

void AVeyrAudio::HandleContact(const FVeyrGroundContact& C)
{
    const AVeyrDragon* D=Dragon.Get();
    if(!D)return;
    const float S=FMath::Clamp(C.Strength,0.f,1.f);
    const FVector At=C.World;
    ++ContactsHandled[static_cast<int32>(C.Class)];
    const int32 ItemFrom=TapItems.Num();
    struct FRecord
    {
        AVeyrAudio* A;const FVeyrGroundContact& C;int32 From;
        ~FRecord()
        {
            if(!A->bTap||A->bAudition||!A->GetWorld())return;
            FTapContact R;R.T=A->AudioNow()-A->TapT0;R.GameT=C.GameTime;R.HandledGameT=A->GetWorld()->GetTimeSeconds();R.Strength=C.Strength;R.SpeedMps=C.SpeedMps;
            R.Serial=C.Serial;R.Part=static_cast<int32>(C.Part);R.Class=static_cast<int32>(C.Class);R.Leg=C.Leg;R.ItemFrom=From;R.ItemTo=A->TapItems.Num();
            A->TapContacts.Add(R);
        }
    } Record{this,C,ItemFrom};
    switch(C.Class)
    {
        case EVeyrGroundContactClass::Footfall:
            if(PlayCueEx(ECue::DragonStep,FMath::Lerp(.42f,.9f,S),EPlace::World,At))++DragonSteps;
            break;
        case EVeyrGroundContactClass::Stomp:
            SatisfyExpect(2);
            if(PlayCueEx(ECue::DragonStep,1.f,EPlace::World,At))++DragonSteps;
            PlayCueEx(ECue::Impact,FMath::Lerp(.6f,1.f,S),EPlace::World,At);
            if(S>.3f){QueueCue(.1f,ECue::Debris,FMath::Lerp(.5f,.95f,S),EPlace::World,At);++DebrisSounds;}
            break;
        case EVeyrGroundContactClass::BodyFall:
        {
            const bool bBulk=C.Part==EVeyrGroundContactPart::Body||C.Part==EVeyrGroundContactPart::Head||C.Part==EVeyrGroundContactPart::Neck;
            if(bBulk){SatisfyExpect(0);bBodyDownHeard=true;}
            if(bBulk||S>.6f)
            {
                if(PlayCueEx(ECue::Exposed,FMath::Lerp(.6f,1.f,S),EPlace::World,At))++BodyFallSounds;
                PlayCueEx(ECue::Impact,FMath::Lerp(.5f,.9f,S),EPlace::World,At);
            }
            else if(PlayCueEx(ECue::Impact,FMath::Lerp(.45f,.85f,S),EPlace::World,At))++BodyFallSounds;
            if(C.DustTier>=3||S>.5f){QueueCue(.1f,ECue::Debris,FMath::Lerp(.5f,1.f,S),EPlace::World,At);++DebrisSounds;}
            break;
        }
        case EVeyrGroundContactClass::Landing:
            SatisfyExpect(1);
            // One landing sound per landing: a foot-by-foot landing (and the detector's 1.2 s window) must not replay it.
            if(AudioNow()-LastLandingHeard<1.5)break;
            LastLandingHeard=AudioNow();
            if(PlayCueEx(ECue::Exposed,.9f,EPlace::World,At))++BodyFallSounds;
            if(PlayCueEx(ECue::DragonStep,1.f,EPlace::World,At))++DragonSteps;
            QueueCue(.12f,ECue::Debris,.85f,EPlace::World,At);++DebrisSounds;
            break;
    }
}

void AVeyrAudio::HandleContacts()
{
    const AVeyrDragon* D=Dragon.Get();
    if(!D||!ContactAudioActive())return;
    ContactScratch.Reset();
    const int32 Last=D->GetGroundContactsSince(LastContactSerial,ContactScratch);
    if(Last<LastContactSerial){LastContactSerial=Last;return;} // the detector restarted
    LastContactSerial=Last;
    for(const FVeyrGroundContact& C:ContactScratch)HandleContact(C);
}

// ---------------------------------------------------------------- dragon: timed sounds

void AVeyrAudio::UpdateTimedSounds()
{
    const AVeyrDragon* D=Dragon.Get();
    if(bNoMoveSounds||TimedClips.IsEmpty()||!D)return;
    FString ClipName;float Phase=0.f,Time=0.f;
    const UVeyrSkeletalPresentation* Pose=D->ImportedPresentation.Get();
    if(Pose&&Pose->bPoseEvaluated&&!Pose->CurrentClip.IsNone())
    {ClipName=Pose->CurrentClip.ToString();Phase=Pose->CurrentPhase;Time=Pose->CurrentTrimmedSeconds;}
    else
    {
        // No imported pose (legacy dragon): the move and state stand in for the clip, the state's own clock for time.
        static const TCHAR* Moves[]={TEXT("Fire"),TEXT("Flight"),TEXT("Claw"),TEXT("Stomp"),TEXT("Tail"),TEXT("Bite")};
        if(D->State==EVeyrDragonState::Windup||D->State==EVeyrDragonState::Active||D->State==EVeyrDragonState::Recovery)
            ClipName=FString(Moves[static_cast<int32>(D->Move)])+(D->State==EVeyrDragonState::Windup?TEXT("Windup"):D->State==EVeyrDragonState::Active?TEXT("Active"):TEXT("Recovery"));
        else if(D->State==EVeyrDragonState::Collapse)ClipName=TEXT("Collapse");
        else if(D->State==EVeyrDragonState::Exposed)ClipName=TEXT("Exposed");
        else if(D->State==EVeyrDragonState::Rise)ClipName=TEXT("Rise");
        else if(D->State==EVeyrDragonState::Buckle)ClipName=TEXT("Buckle");
        else if(D->State==EVeyrDragonState::Dead)ClipName=TEXT("Death");
        Time=D->GetStateElapsed();Phase=Time/FMath::Max(.001f,D->GetStateDuration());
    }
    if(ClipName.IsEmpty()){TimedClipKey=NAME_None;return;}
    if(ClipName.EndsWith(TEXT("V2r")))ClipName.LeftChopInline(3);
    const TArray<FTimedEvent>* List=TimedClips.Find(FName(*ClipName));
    FString Key=ClipName;
    if(!List||List->IsEmpty())
    {
        FString NoDigits;for(TCHAR Ch:ClipName)if(!FChar::IsDigit(Ch))NoDigits.AppendChar(Ch);
        Key=NoDigits;List=TimedClips.Find(FName(*NoDigits));
    }
    const FName KeyName(*ClipName); // an instance is one clip name; a backwards step restarts it
    const bool bNewInstance=KeyName!=TimedClipKey||Phase<TimedLastPhase-AudioEps||Time<TimedLastTime-AudioEps;
    if(bNewInstance){TimedClipKey=KeyName;TimedLastPhase=TimedLastTime=-1.f;}
    if(List&&!List->IsEmpty())
    {
        for(const FTimedEvent& E:*List)
        {
            const float Now=E.bPhase?Phase:Time;
            const float Prev=E.bPhase?TimedLastPhase:TimedLastTime;
            if(!(E.Pos>Prev&&E.Pos<=Now))continue;
            // A jump into the middle of a clip (state seeded late) must not replay what was skipped.
            if(Prev<0.f&&Now-E.Pos>(E.bPhase?.3f:.45f)){++TimedEventsSkipped;continue;}
            if(PlayCueEx(E.Cue,E.Level,EPlace::Part,FVector::ZeroVector,E.Where))
            {++TimedEventsFired;if(E.Cue==ECue::DragonSwing)bSwingFromData=true;}
        }
    }
    TimedLastPhase=Phase;TimedLastTime=Time;
}

// ---------------------------------------------------------------- dragon: presence between attacks

void AVeyrAudio::UpdatePresence(float DeltaSeconds)
{
    const AVeyrKnight* K=Knight.Get();const AVeyrDragon* D=Dragon.Get();
    if(bNoBreath||!K||!D||!K->HasEnteredEncounter()||D->IsDead())return;
    const bool Roaring=D->ImportedPresentation&&D->ImportedPresentation->CurrentClip==FName(TEXT("Roar"));
    const bool Idle=D->State==EVeyrDragonState::Idle,Move=D->State==EVeyrDragonState::Reposition,Rec=D->State==EVeyrDragonState::Recovery;
    const bool Calm=(Idle||Move||Rec)&&!Roaring&&!D->IsAirborne()&&!(D->Move==EVeyrDragonMove::Fire&&D->GetActiveFlameBeam().bDamaging);
    if(!Calm)
    {
        if(bPresenceCalm){StopCueVoices(ECue::DragonBreathIn,ECue::DragonBreathOut);bBreathExhaleNext=false;}
        bPresenceCalm=false;
        BreathClock=FMath::Max(BreathClock,.9f);
        return;
    }
    bPresenceCalm=true;
    BreathClock-=DeltaSeconds;GrowlClock-=DeltaSeconds;
    if(BreathClock<=0.f)
    {
        const float Vol=Move?.85f:Rec?.9f:.75f;
        const ECue Cue=bBreathExhaleNext?ECue::DragonBreathOut:ECue::DragonBreathIn;
        if(PlayCueEx(Cue,Vol,EPlace::Head))
        {
            if(bBreathExhaleNext){++BreathOuts;BreathClock=Rand.FRandRange(1.6f,2.8f)*(Move?.8f:1.f);}
            else {++BreathIns;BreathClock=DurationLastPlayed*.9f+Rand.FRandRange(.15f,.4f);}
            bBreathExhaleNext=!bBreathExhaleNext;
        }
        else BreathClock=Banks[static_cast<int32>(Cue)].Variants.IsEmpty()?3.f:.5f;
    }
    if(GrowlClock<=0.f&&(Idle||Move))
    {
        const ECue Cue=Rand.FRand()<.45f?ECue::DragonGrowlLow:ECue::DragonSnort;
        if(PlayCueEx(Cue,.75f,EPlace::Head))++Growls;
        GrowlClock=Rand.FRandRange(14.f,26.f);
    }
}

// ---------------------------------------------------------------- knight

void AVeyrAudio::UpdateKnightFeet(float DeltaSeconds,float Speed)
{
    const AVeyrKnight* K=Knight.Get();
    if(!K)return;
    FootClock[0]-=DeltaSeconds;FootClock[1]-=DeltaSeconds;
    if(bTap&&!bAudition&&K->ImportedPresentation)
        for(int32 Side=0;Side<2;++Side)
        {
            FTransform F;
            if(K->ImportedPresentation->GetBoneTargetWorldTransform(Side==0?TEXT("left_foot"):TEXT("right_foot"),F))
                (Side==0?TapNow.KneeL:TapNow.KneeR)=F.GetLocation().Z-K->GetFootLocation().Z;
        }
    TapNow.Speed=Speed;
    if(bAudioPolish&&K->ImportedPresentation)
    {
        for(int32 Side=0;Side<2;++Side)
        {
            FTransform Foot;
            if(!K->ImportedPresentation->GetBoneTargetWorldTransform(Side==0?TEXT("left_foot"):TEXT("right_foot"),Foot))continue;
            const float Limit=Side==0?5.5f:6.4f;
            const float Height=Foot.GetLocation().Z-K->GetFootLocation().Z;
            const bool Near=K->IsGrounded()&&Height<Limit;
            if(Near&&!bFootNearFloor[Side]&&Speed>60.f&&FootClock[Side]<=0.f)
            {
                const float Vol=FMath::Lerp(.4f,.75f,FMath::Clamp((Speed-60.f)/500.f,0.f,1.f));
                if(PlayCueEx(ECue::Footstep,Vol,EPlace::World,Foot.GetLocation()))++KnightSteps;
                FootClock[Side]=.16f;
            }
            if(Near)bFootNearFloor[Side]=true;
            else if(Height>Limit+2.5f||!K->IsGrounded())bFootNearFloor[Side]=false; // lift hysteresis: no double steps on a hovering toe
        }
    }
    else if(Speed>60.f&&K->Action==EVeyrKnightAction::Ready&&FootstepClock<=0.f)
    {
        if(PlayCueEx(ECue::Footstep,.5f))++KnightSteps;
        FootstepClock=FMath::Clamp(220.f/Speed,.32f,.62f);
    }
}

// ---------------------------------------------------------------- the new tick

void AVeyrAudio::TickNew(float DeltaSeconds)
{
    const AVeyrKnight* K=Knight.Get();const AVeyrDragon* D=Dragon.Get();
    if(!K||!D){StopVoices();bInitialized=false;SetActorTickEnabled(false);return;}
    UpdatePending();UpdateVoiceFollow();LoadTimedSounds(false);
    if(K->IsDead()){StopVoices();PlayCueEx(ECue::Death,1.f);bTerminal=true;return;}
    if(D->IsDead())
    {
        if(!bBossDeathSeen)
        {
            StopVoices();Pending.Reset();bBossDeathSeen=true;
            ArmExpect(0,3.f,ECue::Impact,1.f);
        }
        // The fall keeps its body contacts and breaths; Victory waits for the settled death as before.
        HandleContacts();UpdateTimedSounds();UpdateExpectations();
        if(D->GetStateElapsed()>=D->GetStateDuration()){PlayCueEx(ECue::Victory,1.f);bTerminal=true;}
        return;
    }

    if(K->Rolls>LastRolls)PlayCueEx(ECue::Roll,1.f);
    if(K->BlinkDodges>LastBlinks)PlayCueEx(ECue::Blink,1.f);
    FootstepClock-=DeltaSeconds;WingClock-=DeltaSeconds;RoarClock-=DeltaSeconds;
    const float Speed=bAudioPolish&&DeltaSeconds>.001f?FVector::Dist2D(K->GetActorLocation(),LastPlayerPosition)/DeltaSeconds:K->GetVelocity().Size2D();
    UpdateKnightFeet(DeltaSeconds,Speed);
    if(bAudioPolish&&K->ImportedPresentation)
    {
        const bool Drinking=K->Action==EVeyrKnightAction::Heal;
        if(Drinking&&!bDrinkCuePlayed&&K->GetActionElapsed()>=.55f){PlayCueEx(ECue::Heal,.8f);bDrinkCuePlayed=true;}
        if(!Drinking)bDrinkCuePlayed=false;
    }

    // Wings and the dragon's single roar: the same rules as before.
    if((bAudioPolish||bDragonLibraryLoaded)&&D->ImportedPresentation)
    {
        const auto* Pose=D->ImportedPresentation.Get();
        const FVector WingA=Pose->GetBoneLocation(TEXT("VeyrWingNegZWrist")),WingB=Pose->GetBoneLocation(TEXT("VeyrWingPosZWrist"));
        const float Height=(WingA.Z+WingB.Z)*.5f-Pose->GetBoneLocation(TEXT("bone_2")).Z;
        const float Velocity=DeltaSeconds>.001f?(Height-PreviousWingHeight)/DeltaSeconds:0.f;
        const bool WingAction=D->IsAirborne()||(D->Move==EVeyrDragonMove::FlyAway&&D->State==EVeyrDragonState::Windup);
        if(WingAction&&Velocity<-30.f&&PreviousWingVelocity>=-30.f&&WingClock<=0.f){PlayCueEx(ECue::Wing,.8f,EPlace::World,(WingA+WingB)*.5f);WingClock=.35f;}
        PreviousWingHeight=Height;PreviousWingVelocity=Velocity;
        const bool Roaring=Pose->CurrentClip==FName(TEXT("Roar"));
        if(Roaring&&!bRoarCuePlayed&&D->GetStateElapsed()>=2.5833f){PlayCueEx(ECue::Roar,.9f,EPlace::Head);bRoarCuePlayed=true;}
        if(!Roaring)bRoarCuePlayed=false;
    }
    else
    {
        if(D->IsAirborne()&&WingClock<=0.f){PlayCueEx(ECue::Wing,.8f,EPlace::Head);WingClock=1.f;}
        if(RoarClock<=0.f&&D->State==EVeyrDragonState::Windup){PlayCueEx(ECue::Roar,.85f,EPlace::Head);RoarClock=17.f;}
    }
    if(D->Move==EVeyrDragonMove::FlyAway&&D->GetActiveFlameBeam().bDamaging)
    {if(AudioNow()-LastCueTimes[static_cast<int32>(ECue::Fire)]>3.f)PlayCueEx(ECue::Fire,1.f,EPlace::Head);}
    // Fire and take-off threat calls only; no roar on every wind-up (the existing rule).
    if(bDragonLibraryLoaded&&D->State==EVeyrDragonState::Windup&&RoarClock<=0.f&&
       (D->Move==EVeyrDragonMove::Fire||D->Move==EVeyrDragonMove::FlyAway))
    {PlayCueEx(ECue::Roar,.85f,EPlace::Head);RoarClock=14.f;}

    // Knight swings, timed by the clip's own damage windows.
    const bool SwordAction=K->Action==EVeyrKnightAction::LightAttack||K->Action==EVeyrKnightAction::HeavyAttack||
        K->Action==EVeyrKnightAction::Combo||K->Action==EVeyrKnightAction::RollAttack||K->Action==EVeyrKnightAction::RunningAttack||K->Action==EVeyrKnightAction::LeapAttack;
    const FName SourceClip=K->GetActionPresentationClip();
    const float SourceSeconds=K->GetActionSourceSeconds();
    if(K->Action!=LastSwingAction||SourceClip!=LastSwingClip||SourceSeconds+.0001f<LastSwingElapsed)SwingWindowsPlayed.Reset();
    const FVeyrVisualClip* Swing=K->CustomuseVisualDefinition?K->CustomuseVisualDefinition->Clips.Find(SourceClip):nullptr;
    if(SwordAction&&Swing&&!Swing->DamageWindows.IsEmpty())
    {
        const float Rate=FMath::Max(.1f,Swing->GameplayPlayRate);
        const float SegmentStart=SourceSeconds-K->GetActionElapsed()*Rate;
        const float SegmentEnd=SegmentStart+K->GetActionDuration()*Rate;
        for(int32 I=0;I<Swing->DamageWindows.Num();++I)
        {
            if(Swing->DamageWindows[I].X>SegmentEnd+.001f||Swing->DamageWindows[I].Y<SegmentStart-.001f)continue;
            const bool Heavy=K->Action==EVeyrKnightAction::HeavyAttack||K->Action==EVeyrKnightAction::LeapAttack||(K->Action==EVeyrKnightAction::Combo&&I==2);
            const float CueAt=FMath::Max(0.f,static_cast<float>(Swing->DamageWindows[I].X)-(Heavy?.35f:.13f)*Rate);
            if(SourceSeconds>=CueAt&&!SwingWindowsPlayed.Contains(I)){PlayCueEx(Heavy?ECue::HeavySwing:ECue::Swing,1.f);SwingWindowsPlayed.Add(I);}
        }
    }
    else if(!Swing)
    {
        if(K->HeavyAttacks>LastHeavy)PlayCueEx(ECue::HeavySwing,1.f);
        else if(K->LightAttacks>LastLight)PlayCueEx(ECue::Swing,1.f);
    }
    LastSwingAction=K->Action;LastSwingClip=SourceClip;LastSwingElapsed=SourceSeconds;

    // Hits.
    if(D->GetSwordContactCount()>LastSwordContact)PlayCueEx(ECue::Contact,D->GetHeadBonusHitCount()>LastHeadBonus?1.f:.8f);
    if(K->GuardedHits>LastGuardedHits)PlayCueEx(ECue::Guard,1.f);
    else if(K->HitsTaken>LastHitsTaken)
    {
        // Armour hit layered under the pain cue.
        if(PlayCueEx(ECue::ArmorHit,.95f))++ArmorLayers;
        QueueCue(.015f,ECue::PlayerPain,.9f);
    }
    if(!bAudioPolish&&K->SuccessfulHeals>LastHeals)PlayCueEx(ECue::Heal,1.f);
    if(D->GetCollapseCount()>LastCollapses)
    {
        bBodyDownHeard=false;
        ArmExpect(0,4.f,ECue::Impact,.7f);
        PlayCueEx(ECue::DragonPain,.9f,EPlace::Head);
    }
    if(D->GetAttackCount(EVeyrDragonMove::Fire)>LastFireAttacks)PlayCueEx(ECue::Breath,1.f,EPlace::Head);
    if(bWasAirborne&&!D->IsAirborne()&&AudioNow()-LastLandingHeard>2.5)ArmExpect(1,1.f,ECue::Impact,1.f);
    if(D->State!=LastDragonState)
    {
        if(D->State==EVeyrDragonState::Windup)bSwingFromData=false;
        if(D->State==EVeyrDragonState::Exposed){if(!bBodyDownHeard)ArmExpect(0,.9f,ECue::Exposed,1.f,ECue::Impact,.8f);} // the knock-down already thudded: no second one
        else if(D->State==EVeyrDragonState::Buckle)PlayCueEx(ECue::DragonPain,.8f,EPlace::Head);
        else if(D->State==EVeyrDragonState::Active)
        {
            if(D->Move==EVeyrDragonMove::Fire)PlayCueEx(ECue::Fire,1.f,EPlace::Head);
            else if(D->Move==EVeyrDragonMove::Bite)PlayCueEx(ECue::DragonGrowl,.65f,EPlace::Head);
            else if(D->Move==EVeyrDragonMove::BackStomp)ArmExpect(2,.8f,ECue::Impact,.9f);
            else if(D->Move!=EVeyrDragonMove::FlyAway&&(bNoMoveSounds||!bSwingFromData))PlayCueEx(ECue::DragonSwing,.9f,EPlace::Body);
        }
    }

    UpdateTimedSounds();
    HandleContacts();
    UpdateExpectations();
    UpdatePresence(DeltaSeconds);
    if(bTap&&!bAudition)
    {
        TapNow.T=AudioNow()-TapT0;TapNow.GameT=GetWorld()->GetTimeSeconds();TapNow.Dt=DeltaSeconds;
        const FVeyrGroundContactDetector& Det=D->GetGroundContactDetector();
        for(int32 I=0;I<FVeyrGroundContactDetector::MaxSlots;++I)
            if(const FVeyrGroundContactDetector::FSlot* Sl=Det.GetSlot(I))
                for(int32 L=0;L<4;++L)if(Sl->Name==FName(*FString::Printf(TEXT("foot%d"),L)))TapNow.D[L]=Sl->Clearance;
        TapTrace.Add(TapNow);
    }
    SnapshotCounters();
}

// ---------------------------------------------------------------- evidence

TSharedRef<FJsonObject> AVeyrAudio::AudioEvidence() const
{
    TSharedRef<FJsonObject> O=MakeShared<FJsonObject>();
    O->SetBoolField(TEXT("newSet"),bNewSet);
    O->SetNumberField(TEXT("cuesStarted"),CuesStarted);
    O->SetNumberField(TEXT("cuesDropped"),CuesDropped);
    O->SetNumberField(TEXT("activeVoices"),ActiveVoices);
    TSharedRef<FJsonObject> Cues=MakeShared<FJsonObject>(),Silent=MakeShared<FJsonObject>();
    for(int32 I=0;I<CueCount;++I)
    {
        const FString Name=CueName(I);
        Cues->SetNumberField(Name,CueCounts[I]);
        if(CueSilent[I]>0)Silent->SetNumberField(Name,CueSilent[I]);
    }
    O->SetObjectField(TEXT("cueCounts"),Cues);
    O->SetObjectField(TEXT("silentCueRequests"),Silent);
    TSharedRef<FJsonObject> Dragon_=MakeShared<FJsonObject>();
    Dragon_->SetNumberField(TEXT("footfalls"),ContactsHandled[0]);Dragon_->SetNumberField(TEXT("stomps"),ContactsHandled[1]);
    Dragon_->SetNumberField(TEXT("bodyFalls"),ContactsHandled[2]);Dragon_->SetNumberField(TEXT("landings"),ContactsHandled[3]);
    Dragon_->SetNumberField(TEXT("stepCues"),DragonSteps);Dragon_->SetNumberField(TEXT("bodyFallCues"),BodyFallSounds);Dragon_->SetNumberField(TEXT("debrisCues"),DebrisSounds);
    Dragon_->SetNumberField(TEXT("guessFallbacks"),ContactFallbacks);
    Dragon_->SetNumberField(TEXT("breathIn"),BreathIns);Dragon_->SetNumberField(TEXT("breathOut"),BreathOuts);Dragon_->SetNumberField(TEXT("growlsAndSnorts"),Growls);
    Dragon_->SetNumberField(TEXT("timedEventsFired"),TimedEventsFired);Dragon_->SetNumberField(TEXT("timedEventsSkipped"),TimedEventsSkipped);
    Dragon_->SetNumberField(TEXT("soundsReloads"),SoundsReloads);
    O->SetObjectField(TEXT("dragon"),Dragon_);
    TSharedRef<FJsonObject> Kn=MakeShared<FJsonObject>();
    Kn->SetNumberField(TEXT("footSteps"),KnightSteps);Kn->SetNumberField(TEXT("armorLayers"),ArmorLayers);
    O->SetObjectField(TEXT("knight"),Kn);
    return O;
}

TSharedRef<FJsonObject> AVeyrAudio::AudioSetupEvidence() const
{
    TSharedRef<FJsonObject> O=MakeShared<FJsonObject>();
    O->SetBoolField(TEXT("newSet"),bNewSet);
    O->SetBoolField(TEXT("legacyCues"),bLegacyCues);
    O->SetBoolField(TEXT("polish"),bAudioPolish);
    O->SetBoolField(TEXT("variants"),!bNoVariants);
    O->SetBoolField(TEXT("dragonBreath"),!bNoBreath);
    O->SetBoolField(TEXT("dragonMoveSounds"),!bNoMoveSounds);
    O->SetBoolField(TEXT("dragonContactSounds"),ContactAudioActive());
    O->SetNumberField(TEXT("samplesLoaded"),RecordedCuesLoaded);
    O->SetNumberField(TEXT("generatedFiles"),GeneratedFiles);
    TSharedRef<FJsonObject> Variants=MakeShared<FJsonObject>();
    for(int32 I=0;I<CueCount;++I)if(Banks[I].Variants.Num()>0)Variants->SetNumberField(CueName(I),Banks[I].Variants.Num());
    O->SetObjectField(TEXT("variantsLoaded"),Variants);
    O->SetNumberField(TEXT("timedClips"),TimedClips.Num());
    O->SetStringField(TEXT("soundsTable"),SoundsDiagnostic);
    O->SetStringField(TEXT("cueSources"),SourcesDiagnostic);
    return O;
}
