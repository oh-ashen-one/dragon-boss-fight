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
#include "Engine/Texture2D.h"
#include "Engine/Font.h"
#include "UObject/ConstructorHelpers.h"
#include "Misc/Paths.h"
#include "Framework/Application/SlateApplication.h"
#include "Fonts/FontMeasure.h"
#include "Rendering/SlateRenderer.h"

namespace
{
    const FLinearColor Ivory(.86f,.85f,.79f,1.f);
    const FLinearColor Quiet(.57f,.61f,.64f,1.f);
    const FLinearColor Pewter(.34f,.39f,.43f,.85f);
    const FLinearColor Silver(.64f,.66f,.64f,1.f);
    const FLinearColor Ink(.009f,.013f,.017f,.86f);
}

AVeyrHUD::AVeyrHUD()
{
    static ConstructorHelpers::FObjectFinderOptional<UTexture2D> Art(TEXT("/Game/UI/MoonlitB/T_MoonlitSilverAtlas_v1.T_MoonlitSilverAtlas_v1"),LOAD_Quiet|LOAD_NoWarn);
    MoonlitAtlas=Art.Get();
}

void AVeyrHUD::Text(const FString& Value,float X,float Y,float Height,const FLinearColor& Color,bool bCentered)
{
    if(!MoonlitFont)
    {
        MoonlitFont=NewObject<UFont>(this);
        MoonlitFont->FontCacheType=EFontCacheType::Runtime;
        MoonlitFont->LegacyFontSize=32;
        MoonlitFont->GetMutableInternalCompositeFont().DefaultTypeface.Fonts.Add(
            FTypefaceEntry(TEXT("Regular"),FPaths::ProjectContentDir()/TEXT("UI/Fonts/CormorantGaramond.ttf"),EFontHinting::Auto,EFontLoadingPolicy::LazyLoad));
    }
    const FSlateFontInfo Font(MoonlitFont,32,TEXT("Regular"));
    const auto Measure=FSlateApplication::Get().GetRenderer()->GetFontMeasureService();
    const FVector2D Base=Measure->Measure(TEXT("Ag"),Font);
    const float Scale=Height*Unit/FMath::Max(1.f,float(Base.Y));
    const FVector2D Size=Measure->Measure(Value,Font)*Scale;
    const FVector2D Position(X*Unit-(bCentered?Size.X*.5f:0.f),Y*Unit);
    FCanvasTextItem Item(Position,FText::FromString(Value),Font,Color);
    Item.Scale=FVector2D(Scale);Item.EnableShadow(FLinearColor(0,0,0,.95f),FVector2D(Unit));
    Canvas->DrawItem(Item);
}

void AVeyrHUD::Atlas(float X,float Y,float Width,float Height,float U,float V,float UW,float VH)
{
    if(!MoonlitAtlas)return;
    DrawTexture(MoonlitAtlas,X*Unit,Y*Unit,Width*Unit,Height*Unit,U/1672.f,V/941.f,UW/1672.f,VH/941.f,FLinearColor::White,BLEND_Translucent);
}

