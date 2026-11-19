#include "VeyrFightFeel.h"
#include "VeyrGameMode.h"
#include "VeyrKnight.h"
#include "VeyrDragon.h"
#include "VeyrImpactFx.h"
#include "VeyrFeelTuning.h"
#include "VeyrLook.h"
#include "VeyrVisualDefinition.h"
#include "VeyrSkeletalPresentation.h"
#include "VeyrReplay.h"
#include "GameFramework/PlayerController.h"
#include "Camera/CameraComponent.h"
#include "Components/SceneComponent.h"
#include "Components/PointLightComponent.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "Dom/JsonObject.h"
#include "Dom/JsonValue.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Kismet/GameplayStatics.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "ProceduralMeshComponent.h"
#include "UObject/ConstructorHelpers.h"

namespace
{
    // Authored by tools/unreal/create_feel_materials.py; the fallbacks exist in the project already.
    const TCHAR* FlashMaterialPath=TEXT("/Game/Veyr/FX/Feel/M_VeyrHitFlash.M_VeyrHitFlash");
    const TCHAR* TrailMaterialPath=TEXT("/Game/Veyr/FX/Feel/M_VeyrWeaponTrail.M_VeyrWeaponTrail");
    const TCHAR* TintFallbackPath=TEXT("/Game/ArtPass/Materials/M_BlinkAfterimage.M_BlinkAfterimage");

    FVector CatmullRom(const FVector& A,const FVector& B,const FVector& C,const FVector& D,float T)
    {
        const float T2=T*T,T3=T2*T;
        return .5f*((2.f*B)+(-A+C)*T+(2.f*A-5.f*B+4.f*C-D)*T2+(-A+3.f*B-3.f*C+D)*T3);
    }
    FRotator ClampBoneRotation(const FQuat& Q)
    {
        // The proxy accepts 20 degrees per axis and 25 in total; stay inside so a blow never drops the pose.
        FQuat R=Q.GetNormalized();
        const float Angle=FMath::RadiansToDegrees(R.GetAngle());
        if(Angle>24.f)R=FQuat(R.GetRotationAxis(),FMath::DegreesToRadians(24.f));
        FRotator Out=R.Rotator();
        Out.Pitch=FMath::Clamp(Out.Pitch,-19.5f,19.5f);Out.Yaw=FMath::Clamp(Out.Yaw,-19.5f,19.5f);Out.Roll=FMath::Clamp(Out.Roll,-19.5f,19.5f);
        return Out;
    }
}

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
    // B6: the blade ribbon, world space, rebuilt in place every frame (fixed vertex count, no allocation).
    Ribbon=CreateDefaultSubobject<UProceduralMeshComponent>(TEXT("WeaponRibbon"));
    Ribbon->SetupAttachment(GetRootComponent());Ribbon->SetUsingAbsoluteLocation(true);Ribbon->SetUsingAbsoluteRotation(true);
    Ribbon->SetUsingAbsoluteScale(true);Ribbon->SetCollisionEnabled(ECollisionEnabled::NoCollision);Ribbon->SetGenerateOverlapEvents(false);
    Ribbon->SetCanEverAffectNavigation(false);Ribbon->SetCastShadow(false);Ribbon->bUseAsyncCooking=false;Ribbon->SetVisibility(false);
}

void AVeyrFightFeel::BeginPlay()
{
    Super::BeginPlay();
    bDisabled=FParse::Param(FCommandLine::Get(),TEXT("VeyrFightFeelOff"));
    bLegacy=FParse::Param(FCommandLine::Get(),TEXT("VeyrFightFeelLegacy"));
    bMarkerOnlyReview=FParse::Param(FCommandLine::Get(),TEXT("VeyrFightFeelMarkerOnly"));
    // Channel 1 already belongs to the knight, sword, cup and dragon.
    // Reuse it without changing receivers or the dragon-only rim channel 2.
    // Relit court: the dragon leaves channel 1 (the knight's key and rim), so the contact light also uses
    // channel 2 to keep lighting the dragon's skin.
    HitFlash->SetLightingChannels(bLegacy,!bLegacy,!bLegacy&&!VeyrLook::IsLegacy());
    HitFlash->SetIndirectLightingIntensity(bLegacy?1.f:0.f);
    LastRealTime=GetWorld()->GetRealTimeSeconds();
    if(UMaterialInterface* Parent=WeaponTrail->GetMaterial(0))
    {
        UMaterialInstanceDynamic* Material=UMaterialInstanceDynamic::Create(Parent,this);
        Material->SetVectorParameterValue(TEXT("Tint"),FLinearColor(.55f,.68f,.82f));
        Material->SetScalarParameterValue(TEXT("Brightness"),.85f);WeaponTrail->SetMaterial(0,Material);
        VeyrLook::FollowExposureAuto(Material);
    }
    for(int32 I=0;I<24;++I)WeaponTrail->AddInstance(FTransform(FQuat::Identity,FVector::ZeroVector,FVector::ZeroVector));
    if(UMaterialInterface* Parent=HitMarker->GetMaterial(0))
    {
        auto* Material=UMaterialInstanceDynamic::Create(Parent,this);
        Material->SetVectorParameterValue(TEXT("Tint"),FLinearColor(1.f,.86f,.58f));
        Material->SetScalarParameterValue(TEXT("Brightness"),4.f);HitMarker->SetMaterial(0,Material);
        VeyrLook::FollowExposureAuto(Material);
    }
    HitMarker->AddInstance(FTransform(FQuat::Identity,FVector::ZeroVector,FVector::ZeroVector));
    // B5: the flash on the dragon's own mesh. The authored overlay lights a radius around the blow; the
    // project's afterimage tint stands in (whole mesh, faint) when it has not been authored yet.
    if(VeyrFeelSwitches::MeshFlash())
    {
        UMaterialInterface* Parent=LoadObject<UMaterialInterface>(nullptr,FlashMaterialPath,nullptr,LOAD_Quiet|LOAD_NoWarn);
        FlashDiagnostic=Parent?TEXT("M_VeyrHitFlash overlay"):TEXT("M_VeyrHitFlash missing");
        if(!Parent){Parent=LoadObject<UMaterialInterface>(nullptr,TintFallbackPath,nullptr,LOAD_Quiet|LOAD_NoWarn);if(Parent)FlashDiagnostic+=TEXT("; M_BlinkAfterimage tint fallback");}
        if(Parent)MeshFlashMaterial=UMaterialInstanceDynamic::Create(Parent,this);
        else FlashDiagnostic+=TEXT("; no overlay material: point light and glint only");
    }
    // B6: the ribbon's material: vertex-alpha trail, or a flat translucent tint; without either the old trail draws.
    if(VeyrFeelSwitches::RibbonTrail())
    {
        UMaterialInterface* Parent=LoadObject<UMaterialInterface>(nullptr,TrailMaterialPath,nullptr,LOAD_Quiet|LOAD_NoWarn);
        RibbonDiagnostic=Parent?TEXT("M_VeyrWeaponTrail"):TEXT("M_VeyrWeaponTrail missing");
        if(!Parent){Parent=LoadObject<UMaterialInterface>(nullptr,TintFallbackPath,nullptr,LOAD_Quiet|LOAD_NoWarn);if(Parent)RibbonDiagnostic+=TEXT("; M_BlinkAfterimage flat fallback");}
        if(Parent)
        {
            RibbonMaterial=UMaterialInstanceDynamic::Create(Parent,this);
            // The authored trail takes its colour from the vertices; the flat fallback needs the cool tint itself.
            RibbonMaterial->SetVectorParameterValue(TEXT("Tint"),RibbonDiagnostic==TEXT("M_VeyrWeaponTrail")?FLinearColor::White:FLinearColor(.62f,.70f,.82f));
            RibbonMaterial->SetScalarParameterValue(TEXT("Opacity"),RibbonDiagnostic==TEXT("M_VeyrWeaponTrail")?.75f:.32f);
            RibbonMaterial->SetScalarParameterValue(TEXT("Brightness"),1.4f);
            Ribbon->SetMaterial(0,RibbonMaterial);
            VeyrLook::FollowExposureAuto(RibbonMaterial);
            // Three edges per row: clear at the hilt side, full on a band near the tip, clear just past the tip.
            const int32 Verts=RibbonMaxRows*3;
            RibbonVerts.Init(FVector::ZeroVector,Verts);RibbonNormals.Init(FVector::UpVector,Verts);
            RibbonColors.Init(FLinearColor(1.f,1.f,1.f,0.f),Verts);RibbonUVs.Init(FVector2D::ZeroVector,Verts);
            RibbonTangents.Init(FProcMeshTangent(),Verts);
            RibbonTris.Reserve((RibbonMaxRows-1)*6);
            for(int32 R=1;R<RibbonMaxRows;++R)
                for(int32 E=0;E<2;++E){const int32 A=(R-1)*3+E,B=R*3+E;RibbonTris.Append({A,B,A+1,A+1,B,B+1});}
            bRibbonReady=true;
        }
        else RibbonDiagnostic+=TEXT("; no material: legacy trail");
    }
    UE_LOG(LogTemp,Display,TEXT("VEYR_FIGHT_FEEL enabled=%d revision=%d flash=%s ribbon=%s"),!bDisabled,GetRevision(),*FlashDiagnostic,*RibbonDiagnostic);
}

