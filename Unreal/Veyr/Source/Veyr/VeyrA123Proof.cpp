#include "VeyrA123Proof.h"
#include "VeyrCameraBoom.h"
#include "VeyrDragon.h"
#include "VeyrKnight.h"
#include "VeyrSkeletalPresentation.h"
#include "VeyrVisualDefinition.h"
#include "Animation/AnimSequence.h"
#include "Camera/CameraComponent.h"
#include "Camera/CameraActor.h"
#include "GameFramework/PlayerController.h"
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
    LiveSeconds=Mode==TEXT("camerahug")?200.f:Mode==TEXT("footclosehits")?560.f:150.f;
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
    // Sole sweeps run at the shipped game scale (the dragon's own actor scale); stretch sweeps at 1x.
    if(Mode==TEXT("soleheights"))Host->SetActorScale3D(D->GetActorScale3D());
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
    P->bGroundingEnabled=true;
    TArray<TSharedPtr<FJsonValue>> Clips;
    constexpr float Step=1.f/30.f;
    for(const auto& Pair:P->VisualDefinition->Clips)
    {
        if(!Pair.Value.Sequence||!IsGroundClip(Pair.Key))continue;
        const float Seconds=ClipSeconds(Pair.Value);
        // Before: no offset. After: the shipped grounding rule stepped at 30 Hz, settled 2 s on the first
        // frame (as when the clip follows a grounded idle), then run through the clip.
        TArray<float> Before,After;float PlantedWorst=0.f;int32 PlantedSamples=0;
        P->ResetGrounding();
        for(float T=0.f;T<=Seconds+1e-3f;T+=Step)
        {
            FVeyrSoleSample S;
            if(!P->SampleClipTime(Pair.Key,T)||!P->MeasureSoles(S)){++SoleFailures;continue;}
            Before.Add(S.LowestAboveFloorCm);
        }
        P->ResetGrounding();
        if(P->SampleClipTime(Pair.Key,0.f))for(int32 I=0;I<60;++I)P->StepGrounding(EVeyrGroundingMode::Ground,Step);
        FVector Previous[4];bool bHasPrevious=false;TArray<float> Support;float StillWorst=0.f;
        for(float T=0.f;T<=Seconds+1e-3f;T+=Step)
        {
            FVeyrSoleSample S;
            if(!P->SampleClipTime(Pair.Key,T))continue;
            P->StepGrounding(EVeyrGroundingMode::Ground,Step);
            if(!P->MeasureSoles(S)){++SoleFailures;continue;}
            After.Add(S.LowestAboveFloorCm);
            // The planted (support) sole is the lowest one: the foot the body rests on. Its distance from
            // the floor, either way, is what reads as floating or sinking.
            Support.Add(FMath::Abs(S.LowestAboveFloorCm));
            // Reported only: other feet that are low (under 15 cm x scale) and still (under 1.5 cm x scale a
            // frame) but not the support, i.e. a paw resting just off the floor.
            for(int32 F=0;F<4;++F)
            {
                const bool bSlow=bHasPrevious&&FVector::Dist2D(S.Lowest[F],Previous[F])<1.5f*Scale;
                if(bSlow&&S.SoleAboveFloorCm[F]<15.f*Scale){StillWorst=FMath::Max(StillWorst,FMath::Abs(S.SoleAboveFloorCm[F]));}
                Previous[F]=S.Lowest[F];
            }
            bHasPrevious=true;
        }
        PlantedSamples=Support.Num();PlantedWorst=Support.IsEmpty()?0.f:Percentile(Support,.9f);
        if(Before.IsEmpty())continue;
        ++SweepGroundClips;SweepClipsWithin3Cm+=PlantedWorst<=3.f?1:0;
        TSharedPtr<FJsonObject> C=MakeShared<FJsonObject>();
        C->SetStringField(TEXT("clip"),Pair.Key.ToString());C->SetBoolField(TEXT("mirrored"),IsMirrored(Pair.Value));
        C->SetNumberField(TEXT("beforeLowestSoleMedianCm"),Percentile(Before,.5f));
        C->SetNumberField(TEXT("beforeLowestSoleMinCm"),Percentile(Before,0.f));
        C->SetNumberField(TEXT("beforeLowestSoleMaxCm"),Percentile(Before,1.f));
        C->SetNumberField(TEXT("afterLowestSoleMedianCm"),Percentile(After,.5f));
        C->SetNumberField(TEXT("afterLowestSoleMaxCm"),Percentile(After,1.f));
        C->SetNumberField(TEXT("afterSupportSoleP90AbsCm"),PlantedWorst);
        C->SetNumberField(TEXT("afterSupportSoleMaxAbsCm"),Support.IsEmpty()?0.f:Percentile(Support,1.f));
        C->SetNumberField(TEXT("afterSupportSamples"),PlantedSamples);
        C->SetNumberField(TEXT("afterLowStillOtherFootWorstCm"),StillWorst);
        Clips.Add(MakeShared<FJsonValueObject>(C));
        if(Pair.Key.ToString().StartsWith(TEXT("IdleOpen")))SweepBeforeIdleMedianCm=Percentile(Before,.5f);
        SweepWorstBeforeMedianCm=FMath::Max(SweepWorstBeforeMedianCm,Percentile(Before,.5f));
        if(Percentile(Before,.5f)>WorstSweepFloatCm){WorstSweepFloatCm=Percentile(Before,.5f);WorstSweepClip=Pair.Key;}
        if(PlantedWorst>SweepWorstPlantedAfterCm){SweepWorstPlantedAfterCm=PlantedWorst;SweepWorstPlantedClip=Pair.Key;}
    }
    SweepJson->SetArrayField(TEXT("clips"),Clips);
    SweepJson->SetStringField(TEXT("scope"),TEXT("pose probe at the dragon's actor scale and floor point; cm are game cm"));
    SweepJson->SetStringField(TEXT("soleModel"),P->GetSoleModel().Diagnostic);
    SweepJson->SetNumberField(TEXT("soleModelFitResidualImportedCm"),P->GetSoleModel().FitResidualImportedCm);
    SweepJson->SetNumberField(TEXT("sampleFailures"),SoleFailures);
}

