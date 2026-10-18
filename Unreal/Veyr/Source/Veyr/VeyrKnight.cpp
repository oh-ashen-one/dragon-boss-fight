#include "VeyrKnight.h"
#include "VeyrDragon.h"
#include "VeyrSkeletalPresentation.h"
#include "VeyrVisualDefinition.h"
#include "Animation/AnimSequence.h"
#include "Camera/CameraComponent.h"
#include "Components/CapsuleComponent.h"
#include "Components/InputComponent.h"
#include "Components/SceneComponent.h"
#include "Components/StaticMeshComponent.h"
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
    Movement->JumpZVelocity = 580.f;
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
    CameraBoom->bEnableCameraLag = true;
    CameraBoom->CameraLagSpeed = 14.f;
    CameraBoom->CameraLagMaxDistance = 65.f;
    CameraBoom->bUseCameraLagSubstepping = true;
    CameraBoom->bEnableCameraRotationLag = true;
    CameraBoom->CameraRotationLagSpeed = 18.f;
    CombatCamera = CreateDefaultSubobject<UCameraComponent>(TEXT("Combat Camera"));
    CombatCamera->SetupAttachment(CameraBoom, USpringArmComponent::SocketName);
    CombatCamera->bUsePawnControlRotation = false;
    CombatCamera->FieldOfView = 72.f;

    ImportedPresentation = CreateDefaultSubobject<UVeyrSkeletalPresentation>(TEXT("ImportedPresentation"));
    ImportedPresentation->SetupAttachment(GetCapsuleComponent());
    ImportedPresentation->SetVisibility(false);
    ImportedPresentation->SetHiddenInGame(true);
    // Optional until the stable native data asset is authored. The definition
    // supplies imported orientation, scale and the capsule-to-feet offset.
    static ConstructorHelpers::FObjectFinderOptional<UVeyrVisualDefinition> KnightDefinition(
        TEXT("/Game/Characters/Customuse/Runtime/DA_Knight.DA_Knight"),LOAD_Quiet|LOAD_NoWarn);
    CustomuseVisualDefinition = KnightDefinition.Get();
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
        TEXT("/Game/Characters/Customuse/Runtime/DA_Knight.DA_Knight"),nullptr,LOAD_Quiet|LOAD_NoWarn);
    if (CustomuseVisualDefinition) ApplyCustomuseVisual(CustomuseVisualDefinition);
    else SetPresentationDiagnostic(TEXT("Temporary primitive presentation: imported visual definition unavailable"));
    UE_LOG(LogTemp, Display, TEXT("VEYR_KNIGHT_READY collisionHeight=244cm art=%s light=%.3f/%.3f heavy=%.3f/%.3f roll=.08-.44/%.2f"),
        bImportedPresentationActive ? TEXT("imported_definition_acceptance_pending") : TEXT("TEMP_original_primitives_pending_Customuse"),
        GetAttackContactTime(false),GetAttackDuration(false),GetAttackContactTime(true),GetAttackDuration(true),
        bImportedPresentationActive?.78f:.58f);
}

bool AVeyrKnight::IsGrounded() const { return GetCharacterMovement() && GetCharacterMovement()->IsMovingOnGround(); }
bool AVeyrKnight::IsRollingInvulnerable() const { return Action == EVeyrKnightAction::Roll && ActionElapsed > .08f && ActionElapsed < .44f; }
float AVeyrKnight::GetPlanarSpeed() const { return GetVelocity().Size2D(); }
FVector AVeyrKnight::GetFootLocation() const { return GetActorLocation() - FVector(0,0,GetCapsuleComponent()->GetScaledCapsuleHalfHeight()); }
float AVeyrKnight::GetAttackDuration(bool bHeavy) const { return bImportedPresentationActive?(bHeavy?1.20f:.85f):(bHeavy?1.15f:.65f); }
float AVeyrKnight::GetAttackContactTime(bool bHeavy) const { return bImportedPresentationActive?(bHeavy?.617f:.522f):(bHeavy?.55f:.23f); }
float AVeyrKnight::GetSwordContactTime() const { return Action == EVeyrKnightAction::HeavyAttack ? GetAttackContactTime(true) : Action == EVeyrKnightAction::LightAttack ? GetAttackContactTime(false) : -1.f; }
bool AVeyrKnight::IsTerminal() const { return IsDead() || (IsValid(Boss) && Boss->IsDead()); }
bool AVeyrKnight::CanStartGroundedAction() const { return !IsTerminal() && IsGrounded() && !bPressedJump && (Action == EVeyrKnightAction::Ready || Action == EVeyrKnightAction::Guard); }

