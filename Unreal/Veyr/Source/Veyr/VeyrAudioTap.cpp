// Quality goal B1-B3: verification of the sound wiring without a window or an audio device.
//
// -VeyrAudioTap=<absolute dir>   records a software mix (48 kHz stereo wav) and a cue list (json) of exactly what the code
//                                submits to the audio engine: variant, pitch, level, distance attenuation (UE linear
//                                curve, the cue's inner radius and falloff), equal-power pan against the camera, plus the
//                                music and ambience beds at their live gains. Works under -nullrhi and -NoSound.
// -VeyrAudioAudition             new set only: renders every variant of every cue once, then a random phase through the
//                                normal variant picker, over the music, in no time at all (no wall-clock wait), and writes
//                                <dir>/VeyrAudition-{mix.wav,cues.json}. Needs -VeyrAudioTap=<dir>.
//
// Not covered (judge on a rendered capture with --audio-capture-seconds): the engine's own spatialiser and HRTF, voice
// stealing mid-sound (a stopped voice is still rendered whole), the device. Flat (2D) cues are mixed at equal-power centre.
#include "VeyrAudio.h"
#include "VeyrKnight.h"
#include "VeyrDragon.h"
#include "Engine/World.h"
#include "GameFramework/PlayerController.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Misc/CommandLine.h"
#include "HAL/FileManager.h"
#include "Dom/JsonObject.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"
#include "Policies/PrettyJsonPrintPolicy.h"
#include "Algo/Count.h"
#include "Math/RotationMatrix.h"
#include <cmath>

namespace
{
    constexpr int32 TapRate=48000;
    constexpr double TapMaxSeconds=900.0;
    int32 GTapSession=0; // a replay can restart the world (the audio actor is rebuilt): one file set per session
    float ToDb(double X){return float(20.0*std::log10(FMath::Max(X,1e-6)));}
}

// Software model of the master limiter: lookahead peak limiter, ceiling -1.5 dBFS, 5 ms lookahead, 140 ms release.
static void ApplyLimiter(TArray<float>& Mix,float Ceiling,int32 Look,float ReleaseMs)
{
    const int32 N=Mix.Num()/2;
    if(N<=0)return;
    TArray<float> G;G.SetNumUninitialized(N);
    for(int32 I=0;I<N;++I){const float P=FMath::Max(FMath::Abs(Mix[I*2]),FMath::Abs(Mix[I*2+1]));G[I]=P>Ceiling?Ceiling/P:1.f;}
    // minimum over [i, i+look] (monotonic deque)
    TArray<float> Gm;Gm.SetNumUninitialized(N);
    TArray<int32> Dq;Dq.Reserve(Look*2+4);int32 Head=0;
    for(int32 I=N-1;I>=0;--I)
    {
        while(Dq.Num()>Head&&G[Dq.Last()]>=G[I])Dq.Pop();
        Dq.Add(I);
        while(Dq.Num()>Head&&Dq[Head]>I+Look)++Head;
        Gm[I]=G[Dq[Head]];
        if(Head>4096){Dq.RemoveAt(0,Head);Head=0;}
    }
    // release: down at once, up slowly; then a box average over the lookahead (attack ramp)
    const float A=1.f-FMath::Exp(-1.f/(ReleaseMs*.001f*TapRate));
    float R=1.f;
    for(int32 I=0;I<N;++I){R=Gm[I]<R?Gm[I]:R+(Gm[I]-R)*A;Gm[I]=R;}
    double Sum=0;
    for(int32 I=0;I<N;++I)
    {
        Sum+=Gm[I];if(I>Look)Sum-=Gm[I-Look-1];
        const float Gain=float(Sum/FMath::Min(I+1,Look+1));
        Mix[I*2]*=Gain;Mix[I*2+1]*=Gain;
    }
}

void AVeyrAudio::TapInit()
{
    FString Dir;
    if(!FParse::Value(FCommandLine::Get(),TEXT("VeyrAudioTap="),Dir)||Dir.IsEmpty()||FPaths::IsRelative(Dir))return;
    if(!IFileManager::Get().MakeDirectory(*Dir,true))return;
    TapDir=Dir;bTap=true;
    bAudition=bNewSet&&FParse::Param(FCommandLine::Get(),TEXT("VeyrAudioAudition"));
    TapSession=++GTapSession;
    TapT0=AudioNow();TapMusicStart=-1.0;TapGainLast=-1.0;
    TapFx.Reset();TapBeds.Reset();TapItems.Reset();TapGains.Reset();TapEvents.Reset();TapContacts.Reset();TapTrace.Reset();
    UE_LOG(LogTemp,Display,TEXT("VEYR_AUDIO_TAP dir=%s audition=%d"),*TapDir,bAudition?1:0);
}

