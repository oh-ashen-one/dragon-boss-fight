#include "VeyrArena.h"

#include "Components/BoxComponent.h"
#include "Components/DirectionalLightComponent.h"
#include "Components/ExponentialHeightFogComponent.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "Components/PointLightComponent.h"
#include "Components/PostProcessComponent.h"
#include "Components/SceneComponent.h"
#include "Components/SkyLightComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "UObject/ConstructorHelpers.h"

namespace
{
    const TCHAR* CourtKitNames[]={TEXT("CloisterWall"),TEXT("ApseWall"),TEXT("ProcessionalStair"),
        TEXT("CollapsedVaultRubble"),TEXT("RockRetainingWall"),TEXT("RuinedGatehouse"),TEXT("FallenGreatBell"),
        TEXT("FuneraryEffigyNiche"),TEXT("RuinedCityRoofBlock"),TEXT("WornPavingPatch"),TEXT("CornerButtress"),TEXT("AncientDeadTree")};
    constexpr float CourtHalfX=4900.f,CourtHalfY=4400.f,AisleHeight=144.2f;
    FVector Radial(float Angle, float Radius, float Height = 0.f)
    {
        return FVector(FMath::Cos(Angle) * Radius, FMath::Sin(Angle) * Radius, Height);
    }
}

AVeyrArena::AVeyrArena()
{
    PrimaryActorTick.bCanEverTick = false;
    USceneComponent* Scene = CreateDefaultSubobject<USceneComponent>(TEXT("ConnectedCourtRoot"));
    Scene->SetMobility(EComponentMobility::Static);
    SetRootComponent(Scene);
    Tags.Add(TEXT("VeyrOriginalLayout"));
    Tags.Add(TEXT("VeyrConnectedCathedralCourt"));
    for(const TCHAR* Name:CourtKitNames)
    {
        const TCHAR* Version=FCString::Strcmp(Name,TEXT("RockRetainingWall"))==0?TEXT("v002"):TEXT("v001");
        const FString Path=FString::Printf(TEXT("/Game/ArtPass/Tripo/Polish%s_%s/SM_Polish%s_%s.SM_Polish%s_%s"),Name,Version,Name,Version,Name,Version);
        ConstructorHelpers::FObjectFinderOptional<UStaticMesh> Mesh(*Path,LOAD_Quiet|LOAD_NoWarn);
        if(Mesh.Get())PolishMeshes.Add(FName(Name),Mesh.Get());
    }

    // These are Unreal Engine resources, not original mesh/texture deliverables.
    // Hard constructor references make the prototype dependencies cookable.
    static ConstructorHelpers::FObjectFinder<UStaticMesh> Cube(TEXT("/Engine/BasicShapes/Cube.Cube"));
    static ConstructorHelpers::FObjectFinderOptional<UStaticMesh> BasaltCliff(
        TEXT("/Game/Veyr/Environment/SM_BasaltCliff.SM_BasaltCliff"),LOAD_Quiet|LOAD_NoWarn);
    static ConstructorHelpers::FObjectFinder<UStaticMesh> CylinderAsset(TEXT("/Engine/BasicShapes/Cylinder.Cylinder"));
    static ConstructorHelpers::FObjectFinder<UStaticMesh> Sphere(TEXT("/Engine/BasicShapes/Sphere.Sphere"));
    static ConstructorHelpers::FObjectFinder<UStaticMesh> Cone(TEXT("/Engine/BasicShapes/Cone.Cone"));
    static ConstructorHelpers::FObjectFinder<UStaticMesh> Sky(TEXT("/Engine/EngineSky/SM_SkySphere.SM_SkySphere"));
    static ConstructorHelpers::FObjectFinder<UMaterialInterface> Base(TEXT("/Engine/BasicShapes/BasicShapeMaterial.BasicShapeMaterial"));
    static ConstructorHelpers::FObjectFinderOptional<UMaterialInterface> AuthoredStone(
        TEXT("/Game/Veyr/Materials/M_CathedralStone_v3.M_CathedralStone_v3"),LOAD_Quiet|LOAD_NoWarn);
    static ConstructorHelpers::FObjectFinder<UMaterialInterface> SkyMaterial(TEXT("/Engine/EngineSky/M_Sky_Panning_Clouds2.M_Sky_Panning_Clouds2"));
    static ConstructorHelpers::FObjectFinderOptional<UStaticMesh> Facade(TEXT("/Game/ArtPass/Tripo/CathedralFacade_v001/SM_CathedralFacade_v001.SM_CathedralFacade_v001"),LOAD_Quiet|LOAD_NoWarn);
    static ConstructorHelpers::FObjectFinderOptional<UStaticMesh> Wall(TEXT("/Game/ArtPass/Tripo/CathedralWall_v001/SM_CathedralWall_v001.SM_CathedralWall_v001"),LOAD_Quiet|LOAD_NoWarn);
    static ConstructorHelpers::FObjectFinderOptional<UStaticMesh> GothicArch(TEXT("/Game/ArtPass/Tripo/CathedralArch_v001/SM_CathedralArch_v001.SM_CathedralArch_v001"),LOAD_Quiet|LOAD_NoWarn);
    static ConstructorHelpers::FObjectFinderOptional<UMaterialInterface> Night(TEXT("/Game/ArtPass/Sky/M_CathedralNight_v004.M_CathedralNight_v004"),LOAD_Quiet|LOAD_NoWarn);
    static ConstructorHelpers::FObjectFinderOptional<UStaticMesh> Brazier(TEXT("/Game/ArtPass/Tripo/CathedralBrazier_v001/SM_CathedralBrazier_v001.SM_CathedralBrazier_v001"),LOAD_Quiet|LOAD_NoWarn);
    static ConstructorHelpers::FObjectFinderOptional<UMaterialInterface> FloorMaterial(TEXT("/Game/ArtPass/Floor/M_CathedralFloor_v001.M_CathedralFloor_v001"),LOAD_Quiet|LOAD_NoWarn);
    CathedralBrazierMesh=Brazier.Get();CathedralFloorParent=FloorMaterial.Get();
    CathedralFacadeMesh=Facade.Get();CathedralWallMesh=Wall.Get();CathedralArchMesh=GothicArch.Get();NightSkyParent=Night.Get();
    BasaltCliffMesh=BasaltCliff.Get();
    CubeMesh = Cube.Object; CylinderMesh = CylinderAsset.Object; SphereMesh = Sphere.Object; ConeMesh = Cone.Object;
    PlainParent=Base.Object;StoneParent=AuthoredStone.Get()?AuthoredStone.Get():Base.Object.Get();
    SkyMesh = Sky.Object; SkyParent = SkyMaterial.Object;
}

