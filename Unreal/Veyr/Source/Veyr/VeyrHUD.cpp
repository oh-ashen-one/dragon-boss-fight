#include "VeyrHUD.h"
#include "VeyrGameMode.h"
#include "VeyrKnight.h"
#include "VeyrDragon.h"
#include "Engine/Canvas.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
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
    Label(TEXT("VEYR / THE CINDER WARDEN"),930,29,1.f);
    Label(TEXT("UNREAL PROTOTYPE / TEMPORARY ART"),900,50,.8f);
    Label(TEXT("V E Y R ,  T H E  C I N D E R  W A R D E N"),422,601,1.2f);
    Bar(230,636,820,13,Dragon->Health/Dragon->MaxHealth,FLinearColor(.58f,.2f,.13f));
    for(int32 I=0;I<4;++I)Bar(450+I*98,661,85,5,Dragon->GetLegStagger(I)/100.f,FLinearColor(.83f,.58f,.23f));
    Label(Dragon->IsHeadExposed()?TEXT("CROWN EXPOSED - STRIKE THE HEAD"):StaticEnum<EVeyrDragonState>()->GetNameStringByValue(static_cast<int64>(Dragon->State)),486,674,.9f);
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
