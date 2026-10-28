#include "VeyrMoveData.h"

#include "Dom/JsonObject.h"
#include "Dom/JsonValue.h"
#include "HAL/IConsoleManager.h"
#include "HAL/FileManager.h"
#include "Misc/CommandLine.h"
#include "Misc/FileHelper.h"
#include "Misc/Parse.h"
#include "Misc/Paths.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"

DEFINE_LOG_CATEGORY(LogVeyrMoveData);

namespace
{
    TAutoConsoleVariable<FString> CVarVeyrMoveDataDir(
        TEXT("veyr.MoveData.Dir"), TEXT(""),
        TEXT("Folder holding moves.json, boxes.json, tempo.json, sounds.json. Empty = <Project>/../../Data/dragon ")
        TEXT("(the repository's Data/dragon), then <Project>/Data/dragon. Command line -VeyrMoveData=<dir> also works. ")
        TEXT("Read when the dragon begins play or on veyr.MoveData.Reload."),
        ECVF_Default);

    TAutoConsoleVariable<int32> CVarVeyrMoveDataEnable(
        TEXT("veyr.MoveData.Enable"), 1,
        TEXT("1 = the dragon loads Data/dragon/*.json at BeginPlay (hurt capsules, data windows). ")
        TEXT("0 = never load; hard-coded behaviour only."),
        ECVF_Default);

    TAutoConsoleVariable<int32> CVarVeyrMoveDataHits(
        TEXT("veyr.MoveData.Hits"), 1,
        TEXT("0 = data windows never hurt. 1 = data-only moves (veyr.MoveData.Play) hurt the knight. ")
        TEXT("2 = moves mapped onto a hard-coded EVeyrDragonMove hurt too and replace that move's hard-coded contact."),
        ECVF_Default);

    TAutoConsoleVariable<int32> CVarVeyrMoveDataSwordParts(
        TEXT("veyr.MoveData.SwordParts"), 1,
        TEXT("1 = a sword sweep that misses every hard-coded region is tested against the boxes.json hurt capsules. 0 = hard-coded regions only."),
        ECVF_Default);

    TAutoConsoleVariable<int32> CVarVeyrMoveDataHurtBlocksPawn(
        TEXT("veyr.MoveData.HurtBlocksPawn"), 1,
        TEXT("0 = hurt capsules are query-only. 1 = all but the wing plates block the knight (Pawn). 2 = every part blocks. ")
        TEXT("Applied when the capsules are bound (BeginPlay, veyr.MoveData.Reload)."),
        ECVF_Default);

    TAutoConsoleVariable<int32> CVarVeyrMoveDataDraw(
        TEXT("veyr.MoveData.Draw"), 0,
        TEXT("1 = draw the hurt capsules (green, red while their window is open) and the current data move each frame."),
        ECVF_Cheat);

    using FJsonObjectPtr=TSharedPtr<FJsonObject>;
    using FJsonArray=TArray<TSharedPtr<FJsonValue>>;

    bool ReadJsonFile(const FString& Path, FJsonObjectPtr& Out, FString& Error)
    {
        FString Text;
        if(!FPaths::FileExists(Path)){Error=FString::Printf(TEXT("missing %s"),*Path);return false;}
        if(!FFileHelper::LoadFileToString(Text,*Path)){Error=FString::Printf(TEXT("unreadable %s"),*Path);return false;}
        const TSharedRef<TJsonReader<>> Reader=TJsonReaderFactory<>::Create(Text);
        if(!FJsonSerializer::Deserialize(Reader,Out)||!Out.IsValid())
        {
            Error=FString::Printf(TEXT("malformed JSON %s: %s"),*Path,*Reader->GetErrorMessage());
            return false;
        }
        return true;
    }

    bool Finite(double V) { return FMath::IsFinite(V); }

    bool NumberField(const FJsonObjectPtr& O, const TCHAR* Field, float& Out, bool bRequired, FString& Error, const FString& Where)
    {
        double V=0.0;
        if(!O->TryGetNumberField(Field,V))
        {
            if(bRequired)Error=FString::Printf(TEXT("%s: missing number '%s'"),*Where,Field);
            return !bRequired;
        }
        if(!Finite(V)){Error=FString::Printf(TEXT("%s: non-finite '%s'"),*Where,Field);return false;}
        Out=static_cast<float>(V);
        return true;
    }

