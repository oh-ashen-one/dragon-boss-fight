#include "VeyrHUD.h"
#include "VeyrGameMode.h"
#include "VeyrKnight.h"
#include "VeyrDragon.h"
#include "CanvasItem.h"
#include "Engine/Canvas.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "GlobalRenderResources.h"
#include "Engine/GameViewportClient.h"
#include "GameFramework/GameUserSettings.h"
#include "GameFramework/PlayerController.h"
#include "InputCoreTypes.h"
#include "UnrealClient.h"
#include "Widgets/SCompoundWidget.h"
#include "Widgets/Layout/SBorder.h"
#include "Widgets/Layout/SBox.h"
#include "Widgets/Layout/SScrollBox.h"
#include "Widgets/SBoxPanel.h"
#include "Widgets/Input/SButton.h"
#include "Widgets/Text/STextBlock.h"
#include "Styling/CoreStyle.h"

namespace
{
    const FLinearColor Ivory(.86f,.81f,.68f,1.f);
    const FLinearColor Quiet(.63f,.59f,.49f,1.f);
    const FLinearColor Pewter(.35f,.29f,.19f,.85f);
    const FLinearColor Bronze(.64f,.48f,.25f,1.f);
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
    // A wooden hull on a long handle; diagonal placement reads at relic-slot size.
    auto P=[&](float Across,float Along){return FVector2D(X+.73f*Along+.68f*Across,Y-.68f*Along+.73f*Across);};
    const TArray<FVector2D> Hull={P(0,28),P(8,18),P(11,6),P(9,-5),P(0,-13),P(-9,-5),P(-11,6),P(-8,18)};
    Polygon(Hull,FLinearColor(.22f,.13f,.055f));
    for(int32 I=0;I<Hull.Num();++I){const auto A=Hull[I],B=Hull[(I+1)%Hull.Num()];Line(A.X,A.Y,B.X,B.Y,Bronze,1.2f);}
    auto Stroke=[&](FVector2D A,FVector2D B,FLinearColor C,float Width=1.f){Line(A.X,A.Y,B.X,B.Y,C,Width);};
    Stroke(P(0,-27),P(0,-13),Ivory,3.f);Stroke(P(-5,-12),P(5,-12),Bronze,1.5f);
    Stroke(P(0,-10),P(0,25),FLinearColor(.72f,.53f,.28f),1.2f);
    for(float V:{-4.f,4.f,12.f,19.f}){const float R=V>15?6.f:8.f;Stroke(P(-R,V),P(R,V),FLinearColor(.48f,.31f,.14f),1.f);}
}

void AVeyrHUD::FlaskIcon(float X,float Y,bool bEmpty)
{
    // The equipped healing item is a handled cup, matching the actual prop.
    const FLinearColor Metal=bEmpty?FLinearColor(.24f,.21f,.16f):FLinearColor(.53f,.31f,.12f);
    Polygon({{X-13,Y-14},{X+13,Y-14},{X+10,Y+14},{X+6,Y+19},{X-6,Y+19},{X-10,Y+14}},Metal);
    Line(X-13,Y-14,X-10,Y+14,Bronze,1.2f);Line(X+13,Y-14,X+10,Y+14,Bronze,1.2f);
    for(int32 I=0;I<24;++I)
    {
        const float A=2.f*PI*I/24.f,B=2.f*PI*(I+1)/24.f;
        Line(X+13.f*FMath::Cos(A),Y-14+4.f*FMath::Sin(A),X+13.f*FMath::Cos(B),Y-14+4.f*FMath::Sin(B),Bronze,1.f);
    }
    Line(X+13,Y-9,X+21,Y-7,Bronze,2.f);Line(X+21,Y-7,X+20,Y+9,Bronze,2.f);Line(X+20,Y+9,X+10,Y+11,Bronze,2.f);
    Line(X-7,Y+20,X+7,Y+20,Bronze,2.f);Line(X-9,Y+23,X+9,Y+23,Pewter,2.f);
    if(!bEmpty){Polygon({{X-7,Y-14},{X-3,Y-24},{X,Y-18},{X+4,Y-27},{X+7,Y-14}},FLinearColor(.82f,.39f,.09f,.85f));}
}

