#include "VeyrCameraBoom.h"
#include "VeyrDragon.h"
#include "VeyrSkeletalPresentation.h"
#include "Components/CapsuleComponent.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "Misc/CommandLine.h"
#include "Camera/CameraComponent.h"
#include "Dom/JsonObject.h"
#include "Dom/JsonValue.h"
#include "Components/CapsuleComponent.h"
#include "Engine/GameViewportClient.h"
#include "GameFramework/Character.h"

UVeyrCameraBoom::UVeyrCameraBoom()
{
    PrimaryComponentTick.TickGroup=TG_PostPhysics;
}

void UVeyrCameraBoom::BeginPlay()
{
    Super::BeginPlay();
    bLegacyBoom=FParse::Param(FCommandLine::Get(),TEXT("VeyrLegacyCameraBoom"));
    bLegacyFraming=FParse::Param(FCommandLine::Get(),TEXT("VeyrLegacyCameraFraming"));
    bLegacySafety=FParse::Param(FCommandLine::Get(),TEXT("VeyrLegacyCameraSafety"));
    // Fourth pass: the knight stays inside the central 80 % of the frame; the lens may open further.
    if(!bLegacySafety){KnightScreenMargin=FMath::Max(KnightScreenMargin,.1f);MaxFovBoostDeg=FMath::Max(MaxFovBoostDeg,14.f);}
    FindDragon();
}

float UVeyrCameraBoom::DragonScale() const
{
    const AVeyrDragon* D=Dragon.Get();
    return D?FMath::Max(.25f,static_cast<float>(D->GetActorScale3D().Z)*.5f):1.f;
}

void UVeyrCameraBoom::FindDragon()
{
    if(Dragon.IsValid()||!GetWorld())return;
    TActorIterator<AVeyrDragon> It(GetWorld());
    if(It)Dragon=*It;
    if(AVeyrDragon* D=Dragon.Get();D&&!bPrerequisiteAdded)
    {
        // The dragon poses its body and solid capsules in its own tick; read them after it.
        PrimaryComponentTick.AddPrerequisite(D,D->PrimaryActorTick);
        bPrerequisiteAdded=true;
    }
}

void UVeyrCameraBoom::RefreshShapes()
{
    Shapes.Reset();
    AVeyrDragon* D=Dragon.Get();
    if(!D)return;
    const float S=DragonScale();
    TInlineComponentArray<UCapsuleComponent*> Capsules(D);
    for(UCapsuleComponent* Capsule:Capsules)
    {
        if(!Capsule||!Capsule->GetName().StartsWith(TEXT("VeyrSolid_")))continue;
        const float Radius=Capsule->GetScaledCapsuleRadius();
        const float Half=FMath::Max(0.f,Capsule->GetScaledCapsuleHalfHeight()-Radius);
        const FVector Center=Capsule->GetComponentLocation(),Axis=Capsule->GetUpVector();
        FShape Shape;Shape.A=Center-Axis*Half;Shape.B=Center+Axis*Half;Shape.Radius=Radius+BodyClearanceCm*S;Shape.Clearance=BodyClearanceCm*S;Shape.Name=Capsule->GetFName();
        Shapes.Add(Shape);
    }
    UVeyrSkeletalPresentation* Presentation=D->ImportedPresentation;
    if(Presentation&&D->bUsingCustomuseVisual&&Presentation->bPoseEvaluated)
    {
        if(!Hull.IsReadyFor(Presentation))Hull.Initialize(Presentation);
        if(Hull.Skin(Presentation,HullSpheres))
        {
            static const FName WingName(TEXT("VeyrHullWing")),BodyName(TEXT("VeyrHullBody"));
            const float Clear=WingClearanceCm*S;
            for(int32 I=0;I<HullSpheres.Num();++I)
            {
                const FVector4& H=HullSpheres[I];
                FShape X;X.A=X.B=FVector(H.X,H.Y,H.Z);X.Radius=static_cast<float>(H.W)+Clear;X.Clearance=Clear;
                X.Name=I<Hull.BoomWingCount()?WingName:BodyName; // table order: wing samples, then body
                Shapes.Add(X);
            }
        }
    }
    ShapeCount=Shapes.Num();
}

float UVeyrCameraBoom::ShapeDistance(const FShape& Shape,const FVector& Point) const
{
    const FVector Closest=Shape.bTriangle?FMath::ClosestPointOnTriangleToPoint(Point,Shape.A,Shape.B,Shape.C):
        FMath::ClosestPointOnSegment(Point,Shape.A,Shape.B);
    return static_cast<float>(FVector::Dist(Point,Closest))-Shape.Radius;
}

bool UVeyrCameraBoom::IsPointInsideDragon(const FVector& Point,float Radius,FName* OutShape) const
{
    for(const FShape& Shape:Shapes)
        if(ShapeDistance(Shape,Point)<Radius){if(OutShape)*OutShape=Shape.Name;return true;}
    return false;
}

bool UVeyrCameraBoom::IsPointInsideBareDragon(const FVector& Point,float Margin,FName* OutShape) const
{
    for(const FShape& Shape:Shapes)
        if(ShapeDistance(Shape,Point)+Shape.Clearance<Margin){if(OutShape)*OutShape=Shape.Name;return true;}
    return false;
}

bool UVeyrCameraBoom::IsPointInsideSolidCapsule(const FVector& Point,float Margin,FName* OutShape) const
{
    for(const FShape& Shape:Shapes)
        if(Shape.Name.ToString().StartsWith(TEXT("VeyrSolid_"))&&ShapeDistance(Shape,Point)+Shape.Clearance<Margin){if(OutShape)*OutShape=Shape.Name;return true;}
    return false;
}

bool UVeyrCameraBoom::EnsureSurface() const
{
    AVeyrDragon* D=Dragon.Get();
    UVeyrSkeletalPresentation* Presentation=D?D->ImportedPresentation.Get():nullptr;
    if(!Presentation||!D->bUsingCustomuseVisual)return false;
    if(SurfaceFrame!=GFrameCounter)
    {
        SurfaceFrame=GFrameCounter;SurfaceGrid.Reset();SurfaceBounds=FBox(ForceInit);WingGrid.Reset();WingBounds=FBox(ForceInit);
        if(!Hull.IsReadyFor(Presentation))Hull.Initialize(Presentation);
        Hull.SkinSurface(Presentation,SurfacePositions,SurfaceNormals);
        Hull.SkinWingSurface(Presentation,WingPositions,WingNormals);
        // Buckets of 50 cm x scale: a query reads a few dozen samples instead of all of them.
        SurfaceCell=FMath::Max(25.f,50.f*DragonScale());
        auto Bucket=[this](const TArray<FVector>& Points,TMap<FIntVector,TArray<int32>>& Grid,FBox& Bounds)
        {
            for(int32 I=0;I<Points.Num();++I)
            {
                const FVector& P=Points[I];Bounds+=P;
                Grid.FindOrAdd(FIntVector(FMath::FloorToInt(P.X/SurfaceCell),FMath::FloorToInt(P.Y/SurfaceCell),FMath::FloorToInt(P.Z/SurfaceCell))).Add(I);
            }
        };
        Bucket(SurfacePositions,SurfaceGrid,SurfaceBounds);Bucket(WingPositions,WingGrid,WingBounds);
    }
    return SurfacePositions.Num()>0;
}

