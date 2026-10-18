#pragma once
#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "VeyrDragonEffects.generated.h"

class AVeyrDragon;
class UInstancedStaticMeshComponent;
class UMaterialInterface;
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
    static constexpr int32 CoreCount=32,FlameCount=72,SmokeCount=24;
    void HideEffects();
    void ConfigurePool(UInstancedStaticMeshComponent* Pool, UMaterialInterface* Material, int32 Count);
    static void Sprite(UInstancedStaticMeshComponent* Pool,int32 Index,const FVector& Position,
        const FVector& Camera,float Size,float Alpha,float Seed);
};
