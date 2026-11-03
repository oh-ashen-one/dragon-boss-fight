#include "VeyrFightFeel.h"
#include "VeyrGameMode.h"
#include "VeyrKnight.h"
#include "VeyrDragon.h"
#include "VeyrVisualDefinition.h"
#include "VeyrSkeletalPresentation.h"
#include "VeyrReplay.h"
#include "GameFramework/PlayerController.h"
#include "Camera/CameraComponent.h"
#include "Components/SceneComponent.h"
#include "Components/PointLightComponent.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Kismet/GameplayStatics.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "UObject/ConstructorHelpers.h"

AVeyrFightFeel::AVeyrFightFeel()
{
    PrimaryActorTick.bCanEverTick=true;
    PrimaryActorTick.bTickEvenWhenPaused=true;
    SetRootComponent(CreateDefaultSubobject<USceneComponent>(TEXT("FightFeelRoot")));
    HitFlash=CreateDefaultSubobject<UPointLightComponent>(TEXT("ContactHitFlash"));
    HitFlash->SetupAttachment(GetRootComponent());HitFlash->SetCastShadows(false);
    HitFlash->SetIntensityUnits(ELightUnits::Lumens);HitFlash->SetIntensity(0.f);
    HitFlash->SetLightColor(FLinearColor(1.f,.78f,.48f));HitFlash->SetVisibility(false);
    WeaponTrail=CreateDefaultSubobject<UInstancedStaticMeshComponent>(TEXT("WeaponTrail"));
    WeaponTrail->SetupAttachment(GetRootComponent());WeaponTrail->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    WeaponTrail->SetGenerateOverlapEvents(false);WeaponTrail->SetCanEverAffectNavigation(false);
    WeaponTrail->SetCastShadow(false);WeaponTrail->SetNumCustomDataFloats(4);WeaponTrail->SetVisibility(false);
    // Reuse the project's existing textured ember and Epic's installed plane;
    // no reference-pack assets or new raw store assets are included.
    static ConstructorHelpers::FObjectFinderOptional<UStaticMesh> Plane(TEXT("/Engine/BasicShapes/Plane.Plane"));
    static ConstructorHelpers::FObjectFinderOptional<UMaterialInterface> Material(TEXT("/Game/Veyr/FX/v3/M_VeyrBreathEmber.M_VeyrBreathEmber"));
    WeaponTrail->SetStaticMesh(Plane.Get());WeaponTrail->SetMaterial(0,Material.Get());
    HitMarker=CreateDefaultSubobject<UInstancedStaticMeshComponent>(TEXT("SurfaceHitMarker"));
    HitMarker->SetupAttachment(GetRootComponent());HitMarker->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    HitMarker->SetGenerateOverlapEvents(false);HitMarker->SetCanEverAffectNavigation(false);
    HitMarker->SetCastShadow(false);HitMarker->SetNumCustomDataFloats(4);HitMarker->SetVisibility(false);
    HitMarker->SetStaticMesh(Plane.Get());HitMarker->SetMaterial(0,Material.Get());
}

void AVeyrFightFeel::BeginPlay()
{
    Super::BeginPlay();
    bDisabled=FParse::Param(FCommandLine::Get(),TEXT("VeyrFightFeelOff"));
    bLegacy=FParse::Param(FCommandLine::Get(),TEXT("VeyrFightFeelLegacy"));
    bMarkerOnlyReview=FParse::Param(FCommandLine::Get(),TEXT("VeyrFightFeelMarkerOnly"));
    // Channel 1 already belongs to the knight, sword, cup and dragon.
    // Reuse it without changing receivers or the dragon-only rim channel 2.
    HitFlash->SetLightingChannels(bLegacy,!bLegacy,false);
    HitFlash->SetIndirectLightingIntensity(bLegacy?1.f:0.f);
    LastRealTime=GetWorld()->GetRealTimeSeconds();
    if(UMaterialInterface* Parent=WeaponTrail->GetMaterial(0))
    {
        UMaterialInstanceDynamic* Material=UMaterialInstanceDynamic::Create(Parent,this);
        Material->SetVectorParameterValue(TEXT("Tint"),FLinearColor(.55f,.68f,.82f));
        Material->SetScalarParameterValue(TEXT("Brightness"),.85f);WeaponTrail->SetMaterial(0,Material);
    }
    for(int32 I=0;I<24;++I)WeaponTrail->AddInstance(FTransform(FQuat::Identity,FVector::ZeroVector,FVector::ZeroVector));
    if(UMaterialInterface* Parent=HitMarker->GetMaterial(0))
    {
        auto* Material=UMaterialInstanceDynamic::Create(Parent,this);
        Material->SetVectorParameterValue(TEXT("Tint"),FLinearColor(1.f,.86f,.58f));
        Material->SetScalarParameterValue(TEXT("Brightness"),4.f);HitMarker->SetMaterial(0,Material);
    }
    HitMarker->AddInstance(FTransform(FQuat::Identity,FVector::ZeroVector,FVector::ZeroVector));
    UE_LOG(LogTemp,Display,TEXT("VEYR_FIGHT_FEEL enabled=%d revision=%d"),!bDisabled,GetRevision());
}