void UVeyrCameraBoom::NearestSkin(const FVector& Point,int32 K,TArray<TPair<double,int32>,TInlineAllocator<13>>& Out,bool bWing) const
{
    Out.Reset();
    if(!EnsureSurface())return;
    const TMap<FIntVector,TArray<int32>>& Grid=bWing?WingGrid:SurfaceGrid;
    const TArray<FVector>& Positions=bWing?WingPositions:SurfacePositions;
    const FIntVector C(FMath::FloorToInt(Point.X/SurfaceCell),FMath::FloorToInt(Point.Y/SurfaceCell),FMath::FloorToInt(Point.Z/SurfaceCell));
    auto Visit=[&](const FIntVector& Cell)
    {
        const TArray<int32>* Bucket=Grid.Find(Cell);if(!Bucket)return;
        for(const int32 I:*Bucket)
        {
            const double Distance=FVector::DistSquared(Positions[I],Point);
            if(Out.Num()==K&&Distance>=Out.Last().Key)continue;
            int32 At=Out.Num();while(At>0&&Out[At-1].Key>Distance)--At;
            Out.Insert(TPair<double,int32>(Distance,I),At);
            if(Out.Num()>K)Out.Pop(EAllowShrinking::No);
        }
    };
    // Rings of cells outwards until K samples are known and the next ring cannot hold a nearer one.
    const int32 MaxRing=FMath::CeilToInt(400.f*DragonScale()/SurfaceCell);
    for(int32 Ring=0;Ring<=MaxRing;++Ring)
    {
        if(Out.Num()==K&&FMath::Sqrt(Out.Last().Key)<(Ring-1)*SurfaceCell)break;
        for(int32 X=-Ring;X<=Ring;++X)for(int32 Y=-Ring;Y<=Ring;++Y)for(int32 Z=-Ring;Z<=Ring;++Z)
            if(FMath::Max3(FMath::Abs(X),FMath::Abs(Y),FMath::Abs(Z))==Ring)Visit(C+FIntVector(X,Y,Z));
    }
}

float UVeyrCameraBoom::NearestSkinCm(const FVector& Point) const
{
    if(!EnsureSurface())return TNumericLimits<float>::Max();
    float Best=TNumericLimits<float>::Max();
    TArray<TPair<double,int32>,TInlineAllocator<13>> Nearest;
    if(SurfaceBounds.ExpandBy(400.f*DragonScale()).IsInside(Point)){NearestSkin(Point,1,Nearest);if(!Nearest.IsEmpty())Best=static_cast<float>(FMath::Sqrt(Nearest[0].Key));}
    if(WingBounds.ExpandBy(400.f*DragonScale()).IsInside(Point)){NearestSkin(Point,1,Nearest,true);if(!Nearest.IsEmpty())Best=FMath::Min(Best,static_cast<float>(FMath::Sqrt(Nearest[0].Key)));}
    return Best;
}

bool UVeyrCameraBoom::CrossesWing(const FVector& A,const FVector& B) const
{
    if(!EnsureSurface()||WingPositions.IsEmpty())return false;
    const FBox Near=WingBounds.ExpandBy(100.f*DragonScale());
    if(!FMath::LineBoxIntersection(Near,A,B,B-A)&&!Near.IsInside(A))return false;
    // Signed side of the nearest membrane sample at every 20 cm step; a flip with both steps within a
    // sample spacing of the sheet is a crossing (an open sheet has no inside, so the side is all there is).
    const float Reach=35.f*DragonScale();
    const float Length=static_cast<float>(FVector::Dist(A,B));
    const int32 Steps=FMath::Clamp(FMath::CeilToInt(Length/20.f),1,160);
    TArray<TPair<double,int32>,TInlineAllocator<13>> Nearest;
    float Previous=0.f;bool bPrevious=false;
    for(int32 I=0;I<=Steps;++I)
    {
        const FVector P=FMath::Lerp(A,B,static_cast<float>(I)/Steps);
        if(!Near.IsInside(P)){bPrevious=false;continue;}
        NearestSkin(P,1,Nearest,true);
        if(Nearest.IsEmpty()||Nearest[0].Key>FMath::Square(Reach)){bPrevious=false;continue;}
        const float Side=static_cast<float>(FVector::DotProduct(P-WingPositions[Nearest[0].Value],WingNormals[Nearest[0].Value]));
        if(bPrevious&&Side*Previous<0.f)return true;
        Previous=Side;bPrevious=true;
    }
    return false;
}

bool UVeyrCameraBoom::IsPointBehindSkin(const FVector& Point,float Margin,float* OutDepthCm) const
{
    if(OutDepthCm)*OutDepthCm=0.f;
    if(!EnsureSurface())return false;
    // Outside the skinned samples' box (plus the thickest part) nothing can be behind the skin.
    if(!SurfaceBounds.ExpandBy(200.f*DragonScale()*2.f).IsInside(Point))return false;
    // Consensus of the 12 nearest body samples, so a single sample with a bent normal (spines, horns,
    // the tail tip) cannot decide it, and only within 200 cm x scale of the skin: the body is nowhere thicker.
    constexpr int32 K=12;
    TArray<TPair<double,int32>,TInlineAllocator<13>> Nearest;NearestSkin(Point,K,Nearest);
    if(Nearest.IsEmpty())return false;
    if(FMath::Sqrt(Nearest[0].Key)>200.f*DragonScale()*2.f)return false;
    int32 Away=0;float Depth=0.f;
    for(const auto& N:Nearest)
    {
        const float Signed=static_cast<float>(FVector::DotProduct(Point-SurfacePositions[N.Value],SurfaceNormals[N.Value]));
        if(Signed<-Margin){++Away;Depth=FMath::Max(Depth,-Signed);}
    }
    if(OutDepthCm)*OutDepthCm=Depth;
    return Away*4>=Nearest.Num()*3;
}

bool UVeyrCameraBoom::IsPointInsideBody(const FVector& Point,float Margin) const
{
    return IsPointInsideBareDragon(Point,Margin)||IsPointBehindSkin(Point,0.f);
}

bool UVeyrCameraBoom::SightClear(const FVector& A,const FVector& B,bool bAlwaysMarch) const
{
    if(!SegmentClearOfBareDragon(A,B,0.f))return false;
    if(bLegacySafety&&!bAlwaysMarch)return true;
    // The surface spheres cover the skin's vertices, not the inside of a thick neck or torso nor the middle
    // of a large flat facet: march the line and ask the back-face test at every step.
    const float Length=static_cast<float>(FVector::Dist(A,B));
    const int32 Steps=FMath::Clamp(FMath::CeilToInt(Length/40.f),1,64);
    for(int32 I=1;I<Steps;++I)if(IsPointBehindSkin(FMath::Lerp(A,B,static_cast<float>(I)/Steps),5.f))return false;
    return !CrossesWing(A,B);
}

float UVeyrCameraBoom::FirstContact(const FVector& Origin,const FVector& End,float Radius) const
{
    const FVector Mid=(Origin+End)*.5;const float Half=static_cast<float>(FVector::Dist(Origin,End))*.5f;
    // Shapes that already contain the origin cannot be avoided by pulling in; the lift handles those.
    constexpr int32 Steps=32;
    float Best=1.f;
    for(const FShape& Shape:Shapes)
    {
        // Quick reject: the shape cannot reach the segment's bounding sphere.
        if(ShapeDistance(Shape,Mid)>Half+Radius)continue;
        // Origin inside the inflated shape (knight right against the body): fall back to the bare
        // shape plus the probe, and skip only if the origin is inside even that.
        float R=Radius;
        if(ShapeDistance(Shape,Origin)<R)R=Radius-Shape.Clearance;
        if(ShapeDistance(Shape,Origin)<R)continue;
        float Previous=0.f;
        for(int32 I=1;I<=Steps;++I)
        {
            const float T=static_cast<float>(I)/Steps;
            if(T>=Best)break;
            if(ShapeDistance(Shape,FMath::Lerp(Origin,End,T))<R)
            {
                float Lo=Previous,Hi=T; // refine: Lo outside, Hi inside
                for(int32 K=0;K<8;++K){const float M=(Lo+Hi)*.5f;(ShapeDistance(Shape,FMath::Lerp(Origin,End,M))<R?Hi:Lo)=M;}
                Best=FMath::Min(Best,Lo);
                break;
            }
            Previous=T;
        }
    }
    return Best;
}

