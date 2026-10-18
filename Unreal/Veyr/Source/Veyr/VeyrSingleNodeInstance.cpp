#include "VeyrSingleNodeInstance.h"
#include "Animation/AnimSingleNodeInstanceProxy.h"
#include "Animation/AnimationPoseData.h"
#include "Animation/AttributesRuntime.h"
#include "Animation/AnimSequence.h"
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
        UAnimSequence* LowerSequence=nullptr; // Owned by UVeyrSingleNodeInstance UPROPERTY.
        float LowerSeconds=0.f,LowerWeight=0.f;
        TWeakObjectPtr<UObject> MaskAsset;
        TArray<FBoneIndexType> MaskBoneMap;
        TArray<float> LowerMask,LowerWeights;

        bool EnsureLowerMask(const FPoseContext& Output)
        {
            const FBoneContainer& Bones=Output.Pose.GetBoneContainer();
            if(MaskAsset.Get()==Bones.GetAsset()&&MaskBoneMap==Bones.GetBoneIndicesArray()&&LowerMask.Num()==Output.Pose.GetNumBones())return true;
            const FReferenceSkeleton& Reference=Bones.GetReferenceSkeleton();
            const int32 Hips=Reference.FindBoneIndex(TEXT("Hips"));
            const int32 Left=Reference.FindBoneIndex(TEXT("LeftUpLeg")),Right=Reference.FindBoneIndex(TEXT("RightUpLeg"));
            const int32 Spine=Reference.FindBoneIndex(TEXT("Spine"));
            auto DescendsFrom=[&](int32 Bone,int32 Root)
            {
                while(Bone!=INDEX_NONE)
                {
                    if(Bone==Root)return true;
                    Bone=Reference.GetParentIndex(Bone);
                }
                return false;
            };
            if(Hips==INDEX_NONE||Left==INDEX_NONE||Right==INDEX_NONE||Spine==INDEX_NONE||
                !DescendsFrom(Left,Hips)||!DescendsFrom(Right,Hips)||!DescendsFrom(Spine,Hips)||
                DescendsFrom(Spine,Left)||DescendsFrom(Spine,Right))
            {
                EvaluationError=TEXT("Lower-body mask requires Hips, LeftUpLeg, RightUpLeg and a separate Spine subtree");
                return false;
            }
            const auto& Map=Bones.GetBoneIndicesArray();
            if(!Map.Contains(static_cast<FBoneIndexType>(Hips))||!Map.Contains(static_cast<FBoneIndexType>(Left))||
                !Map.Contains(static_cast<FBoneIndexType>(Right))||!Map.Contains(static_cast<FBoneIndexType>(Spine)))
            {
                EvaluationError=TEXT("Required lower-body mask roots are absent from the evaluated bone layout");
                return false;
            }
            LowerMask.SetNumZeroed(Output.Pose.GetNumBones());
            for(FCompactPoseBoneIndex Index:Output.Pose.ForEachBoneIndex())
            {
                const int32 MeshIndex=Bones.MakeMeshPoseIndex(Index).GetInt();
                LowerMask[Index.GetInt()]=(MeshIndex==Hips||DescendsFrom(MeshIndex,Left)||DescendsFrom(MeshIndex,Right))?1.f:0.f;
            }
            MaskAsset=Bones.GetAsset();MaskBoneMap=Map;
            return true;
        }

        bool ApplyLowerBody(FPoseContext& Output)
        {
            if(!LowerSequence)return true;
            // Validate the mask even at weight zero: missing layer inputs must
            // not appear accepted merely because the fade has not started yet.
            if(!EnsureLowerMask(Output))return false;
            if(LowerWeight<=0.f)return true;
            FPoseContext Lower(Output),Composed(Output);
            FAnimationPoseData LowerData(Lower);
            LowerSequence->GetAnimationPose(LowerData,FAnimExtractContext(static_cast<double>(LowerSeconds),false));
            if(Lower.ContainsNaN())
            {
                EvaluationError=TEXT("Lower-body sequence produced a non-finite pose");return false;
            }
            LowerWeights.SetNumUninitialized(LowerMask.Num());
            for(int32 I=0;I<LowerMask.Num();++I)LowerWeights[I]=LowerMask[I]*LowerWeight;
            FAnimationRuntime::BlendTwoPosesTogetherPerBone(Output.Pose,Lower.Pose,LowerWeights,Composed.Pose);
            // The engine blend normalizes every bone, including untouched
            // bones. Preserve exact endpoints and unchanged upper local bones.
            for(FCompactPoseBoneIndex Index:Output.Pose.ForEachBoneIndex())
            {
                if(LowerWeights[Index.GetInt()]==0.f)Composed.Pose[Index]=Output.Pose[Index];
                else if(LowerWeights[Index.GetInt()]==1.f)Composed.Pose[Index]=Lower.Pose[Index];
            }
            UE::Anim::Attributes::BlendAttributesPerBone(Output.CustomAttributes,Lower.CustomAttributes,LowerWeights,Composed.CustomAttributes);
            Output.Pose.CopyBonesFrom(Composed.Pose);
            Output.CustomAttributes.CopyFrom(Composed.CustomAttributes);
            // Retain upper curves exactly. The full FAnimationPoseData overload
            // combines lower curves globally, regardless of the per-bone mask.
            return true;
        }

        virtual void Initialize(UAnimInstance* Instance) override
        {
            FAnimSingleNodeInstanceProxy::Initialize(Instance);
            LastPublished.bValid=TransitionSource.bValid=false;Alpha=1.f;
            EvaluationError.Reset();EvaluationSerial=0;
            LowerSequence=nullptr;LowerSeconds=LowerWeight=0.f;
            MaskAsset.Reset();MaskBoneMap.Reset();LowerMask.Reset();LowerWeights.Reset();
        }

        virtual bool Evaluate(FPoseContext& Output) override
        {
            ++EvaluationSerial;
            EvaluationError.Reset();
            FAnimSingleNodeInstanceProxy::Evaluate(Output);
            if(!ApplyLowerBody(Output))
            {
                LastPublished.bValid=false;return true;
            }
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

bool UVeyrSingleNodeInstance::SetExplicitLowerBody(UAnimSequence* Sequence,float SequenceSeconds,float Weight)
{
    if(!IsInGameThread()||!Sequence||!FMath::IsFinite(SequenceSeconds)||SequenceSeconds<0.f||
        !FMath::IsFinite(Weight)||Weight<0.f||Weight>1.f)return false;
    auto& Proxy=GetProxyOnGameThread<FVeyrSingleNodeProxy>();
    ExplicitLowerSequence=Sequence;Proxy.LowerSequence=Sequence;
    Proxy.LowerSeconds=SequenceSeconds;Proxy.LowerWeight=Weight;
    return true;
}

void UVeyrSingleNodeInstance::ClearExplicitLowerBody()
{
    check(IsInGameThread());
    auto& Proxy=GetProxyOnGameThread<FVeyrSingleNodeProxy>();
    Proxy.LowerSequence=nullptr;Proxy.LowerSeconds=Proxy.LowerWeight=0.f;
    ExplicitLowerSequence=nullptr;
}
