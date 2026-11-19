#pragma once
#include "CoreMinimal.h"
#include "GameFramework/SpringArmComponent.h"
#include "VeyrDragonGrounding.h"
#include "VeyrCameraBoom.generated.h"

class AVeyrDragon;
struct FVeyrViewAudit;

/**
 * A2 (2026-11-18): the knight's camera arm, aware of the dragon's body.
 *
 * The dragon's solid capsules ignore the camera channel and its mesh has no collision, so the stock
 * arm sweep never saw the dragon and the camera ended up inside it (owner: legs, belly and the whole
 * body during Collapse). This arm keeps the stock world sweep, then sweeps a sphere along the arm
 * against the dragon's live solid capsules (VeyrSolid_*) plus 1500 skinned skin-hull spheres
 * (FVeyrHullModel; the wings' bones alone missed the membranes by a median 135 cm), all inflated by a
 * clearance.
 *
 * Pull-in is instant, release eases out at ReleaseRate, and the camera rises in proportion to the
 * pull (and further while its point would still sit inside the body), like the reference warden arm.
 * Every distance is authored for the shipped 2x dragon and scales with the dragon's BodyScale, so
 * phase D's 2.5x and 3x runs keep the same framing. -VeyrLegacyCameraBoom restores the stock arm.
 *
 * Knight framing (2026-11-18, second pass): the camera keeps at least MinKnightDistanceCm from the knight
 * (KnightHardMinCm at worst, never inside his capsule) with a clear line of sight to him. When the dragon
 * blocks the arm closer than that, it searches other placements (the arm lowered and levelled under the
 * belly, slid sideways round the body, the pivot raised, then shorter arms with a slightly wider lens) and
 * turns the view so the knight stays whole in frame, above the bottom edge. -VeyrLegacyCameraFraming
 * restores the first-pass arm (which collapsed onto the knight).
 */
UCLASS(ClassGroup=(Veyr))
class VEYR_API UVeyrCameraBoom : public USpringArmComponent
{
    GENERATED_BODY()
public:
    UVeyrCameraBoom();
    virtual void BeginPlay() override;

