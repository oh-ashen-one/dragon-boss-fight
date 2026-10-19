#include "VeyrHUD.h"
#include "VeyrGameMode.h"
#include "VeyrKnight.h"
#include "VeyrDragon.h"
#include "Engine/Canvas.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "GameFramework/PlayerController.h"
void AVeyrHUD::Bar(float X,float Y,float W,float H,float Ratio,const FLinearColor& Color)
{
    DrawRect(FLinearColor(.02f,.025f,.025f,.9f),(X-2)*ScaleX,(Y-2)*ScaleY,(W+4)*ScaleX,(H+4)*ScaleY);
    DrawRect(FLinearColor(.18f,.16f,.12f),X*ScaleX,Y*ScaleY,W*ScaleX,H*ScaleY);
    DrawRect(Color,X*ScaleX,Y*ScaleY,W*FMath::Clamp(Ratio,0.f,1.f)*ScaleX,H*ScaleY);
}
void AVeyrHUD::Label(const FString& Text,float X,float Y,float Size,const FLinearColor& Color)
{
    DrawText(Text,Color,X*ScaleX,Y*ScaleY,GEngine->GetSmallFont(),Size*FMath::Min(ScaleX,ScaleY),false);
}
void AVeyrHUD::DrawExposedHeadMarker(const AVeyrDragon* Dragon)
{
    if(!PlayerOwner||!Dragon->IsHeadExposed())return;
    FVector ViewLocation;FRotator ViewRotation;
    PlayerOwner->GetPlayerViewPoint(ViewLocation,ViewRotation);
    const FVector Head=Dragon->GetHeadLocation();
    const FVector ToHead=Head-ViewLocation;
    const FRotationMatrix ViewAxes(ViewRotation);
    const double Forward=FVector::DotProduct(ToHead,ViewAxes.GetUnitAxis(EAxis::X));
    FVector2D Projected=FVector2D::ZeroVector;
    const bool bProjected=PlayerOwner->ProjectWorldLocationToScreen(Head,Projected);
    const FVector2D Center(Canvas->SizeX*.5f,Canvas->SizeY*.5f);
    // Keep direction guidance clear of resource bars, the boss HUD and footer.
    const FVector2D SafeExtent(Canvas->SizeX*.5f-80.f*ScaleX,Canvas->SizeY*.5f-145.f*ScaleY);
    const FVector2D Relative=Projected-Center;
    const bool bOnscreen=bProjected&&Forward>0&&FMath::Abs(Relative.X)<SafeExtent.X&&FMath::Abs(Relative.Y)<SafeExtent.Y;
    FVector2D Point=Projected;
    FVector2D Direction;
    if(!bOnscreen)
    {
        Direction=bProjected&&Forward>0?Relative:FVector2D(
            FVector::DotProduct(ToHead,ViewAxes.GetUnitAxis(EAxis::Y)),
            -FVector::DotProduct(ToHead,ViewAxes.GetUnitAxis(EAxis::Z)));
        if(Direction.IsNearlyZero())Direction=FVector2D(0,1);
        Direction.Normalize();
        const double EdgeScale=FMath::Min(SafeExtent.X/FMath::Max(.001,FMath::Abs(Direction.X)),
            SafeExtent.Y/FMath::Max(.001,FMath::Abs(Direction.Y)));
        Point=Center+Direction*EdgeScale;
    }
    const float Unit=FMath::Min(ScaleX,ScaleY);
    const FLinearColor Gold(1.f,.78f,.23f);
    auto Stroke=[&](const FVector2D& A,const FVector2D& B)
    {
        DrawLine(A.X,A.Y,B.X,B.Y,FLinearColor(0,0,0,.95f),5.f*Unit);
        DrawLine(A.X,A.Y,B.X,B.Y,Gold,2.f*Unit);
    };
    const FVector2D HeadAnchor=Point;
    if(bOnscreen)
    {
        if(const AVeyrKnight* Knight=Cast<AVeyrKnight>(PlayerOwner->GetPawn()))
        {
            FVector2D Minimum(TNumericLimits<double>::Max(),TNumericLimits<double>::Max());
            FVector2D Maximum(-TNumericLimits<double>::Max(),-TNumericLimits<double>::Max());
            int32 ProjectedCorners=0;
            // A body/arm envelope in view space, not a fixed central-screen box.
            // Include the helmet and boots; do not attach text to either one.
            const FVector Side=ViewAxes.GetUnitAxis(EAxis::Y)*95.f;
            for(float Height:{0.f,255.f})for(float Sign:{-1.f,1.f})
            {
                FVector2D Corner;
                if(PlayerOwner->ProjectWorldLocationToScreen(Knight->GetFootLocation()+FVector(0,0,Height)+Side*Sign,Corner))
                {
                    Minimum.X=FMath::Min(Minimum.X,Corner.X);Minimum.Y=FMath::Min(Minimum.Y,Corner.Y);
                    Maximum.X=FMath::Max(Maximum.X,Corner.X);Maximum.Y=FMath::Max(Maximum.Y,Corner.Y);
                    ++ProjectedCorners;
                }
            }
            if(ProjectedCorners==4)
            {
                Minimum-=FVector2D(18.f*ScaleX,18.f*ScaleY);Maximum+=FVector2D(18.f*ScaleX,18.f*ScaleY);
                auto OverlapsKnight=[&](const FVector2D& Candidate)
                {
                    const double LabelLeft=FMath::Clamp(Candidate.X/ScaleX-65.,12.,1090.)*ScaleX-5.f*ScaleX;
                    const double Left=FMath::Min(Candidate.X-12.f*Unit,LabelLeft);
                    const double Right=FMath::Max(Candidate.X+12.f*Unit,LabelLeft+180.f*ScaleX);
                    return Right>Minimum.X&&Left<Maximum.X&&Candidate.Y+38.f*ScaleY>Minimum.Y&&Candidate.Y-12.f*Unit<Maximum.Y;
                };
                if(OverlapsKnight(Point))
                {
                    const FVector2D Candidates[]={
                        FVector2D(Point.X,Minimum.Y-48.f*ScaleY),
                        FVector2D(Maximum.X+85.f*ScaleX,Point.Y-25.f*ScaleY),
                        FVector2D(Minimum.X-130.f*ScaleX,Point.Y-25.f*ScaleY)};
                    for(FVector2D Candidate:Candidates)
                    {
                        Candidate.X=FMath::Clamp(Candidate.X,Center.X-SafeExtent.X,Center.X+SafeExtent.X);
                        Candidate.Y=FMath::Clamp(Candidate.Y,Center.Y-SafeExtent.Y,Center.Y+SafeExtent.Y);
                        if(!OverlapsKnight(Candidate)) { Point=Candidate;break; }
                    }
                }
            }
        }
        if(!Point.Equals(HeadAnchor,.5f))
        {
            // Keep the target position truthful while moving the bulky marker
            // and label off the player's silhouette. The leader is intentionally thin.
            const FVector2D LeaderDirection=(Point-HeadAnchor).GetSafeNormal();
            const FVector2D End=Point-LeaderDirection*14.f*Unit;
            DrawLine(HeadAnchor.X,HeadAnchor.Y,End.X,End.Y,FLinearColor(0,0,0,.9f),3.f*Unit);
            DrawLine(HeadAnchor.X,HeadAnchor.Y,End.X,End.Y,Gold,1.f*Unit);
        }
    }
    if(bOnscreen)
    {
        const FVector2D Top=Point+FVector2D(0,-12)*Unit,Right=Point+FVector2D(12,0)*Unit;
        const FVector2D Bottom=Point+FVector2D(0,12)*Unit,Left=Point+FVector2D(-12,0)*Unit;
        Stroke(Top,Right);Stroke(Right,Bottom);Stroke(Bottom,Left);Stroke(Left,Top);
    }
    else
    {
        const FVector2D Side(-Direction.Y,Direction.X);
        const FVector2D Tip=Point+Direction*12.f*Unit,Base=Point-Direction*8.f*Unit;
        Stroke(Base+Side*8.f*Unit,Tip);Stroke(Tip,Base-Side*8.f*Unit);
        Stroke(Point-Direction*16.f*Unit,Tip);
    }
    const FString Text=Forward<=0?TEXT("EXPOSED HEAD - TURN"):TEXT("EXPOSED HEAD");
    const float LabelX=FMath::Clamp(static_cast<float>(Point.X/ScaleX)-65.f,12.f,1090.f);
    const float LabelY=static_cast<float>(Point.Y/ScaleY)+19.f;
    DrawRect(FLinearColor(0,0,0,.72f),(LabelX-5.f)*ScaleX,(LabelY-2.f)*ScaleY,180.f*ScaleX,19.f*ScaleY);
    Label(Text,LabelX,LabelY,.95f,Gold);
}
void AVeyrHUD::DrawHUD()
{
    Super::DrawHUD();
    if(!Canvas)return;
    const AVeyrGameMode* Mode=GetWorld()->GetAuthGameMode<AVeyrGameMode>();
    if(!Mode||!Mode->Knight||!Mode->Dragon)return;
    const AVeyrKnight* Knight=Mode->Knight;
    const AVeyrDragon* Dragon=Mode->Dragon;
    ScaleX=Canvas->SizeX/1280.f;ScaleY=Canvas->SizeY/720.f;
    Bar(36,34,270,16,Knight->Health/100.f,FLinearColor(.58f,.15f,.12f));
    Bar(36,57,235,9,Knight->Stamina/100.f,FLinearColor(.43f,.58f,.31f));
    Label(FString::Printf(TEXT("EMBER DRAUGHTS  %d"),Knight->HealingCharges),36,76,1.f);
    Label(Knight->bLockedOn?TEXT("LOCK ON"):TEXT("FREE CAMERA"),36,99,.85f);
    if(!Knight->IsReplayControlled())Label(Knight->IsMouseCaptured()?TEXT("ESC RELEASES MOUSE"):
        Knight->HasEnteredEncounter()?TEXT("CLICK / ENTER TO CONTROL | ESC RELEASES MOUSE"):TEXT("CLICK / ENTER TO BEGIN | ESC RELEASES MOUSE"),36,118,.85f);
    Label(TEXT("VEYR / THE CINDER WARDEN"),930,29,1.f);
    if(!Knight->bImportedPresentationActive||!Dragon->bUsingCustomuseVisual)
        Label(TEXT("PROTOTYPE / TEMPORARY CHARACTER ART"),900,50,.8f);
    Label(TEXT("V E Y R ,  T H E  C I N D E R  W A R D E N"),422,630,1.f);
    Bar(230,651,820,10,Dragon->Health/Dragon->MaxHealth,FLinearColor(.58f,.2f,.13f));
    for(int32 I=0;I<4;++I)Bar(450+I*98,669,85,4,Dragon->GetLegStagger(I)/100.f,FLinearColor(.83f,.58f,.23f));
    Label(Dragon->GetStateLabel().ToString(),486,680,.85f);
    if(!Knight->IsDead())DrawExposedHeadMarker(Dragon);
    Label(TEXT("WASD move | Space jump | Shift roll | J/LMB strike | K heavy"),24,698,.8f);
    Label(TEXT("F/RMB guard | Q heal | Tab lock | R restart after death/victory"),710,698,.8f);
    if(Mode->EncounterSeconds<6)
    {
        Label(TEXT("THE DROWNED CATHEDRAL"),440,188,1.8f);
        Label(TEXT("Break a leg's balance. Reach the fallen crown."),430,223,1.05f);
    }
    if(Knight->IsDead()||Dragon->IsDead())
    {
        DrawRect(FLinearColor(0,0,0,.78f),0,275*ScaleY,Canvas->SizeX,145*ScaleY);
        Label(Knight->IsDead()?TEXT("YOU FELL"):TEXT("CINDER EXTINGUISHED"),480,300,2.1f);
        Label(TEXT("Press R to rise again"),535,358,1.1f);
    }
}
