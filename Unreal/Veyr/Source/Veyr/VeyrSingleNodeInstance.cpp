#include "VeyrSingleNodeInstance.h"
#include "Animation/AnimSingleNodeInstanceProxy.h"
#include "Animation/AnimationPoseData.h"
#include "Animation/AttributesRuntime.h"
#include "Animation/AnimSequence.h"
#include "AnimationRuntime.h"
#include "Engine/SkeletalMesh.h"
#include "Animation/Skeleton.h"
#include "TwoBoneIK.h"

namespace
{
    // All persisted data use heap allocators. Never retain an FPoseContext or
    // its MemStack-backed pose/curve/attribute storage between evaluations.
    struct FVeyrPoseSnapshot
    {
        TArray<FTransform> LocalTransforms;
        TArray<FBoneIndexType> BoneMap;
        TWeakObjectPtr<UObject> LayoutAsset;
        TWeakObjectPtr<const USkeleton> LayoutSkeleton;
        TArray<FName> LayoutBoneNames;
        FBlendedHeapCurve Curve;
        UE::Anim::FHeapAttributeContainer Attributes;
        bool bValid=false;

        void Capture(const FPoseContext& Pose)
        {
            LocalTransforms=Pose.Pose.GetBones();
            BoneMap=Pose.Pose.GetBoneContainer().GetBoneIndicesArray();
            LayoutAsset=Pose.Pose.GetBoneContainer().GetAsset();
            const USkeletalMesh* Mesh=Cast<USkeletalMesh>(LayoutAsset.Get());
            LayoutSkeleton=Mesh?Mesh->GetSkeleton():nullptr;
            LayoutBoneNames.Reset();
            const auto& Reference=Pose.Pose.GetBoneContainer().GetReferenceSkeleton();
            for(int32 I=0;I<Reference.GetNum();++I)LayoutBoneNames.Add(Reference.GetBoneName(I));
            Curve.CopyFrom(Pose.Curve);
            Attributes.CopyFrom(Pose.CustomAttributes);
            bValid=true;
        }

        void CopyFrom(const FVeyrPoseSnapshot& Other)
        {
            LocalTransforms=Other.LocalTransforms;BoneMap=Other.BoneMap;LayoutAsset=Other.LayoutAsset;
            LayoutSkeleton=Other.LayoutSkeleton;LayoutBoneNames=Other.LayoutBoneNames;
            Curve.CopyFrom(Other.Curve);Attributes.CopyFrom(Other.Attributes);bValid=Other.bValid;
        }

