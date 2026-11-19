#pragma once
#include "CoreMinimal.h"
#include "VeyrFeelTuning.h"
#include "VeyrGroundContacts.generated.h"

class AVeyrDragon;

/**
 * B4 (2026-11-18): every dragon contact with the floor, from the evaluated pose frame to frame.
 * Feet: the A3 sole model's lowest skinned sole point. Body: the boxes.json hurt capsules' lowest point.
 * A touchdown is the clearance falling below a touch height while armed; it re-arms above a higher lift
 * height. Speeds are into the floor, a decaying peak over the last ~80 ms. Game clock throughout.
 * Consumers: AVeyrFightFeel (camera), AVeyrImpactFx (dust, debris), the sound layer (footsteps, thuds).
 */
UENUM(BlueprintType)
enum class EVeyrGroundContactPart : uint8 { Foot, Head, Neck, Body, Tail, Wing };

UENUM(BlueprintType)
enum class EVeyrGroundContactClass : uint8 { Footfall, Stomp, BodyFall, Landing };

USTRUCT(BlueprintType)
struct FVeyrGroundContact
{
    GENERATED_BODY()
    UPROPERTY(BlueprintReadOnly) EVeyrGroundContactPart Part=EVeyrGroundContactPart::Foot;
    /** "foot0".."foot3", "head", "neck", "chest", "belly", "hips", "tail", "wing_l", "wing_r". */
    UPROPERTY(BlueprintReadOnly) FName PartName=NAME_None;
    /** 0 FL, 1 FR, 2 HL, 3 HR (boxes.json order) for feet; -1 otherwise. */
    UPROPERTY(BlueprintReadOnly) int32 Leg=INDEX_NONE;
    UPROPERTY(BlueprintReadOnly) EVeyrGroundContactClass Class=EVeyrGroundContactClass::Footfall;
    /** 0 small, 1 medium, 2 large dust; 3 body-fall cloud with debris; 4 landing cloud. */
    UPROPERTY(BlueprintReadOnly) int32 DustTier=0;
    /** On the floor under the touching part, world cm. */
    UPROPERTY(BlueprintReadOnly) FVector World=FVector::ZeroVector;
    /** Raw world speed into the floor (m/s) and the same divided by BodyScale (1x-equivalent). */
    UPROPERTY(BlueprintReadOnly) float SpeedMps=0.f;
    UPROPERTY(BlueprintReadOnly) float ScaledSpeedMps=0.f;
    /** 0..1 within the class, from the class's speed curve. */
    UPROPERTY(BlueprintReadOnly) float Strength=0.f;
    /** UWorld::GetTimeSeconds() at the contact (the dilated game clock). */
    UPROPERTY(BlueprintReadOnly) float GameTime=0.f;
    UPROPERTY(BlueprintReadOnly) int32 Serial=0;
};

DECLARE_MULTICAST_DELEGATE_TwoParams(FVeyrOnGroundContact,AVeyrDragon*,const FVeyrGroundContact&);

struct FVeyrGroundContactCounters
{
    int32 Total=0;
    int32 ByPart[6]={0,0,0,0,0,0};
    int32 ByClass[4]={0,0,0,0};
    int32 ByTier[5]={0,0,0,0,0};
    int32 Feet[4]={0,0,0,0};
    float MaxSpeedMps=0.f,MaxScaledSpeedMps=0.f;
    int32 Rejected=0; // touchdowns under the part's minimum speed (no event)
    int32 Muted=0;    // touchdowns while the pose was displaced by the hit flinch (no event)
    int32 Resets=0;   // frames the pose was unavailable (detector forgot every slot)
};

/** What the dragon is doing this frame, for classification. */
struct FVeyrContactContext
{
    float BodyScale=1.f, GameTime=0.f, FloorZ=0.f;
    bool bFootStrike=false, bTailStrike=false, bHeadStrike=false, bLanding=false;
    /** Airborne this frame (arms each foot's one landing touchdown). */
    bool bAirborne=false;
    /** Head/body on or going to the floor (buckle, collapse, exposed, rise, death): tail and wing touches are body falls. */
    bool bBodyDown=false;
    /** The pose is displaced by presentation only (the hit flinch): track, disarm, but emit nothing. */
    bool bMuted=false;
    FName StateName=NAME_None;
};

class FVeyrGroundContactDetector
{
public:
    static constexpr int32 MaxSlots=16, RingSize=64;
    struct FSlot
    {
        FName Name=NAME_None; EVeyrGroundContactPart Part=EVeyrGroundContactPart::Foot; int32 Leg=INDEX_NONE;
        float Clearance=0.f, PeakDown=0.f, SinceEvent=10.f;
        FVector Point=FVector::ZeroVector;
        bool bSeen=false, bArmed=false, bSampledThisFrame=false, bPendingLanding=false;
    };

    FVeyrGroundContactDetector();
    void Reset();
    /** The pose was not available this frame: forget every slot (no stale speed next frame). */
    void Forget();
    /** Start a frame: GameDelta is the dragon's DeltaSeconds. Clears this frame's contacts. */
    void BeginFrame(float GameDelta,const FVeyrContactContext& Context);
    /** One part this frame. LowestPoint: its lowest world point; the floor height comes from the context unless given. */
    void Sample(int32 Slot,FName Name,EVeyrGroundContactPart Part,int32 Leg,const FVector& LowestPoint,float FloorZ);
    /** Close the frame: parts not sampled this frame are disarmed without an event (missing pose). */
    void EndFrame();

    const TArray<FVeyrGroundContact>& ThisFrame() const { return Frame; }
    int32 LastSerial() const { return Serial; }
    int32 CopySince(int32 AfterSerial,TArray<FVeyrGroundContact>& Out) const;
    const FVeyrGroundContactCounters& Counters() const { return Count; }
    /** Lowest clearance per part name and dragon state seen so far (cm, at the shipped scale). */
    const TMap<FName,TMap<FName,float>>& MinClearanceByState() const { return MinClearance; }
    const FSlot* GetSlot(int32 I) const { return I>=0&&I<MaxSlots?&Slots[I]:nullptr; }

private:
    FSlot Slots[MaxSlots];
    TArray<FVeyrGroundContact> Frame;
    FVeyrGroundContact Ring[RingSize];
    int32 Serial=0;
    float Delta=0.f;
    FVeyrContactContext Ctx;
    FVeyrGroundContactCounters Count;
    TMap<FName,TMap<FName,float>> MinClearance;
    void Emit(FSlot& S,float SpeedCmS);
};
