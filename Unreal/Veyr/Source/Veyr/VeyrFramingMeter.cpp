#include "VeyrFramingMeter.h"
#include "VeyrCameraBoom.h"
#include "VeyrDragon.h"
#include "VeyrKnight.h"
#include "Camera/CameraComponent.h"
#include "Components/CapsuleComponent.h"
#include "Dom/JsonObject.h"
#include "Dom/JsonValue.h"
#include "Engine/GameViewportClient.h"
#include "Engine/World.h"
#include "Camera/PlayerCameraManager.h"
#include "GameFramework/PlayerController.h"

void FVeyrFramingMeter::Begin(AVeyrKnight* InKnight,AVeyrDragon* InDragon)
{
    Knight=InKnight;Dragon=InDragon;
}

bool FVeyrFramingMeter::Project(const FVector& World,FVector2D& OutScreen) const
{
    const FVector D=World-CamLoc;
    const double X=FVector::DotProduct(D,CamF);
    if(X<=1.0)return false;
    OutScreen.X=.5f+.5f*static_cast<float>(FVector::DotProduct(D,CamR)/(X*TanH));
    OutScreen.Y=.5f-.5f*static_cast<float>(FVector::DotProduct(D,CamU)/(X*TanV));
    return true;
}

void FVeyrFramingMeter::Commit()
{
    if(Current.Attack>=0&&Current.BestCm<TNumericLimits<float>::Max())Strikes.Add(Current);
    Current=FStrike();
}

void FVeyrFramingMeter::Sample(float DeltaSeconds)
{
    AVeyrKnight* K=Knight.Get();AVeyrDragon* D=Dragon.Get();
    if(!K||!D||!K->CombatCamera||!K->GetWorld())return;
    SampledSeconds+=DeltaSeconds;
    // Measure only the view that is actually rendered: the knight's own camera, not an inspection/proof camera or a blend.
    const APlayerController* PC=Cast<APlayerController>(K->GetController());
    const APlayerCameraManager* Manager=PC?PC->PlayerCameraManager.Get():nullptr;
    if(!PC||PC->GetViewTarget()!=K||(Manager&&Manager->PendingViewTarget.Target!=nullptr)){++OtherViewFrames;Commit();return;}
    if(!K->HasEnteredEncounter()){++PreEncounterFrames;return;}
    const double W=FMath::Max(0.f,DeltaSeconds);
    Seconds+=W;
    const UCameraComponent* Camera=K->CombatCamera;
    CamLoc=Camera->GetComponentLocation();
    const FRotationMatrix Basis(Camera->GetComponentRotation());
    CamF=Basis.GetUnitAxis(EAxis::X);CamR=Basis.GetUnitAxis(EAxis::Y);CamU=Basis.GetUnitAxis(EAxis::Z);
    FVector2D Size(16.f,9.f);
    if(const UGameViewportClient* Viewport=K->GetWorld()->GetGameViewport())Viewport->GetViewportSize(Size);
    const float Aspect=Size.X>1.f&&Size.Y>1.f?static_cast<float>(Size.X/Size.Y):16.f/9.f;
    // Horizontal field of view is held (the engine's default aspect-ratio axis constraint).
    TanH=FMath::Tan(FMath::DegreesToRadians(Camera->FieldOfView*.5f));TanV=TanH/FMath::Max(.5f,Aspect);
    ++FrameCount;

    const UCapsuleComponent* Capsule=K->GetCapsuleComponent();
    const float Half=Capsule->GetScaledCapsuleHalfHeight(),Radius=Capsule->GetScaledCapsuleRadius();
    const FVector Feet=K->GetFootLocation(),Top=Feet+FVector(0,0,2.f*Half),Mid=Feet+FVector(0,0,Half);
    const FVector Side=CamR.GetSafeNormal2D()*Radius;
    FVector2D PFeet,PTop,PL,PR,PMid;
    const bool bFeet=Project(Feet,PFeet),bTop=Project(Top,PTop);
    const bool bFull=bFeet&&bTop&&Project(Mid-Side,PL)&&Project(Mid+Side,PR)&&OnScreen(PFeet)&&OnScreen(PTop)&&OnScreen(PL)&&OnScreen(PR);
    KnightFull+=bFull?W:0.0;
    KnightCenter+=Project(Mid,PMid)&&OnScreen(PMid)?W:0.0;
    if(K->bLockedOn){Locked+=W;LockedKnightFull+=bFull?W:0.0;}
    if(bFeet&&bTop)
    {
        const float H=100.f*(PFeet.Y-PTop.Y);
        KnightHeightSum+=H*W;KnightHeightSeconds+=W;KnightHeights.Add(H);
    }
    FVector2D PHead,PChest;
    const bool bHead=Project(D->GetHeadLocation(),PHead)&&OnScreen(PHead);
    const bool bChest=Project(D->GetChestLocation(),PChest)&&OnScreen(PChest);
    HeadOn+=bHead?W:0.0;ChestOn+=bChest?W:0.0;HeadOrChest+=bHead||bChest?W:0.0;

    if(UVeyrCameraBoom* Boom=Cast<UVeyrCameraBoom>(K->CameraBoom))
    {
        // The legacy arm never builds its shapes; build them so an old-arm A/B is measured the same way.
        if(Boom->bLegacyBoom)Boom->RefreshDragonShapes();
        const float S=Boom->DragonScale();
        if(Boom->IsPointInsideDragon(CamLoc,10.f-FMath::Min(Boom->BodyClearanceCm,Boom->WingClearanceCm)*S))++InsideBody;
    }

    // One record per attack: the limb's closest approach to the knight's capsule while the attack is active.
    FVector Strike;FName Limb;
    const bool bActive=D->State==EVeyrDragonState::Active&&D->GetStrikeFocus(Strike,&Limb);
    const int32 Attack=D->GetTotalAttackCount();
    if(Current.Attack>=0&&(Current.Attack!=Attack||(!bActive&&D->State!=EVeyrDragonState::Active)))Commit();
    if(bActive)
    {
        if(Current.Attack!=Attack){Current=FStrike();Current.Attack=Attack;Current.Move=FName(*StaticEnum<EVeyrDragonMove>()->GetNameStringByValue(static_cast<int64>(D->Move)));}
        const FVector A=Feet+FVector(0,0,Radius),B=Top-FVector(0,0,Radius);
        const float Gap=static_cast<float>(FMath::PointDistToSegment(Strike,A,B))-Radius;
        if(Gap<Current.BestCm)
        {
            FVector2D P;
            Current.BestCm=Gap;Current.Limb=Limb;Current.bVisible=Project(Strike,P)&&OnScreen(P);
            Current.Screen=Current.bVisible?P:FVector2D(-1,-1);Current.AtSeconds=SampledSeconds;
        }
    }
}

