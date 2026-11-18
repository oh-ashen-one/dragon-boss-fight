#pragma once
#include "CoreMinimal.h"

class AVeyrDragon;
class UVeyrSkeletalPresentation;
class USkeletalMesh;

/**
 * A3 (2026-11-18): dragon sole measurement and grounding.
 *
 * The video-to-animation clips raise the body (tripo__Spine_0) by different amounts, and the
 * presentation carried no correction, so the dragon read as floating (owner: "about 3 ft").
 * FVeyrSoleModel skins 12 measured sole points per foot (VeyrDragonSolePoints.inl) with the
 * evaluated pose, so the heights come from the same weights the renderer uses.
 *
 * The grounding itself is ONE vertical offset of the whole presentation component, eased, applied
 * only while the dragon stands on its feet. It never edits a bone, so a later per-foot floor lock
 * (phase F3) can run as IK on top of it: the IK sees an already-grounded pose and only has to
 * remove the remaining per-foot error. Restore with -VeyrNoDragonGrounding.
 */
enum class EVeyrGroundingMode : uint8 { Ground, Hold, Release };

struct FVeyrSoleSample
{
    float SoleAboveFloorCm[4]={0.f,0.f,0.f,0.f};
    float FloorZ[4]={0.f,0.f,0.f,0.f};
    FVector Lowest[4];
    bool bValid=false;
    /** Lowest foot, and the lowest foot height above the floor. */
    int32 LowestFoot=INDEX_NONE;
    float LowestAboveFloorCm=0.f;
};

class FVeyrSoleModel
{
public:
    /** Fits the glTF rest frame to the imported reference pose. Fails (with a diagnostic) on a poor fit. */
    bool Initialize(UVeyrSkeletalPresentation* Presentation);
    bool IsReady() const { return bReady; }
    /** Skin the sole points with the presentation's current evaluated pose and trace the floor. */
    bool Measure(UVeyrSkeletalPresentation* Presentation,FVeyrSoleSample& Out) const;
    FString Diagnostic;
    float FitResidualImportedCm=-1.f;
    TWeakObjectPtr<const USkeletalMesh> FittedMesh;
private:
    struct FInfluence { int32 Bone=INDEX_NONE; float Weight=0.f; FVector BoneLocal=FVector::ZeroVector; };
    struct FPoint { int32 Foot=0; FInfluence Influences[4]; };
    TArray<FPoint> Points;
    bool bReady=false;
};

/**
 * A2 (2026-11-18): the dragon's skin as 1500 spheres (VeyrDragonHullPoints.inl: farthest-point samples of
 * the shipped mesh, wings and body separately), skinned with the evaluated pose. The bone-only wing model
 * missed the membranes by a median 135 cm (1x), so the camera arm keeps clear of these instead.
 */
class FVeyrHullModel
{
public:
    bool Initialize(UVeyrSkeletalPresentation* Presentation);
    bool IsReadyFor(const UVeyrSkeletalPresentation* Presentation) const;
    /** World centres (XYZ) and radii (W) for the current pose. */
    bool Skin(UVeyrSkeletalPresentation* Presentation,TArray<FVector4>& Out) const;
    FString Diagnostic;
private:
    struct FInfluence { int32 Bone=INDEX_NONE; float Weight=0.f; FVector BoneLocal=FVector::ZeroVector; };
    struct FPoint { float Radius=0.f; FInfluence Influences[4]; };
    TArray<FPoint> Points;
    TWeakObjectPtr<const USkeletalMesh> FittedMesh;
};

/** Which grounding rule the dragon's current state wants. Reads only public dragon state. */
EVeyrGroundingMode VeyrGroundingModeFor(const AVeyrDragon* Dragon);