void FVeyrA123Proof::UpdateSideCamera()
{
    AVeyrDragon* D=Dragon.Get();AVeyrKnight* K=Knight.Get();UWorld* W=World.Get();
    if(!D||!K||!W)return;
    ACameraActor* Cam=SideCamera.Get();
    if(!Cam)
    {
        FActorSpawnParameters Params;Params.SpawnCollisionHandlingOverride=ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
        Cam=W->SpawnActor<ACameraActor>(D->GetActorLocation(),FRotator::ZeroRotator,Params);
        if(!Cam)return;
        SideCamera=Cam;
        if(APlayerController* PC=Cast<APlayerController>(K->GetController()))PC->SetViewTarget(Cam);
    }
    // Side-on at floor level on the near front paw, close enough that a few cm of float or sink reads:
    // lens 20 cm above the floor, 450 cm x scale from the paw, 60 degree lens. Of the two flanks take the one
    // with more room (swept against the camera channel), sticky so the view does not flip.
    const FVector Right=D->GetActorRightVector(),Forward=D->GetActorForwardVector();
    const float Want=450.f*Scale;
    UVeyrSkeletalPresentation* P=D->ImportedPresentation;
    auto PawFor=[&](float Sign)
    {
        static const TCHAR* Feet[4]={TEXT("bone_9"),TEXT("tripo__0_Left_Limb_3"),TEXT("tripo__1_Right_Limb_4"),TEXT("tripo__0_Right_Limb_4")};
        FVector Best=D->GetActorLocation();double BestScore=-1e30;
        for(const TCHAR* Name:Feet)
        {
            const int32 Bone=P?P->GetBoneIndex(Name):INDEX_NONE;
            if(Bone==INDEX_NONE)continue;
            const FVector L=P->GetBoneTransform(Bone).GetLocation();
            const FVector R=L-D->GetActorLocation();
            const double Score=FVector::DotProduct(R,Right)*Sign+FVector::DotProduct(R,Forward)*.5;
            if(Score>BestScore){BestScore=Score;Best=L;}
        }
        return FVector(Best.X,Best.Y,D->GetActorLocation().Z);
    };
    auto Room=[&](const FVector& From,const FVector& Dir)
    {
        FHitResult Hit;FCollisionQueryParams Q(SCENE_QUERY_STAT(VeyrSoleSideCamera),false,D);Q.AddIgnoredActor(K);
        const FVector A=From+FVector(0,0,20.f);
        return W->SweepSingleByChannel(Hit,A,A+Dir*Want,FQuat::Identity,ECC_Camera,FCollisionShape::MakeSphere(20.f),Q)?FMath::Max(0.f,Hit.Distance-40.f):Want;
    };
    const FVector PawRight=PawFor(1.f),PawLeft=PawFor(-1.f);
    const float RoomRight=Room(PawRight,Right),RoomLeft=Room(PawLeft,-Right);
    if(SideSign==0.f||(SideSign>0.f?RoomRight:RoomLeft)<Want*.6f)SideSign=RoomRight>=RoomLeft?1.f:-1.f;
    const FVector Paw=SideSign>0.f?PawRight:PawLeft;
    const float Distance=SideSign>0.f?RoomRight:RoomLeft;
    // Smooth the aim point so the camera does not shake with each step.
    SideAim=SideAimValid?FMath::VInterpTo(SideAim,Paw,1.f/30.f,4.f):Paw;SideAimValid=true;
    const FVector Eye=SideAim+Right*SideSign*Distance+FVector(0,0,20.f);
    Cam->SetActorLocationAndRotation(Eye,(SideAim+FVector(0,0,40.f)-Eye).Rotation());
    Cam->GetCameraComponent()->SetFieldOfView(60.f);
    SideCameraDistanceCm=Distance;
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
        // Front -Z, front +Z (the mirrored clips' toe), hind -Z, hind +Z.
        static const TCHAR* Feet[4]={TEXT("bone_9"),TEXT("tripo__0_Left_Limb_3"),TEXT("tripo__1_Right_Limb_4"),TEXT("tripo__0_Right_Limb_4")};
        UVeyrSkeletalPresentation* P=D->ImportedPresentation;
        const int32 Foot=P?P->GetBoneIndex(Feet[FMath::Clamp(FootIndex,0,3)]):INDEX_NONE;
        return Foot!=INDEX_NONE?P->GetBoneTransform(Foot).GetLocation():D->GetActorLocation();
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
        Sweep();LiveStart=FootStart=Elapsed;
        if(AVeyrDragon* D0=Dragon.Get())LastSwordContacts=D0->GetSwordContactCount();
        if(Hooks.Shot)Hooks.Shot(Mode+TEXT("_live_start"));
        const AVeyrDragon* D=Dragon.Get();
        if(D&&D->ImportedPresentation)LiveMirrorSamplesStart=D->ImportedPresentation->MirrorRepairSamples;
        if(const UVeyrCameraBoom* B=Knight.IsValid()?Cast<UVeyrCameraBoom>(Knight->CameraBoom):nullptr)PullInStart=B->PullInEvents;
        return;
    }
    Live(Elapsed,Dt);
    if(Elapsed-LiveStart>=LiveSeconds||(Mode==TEXT("footclosehits")&&FootIndex>=4))Finalize(Elapsed);
}