void AVeyrFightFeel::BindDragon()
{
    const auto* Mode=GetWorld()->GetAuthGameMode<AVeyrGameMode>();
    AVeyrDragon* Dragon=Mode?Mode->Dragon.Get():nullptr;
    if(BoundDragon.Get()==Dragon)return;
    if(AVeyrDragon* Old=BoundDragon.Get())Old->OnGroundContact.Remove(ContactHandle);
    BoundDragon=Dragon;ContactHandle.Reset();
    if(Dragon)ContactHandle=Dragon->OnGroundContact.AddUObject(this,&AVeyrFightFeel::ContactImpact);
}

void AVeyrFightFeel::RestoreTime()
{
    // Do not overwrite an independent review tool that changed the clock.
    if(bOwnsDilation&&FMath::IsNearlyEqual(UGameplayStatics::GetGlobalTimeDilation(this),SetDilation,.001f))
        UGameplayStatics::SetGlobalTimeDilation(this,SavedDilation);
    bOwnsDilation=false;StopRemaining=0.f;SlowRemaining=0.f;bPendingSlow=false;
}

void AVeyrFightFeel::RefreshSettings()
{
    const auto* Mode=GetWorld()->GetAuthGameMode<AVeyrGameMode>();
    if(!Mode)return;
    if(bDisabled||!Mode->bUserHitStop)RestoreTime();
    if(bDisabled||!Mode->bUserCameraShake){ShakeAmplitude=0.f;ShakeAge=ShakeLife;KickAge=PunchAge=HurtAge=10.f;}
    if(bDisabled||!Mode->bUserHitFlash){FlashAge=1.f;HitFlash->SetIntensity(0.f);HitFlash->SetVisibility(false);HitMarker->SetVisibility(false);MeshFlashAge=10.f;}
}

void AVeyrFightFeel::Tick(float DeltaSeconds)
{
    Super::Tick(DeltaSeconds);
    const double Now=GetWorld()->GetRealTimeSeconds();
    const float RealDelta=FMath::Max(0.f,static_cast<float>(Now-LastRealTime));LastRealTime=Now;
    RefreshSettings();BindDragon();
    if(UGameplayStatics::IsGamePaused(this)){RestoreTime();return;}
    if(bOwnsDilation)
    {
        if(StopRemaining>0.f)
        {
            StopRemaining-=RealDelta;
            if(StopRemaining<=0.f)
            {
                if(bPendingSlow&&SlowTotal>0.f)
                {
                    // B6: a heavy blow comes back to speed through a short slow motion (the reference's tail).
                    bPendingSlow=false;SlowRemaining=SlowTotal;++SlowTails;
                    SetDilation=VeyrFeelTuning().SlowTailFrom;UGameplayStatics::SetGlobalTimeDilation(this,SetDilation);
                }
                else RestoreTime();
            }
        }
        else if(SlowRemaining>0.f)
        {
            if(!FMath::IsNearlyEqual(UGameplayStatics::GetGlobalTimeDilation(this),SetDilation,.001f)){bOwnsDilation=false;SlowRemaining=0.f;}
            else
            {
                SlowRemaining-=RealDelta;
                const float A=1.f-FMath::Max(0.f,SlowRemaining)/FMath::Max(.001f,SlowTotal);
                SetDilation=FMath::Lerp(VeyrFeelTuning().SlowTailFrom,SavedDilation,A*A);
                UGameplayStatics::SetGlobalTimeDilation(this,SetDilation);
                if(SlowRemaining<=0.f)RestoreTime();
            }
        }
        else RestoreTime();
    }
    ShakeAge+=RealDelta;FlashAge+=RealDelta;FlinchAge+=DeltaSeconds;
    KickAge+=RealDelta;PunchAge+=RealDelta;HurtAge+=RealDelta;
    for(FReact& R:Reacts)R.Age+=DeltaSeconds; // the spring runs on the game clock: it starts as the stop ends
    UpdateMeshFlash(RealDelta);
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
        bOwnsDilation=true;
    }
    // A blow inside a slow tail stops the clock again; its own tail (if any) follows.
    SlowRemaining=0.f;SetDilation=.05f;UGameplayStatics::SetGlobalTimeDilation(this,SetDilation);
    LastHitStopSeconds=FMath::Clamp(Seconds,.05f,.12f);
    StopRemaining=FMath::Max(StopRemaining,LastHitStopSeconds);++HitStopEvents;
    UE_LOG(LogTemp,Display,TEXT("VEYR_HIT_STOP seconds=%.3f"),LastHitStopSeconds);
}

