#include "VeyrSizeMeter.h"
#include "VeyrDragon.h"
#include "VeyrKnight.h"
#include "VeyrArenaTour.h"
#include "VeyrSkeletalPresentation.h"
#include "Camera/CameraActor.h"
#include "Camera/CameraComponent.h"
#include "Components/CapsuleComponent.h"
#include "Engine/World.h"
#include "Engine/OverlapResult.h"
#include "CollisionQueryParams.h"
#include "Dom/JsonValue.h"

namespace
{
    // Fortress court (VeyrArenaFortress.cpp): curtain walls on x = +-5100 and y = +-4500, floor inside.
    constexpr float WallHalfX=5100.f, WallHalfY=4500.f, Cell=200.f;
    constexpr int32 CellsX=static_cast<int32>(2*WallHalfX/Cell), CellsY=static_cast<int32>(2*WallHalfY/Cell);
    const TCHAR* PartNames[]={TEXT("head"),TEXT("neck"),TEXT("chest"),TEXT("belly"),TEXT("hips"),TEXT("leg_fl"),TEXT("leg_fr"),
        TEXT("leg_hl"),TEXT("leg_hr"),TEXT("wing_l"),TEXT("wing_r"),TEXT("tail")};
    float SegmentDistance(const FVector& P,const FVector& A,const FVector& B)
    {
        const FVector AB=B-A;const float L2=AB.SizeSquared();
        const float T=L2>1.f?FMath::Clamp(static_cast<float>(FVector::DotProduct(P-A,AB))/L2,0.f,1.f):0.f;
        return static_cast<float>(FVector::Dist(P,A+AB*T));
    }
    float WallMargin(const FVector& P,float Radius)
    {
        return FMath::Min(WallHalfX-FMath::Abs(static_cast<float>(P.X)),WallHalfY-FMath::Abs(static_cast<float>(P.Y)))-Radius;
    }
}

FString FVeyrSizeMeter::PlaceName(const AVeyrDragon* Dragon) const
{
    const FString S=StaticEnum<EVeyrDragonState>()->GetNameStringByValue(static_cast<int64>(Dragon->State));
    const bool bMove=Dragon->State==EVeyrDragonState::Windup||Dragon->State==EVeyrDragonState::Active||Dragon->State==EVeyrDragonState::Recovery;
    return bMove?StaticEnum<EVeyrDragonMove>()->GetNameStringByValue(static_cast<int64>(Dragon->Move))+TEXT(".")+S:S;
}

void FVeyrSizeMeter::MeasureBody(AVeyrDragon* Dragon)
{
    UVeyrSkeletalPresentation* P=Dragon->ImportedPresentation;
    if(!P||P->GetComponentSpaceTransforms().Num()==0)return;
    const FTransform Frame(FRotator(0,Dragon->GetActorRotation().Yaw,0),Dragon->GetActorLocation());
    FBox Box(ForceInit);
    for(int32 I=0;I<P->GetComponentSpaceTransforms().Num();++I)Box+=Frame.InverseTransformPosition(P->GetBoneTransform(I).GetLocation());
    for(const TCHAR* Name:PartNames)
    {
        FVector A,B;float R;
        if(!Dragon->GetHurtPartWorld(Name,A,B,R))continue;
        for(const FVector& Q:{A,B}){const FVector L=Frame.InverseTransformPosition(Q);Box+=L+FVector(R);Box+=L-FVector(R);}
    }
    BodyLengthCm=Box.GetSize().X;BodySpanCm=Box.GetSize().Y;BodyHeightCm=static_cast<float>(Box.Max.Z-FloorZ+Dragon->GetActorLocation().Z);
}

