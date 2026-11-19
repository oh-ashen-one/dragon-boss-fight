#include "VeyrFeelTuning.h"
#include "VeyrMoveData.h"
#include "Dom/JsonObject.h"
#include "Dom/JsonValue.h"
#include "Misc/CommandLine.h"
#include "Misc/FileHelper.h"
#include "Misc/Parse.h"
#include "Misc/Paths.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"

namespace
{
    bool Legacy(){static const bool B=FParse::Param(FCommandLine::Get(),TEXT("VeyrLegacyFeel"));return B;}
    bool Off(const TCHAR* Name){return Legacy()||FParse::Param(FCommandLine::Get(),Name);}

    FVeyrFeelTuning::FEffect MakeEffect(int32 Cards,float Size,float Life,float Opacity,float Rise,float Spread,int32 Chips,float Chip,float ChipSpeed)
    {
        FVeyrFeelTuning::FEffect E;
        E.Cards=Cards;E.CardSizeCm=Size;E.CardLife=Life;E.CardOpacity=Opacity;E.CardRiseCmS=Rise;E.CardSpreadCmS=Spread;
        E.Chips=Chips;E.ChipSizeCm=Chip;E.ChipSpeedCmS=ChipSpeed;E.LifeSeconds=FMath::Max(1.f,Life+.5f);
        return E;
    }
    void Num(const TSharedPtr<FJsonObject>& O,const TCHAR* Key,float& Out)
    {double V;if(O.IsValid()&&O->TryGetNumberField(Key,V)&&FMath::IsFinite(V))Out=static_cast<float>(V);}
    void Int(const TSharedPtr<FJsonObject>& O,const TCHAR* Key,int32& Out)
    {double V;if(O.IsValid()&&O->TryGetNumberField(Key,V)&&FMath::IsFinite(V))Out=FMath::Clamp(FMath::RoundToInt(V),0,64);}
    TSharedPtr<FJsonObject> Obj(const TSharedPtr<FJsonObject>& O,const TCHAR* Key)
    {const TSharedPtr<FJsonObject>* R=nullptr;return O.IsValid()&&O->TryGetObjectField(Key,R)&&R?*R:nullptr;}
    void ReadPart(const TSharedPtr<FJsonObject>& O,FVeyrFeelTuning::FPart& P)
    {Num(O,TEXT("touch_cm"),P.TouchCm);Num(O,TEXT("lift_cm"),P.LiftCm);Num(O,TEXT("min_speed"),P.MinSpeedMps);P.LiftCm=FMath::Max(P.LiftCm,P.TouchCm+1.f);}
    void ReadShake(const TSharedPtr<FJsonObject>& O,FVeyrFeelTuning::FShake& S)
    {
        Num(O,TEXT("min_speed"),S.MinSpeed);Num(O,TEXT("full_speed"),S.FullSpeed);Num(O,TEXT("amp_min"),S.AmpMin);Num(O,TEXT("amp_max"),S.AmpMax);
        Num(O,TEXT("life_min"),S.LifeMin);Num(O,TEXT("life_max"),S.LifeMax);Num(O,TEXT("bounce_cm"),S.Bounce);
        S.FullSpeed=FMath::Max(S.FullSpeed,S.MinSpeed+.01f);
    }
    void ReadEffect(const TSharedPtr<FJsonObject>& O,FVeyrFeelTuning::FEffect& E)
    {
        if(!O.IsValid())return;
        O->TryGetStringField(TEXT("system"),E.System);
        Num(O,TEXT("scale"),E.Scale);Num(O,TEXT("life_s"),E.LifeSeconds);
        const TSharedPtr<FJsonObject> F=Obj(O,TEXT("fallback"));
        Int(F,TEXT("cards"),E.Cards);Num(F,TEXT("size_cm"),E.CardSizeCm);Num(F,TEXT("life_s"),E.CardLife);Num(F,TEXT("opacity"),E.CardOpacity);
        Num(F,TEXT("rise_cm_s"),E.CardRiseCmS);Num(F,TEXT("spread_cm_s"),E.CardSpreadCmS);Int(F,TEXT("chips"),E.Chips);
        Num(F,TEXT("chip_cm"),E.ChipSizeCm);Num(F,TEXT("chip_speed_cm_s"),E.ChipSpeedCmS);
    }
    template<int32 N> void ReadEffects(const TSharedPtr<FJsonObject>& Root,const TCHAR* Key,FVeyrFeelTuning::FEffect (&Out)[N])
    {
        const TArray<TSharedPtr<FJsonValue>>* List=nullptr;
        if(!Root->TryGetArrayField(Key,List)||!List)return;
        for(int32 I=0;I<N&&I<List->Num();++I)ReadEffect((*List)[I]->AsObject(),Out[I]);
    }
}

