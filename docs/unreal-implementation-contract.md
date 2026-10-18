# Native Unreal migration contract

User changed the target to Unreal Engine and Customuse on2026-10-18. Unity009 is preserved history, not Unreal evidence. Root alone owns engine launches, native MCP connection, builds and integration. Workers write disjoint source files only. Installed engine5.8.3, Xcode27.0. Length units are centimeters; +X forward,+Y right,+Z up.

Project: `Unreal/Veyr/Veyr.uproject`, module `Veyr`, macro `VEYR_API`.

## Native interfaces

- `AVeyrKnight : ACharacter`: public `float Health=100,Stamina=100; int32 HealingCharges=4; EVeyrKnightAction Action; TObjectPtr<AVeyrDragon> Boss; bool bLockedOn;` and `bool IsDead() const`, `void ApplyBossDamage(float Amount,const FVector& Source,bool bUnblockable=false)`, `void TryLightAttack()`, `void TryHeavyAttack()`, `void TryRoll()`, `void TryHeal()`, `void SetGuard(bool)`, `void ToggleLockOn()`. Character height244cm. Movement/camera/input owned here. Space jump,Shift roll,J/LMB light,K heavy,F/RMB guard,Q heal,Tab lock,R terminal restart. Preserve action/health ownership. Expose read-only action timing/state needed by imported animations and tests.
- `AVeyrDragon : AActor`: public `float Health=8400,MaxHealth=8400; EVeyrDragonState State; EVeyrDragonMove Move; TObjectPtr<AVeyrKnight> Target;` getters `bool IsDead() const`, `bool IsHeadExposed() const`, `FVector GetHeadLocation() const`, `FVector GetLegLocation(int32) const`, `float GetLegStagger(int32) const`; method `void ReceiveSword(const FVector& Origin,const FVector& Forward,bool bHeavy,int32 SwingId)`. Four independent leg regions with100stagger thresholds. Preserve buckle→collapse→7s head exposure→rise; heavy vs light must have distinct damage/stagger/cost/contact timing.
- `AVeyrArena : AActor`: constructor and BeginPlay create original bounded arena. Radius3600cm. Floor topZ0; knight spawn(-1600,0,125); boss spawn(500,0,0). Preserve walkable center, clear flight landing zones. No new external assets or generator calls. Temporary geometry must be labeled.
- Root owns `AVeyrGameMode`, `AVeyrHUD`, source scaffold/config, native evidence/replay integration. GameMode spawns one arena and one dragon, binds pawn, handles terminal restart. Workers must not overwrite other files or launch an editor/compiler.

Temporary old original assets may support early engine verification. New main mesh creation is Customuse; website rig/animation capability is being inspected. No paid generation or Blender fallback is approved. Do not invent clips or label procedural proxies as Customuse output.