void FVeyrSizeMeter::MeasureIntro(UWorld* World,AVeyrDragon* Dragon)
{
    ACameraActor* Cam=World->SpawnActor<ACameraActor>();
    if(!Cam)return;
    TArray<FVector> Points;
    for(const TCHAR* Name:PartNames)
    {
        FVector A,B;float R;
        if(!Dragon->GetHurtPartWorld(Name,A,B,R))continue;
        Points.Add(A);Points.Add(B);Points.Add((A+B)*.5f);
    }
    if(UVeyrSkeletalPresentation* P=Dragon->ImportedPresentation)
        for(int32 I=0;I<P->GetComponentSpaceTransforms().Num();I+=3)Points.Add(P->GetBoneTransform(I).GetLocation());
    const float Aspect=16.f/9.f;
    for(int32 Shot=0;Shot<VeyrArenaTour::ShotCount();++Shot)
    {
        VeyrArenaTour::Apply(Cam,(Shot+.5f)*VeyrArenaTour::ShotSeconds());
        const FVector Eye=Cam->GetActorLocation();const FRotationMatrix Basis(Cam->GetActorRotation());
        const float TanH=FMath::Tan(FMath::DegreesToRadians(Cam->GetCameraComponent()->FieldOfView*.5f)),TanV=TanH/Aspect;
        int32 In=0;float MinV=2.f,MaxV=-2.f,MinU=2.f,MaxU=-2.f;
        for(const FVector& Q:Points)
        {
            const FVector D=Q-Eye;const float X=FVector::DotProduct(D,Basis.GetUnitAxis(EAxis::X));
            if(X<=10.f)continue;
            const float U=FVector::DotProduct(D,Basis.GetUnitAxis(EAxis::Y))/(X*TanH),V=FVector::DotProduct(D,Basis.GetUnitAxis(EAxis::Z))/(X*TanV);
            if(FMath::Abs(U)<=1.f&&FMath::Abs(V)<=1.f){++In;MinV=FMath::Min(MinV,V);MaxV=FMath::Max(MaxV,V);MinU=FMath::Min(MinU,U);MaxU=FMath::Max(MaxU,U);}
        }
        // Does the drawn body stand between the lens and the shot's subject (the frame centre ray, 40 m)?
        bool bBlocks=false;const FVector Far=Eye+Basis.GetUnitAxis(EAxis::X)*4000.f;
        for(const TCHAR* Name:PartNames)
        {
            FVector A,B;float R;
            if(!Dragon->GetHurtPartWorld(Name,A,B,R))continue;
            for(int32 S=0;S<=8&&!bBlocks;++S)if(SegmentDistance(FMath::Lerp(A,B,S/8.f),Eye,Far)<R)bBlocks=true;
        }
        auto O=MakeShared<FJsonObject>();
        O->SetStringField(TEXT("shot"),VeyrArenaTour::ShotName(Shot));
        O->SetNumberField(TEXT("dragonPointsInFramePct"),Points.Num()?100.f*In/Points.Num():0.f);
        O->SetNumberField(TEXT("dragonScreenHeightPct"),In?50.f*(MaxV-MinV):0.f);
        O->SetNumberField(TEXT("dragonScreenWidthPct"),In?50.f*(MaxU-MinU):0.f);
        O->SetBoolField(TEXT("dragonCutByTopEdge"),In&&MaxV>.97f);
        O->SetBoolField(TEXT("bodyOnCentreRay"),bBlocks);
        IntroShots.Add(MakeShared<FJsonValueObject>(O));
    }
    Cam->Destroy();
}

