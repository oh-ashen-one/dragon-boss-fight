#include "VeyrA123Proof.h"
#include "VeyrCameraBoom.h"
#include "VeyrDragon.h"
#include "VeyrKnight.h"
#include "VeyrSkeletalPresentation.h"
#include "VeyrVisualDefinition.h"
#include "Animation/AnimSequence.h"
#include "Camera/CameraComponent.h"
#include "Dom/JsonObject.h"
#include "Dom/JsonValue.h"
#include "Engine/World.h"
#include "GameFramework/Controller.h"
#include "Misc/CommandLine.h"

namespace
{
    bool IsMirrored(const FVeyrVisualClip& Clip){return Clip.Sequence&&Clip.Sequence->GetName().Contains(TEXT("_mirror"));}
    bool IsGroundClip(FName Name)
    {
        const FString S=Name.ToString();
        for(const TCHAR* Skip:{TEXT("Fly"),TEXT("Flight"),TEXT("Takeoff"),TEXT("TakeOff"),TEXT("Land"),TEXT("Hover"),TEXT("Glide"),
            TEXT("Air"),TEXT("Death"),TEXT("Dead"),TEXT("Collapse"),TEXT("Exposed"),TEXT("Rise")})
            if(S.Contains(Skip))return false;
        return true;
    }
    float Percentile(TArray<float> V,float P)
    {
        if(V.IsEmpty())return 0.f;
        V.Sort();
        return V[FMath::Clamp(FMath::RoundToInt(P*(V.Num()-1)),0,V.Num()-1)];
    }
    float ClipSeconds(const FVeyrVisualClip& Clip)
    {
        const float End=Clip.EndSeconds<0.f?Clip.Sequence->GetPlayLength():Clip.EndSeconds;
        return FMath::Max(0.f,End-Clip.StartSeconds);
    }
}

bool FVeyrA123Proof::Begin(UWorld* InWorld,AVeyrKnight* InKnight,AVeyrDragon* InDragon,const FString& InMode,FHooks InHooks)
{
    World=InWorld;Knight=InKnight;Dragon=InDragon;Mode=InMode;Hooks=MoveTemp(InHooks);
    if(!InWorld||!InKnight||!InDragon||!IsMode(Mode))return false;
    BodyScale=static_cast<float>(InDragon->GetActorScale3D().Z);Scale=FMath::Max(.25f,BodyScale*.5f);
    if(Mode!=TEXT("camerahug")&&(!InDragon->bUsingCustomuseVisual||!InDragon->ImportedPresentation||!InDragon->ImportedPresentation->VisualDefinition))
        return false;
    if(Mode==TEXT("camerahug")&&!Cast<UVeyrCameraBoom>(InKnight->CameraBoom))return false;
    LiveSeconds=Mode==TEXT("camerahug")?200.f:Mode==TEXT("footclosehits")?120.f:120.f;
    return true;
}

UVeyrSkeletalPresentation* FVeyrA123Proof::MakeProbe()
{
    UWorld* W=World.Get();AVeyrDragon* D=Dragon.Get();
    if(!W||!D)return nullptr;
    FActorSpawnParameters Params;Params.SpawnCollisionHandlingOverride=ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
    AActor* Host=W->SpawnActor<AActor>(AActor::StaticClass(),FTransform::Identity,Params);
    if(!Host)return nullptr;
    USceneComponent* Root=NewObject<USceneComponent>(Host,TEXT("A123ProbeRoot"));
    Host->SetRootComponent(Root);Root->RegisterComponent();
    // Same floor point and yaw as the dragon, actor scale 1: sweep numbers are at 1x and reported at game scale too.
    Host->SetActorLocationAndRotation(FVector(D->GetActorLocation().X,D->GetActorLocation().Y,D->GetActorLocation().Z),FRotator(0,D->GetActorRotation().Yaw,0));
    UVeyrSkeletalPresentation* P=NewObject<UVeyrSkeletalPresentation>(Host,TEXT("A123PoseProbe"));
    ProbeActor=Host;
    P->ConfigureRenderPolicy(true,false);
    P->SetupAttachment(Root);P->RegisterComponent();
    if(!P->SetVisualDefinition(D->ImportedPresentation->VisualDefinition,false)){FailReason=TEXT("probe definition: ")+P->LastError;return nullptr;}
    P->bGroundingEnabled=false;
    Probe=P;
    return P;
}

