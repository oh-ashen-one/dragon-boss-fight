#pragma once
#include "CoreMinimal.h"
#include "GameFramework/SpringArmComponent.h"
#include "VeyrCameraBoom.generated.h"

class AVeyrDragon;

/**
 * A2 (2026-11-18): the knight's camera arm, aware of the dragon's body.
 *
 * The dragon's solid capsules ignore the camera channel and its mesh has no collision, so the stock
 * arm sweep never saw the dragon and the camera ended up inside it (owner: legs, belly and the whole
 * body during Collapse). This arm keeps the stock world sweep, then sweeps a sphere along the arm
 * against the dragon's live solid capsules (VeyrSolid_*) plus capsules and triangles for each wing
 * (bones VeyrWing{NegZ,PosZ}{Root,Elbow,Membrane,Wrist,Tip}), all inflated by a clearance.
 *
 * Pull-in is instant, release eases out at ReleaseRate, and the camera rises in proportion to the
 * pull (and further while its point would still sit inside the body), like the reference warden arm.
 * Every distance is authored for the shipped 2x dragon and scales with the dragon's BodyScale, so
 * phase D's 2.5x and 3x runs keep the same framing. -VeyrLegacyCameraBoom restores the stock arm.
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
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Camera|Dragon|Evidence") int32 ShapeCount=0;

    /** Dragon size factor used this frame (BodyScale / 2). */
    float DragonScale() const;
    /** True when the point is within Radius of the dragon's body or wing shapes (shapes are refreshed
     * on each arm update; call after the arm ticked this frame). Optional name of the shape hit. */
    bool IsPointInsideDragon(const FVector& Point,float Radius,FName* OutShape=nullptr) const;
    AVeyrDragon* GetDragon() const { return Dragon.Get(); }
    /** Rebuild the body and wing shapes from the dragon's current pose (the arm does this each update;
     * replays call it so legacy-arm runs are measured against the same shapes). */
    void RefreshDragonShapes() { FindDragon(); RefreshShapes(); }

protected:
    virtual FVector BlendLocations(const FVector& DesiredArmLocation,const FVector& TraceHitLocation,bool bHitSomething,float DeltaTime) override;

private:
    struct FShape { FVector A=FVector::ZeroVector,B=FVector::ZeroVector,C=FVector::ZeroVector; float Radius=0.f; bool bTriangle=false; FName Name; };
    TArray<FShape> Shapes;
    TWeakObjectPtr<AVeyrDragon> Dragon;
    bool bPrerequisiteAdded=false;
    float PreviousTarget=1.f;
    void FindDragon();
    void RefreshShapes();
    float ShapeDistance(const FShape& Shape,const FVector& Point) const;
    /** Smallest fraction t in [0,1] of Origin->End where a sphere of Radius touches a shape not already containing Origin. */
    float FirstContact(const FVector& Origin,const FVector& End,float Radius) const;
};
