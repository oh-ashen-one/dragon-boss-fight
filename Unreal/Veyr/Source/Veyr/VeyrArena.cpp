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
    Foundations=MakeBatch(TEXT("ConnectedCathedralFoundations"),CubeMesh,FloorMaterial);
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
    // A single continuous rendered circle replaces the oversized cube grid.
    // The generated albedo tiles in world XY at400cm; collision remains Z0.
    Cylinder(FloorSurface,FVector(0,0,-4.8f),CombatRadius+80.f,10.f);
    Cylinder(FloorSurface,FVector(0,0,-121.f),7500.f,240.f);
    Cylinder(DarkDisks,FVector(0,0,-250.f),32000.f,80.f);
    for(float Radius:{900.f,3140.f})
        for(int32 I=0;I<128;++I)
        {
            const float Angle=(I+.5f)*2.f*PI/128.f;
            Box(FloorCarvings,Radial(Angle,Radius,.3f),FVector(1.6f,Radius*2.f*PI/128.f+.5f,.25f),FRotator(0,FMath::RadiansToDegrees(Angle),0));
        }
    // Four broad remnants read as the former nave boundary, not scattered props.
    for(float Side:{-1.f,1.f})for(float X:{-1800.f,1800.f})
        Box(BoundaryStone,FVector(X,Side*3900.f,55.f),FVector(1900.f,170.f,110.f));
    // A dark, grounded low parapet replaces the bright unbroken curb strip.
    // Few broad segments have narrow joints; the collision boundary is unchanged.
    for(int32 I=0;I<32;++I)
    {
        const float Angle=I*2.f*PI/32.f;
        const float Height=(I%7==0)?68.f:94.f;
        Box(BoundaryStone,Radial(Angle,3635.f,Height*.5f),FVector(105.f,2.f*PI*3635.f/32.f-20.f,Height),
            FRotator(0,FMath::RadiansToDegrees(Angle),0));
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
        FVector PlinthCenter=BasePosition+Facing.RotateVector(Bounds.GetCenter()*Scale);PlinthCenter.Z=-120.f;
        const FVector Support(Bounds.GetSize().X*Scale+220.f,Bounds.GetSize().Y*Scale+220.f,240.f);
        Box(Foundations,PlinthCenter,Support,Facing);
        const float Reach=PlinthCenter.Size2D();
        FVector Connector=Outward*(Reach*.5f);Connector.Z=-120.5f;
        Box(Foundations,Connector,FVector(Reach+100.f,1400.f,240.f),Outward.Rotation());
    }
    Piece->SetRelativeRotation(Facing);Piece->SetRelativeScale3D(FVector(Scale));
    Piece->SetCollisionEnabled(ECollisionEnabled::NoCollision);Piece->SetGenerateOverlapEvents(false);
    Piece->SetCanEverAffectNavigation(false);Piece->RegisterComponent();if(bArchitecture)++ImportedArchitecturePieces;
}

