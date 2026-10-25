#include "VeyrKnight.h"
#include "VeyrDragon.h"
#include "VeyrSkeletalPresentation.h"
#include "VeyrVisualDefinition.h"
#include "Animation/AnimSequence.h"
#include "Camera/CameraComponent.h"
#include "Components/PointLightComponent.h"
#include "Components/CapsuleComponent.h"
#include "Components/InputComponent.h"
#include "Components/SceneComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Components/PoseableMeshComponent.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/StaticMesh.h"
#include "Engine/GameViewportClient.h"
#include "Engine/World.h"
#include "UnrealClient.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/PlayerController.h"
#include "GameFramework/SpringArmComponent.h"
#include "InputCoreTypes.h"
#include "Kismet/GameplayStatics.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "UObject/ConstructorHelpers.h"

AVeyrKnight::AVeyrKnight()
{
    PrimaryActorTick.bCanEverTick = true;
    GetCapsuleComponent()->InitCapsuleSize(40.f, 122.f); // 244cm standing collision height.
    GetCapsuleComponent()->SetCollisionResponseToChannel(ECC_Camera, ECR_Ignore);
    bUseControllerRotationYaw = false;
    JumpMaxCount = 1;
    JumpMaxHoldTime = .12f;
    UCharacterMovementComponent* Movement = GetCharacterMovement();
    Movement->MaxWalkSpeed = 580.f;
    Movement->MaxAcceleration = 3000.f;
    Movement->BrakingDecelerationWalking = 2500.f;
    Movement->GroundFriction = 8.f;
    Movement->JumpZVelocity = 0.f;
    Movement->GravityScale = 1.8f;
    Movement->AirControl = .30f;
    Movement->RotationRate = FRotator(0.f, 720.f, 0.f);
    Movement->bOrientRotationToMovement = true;
    Movement->MaxStepHeight = 35.f;

    CameraBoom = CreateDefaultSubobject<USpringArmComponent>(TEXT("Collision aware combat camera arm"));
    CameraBoom->SetupAttachment(GetRootComponent());
    CameraBoom->SetRelativeLocation(FVector(0, 0, 65));
    CameraBoom->TargetArmLength = CameraDistance;
    CameraBoom->SocketOffset = FVector(0, 35, 35);
    CameraBoom->ProbeSize = 18.f;
    CameraBoom->ProbeChannel = ECC_Camera;
    CameraBoom->bDoCollisionTest = true;
    CameraBoom->bUsePawnControlRotation = true;
    CameraBoom->bEnableCameraLag = false;
    CameraBoom->CameraLagSpeed = 14.f;
    CameraBoom->CameraLagMaxDistance = 15.f;
    CameraBoom->bUseCameraLagSubstepping = true;
    CameraBoom->bEnableCameraRotationLag = true;
    CameraBoom->CameraRotationLagSpeed = 18.f;
    CombatCamera = CreateDefaultSubobject<UCameraComponent>(TEXT("Combat Camera"));
    CombatCamera->SetupAttachment(CameraBoom, USpringArmComponent::SocketName);
    CombatCamera->bUsePawnControlRotation = false;
    CombatCamera->FieldOfView = 72.f;
    // Soft moon-bounce fill preserves dark metal while exposing hands/shoulders.
    // Channel1 confines this light to the player and held props, not the arena.
    ReadabilityFill=CreateDefaultSubobject<UPointLightComponent>(TEXT("Knight moon bounce fill"));
    ReadabilityFill->SetupAttachment(CombatCamera);
    ReadabilityFill->SetRelativeLocation(FVector(40,-100,100));
    ReadabilityFill->SetIntensityUnits(ELightUnits::Lumens);
    ReadabilityFill->SetIntensity(1800.f);
    ReadabilityFill->SetAttenuationRadius(2600.f);
    ReadabilityFill->SetLightColor(FLinearColor(.80f,.86f,1.f));
    ReadabilityFill->SetCastShadows(false);
    ReadabilityFill->SourceRadius=80.f;
    ReadabilityFill->LightingChannels.bChannel0=false;
    ReadabilityFill->LightingChannels.bChannel1=true;


    ImportedPresentation = CreateDefaultSubobject<UVeyrSkeletalPresentation>(TEXT("ImportedPresentation"));
    ImportedPresentation->SetupAttachment(GetCapsuleComponent());
    ImportedPresentation->LightingChannels.bChannel1=true;
    ImportedPresentation->SetVisibility(false);
    ImportedPresentation->SetHiddenInGame(true);
    // Optional until the stable native data asset is authored. The definition
    // supplies imported orientation, scale and the capsule-to-feet offset.
    static ConstructorHelpers::FObjectFinderOptional<UVeyrVisualDefinition> KnightDefinition(
        TEXT("/Game/Characters/Customuse/RuntimeApproved/DA_Knight.DA_Knight"),LOAD_Quiet|LOAD_NoWarn);
    CustomuseVisualDefinition = KnightDefinition.Get();
    BoatWeapon=CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Tripo Timber Greatsword"));
    BoatWeapon->SetupAttachment(GetCapsuleComponent());
    BoatWeapon->LightingChannels.bChannel1=true;
    BoatWeapon->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    BoatWeapon->SetGenerateOverlapEvents(false);BoatWeapon->SetCanEverAffectNavigation(false);
    BoatWeapon->SetVisibility(false);
    static ConstructorHelpers::FObjectFinderOptional<UStaticMesh> WeaponMesh(
        TEXT("/Game/ArtPass/Tripo/BoatGreatsword_v004/SM_BoatGreatsword_v004.SM_BoatGreatsword_v004"),LOAD_Quiet|LOAD_NoWarn);
    BoatWeapon->SetStaticMesh(WeaponMesh.Get());
    PresentationNominalSpeeds.Add(TEXT("Walk"),123.6f);
    PresentationNominalSpeeds.Add(TEXT("Run"),822.8f);
    PresentationNominalSpeeds.Add(TEXT("StrafeLeft"),170.28f);
    PresentationNominalSpeeds.Add(TEXT("StrafeRight"),163.19f);
    PresentationNominalSpeeds.Add(TEXT("Backpedal"),105.38f);

    // Original engine primitives are a visible verification proxy, not Customuse art.
    TemporaryVisual = CreateDefaultSubobject<USceneComponent>(TEXT("TEMP original primitive knight pending Customuse"));
    TemporaryVisual->SetupAttachment(GetRootComponent());
    TemporaryVisual->SetRelativeLocation(FVector(0, 0, -122));
    static ConstructorHelpers::FObjectFinder<UStaticMesh> Sphere(TEXT("/Engine/BasicShapes/Sphere.Sphere"));
    static ConstructorHelpers::FObjectFinder<UStaticMesh> Cube(TEXT("/Engine/BasicShapes/Cube.Cube"));
    static ConstructorHelpers::FObjectFinder<UStaticMesh> Cylinder(TEXT("/Engine/BasicShapes/Cylinder.Cylinder"));
    static ConstructorHelpers::FObjectFinderOptional<UMaterialInterface> EchoMaterial(
        TEXT("/Game/ArtPass/Materials/M_BlinkAfterimage.M_BlinkAfterimage"),LOAD_Quiet|LOAD_NoWarn);
    BlinkEchoMaterial=EchoMaterial.Get();
    for(int32 I=0;I<2;++I)
    {
        auto* Echo=CreateDefaultSubobject<UPoseableMeshComponent>(I==0?TEXT("Blink departure silhouette"):TEXT("Blink arrival silhouette"));
        Echo->SetupAttachment(GetCapsuleComponent());Echo->SetAbsolute(true,true,true);
        Echo->SetCollisionEnabled(ECollisionEnabled::NoCollision);Echo->SetGenerateOverlapEvents(false);
        Echo->SetCanEverAffectNavigation(false);Echo->SetVisibility(false);Echo->CastShadow=false;
        BlinkEchoBodies.Add(Echo);
        auto* WeaponEcho=CreateDefaultSubobject<UStaticMeshComponent>(I==0?TEXT("Blink departure sword"):TEXT("Blink arrival sword"));
        WeaponEcho->SetupAttachment(GetCapsuleComponent());WeaponEcho->SetAbsolute(true,true,true);
        WeaponEcho->SetCollisionEnabled(ECollisionEnabled::NoCollision);WeaponEcho->SetGenerateOverlapEvents(false);
        WeaponEcho->SetCanEverAffectNavigation(false);WeaponEcho->SetVisibility(false);WeaponEcho->CastShadow=false;
        BlinkEchoWeapons.Add(WeaponEcho);BlinkEchoMaterials.Add(nullptr);
    }
    ApprovedHealCup=CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Approved handled healing cup"));
    ApprovedHealCup->SetupAttachment(GetCapsuleComponent());
    ApprovedHealCup->LightingChannels.bChannel1=true;
    ApprovedHealCup->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    ApprovedHealCup->SetGenerateOverlapEvents(false);
    ApprovedHealCup->SetCanEverAffectNavigation(false);
    ApprovedHealCup->SetVisibility(false);
    HealFlaskRoot=CreateDefaultSubobject<USceneComponent>(TEXT("Original Ember Draught"));
    HealFlaskRoot->SetupAttachment(GetCapsuleComponent());
    HealFlaskRoot->SetAbsolute(false,false,true);
    HealFlaskRoot->SetVisibility(false,true);
    if(Sphere.Succeeded()&&Cylinder.Succeeded())
    {
        // Original proportions in fractions of the measured grip-to-spout
        // distance. Root receives that world-space length once, after sampling.
        auto AddFlaskPart=[&](const TCHAR* Name,UStaticMesh* Mesh,const FVector& Position,const FVector& Size)
        {
            UStaticMeshComponent* Part=CreateDefaultSubobject<UStaticMeshComponent>(Name);
            Part->SetupAttachment(HealFlaskRoot);Part->SetStaticMesh(Mesh);
            Part->SetRelativeLocation(Position);Part->SetRelativeScale3D(Size/100.f);
            Part->SetCollisionEnabled(ECollisionEnabled::NoCollision);
            Part->SetGenerateOverlapEvents(false);Part->SetCanEverAffectNavigation(false);
            Part->CastShadow=false;Part->SetVisibility(false);
            HealFlaskParts.Add(Part);
        };
        AddFlaskPart(TEXT("Ember Draught amber body"),Sphere.Object,FVector(0,0,.10f),FVector(.62f,.62f,.90f));
        AddFlaskPart(TEXT("Ember Draught neck"),Cylinder.Object,FVector(0,0,.67f),FVector(.23f,.23f,.36f));
        AddFlaskPart(TEXT("Ember Draught brass lip"),Cylinder.Object,FVector(0,0,.94f),FVector(.30f,.30f,.12f));
    }
    if (Sphere.Succeeded() && Cube.Succeeded())
    {
        CreateProxyPart(TEXT("TEMP cuirass"), Sphere.Object, TemporaryVisual, FVector(0,0,161), FVector(49,76,83));
        CreateProxyPart(TEXT("TEMP armored hips"), Sphere.Object, TemporaryVisual, FVector(0,0,113), FVector(43,63,36));
        CreateProxyPart(TEXT("TEMP closed helm"), Sphere.Object, TemporaryVisual, FVector(1,0,224), FVector(37,38,40));
        CreateProxyPart(TEXT("TEMP visor ridge"), Cube.Object, TemporaryVisual, FVector(20,0,225), FVector(4,31,5));
        CreateProxyPart(TEXT("TEMP left pauldron"), Sphere.Object, TemporaryVisual, FVector(0,-45,185), FVector(40,38,30));
        CreateProxyPart(TEXT("TEMP right pauldron"), Sphere.Object, TemporaryVisual, FVector(0,45,185), FVector(40,38,30));
        CreateProxyPart(TEXT("TEMP left arm"), Sphere.Object, TemporaryVisual, FVector(3,-46,151), FVector(24,23,57));
        CreateProxyPart(TEXT("TEMP right arm"), Sphere.Object, TemporaryVisual, FVector(10,46,151), FVector(24,23,57));
        LeftLeg = CreateProxyPart(TEXT("TEMP left greave"), Sphere.Object, TemporaryVisual, FVector(0,-20,60), FVector(27,28,102));
        RightLeg = CreateProxyPart(TEXT("TEMP right greave"), Sphere.Object, TemporaryVisual, FVector(0,20,60), FVector(27,28,102));
        CreateProxyPart(TEXT("TEMP left boot"), Cube.Object, TemporaryVisual, FVector(11,-20,12), FVector(49,29,23));
        CreateProxyPart(TEXT("TEMP right boot"), Cube.Object, TemporaryVisual, FVector(11,20,12), FVector(49,29,23));
        SwordPivot = CreateDefaultSubobject<USceneComponent>(TEXT("TEMP sword timing indicator"));
        SwordPivot->SetupAttachment(TemporaryVisual);
        SwordPivot->SetRelativeLocation(FVector(20,47,143));
        CreateProxyPart(TEXT("TEMP sword grip"), Cube.Object, SwordPivot, FVector(0,0,-7), FVector(8,8,28));
        CreateProxyPart(TEXT("TEMP sword guard"), Cube.Object, SwordPivot, FVector(0,0,10), FVector(9,43,7));
        CreateProxyPart(TEXT("TEMP straight blade"), Cube.Object, SwordPivot, FVector(0,0,82), FVector(5,11,138));
    }
}