    /** World cm at the shipped 2x dragon; scaled by BodyScale/2. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Camera|Dragon") float BodyClearanceCm=60.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Camera|Dragon") float WingClearanceCm=40.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Camera|Dragon") float LiftMaxCm=220.f;
    /** Never pulled closer than this to the arm origin (knight-sized; not scaled). */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Camera|Dragon") float MinArmCm=90.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Camera|Dragon") float ReleaseRate=3.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Camera|Dragon") float LiftReleaseRate=2.f;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Camera|Dragon|Evidence") bool bLegacyBoom=false;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Camera|Dragon|Evidence") float BodyFraction=1.f;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Camera|Dragon|Evidence") float LiftCm=0.f;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Camera|Dragon|Evidence") int32 PullInEvents=0;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Camera|Dragon|Evidence") int32 BodyFrames=0;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Camera|Dragon|Evidence") int32 ResultInsideFrames=0;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Camera|Dragon|Evidence") int32 GuardEvents=0;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Camera|Dragon|Evidence") int32 PivotInsideFrames=0;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Camera|Dragon|Evidence") int32 ShapeCount=0;

    /** Knight framing (not scaled: knight-sized). Preferred and hard minimum camera to knight-axis distance. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Camera|Knight") float MinKnightDistanceCm=420.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Camera|Knight") float KnightHardMinCm=260.f;
    /** Widest extra lens used when a placement had to come closer than MinKnightDistanceCm. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Camera|Knight") float MaxFovBoostDeg=8.f;
    /** Screen-edge margin (fraction of the half frame) the knight's capsule keeps. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Camera|Knight") float KnightScreenMargin=.06f;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Camera|Knight|Evidence") bool bLegacyFraming=false;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Camera|Knight|Evidence") int32 FramingSearches=0;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Camera|Knight|Evidence") int32 FramingFallbackFrames=0;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Camera|Knight|Evidence") int32 ViewTurnFrames=0;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Camera|Knight|Evidence") float FovBoostDeg=0.f;

    /** Safety pass (2026-11-18, third pass): the body's interior counts as inside (back-face test), sight lines are
     * marched through it all the way to the knight, no high placements, the view never pitches below
     * MinViewPitchDeg. -VeyrLegacyCameraSafety restores the second pass. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Camera|Knight") float MinViewPitchDeg=-35.f;
    /** Nearest skin sample the camera may have (near plane plus margin), cm. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Camera|Knight") float NearSkinClearanceCm=35.f;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Camera|Knight|Evidence") bool bLegacySafety=false;
    /** Frames where neither the straight, swung nor fast ease was clean and the camera jumped to its placement. */
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Camera|Knight|Evidence") int32 SafetySnaps=0;

    /** Fourth pass (2026-11-19, default; -VeyrLegacyCameraSafety restores the second pass): the stock arm swept as a
     * sphere against the full body (interior and wings), slight lift and wider lens when it gets short, at most
     * MaxMoveCmPerFrame of movement and MaxTurnDegPerFrame of turn per frame. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Camera|Knight") float MaxMoveCmPerFrame=140.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Camera|Knight") float MaxTurnDegPerFrame=11.f;
    /** Lift (cm x dragon scale) and extra lens (deg) at the shortest arm. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Camera|Knight") float ShortArmLiftCm=60.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Camera|Knight") float ShortArmLensDeg=12.f;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Camera|Knight|Evidence") float SafeFraction=1.f;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Camera|Knight|Evidence") int32 ClampedMoves=0;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Camera|Knight|Evidence") int32 SightPullFails=0;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Camera|Knight|Evidence") int32 ClampedTurns=0;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Camera|Knight|Evidence") int32 PivotLiftFrames=0;
    /** Radius (cm x dragon scale) around the lens inside which the dragon dithers away (last-resort net). */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Camera|Knight") float NearLensDitherCm=60.f;

    /** Audit of the camera the player sees; the replay owns the counters so they survive a restart. */
    void AuditView(FVeyrViewAudit& Audit,const FVector& Camera,const FQuat& View,float HorizontalFovDeg,float Seconds);
    TSharedPtr<class FJsonObject> AuditJson(const FVeyrViewAudit& Audit) const;
    /** Inside the bare body shapes or behind the skin (interior). */
    bool IsPointInsideBody(const FVector& Point,float Margin) const;
    /** No skin between A and B: bare shapes (exact) plus the interior marched every ~40 cm. */
    bool SightClear(const FVector& A,const FVector& B,bool bAlwaysMarch=false) const;

    /** Camera-space projection: U right, V up, each -1..1 at the frame edges. False when behind the camera. */
    static bool ProjectToView(const FVector& Point,const FVector& Camera,const FQuat& View,float HorizontalFovDeg,float Aspect,float& OutU,float& OutV);
    /** Viewport aspect (width / height), 16:9 without a viewport. */
    float ViewAspect() const;
    /** Clear sight lines from Point to the knight's chest and head (bare dragon, no see-through). */
    bool IsKnightInSight(const FVector& Point) const;
    /** Any dragon shape centre inside the view frustum. */
    bool IsDragonOnScreen(const FVector& Camera,const FQuat& View,float HorizontalFovDeg,float Aspect) const;
    /** The knight's capsule segment (centres of its end spheres) and radius; false without a capsule owner. */
    bool KnightCapsule(FVector& OutBottom,FVector& OutTop,float& OutRadius) const;

    /** Dragon size factor used this frame (BodyScale / 2). */
    float DragonScale() const;
    /** True when the point is within Radius of the dragon's body or wing shapes (shapes are refreshed
     * on each arm update; call after the arm ticked this frame). Optional name of the shape hit. */
    bool IsPointInsideDragon(const FVector& Point,float Radius,FName* OutShape=nullptr) const;
    /** Same against the bare body (clearances removed): Margin > 0 is a near-plane allowance. */
    bool IsPointInsideBareDragon(const FVector& Point,float Margin,FName* OutShape=nullptr) const;
    /** Solid capsules only (no clearance, no hull): the knight push bodies. */
    bool IsPointInsideSolidCapsule(const FVector& Point,float Margin,FName* OutShape=nullptr) const;
    /** Back-face check: at least 9 of the 12 nearest skinned body skin samples (wings excluded) face away from
     * Point by more than Margin, and the nearest is within 200 cm x scale. */
    bool IsPointBehindSkin(const FVector& Point,float Margin,float* OutDepthCm=nullptr) const;
    /** Distance to the nearest skinned skin sample (body and wings), cm; large when far away. */
    float NearestSkinCm(const FVector& Point) const;
    AVeyrDragon* GetDragon() const { return Dragon.Get(); }
    /** Rebuild the body and wing shapes from the dragon's current pose (the arm does this each update;
     * replays call it so legacy-arm runs are measured against the same shapes). */
    void RefreshDragonShapes() { FindDragon(); RefreshShapes(); }

protected:
    virtual void UpdateDesiredArmLocation(bool bDoTrace,bool bDoLocationLag,bool bDoRotationLag,float DeltaTime) override;
    virtual FVector BlendLocations(const FVector& DesiredArmLocation,const FVector& TraceHitLocation,bool bHitSomething,float DeltaTime) override;