void AVeyrArena::BeginPlay()
{
    Super::BeginPlay();
    // Retry the exact owned import path if the CDO predates native import.
    if(!BasaltCliffMesh)BasaltCliffMesh=LoadObject<UStaticMesh>(nullptr,
        TEXT("/Game/Veyr/Environment/SM_BasaltCliff.SM_BasaltCliff"),nullptr,LOAD_Quiet|LOAD_NoWarn);
    bUsingBasaltCliff=BasaltCliffMesh!=nullptr;
    if(!CathedralFacadeMesh)CathedralFacadeMesh=LoadObject<UStaticMesh>(nullptr,TEXT("/Game/ArtPass/Tripo/CathedralFacade_v001/SM_CathedralFacade_v001.SM_CathedralFacade_v001"),nullptr,LOAD_Quiet|LOAD_NoWarn);
    if(!CathedralWallMesh)CathedralWallMesh=LoadObject<UStaticMesh>(nullptr,TEXT("/Game/ArtPass/Tripo/CathedralWall_v001/SM_CathedralWall_v001.SM_CathedralWall_v001"),nullptr,LOAD_Quiet|LOAD_NoWarn);
    if(!CathedralArchMesh)CathedralArchMesh=LoadObject<UStaticMesh>(nullptr,TEXT("/Game/ArtPass/Tripo/CathedralArch_v001/SM_CathedralArch_v001.SM_CathedralArch_v001"),nullptr,LOAD_Quiet|LOAD_NoWarn);
    if(!NightSkyParent)NightSkyParent=LoadObject<UMaterialInterface>(nullptr,TEXT("/Game/ArtPass/Sky/M_CathedralNight_v004.M_CathedralNight_v004"),nullptr,LOAD_Quiet|LOAD_NoWarn);
    bUsingAuthoredNightSky=NightSkyParent!=nullptr;
    if(!CathedralBrazierMesh)CathedralBrazierMesh=LoadObject<UStaticMesh>(nullptr,TEXT("/Game/ArtPass/Tripo/CathedralBrazier_v001/SM_CathedralBrazier_v001.SM_CathedralBrazier_v001"),nullptr,LOAD_Quiet|LOAD_NoWarn);
    if(!CathedralFloorParent)CathedralFloorParent=LoadObject<UMaterialInterface>(nullptr,TEXT("/Game/ArtPass/Floor/M_CathedralFloor_v001.M_CathedralFloor_v001"),nullptr,LOAD_Quiet|LOAD_NoWarn);
    bUsingAuthoredFloor=CathedralFloorParent!=nullptr;bUsingImportedBraziers=CathedralBrazierMesh!=nullptr;
    LoadPolishKit();
    if(UMaterialInterface* Authored=LoadObject<UMaterialInterface>(nullptr,TEXT("/Game/Veyr/Materials/M_CathedralStone_v3.M_CathedralStone_v3"),nullptr,LOAD_Quiet|LOAD_NoWarn))StoneParent=Authored;
    if (bBuilt || !CubeMesh || !CylinderMesh || !SphereMesh || !ConeMesh || !StoneParent || !PlainParent) return;
    bBuilt = true;
    auto* Ashlar = MakeMaterial(TEXT("PrototypeAshlar"), FLinearColor(.17f, .195f, .22f), .78f);
    auto* Limestone = MakeMaterial(TEXT("PrototypeLimestone"), FLinearColor(.255f, .27f, .275f), .76f);
    auto* Flagstone = MakeMaterial(TEXT("OriginalDampFlagstone"), FLinearColor(.095f, .112f, .125f), .60f);
    auto* FlagstoneLight = MakeMaterial(TEXT("OriginalWornFlagstone"), FLinearColor(.13f, .14f, .145f), .72f);
    auto* WetStone = MakeMaterial(TEXT("OriginalBroadWetStone"), FLinearColor(.060f, .075f, .090f), .32f);
    auto* OldBronze = MakeMaterial(TEXT("PrototypeAncientBronze"), FLinearColor(.23f, .145f, .055f), .64f,true,.72f);
    // Background masses stay broad, dark and fogged, without close-view stone
    // grain that would emphasize their engine-primitive shape and false scale.
    auto* Basalt = MakeMaterial(TEXT("PrototypeDarkBasalt"), FLinearColor(.028f, .039f, .055f), .94f,false);
    auto* Coal = MakeMaterial(TEXT("PrototypeBrazierCoal"), FLinearColor(.65f, .19f, .035f), .92f,true,0.f,1.5f);
    Stone = MakeBatch(TEXT("PROTO_OriginalAshlarLayout"), CubeMesh, Ashlar);
    Trim = MakeBatch(TEXT("PROTO_OriginalLimestoneTracery"), CubeMesh, Limestone);
    Floor = MakeBatch(TEXT("PROTO_FlagstonePavers"), CubeMesh, Flagstone);
    FloorLight = MakeBatch(TEXT("PROTO_FlagstonePaversLight"), CubeMesh, FlagstoneLight);
    FloorWet = MakeBatch(TEXT("OriginalBroadWetPaverAreas"), CubeMesh, WetStone);
    UMaterialInterface* FloorMaterial=CathedralFloorParent?CathedralFloorParent.Get():Flagstone;
    FloorSurface=MakeBatch(TEXT("ContinuousCathedralFloor"),CylinderMesh,FloorMaterial);
    auto* FoundationStone=MakeMaterial(TEXT("RecessedCourtFoundationStone"),FLinearColor(.075f,.080f,.085f),.92f);
    Foundations=MakeBatch(TEXT("ConnectedCathedralFoundations"),CubeMesh,FoundationStone);
    auto* CutStone=MakeMaterial(TEXT("RestrainedFloorCarving"),FLinearColor(.045f,.050f,.054f),.9f,false);
    FloorCarvings=MakeBatch(TEXT("SubtleStoneCarvedRings"),CubeMesh,CutStone);
    auto* ParapetStone=MakeMaterial(TEXT("DarkWeatheredParapetStone"),FLinearColor(.055f,.064f,.072f),.92f);
    BoundaryStone=MakeBatch(TEXT("GroundedDarkStoneBoundary"),CubeMesh,ParapetStone);
    Bronze = MakeBatch(TEXT("PROTO_AncientFloorInlay"), CubeMesh, OldBronze);
    Columns = MakeBatch(TEXT("PROTO_ClusteredPillarCores"), CylinderMesh, Ashlar);
    ColumnTrim = MakeBatch(TEXT("PROTO_ColonettesAndCapitals"), CylinderMesh, Limestone);
    DarkDisks = MakeBatch(TEXT("PROTO_FloorFoundationAndMoat"), CylinderMesh, Basalt);
    Rocks = MakeBatch(bUsingBasaltCliff?TEXT("OriginalBasaltCliffMasses"):TEXT("PROTO_DistantBasaltCliffMasses"),
        bUsingBasaltCliff?BasaltCliffMesh.Get():CubeMesh.Get(),Basalt);
    RockSpurs = MakeBatch(bUsingBasaltCliff?TEXT("OriginalBasaltCrestFragments"):TEXT("PROTO_DistantBasaltCrestFragments"),
        bUsingBasaltCliff?BasaltCliffMesh.Get():ConeMesh.Get(),Basalt);
    Rocks->SetCastShadow(false);RockSpurs->SetCastShadow(false);
    Embers = MakeBatch(TEXT("PROTO_BrazierEmberBeds"), SphereMesh, Coal);
    BuildFloor();
    bUsingImportedCathedral=BuildImportedCathedral();
    // Missing kit assets remain an explicit validation failure. Do not silently
    // dress an old primitive facade as the new reference-matched environment.
    BuildDistance();
    BuildLighting();
    BuildCollision();
    UE_LOG(LogTemp, Display, TEXT("VEYR_ARENA_READY connected court: clear fight diameter~7200cm, walkable aisles0..240cm; %d instanced groups."), Batches.Num());
    UE_LOG(LogTemp,Display,TEXT("VEYR_CONNECTED_COURT ready=%d meshes=%d/12 instances=%d diagnostic=%s"),
        bConnectedCourtAssetsReady,ConnectedCourtMeshCount,ConnectedCourtInstanceCount,*ConnectedCourtDiagnostic);
    UE_LOG(LogTemp,Display,TEXT("VEYR_ARENA_MATERIAL stone=%s backdrop=%s"),*StoneParent->GetPathName(),*PlainParent->GetPathName());
    UE_LOG(LogTemp,Display,TEXT("VEYR_ARENA_ART architecturePieces=%d facade=%d wall=%d arch=%d nightSky=%d yawOffset=%.1f"),
        ImportedArchitecturePieces,CathedralFacadeMesh!=nullptr,CathedralWallMesh!=nullptr,CathedralArchMesh!=nullptr,bUsingAuthoredNightSky,CathedralFacingYawOffset);
    UE_LOG(LogTemp,Display,TEXT("VEYR_ARENA_BASALT imported=%d mesh=%s; native silhouette review required"),
        bUsingBasaltCliff,BasaltCliffMesh?*BasaltCliffMesh->GetPathName():TEXT("engine primitive fallback"));
}