void AVeyrAudio::TapTick()
{
    if(!bTap||bAudition)return;
    const double T=AudioNow()-TapT0;
    if(T-TapGainLast<.1)return;
    TapGainLast=T;
    const bool Live=bInitialized&&!bTerminal&&!BedPCM[0].IsEmpty()&&Knight.IsValid()&&Knight->HasEnteredEncounter()
        &&!(Dragon.IsValid()&&Dragon->IsDead())&&!Knight->IsDead();
    const float FinalGain=bAudioPolish&&Dragon.IsValid()&&Dragon->Health<=Dragon->MaxHealth*.25f?1.15f:1.f;
    FTapGain G;G.T=T;
    G.Music=Live?MasterVolume*MusicVolume*.32f*(bAudioPolish?MusicDuckGain*MusicEnvelope*FinalGain:1.f)*MixTrim()*(bMixTable?FMath::Pow(10.f,MusicTrimDb/20.f):1.f):0.f;
    G.Ambience=Live&&!BedPCM[1].IsEmpty()?MasterVolume*EffectsVolume*.22f*MixTrim():0.f;
    if(Live&&TapMusicStart<0)TapMusicStart=T;
    TapGains.Add(G);
}

void AVeyrAudio::TapAdd(ECue Cue,const TArray<int16>& PCM,int32 Variant,float Volume,float Level,float Pitch,EPlace Place,const FVector& Pos,float Inner,float Falloff,double T,bool bRandom)
{
    if(!bTap||PCM.IsEmpty()||T<0||T>TapMaxSeconds)return;
    float Dist=0.f,Atten=1.f,Pan=0.f;
    if(Place!=EPlace::Flat)
    {
        FVector Eye=FVector::ZeroVector;FRotator Rot=FRotator::ZeroRotator;
        if(const APlayerController* PC=GetWorld()?GetWorld()->GetFirstPlayerController():nullptr)PC->GetPlayerViewPoint(Eye,Rot);
        Dist=FVector::Dist(Pos,Eye);
        Atten=Dist<=Inner?1.f:FMath::Clamp(1.f-(Dist-Inner)/FMath::Max(1.f,Falloff),0.f,1.f);
        const FVector To=(Pos-Eye).GetSafeNormal();
        Pan=FMath::Clamp(float(FVector::DotProduct(To,FRotationMatrix(Rot).GetScaledAxis(EAxis::Y))),-1.f,1.f);
    }
    const float Angle=(Pan+1.f)*PI*.25f;
    const float Amp=Level*MasterVolume*EffectsVolume*Atten*FMath::Pow(10.f,TapOffsetDb/20.f);
    const float GL=Amp*FMath::Cos(Angle),GR=Amp*FMath::Sin(Angle);
    const int64 Start=int64(T*TapRate);
    const int64 Frames=int64(double(PCM.Num())/SampleRate/FMath::Max(.5f,Pitch)*TapRate);
    const int64 Need=(Start+Frames+TapRate)*2;
    if(TapFx.Num()<Need)TapFx.SetNumZeroed(int32(Need));
    double SumSq=0;float Peak=0.f;
    for(int64 K=0;K<Frames;++K)
    {
        const double Src=double(K)*Pitch*SampleRate/TapRate;
        const int32 I0=int32(Src);
        if(I0+1>=PCM.Num())break;
        const float F=float(Src-I0);
        const float S=(PCM[I0]*(1.f-F)+PCM[I0+1]*F)/32768.f;
        const float L=S*GL,R=S*GR;
        TapFx[int32((Start+K)*2)]+=L;TapFx[int32((Start+K)*2+1)]+=R;
        SumSq+=double(L)*L+double(R)*R;Peak=FMath::Max(Peak,FMath::Max(FMath::Abs(L),FMath::Abs(R)));
    }
    FTapItem Item;Item.T=T;Item.Cue=static_cast<int32>(Cue);Item.Variant=Variant;Item.Volume=Volume;Item.Level=Level;Item.Pitch=Pitch;
    Item.Pan=Pan;Item.Wall=FPlatformTime::Seconds();Item.GameT=GetWorld()?GetWorld()->GetTimeSeconds():0.f;Item.Dist=Dist;Item.Gain=Atten;Item.Seconds=float(Frames)/TapRate;Item.Place=static_cast<uint8>(Place);Item.bRandom=bRandom;
    Item.Label=TapLabel;Item.PeakDb=ToDb(Peak);Item.RmsDb=ToDb(std::sqrt(SumSq/FMath::Max<double>(1.0,Frames*2.0)));
    Item.Kind=static_cast<uint8>(CurKind);Item.KindGain=KindGain(CurKind);Item.Trim=MixTrim();Item.TiltFc=TapTiltFc;Item.TiltK=TapTiltK;Item.Probe=TapProbe;Item.Frame=GFrameCounter;
    TapTiltFc=0.f;TapTiltK=-1.f;TapProbe=-1;
    TapItems.Add(Item);
}