void AVeyrKnight::BeginAction(EVeyrKnightAction NewAction, float Duration)
{
    Action = NewAction; ActionElapsed = 0.f; ActionDuration = Duration;
    bContactSent = false; bHealGranted = false; bPreviousBladePoseValid=false;
}

void AVeyrKnight::FinishAction()
{
    bGuardBroken = false;
    BeginAction(bGuardRequested && Stamina > 5.f && IsGrounded() ? EVeyrKnightAction::Guard : EVeyrKnightAction::Ready, 0.f);
}

void AVeyrKnight::TryLightAttack()
{
    if (!CanStartGroundedAction() || Stamina < 22.f) return;
    Stamina -= 22.f; RegenDelay = .75f; ++SwingId; ++LightAttacks;
    BeginAction(EVeyrKnightAction::LightAttack, GetAttackDuration(false));
}

void AVeyrKnight::TryHeavyAttack()
{
    if (!CanStartGroundedAction() || Stamina < 38.f) return;
    Stamina -= 38.f; RegenDelay = 1.05f; ++SwingId; ++HeavyAttacks;
    BeginAction(EVeyrKnightAction::HeavyAttack, GetAttackDuration(true));
}

void AVeyrKnight::TryRoll()
{
    if (!CanStartGroundedAction() || Stamina < 25.f) return;
    Stamina -= 25.f; RegenDelay = .7f; ++Rolls;
    RollDirection = MoveIntent.GetSafeNormal2D();
    if (RollDirection.IsNearlyZero()) RollDirection = GetActorForwardVector().GetSafeNormal2D();
    BeginAction(EVeyrKnightAction::Roll, bImportedPresentationActive?.78f:.58f);
}

void AVeyrKnight::TryHeal()
{
    if (!CanStartGroundedAction() || HealingCharges <= 0 || Health >= 100.f) return;
    --HealingCharges;
    BeginAction(EVeyrKnightAction::Heal, 1.25f);
}

void AVeyrKnight::TryGroundedJump()
{
    if (!CanStartGroundedAction()) return;
    if (Action == EVeyrKnightAction::Guard) BeginAction(EVeyrKnightAction::Ready, 0.f);
    Jump();
}

void AVeyrKnight::OnJumped_Implementation()
{
    Super::OnJumped_Implementation();
    PresentationJumpLaunchSpeed=FMath::Max(1.f,FMath::Max(GetVelocity().Z,GetCharacterMovement()->JumpZVelocity));
    ++SuccessfulJumps;
    UE_LOG(LogTemp, Display, TEXT("VEYR_KNIGHT_JUMP count=%d footZ=%.2f"), SuccessfulJumps, GetFootLocation().Z);
}

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
    const bool bCanBlock = Action == EVeyrKnightAction::Guard && IsGrounded() && !bUnblockable && bFacingThreat;
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
        BeginAction(EVeyrKnightAction::Stagger, bBroken ? .9f : .42f);
        const FVector Away = (GetActorLocation() - Source).GetSafeNormal2D();
        GetCharacterMovement()->AddImpulse(Away * (bBroken ? 190.f : 120.f), true);
    }
}