UMaterialInstanceDynamic* AVeyrArena::MakeMaterial(const FName Name, const FLinearColor Color, float Roughness,
    bool bUseAuthoredStone, float Metallic, float Emission)
{
    UMaterialInstanceDynamic* Material = UMaterialInstanceDynamic::Create(bUseAuthoredStone?StoneParent:PlainParent, this, Name);
    // Color/Roughness also work with the installed BasicShapeMaterial fallback;
    // Metallic/Emission are authored parameters on the optional stone parent.
    Material->SetVectorParameterValue(TEXT("Color"), Color);
    Material->SetScalarParameterValue(TEXT("Roughness"), Roughness);
    Material->SetScalarParameterValue(TEXT("Metallic"), Metallic);
    Material->SetScalarParameterValue(TEXT("Emission"), Emission);
    Materials.Add(Material);
    return Material;
}

UInstancedStaticMeshComponent* AVeyrArena::MakeBatch(const FName Name, UStaticMesh* Mesh, UMaterialInterface* Material)
{
    auto* Batch = NewObject<UInstancedStaticMeshComponent>(this, Name);
    AddInstanceComponent(Batch);
    Batch->SetupAttachment(GetRootComponent());
    Batch->SetMobility(EComponentMobility::Static);
    Batch->SetStaticMesh(Mesh);
    Batch->SetMaterial(0, Material);
    Batch->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    Batch->SetGenerateOverlapEvents(false);
    Batch->SetCanEverAffectNavigation(false);
    Batch->RegisterComponent();
    Batches.Add(Batch);
    return Batch;
}

void AVeyrArena::Box(UInstancedStaticMeshComponent* Batch, const FVector& Position, const FVector& Size, const FRotator& Rotation)
{
    Batch->AddInstance(FTransform(Rotation, Position, Size / 100.f));
}

void AVeyrArena::Beam(UInstancedStaticMeshComponent* Batch, const FVector& A, const FVector& B, float Width)
{
    const FVector Delta = B - A;
    const FQuat Rotation = FQuat::FindBetweenNormals(FVector::UpVector, Delta.GetSafeNormal());
    Batch->AddInstance(FTransform(Rotation, (A + B) * .5f, FVector(Width, Width, Delta.Size() + 2.f) / 100.f));
}

void AVeyrArena::Cylinder(UInstancedStaticMeshComponent* Batch, const FVector& Position, float Radius, float Height)
{
    Batch->AddInstance(FTransform(FQuat::Identity, Position, FVector(Radius * 2.f, Radius * 2.f, Height) / 100.f));
}

void AVeyrArena::Arch(const FVector& Left, const FVector& Right, float Spring, float Apex, float Width, UInstancedStaticMeshComponent* Batch, int32 LeftPieces, int32 RightPieces)
{
    const FVector Across = (Right - Left).GetSafeNormal();
    const float Half = FVector::Distance(Left, Right) * .5f;
    const float Rise = Apex - Spring;
    if (Half < 1.f || Rise <= 0.f) return;
    const float Radius = (Half * Half + Rise * Rise) / (2.f * Half);
    const float Sweep = FMath::Atan2(Rise, Radius - Half);
    for (int32 Side = 0; Side < 2; ++Side)
    {
        const FVector Start = (Side == 0 ? Left : Right) + FVector(0, 0, Spring);
        const FVector Toward = Side == 0 ? Across : -Across;
        const int32 Count = Side == 0 ? LeftPieces : RightPieces;
        for (int32 Segment = 0; Segment < Count; ++Segment)
        {
            const float A = Segment / 16.f * Sweep, B = (Segment + 1) / 16.f * Sweep;
            const FVector P = Start + Toward * (Radius * (1.f - FMath::Cos(A))) + FVector(0, 0, Radius * FMath::Sin(A));
            const FVector Q = Start + Toward * (Radius * (1.f - FMath::Cos(B))) + FVector(0, 0, Radius * FMath::Sin(B));
            Beam(Batch, P, Q, Width);
        }
    }
}

void AVeyrArena::RoseRing(const FVector& Center, float Radius, float Width)
{
    for (int32 I = 0; I < 48; ++I)
    {
        const float A = I * 2.f * PI / 48.f, B = (I + 1) * 2.f * PI / 48.f;
        Beam(Trim, Center + FVector(0, FMath::Sin(A), FMath::Cos(A)) * Radius,
            Center + FVector(0, FMath::Sin(B), FMath::Cos(B)) * Radius, Width);
    }
}

bool AVeyrArena::LoadPolishKit()
{
    ConnectedCourtMeshCount=0;ConnectedCourtDiagnostic.Reset();ConnectedMeshDimensionsCm.Reset();
    for(const TCHAR* Name:CourtKitNames)
    {
        const TCHAR* Version=FCString::Strcmp(Name,TEXT("RockRetainingWall"))==0?TEXT("v002"):TEXT("v001");
        const FString Path=FString::Printf(TEXT("/Game/ArtPass/Tripo/Polish%s_%s/SM_Polish%s_%s.SM_Polish%s_%s"),Name,Version,Name,Version,Name,Version);
        UStaticMesh* Mesh=LoadObject<UStaticMesh>(nullptr,*Path,nullptr,LOAD_Quiet|LOAD_NoWarn);
        if(!Mesh){ConnectedCourtDiagnostic+=FString(Name)+TEXT(" missing; ");continue;}
        const FVector Size=Mesh->GetBoundingBox().GetSize();
        if(Size.ContainsNaN()||!FMath::IsFinite(Size.X+Size.Y+Size.Z)||Size.GetMin()<1.f)
        {ConnectedCourtDiagnostic+=FString(Name)+TEXT(" invalid bounds; ");continue;}
        PolishMeshes.Add(FName(Name),Mesh);ConnectedMeshDimensionsCm.Add(FName(Name),Size);++ConnectedCourtMeshCount;
    }
    bConnectedCourtAssetsReady=ConnectedCourtMeshCount==UE_ARRAY_COUNT(CourtKitNames);
    if(bConnectedCourtAssetsReady)ConnectedCourtDiagnostic=TEXT("12 measured Tripo kit meshes loaded; connected layout and native collision/visual checks required");
    else UE_LOG(LogTemp,Error,TEXT("VEYR_CONNECTED_COURT_ASSETS_MISSING %s"),*ConnectedCourtDiagnostic);
    return bConnectedCourtAssetsReady;
}

FVector AVeyrArena::KitSize(FName Name,float Height) const
{
    UStaticMesh* Mesh=PolishMeshes.FindRef(Name);if(!Mesh)return FVector::ZeroVector;
    const FVector Size=Mesh->GetBoundingBox().GetSize();return Size*(Height/FMath::Max(1.f,static_cast<float>(Size.Z)));
}