void AVeyrFightFeel::RestoreTime()
{
    // Do not overwrite an independent review tool that changed the clock.
    if(bOwnsDilation&&FMath::IsNearlyEqual(UGameplayStatics::GetGlobalTimeDilation(this),.05f,.001f))
        UGameplayStatics::SetGlobalTimeDilation(this,SavedDilation);
    bOwnsDilation=false;StopRemaining=0.f;
}

void AVeyrFightFeel::RefreshSettings()
{
    const auto* Mode=GetWorld()->GetAuthGameMode<AVeyrGameMode>();
    if(!Mode)return;
    if(bDisabled||!Mode->bUserHitStop)RestoreTime();
    if(bDisabled||!Mode->bUserCameraShake){ShakeAmplitude=0.f;ShakeAge=ShakeLife;}
    if(bDisabled||!Mode->bUserHitFlash){FlashAge=1.f;HitFlash->SetIntensity(0.f);HitFlash->SetVisibility(false);HitMarker->SetVisibility(false);}
}

void AVeyrFightFeel::Tick(float DeltaSeconds)
{
    Super::Tick(DeltaSeconds);
    const double Now=GetWorld()->GetRealTimeSeconds();
    const float RealDelta=FMath::Max(0.f,static_cast<float>(Now-LastRealTime));LastRealTime=Now;
    RefreshSettings();
    if(UGameplayStatics::IsGamePaused(this)){RestoreTime();return;}
    if(bOwnsDilation)
    {
        StopRemaining-=RealDelta;
        if(StopRemaining<=0.f)RestoreTime();
    }
    ShakeAge+=RealDelta;FlashAge+=RealDelta;FlinchAge+=DeltaSeconds;
    const bool ShowFlash=!bDisabled&&FlashAge<.18f;
    const bool LightVisible=ShowFlash&&(bLegacy||!bMarkerOnlyReview);
    HitFlash->SetVisibility(LightVisible);
    HitFlash->SetIntensity(LightVisible?(500.f+900.f*FlashWeight)*FMath::Exp(-FlashAge/.045f):0.f);
    HitMarker->SetVisibility(ShowFlash&&!bLegacy);
    if(ShowFlash&&!bLegacy)
    {
        FVector Position=FlashWorldPoint;
        if(FlashMesh.IsValid()&&!FlashBone.IsNone())
        {
            const int32 Bone=FlashMesh->GetBoneIndex(FlashBone);
            if(Bone!=INDEX_NONE)Position=FlashMesh->GetBoneTransform(Bone).TransformPosition(FlashLocalPoint);
        }
        const auto* Mode=GetWorld()->GetAuthGameMode<AVeyrGameMode>();
        if(Mode&&Mode->Knight&&Mode->Knight->CombatCamera)
        {
            const FVector TowardCamera=(Mode->Knight->CombatCamera->GetComponentLocation()-Position).GetSafeNormal();
            const float Size=FMath::Lerp(14.f,26.f,FlashWeight)*(1.f+FlashAge*2.f);
            // A depth-tested glint at the accepted blade contact, following
            // the struck bone. It cannot light the floor like a point light.
            HitMarker->UpdateInstanceTransform(0,FTransform(FRotationMatrix::MakeFromZ(TowardCamera).ToQuat(),
                Position+TowardCamera*8.f,FVector(Size/100.f,Size/100.f,1.f)),true,false,true);
            HitMarker->SetCustomDataValue(0,0,.9f*FMath::Exp(-FlashAge/.045f),false);
            HitMarker->SetCustomDataValue(0,1,.3f,false);HitMarker->SetCustomDataValue(0,2,FlashAge/.18f,false);
            HitMarker->SetCustomDataValue(0,3,.8f,false);HitMarker->MarkRenderStateDirty();
        }
    }
}

