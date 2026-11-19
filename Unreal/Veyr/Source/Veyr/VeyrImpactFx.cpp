#include "VeyrImpactFx.h"
#include "VeyrDragon.h"
#include "VeyrLook.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "Components/SceneComponent.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "GameFramework/PlayerController.h"
#include "Kismet/GameplayStatics.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Materials/MaterialInterface.h"
#include "NiagaraComponent.h"
#include "NiagaraSystem.h"
#include "Particles/ParticleSystem.h"
#include "Particles/ParticleSystemComponent.h"
#include "UObject/ConstructorHelpers.h"

namespace
{
    FString ObjectPath(const FString& Path)
    {
        if(Path.IsEmpty()||Path.Contains(TEXT(".")))return Path;
        return Path+TEXT(".")+FPaths::GetBaseFilename(Path);
    }
    // Pool sizes per tier: dust S/M/L, body cloud, landing; hit S/M/L.
    constexpr int32 PoolSizes[8]={6,5,4,3,3,4,3,2};
}

AVeyrImpactFx::AVeyrImpactFx()
{
    PrimaryActorTick.bCanEverTick=true;PrimaryActorTick.TickGroup=TG_PostUpdateWork;
    SetRootComponent(CreateDefaultSubobject<USceneComponent>(TEXT("ImpactFxRoot")));
    DustCards=CreateDefaultSubobject<UInstancedStaticMeshComponent>(TEXT("ContactDustCards"));
    DebrisChips=CreateDefaultSubobject<UInstancedStaticMeshComponent>(TEXT("ContactDebrisChips"));
    SparkStreaks=CreateDefaultSubobject<UInstancedStaticMeshComponent>(TEXT("HitSparkStreaks"));
    for(UInstancedStaticMeshComponent* Ism:{DustCards.Get(),DebrisChips.Get(),SparkStreaks.Get()})
    {
        Ism->SetupAttachment(GetRootComponent());Ism->SetCollisionEnabled(ECollisionEnabled::NoCollision);
        Ism->SetGenerateOverlapEvents(false);Ism->SetCanEverAffectNavigation(false);Ism->SetVisibility(false);
        Ism->SetCullDistances(0,12000);
    }
    DustCards->SetCastShadow(false);SparkStreaks->SetCastShadow(false);DebrisChips->SetCastShadow(true);
    static ConstructorHelpers::FObjectFinderOptional<UStaticMesh> PlaneMesh(TEXT("/Engine/BasicShapes/Plane.Plane"),LOAD_Quiet|LOAD_NoWarn);
    static ConstructorHelpers::FObjectFinderOptional<UStaticMesh> Cube(TEXT("/Engine/BasicShapes/Cube.Cube"),LOAD_Quiet|LOAD_NoWarn);
    static ConstructorHelpers::FObjectFinderOptional<UMaterialInterface> Smoke(TEXT("/Game/Veyr/FX/v3/M_VeyrBreathSmoke.M_VeyrBreathSmoke"),LOAD_Quiet|LOAD_NoWarn);
    static ConstructorHelpers::FObjectFinderOptional<UMaterialInterface> Ember(TEXT("/Game/Veyr/FX/v3/M_VeyrBreathEmber.M_VeyrBreathEmber"),LOAD_Quiet|LOAD_NoWarn);
    static ConstructorHelpers::FObjectFinderOptional<UMaterialInterface> Basic(TEXT("/Engine/BasicShapes/BasicShapeMaterial.BasicShapeMaterial"),LOAD_Quiet|LOAD_NoWarn);
    Plane=PlaneMesh.Get();ChipMesh=Cube.Get();SmokeMaterial=Smoke.Get();EmberMaterial=Ember.Get();ChipMaterial=Basic.Get();
}

float AVeyrImpactFx::Rand()
{
    // Deterministic per run (same replay, same dust); no global RNG is touched.
    Seed=Seed*1664525u+1013904223u;
    return static_cast<float>((Seed>>8)&0xffffff)/16777216.f;
}