void AVeyrArena::KitPiece(FName Name,const FVector& Anchor,float Height,float Yaw,bool bBlocking,bool bFrontAnchor,float WidthScale)
{
    UStaticMesh* Mesh=PolishMeshes.FindRef(Name);if(!Mesh)return;
    const FBox Bounds=Mesh->GetBoundingBox();const float Uniform=Height/FMath::Max(1.f,static_cast<float>(Bounds.GetSize().Z));
    FVector Scale(Uniform*WidthScale,Uniform,Uniform);
    // Preserve the full eight-metre paving footprint while burying its skirt.
    // Uniform height normalization would shrink the footprint with its depth.
    if(Name==FName(TEXT("WornPavingPatch")))Scale.Z*=.075f;
    const FRotator Rotation(0,Yaw,0);
    const FVector LocalAnchor(Bounds.GetCenter().X,bFrontAnchor?Bounds.Max.Y:Bounds.GetCenter().Y,Bounds.Min.Z);
    const FTransform Transform(Rotation,Anchor-Rotation.RotateVector(LocalAnchor*Scale),Scale);
    const FName BatchName(*FString::Printf(TEXT("CourtKit_%s_%s"),*Name.ToString(),bBlocking?TEXT("Solid"):TEXT("Distant")));
    UInstancedStaticMeshComponent* Batch=PolishBatches.FindRef(BatchName);
    if(!Batch)
    {
        Batch=NewObject<UInstancedStaticMeshComponent>(this,BatchName);AddInstanceComponent(Batch);
        Batch->SetupAttachment(GetRootComponent());Batch->SetMobility(EComponentMobility::Static);Batch->SetStaticMesh(Mesh);
        // The court material uses world-position UVs. Share it across the
        // shallow generated paving so the surface continues through its edge
        // instead of looking like a differently textured rectangular rug.
        if(Name==FName(TEXT("WornPavingPatch"))&&FloorSurface&&FloorSurface->GetMaterial(0))
            for(int32 Slot=0;Slot<Mesh->GetStaticMaterials().Num();++Slot)
                Batch->SetMaterial(Slot,FloorSurface->GetMaterial(0));
        // Other modules keep their imported PBR slots. The collision LOD uses
        // the real openings, rather than a bounding box across a walkable arch.
        Batch->SetCollisionProfileName(bBlocking?TEXT("BlockAll"):TEXT("NoCollision"));
        Batch->SetCollisionEnabled(bBlocking?ECollisionEnabled::QueryAndPhysics:ECollisionEnabled::NoCollision);
        Batch->SetGenerateOverlapEvents(false);Batch->SetCanEverAffectNavigation(false);
        if(Name!=FName(TEXT("WornPavingPatch"))&&Name!=FName(TEXT("ProcessionalStair")))
            Batch->SetWalkableSlopeOverride(FWalkableSlopeOverride(WalkableSlope_Unwalkable,0.f));
        if(!bBlocking){Batch->SetCullDistances(26000,42000);Batch->SetCastShadow(false);}
        Batch->RegisterComponent();Batches.Add(Batch);PolishBatches.Add(BatchName,Batch);
    }
    Batch->AddInstance(Transform);++ConnectedCourtInstanceCount;++ImportedArchitecturePieces;
}

void AVeyrArena::KitWallRun(FName Name,const FVector& Start,const FVector& End,const FVector& Inward,float Height,float FloorZ,bool bBlocking)
{
    const FVector Dimensions=KitSize(Name,Height);const float Length=FVector::Dist2D(Start,End);
    if(Dimensions.X<=1.f||Length<=1.f)return;
    const int32 Count=FMath::Max(1,FMath::CeilToInt(Length/(Dimensions.X*.90f)));
    const float Yaw=Inward.Rotation().Yaw-90.f; // normalized local +Y faces the court
    for(int32 I=0;I<Count;++I)
    {
        FVector Face=FMath::Lerp(Start,End,(I+.5f)/Count);Face.Z=FloorZ;
        KitPiece(Name,Face,Height,Yaw,bBlocking,true);
    }
    // Continuous visible masonry behind the carved bays closes irregular mesh
    // seams. It sits behind their front face, never across an open passage.
    if(bBlocking&&FloorZ>0.f)
    {
        FVector Support=(Start+End)*.5f-Inward*(Dimensions.Y*.5f);
        // The upper gallery already rests on the lower wall. A full-height
        // second support exposed a featureless slab through its carved bays.
        const float H=FloorZ>AisleHeight+500.f?180.f:FloorZ+120.f;
        Support.Z=FloorZ-H*.5f;
        Box(Foundations,Support,FVector(Length+100.f,Dimensions.Y+160.f,H),(End-Start).Rotation());
    }
    if(bBlocking&&Name==FName(TEXT("CloisterWall")))
    {
        const float Depth=FMath::Max(150.f,static_cast<float>(Dimensions.Y)*.65f);
        FVector Center=(Start+End)*.5f-Inward*(Dimensions.Y*.70f);Center.Z=FloorZ+Height*.475f;
        Box(Foundations,Center,FVector(Length+80.f,Depth,Height*.95f),(End-Start).Rotation());
    }
}

void AVeyrArena::BuildFloor()
{
    RaisedWalkableBounds.Reset();
    // The court and the ground beneath its side aisles are one connected mass.
    // Generated paving is the close surface; there is no empty 320m blue disk.
    Box(Floor,FVector(0,0,-20),FVector(CourtHalfX*2+100,CourtHalfY*2+100,40));
    Cylinder(FloorSurface,FVector(0,0,-4.7f),CombatRadius+60.f,10.f);
    Box(Foundations,FVector(0,0,-200),FVector(CourtHalfX*2+900,CourtHalfY*2+900,380));
    // Raised galleries leave a generous margin beyond the 72m combat centre.
    for(float Side:{-1.f,1.f})
    {
        Box(Foundations,FVector(0,Side*4250.f,AisleHeight*.5f),FVector(2.f*CourtHalfX,300.f,AisleHeight));
        Box(Foundations,FVector(Side*4725.f,0,AisleHeight*.5f),FVector(350.f,8200.f,AisleHeight));
        RaisedWalkableBounds.Add(FBox(FVector(-CourtHalfX,Side*4250.f-150.f,0),FVector(CourtHalfX,Side*4250.f+150.f,AisleHeight)));
        RaisedWalkableBounds.Add(FBox(FVector(Side*4725.f-175.f,-4100,0),FVector(Side*4725.f+175.f,4100,AisleHeight)));
    }
    for(float Radius:{950.f,3200.f})
        for(int32 I=0;I<96;++I)
        {
            const float A=(I+.5f)*2.f*PI/96.f;
            Box(FloorCarvings,Radial(A,Radius,.45f),FVector(2.f,Radius*2.f*PI/96.f+1.f,.3f),FRotator(0,FMath::RadiansToDegrees(A),0));
        }
    if(!bConnectedCourtAssetsReady)return;
    for(int32 X=-2;X<=2;++X)for(int32 Y=-2;Y<=2;++Y)
    {
        if(FVector2D(X*1350.f,Y*1350.f).Size()>3300.f)continue;
        KitPiece(TEXT("WornPavingPatch"),FVector(X*1350.f,Y*1350.f,-.1f),8.f,((X+Y+8)%4)*90.f,true);
    }
}

