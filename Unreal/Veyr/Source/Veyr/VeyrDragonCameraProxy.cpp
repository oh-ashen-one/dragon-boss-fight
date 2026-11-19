#include "VeyrDragonCameraProxy.h"
#include "VeyrSkeletalPresentation.h"
#include "Engine/SkeletalMesh.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Misc/CommandLine.h"
#include "HAL/PlatformTime.h"

namespace
{
#include "VeyrDragonCameraProxy.inl"
    constexpr float GProofThreshold=.1f; // must match camera_proxy.py --threshold
}

const TArray<FVeyrDragonProxy::FLocalBox>* FVeyrDragonProxy::Resolve(const USkeletalMesh* Mesh)
{
    if(!Mesh)return nullptr;
    if(const TArray<FLocalBox>* Known=Table.Find(TObjectKey<USkeletalMesh>(Mesh)))return Known->Num()?Known:nullptr;
    TArray<FLocalBox>& Out=Table.Add(TObjectKey<USkeletalMesh>(Mesh));
    const FString Path=Mesh->GetPathName();
    const FReferenceSkeleton& Ref=Mesh->GetRefSkeleton();
    for(const FVeyrProxyMeshSource& M:GVeyrProxyMeshes)
    {
        if(Path!=M.Mesh)continue;
        for(int32 I=M.First;I<M.First+M.Count;++I)
        {
            const FVeyrProxyBoxSource& S=GVeyrProxyBoxes[I];
            const int32 Bone=Ref.FindBoneIndex(FName(S.Bone));
            if(Bone==INDEX_NONE){Diagnostic=FString::Printf(TEXT("proxy bone %s missing in %s"),S.Bone,*Path);Out.Reset();return nullptr;}
            FLocalBox B;B.Bone=Bone;B.Local=FTransform(FQuat(S.Q[0],S.Q[1],S.Q[2],S.Q[3]).GetNormalized(),FVector(S.C[0],S.C[1],S.C[2]));B.Half=FVector(S.H[0],S.H[1],S.H[2]);
            Out.Add(B);
        }
    }
    if(Out.IsEmpty())Diagnostic=FString::Printf(TEXT("no proxy table for %s"),*Path);
    else Diagnostic=FString::Printf(TEXT("proxy %d boxes for %s"),Out.Num(),*Path);
    return Out.Num()?&Out:nullptr;
}

bool FVeyrDragonProxy::Update(const UVeyrSkeletalPresentation* Presentation,float MarginCm)
{
    const double Start=FPlatformTime::Seconds();
    bValid=false;World.Reset();BoneBoxes.Reset();CurrentMargin=MarginCm;
    if(!Presentation||!Presentation->bPoseEvaluated)return false;
    const USkeletalMesh* Mesh=Presentation->GetSkeletalMeshAsset();
    const TArray<FLocalBox>* Local=Resolve(Mesh);
    if(!Local)return false;
    const TArray<FTransform>& Pose=Presentation->GetComponentSpaceTransforms();
    const FTransform Component=Presentation->GetComponentTransform();
    World.Reserve(Local->Num());
    for(const FLocalBox& L:*Local)
    {
        if(!Pose.IsValidIndex(L.Bone))return false;
        const FMatrix BoneWorld=Pose[L.Bone].ToMatrixWithScale()*Component.ToMatrixWithScale();
        FVeyrProxyWorldBox W;W.Bone=L.Bone;
        W.Centre=BoneWorld.TransformPosition(L.Local.GetTranslation());
        const FQuat Q=L.Local.GetRotation();
        const FVector Axes[3]={Q.GetAxisX(),Q.GetAxisY(),Q.GetAxisZ()};
        for(int32 K=0;K<3;++K)
        {
            const FVector V=BoneWorld.TransformVector(Axes[K]);
            const double Len=V.Size();
            W.Axis[K]=Len>1e-6?V/Len:Axes[K];
            W.Half[K]=L.Half[K]*Len+MarginCm;
        }
        BoneBoxes.FindOrAdd(L.Bone).Add(World.Num());
        World.Add(W);
    }
    LastMesh=Mesh;bValid=World.Num()>0;
    UpdateSeconds=FPlatformTime::Seconds()-Start;
    return bValid;
}

