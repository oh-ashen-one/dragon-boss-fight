#include "VeyrKnight.h"
#include "VeyrSkeletalPresentation.h"
#include "VeyrVisualDefinition.h"
#include "Components/CapsuleComponent.h"

bool AVeyrKnight::BuildLocomotionPhaseCache()
{
    if(!CustomuseVisualDefinition||!ImportedPresentation)return false;
    if(!LocomotionPoseProbe)
    {
        LocomotionPoseProbe=NewObject<UVeyrSkeletalPresentation>(this,TEXT("HiddenLocomotionPhaseProbe"));
        AddInstanceComponent(LocomotionPoseProbe);LocomotionPoseProbe->ConfigureRenderPolicy(true,false);
        LocomotionPoseProbe->SetupAttachment(GetCapsuleComponent());LocomotionPoseProbe->SetVisibility(false);
        LocomotionPoseProbe->SetHiddenInGame(true);LocomotionPoseProbe->SetCastShadow(false);LocomotionPoseProbe->SetRenderInMainPass(false);
        LocomotionPoseProbe->RegisterComponent();
    }
    if(!LocomotionPoseProbe->SetVisualDefinition(CustomuseVisualDefinition,false))return false;
    static const FName Bones[]={TEXT("LeftToeBase"),TEXT("RightToeBase"),TEXT("LeftFoot"),TEXT("RightFoot")};
    constexpr int32 Count=96;
    for(FName Clip:{FName(TEXT("Walk")),FName(TEXT("WalkTwoHand")),FName(TEXT("Run")),FName(TEXT("RunAlternate")),FName(TEXT("RunTwoHandSourced")),FName(TEXT("RunOneHandPlanted")),FName(TEXT("RunTwoHandPlanted"))})
    {
        if(!HasVisualClip(Clip))continue;
        const float Duration=VisualClipDuration(Clip,1.f)*VisualClipPlayRate(Clip),Dt=Duration/Count;
        FLocomotionPhaseCache Cache;TArray<float> Heights[4];
        for(int32 I=0;I<Count;++I)
        {
            FLocomotionPhasePose Pose;Pose.Time=I*Dt;
            if(!LocomotionPoseProbe->SampleClipTime(Clip,Pose.Time))return false;
            for(int32 B=0;B<4;++B)
            {
                if(LocomotionPoseProbe->GetBoneIndex(Bones[B])==INDEX_NONE)return false;
                Pose.Points[B]=GetActorTransform().InverseTransformPosition(LocomotionPoseProbe->GetSocketLocation(Bones[B]));
                Heights[B].Add(Pose.Points[B].Z);
            }
            Cache.Poses.Add(Pose);
        }
        float Low[4];for(int32 B=0;B<4;++B){Heights[B].Sort();Low[B]=Heights[B][Count/10]+2.5f;}
        TArray<float> Speeds;
        for(int32 I=1;I<Count;++I)for(int32 Side=0;Side<2;++Side)
        {
            const FLocomotionPhasePose& A=Cache.Poses[I-1];const FLocomotionPhasePose& B=Cache.Poses[I];
            if(A.Points[Side].Z>Low[Side]||B.Points[Side].Z>Low[Side]||A.Points[Side+2].Z>Low[Side+2]||B.Points[Side+2].Z>Low[Side+2])continue;
            const float Backward=-((B.Points[Side].X-A.Points[Side].X)+(B.Points[Side+2].X-A.Points[Side+2].X))*.5f/Dt;
            if(Backward>50.f&&Backward<1600.f)Speeds.Add(Backward);
        }
        if(Speeds.Num()>=4){Speeds.Sort();Cache.NominalSpeed=Speeds[Speeds.Num()/2];}
        UE_LOG(LogTemp,Display,TEXT("VEYR_LOCOMOTION_CACHE clip=%s measuredNominal=%.2f samples=%d"),*Clip.ToString(),Cache.NominalSpeed,Speeds.Num());
        LocomotionPhaseCache.Add(Clip,MoveTemp(Cache));
    }
    return bPlantedSprint?
        LocomotionPhaseCache.Contains(TEXT("RunOneHandPlanted"))&&LocomotionPhaseCache.Contains(TEXT("RunTwoHandPlanted")):
        LocomotionPhaseCache.Contains(TEXT("RunTwoHandSourced"));
}

float AVeyrKnight::ClosestLocomotionPhase(FName Clip) const
{
    const FLocomotionPhaseCache* Cache=LocomotionPhaseCache.Find(Clip);
    if(!Cache||!Cache->Poses.Num()||!ImportedPresentation||!ImportedPresentation->bPoseEvaluated)return 0.f;
    static const FName Bones[]={TEXT("LeftToeBase"),TEXT("RightToeBase"),TEXT("LeftFoot"),TEXT("RightFoot")};
    FVector Current[4];for(int32 B=0;B<4;++B)Current[B]=GetActorTransform().InverseTransformPosition(ImportedPresentation->GetSocketLocation(Bones[B]));
    float Best=MAX_flt,Time=0.f;
    for(const FLocomotionPhasePose& Pose:Cache->Poses)
    {
        float Cost=0.f;
        for(int32 B=0;B<4;++B){const FVector D=Pose.Points[B]-Current[B];Cost+=D.X*D.X+D.Y*D.Y+.6f*D.Z*D.Z;}
        if(Cost<Best){Best=Cost;Time=Pose.Time;}
    }
    return Time;
}
