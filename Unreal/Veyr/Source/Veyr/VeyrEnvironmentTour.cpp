#include "VeyrReplay.h"
#include "VeyrArena.h"
#include "VeyrKnight.h"
#include "VeyrDragon.h"
#include "VeyrGameMode.h"
#include "Camera/CameraActor.h"
#include "Components/CapsuleComponent.h"
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
            if(!GetWorld()->LineTraceSingleByChannel(Hit,P+FVector(0,0,300),P-FVector(0,0,500),ECC_Visibility,Query)||Hit.ImpactPoint.Z<-.5f||Hit.ImpactPoint.Z>20.f)++EnvironmentFloorFailures;
            if(I%6==0&&GetWorld()->SweepSingleByChannel(Hit,P,FVector(-P.X,-P.Y,P.Z),FQuat::Identity,ECC_Pawn,Capsule,Query))++EnvironmentSweepFailures;
        }
        Event(TEXT("architecture_clearance_probed"),false);
    }
    struct FShot{const TCHAR* Name;FVector Camera,Focus;};
    static const FShot Shots[]={
        {TEXT("court_player_height"),FVector(-3300,-1500,350),FVector(2500,800,1200)},
        {TEXT("court_overview"),FVector(-2000,-2000,4500),FVector(600,0,100)},
        {TEXT("southwest_mural"),FVector(-1200,-3000,900),FVector(-1200,-4740,900)},
        {TEXT("southeast_mural"),FVector(1200,-3000,900),FVector(1200,-4740,900)},
        {TEXT("northwest_mural"),FVector(-1200,3000,900),FVector(-1200,4740,900)},
        {TEXT("northeast_mural"),FVector(1200,3000,900),FVector(1200,4740,900)},
        {TEXT("military_gate"),FVector(2700,0,450),FVector(5300,0,1800)},
        {TEXT("court_reverse"),FVector(-1000,1500,550),FVector(-5100,-700,1200)}};
    const int32 Index=FMath::FloorToInt(Elapsed/4.f);
    if(Index>=UE_ARRAY_COUNT(Shots))
    {
        const AVeyrGameMode* Mode=GetWorld()->GetAuthGameMode<AVeyrGameMode>();const AVeyrArena* Arena=Mode?Mode->Arena.Get():nullptr;
        const bool Assets=Arena&&(!Arena->bFortressCandidate||(Arena->bFortressAssetsReady&&Arena->FortressMuralCount==4));
        Finish(Assets&&EnvironmentSweepFailures==0&&EnvironmentFloorFailures==0,
            FString::Printf(TEXT("Architectural inspection: 8 camera views, %d clearance failures, %d floor failures; no combat victory claim"),EnvironmentSweepFailures,EnvironmentFloorFailures));return;
    }
    const FShot& Shot=Shots[Index];
    if(EnvironmentShot!=Index){EnvironmentShot=Index;Event(Shot.Name,false);}
    const float U=FMath::Clamp(FMath::Fmod(Elapsed,4.f)/4.f,0.f,1.f);
    const FVector Position=Shot.Camera+FVector(100.f*(U-.5f),0,0);
    EnvironmentCamera->SetActorLocationAndRotation(Position,(Shot.Focus-Position).Rotation());
}