void AVeyrArena::ImportedPiece(UStaticMesh* Mesh,const FName Name,const FVector& Position,float Height,float Yaw,bool bArchitecture)
{
    if(!Mesh)return;
    const FBox Bounds=Mesh->GetBoundingBox();
    const float SourceHeight=Bounds.GetSize().Z;
    if(!FMath::IsFinite(SourceHeight)||SourceHeight<1.f)return;
    const float Scale=Height/SourceHeight;
    auto* Piece=NewObject<UStaticMeshComponent>(this,Name);
    AddInstanceComponent(Piece);Piece->SetupAttachment(GetRootComponent());
    Piece->SetMobility(EComponentMobility::Static);Piece->SetStaticMesh(Mesh);
    // Intentionally no SetMaterial: all imported PBR slots remain intact.
    const FRotator Facing(0,Yaw,0);const FVector Outward=Position.GetSafeNormal2D();
    const FVector Extent=Bounds.GetExtent()*Scale;
    const float RadialDepth=FMath::Abs(FVector::DotProduct(Facing.RotateVector(FVector(Extent.X,0,0)),Outward))+
        FMath::Abs(FVector::DotProduct(Facing.RotateVector(FVector(0,Extent.Y,0)),Outward));
    const float CenterOffset=FVector::DotProduct(Facing.RotateVector(Bounds.GetCenter()*Scale),Outward);
    const float PushOut=bArchitecture?FMath::Max(0.f,CombatRadius+450.f+RadialDepth-static_cast<float>(Position.Size2D())-CenterOffset):0.f;
    const FVector BasePosition=Position+Outward*PushOut-FVector(0,0,Bounds.Min.Z*Scale);
    Piece->SetRelativeLocation(BasePosition);
    if(bArchitecture&&Foundations)
    {
        FVector PlinthCenter=BasePosition+Facing.RotateVector(Bounds.GetCenter()*Scale);PlinthCenter.Z=Position.Z-120.f;
        const FVector Support(Bounds.GetSize().X*Scale+220.f,Bounds.GetSize().Y*Scale+220.f,240.f);
        Box(Foundations,PlinthCenter,Support,Facing);
    }
    Piece->SetRelativeRotation(Facing);Piece->SetRelativeScale3D(FVector(Scale));
    Piece->SetCollisionProfileName(TEXT("BlockAll"));Piece->SetCollisionEnabled(ECollisionEnabled::QueryAndPhysics);Piece->SetGenerateOverlapEvents(false);
    Piece->SetCanEverAffectNavigation(false);Piece->RegisterComponent();if(bArchitecture)++ImportedArchitecturePieces;
}

bool AVeyrArena::BuildImportedCathedral()
{
    if(!bConnectedCourtAssetsReady)return false;
    const FVector Wall=KitSize(TEXT("CloisterWall"),1400.f),Gate=KitSize(TEXT("RuinedGatehouse"),1600.f);
    const float GateHalf=FMath::Min(CourtHalfY-1200.f,static_cast<float>(Gate.X)*.46f);
    KitWallRun(TEXT("CloisterWall"),FVector(-CourtHalfX,-CourtHalfY,0),FVector(CourtHalfX,-CourtHalfY,0),FVector(0,1,0),1400,AisleHeight);
    KitWallRun(TEXT("CloisterWall"),FVector(CourtHalfX,CourtHalfY,0),FVector(-CourtHalfX,CourtHalfY,0),FVector(0,-1,0),1400,AisleHeight);
    KitWallRun(TEXT("CloisterWall"),FVector(-CourtHalfX,-CourtHalfY,0),FVector(-CourtHalfX,-GateHalf,0),FVector(1,0,0),1400,AisleHeight);
    KitWallRun(TEXT("CloisterWall"),FVector(-CourtHalfX,GateHalf,0),FVector(-CourtHalfX,CourtHalfY,0),FVector(1,0,0),1400,AisleHeight);
    // This asset is a complete 40.55 m deep cathedral. Its near face, not its
    // centre, defines the east court boundary; one building is sufficient.
    const FVector Apse=KitSize(TEXT("ApseWall"),2400.f);
    KitPiece(TEXT("ApseWall"),FVector(CourtHalfX,0,AisleHeight),2400,90,true,true);
    const float ApseHalf=static_cast<float>(Apse.X)*.5f-60.f;
    KitWallRun(TEXT("CloisterWall"),FVector(CourtHalfX,-CourtHalfY,0),FVector(CourtHalfX,-ApseHalf,0),FVector(-1,0,0),1400,AisleHeight);
    KitWallRun(TEXT("CloisterWall"),FVector(CourtHalfX,ApseHalf,0),FVector(CourtHalfX,CourtHalfY,0),FVector(-1,0,0),1400,AisleHeight);
    Box(Foundations,FVector(CourtHalfX+Apse.Y*.5f,0,(AisleHeight-120.f)*.5f),FVector(Apse.Y+120.f,Apse.X+160.f,AisleHeight+120.f));
    // A second, recessed gallery gives the long nave its vertical enclosure.
    // The carved cloister mesh is a solid wall, so its structural backing does
    // not seal genuine openings. The apse's real windows remain unfilled.
    KitWallRun(TEXT("CloisterWall"),FVector(-2600,-CourtHalfY-100,0),FVector(CourtHalfX,-CourtHalfY-100,0),FVector(0,1,0),1000,AisleHeight+1340);
    KitWallRun(TEXT("CloisterWall"),FVector(CourtHalfX,CourtHalfY+100,0),FVector(-2600,CourtHalfY+100,0),FVector(0,-1,0),1000,AisleHeight+1340);
    // Three grounded masses interrupt the repeated arcade skyline. Their
    // front faces stay outside the court and leave the combat floor unchanged.
    auto SkylineMass=[&](FName Name,float X,float Height)
    {
        const FVector Size=KitSize(Name,Height);const float FrontY=CourtHalfY+40.f;
        KitPiece(Name,FVector(X,FrontY,AisleHeight),Height,180.f,true,true);
        Box(Foundations,FVector(X,FrontY+Size.Y*.5f,(AisleHeight-120.f)*.5f),FVector(Size.X+100.f,Size.Y+100.f,AisleHeight+120.f));
    };
    SkylineMass(TEXT("RuinedGatehouse"),-450.f,3400.f);
    SkylineMass(TEXT("CornerButtress"),-3250.f,2100.f);
    SkylineMass(TEXT("CornerButtress"),3350.f,2250.f);
    KitPiece(TEXT("RuinedGatehouse"),FVector(-CourtHalfX,0,AisleHeight),1600,-90,true,true);
    Box(Foundations,FVector(-CourtHalfX-Gate.Y*.5f,0,(AisleHeight-120.f)*.5f),FVector(Gate.Y+120.f,Gate.X+160.f,AisleHeight+120.f));
    // Closed portcullis is visible solid geometry. Its gaps are narrower than
    // the Knight capsule; there is no invisible slab across an apparently open gate.
    const float DoorWidth=FMath::Clamp(static_cast<float>(Gate.X)*.30f,600.f,1200.f),DoorHeight=760.f;
    const float GateX=-CourtHalfX+30.f;
    for(float Y=-DoorWidth*.5f;Y<=DoorWidth*.5f+1.f;Y+=70.f)
        Box(Bronze,FVector(GateX,Y,AisleHeight+DoorHeight*.5f),FVector(18,18,DoorHeight));
    for(float Z:{110.f,380.f,680.f})Box(Bronze,FVector(GateX,0,AisleHeight+Z),FVector(24,DoorWidth+45.f,24));
    // Real stairs connect the gallery to the sunken court. Upper landing slabs
    // meet their measured rear footprint; frame rails do not define placement.
    const float StairHeight=PolishMeshes.FindChecked(TEXT("ProcessionalStair"))->GetBoundingBox().GetSize().Z;
    constexpr float StairWidthScale=2.5f; // 2.30 m source becomes a 5.75 m processional stair.
    FVector Stair=KitSize(TEXT("ProcessionalStair"),StairHeight);Stair.X*=StairWidthScale;
    KitPiece(TEXT("ProcessionalStair"),FVector(-CourtHalfX+Stair.Y+500.f,0,0),StairHeight,-90,true,true,StairWidthScale);
    Box(Foundations,FVector(-CourtHalfX+250.f,0,AisleHeight*.5f),FVector(500.f,Stair.X+150.f,AisleHeight));
    RaisedWalkableBounds.Add(FBox(FVector(-CourtHalfX,-Stair.X*.5f-75.f,0),FVector(-CourtHalfX+500.f+Stair.Y,Stair.X*.5f+75.f,AisleHeight)));
    for(float Side:{-1.f,1.f})
    {
        KitPiece(TEXT("ProcessionalStair"),FVector(1700.f,Side*(4100.f-Stair.Y),0),StairHeight,Side>0?180.f:0.f,true,true,StairWidthScale);
        const float Y0=Side*(4100.f-Stair.Y),Y1=Side*4100.f;
        RaisedWalkableBounds.Add(FBox(FVector(1700.f-Stair.X*.5f,FMath::Min(Y0,Y1),0),FVector(1700.f+Stair.X*.5f,FMath::Max(Y0,Y1),AisleHeight)));
        for(float X:{-3900.f,-1700.f,600.f,2900.f,4500.f})
            KitPiece(TEXT("FuneraryEffigyNiche"),FVector(X,Side*4260.f,AisleHeight),700,Side>0?180.f:0.f,true,true);
        for(float X:{-CourtHalfX,CourtHalfX})
            KitPiece(TEXT("CornerButtress"),FVector(X,Side*CourtHalfY,AisleHeight),1400,Side>0?180.f:0.f,true);
    }
    // Collapsed vault and the fallen bell form one rubble alcove, not random
    // isolated objects sprinkled through the combat centre.
    KitPiece(TEXT("FallenGreatBell"),FVector(-1500,3700,0),500,-25,true);
    for(int32 I=0;I<6;++I)
        KitPiece(TEXT("CollapsedVaultRubble"),FVector(-2700.f+I*520.f,3820.f+(I%2)*130.f,0),210.f+(I%3)*25.f,I*61.f,true);
    for(float Side:{-1.f,1.f})for(int32 I=0;I<5;++I)
        KitPiece(TEXT("CollapsedVaultRubble"),FVector(3900.f+(I%2)*130.f,Side*(-3000.f+I*1450.f),0),160.f+(I%3)*25.f,I*43.f,true);
    for(float Side:{-1.f,1.f})
        KitPiece(TEXT("AncientDeadTree"),FVector(-3900,Side*3950,0),1000,Side*35.f,true);
    return true;
}