void AVeyrHUD::ArcMeter(float X,float Y,float Radius,float Width,float Start,float Sweep,float Value,float Trail,const FLinearColor& Color)
{
    auto Band=[&](float Amount,float R,float Thickness,FLinearColor Tint)
    {
        const int32 Steps=FMath::Max(1,FMath::CeilToInt(Sweep*FMath::Clamp(Amount,0.f,1.f)));
        for(int32 I=0;I<Steps;++I)
        {
            const float A=FMath::DegreesToRadians(Start+Sweep*Amount*I/Steps),B=FMath::DegreesToRadians(Start+Sweep*Amount*(I+1)/Steps);
            auto P=[&](float Angle,float Rad){const float C=FMath::Cos(Angle);const float Fit=C<0.f?(Radius>80.f?.92f:.84f):1.f;return FVector2D(X+C*Rad*Fit,Y+FMath::Sin(Angle)*Rad);};
            Polygon({P(A,R-Thickness*.5f),P(A,R+Thickness*.5f),P(B,R+Thickness*.5f),P(B,R-Thickness*.5f)},Tint);
        }
    };
    Value=FMath::Clamp(Value,0.f,1.f);Trail=FMath::Clamp(Trail,Value,1.f);
    Band(1.f,Radius,Width,FLinearColor(.012f,.020f,.026f,.95f));
    if(Trail>Value)Band(Trail,Radius,Width,FLinearColor(.37f,.25f,.24f,.8f));
    if(Value>.001f)
    {
        Band(Value,Radius,Width+1.2f,FLinearColor(Color.R,Color.G,Color.B,.20f));
        Band(Value,Radius,Width-.8f,Color*.65f+FLinearColor(0,0,0,.35f));
        Band(Value,Radius,Width*.65f,Color);
        Band(Value,Radius+Width*.29f,Width*.13f,FLinearColor(.77f,.78f,.69f,.5f));
    }
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

void AVeyrHUD::ControlLegend(float W,float H,bool bTerminal)
{
    // MediumFont's visible glyphs occupy roughly 80% of its measured line
    // height: 17 layout pixels gives about 13–14 readable pixels at 1280x720.
    const float X=W-263.f,Y=H-275.f;
    Rect(X-8,Y-7,250,89,FLinearColor(.008f,.014f,.023f,.48f));
    const TCHAR* Rows[]={TEXT("WASD  Move    SHIFT  Sprint"),TEXT("LMB  Attack    RMB  Guard"),TEXT("Q  Roll    SPACE  Blink"),TEXT("E  Grip    R  Heal"),TEXT("TAB  Lock    ESC  Menu")};
    UFont* LegendFont=GEngine->GetMediumFont();float TW=0.f,TH=0.f;GetTextSize(TEXT("Ag"),TW,TH,LegendFont);
    const float LegendScale=16.f*Unit/FMath::Max(1.f,TH);
    for(int32 I=0;I<5;++I)DrawText(Rows[I],Ivory,X*Unit,(Y+I*16)*Unit,LegendFont,LegendScale,false);
    if(bTerminal)Text(TEXT("ENTER  Restart encounter"),X,Y-30,17,Ivory);
}

void AVeyrHUD::Keycap(const FString& Key,float X,float Y)
{
    Rect(X,Y,24,24,FLinearColor(.015f,.022f,.028f,.88f));
    for(float D:{0.f,1.5f})
    {
        const FLinearColor C=D==0?Silver:Pewter;
        Line(X+D,Y+D,X+24-D,Y+D,C,.7f);Line(X+D,Y+24-D,X+24-D,Y+24-D,C,.7f);
        Line(X+D,Y+D,X+D,Y+24-D,C,.7f);Line(X+24-D,Y+D,X+24-D,Y+24-D,C,.7f);
    }
    Text(Key,X+12,Y-1,25,Ivory,true);
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

    if(!MoonlitAtlas)MoonlitAtlas=LoadObject<UTexture2D>(nullptr,TEXT("/Game/UI/MoonlitB/T_MoonlitSilverAtlas_v1.T_MoonlitSilverAtlas_v1"));
    // Moonlit Silver reference B: top boss gauge, lunar vitals at lower left,
    // painted equipment reliquaries at lower right, clear center/feet region.
    const float BossWidth=FMath::Min(656.f,W*.515f),BossX=(W-BossWidth)*.5f;
    const float Cap=36.f,BarWidth=BossWidth-2.f*Cap;
    Atlas(BossX,22,Cap,60.5f,240,50,100,110);
    Atlas(BossX+Cap,22,BarWidth,60.5f,340,50,990,110);
    Atlas(BossX+BossWidth-Cap,22,Cap,60.5f,1330,50,110,110);
    Text(TEXT("Veyr, the Cinder Warden"),W*.5f,7,27,Ivory,true);
    const float BX=BossX+Cap+2,BY=44.8f,BW=BarWidth-4;
    Rect(BX,BY,BW,8.4f,FLinearColor(.013f,.018f,.023f,.94f));
    if(BossTrail>BossHealth)Rect(BX,BY,BW*BossTrail,8.4f,FLinearColor(.31f,.20f,.20f,.9f));
    Rect(BX,BY,BW*BossHealth,8.4f,FLinearColor(.32f,.045f,.06f,1.f));
    Rect(BX,BY+2,BW*BossHealth,3.8f,FLinearColor(.49f,.10f,.12f,1.f));
    Line(BX,BY+.5f,BX+BW*BossHealth,BY+.5f,FLinearColor(.77f,.54f,.50f,.6f),.7f);

    ArcMeter(108.f,H-100.f,90.7f,7.2f,198.f,125.f,Health,HealthTrail,FLinearColor(.59f,.105f,.12f,1.f));
    ArcMeter(108.f,H-100.f,76.8f,9.f,155.f,191.f,Stamina,Stamina,FLinearColor(.34f,.53f,.38f,1.f));
    Atlas(19.2f,H-203.2f,192.f,187.2f,20,550,400,390);

    Atlas(W-219.f,H-170.f,110.f,123.2f,1205,630,250,280);
    Atlas(W-106.f,H-159.f,96.8f,121.f,1450,640,220,275);
    Text(Knight->IsChangingGrip()?TEXT("READYING"):Knight->IsTwoHanded()?TEXT("— TWO HANDS —"):TEXT("— ONE HAND —"),W-161.f,H-59.f,16,Ivory,true);
    Keycap(TEXT("E"),W-173.f,H-37.f);
    Keycap(TEXT("R"),W-73.f,H-37.f);
    TArray<FVector2D> ChargeBacking;
    for(int32 I=0;I<32;++I){const float A=2.f*PI*I/32.f;ChargeBacking.Add(FVector2D(W-41.f+15.f*FMath::Cos(A),H-72.f+15.f*FMath::Sin(A)));}
    Polygon(ChargeBacking,FLinearColor(.008f,.014f,.022f,.78f));
    Text(FString::FromInt(Knight->HealingCharges),W-41.f,H-94.f,40,Ivory,true);
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
        Diamond(W*.5f,Y-15,4,Silver);
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
        [SNew(STextBlock).Text(FText::FromString(TEXT("VEYR  /  THE CINDER WARDEN"))).Font(SmallFont).ColorAndOpacity(Silver)];
    auto AddButton=[&](const FString& Label,TFunction<void()> Callback)
    {
        Content->AddSlot().AutoHeight().Padding(0,4)
        [SNew(SButton).ContentPadding(FMargin(16,11)).ButtonColorAndOpacity(FLinearColor(.075f,.095f,.12f,1.f))
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
            [SNew(SBorder).BorderImage(FCoreStyle::Get().GetBrush(TEXT("WhiteBrush"))).BorderBackgroundColor(FLinearColor(.018f,.028f,.042f,.98f)).Padding(28.f)
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
