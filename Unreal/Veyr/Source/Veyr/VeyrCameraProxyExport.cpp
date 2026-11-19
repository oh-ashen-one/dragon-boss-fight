// Camera fourth pass (2026-11-19): editor-only export of the drawn dragon skin for the camera proxy fit.
//
// UnrealEditor-Cmd Veyr.uproject -run=VeyrCameraProxyExport -Out=<file.bin>
//
// Writes, for the shipped dragon definition's base mesh and every clip mesh variant, the LOD0 render
// vertices (reference component space, imported cm), their four skin influences (skeleton bone index,
// normalised weight), the triangle list and the reference pose. tools/dragon_refine/camera_proxy.py fits
// one oriented box per bone from it (VeyrDragonCameraProxy.inl, derived measurements only); the runtime
// audit reads the same file as the true skin. The file is character content and never enters git.
#include "VeyrCameraProxyExport.h"

UVeyrCameraProxyExportCommandlet::UVeyrCameraProxyExportCommandlet()
{
    IsClient=false;IsEditor=true;IsServer=false;LogToConsole=true;
}

#if WITH_EDITOR
#include "VeyrVisualDefinition.h"
#include "Engine/SkeletalMesh.h"
#include "Rendering/SkeletalMeshRenderData.h"
#include "Rendering/SkeletalMeshLODRenderData.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "HAL/FileManager.h"

namespace
{
    void PutU32(TArray<uint8>& B,uint32 V){B.Append(reinterpret_cast<const uint8*>(&V),4);}
    void PutF(TArray<uint8>& B,float V){B.Append(reinterpret_cast<const uint8*>(&V),4);}
    void PutStr(TArray<uint8>& B,const FString& S){FTCHARToUTF8 U(*S);PutU32(B,U.Length());B.Append(reinterpret_cast<const uint8*>(U.Get()),U.Length());}
}