        bool Matches(const FPoseContext& Pose) const
        {
            const auto& Container=Pose.Pose.GetBoneContainer();
            if(!bValid||BoneMap!=Container.GetBoneIndicesArray()||LocalTransforms.Num()!=Pose.Pose.GetNumBones())return false;
            if(LayoutAsset.Get()==Container.GetAsset())return true;
            const USkeletalMesh* Mesh=Cast<USkeletalMesh>(Container.GetAsset());
            if(!Mesh||!LayoutSkeleton.IsValid()||LayoutSkeleton.Get()!=Mesh->GetSkeleton())return false;
            const auto& Reference=Container.GetReferenceSkeleton();
            if(LayoutBoneNames.Num()!=Reference.GetNum())return false;
            for(int32 I=0;I<Reference.GetNum();++I)if(LayoutBoneNames[I]!=Reference.GetBoneName(I))return false;
            return true;
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
        TMap<FName,FRotator> BoneRotations;
        TArray<FTransform> FootTargets;
        TArray<float> FootWeights;

        bool ApplyFootTargets(FPoseContext& Output)
        {
            if(FootTargets.IsEmpty())return true;
            const FBoneContainer& Bones=Output.Pose.GetBoneContainer();
            const FReferenceSkeleton& Ref=Bones.GetReferenceSkeleton();
            TArray<FTransform> CS;CS.SetNum(Output.Pose.GetNumBones());
            for(FCompactPoseBoneIndex I:Output.Pose.ForEachBoneIndex())
            {
                const auto Parent=Bones.GetParentBoneIndex(I);
                CS[I.GetInt()]=Parent.GetInt()==INDEX_NONE?Output.Pose[I]:Output.Pose[I]*CS[Parent.GetInt()];
            }
            const TCHAR* Names[2][3]={{TEXT("LeftUpLeg"),TEXT("LeftLeg"),TEXT("LeftFoot")},{TEXT("RightUpLeg"),TEXT("RightLeg"),TEXT("RightFoot")}};
            for(int32 Side=0;Side<2;++Side)
            {
                if(FootWeights[Side]<=0.f)continue;
                FCompactPoseBoneIndex Indices[3];
                for(int32 J=0;J<3;++J)
                {
                    const int32 Mesh=Ref.FindBoneIndex(Names[Side][J]);
                    if(Mesh==INDEX_NONE){EvaluationError=TEXT("Foot IK bone missing");return false;}
                    Indices[J]=Bones.MakeCompactPoseIndex(FMeshPoseBoneIndex(Mesh));
                    if(Indices[J].GetInt()==INDEX_NONE){EvaluationError=TEXT("Foot IK bone not evaluated");return false;}
                }
                if(Bones.GetParentBoneIndex(Indices[2])!=Indices[1]||Bones.GetParentBoneIndex(Indices[1])!=Indices[0])
                {EvaluationError=TEXT("Foot IK requires direct two-bone leg chains");return false;}
                FTransform Upper=CS[Indices[0].GetInt()],Knee=CS[Indices[1].GetInt()],Foot=CS[Indices[2].GetInt()];
                const FQuat FootRotation=FQuat::Slerp(Foot.GetRotation(),FootTargets[Side].GetRotation(),FootWeights[Side]).GetNormalized();
                const FVector Target=FMath::Lerp(Foot.GetLocation(),FootTargets[Side].GetLocation(),FootWeights[Side]);
                const double UpperLength=FVector::Distance(Upper.GetLocation(),Knee.GetLocation());
                const double LowerLength=FVector::Distance(Knee.GetLocation(),Foot.GetLocation());
                const FVector Pole=Knee.GetLocation()+(Knee.GetLocation()-(Upper.GetLocation()+Foot.GetLocation())*.5).GetSafeNormal()*100.f;
                AnimationCore::SolveTwoBoneIK(Upper,Knee,Foot,Pole,Target,false,1.,1.);
                if(!FMath::IsNearlyEqual(FVector::Distance(Upper.GetLocation(),Knee.GetLocation()),UpperLength,.01)||
                   !FMath::IsNearlyEqual(FVector::Distance(Knee.GetLocation(),Foot.GetLocation()),LowerLength,.01))
                {EvaluationError=TEXT("Foot correction changed leg length");return false;}
                Foot.SetRotation(FootRotation);
                const auto Parent=Bones.GetParentBoneIndex(Indices[0]);
                Output.Pose[Indices[0]]=Parent.GetInt()==INDEX_NONE?Upper:Upper.GetRelativeTransform(CS[Parent.GetInt()]);
                Output.Pose[Indices[1]]=Knee.GetRelativeTransform(Upper);
                Output.Pose[Indices[2]]=Foot.GetRelativeTransform(Knee);
                for(int32 J=0;J<3;++J)Output.Pose[Indices[J]].NormalizeRotation();
            }
            return true;
        }

        bool ApplyBoneRotations(FPoseContext& Output)
        {
            if(BoneRotations.IsEmpty())return true;
            const FBoneContainer& Bones=Output.Pose.GetBoneContainer();
            const FReferenceSkeleton& Reference=Bones.GetReferenceSkeleton();
            TMap<int32,FQuat> Deltas;
            for(const auto& Entry:BoneRotations)
            {
                const int32 MeshIndex=Reference.FindBoneIndex(Entry.Key);
                if(MeshIndex==INDEX_NONE)
                {EvaluationError=TEXT("Rotation modifier bone is missing: ")+Entry.Key.ToString();return false;}
                const FCompactPoseBoneIndex Compact=Bones.MakeCompactPoseIndex(FMeshPoseBoneIndex(MeshIndex));
                if(Compact.GetInt()==INDEX_NONE)
                {EvaluationError=TEXT("Rotation modifier bone was not evaluated: ")+Entry.Key.ToString();return false;}
                Deltas.Add(Compact.GetInt(),Entry.Value.Quaternion());
            }
            // Traverse the complete compact hierarchy, carrying already modified
            // parent rotations. This changes local rotation only: no translated
            // or scaled links and no cosmetic post-publication bone override.
            TArray<FQuat> ComponentRotations;
            ComponentRotations.Init(FQuat::Identity,Output.Pose.GetNumBones());
            for(FCompactPoseBoneIndex Index:Output.Pose.ForEachBoneIndex())
            {
                const FCompactPoseBoneIndex Parent=Bones.GetParentBoneIndex(Index);
                if(Parent.GetInt()!=INDEX_NONE&&Parent.GetInt()>=Index.GetInt())
                {EvaluationError=TEXT("Rotation modifier requires parent-first compact bones");return false;}
                const FQuat ParentRotation=Parent.GetInt()==INDEX_NONE?FQuat::Identity:ComponentRotations[Parent.GetInt()];
                FTransform& Local=Output.Pose[Index];
                if(const FQuat* Delta=Deltas.Find(Index.GetInt()))
                    Local.SetRotation((ParentRotation.Inverse()*(*Delta)*ParentRotation*Local.GetRotation()).GetNormalized());
                ComponentRotations[Index.GetInt()]=(ParentRotation*Local.GetRotation()).GetNormalized();
            }
            return true;
        }

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
            LowerSequence=nullptr;LowerSeconds=LowerWeight=0.f;BoneRotations.Reset();
            FootTargets.Reset();FootWeights.Reset();
            MaskAsset.Reset();MaskBoneMap.Reset();LowerMask.Reset();LowerWeights.Reset();
        }

