# Manager progress — Better Skirmisher Separation

## Task
Small Bannerlord mod. When the player sets a formation's troop preference to Throwing Weapons
(the formation-composition / "preferences" UI in the Order of Battle / formation settings),
vanilla puts Legionaries / Menavlions (who carry 1-2 pilas / throwing spears) there instead of
real skirmishers with two stacks of javelins. Rank throwers by throwable amount:
- 2+ stacks of javelins (or other proper throwing stacks) = highest
- 1 stack = high
- 1-2 pilas / single heavy throwing spears = medium
- no throwables = low (not a thrower)

Project folder: C:\Users\Trax\Documents\BannerlordMods\better_skirmisher_separation (empty at start)
Reference: ..\reference\game-decompiled (decompiled game), ..\TrainingBattlesMod (an existing mod by Anton — copy its build setup/conventions)

## Steps
1. [x] Research: find in decompiled game how troops are assigned to formations by weapon preference
       (Throwing Weapons class / FormationClass / OrderOfBattle / troop sorting), where the
       "is thrower" decision is made, and the best Harmony patch point. Also how TrainingBattlesMod is built
       (csproj, SubModule.xml, Harmony ref, game path, deploy). Write findings to .manager/research.md.
2. [x] Implement: project scaffold + SubModule.xml + Harmony patch with the tiered scoring. Builds clean.
3. [x] Review: independent agent reviews the code against the decompiled game for correctness/edge cases
       (thrown weapon with ammo counts, multiplayer safety, siege, other formations unaffected). Fix issues.
4. [x] Package: deploy to game Modules folder, README with install + how it works.