void AVeyrKnight::Tick(float DeltaSeconds)
{
    Super::Tick(DeltaSeconds);
    if (DeltaSeconds <= 0.f) return;
    UpdateMouseCapture();
    // Keep replay press alive until CharacterMovement has actually consumed it.
    // Jump followed by StopJumping in one actor tick cancels the jump entirely.
    if (bReplayJumpHeld && !IsGrounded()) { StopJumping(); bReplayJumpHeld = false; }
    VisualClock += DeltaSeconds;
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
        else if (bReplayJump) { TryGroundedJump(); bReplayJumpHeld = bPressedJump; }
        else if (bReplayHeal) TryHeal();
        else if (bReplayHeavy) TryHeavyAttack();
        else if (bReplayLight) TryLightAttack();
        bReplayLight = bReplayHeavy = bReplayRoll = bReplayHeal = bReplayJump = false;
    }
    UpdateMovement(DeltaSeconds);
    if (IsDead()) { ActionElapsed += DeltaSeconds; UpdateImportedPresentation(DeltaSeconds); }
    else if (!IsTerminal()) AdvanceCombat(DeltaSeconds);
    else { GetCharacterMovement()->StopMovementImmediately(); bLockedOn = false; UpdateImportedPresentation(DeltaSeconds); }
    UpdateHealFlask();
    UpdateCamera(DeltaSeconds);
    UpdateTemporaryPresentation(DeltaSeconds);
}