void AVeyrFightFeel::RequestHitStop(float Seconds)
{
    const auto* Mode=GetWorld()->GetAuthGameMode<AVeyrGameMode>();
    if(bDisabled||!Mode||!Mode->bUserHitStop||UGameplayStatics::IsGamePaused(this))return;
    if(!bOwnsDilation)
    {
        SavedDilation=UGameplayStatics::GetGlobalTimeDilation(this);
        // Review slow motion owns its clock; do not stack feedback onto it.
        if(!FMath::IsNearlyEqual(SavedDilation,1.f,.001f))return;
        bOwnsDilation=true;UGameplayStatics::SetGlobalTimeDilation(this,.05f);
    }
    LastHitStopSeconds=FMath::Clamp(Seconds,.05f,.12f);
    StopRemaining=FMath::Max(StopRemaining,LastHitStopSeconds);++HitStopEvents;
    UE_LOG(LogTemp,Display,TEXT("VEYR_HIT_STOP seconds=%.3f"),LastHitStopSeconds);
}

void AVeyrFightFeel::Impact(const FVector& Position,float Weight,FName Kind)
{
    const auto* Mode=GetWorld()->GetAuthGameMode<AVeyrGameMode>();
    if(bDisabled||!Mode||!Mode->bUserCameraShake||!Mode->Knight)return;
    FVector Listener=Mode->Knight->CombatCamera?Mode->Knight->CombatCamera->GetComponentLocation():Mode->Knight->GetActorLocation();
    if(Mode->Replay&&Mode->Replay->IsPresentationOnly())
        if(auto* PC=Cast<APlayerController>(Mode->Knight->GetController())){FRotator Rotation;PC->GetPlayerViewPoint(Listener,Rotation);}
    LastShakeDistance=FVector::Distance(Listener,Position);
    const float Falloff=FMath::Square(FMath::Clamp(1.f-LastShakeDistance/5000.f,0.f,1.f));
    const float W=FMath::Clamp(Weight,0.f,1.f);
    const float Amplitude=FMath::Lerp(.25f,1.65f,W)*Falloff;
    const float Remaining=ShakeAmplitude*FMath::Square(FMath::Clamp(1.f-ShakeAge/ShakeLife,0.f,1.f));
    if(Amplitude<=.005f||Amplitude<Remaining)return;
    ShakeAmplitude=Amplitude;ShakeLife=FMath::Lerp(.18f,.5f,W);ShakeAge=0.f;
    LastShakeDegrees=Amplitude;++ShakeEvents;
    UE_LOG(LogTemp,Display,TEXT("VEYR_CAMERA_SHAKE kind=%s weight=%.2f distance=%.1f degrees=%.3f"),*Kind.ToString(),W,LastShakeDistance,Amplitude);
}

void AVeyrFightFeel::ApplyCameraShake(UCameraComponent* Camera)
{
    if(!Camera)return;
    const float A=ShakeAmplitude*FMath::Square(FMath::Clamp(1.f-ShakeAge/ShakeLife,0.f,1.f));
    // Offset the camera socket, never control rotation or player aiming. A
    // deterministic pulse gives comparable replay captures without RNG changes.
    const float T=ShakeAge*2.f*PI;
    Camera->SetRelativeRotation(FRotator(A*FMath::Cos(13.f*T),A*.55f*FMath::Sin(17.f*T),A*.3f*FMath::Sin(11.f*T)));
}

void AVeyrFightFeel::Flash(const FVector& Position,float Weight,USkeletalMeshComponent* Mesh)
{
    const auto* Mode=GetWorld()->GetAuthGameMode<AVeyrGameMode>();
    if(bDisabled||!Mode||!Mode->bUserHitFlash)return;
    FlashAge=0.f;FlashWeight=Weight;HitFlash->SetWorldLocation(Position+FVector(0,0,18));
    FlashWorldPoint=Position;FlashMesh=Mesh;FlashBone=NAME_None;
    if(Mesh)
    {
        FlashBone=Mesh->FindClosestBone(Position);
        const int32 Bone=Mesh->GetBoneIndex(FlashBone);
        if(Bone!=INDEX_NONE)FlashLocalPoint=Mesh->GetBoneTransform(Bone).InverseTransformPosition(Position);
        else FlashBone=NAME_None;
    }
    HitFlash->SetAttenuationRadius(100.f+100.f*Weight);++HitFlashEvents;
}

void AVeyrFightFeel::SwordContact(AVeyrDragon* Boss,bool bHeavy)
{
    if(bDisabled||!Boss)return;
    const float Weight=bHeavy?1.f:.45f;
    Impact(Boss->LastSwordContactWorld,Weight,TEXT("sword"));
    RequestHitStop(bHeavy?.095f:.055f);Flash(Boss->LastSwordContactWorld,Weight,Boss->ImportedPresentation);
    FlinchAge=0.f;FlinchWeight=Weight;
    FlinchSide=FVector::DotProduct(Boss->LastSwordContactWorld-Boss->GetActorLocation(),Boss->GetActorRightVector())>=0.f?1.f:-1.f;
    ++FlinchEvents;
}

