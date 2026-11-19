#include "VeyrDragonGrounding.h"
#include "VeyrDragon.h"
#include "VeyrSkeletalPresentation.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/World.h"
#include "CollisionQueryParams.h"

namespace
{
#include "VeyrDragonSolePoints.inl"
#include "VeyrDragonHullPoints.inl"

    TArray<FTransform> ReferenceComponentSpace(const FReferenceSkeleton& Reference)
    {
        const TArray<FTransform>& Local=Reference.GetRefBonePose();
        TArray<FTransform> Out;Out.SetNum(Local.Num());
        for(int32 I=0;I<Local.Num();++I)
        {
            const int32 Parent=Reference.GetParentIndex(I);
            Out[I]=Parent==INDEX_NONE?Local[I]:Local[I]*Out[Parent];
        }
        return Out;
    }

    /** Least-squares affine map from glTF rest heads (metres, Y up) to the imported reference pose
     * (component cm). Affine, so axis swaps, handedness and the import scale need no assumption. */
    bool FitGltfFrame(const FReferenceSkeleton& Reference,const TArray<FTransform>& Rest,double Map[3][4],float& Residual,int32& Joints,FString& Error)
    {
        FMatrix Normal(ForceInitToZero);double Rhs[3][4]={{0}};
        TArray<TPair<FVector,FVector>> Pairs;
        for(const FVeyrSoleJointHead& Head:GVeyrSoleJointHeads)
        {
            const int32 Bone=Reference.FindBoneIndex(FName(Head.Bone));
            if(Bone==INDEX_NONE)continue;
            const FVector G(Head.X,Head.Y,Head.Z),U=Rest[Bone].GetLocation();
            const double X[4]={G.X,G.Y,G.Z,1.0};
            for(int32 R=0;R<4;++R){for(int32 C=0;C<4;++C)Normal.M[R][C]+=X[R]*X[C];for(int32 K=0;K<3;++K)Rhs[K][R]+=X[R]*U[K];}
            Pairs.Emplace(G,U);
        }
        Joints=Pairs.Num();
        if(Pairs.Num()<12){Error=FString::Printf(TEXT("Only %d glTF joints found"),Pairs.Num());return false;}
        if(FMath::Abs(Normal.Determinant())<1e-12){Error=TEXT("Degenerate glTF joint fit");return false;}
        const FMatrix Inverse=Normal.Inverse();
        for(int32 K=0;K<3;++K)for(int32 C=0;C<4;++C){double V=0;for(int32 R=0;R<4;++R)V+=Inverse.M[C][R]*Rhs[K][R];Map[K][C]=V;}
        double Sum=0;
        for(const auto& P:Pairs)
        {
            const FVector G=P.Key;
            const FVector A(Map[0][0]*G.X+Map[0][1]*G.Y+Map[0][2]*G.Z+Map[0][3],Map[1][0]*G.X+Map[1][1]*G.Y+Map[1][2]*G.Z+Map[1][3],Map[2][0]*G.X+Map[2][1]*G.Y+Map[2][2]*G.Z+Map[2][3]);
            Sum+=FVector::DistSquared(A,P.Value);
        }
        Residual=static_cast<float>(FMath::Sqrt(Sum/Pairs.Num()));
        // The dragon rest pose is about 49 imported cm tall; 0.5 cm RMS is about 1 % of it.
        if(Residual>.5f){Error=FString::Printf(TEXT("glTF frame fit residual %.3f imported cm is too large"),Residual);return false;}
        return true;
    }
    FVector ApplyMap(const double Map[3][4],const FVector& G)
    {
        return FVector(Map[0][0]*G.X+Map[0][1]*G.Y+Map[0][2]*G.Z+Map[0][3],Map[1][0]*G.X+Map[1][1]*G.Y+Map[1][2]*G.Z+Map[1][3],Map[2][0]*G.X+Map[2][1]*G.Y+Map[2][2]*G.Z+Map[2][3]);
    }
}