float FVeyrDragonProxy::OutsideBox(const FVeyrProxyWorldBox& Box,const FVector& P,float Extra)
{
    const FVector D=P-Box.Centre;double Sum=0;
    for(int32 K=0;K<3;++K){const double Q=FMath::Abs(FVector::DotProduct(D,Box.Axis[K]))-(Box.Half[K]+Extra);if(Q>0)Sum+=Q*Q;}
    return static_cast<float>(FMath::Sqrt(Sum));
}

float FVeyrDragonProxy::Distance(const FVector& P,float Extra) const
{
    float Best=TNumericLimits<float>::Max();
    for(const FVeyrProxyWorldBox& Box:World)
    {
        const FVector D=P-Box.Centre;double Sum=0,Max=-1e30;
        for(int32 K=0;K<3;++K){const double Q=FMath::Abs(FVector::DotProduct(D,Box.Axis[K]))-(Box.Half[K]+Extra);Max=FMath::Max(Max,Q);if(Q>0)Sum+=Q*Q;}
        Best=FMath::Min(Best,static_cast<float>(Max>0?FMath::Sqrt(Sum):Max));
    }
    return Best;
}

bool FVeyrDragonProxy::SegmentSlab(const FVeyrProxyWorldBox& Box,const FVector& A,const FVector& B,float Grow,float& OutEnter,float& OutExit)
{
    double Enter=-1e30,Exit=1e30;const FVector D=B-A,O=A-Box.Centre;
    for(int32 K=0;K<3;++K)
    {
        const double H=Box.Half[K]+Grow,Off=FVector::DotProduct(O,Box.Axis[K]),Dir=FVector::DotProduct(D,Box.Axis[K]);
        if(FMath::Abs(Dir)<1e-9){if(FMath::Abs(Off)>H)return false;continue;}
        double T1=(-H-Off)/Dir,T2=(H-Off)/Dir;if(T1>T2)Swap(T1,T2);
        Enter=FMath::Max(Enter,T1);Exit=FMath::Min(Exit,T2);
        if(Enter>Exit)return false;
    }
    OutEnter=static_cast<float>(Enter);OutExit=static_cast<float>(Exit);
    return true;
}

float FVeyrDragonProxy::Sweep(const FVector& A,const FVector& B,float Radius) const
{
    float Best=1.f;const double Length=FVector::Dist(A,B);
    if(Length<1e-3)return Contains(A,Radius)?0.f:1.f;
    for(const FVeyrProxyWorldBox& Box:World)
    {
        float E,X;
        if(!SegmentSlab(Box,A,B,Radius,E,X))continue;
        if(X<0.f||E>Best)continue;
        if(E<=0.f)return 0.f; // A already inside this grown box
        Best=FMath::Min(Best,E);
    }
    // Stop a hair before the contact so the lens is strictly outside.
    return Best<1.f?FMath::Max(0.f,Best-static_cast<float>(.5/Length)):1.f;
}

float FVeyrDragonProxy::FreeAbove(const FVector& P,float Radius,float MaxUp) const
{
    const FVector Top=P+FVector::UpVector*MaxUp;
    TArray<TPair<float,float>,TInlineAllocator<16>> Spans;
    for(const FVeyrProxyWorldBox& Box:World)
    {
        float E,X;
        if(SegmentSlab(Box,P,Top,Radius,E,X)&&X>=0.f&&E<=1.f)Spans.Emplace(FMath::Max(0.f,E)*MaxUp,X*MaxUp);
    }
    float T=0.f;
    for(bool bMoved=true;bMoved;)
    {
        bMoved=false;
        for(const auto& S:Spans)if(S.Key<=T&&T<S.Value){T=S.Value+.5f;bMoved=true;}
    }
    return FMath::Min(T,MaxUp);
}

bool FVeyrDragonProxy::UnderBody(const FVector& P,float MaxUp,float Grow) const
{
    const FVector Top=P+FVector::UpVector*MaxUp;
    for(const FVeyrProxyWorldBox& Box:World){float E,X;if(SegmentSlab(Box,P,Top,Grow,E,X)&&X>=0.f&&E<=1.f)return true;}
    return false;
}

// ---------------------------------------------------------------------------------------------------------------

FVeyrDragonTrueSkin& FVeyrDragonTrueSkin::Get()
{
    static FVeyrDragonTrueSkin Instance;
    if(!Instance.bTried)Instance.Load();
    return Instance;
}