bool AVeyrArena::BuildImportedCathedral()
{
    // Reveal the rose/portal beside the boss silhouette, opposite the moon.
    ImportedPiece(CathedralFacadeMesh,TEXT("TripoCathedralFacade"),FVector(5000,-1100,0),3200,CathedralFacingYawOffset);
    // Repeated wall bays and arches share two nave lines, with one terminal
    // facade. Eleven major meshes replace the disconnected radial display.
    int32 Index=0;
    for(float Side:{-1.f,1.f})
    {
        const float FacingYaw=CathedralFacingYawOffset+(Side>0.f?90.f:-90.f)-Side*20.f;
        for(float X:{700.f,3200.f})
            ImportedPiece(CathedralWallMesh,FName(*FString::Printf(TEXT("TripoNaveWall%d"),Index++)),FVector(X,Side*4100.f,0),2000,FacingYaw);
        for(float X:{-1200.f,1800.f,4200.f})
            ImportedPiece(CathedralArchMesh,FName(*FString::Printf(TEXT("TripoNaveArch%d"),Index++)),FVector(X,Side*3900.f,0),1600,FacingYaw);
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
    for(int32 I=0;I<16;++I)
    {
        const float Angle=(I+Random.FRandRange(-.2f,.2f))*2.f*PI/16.f;
        const float Yaw=FMath::RadiansToDegrees(Angle);
        const FVector P=Radial(Angle,Random.FRandRange(22000.f,28000.f),-600.f);
        const float Height=Random.FRandRange(900.f,1600.f);
        const float CrestYaw=bUsingBasaltCliff?(I%4)*90.f:0.f;
        // Low distant ridges occupy the haze band. Tall near-black geometric
        // needles no longer compete with the imported Gothic architecture.
        Box(Rocks,P+FVector(0,0,Height*.5f),FVector(Random.FRandRange(4000.f,6500.f),Random.FRandRange(5000.f,7500.f),Height),
            FRotator(Random.FRandRange(-4.f,4.f),Yaw+CrestYaw,Random.FRandRange(-3.f,3.f)));
        Box(Rocks,P+Radial(Angle+PI*.5f,2100.f,Height*.22f),FVector(3500,4400,Height*.55f),FRotator(0,Yaw-CrestYaw,0));
        if(I%2==0)
            Box(Rocks,Radial(Angle,27000.f,-50.f),FVector(6500,14000,850),FRotator(0,Yaw,0));
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
        if(CathedralBrazierMesh)
        {
            ImportedPiece(CathedralBrazierMesh,FName(*FString::Printf(TEXT("TripoCathedralBrazier%d"),I)),P,180.f,
                FMath::RadiansToDegrees(Angle),false);
            Box(Embers,P+FVector(0,0,164),FVector(60,60,9));
            // Small native ember tongues sit within the imported bowl; the
            // authored brazier remains the visible structure and keeps its PBR.
            for(int32 Flame=0;Flame<3;++Flame)
                Box(Embers,P+FVector((Flame-1)*14.f,0,176.f+Flame*3),FVector(8,8,20+Flame*5),FRotator(0,0,(Flame-1)*12.f));
        }
        else
        {
            Cylinder(Columns,P+FVector(0,0,60),105,120);
            Cylinder(ColumnTrim,P+FVector(0,0,126),110,20);
            Box(Embers,P+FVector(0,0,159),FVector(132,132,28));
            for(int32 Tine=0;Tine<6;++Tine)
                Beam(Bronze,P+Radial(Tine*PI/3.f,68,132),P+Radial(Tine*PI/3.f,85,225),7);
        }
        auto* Light = NewObject<UPointLightComponent>(this, *FString::Printf(TEXT("PrototypeAmberBrazier%d"), I));
        AddInstanceComponent(Light); Light->SetupAttachment(GetRootComponent());
        Light->SetMobility(EComponentMobility::Movable);
        Light->SetRelativeLocation(P + FVector(0, 0, 205));
        Light->SetIntensityUnits(ELightUnits::Candelas); Light->SetIntensity(220.f);
        Light->SetLightColor(FLinearColor(1.f, .44f, .17f), false);
        Light->SetAttenuationRadius(650); Light->SetSourceRadius(60);
        Light->SetCastShadows(false); Light->SetSpecularScale(.55f); Light->RegisterComponent();
    }
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
    Moon->SetIntensity(3.f); Moon->SetLightColor(FLinearColor(.63f, .76f, 1.f), false);
    Moon->SetCastShadows(true); Moon->SetLightSourceAngle(8.f); Moon->SetSpecularScale(.65f); Moon->RegisterComponent();
    auto* Fill = NewObject<UDirectionalLightComponent>(this, TEXT("PrototypeNeutralFrontFill"));
    AddInstanceComponent(Fill); Fill->SetupAttachment(GetRootComponent()); Fill->SetMobility(EComponentMobility::Movable);
    Fill->SetForwardShadingPriority(0);
    Fill->SetRelativeRotation(FRotator(-20, 0, 0)); Fill->SetIntensity(2.7f);
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
    Ambient->SetIntensity(2.5f);Ambient->SetLightColor(FLinearColor(.92f,.96f,1.f));
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