void AVeyrKnight::AdvanceCombat(float DeltaSeconds)
{
    ActionElapsed += DeltaSeconds;
    // Evaluate the strike at the UPDATED action time, synchronously, before
    // gameplay resolves contact. Imported strikes use evaluated blade sweeps.
    UpdateImportedPresentation(DeltaSeconds);
    if (Action == EVeyrKnightAction::LightAttack || Action == EVeyrKnightAction::HeavyAttack)
    {
        const bool bHeavy=Action==EVeyrKnightAction::HeavyAttack;
        if(bImportedPresentationActive)
        {
            FTransform BasePose,TipPose;
            // A visible imported sword resolves contact only from its evaluated
            // blade. Missing targets cannot silently fall back to proxy damage.
            const bool bBladeReady=bRequestedPresentationClipSampled&&
                ImportedPresentation->GetBoneTargetWorldTransform(TEXT("weapon_base"),BasePose)&&
                ImportedPresentation->GetBoneTargetWorldTransform(TEXT("weapon_tip"),TipPose);
            if(bBladeReady)
            {
                const FVector Base=BasePose.GetLocation(),Tip=TipPose.GetLocation();
                const float Start=bHeavy?.53f:.425f,End=bHeavy?.73f:.664f;
                if(!bContactSent&&ActionElapsed>=Start&&ActionElapsed-DeltaSeconds<=End&&IsValid(Boss))
                {
                    FVector FromBase=bPreviousBladePoseValid?PreviousBladeBase:Base;
                    FVector FromTip=bPreviousBladePoseValid?PreviousBladeTip:Tip;
                    FVector ToBase=Base,ToTip=Tip;
                    const float Alpha=ImportedPresentation->CurrentTransitionAlpha;
                    bool bResampled=false,bWindowValid=true;
                    auto SampleBoundary=[&](float Time,FVector& OutBase,FVector& OutTip)
                    {
                        bResampled=true;
                        if(!ImportedPresentation->SampleClipPhaseBlended(RequestedPresentationClip,Time/ActionDuration,Alpha))return false;
                        FTransform A,B;
                        if(!ImportedPresentation->GetBoneTargetWorldTransform(TEXT("weapon_base"),A)||
                           !ImportedPresentation->GetBoneTargetWorldTransform(TEXT("weapon_tip"),B))return false;
                        OutBase=A.GetLocation();OutTip=B.GetLocation();return true;
                    };
                    // Clip collision to the actual active interval even when a
                    // slow frame crosses its beginning or end; never include
                    // windup/recovery merely because an entire frame was long.
                    if(ActionElapsed-DeltaSeconds<Start||!bPreviousBladePoseValid)
                        bWindowValid=SampleBoundary(FMath::Max(Start,ActionElapsed-DeltaSeconds),FromBase,FromTip);
                    if(ActionElapsed>End)bWindowValid=SampleBoundary(End,ToBase,ToTip)&&bWindowValid;
                    if(bResampled)bWindowValid=ImportedPresentation->SampleClipPhaseBlended(RequestedPresentationClip,
                        FMath::Clamp(ActionElapsed/ActionDuration,0.f,1.f),Alpha)&&bWindowValid;
                    if(bWindowValid)bContactSent=Boss->ReceiveSwordSweep(FromBase,FromTip,ToBase,ToTip,bHeavy,SwingId);
                }
                PreviousBladeBase=Base;PreviousBladeTip=Tip;bPreviousBladePoseValid=true;
            }
            else bPreviousBladePoseValid=false;
        }
        else if (!bContactSent && ActionElapsed >= GetSwordContactTime())
        {
            bContactSent = true;
            if (IsValid(Boss)) Boss->ReceiveSword(GetFootLocation() + FVector(0,0,125), GetActorForwardVector(), bHeavy, SwingId);
        }
    }
    else if (Action == EVeyrKnightAction::Heal && !bHealGranted && ActionElapsed >= .85f)
    {
        bHealGranted = true; Health = FMath::Min(100.f, Health + 55.f); ++SuccessfulHeals;
    }
    else if (Action == EVeyrKnightAction::Guard)
    {
        Stamina = FMath::Max(0.f, Stamina - 3.f * DeltaSeconds);
        if (Stamina <= 0.f || !IsGrounded()) FinishAction();
    }
    if (ActionDuration > 0.f && ActionElapsed >= ActionDuration) FinishAction();
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
    const bool bAttack = Action == EVeyrKnightAction::LightAttack || Action == EVeyrKnightAction::HeavyAttack;
    Movement->bOrientRotationToMovement = !bLockedOn && !bAttack && Action != EVeyrKnightAction::Roll && Action != EVeyrKnightAction::Guard;
    if (Action == EVeyrKnightAction::Roll)
    {
        // Preserve the original 684.4cm intended travel while giving the
        // imported .78s roll its full action window. Invulnerability is unchanged.
        const float RollSpeed=1180.f*.58f/FMath::Max(.001f,ActionDuration);
        Movement->MaxWalkSpeed = RollSpeed;
        Movement->Velocity.X = RollDirection.X * RollSpeed;
        Movement->Velocity.Y = RollDirection.Y * RollSpeed;
        AddMovementInput(RollDirection, 1.f);
    }
    else
    {
        Movement->MaxWalkSpeed = Action == EVeyrKnightAction::Guard ? 240.f : Action == EVeyrKnightAction::Heal ? 120.f :
            Action == EVeyrKnightAction::HeavyAttack ? 75.f : bAttack ? 140.f : Action == EVeyrKnightAction::Stagger ? 0.f : 580.f;
        if(bImportedPresentationActive&&bLockedOn&&Action==EVeyrKnightAction::Ready)
        {
            const FVector Direction=MoveIntent.GetSafeNormal2D();
            const float Forward=FVector::DotProduct(Direction,GetActorForwardVector());
            const float Right=FVector::DotProduct(Direction,GetActorRightVector());
            // A locked combat step is deliberate; free movement and forward
            // running retain full speed, and rolls retain their original travel.
            if(FMath::Abs(Right)>FMath::Abs(Forward))Movement->MaxWalkSpeed=300.f;
            else if(Forward<0.f)Movement->MaxWalkSpeed=240.f;
        }
        if (Action != EVeyrKnightAction::Stagger) AddMovementInput(MoveIntent, 1.f);
    }
    if (bLockedOn && IsValid(Boss) && !bAttack && Action != EVeyrKnightAction::Roll && Action != EVeyrKnightAction::Stagger)
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
    CameraBoom->TargetArmLength = FMath::FInterpTo(CameraBoom->TargetArmLength, CameraDistance, DeltaSeconds, 12.f);
    if (!Controller) { RestoreCameraOcclusion(); return; }
    if (bLockedOn && IsValid(Boss) && !Boss->IsDead())
    {
        // The standing head is far above a player fighting the legs. Frame the
        // grounded combat region nearby, blend toward the head at range and on
        // collapse, and solve from the pivot rather than the lagged camera.
        const float BossRange = FVector::Dist2D(GetActorLocation(), Boss->GetActorLocation());
        const bool bHeadApproach = Boss->State == EVeyrDragonState::Buckle || Boss->State == EVeyrDragonState::Collapse || Boss->IsHeadExposed();
        const float HeadWeight = bHeadApproach ? 1.f : FMath::Clamp((BossRange - 700.f) / 700.f, 0.f, 1.f);
        LockHeadBlend = FMath::FInterpTo(LockHeadBlend, HeadWeight, DeltaSeconds, 4.f);
        const FVector GroundFocus(Boss->GetActorLocation().X, Boss->GetActorLocation().Y, GetFootLocation().Z + 230.f);
        const FVector Focus = FMath::Lerp(GroundFocus, Boss->GetHeadLocation(), LockHeadBlend);
        const FVector ToFocus = Focus - CameraBoom->GetComponentLocation();
        FRotator Current = Controller->GetControlRotation().GetNormalized();
        FRotator Desired = Current;
        // Retain azimuth when walking directly beneath the target. Otherwise a
        // few centimetres crossing its axis can request a sudden 180-degree turn.
        // Head punish range is about 205cm: the body dead zone must not freeze
        // the view while the player walks beside the exposed crown.
        if (ToFocus.Size2D() > (bHeadApproach ? 60.f : 240.f)) Desired.Yaw = ToFocus.Rotation().Yaw;
        Desired.Pitch = FMath::Clamp(static_cast<float>(FMath::RadiansToDegrees(FMath::Atan2(ToFocus.Z,
            FMath::Max(300.f, static_cast<float>(ToFocus.Size2D()))))) - 8.f, -28.f, 18.f);
        Desired.Roll = 0.f;
        const FRotator Smoothed = FMath::RInterpTo(Current, Desired, DeltaSeconds, 5.f);
        Controller->SetControlRotation(FMath::RInterpConstantTo(Current, Smoothed, DeltaSeconds, 100.f));
    }
    else
    {
        FRotator Look = Controller->GetControlRotation();
        Look.Pitch = FMath::Clamp(FRotator::NormalizeAxis(Look.Pitch), -55.f, 45.f); Look.Roll = 0.f;
        Controller->SetControlRotation(Look);
    }
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
    const FVector Direction=GetVelocity().GetSafeNormal2D();
    const float Forward=FVector::DotProduct(Direction,GetActorForwardVector());
    const float Right=FVector::DotProduct(Direction,GetActorRightVector());
    if(FMath::Abs(Right)>FMath::Abs(Forward))return Right<0.f?FName(TEXT("StrafeLeft")):FName(TEXT("StrafeRight"));
    if(Forward<0.f)return TEXT("Backpedal");
    return bAllowRun&&GetPlanarSpeed()>360.f?FName(TEXT("Run")):FName(TEXT("Walk"));
}

