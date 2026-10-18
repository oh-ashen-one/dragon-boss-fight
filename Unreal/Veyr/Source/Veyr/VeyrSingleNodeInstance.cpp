#include "VeyrSingleNodeInstance.h"
#include "Animation/AnimSingleNodeInstanceProxy.h"
#include "Animation/AnimationPoseData.h"
#include "Animation/AttributesRuntime.h"
#include "AnimationRuntime.h"

namespace
{
    // All persisted data use heap allocators. Never retain an FPoseContext or
    // its MemStack-backed pose/curve/attribute storage between evaluations.
    struct FVeyrPoseSnapshot
    {
        TArray<FTransform> LocalTransforms;
        TArray<FBoneIndexType> BoneMap;
        TWeakObjectPtr<UObject> LayoutAsset;
        FBlendedHeapCurve Curve;
        UE::Anim::FHeapAttributeContainer Attributes;
        bool bValid=false;

        void Capture(const FPoseContext& Pose)
        {
            LocalTransforms=Pose.Pose.GetBones();
            BoneMap=Pose.Pose.GetBoneContainer().GetBoneIndicesArray();
            LayoutAsset=Pose.Pose.GetBoneContainer().GetAsset();
            Curve.CopyFrom(Pose.Curve);
            Attributes.CopyFrom(Pose.CustomAttributes);
            bValid=true;
        }

        void CopyFrom(const FVeyrPoseSnapshot& Other)
        {
            LocalTransforms=Other.LocalTransforms;BoneMap=Other.BoneMap;LayoutAsset=Other.LayoutAsset;
            Curve.CopyFrom(Other.Curve);Attributes.CopyFrom(Other.Attributes);bValid=Other.bValid;
        }

        bool Matches(const FPoseContext& Pose) const
        {
            return bValid&&LayoutAsset.Get()==Pose.Pose.GetBoneContainer().GetAsset()&&
                BoneMap==Pose.Pose.GetBoneContainer().GetBoneIndicesArray()&&LocalTransforms.Num()==Pose.Pose.GetNumBones();
        }
    };

    struct FVeyrSingleNodeProxy final : FAnimSingleNodeInstanceProxy
    {
        explicit FVeyrSingleNodeProxy(UAnimInstance* Instance):FAnimSingleNodeInstanceProxy(Instance){}
        FVeyrPoseSnapshot LastPublished,TransitionSource;
        float Alpha=1.f;
        FString EvaluationError;
        uint64 EvaluationSerial=0;

        virtual void Initialize(UAnimInstance* Instance) override
        {
            FAnimSingleNodeInstanceProxy::Initialize(Instance);
            LastPublished.bValid=TransitionSource.bValid=false;Alpha=1.f;
            EvaluationError.Reset();EvaluationSerial=0;
        }

        virtual bool Evaluate(FPoseContext& Output) override
        {
            ++EvaluationSerial;
            EvaluationError.Reset();
            FAnimSingleNodeInstanceProxy::Evaluate(Output);
            if(Alpha<1.f)
            {
                if(!TransitionSource.Matches(Output))
                {
                    EvaluationError=TEXT("Transition source pose is missing or its mesh/bone layout changed");
                    LastPublished.bValid=false;
                    return true;
                }
                FPoseContext Source(Output);
                Source.Pose.CopyBonesFrom(TransitionSource.LocalTransforms);
                Source.Curve.CopyFrom(TransitionSource.Curve);
                Source.CustomAttributes.CopyFrom(TransitionSource.Attributes);
                if(Alpha<=0.f)
                {
                    // Exact endpoint, including curves/attributes: no weighted
                    // blend normalization drift on a repeated alpha-zero sample.
                    Output.Pose.CopyBonesFrom(Source.Pose);
                    Output.Curve.CopyFrom(Source.Curve);
                    Output.CustomAttributes.CopyFrom(Source.CustomAttributes);
                }
                else
                {
                    FAnimationPoseData DestinationData(Output),SourceData(Source);
                    FAnimationRuntime::BlendTwoPosesTogetherInPlace(DestinationData,SourceData,Alpha);
                }
            }
            if(Output.ContainsNaN())
            {
                EvaluationError=TEXT("Explicit pose transition produced a non-finite pose");
                LastPublished.bValid=false;
                return true;
            }
            // Capture AFTER blending so an interrupted transition starts from
            // the current blended pose, not the previous clip's endpoint.
            LastPublished.Capture(Output);
            return true;
        }
    };
}

FAnimInstanceProxy* UVeyrSingleNodeInstance::CreateAnimInstanceProxy()
{
    return new FVeyrSingleNodeProxy(this);
}

bool UVeyrSingleNodeInstance::CaptureTransitionSource()
{
    if(!IsInGameThread())return false;
    auto& Proxy=GetProxyOnGameThread<FVeyrSingleNodeProxy>();
    if(!Proxy.LastPublished.bValid)return false;
    Proxy.TransitionSource.CopyFrom(Proxy.LastPublished);
    return true;
}

bool UVeyrSingleNodeInstance::SetExplicitTransitionAlpha(float Alpha)
{
    if(!IsInGameThread()||!FMath::IsFinite(Alpha)||Alpha<0.f||Alpha>1.f)return false;
    auto& Proxy=GetProxyOnGameThread<FVeyrSingleNodeProxy>();
    if(Alpha<1.f&&!Proxy.TransitionSource.bValid)return false;
    Proxy.Alpha=Alpha;
    return true;
}

void UVeyrSingleNodeInstance::ClearTransitionSource()
{
    check(IsInGameThread());
    auto& Proxy=GetProxyOnGameThread<FVeyrSingleNodeProxy>();
    Proxy.TransitionSource.bValid=false;Proxy.Alpha=1.f;
}

bool UVeyrSingleNodeInstance::HasTransitionSource() const
{
    return GetProxyOnGameThread<FVeyrSingleNodeProxy>().TransitionSource.bValid;
}

FString UVeyrSingleNodeInstance::GetExplicitEvaluationError() const
{
    return GetProxyOnGameThread<FVeyrSingleNodeProxy>().EvaluationError;
}

uint64 UVeyrSingleNodeInstance::GetExplicitEvaluationSerial() const
{
    return GetProxyOnGameThread<FVeyrSingleNodeProxy>().EvaluationSerial;
}