float AVeyrAudio::TypicalVolume(int32 Cue)
{
    // Volumes the live triggers typically use, so the audition measures realistic levels.
    switch(static_cast<ECue>(Cue))
    {
        case ECue::Footstep:return .55f;case ECue::DragonStep:return .7f;
        case ECue::DragonBreathIn:case ECue::DragonBreathOut:return .8f;
        case ECue::DragonGrowlLow:case ECue::DragonSnort:return .75f;case ECue::Debris:return .8f;
        default:return 1.f;
    }
}

void AVeyrAudio::TapAudition()
{
    if(!bTap||!bNewSet)return;
    TapItems.Reset();TapFx.Reset();TapGains.Reset();
    double T=1.0;
    // Dragon cues are placed at a typical fight distance (25 m), the knight's own cues are flat.
    auto Place=[](ECue C,float& Dist,EPlace& P)
    {
        switch(C)
        {
            case ECue::Impact:case ECue::Breath:case ECue::Fire:case ECue::Wing:case ECue::Roar:case ECue::DragonGrowl:case ECue::DragonPain:
            case ECue::DragonStep:case ECue::DragonSwing:case ECue::Bite:case ECue::Debris:case ECue::Exposed:
            case ECue::DragonBreathIn:case ECue::DragonBreathOut:case ECue::DragonGrowlLow:case ECue::DragonSnort:
                P=EPlace::World;Dist=2500.f;break;
            case ECue::Footstep:P=EPlace::World;Dist=300.f;break;
            default:P=EPlace::Flat;Dist=0.f;break;
        }
    };
    for(int32 I=0;I<CueCount;++I)
    {
        const ECue Cue=static_cast<ECue>(I);
        FCueBank& B=Banks[I];
        if(B.Variants.IsEmpty())continue;
        float Dist;EPlace P;Place(Cue,Dist,P);
        float In,Fo;DefaultRadius(Cue,In,Fo);
        const FVector Pos(Dist,0,0);
        const float Volume=TypicalVolume(I);
        const int32 N=B.Variants.Num();
        for(int32 V=0;V<N;++V)
        {
            FChosen C;PickVariant(Cue,Volume,C,V);
            TapAdd(Cue,B.Variants[V],V,Volume,C.Level,C.Pitch,P,Pos,In,Fo,T);
            T+=C.Seconds+.2;
        }
        T+=.5;
        B.Last=-1;
        const float Gap=(Cue==ECue::PlayerPain||Cue==ECue::DragonGrowl||Cue==ECue::DragonPain)?2.2f:(Cue==ECue::DragonGrowlLow||Cue==ECue::DragonSnort)?1.7f:.45f;
        for(int32 D=0;D<FMath::Min(2*N+4,N+3);++D)
        {
            FChosen C;if(!PickVariant(Cue,Volume,C))break;
            TapAdd(Cue,B.Variants[C.V],C.V,Volume,C.Level,C.Pitch,P,Pos,In,Fo,T,true);
            T+=C.Seconds+.15f; (void)Gap;
        }
        T+=1.0;
    }
    // Music underneath, at the live gain with no duck.
    TapMusicStart=0.0;TapGains.Reset();
    FTapGain G;G.T=0.0;G.Music=MasterVolume*MusicVolume*.32f;G.Ambience=BedPCM[1].IsEmpty()?0.f:MasterVolume*EffectsVolume*.22f;
    TapGains.Add(G);
    TapWrite(TEXT("VeyrAudition"));
}