void AVeyrImpactFx::ConfigureIsm(UInstancedStaticMeshComponent* Ism,UStaticMesh* Mesh,UMaterialInterface* Material,int32 Count,int32 CustomFloats)
{
    Ism->ClearInstances();Ism->SetStaticMesh(Mesh);if(Material)Ism->SetMaterial(0,Material);
    Ism->SetNumCustomDataFloats(CustomFloats);
    for(int32 I=0;I<Count;++I)
    {
        Ism->AddInstance(FTransform(FQuat::Identity,FVector::ZeroVector,FVector::ZeroVector));
        for(int32 F=0;F<CustomFloats;++F)Ism->SetCustomDataValue(I,F,0.f,false);
    }
}

void AVeyrImpactFx::BeginPlay()
{
    Super::BeginPlay();
    const FVeyrFeelTuning& T=VeyrFeelTuning();
    // The project's own cards: always ready, so a missing asset never means a missing effect.
    if(Plane&&SmokeMaterial)
    {
        UMaterialInstanceDynamic* Dust=UMaterialInstanceDynamic::Create(SmokeMaterial,this);
        // The cards are unlit, so in the relit court they do not pick up the light around them: under the
        // night exposure (2-6x build 16's) a half-locked follow left them a bright cool-white cloud. Relit:
        // darkened toward the court's warm firelit stone and held close to build 16's on-screen brightness.
        // -VeyrTune=dustlevel=,dustlock= move both; -VeyrLegacyRender keeps the original tint.
        FLinearColor DustTint=T.DustTint;float DustLock=-1.f;
        if(!VeyrLook::IsLegacy())
        {
            DustTint=DustTint*FLinearColor(.78f,.64f,.50f)*VeyrLook::Tune(TEXT("dustlevel"),.75f);DustTint.A=T.DustTint.A;
            DustLock=VeyrLook::Tune(TEXT("dustlock"),.9f);
        }
        Dust->SetVectorParameterValue(TEXT("Tint"),DustTint);Dust->SetScalarParameterValue(TEXT("Brightness"),T.DustBrightness);
        ConfigureIsm(DustCards,Plane,Dust,CardCount,4);
        VeyrLook::FollowExposureAuto(Dust,DustLock);
    }
    if(Plane&&EmberMaterial)
    {
        UMaterialInstanceDynamic* Spark=UMaterialInstanceDynamic::Create(EmberMaterial,this);
        Spark->SetVectorParameterValue(TEXT("Tint"),T.SparkTint);Spark->SetScalarParameterValue(TEXT("Brightness"),T.SparkBrightness);
        ConfigureIsm(SparkStreaks,Plane,Spark,SparkCount,4);
        VeyrLook::FollowExposureAuto(Spark);
    }
    if(!T.DebrisMesh.IsEmpty())
        if(UStaticMesh* Rock=LoadObject<UStaticMesh>(nullptr,*ObjectPath(T.DebrisMesh),nullptr,LOAD_Quiet|LOAD_NoWarn))ChipMesh=Rock;
    if(ChipMesh)
    {
        UMaterialInterface* Chip=ChipMaterial;
        if(ChipMaterial&&ChipMesh->GetPathName().StartsWith(TEXT("/Engine/")))
        {
            UMaterialInstanceDynamic* Basalt=UMaterialInstanceDynamic::Create(ChipMaterial,this);
            Basalt->SetVectorParameterValue(TEXT("Color"),T.ChipTint);Chip=Basalt;
        }
        else Chip=nullptr; // a sourced debris mesh keeps its own material
        ConfigureIsm(DebrisChips,ChipMesh,Chip,ChipCount,0);
    }
    // Asset pools, created once. Missing or unloadable paths fall back to the cards per tier.
    const FVeyrFeelTuning::FEffect* Effects[PoolCount]={&T.Dust[0],&T.Dust[1],&T.Dust[2],&T.Dust[3],&T.Dust[4],&T.Hit[0],&T.Hit[1],&T.Hit[2]};
    for(int32 P=0;P<PoolCount;++P)
    {
        Pools[P].First=Components.Num();Pools[P].Num=0;Pools[P].bAsset=false;
        const FString Path=ObjectPath(Effects[P]->System);
        if(Path.IsEmpty())continue;
        UObject* Loaded=StaticLoadObject(UObject::StaticClass(),nullptr,*Path,nullptr,LOAD_Quiet|LOAD_NoWarn);
        UFXSystemAsset* Asset=Cast<UFXSystemAsset>(Loaded);
        if(!Asset){MissingSystems.Add(Path);continue;}
        Assets.Add(Asset);LoadedSystems.Add(Path);
        for(int32 I=0;I<PoolSizes[P];++I)
        {
            UFXSystemComponent* Component=nullptr;
            if(UParticleSystem* Cascade=Cast<UParticleSystem>(Asset))
            {
                UParticleSystemComponent* C=NewObject<UParticleSystemComponent>(this);
                C->bAutoActivate=false;C->bAutoDestroy=false;C->SetTemplate(Cascade);Component=C;
            }
            else if(UNiagaraSystem* Niagara=Cast<UNiagaraSystem>(Asset))
            {
                UNiagaraComponent* C=NewObject<UNiagaraComponent>(this);
                C->SetAutoActivate(false);C->SetAutoDestroy(false);C->SetAsset(Niagara);Component=C;
            }
            if(!Component)break;
            Component->SetupAttachment(GetRootComponent());Component->SetUsingAbsoluteLocation(true);
            Component->SetUsingAbsoluteRotation(true);Component->SetUsingAbsoluteScale(true);
            Component->RegisterComponent();
            // Unlit sparks and flares were tuned under manual exposure; lit smoke follows the court's light.
            VeyrLook::FollowExposureOnComponent(Component,this,ExposureMids);
            Components.Add(Component);ComponentAge.Add(100.f);ComponentLife.Add(0.f);++Pools[P].Num;
        }
        Pools[P].bAsset=Pools[P].Num>0;
    }
    for(const TPair<UMaterialInterface*,UMaterialInstanceDynamic*>& Pair:ExposureMids)if(Pair.Value)ExposureMidRefs.Add(Pair.Value);
    // Small moving shadow casters redraw their VSM pages every frame; dropped with the other shadow steps.
    if(VeyrLook::RenderTier()>=2)DebrisChips->SetCastShadow(false);
    Diagnostic=FString::Printf(TEXT("%d effect systems loaded, %d missing (fallback cards); tuning: %s"),
        LoadedSystems.Num(),MissingSystems.Num(),*T.Diagnostic);
    UE_LOG(LogTemp,Display,TEXT("VEYR_IMPACT_FX %s"),*Diagnostic);
    for(const FString& M:MissingSystems)UE_LOG(LogTemp,Warning,TEXT("VEYR_IMPACT_FX_MISSING %s"),*M);
}