UStaticMeshComponent* AVeyrKnight::CreateProxyPart(const TCHAR* Name, UStaticMesh* Mesh, USceneComponent* Parent, const FVector& Location, const FVector& Size)
{
    UStaticMeshComponent* Part = CreateDefaultSubobject<UStaticMeshComponent>(Name);
    Part->SetupAttachment(Parent);
    Part->SetStaticMesh(Mesh);
    Part->SetRelativeLocation(Location);
    Part->SetRelativeScale3D(Size / 100.f);
    Part->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    Part->SetGenerateOverlapEvents(false);
    ProxyParts.Add(Part);
    return Part;
}

void AVeyrKnight::BeginPlay()
{
    Super::BeginPlay();
    for(UStaticMeshComponent* Part:HealFlaskParts)
    {
        if(UMaterialInstanceDynamic* Material=Part->CreateAndSetMaterialInstanceDynamic(0))
            Material->SetVectorParameterValue(TEXT("Color"),Part->GetName().Contains(TEXT("body"))?
                FLinearColor(.62f,.13f,.025f):FLinearColor(.35f,.22f,.055f));
    }
    for (UStaticMeshComponent* Part : ProxyParts)
    {
        if (!Part) continue;
        if (UMaterialInstanceDynamic* Material = Part->CreateAndSetMaterialInstanceDynamic(0))
        {
            const FString Name = Part->GetName();
            const bool bBlade = Name.Contains(TEXT("blade"));
            const bool bBrass = Name.Contains(TEXT("guard"));
            const bool bDark = Name.Contains(TEXT("boot")) || Name.Contains(TEXT("grip")) || Name.Contains(TEXT("visor"));
            Material->SetVectorParameterValue(TEXT("Color"), bBlade ? FLinearColor(.62f,.68f,.72f) : bBrass ? FLinearColor(.48f,.31f,.09f) : bDark ? FLinearColor(.045f,.055f,.07f) : FLinearColor(.19f,.25f,.30f));
        }
    }
    if (Controller) Controller->SetControlRotation(FRotator(0.f, GetActorRotation().Yaw, 0.f));
    if(!CustomuseVisualDefinition)CustomuseVisualDefinition=LoadObject<UVeyrVisualDefinition>(nullptr,
        TEXT("/Game/Characters/Customuse/RuntimeApproved/DA_Knight.DA_Knight"),nullptr,LOAD_Quiet|LOAD_NoWarn);
    if(!CustomuseVisualDefinition)
    {
        CustomuseVisualDefinition=LoadObject<UVeyrVisualDefinition>(nullptr,TEXT("/Game/Characters/Customuse/Runtime/DA_Knight.DA_Knight"),nullptr,LOAD_Quiet|LOAD_NoWarn);
        if(CustomuseVisualDefinition)UE_LOG(LogTemp,Warning,TEXT("VEYR_LEGACY_DEFINITION approved native definition missing; old art is not integration acceptance"));
    }
    if (CustomuseVisualDefinition) ApplyCustomuseVisual(CustomuseVisualDefinition);
    else SetPresentationDiagnostic(TEXT("Temporary primitive presentation: imported visual definition unavailable"));
    UE_LOG(LogTemp, Display, TEXT("VEYR_KNIGHT_READY collisionHeight=244cm art=%s light=%.3f/%.3f heavy=%.3f/%.3f roll=.08-.44/%.2f"),
        bImportedPresentationActive ? TEXT("imported_definition_acceptance_pending") : TEXT("TEMP_original_primitives_pending_Customuse"),
        GetAttackContactTime(false),GetAttackDuration(false),GetAttackContactTime(true),GetAttackDuration(true),
        bImportedPresentationActive?.78f:.58f);
}

bool AVeyrKnight::IsGrounded() const { return GetCharacterMovement() && GetCharacterMovement()->IsMovingOnGround(); }
bool AVeyrKnight::IsBlinkAction() const { return Action==EVeyrKnightAction::BlinkLeft||Action==EVeyrKnightAction::BlinkRight; }
bool AVeyrKnight::IsRollPrefix() const { return Action==EVeyrKnightAction::Roll||(Action==EVeyrKnightAction::RollAttack&&ActionElapsed<.78f); }
bool AVeyrKnight::IsAttackAction() const { return Action==EVeyrKnightAction::LightAttack||Action==EVeyrKnightAction::HeavyAttack||Action==EVeyrKnightAction::Combo||Action==EVeyrKnightAction::RollAttack; }
bool AVeyrKnight::IsRollingInvulnerable() const { return (IsRollPrefix()||IsBlinkAction())&&ActionElapsed>.08f&&ActionElapsed<.44f; }
float AVeyrKnight::GetPlanarSpeed() const { return GetVelocity().Size2D(); }
FVector AVeyrKnight::GetFootLocation() const { return GetActorLocation()-FVector(0,0,GetCapsuleComponent()->GetScaledCapsuleHalfHeight()); }
bool AVeyrKnight::HasVisualClip(FName Name) const
{
    const FVeyrVisualClip* C=CustomuseVisualDefinition?CustomuseVisualDefinition->Clips.Find(Name):nullptr;
    return C&&C->Sequence;
}
float AVeyrKnight::VisualClipPlayRate(FName Name) const
{
    const FVeyrVisualClip* C=CustomuseVisualDefinition?CustomuseVisualDefinition->Clips.Find(Name):nullptr;
    return C?FMath::Clamp(C->GameplayPlayRate,.1f,4.f):1.f;
}
float AVeyrKnight::VisualClipDuration(FName Name,float Fallback) const
{
    const FVeyrVisualClip* C=CustomuseVisualDefinition?CustomuseVisualDefinition->Clips.Find(Name):nullptr;
    if(!C||!C->Sequence)return Fallback;
    const float End=C->EndSeconds<0.f?C->Sequence->GetPlayLength():C->EndSeconds;
    return FMath::IsFinite(End)&&End>C->StartSeconds?(End-C->StartSeconds)/VisualClipPlayRate(Name):Fallback;
}
float AVeyrKnight::VisualClipSpeed(FName Name) const
{
    const FVeyrVisualClip* C=CustomuseVisualDefinition?CustomuseVisualDefinition->Clips.Find(Name):nullptr;
    if(C&&FMath::IsFinite(C->NominalSpeedCmPerSecond)&&C->NominalSpeedCmPerSecond>1.f)return C->NominalSpeedCmPerSecond;
    const float* Legacy=PresentationNominalSpeeds.Find(Name);
    return Legacy&&*Legacy>0.f?*Legacy:0.f;
}
FName AVeyrKnight::ChooseAttackClip(bool bHeavy) const
{
    if(bHeavy)
    {
        if(bTwoHanded)return TwoHandHeavyAnimationVariant==1?TEXT("HeavyAttackTwoHandAlternate"):TEXT("HeavyAttackTwoHand");
        return HeavyAnimationVariant==1?TEXT("HeavyAttackAlternate"):TEXT("HeavyAttack");
    }
    return bTwoHanded?TEXT("LightAttackTwoHand"):TEXT("LightAttack");
}
float AVeyrKnight::GetAttackDuration(bool bHeavy) const { return VisualClipDuration(ChooseAttackClip(bHeavy),bTwoHanded?(bHeavy?1.20f:.90f):(bHeavy?.90f:.66f)); }
float AVeyrKnight::GetAttackContactTime(bool bHeavy) const
{
    const FVeyrVisualClip* C=CustomuseVisualDefinition?CustomuseVisualDefinition->Clips.Find(ChooseAttackClip(bHeavy)):nullptr;
    if(C&&!C->DamageWindows.IsEmpty())return C->DamageWindows[0].X/VisualClipPlayRate(ChooseAttackClip(bHeavy));
    if(C&&C->ImpactSeconds>=0.f)return (C->ImpactSeconds-C->StartSeconds)/VisualClipPlayRate(ChooseAttackClip(bHeavy));
    return GetAttackDuration(bHeavy)*.5f;
}
float AVeyrKnight::GetSwordContactTime() const
{
    if(!IsAttackAction())return -1.f;
    const FVeyrVisualClip* Clip=CustomuseVisualDefinition?CustomuseVisualDefinition->Clips.Find(ActionPresentationClip):nullptr;
    if(Clip&&!Clip->DamageWindows.IsEmpty())
    {
        const float Rate=VisualClipPlayRate(ActionPresentationClip);
        for(const FVector2D& Window:Clip->DamageWindows)if(Window.Y/Rate>=ActionElapsed)return Window.X/Rate;
        return Clip->DamageWindows.Last().X/Rate;
    }
    return GetAttackContactTime(Action==EVeyrKnightAction::HeavyAttack);
}
bool AVeyrKnight::IsTerminal() const { return IsDead()||(IsValid(Boss)&&Boss->IsDead()); }
bool AVeyrKnight::CanStartGroundedAction() const
{
    return GripTransitionRemaining<=0.f&&!IsTerminal()&&IsGrounded()&&!bPressedJump&&
        (Action==EVeyrKnightAction::Ready||Action==EVeyrKnightAction::Guard||Action==EVeyrKnightAction::RunStop);
}
FName AVeyrKnight::ResolveActionClip(EVeyrKnightAction NewAction) const
{
    switch(NewAction)
    {
        case EVeyrKnightAction::LightAttack:return ChooseAttackClip(false);
        case EVeyrKnightAction::HeavyAttack:return ChooseAttackClip(true);
        case EVeyrKnightAction::Combo:return TEXT("LightCombo");
        case EVeyrKnightAction::RollAttack:return TEXT("RollAttack");
        case EVeyrKnightAction::Roll:return TEXT("Roll");
        case EVeyrKnightAction::RunStop:return TEXT("RunStop");
        case EVeyrKnightAction::BlinkLeft:return TEXT("BlinkLeft");
        case EVeyrKnightAction::BlinkRight:return TEXT("BlinkRight");
        case EVeyrKnightAction::Backstep:return TEXT("BackpedalStep");
        case EVeyrKnightAction::GuardBreak:return TEXT("GuardBreak");
        case EVeyrKnightAction::Guard:return TEXT("GuardTwoHand");
        case EVeyrKnightAction::Heal:return TEXT("Heal");
        case EVeyrKnightAction::Stagger:return TEXT("Stagger");
        case EVeyrKnightAction::Dead:return TEXT("Death");
        default:return bTwoHanded?TEXT("IdleTwoHand"):TEXT("Idle");
    }
}

void AVeyrKnight::BeginAction(EVeyrKnightAction NewAction,float Duration)
{
    if(NewAction==EVeyrKnightAction::Guard&&!bTwoHanded){bTwoHanded=true;GripTransitionRemaining=.28f;}
    ClearBlinkEchoes();
    Action=NewAction;ActionElapsed=0.f;ActionDuration=Duration;ActionPresentationClip=ResolveActionClip(NewAction);
    bContactSent=false;bHealGranted=false;bPreviousBladePoseValid=false;bPreserveRollPrefix=false;
    bBlinkHidden=false;bLateralDodgeBlocked=false;ContactedDamageWindows.Reset();CurrentDamageWindow=INDEX_NONE;
    ActionRootTravelCm=0.f;bActionRootBlocked=false;
    if(NewAction!=EVeyrKnightAction::Ready)bWasRunning=false;
    if(IsAttackAction()||IsBlinkAction()||NewAction==EVeyrKnightAction::Guard||NewAction==EVeyrKnightAction::Heal||
       NewAction==EVeyrKnightAction::RunStop||NewAction==EVeyrKnightAction::GuardBreak||NewAction==EVeyrKnightAction::Backstep)
    {
        ConsumeMovementInputVector();GetCharacterMovement()->StopMovementImmediately();
    }
    UE_LOG(LogTemp,Display,TEXT("VEYR_KNIGHT_ACTION state=%d clip=%s duration=%.3f"),int32(Action),*ActionPresentationClip.ToString(),ActionDuration);
}

void AVeyrKnight::FinishAction()
{
    bGuardBroken = false;
    BeginAction(bGuardRequested && Stamina > 5.f && IsGrounded() ? EVeyrKnightAction::Guard : EVeyrKnightAction::Ready, 0.f);
}

void AVeyrKnight::ToggleGrip()
{
    if (!CanStartGroundedAction() || Action == EVeyrKnightAction::Guard) return;
    bTwoHanded=!bTwoHanded; GripTransitionRemaining=.28f;
    BufferedAttackRemaining=0.f;
    UE_LOG(LogTemp,Display,TEXT("VEYR_GRIP twoHanded=%d"),bTwoHanded);
}

