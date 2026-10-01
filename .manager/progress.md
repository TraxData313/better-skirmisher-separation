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
- Git: private repo github.com/TraxData313/better-skirmisher-separation (main). Pending: in-game test of OoB sorting + MCM page.

## Phase 3: crash on custom battle launch (2026-10-01)
7. [x] Diagnose + fix crash when pressing Launch on a custom battle (find crash report, root cause, fix, rebuild).
- Step 7 done (crash on custom battle Launch). IT WAS OUR MOD.
  Evidence: rgl_log_31632 ends at "----------Mission-AddTeam-Defender" (19:25:54, custom battle, right after EXECUTE START);
  AddTeam-Attacker never printed; no managed text in rgl/ButterLib logs, crashes\ empty (user cancelled the dump). Windows
  Application log 19:26:09, WER CLR20r3: P4 TaleWorlds.MountAndBlade, P7 0x11f2 (method token 0x060011f2), P8 IL 0x5e,
  P9 System.NullReferenceException. Token resolved against the shipped DLL = MovementOrder..ctor(MovementOrderEnum), i.e.
  `_tickTimer = new Timer(Mission.Current.CurrentTime, 0.5f)` with Mission.Current == null, called from MovementOrder's
  static field initialisers (MovementOrderNull/Charge/Retreat/Stop/Advance/FallBack). No earlier session with this mod ever
  reached a battle (all other battles today ran without BetterSkirmisherSeparation in the load order).
  Root cause: we patched in OnSubModuleLoad. Harmony 2.4 / MonoMod detours by JIT-compiling the ORIGINAL
  (RuntimeHelpers.PrepareMethod). Team.RearrangeFormationsAccordingToFilter reads MovementOrder.MovementOrderStop and
  MovementOrder is beforefieldinit, so that JIT runs MovementOrder's .cctor at load time, when Mission.Current is null -> NRE,
  swallowed by the JIT (so no warning from us), and the type is poisoned for the process: the first battle's Team/Formation
  setup gets TypeInitializationException -> crash. Not the transpiler IL, not SortPockets, not scoring, not MCM.
  Verified with a scratch net472 harness (scratchpad\harness) against the real DLLs + Bannerlord.Harmony's 0Harmony, with a
  Harmony spy prefix on MovementOrder..ctor: patching RearrangeFormationsAccordingToFilter with ANY patch (our transpiler, an
  identity transpiler, an empty prefix) fires the cctor from _PrepareMethod with Mission.Current null and afterwards
  MovementOrderStop throws TypeInitializationException; patching only OrderController.TransferUnitWithPriorityFunction
  does not.
  Fix: SubModule patches in OnBeforeMissionBehaviorInitialize (first mission only, skipped while Mission.Current is null;
  Mission.Initialize sets Current before AfterStart calls this hook, and teams/OOB come later), so the cctor runs with a
  live mission exactly like vanilla's first touch. Harness re-run: nothing fires at OnSubModuleLoad or with Current null; at
  the hook the cctor runs with Current set, all 6 statics build, MovementOrderStop OK, 1 transpiler on each target.
  Safety net: ThrownPriority.GetPriorityFunction / GradedPriority.Score / SortPockets catch everything, fall back to the
  vanilla func / vanilla score / untouched list, and log once (SubModule.LogOnce -> rgl log). Vanilla's own exceptions
  (the vanilla priority func) are not swallowed. Build Release 0 warnings/0 errors, deployed.
  Confidence: high (WER frame + reproduced mechanism + fix verified in harness); not yet confirmed in-game.
  User test: launch a custom battle (and a campaign battle) -> no crash; in the Order of Battle tick Thrown on one infantry
  formation and check skirmishers vs Legionaries; second battle in the same session also fine.
## Phase 4: publishing prep (2026-10-01) — user is testing step 7 in-game meanwhile
User's spec: GitHub README is the main page — few lines: Bannerlord mod; separates dedicated skirmishers
from heavy troops with 1-2 throwables (Legionaries, Menavliatons); how in few words; install = download from
GitHub Release or Steam Workshop (link). Steam description similar, ending "or download it from GitHub here" -> README.
Fully free/open license like his other mods, no wordy legal text; one line: to thank me, open my GitHub profile
and read my top pinned (literally "read my top pinned"). Cover image = two user screenshots BEFORE/AFTER with labels.
Mod zip goes on a GitHub Release, not committed. NOTE: repo is private now -> must be made public for downloads (ask user).
8. [x] Prep: README, LICENSE, Steam description text, release packaging script (zip), cover-image script
       (waits for screenshots), Steam workshop uploader config mirroring TrainingBattlesMod. No publishing.
