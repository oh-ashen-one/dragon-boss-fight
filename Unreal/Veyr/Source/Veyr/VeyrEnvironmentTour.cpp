#include "VeyrReplay.h"
#include "VeyrArenaTour.h"
#include "VeyrArena.h"
#include "VeyrKnight.h"
#include "VeyrDragon.h"
#include "VeyrGameMode.h"
#include "Camera/CameraActor.h"
#include "Camera/CameraComponent.h"
#include "Components/CapsuleComponent.h"
#include "Materials/MaterialInterface.h"
#include "Engine/World.h"

void AVeyrReplay::TickEnvironmentTour()
{
    if(!EnvironmentCamera){Finish(false,TEXT("Architectural inspection camera missing"));return;}
    if(!bEnvironmentProbed)
    {
        bEnvironmentProbed=true;
        FCollisionQueryParams Query(SCENE_QUERY_STAT(VeyrEnvironmentClearance),false,Knight.Get());Query.AddIgnoredActor(Dragon.Get());
        const float Half=Knight->GetCapsuleComponent()->GetScaledCapsuleHalfHeight();
        const FCollisionShape Capsule=FCollisionShape::MakeCapsule(Knight->GetCapsuleComponent()->GetScaledCapsuleRadius(),Half);
        // Read-only sweeps around the clear fighting ring and through its centre.
        // Actual collision and floor hits are tested; no pawn is teleported.
        for(int32 I=0;I<48;++I)
        {
            const float A=I*2.f*PI/48.f,B=(I+1)*2.f*PI/48.f;
            const FVector P(FMath::Cos(A)*3500.f,FMath::Sin(A)*3500.f,Half+10.f);
            const FVector Q(FMath::Cos(B)*3500.f,FMath::Sin(B)*3500.f,Half+10.f);
            FHitResult Hit;
            if(GetWorld()->SweepSingleByChannel(Hit,P,Q,FQuat::Identity,ECC_Pawn,Capsule,Query))++EnvironmentSweepFailures;
            const bool FloorHit=GetWorld()->LineTraceSingleByChannel(Hit,P+FVector(0,0,300),P-FVector(0,0,500),ECC_Visibility,Query);
            if(!FloorHit||Hit.ImpactPoint.Z<-.5f||Hit.ImpactPoint.Z>20.f)++EnvironmentFloorFailures;
            if(I%12==0&&FloorHit&&Hit.GetComponent())
            {
                UMaterialInterface* Surface=Hit.GetComponent()->GetMaterial(0);
                EnvironmentFloorProbeSummary+=FString::Printf(TEXT("%d:%s/%s z=%.3f material=%s; "),I,
                    Hit.GetActor()?*Hit.GetActor()->GetName():TEXT("none"),*Hit.GetComponent()->GetName(),Hit.ImpactPoint.Z,
                    Surface?*Surface->GetPathName():TEXT("none"));
            }
            if(I%6==0&&GetWorld()->SweepSingleByChannel(Hit,P,FVector(-P.X,-P.Y,P.Z),FQuat::Identity,ECC_Pawn,Capsule,Query))++EnvironmentSweepFailures;
        }
        Event(TEXT("architecture_clearance_probed"),false);
    }
    const int32 Index=FMath::FloorToInt(Elapsed/VeyrArenaTour::ShotSeconds());
    if(Index>=VeyrArenaTour::ShotCount())
    {
        const AVeyrGameMode* Mode=GetWorld()->GetAuthGameMode<AVeyrGameMode>();const AVeyrArena* Arena=Mode?Mode->Arena.Get():nullptr;
        const bool Assets=Arena&&(!Arena->bFortressCandidate||(Arena->bFortressAssetsReady&&Arena->FortressMuralCount==4));
        Finish(Assets&&EnvironmentSweepFailures==0&&EnvironmentFloorFailures==0,
            FString::Printf(TEXT("Architectural inspection: 8 camera views, %d clearance failures, %d floor failures; no combat victory claim"),EnvironmentSweepFailures,EnvironmentFloorFailures));return;
    }
    if(EnvironmentShot!=Index){EnvironmentShot=Index;Event(VeyrArenaTour::ShotName(Index),false);}
    VeyrArenaTour::Apply(EnvironmentCamera,Elapsed);
}