bool FVeyrHullModel::Initialize(UVeyrSkeletalPresentation* Presentation)
{
    Points.Reset();FittedMesh.Reset();BoomPoints=GVeyrHullBoomWing+GVeyrHullBoomBody;BoomWing=GVeyrHullBoomWing;
    const USkeletalMesh* Mesh=Presentation?Presentation->GetSkeletalMeshAsset():nullptr;
    if(!Mesh){Diagnostic=TEXT("No skeletal mesh");return false;}
    if(FitCache.IsEmpty()&&Presentation->VisualDefinition)
    {
        // First use: fit every mesh variant the clips can switch to now, so no switch pays for a fit mid-move.
        const UVeyrVisualDefinition* Definition=Presentation->VisualDefinition;
        TArray<const USkeletalMesh*,TInlineAllocator<8>> Variants;
        if(Definition->SkeletalMesh)Variants.AddUnique(Definition->SkeletalMesh.Get());
        for(const auto& Entry:Definition->Clips)if(Entry.Value.MeshOverride)Variants.AddUnique(Entry.Value.MeshOverride.Get());
        for(const USkeletalMesh* Variant:Variants)
            if(Variant!=Mesh&&Variant->GetRefSkeleton().GetNum()==Mesh->GetRefSkeleton().GetNum())
            {TArray<FPoint> Out;Fit(Variant,Out);FitCache.Add(TObjectKey<USkeletalMesh>(Variant),MoveTemp(Out));}
    }
    // A failed fit is cached empty too, so a mesh that cannot be fitted is not refitted every frame.
    if(const TArray<FPoint>* Cached=FitCache.Find(TObjectKey<USkeletalMesh>(Mesh)))Points=*Cached;
    else
    {
        TArray<FPoint> Out;Fit(Mesh,Out);
        Points=Out;FitCache.Add(TObjectKey<USkeletalMesh>(Mesh),MoveTemp(Out));
    }
    FittedMesh=Mesh;
    return Points.Num()>0;
}

bool FVeyrHullModel::Fit(const USkeletalMesh* Mesh,TArray<FPoint>& Out)
{
    Out.Reset();
    const FReferenceSkeleton& Reference=Mesh->GetRefSkeleton();
    const TArray<FTransform> Rest=ReferenceComponentSpace(Reference);
    double Map[3][4];float Residual=0.f;int32 Joints=0;
    if(!FitGltfFrame(Reference,Rest,Map,Residual,Joints,Diagnostic))return false;
    const FMatrix Linear(FPlane(Map[0][0],Map[1][0],Map[2][0],0),FPlane(Map[0][1],Map[1][1],Map[2][1],0),FPlane(Map[0][2],Map[1][2],Map[2][2],0),FPlane(0,0,0,1));
    const double MapScale=FMath::Pow(FMath::Abs(Linear.Determinant()),1.0/3.0);
    // Normals map through the inverse transpose of the linear part (row-vector convention here).
    const FMatrix NormalMatrix=Linear.Inverse().GetTransposed();
    TMap<UPTRINT,int32> BoneOf; // the table repeats a few dozen bone names 26000 times
    Out.Reserve(UE_ARRAY_COUNT(GVeyrHullPoints));
    for(const FVeyrHullPoint& Source:GVeyrHullPoints)
    {
        FPoint Point;Point.Radius=static_cast<float>(Source.Radius*MapScale);
        Point.bWing=Source.Bones[0]&&FCString::Strncmp(Source.Bones[0],TEXT("VeyrWing"),8)==0;
        const FVector P=ApplyMap(Map,FVector(Source.X,Source.Y,Source.Z));
        const FVector N=NormalMatrix.TransformVector(FVector(Source.NX,Source.NY,Source.NZ)).GetSafeNormal();
        for(int32 I=0;I<4;++I)
        {
            if(!Source.Bones[I]||Source.Weights[I]<=0.f)continue;
            int32* Known=BoneOf.Find(reinterpret_cast<UPTRINT>(Source.Bones[I]));
            const int32 Bone=Known?*Known:BoneOf.Add(reinterpret_cast<UPTRINT>(Source.Bones[I]),Reference.FindBoneIndex(FName(Source.Bones[I])));
            if(Bone==INDEX_NONE){Diagnostic=FString::Printf(TEXT("Hull bone %s missing"),Source.Bones[I]);Out.Reset();return false;}
            Point.Influences[I]={Bone,Source.Weights[I],Rest[Bone].InverseTransformPosition(P),Rest[Bone].InverseTransformVectorNoScale(N)};
        }
        Out.Add(Point);
    }
    Diagnostic=FString::Printf(TEXT("Hull model: %d samples (%d boom), fit residual %.3f imported cm"),Out.Num(),FMath::Min(BoomPoints,Out.Num()),Residual);
    return Out.Num()>0;
}

bool FVeyrHullModel::IsReadyFor(const UVeyrSkeletalPresentation* Presentation) const
{
    return Presentation&&Points.Num()>0&&FittedMesh.Get()==Presentation->GetSkeletalMeshAsset();
}