void FVeyrA123Proof::Live(double Elapsed,float Dt)
{
    AVeyrKnight* K=Knight.Get();AVeyrDragon* D=Dragon.Get();
    if(!K||!D)return;
    if(K->Health<45.f){K->Health=100.f;++HealthRefills;} // same refill as the camp mode, so the run lasts
    // footclosehits needs 80 landed leg hits, far beyond the boss's health: top it up (test only, counted).
    if(Mode==TEXT("footclosehits")&&!D->IsDead()&&D->Health<D->MaxHealth*.4f){D->Health=D->MaxHealth*.85f;++BossHealthRefills;}
    const FVector Target=KnightTargetFor(Elapsed);
    FVector To=Target-K->GetActorLocation();To.Z=0;
    const float Near=Mode==TEXT("footclosehits")?300.f:Mode==TEXT("soleheights")?150.f:120.f;
    const bool bArrived=To.Size()<Near;
    const bool bAttack=Mode!=TEXT("soleheights")&&bArrived&&FMath::Fmod(Elapsed,Mode==TEXT("footclosehits")?.3:.6)<Dt*1.5;
    Input(bArrived?FVector::ZeroVector:To.GetSafeNormal(),bAttack);
    UVeyrSkeletalPresentation* P=D->ImportedPresentation;
    if(Mode==TEXT("footclosehits")&&P&&P->bPoseEvaluated)
    {
        ++LiveFrames;
        // Count landed sword contacts while at this foot; 20 on a leg region moves on to the next foot.
        const int32 Contacts=D->GetSwordContactCount();
        if(Contacts>LastSwordContacts&&FootIndex<4)
        {
            const int32 Region=D->GetLastHitRegion();
            if(Region>=0&&Region<6)++RegionHits[FootIndex][Region];
            if(Region>=0&&Region<4)++FootHits[FootIndex];
            if(Hooks.Shot&&Elapsed-LastShot>1.0){LastShot=Elapsed;Hooks.Shot(FString::Printf(TEXT("foot%d_hit%d"),FootIndex,FootHits[FootIndex]));}
        }
        LastSwordContacts=Contacts;
        if(FootIndex<4&&(FootHits[FootIndex]>=20||Elapsed-FootStart>LiveSeconds/4.0)){++FootIndex;FootStart=Elapsed;}
        {FName Any;const float Stretch=P->MeasureMaxLinkStretchCm(Any);if(Stretch>LiveAllMaxStretchCm){LiveAllMaxStretchCm=Stretch;LiveAllWorstBone=Any;}}
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
            // Three independent views of "inside", each with a 10 cm near-plane margin: the solid capsules
            // (knight push bodies), the back-face check (9 of the 12 nearest skinned body samples face away;
            // wings are open sheets and are left out),
            // and the conservative hull spheres the boom itself keeps clear of (reported, not gated).
            const bool bCapsule=B->IsPointInsideSolidCapsule(Cam,10.f,&Shape);
            float Depth=0.f;
            const bool bBack=B->IsPointBehindSkin(Cam,10.f,&Depth);
            FName HullShape;
            if(B->IsPointInsideBareDragon(Cam,10.f,&HullShape))++HullInsideFrames;
            if(bBack){++BackFaceFrames;MaxBackFaceDepthCm=FMath::Max(MaxBackFaceDepthCm,Depth);if(!bCapsule)Shape=TEXT("BackFace");}
            const bool bInside=bCapsule||bBack;
            (void)S;
            ++CameraFrames;
            const bool bCollapse=D->State==EVeyrDragonState::Collapse||D->State==EVeyrDragonState::Exposed;
            CollapseFrames+=bCollapse?1:0;
            if(bCapsule)++CapsuleInsideFrames;
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
    if(Mode==TEXT("soleheights"))UpdateSideCamera();
    if(Mode==TEXT("soleheights")&&P&&P->bPoseEvaluated&&VeyrGroundingModeFor(D)==EVeyrGroundingMode::Ground)
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
        int32 MinFootHits=TNumericLimits<int32>::Max();for(int32 F=0;F<4;++F)MinFootHits=FMath::Min(MinFootHits,FootHits[F]);
        bPassed=MirroredClips>0&&SweepMirroredRepairedMaxCm<=Limit&&LiveMaxStretchCm<=Limit*BodyScale&&MinFootHits>=20;
        Reason=FString::Printf(TEXT("mirrored clips %d: repaired stretch %.1f cm (1x, limit %.1f), legacy %.1f; live mirrored frames %d max %.1f cm; leg hits per foot %d/%d/%d/%d"),
            MirroredClips,SweepMirroredRepairedMaxCm,Limit,SweepMirroredLegacyMaxCm,LiveMirroredFrames,LiveMaxStretchCm,FootHits[0],FootHits[1],FootHits[2],FootHits[3]);
    }
    else if(Mode==TEXT("camerahug"))
    {
        bPassed=CameraFrames>300&&CameraInsideFrames==0;
        Reason=FString::Printf(TEXT("camera inside the dragon in %d of %d frames: capsule %d, back-face %d (collapse/exposed %d of %d; conservative hull %d)"),
            CameraInsideFrames,CameraFrames,CapsuleInsideFrames,BackFaceFrames,CollapseInsideFrames,CollapseFrames,HullInsideFrames);
    }
    else
    {
        const float Median=Percentile(LiveGroundLowest,.5f),P90=Percentile(LiveGroundLowest,.9f);
        // Done when: planted soles within 3 cm of the floor in every ground clip at the shipped scale.
        bPassed=SweepGroundClips>0&&SweepClipsWithin3Cm==SweepGroundClips&&LiveGroundLowest.Num()>=200&&FMath::Abs(Median)<=3.f;
        Reason=FString::Printf(TEXT("sweep: %d of %d ground clips with the planted sole within 3 cm, p90 (worst %.1f cm, %s); before: idle float %.1f cm, worst clip median %.1f cm (%s); live ground frames %d lowest sole median %.1f p90 %.1f cm"),
            SweepClipsWithin3Cm,SweepGroundClips,SweepWorstPlantedAfterCm,*SweepWorstPlantedClip.ToString(),SweepBeforeIdleMedianCm,WorstSweepFloatCm,*WorstSweepClip.ToString(),LiveGroundLowest.Num(),Median,P90);
    }
    UE_LOG(LogTemp,Display,TEXT("VEYR_GATE a123 %s %s: %s"),*Mode,bPassed?TEXT("PASS"):TEXT("FAIL"),*Reason);
    if(Hooks.Finish)Hooks.Finish(bPassed,Reason);
}

