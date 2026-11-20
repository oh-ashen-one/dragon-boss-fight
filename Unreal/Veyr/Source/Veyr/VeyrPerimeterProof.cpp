#include "VeyrPerimeterProof.h"
#include "VeyrArena.h"
#include "VeyrDragon.h"
#include "VeyrKnight.h"
#include "Components/CapsuleComponent.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "Dom/JsonObject.h"
#include "Dom/JsonValue.h"
#include "Engine/World.h"

namespace
{
    // Walk, sprint, roll: start distance inside the line and push seconds after the start.
    constexpr float StartBack[3]={130.f,280.f,260.f};
    constexpr float PushSeconds[3]={1.05f,.95f,1.35f};
    constexpr float SettleSeconds=.25f;
    // Escaped: past the start of the collision ring behind the walls (VeyrArena BuildPerimeterBlockers).
    constexpr float EscapeCm=250.f;
    const TCHAR* SpeedName(int32 S){return S==0?TEXT("walk"):S==1?TEXT("sprint"):TEXT("roll");}
}

bool FVeyrPerimeterProof::Begin(UWorld* InWorld,AVeyrKnight* InKnight,AVeyrDragon* InDragon,AVeyrArena* InArena,FHooks InHooks)
{
    World=InWorld;Knight=InKnight;Dragon=InDragon;Arena=InArena;Hooks=MoveTemp(InHooks);
    if(!InWorld||!InKnight||!InArena||InArena->CourtBoundary.Num()<3)return false;
    if(InDragon)InDragon->BeginShowcase(); // passive rehearsal actor; never attacks
    const TArray<FVector2D>& B=InArena->CourtBoundary;const int32 N=B.Num();
    FVector2D C(0,0);for(const FVector2D& P:B)C+=P;C/=N;
    TArray<FVector2D> Normals;
    for(int32 I=0;I<N;++I)
    {
        const FVector2D A=B[I],E=B[(I+1)%N];const FVector2D D=(E-A).GetSafeNormal();FVector2D Out(D.Y,-D.X);
        if(FVector2D::DotProduct(Out,(A+E)*.5f-C)<0)Out=-Out;
        Normals.Add(Out);
        const float Len=FVector2D::Distance(A,E);
        for(int32 Speed=0;Speed<3;++Speed)
        {
            const float Step=Speed==0?100.f:50.f;
            for(float S=Step*.5f;S<Len;S+=Step)
            {
                FProbe P;P.Target=A+D*S;P.Dir=Out;P.Start=P.Target-Out*StartBack[Speed];P.Speed=Speed;P.Edge=I;
                Probes.Add(P);
            }
        }
    }
    for(int32 I=0;I<N;++I)
    {
        const FVector2D V=B[I];const FVector2D Bisector=(Normals[(I+N-1)%N]+Normals[I]).GetSafeNormal();
        for(float Angle:{-60.f,-30.f,0.f,30.f,60.f})
            for(int32 Speed=0;Speed<3;++Speed)
            {
                const float R=FMath::DegreesToRadians(Angle);
                const FVector2D Dir(Bisector.X*FMath::Cos(R)-Bisector.Y*FMath::Sin(R),Bisector.X*FMath::Sin(R)+Bisector.Y*FMath::Cos(R));
                FProbe P;P.Target=V;P.Dir=Dir;P.Start=V-Dir*(StartBack[Speed]+60.f);P.Speed=Speed;P.Angle=Angle;P.Edge=I;P.bVertex=true;
                Probes.Add(P);
            }
    }
    float Total=0.f;for(const FProbe& P:Probes)Total+=SettleSeconds+PushSeconds[P.Speed]+.1f;
    LimitSeconds=Total+60.f;
    UE_LOG(LogTemp,Display,TEXT("VEYR_PERIMETER_PROOF probes=%d boundaryVertices=%d gameSeconds=%.0f"),Probes.Num(),N,Total);
    return Probes.Num()>0;
}

void FVeyrPerimeterProof::StartProbe(double Elapsed)
{
    AVeyrKnight* K=Knight.Get();if(!K)return;
    const FProbe& P=Probes[Index];
    const FVector Start=Arena->GetActorTransform().TransformPosition(FVector(P.Start.X,P.Start.Y,0))+FVector(0,0,SpawnZ);
    K->SetActorLocationAndRotation(Start,FRotator(0,FMath::RadiansToDegrees(FMath::Atan2(P.Dir.Y,P.Dir.X)),0),false,nullptr,ETeleportType::TeleportPhysics);
    if(UCharacterMovementComponent* M=K->GetCharacterMovement()){M->StopMovementImmediately();M->SetMovementMode(MOVE_Walking);}
    K->Stamina=100.f;K->Health=100.f;
    K->SetSprintRequested(false);K->SetReplayInput(FVector::ZeroVector,false,false,false,false,false,false);
    PhaseStart=Elapsed;bPushing=false;MaxOutside=-1e9f;MinBottom=1e9f;
}