    bool VectorValue(const TSharedPtr<FJsonValue>& Value, int32 Count, FVector& Out)
    {
        const FJsonArray* Items=nullptr;
        if(!Value.IsValid()||!Value->TryGetArray(Items)||!Items||Items->Num()<Count)return false;
        double C[3]={0,0,0};
        for(int32 I=0;I<Count;++I)
        {
            if(!(*Items)[I].IsValid()||!(*Items)[I]->TryGetNumber(C[I])||!Finite(C[I]))return false;
        }
        Out=FVector(C[0],C[1],C[2]);
        return true;
    }

    bool VectorField(const FJsonObjectPtr& O, const TCHAR* Field, int32 Count, FVector& Out, bool bRequired, FString& Error, const FString& Where)
    {
        const TSharedPtr<FJsonValue> V=O->TryGetField(Field);
        if(!V.IsValid())
        {
            if(bRequired)Error=FString::Printf(TEXT("%s: missing vector '%s'"),*Where,Field);
            return !bRequired;
        }
        if(!VectorValue(V,Count,Out)){Error=FString::Printf(TEXT("%s: '%s' is not %d finite numbers"),*Where,Field,Count);return false;}
        return true;
    }

    FName NameField(const FJsonObjectPtr& O, const TCHAR* Field)
    {
        FString S;
        return O->TryGetStringField(Field,S)&&!S.IsEmpty()?FName(*S):NAME_None;
    }

    FString Vec(const FVector& V) { return FString::Printf(TEXT("(%.1f, %.1f, %.1f)"),V.X,V.Y,V.Z); }
}

bool VeyrMoveData::IsEnabled() { return CVarVeyrMoveDataEnable.GetValueOnGameThread()!=0; }
int32 VeyrMoveData::HitsMode() { return FMath::Clamp(CVarVeyrMoveDataHits.GetValueOnGameThread(),0,2); }
bool VeyrMoveData::SwordPartsEnabled() { return CVarVeyrMoveDataSwordParts.GetValueOnGameThread()!=0; }
int32 VeyrMoveData::HurtBlocksPawnMode() { return FMath::Clamp(CVarVeyrMoveDataHurtBlocksPawn.GetValueOnGameThread(),0,2); }
int32 VeyrMoveData::DrawMode() { return CVarVeyrMoveDataDraw.GetValueOnGameThread(); }

float FBossMove::TempoAt(float ClipSeconds) const
{
    if(bLoop)return 1.f;
    for(const FBossTempoPhase& Phase:Tempo)
        if(ClipSeconds>=Phase.From&&ClipSeconds<Phase.To)return FMath::Max(.05f,Phase.Rate);
    return 1.f;
}

FVector FBossMove::TrackAt(float ClipSeconds, float Fps) const
{
    if(Track.IsEmpty())return FVector::ZeroVector;
    const float Frame=FMath::Clamp(ClipSeconds*Fps,0.f,static_cast<float>(Track.Num()-1));
    const int32 I=FMath::FloorToInt(Frame),J=FMath::Min(I+1,Track.Num()-1);
    return FMath::Lerp(Track[I],Track[J],Frame-I);
}

FString FBossMoveData::ResolveDirectory()
{
    TArray<FString> Candidates;
    const FString FromCVar=CVarVeyrMoveDataDir.GetValueOnGameThread();
    if(!FromCVar.IsEmpty())Candidates.Add(FromCVar);
    FString FromCommandLine;
    if(FParse::Value(FCommandLine::Get(),TEXT("VeyrMoveData="),FromCommandLine)&&!FromCommandLine.IsEmpty())Candidates.Add(FromCommandLine);
    // Unreal/Veyr is the project; Data/ sits at the repository root two levels up.
    Candidates.Add(FPaths::Combine(FPaths::ProjectDir(),TEXT("../../Data/dragon")));
    Candidates.Add(FPaths::Combine(FPaths::ProjectDir(),TEXT("Data/dragon")));
    for(FString Candidate:Candidates)
    {
        if(FPaths::IsRelative(Candidate))Candidate=FPaths::Combine(FPaths::ProjectDir(),Candidate);
        Candidate=FPaths::ConvertRelativePathToFull(Candidate);
        FPaths::CollapseRelativeDirectories(Candidate);
        if(FPaths::FileExists(FPaths::Combine(Candidate,TEXT("moves.json"))))return Candidate;
    }
    // Report the first candidate so the log names where it looked.
    FString First=Candidates[0];
    if(FPaths::IsRelative(First))First=FPaths::Combine(FPaths::ProjectDir(),First);
    First=FPaths::ConvertRelativePathToFull(First);
    FPaths::CollapseRelativeDirectories(First);
    return First;
}