void AVeyrKnight::TryLightAttack()
{
    if(Action==EVeyrKnightAction::Roll&&!IsTerminal()&&HasVisualClip(TEXT("RollAttack"))&&Stamina>=22.f)
    {
        // The imported roll-attack prefix is byte-identical to the praised roll.
        // Upgrade in place: keep its movement, clock and invulnerability window.
        Stamina-=22.f;RegenDelay=.9f;++LightAttacks;++RollAttacks;ActionSwingBase=++SwingId;
        Action=EVeyrKnightAction::RollAttack;ActionPresentationClip=TEXT("RollAttack");
        ActionDuration=VisualClipDuration(ActionPresentationClip,2.2f);bSwingTwoHanded=false;
        ContactedDamageWindows.Reset();bPreviousBladePoseValid=false;bPreserveRollPrefix=true;
        UE_LOG(LogTemp,Display,TEXT("VEYR_ROLL_ATTACK_QUEUED preservedTime=%.3f"),ActionElapsed);return;
    }
    if (!CanStartGroundedAction())
    {
        if(!IsTerminal()&&IsAttackAction()&&
           ActionDuration-ActionElapsed<=.18f) { BufferedAttackRemaining=.20f;bBufferedHeavy=false; }
        return;
    }
    const float Cost=bTwoHanded?28.f:22.f;
    if(Stamina<Cost)return;
    Stamina-=Cost;RegenDelay=.75f;ActionSwingBase=++SwingId;++LightAttacks;bSwingTwoHanded=bTwoHanded;BufferedAttackRemaining=0.f;
    BeginAction(EVeyrKnightAction::LightAttack,GetAttackDuration(false));
}

void AVeyrKnight::TryHeavyAttack()
{
    if (!CanStartGroundedAction())
    {
        if(!IsTerminal()&&IsAttackAction()&&
           ActionDuration-ActionElapsed<=.18f) { BufferedAttackRemaining=.20f;bBufferedHeavy=true; }
        return;
    }
    const float Cost=bTwoHanded?40.f:34.f;
    if(Stamina<Cost)return;
    Stamina-=Cost;RegenDelay=1.f;ActionSwingBase=++SwingId;++HeavyAttacks;bSwingTwoHanded=bTwoHanded;BufferedAttackRemaining=0.f;
    BeginAction(EVeyrKnightAction::HeavyAttack,GetAttackDuration(true));
}

void AVeyrKnight::TryRoll()
{
    if (!CanStartGroundedAction() || Stamina < 25.f) return;
    const float Side=FVector::DotProduct(MoveIntent.GetSafeNormal2D(),GetActorRightVector());
    const float Forward=FVector::DotProduct(MoveIntent.GetSafeNormal2D(),GetActorForwardVector());
    if(bLockedOn&&FMath::Abs(Side)>FMath::Abs(Forward)){TryBlink(Side<0.f);return;}
    Stamina -= 25.f; RegenDelay = .7f; ++Rolls;
    RollDirection = MoveIntent.GetSafeNormal2D();
    if (RollDirection.IsNearlyZero()) RollDirection = GetActorForwardVector().GetSafeNormal2D();
    BeginAction(EVeyrKnightAction::Roll,VisualClipDuration(TEXT("Roll"),bImportedPresentationActive?.78f:.58f));
}

void AVeyrKnight::TryHeal()
{
    if (!CanStartGroundedAction() || HealingCharges <= 0 || Health >= 100.f) return;
    --HealingCharges;
    BeginAction(EVeyrKnightAction::Heal,VisualClipDuration(TEXT("Heal"),1.25f));
}

bool AVeyrKnight::TryBlink(bool bLeft)
{
    if(!CanStartGroundedAction()||BlinkCooldownRemaining>0.f||Stamina<25.f)return false;
    const FName Clip=bLeft?TEXT("BlinkLeft"):TEXT("BlinkRight");
    if(!HasVisualClip(Clip)){SetPresentationDiagnostic(TEXT("Approved blink clip missing: ")+Clip.ToString());return false;}
    Stamina-=25.f;RegenDelay=.7f;++BlinkDodges;
    BeginAction(bLeft?EVeyrKnightAction::BlinkLeft:EVeyrKnightAction::BlinkRight,VisualClipDuration(Clip,.7f));
    BlinkCooldownRemaining=ActionDuration+.10f;return true;
}
void AVeyrKnight::TryCombo()
{
    if(!CanStartGroundedAction()||Stamina<70.f||!HasVisualClip(TEXT("LightCombo")))return;
    Stamina-=70.f;RegenDelay=1.f;++ComboAttacks;LightAttacks+=2;++HeavyAttacks;
    ActionSwingBase=SwingId+1;SwingId+=3;bTwoHanded=true;bSwingTwoHanded=true;
    BeginAction(EVeyrKnightAction::Combo,VisualClipDuration(TEXT("LightCombo"),3.32f));
}
void AVeyrKnight::TryBackstep()
{
    if(!CanStartGroundedAction()||!HasVisualClip(TEXT("BackpedalStep")))return;
    BeginAction(EVeyrKnightAction::Backstep,VisualClipDuration(TEXT("BackpedalStep"),2.4f));
}
void AVeyrKnight::VeyrBackstep(){TryBackstep();}
void AVeyrKnight::VeyrCombo(){TryCombo();}
void AVeyrKnight::VeyrSetVariants(int32 RunVariant,int32 HeavyVariant,int32 TwoHandHeavyVariant)
{
    if(!CanStartGroundedAction())return;
    RunAnimationVariant=FMath::Clamp(RunVariant,0,1);HeavyAnimationVariant=FMath::Clamp(HeavyVariant,0,1);
    TwoHandHeavyAnimationVariant=FMath::Clamp(TwoHandHeavyVariant,0,1);
    UE_LOG(LogTemp,Display,TEXT("VEYR_VARIANTS run=%d heavy=%d twoHandHeavy=%d"),RunAnimationVariant,HeavyAnimationVariant,TwoHandHeavyAnimationVariant);
}
void AVeyrKnight::CycleAnimationVariants(){VeyrSetVariants(1-RunAnimationVariant,1-HeavyAnimationVariant,1-TwoHandHeavyAnimationVariant);}
void AVeyrKnight::ComboPressed(){if(HumanInputEnabled())TryCombo();}
void AVeyrKnight::VariantPressed(){if(HumanInputEnabled())CycleAnimationVariants();}
void AVeyrKnight::WalkModifierPressed(){if(HumanInputEnabled())bWalkModifier=true;}
void AVeyrKnight::WalkModifierReleased(){bWalkModifier=false;}

void AVeyrKnight::SetGuard(bool bHeld)
{
    bGuardRequested = bHeld;
    if (!bHeld && Action == EVeyrKnightAction::Guard) BeginAction(EVeyrKnightAction::Ready, 0.f);
    else if (bHeld && CanStartGroundedAction() && Stamina > 5.f && Action != EVeyrKnightAction::Guard)
        BeginAction(EVeyrKnightAction::Guard, 0.f);
}

void AVeyrKnight::ToggleLockOn() { if (!IsTerminal() && IsValid(Boss)) bLockedOn = !bLockedOn; }

void AVeyrKnight::ApplyBossDamage(float Amount, const FVector& Source, bool bUnblockable)
{
    if (IsTerminal() || Amount <= 0.f || !FMath::IsFinite(Amount)) return;
    if (IsRollingInvulnerable()) { ++DodgedHits; return; }
    if (DamageGrace > 0.f) return;
    const FVector ToSource = (Source - GetActorLocation()).GetSafeNormal2D();
    const bool bFacingThreat = !ToSource.IsNearlyZero() && FVector::DotProduct(GetActorForwardVector(), ToSource) >= .5f;
    const bool bGuardRaised=ActionElapsed>=FMath::Min(.30f,VisualClipDuration(TEXT("GuardTwoHand"),.7f)*.43f);
    const bool bCanBlock = Action == EVeyrKnightAction::Guard && bGuardRaised && IsGrounded() && !bUnblockable && bFacingThreat;
    bool bBroken = false;
    if (bCanBlock)
    {
        const float GuardCost = FMath::Max(12.f, Amount * .9f);
        if (Stamina >= GuardCost)
        {
            Stamina -= GuardCost; Amount *= .15f; ++GuardedHits; RegenDelay = 1.f;
            UE_LOG(LogTemp, Display, TEXT("VEYR_KNIGHT_GUARD_BLOCK stamina=%.2f chip=%.2f"), Stamina, Amount);
        }
        else
        {
            Stamina = 0.f; bBroken = true; ++GuardBreaks; bGuardRequested = false; RegenDelay = 1.2f;
            UE_LOG(LogTemp, Display, TEXT("VEYR_KNIGHT_GUARD_BREAK"));
        }
    }
    Health = FMath::Clamp(Health - Amount, 0.f, 100.f);
    ++HitsTaken; DamageGrace = .30f;
    if (IsDead())
    {
        bGuardRequested = false; bLockedOn = false;
        float DeathDuration=bImportedPresentationActive?4.4f:2.f;
        if(bImportedPresentationActive&&CustomuseVisualDefinition)
        {
            const FVeyrVisualClip* Death=CustomuseVisualDefinition->Clips.Find(TEXT("Death"));
            if(Death&&Death->Sequence)
            {
                const float End=Death->EndSeconds<0.f?Death->Sequence->GetPlayLength():Death->EndSeconds;
                if(FMath::IsFinite(Death->StartSeconds)&&FMath::IsFinite(End)&&Death->StartSeconds>=0.f&&
                    End>Death->StartSeconds&&End<=Death->Sequence->GetPlayLength())
                    DeathDuration=End-Death->StartSeconds;
            }
        }
        BeginAction(EVeyrKnightAction::Dead, DeathDuration);
        GetCharacterMovement()->StopMovementImmediately();
        UE_LOG(LogTemp, Display, TEXT("VEYR_KNIGHT_DEAD"));
        return;
    }
    if (!bCanBlock || bBroken)
    {
        bGuardBroken = bBroken;
        BeginAction(bBroken?EVeyrKnightAction::GuardBreak:EVeyrKnightAction::Stagger,VisualClipDuration(bBroken?TEXT("GuardBreak"):TEXT("Stagger"),bBroken?1.2f:.42f));
        const FVector Away = (GetActorLocation() - Source).GetSafeNormal2D();
        if(!bBroken)GetCharacterMovement()->AddImpulse(Away*120.f,true); // Guard-break travel comes from its approved root track.
    }
}

void AVeyrKnight::Tick(float DeltaSeconds)
{
    Super::Tick(DeltaSeconds);
    if (DeltaSeconds <= 0.f) return;
    UpdateMouseCapture();
    VisualClock += DeltaSeconds;
    BlinkCooldownRemaining=FMath::Max(0.f,BlinkCooldownRemaining-DeltaSeconds);
    RegenDelay = FMath::Max(0.f, RegenDelay - DeltaSeconds);
    DamageGrace = FMath::Max(0.f, DamageGrace - DeltaSeconds);
    const FRotator ViewYaw(0.f, Controller ? Controller->GetControlRotation().Yaw : GetActorRotation().Yaw, 0.f);
    MoveIntent = bReplayControlled ? ReplayMove.GetClampedToMaxSize(1.f) :
        (FRotationMatrix(ViewYaw).GetUnitAxis(EAxis::X) * (float(bForwardHeld) - float(bBackHeld)) +
         FRotationMatrix(ViewYaw).GetUnitAxis(EAxis::Y) * (float(bRightHeld) - float(bLeftHeld))).GetClampedToMaxSize(1.f);
    MoveIntent.Z = 0.f;
    if (!bReplayControlled && !bMouseCaptured) MoveIntent = FVector::ZeroVector;
    if (bReplayControlled)
    {
        SetGuard(bReplayGuard);
        if (bReplayRoll) TryRoll();
        else if (bReplayHeal) TryHeal();
        else if (bReplayHeavy) TryHeavyAttack();
        else if (bReplayLight) TryLightAttack();
        bReplayLight = bReplayHeavy = bReplayRoll = bReplayHeal = bReplayJump = false;
    }
    UpdateMovement(DeltaSeconds);
    if (IsDead()) { ActionElapsed += DeltaSeconds; UpdateImportedPresentation(DeltaSeconds); }
    else if (!IsTerminal()) AdvanceCombat(DeltaSeconds);
    else
    {
        // Victory stops combat immediately, but the visible recovery must finish.
        GetCharacterMovement()->StopMovementImmediately();bLockedOn=false;bGuardRequested=false;
        if(Action!=EVeyrKnightAction::Ready)
        {
            ActionElapsed+=DeltaSeconds;
            if(ActionDuration<=0.f||ActionElapsed>=ActionDuration)FinishAction();
        }
        UpdateImportedPresentation(DeltaSeconds);
    }
    UpdateEquippedWeapon();
    UpdateHealFlask();
    UpdateBlinkEchoes();
    UpdateCamera(DeltaSeconds);
    UpdateTemporaryPresentation(DeltaSeconds);
}

