#include "VeyrHUD.h"
#include "VeyrGameMode.h"
#include "VeyrKnight.h"
#include "VeyrDragon.h"
#include "CanvasItem.h"
#include "Engine/Canvas.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "GlobalRenderResources.h"

namespace
{
    const FLinearColor Ivory(.82f,.83f,.78f,1.f);
    const FLinearColor Quiet(.53f,.57f,.58f,1.f);
    const FLinearColor Pewter(.31f,.35f,.36f,.85f);
    const FLinearColor Bronze(.48f,.38f,.23f,1.f);
    const FLinearColor Ink(.009f,.013f,.017f,.86f);
}

void AVeyrHUD::Text(const FString& Value,float X,float Y,float Height,const FLinearColor& Color,bool bCentered)
{
    UFont* Font=GEngine->GetMediumFont();
    float BaseWidth=0.f,BaseHeight=0.f;
    GetTextSize(TEXT("Ag"),BaseWidth,BaseHeight,Font,1.f);
    const float FontScale=Height*Unit/FMath::Max(1.f,BaseHeight);
    float Width=0.f,MeasuredHeight=0.f;
    GetTextSize(Value,Width,MeasuredHeight,Font,FontScale);
    const float ScreenX=X*Unit-(bCentered?Width*.5f:0.f);
    // Small crisp shadow keeps type readable on fire and pale stone without
    // surrounding every label with an opaque rectangle.
    DrawText(Value,FLinearColor(0,0,0,Color.A*.9f),ScreenX+Unit,Y*Unit+Unit,Font,FontScale,false);
    DrawText(Value,Color,ScreenX,Y*Unit,Font,FontScale,false);
}

void AVeyrHUD::Line(float X1,float Y1,float X2,float Y2,const FLinearColor& Color,float Width)
{
    DrawLine(X1*Unit,Y1*Unit,X2*Unit,Y2*Unit,Color,FMath::Max(.7f,Width*Unit));
}

void AVeyrHUD::Rect(float X,float Y,float Width,float Height,const FLinearColor& Color)
{
    DrawRect(Color,X*Unit,Y*Unit,Width*Unit,Height*Unit);
}

void AVeyrHUD::Polygon(const TArray<FVector2D>& Points,const FLinearColor& Color)
{
    if(Points.Num()<3)return;
    // All supplied silhouettes are convex. Engine white texture supplies a
    // solid fill; there are no downloaded icon/material or UMG dependencies.
    for(int32 I=1;I<Points.Num()-1;++I)
    {
        FCanvasTriangleItem Triangle(Points[0]*Unit,Points[I]*Unit,Points[I+1]*Unit,GWhiteTexture);
        Triangle.SetColor(Color);Triangle.BlendMode=SE_BLEND_Translucent;
        Canvas->DrawItem(Triangle);
    }
}

void AVeyrHUD::Diamond(float X,float Y,float Radius,const FLinearColor& Color,bool bFilled)
{
    if(bFilled)Polygon({{X,Y-Radius},{X+Radius,Y},{X,Y+Radius},{X-Radius,Y}},Color);
    else
    {
        Line(X,Y-Radius,X+Radius,Y,Color);Line(X+Radius,Y,X,Y+Radius,Color);
        Line(X,Y+Radius,X-Radius,Y,Color);Line(X-Radius,Y,X,Y-Radius,Color);
    }
}

void AVeyrHUD::Meter(float X,float Y,float Width,float Height,float Value,float Trail,const FLinearColor& Color)
{
    Value=FMath::Clamp(Value,0.f,1.f);Trail=FMath::Clamp(Trail,Value,1.f);
    Rect(X-1,Y-2,Width+2,Height+4,Ink);
    Rect(X,Y,Width,Height,FLinearColor(.095f,.105f,.105f,.8f));
    if(Trail>Value)Rect(X,Y,Width*Trail,Height,FLinearColor(.40f,.31f,.22f,.85f));
    const float Filled=Width*Value;
    if(Filled>.1f)
    {
        const float Bevel=FMath::Min(Height*.5f,Filled*.5f);
        Polygon({{X,Y},{X+Filled-Bevel,Y},{X+Filled,Y+Height*.5f},{X+Filled-Bevel,Y+Height},{X,Y+Height}},Color);
        Line(X,Y+.5f,X+FMath::Max(0.f,Filled-Bevel),Y+.5f,FLinearColor(.83f,.82f,.72f,.25f),.7f);
    }
    Line(X,Y-3,X+Width,Y-3,Pewter,.7f);
    Line(X,Y+Height+3,X+Width,Y+Height+3,FLinearColor(.19f,.23f,.24f,.7f),.7f);
    Line(X-4,Y-4,X-4,Y+Height+4,Bronze);
    Line(X+Width+4,Y-4,X+Width+4,Y+Height+4,Pewter);
}