namespace VeyrFeelSwitches
{
    bool GroundContacts(){static const bool B=!Off(TEXT("VeyrNoGroundContacts"));return B;}
    bool WeightShake(){static const bool B=GroundContacts()&&!Off(TEXT("VeyrLegacyWeightShake"));return B;}
    bool ContactDust(){static const bool B=GroundContacts()&&!Off(TEXT("VeyrNoContactDust"));return B;}
    bool SpineFlinch(){static const bool B=!Off(TEXT("VeyrLegacyFlinch"));return B;}
    bool MeshFlash(){static const bool B=!Off(TEXT("VeyrNoMeshFlash"));return B;}
    bool HitBursts(){static const bool B=!Off(TEXT("VeyrLegacyHitBurst"));return B;}
    bool RibbonTrail(){static const bool B=!Off(TEXT("VeyrLegacyTrail"));return B;}
    bool SlowTail(){static const bool B=!Off(TEXT("VeyrNoSlowTail"));return B;}
    bool ZoomPunch(){static const bool B=!Off(TEXT("VeyrNoZoomPunch"));return B;}
    bool HurtKick(){static const bool B=!Off(TEXT("VeyrNoHurtKick"));return B;}
}

FVeyrFeelTuning::FVeyrFeelTuning()
{
    // Same numbers and asset paths as Data/dragon/ground_fx.json (packaged builds do not stage Data/, as with
    // moves.json). A path that is not in the cooked content falls back to the project's own cards and chips.
    Dust[0]=MakeEffect(2,55.f,.9f,.22f,30.f,55.f,0,3.f,220.f);      // small: walking footfall
    Dust[1]=MakeEffect(4,90.f,1.3f,.30f,40.f,90.f,4,3.5f,280.f);    // medium: a heavy step
    Dust[2]=MakeEffect(6,140.f,1.8f,.36f,45.f,140.f,10,4.f,360.f);  // large: stomp, tail slam
    Dust[3]=MakeEffect(8,230.f,2.6f,.40f,50.f,190.f,22,5.f,420.f);  // body fall: cloud and debris
    Dust[4]=MakeEffect(10,260.f,2.8f,.42f,55.f,230.f,26,5.f,480.f); // landing
    Hit[0]=MakeEffect(10,9.f,.20f,.85f,0.f,520.f,0,0.f,0.f);        // light blow: sparks
    Hit[1]=MakeEffect(16,12.f,.26f,.90f,0.f,640.f,4,2.5f,300.f);    // heavy blow
    Hit[2]=MakeEffect(24,15.f,.32f,.95f,0.f,780.f,8,3.f,380.f);     // heavy two-hand / exposed head
    auto System=[](FEffect& E,const TCHAR* Path,float Scale,float Life){E.System=Path;E.Scale=Scale;E.LifeSeconds=Life;};
    System(Dust[0],TEXT("/Game/ParagonRampage/FX/Particles/Abilities/Lunge/FX/P_Rampage_Jumpdust"),.35f,.9f);
    System(Dust[1],TEXT("/Game/ParagonRampage/FX/Particles/Abilities/Ultimate/FX/P_Rampage_Footstep_Enraged"),.6f,1.3f);
    System(Dust[2],TEXT("/Game/ParagonTerra/FX/Particles/Terra/Abilities/DoubleSweep/FX/P_Terra_DoubleSweep_DustImpact"),.8f,1.8f);
    System(Dust[3],TEXT("/Game/ParagonGreystone/FX/Particles/Greystone/Abilities/LeapAOE/FX/P_Greystone_LeapAOE_GroundSmash"),1.f,2.6f);
    System(Dust[4],TEXT("/Game/ParagonGreystone/FX/Particles/Greystone/Abilities/LeapAOE/FX/P_Greystone_LeapAOE_GroundSmash"),1.15f,2.8f);
    System(Hit[0],TEXT("/Game/ParagonGreystone/FX/Particles/Greystone/Abilities/Primary/FX/P_Greystone_Primary_Sparks"),.6f,.4f);
    System(Hit[1],TEXT("/Game/ParagonGreystone/FX/Particles/Greystone/Abilities/Primary/FX/P_Greystone_Primary_Impact"),.8f,.6f);
    System(Hit[2],TEXT("/Game/ParagonTerra/FX/Particles/Terra/Abilities/Balance/FX/P_Terra_Boom_Impacted"),.7f,.8f);
    DebrisMesh=TEXT("/Game/ParagonKwang/FX/Meshes/Debris/Rock_A");
}

