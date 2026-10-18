#pragma once

#include "CoreMinimal.h"
#include "Engine/DataAsset.h"
#include "VeyrVisualDefinition.generated.h"

class USkeletalMesh;
class UAnimSequence;

USTRUCT(BlueprintType)
struct FVeyrVisualClip
{
    GENERATED_BODY()
    UPROPERTY(EditAnywhere, BlueprintReadOnly) TObjectPtr<UAnimSequence> Sequence;
    UPROPERTY(EditAnywhere, BlueprintReadOnly) float StartSeconds=0.f;
    /** Negative means the actual sequence end. Times use imported clip seconds. */
    UPROPERTY(EditAnywhere, BlueprintReadOnly) float EndSeconds=-1.f;
    UPROPERTY(EditAnywhere, BlueprintReadOnly) float ImpactSeconds=-1.f;
    UPROPERTY(EditAnywhere, BlueprintReadOnly) bool bLoop=false;
};

USTRUCT(BlueprintType)
struct FVeyrVisualBoneTarget
{
    GENERATED_BODY()
    UPROPERTY(EditAnywhere, BlueprintReadOnly) FName BoneName;
    /** Offset in imported bone-local centimetres, before component scale. */
    UPROPERTY(EditAnywhere, BlueprintReadOnly) FTransform LocalOffset=FTransform::Identity;
};

/** Imported art configuration only. Does not alter combat or imply visual acceptance. */
UCLASS(BlueprintType)
class VEYR_API UVeyrVisualDefinition : public UDataAsset
{
    GENERATED_BODY()
public:
    UPROPERTY(EditAnywhere, BlueprintReadOnly) TObjectPtr<USkeletalMesh> SkeletalMesh;
    UPROPERTY(EditAnywhere, BlueprintReadOnly) FTransform MeshRelativeTransform=FTransform::Identity;
    UPROPERTY(EditAnywhere, BlueprintReadOnly) TMap<FName,FVeyrVisualClip> Clips;
    UPROPERTY(EditAnywhere, BlueprintReadOnly) TMap<FName,FVeyrVisualBoneTarget> BoneTargets;
    UPROPERTY(EditAnywhere, BlueprintReadOnly) TArray<FName> RequiredClips;
    UPROPERTY(EditAnywhere, BlueprintReadOnly) TArray<FName> RequiredBoneTargets;
    UPROPERTY(EditAnywhere, BlueprintReadOnly) FString SourceSHA256;
    UPROPERTY(EditAnywhere, BlueprintReadOnly) bool bNativePresentationVerified=false;

    /** Basic validation permits a rig-only milestone; complete mode checks required clips. */
    UFUNCTION(BlueprintCallable, Category="Veyr|Presentation")
    TArray<FString> ValidateDefinition(bool bRequireCompleteMoveset=false) const;

    /** Exposes the actual imported names, including importer sanitization. */
    UFUNCTION(BlueprintCallable, Category="Veyr|Presentation")
    TArray<FName> GetImportedBoneNames() const;

    /** Reference pose in imported mesh component space, before actor/component offsets. */
    UFUNCTION(BlueprintCallable, Category="Veyr|Presentation")
    TMap<FName,FTransform> GetImportedReferenceBoneTransforms() const;

    UFUNCTION(BlueprintCallable, Category="Veyr|Presentation")
    FVector GetImportedBoundsOrigin() const;

    UFUNCTION(BlueprintCallable, Category="Veyr|Presentation")
    FVector GetImportedBoundsExtent() const;
};