void AVeyrAudio::FlushTap()
{
    if(!bTap||bAudition)return;
    TapWrite(FString::Printf(TEXT("VeyrTap-%d"),TapSession));
}

void AVeyrAudio::TapWrite(const FString& Stem)
{
    if(!bTap)return;
    const int32 Frames=TapFx.Num()/2;
    if(Frames<=0&&TapGains.IsEmpty())return;
    // Beds (music, ambience) at the recorded gains.
    TapBeds.SetNumZeroed(FMath::Max(TapFx.Num(),Frames*2));
    const int32 MusicFrames=BedPCM[0].Num()/4,AmbFrames=BedPCM[1].Num()/2;
    const int16* Music=reinterpret_cast<const int16*>(BedPCM[0].GetData());
    const int16* Amb=reinterpret_cast<const int16*>(BedPCM[1].GetData());
    if(TapMusicStart>=0&&!TapGains.IsEmpty())
    {
        int32 Gi=0;
        const int32 First=int32(TapMusicStart*TapRate);
        for(int32 F=First;F<Frames;++F)
        {
            const double T=double(F)/TapRate;
            while(Gi+1<TapGains.Num()&&TapGains[Gi+1].T<=T)++Gi;
            const FTapGain& G=TapGains[Gi];
            if(MusicFrames>0&&G.Music>0.f)
            {
                const int32 M=int32((int64(F-First)*BedSampleRates[0]/TapRate)%MusicFrames);
                TapBeds[F*2]+=Music[M*2]/32768.f*G.Music;TapBeds[F*2+1]+=Music[M*2+1]/32768.f*G.Music;
            }
            if(AmbFrames>0&&G.Ambience>0.f)
            {
                const int32 M=int32((int64(F-First)*BedSampleRates[1]/TapRate)%AmbFrames);
                const float S=Amb[M]/32768.f*G.Ambience;TapBeds[F*2]+=S;TapBeds[F*2+1]+=S;
            }
        }
    }
    // The master limiter (modelled) over effects + beds. Stats and the wav are what comes out of it.
    TArray<float> Mixed;Mixed.SetNumUninitialized(Frames*2);
    for(int32 I=0;I<Frames*2;++I)Mixed[I]=TapFx[I]+(TapBeds.IsValidIndex(I)?TapBeds[I]:0.f);
    const bool bLimited=!FParse::Param(FCommandLine::Get(),TEXT("VeyrNoMasterLimiter"));
    if(bLimited)ApplyLimiter(Mixed,FMath::Pow(10.f,(bMixTable?LimiterDb:-1.5f)/20.f),240,140.f);
    {
        // The beds alone (music + ambience at their live gains, before the limiter): tools/audio/offline_mix.py re-renders the effects from the items.
        TArray<uint8> Bw;Bw.SetNumUninitialized(44+Frames*4);
        auto B32=[&Bw](int32 At,uint32 V){FMemory::Memcpy(&Bw[At],&V,4);};
        auto B16=[&Bw](int32 At,uint16 V){FMemory::Memcpy(&Bw[At],&V,2);};
        FMemory::Memcpy(&Bw[0],"RIFF",4);B32(4,36+Frames*4);FMemory::Memcpy(&Bw[8],"WAVEfmt ",8);B32(16,16);B16(20,1);B16(22,2);B32(24,TapRate);B32(28,TapRate*4);B16(32,4);B16(34,16);
        FMemory::Memcpy(&Bw[36],"data",4);B32(40,Frames*4);
        for(int32 I=0;I<Frames*2;++I){const int16 Q=int16(FMath::Clamp(TapBeds.IsValidIndex(I)?TapBeds[I]:0.f,-1.f,1.f)*32767.f);FMemory::Memcpy(&Bw[44+I*2],&Q,2);}
        FFileHelper::SaveArrayToFile(Bw,*(TapDir/(Stem+TEXT("-beds.wav"))));
    }
    // Master stats and the wav.
    TArray<uint8> Wav;
    Wav.SetNumUninitialized(44+Frames*4);
    auto W32=[&Wav](int32 At,uint32 V){FMemory::Memcpy(&Wav[At],&V,4);};
    auto W16=[&Wav](int32 At,uint16 V){FMemory::Memcpy(&Wav[At],&V,2);};
    FMemory::Memcpy(&Wav[0],"RIFF",4);W32(4,36+Frames*4);FMemory::Memcpy(&Wav[8],"WAVEfmt ",8);W32(16,16);W16(20,1);W16(22,2);W32(24,TapRate);W32(28,TapRate*4);W16(32,4);W16(34,16);
    FMemory::Memcpy(&Wav[36],"data",4);W32(40,Frames*4);
    float Peak=0.f;int32 Clipped=0;double SumFx=0,SumBed=0;int64 ActiveFx=0;
    for(int32 F=0;F<Frames;++F)
        for(int32 C=0;C<2;++C)
        {
            const float Fx=TapFx[F*2+C],Bed=TapBeds.IsValidIndex(F*2+C)?TapBeds[F*2+C]:0.f;
            const float X=Mixed[F*2+C];
            Peak=FMath::Max(Peak,FMath::Abs(X));if(FMath::Abs(X)>=.999f)++Clipped;
            SumFx+=double(Fx)*Fx;SumBed+=double(Bed)*Bed;if(FMath::Abs(Fx)>1e-4f)++ActiveFx;
            const int16 Q=int16(FMath::Clamp(X,-1.f,1.f)*32767.f);
            FMemory::Memcpy(&Wav[44+(F*2+C)*2],&Q,2);
        }
    FFileHelper::SaveArrayToFile(Wav,*(TapDir/(Stem+TEXT("-mix.wav"))));

    // Per-item music level in its own window, per-cue summary.
    TSharedRef<FJsonObject> Root=MakeShared<FJsonObject>();
    TArray<TSharedPtr<FJsonValue>> Items;
    struct FCueSum{int32 N=0,Back2Back=0,Random=0;int32 Last=-1;TArray<int32> Hist;float MinAbove=999.f,MaxPeak=-999.f;};
    TMap<int32,FCueSum> Sum;
    for(const FTapItem& I:TapItems)
    {
        double MS=0;int64 N=0;
        const int32 A=int32(I.T*TapRate),B=FMath::Min(Frames,A+int32(I.Seconds*TapRate));
        for(int32 F=A;F<B;++F)for(int32 C=0;C<2;++C){const double X=TapBeds.IsValidIndex(F*2+C)?TapBeds[F*2+C]:0.0;MS+=X*X;++N;}
        const float MusicDb=N>0?ToDb(std::sqrt(MS/N)):-120.f;
        TSharedRef<FJsonObject> O=MakeShared<FJsonObject>();
        O->SetStringField(TEXT("cue"),CueName(I.Cue));O->SetNumberField(TEXT("t"),I.T);O->SetNumberField(TEXT("variant"),I.Variant);
        O->SetNumberField(TEXT("volume"),I.Volume);O->SetNumberField(TEXT("level"),I.Level);O->SetNumberField(TEXT("pitch"),I.Pitch);
        O->SetNumberField(TEXT("distanceCm"),I.Dist);O->SetNumberField(TEXT("pan"),I.Pan);O->SetNumberField(TEXT("wall"),I.Wall);O->SetNumberField(TEXT("gameT"),I.GameT);O->SetNumberField(TEXT("attenuation"),I.Gain);O->SetNumberField(TEXT("seconds"),I.Seconds);
        O->SetNumberField(TEXT("peakDb"),I.PeakDb);O->SetNumberField(TEXT("rmsDb"),I.RmsDb);O->SetNumberField(TEXT("musicRmsDb"),MusicDb);
        O->SetNumberField(TEXT("aboveMusicDb"),I.RmsDb-MusicDb);O->SetBoolField(TEXT("randomPhase"),I.bRandom);if(!I.Label.IsEmpty())O->SetStringField(TEXT("label"),I.Label);
        O->SetStringField(TEXT("kind"),KindName(I.Kind));O->SetNumberField(TEXT("kindGain"),I.KindGain);O->SetNumberField(TEXT("trim"),I.Trim);O->SetNumberField(TEXT("frame"),double(I.Frame));
        if(I.TiltK>=0.f){O->SetNumberField(TEXT("tiltFc"),I.TiltFc);O->SetNumberField(TEXT("tiltK"),I.TiltK);}
        if(I.Probe>=0&&ProbeWaves.IsValidIndex(I.Probe)&&ProbeWaves[I.Probe])O->SetNumberField(TEXT("firstPullWall"),ProbeWaves[I.Probe]->FirstPullWall);
        Items.Add(MakeShared<FJsonValueObject>(O));
        FCueSum& S=Sum.FindOrAdd(I.Cue);
        ++S.N;if(S.Hist.Num()<=I.Variant)S.Hist.SetNumZeroed(I.Variant+1);++S.Hist[I.Variant];
        if(I.bRandom||!bAudition){if(S.Last==I.Variant)++S.Back2Back;S.Last=I.Variant;if(I.bRandom)++S.Random;}
        if(MusicDb>-100.f)S.MinAbove=FMath::Min(S.MinAbove,I.RmsDb-MusicDb);
        S.MaxPeak=FMath::Max(S.MaxPeak,I.PeakDb);
    }
    TSharedRef<FJsonObject> Cues=MakeShared<FJsonObject>();
    for(const auto& KV:Sum)
    {
        TSharedRef<FJsonObject> O=MakeShared<FJsonObject>();
        O->SetNumberField(TEXT("events"),KV.Value.N);O->SetNumberField(TEXT("variantsLoaded"),Banks[KV.Key].Variants.Num());
        O->SetNumberField(TEXT("variantsUsed"),Algo::CountIf(KV.Value.Hist,[](int32 H){return H>0;}));
        O->SetNumberField(TEXT("backToBackRepeats"),KV.Value.Back2Back);O->SetNumberField(TEXT("maxPeakDb"),KV.Value.MaxPeak);
        if(KV.Value.MinAbove<900.f)O->SetNumberField(TEXT("minAboveMusicDb"),KV.Value.MinAbove);
        TArray<TSharedPtr<FJsonValue>> H;for(int32 X:KV.Value.Hist)H.Add(MakeShared<FJsonValueNumber>(X));
        O->SetArrayField(TEXT("variantHistogram"),H);
        Cues->SetObjectField(CueName(KV.Key),O);
    }
    Root->SetStringField(TEXT("note"),TEXT("Software mix of what the code submits (linear distance curve, equal-power pan, flat cues centred); not the engine's output."));
    Root->SetBoolField(TEXT("newSet"),bNewSet);Root->SetBoolField(TEXT("audition"),bAudition);Root->SetBoolField(TEXT("masterLimiterModelled"),bLimited);Root->SetNumberField(TEXT("tapOffsetDb"),TapOffsetDb);Root->SetNumberField(TEXT("makeupDb"),MakeupDb);
    Root->SetNumberField(TEXT("seconds"),double(Frames)/TapRate);
    Root->SetBoolField(TEXT("mixTable"),bMixTable);Root->SetNumberField(TEXT("masterTrimDb"),MasterTrimDb);Root->SetNumberField(TEXT("musicTrimDb"),MusicTrimDb);Root->SetNumberField(TEXT("limiterDb"),bMixTable?LimiterDb:-1.5f);
    Root->SetNumberField(TEXT("masterVolume"),MasterVolume);Root->SetNumberField(TEXT("effectsVolume"),EffectsVolume);Root->SetNumberField(TEXT("tapT0Wall"),TapT0>=0?FPlatformTime::Seconds()-(AudioNow()-TapT0):0.0);
    {TSharedRef<FJsonObject> Kg=MakeShared<FJsonObject>();for(int32 K=0;K<MixKindCount;++K)Kg->SetNumberField(KindName(K),KindGainDb[K]);Root->SetObjectField(TEXT("kindGainDb"),Kg);}
    Root->SetNumberField(TEXT("masterPeakDb"),ToDb(Peak));Root->SetNumberField(TEXT("clippedSamples"),Clipped);
    Root->SetNumberField(TEXT("effectsRmsDbOverActive"),ActiveFx>0?ToDb(std::sqrt(SumFx/double(ActiveFx))):-120.0);
    Root->SetNumberField(TEXT("bedsRmsDbOverAll"),Frames>0?ToDb(std::sqrt(SumBed/(Frames*2.0))):-120.0);
    Root->SetNumberField(TEXT("musicStartSeconds"),TapMusicStart);
    Root->SetObjectField(TEXT("cues"),Cues);Root->SetArrayField(TEXT("items"),Items);
    {
        TArray<TSharedPtr<FJsonValue>> Cs;
        for(const FTapContact& C:TapContacts)
        {
            TSharedRef<FJsonObject> O=MakeShared<FJsonObject>();
            O->SetNumberField(TEXT("t"),C.T);O->SetNumberField(TEXT("gameTime"),C.GameT);O->SetNumberField(TEXT("handledGameTime"),C.HandledGameT);
            O->SetNumberField(TEXT("serial"),C.Serial);O->SetNumberField(TEXT("part"),C.Part);O->SetNumberField(TEXT("class"),C.Class);O->SetNumberField(TEXT("leg"),C.Leg);
            O->SetNumberField(TEXT("strength"),C.Strength);O->SetNumberField(TEXT("speedMps"),C.SpeedMps);O->SetNumberField(TEXT("itemFrom"),C.ItemFrom);O->SetNumberField(TEXT("itemTo"),C.ItemTo);
            Cs.Add(MakeShared<FJsonValueObject>(O));
        }
        Root->SetArrayField(TEXT("contacts"),Cs);
        TArray<TSharedPtr<FJsonValue>> Es;
        for(const FTapEvent& E:TapEvents)
        {
            TSharedRef<FJsonObject> O=MakeShared<FJsonObject>();O->SetStringField(TEXT("kind"),E.Kind);O->SetNumberField(TEXT("t"),E.T);O->SetNumberField(TEXT("wall"),E.Wall);O->SetNumberField(TEXT("gameT"),E.GameT);O->SetNumberField(TEXT("frame"),double(E.Frame));
            Es.Add(MakeShared<FJsonValueObject>(O));
        }
        Root->SetArrayField(TEXT("events"),Es);
        TArray<TSharedPtr<FJsonValue>> Pulls;
        for(const TObjectPtr<UVeyrProbeWave>& W:ProbeWaves)Pulls.Add(MakeShared<FJsonValueNumber>(W?double(W->FirstPullWall):-1.0));
        Root->SetArrayField(TEXT("probePulls"),Pulls);
        // Per-frame trace (columns): time, game time, dt, knight foot heights (cm above the floor), knight speed, dragon sole clearances (cm).
        TSharedRef<FJsonObject> Tr=MakeShared<FJsonObject>();
        auto Col=[&](const TCHAR* Name,TFunction<double(const FTapFrame&)> F)
        {
            TArray<TSharedPtr<FJsonValue>> A;A.Reserve(TapTrace.Num());
            for(const FTapFrame& T:TapTrace)A.Add(MakeShared<FJsonValueNumber>(FMath::RoundToDouble(F(T)*1000.0)/1000.0));
            Tr->SetArrayField(Name,A);
        };
        Col(TEXT("t"),[](const FTapFrame& T){return T.T;});Col(TEXT("gameT"),[](const FTapFrame& T){return double(T.GameT);});Col(TEXT("dt"),[](const FTapFrame& T){return double(T.Dt);});
        Col(TEXT("kneeL"),[](const FTapFrame& T){return double(T.KneeL);});Col(TEXT("kneeR"),[](const FTapFrame& T){return double(T.KneeR);});Col(TEXT("speed"),[](const FTapFrame& T){return double(T.Speed);});
        Col(TEXT("foot0"),[](const FTapFrame& T){return double(T.D[0]);});Col(TEXT("foot1"),[](const FTapFrame& T){return double(T.D[1]);});
        Col(TEXT("foot2"),[](const FTapFrame& T){return double(T.D[2]);});Col(TEXT("foot3"),[](const FTapFrame& T){return double(T.D[3]);});
        Root->SetObjectField(TEXT("trace"),Tr);
    }
    FString Out;
    TSharedRef<TJsonWriter<TCHAR,TPrettyJsonPrintPolicy<TCHAR>>> Writer=TJsonWriterFactory<TCHAR,TPrettyJsonPrintPolicy<TCHAR>>::Create(&Out);
    FJsonSerializer::Serialize(Root,Writer);
    FFileHelper::SaveStringToFile(Out,*(TapDir/(Stem+TEXT("-cues.json"))));
    UE_LOG(LogTemp,Display,TEXT("VEYR_AUDIO_TAP_WRITTEN %s seconds=%.1f items=%d peakDb=%.1f clipped=%d"),*Stem,double(Frames)/TapRate,TapItems.Num(),ToDb(Peak),Clipped);
}