bool FVeyrFeelTuning::LoadFromFile(const FString& File)
{
    SourceFile=File;
    FString Text;
    if(!FFileHelper::LoadFileToString(Text,*File)){Diagnostic=TEXT("ground_fx.json not found; compiled defaults");return false;}
    TSharedPtr<FJsonObject> Root;
    if(!FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text),Root)||!Root.IsValid())
    {Diagnostic=TEXT("ground_fx.json does not parse; compiled defaults");return false;}
    if(const TSharedPtr<FJsonObject> C=Obj(Root,TEXT("contacts")))
    {
        ReadPart(Obj(C,TEXT("foot")),Foot);ReadPart(Obj(C,TEXT("head")),Head);ReadPart(Obj(C,TEXT("neck")),Neck);
        ReadPart(Obj(C,TEXT("body")),Body);ReadPart(Obj(C,TEXT("tail")),Tail);ReadPart(Obj(C,TEXT("wing")),Wing);
        const TArray<TSharedPtr<FJsonValue>>* Tiers=nullptr;
        if(C->TryGetArrayField(TEXT("dust_tier_max_speed"),Tiers)&&Tiers&&Tiers->Num()>=2)
        {DustTierMaxSpeed[0]=(*Tiers)[0]->AsNumber();DustTierMaxSpeed[1]=FMath::Max(DustTierMaxSpeed[0],static_cast<float>((*Tiers)[1]->AsNumber()));}
        Num(C,TEXT("stomp_min_speed"),StompMinSpeed);Num(C,TEXT("body_cloud_min_speed"),BodyCloudMinSpeed);Num(C,TEXT("landing_window_s"),LandingWindowSeconds);
        Num(C,TEXT("peak_time_constant_s"),PeakTimeConstant);Num(C,TEXT("min_event_interval_s"),MinEventInterval);
    }
    if(const TSharedPtr<FJsonObject> S=Obj(Root,TEXT("shake")))
    {
        Num(S,TEXT("max_distance_cm"),ShakeMaxDistanceCm);Num(S,TEXT("size_gain"),ShakeSizeGain);Num(S,TEXT("max_degrees"),ShakeMaxDegrees);
        const TCHAR* Names[]={TEXT("footfall"),TEXT("stomp"),TEXT("body_fall"),TEXT("landing")};
        for(int32 I=0;I<4;++I)ReadShake(Obj(S,Names[I]),Shake[I]);
    }
    if(const TSharedPtr<FJsonObject> F=Obj(Root,TEXT("flinch")))
    {
        Num(F,TEXT("rock_min_deg"),FlinchRockMin);Num(F,TEXT("rock_max_deg"),FlinchRockMax);
        Num(F,TEXT("twist_min_deg"),FlinchTwistMin);Num(F,TEXT("twist_max_deg"),FlinchTwistMax);Num(F,TEXT("cap_deg"),FlinchCapDegrees);
        Num(F,TEXT("head_part"),FlinchHeadPart);Num(F,TEXT("neck_part"),FlinchNeckPart);Num(F,TEXT("leg_part"),FlinchLegPart);
        Num(F,TEXT("body_share"),FlinchBodyShare);Num(F,TEXT("tail_share"),FlinchTailShare);
        Num(F,TEXT("snap_s"),FlinchSnapSeconds);Num(F,TEXT("hz"),FlinchHz);Num(F,TEXT("damping"),FlinchDamping);Num(F,TEXT("life_s"),FlinchLifeSeconds);
        Num(F,TEXT("flash_peak"),FlashPeak);Num(F,TEXT("flash_peak_gain"),FlashPeakGain);Num(F,TEXT("flash_radius_cm"),FlashRadiusCm);
        Num(F,TEXT("flash_radius_gain_cm"),FlashRadiusGainCm);Num(F,TEXT("flash_fade_s"),FlashFade);Num(F,TEXT("flash_life_s"),FlashLife);
        FlinchDamping=FMath::Clamp(FlinchDamping,.05f,.95f);FlinchHz=FMath::Clamp(FlinchHz,.5f,8.f);
    }
    if(const TSharedPtr<FJsonObject> K=Obj(Root,TEXT("knight")))
    {
        Num(K,TEXT("trail_life_s"),TrailLife);Num(K,TEXT("trail_base_fraction"),TrailBaseFraction);
        Num(K,TEXT("slow_tail_s"),SlowTailSeconds);Num(K,TEXT("slow_tail_from"),SlowTailFrom);
        Num(K,TEXT("punch_heavy"),PunchHeavy);Num(K,TEXT("punch_light"),PunchLight);Num(K,TEXT("punch_s"),PunchSeconds);
        Num(K,TEXT("kick_min_deg"),KickMin);Num(K,TEXT("kick_gain_deg"),KickGain);Num(K,TEXT("kick_s"),KickSeconds);
        Num(K,TEXT("hurt_min"),HurtMin);Num(K,TEXT("hurt_gain"),HurtGain);
        TrailLife=FMath::Clamp(TrailLife,.03f,.4f);SlowTailFrom=FMath::Clamp(SlowTailFrom,.1f,1.f);
    }
    ReadEffects(Root,TEXT("dust"),Dust);
    ReadEffects(Root,TEXT("hit"),Hit);
    Root->TryGetStringField(TEXT("debris_mesh"),DebrisMesh);
    if(const TSharedPtr<FJsonObject> L=Obj(Root,TEXT("fallback_look")))
    {
        auto Colour=[&L](const TCHAR* Key,FLinearColor& Out)
        {
            const TArray<TSharedPtr<FJsonValue>>* V=nullptr;
            if(L->TryGetArrayField(Key,V)&&V&&V->Num()>=3)Out=FLinearColor((*V)[0]->AsNumber(),(*V)[1]->AsNumber(),(*V)[2]->AsNumber());
        };
        Colour(TEXT("dust_tint"),DustTint);Colour(TEXT("chip_tint"),ChipTint);Colour(TEXT("spark_tint"),SparkTint);
        Num(L,TEXT("dust_brightness"),DustBrightness);Num(L,TEXT("spark_brightness"),SparkBrightness);
    }
    bLoadedFromFile=true;Diagnostic=TEXT("loaded ")+File;
    return true;
}