void AVeyrHUD::Circle(float X,float Y,float Radius,const FLinearColor& Color,float Width)
{
    for(int32 I=0;I<48;++I)
    {
        const float A=2.f*PI*I/48.f,B=2.f*PI*(I+1)/48.f;
        Line(X+Radius*FMath::Cos(A),Y+Radius*FMath::Sin(A),X+Radius*FMath::Cos(B),Y+Radius*FMath::Sin(B),Color,Width);
    }
}
void AVeyrHUD::RelicSlot(float X,float Y,float Size)
{
    Rect(X,Y,Size,Size,Ink);Rect(X+3,Y+3,Size-6,Size-6,FLinearColor(.045f,.036f,.022f,.72f));
    Line(X,Y,X+Size,Y,Bronze);Line(X,Y+Size,X+Size,Y+Size,Pewter);
    Line(X,Y,X,Y+Size,Pewter);Line(X+Size,Y,X+Size,Y+Size,Bronze);
    for(float A:{0.f,Size})for(float B:{0.f,Size})
    {
        const float SX=A==0?1.f:-1.f,SY=B==0?1.f:-1.f;
        Line(X+A,Y+B,X+A+SX*8,Y+B+SY*3,Bronze);Line(X+A,Y+B,X+A+SX*3,Y+B+SY*8,Bronze);
    }
}
void AVeyrHUD::ControlLegend(float W,float H,bool bTerminal)
{
    // MediumFont's visible glyphs occupy roughly 80% of its measured line
    // height: 17 layout pixels gives about 13–14 readable pixels at 1280x720.
    const float X=W-334.f,Y=H-178.f;
    Rect(X-12,Y-10,310,122,FLinearColor(.012f,.011f,.009f,.64f));Line(X-12,Y-10,X+298,Y-10,Pewter,.7f);
    const TCHAR* Rows[]={TEXT("WASD  Move    SHIFT  Sprint"),TEXT("LMB  Attack    RMB  Guard"),TEXT("Q  Roll    SPACE  Blink"),TEXT("E  Grip    R  Heal"),TEXT("TAB  Lock    ESC  Menu")};
    for(int32 I=0;I<5;++I)Text(Rows[I],X,Y+I*22,17.f,Ivory);
    if(bTerminal)Text(TEXT("ENTER  Restart encounter"),X,Y-30,17,Ivory);
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
    if(!bShowHUD||!Canvas||!GEngine||Canvas->SizeX<1||Canvas->SizeY<1)return;
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

    // Ashen Gold: one small heraldic crest, two unlabelled resource gauges,
    // compact relic slots and a thin boss bar. The combat center stays clear.
    const float CrestX=Margin+20,CrestY=49;
    Circle(CrestX,CrestY,23,Ink,5);Circle(CrestX,CrestY,22,Bronze,1.1f);Circle(CrestX,CrestY,19,Pewter,.8f);
    Diamond(CrestX,CrestY-25,3,Bronze);Diamond(CrestX,CrestY+25,3,Bronze);
    Line(CrestX,CrestY-14,CrestX,CrestY+13,Bronze,1.4f);
    for(int32 I=0;I<3;++I)
    {
        const float Y=CrestY+7-I*8,Span=10-I*2;
        Line(CrestX,Y,CrestX-Span,Y-6,Bronze,1.f);Line(CrestX,Y,CrestX+Span,Y-6,Bronze,1.f);
    }
    const float ResourceWidth=FMath::Min(292.f,W*.28f);
    Meter(Margin+52,34,ResourceWidth,8,Health,HealthTrail,FLinearColor(.49f,.075f,.065f));
    Meter(Margin+52,59,ResourceWidth*.78f,5,Stamina,Stamina,FLinearColor(.35f,.40f,.19f));

    const float Slot=58.f,EquipmentY=H-131.f;
    RelicSlot(Margin,EquipmentY,Slot);RelicSlot(Margin+76,EquipmentY,Slot);
    SwordIcon(Margin+Slot*.5f,EquipmentY+Slot*.5f);
    FlaskIcon(Margin+76+Slot*.5f,EquipmentY+Slot*.5f-1,Knight->HealingCharges<=0);
    Keycap(TEXT("E"),Margin+20,EquipmentY+64);
    Text(Knight->IsChangingGrip()?TEXT("READYING"):Knight->IsTwoHanded()?TEXT("TWO HANDS"):TEXT("ONE HAND"),Margin+29,EquipmentY+85,10.5f,Ivory,true);
    Keycap(TEXT("R"),Margin+81,EquipmentY+64);
    Text(FString::FromInt(Knight->HealingCharges),Margin+111,EquipmentY+62,21,Ivory,true);

    const float BossWidth=FMath::Min(650.f,W*.53f),BossX=(W-BossWidth)*.5f;
    Text(TEXT("VEYR, THE CINDER WARDEN"),W*.5f,H-57,15,Ivory,true);
    Meter(BossX,H-31,BossWidth,6,BossHealth,BossTrail,FLinearColor(.39f,.055f,.045f));
    Diamond(BossX-10,H-28,5,Bronze);Diamond(BossX+BossWidth+10,H-28,5,Bronze);
    if(Knight->bLockedOn&&!Dragon->IsDead())
    {
        FVector2D Screen;const FVector Target=Dragon->GetHeadLocation()*.4f+(Dragon->GetLegLocation(0)+Dragon->GetLegLocation(1))*.3f;
        if(PlayerOwner&&PlayerOwner->ProjectWorldLocationToScreen(Target,Screen)&&Screen.X>20&&Screen.X<Canvas->SizeX-20&&Screen.Y>20&&Screen.Y<Canvas->SizeY-20)
            Diamond(Screen.X/Unit,Screen.Y/Unit,4,Ivory);
    }
    const bool bTerminal=Knight->IsDead()||Dragon->IsDead();
    ControlLegend(W,H,bTerminal);

    const float Now=GetWorld()->GetTimeSeconds();
    const bool bCaptured=Knight->IsMouseCaptured();
    if(bCaptured&&!bWasCaptured)CaptureHintUntil=Now+5.f;
    bWasCaptured=bCaptured;
    if(bTerminal)
    {
        const float Y=H*.43f;
        Rect(W*.5f-215,Y-16,430,105,FLinearColor(.008f,.012f,.018f,.72f));
        Line(W*.5f-170,Y-15,W*.5f-10,Y-15,Pewter);Line(W*.5f+10,Y-15,W*.5f+170,Y-15,Pewter);
        Diamond(W*.5f,Y-15,4,Bronze);
        Text(Knight->IsDead()?TEXT("YOU FELL"):TEXT("CINDER EXTINGUISHED"),W*.5f,Y+8,25,Ivory,true);
        Text(TEXT("ENTER  /  Rise again"),W*.5f,Y+53,14,Ivory,true);
    }
    else if(!Knight->IsReplayControlled())
    {
        if(!bCaptured)
        {
            const float Y=H*.48f;
            Text(Knight->HasEnteredEncounter()?TEXT("CLICK OR ENTER TO CONTROL"):TEXT("CLICK OR ENTER TO BEGIN"),W*.5f,Y,17,Ivory,true);
            Text(TEXT("Your controls stay in the lower-right corner."),W*.5f,Y+30,12,Quiet,true);
            Text(TEXT("ESC  /  Pause, settings and controls"),W*.5f,Y+50,12,Quiet,true);
        }
        else if(Now<CaptureHintUntil)
            Text(TEXT("Esc  /  Pause"),W-Margin-145,29,12,Quiet);
    }
}

