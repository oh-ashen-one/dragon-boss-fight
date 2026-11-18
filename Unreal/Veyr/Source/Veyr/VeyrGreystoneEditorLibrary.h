#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "VeyrGreystoneEditorLibrary.generated.h"

class UPoseSearchDatabase;
class UPoseSearchSchema;

/** Quality goal E5 editor helpers for the tools/unreal/greystone Python scripts. UPoseSearchDatabase keeps its animation list in a
 * private property that Python cannot reach, so the copy-and-swap of GASP databases onto Greystone's retargeted clips
 * goes through these. Editor builds only (they return -1 / false in a game build). */
UCLASS()
class UVeyrGreystoneEditorLibrary : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()
public:
    /** Replace every animation entry whose asset is a key of Replacements by the mapped asset (keeping sampling range,
     * mirror option and flags), optionally set the schema. Returns the number replaced, -1 on error. */
    UFUNCTION(BlueprintCallable, Category="Veyr|Greystone")
    static int32 RetargetPoseSearchDatabase(UPoseSearchDatabase* Database, const TMap<UObject*, UObject*>& Replacements, UPoseSearchSchema* Schema);

    /** Asset paths of every animation entry, in order (for receipts and the fallback-table baker). */
    UFUNCTION(BlueprintCallable, Category="Veyr|Greystone")
    static TArray<FString> ListPoseSearchDatabaseAssets(UPoseSearchDatabase* Database);

    /** Remove entries whose asset is not in Keep (e.g. GASP clips with no Greystone equivalent). Returns removed count. */
    UFUNCTION(BlueprintCallable, Category="Veyr|Greystone")
    static int32 FilterPoseSearchDatabase(UPoseSearchDatabase* Database, const TArray<UObject*>& Keep);
};