        virtual bool Evaluate(FPoseContext& Output) override
        {
            ++EvaluationSerial;
            EvaluationError.Reset();
            FAnimSingleNodeInstanceProxy::Evaluate(Output);
            if(!ApplyLowerBody(Output)||!ApplyBoneRotations(Output))
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
            if(!ApplyFootTargets(Output)){LastPublished.bValid=false;return true;}
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

bool UVeyrSingleNodeInstance::SetExplicitFootTargets(const TArray<FTransform>& Targets,const TArray<float>& Weights)
{
    if(!IsInGameThread()||Targets.Num()!=2||Weights.Num()!=2)return false;
    for(int32 I=0;I<2;++I)if(Targets[I].ContainsNaN()||!FMath::IsFinite(Weights[I])||Weights[I]<0.f||Weights[I]>1.f)return false;
    auto& P=GetProxyOnGameThread<FVeyrSingleNodeProxy>();P.FootTargets=Targets;P.FootWeights=Weights;return true;
}
void UVeyrSingleNodeInstance::ClearExplicitFootTargets()
{
    if(!IsInGameThread())return;
    auto& P=GetProxyOnGameThread<FVeyrSingleNodeProxy>();P.FootTargets.Reset();P.FootWeights.Reset();
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

bool UVeyrSingleNodeInstance::SetExplicitBoneRotations(const TMap<FName,FRotator>& Rotations)
{
    if(!IsInGameThread()||Rotations.Num()>4)return false;
    for(const auto& Entry:Rotations)
    {
        const FRotator& R=Entry.Value;
        if(Entry.Key.IsNone()||R.ContainsNaN()||FMath::Abs(R.Pitch)>20.f||
            FMath::Abs(R.Yaw)>20.f||FMath::Abs(R.Roll)>20.f||
            FMath::RadiansToDegrees(R.Quaternion().GetAngle())>25.f)return false;
    }
    GetProxyOnGameThread<FVeyrSingleNodeProxy>().BoneRotations=Rotations;
    return true;
}

void UVeyrSingleNodeInstance::ClearExplicitBoneRotations()
{
    check(IsInGameThread());
    GetProxyOnGameThread<FVeyrSingleNodeProxy>().BoneRotations.Reset();
}
