#include "VeyrCameraBoom.h"
#include "VeyrDragon.h"
#include "VeyrSkeletalPresentation.h"
#include "Components/CapsuleComponent.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "Misc/CommandLine.h"
#include "Camera/CameraComponent.h"
#include "VeyrGameMode.h"
#include "VeyrFightFeel.h"
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
    // Consensus of the 12 nearest body samples, so a single sample with a bent normal (spines, horns,
    // the tail tip) cannot decide it, and only within 200 cm x scale of the skin: the body is nowhere thicker.
    constexpr int32 K=12;
    TArray<TPair<double,int32>,TInlineAllocator<K+1>> Nearest;
    for(int32 I=0;I<SurfacePositions.Num();++I)
    {
        const double Distance=FVector::DistSquared(SurfacePositions[I],Point);
        if(Nearest.Num()==K&&Distance>=Nearest.Last().Key)continue;
        int32 At=Nearest.Num();
        while(At>0&&Nearest[At-1].Key>Distance)--At;
        Nearest.Insert(TPair<double,int32>(Distance,I),At);
        if(Nearest.Num()>K)Nearest.Pop(EAllowShrinking::No);
    }
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
    // The knight seen without any see-through: clear sight lines to his chest and head, stopping short of him.
    const FVector Chest=FMath::Lerp(KBottom,KTop,.6f),Head=KTop;
    for(const FVector& T:{Chest,Head})
    {
        const FVector End=T+(P-T).GetSafeNormal()*(KRadius+25.f);
        if(!SegmentClearOfBareDragon(P,End,4.f))return false;
    }
    return true;
}

namespace
{
    struct FVeyrFramingCandidate { float YawDeg; int32 Height; float Length; float Cost; };
    /** Placements in the owner's order of preference: the arm as is, lowered and level under the belly, slid
     * sideways round the body, the pivot raised, then shorter arms (closer than preferred; the lens widens). */
    const TArray<FVeyrFramingCandidate>& FramingCandidates()
    {
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
    const FQuat ArmView=GetTargetRotation().Quaternion();
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
            else if(C.Height==2)P.Z+=200.f*S;             // pivot raised
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
        const TArray<FVeyrFramingCandidate>& List=FramingCandidates();
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
            for(int32 I=0;I<List.Num()&&!bFound&&Evaluated<96;++I,++Evaluated)
            {
                const float Need=List[I].Length<.79f?KnightHardMinCm:Preferred;
                if(Try(I,Need)){bFound=true;StickyCandidate=I;}
            }
        }
        if(!bFound)
        {
            // Nothing clean: keep out of the knight and the dragon first, sight lines second.
            ++FramingFallbackFrames;
            const FVector Up=Foot+FVector::UpVector*FMath::Max(600.f*S,(KT.Z-Foot.Z)+400.f)-F0.GetSafeNormal2D()*KnightHardMinCm;
            Target=!IsPointInsideBareDragon(Proposed,10.f)&&FMath::PointDistToSegment(Proposed,KB,KT)>=KR+60.f?Proposed:Up;
            StickyCandidate=INDEX_NONE;
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
    // Still taller than the frame: open the lens, up to MaxFovBoostDeg.
    double AzB,ElB,AzT,ElT;Angles(Bottom,R,AzB,ElB);Angles(Top,R,AzT,ElT);
    const double Span=(ElT-ElB)*.5;
    if(Span>LimitV)
    {
        const double NeedTanV=FMath::Tan(FMath::DegreesToRadians(Span))/M;
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
