#include "VeyrArena.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Components/SpotLightComponent.h"
#include "Engine/StaticMesh.h"
#include "Materials/MaterialInterface.h"

namespace
{
    constexpr float FortressFloorZ=0.f;
    constexpr float FortressHalfX=5100.f,FortressHalfY=4500.f;
}

bool AVeyrArena::LoadFortressKit()
{
    FortressMeshCount=0;FortressMuralMaterials.Reset();
    for(const TCHAR* Name:{TEXT("FortressGatehouse"),TEXT("FortressPaintedWall"),TEXT("FortressWatchtower"),TEXT("FortressCurtainWall"),TEXT("FortressBrazier")})
    {
        const FString Path=FString::Printf(TEXT("/Game/ArtPass/Tripo/%s_v001/SM_%s_v001.SM_%s_v001"),Name,Name,Name);
        UStaticMesh* Mesh=LoadObject<UStaticMesh>(nullptr,*Path,nullptr,LOAD_Quiet|LOAD_NoWarn);
        if(!Mesh||Mesh->GetNumLODs()<3||Mesh->GetBoundingBox().GetSize().GetMin()<1.f)
        {ConnectedCourtDiagnostic+=FString::Printf(TEXT("; %s missing/invalid"),Name);continue;}
        if(FCString::Strcmp(Name,TEXT("FortressPaintedWall"))==0&&Mesh->GetStaticMaterials().Num()!=2)
        {ConnectedCourtDiagnostic+=TEXT("; mural wall must retain stone and plaster sections");continue;}
        PolishMeshes.Add(FName(Name),Mesh);ConnectedMeshDimensionsCm.Add(FName(Name),Mesh->GetBoundingBox().GetSize());++FortressMeshCount;
    }
    for(int32 I=1;I<=4;++I)
    {
        const FString Path=FString::Printf(TEXT("/Game/ArtPass/FortressMurals/v002/MI_Mural%02d.MI_Mural%02d"),I,I);
        UMaterialInterface* Material=LoadObject<UMaterialInterface>(nullptr,*Path,nullptr,LOAD_Quiet|LOAD_NoWarn);
        if(Material)FortressMuralMaterials.Add(Material);
    }
    bFortressAssetsReady=FortressMeshCount==5&&FortressMuralMaterials.Num()==4;
    if(!bFortressAssetsReady)UE_LOG(LogTemp,Error,TEXT("VEYR_FORTRESS_MISSING meshes=%d/5 muralMaterials=%d/4"),FortressMeshCount,FortressMuralMaterials.Num());
    return bFortressAssetsReady;
}

void AVeyrArena::FortressMuralBay(const FVector& Anchor,float Height,float Yaw,int32 MuralIndex)
{
    if(!FortressMuralMaterials.IsValidIndex(MuralIndex))return;
    UStaticMesh* Mesh=PolishMeshes.FindRef(TEXT("FortressPaintedWall"));if(!Mesh)return;
    const FBox Bounds=Mesh->GetBoundingBox();const float Scale=Height/static_cast<float>(Bounds.GetSize().Z);
    const FRotator Rotation(0,Yaw,0);
    const FVector LocalAnchor(Bounds.GetCenter().X,Bounds.Max.Y,Bounds.Min.Z);
    auto* Piece=NewObject<UStaticMeshComponent>(this,FName(*FString::Printf(TEXT("FortressFresco%02d"),MuralIndex+1)));
    AddInstanceComponent(Piece);Piece->SetupAttachment(GetRootComponent());Piece->SetMobility(EComponentMobility::Static);
    Piece->SetStaticMesh(Mesh);Piece->SetMaterial(1,FortressMuralMaterials[MuralIndex]);
    Piece->SetRelativeTransform(FTransform(Rotation,Anchor-Rotation.RotateVector(LocalAnchor*Scale),FVector(Scale)));
    Piece->SetCollisionProfileName(TEXT("BlockAll"));Piece->SetCollisionEnabled(ECollisionEnabled::QueryAndPhysics);
    Piece->SetGenerateOverlapEvents(false);Piece->SetCanEverAffectNavigation(false);
    Piece->SetWalkableSlopeOverride(FWalkableSlopeOverride(WalkableSlope_Unwalkable,0.f));Piece->RegisterComponent();
    // Light originates at the visible brazier added by BuildDistance. Matte
    // pigments respond to actual illumination; there is no emissive mural boost.
    const FVector Inward=Rotation.RotateVector(FVector(0,1,0));
    const FVector Lamp=Anchor+Inward*600.f+FVector(0,0,110.f-FortressFloorZ);
    const FVector Aim=Anchor+Inward*100.f+FVector(0,0,Height*.43f);
    auto* Light=NewObject<USpotLightComponent>(this,FName(*FString::Printf(TEXT("FrescoBrazierLight%02d"),MuralIndex+1)));
    AddInstanceComponent(Light);Light->SetupAttachment(GetRootComponent());Light->SetMobility(EComponentMobility::Movable);
    Light->SetRelativeLocation(Lamp);Light->SetRelativeRotation((Aim-Lamp).Rotation());
    Light->SetIntensityUnits(ELightUnits::Candelas);Light->SetIntensity(450.f);
    Light->SetLightColor(FLinearColor(1.f,.70f,.40f));Light->SetAttenuationRadius(2100.f);
    Light->SetInnerConeAngle(35.f);Light->SetOuterConeAngle(55.f);Light->SetSourceRadius(30.f);Light->SetCastShadows(false);Light->RegisterComponent();
    ++FortressMuralCount;++ConnectedCourtInstanceCount;++ImportedArchitecturePieces;
}