void FVeyrDragonTrueSkin::Load()
{
    bTried=true;
    FString Path;
    if(!FParse::Value(FCommandLine::Get(),TEXT("VeyrTrueSkin="),Path))Path=FPaths::ProjectContentDir()/TEXT("Characters/Customuse/CameraProxy/DragonTrueSkin.bin");
    TArray<uint8> B;
    if(!FFileHelper::LoadFileToArray(B,*Path,FILEREAD_Silent)||B.Num()<8||FMemory::Memcmp(B.GetData(),"VTS1",4)!=0){Source=TEXT("missing: ")+Path;return;}
    int64 O=4;bool bOk=true;
    auto U32=[&](){uint32 V=0;if(O+4>B.Num()){bOk=false;return V;}FMemory::Memcpy(&V,B.GetData()+O,4);O+=4;return V;};
    auto F32=[&](){float V=0;if(O+4>B.Num()){bOk=false;return V;}FMemory::Memcpy(&V,B.GetData()+O,4);O+=4;return V;};
    auto Str=[&](){const uint32 N=U32();if(!bOk||O+N>B.Num()){bOk=false;return FString();}FString S=FString(FUTF8ToTCHAR(reinterpret_cast<const ANSICHAR*>(B.GetData()+O),N));O+=N;return S;};
    const uint32 Count=U32();
    for(uint32 M=0;M<Count&&bOk;++M)
    {
        FMesh Mesh;Mesh.Path=Str();
        const uint32 NB=U32();
        for(uint32 I=0;I<NB&&bOk;++I)
        {
            Mesh.BoneNames.Add(FName(*Str()));U32();
            float V[10];for(float& X:V)X=F32();
            Mesh.RefComp.Add(FTransform(FQuat(V[3],V[4],V[5],V[6]),FVector(V[0],V[1],V[2]),FVector(V[7],V[8],V[9])));
        }
        const uint32 NV=U32();if(!bOk||O+int64(NV)*(12+24)>B.Num()){bOk=false;break;}
        Mesh.Positions.SetNumUninitialized(NV);FMemory::Memcpy(Mesh.Positions.GetData(),B.GetData()+O,NV*12);O+=NV*12;
        Mesh.Bones.SetNumUninitialized(NV*4);Mesh.Weights.SetNumUninitialized(NV*4);
        for(uint32 I=0;I<NV*4;++I){uint16 Bone;FMemory::Memcpy(&Bone,B.GetData()+O,2);O+=2;Mesh.Bones[I]=Bone;Mesh.Weights[I]=F32();}
        const uint32 NI=U32();if(!bOk||O+int64(NI)*4>B.Num()){bOk=false;break;}
        Mesh.Indices.SetNumUninitialized(NI);FMemory::Memcpy(Mesh.Indices.GetData(),B.GetData()+O,NI*4);O+=NI*4;
        // Triangle groups: dominant bone of the first corner (spatially compact; bounds are rebuilt each frame).
        TMap<int32,int32> GroupOfBone;
        Mesh.GroupOfTriangle.SetNum(NI/3);
        for(uint32 T=0;T<NI/3;++T)
        {
            const uint32 V0=Mesh.Indices[T*3];int32 Dom=Mesh.Bones[V0*4];float W=-1.f;
            for(int32 K=0;K<4;++K)if(Mesh.Weights[V0*4+K]>W){W=Mesh.Weights[V0*4+K];Dom=Mesh.Bones[V0*4+K];}
            int32* G=GroupOfBone.Find(Dom);
            Mesh.GroupOfTriangle[T]=G?*G:GroupOfBone.Add(Dom,GroupOfBone.Num());
        }
        Mesh.GroupCount=GroupOfBone.Num();
        Meshes.Add(MoveTemp(Mesh));
    }
    if(!bOk){Meshes.Reset();Source=TEXT("corrupt: ")+Path;return;}
    Source=FString::Printf(TEXT("%s (%d meshes)"),*Path,Meshes.Num());
}