9. [ ] When screenshots arrive: build cover. Then (user approval) make repo public, cut GitHub release, Steam upload.
- Step 8 done (publishing prep, nothing published). README.md = short main page (cover docs/cover.png placeholder,
  install via GitHub Releases latest / Steam STEAM_WORKSHOP_URL placeholder, Harmony required, MCM optional, Unlicense
  line, "read my top pinned" thank-you, <details> "How it works" -> docs/TECHNICAL.md which holds the old tiers/settings/
  how-it-works/limits/build text + release notes). LICENSE = Unlicense (copied from TrainingBattlesMod).
  tools/: STEAM-DESCRIPTION.bbcode (ends "Not on Steam? Download it from GitHub"), package.ps1 (reads version from
  SubModule.xml, builds Release with DeployToGame=false, dist\BetterSkirmisherSeparation + zip with forward-slash entries,
  refuses to overwrite an existing zip without -Force; zip verified = BetterSkirmisherSeparation/SubModule.xml +
  bin/Win64_Shipping_Client/BetterSkirmisherSeparation.dll, no pdb, left in dist), WorkshopCreate.xml (dist folder,
  image docs\cover.jpg, tags Utility/Native/Singleplayer/v1.4.8, Private), WorkshopUpdate.xml (ItemId ITEM_ID placeholder),
  WORKSHOP-UPLOAD.md, make_cover.py (Pillow 12.3 present; side-by-side for landscape / stacked for portrait, centre-crop to
  16:9 by default, --focus/--no-crop/--layout/--labels/--no-title; writes docs\cover.png for README + docs\cover.jpg <1MB
  for Steam; tested on dummy images in scratchpad, both layouts, jpg 951 KB from noise). preview_thumbnail.html not
  mirrored (make_cover.py replaces it). steam_appid.txt (261550) created locally, gitignored like TrainingBattles.
  Commit eb1ac04 pushed. Next: step 9 (screenshots -> docs\before.png/after.png -> make_cover; user approval for public
  repo, GitHub release with the dist zip, Workshop upload).
- Step 9a done (cover). Screenshots (screenshots\, 1920x1200, gitignored, not committed): pairs are the same desert custom
  battle, formation 1 = infantry (50), formation 2 = Thrown filter (49). BEFORE/AFTER 1 = top-down deployment view, the
  two blocks look alike (unreadable as a thumbnail). BEFORE/AFTER 2 = ground view behind the player: BEFORE 2 right block
  (Thrown) = silver-lamellar heavies with red-pennoned spears (Legionaries/Menavliatons) + a few peltasts, left = kite-shield
  infantry; AFTER 2 the heavies are in the left (infantry) block and the right block is javelin-bundle skirmishers.
  Composition: pair 2 only, side by side, both cropped to the Thrown block (8:9 panels -> 16:9 cover), BEFORE/AFTER labels
  over the sky, captions "Heavy spearmen with 1-2 javelins" / "Real javelin skirmishers" on a bottom fade (hides HUD).
  Command: python tools\make_cover.py "screenshots\BEFORE 2.jpg" "screenshots\AFTER 2.jpg" --crop 1100 250 1920 1065
  --layout side --no-title --captions "Heavy spearmen with 1-2 javelins" "Real javelin skirmishers"
  make_cover.py: new --crop, --captions; JPG is now the default output (--png optional) because the PNG was 2.7 MB.
  Files: docs\cover.jpg 1920x1078 510 KB (README now uses it + Steam preview). README/TECHNICAL/WORKSHOP-UPLOAD updated.
  Commit 84e23a8 pushed. Next: user approval -> public repo, GitHub release, Workshop upload.