float AVeyrArena::GetMaximumWalkableHeightNear(const FVector& WorldPoint,float RadiusCm) const
{
    const FVector Point=GetActorTransform().InverseTransformPosition(WorldPoint);
    const float Radius=RadiusCm/FMath::Max(.001f,static_cast<float>(GetActorScale3D().GetAbsMax()));float Height=.5f;
    for(const FBox& Bounds:RaisedWalkableBounds)
    {
        const float X=FMath::Clamp(Point.X,Bounds.Min.X,Bounds.Max.X),Y=FMath::Clamp(Point.Y,Bounds.Min.Y,Bounds.Max.Y);
        if(FMath::Square(Point.X-X)+FMath::Square(Point.Y-Y)<=FMath::Square(Radius))Height=FMath::Max(Height,static_cast<float>(Bounds.Max.Z));
    }
    return GetActorTransform().TransformPosition(FVector(Point.X,Point.Y,Height)).Z;
}

void AVeyrArena::BuildCathedral()
{
    const FVector Facade(5000, -1500, 0);
    for (int32 Step = 0; Step < 4; ++Step)
        Box(Stone, Facade + FVector(0, 0, Step * 35.f), FVector(900 - Step * 80.f, 3400 - Step * 120.f, 45));
    for (int32 Side : { -1, 1 })
    {
        const FVector Pier = Facade + FVector(0, Side * 1120.f, 0);
        Box(Stone, Pier + FVector(0, 0, 1580), FVector(310, 320, 3160));
        Box(Stone, Facade + FVector(0, Side * 750.f, 400), FVector(300, 800, 800));
        for (int32 Flute = -1; Flute <= 1; ++Flute)
            Cylinder(ColumnTrim, Pier + FVector(-175, Flute * 65.f, 1620), 17, 3000);
        for (int32 Level = 0; Level < 4; ++Level)
            Box(Trim, Pier + FVector(-18, 0, 830 + Level * 660.f), FVector(350, 370, 23));
        const FVector Tower = Facade + FVector(70, Side * 1480.f, 0);
        const float H = Side < 0 ? 3900.f : 2800.f;
        Box(Stone, Tower + FVector(0, 0, H * .5f), FVector(470, 330, H));
        Box(Trim, Tower + FVector(0, 0, H), FVector(510, 375, 32));
        for (int32 Edge : { -1, 1 })
            Cylinder(ColumnTrim, Tower + FVector(-245, Edge * 145.f, H * .5f), 20, H);
        for (int32 Level = 0; Level < 3; ++Level)
        {
            const FVector Niche = Tower + FVector(-250, 0, 320 + Level * 760.f);
            Arch(Niche + FVector(0, -80, 0), Niche + FVector(0, 80, 0), 300, 480, 16, Trim);
            Beam(Trim, Niche + FVector(0, -80, 0), Niche + FVector(0, -80, 300), 15);
            Beam(Trim, Niche + FVector(0, 80, 0), Niche + FVector(0, 80, 300), 15);
        }
    }
    const FVector Front = Facade + FVector(-180, 0, 0);
    for (int32 Layer = 0; Layer < 3; ++Layer)
    {
        const float Half = 960 - Layer * 50.f;
        const FVector P = Front + FVector(-Layer * 22.f, 0, 0);
        Arch(P + FVector(0, -Half, 0), P + FVector(0, Half, 0), 1250, 3320 - Layer * 60.f, Layer == 0 ? 100.f : 21.f, Layer == 0 ? Stone : Trim);
        const float DoorHalf = 300 - Layer * 30.f;
        Arch(P + FVector(0, -DoorHalf, 0), P + FVector(0, DoorHalf, 0), 390, 910 - Layer * 40.f, Layer == 0 ? 55.f : 17.f, Trim);
    }
    for (int32 I = -2; I <= 2; ++I)
    {
        const float Y = I * 345.f;
        Beam(Trim, Front + FVector(-18, Y, 800), Front + FVector(-18, Y, 1760), 23);
        if (I < 2) Arch(Front + FVector(-18, Y, 0), Front + FVector(-18, Y + 345, 0), 1660, 2070, 15, Trim);
    }
    const FVector Rose = Front + FVector(-25, 0, 2500);
    RoseRing(Rose, 455, 24); RoseRing(Rose, 417, 12); RoseRing(Rose, 94, 14);
    for (int32 I = 0; I < 8; ++I)
    {
        const float Angle = I * PI / 4.f;
        const FVector Dir(0, FMath::Sin(Angle), FMath::Cos(Angle));
        Beam(Trim, Rose + Dir * 95.f, Rose + Dir * 420.f, 12);
        RoseRing(Rose + Dir * 242.f, 138, 10);
    }
    Beam(Stone, Front + FVector(60, -1160, 3160), Front + FVector(60, 0, 3820), 95);
    Beam(Stone, Front + FVector(60, 0, 3820), Front + FVector(60, 420, 3580), 85);

    for (int32 I = 0; I < 12; ++I)
    {
        const float Angle = I * PI / 6.f;
        const FVector P = Radial(Angle, 4100);
        const bool Broken = I == 1 || I == 4 || I == 8;
        const float H = Broken ? 650.f : 1280.f;
        Box(Stone, P + FVector(0, 0, 55), FVector(350, 350, 110));
        Cylinder(Columns, P + FVector(0, 0, H * .5f + 115), 96, H);
        for (int32 Rib = 0; Rib < 6; ++Rib)
            Cylinder(ColumnTrim, P + Radial(Rib * PI / 3.f, 93, H * .5f + 115), 21, H);
        Box(Trim, P + FVector(0, 0, H + 130), FVector(260, 260, 26));
        Beam(Stone, P + Radial(Angle, 150, 760), P + Radial(Angle, 450, 60), 110);
        if (I != 0 && I != 1 && I != 4 && I != 8 && I != 11)
        {
            const FVector Q = Radial(Angle + PI / 6.f, 4100);
            const bool Fragment = I == 3 || I == 7;
            Arch(P, Q, 1370, 2770, 85, Stone, Fragment ? 7 : 16, Fragment ? 3 : 16);
            Arch(P - Radial(Angle, 55), Q - Radial(Angle + PI / 6.f, 55), 1370, 2700, 18, Trim, Fragment ? 7 : 16, Fragment ? 3 : 16);
        }
    }
}