void AVeyrHUD::SwordIcon(float X,float Y)
{
    // A broad wooden hull, tapered bow, keel and longitudinal planks. The
    // equipment icon describes the new boat-shaped greatsword, not a steel blade.
    const TArray<FVector2D> Hull={{X,Y-36},{X+12,Y-22},{X+17,Y-2},{X+13,Y+16},
        {X,Y+29},{X-13,Y+16},{X-17,Y-2},{X-12,Y-22}};
    Polygon(Hull,FLinearColor(.36f,.25f,.14f,1.f));
    for(int32 I=0;I<Hull.Num();++I)
    {
        const FVector2D A=Hull[I],B=Hull[(I+1)%Hull.Num()];Line(A.X,A.Y,B.X,B.Y,Bronze,1.2f);
    }
    Line(X,Y-31,X,Y+23,FLinearColor(.67f,.52f,.30f),1.4f);
    Line(X-6,Y-20,X-6,Y+15,FLinearColor(.14f,.11f,.08f),1.f);
    Line(X+6,Y-20,X+6,Y+15,FLinearColor(.14f,.11f,.08f),1.f);
    Line(X-13,Y-3,X+13,Y-3,FLinearColor(.17f,.14f,.10f),1.4f);
    Line(X-10,Y+12,X+10,Y+12,FLinearColor(.17f,.14f,.10f),1.4f);
    Rect(X-2,Y+28,4,17,FLinearColor(.40f,.39f,.32f));
    Line(X-10,Y+28,X+10,Y+28,Ivory,2.f);
    for(int32 I=0;I<3;++I)Line(X-3,Y+32+I*4,X+3,Y+34+I*4,Ink,.8f);
    Diamond(X,Y+48,3,Bronze,true);
}

void AVeyrHUD::FlaskIcon(float X,float Y,bool bEmpty)
{
    const FLinearColor Glass=bEmpty?FLinearColor(.22f,.25f,.25f):FLinearColor(.53f,.24f,.07f);
    Polygon({{X-7,Y-10},{X+7,Y-10},{X+13,Y},{X+10,Y+17},{X-10,Y+17},{X-13,Y}},Ink);
    Polygon({{X-6,Y-7},{X+6,Y-7},{X+10,Y+1},{X+8,Y+14},{X-8,Y+14},{X-10,Y+1}},Glass);
    if(!bEmpty)
    {
        Polygon({{X,Y-3},{X+4,Y+5},{X+2,Y+11},{X-3,Y+11},{X-5,Y+6}},FLinearColor(.92f,.55f,.15f));
        Line(X-6,Y+2,X-5,Y+9,FLinearColor(.91f,.71f,.36f),1.f);
    }
    Rect(X-4,Y-18,8,9,Glass);Rect(X-6,Y-21,12,4,Bronze);
    Line(X-9,Y+17,X+9,Y+17,Pewter);
}

void AVeyrHUD::Keycap(const FString& Key,float X,float Y)
{
    Rect(X,Y,18,18,FLinearColor(.02f,.025f,.03f,.65f));
    Line(X,Y+17,X+18,Y+17,Pewter);
    Text(Key,X+9,Y+2,12,Ivory,true);
}