TSharedPtr<FJsonObject> FVeyrA123Proof::Evidence() const
{
    TSharedPtr<FJsonObject> O=MakeShared<FJsonObject>();
    O->SetStringField(TEXT("mode"),Mode);O->SetBoolField(TEXT("done"),bDone);O->SetBoolField(TEXT("passed"),bPassed);
    O->SetNumberField(TEXT("bodyScale"),BodyScale);O->SetNumberField(TEXT("knightHealthRefills"),HealthRefills);
    O->SetNumberField(TEXT("bossHealthRefills"),BossHealthRefills);
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
        O->SetNumberField(TEXT("liveAnyClipMaxStretchCm"),LiveAllMaxStretchCm);O->SetStringField(TEXT("liveAnyClipWorstBone"),LiveAllWorstBone.ToString());
        TArray<TSharedPtr<FJsonValue>> Hits;for(int32 F=0;F<4;++F)Hits.Add(MakeShared<FJsonValueNumber>(FootHits[F]));
        O->SetArrayField(TEXT("legHitsPerFoot"),Hits);
        TArray<TSharedPtr<FJsonValue>> Regions;
        for(int32 F=0;F<4;++F){TArray<TSharedPtr<FJsonValue>> Row;for(int32 R=0;R<6;++R)Row.Add(MakeShared<FJsonValueNumber>(RegionHits[F][R]));Regions.Add(MakeShared<FJsonValueArray>(Row));}
        O->SetArrayField(TEXT("regionHitsPerFootTarget"),Regions);
    }
    else if(Mode==TEXT("camerahug"))
    {
        O->SetNumberField(TEXT("cameraFrames"),CameraFrames);O->SetNumberField(TEXT("cameraInsideFrames"),CameraInsideFrames);
        O->SetNumberField(TEXT("capsuleInsideFrames"),CapsuleInsideFrames);O->SetNumberField(TEXT("backFaceFrames"),BackFaceFrames);
        O->SetNumberField(TEXT("maxBackFaceDepthCm"),MaxBackFaceDepthCm);O->SetNumberField(TEXT("hullInsideFrames"),HullInsideFrames);
        if(UVeyrCameraBoom* GB=Knight.IsValid()?Cast<UVeyrCameraBoom>(Knight->CameraBoom):nullptr){O->SetNumberField(TEXT("boomGuardEvents"),GB->GuardEvents);O->SetNumberField(TEXT("boomPivotInsideFrames"),GB->PivotInsideFrames);O->SetNumberField(TEXT("boomResultInsideFrames"),GB->ResultInsideFrames);}
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
        O->SetNumberField(TEXT("sweepBeforeIdleFloatCm"),SweepBeforeIdleMedianCm);
        O->SetNumberField(TEXT("sweepBeforeWorstClipMedianCm"),WorstSweepFloatCm);
        O->SetNumberField(TEXT("sweepAfterPlantedWorstCm"),SweepWorstPlantedAfterCm);
        O->SetNumberField(TEXT("sideCameraDistanceCm"),SideCameraDistanceCm);
        if(const AVeyrDragon* GD=Dragon.Get();GD&&GD->ImportedPresentation)O->SetBoolField(TEXT("groundingLowerOnly"),GD->ImportedPresentation->bGroundingLowerOnly);
        O->SetStringField(TEXT("sweepAfterPlantedWorstClip"),SweepWorstPlantedClip.ToString());
        O->SetNumberField(TEXT("sweepGroundClips"),SweepGroundClips);O->SetNumberField(TEXT("sweepClipsWithin3Cm"),SweepClipsWithin3Cm);
        O->SetStringField(TEXT("sweepWorstClip"),WorstSweepClip.ToString());
        O->SetNumberField(TEXT("groundingOffsetCm"),P?P->GroundingOffsetCm:0.f);
        O->SetStringField(TEXT("groundingDiagnostic"),P?P->GroundingDiagnostic:FString());
    }
    return O;
}
