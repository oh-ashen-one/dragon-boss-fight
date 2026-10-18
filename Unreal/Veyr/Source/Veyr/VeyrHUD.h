#pragma once
#include "CoreMinimal.h"
#include "GameFramework/HUD.h"
#include "VeyrHUD.generated.h"
UCLASS()
class VEYR_API AVeyrHUD : public AHUD
{
    GENERATED_BODY()
public:
    virtual void DrawHUD() override;
private:
    void Bar(float X,float Y,float W,float H,float Ratio,const FLinearColor& Color);
    void Label(const FString& Text,float X,float Y,float Size,const FLinearColor& Color=FLinearColor(.88f,.86f,.78f));
    float ScaleX=1,ScaleY=1;
};