void AVeyrKnight::AdvanceCombat(float DeltaSeconds)
{
    GripTransitionRemaining=FMath::Max(0.f,GripTransitionRemaining-DeltaSeconds);
    BufferedAttackRemaining=FMath::Max(0.f,BufferedAttackRemaining-DeltaSeconds);
    const float PreviousSeconds=ActionElapsed;
    ActionElapsed+=DeltaSeconds;
    ApplyAuthoredRootMotion(PreviousSeconds,ActionElapsed);
    UpdateImportedPresentation(DeltaSeconds);
    if(IsAttackAction())ResolveAttackWindows(PreviousSeconds);
    else if (Action == EVeyrKnightAction::Heal && bRequestedPresentationClipSampled && !bHealGranted && ActionElapsed >= VisualClipDuration(TEXT("Heal"),1.25f)*.55f)
    {
        bHealGranted = true; Health = FMath::Min(100.f, Health + 55.f); ++SuccessfulHeals;
    }
    else if (Action == EVeyrKnightAction::Guard)
    {
        Stamina = FMath::Max(0.f, Stamina - 3.f * DeltaSeconds);
        if (Stamina <= 0.f || !IsGrounded()) FinishAction();
    }
    if (ActionDuration > 0.f && ActionElapsed >= ActionDuration)
    {
        FinishAction();
        if(BufferedAttackRemaining>0.f) { if(bBufferedHeavy)TryHeavyAttack();else TryLightAttack(); }
    }
    if (Action == EVeyrKnightAction::Ready)
    {
        if (RegenDelay <= 0.f) Stamina = FMath::Min(100.f, Stamina + 29.f * DeltaSeconds);
        if (bGuardRequested && Stamina > 5.f && IsGrounded() && !bPressedJump) BeginAction(EVeyrKnightAction::Guard, 0.f);
    }
}

void AVeyrKnight::UpdateMovement(float DeltaSeconds)
{
    if (IsTerminal()) return;
    UCharacterMovementComponent* Movement = GetCharacterMovement();
    if (!bReplayControlled && !bMouseCaptured)
    {
        ConsumeMovementInputVector();
        Movement->Velocity.X = Movement->Velocity.Y = 0.f;
        return;
    }
    if(Action==EVeyrKnightAction::RunStop&&!MoveIntent.IsNearlyZero())FinishAction();
    if(Action==EVeyrKnightAction::Ready&&bWasRunning&&MoveIntent.IsNearlyZero()&&HasVisualClip(TEXT("RunStop")))
    {
        ++RunStops;BeginAction(EVeyrKnightAction::RunStop,VisualClipDuration(TEXT("RunStop"),.6f));
    }
    bLateralDodgeBlocked=false;
    if(Action==EVeyrKnightAction::Ready&&bLockedOn&&!MoveIntent.IsNearlyZero())
    {
        const float Side=FVector::DotProduct(MoveIntent.GetSafeNormal2D(),GetActorRightVector());
        const float Forward=FVector::DotProduct(MoveIntent.GetSafeNormal2D(),GetActorForwardVector());
        if(FMath::Abs(Side)>FMath::Abs(Forward))
        {
            if(!TryBlink(Side<0.f))bLateralDodgeBlocked=true;
        }
    }
    const bool bAttack=IsAttackAction();
    Movement->bOrientRotationToMovement=!bLockedOn&&Action==EVeyrKnightAction::Ready;
    if(IsRollPrefix())
    {
        const float RollSpeed=1180.f*.58f/.78f;
        Movement->MaxWalkSpeed=RollSpeed;
        Movement->Velocity.X=RollDirection.X*RollSpeed;Movement->Velocity.Y=RollDirection.Y*RollSpeed;
        AddMovementInput(RollDirection,1.f);
    }
    else if(Action==EVeyrKnightAction::Ready&&!bLateralDodgeBlocked)
    {
        FVector EffectiveMove=MoveIntent;
        Movement->MaxWalkSpeed=bTwoHanded?FMath::Clamp(VisualClipSpeed(TEXT("WalkTwoHand")),120.f,380.f):bWalkModifier?FMath::Clamp(VisualClipSpeed(TEXT("Walk")),100.f,300.f):580.f;
        if(bLockedOn)
        {
            const float Forward=FVector::DotProduct(MoveIntent,GetActorForwardVector());
            EffectiveMove=GetActorForwardVector()*Forward; // Lateral travel belongs to a discrete blink.
            if(Forward<0.f)Movement->MaxWalkSpeed=FMath::Clamp(VisualClipSpeed(TEXT("Backpedal")),100.f,300.f);
        }
        AddMovementInput(EffectiveMove,1.f);
    }
    else
    {
        ConsumeMovementInputVector();Movement->StopMovementImmediately();Movement->MaxWalkSpeed=0.f;
    }
    if (bLockedOn && IsValid(Boss) && !bAttack && Action==EVeyrKnightAction::Ready)
    {
        const FVector Toward = (Boss->GetActorLocation() - GetActorLocation()).GetSafeNormal2D();
        if (!Toward.IsNearlyZero()) SetActorRotation(FMath::RInterpTo(GetActorRotation(), Toward.Rotation(), DeltaSeconds, 10.f));
    }
    else if (Action == EVeyrKnightAction::Guard && Controller)
    {
        // Backpedaling while guarding preserves the direction the player is looking.
        const FRotator Facing(0.f, Controller->GetControlRotation().Yaw, 0.f);
        SetActorRotation(FMath::RInterpTo(GetActorRotation(), Facing, DeltaSeconds, 10.f));
    }
}

void AVeyrKnight::UpdateCamera(float DeltaSeconds)
{
    const FVector Feet=GetFootLocation();
    const bool bHasBoss=IsValid(Boss)&&!Boss->IsDead();
    const float BossRange=bHasBoss?FVector::Dist2D(GetActorLocation(),Boss->GetActorLocation()):1600.f;
    const float FarBlend=FMath::Clamp((BossRange-1000.f)/600.f,0.f,1.f);
    const bool FlightFraming=bHasBoss&&Boss->Move==EVeyrDragonMove::FlyAway&&
        (Boss->State==EVeyrDragonState::Windup||Boss->State==EVeyrDragonState::Active||Boss->State==EVeyrDragonState::Recovery);
    FlightCameraBlend=FMath::FInterpTo(FlightCameraBlend,FlightFraming?1.f:0.f,DeltaSeconds,3.f);
    CombatCamera->SetFieldOfView(FMath::Lerp(72.f,86.f,FlightCameraBlend));
    // A small distance allowance at range permits a level view of the entire
    // giant while retaining floor clearance and space above the boss HUD.
    const bool bOpeningView=!bReplayControlled&&!bHasEverCapturedMouse;
    const float GroundArm=FMath::Clamp(CameraDistance,500.f,1100.f)+100.f*FarBlend+(bOpeningView?350.f:0.f);
    const float DesiredArm=FMath::Lerp(GroundArm,FMath::Max(GroundArm,1600.f),FlightCameraBlend);
    if(VisualClock<=DeltaSeconds*1.5f)CameraBoom->TargetArmLength=DesiredArm;
    else CameraBoom->TargetArmLength=FMath::FInterpTo(CameraBoom->TargetArmLength,DesiredArm,DeltaSeconds,12.f);
    const float Arm=FMath::Max(1.f,CameraBoom->TargetArmLength);
    // Position lag shortened the real player-to-camera distance during a roll,
    // invalidating the requested-arm framing solve. Rotation retains its own
    // smoothing below; position now follows the pawn without that hidden offset.
    CameraBoom->bEnableCameraLag=false;
    float FramingCandidate=Arm;
    if(CameraBoom->IsCollisionFixApplied())
        FramingCandidate=FMath::Min(FramingCandidate,static_cast<float>(FVector::Dist2D(
            CameraBoom->GetComponentLocation(),CombatCamera->GetComponentLocation())));
    if(Controller&&CameraBoom->bDoCollisionTest)
    {
        // Predict using the same sphere/channel as the owned spring arm. The
        // horizontal obstruction distance remains stable as pitch tilts down
        // against a wall; using the slanted distance would cause feedback.
        const float ProbeHeight=FMath::Lerp(FMath::Min(187.f,Arm*.27f),FMath::Min(375.f,Arm*.24f),FlightCameraBlend);
        const FVector ProbeOrigin=Feet+FVector(0,0,ProbeHeight);
        const FRotator ProbeRotation=Controller->GetControlRotation();
        const FVector ProbeEnd=ProbeOrigin-ProbeRotation.Vector()*Arm+ProbeRotation.RotateVector(CameraBoom->SocketOffset);
        FHitResult CameraHit;
        FCollisionQueryParams CameraQuery(SCENE_QUERY_STAT(VeyrCameraFraming),false,this);
        if(GetWorld()->SweepSingleByChannel(CameraHit,ProbeOrigin,ProbeEnd,FQuat::Identity,
            CameraBoom->ProbeChannel,FCollisionShape::MakeSphere(CameraBoom->ProbeSize),CameraQuery))
            FramingCandidate=FMath::Min(FramingCandidate,static_cast<float>(FVector::Dist2D(ProbeOrigin,CameraHit.Location)));
    }
    FramingCandidate=FMath::Clamp(FramingCandidate,80.f,Arm);
    if(VisualClock<=DeltaSeconds*1.5f)CameraFramingArm=FramingCandidate;
    else if(FramingCandidate<CameraFramingArm)
    {
        CameraFramingArm=FramingCandidate;CameraObstructionHold=.20f;
    }
    else
    {
        CameraObstructionHold=FMath::Max(0.f,CameraObstructionHold-DeltaSeconds);
        if(CameraObstructionHold<=0.f)
            CameraFramingArm=FMath::FInterpConstantTo(CameraFramingArm,FramingCandidate,DeltaSeconds,220.f);
    }
    CameraFramingArm=FMath::Min(CameraFramingArm,Arm);
    const float PivotAboveFeet=FMath::Lerp(FMath::Min(187.f,CameraFramingArm*.27f),
        FMath::Min(375.f,CameraFramingArm*.24f),FlightCameraBlend);
    CameraBoom->SetRelativeLocation(FVector(0,0,PivotAboveFeet-GetCapsuleComponent()->GetScaledCapsuleHalfHeight()));
    if (!Controller) { RestoreCameraOcclusion(); return; }

    // Read the actual static play surface, excluding both combatants. This is
    // a view constraint only: never move the pawn or bypass spring-arm collision.
    FHitResult FloorHit;
    FCollisionQueryParams FloorQuery(SCENE_QUERY_STAT(VeyrCameraFloor),false,this);
    if(IsValid(Boss))FloorQuery.AddIgnoredActor(Boss);
    if(GetWorld()->LineTraceSingleByChannel(FloorHit,Feet+FVector(0,0,60),Feet-FVector(0,0,5000),ECC_Visibility,FloorQuery))
        CameraFloorZ=FloorHit.ImpactPoint.Z;
    else if(IsGrounded())CameraFloorZ=Feet.Z;
    const float PivotZ=CameraBoom->GetComponentLocation().Z;
    int32 ViewWidth=0,ViewHeight=0;
    if(APlayerController* Player=Cast<APlayerController>(Controller))Player->GetViewportSize(ViewWidth,ViewHeight);
    const float Aspect=ViewHeight>0?float(ViewWidth)/ViewHeight:FMath::Max(.1f,CombatCamera->AspectRatio);
    const float VerticalTangent=FMath::Tan(FMath::DegreesToRadians(CombatCamera->FieldOfView*.5f))/Aspect;
    // Leave 30px above the boss-name band for camera-view-cache timing and toes.
    const float BootRatio=(600.f/720.f*2.f-1.f)*VerticalTangent;
    const float SocketZ=CameraBoom->SocketOffset.Z;
    const float FloorSocketZ=SocketZ*FMath::Clamp(CameraFramingArm/Arm,0.f,1.f);
    auto SafePitch=[&](float Pitch)
    {
        const float Radians=FMath::DegreesToRadians(Pitch),S=FMath::Sin(Radians),C=FMath::Cos(Radians);
        // A collision hit also shortens the socket offset. Count only its
        // compressed fraction for floor clearance, but its full height for
        // the conservative boot-framing bound below.
        // During flight the resolved arm can extend before the conservative
        // framing allowance catches up. An upward view gets lower as the arm
        // grows: constrain floor clearance with the full requested arm then.
        const float FloorArm=S>0.f?Arm:CameraFramingArm;
        const float CameraZ=PivotZ-FloorArm*S+FloorSocketZ*C;
        const float FootDepth=CameraFramingArm-PivotAboveFeet*S;
        const float FootBelowView=PivotAboveFeet*C+SocketZ;
        // Keep a small integration margin above the 225cm resolved-view guard.
        return CameraZ>=CameraFloorZ+230.f&&FootDepth>1.f&&FootBelowView/FootDepth<=BootRatio;
    };
    float Low=-55.f,High=45.f;
    for(int32 I=0;I<16;++I)
    {
        const float Middle=(Low+High)*.5f;
        if(SafePitch(Middle))Low=Middle;else High=Middle;
    }
    CameraPitchCeiling=Low;
    const bool bLock=bLockedOn&&bHasBoss;
    // Controller rotation already has an explicit bounded smoothing path.
    // A second rotational lag can retain an unsafe upward view during collapse.
    CameraBoom->bEnableCameraRotationLag=false;
    if (bLock)
    {
        const bool bHeadApproach=Boss->State==EVeyrDragonState::Buckle||Boss->State==EVeyrDragonState::Collapse||Boss->IsHeadExposed();
        const float HeadWeight=bHeadApproach?1.f:FMath::Lerp(FarBlend,1.f,FlightCameraBlend);
        LockHeadBlend=FMath::FInterpTo(LockHeadBlend,HeadWeight,DeltaSeconds,4.f);
        const FVector GroundFocus(Boss->GetActorLocation().X,Boss->GetActorLocation().Y,CameraFloorZ+FMath::Lerp(150.f,350.f,FlightCameraBlend));
        FVector HeadRoute=Boss->GetHeadLocation();
        // Follow the route toward the crown in XY, but never chase the standing
        // skull's height while the buckle/collapse is only beginning.
        HeadRoute.Z=FMath::Min(HeadRoute.Z,CameraFloorZ+(bHeadApproach?190.f:FMath::Lerp(400.f,1400.f,FlightCameraBlend)));
        const FVector Focus=FMath::Lerp(GroundFocus,HeadRoute,LockHeadBlend);
        const FVector ToFocus=Focus-CameraBoom->GetComponentLocation();
        FRotator Current=Controller->GetControlRotation().GetNormalized(),Desired=Current;
        if(ToFocus.Size2D()>(bHeadApproach?60.f:240.f))Desired.Yaw=ToFocus.Rotation().Yaw;
        const float NearBlend=bHeadApproach?1.f:1.f-FarBlend;
        const float LockCeiling=FMath::Min(CameraPitchCeiling,FMath::Lerp(FMath::Lerp(0.f,-16.f,NearBlend),45.f,FlightCameraBlend));
        Desired.Pitch=FMath::Clamp(static_cast<float>(FMath::RadiansToDegrees(FMath::Atan2(ToFocus.Z,
            FMath::Max(300.f,static_cast<float>(ToFocus.Size2D())))))-4.f,-55.f,LockCeiling);
        Desired.Roll=0.f;
        FRotator Smoothed=FMath::RInterpConstantTo(Current,FMath::RInterpTo(Current,Desired,DeltaSeconds,5.f),DeltaSeconds,100.f);
        Smoothed.Pitch=FMath::Clamp(FRotator::NormalizeAxis(Smoothed.Pitch),-55.f,CameraPitchCeiling);
        Controller->SetControlRotation(Smoothed);
    }
    else
    {
        FRotator Look=Controller->GetControlRotation();
        if(bOpeningView)Look.Pitch=0.f;
        Look.Pitch=FMath::Clamp(FRotator::NormalizeAxis(Look.Pitch),-55.f,CameraPitchCeiling);Look.Roll=0.f;
        Controller->SetControlRotation(Look);
    }
    // Record the resolved view as well as CameraFramingArm. Collision still
    // owns the final camera position, including an unavoidable initial overlap.
    CameraFloorClearance=CombatCamera->GetComponentLocation().Z-CameraFloorZ;
    UpdateCameraOcclusion(DeltaSeconds);
}