FVector UVeyrCameraBoom::BlendLocations(const FVector& DesiredArmLocation,const FVector& TraceHitLocation,bool bHitSomething,float DeltaTime)
{
    const FVector Base=Super::BlendLocations(DesiredArmLocation,TraceHitLocation,bHitSomething,DeltaTime);
    bFramedViewValid=false;
    if(bLegacyBoom)return Base;
    FindDragon();
    RefreshShapes();
    if(Shapes.IsEmpty()){BodyFraction=1.f;LiftCm=0.f;bLastSolved=false;return Base;}
    ++BodyFrames;
    if(!bLegacySafety&&!bLegacyFraming)return SafeArm(PreviousArmOrigin,Base,DeltaTime);
    const float S=DragonScale();
    const float Probe=FMath::Max(ProbeSize,10.f);
    const FVector Origin=PreviousArmOrigin;
    const float Length=static_cast<float>(FVector::Dist(Origin,Base));
    float Target=FirstContact(Origin,Base,Probe);
    if(Length>1.f)Target=FMath::Max(Target,FMath::Min(1.f,MinArmCm/Length));
    // Instant pull-in, eased release (never eases outward past the contact).
    if(Target<BodyFraction){if(BodyFraction>=.999f&&Target<.999f)++PullInEvents;BodyFraction=Target;}
    else BodyFraction=FMath::Min(Target,FMath::FInterpTo(BodyFraction,Target,DeltaTime,ReleaseRate));
    const FVector Pulled=FMath::Lerp(Origin,Base,BodyFraction);
    // Rise with the pull, stopping under any body part above (the belly), and keep rising while the
    // pulled point still sits inside a tall part (a leg or the torso side right behind the knight).
    float WantLift=LiftMaxCm*S*(1.f-BodyFraction);
    if(WantLift>1.f)WantLift*=FirstContact(Pulled,Pulled+FVector::UpVector*WantLift,Probe);
    // Rising out of a tall part is allowed only while the way up stays outside the bare body.
    for(float Extra=0.f;IsPointInsideDragon(Pulled+FVector::UpVector*WantLift,Probe)&&Extra<LiftMaxCm*S*2.f;Extra+=25.f*S)
    {
        if(IsPointInsideBareDragon(Pulled+FVector::UpVector*(WantLift+25.f*S),Probe))break;
        WantLift+=25.f*S;
    }
    LiftCm=WantLift>LiftCm?WantLift:FMath::FInterpTo(LiftCm,WantLift,DeltaTime,LiftReleaseRate);
    FVector Result=Pulled+FVector::UpVector*LiftCm;
    if(LiftCm>1.f&&GetWorld())
    {
        // The lift must not push the camera into the arena (ceilings, arches).
        FHitResult Hit;FCollisionQueryParams Params(SCENE_QUERY_STAT(VeyrBoomLift),false,GetOwner());
        if(GetWorld()->SweepSingleByChannel(Hit,Pulled,Result,FQuat::Identity,ProbeChannel,FCollisionShape::MakeSphere(ProbeSize),Params))
            Result=Hit.Location;
    }
    // Last guard: never leave the camera inside the bare body. Try, longest arm first: the clear part of the
    // arm (with the lift, without it, and held level at the pivot's height, which is the room under the
    // belly), then points past the contact (the far side of a tail or leg sweeping through), then the pivot
    // lowered, then the pivot itself.
    if(IsPointInsideBareDragon(Result,Probe))
    {
        ++GuardEvents;
        const FVector Level(Base.X,Base.Y,Origin.Z);
        const float LiftPerFraction=LiftCm/FMath::Max(BodyFraction,.01f);
        auto Outside=[&](const FVector& P){return !IsPointInsideBareDragon(P,Probe);};
        bool bFound=false;
        for(int32 I=16;I>=1&&!bFound;--I)
        {
            const float F=BodyFraction*I/16.f;
            const FVector Arm=FMath::Lerp(Origin,Base,F);
            const FVector Options[3]={Arm+FVector::UpVector*LiftPerFraction*F,Arm,FMath::Lerp(Origin,Level,F)};
            for(const FVector& P:Options)if(Outside(P)){Result=P;bFound=true;break;}
        }
        for(int32 I=1;I<=16&&!bFound;++I)
        {
            const float F=BodyFraction+(1.f-BodyFraction)*I/16.f;
            const FVector Options[2]={FMath::Lerp(Origin,Base,F),FMath::Lerp(Origin,Level,F)};
            for(const FVector& P:Options)if(Outside(P)){Result=P;bFound=true;break;}
        }
        for(int32 K=1;K<=6&&!bFound;++K)
        {const FVector P=Origin-FVector::UpVector*25.f*S*K;if(Outside(P)){Result=P;bFound=true;}}
        if(!bFound){Result=Origin;++PivotInsideFrames;}
        BodyFraction=FMath::Min(BodyFraction,Length>1.f?static_cast<float>(FVector::Dist2D(Origin,Result)/FMath::Max(1.0,FVector::Dist2D(Origin,Base))):BodyFraction);
    }
    if(!bLegacyFraming)Result=FrameKnight(Origin,Base,Result,DeltaTime);
    // Evidence: inside the bare body (clearance removed), with a 10 cm near-plane margin.
    if(IsPointInsideBareDragon(Result,10.f))++ResultInsideFrames;
    return Result;
}

float UVeyrCameraBoom::ViewAspect() const
{
    FVector2D Size(16.f,9.f);
    if(GetWorld()&&GetWorld()->GetGameViewport())GetWorld()->GetGameViewport()->GetViewportSize(Size);
    return Size.Y>1.f?static_cast<float>(Size.X/Size.Y):16.f/9.f;
}

bool UVeyrCameraBoom::ProjectToView(const FVector& Point,const FVector& Camera,const FQuat& View,float HorizontalFovDeg,float Aspect,float& OutU,float& OutV)
{
    const FVector L=View.UnrotateVector(Point-Camera);
    OutU=OutV=0.f;
    if(L.X<=1.0)return false;
    const double TanH=FMath::Tan(FMath::DegreesToRadians(HorizontalFovDeg*.5)),TanV=TanH/FMath::Max(.5f,Aspect);
    OutU=static_cast<float>(L.Y/(L.X*TanH));OutV=static_cast<float>(L.Z/(L.X*TanV));
    return true;
}

bool UVeyrCameraBoom::KnightCapsule(FVector& OutBottom,FVector& OutTop,float& OutRadius) const
{
    const ACharacter* Owner=Cast<ACharacter>(GetOwner());
    const UCapsuleComponent* Capsule=Owner?Owner->GetCapsuleComponent():nullptr;
    if(!Capsule)return false;
    OutRadius=Capsule->GetScaledCapsuleRadius();
    const float Half=FMath::Max(0.f,Capsule->GetScaledCapsuleHalfHeight()-OutRadius);
    const FVector C=Capsule->GetComponentLocation(),Up=Capsule->GetUpVector();
    OutBottom=C-Up*Half;OutTop=C+Up*Half;
    return true;
}

bool UVeyrCameraBoom::SegmentClearOfBareDragon(const FVector& A,const FVector& B,float Radius) const
{
    for(const FShape& Shape:Shapes)
    {
        const float Bare=Shape.Radius-Shape.Clearance+Radius;
        double D;
        if(Shape.A.Equals(Shape.B,.01))D=FMath::PointDistToSegment(Shape.A,A,B);
        else{FVector P1,P2;FMath::SegmentDistToSegmentSafe(A,B,Shape.A,Shape.B,P1,P2);D=FVector::Dist(P1,P2);}
        if(D<Bare)return false;
    }
    return true;
}

bool UVeyrCameraBoom::IsKnightInSight(const FVector& Point) const
{
    FVector KB,KT;float KR=0.f;
    if(!KnightCapsule(KB,KT,KR))return true;
    for(const FVector& T:{FMath::Lerp(KB,KT,.6f),KT})
        if(!SegmentClearOfBareDragon(Point,T+(Point-T).GetSafeNormal()*(KR+25.f),0.f))return false;
    return true;
}