## Log
- Step 1 done (research.md). Root cause: TroopFilteringUtilities.GetTroopPriority gives flat +10 for Thrown
  (Agent.HasThrownCached is true for pila's secondary throw mode). Team.RearrangeFormationsAccordingToFilter
  fills best-score-first, so graded scores just work. Plan: transpile RearrangeFormationsAccordingToFilter,
  swap GetPriorityFunction call for our wrapper; tiers 2+ stacks=10, 1 stack=7, pila-only=3, cached per agent.
  Build: net472, game v1.4.8 at D:\SteamLibrary\...\Bannerlord, Harmony 2.4.2 from Bannerlord.Harmony (2859188632).
- Step 2 done. Files: Directory.Build.props (GameFolder, HarmonyBinFolder, DeployToGame), .gitignore, README.md,
  module/SubModule.xml (Id BetterSkirmisherSeparation, v1.0.0; deps Bannerlord.Harmony + Native v1.4.8 only;
  no Sandbox deps since the patch is in TaleWorlds.MountAndBlade and works in custom battle),
  src/BetterSkirmisherSeparation/{BetterSkirmisherSeparation.csproj, SubModule.cs, PriorityFunctionPatch.cs, ThrownPriority.cs}.
  Build: `dotnet build ... -c Release` = 0 warnings, 0 errors; outputs to module/bin/Win64_Shipping_Client; an
  AfterBuild target mirrors module/ into D:\SteamLibrary\...\Bannerlord\Modules\BetterSkirmisherSeparation (deployed).
  Patching: transpiler matches the call by MethodInfo (CodeInstruction.Calls), applied to Team.RearrangeFormationsAccordingToFilter
  AND OrderController.TransferUnitWithPriorityFunction (the only two callers of the Agent overload; verified 1 call each in the
  shipped DLL's IL via reflection). Second one is inert in vanilla (hasThrown:false) but keeps mods consistent.
  Not found / exception -> Debug.Print + one yellow message at main menu, vanilla untouched.
  Cache: per-call Dictionary<Agent,int> inside the returned closure (closure lives only for one rearrange/transfer call),
  so it cannot go stale across missions or leak agents and re-reads equipment on every distribution.
  Reviewer check: tier logic in ThrownPriority.GetTier (first usage that is RangedWeapon&&Consumable; index 0 = stack,
  else single; empty / Amount<=0 skipped -> such an agent still has HasThrownCached but scores tier 0);
  score = vanilla - 10 + tier only when filter has Thrown and agent.HasThrownCached; Stone/Boulder primary usages
  would count as stacks (agents don't spawn with them); exact DependentVersion v1.4.8 pin on Native may warn on future patches.
- Step 3 done (independent review). Evidence from decompiled 1.4.8 + shipped DLL IL + installed item XML.
  Path: only callers of Team.RearrangeFormationsAccordingToFilter are OrderOfBattleVM (Initialize->DistributeAllTroops,
  DistributeTroops on weight/filter toggle, TransferAllAvailableTroopsToFormation); no in-battle filter re-apply exists
  (MissionOrderVM filters are display only). Bypasses (vanilla, NOT patched): reinforcements
  (MissionReinforcementsHelper picks formation by GetAgentTroopClass + class ratios, so Legionary reinforcements can join an
  infantry skirmisher formation mid-battle); NavalDLC ship assignment (NavalShipAgents -> GetTroopPriority, origin traits
  where pila = Spear, so it never adds legionaries via Thrown); OOB not shown / only one formation of a class -> no filtering.
  Items: crafting templates Javelin/ThrowingAxe/ThrowingKnife put the thrown usage first (stack 3-5 in all vanilla items);
  TwoHandedPolearm puts TwoHandedPolearm_Thrown last (isAlternative -> amount 1). Simulated crafting on real XML:
  singles = imperial_throwing_spear_1_t4, eastern_throwing_spear_1_t3/_2_t4 (+mp_). NOTE imperial_throwing_spear_1_t4_2
  ("Pilum", handle spear_handle_13_2) has NO thrown usage, so Legionaries carry 1 throwable pilum. Tiers: battanian_skirmisher,
  battanian_veteran_skirmisher, battanian_wildling, sturgian_veteran_warrior, sturgian_brigand, empire/sturgia marines = 10;
  aserai_infantry, sturgian_spearman, battanian_woodrunner, imperial_trained_infantryman, vlandian_voulgier, aserai_faris = 7;
  imperial_legionary, imperial_elite_menavliaton, imperial_veteran_infantryman, khuzait_spear_infantry/darkhan = 3.
  FIXED: (1) vanilla fill loop computes `list2.OrderByDescending(ScoreToSeek)` and discards it (IL: call; pop), then seeks
  list2[0].ScoreToSeek. With graded scores, another same-class filtered pocket ordered first (e.g. Infantry+Shield) drops the
  threshold to 101 and the thrown formation then takes troops in list order (sim: 10 skirm + 5 one-stack + 14 plain + 1 pila
  instead of 10 + 15 + 5 pila). Transpiler now swaps that call (only the one followed by pop) for ThrownPriority.SortPockets,
  which sorts in place (stable) only if a pocket uses our GradedPriority -> non-Thrown distributions stay vanilla.
  Verified by applying the patch to the real TaleWorlds.MountAndBlade.dll in PowerShell: both swaps land, no warnings.
  (2) Closure -> explicit GradedPriority class (marker for the above); GetTier wrapped in try/catch falling back to vanilla score.
  (3) Primary-thrown item with ModifiedMaxAmount<=1 (modded one-shot) counts as a single. (4) Native DependentVersion/version
  v1.4.8 pin removed (Anton's other mods use none; avoids launcher mismatch warnings on patches). README: Limits section.
  Build Release 0 warnings/0 errors, deployed.
  OK as is: Harmony id, null agent/Character/Equipment (vanilla returns max), heroes/player scored like anyone, MP (OOB is SP
  only; ModuleCategory Singleplayer), Stone/Boulder never in spawn equipment.
  OPEN / design: reinforcements bypass (would need a GetReinforcementAssignments patch); Thrown+HighTier/LowTier lets tier
  points (<=7) cross the 3-4 point gaps (e.g. t6 non-thrower 107 > t1 pila 105); Thrown+Shield ranks a shielded non-thrower
  (111) above a shieldless pila troop (104) — consistent with vanilla's additive traits. Needs in-game test: OOB with
  Infantry+Thrown next to Infantry+Shield, and a quick look at the filter count tooltip (still counts pila as thrown, cosmetic).
- Step 4 done (manager check): module deployed to game Modules\BetterSkirmisherSeparation, README present. Open follow-up offered to user: reinforcements join by troop class (separate patch).

## Phase 2 (user request 2026-10-01): MCM settings
5. [x] MCM settings: master on/off switch + "minimum throwables to count as skirmisher" threshold
       (total throwable count across slots; below it the agent gets no Thrown bonus at all).
6. [x] Review of step 5.
- Step 5 done (MCM settings). Files: NEW src/BetterSkirmisherSeparation/McmSettings.cs (AttributeGlobalSettings<McmSettings>,
  Id BetterSkirmisherSeparation_v1, folder BetterSkirmisherSeparation, json2, group "General": Enabled bool default true,
  MinThrowables int slider 1-10 default 1, hints mention examples and that it applies in the Order of Battle),
  NEW Settings.cs (static reader: checks the MCMv5 assembly is loaded, then reads McmSettings.Instance inside a NoInlining
  method; null instance / any exception -> defaults; MinThrowables clamped >= 1), ThrownPriority.cs, csproj (MCMv5 reference
  Private=false), Directory.Build.props (McmBinFolder = workshop 2859238197 bin), module/SubModule.xml, README (Settings section,
  install/build notes).
  Design: follows TrainingBattlesMod/ImmersiveAI exactly - MCM is a SOFT dependency: DependedModuleMetadata
  Bannerlord.MBOptionScreen LoadBeforeThis optional="true", not in DependedModules; no UIExtenderEx/ButterLib entries (MCM declares
  those itself, Anton's mods don't). Settings are read once per ThrownPriority.GetPriorityFunction call (i.e. per OOB
  distribution), so toggles apply live. Enabled=false -> GetPriorityFunction returns vanilla's Func and never builds a
  GradedPriority, so SortPockets (which only acts when a GradedPriority pocket exists) passes through too -> exactly vanilla.
  Threshold: GetTier(equipment, minThrowables) sums weapon.Amount over every slot with a thrown usage (same slot test as the
  tiers; Amount>0 only); count < min -> tier 0 (score = vanilla - 10). Default 1 is identical to before (any counted slot has
  Amount >= 1). Build Release 0 warnings/0 errors; bin has only BetterSkirmisherSeparation.dll/.pdb; deployed.
  Reviewer check: (a) soft-dependency safety without MCM - McmSettings's base type is unresolvable then; only Settings.ReadMcm
  touches it, but any game/mod code calling GetTypes() on our assembly would hit ReflectionTypeLoadException (same exposure as
  TrainingBattles/ImmersiveAI, which run fine); (b) min-throwables counts current Amount, so the OOB (pre-battle, full ammo)
  sees full stacks; (c) MCM value persistence/json2 path; (d) in-game: MCM page shows, toggle off -> vanilla OOB, min 3 ->
  Legionaries drop out of the Thrown formation.
- Step 6 done (independent review of step 5).
  FIXED (critical): without MCM the mod would NOT load. The game's Module.AddSubModule -> CollectModuleAssemblyTypes calls
  moduleAssembly.GetTypes() with no ReflectionTypeLoadException handling -> AssemblyLoadResult.CriticalError -> submodule
  skipped + "Error while loading" box. McmSettings : AttributeGlobalSettings<> made GetTypes throw (reproduced with a net472
  probe loading the built DLL without MCMv5: RTLE "Could not load MCMv5 5.12.3.0"). The NoInlining guard only protects JIT,
  not type enumeration. Fix: McmSettings is now a static class that builds the page with MCM's fluent API
  (BaseSettingsBuilder.Create(...).SetFolderName/SetFormat("json2").CreateGroup("General", AddBool/AddInteger with ProxyRef
  to Settings' static fields, SetOrder/SetRequireRestart(false)/SetHintText, AddValueFormat("0")).BuildAsGlobal().Register()),
  inside a NoInlining method, called once from SubModule.OnBeforeInitialModuleScreenSetAsRoot only if MCMv5 is loaded; any
  failure/null builder -> Debug.Print, defaults. Same Id/folder/json2 so saved values carry over. Settings now holds volatile
  static fields (Enabled, MinThrowables clamped >=1); Read() is two field loads, no MCM call or assembly scan per distribution.
  Verified: probe GetTypes OK without MCM (only compiler <>c closures, no MCM base types); TryRegisterMcm no-op without MCM;
  with MCMv5.dll loaded Register JITs/binds against 5.12.3 and returns false (no DI outside the game) - no MissingMethod.
  Build Release 0 warnings/0 errors, deployed.
  OK as is: threshold sums Amount over thrown-usage slots (same slot test as tiers), default 1 == previous; Enabled=false ->
  vanilla Func, no GradedPriority, SortPockets builds a lazy OrderByDescending that is popped unenumerated and leaves the list
  untouched == vanilla; tier 0 score = vanilla - 10 == a non-thrower's score.
  OPEN: TrainingBattlesMod (and likely ImmersiveAI) have the same AttributeGlobalSettings-in-main-assembly pattern, so they
  would also fail to load without MCM - not touched here. In-game check still needed: MCM page appears, values persist.
