#pragma once
#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "VeyrDragonEffects.generated.h"

class AVeyrDragon;
class UInstancedStaticMeshComponent;
class UMaterialInterface;
class UMaterialInstanceDynamic;
class UStaticMesh;

/** Original bounded sprite presentation. Reads encounter geometry; never deals damage. */
UCLASS()
class VEYR_API AVeyrDragonEffects : public AActor
{
    GENERATED_BODY()
public:
    AVeyrDragonEffects();
    virtual void Tick(float DeltaSeconds) override;
    UFUNCTION(BlueprintCallable, Category="Veyr|FX") bool Initialize(AVeyrDragon* InDragon);
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Veyr|FX") bool bEffectsReady=false;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Veyr|FX") int32 VisibleSpriteCount=0;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Veyr|FX") int32 PresentationUpdates=0;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Veyr|FX") FString EffectsDiagnostic;
private:
    UPROPERTY() TObjectPtr<AVeyrDragon> Dragon;
    UPROPERTY() TObjectPtr<UInstancedStaticMeshComponent> Core;
    UPROPERTY() TObjectPtr<UInstancedStaticMeshComponent> Flame;
    UPROPERTY() TObjectPtr<UInstancedStaticMeshComponent> Smoke;
    UPROPERTY() TObjectPtr<UStaticMesh> SpritePlane;
    UPROPERTY() TObjectPtr<UMaterialInterface> CoreMaterial;
    UPROPERTY() TObjectPtr<UMaterialInterface> FlameMaterial;
    UPROPERTY() TObjectPtr<UMaterialInterface> SmokeMaterial;
    UPROPERTY(Transient) TObjectPtr<UMaterialInstanceDynamic> WarmCoreMaterial;
    UPROPERTY(Transient) TObjectPtr<UMaterialInstanceDynamic> WarmFlameMaterial;
    // Fixed pools: continuous body, a smaller turbulent layer, and16 embers.
    static constexpr int32 CoreCount=48,FlameCount=96,SmokeCount=32;
    static constexpr int32 FlameBodyCount=48,FlameTurbulenceCount=32;
    void HideEffects();
    void ConfigurePool(UInstancedStaticMeshComponent* Pool, UMaterialInterface* Material, int32 Count);
    static void Sprite(UInstancedStaticMeshComponent* Pool,int32 Index,const FVector& Position,
        const FVector& Camera,float Size,float Alpha,float Seed);
    static void Streak(UInstancedStaticMeshComponent* Pool,int32 Index,const FVector& Position,
        const FVector& Camera,const FVector& Axis,float Along,float Across,float Alpha,float Seed);
};