bool FVeyrHullModel::Skin(UVeyrSkeletalPresentation* Presentation,TArray<FVector4>& Out) const
{
    Out.Reset();
    if(!IsReadyFor(Presentation)||!Presentation->bPoseEvaluated)return false;
    const TArray<FTransform>& Pose=Presentation->GetComponentSpaceTransforms();
    const FTransform Component=Presentation->GetComponentTransform();
    const double Scale=Component.GetScale3D().GetAbsMax();
    const int32 Count=BoomCount();Out.Reserve(Count);
    for(int32 Index=0;Index<Count;++Index)
    {
        const FPoint& Point=Points[Index];
        FVector Skinned=FVector::ZeroVector;
        for(const FInfluence& I:Point.Influences)
            if(I.Bone!=INDEX_NONE&&Pose.IsValidIndex(I.Bone))Skinned+=Pose[I.Bone].TransformPosition(I.BoneLocal)*I.Weight;
        Out.Emplace(Component.TransformPosition(Skinned),Point.Radius*Scale);
    }
    return true;
}

bool FVeyrHullModel::SkinSurface(UVeyrSkeletalPresentation* Presentation,TArray<FVector>& OutPositions,TArray<FVector>& OutNormals) const
{
    OutPositions.Reset();OutNormals.Reset();
    if(!IsReadyFor(Presentation)||!Presentation->bPoseEvaluated)return false;
    const TArray<FTransform>& Pose=Presentation->GetComponentSpaceTransforms();
    const FTransform Component=Presentation->GetComponentTransform();
    OutPositions.Reserve(Points.Num());OutNormals.Reserve(Points.Num());
    for(const FPoint& Point:Points)
    {
        if(Point.bWing)continue;
        FVector Skinned=FVector::ZeroVector,Normal=FVector::ZeroVector;
        for(const FInfluence& I:Point.Influences)
            if(I.Bone!=INDEX_NONE&&Pose.IsValidIndex(I.Bone))
            {Skinned+=Pose[I.Bone].TransformPosition(I.BoneLocal)*I.Weight;Normal+=Pose[I.Bone].TransformVectorNoScale(I.NormalLocal)*I.Weight;}
        OutPositions.Add(Component.TransformPosition(Skinned));
        OutNormals.Add(Component.TransformVectorNoScale(Normal).GetSafeNormal());
    }
    return true;
}

bool FVeyrHullModel::SkinWingSurface(UVeyrSkeletalPresentation* Presentation,TArray<FVector>& OutPositions,TArray<FVector>& OutNormals) const
{
    OutPositions.Reset();OutNormals.Reset();
    if(!IsReadyFor(Presentation)||!Presentation->bPoseEvaluated)return false;
    const TArray<FTransform>& Pose=Presentation->GetComponentSpaceTransforms();
    const FTransform Component=Presentation->GetComponentTransform();
    OutPositions.Reserve(Points.Num());OutNormals.Reserve(Points.Num());
    for(const FPoint& Point:Points)
    {
        if(!Point.bWing)continue;
        FVector Skinned=FVector::ZeroVector,Normal=FVector::ZeroVector;
        for(const FInfluence& I:Point.Influences)
            if(I.Bone!=INDEX_NONE&&Pose.IsValidIndex(I.Bone))
            {Skinned+=Pose[I.Bone].TransformPosition(I.BoneLocal)*I.Weight;Normal+=Pose[I.Bone].TransformVectorNoScale(I.NormalLocal)*I.Weight;}
        OutPositions.Add(Component.TransformPosition(Skinned));
        OutNormals.Add(Component.TransformVectorNoScale(Normal).GetSafeNormal());
    }
    return true;
}

bool FVeyrSoleModel::Initialize(UVeyrSkeletalPresentation* Presentation)
{
    bReady=false;Points.Reset();FitResidualImportedCm=-1.f;FittedMesh.Reset();
    const USkeletalMesh* Mesh=Presentation?Presentation->GetSkeletalMeshAsset():nullptr;
    if(!Mesh){Diagnostic=TEXT("No skeletal mesh");return false;}
    const FReferenceSkeleton& Reference=Mesh->GetRefSkeleton();
    const TArray<FTransform> Rest=ReferenceComponentSpace(Reference);
    double Map[3][4];int32 Joints=0;FString Error;
    if(!FitGltfFrame(Reference,Rest,Map,FitResidualImportedCm,Joints,Error))
    {Diagnostic=Error+TEXT("; grounding off");return false;}
    auto Apply=[&](const FVector& G){return ApplyMap(Map,G);};
    for(const FVeyrSolePoint& Source:GVeyrSolePoints)
    {
        FPoint Point;Point.Foot=Source.Foot;const FVector P=Apply(FVector(Source.X,Source.Y,Source.Z));
        for(int32 I=0;I<4;++I)
        {
            if(!Source.Bones[I]||Source.Weights[I]<=0.f)continue;
            const int32 Bone=Reference.FindBoneIndex(FName(Source.Bones[I]));
            if(Bone==INDEX_NONE){Diagnostic=FString::Printf(TEXT("Sole bone %s missing"),Source.Bones[I]);return false;}
            Point.Influences[I]={Bone,Source.Weights[I],Rest[Bone].InverseTransformPosition(P)};
        }
        Points.Add(Point);
    }
    FittedMesh=Mesh;bReady=Points.Num()>0;
    Diagnostic=FString::Printf(TEXT("Sole model: %d points, %d joints, fit residual %.3f imported cm"),Points.Num(),Joints,FitResidualImportedCm);
    return bReady;
}