private:
    struct FShape { FVector A=FVector::ZeroVector,B=FVector::ZeroVector,C=FVector::ZeroVector; float Radius=0.f,Clearance=0.f; bool bTriangle=false; FName Name; };
    TArray<FShape> Shapes;
    mutable FVeyrHullModel Hull;
    TArray<FVector4> HullSpheres;
    mutable TArray<FVector> SurfacePositions,SurfaceNormals;
    mutable uint64 SurfaceFrame=0;
    mutable TMap<FIntVector,TArray<int32>> SurfaceGrid; mutable float SurfaceCell=100.f; mutable FBox SurfaceBounds;
    mutable TArray<FVector> WingPositions,WingNormals; mutable TMap<FIntVector,TArray<int32>> WingGrid; mutable FBox WingBounds;
    /** A wing membrane between A and B: the line changes side of the sheet right next to its samples. */
    bool CrossesWing(const FVector& A,const FVector& B) const;
    /** Skin the dense samples once per frame and bucket them; false without a fitted hull. */
    bool EnsureSurface() const;
    /** Up to K nearest skin samples to Point within MaxRing cells; distance-squared ascending. */
    void NearestSkin(const FVector& Point,int32 K,TArray<TPair<double,int32>,TInlineAllocator<13>>& Out,bool bWing=false) const;
    TWeakObjectPtr<AVeyrDragon> Dragon;
    bool bPrerequisiteAdded=false;
    float PreviousTarget=1.f;
    void FindDragon();
    void RefreshShapes();
    float ShapeDistance(const FShape& Shape,const FVector& Point) const;
    /** Smallest fraction t in [0,1] of Origin->End where a sphere of Radius touches a shape not already containing Origin. */
    float FirstContact(const FVector& Origin,const FVector& End,float Radius) const;
    /** True when a sphere of Radius moving from A to B touches no bare dragon shape (exact, no marching). */
    bool SegmentClearOfBareDragon(const FVector& A,const FVector& B,float Radius) const;
    /** Knight framing pass over the first-pass result; returns the final camera location. */
    FVector FrameKnight(const FVector& Origin,const FVector& Base,const FVector& Proposed,float DeltaTime);
    bool KnightWholeInView(const FVector& Camera,const FQuat& View,float HorizontalFovDeg) const;
    bool PlacementOk(const FVector& P,const FVector& KBottom,const FVector& KTop,float KRadius,float MinDistance) const;
    /** View that keeps the knight whole in frame from Camera, starting from the arm's view; boost in degrees. */
    FQuat FrameView(const FVector& Camera,const FQuat& ArmView,const FVector& LookAt,float Fov,float& OutBoost) const;
    FVector LastFramedRelative=FVector::ZeroVector; bool bLastFramed=false; bool bLastSolved=false;
    FVector SafeLastRelative=FVector::ZeroVector; bool bSafeLast=false; float SafeLift=0.f; float SafeLens=0.f; float SafePitch=0.f; float SafeYaw=0.f; float SwingClearSeconds=0.f; FVector SafeLastWorld=FVector::ZeroVector; FVector SafeLastAnchor=FVector::ZeroVector; float SwingPitchTarget=0.f; float SwingYawTarget=0.f;
    FQuat SafeLastView=FQuat::Identity; bool bSafeLastView=false;
    /** Fourth pass arm: returns the camera point and sets FramedView. */
    FVector SafeArm(const FVector& Origin,const FVector& Base,float DeltaTime);
    void FinishView(const FVector& Out,const FVector& Base,float DeltaTime,float ExtraLensDeg);
    int32 StickyCandidate=INDEX_NONE;
    FQuat FramedView=FQuat::Identity; bool bFramedViewValid=false; FVector FramedLookAt=FVector::ZeroVector;
    float AppliedFovBoost=0.f,AppliedFov=0.f;
    FQuat ViewCorrection=FQuat::Identity; bool bViewCorrectionValid=false;
};

/** Whole-replay camera audit (VeyrCameraBoom::AuditView), held by the replay so a restart keeps it. */
struct FVeyrViewAudit
{
    int32 Frames=0,InsideAny=0,InsideCapsule=0,InsideHull=0,BehindSkin=0,NearSkin=0,InsideKnight=0,KnightWhole=0;
    int32 HalfVisible=0,FullyHidden=0,MoveJumps=0,TurnJumps=0,KnightTeleports=0,LongestInsideRun=0,InsideRun=0;
    int32 SteepFrames=0,OutsideCentre=0;
    float HiddenRunSeconds=0.f,LongestHiddenSeconds=0.f,MinCameraToKnightCm=TNumericLimits<float>::Max(),MinPitchDeg=90.f;
    float MaxMoveCm=0.f,MaxTurnDeg=0.f,LastSeconds=-1.f;
    FVector LastCamera=FVector::ZeroVector,LastKnight=FVector::ZeroVector;FQuat LastView=FQuat::Identity;bool bHasLast=false;
    TArray<float> InsideSeconds,HiddenSeconds,JumpSeconds,SteepSeconds,JumpDetail; int32 Cuts=0,SettleFrames=0;
};
