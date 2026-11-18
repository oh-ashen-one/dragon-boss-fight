#include "VeyrBoneRoles.h"

#include "Components/SkinnedMeshComponent.h"
#include "Engine/SkinnedAsset.h"
#include "ReferenceSkeleton.h"

namespace
{
    struct FRoleNames { const TCHAR* Mixamo; const TCHAR* Paragon; };
    // Order must match EVeyrBoneRole.
    constexpr FRoleNames GRoleNames[static_cast<int32>(EVeyrBoneRole::Count)]=
    {
        {TEXT("VeyrRoot"),TEXT("root")},
        {TEXT("Hips"),TEXT("pelvis")},
        {TEXT("Spine"),TEXT("spine_01")},
        {TEXT("Spine2"),TEXT("spine_03")},
        {TEXT("Neck"),TEXT("neck_01")},
        {TEXT("Head"),TEXT("head")},
        {TEXT("LeftUpLeg"),TEXT("thigh_l")},{TEXT("LeftLeg"),TEXT("calf_l")},{TEXT("LeftFoot"),TEXT("foot_l")},{TEXT("LeftToeBase"),TEXT("ball_l")},
        {TEXT("RightUpLeg"),TEXT("thigh_r")},{TEXT("RightLeg"),TEXT("calf_r")},{TEXT("RightFoot"),TEXT("foot_r")},{TEXT("RightToeBase"),TEXT("ball_r")},
        {TEXT("LeftHand"),TEXT("hand_l")},{TEXT("RightHand"),TEXT("hand_r")},
        {TEXT("LeftForeArm"),TEXT("lowerarm_l")},{TEXT("RightForeArm"),TEXT("lowerarm_r")},
    };
    const FRoleNames& Names(EVeyrBoneRole Role)
    {
        const int32 Index=FMath::Clamp(static_cast<int32>(Role),0,static_cast<int32>(EVeyrBoneRole::Count)-1);
        return GRoleNames[Index];
    }
}

FName VeyrBoneRoles::MixamoName(EVeyrBoneRole Role){return FName(Names(Role).Mixamo);}
FName VeyrBoneRoles::ParagonName(EVeyrBoneRole Role){return FName(Names(Role).Paragon);}

FName VeyrBoneRoles::Resolve(const FReferenceSkeleton& Skeleton, EVeyrBoneRole Role)
{
    const FName Mixamo=MixamoName(Role);
    if(Skeleton.FindBoneIndex(Mixamo)!=INDEX_NONE)return Mixamo;
    const FName Paragon=ParagonName(Role);
    if(Skeleton.FindBoneIndex(Paragon)!=INDEX_NONE)return Paragon;
    return NAME_None;
}

FName VeyrBoneRoles::Resolve(const USkinnedMeshComponent* Component, EVeyrBoneRole Role)
{
    const USkinnedAsset* Asset=Component?Component->GetSkinnedAsset():nullptr;
    // No mesh: keep the Mixamo name so callers see the same "missing bone" result as before.
    return Asset?Resolve(Asset->GetRefSkeleton(),Role):MixamoName(Role);
}

bool VeyrBoneRoles::IsParagonLayout(const FReferenceSkeleton& Skeleton)
{
    return Skeleton.FindBoneIndex(TEXT("Hips"))==INDEX_NONE&&Skeleton.FindBoneIndex(TEXT("pelvis"))!=INDEX_NONE&&
        Skeleton.FindBoneIndex(TEXT("thigh_l"))!=INDEX_NONE&&Skeleton.FindBoneIndex(TEXT("ball_l"))!=INDEX_NONE;
}

void VeyrBoneRoles::ResolveFootPoints(const USkinnedMeshComponent* Component, FName Out[4])
{
    for(int32 I=0;I<4;++I)Out[I]=Resolve(Component,FootPoints[I]);
}