int32 UVeyrCameraProxyExportCommandlet::Main(const FString& Params)
{
    FString Out;
    if(!FParse::Value(*Params,TEXT("Out="),Out)||FPaths::IsRelative(Out)){UE_LOG(LogTemp,Error,TEXT("VEYR_PROXY_EXPORT needs -Out=<absolute file>"));return 1;}
    FString DefinitionPath=TEXT("/Game/Characters/Customuse/RuntimePolish/DA_Dragon.DA_Dragon");
    FParse::Value(*Params,TEXT("Definition="),DefinitionPath);
    UVeyrVisualDefinition* Definition=LoadObject<UVeyrVisualDefinition>(nullptr,*DefinitionPath);
    if(!Definition||!Definition->SkeletalMesh){UE_LOG(LogTemp,Error,TEXT("VEYR_PROXY_EXPORT definition %s missing"),*DefinitionPath);return 1;}
    TArray<USkeletalMesh*> Meshes;Meshes.Add(Definition->SkeletalMesh);
    for(const auto& Entry:Definition->Clips)if(Entry.Value.MeshOverride)Meshes.AddUnique(Entry.Value.MeshOverride.Get());
    TArray<uint8> B;B.Append(reinterpret_cast<const uint8*>("VTS1"),4);PutU32(B,Meshes.Num());
    for(USkeletalMesh* Mesh:Meshes)
    {
        const FReferenceSkeleton& Ref=Mesh->GetRefSkeleton();
        FSkeletalMeshRenderData* Render=Mesh->GetResourceForRendering();
        if(!Render||Render->LODRenderData.IsEmpty()){UE_LOG(LogTemp,Error,TEXT("VEYR_PROXY_EXPORT %s has no render data"),*Mesh->GetPathName());return 2;}
        const FSkeletalMeshLODRenderData& LOD=Render->LODRenderData[0];
        const FPositionVertexBuffer& Positions=LOD.StaticVertexBuffers.PositionVertexBuffer;
        const FSkinWeightVertexBuffer* Weights=LOD.GetSkinWeightVertexBuffer();
        const uint32 NumVerts=Positions.GetNumVertices();
        if(NumVerts==0||!Positions.GetVertexData()||!Weights||Weights->GetNumVertices()!=NumVerts)
        {UE_LOG(LogTemp,Error,TEXT("VEYR_PROXY_EXPORT %s LOD0 CPU data unavailable (verts %u)"),*Mesh->GetPathName(),NumVerts);return 3;}
        PutStr(B,Mesh->GetPathName());
        // Reference pose, component space.
        const TArray<FTransform>& Local=Ref.GetRefBonePose();
        TArray<FTransform> Comp;Comp.SetNum(Local.Num());
        for(int32 I=0;I<Local.Num();++I){const int32 P=Ref.GetParentIndex(I);Comp[I]=P==INDEX_NONE?Local[I]:Local[I]*Comp[P];}
        PutU32(B,Ref.GetNum());
        for(int32 I=0;I<Ref.GetNum();++I)
        {
            PutStr(B,Ref.GetBoneName(I).ToString());PutU32(B,static_cast<uint32>(Ref.GetParentIndex(I)));
            const FVector T=Comp[I].GetTranslation();const FQuat Q=Comp[I].GetRotation();const FVector S=Comp[I].GetScale3D();
            for(const double V:{T.X,T.Y,T.Z,Q.X,Q.Y,Q.Z,Q.W,S.X,S.Y,S.Z})PutF(B,static_cast<float>(V));
        }
        PutU32(B,NumVerts);
        for(uint32 V=0;V<NumVerts;++V){const FVector3f P=Positions.VertexPosition(V);PutF(B,P.X);PutF(B,P.Y);PutF(B,P.Z);}
        // Influences: section-local bone indices through each render section's bone map.
        TArray<int32> SectionOf;SectionOf.Init(INDEX_NONE,NumVerts);
        for(int32 S=0;S<LOD.RenderSections.Num();++S)
        {
            const FSkelMeshRenderSection& Section=LOD.RenderSections[S];
            for(uint32 V=Section.BaseVertexIndex;V<Section.BaseVertexIndex+Section.NumVertices&&V<NumVerts;++V)SectionOf[V]=S;
        }
        const int32 MaxInf=FMath::Min<int32>(Weights->GetMaxBoneInfluences(),8);
        int32 Truncated=0;
        for(uint32 V=0;V<NumVerts;++V)
        {
            TArray<TPair<float,int32>,TInlineAllocator<8>> Inf;
            const FSkelMeshRenderSection* Section=SectionOf[V]!=INDEX_NONE?&LOD.RenderSections[SectionOf[V]]:nullptr;
            for(int32 K=0;K<MaxInf;++K)
            {
                const float W=static_cast<float>(Weights->GetBoneWeight(V,K))/(Weights->Use16BitBoneWeight()?65535.f:255.f);
                if(W<=0.f||!Section)continue;
                const int32 LocalBone=Weights->GetBoneIndex(V,K);
                if(!Section->BoneMap.IsValidIndex(LocalBone))continue;
                Inf.Emplace(W,Section->BoneMap[LocalBone]);
            }
            Inf.Sort([](const TPair<float,int32>& A,const TPair<float,int32>& C){return A.Key>C.Key;});
            if(Inf.Num()>4)++Truncated;
            float Sum=0.f;for(int32 K=0;K<FMath::Min(4,Inf.Num());++K)Sum+=Inf[K].Key;
            for(int32 K=0;K<4;++K)
            {
                const bool bHas=K<Inf.Num()&&Sum>0.f;
                const uint16 Bone=bHas?static_cast<uint16>(Inf[K].Value):0;const float W=bHas?Inf[K].Key/Sum:0.f;
                B.Append(reinterpret_cast<const uint8*>(&Bone),2);PutF(B,W);
            }
        }
        TArray<uint32> Indices;LOD.MultiSizeIndexContainer.GetIndexBuffer(Indices);
        PutU32(B,Indices.Num());for(const uint32 I:Indices)PutU32(B,I);
        UE_LOG(LogTemp,Display,TEXT("VEYR_PROXY_EXPORT mesh=%s verts=%u tris=%d sections=%d maxInfluences=%d truncated=%d bones=%d"),
            *Mesh->GetPathName(),NumVerts,Indices.Num()/3,LOD.RenderSections.Num(),Weights->GetMaxBoneInfluences(),Truncated,Ref.GetNum());
    }
    IFileManager::Get().MakeDirectory(*FPaths::GetPath(Out),true);
    if(!FFileHelper::SaveArrayToFile(B,*Out)){UE_LOG(LogTemp,Error,TEXT("VEYR_PROXY_EXPORT cannot write %s"),*Out);return 4;}
    UE_LOG(LogTemp,Display,TEXT("VEYR_PROXY_EXPORT wrote %s (%d bytes, %d meshes)"),*Out,B.Num(),Meshes.Num());
    return 0;
}
#endif