bool FVeyrDragonTrueSkin::Skin(const UVeyrSkeletalPresentation* Presentation)
{
    if(!IsLoaded()||!Presentation||!Presentation->bPoseEvaluated)return false;
    const USkeletalMesh* Mesh=Presentation->GetSkeletalMeshAsset();
    if(SkinnedFrame==GFrameCounter&&SkinnedMesh==Mesh&&Current)return true;
    const double Start=FPlatformTime::Seconds();
    if(Mesh!=SkinnedMesh)
    {
        Current=nullptr;PrevSkinned.Reset();Skinned.Reset();const FString Path=Mesh?Mesh->GetPathName():FString();
        for(FMesh& M:Meshes)if(M.Path==Path){Current=&M;break;}
        SkinnedMesh=Mesh;
    }
    if(!Current)return false;
    const FReferenceSkeleton& Ref=Mesh->GetRefSkeleton();
    const TArray<FTransform>& Pose=Presentation->GetComponentSpaceTransforms();
    const FTransform Component=Presentation->GetComponentTransform();
    // Linear blend skinning with the engine's matrices: component pose x inverse reference pose, then the component.
    TArray<FTransform> RefComp;RefComp.SetNum(Ref.GetNum());
    const TArray<FTransform>& Local=Ref.GetRefBonePose();
    for(int32 I=0;I<Ref.GetNum();++I){const int32 P=Ref.GetParentIndex(I);RefComp[I]=P==INDEX_NONE?Local[I]:Local[I]*RefComp[P];}
    TArray<FMatrix44f> M;M.SetNum(Ref.GetNum());const FMatrix ComponentM=Component.ToMatrixWithScale();
    for(int32 I=0;I<Ref.GetNum();++I)
        M[I]=FMatrix44f(RefComp[I].ToMatrixWithScale().Inverse()*(Pose.IsValidIndex(I)?Pose[I]:RefComp[I]).ToMatrixWithScale()*ComponentM);
    const int32 NV=Current->Positions.Num();
    if(Skinned.Num()==NV&&SkinnedFrame!=GFrameCounter){Swap(Skinned,PrevSkinned);PrevSkinnedFrame=SkinnedFrame;}
    else PrevSkinned.Reset();
    Skinned.SetNumUninitialized(NV);
    for(int32 V=0;V<NV;++V)
    {
        const FVector3f& P=Current->Positions[V];FVector3f Sum(0,0,0);
        for(int32 K=0;K<4;++K)
        {
            const float W=Current->Weights[V*4+K];if(W<=0.f)continue;
            const int32 Bone=Current->Bones[V*4+K];
            if(M.IsValidIndex(Bone)){const FVector4f Q=M[Bone].TransformPosition(P);Sum+=FVector3f(Q.X,Q.Y,Q.Z)*W;}
        }
        Skinned[V]=FVector(Sum);
    }
    GroupBounds.Init(FBox(ForceInit),Current->GroupCount);
    GroupTriangles.SetNum(Current->GroupCount);for(TArray<int32>& G:GroupTriangles)G.Reset();
    const int32 NT=Current->Indices.Num()/3;
    for(int32 T=0;T<NT;++T)
    {
        const int32 G=Current->GroupOfTriangle[T];GroupTriangles[G].Add(T);
        for(int32 C=0;C<3;++C)GroupBounds[G]+=Skinned[Current->Indices[T*3+C]];
    }
    SkinnedFrame=GFrameCounter;
    SkinSeconds=FPlatformTime::Seconds()-Start;
    return true;
}

// Ericson's closest point on a triangle (Real-Time Collision Detection 5.1.5): exact for degenerate (zero-area)
// faces too. FMath::ClosestPointOnTriangleToPoint returns the query point itself for a zero-area face, which made
// the audit report "0 cm from the skin" (inside the dragon) 22 cm off every box (-VeyrAuditEngineTriangle restores).
static FVector VeyrClosestOnTriangle(const FVector& P,const FVector& A,const FVector& B,const FVector& C)
{
    const FVector AB=B-A,AC=C-A,AP=P-A;
    const double D1=AB|AP,D2=AC|AP;if(D1<=0&&D2<=0)return A;
    const FVector BP=P-B;const double D3=AB|BP,D4=AC|BP;if(D3>=0&&D4<=D3)return B;
    const double VC=D1*D4-D3*D2;if(VC<=0&&D1>=0&&D3<=0){const double V=D1/FMath::Max(D1-D3,1e-12);return A+AB*V;}
    const FVector CP=P-C;const double D5=AB|CP,D6=AC|CP;if(D6>=0&&D5<=D6)return C;
    const double VB=D5*D2-D1*D6;if(VB<=0&&D2>=0&&D6<=0){const double W=D2/FMath::Max(D2-D6,1e-12);return A+AC*W;}
    const double VA=D3*D6-D5*D4;if(VA<=0&&(D4-D3)>=0&&(D5-D6)>=0){const double W=(D4-D3)/FMath::Max((D4-D3)+(D5-D6),1e-12);return B+(C-B)*W;}
    const double Sum=VA+VB+VC;
    if(FMath::Abs(Sum)<1e-12)
    {
        // Zero area: nearest of the three edges.
        auto Seg=[&](const FVector& X,const FVector& Y){return FMath::ClosestPointOnSegment(P,X,Y);};
        const FVector E0=Seg(A,B),E1=Seg(B,C),E2=Seg(C,A);
        const double S0=FVector::DistSquared(P,E0),S1=FVector::DistSquared(P,E1),S2=FVector::DistSquared(P,E2);
        return S0<=S1&&S0<=S2?E0:(S1<=S2?E1:E2);
    }
    const double Denom=1.0/Sum;const double V=VB*Denom,W=VC*Denom;
    return A+AB*V+AC*W;
}

