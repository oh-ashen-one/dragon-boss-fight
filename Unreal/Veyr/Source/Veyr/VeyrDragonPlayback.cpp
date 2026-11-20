#include "VeyrDragonPlayback.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "VeyrMoveData.h"
#include "Dom/JsonObject.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "Misc/SecureHash.h"
#include "VeyrDragonPlaybackData.inl"

namespace
{
    float Num(const TSharedPtr<FJsonObject>& O,const TCHAR* Key,float Default)
    {
        double V=0.0;return O.IsValid()&&O->TryGetNumberField(Key,V)?static_cast<float>(V):Default;
    }
}

float FVeyrClipPlayback::SourceFrameAt(float BakedSeconds) const
{
    if(Bake.IsEmpty())return 0.f;
    const float F=FMath::Clamp(BakedSeconds*OutFps,0.f,static_cast<float>(Bake.Num()-1));
    const int32 I=FMath::Min(FMath::FloorToInt(F),Bake.Num()-1),J=FMath::Min(I+1,Bake.Num()-1);
    return FMath::Lerp(Bake[I],Bake[J],F-I);
}

FVector2D FVeyrClipPlayback::TrackAt(float BakedSeconds) const
{
    if(TrackCm.IsEmpty())return FVector2D::ZeroVector;
    const float F=FMath::Clamp(BakedSeconds*OutFps,0.f,static_cast<float>(TrackCm.Num()-1));
    const int32 I=FMath::Min(FMath::FloorToInt(F),TrackCm.Num()-1),J=FMath::Min(I+1,TrackCm.Num()-1);
    return FMath::Lerp(TrackCm[I],TrackCm[J],static_cast<double>(F-I));
}

bool FVeyrClipPlayback::InHold(float SourceFrame) const
{
    for(const FVector2f& H:Holds)if(SourceFrame>=H.X&&SourceFrame<=H.Y)return true;
    return false;
}

