#include "VeyrGreystone.h"

#include "AnimationRuntime.h"
#include "Dom/JsonObject.h"
#include "Engine/SkeletalMesh.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "VeyrBoneRoles.h"
#include "VeyrSkeletalPresentation.h"
#include "VeyrVisualDefinition.h"

bool VeyrGreystone::IsLegacyKnightForced(){return FParse::Param(FCommandLine::Get(),TEXT("VeyrLegacyKnight"));}
bool VeyrGreystone::IsRequested(){return FParse::Param(FCommandLine::Get(),TEXT("VeyrGreystone"))&&!IsLegacyKnightForced();}
bool VeyrGreystone::IsLegacyMotionForced(){return FParse::Param(FCommandLine::Get(),TEXT("VeyrLegacyMotion"));}
bool VeyrGreystone::FootCleanupEnabled(){return FParse::Param(FCommandLine::Get(),TEXT("VeyrGreystoneFeet"));}

float VeyrGreystone::BladeRadiusCm(float Default)
{
    float Value=0.f;
    if(FParse::Value(FCommandLine::Get(),TEXT("VeyrGreystoneBladeRadius="),Value)&&FMath::IsFinite(Value))return FMath::Clamp(Value,8.f,42.f);
    return Default;
}

bool VeyrGreystone::IsGreystoneDefinition(const UVeyrVisualDefinition* Definition)
{
    if(!Definition||!Definition->SkeletalMesh)return false;
    const FReferenceSkeleton& Ref=Definition->SkeletalMesh->GetRefSkeleton();
    return VeyrBoneRoles::IsParagonLayout(Ref)&&Ref.FindBoneIndex(SwordTopBone)!=INDEX_NONE&&Ref.FindBoneIndex(ShieldInnerBone)!=INDEX_NONE;
}

float VeyrGreystone::ShieldBackWeight(bool bTwoHanded,bool bGripToTwoHand,bool bGripToOneHand,float ActionElapsed,float ActionDuration)
{
    const float T=ActionDuration>0.f?FMath::Clamp(ActionElapsed/ActionDuration,0.f,1.f):1.f;
    if(bGripToTwoHand)return FMath::SmoothStep(0.f,1.f,T);
    if(bGripToOneHand)return 1.f-FMath::SmoothStep(0.f,1.f,T);
    return bTwoHanded?1.f:0.f;
}

float VeyrGreystone::ShieldHealWeight(bool bHealing,float ActionElapsed,float ActionDuration)
{
    if(!bHealing||ActionDuration<=0.f)return 0.f;
    const float T=FMath::Clamp(ActionElapsed/ActionDuration,0.f,1.f);
    return FMath::Min(FMath::SmoothStep(0.f,.15f,T),1.f-FMath::SmoothStep(.80f,1.f,T));
}

bool VeyrGreystone::BuildShieldPins(const UVeyrVisualDefinition* Definition,const UVeyrSkeletalPresentation* Presentation,
    float BackWeight,float HealWeight,TArray<FVeyrBonePin>& OutPins,FString& OutError)
{
    OutPins.Reset();OutError.Reset();
    if(!Definition||!Definition->SkeletalMesh||!Presentation){OutError=TEXT("No Greystone definition");return false;}
    const FReferenceSkeleton& Ref=Definition->SkeletalMesh->GetRefSkeleton();
    const int32 Inner=Ref.FindBoneIndex(ShieldInnerBone),Outer=Ref.FindBoneIndex(ShieldOuterBone);
    if(Inner==INDEX_NONE){OutError=TEXT("Greystone shield_inner bone missing");return false;}
    // shield_outer keeps its reference-pose relation to shield_inner when it is not already its child.
    const bool PinOuter=Outer!=INDEX_NONE&&Ref.GetParentIndex(Outer)!=Inner;
    FTransform OuterFromInner=FTransform::Identity;
    if(PinOuter)
    {
        const FTransform InnerRef=FAnimationRuntime::GetComponentSpaceTransformRefPose(Ref,Inner);
        const FTransform OuterRef=FAnimationRuntime::GetComponentSpaceTransformRefPose(Ref,Outer);
        OuterFromInner=OuterRef.GetRelativeTransform(InnerRef);
    }
    auto Add=[&](const TCHAR* TargetName,float Weight)
    {
        if(Weight<=0.f)return true;
        const FVeyrVisualBoneTarget* Target=Definition->BoneTargets.Find(TargetName);
        if(!Target){if(FCString::Strcmp(TargetName,ShieldBackTarget)==0)OutError=TEXT("Greystone definition has no shield_back target");return false;}
        FVeyrBonePin Pin;Pin.Bone=ShieldInnerBone;Pin.Anchor=Target->BoneName;Pin.AnchorLocal=Target->LocalOffset;Pin.Weight=Weight;
        OutPins.Add(Pin);
        if(PinOuter){Pin.Bone=ShieldOuterBone;Pin.AnchorLocal=OuterFromInner*Target->LocalOffset;OutPins.Add(Pin);}
        return true;
    };
    // Back first, heal second: the heal pin blends from wherever the back pin left the shield.
    if(!Add(ShieldBackTarget,FMath::Clamp(BackWeight,0.f,1.f))&&BackWeight>0.f)return false;
    if(HealWeight>0.f&&Definition->BoneTargets.Contains(ShieldHealTarget))Add(ShieldHealTarget,FMath::Clamp(HealWeight,0.f,1.f));
    return true;
}

TSharedRef<FJsonObject> VeyrGreystone::PresentationEvidence(const UVeyrVisualDefinition* Definition,const UVeyrSkeletalPresentation* Presentation,float FloorZ)
{
    TSharedRef<FJsonObject> O=MakeShared<FJsonObject>();
    const bool Active=IsGreystoneDefinition(Definition);
    O->SetBoolField(TEXT("greystone"),Active);
    O->SetBoolField(TEXT("requested"),IsRequested());
    O->SetBoolField(TEXT("legacyKnightForced"),IsLegacyKnightForced());
    O->SetBoolField(TEXT("legacyMotionForced"),IsLegacyMotionForced());
    O->SetBoolField(TEXT("footCleanup"),!Active||FootCleanupEnabled());
    if(!Definition)return O;
    O->SetStringField(TEXT("definition"),Definition->GetPathName());
    O->SetNumberField(TEXT("meshScale"),Definition->MeshRelativeTransform.GetScale3D().Z);
    if(Presentation&&Presentation->bPoseEvaluated)
    {
        const FName Head=VeyrBoneRoles::Resolve(Presentation,EVeyrBoneRole::Head);
        if(!Head.IsNone())O->SetNumberField(TEXT("headBoneAboveFloorCm"),Presentation->GetBoneLocation(Head).Z-FloorZ);
        if(Active)
        {
            const FVector Bottom=Presentation->GetBoneLocation(SwordBottomBone),Top=Presentation->GetBoneLocation(SwordTopBone);
            O->SetNumberField(TEXT("swordBoneLengthCm"),FVector::Distance(Bottom,Top));
        }
    }
    return O;
}
