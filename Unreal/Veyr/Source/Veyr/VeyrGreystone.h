#pragma once

#include "CoreMinimal.h"
#include "VeyrSingleNodeInstance.h"

class FJsonObject;
class UVeyrVisualDefinition;
class UVeyrSkeletalPresentation;

// Quality goal E: Epic's free Paragon: Greystone as the knight (owner pick 2026-11-18, default skin, dark gold).
//
// Switches (every new behaviour is opt-in until the E4 review flips the default):
//   -VeyrGreystone      use /Game/Characters/Greystone/Runtime/DA_Greystone (all 64 clip keys, baked offline by
//                       tools/unreal/greystone/*.py; no runtime retarget, no AnimBP).
//   -VeyrLegacyKnight   always wins: KnightB definition, BoatWeapon prop and today's locomotion code, unchanged.
//   -VeyrLegacyMotion   (E5) Greystone with today's clip selection instead of the motion matcher.
//   -VeyrGreystoneFeet  opt-in: run the stance/locomotion foot clean-up on Greystone (its thresholds are KnightB boot
//                       measurements and are re-measured in step 2; off on Greystone until then).
//   -VeyrGreystoneBladeRadius=<cm>  hit radius of the blade (default keeps the knight's 18 cm member default).
//
// Content stays out of git: Content/ParagonGreystone (copied pack) and Content/Characters/Greystone (our baked assets).
namespace VeyrGreystone
{
    inline const TCHAR* DefinitionPath=TEXT("/Game/Characters/Greystone/Runtime/DA_Greystone.DA_Greystone");
    /** The knight's shown height; Greystone's MeshRelativeTransform scale is chosen by the supplier to match it. */
    constexpr float TargetStandingHeightCm=244.f;
    /** Bone targets the supplier writes (in addition to the KnightB keys head, weapon_hand, left/right_foot,
     * weapon_base, weapon_tip, cup_socket, flask_grip, flask_spout, left_grip). */
    inline const TCHAR* ShieldBackTarget=TEXT("shield_back"); // anchor bone + shield_inner transform in that frame
    inline const TCHAR* ShieldHealTarget=TEXT("shield_heal"); // optional: shield eased away from the face while drinking
    inline const TCHAR* ShieldInnerBone=TEXT("shield_inner");
    inline const TCHAR* ShieldOuterBone=TEXT("shield_outer");
    inline const TCHAR* SwordBottomBone=TEXT("sword_bottom");
    inline const TCHAR* SwordTopBone=TEXT("sword_top");

    bool IsLegacyKnightForced();
    bool IsRequested();
    bool IsLegacyMotionForced();
    bool FootCleanupEnabled();
    float BladeRadiusCm(float Default);
    /** Paragon layout with Greystone's sword and shield bones. */
    bool IsGreystoneDefinition(const UVeyrVisualDefinition* Definition);

    /** 0 = one-hand (shield on the forearm, as authored), 1 = two-hand (shield on the back). Eased through the grip
     * change action with smoothstep over its duration so the shield travels with the authored hand motion. */
    float ShieldBackWeight(bool bTwoHanded,bool bGripToTwoHand,bool bGripToOneHand,float ActionElapsed,float ActionDuration);
    /** 0..1 bump over the drink (eases in over 15 %, out over the last 20 %), only when shield_heal is supplied. */
    float ShieldHealWeight(bool bHealing,float ActionElapsed,float ActionDuration);

    /** Pins for shield_inner (and shield_outer when it is not shield_inner's child) from the definition targets.
     * Back and heal targets blend: heal is applied on top of whatever the grip pose is. */
    bool BuildShieldPins(const UVeyrVisualDefinition* Definition,const UVeyrSkeletalPresentation* Presentation,
        float BackWeight,float HealWeight,TArray<FVeyrBonePin>& OutPins,FString& OutError);

    /** Standing-height check on the evaluated pose: head bone height above the given floor, and the head-to-ref ratio
     * the supplier used (reported, not enforced). */
    TSharedRef<FJsonObject> PresentationEvidence(const UVeyrVisualDefinition* Definition,const UVeyrSkeletalPresentation* Presentation,float FloorZ);
}