bool FVeyrSoleModel::Measure(UVeyrSkeletalPresentation* Presentation,FVeyrSoleSample& Out) const
{
    Out=FVeyrSoleSample();
    if(!bReady||!Presentation||!Presentation->bPoseEvaluated||Presentation->GetSkeletalMeshAsset()!=FittedMesh.Get())return false;
    const TArray<FTransform>& Pose=Presentation->GetComponentSpaceTransforms();
    const FTransform Component=Presentation->GetComponentTransform();
    float Lowest[4]={TNumericLimits<float>::Max(),TNumericLimits<float>::Max(),TNumericLimits<float>::Max(),TNumericLimits<float>::Max()};
    for(const FPoint& Point:Points)
    {
        FVector Skinned=FVector::ZeroVector;
        for(const FInfluence& I:Point.Influences)
            if(I.Bone!=INDEX_NONE&&Pose.IsValidIndex(I.Bone))Skinned+=Pose[I.Bone].TransformPosition(I.BoneLocal)*I.Weight;
        const FVector World=Component.TransformPosition(Skinned);
        if(World.Z<Lowest[Point.Foot]){Lowest[Point.Foot]=World.Z;Out.Lowest[Point.Foot]=World;}
    }
    const AActor* Owner=Presentation->GetOwner();
    UWorld* World=Presentation->GetWorld();
    FCollisionQueryParams Params(SCENE_QUERY_STAT(VeyrSoleFloor),false,Owner);
    const float Reach=500.f*FMath::Max(1.f,static_cast<float>(Component.GetScale3D().Z/21.558172));
    Out.LowestAboveFloorCm=TNumericLimits<float>::Max();
    for(int32 Foot=0;Foot<4;++Foot)
    {
        if(Lowest[Foot]==TNumericLimits<float>::Max())return false;
        float Floor=Owner?static_cast<float>(Owner->GetActorLocation().Z):0.f;
        FHitResult Hit;
        const FVector P=Out.Lowest[Foot];
        if(World&&World->LineTraceSingleByObjectType(Hit,FVector(P.X,P.Y,P.Z+Reach),FVector(P.X,P.Y,P.Z-Reach),
            FCollisionObjectQueryParams(ECC_WorldStatic),Params)&&Hit.ImpactNormal.Z>.6f)Floor=static_cast<float>(Hit.ImpactPoint.Z);
        Out.FloorZ[Foot]=Floor;Out.SoleAboveFloorCm[Foot]=static_cast<float>(P.Z)-Floor;
        if(Out.SoleAboveFloorCm[Foot]<Out.LowestAboveFloorCm){Out.LowestAboveFloorCm=Out.SoleAboveFloorCm[Foot];Out.LowestFoot=Foot;}
    }
    Out.bValid=true;
    return true;
}

EVeyrGroundingMode VeyrGroundingModeFor(const AVeyrDragon* Dragon)
{
    if(!Dragon||Dragon->IsAirborne())return EVeyrGroundingMode::Release;
    switch(Dragon->State)
    {
        case EVeyrDragonState::Idle:case EVeyrDragonState::Reposition:case EVeyrDragonState::Buckle:return EVeyrGroundingMode::Ground;
        case EVeyrDragonState::Windup:case EVeyrDragonState::Active:case EVeyrDragonState::Recovery:
            // Takeoff and landing carry their own authored heights.
            return Dragon->Move==EVeyrDragonMove::FlyAway?EVeyrGroundingMode::Release:EVeyrGroundingMode::Ground;
        default:
            // Collapse, exposed, rise and death lie on the belly: keep the offset the standing pose had,
            // so the body neither pops up nor sinks when the feet stop being the lowest point.
            return EVeyrGroundingMode::Hold;
    }
}