void AVeyrArena::BuildCourtTerrain()
{
    if(!bConnectedCourtAssetsReady)return;
    // Connected lower terrace and retaining cliffs replace the empty flat
    // exterior. Every city block sits on a terrain platform with a real edge.
    Box(Foundations,FVector(0,0,-310.f),FVector(15200,14000,420));
    KitWallRun(TEXT("RockRetainingWall"),FVector(-7600,-7000,0),FVector(7600,-7000,0),FVector(0,1,0),1400,-1500,false);
    KitWallRun(TEXT("RockRetainingWall"),FVector(7600,7000,0),FVector(-7600,7000,0),FVector(0,-1,0),1400,-1500,false);
    KitWallRun(TEXT("RockRetainingWall"),FVector(-7600,7000,0),FVector(-7600,-7000,0),FVector(1,0,0),1400,-1500,false);
    KitWallRun(TEXT("RockRetainingWall"),FVector(7600,-7000,0),FVector(7600,7000,0),FVector(-1,0,0),1400,-1500,false);
    // A northern city terrace and eastern sanctuary terrace create layered
    // inhabited-scale ruins behind the lower cloister, rather than blue cubes.
    Box(Foundations,FVector(0,12000,400),FVector(22000,6000,1200));
    Box(Foundations,FVector(12500,0,850),FVector(6000,20000,1500));
    KitWallRun(TEXT("RockRetainingWall"),FVector(-11000,9000,0),FVector(11000,9000,0),FVector(0,-1,0),1400,-400,false);
    KitWallRun(TEXT("RockRetainingWall"),FVector(9500,-10000,0),FVector(9500,10000,0),FVector(-1,0,0),2000,-400,false);
    for(int32 Row=0;Row<2;++Row)for(int32 I=-3;I<=3;++I)
    {
        const float Height=1600.f+((I+Row+8)%3)*200.f;
        KitPiece(TEXT("RuinedCityRoofBlock"),FVector(I*2850.f,10500.f+Row*2800.f,1000.f),Height,180.f+(I%2)*12.f,false);
    }
    for(int32 I=-3;I<=3;++I)
        KitPiece(TEXT("RuinedCityRoofBlock"),FVector(11900.f+(I%2)*1100.f,I*2600.f,1600.f),1800.f+(I%2)*220.f,-90.f,false);
    KitPiece(TEXT("RuinedGatehouse"),FVector(-6000,13000,1000),3000,180,false);
    KitPiece(TEXT("RuinedGatehouse"),FVector(12500,4500,1600),3200,-90,false);
    ImportedPiece(CathedralFacadeMesh,TEXT("FarCityCathedralSpire"),FVector(1500,13600,1000),4200,180,true);
    for(float Side:{-1.f,1.f})
    {
        for(int32 I=0;I<5;++I)
            KitPiece(TEXT("CollapsedVaultRubble"),FVector(-5500+I*2500.f,Side*5800.f,-100.f),250.f+(I%2)*65.f,I*57.f,false);
        KitPiece(TEXT("AncientDeadTree"),FVector(6100,Side*5800,-100),1100,Side*80,false);
        KitPiece(TEXT("RuinedCityRoofBlock"),FVector(-6500,Side*4800,-100),1800,Side*90,false);
    }
}

void AVeyrArena::BuildDistance()
{
    BuildCourtTerrain();
    UStaticMesh* FlamePlane=LoadObject<UStaticMesh>(nullptr,TEXT("/Engine/BasicShapes/Plane.Plane"),nullptr,LOAD_Quiet|LOAD_NoWarn);
    UMaterialInterface* FlameMaterial=LoadObject<UMaterialInterface>(nullptr,TEXT("/Game/Veyr/FX/v3/M_VeyrBreathFlame.M_VeyrBreathFlame"),nullptr,LOAD_Quiet|LOAD_NoWarn);
    UInstancedStaticMeshComponent* FlameCards=nullptr;
    if(FlamePlane&&FlameMaterial)
    {
        FlameCards=MakeBatch(TEXT("CourtBrazierAtlasFlames"),FlamePlane,FlameMaterial);
        FlameCards->SetNumCustomDataFloats(4);FlameCards->SetCastShadow(false);
    }
    int32 Index=0;
    auto Brazier=[&](const FVector& P)
    {
        const int32 I=Index++;
        if(CathedralBrazierMesh)
            ImportedPiece(CathedralBrazierMesh,FName(*FString::Printf(TEXT("CourtBrazier%02d"),I)),P,180.f,0.f,false);
        if(FlameCards)
            for(int32 Cross=0;Cross<3;++Cross)
            {
                const int32 Instance=FlameCards->AddInstance(FTransform(FRotator(90,Cross*60.f,0),P+FVector(0,0,198),FVector(.72f,.38f,1)));
                FlameCards->SetCustomDataValue(Instance,0,.45f,false);FlameCards->SetCustomDataValue(Instance,1,FMath::Frac(I*.618f+Cross*.23f),false);
                FlameCards->SetCustomDataValue(Instance,2,.25f,false);FlameCards->SetCustomDataValue(Instance,3,1.f,false);
            }
        else Box(Embers,P+FVector(0,0,165),FVector(55,55,8));
        auto* Light=NewObject<UPointLightComponent>(this,*FString::Printf(TEXT("CourtAmberBrazier%02d"),I));
        AddInstanceComponent(Light);Light->SetupAttachment(GetRootComponent());Light->SetMobility(EComponentMobility::Movable);
        Light->SetRelativeLocation(P+FVector(0,0,210));Light->SetIntensityUnits(ELightUnits::Candelas);Light->SetIntensity(190.f);
        Light->SetLightColor(FLinearColor(1.f,.43f,.13f),false);Light->SetAttenuationRadius(1000.f);Light->SetSourceRadius(45.f);
        Light->SetCastShadows(false);Light->SetSpecularScale(.7f);Light->RegisterComponent();
    };
    for(float Side:{-1.f,1.f})
    {
        for(float X:{-3300.f,0.f,3300.f})Brazier(FVector(X,Side*3980.f,0));
        for(float Y:{-2400.f,2400.f})Brazier(FVector(Side*4300.f,Y,0));
        Brazier(FVector(-4550,Side*750.f,AisleHeight));
    }
    if(FlameCards)FlameCards->MarkRenderStateDirty();
}