- WAITING on user's green light after more in-game tests (user approved making repo public 2026-10-01). On green light: apply any polishes, package.ps1 -Force, gh repo edit --visibility public, gh release create v1.0.0 with dist zip, then Steam upload per tools/WORKSHOP-UPLOAD.md (user does SteamCMD login), then fill STEAM_WORKSHOP_URL in README.
- Step 9b done (cover redo; old cover was wrong: its AFTER panel still showed Legionaries). User replaced screenshots
  (screenshots\, 3440x1440, gitignored): "A1 Before"/"A2 After" = top-down, no HUD; left block = kite-shield infantry,
  right block = Throwing Weapons formation. A1 right = red-pennoned Legionaries + silver-scale Menavliatons (+ a few
  bundle peltasts); A2 right = all javelin-bundle skirmishers with small round shields, the pennoned heavies moved left.
  "B1 Before"/"B2 After" (deployment HUD, formation 2 = 26) look REVERSED: B1 formation 2 = skirmishers, B2 formation 2
  = Legionaries/Menavliatons -> pair B not used (ask user whether the B files are swapped).
  Cover: pair A only, stacked (BEFORE top, AFTER bottom), both cropped to the throwing block, labels + captions in
  top-right corner tags (sand, no troops covered). make_cover.py: new --label-pos band|tl|tr; stack via --layout stack
  --no-crop. Command: python tools\make_cover.py "screenshots\A1 Before.jpg" "screenshots\A2 After.jpg" --crop 1960 330
  3420 1290 --layout stack --no-crop --label-pos tr --width 1460 --no-title --captions "Legionaries / Menavliatons with
  1-2 pila" "Real javelin skirmishers". docs\cover.jpg 1460x1923 (~3:4 portrait) 773 KB; overwrote the old one (no other
  cover files in docs). Steam square thumbnails will centre-crop it.
- Step 9c (in progress): user marked a screenshot by hand (screenshots/crossed/_toni_marked_example.webp): red X = soldier in the wrong formation, tick = right one. Wants a trial: one picture with every soldier marked (red X, GREEN tick) saved in screenshots/crossed. If approved: mark all 4 shots and rebuild the comparison cover from them.
- Step 9c trial done: source of Toni's example = "A1 Before.jpg" (example = crop x134..3344 y296..1301 at 1/1.605; screenshots
  are 3440x1440). Rule (matches his marks): javelin bundle on the back = skirmisher, armored or not. Left (infantry, kite
  shields) block: bundle carriers X, everyone else tick. Right (Throwing Weapons) block: Legionaries (pennoned spears,
  lamellar/pteruges) + silver-scale Menavliatons X; bundle carriers (purple quilted/turban, brown vests, hooded) tick.
  Counts: left 43 = 11 X + 32 tick; right 26 = 12 X + 14 tick (69 total). Files: screenshots\crossed\A1 Before.marks.json
  (ids L*/B*/R*, size by depth 46/52/58), output screenshots\crossed\A1 Before marked.jpg (3440x1440, q92), both gitignored.
  Tool: python tools\mark_soldiers.py IMAGE MARKS.json [-o OUT] [--scale] (commit 70c54e4). Next: user approval -> mark
  A2/B1/B2 the same way, rebuild cover.
- 9c trial approved by Toni. Next: mark A2 After, B1 Before, B2 After the same way into screenshots/crossed. Toni's own hand-marked one is in 'screenshots/crossed toni manual'.
- 9c all 4 marked (screenshots\crossed\<name> marked.jpg 3440x1440 q92 + <name>.marks.json, same tool/sizes 46/52/58 by y,
  gitignored). Toni's manual A1 == our A1: all 69 marks match (same soldiers, same X/tick), so A1 unchanged.
  A2 After: left = infantry, right = Throwing; left 43 = 0 X + 43 tick, right 26 = 0 X + 26 tick (all bundle skirmishers).
  B1 Before: left (formation 1, 43) = infantry, right (formation 2, 26) = Throwing; 0 X: left 43 tick, right 26 tick.
  B2 After: same blocks; left 43 = 11 X (bundle carriers) + 32 tick, right 26 = 12 X (Legionaries/Menavliatons) + 14 tick.
  VERDICT pair B: names swapped. B1 content = A2 (after state, same slots), B2 content = A1 (before state, same slots).
  Files not renamed. B marks were seeded by a homography from A2->B1 / A1->B2 then checked/fixed by eye; one swap fixed in
  B2 (bundle carrier vs bareheaded man in one column, ids B10/B16). Doubts: B1/B2 a few marks sit on the HUD labels
  ("1/43", "2/26") over hidden soldiers (B1 L12, R12; B2 B14a, B14b, R6, R10); B2 R5/R10 are mostly hidden, ticked as in A1.