void FVeyrSizeMeter::Tick(UWorld* World,AVeyrDragon* Dragon,AVeyrKnight* Knight,float Dt)
{
    if(!World||!IsValid(Dragon)||!IsValid(Knight)||!Dragon->ImportedPresentation||!Dragon->ImportedPresentation->bPoseEvaluated)return;
    Clock+=Dt;++Frames;
    if(!bStarted)
    {
        bStarted=true;FloorZ=static_cast<float>(Knight->GetFootLocation().Z);
        BrainSeed=Dragon->BrainSeed;BodyScale=Dragon->BodyScale;LastDragonHealth=Dragon->Health;LastHitsTaken=Knight->HitsTaken;
        Coverage.Init(false,CellsX*CellsY);
    }
    bTwoHanded|=Knight->IsTwoHanded();
    if(!bIntroMeasured&&Clock>.3f){bIntroMeasured=true;MeasureBody(Dragon);MeasureIntro(World,Dragon);
        FVector A,B;float R;if(Dragon->GetHurtPartWorld(TEXT("head"),A,B,R))HeadStandingZ=static_cast<float>(FMath::Max(A.Z,B.Z)-FloorZ);
        if(Dragon->GetHurtPartWorld(TEXT("leg_fl"),A,B,R))LegTopStandingZ=static_cast<float>(FMath::Max(A.Z,B.Z)-FloorZ);}
    const FString Place=PlaceName(Dragon);
    // Clearance against the fortress wall lines: every hurt capsule and every bone of the drawn body.
    float Margin=1.e9f;FString Where;
    for(const TCHAR* Name:PartNames)
    {
        FVector A,B;float R;
        if(!Dragon->GetHurtPartWorld(Name,A,B,R))continue;
        for(const FVector& Q:{A,B,(A+B)*.5f}){const float M=WallMargin(Q,R);if(M<Margin){Margin=M;Where=Name;}}
    }
    if(UVeyrSkeletalPresentation* P=Dragon->ImportedPresentation)
        for(int32 I=0;I<P->GetComponentSpaceTransforms().Num();++I)
        {const float M=WallMargin(P->GetBoneTransform(I).GetLocation(),0.f);if(M<Margin){Margin=M;Where=P->GetBoneName(I).ToString();}}
    if(Margin<MinWallMarginCm){MinWallMarginCm=Margin;MinWallMarginWhere=Where+TEXT(" in ")+Place;}
    float& PlaceMin=MinMarginByPlace.FindOrAdd(Place,1.e9f);PlaceMin=FMath::Min(PlaceMin,Margin);
    // Physics overlap of the hurt capsules with any tall static geometry (walls, towers, props), every third frame.
    if(Frames%3==0)
    {
        ++OverlapChecks;bool bAny=false;
        FCollisionQueryParams Params(SCENE_QUERY_STAT(VeyrSizeMeter),false,Dragon);Params.AddIgnoredActor(Knight);
        for(const TCHAR* Name:PartNames)
        {
            FVector A,B;float R;
            if(!Dragon->GetHurtPartWorld(Name,A,B,R))continue;
            const FVector Axis=B-A;const float Half=static_cast<float>(Axis.Size())*.5f;
            const FQuat Q=Axis.IsNearlyZero()?FQuat::Identity:FRotationMatrix::MakeFromZ(Axis.GetSafeNormal()).ToQuat();
            TArray<FOverlapResult> Hits;
            World->OverlapMultiByObjectType(Hits,(A+B)*.5f,Q,FCollisionObjectQueryParams(ECC_WorldStatic),FCollisionShape::MakeCapsule(R,Half+R),Params);
            for(const FOverlapResult& H:Hits)
            {
                const UPrimitiveComponent* C=H.GetComponent();
                if(!C||C->Bounds.BoxExtent.Z<150.f)continue; // the floor and flat tiles are not walls
                if(C->Bounds.Origin.Z+C->Bounds.BoxExtent.Z<FloorZ+150.f)continue;
                bAny=true;OverlapComponents.FindOrAdd(FString(Name)+TEXT(":")+C->GetName())++;
            }
        }
        if(bAny){++OverlapFrames;OverlapByPlace.FindOrAdd(Place)++;}
    }
    // Attack reach and arena coverage per attack instance.
    const bool bActive=Dragon->State==EVeyrDragonState::Active&&Dragon->Move!=EVeyrDragonMove::FlyAway;
    const bool bAerialFire=Dragon->State==EVeyrDragonState::Active&&Dragon->Move==EVeyrDragonMove::FlyAway;
    const int32 MoveIndex=static_cast<int32>(Dragon->Move);
    if((bActive||bAerialFire)&&!bWasActive){ActiveMove=MoveIndex;Coverage.Init(false,CellsX*CellsY);Moves[MoveIndex].Instances++;}
    if(bWasActive&&!(bActive||bAerialFire)&&ActiveMove>=0)
    {
        int32 N=0;for(int32 I=0;I<Coverage.Num();++I)N+=Coverage[I]?1:0;
        const float Pct=100.f*N/FMath::Max(1,Coverage.Num());
        Moves[ActiveMove].MaxCoveragePct=FMath::Max(Moves[ActiveMove].MaxCoveragePct,Pct);Moves[ActiveMove].SumCoveragePct+=Pct;
    }
    if(bActive||bAerialFire)
    {
        const FVector Root=Dragon->GetActorLocation();FMoveStats& S=Moves[MoveIndex];
        const TArray<FVeyrDragonContact> Contacts=Dragon->GetImportedContacts();
        const FVeyrDragonFlameBeam Beam=Dragon->GetActiveFlameBeam();
        for(const FVeyrDragonContact& C:Contacts)for(const FVector& Q:{C.Start,C.End})
            S.MaxReachCm=FMath::Max(S.MaxReachCm,static_cast<float>(FVector::Dist2D(Q,Root))+C.Radius);
        if(Beam.bDamaging)S.MaxReachCm=FMath::Max(S.MaxReachCm,static_cast<float>(FVector::Dist2D(Beam.Origin+Beam.Direction*Beam.Length,Root)));
        const float CosHalf=FMath::Cos(FMath::DegreesToRadians(Beam.HalfAngleDegrees));
        for(int32 Y=0;Y<CellsY;++Y)for(int32 X=0;X<CellsX;++X)
        {
            const int32 Index=Y*CellsX+X;if(Coverage[Index])continue;
            const FVector P(-WallHalfX+(X+.5f)*Cell,-WallHalfY+(Y+.5f)*Cell,FloorZ+100.f);
            bool bIn=false;
            for(const FVeyrDragonContact& C:Contacts)if(SegmentDistance(P,C.Start,C.End)<=C.Radius+45.f){bIn=true;break;}
            if(!bIn&&Beam.bDamaging)
            {
                const FVector D=P-Beam.Origin;const float Along=FVector::DotProduct(D,Beam.Direction);
                bIn=Along>0.f&&Along<=Beam.Length&&Along>=D.Size()*CosHalf;
            }
            if(bIn)Coverage[Index]=true;
        }
    }
    if(Knight->HitsTaken>LastHitsTaken&&ActiveMove>=0&&(bActive||bAerialFire||Dragon->State==EVeyrDragonState::Recovery))Moves[ActiveMove].KnightHits+=Knight->HitsTaken-LastHitsTaken;
    LastHitsTaken=Knight->HitsTaken;bWasActive=bActive||bAerialFire;
    // Knight's sword hits on the dragon, by part, standing or down.
    const bool bDown=Dragon->State==EVeyrDragonState::Collapse||Dragon->State==EVeyrDragonState::Exposed||Dragon->State==EVeyrDragonState::Rise;
    if(Dragon->Health<LastDragonHealth-.01f)(bDown?HitsDown:HitsStanding).FindOrAdd(Dragon->LastSwordHurtPart.ToString())++;
    LastDragonHealth=Dragon->Health;
    if(Dragon->State==EVeyrDragonState::Exposed)
    {
        FVector A,B;float R;
        if(Dragon->GetHurtPartWorld(TEXT("head"),A,B,R))
        {const float Z=static_cast<float>(FMath::Min(A.Z,B.Z)-R-FloorZ);HeadDownMinZ=FMath::Min(HeadDownMinZ,Z);HeadDownMaxZ=FMath::Max(HeadDownMaxZ,Z);}
    }
    const bool bAir=Dragon->IsAirborne();
    if(bAir&&!bWasAirborne)++FlightsStarted;
    bWasAirborne=bAir;
    if(bAir)MaxAirborneHeightCm=FMath::Max(MaxAirborneHeightCm,static_cast<float>(Dragon->GetActorLocation().Z-FloorZ));
}

