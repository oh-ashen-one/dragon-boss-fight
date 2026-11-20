#include "VeyrCameraBoom.h"
#include "VeyrKnight.h"
#include "VeyrDragon.h"
#include "VeyrSkeletalPresentation.h"
#include "Components/CapsuleComponent.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "Misc/CommandLine.h"
#include "Camera/CameraComponent.h"
#include "Dom/JsonObject.h"
#include "Dom/JsonValue.h"
#include "VeyrGameMode.h"
#include "VeyrFightFeel.h"
#include "Components/CapsuleComponent.h"
#include "Engine/GameViewportClient.h"
#include "GameFramework/Character.h"
#include "HAL/PlatformTime.h"
#include "Engine/SkeletalMesh.h"

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
    bCollideRig=!FadeRigSwitchedOn(); // -VeyrCameraCollideRig (or any older-camera switch)
    bLegacyPlacement=FParse::Param(FCommandLine::Get(),TEXT("VeyrLegacyCameraPlacement"));
    // Windowless tuning without a rebuild (defaults are the shipped values).
    const TCHAR* Cmd=FCommandLine::Get();
    FParse::Value(Cmd,TEXT("VeyrRigMargin="),RigProxyMarginCm);FParse::Value(Cmd,TEXT("VeyrRigLens="),RigLensRadiusCm);
    FParse::Value(Cmd,TEXT("VeyrRigShortArm="),RigShortArmCm);FParse::Value(Cmd,TEXT("VeyrRigHide="),RigHideCm);
    FParse::Value(Cmd,TEXT("VeyrRigOverUp="),RigOverheadUpCm);FParse::Value(Cmd,TEXT("VeyrRigOverBack="),RigOverheadBackCm);
    FParse::Value(Cmd,TEXT("VeyrRigOverPitch="),RigOverheadPitchDeg);FParse::Value(Cmd,TEXT("VeyrRigAssistDown="),RigAssistDownDeg);FParse::Value(Cmd,TEXT("VeyrRigMaxUp="),RigMaxUpDeg);
    FParse::Value(Cmd,TEXT("VeyrRigFootprint="),RigFootprintCm);
    FParse::Value(Cmd,TEXT("VeyrFadeNear="),FadeNearCm);FParse::Value(Cmd,TEXT("VeyrFadeFar="),FadeFarCm);FParse::Value(Cmd,TEXT("VeyrFadeMinArm="),FadeMinArmFraction);
    FParse::Value(Cmd,TEXT("VeyrFadeUp="),FadeUpDeg);FParse::Value(Cmd,TEXT("VeyrFadeDown="),FadeDownDeg);FParse::Value(Cmd,TEXT("VeyrFadeSightFloor="),FadeSightFloor);FParse::Value(Cmd,TEXT("VeyrFadeMaxStep="),FadeMaxStepCm);if(FParse::Param(Cmd,TEXT("VeyrFadeNoStepLimit")))FadeMaxStepCm=0.f;bDragonFraming=!FParse::Param(Cmd,TEXT("VeyrNoDragonFraming"));bHeadChestFraming=!FParse::Param(Cmd,TEXT("VeyrLegacyDragonFraming"));bCoverageFade=!FParse::Param(Cmd,TEXT("VeyrFadeDistanceOnly"));bKnightSafeArea=!FParse::Param(Cmd,TEXT("VeyrNoKnightSafeArea"));FParse::Value(Cmd,TEXT("VeyrFramePullMax="),FramePullMax);FParse::Value(Cmd,TEXT("VeyrRigPivot="),RigPivotHeightCm);
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
    if(UsesRig())
    {
        const double Start=FPlatformTime::Seconds();
        UpdateProxy();++BodyFrames;
        // Fade rig only with the dragon's fade materials bound; otherwise the lens must stay outside (collide rig).
        const AVeyrDragon* FadeDragon=Dragon.Get();
        const bool bFade=UsesFadeRig()&&(!FadeDragon||FadeDragon->bCameraFadeMaterials);
        const FVector Lens=bFade?FadeArm(Base,DeltaTime):RigArm(Base,DeltaTime);
        if(bFadeArenaPull)FadeArenaPullFrame=GFrameCounter;
        const double Spent=FPlatformTime::Seconds()-Start;RigSeconds+=Spent;RigMaxSeconds=FMath::Max(RigMaxSeconds,Spent);++RigCalls;
        if(OverheadAlpha>.01f)++RigOverheadFrames;
        return Lens;
    }
    if(bKnightHiddenByCamera)SetKnightHiddenByCamera(false);
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
    UCameraComponent* Camera=nullptr;
    for(USceneComponent* Child:GetAttachChildren())if(UCameraComponent* C=Cast<UCameraComponent>(Child)){Camera=C;break;}
    // Last frame's punch, if nobody set the lens since: take it back out before framing reads the lens.
    if(Camera&&PunchedFov>0.f&&FMath::IsNearlyEqual(Camera->FieldOfView,PunchedFov,.001f))Camera->SetFieldOfView(PunchBaseFov);
    PunchedFov=-1.f;
    Super::UpdateDesiredArmLocation(bDoTrace,bDoLocationLag,bDoRotationLag,DeltaTime);
    if(!bFramedViewValid||bLegacyBoom||bLegacyFraming)
    {
        bViewCorrectionValid=false;
        if(Camera&&AppliedFovBoost!=0.f&&FMath::IsNearlyEqual(Camera->FieldOfView,AppliedFov,.01f))Camera->SetFieldOfView(Camera->FieldOfView-AppliedFovBoost);
        AppliedFovBoost=0.f;FovBoostDeg=0.f;
        ApplyFeelPunch(Camera);
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
    ApplyFeelPunch(Camera);
}

void UVeyrCameraBoom::ApplyFeelPunch(UCameraComponent* Camera)
{
    const UWorld* World=GetWorld();
    const AVeyrGameMode* Mode=World?World->GetAuthGameMode<AVeyrGameMode>():nullptr;
    if(!Camera||!Mode||!Mode->FightFeel||!Mode->FightFeel->PunchesAfterBoom(Camera))return;
    const float Punch=Mode->FightFeel->CurrentPunch();
    if(Punch<=0.f)return;
    PunchBaseFov=Camera->FieldOfView;
    Camera->SetFieldOfView(PunchBaseFov*(1.f-Punch));
    PunchedFov=Camera->FieldOfView;
}

