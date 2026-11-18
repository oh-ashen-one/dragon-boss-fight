#include "VeyrCameraBoom.h"
#include "VeyrDragon.h"
#include "VeyrSkeletalPresentation.h"
#include "Components/CapsuleComponent.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "Misc/CommandLine.h"

UVeyrCameraBoom::UVeyrCameraBoom()
{
    PrimaryComponentTick.TickGroup=TG_PostPhysics;
}

void UVeyrCameraBoom::BeginPlay()
{
    Super::BeginPlay();
    bLegacyBoom=FParse::Param(FCommandLine::Get(),TEXT("VeyrLegacyCameraBoom"));
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

bool UVeyrCameraBoom::IsPointBehindSkin(const FVector& Point,float Margin,float* OutDepthCm)
{
    if(OutDepthCm)*OutDepthCm=0.f;
    AVeyrDragon* D=Dragon.Get();
    UVeyrSkeletalPresentation* Presentation=D?D->ImportedPresentation.Get():nullptr;
    if(!Presentation||!D->bUsingCustomuseVisual)return false;
    if(SurfaceFrame!=GFrameCounter)
    {
        SurfaceFrame=GFrameCounter;
        if(!Hull.IsReadyFor(Presentation))Hull.Initialize(Presentation);
        Hull.SkinSurface(Presentation,SurfacePositions,SurfaceNormals);
    }
    int32 Best=INDEX_NONE;double BestDistance=TNumericLimits<double>::Max();
    for(int32 I=0;I<SurfacePositions.Num();++I)
    {const double Distance=FVector::DistSquared(SurfacePositions[I],Point);if(Distance<BestDistance){BestDistance=Distance;Best=I;}}
    if(Best==INDEX_NONE)return false;
    const float Signed=static_cast<float>(FVector::DotProduct(Point-SurfacePositions[Best],SurfaceNormals[Best]));
    if(OutDepthCm)*OutDepthCm=-Signed;
    return Signed<-Margin;
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
    if(bLegacyBoom)return Base;
    FindDragon();
    RefreshShapes();
    if(Shapes.IsEmpty()){BodyFraction=1.f;LiftCm=0.f;return Base;}
    ++BodyFrames;
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
    // Evidence: inside the bare body (clearance removed), with a 10 cm near-plane margin.
    if(IsPointInsideBareDragon(Result,10.f))++ResultInsideFrames;
    return Result;
}