void FBossMoveData::Reset()
{
    bLoaded=false;Directory.Reset();Fps=24.f;GameScale=1.f;
    Moves.Reset();MoveOrder.Reset();Parts.Reset();SoundDirectory.Reset();StepSounds.Reset();
    Errors.Reset();Warnings.Reset();
}

const FBossPart* FBossMoveData::FindPart(FName Part) const
{
    return Parts.FindByPredicate([Part](const FBossPart& P){return P.Name==Part;});
}

int32 FBossMoveData::CountAttacks() const
{
    int32 Count=0;
    for(const auto& Entry:Moves)Count+=Entry.Value.Attacks.Num();
    return Count;
}

bool FBossMoveData::Load(const FString& InDirectory)
{
    Reset();
    Directory=InDirectory;
    FString Error;
    auto Fail=[&](const FString& Reason)
    {
        Errors.Add(Reason);
        UE_LOG(LogVeyrMoveData,Warning,TEXT("VEYR_MOVEDATA_FAILED dir=%s reason=%s; dragon keeps its hard-coded behaviour"),*Directory,*Reason);
        TArray<FString> Keep=Errors;
        Reset();Directory=InDirectory;Errors=MoveTemp(Keep);
        return false;
    };

    // moves.json (required)
    FJsonObjectPtr MovesRoot;
    if(!ReadJsonFile(FPaths::Combine(Directory,TEXT("moves.json")),MovesRoot,Error))return Fail(Error);
    double Number=0.0;
    if(MovesRoot->TryGetNumberField(TEXT("fps"),Number)&&Finite(Number)&&Number>0.0)Fps=static_cast<float>(Number);
    if(MovesRoot->TryGetNumberField(TEXT("game_scale"),Number)&&Finite(Number)&&Number>0.0)GameScale=static_cast<float>(Number);
    else Warnings.Add(TEXT("moves.json has no game_scale; assuming 1"));
    const FJsonObjectPtr* MovesObject=nullptr;
    if(!MovesRoot->TryGetObjectField(TEXT("moves"),MovesObject)||!MovesObject||!MovesObject->IsValid())
        return Fail(TEXT("moves.json: missing object 'moves'"));
    for(const auto& Entry:(*MovesObject)->Values)
    {
        const FString Key(*Entry.Key);
        const FString Where=TEXT("moves.json ")+Key;
        const FJsonObjectPtr* MoveObject=nullptr;
        if(!Entry.Value.IsValid()||!Entry.Value->TryGetObject(MoveObject)||!MoveObject||!MoveObject->IsValid())
            return Fail(Where+TEXT(": not an object"));
        const FJsonObjectPtr& O=*MoveObject;
        FBossMove Move;Move.Name=FName(*Key);
        if(!NumberField(O,TEXT("duration"),Move.Duration,true,Error,Where))return Fail(Error);
        if(Move.Duration<=0.f)return Fail(Where+TEXT(": duration must be positive"));
        float Frames=0.f;
        if(!NumberField(O,TEXT("frames"),Frames,false,Error,Where))return Fail(Error);
        Move.Frames=FMath::RoundToInt(Frames);
        O->TryGetBoolField(TEXT("loop"),Move.bLoop);
        const FJsonArray* Items=nullptr;
        if(O->TryGetArrayField(TEXT("track"),Items)&&Items)
            for(int32 I=0;I<Items->Num();++I)
            {
                FVector P;
                if(!VectorValue((*Items)[I],3,P))return Fail(FString::Printf(TEXT("%s: track[%d] is not [x, y, yaw]"),*Where,I));
                Move.Track.Add(P);
            }
        if(O->TryGetArrayField(TEXT("attacks"),Items)&&Items)
            for(int32 I=0;I<Items->Num();++I)
            {
                const FJsonObjectPtr* A=nullptr;const FString W=FString::Printf(TEXT("%s attacks[%d]"),*Where,I);
                if(!(*Items)[I].IsValid()||!(*Items)[I]->TryGetObject(A)||!A||!A->IsValid())return Fail(W+TEXT(": not an object"));
                FBossAttack Attack;Attack.Part=NameField(*A,TEXT("part"));
                if(Attack.Part.IsNone())return Fail(W+TEXT(": missing part"));
                if(!NumberField(*A,TEXT("t0"),Attack.T0,true,Error,W)||!NumberField(*A,TEXT("t1"),Attack.T1,true,Error,W)||
                   !NumberField(*A,TEXT("peak_t"),Attack.PeakT,false,Error,W)||!NumberField(*A,TEXT("peak_v"),Attack.PeakV,false,Error,W)||
                   !VectorField(*A,TEXT("at_peak"),3,Attack.AtPeak,false,Error,W))return Fail(Error);
                if(Attack.T1<Attack.T0)return Fail(W+TEXT(": t1 before t0"));
                Move.Attacks.Add(Attack);
            }
        if(O->TryGetArrayField(TEXT("shocks"),Items)&&Items)
            for(int32 I=0;I<Items->Num();++I)
            {
                const FJsonObjectPtr* S=nullptr;const FString W=FString::Printf(TEXT("%s shocks[%d]"),*Where,I);
                if(!(*Items)[I].IsValid()||!(*Items)[I]->TryGetObject(S)||!S||!S->IsValid())return Fail(W+TEXT(": not an object"));
                FBossShock Shock;Shock.Bone=NameField(*S,TEXT("bone"));
                if(!NumberField(*S,TEXT("t"),Shock.T,true,Error,W)||!VectorField(*S,TEXT("at"),3,Shock.At,true,Error,W)||
                   !NumberField(*S,TEXT("speed"),Shock.Speed,false,Error,W)||!NumberField(*S,TEXT("radius"),Shock.Radius,true,Error,W))return Fail(Error);
                Move.Shocks.Add(Shock);
            }
        if(O->TryGetArrayField(TEXT("contacts"),Items)&&Items)
            for(int32 I=0;I<Items->Num();++I)
            {
                const FJsonObjectPtr* C=nullptr;const FString W=FString::Printf(TEXT("%s contacts[%d]"),*Where,I);
                if(!(*Items)[I].IsValid()||!(*Items)[I]->TryGetObject(C)||!C||!C->IsValid())return Fail(W+TEXT(": not an object"));
                FBossContact Contact;Contact.Bone=NameField(*C,TEXT("bone"));Contact.Kind=NameField(*C,TEXT("kind"));
                float Frame=0.f;
                if(!NumberField(*C,TEXT("t"),Contact.T,true,Error,W)||!NumberField(*C,TEXT("frame"),Frame,false,Error,W)||
                   !NumberField(*C,TEXT("speed"),Contact.Speed,false,Error,W)||!VectorField(*C,TEXT("at"),3,Contact.At,false,Error,W))return Fail(Error);
                Contact.Frame=FMath::RoundToInt(Frame);
                Move.Contacts.Add(Contact);
            }
        Moves.Add(Move.Name,MoveTemp(Move));MoveOrder.Add(FName(*Key));
    }
    if(Moves.IsEmpty())return Fail(TEXT("moves.json: no moves"));

    // boxes.json (required)
    FJsonObjectPtr BoxesRoot;
    if(!ReadJsonFile(FPaths::Combine(Directory,TEXT("boxes.json")),BoxesRoot,Error))return Fail(Error);
    if(BoxesRoot->TryGetNumberField(TEXT("game_scale"),Number)&&Finite(Number)&&!FMath::IsNearlyEqual(static_cast<float>(Number),GameScale,1.e-3f))
        return Fail(FString::Printf(TEXT("boxes.json game_scale %.6f differs from moves.json %.6f"),Number,GameScale));
    const FJsonObjectPtr* PartsObject=nullptr;
    if(!BoxesRoot->TryGetObjectField(TEXT("parts"),PartsObject)||!PartsObject||!PartsObject->IsValid())
        return Fail(TEXT("boxes.json: missing object 'parts'"));
    for(const auto& Entry:(*PartsObject)->Values)
    {
        const FString Key(*Entry.Key);
        const FString Where=TEXT("boxes.json ")+Key;
        const FJsonObjectPtr* PartObject=nullptr;
        if(!Entry.Value.IsValid()||!Entry.Value->TryGetObject(PartObject)||!PartObject||!PartObject->IsValid())
            return Fail(Where+TEXT(": not an object"));
        const FJsonObjectPtr& O=*PartObject;
        FBossPart Part;Part.Name=FName(*Key);Part.Bone=NameField(O,TEXT("bone"));Part.Kind=NameField(O,TEXT("kind"));
        if(Part.Bone.IsNone())return Fail(Where+TEXT(": missing bone"));
        if(!VectorField(O,TEXT("a"),3,Part.A,true,Error,Where)||!VectorField(O,TEXT("b"),3,Part.B,true,Error,Where)||
           !NumberField(O,TEXT("radius"),Part.Radius,true,Error,Where)||!NumberField(O,TEXT("damage"),Part.Damage,false,Error,Where))return Fail(Error);
        if(Part.Radius<=0.f)return Fail(Where+TEXT(": radius must be positive"));
        Part.bHasBoneLocal=VectorField(O,TEXT("a_bone"),3,Part.ABone,true,Error,Where)&&VectorField(O,TEXT("b_bone"),3,Part.BBone,true,Error,Where);
        Error.Reset();
        float Leg=-1.f;
        if(NumberField(O,TEXT("leg"),Leg,false,Error,Where)&&Leg>=0.f&&Leg<=3.f)Part.Leg=FMath::RoundToInt(Leg);
        Parts.Add(Part);
    }
    if(Parts.IsEmpty())return Fail(TEXT("boxes.json: no parts"));
    TSet<int32> Legs;
    for(const FBossPart& Part:Parts)if(Part.Leg!=INDEX_NONE&&!Legs.Contains(Part.Leg))Legs.Add(Part.Leg);
    if(Legs.Num()!=4)Warnings.Add(FString::Printf(TEXT("boxes.json maps %d of 4 leg indices; unmapped legs keep only the hard-coded regions"),Legs.Num()));

    // tempo.json and sounds.json are optional; a broken one is a warning, not a failure.
    FJsonObjectPtr TempoRoot;
    if(ReadJsonFile(FPaths::Combine(Directory,TEXT("tempo.json")),TempoRoot,Error))
    {
        for(const auto& Entry:TempoRoot->Values)
        {
            const FString Key(*Entry.Key);
            if(Key.StartsWith(TEXT("_")))continue;
            FBossMove* Move=Moves.Find(FName(*Key));
            const FJsonArray* Phases=nullptr;
            if(!Move){Warnings.Add(TEXT("tempo.json names unknown move ")+Key);continue;}
            if(!Entry.Value.IsValid()||!Entry.Value->TryGetArray(Phases)||!Phases){Warnings.Add(TEXT("tempo.json: not a phase list for ")+Key);continue;}
            for(const TSharedPtr<FJsonValue>& Phase:*Phases)
            {
                FVector P;
                if(!VectorValue(Phase,3,P)||P.Y<P.X||P.Z<=0.0){Warnings.Add(TEXT("tempo.json: bad phase in ")+Key);continue;}
                Move->Tempo.Add({static_cast<float>(P.X),static_cast<float>(P.Y),static_cast<float>(P.Z)});
            }
        }
    }
    else Warnings.Add(Error);
    FJsonObjectPtr SoundsRoot;
    if(ReadJsonFile(FPaths::Combine(Directory,TEXT("sounds.json")),SoundsRoot,Error))
    {
        SoundsRoot->TryGetStringField(TEXT("dir"),SoundDirectory);
        const FJsonArray* Steps=nullptr;
        if(SoundsRoot->TryGetArrayField(TEXT("steps"),Steps)&&Steps)
            for(const TSharedPtr<FJsonValue>& Step:*Steps){FString S;if(Step.IsValid()&&Step->TryGetString(S))StepSounds.Add(FName(*S));}
        const FJsonObjectPtr* SoundMoves=nullptr;
        if(SoundsRoot->TryGetObjectField(TEXT("moves"),SoundMoves)&&SoundMoves&&SoundMoves->IsValid())
            for(const auto& Entry:(*SoundMoves)->Values)
            {
                const FString Key(*Entry.Key);
                FBossMove* Move=Moves.Find(FName(*Key));
                const FJsonArray* Events=nullptr;
                if(!Move){Warnings.Add(TEXT("sounds.json names unknown move ")+Key);continue;}
                if(!Entry.Value.IsValid()||!Entry.Value->TryGetArray(Events)||!Events)continue;
                for(const TSharedPtr<FJsonValue>& Value:*Events)
                {
                    const FJsonObjectPtr* E=nullptr;
                    if(!Value.IsValid()||!Value->TryGetObject(E)||!E||!E->IsValid())continue;
                    FBossSoundEvent Event;Event.Sound=NameField(*E,TEXT("sound"));Event.At=NameField(*E,TEXT("at"));
                    if(Event.Sound.IsNone()||!NumberField(*E,TEXT("t"),Event.T,true,Error,Key)){Warnings.Add(TEXT("sounds.json: bad event in ")+Key);continue;}
                    NumberField(*E,TEXT("volume"),Event.Volume,false,Error,Key);
                    Move->Sounds.Add(Event);
                }
            }
    }
    else Warnings.Add(Error);

    bLoaded=true;
    for(const FString& Warning:Warnings)UE_LOG(LogVeyrMoveData,Warning,TEXT("VEYR_MOVEDATA_WARNING %s"),*Warning);
    UE_LOG(LogVeyrMoveData,Display,TEXT("VEYR_MOVEDATA_LOADED dir=%s moves=%d attacks=%d parts=%d game_scale=%.6f fps=%.1f"),
        *Directory,Moves.Num(),CountAttacks(),Parts.Num(),GameScale,Fps);
    return true;
}