bool UVeyrCameraBoom::IsDragonOnScreen(const FVector& Camera,const FQuat& View,float HorizontalFovDeg,float Aspect) const
{
    for(const FShape& Shape:Shapes)
    {
        float U,V;
        if(ProjectToView((Shape.A+Shape.B)*.5,Camera,View,HorizontalFovDeg,Aspect,U,V)&&FMath::Abs(U)<=1.f&&FMath::Abs(V)<=1.f)return true;
    }
    return false;
}

bool UVeyrCameraBoom::KnightWholeInView(const FVector& Camera,const FQuat& View,float HorizontalFovDeg) const
{
    FVector KB,KT;float KR=0.f;
    if(!KnightCapsule(KB,KT,KR))return true;
    const float Aspect=ViewAspect();const FVector Right=View.GetRightVector(),Mid=(KB+KT)*.5;
    for(const FVector& P:{KB-FVector::UpVector*KR,KT+FVector::UpVector*KR,Mid+Right*KR,Mid-Right*KR})
    {
        float U,V;
        if(!ProjectToView(P,Camera,View,HorizontalFovDeg,Aspect,U,V)||FMath::Abs(U)>1.f||FMath::Abs(V)>1.f)return false;
    }
    return true;
}

bool UVeyrCameraBoom::PlacementOk(const FVector& P,const FVector& KBottom,const FVector& KTop,float KRadius,float MinDistance) const
{
    if(FMath::PointDistToSegment(P,KBottom,KTop)<MinDistance)return false;
    if(P.Z<KBottom.Z-KRadius+40.f)return false; // above the floor the knight stands on
    if(IsPointInsideBareDragon(P,FMath::Max(ProbeSize,10.f)+10.f))return false;
    if(!bLegacySafety)
    {
        // Third pass: the interior of a thick body part is inside too, and the near plane needs room from the skin.
        if(IsPointBehindSkin(P,0.f))return false;
        if(NearestSkinCm(P)<NearSkinClearanceCm)return false;
    }
    // The knight seen without any see-through: clear sight lines to his chest and head, stopping short of him.
    const FVector Chest=FMath::Lerp(KBottom,KTop,.6f),Head=KTop;
    for(const FVector& T:{Chest,Head})
    {
        const FVector End=T+(P-T).GetSafeNormal()*(KRadius+25.f);
        if(!SegmentClearOfBareDragon(P,End,4.f))return false;
        // Marched all the way to his capsule: a knight against the lying neck is covered right next to him.
        if(!bLegacySafety&&!SightClear(P,T+(P-T).GetSafeNormal()*(KRadius+5.f)))return false;
    }
    return true;
}

namespace
{
    struct FVeyrFramingCandidate { float YawDeg; int32 Height; float Length; float Cost; };
    /** Placements in the owner's order of preference: the arm as is, lowered and level under the belly, slid
     * sideways round the body, the pivot raised, then shorter arms (closer than preferred; the lens widens). */
    const TArray<FVeyrFramingCandidate>& FramingCandidates(bool bLegacy)
    {
        // Third pass: low and to the side before up; the highest ring (pivot +420 cm x scale) is gone.
        static TArray<FVeyrFramingCandidate> Safe=[]
        {
            TArray<FVeyrFramingCandidate> L;
            const float Yaws[]={0.f,25.f,-25.f,50.f,-50.f,75.f,-75.f,105.f,-105.f,140.f,-140.f,180.f};
            const float HeightCost[]={0.f,.5f,4.f};
            const float Lengths[]={1.f,.8f,.62f,.5f};
            for(const float Y:Yaws)for(int32 H=0;H<3;++H)for(const float Len:Lengths)
                L.Add({Y,H,Len,FMath::Abs(Y)/25.f*.8f+HeightCost[H]+(1.f-Len)*6.f});
            L.Sort([](const FVeyrFramingCandidate& A,const FVeyrFramingCandidate& B){return A.Cost<B.Cost;});
            return L;
        }();
        if(!bLegacy)return Safe;
        static TArray<FVeyrFramingCandidate> List=[]
        {
            TArray<FVeyrFramingCandidate> L;
            const float Yaws[]={0.f,25.f,-25.f,50.f,-50.f,75.f,-75.f,105.f,-105.f,140.f,-140.f,180.f};
            const float HeightCost[]={0.f,.5f,1.6f,2.6f};
            const float Lengths[]={1.f,.8f,.62f,.5f};
            for(const float Y:Yaws)for(int32 H=0;H<4;++H)for(const float Len:Lengths)
                L.Add({Y,H,Len,FMath::Abs(Y)/25.f*.8f+HeightCost[H]+(1.f-Len)*6.f});
            L.Sort([](const FVeyrFramingCandidate& A,const FVeyrFramingCandidate& B){return A.Cost<B.Cost;});
            return L;
        }();
        return List;
    }
}

