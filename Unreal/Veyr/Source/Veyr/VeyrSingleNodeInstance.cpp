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
        bool bRootSpaceBlend=false;
        UAnimSequence* TransitionSequence=nullptr;
        float TransitionSeconds=0.f;
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
        bool bMirrorRepair=false;
        TSet<FName> MirrorRestBones,MirrorTranslatingBones;
        int32 MirrorRepairEvaluations=0;
        // F2 (2026-11-18): the moving transition source gets the same clean-up as the destination.
        bool bTransitionMirrorRepair=false,bTransitionCleanup=false;
        // F4: planar Spine_0 offsets removed from each pose (component cm), the actor carries them instead.
        FVector RootOffsetDest=FVector::ZeroVector,RootOffsetSource=FVector::ZeroVector;
        // F3: generic two-bone leg locks (dragon). Target = animated end-bone position + Delta * Weight.
        TArray<FVeyrLegLock> LegLocks;
        TArray<float> LegLockMissCm;
        FVector LegLockBends[4]={FVector(1,0,0),FVector(1,0,0),FVector(1,0,0),FVector(1,0,0)};
        // Review M7: the outgoing clip's aim/flinch layer, kept for the moving transition source.
        TMap<FName,FRotator> SourceBoneRotations,PublishedBoneRotations;
        FString LegLockError;

        void ApplyMirrorRepair(FPoseContext& Output){ApplyMirrorRepairIf(Output,bMirrorRepair);}
        void ApplyMirrorRepairIf(FPoseContext& Output,bool bEnabled)
        {
            if(!bEnabled)return;
            const FBoneContainer& Bones=Output.Pose.GetBoneContainer();
            const FReferenceSkeleton& Reference=Bones.GetReferenceSkeleton();
            for(FCompactPoseBoneIndex Index:Output.Pose.ForEachBoneIndex())
            {
                if(Bones.GetParentBoneIndex(Index).GetInt()==INDEX_NONE)continue;
                const FName Name=Reference.GetBoneName(Bones.MakeMeshPoseIndex(Index).GetInt());
                const FTransform& Rest=Bones.GetRefPoseTransform(Index);
                if(MirrorRestBones.Contains(Name))Output.Pose[Index]=Rest;
                else if(!MirrorTranslatingBones.Contains(Name))Output.Pose[Index].SetTranslation(Rest.GetTranslation());
            }
            ++MirrorRepairEvaluations;
        }

        bool RebaseRootForBlend(FPoseContext& Pose)
        {
            const FBoneContainer& Bones=Pose.Pose.GetBoneContainer();
            const int32 MeshIndex=Bones.GetReferenceSkeleton().FindBoneIndex(TEXT("VeyrRoot"));
            if(MeshIndex==INDEX_NONE){EvaluationError=TEXT("Root-space blend requires the canonical VeyrRoot");return false;}
            const FCompactPoseBoneIndex Root=Bones.MakeCompactPoseIndex(FMeshPoseBoneIndex(MeshIndex));
            if(Root.GetInt()==INDEX_NONE||Bones.GetParentBoneIndex(Root).GetInt()!=INDEX_NONE||
               !Pose.Pose[Root].GetScale3D().Equals(FVector::OneVector,.0001f))
            {EvaluationError=TEXT("Root-space blend requires an unscaled hierarchy root");return false;}
            const FTransform RootTransform=Pose.Pose[Root];
            // VeyrRoot is nondeforming in the canonical knight. Move its
            // transform into each direct child before interpolation. Their
            // component poses are unchanged, and all lower local bone lengths
            // remain intact. This avoids blending counter-rotating root/hips
            // separately through large arcs during authored-turn transitions.
            for(FCompactPoseBoneIndex Index:Pose.Pose.ForEachBoneIndex())
                if(Bones.GetParentBoneIndex(Index)==Root)
                {Pose.Pose[Index]=Pose.Pose[Index]*RootTransform;Pose.Pose[Index].NormalizeRotation();}
            Pose.Pose[Root]=FTransform::Identity;
            return true;
        }

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

        bool ApplyBoneRotations(FPoseContext& Output){return ApplyBoneRotationsFrom(Output,BoneRotations);}
        bool ApplyBoneRotationsFrom(FPoseContext& Output,const TMap<FName,FRotator>& Rotations)
        {
            if(Rotations.IsEmpty())return true;
            const FBoneContainer& Bones=Output.Pose.GetBoneContainer();
            const FReferenceSkeleton& Reference=Bones.GetReferenceSkeleton();
            TMap<int32,FQuat> Deltas;
            for(const auto& Entry:Rotations)
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

        void ApplySpine0Fix(FPoseContext& Pose)
        {
            const FBoneContainer& WalkBones=Pose.Pose.GetBoneContainer();
            const int32 Spine0Mesh=WalkBones.GetReferenceSkeleton().FindBoneIndex(TEXT("tripo__Spine_0"));
            if(Spine0Mesh==INDEX_NONE)return;
            const FCompactPoseBoneIndex Spine0=WalkBones.MakeCompactPoseIndex(FMeshPoseBoneIndex(Spine0Mesh));
            if(Spine0.GetInt()!=INDEX_NONE&&Pose.Pose[Spine0].GetTranslation().Y>25.f)
                Pose.Pose[Spine0].AddToTranslation(FVector(12.44f,-38.99f,0.f));
        }

        /** Component-space transform of a compact bone (walks the parent chain). */
        static FTransform ComponentOf(const FPoseContext& Pose,FCompactPoseBoneIndex Index)
        {
            const FBoneContainer& Bones=Pose.Pose.GetBoneContainer();
            FTransform Result=FTransform::Identity;
            while(Index.GetInt()!=INDEX_NONE){Result=Result*Pose.Pose[Index];Index=Bones.GetParentBoneIndex(Index);}
            return Result;
        }

        void ApplyRootOffset(FPoseContext& Pose,const FVector& Offset)
        {
            if(Offset.IsNearlyZero(.001))return;
            const FBoneContainer& Bones=Pose.Pose.GetBoneContainer();
            const int32 Mesh=Bones.GetReferenceSkeleton().FindBoneIndex(TEXT("tripo__Spine_0"));
            if(Mesh==INDEX_NONE)return;
            const FCompactPoseBoneIndex Spine0=Bones.MakeCompactPoseIndex(FMeshPoseBoneIndex(Mesh));
            if(Spine0.GetInt()==INDEX_NONE)return;
            const FCompactPoseBoneIndex Parent=Bones.GetParentBoneIndex(Spine0);
            const FTransform ParentCS=Parent.GetInt()==INDEX_NONE?FTransform::Identity:ComponentOf(Pose,Parent);
            // Move the body bone by -Offset in component space; every descendant follows.
            Pose.Pose[Spine0].AddToTranslation(ParentCS.InverseTransformVector(-Offset));
        }

        bool ApplyLegLocks(FPoseContext& Output)
        {
            LegLockMissCm.SetNumZeroed(LegLocks.Num());
            if(LegLocks.IsEmpty())return true;
            const FBoneContainer& Bones=Output.Pose.GetBoneContainer();
            const FReferenceSkeleton& Ref=Bones.GetReferenceSkeleton();
            TArray<FTransform> CS;CS.SetNum(Output.Pose.GetNumBones());
            for(FCompactPoseBoneIndex I:Output.Pose.ForEachBoneIndex())
            {
                const auto Parent=Bones.GetParentBoneIndex(I);
                CS[I.GetInt()]=Parent.GetInt()==INDEX_NONE?Output.Pose[I]:Output.Pose[I]*CS[Parent.GetInt()];
            }
            for(int32 L=0;L<LegLocks.Num();++L)
            {
                const FVeyrLegLock& Lock=LegLocks[L];
                if(Lock.Weight<=0.f||Lock.Delta.IsNearlyZero(.01))continue;
                FCompactPoseBoneIndex Idx[3];
                for(int32 J=0;J<3;++J)
                {
                    const int32 Mesh=Ref.FindBoneIndex(Lock.Bones[J]);
                    Idx[J]=Mesh==INDEX_NONE?FCompactPoseBoneIndex(INDEX_NONE):Bones.MakeCompactPoseIndex(FMeshPoseBoneIndex(Mesh));
                    if(Idx[J].GetInt()==INDEX_NONE){LegLockError=TEXT("Leg lock bone missing: ")+Lock.Bones[J].ToString();return true;}
                }
                if(Bones.GetParentBoneIndex(Idx[2])!=Idx[1]||Bones.GetParentBoneIndex(Idx[1])!=Idx[0])
                {LegLockError=TEXT("Leg lock needs a direct three-bone chain at ")+Lock.Bones[0].ToString();return true;}
                FTransform Upper=CS[Idx[0].GetInt()],Knee=CS[Idx[1].GetInt()],End=CS[Idx[2].GetInt()];
                const FQuat EndRotation=End.GetRotation();
                const FVector Target=End.GetLocation()+Lock.Delta*FMath::Clamp(Lock.Weight,0.f,1.f);
                // Bend plane: the move's own knee direction.
                const FVector Mid=(Upper.GetLocation()+End.GetLocation())*.5;
                FVector Bend=Knee.GetLocation()-Mid;
                if(Bend.SizeSquared()<1.0)Bend=LegLockBends[L%4];else LegLockBends[L%4]=Bend; // review L3
                const FVector Pole=Knee.GetLocation()+Bend.GetSafeNormal()*100.f;
                const FTransform OldEnd=End;
                AnimationCore::SolveTwoBoneIK(Upper,Knee,End,Pole,Target,false,1.,1.);
                End.SetRotation(EndRotation); // paw/hoof keeps its own orientation; toes ride it
                LegLockMissCm[L]=static_cast<float>(FVector::Distance(End.GetLocation(),Target));
                const auto Parent=Bones.GetParentBoneIndex(Idx[0]);
                const FTransform ParentCS=Parent.GetInt()==INDEX_NONE?FTransform::Identity:CS[Parent.GetInt()];
                Output.Pose[Idx[0]]=Upper.GetRelativeTransform(ParentCS);
                Output.Pose[Idx[1]]=Knee.GetRelativeTransform(Upper);
                Output.Pose[Idx[2]]=End.GetRelativeTransform(Knee);
                for(int32 J=0;J<3;++J)Output.Pose[Idx[J]].NormalizeRotation();
                // Review H2: paw bones hanging off the knee beside the end bone follow the end bone, not the shin.
                for(const FName Rider:Lock.Riders)
                {
                    if(Rider.IsNone())continue;
                    const int32 Mesh=Ref.FindBoneIndex(Rider);
                    const FCompactPoseBoneIndex R=Mesh==INDEX_NONE?FCompactPoseBoneIndex(INDEX_NONE):Bones.MakeCompactPoseIndex(FMeshPoseBoneIndex(Mesh));
                    if(R.GetInt()==INDEX_NONE||Bones.GetParentBoneIndex(R)!=Idx[1])
                    {LegLockError=TEXT("Leg lock rider is not a child of the knee: ")+Rider.ToString();continue;}
                    const FTransform NewRider=CS[R.GetInt()].GetRelativeTransform(OldEnd)*End;
                    Output.Pose[R]=NewRider.GetRelativeTransform(Knee);Output.Pose[R].NormalizeRotation();
                    CS[R.GetInt()]=NewRider;
                }
                // Children of the chain read CS lazily below only through Output; refresh the three entries.
                CS[Idx[0].GetInt()]=Upper;CS[Idx[1].GetInt()]=Knee;CS[Idx[2].GetInt()]=End;
            }
            return true;
        }

        virtual void Initialize(UAnimInstance* Instance) override
        {
            FAnimSingleNodeInstanceProxy::Initialize(Instance);
            LastPublished.bValid=TransitionSource.bValid=false;Alpha=1.f;
            EvaluationError.Reset();EvaluationSerial=0;
            LowerSequence=nullptr;LowerSeconds=LowerWeight=0.f;BoneRotations.Reset();
            TransitionSequence=nullptr;TransitionSeconds=0.f;
            FootTargets.Reset();FootWeights.Reset();
            bMirrorRepair=false;MirrorRestBones.Reset();MirrorTranslatingBones.Reset();MirrorRepairEvaluations=0;
            bTransitionMirrorRepair=bTransitionCleanup=false;RootOffsetDest=RootOffsetSource=FVector::ZeroVector;
            LegLocks.Reset();LegLockMissCm.Reset();LegLockError.Reset();
            MaskAsset.Reset();MaskBoneMap.Reset();LowerMask.Reset();LowerWeights.Reset();
        }

        virtual bool Evaluate(FPoseContext& Output) override
        {
            ++EvaluationSerial;
            EvaluationError.Reset();
            FAnimSingleNodeInstanceProxy::Evaluate(Output);
            ApplySpine0Fix(Output);
            ApplyMirrorRepair(Output);
            ApplyRootOffset(Output,RootOffsetDest);
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
                if(TransitionSequence)
                {
                    // Caller supplies both clocks. Evaluating the outgoing
                    // locomotion avoids carrying a frozen planted foot with
                    // the moving capsule during a run/stop crossfade.
                    FAnimationPoseData SourceData(Source);
                    TransitionSequence->GetAnimationPose(SourceData,FAnimExtractContext(static_cast<double>(TransitionSeconds),false));
                    if(Source.ContainsNaN()){EvaluationError=TEXT("Continuous transition source produced a non-finite pose");LastPublished.bValid=false;return true;}
                    if(bTransitionCleanup)
                    {
                        // F2: same Spine_0 fix, mirror repair, root-track offset and aim rotations as the destination,
                        // so a moving source never pops when its weight changes.
                        ApplySpine0Fix(Source);
                        ApplyMirrorRepairIf(Source,bTransitionMirrorRepair);
                        ApplyRootOffset(Source,RootOffsetSource);
                        if(!ApplyBoneRotationsFrom(Source,SourceBoneRotations)){LastPublished.bValid=false;return true;}
                    }
                }
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
                    // Alpha0 and1 remain exact original local-pose endpoints.
                    // Only the intermediate blend changes representation.
                    if(bRootSpaceBlend&&(!RebaseRootForBlend(Output)||!RebaseRootForBlend(Source)))
                    {LastPublished.bValid=false;return true;}
                    FAnimationPoseData DestinationData(Output),SourceData(Source);
                    FAnimationRuntime::BlendTwoPosesTogetherInPlace(DestinationData,SourceData,Alpha);
                }
            }
            if(!ApplyFootTargets(Output)){LastPublished.bValid=false;return true;}
            if(!ApplyLegLocks(Output)){LastPublished.bValid=false;return true;}
            if(Output.ContainsNaN())
            {
                EvaluationError=TEXT("Explicit pose transition produced a non-finite pose");
                LastPublished.bValid=false;
                return true;
            }
            // Capture AFTER blending so an interrupted transition starts from
            // the current blended pose, not the previous clip's endpoint.
            LastPublished.Capture(Output);
            PublishedBoneRotations=BoneRotations;
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
    Proxy.TransitionSequence=nullptr;Proxy.TransitionSeconds=0.f;ExplicitTransitionSequence=nullptr;
    Proxy.bTransitionCleanup=Proxy.bTransitionMirrorRepair=false;
    Proxy.SourceBoneRotations=Proxy.PublishedBoneRotations; // review M7: the outgoing clip keeps its own aim layer
    return true;
}

