#pragma once
#include "CoreMinimal.h"

/**
 * F1-F4 (2026-11-18): how the dragon's video-to-animation clips are PLAYED.
 *
 * Data: Data/dragon/playback.json (tools/dragon_refine/build_playback_data.py), read at BeginPlay, tunable without a
 * rebuild. Each imported clip stem ("Claw1", "Bite", "Buckle0", "Walk"...) carries the exact bake map of its cut
 * (source video frame shown at every baked 30 Hz frame), its held spans and its Spine_0 planar root track. Each move
 * carries the playback rates the game applies on top of the source speed (1.0 = the clip as generated).
 *
 * Restore switches: -VeyrLegacyClipTempo (F1), -VeyrLegacyBlend (F2), -VeyrNoFootLock and -VeyrLegacySnapTurn (F3),
 * -VeyrNoRootTracks (F4).
 */
struct FVeyrMoveTempo
{
    float WindupRate=1.f,StrikeRate=1.f,RecoveryRate=1.f,Rate=1.f,HoldRate=1.f;
    float RecoveryExit=1.f,GapScale=1.f,GapAdd=0.f,ChainEntry=0.f;
    /** F4: the actor follows this move's Spine_0 track (only moves whose track has real net travel). */
    bool bRootTrack=false;
};

struct FVeyrClipPlayback
{
    FName Stem,Move;
    float SrcFps=24.f,OutFps=30.f;
    /** Source frame shown at baked frame i (i / OutFps baked seconds). Monotone. */
    TArray<float> Bake;
    /** Held source-frame spans [from,to]. */
    TArray<FVector2f> Holds;
    /** Spine_0 planar offset from baked frame 0, mesh-space cm, and yaw degrees. */
    TArray<FVector2D> TrackCm;
    TArray<float> TrackYaw;
    float BakedLength() const { return Bake.Num()>1?(Bake.Num()-1)/OutFps:0.f; }
    float SourceFrameAt(float BakedSeconds) const;
    FVector2D TrackAt(float BakedSeconds) const;
    bool InHold(float SourceFrame) const;
};

struct FVeyrFootLockTuning
{
    float PlantHeightCm=4.f,PlantSpeedCms=120.f,ReleaseHeightCm=8.f,DragReleaseCm=30.f,SlipCm=70.f;
    float ReleaseSeconds=.12f,StepSeconds=.3f,StepLiftCm=18.f;
    /** Round 2 procedural stepping: a planted foot whose clip position drifts past TriggerCm from its pin takes a
     * lift-arc-plant step of ProcStepSeconds, landing LeadSeconds ahead of its drift; one foot at a time (a diagonal
     * pair when both are far). Wind-up aim turns no faster than CarryDps. */
    float ProcStepSeconds=.24f,StepTriggerCm=12.f,StepLeadSeconds=.2f,CarryDps=60.f;
};

class FVeyrDragonPlayback
{
public:
    bool Load(FString& OutDiagnostic);
    bool bLoaded=false;
    FString Path;
    TMap<FName,FVeyrClipPlayback> Clips;
    TMap<FName,FVeyrMoveTempo> Moves;
    TMap<FName,float> Fades;
    float FadeDefault=.35f,TrackRateDps=90.f,TrackLeadSeconds=.06f;
    /** Rate factor on attack phases while the boss is in phase two (the old x1.12 escalation). */
    float Phase2Rate=1.12f;
    /** Phase two never pushes a non-hold rate past this (the 1.25 own-speed ceiling); holds take the full factor. */
    float Phase2MaxRate=1.25f;
    /** Phase two shortens the visible recovery instead (x this on recovery_exit). */
    float Phase2RecoveryExitScale=.85f;
    /** Phase two: extra in-string gap scale and extra chained wind-up skip (the 1.25 ceiling cannot carry x1.12). */
    float Phase2GapScale=1.f,Phase2ChainEntryAdd=0.f;
    /** "compiled" (VeyrDragonPlaybackData.inl) or the loose file path that overrode it. */
    FString Source;
    FVeyrFootLockTuning FootLock;

    /** Strips "V2r" and a Windup/Active/Recovery suffix; returns the stem entry and the phase (NAME_None for whole clips). */
    const FVeyrClipPlayback* Find(FName ClipName,FName& OutPhase) const;
    const FVeyrMoveTempo* MoveTempo(const FVeyrClipPlayback& Clip) const { return Moves.Find(Clip.Move); }
    /** Phase rate of this clip (windup/strike/recovery or whole-clip rate) and its hold rate. */
    void RatesFor(const FVeyrClipPlayback& Clip,FName Phase,float& OutRate,float& OutHoldRate) const;
    /** Real seconds that baked span [B0,B1] takes when the source plays at Rate (holds at HoldRate). */
    static float RealSeconds(const FVeyrClipPlayback& Clip,float B0,float B1,float Rate,float HoldRate);
    /** Baked seconds reached Real seconds after B0 (clamped at B1). */
    static float BakedAfter(const FVeyrClipPlayback& Clip,float B0,float B1,float Real,float Rate,float HoldRate);
    float FadeFor(FName Key) const { const float* F=Fades.Find(Key);return F?*F:FadeDefault; }
};