void FVeyrA123Proof::Sweep()
{
    bSwept=true;
    SweepJson=MakeShared<FJsonObject>();
    if(Mode==TEXT("footclosehits"))SweepFootStretch();
    else if(Mode==TEXT("soleheights"))SweepSoles();
    if(AActor* Host=ProbeActor.Get())Host->Destroy();
}

void FVeyrA123Proof::SweepFootStretch()
{
    UVeyrSkeletalPresentation* P=MakeProbe();
    if(!P){SweepJson->SetStringField(TEXT("error"),FailReason);return;}
    P->SampleReferencePose();
    const float HeightCm=static_cast<float>(P->Bounds.BoxExtent.Z*2.0);
    SweepJson->SetNumberField(TEXT("restHeightCm1x"),HeightCm);
    TArray<TSharedPtr<FJsonValue>> Clips;
    for(const auto& Pair:P->VisualDefinition->Clips)
    {
        if(!Pair.Value.Sequence)continue;
        const bool bMirrored=IsMirrored(Pair.Value);MirroredClips+=bMirrored?1:0;
        const float Seconds=ClipSeconds(Pair.Value);
        float Worst[2]={0.f,0.f};FName WorstBone[2];
        for(int32 Pass=0;Pass<(bMirrored?2:1);++Pass)
        {
            P->bRepairMirroredClips=Pass==0; // pass 1 = the old (unrepaired) pose
            for(float T=0.f;T<=Seconds+1e-3f;T+=1.f/30.f)
            {
                if(!P->SampleClipTime(Pair.Key,T))break;
                FName Bone;const float Stretch=P->MeasureMaxLinkStretchCm(Bone);
                if(Stretch>Worst[Pass]){Worst[Pass]=Stretch;WorstBone[Pass]=Bone;}
            }
        }
        P->bRepairMirroredClips=true;
        TSharedPtr<FJsonObject> C=MakeShared<FJsonObject>();
        C->SetStringField(TEXT("clip"),Pair.Key.ToString());C->SetBoolField(TEXT("mirrored"),bMirrored);
        C->SetNumberField(TEXT("maxLinkStretchCm1x"),Worst[0]);C->SetStringField(TEXT("worstBone"),WorstBone[0].ToString());
        if(bMirrored){C->SetNumberField(TEXT("legacyMaxLinkStretchCm1x"),Worst[1]);C->SetStringField(TEXT("legacyWorstBone"),WorstBone[1].ToString());}
        Clips.Add(MakeShared<FJsonValueObject>(C));
        if(bMirrored)
        {
            if(Worst[0]>SweepMirroredRepairedMaxCm){SweepMirroredRepairedMaxCm=Worst[0];SweepWorstBone=WorstBone[0];}
            SweepMirroredLegacyMaxCm=FMath::Max(SweepMirroredLegacyMaxCm,Worst[1]);
        }
        else SweepUnmirroredMaxCm=FMath::Max(SweepUnmirroredMaxCm,Worst[0]);
    }
    SweepJson->SetArrayField(TEXT("clips"),Clips);
    SweepJson->SetNumberField(TEXT("stretchLimitCm1x"),HeightCm*.01f);
}