void AVeyrImpactFx::EndPlay(const EEndPlayReason::Type Reason)
{
    if(AVeyrDragon* D=BoundDragon.Get())D->OnGroundContact.Remove(ContactHandle);
    Super::EndPlay(Reason);
}

void AVeyrImpactFx::Bind(AVeyrDragon* Dragon)
{
    if(BoundDragon.Get()==Dragon)return;
    if(AVeyrDragon* Old=BoundDragon.Get())Old->OnGroundContact.Remove(ContactHandle);
    BoundDragon=Dragon;ContactHandle.Reset();
    if(Dragon)ContactHandle=Dragon->OnGroundContact.AddUObject(this,&AVeyrImpactFx::OnContact);
}

bool AVeyrImpactFx::SpawnAsset(int32 P,const FVector& At,const FRotator& Facing,float Scale,float Life)
{
    FPool& Pool=Pools[P];
    if(!Pool.bAsset||Pool.Num<=0)return false;
    const int32 Index=Pool.First+Pool.Next;Pool.Next=(Pool.Next+1)%Pool.Num;
    UFXSystemComponent* C=Components[Index];
    if(!IsValid(C))return false;
    C->Deactivate();
    C->SetWorldLocationAndRotation(At,Facing);C->SetWorldScale3D(FVector(Scale));
    C->Activate(true);
    ComponentAge[Index]=0.f;ComponentLife[Index]=Life;
    return true;
}