float FVeyrFeelTuning::ClassStrength(EVeyrFeelClass Class,float ScaledSpeed) const
{
    const FShake& S=Shake[static_cast<int32>(Class)];
    return Smooth01((ScaledSpeed-S.MinSpeed)/FMath::Max(.01f,S.FullSpeed-S.MinSpeed));
}

float FVeyrFeelTuning::ShakeDegrees(EVeyrFeelClass Class,float ScaledSpeed,float DistanceCm,float BodyScale,float& OutLife,float& OutBounce) const
{
    const FShake& S=Shake[static_cast<int32>(Class)];
    OutLife=S.LifeMin;OutBounce=0.f;
    if(ScaledSpeed<S.MinSpeed)return 0.f;
    const float K=ClassStrength(Class,ScaledSpeed);
    const float Near=1.f-Smooth01(DistanceCm/FMath::Max(1.f,ShakeMaxDistanceCm*BodyScale));
    if(Near<=.02f)return 0.f;
    const float Size=1.f+ShakeSizeGain*FMath::Max(0.f,BodyScale-1.f);
    OutLife=FMath::Lerp(S.LifeMin,S.LifeMax,K);OutBounce=S.Bounce*K*Near*Size;
    return FMath::Min(ShakeMaxDegrees,FMath::Lerp(S.AmpMin,S.AmpMax,K)*Near*Size);
}

const FVeyrFeelTuning& VeyrFeelTuning()
{
    static FVeyrFeelTuning Tuning;
    static bool bTried=false;
    if(!bTried)
    {
        bTried=true;
        const FString File=FPaths::Combine(FBossMoveData::ResolveDirectory(),TEXT("ground_fx.json"));
        Tuning.LoadFromFile(File);
        UE_LOG(LogTemp,Display,TEXT("VEYR_FEEL_TUNING %s"),*Tuning.Diagnostic);
    }
    return Tuning;
}
