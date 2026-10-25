#pragma once
#include "CoreMinimal.h"
#include "GameFramework/HUD.h"
#include "VeyrHUD.generated.h"

/** Moonlit Silver HUD: generated reference artwork with live resource gauges. */
UCLASS()
class VEYR_API AVeyrHUD : public AHUD
{
    GENERATED_BODY()
public:
    AVeyrHUD();
    virtual void DrawHUD() override;
    virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;
    void TogglePauseMenu();
    bool IsPauseMenuOpen() const { return PauseRoot.IsValid(); }
private:
    UPROPERTY() TObjectPtr<class UTexture2D> MoonlitAtlas;
    UPROPERTY() TObjectPtr<class UFont> MoonlitFont;
    void Atlas(float X,float Y,float Width,float Height,float U,float V,float UW,float VH);
    void ArcMeter(float X,float Y,float Radius,float Width,float Start,float Sweep,float Value,float Trail,const FLinearColor& Color);
    TSharedPtr<class SWidget> PauseRoot;
    int32 PausePage=0;
    bool bRestoreCapture=false;
    void RebuildPauseMenu();
    void ClosePauseMenu();
    void SetPausePage(int32 Page);
    void ChangeVolume(float Delta);
    void ChangeSensitivity(float Delta);
    void ToggleDisplayMode();
    void CycleResolution();
    void ControlLegend(float W,float H,bool bTerminal);
    void Text(const FString& Value,float X,float Y,float Height,const FLinearColor& Color,bool bCentered=false);
    void Line(float X1,float Y1,float X2,float Y2,const FLinearColor& Color,float Width=1.f);
    void Rect(float X,float Y,float Width,float Height,const FLinearColor& Color);
    void Polygon(const TArray<FVector2D>& Points,const FLinearColor& Color);
    void Diamond(float X,float Y,float Radius,const FLinearColor& Color,bool bFilled=false);
    void Keycap(const FString& Key,float X,float Y);
    float Unit=1.f;
    float HealthTrail=1.f,BossTrail=1.f;
    float PreviousHealth=1.f,PreviousBoss=1.f;
    float HealthTrailDelay=0.f,BossTrailDelay=0.f;
    float CaptureHintUntil=0.f;
    bool bWasCaptured=false;
};