TSharedPtr<FJsonObject> FVeyrFramingMeter::Evidence() const
{
    TSharedPtr<FJsonObject> O=MakeShared<FJsonObject>();
    const AVeyrKnight* K=Knight.Get();const AVeyrDragon* D=Dragon.Get();
    auto Share=[](double N,double Of){return Of>0.0?N/Of:0.0;};
    TArray<FStrike> All=Strikes;
    if(Current.Attack>=0&&Current.BestCm<TNumericLimits<float>::Max())All.Add(Current);
    int32 Visible=0,Near=0,NearVisible=0;
    const float S=D?FMath::Max(.5f,D->BodyScale*.5f):1.f;
    TMap<FName,FIntPoint> ByMove;
    TArray<TSharedPtr<FJsonValue>> List;
    for(const FStrike& X:All)
    {
        Visible+=X.bVisible?1:0;
        const bool bNear=X.BestCm<400.f*S;Near+=bNear?1:0;NearVisible+=bNear&&X.bVisible?1:0;
        FIntPoint& M=ByMove.FindOrAdd(X.Move);M.X+=X.bVisible?1:0;++M.Y;
        TSharedPtr<FJsonObject> E=MakeShared<FJsonObject>();
        E->SetNumberField(TEXT("attack"),X.Attack);E->SetStringField(TEXT("move"),X.Move.ToString());E->SetStringField(TEXT("limb"),X.Limb.ToString());
        E->SetNumberField(TEXT("closestGapCm"),X.BestCm);E->SetBoolField(TEXT("visible"),X.bVisible);
        E->SetNumberField(TEXT("screenX"),X.Screen.X);E->SetNumberField(TEXT("screenY"),X.Screen.Y);E->SetNumberField(TEXT("atSeconds"),X.AtSeconds);
        List.Add(MakeShared<FJsonValueObject>(E));
    }
    TArray<float> Heights=KnightHeights;Heights.Sort();
    auto Pct=[&Heights](float P){return Heights.IsEmpty()?0.f:Heights[FMath::Clamp(FMath::RoundToInt(P*(Heights.Num()-1)),0,Heights.Num()-1)];};
    O->SetNumberField(TEXT("frames"),FrameCount);O->SetNumberField(TEXT("measuredSeconds"),Seconds);
    O->SetNumberField(TEXT("otherViewFrames"),OtherViewFrames);O->SetNumberField(TEXT("preEncounterFrames"),PreEncounterFrames);
    O->SetNumberField(TEXT("knightFullyInFrameShare"),Share(KnightFull,Seconds));
    O->SetNumberField(TEXT("knightCentreOnScreenShare"),Share(KnightCenter,Seconds));
    O->SetNumberField(TEXT("lockedSeconds"),Locked);
    O->SetNumberField(TEXT("lockedKnightFullyInFrameShare"),Share(LockedKnightFull,Locked));
    O->SetNumberField(TEXT("headOrChestOnScreenShare"),Share(HeadOrChest,Seconds));
    O->SetNumberField(TEXT("headOnScreenShare"),Share(HeadOn,Seconds));
    O->SetNumberField(TEXT("chestOnScreenShare"),Share(ChestOn,Seconds));
    O->SetNumberField(TEXT("knightMeanScreenHeightPct"),KnightHeightSeconds>0.0?KnightHeightSum/KnightHeightSeconds:0.0);
    O->SetNumberField(TEXT("knightScreenHeightP10Pct"),Pct(.1f));O->SetNumberField(TEXT("knightScreenHeightP90Pct"),Pct(.9f));
    O->SetNumberField(TEXT("cameraInsideBodyFrames"),InsideBody);
    O->SetNumberField(TEXT("strikes"),All.Num());
    O->SetNumberField(TEXT("strikeLimbVisibleShare"),Share(double(Visible),double(All.Num())));
    O->SetNumberField(TEXT("nearStrikes"),Near);
    O->SetNumberField(TEXT("nearStrikeLimbVisibleShare"),Share(double(NearVisible),double(Near)));
    TSharedPtr<FJsonObject> Moves=MakeShared<FJsonObject>();
    for(const auto& Pair:ByMove)Moves->SetStringField(Pair.Key.ToString(),FString::Printf(TEXT("%d/%d"),Pair.Value.X,Pair.Value.Y));
    O->SetObjectField(TEXT("strikeLimbVisibleByMove"),Moves);
    O->SetArrayField(TEXT("strikeList"),List);
    O->SetBoolField(TEXT("goalD1Met"),Share(KnightFull,Seconds)>=.95&&All.Num()>0&&Share(double(Visible),double(All.Num()))>=.90);
    if(K)
    {
        O->SetBoolField(TEXT("giantCamera"),K->UsesGiantCamera());
        const AVeyrKnight::FGiantCameraEvidence& G=K->GetGiantCameraEvidence();
        TSharedPtr<FJsonObject> C=MakeShared<FJsonObject>();
        C->SetNumberField(TEXT("verticalFov"),G.VerticalFov);C->SetNumberField(TEXT("horizontalFov"),K->CombatCamera?K->CombatCamera->FieldOfView:0.f);
        C->SetNumberField(TEXT("armCm"),G.ArmCm);C->SetNumberField(TEXT("pitchMax"),G.PitchMax);C->SetNumberField(TEXT("feetAngle"),G.FeetAngle);
        C->SetNumberField(TEXT("strikeWeight"),G.StrikeWeight);C->SetNumberField(TEXT("underBelly"),G.UnderBelly);C->SetNumberField(TEXT("lockBlend"),G.LockBlend);
        O->SetObjectField(TEXT("cameraNow"),C);
    }
    if(D)O->SetNumberField(TEXT("bodyScale"),D->BodyScale);
    O->SetStringField(TEXT("scope"),TEXT("geometric: combat camera component pose, horizontal FOV, viewport aspect (16:9 when headless); only frames with the knight as view target (no blend) after the encounter starts; shares weighted by game seconds; occlusion by the dragon's own body is not counted"));
    return O;
}