void AVeyrImpactFx::OnContact(AVeyrDragon* Dragon,const FVeyrGroundContact& C)
{
    if(!VeyrFeelSwitches::ContactDust()||!Dragon)return;
    const FVeyrFeelTuning& T=VeyrFeelTuning();
    const int32 Tier=FMath::Clamp(C.DustTier,0,4);
    const float Scale=Dragon->BodyScale;
    // Four feet landing in the same instant make one cloud, not four stacked ones.
    if(Tier>=3)
    {
        if(Clock-LastCloudClock<.25f&&FVector::Dist2D(C.World,LastCloudAt)<350.f*Scale){++SkippedMerged;return;}
        LastCloudClock=Clock;LastCloudAt=C.World;
    }
    const FVeyrFeelTuning::FEffect& E=T.Dust[Tier];
    const FRotator Facing(0.f,Dragon->GetActorRotation().Yaw,0.f);
    const float Strength=FMath::Lerp(.75f,1.25f,C.Strength);
    // Blind review 1: "dust is an opaque grey slab that hides the boss". Relit: smaller, shorter-lived clouds
    // and thinner cards (-VeyrTune=dustscale=,dustlife=,dustalpha=).
    static const float DustScale=VeyrLook::IsLegacy()?1.f:VeyrLook::Tune(TEXT("dustscale"),.38f);
    static const float DustLife=VeyrLook::IsLegacy()?1.f:VeyrLook::Tune(TEXT("dustlife"),.7f);
    if(SpawnAsset(Tier,C.World,Facing,E.Scale*Scale*Strength*DustScale,E.LifeSeconds*DustLife))
    {++DustAsset[Tier];if(E.bCardsWithAsset)SpawnDustCards(E,C.World,Scale,Strength,Tier>=3);}
    else{SpawnDustCards(E,C.World,Scale,Strength,Tier>=3);++DustFallback[Tier];}
    // Debris is ours in both cases (the asset tiers may have none).
    if(E.Chips>0)ThrowChips(E,C.World,FVector::UpVector,Scale*Strength,static_cast<float>(C.World.Z)-1.f);
}

void AVeyrImpactFx::HitBurst(const FVector& At,const FVector& Out,int32 Tier,float BodyScale)
{
    if(!VeyrFeelSwitches::HitBursts())return;
    Tier=FMath::Clamp(Tier,0,2);
    const FVector Normal=Out.IsNearlyZero()?FVector::UpVector:Out.GetSafeNormal();
    if(VeyrFeelSwitches::ContactBurst())
    {
        // B2: every blow, legs included, throws a burst that lasts about half a second at the blade's contact point:
        // the spark asset larger, spark cards that live 0.45 s, debris specks, and a short pale burst (the reference's
        // white flash-and-dust), all sized by the blow's tier and the dragon's size.
        FVeyrFeelTuning::FEffect E=VeyrFeelTuning().Hit[Tier];
        const float Body=FMath::Sqrt(FMath::Max(.25f,BodyScale));
        if(SpawnAsset(5+Tier,At,Normal.Rotation(),E.Scale*1.6f*Body,E.LifeSeconds))++HitAsset[Tier];else ++HitFallback[Tier];
        // Round 3: the 1.7x, 0.45 s, opaque spark streaks lay on the floor as a white slab for half a second: streaks keep
        // their data size and opacity and live at most 0.25 s.
        E.Cards+=4;E.CardLife=FMath::Min(E.CardLife,.25f);
        ThrowSparks(E,At,Normal,Body);
        E.Chips=FMath::Max(E.Chips,6+4*Tier);E.ChipSizeCm=FMath::Max(E.ChipSizeCm,3.f+Tier);E.ChipSpeedCmS=FMath::Max(E.ChipSpeedCmS,360.f);
        ThrowChips(E,At,Normal,Body,0.f);
        // The pale dust-card puff (90+40 tier cm, opacity .9) drew a flat white slab on heavy hits under the new exposure,
        // held through the stop (films 20261119T205054Z and T224519Z): only with -VeyrContactPuff.
        static const bool bPuff=FParse::Param(FCommandLine::Get(),TEXT("VeyrContactPuff"));
        if(bPuff)
        {
            FVeyrFeelTuning::FEffect Burst=VeyrFeelTuning().Dust[0];
            Burst.Cards=5+2*Tier;Burst.CardSizeCm=90.f+40.f*Tier;Burst.CardLife=.5f;Burst.CardOpacity=.9f;
            Burst.CardRiseCmS=40.f;Burst.CardSpreadCmS=120.f+40.f*Tier;
            SpawnDustCards(Burst,At+Normal*12.f*Body,Body,1.f,false);++HitSmoke;
        }
        ++ContactBursts;
        return;
    }
    const FVeyrFeelTuning::FEffect& E=VeyrFeelTuning().Hit[Tier];
    if(SpawnAsset(5+Tier,At,Normal.Rotation(),E.Scale*FMath::Sqrt(FMath::Max(.25f,BodyScale)),E.LifeSeconds))
    {++HitAsset[Tier];if(E.bCardsWithAsset)ThrowSparks(E,At,Normal,1.f);}
    else{ThrowSparks(E,At,Normal,1.f);++HitFallback[Tier];}
    if(E.Chips>0)ThrowChips(E,At,Normal,1.f,0.f);
    // The reference's hits throw a pale puff that hangs for a second, not only sparks.
    if(E.SmokeTier>=0&&E.SmokeTier<5)
    {
        const float Puff=E.SmokeScale*FMath::Sqrt(FMath::Max(.25f,BodyScale));
        SpawnDustCards(VeyrFeelTuning().Dust[E.SmokeTier],At+Normal*20.f*Puff,Puff,1.f,false);++HitSmoke;
    }
}

