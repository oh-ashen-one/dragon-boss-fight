#include "VeyrArenaTour.h"
#include "Camera/CameraActor.h"
#include "Camera/CameraComponent.h"
namespace
{
    struct FShot{const TCHAR* Name;FVector Camera,Focus;};
    const FShot Shots[]={
        {TEXT("court_player_height"),FVector(-4000,-2600,500),FVector(1400,2000,1100)},
        {TEXT("court_overview"),FVector(-9000,-11000,10500),FVector(2300,800,1800)},
        {TEXT("southwest_mural"),FVector(-2600,-2800,850),FVector(-3100,-4700,700)},
        {TEXT("southeast_mural"),FVector(2600,-2800,850),FVector(3100,-4700,700)},
        {TEXT("northwest_mural"),FVector(-3600,2800,850),FVector(-3100,4700,700)},
        {TEXT("northeast_mural"),FVector(3600,2800,850),FVector(3100,4700,700)},
        {TEXT("military_gate"),FVector(2700,0,450),FVector(5300,0,1800)},
        {TEXT("court_reverse"),FVector(-1000,1500,550),FVector(-5100,-700,1200)}};
}
int32 VeyrArenaTour::ShotCount(){return UE_ARRAY_COUNT(Shots);}
float VeyrArenaTour::ShotSeconds(){return 4.f;}
float VeyrArenaTour::Duration(){return ShotCount()*ShotSeconds();}
const TCHAR* VeyrArenaTour::ShotName(int32 Index){return Shots[FMath::Clamp(Index,0,ShotCount()-1)].Name;}
int32 VeyrArenaTour::Apply(ACameraActor* Camera,float Seconds)
{
    if(!Camera)return INDEX_NONE;
    const int32 Index=FMath::Clamp(FMath::FloorToInt(Seconds/ShotSeconds()),0,ShotCount()-1);
    const FShot& Shot=Shots[Index];
    const float U=FMath::Clamp((Seconds-Index*ShotSeconds())/ShotSeconds(),0.f,1.f);
    const FVector Position=Shot.Camera+FVector(100.f*(U-.5f),0,0);
    Camera->GetCameraComponent()->FieldOfView=Index==1?75.f:60.f;
    Camera->SetActorLocationAndRotation(Position,(Shot.Focus-Position).Rotation());
    return Index;
}