bool FVeyrDragonPlayback::Load(FString& OutDiagnostic)
{
    bLoaded=false;Clips.Reset();Moves.Reset();Fades.Reset();
    // Review H5: the data is compiled in (packaged builds do not stage Data/); a readable loose playback.json in the
    // checkout (or -VeyrMoveData=<dir>) overrides it for tuning without a rebuild.
    FString Compiled;
    for(const TCHAR* Chunk:GVeyrDragonPlaybackJson)Compiled+=Chunk;
    Path=FPaths::Combine(FBossMoveData::ResolveDirectory(),TEXT("playback.json"));
    FString Text;
    TSharedPtr<FJsonObject> Root;
    if(FFileHelper::LoadFileToString(Text,*Path)&&FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text),Root)&&Root.IsValid())Source=Path;
    else if(FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Compiled),Root)&&Root.IsValid()){Source=TEXT("compiled");Text=Compiled;}
    else{OutDiagnostic=TEXT("no readable playback data (loose or compiled)");return false;}
    const TSharedPtr<FJsonObject>* Obj=nullptr;
    if(Root->TryGetObjectField(TEXT("fades"),Obj))
        for(const auto& E:(*Obj)->Values){double V=0;if(E.Value->TryGetNumber(V)){if(E.Key==TEXT("default"))FadeDefault=V;else Fades.Add(FName(*E.Key),V);}}
    Phase2Rate=FMath::Clamp(Num(Root,TEXT("phase2_rate"),1.12f),1.f,2.f);
    Phase2MaxRate=FMath::Clamp(Num(Root,TEXT("phase2_max_rate"),1.25f),1.f,8.f);
    Phase2RecoveryExitScale=FMath::Clamp(Num(Root,TEXT("phase2_recovery_exit_scale"),.85f),.2f,1.f);
    // Round 2 one-hand band: phase two no longer halves the recoveries (0.5); 0.85 (goal branch: about 0.9).
    if(!FParse::Param(FCommandLine::Get(),TEXT("VeyrDragonShortRecoveries")))Phase2RecoveryExitScale=FMath::Max(Phase2RecoveryExitScale,.85f);
    Phase2GapScale=FMath::Clamp(Num(Root,TEXT("phase2_gap_scale"),1.f),0.f,1.f);
    Phase2ChainEntryAdd=FMath::Clamp(Num(Root,TEXT("phase2_chain_entry_add"),0.f),0.f,.5f);
    if(Root->TryGetObjectField(TEXT("turn"),Obj)){TrackRateDps=Num(*Obj,TEXT("track_rate_dps"),TrackRateDps);TrackLeadSeconds=Num(*Obj,TEXT("track_lead_seconds"),TrackLeadSeconds);}
    if(Root->TryGetObjectField(TEXT("foot_lock"),Obj))
    {
        FVeyrFootLockTuning& L=FootLock;const TSharedPtr<FJsonObject>& O=*Obj;
        L.PlantHeightCm=Num(O,TEXT("plant_height_cm"),L.PlantHeightCm);L.PlantSpeedCms=Num(O,TEXT("plant_speed_cms"),L.PlantSpeedCms);
        L.ReleaseHeightCm=Num(O,TEXT("release_height_cm"),L.ReleaseHeightCm);L.DragReleaseCm=Num(O,TEXT("drag_release_cm"),L.DragReleaseCm);
        L.SlipCm=Num(O,TEXT("slip_cm"),L.SlipCm);L.ReleaseSeconds=Num(O,TEXT("release_seconds"),L.ReleaseSeconds);
        L.StepSeconds=Num(O,TEXT("step_seconds"),L.StepSeconds);L.StepLiftCm=Num(O,TEXT("step_lift_cm"),L.StepLiftCm);
        L.ProcStepSeconds=FMath::Clamp(Num(O,TEXT("proc_step_seconds"),L.ProcStepSeconds),.1f,.5f);
        L.StepTriggerCm=FMath::Clamp(Num(O,TEXT("step_trigger_cm"),L.StepTriggerCm),2.f,60.f);
        L.StepLeadSeconds=FMath::Clamp(Num(O,TEXT("step_lead_seconds"),L.StepLeadSeconds),0.f,.6f);
        L.CarryDps=FMath::Clamp(Num(O,TEXT("carry_dps"),L.CarryDps),10.f,360.f);
    }
    if(Root->TryGetObjectField(TEXT("moves"),Obj))
        for(const auto& E:(*Obj)->Values)
        {
            const TSharedPtr<FJsonObject> O=E.Value->AsObject();if(!O.IsValid())continue;
            FVeyrMoveTempo T;
            T.Rate=Num(O,TEXT("rate"),1.f);
            T.WindupRate=Num(O,TEXT("windup_rate"),T.Rate);T.StrikeRate=Num(O,TEXT("strike_rate"),T.Rate);T.RecoveryRate=Num(O,TEXT("recovery_rate"),T.Rate);
            T.HoldRate=Num(O,TEXT("hold_rate"),1.f);T.RecoveryExit=FMath::Clamp(Num(O,TEXT("recovery_exit"),1.f),.05f,1.f);
            T.GapScale=FMath::Max(0.f,Num(O,TEXT("gap_scale"),1.f));T.GapAdd=Num(O,TEXT("gap_add"),0.f);
            T.ChainEntry=FMath::Clamp(Num(O,TEXT("chain_entry"),0.f),0.f,.9f);
            O->TryGetBoolField(TEXT("root_track"),T.bRootTrack);
            // Round 2 one-hand band (coordinator 2026-11-19): the recoveries paid for the longer wind-ups shrank the punish
            // window (recovery + idle) 13-18 % against the goal branch. Pay less back: recovery exits rise so the claw,
            // stomp, bite and tail recoveries return to about 0.55 s (fire 0.4 s) and those moves grow instead.
            // -VeyrDragonShortRecoveries keeps the package-14 exits.
            if(!FParse::Param(FCommandLine::Get(),TEXT("VeyrDragonShortRecoveries")))
            {
                const FString K=E.Key;
                const float R2=K==TEXT("claw")?.46f:K==TEXT("stomp")?.43f:K==TEXT("bite")?.45f:K==TEXT("tail")?.40f:K==TEXT("fire")?1.f:0.f;
                T.RecoveryExit=FMath::Max(T.RecoveryExit,R2);
            }
            for(float* R:{&T.Rate,&T.WindupRate,&T.StrikeRate,&T.RecoveryRate,&T.HoldRate})*R=FMath::Clamp(*R,.2f,8.f);
            Moves.Add(FName(*E.Key),T);
        }
    if(!Root->TryGetObjectField(TEXT("clips"),Obj)){OutDiagnostic=TEXT("no clips in ")+Path;return false;}
    for(const auto& E:(*Obj)->Values)
    {
        const TSharedPtr<FJsonObject> O=E.Value->AsObject();if(!O.IsValid())continue;
        FVeyrClipPlayback C;C.Stem=FName(*E.Key);
        FString MoveName;O->TryGetStringField(TEXT("move"),MoveName);C.Move=FName(*MoveName);
        C.SrcFps=FMath::Max(1.f,Num(O,TEXT("src_fps"),24.f));C.OutFps=FMath::Max(1.f,Num(O,TEXT("out_fps"),30.f));
        const TArray<TSharedPtr<FJsonValue>>* A=nullptr;
        if(O->TryGetArrayField(TEXT("bake"),A))for(const auto& V:*A)C.Bake.Add(static_cast<float>(V->AsNumber()));
        if(O->TryGetArrayField(TEXT("holds"),A))for(const auto& V:*A)
        {const auto& P=V->AsArray();if(P.Num()==2)C.Holds.Add(FVector2f(P[0]->AsNumber(),P[1]->AsNumber()));}
        if(O->TryGetArrayField(TEXT("track_cm"),A))for(const auto& V:*A)
        {const auto& P=V->AsArray();if(P.Num()==2)C.TrackCm.Add(FVector2D(P[0]->AsNumber(),P[1]->AsNumber()));}
        if(O->TryGetArrayField(TEXT("track_yaw_deg"),A))for(const auto& V:*A)C.TrackYaw.Add(static_cast<float>(V->AsNumber()));
        bool Monotone=C.Bake.Num()>=2;
        for(int32 I=1;I<C.Bake.Num()&&Monotone;++I)Monotone=C.Bake[I]>=C.Bake[I-1];
        if(!Monotone){OutDiagnostic+=FString(TEXT(" bad bake map "))+FString(*E.Key);continue;}
        if(C.TrackCm.Num()!=C.Bake.Num())C.TrackCm.Reset();
        Clips.Add(C.Stem,MoveTemp(C));
    }
    bLoaded=Clips.Num()>0;
    OutDiagnostic=FString::Printf(TEXT("source=%s md5=%s clips=%d moves=%d fade=%.2f track=%.0fdps phase2=%.2f%s"),*Source,
        *FMD5::HashAnsiString(*Text).Left(8),Clips.Num(),Moves.Num(),FadeDefault,TrackRateDps,Phase2Rate,*OutDiagnostic);
    return bLoaded;
}