float FVeyrDragonTrueSkin::NearestDistance(const FVector& P,float MaxDistance) const
{
    static const bool bEngine=FParse::Param(FCommandLine::Get(),TEXT("VeyrAuditEngineTriangle"));
    if(!Current)return MaxDistance;
    double Best=MaxDistance*double(MaxDistance);
    for(int32 G=0;G<GroupBounds.Num();++G)
    {
        if(!GroupBounds[G].IsValid||GroupBounds[G].ComputeSquaredDistanceToPoint(P)>=Best)continue;
        for(const int32 T:GroupTriangles[G])
        {
            const FVector& A=Skinned[Current->Indices[T*3]];const FVector& B=Skinned[Current->Indices[T*3+1]];const FVector& C=Skinned[Current->Indices[T*3+2]];
            const double D=FVector::DistSquared(P,bEngine?FMath::ClosestPointOnTriangleToPoint(P,A,B,C):VeyrClosestOnTriangle(P,A,B,C));
            if(D<Best)Best=D;
        }
    }
    return static_cast<float>(FMath::Sqrt(Best));
}

int32 FVeyrDragonTrueSkin::RayCrossings(const FVector& P,const FVector& Dir,float Length) const
{
    const FVector E=P+Dir*Length;int32 Count=0;
    for(int32 G=0;G<GroupBounds.Num();++G)
    {
        const FBox& Box=GroupBounds[G];
        if(!Box.IsValid||(!Box.IsInside(P)&&!FMath::LineBoxIntersection(Box,P,E,E-P)))continue;
        for(const int32 T:GroupTriangles[G])
        {
            FVector Hit,Normal;
            if(FMath::SegmentTriangleIntersection(P,E,Skinned[Current->Indices[T*3]],Skinned[Current->Indices[T*3+1]],Skinned[Current->Indices[T*3+2]],Hit,Normal))++Count;
        }
    }
    return Count;
}

bool FVeyrDragonTrueSkin::InsideVolume(const FVector& P) const
{
    if(!Current)return false;
    FBox All(ForceInit);for(const FBox& B:GroupBounds)if(B.IsValid)All+=B;
    if(!All.IsValid||!All.IsInside(P))return false;
    const float L=static_cast<float>(All.GetSize().Size())+10.f;
    int32 Odd=0;
    for(const FVector& D:{FVector(0,0,1),FVector(1,0,0),FVector(0,-1,0)})Odd+=RayCrossings(P,D,L)&1;
    return Odd>=2;
}

bool FVeyrDragonTrueSkin::SegmentBlocked(const FVector& A,const FVector& B) const
{
    if(!Current)return false;
    for(int32 G=0;G<GroupBounds.Num();++G)
    {
        const FBox& Box=GroupBounds[G];
        if(!Box.IsValid||(!Box.IsInside(A)&&!FMath::LineBoxIntersection(Box,A,B,B-A)))continue;
        for(const int32 T:GroupTriangles[G])
        {
            FVector Hit,Normal;
            if(FMath::SegmentTriangleIntersection(A,B,Skinned[Current->Indices[T*3]],Skinned[Current->Indices[T*3+1]],Skinned[Current->Indices[T*3+2]],Hit,Normal))return true;
        }
    }
    return false;
}

