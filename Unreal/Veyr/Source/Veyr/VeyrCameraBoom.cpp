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
    if(TActorIterator<AVeyrDragon> It(GetWorld());It)Dragon=*It; // first dragon (same as the loop-and-break; -Werror clean)
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
        FShape Shape;Shape.A=Center-Axis*Half;Shape.B=Center+Axis*Half;Shape.Radius=Radius+BodyClearanceCm*S;Shape.Name=Capsule->GetFName();
        Shapes.Add(Shape);
    }
    UVeyrSkeletalPresentation* Presentation=D->ImportedPresentation;
    if(Presentation&&D->bUsingCustomuseVisual&&Presentation->bPoseEvaluated)
    {
        for(const TCHAR* Side:{TEXT("NegZ"),TEXT("PosZ")})
        {
            FVector P[5];bool bOk=true;
            const TCHAR* Parts[5]={TEXT("Root"),TEXT("Elbow"),TEXT("Membrane"),TEXT("Wrist"),TEXT("Tip")};
            for(int32 I=0;I<5;++I)
            {
                const int32 Bone=Presentation->GetBoneIndex(FName(*FString::Printf(TEXT("VeyrWing%s%s"),Side,Parts[I])));
                if(Bone==INDEX_NONE){bOk=false;break;}
                P[I]=Presentation->GetBoneTransform(Bone).GetLocation();
            }
            if(!bOk)continue;
            const float Arm=30.f*S+WingClearanceCm*S,Sheet=WingClearanceCm*S;
            const FName Name(*FString::Printf(TEXT("VeyrWing%s"),Side));
            auto Segment=[&](const FVector& A,const FVector& B,float R){FShape X;X.A=A;X.B=B;X.Radius=R;X.Name=Name;Shapes.Add(X);};
            auto Triangle=[&](const FVector& A,const FVector& B,const FVector& C){FShape X;X.A=A;X.B=B;X.C=C;X.Radius=Sheet;X.bTriangle=true;X.Name=Name;Shapes.Add(X);};
            Segment(P[0],P[1],Arm);Segment(P[3],P[4],Arm);
            Triangle(P[0],P[1],P[4]);Triangle(P[0],P[3],P[2]);Triangle(P[0],P[2],P[4]);
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

float UVeyrCameraBoom::FirstContact(const FVector& Origin,const FVector& End,float Radius) const
{
    // Shapes that already contain the origin cannot be avoided by pulling in; the lift handles those.
    constexpr int32 Steps=32;
    float Best=1.f;
    for(const FShape& Shape:Shapes)
    {
        if(ShapeDistance(Shape,Origin)<Radius)continue;
        float Previous=0.f;
        for(int32 I=1;I<=Steps;++I)
        {
            const float T=static_cast<float>(I)/Steps;
            if(T>=Best)break;
            if(ShapeDistance(Shape,FMath::Lerp(Origin,End,T))<Radius)
            {
                float Lo=Previous,Hi=T; // refine: Lo outside, Hi inside
                for(int32 K=0;K<8;++K){const float M=(Lo+Hi)*.5f;(ShapeDistance(Shape,FMath::Lerp(Origin,End,M))<Radius?Hi:Lo)=M;}
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
    for(float Extra=0.f;IsPointInsideDragon(Pulled+FVector::UpVector*WantLift,Probe)&&Extra<LiftMaxCm*S*2.f;Extra+=25.f*S)
        WantLift+=25.f*S;
    LiftCm=WantLift>LiftCm?WantLift:FMath::FInterpTo(LiftCm,WantLift,DeltaTime,LiftReleaseRate);
    FVector Result=Pulled+FVector::UpVector*LiftCm;
    if(LiftCm>1.f&&GetWorld())
    {
        // The lift must not push the camera into the arena (ceilings, arches).
        FHitResult Hit;FCollisionQueryParams Params(SCENE_QUERY_STAT(VeyrBoomLift),false,GetOwner());
        if(GetWorld()->SweepSingleByChannel(Hit,Pulled,Result,FQuat::Identity,ProbeChannel,FCollisionShape::MakeSphere(ProbeSize),Params))
            Result=Hit.Location;
    }
    // Evidence: inside the bare body (clearance removed), with a 10 cm near-plane margin.
    if(IsPointInsideDragon(Result,10.f-FMath::Min(BodyClearanceCm,WingClearanceCm)*S))++ResultInsideFrames;
    return Result;
}