const FVeyrClipPlayback* FVeyrDragonPlayback::Find(FName ClipName,FName& OutPhase) const
{
    OutPhase=NAME_None;
    FString S=ClipName.ToString();
    if(!S.EndsWith(TEXT("V2r")))return nullptr; // only the video-to-animation clips carry a bake map
    S.LeftChopInline(3);
    for(const TCHAR* Phase:{TEXT("Windup"),TEXT("Active"),TEXT("Recovery")})
        if(S.EndsWith(Phase)){S.LeftChopInline(FCString::Strlen(Phase));OutPhase=FName(Phase);break;}
    return Clips.Find(FName(*S));
}

void FVeyrDragonPlayback::RatesFor(const FVeyrClipPlayback& Clip,FName Phase,float& OutRate,float& OutHoldRate) const
{
    OutRate=1.f;OutHoldRate=1.f;
    const FVeyrMoveTempo* T=MoveTempo(Clip);
    if(!T)return;
    OutHoldRate=T->HoldRate;
    OutRate=Phase==FName(TEXT("Windup"))?T->WindupRate:Phase==FName(TEXT("Active"))?T->StrikeRate:
        Phase==FName(TEXT("Recovery"))?T->RecoveryRate:T->Rate;
}

float FVeyrDragonPlayback::RealSeconds(const FVeyrClipPlayback& Clip,float B0,float B1,float Rate,float HoldRate)
{
    if(Clip.Bake.Num()<2||B1<=B0)return 0.f;
    double Real=0.0;
    const float Step=1.f/Clip.OutFps;
    for(int32 I=0;I+1<Clip.Bake.Num();++I)
    {
        const float T0=I*Step,T1=(I+1)*Step;
        const float A=FMath::Max(T0,B0),B=FMath::Min(T1,B1);
        if(B<=A)continue;
        const float S0=FMath::Lerp(Clip.Bake[I],Clip.Bake[I+1],(A-T0)/Step),S1=FMath::Lerp(Clip.Bake[I],Clip.Bake[I+1],(B-T0)/Step);
        const float R=Clip.InHold((S0+S1)*.5f)?HoldRate:Rate;
        Real+=(S1-S0)/(Clip.SrcFps*R);
    }
    // Past the measured map (trim rounding): baked rate 1.
    if(B1>Clip.BakedLength())Real+=B1-FMath::Max(B0,Clip.BakedLength());
    return static_cast<float>(Real);
}

float FVeyrDragonPlayback::BakedAfter(const FVeyrClipPlayback& Clip,float B0,float B1,float Real,float Rate,float HoldRate)
{
    if(Clip.Bake.Num()<2||Real<=0.f)return B0;
    double Left=Real;
    const float Step=1.f/Clip.OutFps;
    for(int32 I=0;I+1<Clip.Bake.Num();++I)
    {
        const float T0=I*Step,T1=(I+1)*Step;
        const float A=FMath::Max(T0,B0),B=FMath::Min(T1,B1);
        if(B<=A)continue;
        const float S0=FMath::Lerp(Clip.Bake[I],Clip.Bake[I+1],(A-T0)/Step),S1=FMath::Lerp(Clip.Bake[I],Clip.Bake[I+1],(B-T0)/Step);
        const float R=Clip.InHold((S0+S1)*.5f)?HoldRate:Rate;
        const double Seg=(S1-S0)/(Clip.SrcFps*R);
        if(Seg>=Left)return Seg<=1e-9?B:A+(B-A)*static_cast<float>(Left/Seg);
        Left-=Seg;
    }
    return FMath::Min(B1,FMath::Max(B0,Clip.BakedLength())+static_cast<float>(Left));
}
