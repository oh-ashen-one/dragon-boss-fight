#pragma once
#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "VeyrGroundContacts.h"
#include "VeyrImpactFx.generated.h"

class AVeyrDragon;
class UFXSystemAsset;
class UFXSystemComponent;
class UInstancedStaticMeshComponent;
class UStaticMesh;
class UMaterialInterface;

/**
 * B4/B5 (2026-11-18): what the dragon's weight throws up. Dust in three sizes under each contact, a cloud with
 * debris for body falls and landings, and hit bursts in three sizes where the sword lands. Effect assets are
 * soft paths in Data/dragon/ground_fx.json (Cascade or Niagara), pooled per tier and created once; when an asset
 * is missing the project's own instanced cards stand in. Everything runs on the game clock (hit-stop freezes it).
 * Presentation only: reads contacts, never damages.
 */
UCLASS()
class VEYR_API AVeyrImpactFx : public AActor
{
    GENERATED_BODY()
public:
    AVeyrImpactFx();
    virtual void BeginPlay() override;
    virtual void Tick(float DeltaSeconds) override;
    virtual void EndPlay(const EEndPlayReason::Type Reason) override;
    /** Listen to this dragon's ground contacts (safe to call again). */
    void Bind(AVeyrDragon* Dragon);
    /** Tier 0 light, 1 heavy, 2 heaviest. Out: away from the hide toward the striker. */
    void HitBurst(const FVector& At,const FVector& Out,int32 Tier,float BodyScale);

    // Evidence
    UPROPERTY(VisibleAnywhere,Category="Evidence") int32 DustAsset[5]={0,0,0,0,0};
    UPROPERTY(VisibleAnywhere,Category="Evidence") int32 DustFallback[5]={0,0,0,0,0};
    UPROPERTY(VisibleAnywhere,Category="Evidence") int32 HitAsset[3]={0,0,0};
    UPROPERTY(VisibleAnywhere,Category="Evidence") int32 HitFallback[3]={0,0,0};
    UPROPERTY(VisibleAnywhere,Category="Evidence") int32 ChipsThrown=0;
    UPROPERTY(VisibleAnywhere,Category="Evidence") int32 HitSmoke=0;
    int32 ContactBursts=0; // B2
    UPROPERTY(VisibleAnywhere,Category="Evidence") int32 CardsSpawned=0;
    UPROPERTY(VisibleAnywhere,Category="Evidence") int32 MaxLiveCards=0;
    UPROPERTY(VisibleAnywhere,Category="Evidence") int32 SkippedMerged=0;
    UPROPERTY(VisibleAnywhere,Category="Evidence") FString Diagnostic;
    TArray<FString> LoadedSystems,MissingSystems;

private:
    static constexpr int32 PoolCount=8,CardCount=112,ChipCount=160,SparkCount=112;
    struct FPool { int32 First=0,Num=0,Next=0; bool bAsset=false; };
    FPool Pools[PoolCount]; // 0..4 dust tiers, 5..7 hit tiers
    UPROPERTY() TArray<TObjectPtr<UFXSystemAsset>> Assets;
    UPROPERTY() TArray<TObjectPtr<UFXSystemComponent>> Components;
    TArray<float> ComponentAge,ComponentLife;
    UPROPERTY() TObjectPtr<UInstancedStaticMeshComponent> DustCards;
    UPROPERTY() TObjectPtr<UInstancedStaticMeshComponent> DebrisChips;
    UPROPERTY() TObjectPtr<UInstancedStaticMeshComponent> SparkStreaks;
    UPROPERTY() TObjectPtr<UStaticMesh> Plane;
    UPROPERTY() TObjectPtr<UStaticMesh> ChipMesh;
    UPROPERTY() TObjectPtr<UMaterialInterface> SmokeMaterial;
    UPROPERTY() TObjectPtr<UMaterialInterface> EmberMaterial;
    UPROPERTY() TObjectPtr<UMaterialInterface> ChipMaterial;
    TWeakObjectPtr<AVeyrDragon> BoundDragon;
    /** Phase C: unlit source materials of the effect systems -> exposure-following copies (VeyrLook). */
    TMap<UMaterialInterface*,UMaterialInstanceDynamic*> ExposureMids;
    UPROPERTY() TArray<TObjectPtr<UMaterialInstanceDynamic>> ExposureMidRefs;
    FDelegateHandle ContactHandle;

    struct FCard { FVector P=FVector::ZeroVector,V=FVector::ZeroVector; float Age=0.f,Life=0.f,Size=0.f,Grow=0.f,Opacity=0.f,Seed=0.f; bool bLive=false; };
    struct FChip { FVector P=FVector::ZeroVector,V=FVector::ZeroVector; FRotator R=FRotator::ZeroRotator,Spin=FRotator::ZeroRotator; float Age=0.f,Life=0.f,Size=0.f,Floor=0.f; bool bLive=false; };
    struct FSpark { FVector P=FVector::ZeroVector,V=FVector::ZeroVector; float Age=0.f,Life=0.f,Size=0.f,Opacity=0.f; bool bLive=false; };
    FCard Cards[CardCount]; FChip Chips[ChipCount]; FSpark Sparks[SparkCount];
    int32 NextCard=0,NextChip=0,NextSpark=0;
    bool bCardsDirty=false,bChipsDirty=false,bSparksDirty=false;
    float Clock=0.f,LastCloudClock=-10.f;
    FVector LastCloudAt=FVector::ZeroVector;
    uint32 Seed=0x5eed1234u;

    float Rand();
    void OnContact(AVeyrDragon* Dragon,const FVeyrGroundContact& Contact);
    bool SpawnAsset(int32 Pool,const FVector& At,const FRotator& Facing,float Scale,float Life);
    void SpawnDustCards(const FVeyrFeelTuning::FEffect& E,const FVector& At,float Scale,float Strength,bool bRing);
    void ThrowChips(const FVeyrFeelTuning::FEffect& E,const FVector& At,const FVector& Out,float Scale,float Floor);
    void ThrowSparks(const FVeyrFeelTuning::FEffect& E,const FVector& At,const FVector& Out,float Scale);
    void UpdateCards(float Dt,const FVector& Camera);
    void UpdateChips(float Dt);
    void UpdateSparks(float Dt,const FVector& Camera);
    void ConfigureIsm(UInstancedStaticMeshComponent* Ism,UStaticMesh* Mesh,UMaterialInterface* Material,int32 Count,int32 CustomFloats);
};