void AVeyrKnight::RestoreCameraOcclusion()
{
    if(IsValid(Boss))Boss->SetViewOcclusion(FVector::ZeroVector,FVector::ZeroVector,false);
    if (APlayerController* Player = OcclusionController.Get())
        for (const auto& Pair : CameraHiddenParts) Player->HiddenPrimitiveComponents.Remove(Pair.Key);
    CameraHiddenParts.Empty();
    OcclusionController.Reset();
    CameraHiddenProxyParts = 0;
}

void AVeyrKnight::UpdateCameraOcclusion(float DeltaSeconds)
{
    CameraResolvedDistance = FVector::Distance(CameraBoom->GetComponentLocation(), CombatCamera->GetComponentLocation());
    if (CameraResolvedDistance < 180.f) CameraSeverelyCompressedSeconds += DeltaSeconds;
    APlayerController* Player = Cast<APlayerController>(Controller);
    if (Player != OcclusionController.Get()) RestoreCameraOcclusion();
    if (!Player || !Player->IsLocalController() || !IsValid(Boss)) { RestoreCameraOcclusion(); return; }
    OcclusionController = Player;
    if(Boss->bUsingCustomuseVisual)
    {
        for(const auto& Pair:CameraHiddenParts)Player->HiddenPrimitiveComponents.Remove(Pair.Key);
        CameraHiddenParts.Empty();CameraHiddenProxyParts=0;
        const FVector Chest=GetFootLocation()+FVector(0,0,160.f);
        const FVector Focus=Boss->IsHeadExposed()?FMath::Lerp(Chest,Boss->GetHeadLocation(),.8f):Chest;
        Boss->SetViewOcclusion(CombatCamera->GetComponentLocation(),Focus,true);
        return;
    }

    // Temporary proxy-only visibility aid. Hide individual intersecting pieces
    // in this player's view; keep collisions, danger indicators and every
    // other view unchanged. Final Customuse art needs its own material
    // fade/outline treatment and a fresh visual acceptance pass.
    for (auto& Pair : CameraHiddenParts) Pair.Value -= DeltaSeconds;
    const FVector CameraLocation = CombatCamera->GetComponentLocation();
    const FVector Foot = GetFootLocation();
    const FVector Side = CombatCamera->GetRightVector() * 28.f;
    const FVector Samples[] = {Foot + FVector(0,0,215), Foot + FVector(0,0,145) + Side,
        Foot + FVector(0,0,145) - Side, Foot + FVector(0,0,65)};
    TInlineComponentArray<UStaticMeshComponent*> Parts;
    Boss->GetComponents(Parts);
    for (UStaticMeshComponent* Part : Parts)
    {
        if (!Part || !Part->GetStaticMesh() || !Part->GetName().StartsWith(TEXT("TEMP_"))) continue;
        const FTransform Transform = Part->GetComponentTransform();
        const FVector Start = Transform.InverseTransformPosition(CameraLocation);
        const float Margin = 12.f / FMath::Max(.01f, static_cast<float>(Transform.GetScale3D().GetAbsMin()));
        const FBox Box = Part->GetStaticMesh()->GetBoundingBox().ExpandBy(Margin);
        bool bOccludes = Box.IsInsideOrOn(Start);
        for (const FVector& Sample : Samples)
        {
            const FVector End = Transform.InverseTransformPosition(Sample);
            bOccludes |= FMath::LineBoxIntersection(Box, Start, End, End - Start);
        }
        if (!bOccludes) continue;
        const TWeakObjectPtr<UPrimitiveComponent> Key(Part);
        // Never take ownership of a component another system already hid.
        if (!CameraHiddenParts.Contains(Key) && Player->HiddenPrimitiveComponents.Contains(Key)) continue;
        Player->HiddenPrimitiveComponents.AddUnique(Key);
        CameraHiddenParts.FindOrAdd(Key) = .12f;
    }
    for (auto It = CameraHiddenParts.CreateIterator(); It; ++It)
    {
        if (!It.Key().IsValid() || It.Value() <= 0.f)
        {
            Player->HiddenPrimitiveComponents.Remove(It.Key());
            It.RemoveCurrent();
        }
    }
    CameraHiddenProxyParts = CameraHiddenParts.Num();
}

void AVeyrKnight::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
    RestoreCameraOcclusion();
    Super::EndPlay(EndPlayReason);
}

void AVeyrKnight::SetPresentationDiagnostic(const FString& Diagnostic)
{
    if (PresentationDiagnostic == Diagnostic) return;
    PresentationDiagnostic = Diagnostic;
    if (!Diagnostic.IsEmpty()) UE_LOG(LogTemp, Warning, TEXT("VEYR_KNIGHT_PRESENTATION %s"), *Diagnostic);
}

bool AVeyrKnight::ApplyCustomuseVisual(UVeyrVisualDefinition* Definition)
{
    CustomuseVisualDefinition = Definition;
    bApprovedNativeDefinitionActive=Definition&&Definition->GetPathName().Contains(TEXT("/RuntimeApproved/"));
    ClearBlinkEchoes();
    bPreviousBladePoseValid=false;
    bImportedPresentationActive = bRequestedPresentationClipSampled = bPresentationUsingFallback = false;
    RequestedPresentationClip = FailedPresentationClip = NAME_None;
    FailedPresentationReason.Reset();
    bIdleFallbackRejected=false;
    PresentationTransitionClip=NAME_None;
    PresentationPreviousActionElapsed=-1.f;
    bPresentationTransitionActive=false;
    PresentationLowerClip=PresentationTransitionLowerClip=RequestedLowerPresentationClip=NAME_None;
    PresentationLowerWeight=PresentationLowerTime=PresentationLocomotionTime=PresentationRollYaw=0.f;
    if(HealFlaskRoot)HealFlaskRoot->SetVisibility(false,true);
    bHealFlaskVisible=false;
    if (ImportedPresentation)
    {
        ImportedPresentation->SetVisibility(false,true);
        ImportedPresentation->SetHiddenInGame(true,true);
    }
    if (TemporaryVisual) TemporaryVisual->SetVisibility(true,true);
    if (!ImportedPresentation || !Definition)
    {
        SetPresentationDiagnostic(TEXT("Temporary primitive presentation: imported component or definition missing"));
        return false;
    }
    if (!ImportedPresentation->SetVisualDefinition(Definition,false))
    {
        SetPresentationDiagnostic(TEXT("Imported definition rejected; temporary primitives retained: ")+ImportedPresentation->LastError);
        return false;
    }
    bImportedPresentationActive = true;
    UpdateImportedPresentation();
    if (!bImportedPresentationActive || !ImportedPresentation->bPoseEvaluated) return false;
    ImportedPresentation->SetVisibility(true,true);
    ImportedPresentation->SetHiddenInGame(false,true);
    if (TemporaryVisual) TemporaryVisual->SetVisibility(false,true);
    // True means this definition produced an explicit pose, not that every clip
    // exists or that its imported art/animation has passed native acceptance.
    return true;
}

FName AVeyrKnight::SelectDirectionalLocomotion(bool bAllowRun) const
{
    const float Forward=FVector::DotProduct(GetVelocity().GetSafeNormal2D(),GetActorForwardVector());
    if(bLockedOn&&Forward<-.15f)return TEXT("Backpedal");
    if(bTwoHanded)return TEXT("WalkTwoHand");
    if(bAllowRun&&!bWalkModifier&&GetPlanarSpeed()>360.f)return RunAnimationVariant==1?TEXT("RunAlternate"):TEXT("Run");
    return TEXT("Walk");
}

bool AVeyrKnight::GetWeaponSweep(FVector& Base,FVector& Tip)
{
    FTransform Authored;
    if(CustomuseVisualDefinition&&CustomuseVisualDefinition->BoneTargets.Contains(TEXT("weapon_socket")))
    {
        if(!ImportedPresentation->GetBoneTargetWorldTransform(TEXT("weapon_socket"),Authored))return false;
        const FVeyrVisualClip* C=CustomuseVisualDefinition->Clips.Find(RequestedPresentationClip);
        UStaticMesh* Mesh=C?C->WeaponMesh.Get():nullptr;
        if(!Mesh)return false;
        const FBox Box=Mesh->GetBoundingBox();const FVector Size=Box.GetSize();
        const int32 Axis=Size.X>Size.Y?(Size.X>Size.Z?0:2):(Size.Y>Size.Z?1:2);
        const float Near=FMath::Abs(Box.Min[Axis])<FMath::Abs(Box.Max[Axis])?Box.Min[Axis]:Box.Max[Axis];
        const float Far=Near==Box.Min[Axis]?Box.Max[Axis]:Box.Min[Axis];
        FVector A=Box.GetCenter(),B=A;A[Axis]=FMath::Lerp(Near,Far,.28f);B[Axis]=Far;
        Base=Authored.TransformPosition(A);Tip=Authored.TransformPosition(B);return true;
    }
    FTransform Grip;
    if(BoatWeapon&&BoatWeapon->GetStaticMesh()&&CustomuseVisualDefinition&&CustomuseVisualDefinition->BoneTargets.Contains(TEXT("weapon_grip"))&&ImportedPresentation->GetBoneTargetWorldTransform(TEXT("weapon_grip"),Grip))
    {
        // The imported rigid mesh is authored in actual cm with +Z along its
        // blade. Ignore skeletal scale here: the grip location is already world space.
        const FTransform Weapon(Grip.GetRotation(),Grip.GetLocation(),FVector::OneVector);
        Base=Weapon.TransformPosition(FVector(6.2972f,-1.1143f,71.3305f));Tip=Weapon.TransformPosition(FVector(28.7113f,-8.1916f,235.f));
        return true;
    }
    FTransform A,B;
    if(!ImportedPresentation->GetBoneTargetWorldTransform(TEXT("weapon_base"),A)||
       !ImportedPresentation->GetBoneTargetWorldTransform(TEXT("weapon_tip"),B))return false;
    Base=A.GetLocation();Tip=B.GetLocation();return true;
}

