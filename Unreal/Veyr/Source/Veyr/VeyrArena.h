#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "VeyrArena.generated.h"

class UInstancedStaticMeshComponent;
class UMaterialInterface;
class UMaterialInstanceDynamic;
class UStaticMesh;
class UStaticMeshComponent;
class APlayerController;
class UVeyrSkeletalPresentation;

/** Connected sunken court assembled from measured Tripo architecture.
 *  Centimeters, +X toward the apse, Z up. Native visual acceptance is separate. */
UCLASS()
class VEYR_API AVeyrArena : public AActor
{
    GENERATED_BODY()
public:
    AVeyrArena();
    virtual void Tick(float DeltaSeconds) override;
    void UpdatePropCameraOcclusion(APlayerController* Player,const FVector& Camera,const FVector& Focus,float DeltaSeconds);
    void DamagePropsAlongSweep(const FVector& PreviousBase,const FVector& PreviousTip,const FVector& Base,const FVector& Tip);
    UPROPERTY(VisibleAnywhere,BlueprintReadOnly,Category="Environment") int32 BrokenProps=0;
    UPROPERTY(VisibleAnywhere,BlueprintReadOnly,Category="Environment") bool bOverhaulAssetsReady=false;
    UPROPERTY(VisibleAnywhere,BlueprintReadOnly,Category="Environment") int32 GeneratedArchitectureMeshCount=0;
    UPROPERTY(VisibleAnywhere,BlueprintReadOnly,Category="Environment") int32 BreakablePropCount=0;
    UPROPERTY(VisibleAnywhere,BlueprintReadOnly,Category="Environment") int32 BackgroundDragonCount=0;
    static constexpr float CombatRadius = 3600.f;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Environment") bool bUsingBasaltCliff=false;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Environment") bool bUsingImportedCathedral=false;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Environment") bool bUsingAuthoredNightSky=false;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Environment") bool bUsingAuthoredFloor=false;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Environment") bool bUsingImportedBraziers=false;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Environment") int32 ImportedArchitecturePieces=0;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Environment") bool bConnectedCourtAssetsReady=false;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Environment") int32 ConnectedCourtMeshCount=0;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Environment") int32 ConnectedCourtInstanceCount=0;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Environment") FString ConnectedCourtDiagnostic;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Environment") TMap<FName,FVector> ConnectedMeshDimensionsCm;
    UFUNCTION(BlueprintPure, Category="Environment") float GetMaximumWalkableHeightNear(const FVector& WorldPoint,float RadiusCm) const;
    /** GLB front is provisionally +Y after import; root verifies native orientation. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Environment") float CathedralFacingYawOffset=90.f;

protected:
    virtual void BeginPlay() override;

private:
    UPROPERTY() TObjectPtr<UStaticMesh> CubeMesh;
    UPROPERTY() TObjectPtr<UStaticMesh> BasaltCliffMesh;
    UPROPERTY() TObjectPtr<UStaticMesh> CylinderMesh;
    UPROPERTY() TObjectPtr<UStaticMesh> SphereMesh;
    UPROPERTY() TObjectPtr<UStaticMesh> ConeMesh;
    UPROPERTY() TObjectPtr<UStaticMesh> SkyMesh;
    UPROPERTY() TObjectPtr<UStaticMesh> CathedralFacadeMesh;
    UPROPERTY() TObjectPtr<UStaticMesh> CathedralWallMesh;
    UPROPERTY() TObjectPtr<UStaticMesh> CathedralArchMesh;
    UPROPERTY() TObjectPtr<UStaticMesh> CathedralBrazierMesh;
    UPROPERTY() TObjectPtr<UMaterialInterface> CathedralFloorParent;
    UPROPERTY() TObjectPtr<UMaterialInterface> NightSkyParent;
    UPROPERTY() TObjectPtr<UMaterialInterface> StoneParent;
    UPROPERTY() TObjectPtr<UMaterialInterface> PlainParent;
    UPROPERTY() TObjectPtr<UMaterialInterface> SkyParent;
    UPROPERTY() TArray<TObjectPtr<UMaterialInstanceDynamic>> Materials;
    UPROPERTY() TArray<TObjectPtr<UInstancedStaticMeshComponent>> Batches;
    UPROPERTY() TMap<FName,TObjectPtr<UStaticMesh>> PolishMeshes;
    UPROPERTY() TMap<FName,TObjectPtr<UInstancedStaticMeshComponent>> PolishBatches;
    TArray<FBox> RaisedWalkableBounds;

    UInstancedStaticMeshComponent* Stone = nullptr;
    UInstancedStaticMeshComponent* Trim = nullptr;
    UInstancedStaticMeshComponent* Floor = nullptr;
    UInstancedStaticMeshComponent* FloorLight = nullptr;
    UInstancedStaticMeshComponent* FloorWet = nullptr;
    UInstancedStaticMeshComponent* FloorSurface = nullptr;
    UInstancedStaticMeshComponent* Foundations = nullptr;
    UInstancedStaticMeshComponent* FloorCarvings = nullptr;
    UInstancedStaticMeshComponent* BoundaryStone = nullptr;
    UInstancedStaticMeshComponent* Bronze = nullptr;
    UInstancedStaticMeshComponent* Columns = nullptr;
    UInstancedStaticMeshComponent* ColumnTrim = nullptr;
    UInstancedStaticMeshComponent* DarkDisks = nullptr;
    UInstancedStaticMeshComponent* Rocks = nullptr;
    UInstancedStaticMeshComponent* RockSpurs = nullptr;
    UInstancedStaticMeshComponent* Embers = nullptr;
    bool bBuilt = false;
    UPROPERTY() TArray<TObjectPtr<UStaticMeshComponent>> BreakableProps;
    UPROPERTY() TArray<TObjectPtr<UStaticMeshComponent>> Debris;
    UPROPERTY() TArray<TObjectPtr<UVeyrSkeletalPresentation>> SkyDragons;
    TArray<FVector> DebrisVelocity;
    TArray<float> DebrisAge;
    TArray<float> PropHealth;
    TArray<float> PropFallSpeed;
    TMap<TWeakObjectPtr<UStaticMeshComponent>,float> HiddenPropTimers;
    TArray<FTransform> SkyDragonBasis;
    float AtmosphereClock=0.f;
    void BuildOverarchingArchitecture();
    void BuildInteractiveDetails();
    void BreakProp(int32 Index);
    void SpawnBreakable(UStaticMesh* Mesh,const FVector& Position,float Height,float Yaw);

    UMaterialInstanceDynamic* MakeMaterial(const FName Name, const FLinearColor Color, float Roughness,
        bool bUseAuthoredStone=true, float Metallic=0.f, float Emission=0.f);
    UInstancedStaticMeshComponent* MakeBatch(const FName Name, UStaticMesh* Mesh, UMaterialInterface* Material);
    void Box(UInstancedStaticMeshComponent* Batch, const FVector& Position, const FVector& Size, const FRotator& Rotation = FRotator::ZeroRotator);
    void Beam(UInstancedStaticMeshComponent* Batch, const FVector& A, const FVector& B, float Width);
    void Cylinder(UInstancedStaticMeshComponent* Batch, const FVector& Position, float Radius, float Height);
    void Arch(const FVector& Left, const FVector& Right, float Spring, float Apex, float Width, UInstancedStaticMeshComponent* Batch, int32 LeftPieces = 16, int32 RightPieces = 16);
    void RoseRing(const FVector& Center, float Radius, float Width);
    void BuildFloor();
    void BuildCathedral();
    bool BuildImportedCathedral();
    void ImportedPiece(UStaticMesh* Mesh,const FName Name,const FVector& Position,float Height,float Yaw,bool bArchitecture=true);
    void BuildDistance();
    void BuildLighting();
    void BuildCollision();
    bool LoadPolishKit();
    FVector KitSize(FName Name,float Height) const;
    void KitPiece(FName Name,const FVector& Anchor,float Height,float Yaw,bool bBlocking=true,bool bFrontAnchor=false,float WidthScale=1.f);
    void KitWallRun(FName Name,const FVector& Start,const FVector& End,const FVector& Inward,float Height,float FloorZ,bool bBlocking=true);
    void BuildCourtTerrain();
};