void AVeyrFightFeel::StartShake(float Degrees,float Life,float Bounce,float Frequency,FName Kind,float Distance,bool bVaryPhase)
{
    const float Remaining=ShakeAmplitude*FMath::Square(FMath::Clamp(1.f-ShakeAge/FMath::Max(.01f,ShakeLife),0.f,1.f));
    if(Degrees<=.005f||Degrees<Remaining)return;
    ShakeAmplitude=Degrees;ShakeLife=FMath::Max(.05f,Life);ShakeAge=0.f;ShakeBounce=Bounce;ShakeFrequency=Frequency;
    // Contact shakes get deterministic phases per event (no RNG); the fixed impacts keep the base's zero phase.
    const float K=ShakeEvents*1.618034f;
    ShakePhase=bVaryPhase?FVector(FMath::Frac(K)*6.283f,FMath::Frac(K*1.37f)*6.283f,FMath::Frac(K*1.91f)*6.283f):FVector::ZeroVector;
    LastShakeDegrees=Degrees;LastShakeDistance=Distance;++ShakeEvents;
    UE_LOG(LogTemp,Display,TEXT("VEYR_CAMERA_SHAKE kind=%s distance=%.1f degrees=%.3f life=%.2f bounce=%.1f"),*Kind.ToString(),Distance,Degrees,ShakeLife,Bounce);
}

void AVeyrFightFeel::Impact(const FVector& Position,float Weight,FName Kind)
{
    const auto* Mode=GetWorld()->GetAuthGameMode<AVeyrGameMode>();
    if(bDisabled||!Mode||!Mode->bUserCameraShake||!Mode->Knight)return;
    FVector Listener=Mode->Knight->CombatCamera?Mode->Knight->CombatCamera->GetComponentLocation():Mode->Knight->GetActorLocation();
    if(Mode->Replay&&Mode->Replay->IsPresentationOnly())
        if(auto* PC=Cast<APlayerController>(Mode->Knight->GetController())){FRotator Rotation;PC->GetPlayerViewPoint(Listener,Rotation);}
    const float Distance=FVector::Distance(Listener,Position);
    LastShakeDistance=Distance; // as the base: every impact call, accepted or not
    const float Falloff=FMath::Square(FMath::Clamp(1.f-Distance/5000.f,0.f,1.f));
    const float W=FMath::Clamp(Weight,0.f,1.f);
    StartShake(FMath::Lerp(.25f,1.65f,W)*Falloff,FMath::Lerp(.18f,.5f,W),0.f,1.f,Kind,Distance,false);
}

void AVeyrFightFeel::ContactImpact(AVeyrDragon* Dragon,const FVeyrGroundContact& Contact)
{
    const auto* Mode=GetWorld()->GetAuthGameMode<AVeyrGameMode>();
    if(bDisabled||bLegacy||!Dragon||!VeyrFeelSwitches::WeightShake()||!Mode||!Mode->bUserCameraShake||!Mode->Knight)return;
    FVector Listener=Mode->Knight->CombatCamera?Mode->Knight->CombatCamera->GetComponentLocation():Mode->Knight->GetActorLocation();
    if(auto* PC=Cast<APlayerController>(Mode->Knight->GetController())){FRotator Rotation;PC->GetPlayerViewPoint(Listener,Rotation);}
    const float Distance=FVector::Distance(Listener,Contact.World);
    float Life=0.f,Bounce=0.f;
    const EVeyrFeelClass Class=static_cast<EVeyrFeelClass>(Contact.Class);
    const float Degrees=VeyrFeelTuning().ShakeDegrees(Class,Contact.ScaledSpeedMps,Distance,Dragon->BodyScale,Life,Bounce);
    if(Degrees<=0.f)return;
    const int32 C=static_cast<int32>(Contact.Class);
    ++ContactShakes;++ShakesByClass[C];MaxShakeByClass[C]=FMath::Max(MaxShakeByClass[C],Degrees);
    // Heavier classes shake slower: a ton landing rolls the view, a footfall ticks it.
    static const float Frequency[4]={1.15f,.85f,.65f,.6f};
    static const FName Kinds[4]={TEXT("contact_footfall"),TEXT("contact_stomp"),TEXT("contact_body_fall"),TEXT("contact_landing")};
    StartShake(Degrees,Life,Bounce,Frequency[C],Kinds[C],Distance,true);
}