void FBossMoveData::Describe(TArray<FString>& OutLines) const
{
    int32 Shocks=0,Contacts=0;
    for(const auto& Entry:Moves){Shocks+=Entry.Value.Shocks.Num();Contacts+=Entry.Value.Contacts.Num();}
    OutLines.Add(FString::Printf(TEXT("VEYR_MOVEDATA dir=%s loaded=%d moves=%d attacks=%d shocks=%d contacts=%d parts=%d game_scale=%.6f fps=%.1f errors=%d warnings=%d"),
        *Directory,bLoaded?1:0,Moves.Num(),CountAttacks(),Shocks,Contacts,Parts.Num(),GameScale,Fps,Errors.Num(),Warnings.Num()));
    for(const FString& E:Errors)OutLines.Add(TEXT("VEYR_MOVEDATA_ERROR ")+E);
    for(const FString& W:Warnings)OutLines.Add(TEXT("VEYR_MOVEDATA_WARNING ")+W);
    for(FName Name:MoveOrder)
    {
        const FBossMove& M=Moves[Name];
        FString Tempo;
        for(const FBossTempoPhase& P:M.Tempo)Tempo+=FString::Printf(TEXT("%s%.2f-%.2f x%.2f"),Tempo.IsEmpty()?TEXT(""):TEXT(", "),P.From,P.To,P.Rate);
        const FVector End=M.Track.IsEmpty()?FVector::ZeroVector:M.Track.Last();
        OutLines.Add(FString::Printf(TEXT("VEYR_MOVEDATA_MOVE %s duration=%.3f frames=%d loop=%d attacks=%d shocks=%d contacts=%d sounds=%d track_end=(%.1f, %.1f, yaw %.1f) tempo=[%s]"),
            *Name.ToString(),M.Duration,M.Frames,M.bLoop?1:0,M.Attacks.Num(),M.Shocks.Num(),M.Contacts.Num(),M.Sounds.Num(),End.X,End.Y,End.Z,*Tempo));
        for(int32 I=0;I<M.Attacks.Num();++I)
        {
            const FBossAttack& A=M.Attacks[I];
            OutLines.Add(FString::Printf(TEXT("VEYR_MOVEDATA_WINDOW %s[%d] part=%s t=%.3f-%.3f peak=%.3f s %.2f m/s at_peak=%s%s"),
                *Name.ToString(),I,*A.Part.ToString(),A.T0,A.T1,A.PeakT,A.PeakV,*Vec(A.AtPeak),M.bLoop?TEXT(" (loop: never hurts)"):TEXT("")));
        }
        for(const FBossShock& S:M.Shocks)
            OutLines.Add(FString::Printf(TEXT("VEYR_MOVEDATA_SHOCK %s t=%.3f bone=%s at=%s speed=%.2f radius=%.1f"),*Name.ToString(),S.T,*S.Bone.ToString(),*Vec(S.At),S.Speed,S.Radius));
    }
    for(const FBossPart& P:Parts)
        OutLines.Add(FString::Printf(TEXT("VEYR_MOVEDATA_PART %s bone=%s kind=%s leg=%d damage=%.2f radius=%.1f a=%s b=%s"),
            *P.Name.ToString(),*P.Bone.ToString(),*P.Kind.ToString(),P.Leg,P.Damage,P.Radius,*Vec(P.A),*Vec(P.B)));
}