- AI-authorship line added to README + Steam desc (Toni's wish: tell people upfront). Pair B names are swapped (B2 = before state). Remaining: (9d) comparison image from marked A1 (top) / A2 (bottom) -> docs/cover.jpg; (9e) Steam thumbnail in the style of ../TrainingBattlesMod/Screenshots/preview_thumbnail* ('shows the result in 3 seconds'); then green light -> release.
- Step 9d done (comparison cover from the marked shots). docs\cover.jpg 1920x1374, 874 KB (q92): stacked, BEFORE
  (crossed\A1 Before marked) on top, AFTER (crossed\A2 After marked) below, crop x100..3380 y130..1300 keeps both blocks
  (marks ~30 px, clearly visible even at 640 wide). Labels as top-right corner tags over empty sand (tag-scale 0.6), captions
  "23 of 69 in the wrong formation" / "All 69 in the right place" (verified from the JSONs: A1 23 X of 69, A2 0 X of 69).
  No block labels (reads fine without). make_cover.py: new --tag-scale; command in its docstring + WORKSHOP-UPLOAD.md.
  README alt text updated. Next: (9e) Steam square thumbnail; then green light -> release.
- Step 9e done (Steam/mod thumbnail). docs\thumbnail.jpg 1024x1024, 318 KB, same family as TrainingBattles'
  preview_thumbnail (gold frame, Palatino small caps over a dark fade, which was an HTML + render): BEFORE (red tag) |
  AFTER (green tag) side by side, each the Throwing Weapons block of the unmarked A1/A2 with marks redrawn 2.0x from the
  JSONs, gold split line; title "Better Skirmisher / Separation" on two lines, tagline "Skirmishers where they belong."
  Checked at full size and 256 px: title, tags and red-vs-green all read. Build: python tools\make_thumbnail.py
  (renders tools\preview_thumbnail.html with headless Edge; panels + 1024 PNG in screenshots\thumb\, gitignored).
  WorkshopCreate.xml <Image> -> docs\thumbnail.jpg (WorkshopUpdate has no image, like TrainingBattles);
  WORKSHOP-UPLOAD.md: thumbnail step + add docs\cover.jpg as an extra screenshot on the item page. cover.jpg unchanged.
  Next: green light -> release.
- Screenshots reorganized (local, gitignored): top = thumbnail.jpg + 4 '* marked.jpg'; subfolders originals/, marks/ (json), comparison/, 'thumbnail build'/, 'toni manual'/. Tools paths updated; make_thumbnail.py rerun gives byte-identical docs/thumbnail.jpg.
- 9f (in progress): Toni wants a 2nd thumbnail that shows the Order of Battle formation card with the Throwing/skirmisher filter icon ticked (formation 2, 26/69; his circled sketch: screenshots/toni manual/'thumbnail idea - thrower icon circled.webp', the card is from the left UI of the B1 shot). Message: 'with skirmisher ticked, Before = Legionaries (red X), After = all javelin throwers'. Keep the current thumbnail too.
- Step 9f done (thumbnail v2, user picks). docs\thumbnail_v2.jpg 1024x1024, 269 KB (copy: screenshots\thumbnail_v2.jpg):
  top = formation-2 Order of Battle card (26 / 69, cut from originals\B1 Before x14..426 y396..700; identical in B2; only the
  B shots have the UI) with the sand masked out, its Throwing icon (~32 px at 397,545) ringed in glowing gold + a leader line
  to a magnifier circle and the label "Throwing ✓"; below = BEFORE | AFTER (A1/A2 Throwing block, wider crops, marks 2.3x,
  tags top-right of each panel over empty sand); title one line "Better Skirmisher Separation", no tagline. Checked at full
  size and 256 px: card, ringed icon, magnifier, red X vs green ticks all read. Build: python tools\make_thumbnail.py
  --variant v2 (template tools\preview_thumbnail_v2.html); v1 rebuild byte-identical. WorkshopCreate.xml still uses
  docs\thumbnail.jpg; WORKSHOP-UPLOAD.md lists both options. Commits e919e40 + doc note.
- Comparison rebuilt without captions (Toni: no '69' anywhere — troop size 70 minus the general made it 69 by accident; avoid that number in all public images/text). 9g next: v2 card shows '26 / 69' -> remove the count; tagline -> 'Legionaries are not skirmishers anymore.'
- Step 9g done (f5f8205). v2 card: the slider's '26 / <total>' label is painted out in make_thumbnail.py (erase_count:
  clones the plain card background from the strip to its right, stops above the slider handle and bar) - checked at 6x
  zoom and 256 px, no smudge; top-left '26' kept (it is the formation's own count, reads fine alone). No other total
  visible in either thumbnail. Tagline -> 'Legionaries are not skirmishers anymore.' on v1; v2 now has it under the title
  (36 px italic, panels 430 -> 390 px, crop boxes trimmed to match) - small but legible at 256 px. No other doc quoted
  the old tagline. Copies in screenshots\thumbnail.jpg / thumbnail_v2.jpg.
- 9g done (v2 count erased, tagline 'Legionaries are not skirmishers anymore.'). 9h: Toni prefers v1 layout; wants v3 = v1 + the ringed Throwing icon (small icon from v2's card, with gold ring) placed top-center over the BEFORE|AFTER divider. (Sketch only in chat, not on disk.)
- Step 9h done (b52bc7e). Thumbnail v3: docs\thumbnail_v3.jpg 1024x1024, 321 KB (copy screenshots\thumbnail_v3.jpg) = v1 layout +
  the Throwing filter icon (keyed off the B1 card onto its dark brown) on a 150 px disc with a glowing gold ring, top
  centre on the split line between the tags. No label (reads clean without). Checked full size + 256 px; no total shown.
  Build: python tools\make_thumbnail.py --variant v3 (template tools\preview_thumbnail_v3.html). WORKSHOP-UPLOAD.md
  lists option 3; WorkshopCreate.xml unchanged (option 1). v1/v2 images unchanged.
- GO LIVE 2026-10-01: Toni chose thumbnail v3 (WorkshopCreate preview). Repo made public, release v1.0.0 with dist zip. Remaining: Toni uploads to Steam (tools/WORKSHOP-UPLOAD.md), then fill STEAM_WORKSHOP_URL in README + item ID in WorkshopUpdate.xml.

## Phase 5: Steam release (2026-10-01) — Toni wants us to do it all ourselves via CLI
10. [x] Learn the upload flow from ../TrainingBattlesMod and ../ImmersiveAI (workshop docs/tools), upload as Private, report item ID + what CLI can't do.
11. [ ] Finish item page (description, comparison screenshot first, Harmony required item, public) + README link + WorkshopUpdate item ID.
- Step 10 done (e986834). Flow learned from TrainingBattles/ImmersiveAI = Bannerlord's own TaleWorlds.MountAndBlade.SteamWorkshop.exe
  riding the logged-in Steam client (no SteamCMD, no credentials). package.ps1 -Force (v1.0.0, dist = SubModule.xml + 17 KB dll),
  then the exe with tools\WorkshopCreate.xml, run from scratchpad\upload (it drops steam_appid.txt + steam_workshop_uploader.txt in
  the cwd). Output: "Item created. Item ID is 3811452468" + "Uploading done!", then the usual press-any-key crash (exit 82, ignore).
  Item 3811452468, Private: https://steamcommunity.com/sharedfiles/filedetails/?id=3811452468 . ID now in WorkshopUpdate.xml;
  WORKSHOP-UPLOAD.md has the ID + new quirks. No Steam Guard / legal-agreement prompt (account already has Workshop items).
  Uploader capabilities (strings in the exe): task fields ModuleFolder, ItemDescription, Tags, Image, ChangeNotes, Visibility only
  (SetItemTitle/Description/Tags/Content/Preview/Visibility). No AddItemPreviewFile (extra screenshots), no AddDependency
  (required items). Current page description = the one-paragraph ItemDescription from WorkshopCreate.xml (plain text).
  Step 11 plan: (a) description + Public + change notes CAN go via the uploader: a one-off task file = GetItem 3811452468 +
  UpdateItem with ModuleFolder (same dist, harmless re-upload), ItemDescription = STEAM-DESCRIPTION.bbcode (1528 chars, limit 8000,
  BBCode renders) with newlines escaped as &#10; and quotes/&/< escaped, ChangeNotes "v1.0.0 - first release", Visibility Public
  (do Public LAST, after the page is complete). (b) cover.jpg as extra screenshot and (c) Harmony 2859188632 as required item are
  item-page only: Owner Controls "Add/edit images & videos" and "Add/Remove Required Items" - via claude-in-chrome with Toni
  logged in, or Toni by hand. Then README STEAM_WORKSHOP_URL -> the page URL.