void AVeyrKnight::UpdateImportedPresentation(float DeltaSeconds)
{
    if (!bImportedPresentationActive || !ImportedPresentation || !CustomuseVisualDefinition) return;
    const float Speed=GetPlanarSpeed();
    const bool bMoving=IsGrounded()&&Speed>8.f;
    const bool bLayerAction=Action==EVeyrKnightAction::Guard||Action==EVeyrKnightAction::Heal;
    const FName DesiredLower=bLayerAction&&bMoving?SelectDirectionalLocomotion(false):NAME_None;
    if(!DesiredLower.IsNone())PresentationLowerClip=DesiredLower;
    PresentationLowerWeight=FMath::FInterpConstantTo(PresentationLowerWeight,
        !DesiredLower.IsNone()?1.f:0.f,DeltaSeconds,1.f/.12f);
    // Other actions already use the full-pose transition. Never carry a leg
    // overlay into attacks, jumping, rolls, stagger or death.
    if(!bLayerAction)PresentationLowerWeight=0.f;
    if(PresentationLowerWeight<=0.f&&DesiredLower.IsNone())PresentationLowerClip=NAME_None;
    RequestedLowerPresentationClip=PresentationLowerClip;

    // Turn only the imported visual toward the roll vector, leaving gameplay
    // facing, collision, lock-on and the movement direction untouched.
    const float DesiredRollYaw=Action==EVeyrKnightAction::Roll?
        FMath::FindDeltaAngleDegrees(GetActorRotation().Yaw,RollDirection.Rotation().Yaw):0.f;
    PresentationRollYaw=FMath::RInterpTo(FRotator(0,PresentationRollYaw,0),
        FRotator(0,DesiredRollYaw,0),DeltaSeconds,20.f).Yaw;
    const FQuat BaseRotation=CustomuseVisualDefinition->MeshRelativeTransform.GetRotation();
    ImportedPresentation->SetRelativeRotation(FQuat(FVector::UpVector,FMath::DegreesToRadians(PresentationRollYaw))*BaseRotation);

    FName Clip=TEXT("Idle");
    bool bUsePhase=false,bJumpPose=false;
    float Time=VisualClock,Phase=FMath::Clamp(ActionElapsed/FMath::Max(.001f,ActionDuration),0.f,1.f);
    switch (Action)
    {
        case EVeyrKnightAction::LightAttack: Clip=TEXT("LightAttack"); bUsePhase=true; break;
        case EVeyrKnightAction::HeavyAttack: Clip=TEXT("HeavyAttack"); bUsePhase=true; break;
        case EVeyrKnightAction::Roll: Clip=TEXT("Roll"); bUsePhase=true; break;
        case EVeyrKnightAction::Heal: Clip=TEXT("Heal"); bUsePhase=true; break;
        case EVeyrKnightAction::Stagger: Clip=TEXT("Stagger"); bUsePhase=true; break;
        case EVeyrKnightAction::Dead: Clip=TEXT("Death"); bUsePhase=true; break;
        case EVeyrKnightAction::Guard: Clip=TEXT("Guard"); Time=ActionElapsed; break;
        default:
            if (!IsGrounded())
            {
                Clip=TEXT("Jump");bUsePhase=bJumpPose=true;
                // Authored jump has its apex at phase .5, with ballistic root
                // translation removed. Follow actual vertical motion, not time.
                Phase=FMath::Clamp(.5f-.5f*GetVelocity().Z/FMath::Max(1.f,PresentationJumpLaunchSpeed),0.f,1.f);
                PresentationJumpPhase=Phase;
            }
            else if (bMoving)
            {
                Clip=bLockedOn?SelectDirectionalLocomotion(true):(Speed>360.f?FName(TEXT("Run")):FName(TEXT("Walk")));
                const float* Nominal=PresentationNominalSpeeds.Find(Clip);
                if(Nominal&&FMath::IsFinite(*Nominal)&&*Nominal>0.f)
                    PresentationLocomotionTime+=DeltaSeconds*Speed/(*Nominal);
                Time=PresentationLocomotionTime;
            }
            break;
    }
    if(IsGrounded())PresentationJumpPhase=0.f;
    RequestedPresentationClip=Clip;
    const FVeyrVisualClip* Config=CustomuseVisualDefinition->Clips.Find(Clip);
    const FVeyrVisualClip* Lower=PresentationLowerClip.IsNone()?nullptr:CustomuseVisualDefinition->Clips.Find(PresentationLowerClip);
    FString Error;
    bool bSampled=false;
    const bool bLocomotion=Action==EVeyrKnightAction::Ready&&bMoving;
    const float* Nominal=PresentationNominalSpeeds.Find(bLocomotion?Clip:PresentationLowerClip);
    if (!Config || !Config->Sequence) Error=TEXT("Requested imported clip is missing: ")+Clip.ToString();
    else if (!PresentationLowerClip.IsNone()&&(!Lower||!Lower->Sequence))
        Error=TEXT("Requested directional lower clip is missing: ")+PresentationLowerClip.ToString();
    else if ((bLocomotion||!PresentationLowerClip.IsNone())&&(!Nominal||!FMath::IsFinite(*Nominal)||*Nominal<=0.f))
        Error=TEXT("Missing or invalid nominal speed for locomotion clip: ")+(bLocomotion?Clip:PresentationLowerClip).ToString();
    else if (FailedPresentationClip==Clip) Error=FailedPresentationReason;
    else
    {
        if(Lower)PresentationLowerTime+=DeltaSeconds*Speed/(*Nominal);
        const bool bActionRestarted=bUsePhase&&!bJumpPose&&PresentationPreviousActionElapsed>=0.f&&ActionElapsed<PresentationPreviousActionElapsed;
        const float ClipEnd=Config->EndSeconds<0.f?Config->Sequence->GetPlayLength():Config->EndSeconds;
        const float ClipDuration=ClipEnd-Config->StartSeconds;
        const bool bLoopWrapped=!bUsePhase&&Config->bLoop&&ClipDuration>0.f&&ImportedPresentation->CurrentClip==Clip&&
            FMath::Fmod(Time,ClipDuration)+.0001f<ImportedPresentation->CurrentTrimmedSeconds;
        if(Clip!=PresentationTransitionClip||PresentationLowerClip!=PresentationTransitionLowerClip||bActionRestarted||bLoopWrapped)
        {
            bPresentationTransitionActive=!PresentationTransitionClip.IsNone()&&ImportedPresentation->bPoseEvaluated&&ImportedPresentation->BeginTransition();
            PresentationTransitionStarted=VisualClock;
            PresentationTransitionClip=Clip;
            PresentationTransitionLowerClip=PresentationLowerClip;
        }
        const float Alpha=bPresentationTransitionActive?FMath::Clamp((VisualClock-PresentationTransitionStarted)/.12f,0.f,1.f):1.f;
        if(Lower)
            bSampled=ImportedPresentation->SampleLayeredClips(Clip,bUsePhase?Phase*ClipDuration:Time,
                PresentationLowerClip,PresentationLowerTime,PresentationLowerWeight,Alpha);
        else
            bSampled=bUsePhase?ImportedPresentation->SampleClipPhaseBlended(Clip,Phase,Alpha):
                ImportedPresentation->SampleClipTimeBlended(Clip,Time,Alpha);
        if(Alpha>=1.f)bPresentationTransitionActive=false;
        if (!bSampled)
        {
            // A lower-layer rejection must not blacklist the stationary upper
            // Guard/Heal clip. Missing directions remain explicit diagnostics.
            if(!Lower) { FailedPresentationClip=Clip;FailedPresentationReason=ImportedPresentation->LastError; }
            Error=ImportedPresentation->LastError;
        }
    }
    bRequestedPresentationClipSampled=bSampled;
    bPresentationUsingFallback=!bSampled;
    PresentationPreviousActionElapsed=bUsePhase&&!bJumpPose?ActionElapsed:-1.f;
    if (bSampled) { SetPresentationDiagnostic(FString()); return; }

    bPresentationTransitionActive=false;
    PresentationTransitionClip=PresentationTransitionLowerClip=NAME_None;
    const FVeyrVisualClip* Idle=CustomuseVisualDefinition->Clips.Find(TEXT("Idle"));
    bool bHeldIdle=false;
    if (Idle && Idle->Sequence && !bIdleFallbackRejected && FailedPresentationClip!=FName(TEXT("Idle")))
    {
        bHeldIdle=ImportedPresentation->SampleClipTime(TEXT("Idle"),0.f);
        bIdleFallbackRejected=!bHeldIdle;
    }
    if (bHeldIdle || ImportedPresentation->SampleReferencePose())
    {
        SetPresentationDiagnostic(Error+(bHeldIdle ? TEXT("; holding Idle fallback (action animation unverified)") :
            TEXT("; holding reference pose fallback (action animation unavailable)")));
        return;
    }
    bImportedPresentationActive=false;
    ImportedPresentation->SetVisibility(false,true);
    ImportedPresentation->SetHiddenInGame(true,true);
    if (TemporaryVisual) TemporaryVisual->SetVisibility(true,true);
    SetPresentationDiagnostic(Error+TEXT("; fallback evaluation failed, temporary primitives restored"));
}