TSharedPtr<FJsonObject> FVeyrSizeMeter::ToJson() const
{
    auto O=MakeShared<FJsonObject>();
    O->SetStringField(TEXT("scope"),TEXT("D3 size checks: wall margin = distance from the drawn body (hurt capsules and bones) to the fortress wall lines x=+-5100, y=+-4500, negative = past the line; overlap = hurt capsules overlapping tall static geometry; coverage = share of 200 cm floor cells (knight height 1 m, 45 cm knight radius) inside one attack instance's damaging contacts or flame"));
    O->SetNumberField(TEXT("bodyScale"),BodyScale);O->SetNumberField(TEXT("brainSeed"),BrainSeed);O->SetBoolField(TEXT("twoHanded"),bTwoHanded);
    O->SetNumberField(TEXT("bodyLengthCm"),BodyLengthCm);O->SetNumberField(TEXT("bodySpanCm"),BodySpanCm);O->SetNumberField(TEXT("bodyHeightCm"),BodyHeightCm);
    O->SetNumberField(TEXT("headStandingTopCm"),HeadStandingZ);O->SetNumberField(TEXT("frontLegTopStandingCm"),LegTopStandingZ);
    O->SetNumberField(TEXT("frames"),Frames);
    O->SetNumberField(TEXT("minWallMarginCm"),MinWallMarginCm);O->SetStringField(TEXT("minWallMarginWhere"),MinWallMarginWhere);
    auto Places=MakeShared<FJsonObject>();for(const auto& P:MinMarginByPlace)Places->SetNumberField(P.Key,P.Value);
    O->SetObjectField(TEXT("minWallMarginByPlaceCm"),Places);
    O->SetNumberField(TEXT("overlapChecks"),OverlapChecks);O->SetNumberField(TEXT("overlapFrames"),OverlapFrames);
    auto OP=MakeShared<FJsonObject>();for(const auto& P:OverlapByPlace)OP->SetNumberField(P.Key,P.Value);O->SetObjectField(TEXT("overlapByPlace"),OP);
    auto OC=MakeShared<FJsonObject>();for(const auto& P:OverlapComponents)OC->SetNumberField(P.Key,P.Value);O->SetObjectField(TEXT("overlapComponents"),OC);
    auto M=MakeShared<FJsonObject>();
    for(int32 I=0;I<6;++I)
    {
        auto S=MakeShared<FJsonObject>();const FMoveStats& X=Moves[I];
        S->SetNumberField(TEXT("activeInstances"),X.Instances);S->SetNumberField(TEXT("knightHits"),X.KnightHits);
        S->SetNumberField(TEXT("maxReachCm"),X.MaxReachCm);S->SetNumberField(TEXT("maxArenaCoveragePct"),X.MaxCoveragePct);
        S->SetNumberField(TEXT("meanArenaCoveragePct"),X.Instances?X.SumCoveragePct/X.Instances:0.f);
        M->SetObjectField(StaticEnum<EVeyrDragonMove>()->GetNameStringByValue(I),S);
    }
    O->SetObjectField(TEXT("moves"),M);
    auto HS=MakeShared<FJsonObject>();for(const auto& P:HitsStanding)HS->SetNumberField(P.Key,P.Value);O->SetObjectField(TEXT("swordHitsStanding"),HS);
    auto HD=MakeShared<FJsonObject>();for(const auto& P:HitsDown)HD->SetNumberField(P.Key,P.Value);O->SetObjectField(TEXT("swordHitsDown"),HD);
    O->SetNumberField(TEXT("headDownLowestCm"),HeadDownMinZ<1.e8f?HeadDownMinZ:-1.f);O->SetNumberField(TEXT("headDownHighestCm"),HeadDownMaxZ>-1.e8f?HeadDownMaxZ:-1.f);
    O->SetNumberField(TEXT("flightsStarted"),FlightsStarted);O->SetNumberField(TEXT("maxAirborneHeightCm"),MaxAirborneHeightCm);
    O->SetArrayField(TEXT("introShots"),IntroShots);
    return O;
}
