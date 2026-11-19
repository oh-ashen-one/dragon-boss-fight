#pragma once
#include "UObject/ObjectKey.h"
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
 * A2 (2026-11-18): the dragon's skin as 1500 boom spheres plus 5000 denser samples with normals (VeyrDragonHullPoints.inl: farthest-point samples of
 * the shipped mesh, wings and body separately), skinned with the evaluated pose. The bone-only wing model
 * missed the membranes by a median 135 cm (1x), so the camera arm keeps clear of these instead.
 */
class FVeyrHullModel
{
public:
    bool Initialize(UVeyrSkeletalPresentation* Presentation);
    bool IsReadyFor(const UVeyrSkeletalPresentation* Presentation) const;
    /** Camera boom spheres for the current pose: world centres (XYZ) and radii (W). */
    bool Skin(UVeyrSkeletalPresentation* Presentation,TArray<FVector4>& Out) const;
    /** Every body skin sample (boom + dense) with its skinned outward normal, world space. Wing samples are
     * left out: the membranes are open sheets, so the far side of one is not inside anything. */
    bool SkinSurface(UVeyrSkeletalPresentation* Presentation,TArray<FVector>& OutPositions,TArray<FVector>& OutNormals) const;
    /** The wing membrane samples (boom + dense) with skinned normals: a sight line that changes side of a
     * membrane next to its samples crosses it (camera third pass). */
    bool SkinWingSurface(UVeyrSkeletalPresentation* Presentation,TArray<FVector>& OutPositions,TArray<FVector>& OutNormals) const;
    int32 BoomCount() const { return FMath::Min(BoomPoints,Points.Num()); }
    int32 BoomWingCount() const { return BoomWing; }
    FString Diagnostic;
private:
    struct FInfluence { int32 Bone=INDEX_NONE; float Weight=0.f; FVector BoneLocal=FVector::ZeroVector,NormalLocal=FVector::ZeroVector; };
    struct FPoint { float Radius=0.f; bool bWing=false; FInfluence Influences[4]; };
    TArray<FPoint> Points;
    int32 BoomPoints=0,BoomWing=0;
    TWeakObjectPtr<const USkeletalMesh> FittedMesh;
    /** Fit per mesh, kept across the clip mesh-variant switches (Stomp/Tail swap meshes every state): refitting
     * 6500 samples on each switch cost 60-250 ms frames and cut the showcase Tail clips short. */
    TMap<TObjectKey<USkeletalMesh>,TArray<FPoint>> FitCache;
    bool Fit(const USkeletalMesh* Mesh,TArray<FPoint>& Out);
};

/** Which grounding rule the dragon's current state wants. Reads only public dragon state. */
EVeyrGroundingMode VeyrGroundingModeFor(const AVeyrDragon* Dragon);