void FVeyrA123Proof::SweepSoles()
{
    UVeyrSkeletalPresentation* P=MakeProbe();
    if(!P){SweepJson->SetStringField(TEXT("error"),FailReason);return;}
    TArray<TSharedPtr<FJsonValue>> Clips;
    for(const auto& Pair:P->VisualDefinition->Clips)
    {
        if(!Pair.Value.Sequence||!IsGroundClip(Pair.Key))continue;
        const float Seconds=ClipSeconds(Pair.Value);
        TArray<float> Lowest;TArray<float> Feet[4];
        for(float T=0.f;T<=Seconds+1e-3f;T+=1.f/15.f)
        {
            FVeyrSoleSample S;
            if(!P->SampleClipTime(Pair.Key,T)||!P->MeasureSoles(S)){++SoleFailures;continue;}
            Lowest.Add(S.LowestAboveFloorCm);
            for(int32 F=0;F<4;++F)Feet[F].Add(S.SoleAboveFloorCm[F]);
        }
        if(Lowest.IsEmpty())continue;
        TSharedPtr<FJsonObject> C=MakeShared<FJsonObject>();
        C->SetStringField(TEXT("clip"),Pair.Key.ToString());C->SetBoolField(TEXT("mirrored"),IsMirrored(Pair.Value));
        C->SetNumberField(TEXT("lowestSoleMedianCm1x"),Percentile(Lowest,.5f));
        C->SetNumberField(TEXT("lowestSoleMinCm1x"),Percentile(Lowest,0.f));
        C->SetNumberField(TEXT("lowestSoleMaxCm1x"),Percentile(Lowest,1.f));
        C->SetNumberField(TEXT("lowestSoleMedianCmGame"),Percentile(Lowest,.5f)*BodyScale);
        TArray<TSharedPtr<FJsonValue>> FeetJson;
        for(int32 F=0;F<4;++F)FeetJson.Add(MakeShared<FJsonValueNumber>(Percentile(Feet[F],.5f)));
        C->SetArrayField(TEXT("footMedianCm1x"),FeetJson);
        Clips.Add(MakeShared<FJsonValueObject>(C));
        if(Percentile(Lowest,.5f)>WorstSweepFloatCm){WorstSweepFloatCm=Percentile(Lowest,.5f);WorstSweepClip=Pair.Key;}
    }
    SweepJson->SetArrayField(TEXT("clips"),Clips);
    SweepJson->SetStringField(TEXT("soleModel"),P->GetSoleModel().Diagnostic);
    SweepJson->SetNumberField(TEXT("soleModelFitResidualImportedCm"),P->GetSoleModel().FitResidualImportedCm);
    SweepJson->SetNumberField(TEXT("sampleFailures"),SoleFailures);
}

void FVeyrA123Proof::Input(const FVector& Move,bool bLight) const
{
    if(AVeyrKnight* K=Knight.Get())K->SetReplayInput(Move,bLight,false,false,false,false,false);
}

FVector FVeyrA123Proof::KnightTargetFor(double Elapsed)
{
    AVeyrDragon* D=Dragon.Get();
    if(!D)return FVector::ZeroVector;
    if(Mode==TEXT("footclosehits"))
    {
        UVeyrSkeletalPresentation* P=D->ImportedPresentation;
        const int32 Toe=P?P->GetBoneIndex(TEXT("tripo__0_Left_Limb_3")):INDEX_NONE;
        return Toe!=INDEX_NONE?P->GetBoneTransform(Toe).GetLocation():D->GetActorLocation();
    }
    const FVector Extent=D->ImportedPresentation&&D->bUsingCustomuseVisual?FVector(D->ImportedPresentation->Bounds.BoxExtent):FVector(600*Scale,400*Scale,300*Scale);
    const FVector F=D->GetActorForwardVector(),R=D->GetActorRightVector();
    if(Mode==TEXT("soleheights"))return D->GetActorLocation()+F*Extent.X*1.1f;
    // camerahug: front-left leg, under the belly, right flank, under the left wing, tail, chin.
    static const FVector2D Points[]={{.5f,-.6f},{0.f,0.f},{0.f,.9f},{-.3f,-.9f},{-.9f,0.f},{.8f,0.f}};
    const double Per=LiveSeconds/UE_ARRAY_COUNT(Points);
    const int32 I=FMath::Clamp(static_cast<int32>((Elapsed-LiveStart)/Per),0,static_cast<int32>(UE_ARRAY_COUNT(Points))-1);
    WaypointIndex=I;
    return D->GetActorLocation()+F*Extent.X*Points[I].X+R*Extent.Y*Points[I].Y;
}