void AVeyrImpactFx::SpawnDustCards(const FVeyrFeelTuning::FEffect& E,const FVector& At,float Scale,float Strength,bool bRing)
{
    if(!DustCards->GetStaticMesh())return;
    for(int32 I=0;I<E.Cards;++I)
    {
        FCard& C=Cards[NextCard];NextCard=(NextCard+1)%CardCount;
        const float A=(I+Rand()*.6f)*2.f*PI/FMath::Max(1,E.Cards);
        const FVector Dir(FMath::Cos(A),FMath::Sin(A),0.f);
        const float Spread=E.CardSpreadCmS*Scale*Strength*(bRing?.8f+.4f*Rand():.35f+.65f*Rand());
        C.P=At+Dir*(E.CardSizeCm*.15f*Scale)+FVector(0,0,E.CardSizeCm*.25f*Scale);
        C.V=Dir*Spread+FVector(0,0,E.CardRiseCmS*Scale*(.6f+.8f*Rand()));
        static const float CardThin=VeyrLook::IsLegacy()?1.f:VeyrLook::Tune(TEXT("dustalpha"),.3f);
        static const float CardSize=VeyrLook::IsLegacy()?1.f:VeyrLook::Tune(TEXT("dustsize"),.8f);
        static const float CardLife=VeyrLook::IsLegacy()?1.f:VeyrLook::Tune(TEXT("dustlife"),.7f);
        C.Size=E.CardSizeCm*Scale*Strength*CardSize*(.7f+.5f*Rand());C.Grow=C.Size*(bRing?1.6f:1.1f);
        C.Life=E.CardLife*CardLife*(.8f+.4f*Rand());C.Age=0.f;C.Opacity=E.CardOpacity*CardThin*FMath::Clamp(Strength,.6f,1.2f);C.Seed=Rand();C.bLive=true;
        ++CardsSpawned;
    }
    bCardsDirty=true;
}

void AVeyrImpactFx::ThrowChips(const FVeyrFeelTuning::FEffect& E,const FVector& At,const FVector& Out,float Scale,float Floor)
{
    if(!DebrisChips->GetStaticMesh())return;
    for(int32 I=0;I<E.Chips;++I)
    {
        FChip& C=Chips[NextChip];NextChip=(NextChip+1)%ChipCount;
        const float A=Rand()*2.f*PI;
        const FVector Side(FMath::Cos(A),FMath::Sin(A),0.f);
        const FVector Dir=(Out*(.6f+.6f*Rand())+Side*(.5f+.7f*Rand())+FVector(0,0,.6f)).GetSafeNormal();
        C.P=At+FVector(0,0,4.f);C.V=Dir*E.ChipSpeedCmS*FMath::Sqrt(Scale)*(.55f+.7f*Rand());
        C.R=FRotator(Rand()*360.f,Rand()*360.f,Rand()*360.f);C.Spin=FRotator(Rand()*900.f-450.f,Rand()*900.f-450.f,0.f);
        C.Size=E.ChipSizeCm*Scale*(.5f+Rand());C.Life=1.6f+Rand()*.8f;C.Age=0.f;C.Floor=Floor;C.bLive=true;
        ++ChipsThrown;
    }
    bChipsDirty=true;
}