void AVeyrArena::BuildLighting()
{
    auto* Moon = NewObject<UDirectionalLightComponent>(this, TEXT("PrototypeSoftMoonKey"));
    AddInstanceComponent(Moon); Moon->SetupAttachment(GetRootComponent()); Moon->SetMobility(EComponentMobility::Movable);
    // The visible disc and lighting share this direction. A low moon remains
    // in the playable camera's upper sky without violating floor framing.
    Moon->SetRelativeRotation(FRotator(-14, -155, 0));
    // Only the moon drives forward/translucent lighting. Keeping priorities
    // distinct avoids the competing-directional-lights warning seen in PIE001.
    Moon->SetForwardShadingPriority(1);
    Moon->SetIntensity(2.7f); Moon->SetLightColor(FLinearColor(.63f, .76f, 1.f), false);
    Moon->SetCastShadows(true); Moon->SetLightSourceAngle(8.f); Moon->SetSpecularScale(.65f); Moon->RegisterComponent();
    auto* Fill = NewObject<UDirectionalLightComponent>(this, TEXT("PrototypeNeutralFrontFill"));
    AddInstanceComponent(Fill); Fill->SetupAttachment(GetRootComponent()); Fill->SetMobility(EComponentMobility::Movable);
    Fill->SetForwardShadingPriority(0);
    Fill->SetRelativeRotation(FRotator(-20, 0, 0)); Fill->SetIntensity(1.35f);
    Fill->SetLightColor(FLinearColor(.86f, .90f, 1.f), false); Fill->SetCastShadows(false); Fill->SetSpecularScale(.45f); Fill->RegisterComponent();

    if (SkyMesh && (NightSkyParent||SkyParent))
    {
        auto* Sky = NewObject<UStaticMeshComponent>(this, TEXT("PROTO_EngineSkyOriginalPalette"));
        AddInstanceComponent(Sky); Sky->SetupAttachment(GetRootComponent()); Sky->SetStaticMesh(SkyMesh);
        Sky->SetCollisionEnabled(ECollisionEnabled::NoCollision); Sky->SetCastShadow(false);
        Sky->SetCanEverAffectNavigation(false);
        const float Scale = 200000.f / FMath::Max(1.f, static_cast<float>(SkyMesh->GetBounds().SphereRadius));
        Sky->SetRelativeScale3D(FVector(Scale));
        auto* Material = UMaterialInstanceDynamic::Create(NightSkyParent?NightSkyParent.Get():SkyParent.Get(), this);
        Materials.Add(Material);
        const FVector MoonDirection=-Moon->GetForwardVector();
        Material->SetVectorParameterValue(TEXT("MoonDirection"),FLinearColor(MoonDirection.X,MoonDirection.Y,MoonDirection.Z,0));
        Material->SetScalarParameterValue(TEXT("CloudOpacity"),.95f);
        Material->SetScalarParameterValue(TEXT("CloudSpeed"),.02f);
        Material->SetScalarParameterValue(TEXT("StarBrightness"),.32f);
        Material->SetVectorParameterValue(TEXT("CloudColor"),FLinearColor(.30f,.35f,.42f));
        Material->SetVectorParameterValue(TEXT("HorizonColor"),FLinearColor(.035f,.048f,.068f));
        Material->SetVectorParameterValue(TEXT("Zenith Color"), FLinearColor(.018f, .030f, .060f));
        Material->SetVectorParameterValue(TEXT("Horizon color"), FLinearColor(.065f, .090f, .13f));
        Material->SetVectorParameterValue(TEXT("Cloud color"), FLinearColor(.12f, .15f, .19f));
        Material->SetVectorParameterValue(TEXT("Overall Color"), FLinearColor::White);
        Material->SetVectorParameterValue(TEXT("Light direction"), FLinearColor(.85f, .32f, .25f, 0));
        Material->SetVectorParameterValue(TEXT("Sun color"), FLinearColor(.55f, .66f, .82f));
        Material->SetScalarParameterValue(TEXT("Sun brightness"), .5f);
        Material->SetScalarParameterValue(TEXT("Sun Radius"), .018f);
        Material->SetScalarParameterValue(TEXT("Cloud opacity"), .78f);
        Material->SetScalarParameterValue(TEXT("Cloud speed"), .08f);
        Material->SetScalarParameterValue(TEXT("Stars brightness"), .03f);
        Sky->SetMaterial(0, Material); Sky->RegisterComponent();
    }
    auto* Ambient = NewObject<USkyLightComponent>(this, TEXT("PrototypeGentleSkyBounce"));
    AddInstanceComponent(Ambient); Ambient->SetupAttachment(GetRootComponent()); Ambient->SetMobility(EComponentMobility::Movable);
    // Capture the authored night instead of tinting the engine's unrelated
    // default HDR cubemap. Only the distant sky is inside the capture domain.
    Ambient->SourceType=SLS_CapturedScene;
    Ambient->SetRealTimeCapture(false);
    Ambient->SkyDistanceThreshold=50000.f;
    Ambient->SetIntensity(1.15f);Ambient->SetLightColor(FLinearColor(.92f,.96f,1.f));
    Ambient->SetLowerHemisphereColor(FLinearColor(.025f,.035f,.05f));Ambient->RegisterComponent();

    auto* Fog = NewObject<UExponentialHeightFogComponent>(this, TEXT("PrototypeDrownedCathedralMist"));
    AddInstanceComponent(Fog); Fog->SetupAttachment(GetRootComponent());
    Fog->SetRelativeLocation(FVector(0, 0, -150));
    Fog->SetFogDensity(.018f); Fog->SetFogHeightFalloff(.35f);
    Fog->SetFogInscatteringColor(FLinearColor(.038f, .050f, .065f));
    Fog->SetStartDistance(3000); Fog->SetFogMaxOpacity(.82f);
    // A restrained low layer on the existing fog component softens the distant
    // platform/ridge join. The inner fight stays ahead of the fog start plane.
    Fog->SetSecondFogDensity(.015f);
    Fog->SetSecondFogHeightOffset(240.f);
    Fog->SetSecondFogHeightFalloff(1.2f);
    Fog->SetVolumetricFog(false); // native layout baseline; no unmeasured volume cost
    Fog->RegisterComponent();

    auto* Grade = NewObject<UPostProcessComponent>(this, TEXT("PrototypeReadableMoonlitExposure"));
    AddInstanceComponent(Grade); Grade->SetupAttachment(GetRootComponent()); Grade->bUnbound = true;
    Grade->Settings.bOverride_AutoExposureMethod = true; Grade->Settings.AutoExposureMethod = AEM_Manual;
    Grade->Settings.bOverride_AutoExposureApplyPhysicalCameraExposure = true; Grade->Settings.AutoExposureApplyPhysicalCameraExposure = false;
    // Restrained fixed exposure preserves the night palette without pumping
    // when fire or the giant fills the frame. Verify this balance in native PIE.
    Grade->Settings.bOverride_AutoExposureBias = true; Grade->Settings.AutoExposureBias = -.25f;
    Grade->Settings.bOverride_BloomIntensity = true; Grade->Settings.BloomIntensity = .18f;
    Grade->Settings.bOverride_VignetteIntensity = true; Grade->Settings.VignetteIntensity = .12f;
    Grade->RegisterComponent();
    // One queued capture after sky and fog registration. No frame tick,
    // recurring timer, or real-time capture is enabled by the arena.
    Ambient->RecaptureSky();
}

void AVeyrArena::BuildCollision()
{
    // Collision corresponds to rendered masonry, floors, portcullis bars and
    // imported meshes. There is deliberately no invisible radius wall.
    for(UInstancedStaticMeshComponent* Batch:{Floor,FloorSurface,Foundations,BoundaryStone,Bronze})
        if(Batch)
        {
            Batch->SetCollisionProfileName(TEXT("BlockAll"));Batch->SetCollisionEnabled(ECollisionEnabled::QueryAndPhysics);
            Batch->SetGenerateOverlapEvents(false);
        }
}