void AVeyrKnight::UpdateEquippedWeapon()
{
    if(!BoatWeapon)return;
    if(CustomuseVisualDefinition&&CustomuseVisualDefinition->BoneTargets.Contains(TEXT("weapon_socket")))
    {
        FTransform Authored;const FVeyrVisualClip* C=CustomuseVisualDefinition->Clips.Find(RequestedPresentationClip);
        const bool Valid=bImportedPresentationActive&&bRequestedPresentationClipSampled&&C&&C->WeaponMesh&&
            ImportedPresentation->GetBoneTargetWorldTransform(TEXT("weapon_socket"),Authored);
        if(Valid){BoatWeapon->SetStaticMesh(C->WeaponMesh);BoatWeapon->SetWorldTransform(Authored);}
        BoatWeapon->SetVisibility(Valid&&!bBlinkHidden);bBoatReleased=false;return;
    }
    if(!BoatWeapon->GetStaticMesh())BoatWeapon->SetStaticMesh(LoadObject<UStaticMesh>(nullptr,
        TEXT("/Game/ArtPass/Tripo/BoatGreatsword_v004/SM_BoatGreatsword_v004.SM_BoatGreatsword_v004"),nullptr,LOAD_Quiet|LOAD_NoWarn));
    FTransform Grip;
    const bool Visible=bImportedPresentationActive&&BoatWeapon->GetStaticMesh()&&CustomuseVisualDefinition&&CustomuseVisualDefinition->BoneTargets.Contains(TEXT("weapon_grip"))&&
        ImportedPresentation->GetBoneTargetWorldTransform(TEXT("weapon_grip"),Grip);
    BoatWeapon->SetVisibility(Visible);
    if(!Visible)return;
    if(Action!=EVeyrKnightAction::Dead)bBoatReleased=false;
    if(Action==EVeyrKnightAction::Dead&&ActionElapsed>=.30f)
    {
        if(!bBoatReleased)
        {
            // Preserve the last held pose at release, then let the visible
            // oversized prop fall beside the body. It never follows the dying
            // hand through the ground or changes combat/corpse collision.
            bBoatReleased=true;BoatReleaseTime=ActionElapsed;
            BoatReleaseStart=BoatWeapon->GetComponentTransform();
            const FQuat RestRotation=FRotationMatrix::MakeFromZY(GetActorForwardVector(),FVector::UpVector).ToQuat();
            FVector Rest=GetActorLocation()+GetActorRightVector()*250.f+GetActorForwardVector()*70.f;
            float FloorZ=GetActorLocation().Z-GetCapsuleComponent()->GetScaledCapsuleHalfHeight();
            FHitResult Hit;FCollisionQueryParams Query(SCENE_QUERY_STAT(VeyrDroppedWeaponFloor),false,this);
            if(IsValid(Boss))Query.AddIgnoredActor(Boss);
            if(GetWorld()->LineTraceSingleByChannel(Hit,Rest+FVector(0,0,400),Rest-FVector(0,0,2000),ECC_Visibility,Query))FloorZ=Hit.ImpactPoint.Z;
            const FBox Bounds=BoatWeapon->GetStaticMesh()->GetBoundingBox();
            float MinZ=TNumericLimits<float>::Max();
            for(int32 X=0;X<2;++X)for(int32 Y=0;Y<2;++Y)for(int32 Z=0;Z<2;++Z)
                MinZ=FMath::Min(MinZ,float(RestRotation.RotateVector(FVector(X?Bounds.Max.X:Bounds.Min.X,Y?Bounds.Max.Y:Bounds.Min.Y,Z?Bounds.Max.Z:Bounds.Min.Z)).Z));
            Rest.Z=FloorZ+3.f-MinZ;
            BoatReleaseRest=FTransform(RestRotation,Rest,FVector::OneVector);
        }
        const float T=FMath::Clamp((ActionElapsed-BoatReleaseTime)/.72f,0.f,1.f);
        const float RotationT=FMath::SmoothStep(0.f,1.f,T);
        FVector Location=FMath::Lerp(BoatReleaseStart.GetLocation(),BoatReleaseRest.GetLocation(),T);
        Location.Z+=65.f*FMath::Sin(T*PI);
        BoatWeapon->SetWorldTransform(FTransform(FQuat::Slerp(BoatReleaseStart.GetRotation(),BoatReleaseRest.GetRotation(),RotationT),Location,FVector::OneVector));
        return;
    }
    BoatWeapon->SetWorldTransform(FTransform(Grip.GetRotation(),Grip.GetLocation(),FVector::OneVector));
}

void AVeyrKnight::UpdateImportedPresentation(float DeltaSeconds)
{
    if(!bImportedPresentationActive||!ImportedPresentation||!CustomuseVisualDefinition)return;
    const bool Moving=Action==EVeyrKnightAction::Ready&&IsGrounded()&&GetPlanarSpeed()>8.f&&!bLateralDodgeBlocked;
    FName Clip=Action==EVeyrKnightAction::Ready?(Moving?SelectDirectionalLocomotion(true):(bTwoHanded?FName(TEXT("IdleTwoHand")):FName(TEXT("Idle")))):ActionPresentationClip;
    float Time=Action==EVeyrKnightAction::Ready?VisualClock:ActionElapsed;
    if(Moving)
    {
        const float Nominal=VisualClipSpeed(Clip);
        if(Nominal<=0.f){bRequestedPresentationClipSampled=false;bPresentationUsingFallback=true;SetPresentationDiagnostic(TEXT("Missing locomotion speed: ")+Clip.ToString());return;}
        if(LastLocomotionClip!=Clip)
        {
            const float OldDuration=VisualClipDuration(LastLocomotionClip,1.f),NewDuration=VisualClipDuration(Clip,1.f);
            PresentationLocomotionTime=FMath::Fmod(PresentationLocomotionTime,OldDuration)/OldDuration*NewDuration;
            LastLocomotionClip=Clip;
        }
        PresentationLocomotionTime+=DeltaSeconds*GetPlanarSpeed()/Nominal;Time=PresentationLocomotionTime;
    }
    bWasRunning=Moving&&(Clip==FName(TEXT("Run"))||Clip==FName(TEXT("RunAlternate")));
    PresentationLowerClip=PresentationTransitionLowerClip=RequestedLowerPresentationClip=NAME_None;
    PresentationLowerWeight=PresentationLowerTime=PresentationJumpPhase=0.f;
    const float DesiredRollYaw=IsRollPrefix()?FMath::FindDeltaAngleDegrees(GetActorRotation().Yaw,RollDirection.Rotation().Yaw):0.f;
    PresentationRollYaw=FMath::RInterpTo(FRotator(0,PresentationRollYaw,0),FRotator(0,DesiredRollYaw,0),DeltaSeconds,20.f).Yaw;
    ImportedPresentation->SetRelativeRotation(FQuat(FVector::UpVector,FMath::DegreesToRadians(PresentationRollYaw))*CustomuseVisualDefinition->MeshRelativeTransform.GetRotation());
    RequestedPresentationClip=Clip;
    const bool Restarted=Action!=EVeyrKnightAction::Ready&&PresentationPreviousActionElapsed>=0.f&&ActionElapsed<PresentationPreviousActionElapsed;
    if(Clip!=PresentationTransitionClip||Restarted)
    {
        const bool PreservePrefix=bPreserveRollPrefix&&PresentationTransitionClip==FName(TEXT("Roll"))&&Clip==FName(TEXT("RollAttack"));
        bPresentationTransitionActive=!PreservePrefix&&!PresentationTransitionClip.IsNone()&&ImportedPresentation->bPoseEvaluated&&ImportedPresentation->BeginTransition();
        PresentationTransitionStarted=VisualClock;PresentationTransitionClip=Clip;bPreserveRollPrefix=false;
    }
    const float BlendSeconds=GripTransitionRemaining>0.f?.28f:Action==EVeyrKnightAction::Guard?.06f:.10f;
    const float Alpha=bPresentationTransitionActive?FMath::Clamp((VisualClock-PresentationTransitionStarted)/BlendSeconds,0.f,1.f):1.f;
    const bool Sampled=ImportedPresentation->SampleClipTimeBlended(Clip,Time*VisualClipPlayRate(Clip),Alpha);
    if(Alpha>=1.f)bPresentationTransitionActive=false;
    bRequestedPresentationClipSampled=Sampled;bPresentationUsingFallback=!Sampled;
    PresentationPreviousActionElapsed=Action==EVeyrKnightAction::Ready?-1.f:ActionElapsed;
    bBlinkHidden=IsBlinkAction()&&!IsTerminal()&&ActionElapsed>=.18f&&ActionElapsed<.34f;
    ImportedPresentation->SetVisibility(!bBlinkHidden,true);ImportedPresentation->SetHiddenInGame(bBlinkHidden,true);
    if(Sampled){SetPresentationDiagnostic(FString());return;}
    SetPresentationDiagnostic(TEXT("Native approved clip evaluation failed: ")+Clip.ToString()+TEXT("; ")+ImportedPresentation->LastError);
    // Keep failures explicit and harmless: never substitute an attack or deal fallback damage.
}

FVector AVeyrKnight::RootTranslationAt(float Seconds) const
{
    const FVeyrVisualClip* C=CustomuseVisualDefinition?CustomuseVisualDefinition->Clips.Find(ActionPresentationClip):nullptr;
    if(!C||C->RootTranslationSamplesCm.IsEmpty()||C->RootSampleRate<=0.f)return FVector::ZeroVector;
    const float Frame=FMath::Clamp(Seconds*VisualClipPlayRate(ActionPresentationClip)*C->RootSampleRate,0.f,float(C->RootTranslationSamplesCm.Num()-1));
    const int32 A=FMath::FloorToInt(Frame),B=FMath::Min(A+1,C->RootTranslationSamplesCm.Num()-1);
    return FMath::Lerp(C->RootTranslationSamplesCm[A],C->RootTranslationSamplesCm[B],Frame-A);
}
void AVeyrKnight::ClearBlinkEchoes()
{
    for(int32 I=0;I<2;++I)
    {
        bBlinkEchoCaptured[I]=false;
        if(BlinkEchoBodies.IsValidIndex(I))BlinkEchoBodies[I]->SetVisibility(false);
        if(BlinkEchoWeapons.IsValidIndex(I))BlinkEchoWeapons[I]->SetVisibility(false);
    }
}
bool AVeyrKnight::CaptureBlinkEcho(int32 Index,float SourceSeconds)
{
    if(!ImportedPresentation||!ImportedPresentation->GetSkeletalMeshAsset()||!CustomuseVisualDefinition)return false;
    if(!BlinkEchoMaterial)BlinkEchoMaterial=LoadObject<UMaterialInterface>(nullptr,TEXT("/Game/ArtPass/Materials/M_BlinkAfterimage.M_BlinkAfterimage"),nullptr,LOAD_Quiet|LOAD_NoWarn);
    if(!BlinkEchoMaterial){BlinkVFXDiagnostic=TEXT("Approved blink afterimage material unavailable");return false;}
    const FVeyrVisualClip* C=CustomuseVisualDefinition->Clips.Find(ActionPresentationClip);
    if(!C||!C->WeaponMesh)return false;
    const float RestoreSeconds=ImportedPresentation->CurrentTrimmedSeconds,Alpha=ImportedPresentation->CurrentTransitionAlpha;
    if(!ImportedPresentation->SampleClipTimeBlended(ActionPresentationClip,SourceSeconds,Alpha))return false;
    auto* Echo=BlinkEchoBodies[Index].Get();auto* WeaponEcho=BlinkEchoWeapons[Index].Get();
    Echo->SetSkinnedAssetAndUpdate(ImportedPresentation->GetSkeletalMeshAsset(),true);
    Echo->CopyPoseFromSkeletalComponent(ImportedPresentation);Echo->RefreshBoneTransforms();
    // Mesh roots are in-place. Freeze the echo at the corresponding swept actor position,
    // not at the actor's later transit position if one slow frame crossed the visibility event.
    FVector Offset=RootTranslationAt(SourceSeconds)-RootTranslationAt(ActionElapsed);Offset.Z=0.f;
    Offset=GetActorQuat().RotateVector(CustomuseVisualDefinition->MeshRelativeTransform.TransformVector(Offset));Offset.Z=0.f;
    if(bActionRootBlocked)Offset=FVector::ZeroVector;
    FTransform World=ImportedPresentation->GetComponentTransform();World.AddToTranslation(Offset);Echo->SetWorldTransform(World);
    FTransform Weapon;const bool HasWeapon=ImportedPresentation->GetBoneTargetWorldTransform(TEXT("weapon_socket"),Weapon);
    if(HasWeapon){Weapon.AddToTranslation(Offset);WeaponEcho->SetStaticMesh(C->WeaponMesh);WeaponEcho->SetWorldTransform(Weapon);}
    if(!BlinkEchoMaterials[Index])BlinkEchoMaterials[Index]=UMaterialInstanceDynamic::Create(BlinkEchoMaterial,this);
    auto* Material=BlinkEchoMaterials[Index].Get();
    for(int32 Slot=0;Slot<Echo->GetNumMaterials();++Slot)Echo->SetMaterial(Slot,Material);
    for(int32 Slot=0;Slot<WeaponEcho->GetNumMaterials();++Slot)WeaponEcho->SetMaterial(Slot,Material);
    Material->SetVectorParameterValue(TEXT("Tint"),FLinearColor(.08f,.32f,.55f));
    Material->SetScalarParameterValue(TEXT("Opacity"),Index==0?.14f:.10f);
    Echo->SetVisibility(true);WeaponEcho->SetVisibility(HasWeapon);
    bBlinkEchoCaptured[Index]=true;BlinkEchoStarted[Index]=ActionElapsed;++BlinkEchoCaptures;
    const bool Restored=ImportedPresentation->SampleClipTimeBlended(ActionPresentationClip,RestoreSeconds,Alpha);
    BlinkVFXDiagnostic=Restored?FString():TEXT("Could not restore live pose after afterimage capture");
    return Restored;
}
void AVeyrKnight::UpdateBlinkEchoes()
{
    if(!IsBlinkAction()||IsTerminal()){ClearBlinkEchoes();return;}
    if(!bBlinkEchoCaptured[0]&&ActionElapsed>=.16f&&ActionElapsed<.36f)CaptureBlinkEcho(0,.16f);
    if(!bBlinkEchoCaptured[1]&&ActionElapsed>=.34f&&ActionElapsed<.46f)CaptureBlinkEcho(1,.34f);
    for(int32 I=0;I<2;++I)
    {
        if(!bBlinkEchoCaptured[I])continue;
        const float Age=ActionElapsed-BlinkEchoStarted[I],Life=I==0?.20f:.09f;
        const bool Visible=Age<Life;
        BlinkEchoBodies[I]->SetVisibility(Visible);BlinkEchoWeapons[I]->SetVisibility(Visible);
        if(BlinkEchoMaterials[I])BlinkEchoMaterials[I]->SetScalarParameterValue(TEXT("Opacity"),(I==0?.14f:.10f)*FMath::Clamp(1.f-Age/Life,0.f,1.f));
    }
}