void FVeyrDragonTrueSkin::Prove(const FVeyrDragonProxy& Proxy,float& OutWorstWithMargin,float& OutWorstBare,int32& OutTested,int32& OutOutside,FVector& OutWorstPoint) const
{
    OutWorstWithMargin=0.f;OutWorstBare=0.f;OutTested=0;OutOutside=0;OutWorstPoint=FVector::ZeroVector;
    if(!Current||!Proxy.IsValid())return;
    const TArray<FVeyrProxyWorldBox>& Boxes=Proxy.Boxes();const float Margin=Proxy.Margin();
    for(int32 V=0;V<Skinned.Num();++V)
    {
        const FVector& P=Skinned[V];float Bare=TNumericLimits<float>::Max();
        int32 Dom=0;for(int32 K=1;K<4;++K)if(Current->Weights[V*4+K]>Current->Weights[V*4+Dom])Dom=K;
        for(int32 K=0;K<4&&Bare>0.f;++K)
        {
            if(K!=Dom&&Current->Weights[V*4+K]<GProofThreshold)continue;
            if(const TArray<int32>* List=Proxy.BoxesOfBone(Current->Bones[V*4+K]))
                for(const int32 I:*List)Bare=FMath::Min(Bare,FVeyrDragonProxy::OutsideBox(Boxes[I],P,-Margin));
        }
        if(Bare>0.f)for(const FVeyrProxyWorldBox& Box:Boxes)Bare=FMath::Min(Bare,FVeyrDragonProxy::OutsideBox(Box,P,-Margin));
        // Outside with the margin: recompute against the grown boxes only when the bare test failed.
        float With=0.f;
        if(Bare>0.f){With=TNumericLimits<float>::Max();for(const FVeyrProxyWorldBox& Box:Boxes)With=FMath::Min(With,FVeyrDragonProxy::OutsideBox(Box,P,0.f));}
        ++OutTested;
        if(With>0.f)++OutOutside;
        if(Bare>OutWorstBare){OutWorstBare=Bare;}
        if(With>OutWorstWithMargin){OutWorstWithMargin=With;OutWorstPoint=P;}
    }
}