namespace
{
    class SVeyrPausePanel final : public SCompoundWidget
    {
    public:
        SLATE_BEGIN_ARGS(SVeyrPausePanel) {}
            SLATE_EVENT(FSimpleDelegate,OnDismiss)
            SLATE_DEFAULT_SLOT(FArguments,Content)
        SLATE_END_ARGS()
        void Construct(const FArguments& Args){Dismiss=Args._OnDismiss;ChildSlot[Args._Content.Widget];}
        virtual bool SupportsKeyboardFocus() const override { return true; }
        virtual FReply OnKeyDown(const FGeometry& Geometry,const FKeyEvent& Event) override
        {
            if(Event.GetKey()==EKeys::Escape){Dismiss.ExecuteIfBound();return FReply::Handled();}
            return SCompoundWidget::OnKeyDown(Geometry,Event);
        }
    private:
        FSimpleDelegate Dismiss;
    };
}

void AVeyrHUD::TogglePauseMenu()
{
    if(PauseRoot.IsValid()){ClosePauseMenu();return;}
    AVeyrGameMode* Mode=GetWorld()?GetWorld()->GetAuthGameMode<AVeyrGameMode>():nullptr;
    if(!Mode||!PlayerOwner||!PlayerOwner->IsLocalController())return;
    bRestoreCapture=Mode->Knight&&Mode->Knight->IsMouseCaptured();
    if(!Mode->SetPauseMenuOpen(true))return;
    if(Mode->Knight)Mode->Knight->SuspendForPauseMenu();
    PausePage=0;RebuildPauseMenu();
}