FVector UVeyrCameraBoom::SafeArm(const FVector& Origin0,const FVector& Base,float DeltaTime)
{
    // A2 fifth pass: a steady third-person arm. Direction from the player's yaw/pitch only (plus an eased, sticky
    // rise while the knight is in the dragon's footprint); the lens is ALWAYS the swept pull-in result (instant in,
    // eased out). All smoothing happens on the desired arm before the sweep, never after it.
    const float S=DragonScale();
    FVector KB,KT;float KR=0.f;const bool bKnight=KnightCapsule(KB,KT,KR);
    // Near plane plus margin, plus room for the fight-feel bounce that moves the lens off the socket.
    const float Clear=FMath::Max(ProbeSize+10.f,20.f*S)+20.f*S;
    auto Blocked=[&](const FVector& P){return IsPointInsideBareDragon(P,Clear)||IsPointBehindSkin(P,0.f)||NearestSkinCm(P)<Clear;};
    // 1. Pivot inside the body set (the dragon fell on him, he stands in the claws): straight up to the nearest free point.
    FVector Origin=Origin0;
    if(Blocked(Origin))
    {
        ++PivotLiftFrames;
        for(int32 K=1;K<=24;++K){const FVector P=Origin0+FVector::UpVector*15.f*S*K;if(!Blocked(P)){Origin=P;break;}}
    }
    // 2. Footprint assist: the knight close to the skin -> ease (0.5 s) the arm up to a 30 deg down-look (never past
    // 35) and 20 % longer; sticky, released after 1 s clear.
    const bool bNearBody=bKnight&&NearestSkinCm(FMath::Lerp(KB,KT,.5f))<250.f*S;
    if(bNearBody){AssistClearSeconds=0.f;bAssist=true;}
    else if(bAssist&&(AssistClearSeconds+=DeltaTime)>1.f)bAssist=false;
    AssistAlpha=FMath::FInterpConstantTo(AssistAlpha,bAssist?1.f:0.f,DeltaTime,2.f);
    const FRotator Control=GetTargetRotation();
    const float DownLook=-Control.Pitch;
    const float AssistDown=FMath::Min(35.f,FMath::Max(DownLook,FMath::Lerp(DownLook,30.f,AssistAlpha)));
    AssistRisePitch=FMath::Max(0.f,AssistDown-DownLook);
    FVector Dir=Base-Origin0;const float BaseLength=static_cast<float>(Dir.Size());
    FRotator ArmRot=Dir.Rotation();ArmRot.Pitch=FMath::Min(ArmRot.Pitch+AssistRisePitch,70.f);
    const float Length=BaseLength*(1.f+.2f*AssistAlpha);
    // 3. Sweep from the pivot: the first blocked step (or a wing crossed) ends the free arm.
    FBox Body(ForceInit);const bool bSurface=EnsureSurface();
    if(bSurface){Body=SurfaceBounds;if(WingBounds.IsValid)Body+=WingBounds;Body=Body.ExpandBy(Clear+100.f*S);}
    auto Sweep=[&](const FVector& From,const FVector& To)
    {
        const float L=static_cast<float>(FVector::Dist(From,To));
        FBox Arm(ForceInit);Arm+=From;Arm+=To;
        if(L<=1.f||(bSurface&&!Body.Intersect(Arm)))return 1.f;
        const int32 Steps=FMath::Clamp(FMath::CeilToInt(L/FMath::Max(8.f,6.f*S)),1,160);
        FVector Previous=From;
        for(int32 I=1;I<=Steps;++I)
        {
            const FVector P=FMath::Lerp(From,To,static_cast<float>(I)/Steps);
            if(Blocked(P)||CrossesWing(Previous,P))return static_cast<float>(I-1)/Steps;
            Previous=P;
        }
        return 1.f;
    };
    FVector End=Origin+ArmRot.Vector()*Length;
    float Target=Sweep(Origin,End);
    // No room behind him (the lens would sit in his shoulder): the whole arm moves straight up, through free
    // space, to the first height that leaves the lens clear of his body.
    if(bKnight&&Target*Length<KR+80.f)
        for(int32 K=1;K<=16;++K)
        {
            const FVector Up=Origin+FVector::UpVector*15.f*S*K;
            if(Blocked(Up))break;
            const FVector E=Up+ArmRot.Vector()*Length;const float T=Sweep(Up,E);
            if(T*Length>=KR+80.f||K==16){Origin=Up;End=E;Target=T;++PivotLiftFrames;break;}
        }
    // Instant in, eased out (any fraction up to Target lies on the swept free segment).
    if(Target<SafeFraction){if(SafeFraction>=.999f&&Target<.999f)++PullInEvents;SafeFraction=Target;}
    else SafeFraction=FMath::Min(Target,FMath::FInterpTo(SafeFraction,Target,DeltaTime,ReleaseRate));
    const FVector Pulled=FMath::Lerp(Origin,End,SafeFraction);
    // 4. Short arm (under KR+140): the lens rises over his head (only through free space) and the lens widens.
    const float Reach=SafeFraction*Length;
    const float Short=bKnight?FMath::Clamp(1.f-(Reach-KR)/140.f,0.f,1.f):0.f;
    float WantLift=0.f;
    if(Short>0.f&&bKnight)WantLift=FMath::Max(0.f,static_cast<float>(KT.Z+KR+60.f*S-Pulled.Z))*Short+ShortArmLiftCm*S*Short*.5f;
    SafeLift=WantLift>SafeLift?WantLift:FMath::FInterpTo(SafeLift,WantLift,DeltaTime,3.f); // up at once (out of his head), down eased
    float Lift=SafeLift;
    if(Lift>1.f)
    {
        const int32 Steps=FMath::Clamp(FMath::CeilToInt(Lift/FMath::Max(8.f,6.f*S)),1,64);
        for(int32 I=1;I<=Steps;++I)if(Blocked(Pulled+FVector::UpVector*Lift*I/Steps)){Lift*=static_cast<float>(I-1)/Steps;break;}
    }
    SafeLens=FMath::FInterpTo(SafeLens,ShortArmLensDeg*Short,DeltaTime,5.f);
    const FVector Result=Pulled+FVector::UpVector*Lift;
    if(IsPointInsideBareDragon(Result,10.f))++ResultInsideFrames;
    FinishView(Result,Base,DeltaTime,SafeLens);
    return Result;
}

