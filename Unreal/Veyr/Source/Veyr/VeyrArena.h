#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "VeyrArena.generated.h"

class UInstancedStaticMeshComponent;
class UMaterialInterface;
class UMaterialInstanceDynamic;
class UStaticMesh;

/** Original native layout, using labelled engine-primitive prototype geometry.
 *  No Customuse asset or finished art is claimed. Centimeters, +X forward, Z up. */
UCLASS()
class VEYR_API AVeyrArena : public AActor
{
    GENERATED_BODY()
public:
    AVeyrArena();
    static constexpr float CombatRadius = 3600.f;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Environment") bool bUsingBasaltCliff=false;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Environment") bool bUsingImportedCathedral=false;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Environment") bool bUsingAuthoredNightSky=false;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Environment") bool bUsingAuthoredFloor=false;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Environment") bool bUsingImportedBraziers=false;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Environment") int32 ImportedArchitecturePieces=0;
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
};