void AVeyrHUD::ClosePauseMenu()
{
    AVeyrGameMode* Mode=GetWorld()?GetWorld()->GetAuthGameMode<AVeyrGameMode>():nullptr;
    // Keep the usable menu on screen if the world cannot resume.
    if(Mode&&!Mode->SetPauseMenuOpen(false))return;
    if(GetWorld()&&GetWorld()->GetGameViewport()&&PauseRoot.IsValid())
        GetWorld()->GetGameViewport()->RemoveViewportWidgetContent(PauseRoot.ToSharedRef());
    PauseRoot.Reset();
    if(Mode)
    {
        if(Mode->Knight)Mode->Knight->ResumeFromPauseMenu(bRestoreCapture);
    }
}

void AVeyrHUD::SetPausePage(int32 Page){PausePage=Page;RebuildPauseMenu();}
void AVeyrHUD::ChangeVolume(float Delta)
{
    if(AVeyrGameMode* Mode=GetWorld()->GetAuthGameMode<AVeyrGameMode>())Mode->SetMasterVolume(Mode->UserMasterVolume+Delta);
    RebuildPauseMenu();
}
void AVeyrHUD::ChangeSensitivity(float Delta)
{
    if(AVeyrGameMode* Mode=GetWorld()->GetAuthGameMode<AVeyrGameMode>())Mode->SetMouseSensitivity(Mode->UserMouseSensitivity+Delta);
    RebuildPauseMenu();
}
void AVeyrHUD::ToggleDisplayMode()
{
    if(UGameUserSettings* Settings=GEngine?GEngine->GetGameUserSettings():nullptr)
    {
        Settings->SetFullscreenMode(Settings->GetFullscreenMode()==EWindowMode::Windowed?EWindowMode::WindowedFullscreen:EWindowMode::Windowed);
        Settings->ApplyResolutionSettings(false);Settings->ConfirmVideoMode();Settings->SaveSettings();
    }
    RebuildPauseMenu();
}
void AVeyrHUD::CycleResolution()
{
    if(UGameUserSettings* Settings=GEngine?GEngine->GetGameUserSettings():nullptr)
    {
        const FIntPoint Current=Settings->GetScreenResolution();
        const FIntPoint Next=Current.X<1600?FIntPoint(1600,900):Current.X<1920?FIntPoint(1920,1080):FIntPoint(1280,720);
        Settings->SetScreenResolution(Next);Settings->ApplyResolutionSettings(false);Settings->ConfirmVideoMode();Settings->SaveSettings();
    }
    RebuildPauseMenu();
}

