#pragma once

#include "CoreMinimal.h"

class USkinnedMeshComponent;
struct FReferenceSkeleton;

// Quality goal E (Greystone): skeleton-neutral bone roles. Code that used to name Mixamo bones (KnightB: Hips,
// LeftUpLeg, LeftToeBase, VeyrRoot, ...) asks for a role instead. Resolution tries the Mixamo name first, so the
// legacy KnightB skeleton resolves to exactly the names it used before (same bones, same behaviour); only a skeleton
// without that name (Paragon/UE4 mannequin layout: pelvis, thigh_l, ball_l, root, ...) falls through to the second
// name. A role missing from both returns NAME_None, which every caller already treated as "bone missing".
enum class EVeyrBoneRole : uint8
{
    Root,        // nondeforming hierarchy root (VeyrRoot / root)
    Pelvis,      // Hips / pelvis
    Spine,       // first spine bone above the pelvis: Spine / spine_01
    Chest,       // upper spine: Spine2 / spine_03
    Neck,
    Head,
    LeftThigh, LeftCalf, LeftAnkle, LeftToe,
    RightThigh, RightCalf, RightAnkle, RightToe,
    LeftHand, RightHand,
    LeftForearm, RightForearm,
    Count
};

namespace VeyrBoneRoles
{
    /** KnightB (Mixamo names without prefix). */
    FName MixamoName(EVeyrBoneRole Role);
    /** Greystone (Paragon / UE4 mannequin names). */
    FName ParagonName(EVeyrBoneRole Role);
    /** Mixamo name if the skeleton has it, else the Paragon name if present, else NAME_None. */
    FName Resolve(const FReferenceSkeleton& Skeleton, EVeyrBoneRole Role);
    FName Resolve(const USkinnedMeshComponent* Component, EVeyrBoneRole Role);
    /** True when the skeleton carries the Paragon layout (pelvis + thigh_l + ball_l) and not the Mixamo one. */
    bool IsParagonLayout(const FReferenceSkeleton& Skeleton);

    /** The four foot points the locomotion code compares: left toe, right toe, left ankle, right ankle (old order). */
    inline constexpr EVeyrBoneRole FootPoints[4]={EVeyrBoneRole::LeftToe,EVeyrBoneRole::RightToe,EVeyrBoneRole::LeftAnkle,EVeyrBoneRole::RightAnkle};
    /** Resolve FootPoints for one component (NAME_None for missing bones, as before). */
    void ResolveFootPoints(const USkinnedMeshComponent* Component, FName Out[4]);
}
