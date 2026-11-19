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
#include "AudioMixerBlueprintLibrary.h"
#include "SubmixEffects/AudioMixerSubmixEffectDynamicsProcessor.h"
#include <cmath>

namespace
{
#include "VeyrAudioDefaultSounds.inl"
    constexpr double AudioEps=1e-4;
}

float AVeyrAudio::TargetLevelDb(ECue Cue)
{
    // Final gated RMS (dBFS) of a variant at cue Volume 1.0, after the master (0.65) and before the master limiter.
    // 2026-11-19 second pass: a real capture of the first pass was 15 LU under the reference (-30 LUFS) and the weapon
    // hits did not rise out of the mix, so transients are now set near full scale and background cues (breath, steps of
    // the dragon's calm) stay low: the loudness range comes from the difference.
    switch(Cue)
    {
        case ECue::Swing:return -10.f;         case ECue::HeavySwing:return -8.f;
        case ECue::Contact:return -5.f;        case ECue::Guard:return -6.f;
        case ECue::ArmorHit:return -5.f;       case ECue::Impact:return -5.f;
        case ECue::DragonStep:return -6.f;     case ECue::DragonSwing:return -7.f;
        case ECue::Bite:return -7.f;           case ECue::Breath:return -15.f;
        case ECue::Fire:return -11.f;          case ECue::Wing:return -15.f;
        case ECue::Roll:return -16.f;          case ECue::Footstep:return -9.f;
        case ECue::Blink:return -15.f;         case ECue::Break:return -9.f;
        case ECue::Debris:return -12.f;        case ECue::Exposed:return -5.f;
        case ECue::Death:return -8.f;          case ECue::Heal:return -15.f;
        case ECue::Victory:return -10.f;       case ECue::DragonBreathIn:return -22.f;
        case ECue::DragonBreathOut:return -22.f; case ECue::DragonGrowlLow:return -14.f;
        case ECue::DragonSnort:return -18.f;
        case ECue::Roar:return -8.f;           case ECue::DragonGrowl:return -11.f;
        case ECue::DragonPain:return -11.f;    case ECue::PlayerPain:return -8.f;
        default:return 0.f;
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

namespace
{
    struct FBiquad
    {
        float B0=0,B1=0,B2=0,A1=0,A2=0,Z1=0,Z2=0;
        static FBiquad Make(bool bHigh,float Hz,float Rate)
        {
            FBiquad F;const float W=2.f*PI*Hz/Rate,C=FMath::Cos(W),Sn=FMath::Sin(W),Al=Sn/(2.f*.7071f),A0=1.f+Al;
            if(bHigh){F.B0=(1+C)/2/A0;F.B1=-(1+C)/A0;F.B2=(1+C)/2/A0;}else{F.B0=(1-C)/2/A0;F.B1=(1-C)/A0;F.B2=(1-C)/2/A0;}
            F.A1=-2*C/A0;F.A2=(1-Al)/A0;return F;
        }
        float Run(float X){const float Y=B0*X+Z1;Z1=B1*X-A1*Y+Z2;Z2=B2*X-A2*Y;return Y;}
    };
}

void AVeyrAudio::AddVariant(ECue Cue,TArray<int16>&& S)
{
    FCueBank& B=Banks[static_cast<int32>(Cue)];
    double Sum=0,E=0,El=0,Eh=0;int64 N=0;float Peak=1e-4f;
    FBiquad Lp=FBiquad::Make(false,200.f,SampleRate),Hp=FBiquad::Make(true,2000.f,SampleRate);
    for(int16 V:S)
    {
        const float X=float(V)/32768.f,Ax=FMath::Abs(X);
        Peak=FMath::Max(Peak,Ax);
        if(Ax>.01f){Sum+=double(X)*X;++N;}
        const float L=Lp.Run(X),H=Hp.Run(X);E+=double(X)*X;El+=double(L)*L;Eh+=double(H)*H;
    }
    float AttackMs=0.f;
    for(int32 I=0;I<S.Num();++I)if(FMath::Abs(float(S[I]))/32768.f>=.5f*Peak){AttackMs=1000.f*I/SampleRate;break;}
    const double Rms=N>0?std::sqrt(Sum/double(N)):1e-4;
    const float MeasuredDb=float(20.0*std::log10(FMath::Max(Rms,1e-5)));
    const float TargetDb=TargetLevelDb(Cue);
    // Gain brings the variant's gated RMS to the target at the default master (0.65); the peak keeps it under -1 dBFS.
    // Targets are dBFS of the RECORDED master, so the engine's measured -9 dB is divided out here; the peak keeps a single voice near -1 dBFS there.
    float Gain=TargetDb<0.f?FMath::Pow(10.f,(TargetDb-MeasuredDb)/20.f)/(.65f*EngineFactor):1.f/(.65f*EngineFactor);
    Gain=FMath::Min(Gain,.55f/(Peak*.65f*EngineFactor));
    B.Variants.Add(MoveTemp(S));B.Gains.Add(Gain);B.Peaks.Add(Peak);
    B.LowShare.Add(float(El/FMath::Max(E,1e-9)));B.HighShare.Add(float(Eh/FMath::Max(E,1e-9)));B.AttackMs.Add(AttackMs);
}

void AVeyrAudio::SetBankFromSingle(ECue Cue,const TArray<uint8>& Bytes,bool bNormalize)
{
    TArray<int16> S;
    if(!BytesToSamples(Bytes,S))return;
    FCueBank& B=Banks[static_cast<int32>(Cue)];
    B.Variants.Reset();B.Gains.Reset();B.Peaks.Reset();B.LowShare.Reset();B.HighShare.Reset();B.AttackMs.Reset();
    AddVariant(Cue,MoveTemp(S));
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
    B.Variants.Reset();B.Gains.Reset();B.Peaks.Reset();B.LowShare.Reset();B.HighShare.Reset();B.AttackMs.Reset();B.Last=-1;
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
    for(const FString& File:Use)
    {
        if(B.Variants.Num()>=MaxVariants)break;
        TArray<uint8> Bytes;TArray<int16> S;
        if(!FFileHelper::LoadFileToArray(Bytes,*(Dir/File))||!BytesToSamples(Bytes,S))continue;
        AddVariant(Cue,MoveTemp(S));
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
            FString CueText,WhereText,RoleText;double Phase=0,Time=0,Level=1,PitchD=1;
            (*E)->TryGetStringField(TEXT("cue"),CueText);(*E)->TryGetStringField(TEXT("where"),WhereText);
            (*E)->TryGetNumberField(TEXT("level"),Level);(*E)->TryGetStringField(TEXT("role"),RoleText);(*E)->TryGetNumberField(TEXT("pitch"),PitchD);
            FTimedEvent Ev;Ev.Level=float(Level);Ev.PitchMul=float(PitchD);Ev.Role=RoleText==TEXT("sharp")?1:RoleText==TEXT("body")?2:RoleText==TEXT("low")?3:0;Ev.Where=WhereText.IsEmpty()?FName(TEXT("head")):FName(*WhereText);
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

bool AVeyrAudio::PickVariant(ECue Cue,float Volume,FChosen& C,int32 Force,uint8 Role,float PitchMul)
{
    const int32 Index=static_cast<int32>(Cue);
    FCueBank& Bank=Banks[Index];
    if(Bank.Variants.IsEmpty())return false;
    int32 V=0;
    if(Force>=0)V=FMath::Min(Force,Bank.Variants.Num()-1);
    else
    {
        // Candidates: the variants that fit the role (sharp = attack with highs, body = mids, low = sub/low), falling back to all.
        TArray<int32,TInlineAllocator<MaxVariants>> Pool;
        for(int32 I=0;I<Bank.Variants.Num();++I)
        {
            const float Lo=Bank.LowShare[I],Hi=Bank.HighShare[I],Mid=FMath::Max(0.f,1.f-Lo-Hi);
            const bool Ok=Role==0||(Role==1&&Hi>.40f&&Bank.AttackMs[I]<30.f)||(Role==2&&Mid>.35f)||(Role==3&&Lo>.40f);
            if(Ok)Pool.Add(I);
        }
        if(Pool.IsEmpty())for(int32 I=0;I<Bank.Variants.Num();++I)Pool.Add(I);
        if(bNoVariants)V=Pool[0];
        else if(Pool.Num()==1)V=Pool[0];
        else{do{V=Pool[Rand.RandRange(0,Pool.Num()-1)];}while(V==Bank.Last);}
    }
    Bank.Last=V;
    C.V=V;
    C.Seconds0=float(Bank.Variants[V].Num())/SampleRate;
    const bool bVocal=IsVocal(Cue);
    float Pitch=1.f,LevelJitter=1.f;
    if(!bVocal&&!bNoVariants&&Force<0)
    {
        Pitch=1.f+Rand.FRandRange(-.05f,.05f);
        LevelJitter=FMath::Pow(10.f,Rand.FRandRange(-2.f,2.f)/20.f);
        // Big bodies: a wider pitch spread so consecutive stomps and falls differ even when the same few samples are near.
        if(Cue==ECue::DragonStep||Cue==ECue::Exposed||Cue==ECue::Impact||Cue==ECue::Debris)Pitch*=1.f+Rand.FRandRange(-.10f,.10f);
    }
    if(Cue==ECue::DragonStep||Cue==ECue::Exposed)Pitch*=FMath::Lerp(1.07f,.9f,FMath::Clamp(Volume,0.f,1.f)); // heavier = lower
    Pitch*=PitchMul;
    C.Pitch=Pitch;
    C.Seconds=C.Seconds0/FMath::Max(.5f,Pitch);
    C.Level=FMath::Clamp(Volume,0.f,1.5f)*Bank.Gains[V]*LevelJitter*FMath::Pow(10.f,MakeupDb/20.f);
    // Solo peak ceiling just under full scale after the master; the master limiter deals with sums.
    if(Bank.Peaks.IsValidIndex(V)&&Bank.Peaks[V]>.01f)
        C.Level=FMath::Min(C.Level,.55f/(Bank.Peaks[V]*FMath::Max(.05f,MasterVolume*EffectsVolume)*EngineFactor));
    return true;
}

// A per-play spectral tilt for the big bodies (stomps, falls, debris): a random low-pass split with the high part
// scaled, so consecutive events differ in colour and not only in sample, pitch and level.
static void TiltCopy(const TArray<int16>& In,TArray<int16>& Out,FRandomStream& Rand,float Rate,uint8 Mode)
{
    // Mode 1: dark (the highs scaled right down); mode 2: bright (the highs kept or lifted); 0: anywhere in between.
    const float Fc=Mode==1?Rand.FRandRange(350.f,900.f):Mode==2?Rand.FRandRange(1800.f,5000.f):Rand.FRandRange(450.f,3200.f);
    const float K=Mode==1?Rand.FRandRange(.02f,.25f):Mode==2?Rand.FRandRange(.9f,1.5f):Rand.FRandRange(.08f,1.25f);
    const float A=1.f-FMath::Exp(-2.f*PI*Fc/Rate);
    Out.SetNumUninitialized(In.Num());
    float Lp=0.f;
    for(int32 I=0;I<In.Num();++I)
    {
        const float X=In[I];Lp+=A*(X-Lp);
        Out[I]=int16(FMath::Clamp(Lp+K*(X-Lp),-32767.f,32767.f));
    }
}

bool AVeyrAudio::PlayCueEx(ECue Cue,float Volume,EPlace Place,const FVector& World,FName Part,float Inner,float Falloff,uint8 Role,float PitchMul)
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
    if(Now-LastCueTimes[Index]<(Cue==ECue::DragonStep?0.0:bStep?.025:.06))return false; // four feet may land in one frame
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
    if(!PickVariant(Cue,Volume,C,-1,Role,PitchMul))return false; // never the variant played last; random pitch and level off vocal cues
    const int32 V=C.V;const float Pitch=C.Pitch,Seconds=C.Seconds,Seconds0=C.Seconds0;
    TArray<int16> Tilted;
    const TArray<int16>* Source=&Bank.Variants[V];
    if(!bNoVariants&&(Cue==ECue::DragonStep||Cue==ECue::Exposed||Cue==ECue::Impact||Cue==ECue::Debris)&&(Place!=EPlace::Flat||TiltMode!=0))
    {TiltCopy(Bank.Variants[V],Tilted,Rand,float(SampleRate),TiltMode);Source=&Tilted;} // not on the knight's own near-field hits
    const TArray<int16>& PCM=*Source;
    float Level=C.Level;
    // Brief duck of the small background cues after a head hit or a flame ignition, so the big moment rises out of them.
    if(Now<BackgroundDuckUntil&&Volume<.6f&&(Cue==ECue::DragonStep||Cue==ECue::Footstep||Cue==ECue::DragonBreathIn||Cue==ECue::DragonBreathOut||Cue==ECue::Wing||Cue==ECue::Roll||Cue==ECue::Debris))
        Level*=.35f;
    // Peak budget instead of a limiter: transients that start together (a stomp is four layers) are scaled so their peaks, if they
    // coincided, stay under about -1.5 dBFS on the recorded master. Only voices started in the last 120 ms count (their peaks are still ahead or just passed).
    float Load=0.f;
    for(int32 I=0;I<TotalVoices;++I)if(VoiceEndTimes[I]>0&&Now-VoiceStartTimes[I]<.12)Load+=VoicePeakAmp[I];
    const float PeakOfThis=Bank.Peaks.IsValidIndex(V)?Bank.Peaks[V]:1.f;
    float PeakAmp=Level*MasterVolume*EffectsVolume*EngineFactor*PeakOfThis;
    constexpr float PeakBudget=.64f; // -3.9 dBFS: the real peak sat 1.1 dB above the .84 (-1.5 dBFS) design with the music under it, so -3.9 gives about -2.8 dBFS, clear of -1 dBTP
    if(Load+PeakAmp>PeakBudget&&PeakAmp>1e-4f){Level*=FMath::Max(.35f,(PeakBudget-Load)/PeakAmp);PeakAmp=Level*MasterVolume*EffectsVolume*EngineFactor*PeakOfThis;}
    const bool bPeakTracked=true;(void)bPeakTracked;
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
    VoiceEndTimes[Slot]=Now+Seconds+.15;VoiceStartTimes[Slot]=Now;VoicePeakAmp[Slot]=PeakAmp;
    VoiceCue[Slot]=Index;
    LastCueTimes[Index]=Now;
    DurationLastPlayed=Seconds;
    ++CuesStarted;++ActiveVoices;++CueCounts[Index];++VariantPlays[Index][FMath::Min(V,MaxVariants-1)];
    if(Cue==ECue::PlayerPain)++PlayerPainCues;
    if(Cue==ECue::Roar||Cue==ECue::DragonGrowl||Cue==ECue::DragonPain)++DragonVocalCues;
    if(bLogCues)UE_LOG(LogTemp,Display,TEXT("VEYR_CUE t=%.2f %s v=%d vol=%.2f lvl=%.2f pitch=%.3f place=%d part=%s"),Now,CueName(Index),V,Volume,Level,Pitch,int32(Place),*Part.ToString());
    return true;
}

void AVeyrAudio::QueueCue(float Delay,ECue Cue,float Volume,EPlace Place,const FVector& World,FName Part,float Inner,float Falloff,uint8 Role,float PitchMul,uint8 Tilt)
{
    if(!GetWorld())return;
    FPending P;P.At=AudioNow()+Delay;P.Cue=Cue;P.Volume=Volume;P.Place=Place;P.World=World;P.Part=Part;P.Inner=Inner;P.Falloff=Falloff;P.Role=Role;P.PitchMul=PitchMul;P.Tilt=Tilt;
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
        TiltMode=P.Tilt;
        PlayCueEx(P.Cue,P.Volume,P.Place,P.World,P.Part,P.Inner,P.Falloff,P.Role,P.PitchMul);
        TiltMode=0;
    }
}

void AVeyrAudio::StopCueVoices(ECue A,ECue B)
{
    for(int32 I=0;I<TotalVoices;++I)
    {
        if(VoiceEndTimes[I]<=0)continue;
        const ECue C=static_cast<ECue>(VoiceCue[I]);
        if(C!=A&&C!=B)continue;
        // Fade out (0.3 s) instead of a hard stop: a breath cut by a strike must not click. The slot frees at once for the mix budget.
        if(IsValid(Voices[I]))Voices[I]->FadeOut(.3f,0.f);
        VoiceEndTimes[I]=FMath::Min(VoiceEndTimes[I],AudioNow()+.35);VoiceLevels[I]*=.3f;
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

void AVeyrAudio::TapEvent(const TCHAR* Kind)
{
    if(!bTap||bAudition||!GetWorld())return;
    FTapEvent E;E.Kind=Kind;E.T=AudioNow()-TapT0;TapEvents.Add(E);
}

void AVeyrAudio::InstallMasterChain()
{
    // A master limiter so the louder mix peaks at about -1.5 dBFS instead of clipping. -VeyrNoMasterLimiter removes it.
    if(bMasterChain||FParse::Param(FCommandLine::Get(),TEXT("VeyrNoMasterLimiter"))||!GetWorld())return;
    bMasterChain=true;
    USubmixEffectDynamicsProcessorPreset* Limiter=NewObject<USubmixEffectDynamicsProcessorPreset>(this,TEXT("VeyrMasterLimiter"));
    FSubmixEffectDynamicsProcessorSettings S;
    S.DynamicsProcessorType=ESubmixEffectDynamicsProcessorType::Limiter;
    S.PeakMode=ESubmixEffectDynamicsPeakMode::Peak;
    S.LinkMode=ESubmixEffectDynamicsChannelLinkMode::Peak;
    S.ThresholdDb=-1.5f;S.KneeBandwidthDb=0.f;S.LookAheadMsec=5.f;S.AttackTimeMsec=1.f;S.ReleaseTimeMsec=140.f;
    S.InputGainDb=0.f;S.OutputGainDb=0.f;
    Limiter->SetSettings(S);
    UAudioMixerBlueprintLibrary::AddMasterSubmixEffect(this,Limiter);
    UE_LOG(LogTemp,Display,TEXT("VEYR_AUDIO_MASTER_LIMITER installed ceiling -1.5 dBFS lookahead 5 ms release 140 ms"));
}

void AVeyrAudio::PlayWeaponHit(int32 Weight,bool bHead)
{
    // The knight's own sword hitting the dragon: near-field (flat, never attenuated by where the camera is), layered:
    // a sharp mid/high attack, a body, a low thump; sized by weight class (0 light, 1 heavy). A hit on the downed head is the
    // reward moment and the fullest of all: every layer up, a ring, a smash body, and the small background and the music duck briefly.
    TapEvent(bHead?TEXT("weaponHead"):Weight>0?TEXT("weaponHeavy"):TEXT("weaponLight"));
    const double Now=AudioNow();
    if(bHead&&GetWorld())
    {
        BackgroundDuckUntil=Now+.5;
        MusicDuckTarget=.22f;MusicDuckUntil=GetWorld()->GetTimeSeconds()+.6;
    }
    const float W=bHead?1.15f:Weight>0?1.f:.8f;
    PlayCueEx(ECue::Contact,W*1.4f,EPlace::Flat,FVector::ZeroVector,NAME_None,0.f,0.f,1);
    PlayCueEx(ECue::Guard,W*(bHead?1.1f:.55f),EPlace::Flat,FVector::ZeroVector,NAME_None,0.f,0.f,1);
    PlayCueEx(ECue::ArmorHit,W*1.1f,EPlace::Flat,FVector::ZeroVector,NAME_None,0.f,0.f,2);
    PlayCueEx(ECue::Impact,bHead?1.5f:Weight>0?1.2f:.5f,EPlace::Flat,FVector::ZeroVector,NAME_None,0.f,0.f,3,Weight>0||bHead?1.f:1.15f);
    if(Weight>0||bHead)
    {
        // Heavy and head hits: a second low body and a mid thump so all three bands rise, not only the highs.
        PlayCueEx(ECue::Exposed,bHead?1.1f:.9f,EPlace::Flat,FVector::ZeroVector,NAME_None,0.f,0.f,3,1.05f);
        QueueCue(.012f,ECue::DragonStep,bHead?.9f:.7f,EPlace::Flat,FVector::ZeroVector,NAME_None,0.f,0.f,2,1.2f);
    }
    if(bHead)
    {
        QueueCue(.02f,ECue::Guard,.8f,EPlace::Flat,FVector::ZeroVector,NAME_None,0.f,0.f,1,.8f);              // the ring, a little later and lower
        QueueCue(.02f,ECue::Break,.7f,EPlace::Flat,FVector::ZeroVector,NAME_None,0.f,0.f,3,.9f);               // a smash body
    }
}

void AVeyrAudio::PlayStompLayers(const FVector& AtIn,float S,bool bLanding)
{
    // An attack stomp, a slam or a landing: a random recipe over differently shaped samples. Neighbours differ by more than tilt:
    // the colour alternates dark and bright, the recipe and the transient layer never repeat twice in a row, and the pitch moves within +-2 semitones.
    // The sound sits halfway between the contact and the body centre, so the feet's sideways offsets pan less hard.
    FVector At=AtIn;
    if(const AVeyrDragon* D=Dragon.Get())At=FMath::Lerp(AtIn,FVector(D->GetActorLocation().X,D->GetActorLocation().Y,AtIn.Z),.5f);
    bTiltBrightNext=!bTiltBrightNext;
    const uint8 Tilt=bTiltBrightNext?2:1;
    int32 R=Rand.RandRange(0,3);
    if(R==LastStompRecipe)R=(R+1+Rand.RandRange(0,2))%4;
    LastStompRecipe=R;
    int32 Tr=Rand.RandRange(0,2);
    if(Tr==LastTransient)Tr=(Tr+1)%3;
    LastTransient=Tr;
    const float Semis=Rand.FRandRange(-2.f,2.f);
    const float Pitch=FMath::Pow(2.f,Semis/12.f);
    const float Heavy=FMath::Lerp(.7f,.95f,S);
    const float Slip=Rand.FRandRange(0.f,.05f);
    TiltMode=Tilt;
    if(PlayCueEx(ECue::DragonStep,Heavy,EPlace::World,At,NAME_None,0.f,0.f,R==1||R==3?2:3,Pitch))++DragonSteps;
    if(R==0)PlayCueEx(ECue::Impact,FMath::Lerp(.6f,1.f,S),EPlace::World,At,NAME_None,0.f,0.f,3,Pitch);
    else if(R==1)QueueCue(Slip,ECue::Exposed,FMath::Lerp(.5f,.85f,S),EPlace::World,At,NAME_None,0.f,0.f,2,Pitch,Tilt);
    else if(R==2){QueueCue(.03f+Slip,ECue::DragonStep,.7f,EPlace::World,At,NAME_None,0.f,0.f,3,.8f*Pitch,Tilt);PlayCueEx(ECue::Impact,.55f,EPlace::World,At,NAME_None,0.f,0.f,2,Pitch);}
    else{PlayCueEx(ECue::Break,.55f,EPlace::World,At,NAME_None,0.f,0.f,3,1.1f*Pitch);QueueCue(Slip,ECue::Impact,.5f,EPlace::World,At,NAME_None,0.f,0.f,2,1.15f*Pitch,Tilt);}
    TiltMode=0;
    // A different transient layer each time: debris crackle, a break crack, or a late body.
    if(Tr==0)QueueCue(.04f,ECue::Debris,FMath::Lerp(.5f,.95f,S),EPlace::World,At,NAME_None,0.f,0.f,1,Pitch,Tilt);
    else if(Tr==1)QueueCue(.03f,ECue::Break,.45f,EPlace::World,At,NAME_None,0.f,0.f,1,Pitch);
    else QueueCue(.08f,ECue::Exposed,.5f,EPlace::World,At,NAME_None,0.f,0.f,2,.9f*Pitch,Tilt);
    if(bLanding)PlayCueEx(ECue::Exposed,.9f,EPlace::World,At,NAME_None,0.f,0.f,3);
    if(S>.3f||bLanding){QueueCue(.1f,ECue::Debris,FMath::Lerp(.5f,.95f,S),EPlace::World,At,NAME_None,0.f,0.f,Rand.RandRange(0,1)?1:2);++DebrisSounds;}
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
            // Which foot strikes are "strong": with -VeyrStompPass3 every Footfall with detector strength >= 0.65 (the speed into the floor, a curve that
            // saturates early: about half the foot contacts of a fight reach 1.0) plays the heavy layers like an attack. With -VeyrStompHierarchy none do:
            // a walking step is a lighter thump scaled by its strength, and only attacks (Stomp class = a foot in a strike state, slams, claws, tail, landing, falls) are heavy.
            if(!bStompHierarchy&&S>=.65f)
            {
                TapEvent(TEXT("dragonStomp"));
                PlayStompLayers(At,S,false);
                break;
            }
            TapEvent(TEXT("dragonFootfall"));
            {
                const float V=bStompHierarchy?FMath::Lerp(.1f,.5f,S):(S<.3f?.1f:FMath::Lerp(.14f,.4f,(S-.3f)/.35f));
                if(PlayCueEx(ECue::DragonStep,V,EPlace::World,At,NAME_None,0.f,0.f,Rand.RandRange(0,1)?2:3))++DragonSteps;
                if(bStompHierarchy&&S>.7f)PlayCueEx(ECue::Impact,.18f,EPlace::World,At,NAME_None,0.f,0.f,3);
            }
            break;
        case EVeyrGroundContactClass::Stomp:
            TapEvent(TEXT("dragonStomp"));
            SatisfyExpect(2);
            PlayStompLayers(At,S,false);
            break;
        case EVeyrGroundContactClass::BodyFall:
        {
            TapEvent(TEXT("bodyFall"));
            const bool bBulk=C.Part==EVeyrGroundContactPart::Body||C.Part==EVeyrGroundContactPart::Head||C.Part==EVeyrGroundContactPart::Neck;
            if(bBulk){SatisfyExpect(0);bBodyDownHeard=true;}
            if(bBulk||S>.6f)
            {
                if(PlayCueEx(ECue::Exposed,FMath::Lerp(.7f,1.f,S),EPlace::World,At,NAME_None,0.f,0.f,Rand.RandRange(0,1)?2:3))++BodyFallSounds;
                PlayCueEx(ECue::Impact,FMath::Lerp(.5f,.9f,S),EPlace::World,At,NAME_None,0.f,0.f,Rand.RandRange(2,3));
            }
            else if(PlayCueEx(ECue::Impact,FMath::Lerp(.45f,.85f,S),EPlace::World,At,NAME_None,0.f,0.f,Rand.RandRange(2,3)))++BodyFallSounds;
            if(C.DustTier>=3||S>.5f){QueueCue(.1f,ECue::Debris,FMath::Lerp(.5f,1.f,S),EPlace::World,At);++DebrisSounds;}
            break;
        }
        case EVeyrGroundContactClass::Landing:
            SatisfyExpect(1);
            // One landing sound per landing (already played at the airborne flip when that came first).
            if(AudioNow()-LastLandingHeard<1.5)break;
            LastLandingHeard=AudioNow();
            TapEvent(TEXT("dragonLanding"));
            PlayStompLayers(At,1.f,true);++BodyFallSounds;
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
            if(bTap)TapLabel=FString::Printf(TEXT("%s@%s%.2f"),*ClipName,E.bPhase?TEXT("p"):TEXT("t"),Now);
            const bool bPlayed=PlayCueEx(E.Cue,E.Level,EPlace::Part,FVector::ZeroVector,E.Where,0.f,0.f,E.Role,E.PitchMul);
            TapLabel.Reset();
            if(bPlayed)
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
        const float Vol=Move?.9f:Rec?.95f:.8f;
        const ECue Cue=bBreathExhaleNext?ECue::DragonBreathOut:ECue::DragonBreathIn;
        if(PlayCueEx(Cue,Vol,EPlace::Head))
        {
            if(bBreathExhaleNext){++BreathOuts;BreathClock=Rand.FRandRange(2.4f,3.6f)*(Move?.8f:1.f);} // calm large animal: about 12 breaths a minute
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
                const float Vol=FMath::Lerp(.45f,.8f,FMath::Clamp((Speed-60.f)/500.f,0.f,1.f));
                TapEvent(TEXT("knightStep"));
                // Near-field: the knight's own footsteps are not attenuated by the camera.
                if(PlayCueEx(ECue::Footstep,Vol,EPlace::Flat))++KnightSteps;
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
    InstallMasterChain();
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
    // Flame: the ignition on the first frame the flame exists, then the roar re-triggered while it burns (ground fire and the flight jet alike).
    {
        const bool Beam=D->GetActiveFlameBeam().bDamaging;
        const double NowA=AudioNow();
        if(Beam&&!bFireBeamWas)
        {
            FireStartedAt=NowA;TapEvent(TEXT("fireIgnition"));
            // The first flame frame: a sharp crack and a burst (mid and high), the low thump, the whoosh and then the sustained roar below.
            // The small background and the music duck for a moment so the start rises out of them.
            BackgroundDuckUntil=NowA+.4;MusicDuckTarget=.35f;MusicDuckUntil=GetWorld()->GetTimeSeconds()+.45;
            PlayCueEx(ECue::Debris,1.3f,EPlace::Flat,FVector::ZeroVector,NAME_None,0.f,0.f,1,1.25f);
            PlayCueEx(ECue::Break,1.f,EPlace::Flat,FVector::ZeroVector,NAME_None,0.f,0.f,1,1.3f);
            PlayCueEx(ECue::Impact,1.2f,EPlace::Flat,FVector::ZeroVector,NAME_None,0.f,0.f,3);
            PlayCueEx(ECue::Breath,1.f,EPlace::Head);
            PlayCueEx(ECue::Fire,1.f,EPlace::Head);
        }
        else if(Beam&&NowA-LastCueTimes[static_cast<int32>(ECue::Fire)]>FMath::Max(1.2f,Banks[static_cast<int32>(ECue::Fire)].Variants.IsEmpty()?1.2f:float(Banks[static_cast<int32>(ECue::Fire)].Variants[0].Num())/SampleRate-.4f))
            PlayCueEx(ECue::Fire,1.f,EPlace::Head);
        bFireBeamWas=Beam;
    }
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
    if(D->GetSwordContactCount()>LastSwordContact)
    {
        const bool bHead=D->GetHeadBonusHitCount()>LastHeadBonus;
        const bool bHeavy=K->Action==EVeyrKnightAction::HeavyAttack||K->Action==EVeyrKnightAction::LeapAttack||K->Action==EVeyrKnightAction::RollAttack;
        PlayWeaponHit(bHeavy?1:0,bHead);
    }
    if(K->GuardedHits>LastGuardedHits)PlayCueEx(ECue::Guard,1.f);
    else if(K->HitsTaken>LastHitsTaken)
    {
        // Armour hit layered under the pain cue (near-field, flat).
        TapEvent(TEXT("hurt"));
        if(PlayCueEx(ECue::ArmorHit,1.f,EPlace::Flat,FVector::ZeroVector,NAME_None,0.f,0.f,1))++ArmorLayers;
        PlayCueEx(ECue::Impact,.5f,EPlace::Flat,FVector::ZeroVector,NAME_None,0.f,0.f,3,1.2f);
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
    if(bWasAirborne&&!D->IsAirborne()&&AudioNow()-LastLandingHeard>2.5)
    {
        // The landing sounds at the airborne flip, the frame the dust wall rises, not when the last foot has settled.
        LastLandingHeard=AudioNow();TapEvent(TEXT("dragonLanding"));
        PlayStompLayers(D->GetActorLocation(),1.f,true);++BodyFallSounds;
    }
    if(D->State!=LastDragonState)
    {
        if(D->State==EVeyrDragonState::Windup)bSwingFromData=false;
        if(D->State==EVeyrDragonState::Exposed){if(!bBodyDownHeard)ArmExpect(0,.9f,ECue::Exposed,1.f,ECue::Impact,.8f);} // the knock-down already thudded: no second one
        else if(D->State==EVeyrDragonState::Buckle)PlayCueEx(ECue::DragonPain,.8f,EPlace::Head);
        else if(D->State==EVeyrDragonState::Active)
        {
            if(D->Move==EVeyrDragonMove::Fire&&!D->GetActiveFlameBeam().bDamaging){} // the flame's own first frame fires the ignition below
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