void AVeyrKnight::UpdateHealFlask()
{
    bHealFlaskVisible=false;
    if(HealFlaskRoot)HealFlaskRoot->SetVisibility(false,true);
    if(Action!=EVeyrKnightAction::Heal||!bImportedPresentationActive||!bRequestedPresentationClipSampled)
    {
        HealFlaskDiagnostic.Reset();return;
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
    bReplayLight |= bLight; bReplayHeavy |= bHeavy; bReplayRoll |= bRoll; bReplayHeal |= bHeal; bReplayJump |= bJump; bReplayGuard = bGuard;
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
    Input->BindKey(EKeys::LeftShift, IE_Pressed, this, &AVeyrKnight::RollPressed);
    Input->BindKey(EKeys::SpaceBar, IE_Pressed, this, &AVeyrKnight::JumpPressed); Input->BindKey(EKeys::SpaceBar, IE_Released, this, &AVeyrKnight::JumpReleased);
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
    bForwardHeld = bBackHeld = bLeftHeld = bRightHeld = false;
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

void AVeyrKnight::LightPressed() { if (HumanInputEnabled()) TryLightAttack(); }
void AVeyrKnight::HeavyPressed() { if (HumanInputEnabled()) TryHeavyAttack(); }
void AVeyrKnight::RollPressed() { if (HumanInputEnabled()) TryRoll(); }
void AVeyrKnight::HealPressed() { if (HumanInputEnabled()) TryHeal(); }
void AVeyrKnight::JumpPressed() { if (HumanInputEnabled()) TryGroundedJump(); }
void AVeyrKnight::LockPressed() { if (HumanInputEnabled()) ToggleLockOn(); }
void AVeyrKnight::LookYaw(float Value) { if (HumanInputEnabled() && !bLockedOn) AddControllerYawInput(Value * .7f); }
void AVeyrKnight::LookPitch(float Value) { if (HumanInputEnabled() && !bLockedOn) AddControllerPitchInput(-Value * .6f); }
void AVeyrKnight::ZoomIn() { if (HumanInputEnabled()) CameraDistance = FMath::Clamp(CameraDistance - 65.f, 300.f, 1100.f); }
void AVeyrKnight::ZoomOut() { if (HumanInputEnabled()) CameraDistance = FMath::Clamp(CameraDistance + 65.f, 300.f, 1100.f); }
void AVeyrKnight::GuardPressed() { if (HumanInputEnabled()) SetGuard(true); }
void AVeyrKnight::GuardReleased() { if (!bReplayControlled) SetGuard(false); }
void AVeyrKnight::JumpReleased() { if (!bReplayControlled) StopJumping(); }
void AVeyrKnight::ForwardPressed() { bForwardHeld = HumanInputEnabled(); } void AVeyrKnight::ForwardReleased() { bForwardHeld = false; }
void AVeyrKnight::BackPressed() { bBackHeld = HumanInputEnabled(); } void AVeyrKnight::BackReleased() { bBackHeld = false; }
void AVeyrKnight::LeftPressed() { bLeftHeld = HumanInputEnabled(); } void AVeyrKnight::LeftReleased() { bLeftHeld = false; }
void AVeyrKnight::RightPressed() { bRightHeld = HumanInputEnabled(); } void AVeyrKnight::RightReleased() { bRightHeld = false; }
