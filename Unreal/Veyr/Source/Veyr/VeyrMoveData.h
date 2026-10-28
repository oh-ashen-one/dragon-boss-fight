#pragma once

#include "CoreMinimal.h"

/**
 * Measured boss move data (boss-fight-blueprint, boss-runtime.md section 2).
 * Plain structs, filled from Data/dragon/{moves,boxes,tempo,sounds}.json written by
 * tools/movedata/build_moves.py. Units: game cm, clip seconds, degrees, m/s.
 * Frame: x forward along the dragon's nose, y right, z up (actor frame; the mesh
 * rest pose for boxes.json). Nothing here touches gameplay; AVeyrDragon decides
 * how the data is used and keeps its hard-coded behaviour when Load fails.
 */
VEYR_API DECLARE_LOG_CATEGORY_EXTERN(LogVeyrMoveData, Log, All);

/** One hot window of an attack part (moves.json attacks[]). */
struct FBossAttack
{
    FName Part;
    float T0=0.f, T1=0.f, PeakT=0.f, PeakV=0.f;
    FVector AtPeak=FVector::ZeroVector;
};

/** A ground ring (moves.json shocks[]); loaded, not yet evaluated. */
struct FBossShock
{
    float T=0.f;
    FName Bone;
    FVector At=FVector::ZeroVector;
    float Speed=0.f, Radius=0.f;
};

/** A touchdown (moves.json contacts[]); loaded for footfalls and dust, not yet played. */
struct FBossContact
{
    float T=0.f;
    int32 Frame=0;
    FName Bone, Kind;
    float Speed=0.f;
    FVector At=FVector::ZeroVector;
};

/** tempo.json phase: clip seconds [From, To) play at Rate. */
struct FBossTempoPhase
{
    float From=0.f, To=99.f, Rate=1.f;
};

/** sounds.json event: Sound at clip time T from the voice (head) or body socket. */
struct FBossSoundEvent
{
    FName Sound, At;
    float T=0.f, Volume=1.f;
};

struct FBossMove
{
    FName Name;
    float Duration=0.f;
    int32 Frames=0;
    bool bLoop=false;
    /** Per 24 fps frame: X = x cm, Y = y cm, Z = cumulative yaw degrees (actor frame, from frame 0). */
    TArray<FVector> Track;
    TArray<FBossAttack> Attacks;
    TArray<FBossShock> Shocks;
    TArray<FBossContact> Contacts;
    TArray<FBossTempoPhase> Tempo;
    TArray<FBossSoundEvent> Sounds;

    /** Playback rate at a clip time; 1 outside every phase. Loops never get tempo. */
    float TempoAt(float ClipSeconds) const;
    /** Linear interpolation of the track at 24 fps, clamped. */
    FVector TrackAt(float ClipSeconds, float Fps=24.f) const;
};

/** One hurt capsule (boxes.json parts{}). A/B in the mesh rest pose, component frame, game cm. */
struct FBossPart
{
    FName Name, Bone, Kind;
    float Damage=1.f, Radius=0.f;
    FVector A=FVector::ZeroVector, B=FVector::ZeroVector;
    /** Same ends relative to the bone's rest head (bone frame); used only for the import frame check. */
    FVector ABone=FVector::ZeroVector, BBone=FVector::ZeroVector;
    bool bHasBoneLocal=false;
    /** The C++ leg index (0 FL, 1 FR, 2 HL, 3 HR) or INDEX_NONE. */
    int32 Leg=INDEX_NONE;
};

struct VEYR_API FBossMoveData
{
    bool bLoaded=false;
    FString Directory;
    float Fps=24.f;
    float GameScale=1.f;
    TMap<FName,FBossMove> Moves;
    TArray<FName> MoveOrder;
    TArray<FBossPart> Parts;
    FString SoundDirectory;
    TArray<FName> StepSounds;
    TArray<FString> Errors, Warnings;

    /** CVar veyr.MoveData.Dir, then -VeyrMoveData=<dir>, then <Project>/../../Data/dragon, then <Project>/Data/dragon. */
    static FString ResolveDirectory();
    /** Reads the four files. Missing/malformed moves.json or boxes.json leaves bLoaded false and Moves/Parts empty. */
    bool Load(const FString& InDirectory);
    void Reset();
    const FBossMove* Find(FName Move) const { return Moves.Find(Move); }
    const FBossPart* FindPart(FName Part) const;
    int32 CountAttacks() const;
    /** The "gate line" of the blueprint: one line per move, window and part. */
    void Describe(TArray<FString>& OutLines) const;
};

namespace VeyrMoveData
{
    /** veyr.MoveData.Enable (default 1). 0 = never load; the dragon stays fully hard-coded. */
    VEYR_API bool IsEnabled();
    /** veyr.MoveData.Hits: 0 windows never hurt, 1 (default) data-only moves hurt, 2 enum-mapped moves too (their hard-coded contact is replaced). */
    VEYR_API int32 HitsMode();
    /** veyr.MoveData.SwordParts (default 1): sword blows that miss every hard-coded region test the hurt capsules. */
    VEYR_API bool SwordPartsEnabled();
    /** veyr.MoveData.HurtBlocksPawn: 0 query-only, 1 (default) every part but the wings blocks the knight, 2 all parts. Read when capsules are bound. */
    VEYR_API int32 HurtBlocksPawnMode();
    /** veyr.MoveData.Draw (default 0): 1 draws hurt capsules and active windows each frame (debug draw, not Shipping). */
    VEYR_API int32 DrawMode();
}
