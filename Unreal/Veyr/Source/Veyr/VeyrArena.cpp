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
#include "Engine/TextureCube.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "UObject/ConstructorHelpers.h"

namespace
{
    FVector Radial(float Angle, float Radius, float Height = 0.f)
    {
        return FVector(FMath::Cos(Angle) * Radius, FMath::Sin(Angle) * Radius, Height);
    }
}

AVeyrArena::AVeyrArena()
{
    PrimaryActorTick.bCanEverTick = false;
    USceneComponent* Scene = CreateDefaultSubobject<USceneComponent>(TEXT("PrototypeArenaRoot"));
    Scene->SetMobility(EComponentMobility::Static);
    SetRootComponent(Scene);
    Tags.Add(TEXT("VeyrOriginalLayout"));
    Tags.Add(TEXT("PrototypeEnginePrimitives_NotCustomuse"));

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
    static ConstructorHelpers::FObjectFinder<UTextureCube> CubeMap(TEXT("/Engine/EngineMaterials/DefaultCubemap.DefaultCubemap"));
    static ConstructorHelpers::FObjectFinderOptional<UStaticMesh> Facade(TEXT("/Game/ArtPass/Tripo/CathedralFacade_v001/SM_CathedralFacade_v001.SM_CathedralFacade_v001"),LOAD_Quiet|LOAD_NoWarn);
    static ConstructorHelpers::FObjectFinderOptional<UStaticMesh> Wall(TEXT("/Game/ArtPass/Tripo/CathedralWall_v001/SM_CathedralWall_v001.SM_CathedralWall_v001"),LOAD_Quiet|LOAD_NoWarn);
    static ConstructorHelpers::FObjectFinderOptional<UStaticMesh> GothicArch(TEXT("/Game/ArtPass/Tripo/CathedralArch_v001/SM_CathedralArch_v001.SM_CathedralArch_v001"),LOAD_Quiet|LOAD_NoWarn);
    static ConstructorHelpers::FObjectFinderOptional<UMaterialInterface> Night(TEXT("/Game/ArtPass/Sky/M_CathedralNight_v002.M_CathedralNight_v002"),LOAD_Quiet|LOAD_NoWarn);
    CathedralFacadeMesh=Facade.Get();CathedralWallMesh=Wall.Get();CathedralArchMesh=GothicArch.Get();NightSkyParent=Night.Get();
    BasaltCliffMesh=BasaltCliff.Get();
    CubeMesh = Cube.Object; CylinderMesh = CylinderAsset.Object; SphereMesh = Sphere.Object; ConeMesh = Cone.Object;
    PlainParent=Base.Object;StoneParent=AuthoredStone.Get()?AuthoredStone.Get():Base.Object.Get();
    SkyMesh = Sky.Object; SkyParent = SkyMaterial.Object; AmbientCube = CubeMap.Object;
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
    if(!NightSkyParent)NightSkyParent=LoadObject<UMaterialInterface>(nullptr,TEXT("/Game/ArtPass/Sky/M_CathedralNight_v002.M_CathedralNight_v002"),nullptr,LOAD_Quiet|LOAD_NoWarn);
    bUsingAuthoredNightSky=NightSkyParent!=nullptr;
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
    if(!bUsingImportedCathedral)BuildCathedral();
    BuildDistance();
    BuildLighting();
    BuildCollision();
    UE_LOG(LogTemp, Display, TEXT("VEYR_ARENA_READY native prototype: radius=3600cm floorZ=0; %d instanced groups; original layout, engine primitive dependencies."), Batches.Num());
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

void AVeyrArena::BuildFloor()
{
    Cylinder(DarkDisks, FVector(0, 0, -45), CombatRadius + 90.f, 90);
    Cylinder(DarkDisks, FVector(0, 0, -190), 16000, 50); // dark moat, no collision
    FRandomStream Random(3187);
    for (int32 Row = -12; Row <= 12; ++Row)
    {
        const float Y=Row*280.f,Radius=CombatRadius-130.f;
        const float HalfRow=FMath::Sqrt(FMath::Max(0.f,Radius*Radius-Y*Y));
        float X=-HalfRow;
        while(X<HalfRow-60.f)
        {
            const float Span=FMath::Min(Random.FRandRange(310.f,530.f),HalfRow-X);
            const FVector P(X+Span*.5f,Y,-5.f);
            // Coherent meter-scale weathering regions, not checkerboard
            // random colors. Decorative surfaces still meet the flat Z0 floor.
            const float Damp=FMath::PerlinNoise2D(FVector2D(P.X+617.f,P.Y-231.f)/1150.f);
            const float Wear=FMath::PerlinNoise2D(FVector2D(P.X-1200.f,P.Y+500.f)/1700.f);
            UInstancedStaticMeshComponent* Batch=Damp>.15f?FloorWet:Wear<-.18f?FloorLight:Floor;
            Box(Batch,P,FVector(Span-Random.FRandRange(4.f,8.f),273.f,10.f));
            X+=Span;
        }
    }
    for (const float Radius : { 380.f, 900.f, 1850.f, 3140.f, 3570.f })
    {
        const int32 Segments = 128;
        for (int32 I = 0; I < Segments; ++I)
        {
            const float Angle = (I + .5f) * 2.f * PI / Segments;
            Box(Bronze, Radial(Angle, Radius, .8f), FVector(3.5f, Radius * 2.f * PI / Segments + 1.f, 1.6f), FRotator(0, FMath::RadiansToDegrees(Angle), 0));
        }
    }
    // Low stone coping makes the bounded play space legible. No obstacles are
    // placed inside the circle: flight landings and leg approaches stay clear.
    for (int32 I = 0; I < 96; ++I)
    {
        const float Angle = I * 2.f * PI / 96.f;
        Box(Trim, Radial(Angle, 3635.f, 16.f), FVector(90, 242, 32), FRotator(0, FMath::RadiansToDegrees(Angle), 0));
    }
}

void AVeyrArena::ImportedPiece(UStaticMesh* Mesh,const FName Name,const FVector& Position,float Height,float Yaw)
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
    const float PushOut=FMath::Max(0.f,CombatRadius+450.f+RadialDepth-static_cast<float>(Position.Size2D())-CenterOffset);
    Piece->SetRelativeLocation(Position+Outward*PushOut-FVector(0,0,Bounds.Min.Z*Scale));
    Piece->SetRelativeRotation(Facing);Piece->SetRelativeScale3D(FVector(Scale));
    Piece->SetCollisionEnabled(ECollisionEnabled::NoCollision);Piece->SetGenerateOverlapEvents(false);
    Piece->SetCanEverAffectNavigation(false);Piece->RegisterComponent();++ImportedArchitecturePieces;
}