void AVeyrFightFeel::PlayerContact(AVeyrKnight* Player,float Damage,bool bBlocked)
{
    if(!Player||bDisabled)return;
    const float Weight=bBlocked?.2f:FMath::Clamp(Damage/40.f,.35f,1.f);
    Impact(Player->GetActorLocation(),Weight,bBlocked?TEXT("guard"):TEXT("player_damage"));
    RequestHitStop(bBlocked?.05f:.07f);Flash(Player->GetActorLocation()+FVector(0,0,35),Weight*.6f,Player->ImportedPresentation);
}

void AVeyrFightFeel::AddBossFlinch(AVeyrDragon* Boss,TMap<FName,FRotator>& Rotations) const
{
    if(bDisabled||!Boss||!Boss->VisualDefinition||Boss->IsDead()||Boss->IsAirborne()||FlinchAge>=.45f)return;
    // Add a small contact correction to the sourced pose. It does not replace
    // the clip or interrupt its windup, active window, recovery or root track.
    const float Snap=FMath::Clamp(FlinchAge/.035f,0.f,1.f);
    const float Spring=Snap*FMath::Exp(-FlinchAge*10.f)*FMath::Cos(FlinchAge*19.f);
    for(const FName Target:{FName(TEXT("head")),FName(TEXT("gaze_neck"))})
    {
        const auto* Bone=Boss->VisualDefinition->BoneTargets.Find(Target);
        if(!Bone||(!Rotations.Contains(Bone->BoneName)&&Rotations.Num()>=4))continue;
        Rotations.FindOrAdd(Bone->BoneName)+=FRotator(-Spring*(2.f+4.f*FlinchWeight),Spring*FlinchSide*2.f,0.f);
    }
}

void AVeyrFightFeel::UpdateWeaponTrail(AVeyrKnight* Player,float GameDelta)
{
    if(!Player||GameDelta<=0.f)return;
    for(auto& Segment:Trail)Segment.Age+=GameDelta;
    Trail.RemoveAll([](const FTrailSegment& S){return S.Age>=.10f;});
    FVector Base=FVector::ZeroVector,Tip=FVector::ZeroVector;
    const bool Attack=Player->IsWeaponTrailActive();
    const bool Pose=Player->GetWeaponSweep(Base,Tip);
    if(!bDisabled&&Attack&&Pose&&bHaveBlade)
    {
        const float Distance=FVector::Distance(Tip,PreviousBladeTip);
        const float Speed=Distance/FMath::Max(GameDelta,.001f);
        // Suppress discontinuities at clip/mesh changes and low-speed recovery.
        if(Speed>650.f&&Distance>1.f&&Distance<150.f&&Trail.Num()<24)
        {Trail.Add({PreviousBladeTip,Tip,0.f,FMath::Clamp((Speed-400.f)/1800.f,.15f,.65f)});++TrailSamples;}
    }
    bHaveBlade=Pose&&Attack;PreviousBladeTip=Tip;
    if(bDisabled)Trail.Reset();
    VisibleTrailSegments=Trail.Num();WeaponTrail->SetVisibility(VisibleTrailSegments>0);
    const FVector Camera=Player->CombatCamera->GetComponentLocation();
    for(int32 I=0;I<24;++I)
    {
        FTransform Transform(FQuat::Identity,FVector::ZeroVector,FVector::ZeroVector);float Opacity=0.f;
        if(Trail.IsValidIndex(I))
        {
            const auto& S=Trail[I];const FVector Center=(S.Start+S.End)*.5f,Axis=S.End-S.Start;
            const FVector Facing=(Camera-Center).GetSafeNormal();
            Transform=FTransform(FRotationMatrix::MakeFromXZ(Axis.GetSafeNormal(),Facing).ToQuat(),Center,FVector(Axis.Size()/100.f,.035f,1.f));
            Opacity=S.Strength*FMath::Square(1.f-S.Age/.10f);
        }
        WeaponTrail->UpdateInstanceTransform(I,Transform,true,false,true);
        WeaponTrail->SetCustomDataValue(I,0,Opacity,false);WeaponTrail->SetCustomDataValue(I,1,.3f,false);
        WeaponTrail->SetCustomDataValue(I,2,0.f,false);WeaponTrail->SetCustomDataValue(I,3,.4f,false);
    }
    WeaponTrail->MarkRenderStateDirty();
}

void AVeyrFightFeel::EndPlay(const EEndPlayReason::Type Reason)
{
    RestoreTime();Super::EndPlay(Reason);
}