FVector UVeyrCameraBoom::FrameKnight(const FVector& Origin,const FVector& Base,const FVector& Proposed,float DeltaTime)
{
    FVector KB,KT;float KR=0.f;
    if(!KnightCapsule(KB,KT,KR)){bLastSolved=false;return Proposed;}
    const FVector Foot=KB-FVector::UpVector*KR;
    const float S=DragonScale();
    // The view turns with the swung arm (about the same pivot), keeping the knight where he was on screen.
    FRotator Swing=GetTargetRotation();Swing.Pitch=FMath::Max(Swing.Pitch-SafePitch,-38.f);Swing.Yaw+=SafeYaw;
    const FQuat ArmView=Swing.Quaternion();
    const FVector F0=ArmView.GetForwardVector();
    // What the arm's view looks at (the locked dragon or the player's aim), far enough past the knight.
    const FVector Mid=(KB+KT)*.5;
    const FVector LookAt=Base+F0*(FMath::Max(0.0,FVector::DotProduct(Mid-Base,F0))+1500.0);
    const float BaseDistance=FMath::PointDistToSegment(Base,KB,KT);
    // Never ask for more room than the stock arm had (an arena wall behind the knight), never less than the hard floor.
    const float Preferred=FMath::Clamp(BaseDistance,KnightHardMinCm,MinKnightDistanceCm);
    FVector Target=Proposed;bool bSolved=false;bool bFound=PlacementOk(Proposed,KB,KT,KR,Preferred);
    if(!bFound)
    {
        ++FramingSearches;
        const FVector Arm=Base-Origin;const double Length=Arm.Size();
        auto Make=[&](const FVeyrFramingCandidate& C)
        {
            FVector P=Origin+FRotator(0.f,C.YawDeg,0.f).RotateVector(Arm)*C.Length;
            if(C.Height==1)P.Z=Foot.Z+120.f;              // lowered and level: the room under the belly
            else if(C.Height==2)P.Z+=(bLegacySafety?200.f:120.f)*S; // pivot raised (third pass: less)
            else if(C.Height==3)P.Z+=420.f*S;
            return P;
        };
        auto WorldClear=[&](FVector& P)
        {
            if(!GetWorld())return true;
            FHitResult Hit;FCollisionQueryParams Params(SCENE_QUERY_STAT(VeyrBoomFraming),false,GetOwner());
            if(!GetWorld()->SweepSingleByChannel(Hit,Origin,P,FQuat::Identity,ProbeChannel,FCollisionShape::MakeSphere(ProbeSize),Params))return true;
            P=Hit.Location;return false;
        };
        const TArray<FVeyrFramingCandidate>& List=FramingCandidates(bLegacySafety);
        auto Try=[&](int32 Index,float MinDistance)
        {
            FVector P=Make(List[Index]);
            if(!PlacementOk(P,KB,KT,KR,MinDistance))return false;
            FVector Swept=P;
            if(!WorldClear(Swept)&&!PlacementOk(Swept,KB,KT,KR,MinDistance))return false;
            Target=Swept;return true;
        };
        if(Length>1.0)
        {
            // The placement used last frame first, so the view does not flip between equal choices.
            if(StickyCandidate!=INDEX_NONE&&Try(StickyCandidate,KnightHardMinCm))bFound=true;
            int32 Evaluated=0;
            for(int32 I=0;I<List.Num()&&!bFound&&Evaluated<(bLegacySafety?96:144);++I,++Evaluated)
            {
                const float Need=List[I].Length<.79f?KnightHardMinCm:Preferred;
                if(Try(I,Need)){bFound=true;StickyCandidate=I;}
            }
        }
        if(!bFound)
        {
            // Nothing clean: keep out of the knight and the dragon first, sight lines second.
            ++FramingFallbackFrames;
            StickyCandidate=INDEX_NONE;
            if(bLegacySafety)
            {
                const FVector Up=Foot+FVector::UpVector*FMath::Max(600.f*S,(KT.Z-Foot.Z)+400.f)-F0.GetSafeNormal2D()*KnightHardMinCm;
                Target=!IsPointInsideBareDragon(Proposed,10.f)&&FMath::PointDistToSegment(Proposed,KB,KT)>=KR+60.f?Proposed:Up;
            }
            else
            {
                // Never up and never into the body: walk the arm in towards its pivot (the stock arm's answer; the
                // pivot sits at the knight's shoulder, outside the dragon), then a low ring round the knight.
                const FVector Chest=FMath::Lerp(KB,KT,.6f);
                auto Clean=[&](const FVector& P,bool bNeedSight)
                {
                    if(P.Z<Foot.Z+40.f||FMath::PointDistToSegment(P,KB,KT)<KR+60.f||IsPointInsideBody(P,10.f))return false;
                    return !bNeedSight||SightClear(P,Chest+(P-Chest).GetSafeNormal()*(KR+5.f));
                };
                bool bPicked=false;
                for(const bool bNeedSight:{true,false})
                {
                    for(const float T:{.85f,.7f,.55f,.42f,.3f})
                    {
                        const FVector P=FMath::Lerp(Origin,Proposed,T);
                        if(Clean(P,bNeedSight)){Target=P;bPicked=true;break;}
                    }
                    for(int32 A=0;A<12&&!bPicked;++A)
                    {
                        const FVector Dir=FRotator(0.f,A*30.f,0.f).RotateVector(-F0.GetSafeNormal2D());
                        const FVector P=FVector(Chest.X,Chest.Y,Foot.Z+170.f)+Dir*KnightHardMinCm;
                        if(Clean(P,bNeedSight)){Target=P;bPicked=true;}
                    }
                    if(bPicked)break;
                }
                if(!bPicked)Target=bLastFramed?Foot+LastFramedRelative:FMath::Lerp(Origin,Proposed,.3f);
            }
        }
        bSolved=true;
    }
    else StickyCandidate=INDEX_NONE;
    // Ease between placements (relative to the knight) whenever a search is involved, unless the eased point is not clean.
    FVector Out=Target;
    if((bSolved||bLastSolved)&&bLastFramed)
    {
        const FVector Eased=Foot+FMath::VInterpTo(LastFramedRelative,Target-Foot,DeltaTime,7.f);
        if(PlacementOk(Eased,KB,KT,KR,KnightHardMinCm))Out=Eased;
        else if(!bLegacySafety)
        {
            // Third pass: a straight ease can cut through the body between two clean placements; swing round the
            // knight instead (yaw, height and distance eased separately), then a faster ease; a snap only after both.
            const FVector From=LastFramedRelative,To=Target-Foot;
            const float A=FMath::RadiansToDegrees(FMath::Atan2(From.Y,From.X)),B=FMath::RadiansToDegrees(FMath::Atan2(To.Y,To.X));
            const float Alpha=FMath::Clamp(DeltaTime*7.f,0.f,1.f);
            const float Yaw=FMath::DegreesToRadians(A+FMath::FindDeltaAngleDegrees(A,B)*Alpha);
            const float Radius=FMath::Lerp(static_cast<float>(From.Size2D()),static_cast<float>(To.Size2D()),Alpha);
            const FVector Swung=Foot+FVector(FMath::Cos(Yaw)*Radius,FMath::Sin(Yaw)*Radius,FMath::Lerp(From.Z,To.Z,Alpha));
            const FVector Fast=Foot+FMath::VInterpTo(LastFramedRelative,To,DeltaTime,20.f);
            if(PlacementOk(Swung,KB,KT,KR,KnightHardMinCm))Out=Swung;
            else if(PlacementOk(Fast,KB,KT,KR,KnightHardMinCm))Out=Fast;
            else ++SafetySnaps;
        }
    }
    LastFramedRelative=Out-Foot;bLastFramed=true;bLastSolved=bSolved;
    // View: keep looking where the arm looked, turned only as far as the knight needs to stay whole in frame.
    float Boost=0.f;
    const UCameraComponent* Camera=nullptr;
    for(USceneComponent* Child:GetAttachChildren())if(const UCameraComponent* C=Cast<UCameraComponent>(Child)){Camera=C;break;}
    // The lens the knight set this frame (without the boost this arm added last frame).
    const float Fov=!Camera?72.f:FMath::IsNearlyEqual(Camera->FieldOfView,AppliedFov,.01f)?Camera->FieldOfView-AppliedFovBoost:Camera->FieldOfView;
    const FQuat View=FrameView(Out,ArmView,LookAt,Fov,Boost);
    // Ease only the correction on top of the arm's own view, so player look keeps no lag.
    const FQuat Correction=View*ArmView.Inverse();
    ViewCorrection=bViewCorrectionValid?FQuat::Slerp(ViewCorrection,Correction,FMath::Clamp(DeltaTime*10.f,0.f,1.f)):Correction;
    ViewCorrection.Normalize();bViewCorrectionValid=true;
    FramedView=ViewCorrection*ArmView;
    // The eased view must still hold the whole knight; otherwise take the solved view at once.
    if(!KnightWholeInView(Out,FramedView,Fov+FMath::Max(FovBoostDeg,Boost))){ViewCorrection=Correction;ViewCorrection.Normalize();FramedView=View;}
    FramedLookAt=LookAt;bFramedViewValid=true;
    FovBoostDeg=FMath::FInterpTo(FovBoostDeg,Boost,DeltaTime,4.f);
    if(FramedView.AngularDistance(ArmView)>FMath::DegreesToRadians(2.f))++ViewTurnFrames;
    return Out;
}

FQuat UVeyrCameraBoom::FrameView(const FVector& Camera,const FQuat& ArmView,const FVector& LookAt,float Fov,float& OutBoost) const
{
    OutBoost=0.f;
    FVector KB,KT;float KR=0.f;
    FRotator R=(LookAt-Camera).Rotation();R.Roll=0.f;
    if(!KnightCapsule(KB,KT,KR))return R.Quaternion();
    const float Aspect=ViewAspect();
    const FVector Bottom=KB-FVector::UpVector*KR,Top=KT+FVector::UpVector*KR;
    const double M=1.0-KnightScreenMargin;
    const double TanH=FMath::Tan(FMath::DegreesToRadians(Fov*.5)),TanV=TanH/FMath::Max(.5f,Aspect);
    const double LimitV=FMath::RadiansToDegrees(FMath::Atan(M*TanV)),LimitH=FMath::RadiansToDegrees(FMath::Atan(M*TanH));
    auto Angles=[&](const FVector& P,const FRotator& View,double& Azimuth,double& Elevation)
    {
        const FVector L=View.Quaternion().UnrotateVector(P-Camera);
        Azimuth=FMath::RadiansToDegrees(FMath::Atan2(L.Y,FMath::Max(1.0,L.X)));
        Elevation=FMath::RadiansToDegrees(FMath::Atan2(L.Z,FMath::Max(1.0,FVector2D(L.X,L.Y).Size())));
    };
    for(int32 Pass=0;Pass<3;++Pass)
    {
        double AzB,ElB,AzT,ElT,AzM,ElM;
        Angles(Bottom,R,AzB,ElB);Angles(Top,R,AzT,ElT);Angles((Bottom+Top)*.5,R,AzM,ElM);
        // Vertical: boots above the bottom edge first (the owner's cut-off complaint), then the head below the top.
        double Pitch=0.0;
        if(ElB<-LimitV)Pitch=ElB+LimitV;
        else if(ElT>LimitV)Pitch=FMath::Min(ElT-LimitV,ElB+LimitV);
        // Horizontal: the knight's sides inside the frame.
        const double Side=FMath::Atan2(static_cast<double>(KR),FMath::Max(1.0,static_cast<double>(FVector::Dist(Camera,(KB+KT)*.5))));
        const double Half=FMath::RadiansToDegrees(Side);
        double Yaw=0.0;
        if(AzM+Half>LimitH)Yaw=AzM+Half-LimitH;else if(AzM-Half<-LimitH)Yaw=AzM-Half+LimitH;
        if(FMath::Abs(Pitch)<.05&&FMath::Abs(Yaw)<.05)break;
        R.Pitch+=static_cast<float>(Pitch);R.Yaw+=static_cast<float>(Yaw);
    }
    // Third pass: no steep top-down view; past the floor the lens opens instead (boots may sit at the edge).
    if(!bLegacySafety&&R.Pitch<MinViewPitchDeg)R.Pitch=MinViewPitchDeg;
    // Still taller than the frame: open the lens, up to MaxFovBoostDeg.
    double AzB,ElB,AzT,ElT;Angles(Bottom,R,AzB,ElB);Angles(Top,R,AzT,ElT);
    // Third pass: the half-height the lens must hold is also whatever the pitch floor pushed past the edge.
    const double Span=bLegacySafety?(ElT-ElB)*.5:FMath::Max3((ElT-ElB)*.5,-ElB,ElT);
    if(Span>LimitV)
    {
        const double NeedTanV=FMath::Tan(FMath::DegreesToRadians(FMath::Min(Span,80.0)))/M;
        const double NeedFov=2.0*FMath::RadiansToDegrees(FMath::Atan(NeedTanV*Aspect));
        OutBoost=static_cast<float>(FMath::Clamp(NeedFov-Fov,0.0,static_cast<double>(MaxFovBoostDeg)));
    }
    return R.Quaternion();
}