void AVeyrKnight::ApplyAuthoredRootMotion(float PreviousSeconds,float NewSeconds)
{
    if(Action==EVeyrKnightAction::Ready||Action==EVeyrKnightAction::Guard||Action==EVeyrKnightAction::Heal||
       Action==EVeyrKnightAction::Roll||Action==EVeyrKnightAction::Dead||Action==EVeyrKnightAction::Stagger)return;
    const FVeyrVisualClip* C=CustomuseVisualDefinition?CustomuseVisualDefinition->Clips.Find(ActionPresentationClip):nullptr;
    if(!C||!C->bRootMotionRemoved||C->RootTranslationSamplesCm.Num()<2||C->RootSampleRate<=0.f)return;
    if(Action==EVeyrKnightAction::RollAttack){PreviousSeconds=FMath::Max(.78f,PreviousSeconds);if(NewSeconds<=PreviousSeconds)return;}
    FVector Delta=RootTranslationAt(NewSeconds)-RootTranslationAt(PreviousSeconds);Delta.Z=0.f;
    Delta=CustomuseVisualDefinition->MeshRelativeTransform.TransformVector(Delta);
    Delta=GetActorQuat().RotateVector(Delta);Delta.Z=0.f;
    if(Delta.IsNearlyZero())return;
    const FVector Before=GetActorLocation();FHitResult Hit;
    GetCharacterMovement()->SafeMoveUpdatedComponent(Delta,GetActorQuat(),true,Hit);
    if(Hit.IsValidBlockingHit()){++RootMotionBlockedCount;bActionRootBlocked=true;}
    ActionRootTravelCm+=(GetActorLocation()-Before).Size2D();
}

void AVeyrKnight::ResolveAttackWindows(float PreviousSeconds)
{
    CurrentDamageWindow=INDEX_NONE;
    if(!bImportedPresentationActive||!bRequestedPresentationClipSampled||!IsValid(Boss))return;
    const FVeyrVisualClip* C=CustomuseVisualDefinition->Clips.Find(ActionPresentationClip);
    if(!C)return;
    const float Rate=VisualClipPlayRate(ActionPresentationClip);
    TArray<FVector2D> Windows=C->DamageWindows;
    for(FVector2D& Window:Windows)Window/=Rate;
    if(Windows.IsEmpty())
    {
        // Legacy definitions retain one authored contact; new imports must supply windows.
        const float Impact=C->ImpactSeconds>=0.f?(C->ImpactSeconds-C->StartSeconds)/Rate:ActionDuration*.5f;
        Windows.Add(FVector2D(FMath::Max(0.f,Impact-.06f),FMath::Min(ActionDuration,Impact+.08f)));
    }
    const float Alpha=ImportedPresentation->CurrentTransitionAlpha;
    bool Resampled=false;
    auto SampleBlade=[&](float Seconds,FVector& Base,FVector& Tip)
    {
        Resampled=true;
        if(!ImportedPresentation->SampleClipTimeBlended(ActionPresentationClip,Seconds*Rate,Alpha)||!GetWeaponSweep(Base,Tip))return false;
        if(C->bRootMotionRemoved&&!bActionRootBlocked)
        {
            FVector Offset=RootTranslationAt(Seconds)-RootTranslationAt(ActionElapsed);Offset.Z=0.f;
            Offset=GetActorQuat().RotateVector(CustomuseVisualDefinition->MeshRelativeTransform.TransformVector(Offset));Offset.Z=0.f;
            Base+=Offset;Tip+=Offset;
        }
        return true;
    };
    for(int32 I=0;I<Windows.Num();++I)
    {
        const float Start=Windows[I].X,End=Windows[I].Y;
        if(ContactedDamageWindows.Contains(I)||ActionElapsed<Start||PreviousSeconds>End)continue;
        CurrentDamageWindow=I;
        FVector A,B,CurrA,CurrB;
        const float From=FMath::Max(Start,PreviousSeconds),To=FMath::Min(End,ActionElapsed);
        const int32 Steps=FMath::Clamp(FMath::CeilToInt((To-From)*90.f),1,12);
        if(!SampleBlade(From,A,B))continue;
        for(int32 Step=1;Step<=Steps;++Step)
        {
            if(!SampleBlade(FMath::Lerp(From,To,float(Step)/Steps),CurrA,CurrB))break;
            const bool Heavy=Action==EVeyrKnightAction::HeavyAttack||(Action==EVeyrKnightAction::Combo&&I>=2);
            if(Boss->ReceiveSwordSweep(A,B,CurrA,CurrB,Heavy,ActionSwingBase+I,bSwingTwoHanded?1.55f:1.f))
            {
                ContactedDamageWindows.Add(I);++SuccessfulStrikeWindows;bContactSent=true;
                UE_LOG(LogTemp,Display,TEXT("VEYR_STRIKE_WINDOW clip=%s window=%d time=%.3f heavy=%d"),*ActionPresentationClip.ToString(),I,ActionElapsed,Heavy);break;
            }
            A=CurrA;B=CurrB;
        }
    }
    if(Resampled)bRequestedPresentationClipSampled=ImportedPresentation->SampleClipTimeBlended(ActionPresentationClip,FMath::Min(ActionElapsed,ActionDuration)*Rate,Alpha);

}

void AVeyrKnight::UpdateHealFlask()
{
    bHealFlaskVisible=false;
    if(ApprovedHealCup)ApprovedHealCup->SetVisibility(false);
    if(HealFlaskRoot)HealFlaskRoot->SetVisibility(false,true);
    if(Action!=EVeyrKnightAction::Heal||!bImportedPresentationActive||!bRequestedPresentationClipSampled)
    {
        HealFlaskDiagnostic.Reset();return;
    }
    if(CustomuseVisualDefinition&&CustomuseVisualDefinition->BoneTargets.Contains(TEXT("cup_socket")))
    {
        FTransform Cup;UStaticMesh* Mesh=CustomuseVisualDefinition->Props.FindRef(TEXT("Cup"));
        const bool Valid=Mesh&&ImportedPresentation->GetBoneTargetWorldTransform(TEXT("cup_socket"),Cup);
        const bool Visible=Valid&&Cup.GetScale3D().GetAbsMax()>.001f&&!bBlinkHidden;
        if(Valid){ApprovedHealCup->SetStaticMesh(Mesh);ApprovedHealCup->SetWorldTransform(Cup);}
        ApprovedHealCup->SetVisibility(Visible);bHealFlaskVisible=Visible;
        HealFlaskDiagnostic=Valid?FString():TEXT("Approved cup mesh/socket unavailable");return;
    }
    FTransform Grip,Spout;
    FString Error;
    if(!HealFlaskRoot||HealFlaskParts.Num()!=3)Error=TEXT("Original Ember Draught primitives unavailable");
    else if(!ImportedPresentation->GetBoneTargetWorldTransform(TEXT("flask_grip"),Grip)||
        !ImportedPresentation->GetBoneTargetWorldTransform(TEXT("flask_spout"),Spout))
        Error=TEXT("Ember Draught requires evaluated flask_grip/LeftHand and flask_spout targets: ")+ImportedPresentation->LastError;
    else
    {
        const FVector Axis=Spout.GetLocation()-Grip.GetLocation();
        const float Length=Axis.Size();
        if(!FMath::IsFinite(Length)||Length<1.f||Length>40.f)Error=TEXT("Ember Draught grip-to-spout distance is outside [1,40]cm");
        else
        {
            // Capsule-attached prop receives an already-scaled world distance;
            // never inherit the skeletal mesh's import scale a second time.
            HealFlaskRoot->SetWorldLocationAndRotation(Grip.GetLocation(),FRotationMatrix::MakeFromZ(Axis).ToQuat());
            HealFlaskRoot->SetWorldScale3D(FVector(Length));
            HealFlaskRoot->SetVisibility(true,true);bHealFlaskVisible=true;
        }
    }
    if(Error!=HealFlaskDiagnostic&&!Error.IsEmpty())UE_LOG(LogTemp,Warning,TEXT("VEYR_HEAL_FLASK %s"),*Error);
    HealFlaskDiagnostic=Error;
}

void AVeyrKnight::UpdateTemporaryPresentation(float DeltaSeconds)
{
    if (!TemporaryVisual || bImportedPresentationActive) return;
    // Explicit proxy pose cues only: no authored animation asset or Customuse claim.
    FRotator BodyRotation = FRotator::ZeroRotator;
    if (Action == EVeyrKnightAction::Roll) BodyRotation.Pitch = FMath::Clamp(ActionElapsed / .58f, 0.f, 1.f) * 360.f;
    else if (IsDead()) BodyRotation.Roll = 86.f * FMath::SmoothStep(0.f, 1.f, ActionElapsed / 1.5f);
    else if (Action == EVeyrKnightAction::Stagger) BodyRotation.Pitch = -12.f * FMath::Sin(FMath::Clamp(ActionElapsed / FMath::Max(.01f, ActionDuration), 0.f, 1.f) * PI);
    TemporaryVisual->SetRelativeRotation(BodyRotation);
    if (SwordPivot)
    {
        FRotator SwordRotation(-12,0,-10);
        if (Action == EVeyrKnightAction::LightAttack || Action == EVeyrKnightAction::HeavyAttack)
        {
            const bool bHeavy = Action == EVeyrKnightAction::HeavyAttack;
            const float Contact = bHeavy ? .55f : .23f;
            const FRotator Gather = bHeavy ? FRotator(-55,-15,0) : FRotator(-25,-80,-20);
            const FRotator Strike = bHeavy ? FRotator(115,0,0) : FRotator(90,25,15);
            if (ActionElapsed < Contact * .72f) SwordRotation = FMath::Lerp(FRotator(-12,0,-10), Gather, ActionElapsed / (Contact * .72f));
            else if (ActionElapsed < Contact) SwordRotation = FMath::Lerp(Gather, Strike, (ActionElapsed - Contact * .72f) / (Contact * .28f));
            else SwordRotation = FMath::Lerp(Strike, FRotator(-12,0,-10), FMath::Clamp((ActionElapsed - Contact) / (ActionDuration - Contact), 0.f, 1.f));
        }
        else if (Action == EVeyrKnightAction::Guard) SwordRotation = FRotator(55,-30,65);
        else if (Action == EVeyrKnightAction::Heal) SwordRotation = FRotator(145,0,0);
        SwordPivot->SetRelativeRotation(SwordRotation);
    }
    const float Gait = Action == EVeyrKnightAction::Ready ? FMath::Sin(VisualClock * 12.f) * FMath::Clamp(GetPlanarSpeed() / 580.f, 0.f, 1.f) * 16.f : 0.f;
    if (LeftLeg) LeftLeg->SetRelativeRotation(FRotator(Gait,0,0));
    if (RightLeg) RightLeg->SetRelativeRotation(FRotator(-Gait,0,0));
}