void FVeyrA123Proof::Drive(double Elapsed,float Dt)
{
    if(bDone)return;
    if(!bSwept)
    {
        Sweep();LiveStart=Elapsed;
        if(Hooks.Shot)Hooks.Shot(Mode+TEXT("_live_start"));
        const AVeyrDragon* D=Dragon.Get();
        if(D&&D->ImportedPresentation)LiveMirrorSamplesStart=D->ImportedPresentation->MirrorRepairSamples;
        if(const UVeyrCameraBoom* B=Knight.IsValid()?Cast<UVeyrCameraBoom>(Knight->CameraBoom):nullptr)PullInStart=B->PullInEvents;
        return;
    }
    Live(Elapsed,Dt);
    if(Elapsed-LiveStart>=LiveSeconds)Finalize(Elapsed);
}

void FVeyrA123Proof::Live(double Elapsed,float Dt)
{
    AVeyrKnight* K=Knight.Get();AVeyrDragon* D=Dragon.Get();
    if(!K||!D)return;
    if(K->Health<45.f){K->Health=100.f;++HealthRefills;} // same refill as the camp mode, so the run lasts
    const FVector Target=KnightTargetFor(Elapsed);
    FVector To=Target-K->GetActorLocation();To.Z=0;
    const float Near=Mode==TEXT("footclosehits")?220.f:Mode==TEXT("soleheights")?150.f:120.f;
    const bool bArrived=To.Size()<Near;
    const bool bAttack=Mode!=TEXT("soleheights")&&bArrived&&FMath::Fmod(Elapsed,.6)<Dt*1.5;
    Input(bArrived?FVector::ZeroVector:To.GetSafeNormal(),bAttack);
    UVeyrSkeletalPresentation* P=D->ImportedPresentation;
    if(Mode==TEXT("footclosehits")&&P&&P->bPoseEvaluated)
    {
        ++LiveFrames;
        const FVeyrVisualClip* Clip=P->VisualDefinition?P->VisualDefinition->Clips.Find(P->CurrentClip):nullptr;
        if(Clip&&IsMirrored(*Clip))
        {
            ++LiveMirroredFrames;
            FName Bone;const float Stretch=P->MeasureMaxLinkStretchCm(Bone);
            if(Stretch>LiveMaxStretchCm){LiveMaxStretchCm=Stretch;LiveWorstBone=Bone;}
            if(Elapsed-LastShot>1.5&&Hooks.Shot){LastShot=Elapsed;Hooks.Shot(FString::Printf(TEXT("mirrored_%s"),*P->CurrentClip.ToString()));}
        }
    }
    else if(Mode==TEXT("camerahug"))
    {
        UVeyrCameraBoom* B=Cast<UVeyrCameraBoom>(K->CameraBoom);
        if(AController* C=K->GetController())
        {
            // Orbit the view; second half of the run is locked on (the lock-on camera owns yaw then).
            const bool bWantLock=Elapsed-LiveStart>LiveSeconds*.5;
            if(K->bLockedOn!=bWantLock)K->ToggleLockOn();
            if(!K->bLockedOn)C->SetControlRotation(FRotator(-12.f,FMath::Fmod(static_cast<float>(Elapsed-LiveStart)*45.f,360.f),0.f));
        }
        if(B&&K->CombatCamera)
        {
            B->RefreshDragonShapes();
            const FVector Cam=K->CombatCamera->GetComponentLocation();
            const float S=B->DragonScale();
            FName Shape;
            const bool bInside=B->IsPointInsideDragon(Cam,10.f-FMath::Min(B->BodyClearanceCm,B->WingClearanceCm)*S,&Shape);
            ++CameraFrames;
            const bool bCollapse=D->State==EVeyrDragonState::Collapse||D->State==EVeyrDragonState::Exposed;
            CollapseFrames+=bCollapse?1:0;
            if(bInside)
            {
                ++CameraInsideFrames;CollapseInsideFrames+=bCollapse?1:0;InsideByShape.FindOrAdd(Shape)++;
                if(Elapsed-LastShot>1.0&&Hooks.Shot){LastShot=Elapsed;Hooks.Shot(TEXT("camera_inside_")+Shape.ToString());}
            }
            else if(Elapsed-LastShot>6.0&&Hooks.Shot){LastShot=Elapsed;Hooks.Shot(FString::Printf(TEXT("hug_waypoint_%d"),WaypointIndex));}
            MaxLiftCm=FMath::Max(MaxLiftCm,B->LiftCm);MinFraction=FMath::Min(MinFraction,B->BodyFraction);
            const FVector Rel=Cam-K->GetActorLocation();
            if(bHasLastCamera)MaxCameraJumpCm=FMath::Max(MaxCameraJumpCm,static_cast<float>(FVector::Dist(Rel,LastCameraRelative)));
            LastCameraRelative=Rel;bHasLastCamera=true;
        }
    }
    else if(Mode==TEXT("soleheights")&&P&&P->bPoseEvaluated&&VeyrGroundingModeFor(D)==EVeyrGroundingMode::Ground)
    {
        FVeyrSoleSample S;
        // Measured independently of the grounding switch, on the visible dragon after this frame's offset.
        if(Elapsed-LiveStart>1.5&&P->MeasureSoles(S))LiveGroundLowest.Add(S.LowestAboveFloorCm);
        if(Elapsed-LastShot>8.0&&Hooks.Shot){LastShot=Elapsed;Hooks.Shot(TEXT("sole_ground"));}
    }
}