void UVeyrCameraBoom::UpdateDesiredArmLocation(bool bDoTrace,bool bDoLocationLag,bool bDoRotationLag,float DeltaTime)
{
    Super::UpdateDesiredArmLocation(bDoTrace,bDoLocationLag,bDoRotationLag,DeltaTime);
    UCameraComponent* Camera=nullptr;
    for(USceneComponent* Child:GetAttachChildren())if(UCameraComponent* C=Cast<UCameraComponent>(Child)){Camera=C;break;}
    if(!bFramedViewValid||bLegacyBoom||bLegacyFraming)
    {
        bViewCorrectionValid=false;
        if(Camera&&AppliedFovBoost!=0.f&&FMath::IsNearlyEqual(Camera->FieldOfView,AppliedFov,.01f))Camera->SetFieldOfView(Camera->FieldOfView-AppliedFovBoost);
        AppliedFovBoost=0.f;FovBoostDeg=0.f;
        return;
    }
    RelativeSocketRotation=GetComponentTransform().GetRotation().Inverse()*FramedView;
    UpdateChildTransforms();
    if(Camera)
    {
        // The knight sets the lens every frame; add the boost once on top of whatever it set.
        const float BaseFov=FMath::IsNearlyEqual(Camera->FieldOfView,AppliedFov,.01f)?Camera->FieldOfView-AppliedFovBoost:Camera->FieldOfView;
        AppliedFovBoost=FovBoostDeg;AppliedFov=BaseFov+AppliedFovBoost;
        Camera->SetFieldOfView(AppliedFov);
    }
}

FVector UVeyrCameraBoom::SafeArm(const FVector& Origin0,const FVector& Base,float DeltaTime)
{
    const float S=DragonScale();
    FVector KB,KT;float KR=0.f;const bool bKnight=KnightCapsule(KB,KT,KR);
    // Clearance of the lens from the skin: the near plane plus a margin, growing with the dragon.
    const float Clear=FMath::Max(ProbeSize+10.f,20.f*S);
    auto Blocked=[&](const FVector& P){return IsPointInsideBareDragon(P,Clear)||IsPointBehindSkin(P,0.f)||NearestSkinCm(P)<Clear;};
    // 1. The pivot (the knight's shoulder) pressed into the body: raise it a little until it is clear.
    FVector Origin=Origin0;
    if(Blocked(Origin))
    {
        ++PivotLiftFrames;
        for(int32 K=1;K<=6;++K){const FVector P=Origin0+FVector::UpVector*15.f*S*K;if(!Blocked(P)){Origin=P;break;}}
    }
    // 2. The arm swept as a sphere against the full body: the first blocked step (or a wing crossed) ends it.
    const float Length=static_cast<float>(FVector::Dist(Origin,Base));
    FBox Body(ForceInit);const bool bSurface=EnsureSurface();
    if(bSurface){Body=SurfaceBounds;if(WingBounds.IsValid)Body+=WingBounds;Body=Body.ExpandBy(Clear+100.f*S);}
    auto Sweep=[&](const FVector& End,float StepCm=0.f)
    {
        // Quick reject: the arm nowhere near the skinned body or wings (shapes stay inside those boxes).
        FBox Arm(ForceInit);Arm+=Origin;Arm+=End;
        if(Length<=1.f||(bSurface&&!Body.Intersect(Arm)))return 1.f;
        const int32 Steps=FMath::Clamp(FMath::CeilToInt(Length/(StepCm>0.f?StepCm:FMath::Max(8.f,6.f*S))),1,128);
        FVector Previous=Origin;
        for(int32 I=1;I<=Steps;++I)
        {
            const FVector P=FMath::Lerp(Origin,End,static_cast<float>(I)/Steps);
            if(Blocked(P)||CrossesWing(Previous,P))return static_cast<float>(I-1)/Steps;
            Previous=P;
        }
        return 1.f;
    };
    // A short arm swings up about the pivot (12-36 deg) before it gives up length: over the body behind the
    // knight rather than into his back. The swing eases; the length pulls in at once.
    // A blocked arm swings about the pivot (up first, then round the knight) to the first swing that is clear for
    // most of its length with the knight in sight; the swing eases, the length pulls in at once. Sticky: the
    // swing in use is kept while it still works.
    auto Swung=[&](float Pitch,float Yaw){FRotator R=(Base-Origin).Rotation();R.Pitch=FMath::Min(R.Pitch+Pitch,60.f);R.Yaw+=Yaw;return Origin+R.Vector()*Length;};
    FVector KChest=Origin,KHelm=Origin;if(bKnight){KChest=FMath::Lerp(KB,KT,.6f);KHelm=KT;}
    auto SeesFrom=[&](const FVector& P)
    {
        if(!bKnight)return true;
        for(const FVector& T:{KChest,KHelm})if(!SightClear(P,T+(P-T).GetSafeNormal()*(KR+5.f),true))return false;
        return true;
    };
    auto Good=[&](float Pitch,float Yaw)
    {
        const FVector E=Swung(Pitch,Yaw);const float T=Sweep(E,30.f*S);
        return T>=.6f&&SeesFrom(FMath::Lerp(Origin,E,T));
    };
    if(!Good(SwingPitchTarget,SwingYawTarget))
    {
        // Up first (the view tilts down by the same angle, so the knight keeps his place on screen), never past
        // a view pitch of -38 deg; round him only when no rise works.
        static const float Options[][2]={{0,0},{12,0},{24,0},{36,0},{0,30},{0,-30},{20,30},{20,-30},{0,60},{0,-60}};
        const float MaxRise=FMath::Max(0.f,GetTargetRotation().Pitch+38.f);
        bool bFound=false;
        for(const auto& O:Options)if(O[0]<=MaxRise&&Good(O[0],O[1])){SwingPitchTarget=O[0];SwingYawTarget=O[1];bFound=true;break;}
        if(!bFound){SwingPitchTarget=FMath::Min(12.f,MaxRise);SwingYawTarget=0.f;++SightPullFails;}
    }
    else if(SwingPitchTarget!=0.f||SwingYawTarget!=0.f)
    {
        // Drift back to the player's own arm once it has been clear for a second (no flapping).
        SwingClearSeconds=Good(0.f,0.f)?SwingClearSeconds+DeltaTime:0.f;
        if(SwingClearSeconds>1.f){SwingPitchTarget=0.f;SwingYawTarget=0.f;SwingClearSeconds=0.f;}
    }
    SafePitch=FMath::FInterpTo(SafePitch,SwingPitchTarget,DeltaTime,3.f);
    SafeYaw=FMath::FInterpTo(SafeYaw,SwingYawTarget,DeltaTime,2.5f);
    const FVector End=Swung(SafePitch,SafeYaw);
    float Target=Sweep(End);
    // Never closer to the knight than his own body plus room for the near plane.
    if(bKnight&&Length>1.f)Target=FMath::Max(Target,FMath::Min(1.f,(KR+140.f)/Length));
    // The knight in sight from there (chest and helmet, to his capsule): otherwise come in along the arm
    // until he is, so a claw or the neck between lens and knight never hides him.
    if(bKnight&&Length>1.f)
    {
        const FVector Chest=FMath::Lerp(KB,KT,.6f),Helm=KT;
        auto Sees=[&](float F)
        {
            const FVector P=FMath::Lerp(Origin,End,F);
            for(const FVector& T:{Chest,Helm})if(!SightClear(P,T+(P-T).GetSafeNormal()*(KR+5.f),true))return false;
            return true;
        };
        if(!Sees(Target))
        {
            const float Floor=FMath::Min(1.f,(KR+140.f)/Length);
            float Found=-1.f;
            for(const float K:{.85f,.7f,.55f,.4f,.25f}){const float F=FMath::Max(Floor,Target*K);if(Sees(F)){Found=F;break;}if(F<=Floor)break;}
            if(Found>0.f)Target=Found;else ++SightPullFails;
        }
    }
    // Instant pull-in, eased release.
    if(Target<SafeFraction){if(SafeFraction>=.999f&&Target<.999f)++PullInEvents;SafeFraction=Target;}
    else SafeFraction=FMath::Min(Target,FMath::FInterpTo(SafeFraction,Target,DeltaTime,ReleaseRate));
    const FVector Pulled=FMath::Lerp(Origin,End,SafeFraction);
    // 3. A short arm rises slightly (only through clear space) and widens the lens.
    const float Short=FMath::Clamp(1.f-SafeFraction/.55f,0.f,1.f);
    float WantLift=ShortArmLiftCm*S*Short;
    if(WantLift>1.f)
        for(int32 K=1;K<=8;++K)
            if(Blocked(Pulled+FVector::UpVector*WantLift*K/8.f)){WantLift*=(K-1)/8.f;break;}
    SafeLift=FMath::FInterpTo(SafeLift,WantLift,DeltaTime,WantLift>SafeLift?6.f:3.f);
    SafeLens=FMath::FInterpTo(SafeLens,ShortArmLensDeg*Short,DeltaTime,5.f);
    FVector Result=Pulled+FVector::UpVector*SafeLift;
    if(SafeLift>1.f&&Blocked(Result))Result=Pulled;
    // 4. No pops: at most MaxMoveCmPerFrame relative to the knight per frame (a blink still carries the camera).
    // World space: the knight's own run counts too; only a knight blink (over 150 cm) carries the camera along.
    const FVector Anchor=bKnight?KB:Origin;
    if(bSafeLast)
    {
        FVector Previous=SafeLastWorld;const FVector Carried=Anchor-SafeLastAnchor;
        if(Carried.Size()>150.f)Previous+=Carried;
        const FVector Delta=Result-Previous;
        if(Delta.Size()>MaxMoveCmPerFrame){Result=Previous+Delta.GetClampedToMaxSize(MaxMoveCmPerFrame);++ClampedMoves;}
    }
    SafeLastRelative=Result-Anchor;SafeLastWorld=Result;SafeLastAnchor=Anchor;bSafeLast=true;
    if(IsPointInsideBareDragon(Result,10.f))++ResultInsideFrames;
    FinishView(Result,Base,DeltaTime,SafeLens);
    return Result;
}