void AVeyrHUD::RebuildPauseMenu()
{
    AVeyrGameMode* Mode=GetWorld()?GetWorld()->GetAuthGameMode<AVeyrGameMode>():nullptr;
    UGameViewportClient* Viewport=GetWorld()?GetWorld()->GetGameViewport():nullptr;
    if(!Mode||!Mode->bPauseMenuOpen||!Viewport||!PlayerOwner)return;
    if(PauseRoot.IsValid())Viewport->RemoveViewportWidgetContent(PauseRoot.ToSharedRef());
    const TWeakObjectPtr<AVeyrHUD> Self(this);
    const FSlateFontInfo HeadingFont=FCoreStyle::GetDefaultFontStyle(TEXT("Regular"),28);
    const FSlateFontInfo BodyFont=FCoreStyle::GetDefaultFontStyle(TEXT("Regular"),16);
    const FSlateFontInfo SmallFont=FCoreStyle::GetDefaultFontStyle(TEXT("Regular"),13);
    TSharedRef<SVerticalBox> Content=SNew(SVerticalBox);
    Content->AddSlot().AutoHeight().Padding(0,0,0,6)
        [SNew(STextBlock).Text(FText::FromString(PausePage==1?TEXT("SETTINGS"):PausePage==2?TEXT("CONTROLS"):TEXT("PAUSED"))).Font(HeadingFont).ColorAndOpacity(Ivory)];
    Content->AddSlot().AutoHeight().Padding(0,0,0,22)
        [SNew(STextBlock).Text(FText::FromString(TEXT("VEYR  /  THE CINDER WARDEN"))).Font(SmallFont).ColorAndOpacity(Bronze)];
    auto AddButton=[&](const FString& Label,TFunction<void()> Callback)
    {
        Content->AddSlot().AutoHeight().Padding(0,4)
        [SNew(SButton).ContentPadding(FMargin(16,11)).ButtonColorAndOpacity(FLinearColor(.12f,.105f,.075f,1.f))
            .OnClicked_Lambda([Callback=MoveTemp(Callback)](){Callback();return FReply::Handled();})
            [SNew(STextBlock).Text(FText::FromString(Label)).Font(BodyFont).ColorAndOpacity(Ivory)]];
    };
    if(PausePage==0)
    {
        AddButton(TEXT("Resume"),[Self](){if(Self.IsValid())Self->ClosePauseMenu();});
        AddButton(TEXT("Settings"),[Self](){if(Self.IsValid())Self->SetPausePage(1);});
        AddButton(TEXT("Controls"),[Self](){if(Self.IsValid())Self->SetPausePage(2);});
        if(Mode->Knight&&Mode->Dragon&&(Mode->Knight->IsDead()||Mode->Dragon->IsDead()))
            AddButton(TEXT("Restart encounter"),[Self](){if(Self.IsValid()){AVeyrGameMode* M=Self->GetWorld()->GetAuthGameMode<AVeyrGameMode>();Self->ClosePauseMenu();if(M&&M->Knight)M->Knight->RestartIfTerminal();}});
    }
    else if(PausePage==1)
    {
        auto SettingRow=[&](const FString& Label,TFunction<void()> Less,TFunction<void()> More)
        {
            Content->AddSlot().AutoHeight().Padding(0,7)
            [SNew(SHorizontalBox)
                +SHorizontalBox::Slot().FillWidth(1.f).VAlign(VAlign_Center)[SNew(STextBlock).Text(FText::FromString(Label)).Font(BodyFont).ColorAndOpacity(Ivory)]
                +SHorizontalBox::Slot().AutoWidth().Padding(5,0)[SNew(SButton).ContentPadding(FMargin(13,8)).Text(FText::FromString(TEXT("−"))).OnClicked_Lambda([Less=MoveTemp(Less)](){Less();return FReply::Handled();})]
                +SHorizontalBox::Slot().AutoWidth()[SNew(SButton).ContentPadding(FMargin(13,8)).Text(FText::FromString(TEXT("+"))).OnClicked_Lambda([More=MoveTemp(More)](){More();return FReply::Handled();})]];
        };
        SettingRow(FString::Printf(TEXT("Volume  %d%%"),FMath::RoundToInt(Mode->UserMasterVolume*100.f)),
            [Self](){if(Self.IsValid())Self->ChangeVolume(-.1f);},[Self](){if(Self.IsValid())Self->ChangeVolume(.1f);});
        SettingRow(FString::Printf(TEXT("Mouse sensitivity  %.2f×"),Mode->UserMouseSensitivity),
            [Self](){if(Self.IsValid())Self->ChangeSensitivity(-.1f);},[Self](){if(Self.IsValid())Self->ChangeSensitivity(.1f);});
        if(UGameUserSettings* Settings=GEngine?GEngine->GetGameUserSettings():nullptr)
        {
            AddButton(Settings->GetFullscreenMode()==EWindowMode::Windowed?TEXT("Display  ·  Windowed"):TEXT("Display  ·  Borderless"),[Self](){if(Self.IsValid())Self->ToggleDisplayMode();});
            const FIntPoint Res=Settings->GetScreenResolution();
            AddButton(FString::Printf(TEXT("Resolution  ·  %d × %d"),Res.X,Res.Y),[Self](){if(Self.IsValid())Self->CycleResolution();});
        }
        Content->AddSlot().AutoHeight().Padding(0,10)[SNew(STextBlock).Text(FText::FromString(TEXT("Changes are saved for this game.\nResolution applies directly in windowed mode."))).Font(SmallFont).ColorAndOpacity(Quiet)];
        AddButton(TEXT("Back"),[Self](){if(Self.IsValid())Self->SetPausePage(0);});
    }
    else
    {
        const TCHAR* Lines[]={TEXT("WASD  —  Move / jog"),TEXT("Shift  —  Sprint, in either grip"),TEXT("LMB  —  Attack; repeat or hold to chain"),TEXT("RMB  —  Guard"),TEXT("Q  —  Directional roll / dodge"),TEXT("Space  —  Blink in your movement direction"),TEXT("E  —  One / two hands on the same sword"),TEXT("R  —  Drink Ember Draught"),TEXT("Tab  —  Lock on / release target"),TEXT("Enter  —  Restart after death or victory"),TEXT("Escape  —  Pause / resume")};
        for(const TCHAR* LineText:Lines)Content->AddSlot().AutoHeight().Padding(0,5)[SNew(STextBlock).Text(FText::FromString(LineText)).Font(BodyFont).ColorAndOpacity(Ivory)];
        AddButton(TEXT("Back"),[Self](){if(Self.IsValid())Self->SetPausePage(0);});
    }
    Content->AddSlot().AutoHeight().Padding(0,18,0,0)[SNew(STextBlock).Text(FText::FromString(TEXT("ESC  /  Resume"))).Font(SmallFont).ColorAndOpacity(Quiet)];
    const float MaxHeight=Viewport->Viewport?FMath::Max(300.f,float(Viewport->Viewport->GetSizeXY().Y)-72.f):600.f;
    PauseRoot=SNew(SVeyrPausePanel).OnDismiss(FSimpleDelegate::CreateLambda([Self](){if(Self.IsValid())Self->ClosePauseMenu();}))
    [SNew(SBorder).BorderImage(FCoreStyle::Get().GetBrush(TEXT("WhiteBrush"))).BorderBackgroundColor(FLinearColor(.005f,.006f,.008f,.76f))
        .HAlign(HAlign_Center).VAlign(VAlign_Center)
        [SNew(SBox).WidthOverride(500.f).MaxDesiredHeight(MaxHeight)
            [SNew(SBorder).BorderImage(FCoreStyle::Get().GetBrush(TEXT("WhiteBrush"))).BorderBackgroundColor(FLinearColor(.035f,.029f,.020f,.98f)).Padding(28.f)
                [SNew(SScrollBox)+SScrollBox::Slot()[Content]]]]];
    Viewport->AddViewportWidgetContent(PauseRoot.ToSharedRef(),1000);
    FInputModeUIOnly Input;Input.SetWidgetToFocus(PauseRoot);Input.SetLockMouseToViewportBehavior(EMouseLockMode::DoNotLock);
    PlayerOwner->SetInputMode(Input);PlayerOwner->SetShowMouseCursor(true);
}

void AVeyrHUD::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
    if(GetWorld()&&GetWorld()->GetGameViewport()&&PauseRoot.IsValid())GetWorld()->GetGameViewport()->RemoveViewportWidgetContent(PauseRoot.ToSharedRef());
    PauseRoot.Reset();Super::EndPlay(EndPlayReason);
}
