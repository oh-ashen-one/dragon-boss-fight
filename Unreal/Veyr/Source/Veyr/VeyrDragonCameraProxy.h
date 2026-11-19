#pragma once
#include "CoreMinimal.h"
#include "UObject/ObjectKey.h"
#include "UObject/WeakObjectPtrTemplates.h"

class UVeyrSkeletalPresentation;
class USkeletalMesh;

/**
 * Camera fourth pass (2026-11-19): a body proxy that encloses the drawn dragon.
 *
 * One oriented box per bone and mesh variant, fitted offline to every LOD0 skin vertex weighted to that bone
 * (tools/dragon_refine/camera_proxy.py -> VeyrDragonCameraProxy.inl). Each frame the boxes move with the
 * evaluated bones and grow by a margin (world cm, the caller scales it with the dragon). Queries are analytic:
 * point inside, swept sphere (slab test against the box grown by the radius, conservative at corners) and the
 * first free point straight up (union of the vertical intervals).
 */
struct FVeyrProxyWorldBox
{
    FVector Centre=FVector::ZeroVector;
    FVector Axis[3]={FVector::XAxisVector,FVector::YAxisVector,FVector::ZAxisVector};
    FVector Half=FVector::ZeroVector; // grown by the margin
    int32 Bone=INDEX_NONE;
};

class VEYR_API FVeyrDragonProxy
{
public:
    /** Move the boxes with the current pose; false when the mesh has no fitted table. */
    bool Update(const UVeyrSkeletalPresentation* Presentation,float MarginCm);
    bool IsValid() const { return bValid; }
    const TArray<FVeyrProxyWorldBox>& Boxes() const { return World; }
    /** Signed-ish distance from P to the nearest box (<= 0 inside), with every box grown by Extra. */
    float Distance(const FVector& P,float Extra=0.f) const;
    bool Contains(const FVector& P,float Radius) const { return Distance(P,Radius)<=0.f; }
    /** First fraction of A->B where a sphere of Radius touches a box (box grown by Radius); 1 when clear, 0 when A is inside. */
    float Sweep(const FVector& A,const FVector& B,float Radius) const;
    /** Height above P of the first point whose sphere of Radius is outside every box (0 when P is free). */
    float FreeAbove(const FVector& P,float Radius,float MaxUp) const;
    /** True when a vertical line through P (from P up to MaxUp) meets a box grown by Grow. */
    bool UnderBody(const FVector& P,float MaxUp,float Grow) const;
    /** Outside distance from P to one box grown by Extra (0 inside). */
    static float OutsideBox(const FVeyrProxyWorldBox& Box,const FVector& P,float Extra);
    /** Box index list for a bone (current mesh), for the proof. */
    const TArray<int32>* BoxesOfBone(int32 Bone) const { return BoneBoxes.Find(Bone); }
    int32 BoxCount() const { return World.Num(); }
    float Margin() const { return CurrentMargin; }
    FString Diagnostic;
    double UpdateSeconds=0.0;
private:
    friend class FVeyrDragonTrueSkin;
    struct FLocalBox { int32 Bone=INDEX_NONE; FTransform Local; FVector Half=FVector::ZeroVector; };
    TMap<TObjectKey<USkeletalMesh>,TArray<FLocalBox>> Table;
    TArray<FVeyrProxyWorldBox> World;
    TMap<int32,TArray<int32>> BoneBoxes;
    TWeakObjectPtr<const USkeletalMesh> LastMesh;
    bool bValid=false; float CurrentMargin=0.f;
    const TArray<FLocalBox>* Resolve(const USkeletalMesh* Mesh);
    static bool SegmentSlab(const FVeyrProxyWorldBox& Box,const FVector& A,const FVector& B,float Grow,float& OutEnter,float& OutExit);
};

/**
 * The drawn skin itself (every LOD0 vertex and triangle, every mesh variant), for the camera audit and the proxy
 * proof only. Loaded from the git-ignored file the editor commandlet VeyrCameraProxyExport writes (staged into
 * packages); absent file = audit falls back to nothing and says so.
 */
class VEYR_API FVeyrDragonTrueSkin
{
public:
    static FVeyrDragonTrueSkin& Get();
    bool IsLoaded() const { return Meshes.Num()>0; }
    FString Source;
    /** Skin the current mesh with the current pose once per frame (cached by GFrameCounter). */
    bool Skin(const UVeyrSkeletalPresentation* Presentation);
    /** Nearest skin triangle distance from P, up to MaxDistance (returns MaxDistance when nothing nearer). */
    float NearestDistance(const FVector& P,float MaxDistance) const;
    /** Inside the closed skin: majority of three axis rays cross it an odd number of times. */
    bool InsideVolume(const FVector& P) const;
    /** Refit every proxy box's extents along its bone-moved axes to the skinned vertices assigned to it (each vertex
     * to one box of its dominant bone, chosen at rest), then grow by the proxy's margin. Exact containment: linear
     * blend skinning moves blended vertices off their bones' rigid boxes (up to 210 cm at 2x in Collapse/Rise). */
    bool Tighten(FVeyrDragonProxy& Proxy);
    /** Sphere of radius R swept A->B against the skinned faces by conservative advancement (the distance to the skin
     * is 1-Lipschitz, so each step of distance-R never crosses a face), starting at StartT (the part before it is known
     * free, e.g. from the proxy). Returns the free fraction (contact minus 0.5 cm); unconverged = blocked there. */
    float SweepSphere(const FVector& A,const FVector& B,float R,float StartT,int32* OutSteps=nullptr) const;
    /** Any skin triangle crossing the segment A->B. */
    bool SegmentBlocked(const FVector& A,const FVector& B) const;
    /** Proof against a proxy: worst outside distance of any vertex with the proxy's margin (should be 0) and with
     * none (the margin the proxy needs), world cm; vertices tested. Uses the vertex's own bones first. */
    void Prove(const FVeyrDragonProxy& Proxy,float& OutWorstWithMargin,float& OutWorstBare,int32& OutTested,int32& OutOutside,FVector& OutWorstPoint) const;
    int32 VertexCount() const { return Current?Current->Positions.Num():0; }
    int32 TriangleCount() const { return Current?Current->Indices.Num()/3:0; }
    double SkinSeconds=0.0;
    uint64 SkinFrame() const { return SkinnedFrame; }
private:
    struct FMesh
    {
        FString Path; TArray<FVector3f> Positions; TArray<uint16> Bones; TArray<float> Weights; TArray<uint32> Indices;
        TArray<FName> BoneNames; TArray<FTransform> RefComp;
        TArray<int32> GroupOfTriangle; int32 GroupCount=0;
        TArray<int32> BoxOfVertex; int32 BoxCountAssigned=-1;
    };
    TArray<FMesh> Meshes;
    FMesh* Current=nullptr;
    TArray<FVector> Skinned,PrevSkinned;uint64 PrevSkinnedFrame=0;
    TArray<FBox> GroupBounds;
    TArray<TArray<int32>> GroupTriangles;
    uint64 SkinnedFrame=0; const USkeletalMesh* SkinnedMesh=nullptr;
    bool bTried=false;
    void Load();
    int32 RayCrossings(const FVector& P,const FVector& Dir,float Length) const;
};