void FVeyrA123Proof::Finalize(double Elapsed)
{
    bDone=true;
    Input(FVector::ZeroVector,false);
    FString Reason;
    if(Mode==TEXT("footclosehits"))
    {
        const float Limit=SweepJson.IsValid()&&SweepJson->HasField(TEXT("stretchLimitCm1x"))?static_cast<float>(SweepJson->GetNumberField(TEXT("stretchLimitCm1x"))):10.f;
        bPassed=MirroredClips>0&&SweepMirroredRepairedMaxCm<=Limit&&LiveMaxStretchCm<=Limit*BodyScale;
        Reason=FString::Printf(TEXT("mirrored clips %d: repaired stretch %.1f cm (1x, limit %.1f), legacy %.1f; live mirrored frames %d max %.1f cm"),
            MirroredClips,SweepMirroredRepairedMaxCm,Limit,SweepMirroredLegacyMaxCm,LiveMirroredFrames,LiveMaxStretchCm);
    }
    else if(Mode==TEXT("camerahug"))
    {
        bPassed=CameraFrames>300&&CameraInsideFrames==0;
        Reason=FString::Printf(TEXT("camera inside the dragon in %d of %d frames (collapse/exposed %d of %d)"),CameraInsideFrames,CameraFrames,CollapseInsideFrames,CollapseFrames);
    }
    else
    {
        const float Median=Percentile(LiveGroundLowest,.5f),P90=Percentile(LiveGroundLowest,.9f);
        bPassed=LiveGroundLowest.Num()>=200&&Median>=-10.f*Scale&&Median<=12.f*Scale&&P90<=30.f*Scale;
        Reason=FString::Printf(TEXT("live ground frames %d: lowest sole median %.1f cm, p90 %.1f cm; worst clip median float %.1f cm at 1x (%s)"),
            LiveGroundLowest.Num(),Median,P90,WorstSweepFloatCm,*WorstSweepClip.ToString());
    }
    UE_LOG(LogTemp,Display,TEXT("VEYR_GATE a123 %s %s: %s"),*Mode,bPassed?TEXT("PASS"):TEXT("FAIL"),*Reason);
    if(Hooks.Finish)Hooks.Finish(bPassed,Reason);
}