void AVeyrImpactFx::ThrowSparks(const FVeyrFeelTuning::FEffect& E,const FVector& At,const FVector& Out,float Scale)
{
    if(!SparkStreaks->GetStaticMesh())return;
    for(int32 I=0;I<E.Cards;++I)
    {
        FSpark& S=Sparks[NextSpark];NextSpark=(NextSpark+1)%SparkCount;
        const float A=I*2.399963f+Rand();
        const FVector Side=FVector::CrossProduct(Out,FVector::UpVector).GetSafeNormal();
        const FVector Up=FVector::CrossProduct(Side,Out).GetSafeNormal();
        const FVector Dir=(Out+(Side*FMath::Cos(A)+Up*FMath::Sin(A))*(.6f+.6f*Rand())).GetSafeNormal();
        S.P=At+Out*4.f;S.V=Dir*E.CardSpreadCmS*Scale*(.5f+.8f*Rand());
        S.Size=E.CardSizeCm*Scale*(.6f+.8f*Rand());S.Life=E.CardLife*(.7f+.6f*Rand());S.Age=0.f;S.Opacity=E.CardOpacity;S.bLive=true;
    }
    bSparksDirty=true;
}

void AVeyrImpactFx::UpdateCards(float Dt,const FVector& Camera)
{
    if(!bCardsDirty)return;
    bool Any=false;int32 Live=0;
    for(int32 I=0;I<CardCount;++I)
    {
        FCard& C=Cards[I];
        FTransform X(FQuat::Identity,FVector::ZeroVector,FVector::ZeroVector);float Alpha=0.f,Age=0.f;
        if(C.bLive)
        {
            C.Age+=Dt;
            if(C.Age>=C.Life)C.bLive=false;
            else
            {
                Any=true;++Live;
                // Ground dust: fast out, slows hard (drag), rises a little and grows.
                C.V*=FMath::Exp(-Dt*3.2f);C.P+=C.V*Dt;
                const float T=C.Age/C.Life;Age=T;
                const float Size=C.Size+C.Grow*FMath::Sqrt(T);
                const FVector Facing=(Camera-C.P).GetSafeNormal();
                X=FTransform(FRotationMatrix::MakeFromZ(Facing.IsNearlyZero()?FVector::UpVector:Facing).ToQuat(),C.P,FVector(Size/100.f,Size/100.f,1.f));
                const float Near=FMath::Clamp((static_cast<float>(FVector::Distance(Camera,C.P))-60.f)/160.f,0.f,1.f);
                Alpha=C.Opacity*FMath::Clamp(T/.08f,0.f,1.f)*FMath::Square(1.f-T)*Near;
            }
        }
        DustCards->UpdateInstanceTransform(I,X,true,false,true);
        DustCards->SetCustomDataValue(I,0,Alpha,false);DustCards->SetCustomDataValue(I,1,C.Seed,false);
        DustCards->SetCustomDataValue(I,2,Age,false);DustCards->SetCustomDataValue(I,3,.35f,false);
    }
    MaxLiveCards=FMath::Max(MaxLiveCards,Live);
    DustCards->SetVisibility(Any);DustCards->MarkRenderStateDirty();bCardsDirty=Any;
}