void AVeyrHUD::DrawHUD()
{
    Super::DrawHUD();
    if(!Canvas||!GEngine||Canvas->SizeX<1||Canvas->SizeY<1)return;
    const AVeyrGameMode* Mode=GetWorld()->GetAuthGameMode<AVeyrGameMode>();
    if(!Mode||!Mode->Knight||!Mode->Dragon)return;
    const AVeyrKnight* Knight=Mode->Knight;const AVeyrDragon* Dragon=Mode->Dragon;
    // Uniform scaling preserves icon shapes on 4:3 and ultrawide displays;
    // anchors use the actual viewport, with a legible minimum on small windows.
    Unit=FMath::Max(.75f,FMath::Min(Canvas->SizeX/1280.f,Canvas->SizeY/720.f));
    const float W=Canvas->SizeX/Unit,H=Canvas->SizeY/Unit;
    const float Margin=FMath::Min(40.f,W*.045f);
    const float Health=FMath::Clamp(Knight->Health/100.f,0.f,1.f);
    const float Stamina=FMath::Clamp(Knight->Stamina/100.f,0.f,1.f);
    const float BossHealth=FMath::Clamp(Dragon->Health/FMath::Max(1.f,Dragon->MaxHealth),0.f,1.f);
    const float Dt=FMath::Min(GetWorld()->GetDeltaSeconds(),.1f);
    auto DamageTrail=[&](float Value,float& Previous,float& Trail,float& Delay)
    {
        if(Value<Previous-.0001f)Delay=.35f;
        if(Value>=Trail)Trail=Value;
        Delay=FMath::Max(0.f,Delay-Dt);
        if(Delay<=0.f)Trail=FMath::FInterpConstantTo(Trail,Value,Dt,.5f);
        Previous=Value;
    };
    DamageTrail(Health,PreviousHealth,HealthTrail,HealthTrailDelay);
    DamageTrail(BossHealth,PreviousBoss,BossTrail,BossTrailDelay);

    const float ResourceWidth=FMath::Min(264.f,W*.34f);
    Text(TEXT("HEALTH"),Margin+17,29,12,Quiet);
    Diamond(Margin+3,52,5,FLinearColor(.57f,.21f,.17f),true);
    Meter(Margin+17,48,ResourceWidth,7,Health,HealthTrail,FLinearColor(.54f,.15f,.13f));
    Text(TEXT("STAMINA"),Margin+17,69,12,Quiet);
    Diamond(Margin+3,91,3,FLinearColor(.45f,.56f,.40f),true);
    Meter(Margin+17,88,ResourceWidth*.82f,4,Stamina,Stamina,FLinearColor(.38f,.49f,.34f));

    // Only equipped items occupy the lower-left corner. A few short etched
    // strokes replace large inventory tiles and leave the central floor clear.
    const float EquipmentX=Margin+27,EquipmentY=H-169;
    Rect(Margin-5,EquipmentY-43,61,96,FLinearColor(.012f,.017f,.022f,.42f));
    Line(Margin-5,EquipmentY-43,Margin+9,EquipmentY-43,Pewter);
    Line(Margin-5,EquipmentY-43,Margin-5,EquipmentY-31,Pewter);
    Line(Margin+56,EquipmentY+53,Margin+42,EquipmentY+53,Pewter);
    SwordIcon(EquipmentX,EquipmentY);
    Text(TEXT("TIMBER GREATSWORD"),Margin+75,EquipmentY-14,14,Ivory);
    Text(Knight->IsTwoHanded()?TEXT("TWO-HANDED"):TEXT("ONE-HANDED"),Margin+75,EquipmentY+11,12,Quiet);
    Keycap(TEXT("E"),Margin+181,EquipmentY+9);
    const float FlaskY=H-83;
    FlaskIcon(EquipmentX,FlaskY,Knight->HealingCharges<=0);
    Text(FString::FromInt(Knight->HealingCharges),Margin+47,FlaskY+2,18,Ivory);
    Text(TEXT("EMBER DRAUGHT"),Margin+75,FlaskY-12,14,Ivory);
    Keycap(TEXT("Q"),Margin+75,FlaskY+11);

    const float BossWidth=FMath::Min(660.f,W*.56f);
    const float BossX=(W-BossWidth)*.5f;
    Text(TEXT("Veyr, the Cinder Warden"),W*.5f,H-56,17,Ivory,true);
    Meter(BossX,H-29,BossWidth,6,BossHealth,BossTrail,FLinearColor(.44f,.12f,.10f));
    Diamond(BossX-13,H-26,4,Bronze);Diamond(BossX+BossWidth+13,H-26,4,Bronze);

    const float Now=GetWorld()->GetTimeSeconds();
    const bool bCaptured=Knight->IsMouseCaptured();
    if(bCaptured&&!bWasCaptured)CaptureHintUntil=Now+5.f;
    bWasCaptured=bCaptured;
    const bool bTerminal=Knight->IsDead()||Dragon->IsDead();
    if(bTerminal)
    {
        const float Y=H*.43f;
        Rect(W*.5f-215,Y-16,430,105,FLinearColor(.008f,.012f,.018f,.72f));
        Line(W*.5f-170,Y-15,W*.5f-10,Y-15,Pewter);Line(W*.5f+10,Y-15,W*.5f+170,Y-15,Pewter);
        Diamond(W*.5f,Y-15,4,Bronze);
        Text(Knight->IsDead()?TEXT("YOU FELL"):TEXT("CINDER EXTINGUISHED"),W*.5f,Y+8,25,Ivory,true);
        Text(TEXT("R  /  Rise again"),W*.5f,Y+53,14,Ivory,true);
    }
    else if(!Knight->IsReplayControlled())
    {
        if(!bCaptured)
        {
            const float Y=H*.48f;
            Text(Knight->HasEnteredEncounter()?TEXT("CLICK OR ENTER TO CONTROL"):TEXT("CLICK OR ENTER TO BEGIN"),W*.5f,Y,17,Ivory,true);
            Text(TEXT("Esc releases the mouse"),W*.5f,Y+28,12,Quiet,true);
        }
        else if(Now<CaptureHintUntil)
            Text(TEXT("Esc  /  Release mouse"),W-Margin-145,29,12,Quiet);
    }
}