bool AVeyrArena::BuildFortressCourt()
{
    if(!bConnectedCourtAssetsReady||!bFortressAssetsReady)return false;
    Tags.Remove(TEXT("VeyrConnectedCathedralCourt"));Tags.Add(TEXT("VeyrSecularFortressCourt"));
    // Broad military walls, four fresco bays and square defensive towers replace
    // the shrine/apse/nave composition. Every permanent mass is outside the
    // unchanged 72m clear combat diameter, including its camera margin.
    const float WallHeight=1800.f;
    for(int32 SideIndex=0;SideIndex<2;++SideIndex)
    {
        const float Side=SideIndex==0?-1.f:1.f,Yaw=Side>0?180.f:0.f;
        FortressMuralBay(FVector(-3100,Side*FortressHalfY,0),WallHeight,Yaw,SideIndex*2);
        KitPiece(TEXT("FortressCurtainWall"),FVector(0,Side*FortressHalfY,0),WallHeight,Yaw,true,true);
        FortressMuralBay(FVector(3100,Side*FortressHalfY,0),WallHeight,Yaw,SideIndex*2+1);
        for(float X:{-FortressHalfX,FortressHalfX})
        {
            const float H=X>0?3500.f:2900.f;
            KitPiece(TEXT("FortressWatchtower"),FVector(X,Side*(FortressHalfY+350.f),0),H,Side*90.f,true);
            ++FortressTowerCount;
        }
    }
    for(float Side:{-1.f,1.f})
    {
        const float Height=Side>0?3000.f:2000.f,Yaw=Side>0?90.f:-90.f;
        const FVector GateSize=KitSize(TEXT("FortressGatehouse"),Height);
        const float GateHalf=GateSize.X*.5f-70.f;
        KitPiece(TEXT("FortressGatehouse"),FVector(Side*FortressHalfX,0,FortressFloorZ),Height,Yaw,true,true);
        for(float End:{-1.f,1.f})
            KitWallRun(TEXT("FortressCurtainWall"),FVector(Side*FortressHalfX,End*GateHalf,0),
                FVector(Side*FortressHalfX,End*FortressHalfY,0),FVector(-Side,0,0),WallHeight,FortressFloorZ);
        Box(Foundations,FVector(Side*(FortressHalfX+GateSize.Y*.5f),0,FortressFloorZ*.5f-60.f),
            FVector(GateSize.Y+120.f,GateSize.X+120.f,FortressFloorZ+120.f));
        // Rendered iron bars close the real generated gateway. No invisible
        // blocking slab or doorway that appears traversable but is not.
        const float DoorWidth=GateSize.X*.36f,DoorHeight=Height*.54f;
        for(float Y=-DoorWidth*.5f;Y<=DoorWidth*.5f;Y+=65.f)
            Box(Bronze,FVector(Side*(FortressHalfX+35.f),Y,FortressFloorZ+DoorHeight*.5f),FVector(32,32,DoorHeight));
        for(int32 Rail=0;Rail<4;++Rail)
            Box(Bronze,FVector(Side*(FortressHalfX+35.f),0,FortressFloorZ+120.f+Rail*DoorHeight*.23f),FVector(38,DoorWidth+30.f,38));
    }
    // Limited collapsed masonry along the perimeter; no funerary statues or bell.
    for(float Side:{-1.f,1.f})for(int32 I=0;I<4;++I)
        KitPiece(TEXT("CollapsedVaultRubble"),FVector(-3400+I*2200.f,Side*4210.f,0),120.f+(I%3)*35.f,I*61.f,true);
    UE_LOG(LogTemp,Display,TEXT("VEYR_FORTRESS_COURT meshes=%d murals=%d towers=%d clearDiameterCm=7200"),FortressMeshCount,FortressMuralCount,FortressTowerCount);
    return FortressMuralCount==4;
}

void AVeyrArena::BuildFortressSkyline()
{
    if(!bFortressAssetsReady)return;
    // Grounded stepped curtain walls and offset watchtowers make an inhabited
    // fortified skyline. The entire overhead combat/flight corridor stays open.
    for(float Side:{-1.f,1.f})
    {
        const float Y=Side*6500.f;
        KitWallRun(TEXT("RockRetainingWall"),FVector(-7200,Y,0),FVector(7200,Y,0),FVector(0,-Side,0),2000,-200,false);
        KitWallRun(TEXT("FortressCurtainWall"),FVector(-6500,Y,0),FVector(6500,Y,0),FVector(0,-Side,0),1800,1700,false);
        for(int32 I=0;I<3;++I)
        {
            KitPiece(TEXT("FortressWatchtower"),FVector(-5800.f+I*5800.f,Y+Side*350.f,0),4100.f+(I%2)*900.f,Side*90.f,false);
            ++FortressTowerCount;
        }
    }
    KitPiece(TEXT("FortressGatehouse"),FVector(14500,700,1550),4200,90,false,true);
    for(float Side:{-1.f,1.f})
    {
        KitPiece(TEXT("FortressWatchtower"),FVector(15000,Side*5200.f,1300),5200.f+(Side>0?700.f:0.f),90,false);
        ++FortressTowerCount;
    }
    // Iron gallery detail belongs behind the northern mural wall, not above
    // the player's camera. Existing approved stone and iron materials reused.
    Box(Foundations,FVector(-1200,4900,1450),FVector(7800,600,80));
    for(float X=-5000.f;X<=2600.f;X+=240.f)
        Box(Bronze,FVector(X,4820,1760),FVector(14,14,240));
    for(float Z:{1660.f,1880.f})Box(Bronze,FVector(-1200,4820,Z),FVector(7800,18,18));
}