void UVeyrCameraBoom::FinishView(const FVector& Out,const FVector& Base,float DeltaTime,float ExtraLensDeg)
{
    // The view turns with the swung arm (about the same pivot), keeping the knight where he was on screen.
    FRotator Swing=GetTargetRotation();Swing.Pitch=FMath::Max(Swing.Pitch-SafePitch,-38.f);Swing.Yaw+=SafeYaw;
    const FQuat ArmView=Swing.Quaternion();
    const FVector F0=ArmView.GetForwardVector();
    FVector KB,KT;float KR=0.f;
    FVector LookAt=Base+F0*1500.0;
    if(KnightCapsule(KB,KT,KR)){const FVector Mid=(KB+KT)*.5;LookAt=Base+F0*(FMath::Max(0.0,FVector::DotProduct(Mid-Base,F0))+1500.0);}
    const UCameraComponent* Camera=nullptr;
    for(USceneComponent* Child:GetAttachChildren())if(const UCameraComponent* C=Cast<UCameraComponent>(Child)){Camera=C;break;}
    const float Fov=!Camera?72.f:FMath::IsNearlyEqual(Camera->FieldOfView,AppliedFov,.01f)?Camera->FieldOfView-AppliedFovBoost:Camera->FieldOfView;
    float Boost=0.f;
    const FQuat View=FrameView(Out,ArmView,LookAt,Fov+ExtraLensDeg,Boost);
    Boost=FMath::Min(MaxFovBoostDeg,Boost+ExtraLensDeg);
    const FQuat Correction=View*ArmView.Inverse();
    ViewCorrection=bViewCorrectionValid?FQuat::Slerp(ViewCorrection,Correction,FMath::Clamp(DeltaTime*10.f,0.f,1.f)):Correction;
    ViewCorrection.Normalize();bViewCorrectionValid=true;
    FramedView=ViewCorrection*ArmView;
    if(!KnightWholeInView(Out,FramedView,Fov+FMath::Max(FovBoostDeg,Boost))){ViewCorrection=Correction;ViewCorrection.Normalize();FramedView=View;}
    // No pops: at most MaxTurnDegPerFrame of turn per frame.
    if(bSafeLastView)
    {
        const float Turn=FMath::RadiansToDegrees(static_cast<float>(FramedView.AngularDistance(SafeLastView)));
        if(Turn>MaxTurnDegPerFrame){FramedView=FQuat::Slerp(SafeLastView,FramedView,MaxTurnDegPerFrame/Turn);FramedView.Normalize();++ClampedTurns;}
    }
    SafeLastView=FramedView;bSafeLastView=true;
    FramedLookAt=LookAt;bFramedViewValid=true;
    FovBoostDeg=FMath::FInterpTo(FovBoostDeg,Boost,DeltaTime,4.f);
    if(FramedView.AngularDistance(ArmView)>FMath::DegreesToRadians(2.f))++ViewTurnFrames;
}