void UVeyrCameraBoom::FinishView(const FVector& Out,const FVector& Base,float DeltaTime,float ExtraLensDeg)
{
    // The view follows the player's rotation, tilted down by the footprint rise (same pivot: the knight keeps
    // his place on screen); framing corrections ease; the turn rate is capped; never steeper than 38 deg down.
    FRotator Steady=GetTargetRotation();Steady.Pitch=FMath::Max(Steady.Pitch-AssistRisePitch,-35.f);
    const FQuat ArmView=Steady.Quaternion();
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
    ViewCorrection=bViewCorrectionValid?FQuat::Slerp(ViewCorrection,Correction,FMath::Clamp(DeltaTime*6.f,0.f,1.f)):Correction;
    ViewCorrection.Normalize();bViewCorrectionValid=true;
    FramedView=ViewCorrection*ArmView;
    FRotator Clamped=FramedView.Rotator();if(Clamped.Pitch<-38.f){Clamped.Pitch=-38.f;FramedView=Clamped.Quaternion();}
    if(bSafeLastView)
    {
        const float MaxTurn=FMath::Max(.5f,MaxTurnRateDegPerSec*FMath::Max(DeltaTime,1.f/120.f));
        const float Turn=FMath::RadiansToDegrees(static_cast<float>(FramedView.AngularDistance(SafeLastView)));
        if(Turn>MaxTurn){FramedView=FQuat::Slerp(SafeLastView,FramedView,MaxTurn/Turn);FramedView.Normalize();++ClampedTurns;}
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
    if(A.SampleGapCm<0.f&&EnsureSurface())
    {
        // Density of the live skin samples the sweep keeps clear of: the largest nearest-neighbour gap.
        float Gap=0.f;TArray<TPair<double,int32>,TInlineAllocator<13>> Near;
        const TArray<FVector> Points=SurfacePositions;
        for(int32 I=0;I<Points.Num();I+=1){NearestSkin(Points[I],2,Near,false);if(Near.Num()==2)Gap=FMath::Max(Gap,static_cast<float>(FMath::Sqrt(Near[1].Key)));}
        A.SampleGapCm=Gap;
    }
    auto Note=[](TArray<float>& L,float T){if(L.Num()<60&&(L.IsEmpty()||T-L.Last()>.5f))L.Add(T);};
    FVector KB,KT;float KR=0.f;const bool bKnight=KnightCapsule(KB,KT,KR);
    // Fourth pass: the drawn skin itself (every LOD0 triangle, skinned this frame), never the proxy or the hull.
    FVeyrDragonTrueSkin& True=FVeyrDragonTrueSkin::Get();A.TrueSkinSource=True.Source;
    AVeyrDragon* AuditDragon=Dragon.Get();
    const bool bTrue=AuditDragon&&AuditDragon->bUsingCustomuseVisual&&True.Skin(AuditDragon->ImportedPresentation);
    bool bCapsule=false,bHull=false,bBehind=false,bNear=false,bInside=false;bool bVolumeHere=false;float NearHere=1e6f;float StepCm=-1.f;float ViewPx=-1.f,SteerPx=-1.f;
    if(bTrue)
    {
        ++A.TrueSkinFrames;AuditOtherFrame+=RigFrame!=GFrameCounter;AuditOtherSkinFrame+=RigSkinFrame!=True.SkinFrame();
        const float NearCm=True.NearestDistance(Camera,200.f);A.MinSkinCm=FMath::Min(A.MinSkinCm,NearCm);
        const bool bVolume=True.InsideVolume(Camera);bVolumeHere=bVolume;NearHere=NearCm;
        // The near plane (10 cm) reaches its corners about 17 cm from the eye at the widest lens: skin that close is cut open.
        bNear=NearCm<17.f;A.InsideVolume+=bVolume;A.NearClip+=bNear;
        bInside=bVolume||bNear;
        if(bInside)
        {
            A.InsideHidden+=bKnightHiddenByCamera;A.InsideOverhead+=OverheadAlpha>.01f;
            A.InsideLensOffsetMaxCm=FMath::Max(A.InsideLensOffsetMaxCm,static_cast<float>(FVector::Dist(Camera,LastRigLens)));
            A.InsideNearMinCm=FMath::Min(A.InsideNearMinCm,NearCm);
            if(Proxy.IsValid()){A.InsideInRigProxy+=Proxy.Contains(Camera,0.f);A.InsideRigProxyMinCm=FMath::Min(A.InsideRigProxyMinCm,Proxy.Distance(Camera,0.f));}
        }
    }
    else
    {
        if(Shapes.IsEmpty())RefreshShapes();
        bCapsule=IsPointInsideSolidCapsule(Camera,0.f);bHull=IsPointInsideBareDragon(Camera,10.f);bBehind=IsPointBehindSkin(Camera,10.f);
        bNear=NearestSkinCm(Camera)<10.f;bInside=bCapsule||bHull||bBehind;A.LegacyInside+=bInside;
    }
    A.InsideCapsule+=bCapsule;A.InsideHull+=bHull;A.BehindSkin+=bBehind;A.NearSkin+=bNear;A.InsideAny+=bInside;
    A.InsideRun=bInside?A.InsideRun+1:0;A.LongestInsideRun=FMath::Max(A.LongestInsideRun,A.InsideRun);
    if(bInside)Note(A.InsideSeconds,Seconds);
    const float Pitch=View.Rotator().Pitch;A.MinPitchDeg=FMath::Min(A.MinPitchDeg,Pitch);
    if(Pitch<-40.f){++A.SteepFrames;Note(A.SteepSeconds,Seconds);}
    // Pops: camera movement and turn per frame (a knight blink is counted apart).
    const FVector KnightAt=bKnight?KB:Camera;
    // Steering: the view without the camera's own fight-feel shake/kick rotation (applied on the lens, not the arm).
    FQuat Steer=View;
    for(USceneComponent* Child:GetAttachChildren())if(const UCameraComponent* C=Cast<UCameraComponent>(Child)){Steer=View*C->GetRelativeRotation().Quaternion().Inverse();break;}
    // A gap in the audited frames is a cut away from the knight's camera (intro, restart): not a pop.
    if(A.bHasLast&&Dt>.25f){++A.Cuts;A.bHasLast=false;A.SettleFrames=0;A.FadeLastCutAt=Seconds;}
    // The first frames after the intro hands over (or after a cut) are the cut itself, not a pop.
    if(++A.SettleFrames<=3)A.bHasLast=false;
    if(A.bHasLast)
    {
        const float Move=static_cast<float>(FVector::Dist(Camera,A.LastCamera));StepCm=Move;
        const float Turn=FMath::RadiansToDegrees(static_cast<float>(View.AngularDistance(A.LastView)));
        const bool bTeleport=FVector::Dist(KnightAt,A.LastKnight)>150.f;
        A.KnightTeleports+=bTeleport;
        if(Dt>0.f&&A.TurnRates.Num()<20000)A.TurnRates.Add(Turn/Dt);
        if(Dt>0.f&&A.SteerRates.Num()<20000)A.SteerRates.Add(FMath::RadiansToDegrees(static_cast<float>(Steer.AngularDistance(A.LastSteer)))/Dt);
        // Third pass: frame-to-frame view motion in pixels at 640 px width - where last frame's centre point 15 m ahead
        // lands now (rotation plus parallax), with (view) and without (steer) the fight-feel kick.
        {
            const float Asp=ViewAspect();float U,V;
            const FVector PV=A.LastCamera+A.LastView.GetForwardVector()*1500.f,PS=A.LastCamera+A.LastSteer.GetForwardVector()*1500.f;
            ViewPx=ProjectToView(PV,Camera,View,HorizontalFovDeg,Asp,U,V)?FMath::Sqrt(FMath::Square(U*320.f)+FMath::Square(V*320.f/Asp)):640.f;
            SteerPx=ProjectToView(PS,Camera,Steer,HorizontalFovDeg,Asp,U,V)?FMath::Sqrt(FMath::Square(U*320.f)+FMath::Square(V*320.f/Asp)):640.f;
        }
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
    A.LastCamera=Camera;A.LastView=View;A.LastKnight=KnightAt;A.LastSteer=Steer;A.bHasLast=true;
    if(!bKnight)return;
    const float Surface=FMath::PointDistToSegment(Camera,KB,KT)-KR;
    A.MinCameraToKnightCm=FMath::Min(A.MinCameraToKnightCm,Surface);A.InsideKnight+=Surface<10.f;
    const bool bRuleHidden=bKnightHiddenByCamera;
    A.HiddenByRule+=bRuleHidden;if(bRuleHidden)Note(A.RuleHiddenSeconds,Seconds);
    if(bRuleHidden)
    {
        if(A.RuleRunStart<0.f||Seconds-A.RuleRunLast>.1f){A.RuleRunStart=Seconds;++A.RuleHiddenRuns;A.bRuleRunCounted=false;}
        A.RuleRunLast=Seconds;const float Run=Seconds-A.RuleRunStart;
        if(Run>A.LongestRuleHiddenSeconds){A.LongestRuleHiddenSeconds=Run;A.LongestRuleHiddenAt=A.RuleRunStart;}
        if(Run>1.f&&!A.bRuleRunCounted){++A.RuleRunsOver1s;A.bRuleRunCounted=true;}
    }
    if(Surface<10.f&&!bRuleHidden){++A.InsideKnightVisible;Note(A.KnightInsideSeconds,Seconds);}
    A.KnightWhole+=KnightWholeInView(Camera,View,HorizontalFovDeg);
    // How much of the knight the player sees: 7 points on his body, each inside the central 80 % of the frame
    // with no dragon skin (shapes, interior, wings) between it and the lens.
    const float Aspect=ViewAspect();const FVector Right=View.GetRightVector();
    const FVector Foot=KB-FVector::UpVector*KR,Head=KT+FVector::UpVector*KR*.6f;
    const FVector Points[7]={FMath::Lerp(Foot,Head,.05f),FMath::Lerp(Foot,Head,.3f),FMath::Lerp(Foot,Head,.55f),FMath::Lerp(Foot,Head,.8f),Head,
        FMath::Lerp(Foot,Head,.5f)+Right*KR*.8f,FMath::Lerp(Foot,Head,.5f)-Right*KR*.8f};
    int32 Seen=0,Centre=0,InFrame=0;
    for(const FVector& P:Points)
    {
        float U,V;
        if(!ProjectToView(P,Camera,View,HorizontalFovDeg,Aspect,U,V))continue;
        if(FMath::Abs(U)<=1.f&&FMath::Abs(V)<=1.f)++InFrame;
        if(FMath::Abs(U)>.8f||FMath::Abs(V)>.8f)continue;
        ++Centre;
        if(bRuleHidden)continue;
        if(bTrue?!True.SegmentBlocked(Camera,P):SightClear(Camera,P,true))++Seen;
    }
    A.OutsideCentre+=Centre<4;A.KnightInFrame+=InFrame>=4&&!bRuleHidden;
    if(!bRuleHidden){++A.VisibleFrames;A.KnightInFrameVisible+=InFrame>=4;}
    if(!bRuleHidden&&InFrame<4){Note(A.OutFrameSeconds,Seconds);A.OutFrameNear+=Surface<150.f;A.OutFramePitchUp+=View.Rotator().Pitch>5.0;A.OutFrameOverhead+=OverheadAlpha>.5f;A.OutFrameDistanceSum+=Surface;}
    const bool bHalf=Seen*2>=7;A.HalfVisible+=bHalf;
    const bool bHidden=Seen==0;A.FullyHidden+=bHidden;
    A.HiddenRunSeconds=bHidden?A.HiddenRunSeconds+Dt:0.f;A.LongestHiddenSeconds=FMath::Max(A.LongestHiddenSeconds,A.HiddenRunSeconds);
    if(!bHalf)Note(A.HiddenSeconds,Seconds);
    // Fight scope: dragon alive (the victory replay keeps auditing through the terminal pose and the restart check).
    if(AuditDragon&&!AuditDragon->IsDead())
    {
        ++A.FightFrames;A.FightRuleHidden+=bRuleHidden;A.FightHalf+=bHalf;A.FightInside+=bInside;
        if(!bRuleHidden){++A.FightVisible;A.FightInFrameVisible+=InFrame>=4;}
        A.FightHiddenRun=bHidden?A.FightHiddenRun+Dt:0.f;A.FightLongestHidden=FMath::Max(A.FightLongestHidden,A.FightHiddenRun);
        if(bRuleHidden)A.FightLongestRule=FMath::Max(A.FightLongestRule,Seconds-A.RuleRunStart);
        // Fifth pass (fade rig): the lens may be inside the body; the materials must clip every back face then.
        if(UsesFadeRig()&&AuditDragon->bCameraFadeMaterials)
        {
            ++A.FadeFrames;
            const bool bApplied=AuditDragon->CameraFadeFrame==GFrameCounter;A.FadeApplied+=bApplied;
            A.FadeLensInside+=bVolumeHere;if(bVolumeHere)Note(A.FadeInsideSeconds,Seconds);
            A.FadeInteriorDrawable+=bVolumeHere&&!(bApplied&&AuditDragon->bCameraFadeBackDiscardApplied);
            A.FadeNearClipNoFade+=NearHere<17.f&&!bApplied;
            const bool bSight=bApplied&&AuditDragon->CameraFadeSightApplied>=.5f;A.FadeSightActive+=bSight;
            int32 Clear=0;for(const FVector& P:Points)Clear+=bTrue?!True.SegmentBlocked(Camera,P):SightClear(Camera,P,true);
            const bool bReadable=Clear>=4||bSight;A.FadeKnightReadable+=bReadable;if(!bReadable)Note(A.FadeUnreadableSeconds,Seconds);
            A.FadeKnightInFrame+=InFrame>=4;
            float UF,VF,UH,VH;
            if(ProjectToView(Foot,Camera,View,HorizontalFovDeg,Aspect,UF,VF)&&ProjectToView(KT+FVector::UpVector*KR,Camera,View,HorizontalFovDeg,Aspect,UH,VH))
            {
                const float Height=FMath::Abs(VH-VF)*.5f;A.FadeKnightMaxHeight=FMath::Max(A.FadeKnightMaxHeight,Height);
                if(Height>.45f){++A.FadeKnightTall;Note(A.FadeTallSeconds,Seconds);}
            }
            if(const AVeyrKnight* K=Cast<AVeyrKnight>(GetOwner());K&&K->bLockedOn)
            {
                ++A.FadeLocked;float UL,VL;
                A.FadeLockInFrame+=ProjectToView(FadeLockChest(),Camera,View,HorizontalFovDeg,Aspect,UL,VL)&&FMath::Abs(UL)<=1.f&&FMath::Abs(VL)<=1.f;
            }
            const float SteerPitch=Steer.Rotator().Pitch;A.FadePitchInBand+=SteerPitch>=-FadeDownDeg-.5f&&SteerPitch<=FadeUpDeg+.5f;
            if(StepCm>=0.f&&FadeArenaPullFrame!=GFrameCounter&&A.FadeLensSteps.Num()<40000)A.FadeLensSteps.Add(StepCm);
            if(StepCm>=FadeCutCm)++A.FadeCuts;
            else if(StepCm>40.f&&FadeArenaPullFrame!=GFrameCounter){++A.FadeJumps;Note(A.FadeJumpSeconds,Seconds);}
            // The dragon in frame: head or torso (chest, neck base, pelvis), not only his feet.
            {
                auto In=[&](const FVector& P){float U,V;return ProjectToView(P,Camera,View,HorizontalFovDeg,Aspect,U,V)&&FMath::Abs(U)<=1.f&&FMath::Abs(V)<=1.f;};
                const bool bHead=In(AuditDragon->GetHeadLocation());
                FVector Chest,NeckBase,Pelvis;bool bTorso=false;
                if(AuditDragon->GetTorsoLocations(Chest,NeckBase,Pelvis))
                {
                    // Bones and the belly underneath them (the body's measured half-depth ~2 m at the shipped size).
                    const FVector Down=-FVector::UpVector*180.f*DragonScale();
                    bTorso=In(Chest)||In(NeckBase)||In(Pelvis)||In((Chest+Pelvis)*.5)||In(Chest+Down)||In(Pelvis+Down)||In((Chest+Pelvis)*.5+Down);
                }
                A.FadeDragonHeadVisible+=bHead;A.FadeDragonVisible+=bHead||bTorso;
                if(!bHead&&!bTorso)Note(A.FadeDragonOutSeconds,Seconds);
                // Third pass: the chest bone itself, and head AND chest together.
                FVector C2,N2,P2;const bool bChest=AuditDragon->GetTorsoLocations(C2,N2,P2)&&In(C2);
                A.FadeDragonChestVisible+=bChest;A.FadeDragonHeadChest+=bHead&&bChest;if(!(bHead&&bChest))Note(A.FadeHeadChestOutSeconds,Seconds);
            }
            // Third pass: safe area (body inside the central 80 % of width, feet above the bottom 22 %) and the HUD dials
            // (bottom-left x<13 %, y>72 %; bottom-right x>82 %, y>76 %), from feet, middle and head.
            {
                float U0,V0,U1,V1,U2,V2;
                const bool bP=ProjectToView(Foot,Camera,View,HorizontalFovDeg,Aspect,U0,V0)&&ProjectToView(FMath::Lerp(Foot,Head,.5f),Camera,View,HorizontalFovDeg,Aspect,U1,V1)&&ProjectToView(Head,Camera,View,HorizontalFovDeg,Aspect,U2,V2);
                if(bP)
                {
                    A.FadeKnightSafe+=FMath::Abs(U0)<=.8f&&FMath::Abs(U1)<=.8f&&FMath::Abs(U2)<=.8f&&V0>=-.56f;
                    auto Dial=[](float U,float V){return (U<-.74f&&V<-.44f)||(U>.64f&&V<-.52f);};
                    const bool bDial=Dial(U0,V0)||Dial(U1,V1)||Dial(U2,V2);A.FadeKnightUnderDial+=bDial;if(bDial)Note(A.FadeDialSeconds,Seconds);
                }
            }
            // Third pass: unfaded dragon surface nearer than the knight, share of the frame (rig's 6x4 rays this frame).
            if(RigFrame==GFrameCounter)
            {
                A.FadeCoverMax=FMath::Max(A.FadeCoverMax,CoverUnfadedShare);if(A.FadeCoverShares.Num()<40000)A.FadeCoverShares.Add(CoverUnfadedShare);
                if(CoverUnfadedShare>.25f){++A.FadeCoverOver25;Note(A.FadeCoverSeconds,Seconds);}
            }
            // Third pass: view motion (px at 640 wide) and what moved it.
            {
                const AVeyrKnight* LK=Cast<AVeyrKnight>(GetOwner());const bool bLockNow=LK&&LK->bLockedOn;
                if(bLockNow!=A.bFadeLastLocked){A.FadeLockChangedAt=Seconds;A.bFadeLastLocked=bLockNow;}
                if(ViewPx>=0.f)
                {
                    if(A.FadeViewPx.Num()<40000){A.FadeViewPx.Add(ViewPx);A.FadeSteerPx.Add(SteerPx);}
                    A.FadeViewOver20+=ViewPx>20.f;A.FadeSteerOver20+=SteerPx>20.f;
                    if(ViewPx>20.f&&A.FadeLurchDetail.Num()<7*200)
                        A.FadeLurchDetail.Append({Seconds,ViewPx,SteerPx,StepCm,Seconds-A.FadeLockChangedAt,Seconds-A.FadeLastCutAt,static_cast<float>(FadeStepLimitedFrames)});
                }
            }
            }
        }
    }
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
    Times(TEXT("insideSeconds"),A.InsideSeconds);Times(TEXT("hiddenSeconds"),A.HiddenSeconds);Times(TEXT("jumpSeconds"),A.JumpSeconds);Times(TEXT("steepSeconds"),A.SteepSeconds);Times(TEXT("jumpDetail_t_move_knightMove_turn_dt_inside_fromPivot"),A.JumpDetail);
    {
        TArray<float> R=A.TurnRates;R.Sort();
        auto Q=[&](float F){return R.IsEmpty()?0.f:R[FMath::Clamp(FMath::FloorToInt(F*(R.Num()-1)),0,R.Num()-1)];};
        int32 Over=0;for(float X:R)Over+=X>240.f;
        TArray<float> SR=A.SteerRates;SR.Sort();int32 SOver=0;for(float X:SR)SOver+=X>240.f;
        N(TEXT("steerRateP99DegPerSec"),SR.IsEmpty()?0.f:SR[FMath::Clamp(FMath::FloorToInt(.99f*(SR.Num()-1)),0,SR.Num()-1)]);N(TEXT("steerRateMaxDegPerSec"),SR.IsEmpty()?0.f:SR.Last());N(TEXT("steerRateOver240Frames"),SOver);
        N(TEXT("turnRateP50DegPerSec"),Q(.5f));N(TEXT("turnRateP99DegPerSec"),Q(.99f));N(TEXT("turnRateMaxDegPerSec"),Q(1.f));N(TEXT("turnRateOver240Frames"),Over);
        N(TEXT("knightInFrameShare"),A.Frames?static_cast<double>(A.KnightInFrame)/A.Frames:0.0);
        N(TEXT("maxDownLookDeg"),-A.MinPitchDeg);N(TEXT("resultInsideFrames"),ResultInsideFrames);N(TEXT("skinSamples"),SurfacePositions.Num());N(TEXT("skinSampleMaxGapCm"),A.SampleGapCm);
    }N(TEXT("viewCuts"),A.Cuts);
    // Fourth pass fields: inside = inside the drawn skin's volume or skin within 17 cm of the eye (true skin).
    O->SetStringField(TEXT("trueSkin"),A.TrueSkinSource);N(TEXT("trueSkinFrames"),A.TrueSkinFrames);
    N(TEXT("insideVolumeFrames"),A.InsideVolume);N(TEXT("skinWithin17cmFrames"),A.NearClip);N(TEXT("legacyShapeInsideFrames"),A.LegacyInside);
    N(TEXT("minSkinDistanceCm"),A.MinSkinCm<1e30f?A.MinSkinCm:-1.0);
    N(TEXT("hiddenByCameraRuleFrames"),A.HiddenByRule);N(TEXT("hiddenByCameraRuleShare"),A.Frames?static_cast<double>(A.HiddenByRule)/A.Frames:0.0);
    N(TEXT("insideKnightVisibleFrames"),A.InsideKnightVisible);
    N(TEXT("knightInFrameShareOfVisibleFrames"),A.VisibleFrames?static_cast<double>(A.KnightInFrameVisible)/A.VisibleFrames:0.0);
    Times(TEXT("ruleHiddenSeconds"),A.RuleHiddenSeconds);Times(TEXT("outOfFrameSeconds"),A.OutFrameSeconds);N(TEXT("ruleHiddenRuns"),A.RuleHiddenRuns);N(TEXT("fightFrames"),A.FightFrames);N(TEXT("fightInsideDragonFrames"),A.FightInside);N(TEXT("fightRuleHiddenShare"),A.FightFrames?double(A.FightRuleHidden)/A.FightFrames:0.0);N(TEXT("fightKnightInFrameShareOfVisible"),A.FightVisible?double(A.FightInFrameVisible)/A.FightVisible:0.0);N(TEXT("fightHalfVisibleShare"),A.FightFrames?double(A.FightHalf)/A.FightFrames:0.0);N(TEXT("fightLongestHiddenSeconds"),A.FightLongestHidden);N(TEXT("fightLongestRuleHiddenSeconds"),A.FightLongestRule);N(TEXT("ruleHiddenRunsOver1s"),A.RuleRunsOver1s);N(TEXT("longestRuleHiddenSeconds"),A.LongestRuleHiddenSeconds);N(TEXT("longestRuleHiddenAtSeconds"),A.LongestRuleHiddenAt);N(TEXT("insideWhileHiddenFrames"),A.InsideHidden);N(TEXT("insideWhileOverheadFrames"),A.InsideOverhead);N(TEXT("insideLensInRigProxyFrames"),A.InsideInRigProxy);
    N(TEXT("insideLensOffsetFromRigMaxCm"),A.InsideLensOffsetMaxCm);N(TEXT("insideRigProxyMinDistanceCm"),A.InsideRigProxyMinCm<1e30f?A.InsideRigProxyMinCm:-1.0);N(TEXT("insideNearestSkinMinCm"),A.InsideNearMinCm<1e30f?A.InsideNearMinCm:-1.0);
    {const int32 Out=A.VisibleFrames-A.KnightInFrameVisible;N(TEXT("outOfFrameVisibleFrames"),Out);N(TEXT("outOfFrameNearFrames"),A.OutFrameNear);N(TEXT("outOfFramePitchUpFrames"),A.OutFramePitchUp);N(TEXT("outOfFrameOverheadFrames"),A.OutFrameOverhead);N(TEXT("outOfFrameMeanDistanceCm"),Out?A.OutFrameDistanceSum/Out:0.0);}Times(TEXT("knightInsideVisibleSeconds"),A.KnightInsideSeconds);
    {
        // Fifth pass (fade rig), fight scope: interior drawable = lens inside the drawn volume while the back-face clip
        // was not applied this frame (must be 0); readable = 4 of 7 knight points clear of skin, or the sight fade on.
        O->SetBoolField(TEXT("fadeRig"),UsesFadeRig());const double F=A.FadeFrames?double(A.FadeFrames):1.0;
        N(TEXT("fadeFrames"),A.FadeFrames);N(TEXT("fadeAppliedShare"),A.FadeApplied/F);N(TEXT("fadeLensInsideFrames"),A.FadeLensInside);
        N(TEXT("fadeInteriorDrawableFrames"),A.FadeInteriorDrawable);N(TEXT("fadeNearClipUnfadedFrames"),A.FadeNearClipNoFade);
        N(TEXT("fadeKnightReadableShare"),A.FadeKnightReadable/F);N(TEXT("fadeKnightInFrameShare"),A.FadeKnightInFrame/F);
        N(TEXT("fadeKnightTallFrames"),A.FadeKnightTall);N(TEXT("fadeKnightMaxScreenHeight"),A.FadeKnightMaxHeight);
        N(TEXT("fadeLockedFrames"),A.FadeLocked);N(TEXT("fadeLockTargetInFrameShare"),A.FadeLocked?double(A.FadeLockInFrame)/A.FadeLocked:0.0);
        N(TEXT("fadePitchInBandShare"),A.FadePitchInBand/F);N(TEXT("fadeSightActiveShare"),A.FadeSightActive/F);
        TArray<float> St=A.FadeLensSteps;St.Sort();
        N(TEXT("fadeLensStepP999Cm"),St.IsEmpty()?0.f:St[FMath::Clamp(FMath::FloorToInt(.999f*(St.Num()-1)),0,St.Num()-1)]);N(TEXT("fadeLensStepMaxCm"),St.IsEmpty()?0.f:St.Last());
        N(TEXT("fadeRigSightFrames"),FadeSightFrames);N(TEXT("fadeRigInsideFrames"),FadeInsideFrames);N(TEXT("fadeRigShortenedFrames"),FadeShortFrames);
        Times(TEXT("fadeInsideSeconds"),A.FadeInsideSeconds);Times(TEXT("fadeUnreadableSeconds"),A.FadeUnreadableSeconds);Times(TEXT("fadeTallSeconds"),A.FadeTallSeconds);
        N(TEXT("fadeDragonInFrameShare"),A.FadeFrames?double(A.FadeDragonVisible)/A.FadeFrames:0.0);N(TEXT("fadeDragonHeadInFrameShare"),A.FadeFrames?double(A.FadeDragonHeadVisible)/A.FadeFrames:0.0);
        N(TEXT("fadeJumpsOver40Cm"),A.FadeJumps);N(TEXT("fadeCuts"),A.FadeCuts);N(TEXT("fadeStepLimitedFrames"),FadeStepLimitedFrames);N(TEXT("fadeDragonLiftFrames"),FadeDragonLiftFrames);
        N(TEXT("fadeDragonChestInFrameShare"),A.FadeDragonChestVisible/F);N(TEXT("fadeDragonHeadAndChestInFrameShare"),A.FadeDragonHeadChest/F);
        N(TEXT("fadeKnightSafeAreaShare"),A.FadeKnightSafe/F);N(TEXT("fadeKnightUnderDialFrames"),A.FadeKnightUnderDial);Times(TEXT("fadeKnightUnderDialSeconds"),A.FadeDialSeconds);
        Times(TEXT("fadeHeadChestOutSeconds"),A.FadeHeadChestOutSeconds);
        N(TEXT("fadeNearCoverMaxShare"),A.FadeCoverMax);N(TEXT("fadeNearCoverOver25Frames"),A.FadeCoverOver25);Times(TEXT("fadeNearCoverOver25Seconds"),A.FadeCoverSeconds);
        {TArray<float> Cv=A.FadeCoverShares;Cv.Sort();N(TEXT("fadeNearCoverP99Share"),Cv.IsEmpty()?0.f:Cv[FMath::Clamp(FMath::FloorToInt(.99f*(Cv.Num()-1)),0,Cv.Num()-1)]);}
        {
            TArray<float> Vp=A.FadeViewPx,Sp=A.FadeSteerPx;Vp.Sort();Sp.Sort();
            auto Q=[](const TArray<float>& X,float P){return X.IsEmpty()?0.f:X[FMath::Clamp(FMath::FloorToInt(P*(X.Num()-1)),0,X.Num()-1)];};
            N(TEXT("viewPxP50"),Q(Vp,.5f));N(TEXT("viewPxP99"),Q(Vp,.99f));N(TEXT("viewPxP999"),Q(Vp,.999f));N(TEXT("viewPxMax"),Vp.IsEmpty()?0.f:Vp.Last());N(TEXT("viewPxOver20Frames"),A.FadeViewOver20);
            N(TEXT("steerPxP999"),Q(Sp,.999f));N(TEXT("steerPxMax"),Sp.IsEmpty()?0.f:Sp.Last());N(TEXT("steerPxOver20Frames"),A.FadeSteerOver20);
            TArray<TSharedPtr<FJsonValue>> L;for(float X:A.FadeLurchDetail)L.Add(MakeShared<FJsonValueNumber>(FMath::RoundToFloat(X*100.f)/100.f));
            O->SetArrayField(TEXT("lurch_t_viewPx_steerPx_stepCm_sinceLockSwitch_sinceCut_stepLimitedTotal"),L);
        }
        N(TEXT("framePullFrames"),FramePullFrames);N(TEXT("headChestUnmetFrames"),HeadChestUnmetFrames);N(TEXT("coverageFadeFrames"),CoverageFadeFrames);N(TEXT("safeAreaYawFrames"),SafeAreaYawFrames);
        O->SetBoolField(TEXT("headChestFraming"),bHeadChestFraming);O->SetBoolField(TEXT("coverageFade"),bCoverageFade);O->SetBoolField(TEXT("knightSafeArea"),bKnightSafeArea);
        Times(TEXT("fadeDragonOutSeconds"),A.FadeDragonOutSeconds);Times(TEXT("fadeJumpSeconds"),A.FadeJumpSeconds);
    }
    O->SetBoolField(TEXT("legacyCameraPlacement"),bLegacyPlacement);
    N(TEXT("rigOverheadFrames"),RigOverheadFrames);N(TEXT("rigHiddenFrames"),RigHiddenFrames);N(TEXT("rigPivotLiftFrames"),RigPivotLiftFrames);
    N(TEXT("rigMeanMs"),RigCalls?RigSeconds*1000.0/RigCalls:0.0);N(TEXT("rigMaxMs"),RigMaxSeconds*1000.0);N(TEXT("rigProxyBoxes"),Proxy.BoxCount());N(TEXT("rigWorldHits"),RigWorldHits);N(TEXT("rigSkinSweeps"),RigSkinSweeps);N(TEXT("rigSkinStepsMean"),RigSkinSweeps?double(RigSkinSteps)/RigSkinSweeps:0.0);N(TEXT("rigSkinSweepMsPerSweep"),RigSkinSweeps?RigSkinSweepSeconds*1000.0/RigSkinSweeps:0.0);N(TEXT("auditRigOtherFrame"),AuditOtherFrame);N(TEXT("auditRigOtherSkinFrame"),AuditOtherSkinFrame);N(TEXT("rigStaleProxyFrames"),RigStaleProxyFrames);N(TEXT("rigLowOverheadFrames"),RigLowFrames);N(TEXT("rigHideUnderBodyFrames"),RigHideUnderBodyFrames);{TArray<TSharedPtr<FJsonValue>> L;for(const FString& X:RigWorldHitNames)L.Add(MakeShared<FJsonValueString>(X));O->SetArrayField(TEXT("rigWorldHitActors"),L);}N(TEXT("trueSkinMs"),FVeyrDragonTrueSkin::Get().SkinSeconds*1000.0);O->SetBoolField(TEXT("rigProxyTight"),bProxyTight);
    O->SetStringField(TEXT("rigProxy"),Proxy.Diagnostic);N(TEXT("rigProxyMarginCm"),RigProxyMarginCm*DragonScale());N(TEXT("rigLensRadiusCm"),RigLensRadiusCm);
    O->SetStringField(TEXT("scope"),TEXT("every replay frame whose view target is the knight, whole replay (held by the replay, survives restart); seconds are replay seconds; visible = 7 knight points inside the central 80 % with no dragon skin (shapes, interior, wings) in between; jumps = >150 cm or >12 deg in one frame, knight blinks excluded"));
    return O;
}

void UVeyrCameraBoom::ProveProxy(FVeyrProxyProof& P,float Seconds)
{
    FindDragon();
    AVeyrDragon* D=Dragon.Get();
    UVeyrSkeletalPresentation* Pres=D&&D->bUsingCustomuseVisual?D->ImportedPresentation.Get():nullptr;
    if(!Pres)return;
    FVeyrDragonTrueSkin& True=FVeyrDragonTrueSkin::Get();
    if(!True.Skin(Pres))return;
    const double Start=FPlatformTime::Seconds();
    if(!ProofProxy.Update(Pres,RigProxyMarginCm*DragonScale()))return;
    static const bool bBoneOnly=FParse::Param(FCommandLine::Get(),TEXT("VeyrRigBoneBoxes"));
    if(!bBoneOnly)True.Tighten(ProofProxy);
    const double Spent=FPlatformTime::Seconds()-Start;P.ProxySeconds+=Spent;P.ProxyMaxSeconds=FMath::Max(P.ProxyMaxSeconds,Spent);
    float With=0.f,Bare=0.f;int32 Tested=0,Outside=0;FVector Worst;
    True.Prove(ProofProxy,With,Bare,Tested,Outside,Worst);
    ++P.Frames;P.Vertices+=Tested;P.OutsideVertices+=Outside;P.FramesWithOutside+=Outside>0;P.MarginCm=ProofProxy.Margin();P.MaxBoxes=FMath::Max(P.MaxBoxes,ProofProxy.BoxCount());
    const FString Clip=Pres->CurrentClip.ToString();
    float& ClipBare=P.BareByClip.FindOrAdd(Clip);ClipBare=FMath::Max(ClipBare,Bare);
    ++P.FramesByMesh.FindOrAdd(Pres->GetSkeletalMeshAsset()?Pres->GetSkeletalMeshAsset()->GetName():FString());
    if(Bare>P.WorstBareCm){P.WorstBareCm=Bare;}
    if(With>P.WorstWithMarginCm||(P.WorstAtSeconds<0.f&&Bare>=P.WorstBareCm))
    {P.WorstWithMarginCm=FMath::Max(P.WorstWithMarginCm,With);P.WorstAtSeconds=Seconds;P.WorstClip=Clip;P.WorstMesh=Pres->GetSkeletalMeshAsset()?Pres->GetSkeletalMeshAsset()->GetName():FString();P.WorstPoint=Worst;}
}

TSharedPtr<FJsonObject> UVeyrCameraBoom::ProofJson(const FVeyrProxyProof& P) const
{
    TSharedPtr<FJsonObject> O=MakeShared<FJsonObject>();
    auto N=[&](const TCHAR* K,double V){O->SetNumberField(K,V);};
    N(TEXT("frames"),P.Frames);N(TEXT("verticesTested"),static_cast<double>(P.Vertices));N(TEXT("outsideVertices"),static_cast<double>(P.OutsideVertices));
    N(TEXT("framesWithOutside"),P.FramesWithOutside);N(TEXT("worstOutsideWithMarginCm"),P.WorstWithMarginCm);
    N(TEXT("marginNeededCm"),P.WorstBareCm);N(TEXT("marginCm"),P.MarginCm);N(TEXT("proxyBoxes"),P.MaxBoxes);
    N(TEXT("proxyUpdateMeanMs"),P.Frames?P.ProxySeconds*1000.0/P.Frames:0.0);N(TEXT("proxyUpdateMaxMs"),P.ProxyMaxSeconds*1000.0);
    N(TEXT("worstAtSeconds"),P.WorstAtSeconds);O->SetStringField(TEXT("worstClip"),P.WorstClip);O->SetStringField(TEXT("worstMesh"),P.WorstMesh);
    O->SetStringField(TEXT("trueSkin"),FVeyrDragonTrueSkin::Get().Source);
    TSharedPtr<FJsonObject> Clips=MakeShared<FJsonObject>();for(const auto& C:P.BareByClip)Clips->SetNumberField(C.Key,C.Value);O->SetObjectField(TEXT("marginNeededByClipCm"),Clips);
    TSharedPtr<FJsonObject> Meshes=MakeShared<FJsonObject>();for(const auto& C:P.FramesByMesh)Meshes->SetNumberField(C.Key,C.Value);O->SetObjectField(TEXT("framesByMesh"),Meshes);
    O->SetStringField(TEXT("scope"),TEXT("every LOD0 vertex of the current dragon mesh, skinned with the engine's linear blend each audited frame, tested against the proxy boxes grown by the margin; marginNeeded = worst distance outside the bare boxes"));
    return O;
}