void AVeyrImpactFx::UpdateChips(float Dt)
{
    if(!bChipsDirty)return;
    bool Any=false;
    for(int32 I=0;I<ChipCount;++I)
    {
        FChip& C=Chips[I];
        FTransform X(FQuat::Identity,FVector::ZeroVector,FVector::ZeroVector);
        if(C.bLive)
        {
            C.Age+=Dt;
            if(C.Age>=C.Life)C.bLive=false;
            else
            {
                Any=true;
                C.V.Z-=980.f*Dt;C.P+=C.V*Dt;C.R+=C.Spin*Dt;
                if(C.P.Z<C.Floor+C.Size*.5f){C.P.Z=C.Floor+C.Size*.5f;C.V*=FVector(.35f,.35f,-.25f);C.Spin*=.4f;}
                const float Shrink=FMath::Clamp((C.Life-C.Age)/.35f,0.f,1.f);
                X=FTransform(C.R,C.P,FVector(C.Size*Shrink/100.f));
            }
        }
        DebrisChips->UpdateInstanceTransform(I,X,true,false,true);
    }
    DebrisChips->SetVisibility(Any);DebrisChips->MarkRenderStateDirty();bChipsDirty=Any;
}

void AVeyrImpactFx::UpdateSparks(float Dt,const FVector& Camera)
{
    if(!bSparksDirty)return;
    bool Any=false;
    for(int32 I=0;I<SparkCount;++I)
    {
        FSpark& S=Sparks[I];
        FTransform X(FQuat::Identity,FVector::ZeroVector,FVector::ZeroVector);float Alpha=0.f,Age=0.f;
        if(S.bLive)
        {
            S.Age+=Dt;
            if(S.Age>=S.Life)S.bLive=false;
            else
            {
                Any=true;S.V.Z-=650.f*Dt;S.V*=FMath::Exp(-Dt*2.f);S.P+=S.V*Dt;
                const float T=S.Age/S.Life;Age=T;
                FVector Facing=(Camera-S.P).GetSafeNormal();if(Facing.IsNearlyZero())Facing=FVector::UpVector;
                const FVector Axis=S.V-Facing*FVector::DotProduct(S.V,Facing);
                const float Len=FMath::Clamp(static_cast<float>(Axis.Size())*.035f,S.Size*.5f,S.Size*3.f);
                const FQuat Q=Axis.Size()>1.f?FRotationMatrix::MakeFromXZ(Axis.GetSafeNormal(),Facing).ToQuat():FRotationMatrix::MakeFromZ(Facing).ToQuat();
                X=FTransform(Q,S.P,FVector(Len/100.f,FMath::Max(.6f,S.Size*.16f)/100.f,1.f));
                Alpha=S.Opacity*(1.f-T);
            }
        }
        SparkStreaks->UpdateInstanceTransform(I,X,true,false,true);
        SparkStreaks->SetCustomDataValue(I,0,Alpha,false);SparkStreaks->SetCustomDataValue(I,1,FMath::Frac(I*.618f),false);
        SparkStreaks->SetCustomDataValue(I,2,Age,false);SparkStreaks->SetCustomDataValue(I,3,.9f,false);
    }
    SparkStreaks->SetVisibility(Any);SparkStreaks->MarkRenderStateDirty();bSparksDirty=Any;
}

void AVeyrImpactFx::SetFxTimeScale(float Scale)
{
    CustomTimeDilation=Scale;
    for(UFXSystemComponent* C:Components)if(UNiagaraComponent* N=Cast<UNiagaraComponent>(C))N->SetCustomTimeDilation(Scale);
}

void AVeyrImpactFx::Tick(float DeltaSeconds)
{
    Super::Tick(DeltaSeconds);
    Clock+=DeltaSeconds;
    for(int32 I=0;I<Components.Num();++I)
    {
        if(ComponentAge[I]>=100.f)continue;
        ComponentAge[I]+=DeltaSeconds;
        // Caps a looping source emitter: stop spawning after its life, let the last particles finish.
        if(ComponentAge[I]>=ComponentLife[I]){if(IsValid(Components[I]))Components[I]->Deactivate();ComponentAge[I]=100.f;}
    }
    if(!bCardsDirty&&!bChipsDirty&&!bSparksDirty)return;
    FVector Camera=GetActorLocation();FRotator View;
    if(APlayerController* PC=UGameplayStatics::GetPlayerController(this,0))PC->GetPlayerViewPoint(Camera,View);
    UpdateCards(DeltaSeconds,Camera);UpdateChips(DeltaSeconds);UpdateSparks(DeltaSeconds,Camera);
}