void UVeyrCameraBoom::AuditView(FVeyrViewAudit& A,const FVector& Camera,const FQuat& View,float HorizontalFovDeg,float Seconds)
{
    FindDragon();
    if(bLegacyBoom)RefreshShapes(); // the stock arm does not refresh the shapes itself
    const float Dt=A.LastSeconds>=0.f?FMath::Max(0.f,Seconds-A.LastSeconds):0.f;A.LastSeconds=Seconds;
    ++A.Frames;
    auto Note=[](TArray<float>& L,float T){if(L.Num()<60&&(L.IsEmpty()||T-L.Last()>.5f))L.Add(T);};
    FVector KB,KT;float KR=0.f;const bool bKnight=KnightCapsule(KB,KT,KR);
    const bool bCapsule=IsPointInsideSolidCapsule(Camera,0.f);
    const bool bHull=IsPointInsideBareDragon(Camera,10.f);
    const bool bBehind=IsPointBehindSkin(Camera,10.f);
    const bool bNear=NearestSkinCm(Camera)<10.f;
    const bool bInside=bCapsule||bHull||bBehind;
    A.InsideCapsule+=bCapsule;A.InsideHull+=bHull;A.BehindSkin+=bBehind;A.NearSkin+=bNear;A.InsideAny+=bInside;
    A.InsideRun=bInside?A.InsideRun+1:0;A.LongestInsideRun=FMath::Max(A.LongestInsideRun,A.InsideRun);
    if(bInside)Note(A.InsideSeconds,Seconds);
    const float Pitch=View.Rotator().Pitch;A.MinPitchDeg=FMath::Min(A.MinPitchDeg,Pitch);
    if(Pitch<-40.f){++A.SteepFrames;Note(A.SteepSeconds,Seconds);}
    // Pops: camera movement and turn per frame (a knight blink is counted apart).
    const FVector KnightAt=bKnight?KB:Camera;
    // A gap in the audited frames is a cut away from the knight's camera (intro, restart): not a pop.
    if(A.bHasLast&&Dt>.25f){++A.Cuts;A.bHasLast=false;A.SettleFrames=0;}
    // The first frames after the intro hands over (or after a cut) are the cut itself, not a pop.
    if(++A.SettleFrames<=3)A.bHasLast=false;
    if(A.bHasLast)
    {
        const float Move=static_cast<float>(FVector::Dist(Camera,A.LastCamera));
        const float Turn=FMath::RadiansToDegrees(static_cast<float>(View.AngularDistance(A.LastView)));
        const bool bTeleport=FVector::Dist(KnightAt,A.LastKnight)>150.f;
        A.KnightTeleports+=bTeleport;
        if(!bTeleport)
        {
            A.MaxMoveCm=FMath::Max(A.MaxMoveCm,Move);A.MaxTurnDeg=FMath::Max(A.MaxTurnDeg,Turn);
            if(Move>150.f||Turn>12.f)
            {
                if(Move>150.f)++A.MoveJumps;if(Turn>12.f)++A.TurnJumps;Note(A.JumpSeconds,Seconds);
                if(A.JumpDetail.Num()<200)A.JumpDetail.Append({Seconds,Move,static_cast<float>(FVector::Dist(KnightAt,A.LastKnight)),Turn,Dt,
                    static_cast<float>(IsPointInsideBareDragon(Camera,10.f)),static_cast<float>(FVector::Dist(Camera,GetComponentLocation()))});
            }
        }
    }
    A.LastCamera=Camera;A.LastView=View;A.LastKnight=KnightAt;A.bHasLast=true;
    if(!bKnight)return;
    const float Surface=FMath::PointDistToSegment(Camera,KB,KT)-KR;
    A.MinCameraToKnightCm=FMath::Min(A.MinCameraToKnightCm,Surface);A.InsideKnight+=Surface<10.f;
    A.KnightWhole+=KnightWholeInView(Camera,View,HorizontalFovDeg);
    // How much of the knight the player sees: 7 points on his body, each inside the central 80 % of the frame
    // with no dragon skin (shapes, interior, wings) between it and the lens.
    const float Aspect=ViewAspect();const FVector Right=View.GetRightVector();
    const FVector Foot=KB-FVector::UpVector*KR,Head=KT+FVector::UpVector*KR*.6f;
    const FVector Points[7]={FMath::Lerp(Foot,Head,.05f),FMath::Lerp(Foot,Head,.3f),FMath::Lerp(Foot,Head,.55f),FMath::Lerp(Foot,Head,.8f),Head,
        FMath::Lerp(Foot,Head,.5f)+Right*KR*.8f,FMath::Lerp(Foot,Head,.5f)-Right*KR*.8f};
    int32 Seen=0,Centre=0;
    for(const FVector& P:Points)
    {
        float U,V;
        if(!ProjectToView(P,Camera,View,HorizontalFovDeg,Aspect,U,V)||FMath::Abs(U)>.8f||FMath::Abs(V)>.8f)continue;
        ++Centre;
        if(SightClear(Camera,P,true))++Seen;
    }
    A.OutsideCentre+=Centre<4;
    const bool bHalf=Seen*2>=7;A.HalfVisible+=bHalf;
    const bool bHidden=Seen==0;A.FullyHidden+=bHidden;
    A.HiddenRunSeconds=bHidden?A.HiddenRunSeconds+Dt:0.f;A.LongestHiddenSeconds=FMath::Max(A.LongestHiddenSeconds,A.HiddenRunSeconds);
    if(!bHalf)Note(A.HiddenSeconds,Seconds);
}

TSharedPtr<FJsonObject> UVeyrCameraBoom::AuditJson(const FVeyrViewAudit& A) const
{
    TSharedPtr<FJsonObject> O=MakeShared<FJsonObject>();
    auto N=[&](const TCHAR* K,double V){O->SetNumberField(K,V);};
    N(TEXT("frames"),A.Frames);N(TEXT("insideDragonFrames"),A.InsideAny);N(TEXT("insideCapsuleFrames"),A.InsideCapsule);
    N(TEXT("insideHullFrames"),A.InsideHull);N(TEXT("behindSkinFrames"),A.BehindSkin);N(TEXT("skinWithin10cmFrames"),A.NearSkin);
    N(TEXT("longestInsideRunFrames"),A.LongestInsideRun);N(TEXT("insideKnightFrames"),A.InsideKnight);
    N(TEXT("knightWholeOnScreenShare"),A.Frames?static_cast<double>(A.KnightWhole)/A.Frames:0.0);
    N(TEXT("knightHalfVisibleShare"),A.Frames?static_cast<double>(A.HalfVisible)/A.Frames:0.0);
    N(TEXT("knightFullyHiddenFrames"),A.FullyHidden);N(TEXT("longestHiddenSeconds"),A.LongestHiddenSeconds);
    N(TEXT("knightOutsideCentreFrames"),A.OutsideCentre);
    N(TEXT("moveJumpFrames"),A.MoveJumps);N(TEXT("turnJumpFrames"),A.TurnJumps);N(TEXT("knightTeleportFrames"),A.KnightTeleports);
    N(TEXT("maxMoveCmPerFrame"),A.MaxMoveCm);N(TEXT("maxTurnDegPerFrame"),A.MaxTurnDeg);
    N(TEXT("steepPitchFrames"),A.SteepFrames);N(TEXT("minPitchDeg"),A.MinPitchDeg);
    N(TEXT("minCameraToKnightCm"),A.MinCameraToKnightCm<1e30f?A.MinCameraToKnightCm:-1.0);
    N(TEXT("clampedMoves"),ClampedMoves);N(TEXT("sightPullFails"),SightPullFails);N(TEXT("clampedTurns"),ClampedTurns);N(TEXT("pivotLiftFrames"),PivotLiftFrames);N(TEXT("pullInEvents"),PullInEvents);
    O->SetBoolField(TEXT("legacyCameraSafety"),bLegacySafety);O->SetBoolField(TEXT("legacyCameraFraming"),bLegacyFraming);O->SetBoolField(TEXT("legacyCameraBoom"),bLegacyBoom);
    auto Times=[&](const TCHAR* K,const TArray<float>& V){TArray<TSharedPtr<FJsonValue>> L;for(float T:V)L.Add(MakeShared<FJsonValueNumber>(FMath::RoundToFloat(T*100.f)/100.f));O->SetArrayField(K,L);};
    Times(TEXT("insideSeconds"),A.InsideSeconds);Times(TEXT("hiddenSeconds"),A.HiddenSeconds);Times(TEXT("jumpSeconds"),A.JumpSeconds);Times(TEXT("steepSeconds"),A.SteepSeconds);Times(TEXT("jumpDetail_t_move_knightMove_turn_dt_inside_fromPivot"),A.JumpDetail);N(TEXT("viewCuts"),A.Cuts);
    O->SetStringField(TEXT("scope"),TEXT("every replay frame whose view target is the knight, whole replay (held by the replay, survives restart); seconds are replay seconds; visible = 7 knight points inside the central 80 % with no dragon skin (shapes, interior, wings) in between; jumps = >150 cm or >12 deg in one frame, knight blinks excluded"));
    return O;
}
