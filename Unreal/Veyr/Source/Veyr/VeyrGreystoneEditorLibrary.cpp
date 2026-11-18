#include "VeyrGreystoneEditorLibrary.h"

#include "PoseSearch/PoseSearchDatabase.h"
#include "PoseSearch/PoseSearchSchema.h"

int32 UVeyrGreystoneEditorLibrary::RetargetPoseSearchDatabase(UPoseSearchDatabase* Database, const TMap<UObject*, UObject*>& Replacements, UPoseSearchSchema* Schema)
{
#if WITH_EDITOR
    if(!Database)return -1;
    Database->Modify();
    if(Schema)Database->Schema=Schema;
    int32 Replaced=0;
    for(int32 Index=0;Index<Database->GetNumAnimationAssets();++Index)
    {
        const FPoseSearchDatabaseAnimationAsset* Entry=Database->GetDatabaseAnimationAsset(Index);
        if(!Entry)continue;
        UObject* const* Mapped=Replacements.Find(Entry->AnimAsset.Get());
        if(!Mapped||!*Mapped)continue;
        FPoseSearchDatabaseAnimationAsset Copy=*Entry;
        Copy.AnimAsset=*Mapped;
        // Greystone has no mirror data table yet: keep only the original (unmirrored) poses.
        if(Schema&&!Schema->GetMirrorDataTable(UE::PoseSearch::DefaultRole))
            Copy.MirrorOption=EPoseSearchMirrorOption::UnmirroredOnly;
        Database->SetAnimationAssetAt(Copy,Index);
        ++Replaced;
    }
    Database->PostEditChange();
    Database->MarkPackageDirty();
    return Replaced;
#else
    return -1;
#endif
}

TArray<FString> UVeyrGreystoneEditorLibrary::ListPoseSearchDatabaseAssets(UPoseSearchDatabase* Database)
{
    TArray<FString> Out;
    if(!Database)return Out;
    for(int32 Index=0;Index<Database->GetNumAnimationAssets();++Index)
        if(const FPoseSearchDatabaseAnimationAsset* Entry=Database->GetDatabaseAnimationAsset(Index))
            Out.Add(Entry->AnimAsset?Entry->AnimAsset->GetPathName():FString());
    return Out;
}

int32 UVeyrGreystoneEditorLibrary::FilterPoseSearchDatabase(UPoseSearchDatabase* Database, const TArray<UObject*>& Keep)
{
#if WITH_EDITOR
    if(!Database)return -1;
    Database->Modify();
    int32 Removed=0;
    for(int32 Index=Database->GetNumAnimationAssets()-1;Index>=0;--Index)
    {
        const FPoseSearchDatabaseAnimationAsset* Entry=Database->GetDatabaseAnimationAsset(Index);
        if(Entry&&!Keep.Contains(Entry->AnimAsset.Get())){Database->RemoveAnimationAssetAt(Index);++Removed;}
    }
    Database->PostEditChange();
    Database->MarkPackageDirty();
    return Removed;
#else
    return -1;
#endif
}