bool AVeyrArena::BuildImportedCathedral()
{
    ImportedPiece(CathedralFacadeMesh,TEXT("TripoCathedralFacade"),FVector(5400,0,0),3200,CathedralFacingYawOffset);
    for(int32 I=0;I<4;++I)
    {
        const float Angle=FMath::DegreesToRadians(I==0?70.f:I==1?-70.f:I==2?140.f:-140.f);
        ImportedPiece(CathedralWallMesh,FName(*FString::Printf(TEXT("TripoCathedralWall%d"),I)),Radial(Angle,5200),2000,
            FMath::RadiansToDegrees(Angle)+CathedralFacingYawOffset);
        const float ArchAngle=FMath::DegreesToRadians(I==0?35.f:I==1?-35.f:I==2?110.f:-110.f);
        ImportedPiece(CathedralArchMesh,FName(*FString::Printf(TEXT("TripoCathedralArch%d"),I)),Radial(ArchAngle,4500),1600,
            FMath::RadiansToDegrees(ArchAngle)+CathedralFacingYawOffset);
    }
    return ImportedArchitecturePieces>0;
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

void AVeyrArena::BuildDistance()
{
    FRandomStream Random(6194);
    for (int32 I = 0; I < 23; ++I)
    {
        const float Angle=(I+Random.FRandRange(-.25f,.25f))*2.f*PI/23.f;
        const float Yaw=FMath::RadiansToDegrees(Angle);
        const FVector P=Radial(Angle,Random.FRandRange(13500,16500),-500);
        const float Height=Random.FRandRange(1500,2900);
        // Original unit-bounds basalt is centered at its pivot, matching the
        // existing cube's100cm sizing contract. Rotate the asymmetric crest
        // through several views without changing the deterministic layout.
        const float CrestYaw=bUsingBasaltCliff?(I%4)*90.f:0.f;
        // All backdrop instances stay outside the cathedral and play space.
        Box(Rocks,P+FVector(0,0,Height*.5f),FVector(Random.FRandRange(1500,2100),Random.FRandRange(2300,3400),Height),
            FRotator(Random.FRandRange(-14,9),Yaw+CrestYaw+Random.FRandRange(-16,16),Random.FRandRange(-13,13)));
        const FVector Shoulder=P+Radial(Angle+PI*.5f,Random.FRandRange(700,1200),Height*.26f);
        Box(Rocks,Shoulder,FVector(Random.FRandRange(1100,1700),Random.FRandRange(900,1600),Height*.75f),
            FRotator(Random.FRandRange(-18,14),Yaw-CrestYaw+Random.FRandRange(-30,30),Random.FRandRange(-22,18)));
        if(I%3==0)
        {
            const float SpurHeight=Random.FRandRange(550,900);
            Box(RockSpurs,P+Radial(Angle+PI*.5f,Random.FRandRange(-500,500),Height+SpurHeight*.15f),
                FVector(Random.FRandRange(280,430),Random.FRandRange(400,650),SpurHeight),
                FRotator(Random.FRandRange(-20,16),Yaw+CrestYaw,Random.FRandRange(-18,20)));
        }
    }
    for (int32 I = 0; I < 24; ++I)
    {
        const float Angle = Random.FRandRange(0, 2.f * PI);
        const FVector Size(Random.FRandRange(80, 230), Random.FRandRange(90, 230), Random.FRandRange(65, 170));
        Box(Stone, Radial(Angle, Random.FRandRange(3930, 4900), Size.Z * .25f - 20), Size,
            FRotator(Random.FRandRange(-18, 18), Random.FRandRange(0, 180), Random.FRandRange(-12, 12)));
    }
    for (int32 I = 0; I < 8; ++I)
    {
        const float Angle = (I + .5f) * PI / 4.f;
        const FVector P = Radial(Angle, 3740);
        Cylinder(Columns, P + FVector(0, 0, 60), 105, 120);
        Cylinder(ColumnTrim, P + FVector(0, 0, 126), 110, 20);
        Box(Embers, P + FVector(0, 0, 159), FVector(132, 132, 28));
        for (int32 Tine = 0; Tine < 6; ++Tine)
            Beam(Bronze, P + Radial(Tine * PI / 3.f, 68, 132), P + Radial(Tine * PI / 3.f, 85, 225), 7);
        auto* Light = NewObject<UPointLightComponent>(this, *FString::Printf(TEXT("PrototypeAmberBrazier%d"), I));
        AddInstanceComponent(Light); Light->SetupAttachment(GetRootComponent());
        Light->SetMobility(EComponentMobility::Movable);
        Light->SetRelativeLocation(P + FVector(0, 0, 205));
        Light->SetIntensityUnits(ELightUnits::Candelas); Light->SetIntensity(380.f);
        Light->SetLightColor(FLinearColor(1.f, .37f, .10f), false);
        Light->SetAttenuationRadius(1050); Light->SetSourceRadius(45);
        Light->SetCastShadows(false); Light->SetSpecularScale(.55f); Light->RegisterComponent();
    }
}

void AVeyrArena::BuildLighting()
{
    auto* Moon = NewObject<UDirectionalLightComponent>(this, TEXT("PrototypeSoftMoonKey"));
    AddInstanceComponent(Moon); Moon->SetupAttachment(GetRootComponent()); Moon->SetMobility(EComponentMobility::Movable);
    // The visible disc and lighting share this direction. A low moon remains
    // in the playable camera's upper sky without violating floor framing.
    Moon->SetRelativeRotation(FRotator(-18, -155, 0));
    // Only the moon drives forward/translucent lighting. Keeping priorities
    // distinct avoids the competing-directional-lights warning seen in PIE001.
    Moon->SetForwardShadingPriority(1);
    Moon->SetIntensity(3.4f); Moon->SetLightColor(FLinearColor(.63f, .76f, 1.f), false);
    Moon->SetCastShadows(true); Moon->SetLightSourceAngle(3.f); Moon->SetSpecularScale(.75f); Moon->RegisterComponent();
    auto* Fill = NewObject<UDirectionalLightComponent>(this, TEXT("PrototypeNeutralFrontFill"));
    AddInstanceComponent(Fill); Fill->SetupAttachment(GetRootComponent()); Fill->SetMobility(EComponentMobility::Movable);
    Fill->SetForwardShadingPriority(0);
    Fill->SetRelativeRotation(FRotator(-20, 0, 0)); Fill->SetIntensity(2.4f);
    Fill->SetLightColor(FLinearColor(.80f, .87f, 1.f), false); Fill->SetCastShadows(false); Fill->SetSpecularScale(.6f); Fill->RegisterComponent();

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
    if (AmbientCube) { Ambient->SourceType = SLS_SpecifiedCubemap; Ambient->SetCubemap(AmbientCube); }
    Ambient->SetIntensity(.7f); Ambient->SetLightColor(FLinearColor(.52f, .60f, .72f));
    Ambient->SetLowerHemisphereColor(FLinearColor(.10f, .12f, .15f)); Ambient->RegisterComponent();

    auto* Fog = NewObject<UExponentialHeightFogComponent>(this, TEXT("PrototypeDrownedCathedralMist"));
    AddInstanceComponent(Fog); Fog->SetupAttachment(GetRootComponent());
    Fog->SetRelativeLocation(FVector(0, 0, -150));
    Fog->SetFogDensity(.009f); Fog->SetFogHeightFalloff(.22f);
    Fog->SetFogInscatteringColor(FLinearColor(.065f, .09f, .13f));
    Fog->SetStartDistance(2200); Fog->SetFogMaxOpacity(.65f);
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
}

void AVeyrArena::BuildCollision()
{
    // One perfectly flat contact surface. Decorative paver seams never catch a
    // capsule. Perimeter blocks also stop the camera; the center has no scenery.
    auto* Ground = NewObject<UBoxComponent>(this, TEXT("ArenaFloorCollisionZ0"));
    AddInstanceComponent(Ground); Ground->SetupAttachment(GetRootComponent());
    Ground->SetRelativeLocation(FVector(0, 0, -50)); Ground->SetBoxExtent(FVector(3690, 3690, 50));
    Ground->SetCollisionProfileName(TEXT("BlockAll")); Ground->SetGenerateOverlapEvents(false); Ground->RegisterComponent();
    for (int32 I = 0; I < 48; ++I)
    {
        const float Angle = (I + .5f) * 2.f * PI / 48.f;
        auto* Wall = NewObject<UBoxComponent>(this, *FString::Printf(TEXT("ArenaBoundary%02d"), I));
        AddInstanceComponent(Wall); Wall->SetupAttachment(GetRootComponent());
        Wall->SetRelativeLocation(Radial(Angle, 3670, 600));
        Wall->SetRelativeRotation(FRotator(0, FMath::RadiansToDegrees(Angle), 0));
        Wall->SetBoxExtent(FVector(65, 245, 600));
        Wall->SetCollisionProfileName(TEXT("BlockAll")); Wall->SetGenerateOverlapEvents(false); Wall->RegisterComponent();
    }
}