void AVeyrFightFeel::ApplyCameraShake(UCameraComponent* Camera)
{
    if(!Camera)return;
    if(!bCameraBaseCaptured){CameraBaseLocation=Camera->GetRelativeLocation();bCameraBaseCaptured=true;}
    const float Env=FMath::Square(FMath::Clamp(1.f-ShakeAge/FMath::Max(.01f,ShakeLife),0.f,1.f));
    const float A=ShakeAmplitude*Env;
    // Offset the camera socket, never control rotation or player aiming. A
    // deterministic pulse gives comparable replay captures without RNG changes.
    const float T=ShakeAge*2.f*PI*ShakeFrequency;
    FRotator Rotation(A*FMath::Cos(13.f*T+ShakePhase.X),A*.55f*FMath::Sin(17.f*T+ShakePhase.Y),A*.3f*FMath::Sin(11.f*T+ShakePhase.Z));
    FVector Location=CameraBaseLocation;
    if(ShakeBounce>0.f&&ShakeAge<ShakeLife)
        Location.Z-=ShakeBounce*Env*FMath::Cos(ShakeAge*2.f*PI*4.5f); // the floor drops and rebounds under a heavy fall
    // B6: struck, the view is kicked away from the blow, then the screen flushes and drains.
    const bool bKick=VeyrFeelSwitches::HurtKick()&&!bDisabled&&!bLegacy;
    const float KickLife=VeyrFeelTuning().KickSeconds;
    if(bKick&&KickAge<KickLife)
    {
        const float KE=FMath::Exp(-KickAge/.09f)*(1.f-KickAge/KickLife);
        const FVector Right=Camera->GetRightVector().GetSafeNormal2D();
        const float Side=static_cast<float>(FVector::DotProduct(KickFrom.GetSafeNormal2D(),Right));
        Rotation+=FRotator(.45f*KickAmp*KE,-Side*KickAmp*KE,-Side*.6f*KickAmp*KE);
    }
    Camera->SetRelativeRotation(Rotation);
    if(ShakeBounce>0.f||!Camera->GetRelativeLocation().Equals(Location,.01f))Camera->SetRelativeLocation(Location);
    FPostProcessSettings& PP=Camera->PostProcessSettings;
    const float Hurt=bKick&&HurtAge<.9f?HurtAmp*FMath::Exp(-HurtAge/.22f):0.f;
    if(Hurt>.002f)
    {
        PP.bOverride_VignetteIntensity=true;PP.VignetteIntensity=.12f+1.2f*Hurt;
        PP.bOverride_SceneColorTint=true;PP.SceneColorTint=FLinearColor(1.f,1.f-.5f*Hurt,1.f-.55f*Hurt,1.f);
        bVignetteOwned=true;
    }
    else if(bVignetteOwned)
    {
        // Hand the picture back to the arena's grading volume.
        PP.bOverride_VignetteIntensity=false;PP.bOverride_SceneColorTint=false;PP.SceneColorTint=FLinearColor::White;bVignetteOwned=false;
    }
    // B6: a heavy blow punches the view in for a moment (on top of the knight's own field of view this frame).
    const float Base=FMath::IsNearlyEqual(Camera->FieldOfView,LastFovSet,.0001f)?Camera->FieldOfView-LastFovDelta:Camera->FieldOfView;
    const float PunchLife=VeyrFeelTuning().PunchSeconds;
    const float Punch=VeyrFeelSwitches::ZoomPunch()&&!bDisabled&&!bLegacy&&PunchAge<PunchLife?PunchAmp*FMath::Square(1.f-PunchAge/PunchLife):0.f;
    LastFovDelta=-Base*Punch;
    if(Punch>0.f||LastFovSet>=0.f)
    {
        Camera->SetFieldOfView(Base+LastFovDelta);
        LastFovSet=Punch>0.f?Camera->FieldOfView:-1.f;
        if(Punch<=0.f)LastFovDelta=0.f;
    }
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

void AVeyrFightFeel::StartMeshFlash(USkeletalMeshComponent* Mesh,const FVector& Position,float Weight)
{
    const auto* Mode=GetWorld()->GetAuthGameMode<AVeyrGameMode>();
    if(bDisabled||bLegacy||!Mesh||!MeshFlashMaterial||!VeyrFeelSwitches::MeshFlash()||!Mode||!Mode->bUserHitFlash)return;
    // Only take the overlay slot when nobody else uses it, and give it back when done.
    if(Mesh->GetOverlayMaterial()&&Mesh->GetOverlayMaterial()!=MeshFlashMaterial)return;
    const FVeyrFeelTuning& T=VeyrFeelTuning();
    if(OverlayMesh.IsValid()&&OverlayMesh.Get()!=Mesh&&OverlayMesh->GetOverlayMaterial()==MeshFlashMaterial)OverlayMesh->SetOverlayMaterial(nullptr);
    OverlayMesh=Mesh;Mesh->SetOverlayMaterial(MeshFlashMaterial);
    const float Scale=FMath::Max(.25f,static_cast<float>(Mesh->GetComponentScale().GetAbsMax()));
    MeshFlashMaterial->SetVectorParameterValue(TEXT("HitPos"),FLinearColor(Position.X,Position.Y,Position.Z,0.f));
    MeshFlashMaterial->SetScalarParameterValue(TEXT("Radius"),(T.FlashRadiusCm+T.FlashRadiusGainCm*Weight)*FMath::Sqrt(Scale));
    MeshFlashMaterial->SetVectorParameterValue(TEXT("FlashColor"),FLinearColor(1.f,.82f,.6f));
    MeshFlashMaterial->SetVectorParameterValue(TEXT("Tint"),FLinearColor(1.f,.78f,.55f));
    MeshFlashPeak=T.FlashPeak+T.FlashPeakGain*Weight;MeshFlashAge=0.f;++MeshFlashes;
    UpdateMeshFlash(0.f);
}

void AVeyrFightFeel::UpdateMeshFlash(float RealDelta)
{
    if(!MeshFlashMaterial||!OverlayMesh.IsValid())return;
    MeshFlashAge+=RealDelta;
    const FVeyrFeelTuning& T=VeyrFeelTuning();
    if(MeshFlashAge>=T.FlashLife)
    {
        if(OverlayMesh->GetOverlayMaterial()==MeshFlashMaterial)OverlayMesh->SetOverlayMaterial(nullptr);
        OverlayMesh.Reset();return;
    }
    // Additive and unlit: scaled with the exposure so a flash in a dark corner does not clip to white.
    float I=MeshFlashPeak*FMath::Exp(-MeshFlashAge/FMath::Max(.01f,T.FlashFade))*VeyrLook::FxExposureGain();
    // Relit court: the additive peak is capped in display terms (intensity x exposure), so the hit leg flashes
    // warm instead of clipping to white at 2-6x build 16's exposure. -VeyrTune=flashcap= (display units).
    static const float FlashCap=VeyrLook::Tune(TEXT("flashcap"),.55f);
    if(VeyrLook::FxExposureLock()>0.f&&VeyrLook::LastExposure()>0.f)I=FMath::Min(I,FlashCap/VeyrLook::LastExposure());
    MeshFlashMaterial->SetScalarParameterValue(TEXT("Intensity"),I);
    MeshFlashMaterial->SetScalarParameterValue(TEXT("Opacity"),FMath::Clamp(.09f*I,0.f,.45f)); // the afterimage fallback's only control
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
    if(bLegacy)return;
    const FVeyrFeelTuning& T=VeyrFeelTuning();
    // Blow weight from the damage it did: light one-hand ~45, heavy two-hand ~130, exposed head more.
    const float W=FMath::Clamp(Boss->GetLastSwordDamage()/130.f,.3f,1.f);
    const auto* Mode=GetWorld()->GetAuthGameMode<AVeyrGameMode>();
    const FVector From=Mode&&Mode->Knight?Mode->Knight->GetActorLocation():Boss->LastSwordContactWorld-Boss->GetActorForwardVector()*100.f;
    const FVector Flat=FVector(Boss->LastSwordContactWorld-From).GetSafeNormal2D();
    if(VeyrFeelSwitches::SpineFlinch()&&!Flat.IsNearlyZero())
    {
        // B5: the reference's rock (about up x blow), twist (blow across the body) and spring, summed along the spine.
        const int32 Region=Boss->GetLastHitRegion();
        const float Part=Region==4?T.FlinchHeadPart:Region>=0&&Region<4?T.FlinchLegPart:1.f;
        // A bigger body rocks through a smaller angle; 2x is the reference size.
        const float Size=FMath::Clamp(FMath::Sqrt(2.f/FMath::Max(.5f,Boss->BodyScale)),.75f,1.15f);
        FReact& R=Reacts[NextReact];NextReact=(NextReact+1)%UE_ARRAY_COUNT(Reacts);
        R.Rock=FVector::CrossProduct(FVector::UpVector,Flat).GetSafeNormal()*(T.FlinchRockMin+T.FlinchRockMax*W*W)*Part*Size;
        R.Twist=static_cast<float>(FVector::DotProduct(Flat,Boss->GetActorRightVector()))*(T.FlinchTwistMin+T.FlinchTwistMax*W*W)*Part*Size;
        R.Age=0.f;++SpineFlinches;
    }
    StartMeshFlash(Boss->ImportedPresentation,Boss->LastSwordContactWorld,W);
    if(Mode&&Mode->ImpactFx)
    {
        const FVector Out=(From+FVector(0,0,120)-Boss->LastSwordContactWorld).GetSafeNormal();
        Mode->ImpactFx->HitBurst(Boss->LastSwordContactWorld,Out,W<.45f?0:W<.8f?1:2,Boss->BodyScale);
    }
    if(bHeavy&&VeyrFeelSwitches::SlowTail()&&bOwnsDilation){bPendingSlow=true;SlowTotal=T.SlowTailSeconds;}
    if(bHeavy&&VeyrFeelSwitches::ZoomPunch()){PunchAge=0.f;PunchAmp=T.PunchHeavy*FMath::Lerp(.75f,1.f,W);++ZoomPunches;}
    else if(!bHeavy&&T.PunchLight>0.f&&VeyrFeelSwitches::ZoomPunch()){PunchAge=0.f;PunchAmp=T.PunchLight;++ZoomPunches;}
}

void AVeyrFightFeel::PlayerContact(AVeyrKnight* Player,float Damage,bool bBlocked,const FVector& Source)
{
    if(!Player||bDisabled)return;
    const float Weight=bBlocked?.2f:FMath::Clamp(Damage/40.f,.35f,1.f);
    Impact(Player->GetActorLocation(),Weight,bBlocked?TEXT("guard"):TEXT("player_damage"));
    RequestHitStop(bBlocked?.05f:.07f);Flash(Player->GetActorLocation()+FVector(0,0,35),Weight*.6f,Player->ImportedPresentation);
    if(bLegacy||!VeyrFeelSwitches::HurtKick())return;
    const FVeyrFeelTuning& T=VeyrFeelTuning();
    const FVector Toward=Source.IsZero()?Player->GetActorForwardVector():FVector(Source-Player->GetActorLocation());
    KickFrom=Toward.GetSafeNormal2D().IsNearlyZero()?Player->GetActorForwardVector():Toward.GetSafeNormal2D();
    KickAge=0.f;KickAmp=bBlocked?1.2f:T.KickMin+T.KickGain*Weight;
    if(!bBlocked){HurtAge=0.f;HurtAmp=T.HurtMin+T.HurtGain*Weight;}
    ++HurtKicks;
}

void AVeyrFightFeel::BuildChain(AVeyrDragon* Boss) const
{
    Chain.Reset();FlinchDiagnostic.Reset();
    USkeletalMeshComponent* Mesh=Boss->ImportedPresentation;
    const USkeletalMesh* Asset=Mesh?Mesh->GetSkeletalMeshAsset():nullptr;
    ChainMesh=Asset;
    const FVeyrVisualBoneTarget* Head=Boss->VisualDefinition?Boss->VisualDefinition->BoneTargets.Find(TEXT("head")):nullptr;
    if(!Asset||!Head){FlinchDiagnostic=TEXT("no head target: legacy flinch");return;}
    const FReferenceSkeleton& Ref=Asset->GetRefSkeleton();
    const int32 HeadIndex=Ref.FindBoneIndex(Head->BoneName);
    if(HeadIndex==INDEX_NONE){FlinchDiagnostic=TEXT("head bone missing: legacy flinch");return;}
    // Which legs hang below each bone (bit per leg), from the ankle targets up to the root.
    TArray<uint8> LegMask;LegMask.Init(0,Ref.GetNum());
    TArray<int32> Ankles;
    for(int32 L=0;L<4;++L)
    {
        const FVeyrVisualBoneTarget* Leg=Boss->VisualDefinition->BoneTargets.Find(FName(*FString::Printf(TEXT("leg%d"),L)));
        int32 B=Leg?Ref.FindBoneIndex(Leg->BoneName):INDEX_NONE;Ankles.Add(B);
        for(;B!=INDEX_NONE;B=Ref.GetParentIndex(B))LegMask[B]|=1<<L;
    }
    // Head up to the root. Bones carrying all four legs would swing the whole creature: left out.
    TArray<int32> Spine,Bearing;
    for(int32 B=HeadIndex;B!=INDEX_NONE&&Ref.GetParentIndex(B)!=INDEX_NONE;B=Ref.GetParentIndex(B))
    {
        if(LegMask[B]==0xF)break;
        (LegMask[B]?Bearing:Spine).Add(B);
    }
    const FVeyrFeelTuning& T=VeyrFeelTuning();
    const float BodyShare=Bearing.IsEmpty()?0.f:FMath::Clamp(T.FlinchBodyShare,0.f,.6f);
    float WeightSum=0.f;for(int32 I=0;I<Spine.Num();++I)WeightSum+=Spine.Num()-I*.5f;
    TMap<int32,float> Shares;
    for(int32 I=0;I<Spine.Num();++I){const float S=(1.f-BodyShare)*(Spine.Num()-I*.5f)/FMath::Max(.01f,WeightSum);Shares.Add(Spine[I],S);Chain.Add({Ref.GetBoneName(Spine[I]),S});}
    for(int32 B:Bearing){const float S=BodyShare/Bearing.Num();Shares.Add(B,S);Chain.Add({Ref.GetBoneName(B),S});}
    // Legs under a rocked bone keep their own orientation (the leg's first bone takes the inverse of what is above it).
    int32 Compensated=0;
    for(int32 L=0;L<4;++L)
    {
        int32 B=Ankles[L];if(B==INDEX_NONE)continue;
        while(B!=INDEX_NONE&&!Shares.Contains(Ref.GetParentIndex(B)))
        {
            const int32 P=Ref.GetParentIndex(B);
            if(P==INDEX_NONE||LegMask[P]==0xF){B=INDEX_NONE;break;}
            B=P;
        }
        if(B==INDEX_NONE||Chain.ContainsByPredicate([&](const FChainBone& C){return C.Bone==Ref.GetBoneName(B);}))continue;
        float Above=0.f;for(int32 P=Ref.GetParentIndex(B);P!=INDEX_NONE;P=Ref.GetParentIndex(P))if(const float* S=Shares.Find(P))Above+=*S;
        if(Above>0.f){Chain.Add({Ref.GetBoneName(B),-Above});++Compensated;}
    }
    // The tail lags the other way (two of its bones).
    int32 TailBones=0;
    for(const TCHAR* Name:{TEXT("tail0"),TEXT("tail1")})
        if(const FVeyrVisualBoneTarget* Tail=Boss->VisualDefinition->BoneTargets.Find(Name))
            if(Ref.FindBoneIndex(Tail->BoneName)!=INDEX_NONE&&!Chain.ContainsByPredicate([&](const FChainBone& C){return C.Bone==Tail->BoneName;}))
            {Chain.Add({Tail->BoneName,-T.FlinchTailShare*.5f});++TailBones;}
    while(Chain.Num()>12)Chain.Pop(); // the proxy takes 16; gaze/aim keep their room
    FlinchBoneCount=Chain.Num();
    LegCompensations=Compensated;
    FlinchDiagnostic=FString::Printf(TEXT("%d spine bones, %d leg-bearing (share %.2f), %d leg roots held, %d tail"),Spine.Num(),Bearing.Num(),BodyShare,Compensated,TailBones);
    UE_LOG(LogTemp,Display,TEXT("VEYR_FLINCH_CHAIN %s"),*FlinchDiagnostic);
}

void AVeyrFightFeel::AddBossFlinch(AVeyrDragon* Boss,TMap<FName,FRotator>& Rotations) const
{
    FlinchDegreesNow=0.f;FlinchFrame=GFrameCounter;
    if(bDisabled||!Boss||!Boss->VisualDefinition||Boss->IsDead()||Boss->IsAirborne())return;
    // Down on the floor (buckle, collapse, exposed head, rise) a whole-spine rock would push the head and chest
    // through the floor or bounce them off it: there only the small head-and-neck nudge plays.
    const bool bDown=Boss->State==EVeyrDragonState::Buckle||Boss->State==EVeyrDragonState::Collapse||
        Boss->State==EVeyrDragonState::Exposed||Boss->State==EVeyrDragonState::Rise;
    const USkeletalMesh* Asset=Boss->ImportedPresentation?Boss->ImportedPresentation->GetSkeletalMeshAsset():nullptr;
    if(Asset&&ChainMesh.Get()!=Asset&&!bLegacy&&VeyrFeelSwitches::SpineFlinch())BuildChain(Boss);
    if(!bLegacy&&VeyrFeelSwitches::SpineFlinch()&&!bDown&&Asset&&!Chain.IsEmpty())
    {
        const FVeyrFeelTuning& T=VeyrFeelTuning();
        // Snap up in the first 40 ms, then an under-damped spring home (2 Hz, damping .45: one rebound, ~0.6 s).
        const double Zeta=T.FlinchDamping,Om=2.0*PI*T.FlinchHz,Root=FMath::Sqrt(1.0-Zeta*Zeta),Wd=Om*Root;
        FVector Total=FVector::ZeroVector;bool Any=false;
        for(const FReact& R:Reacts)
        {
            if(R.Age>=T.FlinchLifeSeconds)continue;
            Any=true;
            double C;
            if(R.Age<T.FlinchSnapSeconds){const double S=R.Age/FMath::Max(.001f,T.FlinchSnapSeconds);C=1.0-(1.0-S)*(1.0-S);}
            else{const double U=R.Age-T.FlinchSnapSeconds;C=FMath::Exp(-Zeta*Om*U)*(FMath::Cos(Wd*U)+Zeta/Root*FMath::Sin(Wd*U));}
            Total+=(R.Rock+FVector::UpVector*R.Twist)*static_cast<float>(C);
        }
        if(!Any)return;
        const float Size=FMath::Min(static_cast<float>(Total.Size()),T.FlinchCapDegrees);
        if(Size<.01f)return;
        MaxFlinchDegrees=FMath::Max(MaxFlinchDegrees,Size);FlinchDegreesNow=Size;
        // World rotation vector into the mesh's component space (what the proxy's deltas are in).
        const FVector Axis=Boss->ImportedPresentation->GetComponentQuat().UnrotateVector(Total.GetSafeNormal());
        for(const FChainBone& B:Chain)
        {
            if(!Rotations.Contains(B.Bone)&&Rotations.Num()>=16)continue;
            const FQuat Delta(Axis,FMath::DegreesToRadians(Size*B.Share));
            FRotator& Slot=Rotations.FindOrAdd(B.Bone);
            Slot=ClampBoneRotation(Delta*Slot.Quaternion());
        }
        return;
    }
    if(FlinchAge>=.45f)return;
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

void AVeyrFightFeel::UpdateRibbon(AVeyrKnight* Player,float GameDelta)
{
    const FVeyrFeelTuning& T=VeyrFeelTuning();
    for(int32 I=0;I<RibbonCount;++I)RibbonSamples[I].Age+=GameDelta;
    int32 Drop=0;while(Drop<RibbonCount&&RibbonSamples[Drop].Age>=T.TrailLife)++Drop;
    if(Drop>0){for(int32 I=Drop;I<RibbonCount;++I)RibbonSamples[I-Drop]=RibbonSamples[I];RibbonCount-=Drop;}
    FVector Base=FVector::ZeroVector,Tip=FVector::ZeroVector;
    const bool Attack=!bDisabled&&Player->IsWeaponTrailActive();
    const bool Pose=Player->GetWeaponSweep(Base,Tip);
    if(Attack&&Pose&&bHaveRibbonTip)
    {
        const float Distance=FVector::Distance(Tip,PreviousRibbonTip);
        const float Speed=Distance/FMath::Max(GameDelta,.0005f);
        // A fast blade only, and no jump at a clip or mesh change.
        if(Speed>300.f&&Distance>.5f&&Distance<200.f)
        {
            if(RibbonCount==RibbonMaxSamples){for(int32 I=1;I<RibbonCount;++I)RibbonSamples[I-1]=RibbonSamples[I];--RibbonCount;}
            FRibbonSample& S=RibbonSamples[RibbonCount++];
            S.Base=FMath::Lerp(Base,Tip,FMath::Clamp(T.TrailBaseFraction,0.f,.9f));S.Tip=Tip;S.Age=0.f;
            S.Strength=FMath::Clamp((Speed-300.f)/1500.f,.25f,1.f);
            S.bHeavy=Player->Action==EVeyrKnightAction::HeavyAttack||Player->Action==EVeyrKnightAction::LeapAttack;
            MaxRibbonWidthCm=FMath::Max(MaxRibbonWidthCm,static_cast<float>(FVector::Distance(S.Base,S.Tip)));
            ++TrailSamples;
        }
    }
    bHaveRibbonTip=Pose&&Attack;PreviousRibbonTip=Tip;
    const int32 Rows=RibbonCount>=2?(RibbonCount-1)*RibbonSub+1:0;
    VisibleTrailSegments=FMath::Max(0,Rows-1);
    if(Rows<2)
    {
        if(bRibbonVisible){Ribbon->SetVisibility(false);bRibbonVisible=false;}
        return;
    }
    // Pale, as the reference's hammer smear: white for light swings, a warm white for heavy ones.
    const FLinearColor Cool(.86f,.90f,.98f),Warm(1.f,.92f,.78f);
    for(int32 R=0;R<RibbonMaxRows;++R)
    {
        FVector Inner,Outer;float Alpha=0.f;FLinearColor Colour=Cool;
        if(R<Rows)
        {
            const int32 I=FMath::Min(R/RibbonSub,RibbonCount-2);
            const float U=static_cast<float>(R-I*RibbonSub)/RibbonSub;
            const FRibbonSample& A=RibbonSamples[FMath::Max(I-1,0)];const FRibbonSample& B=RibbonSamples[I];
            const FRibbonSample& C=RibbonSamples[I+1];const FRibbonSample& D=RibbonSamples[FMath::Min(I+2,RibbonCount-1)];
            Outer=CatmullRom(A.Tip,B.Tip,C.Tip,D.Tip,U);Inner=CatmullRom(A.Base,B.Base,C.Base,D.Base,U);
            const float Age=FMath::Clamp(FMath::Lerp(B.Age,C.Age,U)/T.TrailLife,0.f,1.f);
            // The newest end fades in over its row: no hard edge at the blade.
            Alpha=FMath::Pow(1.f-Age,1.6f)*FMath::Lerp(B.Strength,C.Strength,U)*(R==Rows-1?.35f:1.f);
            Colour=(B.bHeavy||C.bHeavy)?Warm:Cool;
        }
        else{Inner=RibbonVerts[(Rows-1)*3];Outer=RibbonVerts[(Rows-1)*3+2]-(RibbonVerts[(Rows-1)*3+2]-Inner)*(.08f/1.08f);}
        // Clear at the hilt side, a full band where the weapon head travels, clear again just past the tip: a soft
        // smear like the reference hammer's, never a flat slab with a hard outer edge.
        const FVector Band=FMath::Lerp(Inner,Outer,.72f),Past=Outer+(Outer-Inner)*.08f;
        RibbonVerts[R*3]=Inner;RibbonVerts[R*3+1]=Band;RibbonVerts[R*3+2]=Past;
        RibbonColors[R*3]=FLinearColor(Colour.R,Colour.G,Colour.B,0.f);RibbonColors[R*3+1]=FLinearColor(Colour.R,Colour.G,Colour.B,Alpha);
        RibbonColors[R*3+2]=FLinearColor(Colour.R,Colour.G,Colour.B,0.f);
        const float V=Rows>1?static_cast<float>(FMath::Min(R,Rows-1))/(Rows-1):0.f;
        RibbonUVs[R*3]=FVector2D(V,0.f);RibbonUVs[R*3+1]=FVector2D(V,.5f);RibbonUVs[R*3+2]=FVector2D(V,1.f);
        const FVector Along=R>0?RibbonVerts[R*3]-RibbonVerts[(R-1)*3]:FVector::ForwardVector;
        const FVector Normal=FVector::CrossProduct(Outer-Inner,Along).GetSafeNormal();
        RibbonNormals[R*3]=RibbonNormals[R*3+1]=RibbonNormals[R*3+2]=Normal.IsNearlyZero()?FVector::UpVector:Normal;
    }
    if(!bRibbonCreated)
    {
        Ribbon->CreateMeshSection_LinearColor(0,RibbonVerts,RibbonTris,RibbonNormals,RibbonUVs,RibbonColors,RibbonTangents,false);
        bRibbonCreated=true;
    }
    else Ribbon->UpdateMeshSection_LinearColor(0,RibbonVerts,RibbonNormals,RibbonUVs,RibbonColors,RibbonTangents);
    if(!bRibbonVisible){Ribbon->SetVisibility(true);bRibbonVisible=true;}
    ++RibbonFrames;MaxRibbonRows=FMath::Max(MaxRibbonRows,Rows);
}

void AVeyrFightFeel::UpdateWeaponTrail(AVeyrKnight* Player,float GameDelta)
{
    if(!Player||GameDelta<=0.f)return;
    if(bRibbonReady&&!bLegacy){UpdateRibbon(Player,GameDelta);return;}
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

TSharedPtr<FJsonObject> AVeyrFightFeel::FeelEvidence(bool bStatic) const
{
    // bStatic: also the parts that do not change per sample (switches, tuning, clearances, asset lists); written once at the root.
    TSharedPtr<FJsonObject> F=MakeShared<FJsonObject>();
    const FVeyrFeelTuning& T=VeyrFeelTuning();
    if(bStatic)
    {
    TSharedPtr<FJsonObject> S=MakeShared<FJsonObject>();
    S->SetBoolField(TEXT("groundContacts"),VeyrFeelSwitches::GroundContacts());S->SetBoolField(TEXT("weightShake"),VeyrFeelSwitches::WeightShake());
    S->SetBoolField(TEXT("contactDust"),VeyrFeelSwitches::ContactDust());S->SetBoolField(TEXT("spineFlinch"),VeyrFeelSwitches::SpineFlinch());
    S->SetBoolField(TEXT("meshFlash"),VeyrFeelSwitches::MeshFlash());S->SetBoolField(TEXT("hitBursts"),VeyrFeelSwitches::HitBursts());
    S->SetBoolField(TEXT("ribbonTrail"),VeyrFeelSwitches::RibbonTrail());S->SetBoolField(TEXT("slowTail"),VeyrFeelSwitches::SlowTail());
    S->SetBoolField(TEXT("zoomPunch"),VeyrFeelSwitches::ZoomPunch());S->SetBoolField(TEXT("hurtKick"),VeyrFeelSwitches::HurtKick());
    F->SetObjectField(TEXT("switches"),S);
    F->SetStringField(TEXT("tuning"),T.Diagnostic);
    }
    static const TCHAR* Classes[4]={TEXT("footfall"),TEXT("stomp"),TEXT("bodyFall"),TEXT("landing")};
    TSharedPtr<FJsonObject> Shakes=MakeShared<FJsonObject>(),MaxShake=MakeShared<FJsonObject>();
    for(int32 I=0;I<4;++I){Shakes->SetNumberField(Classes[I],ShakesByClass[I]);MaxShake->SetNumberField(Classes[I],MaxShakeByClass[I]);}
    F->SetNumberField(TEXT("contactShakes"),ContactShakes);F->SetObjectField(TEXT("shakesByClass"),Shakes);F->SetObjectField(TEXT("maxShakeDegreesByClass"),MaxShake);
    F->SetNumberField(TEXT("shakesFired"),ShakeEvents);
    F->SetNumberField(TEXT("flinches"),FlinchEvents);F->SetNumberField(TEXT("spineFlinches"),SpineFlinches);
    F->SetNumberField(TEXT("maxFlinchDegrees"),MaxFlinchDegrees);F->SetNumberField(TEXT("flinchBones"),FlinchBoneCount);
    F->SetNumberField(TEXT("flinchLegRootsHeld"),LegCompensations);F->SetStringField(TEXT("flinchChain"),FlinchDiagnostic);
    F->SetNumberField(TEXT("meshFlashes"),MeshFlashes);F->SetStringField(TEXT("meshFlash"),FlashDiagnostic);
    F->SetNumberField(TEXT("hitStops"),HitStopEvents);F->SetNumberField(TEXT("slowTails"),SlowTails);
    F->SetNumberField(TEXT("zoomPunches"),ZoomPunches);F->SetNumberField(TEXT("hurtKicks"),HurtKicks);
    F->SetNumberField(TEXT("trailSamples"),TrailSamples);F->SetNumberField(TEXT("trailSegmentsVisible"),VisibleTrailSegments);
    F->SetNumberField(TEXT("ribbonFrames"),RibbonFrames);F->SetNumberField(TEXT("ribbonMaxRows"),MaxRibbonRows);
    F->SetNumberField(TEXT("ribbonMaxWidthCm"),MaxRibbonWidthCm);F->SetStringField(TEXT("ribbon"),RibbonDiagnostic);
    const auto* Mode=GetWorld()?GetWorld()->GetAuthGameMode<AVeyrGameMode>():nullptr;
    if(Mode&&Mode->Dragon)
    {
        const FVeyrGroundContactCounters& C=Mode->Dragon->GetGroundContactCounters();
        TSharedPtr<FJsonObject> G=MakeShared<FJsonObject>();
        static const TCHAR* Parts[6]={TEXT("foot"),TEXT("head"),TEXT("neck"),TEXT("body"),TEXT("tail"),TEXT("wing")};
        TSharedPtr<FJsonObject> ByPart=MakeShared<FJsonObject>(),ByClass=MakeShared<FJsonObject>(),ByTier=MakeShared<FJsonObject>(),Feet=MakeShared<FJsonObject>();
        for(int32 I=0;I<6;++I)ByPart->SetNumberField(Parts[I],C.ByPart[I]);
        for(int32 I=0;I<4;++I){ByClass->SetNumberField(Classes[I],C.ByClass[I]);Feet->SetNumberField(FString::Printf(TEXT("foot%d"),I),C.Feet[I]);}
        for(int32 I=0;I<5;++I)ByTier->SetNumberField(FString::FromInt(I),C.ByTier[I]);
        G->SetNumberField(TEXT("total"),C.Total);G->SetNumberField(TEXT("rejectedSlow"),C.Rejected);
        G->SetObjectField(TEXT("byPart"),ByPart);G->SetObjectField(TEXT("byClass"),ByClass);G->SetObjectField(TEXT("byDustTier"),ByTier);G->SetObjectField(TEXT("feet"),Feet);
        G->SetNumberField(TEXT("maxSpeedMps"),C.MaxSpeedMps);G->SetNumberField(TEXT("maxScaledSpeedMps"),C.MaxScaledSpeedMps);
        G->SetNumberField(TEXT("mutedByFlinch"),C.Muted);G->SetNumberField(TEXT("poseGaps"),C.Resets);
        if(bStatic)
        {
            TSharedPtr<FJsonObject> Clear=MakeShared<FJsonObject>();
            for(const auto& State:Mode->Dragon->GetGroundContactDetector().MinClearanceByState())
            {
                TSharedPtr<FJsonObject> P=MakeShared<FJsonObject>();
                for(const auto& Part:State.Value)P->SetNumberField(Part.Key.ToString(),FMath::RoundToFloat(Part.Value*10.f)/10.f);
                Clear->SetObjectField(State.Key.ToString(),P);
            }
            G->SetObjectField(TEXT("minClearanceCmByState"),Clear);
        }
        F->SetObjectField(TEXT("contacts"),G);
    }
    if(Mode&&Mode->ImpactFx)
    {
        const AVeyrImpactFx* X=Mode->ImpactFx.Get();
        TSharedPtr<FJsonObject> D=MakeShared<FJsonObject>();
        static const TCHAR* Tiers[5]={TEXT("small"),TEXT("medium"),TEXT("large"),TEXT("bodyCloud"),TEXT("landingCloud")};
        for(int32 I=0;I<5;++I){TSharedPtr<FJsonObject> E=MakeShared<FJsonObject>();E->SetNumberField(TEXT("asset"),X->DustAsset[I]);E->SetNumberField(TEXT("fallback"),X->DustFallback[I]);D->SetObjectField(Tiers[I],E);}
        F->SetObjectField(TEXT("dustSpawnedByTier"),D);
        TSharedPtr<FJsonObject> H=MakeShared<FJsonObject>();
        for(int32 I=0;I<3;++I){TSharedPtr<FJsonObject> E=MakeShared<FJsonObject>();E->SetNumberField(TEXT("asset"),X->HitAsset[I]);E->SetNumberField(TEXT("fallback"),X->HitFallback[I]);H->SetObjectField(FString::FromInt(I),E);}
        F->SetObjectField(TEXT("hitBurstsByTier"),H);
        F->SetNumberField(TEXT("debrisChips"),X->ChipsThrown);F->SetNumberField(TEXT("hitSmoke"),X->HitSmoke);F->SetNumberField(TEXT("dustCards"),X->CardsSpawned);
        F->SetNumberField(TEXT("dustCardsMaxLive"),X->MaxLiveCards);F->SetNumberField(TEXT("cloudsMerged"),X->SkippedMerged);
        if(bStatic)
        {
            F->SetStringField(TEXT("effects"),X->Diagnostic);
            TArray<TSharedPtr<FJsonValue>> Missing;for(const FString& M:X->MissingSystems)Missing.Add(MakeShared<FJsonValueString>(M));
            F->SetArrayField(TEXT("missingSystems"),Missing);
        }
    }
    return F;
}

void AVeyrFightFeel::EndPlay(const EEndPlayReason::Type Reason)
{
    if(AVeyrDragon* D=BoundDragon.Get())D->OnGroundContact.Remove(ContactHandle);
    if(OverlayMesh.IsValid()&&OverlayMesh->GetOverlayMaterial()==MeshFlashMaterial)OverlayMesh->SetOverlayMaterial(nullptr);
    RestoreTime();Super::EndPlay(Reason);
}
