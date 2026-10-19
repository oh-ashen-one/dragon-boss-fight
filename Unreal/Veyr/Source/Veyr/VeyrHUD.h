#pragma once
#include "CoreMinimal.h"
#include "GameFramework/HUD.h"
#include "VeyrHUD.generated.h"

/** Restrained native encounter HUD. Original vector silhouettes; no asset dependency. */
UCLASS()
class VEYR_API AVeyrHUD : public AHUD
{
    GENERATED_BODY()
public:
    virtual void DrawHUD() override;
private:
    void Text(const FString& Value,float X,float Y,float Height,const FLinearColor& Color,bool bCentered=false);
    void Line(float X1,float Y1,float X2,float Y2,const FLinearColor& Color,float Width=1.f);
    void Rect(float X,float Y,float Width,float Height,const FLinearColor& Color);
    void Polygon(const TArray<FVector2D>& Points,const FLinearColor& Color);
    void Diamond(float X,float Y,float Radius,const FLinearColor& Color,bool bFilled=false);
    void Meter(float X,float Y,float Width,float Height,float Value,float Trail,const FLinearColor& Color);
    void SwordIcon(float X,float Y);
    void FlaskIcon(float X,float Y,bool bEmpty);
    void Keycap(const FString& Key,float X,float Y);
    float Unit=1.f;
    float HealthTrail=1.f,BossTrail=1.f;
    float PreviousHealth=1.f,PreviousBoss=1.f;
    float HealthTrailDelay=0.f,BossTrailDelay=0.f;
    float CaptureHintUntil=0.f;
    bool bWasCaptured=false;
};