bool UVeyrSingleNodeInstance::SetExplicitTransitionSequence(UAnimSequence* Sequence,float SequenceSeconds)
{
    if(!IsInGameThread()||!Sequence||!FMath::IsFinite(SequenceSeconds)||SequenceSeconds<0.f||SequenceSeconds>Sequence->GetPlayLength())return false;
    auto& Proxy=GetProxyOnGameThread<FVeyrSingleNodeProxy>();
    if(!Proxy.TransitionSource.bValid)return false;
    ExplicitTransitionSequence=Sequence;Proxy.TransitionSequence=Sequence;Proxy.TransitionSeconds=SequenceSeconds;
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

void UVeyrSingleNodeInstance::SetExplicitRootSpaceBlend(bool bEnabled)
{
    check(IsInGameThread());
    GetProxyOnGameThread<FVeyrSingleNodeProxy>().bRootSpaceBlend=bEnabled;
}

void UVeyrSingleNodeInstance::ClearTransitionSource()
{
    check(IsInGameThread());
    auto& Proxy=GetProxyOnGameThread<FVeyrSingleNodeProxy>();
    Proxy.TransitionSource.bValid=false;Proxy.Alpha=1.f;
    Proxy.TransitionSequence=nullptr;Proxy.TransitionSeconds=0.f;ExplicitTransitionSequence=nullptr;
    Proxy.bTransitionCleanup=Proxy.bTransitionMirrorRepair=false;
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
    if(!IsInGameThread()||Rotations.Num()>16)return false; // B5: gaze or aim plus the whole-spine flinch
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

void UVeyrSingleNodeInstance::SetExplicitMirrorRepair(bool bEnabled,const TArray<FName>& RestBones,const TArray<FName>& TranslatingBones)
{
    check(IsInGameThread());
    auto& Proxy=GetProxyOnGameThread<FVeyrSingleNodeProxy>();
    Proxy.bMirrorRepair=bEnabled;
    Proxy.MirrorRestBones.Reset();Proxy.MirrorRestBones.Append(RestBones);
    Proxy.MirrorTranslatingBones.Reset();Proxy.MirrorTranslatingBones.Append(TranslatingBones);
}

int32 UVeyrSingleNodeInstance::GetMirrorRepairEvaluations() const
{
    return GetProxyOnGameThread<FVeyrSingleNodeProxy>().MirrorRepairEvaluations;
}

void UVeyrSingleNodeInstance::SetExplicitTransitionCleanup(bool bEnabled,bool bSourceMirrorRepair)
{
    check(IsInGameThread());
    auto& P=GetProxyOnGameThread<FVeyrSingleNodeProxy>();P.bTransitionCleanup=bEnabled;P.bTransitionMirrorRepair=bSourceMirrorRepair;
}

void UVeyrSingleNodeInstance::SetExplicitRootOffsets(const FVector& Destination,const FVector& Source)
{
    check(IsInGameThread());
    auto& P=GetProxyOnGameThread<FVeyrSingleNodeProxy>();
    P.RootOffsetDest=Destination.ContainsNaN()?FVector::ZeroVector:Destination;P.RootOffsetSource=Source.ContainsNaN()?FVector::ZeroVector:Source;
}

bool UVeyrSingleNodeInstance::SetExplicitLegLocks(const TArray<FVeyrLegLock>& Locks)
{
    if(!IsInGameThread()||Locks.Num()>4)return false;
    for(const FVeyrLegLock& L:Locks)if(L.Delta.ContainsNaN()||!FMath::IsFinite(L.Weight))return false;
    auto& P=GetProxyOnGameThread<FVeyrSingleNodeProxy>();P.LegLocks=Locks;P.LegLockError.Reset();return true;
}

void UVeyrSingleNodeInstance::ClearExplicitLegLocks()
{
    if(!IsInGameThread())return;
    auto& P=GetProxyOnGameThread<FVeyrSingleNodeProxy>();P.LegLocks.Reset();
}

TArray<float> UVeyrSingleNodeInstance::GetLegLockMissCm() const
{
    return GetProxyOnGameThread<FVeyrSingleNodeProxy>().LegLockMissCm;
}

FString UVeyrSingleNodeInstance::GetLegLockError() const
{
    return GetProxyOnGameThread<FVeyrSingleNodeProxy>().LegLockError;
}