TSharedPtr<FJsonObject> FVeyrA123Proof::Evidence() const
{
    TSharedPtr<FJsonObject> O=MakeShared<FJsonObject>();
    O->SetStringField(TEXT("mode"),Mode);O->SetBoolField(TEXT("done"),bDone);O->SetBoolField(TEXT("passed"),bPassed);
    O->SetNumberField(TEXT("bodyScale"),BodyScale);O->SetNumberField(TEXT("knightHealthRefills"),HealthRefills);
    O->SetBoolField(TEXT("legacyMirrorToe"),FParse::Param(FCommandLine::Get(),TEXT("VeyrLegacyMirrorToe")));
    O->SetBoolField(TEXT("legacyCameraBoom"),FParse::Param(FCommandLine::Get(),TEXT("VeyrLegacyCameraBoom")));
    O->SetBoolField(TEXT("noDragonGrounding"),FParse::Param(FCommandLine::Get(),TEXT("VeyrNoDragonGrounding")));
    if(SweepJson.IsValid())O->SetObjectField(TEXT("sweep"),SweepJson);
    const AVeyrDragon* D=Dragon.Get();
    const UVeyrSkeletalPresentation* P=D?D->ImportedPresentation.Get():nullptr;
    if(Mode==TEXT("footclosehits"))
    {
        O->SetNumberField(TEXT("mirroredClips"),MirroredClips);
        O->SetNumberField(TEXT("sweepMirroredMaxStretchCm1x"),SweepMirroredRepairedMaxCm);
        O->SetStringField(TEXT("sweepMirroredWorstBone"),SweepWorstBone.ToString());
        O->SetNumberField(TEXT("sweepLegacyMirroredMaxStretchCm1x"),SweepMirroredLegacyMaxCm);
        O->SetNumberField(TEXT("sweepUnmirroredMaxStretchCm1x"),SweepUnmirroredMaxCm);
        O->SetNumberField(TEXT("liveFrames"),LiveFrames);O->SetNumberField(TEXT("liveMirroredFrames"),LiveMirroredFrames);
        O->SetNumberField(TEXT("liveMirroredMaxStretchCm"),LiveMaxStretchCm);O->SetStringField(TEXT("liveWorstBone"),LiveWorstBone.ToString());
        O->SetNumberField(TEXT("liveMirrorRepairSamples"),P?P->MirrorRepairSamples-LiveMirrorSamplesStart:0);
    }
    else if(Mode==TEXT("camerahug"))
    {
        O->SetNumberField(TEXT("cameraFrames"),CameraFrames);O->SetNumberField(TEXT("cameraInsideFrames"),CameraInsideFrames);
        O->SetNumberField(TEXT("collapseFrames"),CollapseFrames);O->SetNumberField(TEXT("collapseInsideFrames"),CollapseInsideFrames);
        O->SetNumberField(TEXT("maxLiftCm"),MaxLiftCm);O->SetNumberField(TEXT("minBodyFraction"),MinFraction);
        O->SetNumberField(TEXT("maxCameraJumpCmPerFrame"),MaxCameraJumpCm);
        const UVeyrCameraBoom* B=Knight.IsValid()?Cast<UVeyrCameraBoom>(Knight->CameraBoom):nullptr;
        O->SetNumberField(TEXT("pullInEvents"),B?B->PullInEvents-PullInStart:0);
        O->SetNumberField(TEXT("boomShapes"),B?B->ShapeCount:0);
        TSharedPtr<FJsonObject> Shapes=MakeShared<FJsonObject>();
        for(const auto& Pair:InsideByShape)Shapes->SetNumberField(Pair.Key.ToString(),Pair.Value);
        O->SetObjectField(TEXT("insideByShape"),Shapes);
    }
    else
    {
        O->SetNumberField(TEXT("liveGroundFrames"),LiveGroundLowest.Num());
        O->SetNumberField(TEXT("liveLowestSoleMedianCm"),Percentile(LiveGroundLowest,.5f));
        O->SetNumberField(TEXT("liveLowestSoleP10Cm"),Percentile(LiveGroundLowest,.1f));
        O->SetNumberField(TEXT("liveLowestSoleP90Cm"),Percentile(LiveGroundLowest,.9f));
        O->SetNumberField(TEXT("sweepWorstClipMedianFloatCm1x"),WorstSweepFloatCm);
        O->SetStringField(TEXT("sweepWorstClip"),WorstSweepClip.ToString());
        O->SetNumberField(TEXT("groundingOffsetCm"),P?P->GroundingOffsetCm:0.f);
        O->SetStringField(TEXT("groundingDiagnostic"),P?P->GroundingDiagnostic:FString());
    }
    return O;
}