void AVeyrKnight::SetReplayInput(const FVector& WorldMove, bool bLight, bool bHeavy, bool bRoll, bool bHeal, bool bJump, bool bGuard)
{
    bReplayControlled = true; ReplayMove = FVector(WorldMove.X, WorldMove.Y, 0).GetClampedToMaxSize(1.f);
    bReplayLight |= bLight; bReplayHeavy |= bHeavy; bReplayRoll |= bRoll; bReplayHeal |= bHeal; bReplayJump = false; // Legacy replay jump input is intentionally ignored.
    bReplayGuard = bGuard;
}
void AVeyrKnight::ClearReplayInput()
{
    bReplayControlled = false; ReplayMove = FVector::ZeroVector;
    if (bReplayJumpHeld) StopJumping();
    bReplayJumpHeld = false;
    bReplayLight = bReplayHeavy = bReplayRoll = bReplayHeal = bReplayJump = bReplayGuard = false;
    SetGuard(false);
}
void AVeyrKnight::RestartIfTerminal()
{
    if (!IsTerminal()) return;
    const FString Level = UGameplayStatics::GetCurrentLevelName(this, true);
    if (!Level.IsEmpty()) UGameplayStatics::OpenLevel(this, FName(*Level));
}

void AVeyrKnight::SetupPlayerInputComponent(UInputComponent* Input)
{
    Super::SetupPlayerInputComponent(Input);
    Input->BindKey(EKeys::W, IE_Pressed, this, &AVeyrKnight::ForwardPressed); Input->BindKey(EKeys::W, IE_Released, this, &AVeyrKnight::ForwardReleased);
    Input->BindKey(EKeys::S, IE_Pressed, this, &AVeyrKnight::BackPressed); Input->BindKey(EKeys::S, IE_Released, this, &AVeyrKnight::BackReleased);
    Input->BindKey(EKeys::A, IE_Pressed, this, &AVeyrKnight::LeftPressed); Input->BindKey(EKeys::A, IE_Released, this, &AVeyrKnight::LeftReleased);
    Input->BindKey(EKeys::D, IE_Pressed, this, &AVeyrKnight::RightPressed); Input->BindKey(EKeys::D, IE_Released, this, &AVeyrKnight::RightReleased);
    Input->BindKey(EKeys::J, IE_Pressed, this, &AVeyrKnight::LightPressed); Input->BindKey(EKeys::LeftMouseButton, IE_Pressed, this, &AVeyrKnight::CaptureMouseOrAttack);
    Input->BindKey(EKeys::K, IE_Pressed, this, &AVeyrKnight::HeavyPressed);
    Input->BindKey(EKeys::E, IE_Pressed, this, &AVeyrKnight::GripPressed);
    Input->BindKey(EKeys::C, IE_Pressed, this, &AVeyrKnight::ComboPressed);
    Input->BindKey(EKeys::V, IE_Pressed, this, &AVeyrKnight::VariantPressed);
    Input->BindKey(EKeys::LeftControl, IE_Pressed, this, &AVeyrKnight::WalkModifierPressed);
    Input->BindKey(EKeys::LeftControl, IE_Released, this, &AVeyrKnight::WalkModifierReleased);
    Input->BindKey(EKeys::LeftShift, IE_Pressed, this, &AVeyrKnight::RollPressed);
    Input->BindKey(EKeys::F, IE_Pressed, this, &AVeyrKnight::GuardPressed); Input->BindKey(EKeys::F, IE_Released, this, &AVeyrKnight::GuardReleased);
    Input->BindKey(EKeys::RightMouseButton, IE_Pressed, this, &AVeyrKnight::GuardPressed); Input->BindKey(EKeys::RightMouseButton, IE_Released, this, &AVeyrKnight::GuardReleased);
    Input->BindKey(EKeys::Q, IE_Pressed, this, &AVeyrKnight::HealPressed); Input->BindKey(EKeys::Tab, IE_Pressed, this, &AVeyrKnight::LockPressed);
    Input->BindKey(EKeys::R, IE_Pressed, this, &AVeyrKnight::RestartIfTerminal);
    Input->BindKey(EKeys::Escape, IE_Pressed, this, &AVeyrKnight::ReleaseMouse).bExecuteWhenPaused = true;
    Input->BindKey(EKeys::Enter, IE_Pressed, this, &AVeyrKnight::BeginControlFromKeyboard);
    Input->BindKey(EKeys::MouseScrollUp, IE_Pressed, this, &AVeyrKnight::ZoomIn); Input->BindKey(EKeys::MouseScrollDown, IE_Pressed, this, &AVeyrKnight::ZoomOut);
    Input->BindAxisKey(EKeys::MouseX, this, &AVeyrKnight::LookYaw); Input->BindAxisKey(EKeys::MouseY, this, &AVeyrKnight::LookPitch);
}
void AVeyrKnight::UpdateMouseCapture()
{
    APlayerController* Player = Cast<APlayerController>(Controller);
    if (!Player || !Player->IsLocalController()) return;
    if (MouseInputController.Get() != Player)
    {
        MouseInputController = Player;
        ReleaseMouse(); // New world/possession starts with an explicitly free cursor.
    }
    if (bMouseCaptured)
    {
        UGameViewportClient* Viewport = GetWorld()->GetGameViewport();
        if (Viewport && Viewport->Viewport)
        {
            const bool bFocused = Viewport->Viewport->HasFocus(), bForeground = Viewport->Viewport->IsForegroundWindow();
            if (!bFocused || !bForeground)
            {
                UE_LOG(LogTemp, Display, TEXT("VEYR_MOUSE_CAPTURE_RELEASE reason=focus_loss focused=%d foreground=%d nativeCapture=%d"),
                    bFocused, bForeground, Viewport->Viewport->HasMouseCapture());
                ReleaseMouse();
            }
            else if (bMouseCaptureConfirmationPending && Viewport->Viewport->HasMouseCapture())
            {
                bMouseCaptureConfirmationPending = false;
                bHasEverCapturedMouse = true;
                UE_LOG(LogTemp, Display, TEXT("VEYR_MOUSE_CAPTURE_CONFIRMED focused=1 foreground=1 nativeCapture=1 local=%d replay=%d"),Player->IsLocalController(),bReplayControlled);
            }
            else if (bMouseCaptureConfirmationPending && GetWorld()->GetTimeSeconds() - MouseCaptureRequestedAt > .5f)
            {
                UE_LOG(LogTemp, Warning, TEXT("VEYR_MOUSE_CAPTURE_REJECTED reason=native_capture_timeout focused=%d foreground=%d nativeCapture=0"),bFocused,bForeground);
                ReleaseMouse();
            }
            else if (!bMouseCaptureConfirmationPending && !Viewport->Viewport->HasMouseCapture())
            {
                UE_LOG(LogTemp, Display, TEXT("VEYR_MOUSE_CAPTURE_RELEASE reason=native_capture_lost focused=%d foreground=%d"),bFocused,bForeground);
                ReleaseMouse();
            }
        }
    }
}

void AVeyrKnight::CaptureMouseOrAttack()
{
    if (bMouseCaptured) { LightPressed(); return; }
    APlayerController* Player = Cast<APlayerController>(Controller);
    UGameViewportClient* Viewport = GetWorld()->GetGameViewport();
    const bool bLocal = Player && Player->IsLocalController();
    const bool bFocused = Viewport && Viewport->Viewport && Viewport->Viewport->HasFocus();
    const bool bForeground = Viewport && Viewport->Viewport && Viewport->Viewport->IsForegroundWindow();
    UE_LOG(LogTemp, Display, TEXT("VEYR_MOUSE_CAPTURE_INPUT local=%d replay=%d focused=%d foreground=%d nativeCapture=%d"),
        bLocal,bReplayControlled,bFocused,bForeground,Viewport && Viewport->Viewport && Viewport->Viewport->HasMouseCapture());
    if (!bLocal || bReplayControlled || !bForeground)
    {
        UE_LOG(LogTemp, Display, TEXT("VEYR_MOUSE_CAPTURE_REJECTED reason=input_context"));
        return;
    }
    FInputModeGameOnly Mode;
    Mode.SetConsumeCaptureMouseDown(true);
    Player->SetInputMode(Mode);
    Player->SetShowMouseCursor(false);
    MouseInputController = Player;
    bMouseCaptured = true;
    bMouseCaptureConfirmationPending = true;
    MouseCaptureRequestedAt = GetWorld()->GetTimeSeconds();
    UE_LOG(LogTemp, Display, TEXT("VEYR_MOUSE_CAPTURE_REQUESTED awaiting_native_confirmation=1"));
    // The deliberate capture click never doubles as a sword swing.
}

void AVeyrKnight::BeginControlFromKeyboard()
{
    // Enter is an accessibility route into controls, never a sword binding.
    if (bMouseCaptured) return;
    UE_LOG(LogTemp, Display, TEXT("VEYR_MOUSE_CAPTURE_INPUT_ROUTE key=Enter"));
    CaptureMouseOrAttack();
}

void AVeyrKnight::ReleaseMouse()
{
    UE_LOG(LogTemp, Display, TEXT("VEYR_MOUSE_RELEASE_INPUT captured=%d confirmationPending=%d replay=%d"),
        bMouseCaptured,bMouseCaptureConfirmationPending,bReplayControlled);
    bMouseCaptured = false;
    bMouseCaptureConfirmationPending = false;
    bForwardHeld = bBackHeld = bLeftHeld = bRightHeld = false;bWalkModifier=false;
    if (!bReplayControlled)
    {
        SetGuard(false); StopJumping();
        MoveIntent = FVector::ZeroVector;
        ConsumeMovementInputVector();
        GetCharacterMovement()->Velocity.X = GetCharacterMovement()->Velocity.Y = 0.f;
    }
    if (APlayerController* Player = Cast<APlayerController>(Controller))
    {
        if (!Player->IsLocalController()) return;
        FInputModeGameAndUI Mode;
        Mode.SetLockMouseToViewportBehavior(EMouseLockMode::DoNotLock);
        Mode.SetHideCursorDuringCapture(false);
        Player->SetInputMode(Mode);
        Player->SetShowMouseCursor(true);
        // Retain GameAndUI's CaptureDuringMouseDown with a visible, unlocked
        // cursor. UE5.8 FSceneViewport drops IE_Pressed for an uncaptured game
        // viewport in NoCapture mode, preventing the deliberate first click.
        // Startup capture remains disabled; permanent capture needs that click
        // (or Enter), and Escape immediately releases it again.
        Player->FlushPressedKeys();
    }
}

void AVeyrKnight::GripPressed() { if(HumanInputEnabled()) ToggleGrip(); }
void AVeyrKnight::LightPressed() { if (HumanInputEnabled()) TryLightAttack(); }
void AVeyrKnight::HeavyPressed() { if (HumanInputEnabled()) TryHeavyAttack(); }
void AVeyrKnight::RollPressed() { if (HumanInputEnabled()) TryRoll(); }
void AVeyrKnight::HealPressed() { if (HumanInputEnabled()) TryHeal(); }
void AVeyrKnight::LockPressed() { if (HumanInputEnabled()) ToggleLockOn(); }
void AVeyrKnight::LookYaw(float Value) { if (HumanInputEnabled() && !bLockedOn) AddControllerYawInput(Value * .7f); }
void AVeyrKnight::LookPitch(float Value) { if (HumanInputEnabled() && !bLockedOn) AddControllerPitchInput(-Value * .6f); }
void AVeyrKnight::ZoomIn() { if (HumanInputEnabled()) CameraDistance = FMath::Clamp(CameraDistance - 65.f, 500.f, 1100.f); }
void AVeyrKnight::ZoomOut() { if (HumanInputEnabled()) CameraDistance = FMath::Clamp(CameraDistance + 65.f, 500.f, 1100.f); }
void AVeyrKnight::GuardPressed() { if (HumanInputEnabled()) SetGuard(true); }
void AVeyrKnight::GuardReleased() { if (!bReplayControlled) SetGuard(false); }
void AVeyrKnight::ForwardPressed() { bForwardHeld = HumanInputEnabled(); } void AVeyrKnight::ForwardReleased() { bForwardHeld = false; }
void AVeyrKnight::BackPressed() { bBackHeld = HumanInputEnabled(); } void AVeyrKnight::BackReleased() { bBackHeld = false; }
void AVeyrKnight::LeftPressed() { bLeftHeld = HumanInputEnabled(); } void AVeyrKnight::LeftReleased() { bLeftHeld = false; }
void AVeyrKnight::RightPressed() { bRightHeld = HumanInputEnabled(); } void AVeyrKnight::RightReleased() { bRightHeld = false; }