bool FVeyrDragonTrueSkin::Tighten(FVeyrDragonProxy& Proxy)
{
    if(!Current||!Proxy.IsValid()||Skinned.Num()!=Current->Positions.Num())return false;
    const TArray<FVeyrDragonProxy::FLocalBox>* Local=Proxy.Resolve(Proxy.LastMesh.Get());
    if(!Local||Local->Num()!=Proxy.World.Num())return false;
    const int32 NV=Current->Positions.Num();
    if(Current->BoxCountAssigned!=Local->Num())
    {
        // Each vertex to the box of its dominant bone that holds it at rest (nearest when none does).
        TMap<int32,TArray<int32>> ByBone;for(int32 I=0;I<Local->Num();++I)ByBone.FindOrAdd((*Local)[I].Bone).Add(I);
        const USkeletalMesh* Mesh=Proxy.LastMesh.Get();
        const FReferenceSkeleton& Ref=Mesh->GetRefSkeleton();const TArray<FTransform>& L=Ref.GetRefBonePose();
        TArray<FTransform> RefComp;RefComp.SetNum(Ref.GetNum());
        for(int32 I=0;I<Ref.GetNum();++I){const int32 P=Ref.GetParentIndex(I);RefComp[I]=P==INDEX_NONE?L[I]:L[I]*RefComp[P];}
        Current->BoxOfVertex.Init(INDEX_NONE,NV);
        for(int32 V=0;V<NV;++V)
        {
            int32 Dom=0;for(int32 K=1;K<4;++K)if(Current->Weights[V*4+K]>Current->Weights[V*4+Dom])Dom=K;
            const int32 Bone=Current->Bones[V*4+Dom];
            const TArray<int32>* List=ByBone.Find(Bone);if(!List||!RefComp.IsValidIndex(Bone))continue;
            const FVector BoneLocal=RefComp[Bone].InverseTransformPosition(FVector(Current->Positions[V]));
            float Best=TNumericLimits<float>::Max();
            for(const int32 I:*List)
            {
                const FVeyrDragonProxy::FLocalBox& B=(*Local)[I];
                const FVector Q=B.Local.InverseTransformPosition(BoneLocal);double Sum=0;
                for(int32 K=0;K<3;++K){const double D=FMath::Abs(Q[K])-B.Half[K];if(D>0)Sum+=D*D;}
                if(Sum<Best){Best=static_cast<float>(Sum);Current->BoxOfVertex[V]=I;}
            }
        }
        Current->BoxCountAssigned=Local->Num();
    }
    const int32 NB=Proxy.World.Num();
    TArray<FVector> Lo,Hi;Lo.Init(FVector(1e30),NB);Hi.Init(FVector(-1e30),NB);
    auto Grow=[&](int32 I,const FVector& P)
    {
        const FVeyrProxyWorldBox& B=Proxy.World[I];const FVector D=P-B.Centre;
        for(int32 K=0;K<3;++K){const double X=FVector::DotProduct(D,B.Axis[K]);Lo[I][K]=FMath::Min(Lo[I][K],X);Hi[I][K]=FMath::Max(Hi[I][K],X);}
    };
    for(int32 V=0;V<NV;++V){const int32 I=Current->BoxOfVertex[V];if(I!=INDEX_NONE)Grow(I,Skinned[V]);}
    // The lens is placed and the skin drawn up to a frame apart: hold last frame's skin and its constant-velocity
    // next frame too (-VeyrRigOneFrameSkin keeps this frame only).
    static const bool bOneFrame=FParse::Param(FCommandLine::Get(),TEXT("VeyrRigOneFrameSkin"));
    if(!bOneFrame&&PrevSkinned.Num()==NV&&SkinnedFrame-PrevSkinnedFrame<=2)
        for(int32 V=0;V<NV;++V)
        {
            const int32 I=Current->BoxOfVertex[V];if(I==INDEX_NONE)continue;
            Grow(I,PrevSkinned[V]);Grow(I,Skinned[V]*2.0-PrevSkinned[V]);
        }
    // Whole triangles: a box holding all three corners holds the face (boxes are convex), so a face stretched
    // between two bones' boxes can never leave a gap the lens fits through (seen: lens 34 cm off the proxy, 0 cm off skin).
    const TArray<uint32>& Idx=Current->Indices;
    for(int32 T=0;T+2<Idx.Num();T+=3)
    {
        const int32 A0=Idx[T],A1=Idx[T+1],A2=Idx[T+2];
        if(A0>=NV||A1>=NV||A2>=NV)continue;
        const int32 I=Current->BoxOfVertex[A0]!=INDEX_NONE?Current->BoxOfVertex[A0]:(Current->BoxOfVertex[A1]!=INDEX_NONE?Current->BoxOfVertex[A1]:Current->BoxOfVertex[A2]);
        if(I==INDEX_NONE)continue;
        const int32 I1=Current->BoxOfVertex[A1],I2=Current->BoxOfVertex[A2];
        if(I1==I&&I2==I)continue; // already inside from the vertex pass
        Grow(I,Skinned[A0]);Grow(I,Skinned[A1]);Grow(I,Skinned[A2]);
    }
    for(int32 I=0;I<NB;++I)
    {
        if(Lo[I].X>Hi[I].X)continue; // no vertex of its own: keep the bone-moved box
        FVeyrProxyWorldBox& B=Proxy.World[I];FVector Shift=FVector::ZeroVector;
        for(int32 K=0;K<3;++K){Shift+=B.Axis[K]*((Lo[I][K]+Hi[I][K])*.5);B.Half[K]=(Hi[I][K]-Lo[I][K])*.5+Proxy.CurrentMargin;}
        B.Centre+=Shift;
    }
    return true;
}

float FVeyrDragonTrueSkin::SweepSphere(const FVector& A,const FVector& B,float R,float StartT,int32* OutSteps) const
{
    const double Len=FVector::Dist(A,B);int32 Steps=0;
    if(!Current||Len<1e-3){if(OutSteps)*OutSteps=0;return 1.f;}
    double T=FMath::Clamp<double>(StartT,0.0,1.0);
    while(Steps<48)
    {
        ++Steps;
        const FVector P=A+(B-A)*T;
        const double Remaining=(1.0-T)*Len;
        const double D=NearestDistance(P,static_cast<float>(Remaining+R+1.0))-R;
        if(D>Remaining){T=1.0;break;}
        if(D<.5){if(OutSteps)*OutSteps=Steps;return static_cast<float>(FMath::Max(0.0,T-.5/Len));}
        T+=D/Len;
        if(T>=1.0){T=1.0;break;}
    }
    if(OutSteps)*OutSteps=Steps;
    return static_cast<float>(T>=1.0?1.0:FMath::Max(0.0,T-.5/Len));
}
