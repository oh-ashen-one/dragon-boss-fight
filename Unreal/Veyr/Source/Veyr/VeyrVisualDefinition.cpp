#include "VeyrVisualDefinition.h"
#include "Engine/SkeletalMesh.h"
#include "Animation/AnimSequence.h"

TArray<FName> UVeyrVisualDefinition::GetImportedBoneNames() const
{
    TArray<FName> Names;
    if(SkeletalMesh)
        for(const FMeshBoneInfo& Bone:SkeletalMesh->GetRefSkeleton().GetRefBoneInfo())Names.Add(Bone.Name);
    return Names;
}

TMap<FName,FTransform> UVeyrVisualDefinition::GetImportedReferenceBoneTransforms() const
{
    TMap<FName,FTransform> Result;
    if(!SkeletalMesh)return Result;
    const FReferenceSkeleton& Reference=SkeletalMesh->GetRefSkeleton();
    TArray<FTransform> ComponentPose=Reference.GetRefBonePose();
    for(int32 Index=0;Index<ComponentPose.Num();++Index)
    {
        const int32 Parent=Reference.GetParentIndex(Index);
        if(Parent!=INDEX_NONE)ComponentPose[Index]=ComponentPose[Index]*ComponentPose[Parent];
        Result.Add(Reference.GetBoneName(Index),ComponentPose[Index]);
    }
    return Result;
}

FVector UVeyrVisualDefinition::GetImportedBoundsOrigin() const
{
    return SkeletalMesh?SkeletalMesh->GetImportedBounds().Origin:FVector::ZeroVector;
}

FVector UVeyrVisualDefinition::GetImportedBoundsExtent() const
{
    return SkeletalMesh?SkeletalMesh->GetImportedBounds().BoxExtent:FVector::ZeroVector;
}

TArray<FString> UVeyrVisualDefinition::ValidateDefinition(bool bRequireCompleteMoveset) const
{
    TArray<FString> Errors;
    if(!SkeletalMesh){Errors.Add(TEXT("SkeletalMesh is missing"));return Errors;}
    if(!SkeletalMesh->GetSkeleton())Errors.Add(TEXT("Imported mesh has no skeleton"));
    if(MeshRelativeTransform.ContainsNaN()||MeshRelativeTransform.GetScale3D().GetMin()<=0.f)
        Errors.Add(TEXT("Mesh transform must be finite with positive scale"));
    if(BoneTargets.IsEmpty())Errors.Add(TEXT("No measured bone targets supplied"));
    for(const auto& Target:BoneTargets)
    {
        if(SkeletalMesh->GetRefSkeleton().FindBoneIndex(Target.Value.BoneName)==INDEX_NONE)
            Errors.Add(FString::Printf(TEXT("Bone target %s references missing bone %s"),*Target.Key.ToString(),*Target.Value.BoneName.ToString()));
        if(Target.Value.LocalOffset.ContainsNaN())Errors.Add(TEXT("Bone target contains a non-finite offset"));
    }
    for(FName Required:RequiredBoneTargets)
        if(!BoneTargets.Contains(Required))Errors.Add(TEXT("Required bone target missing: ")+Required.ToString());
    for(const auto& Entry:Clips)
    {
        const FVeyrVisualClip& Clip=Entry.Value;
        if(!Clip.Sequence){Errors.Add(TEXT("Clip asset missing: ")+Entry.Key.ToString());continue;}
        if(Clip.Sequence->GetSkeleton()!=SkeletalMesh->GetSkeleton())
            Errors.Add(TEXT("Clip uses a different skeleton: ")+Entry.Key.ToString());
        const float End=Clip.EndSeconds<0?Clip.Sequence->GetPlayLength():Clip.EndSeconds;
        if(!FMath::IsFinite(Clip.StartSeconds)||!FMath::IsFinite(Clip.EndSeconds)||!FMath::IsFinite(Clip.ImpactSeconds)||
           Clip.StartSeconds<0||End<=Clip.StartSeconds||End>Clip.Sequence->GetPlayLength()||
           (Clip.ImpactSeconds>=0&&(Clip.ImpactSeconds<Clip.StartSeconds||Clip.ImpactSeconds>End)))
            Errors.Add(TEXT("Clip timing invalid: ")+Entry.Key.ToString());
        for(const FVector2D& Window:Clip.DamageWindows)
            if(!FMath::IsFinite(Window.X)||!FMath::IsFinite(Window.Y)||Window.X<0||Window.Y<=Window.X||Window.Y>End-Clip.StartSeconds+.001f)
                Errors.Add(TEXT("Damage window invalid: ")+Entry.Key.ToString());
        if(!Clip.RootTranslationSamplesCm.IsEmpty()&&(!FMath::IsFinite(Clip.RootSampleRate)||Clip.RootSampleRate<=0.f))
            Errors.Add(TEXT("Root sample rate invalid: ")+Entry.Key.ToString());
        for(const FVector& Point:Clip.RootTranslationSamplesCm)
            if(Point.ContainsNaN())Errors.Add(TEXT("Nonfinite root path: ")+Entry.Key.ToString());
    }
    if(bRequireCompleteMoveset)
        for(FName Required:RequiredClips)
            if(!Clips.Contains(Required))Errors.Add(TEXT("Required clip missing: ")+Required.ToString());
    return Errors;
}