void FVeyrPerimeterProof::EndProbe(double Elapsed)
{
    AVeyrKnight* K=Knight.Get();AVeyrArena* A=Arena.Get();if(!K||!A)return;
    const FProbe& P=Probes[Index];
    const FVector L=K->GetActorLocation();
    const float Half=K->GetCapsuleComponent()->GetScaledCapsuleHalfHeight();
    const float Floor=A->GetActorLocation().Z;
    const float Outside=A->CourtOutsideDistance(L);
    const UCharacterMovementComponent* M=K->GetCharacterMovement();
    const bool bFalling=M&&M->IsFalling()&&L.Z-Half<Floor-50.f;
    const bool bEscaped=Outside>EscapeCm||MaxOutside>EscapeCm||MinBottom<Floor-300.f||bFalling;
    WorstOutside=FMath::Max(WorstOutside,MaxOutside);++Completed;
    auto Record=[&](TArray<TSharedPtr<FJsonValue>>& List)
    {
        TSharedPtr<FJsonObject> O=MakeShared<FJsonObject>();
        O->SetStringField(TEXT("speed"),SpeedName(P.Speed));O->SetBoolField(TEXT("vertex"),P.bVertex);O->SetNumberField(TEXT("edge"),P.Edge);
        O->SetNumberField(TEXT("angle"),P.Angle);O->SetNumberField(TEXT("targetX"),FMath::RoundToFloat(P.Target.X));O->SetNumberField(TEXT("targetY"),FMath::RoundToFloat(P.Target.Y));
        O->SetNumberField(TEXT("endX"),FMath::RoundToFloat(L.X));O->SetNumberField(TEXT("endY"),FMath::RoundToFloat(L.Y));O->SetNumberField(TEXT("endZ"),FMath::RoundToFloat(L.Z));
        O->SetNumberField(TEXT("maxOutsideCm"),FMath::RoundToFloat(MaxOutside));O->SetNumberField(TEXT("minBottomZ"),FMath::RoundToFloat(MinBottom));
        O->SetBoolField(TEXT("falling"),bFalling);
        List.Add(MakeShared<FJsonValueObject>(O));
    };
    if(bEscaped)
    {
        ++Escapes;Record(EscapeList);
        UE_LOG(LogTemp,Warning,TEXT("VEYR_PERIMETER_ESCAPE %s %s edge=%d angle=%.0f target=(%.0f,%.0f) end=(%.0f,%.0f,%.0f) maxOutside=%.0f"),
            SpeedName(P.Speed),P.bVertex?TEXT("vertex"):TEXT("edge"),P.Edge,P.Angle,P.Target.X,P.Target.Y,L.X,L.Y,L.Z,MaxOutside);
    }
    else if(MaxOutside>60.f){++IntoWall;if(DeepList.Num()<60)Record(DeepList);}
}

void FVeyrPerimeterProof::Drive(double Elapsed,float Dt)
{
    AVeyrKnight* K=Knight.Get();AVeyrArena* A=Arena.Get();
    if(bDone||!K||!A)return;
    if(Index<0){Index=0;StartProbe(Elapsed);return;}
    const FProbe& P=Probes[Index];
    const double T=Elapsed-PhaseStart;
    if(bPushing)
    {
        const FVector L=K->GetActorLocation();
        MaxOutside=FMath::Max(MaxOutside,A->CourtOutsideDistance(L));
        MinBottom=FMath::Min(MinBottom,static_cast<float>(L.Z-K->GetCapsuleComponent()->GetScaledCapsuleHalfHeight()));
    }
    if(!bPushing&&T>=SettleSeconds){bPushing=true;PhaseStart=Elapsed;}
    if(bPushing)
    {
        const FVector Move(P.Dir.X,P.Dir.Y,0);
        K->Stamina=100.f;
        K->SetSprintRequested(P.Speed==1);
        // Roll: press once at the start, again whenever the knight is free to act.
        const bool bRoll=P.Speed==2&&(T<.05||K->Action==EVeyrKnightAction::Ready);
        K->SetReplayInput(Move,false,false,bRoll,false,false,false);
        if(Elapsed-PhaseStart>=PushSeconds[P.Speed])
        {
            EndProbe(Elapsed);
            if(++Index>=Probes.Num())
            {
                bDone=true;K->SetSprintRequested(false);K->SetReplayInput(FVector::ZeroVector,false,false,false,false,false,false);
                UE_LOG(LogTemp,Display,TEXT("VEYR_PERIMETER_RESULT probes=%d escapes=%d intoWall=%d worstOutsideCm=%.0f"),Completed,Escapes,IntoWall,WorstOutside);
                if(Hooks.Finish)Hooks.Finish(Escapes==0,FString::Printf(TEXT("perimeter probe: %d probes, %d escapes, %d into a wall over 60 cm"),Completed,Escapes,IntoWall));
                return;
            }
            StartProbe(Elapsed);
        }
    }
    else K->SetReplayInput(FVector::ZeroVector,false,false,false,false,false,false);
}

TSharedPtr<FJsonObject> FVeyrPerimeterProof::Evidence() const
{
    TSharedPtr<FJsonObject> O=MakeShared<FJsonObject>();
    O->SetNumberField(TEXT("probes"),Probes.Num());O->SetNumberField(TEXT("completed"),Completed);
    O->SetNumberField(TEXT("escapes"),Escapes);O->SetNumberField(TEXT("intoWallOver60Cm"),IntoWall);
    O->SetNumberField(TEXT("worstOutsideCm"),FMath::RoundToFloat(WorstOutside));O->SetBoolField(TEXT("done"),bDone);
    O->SetArrayField(TEXT("escapeList"),EscapeList);O->SetArrayField(TEXT("intoWallList"),DeepList);
    if(const AVeyrArena* A=Arena.Get())
    {
        TArray<TSharedPtr<FJsonValue>> Poly;
        for(const FVector2D& P:A->CourtBoundary){TArray<TSharedPtr<FJsonValue>> XY;XY.Add(MakeShared<FJsonValueNumber>(P.X));XY.Add(MakeShared<FJsonValueNumber>(P.Y));Poly.Add(MakeShared<FJsonValueArray>(XY));}
        O->SetArrayField(TEXT("boundary"),Poly);O->SetNumberField(TEXT("perimeterBlockers"),A->PerimeterBlockerCount);
        O->SetBoolField(TEXT("fortress"),A->bFortressCandidate);O->SetBoolField(TEXT("fortressAssetsReady"),A->bFortressAssetsReady);
    }
    return O;
}
