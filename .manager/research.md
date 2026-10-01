# Research: Thrown-weapons formation preference (Bannerlord v1.4.8)

Decompiled source root used: `reference\game-decompiled` (identical to `game-decompiled-1.4.8` for
TroopFilteringUtilities.cs, Team.cs, FormationPocket.cs). Installed game: `v1.4.8` (Native SubModule.xml).
Abbrev: `GD = C:\Users\Trax\Documents\BannerlordMods\reference\game-decompiled`.

---

## 1. Where the "Thrown Weapons" preference is applied

### 1.1 The filter enum and mask
- `GD\TaleWorlds.Core\TaleWorlds.Core\FormationFilterType.cs` — `enum FormationFilterType { Unset, Shield, Spear, Thrown, Heavy, HighTier, LowTier, NumberOfFilterTypes }`
  (UI text: `Thrown => "{=Ea3K1PVR}Thrown Weapons"` in `OrderOfBattleFormationExtensions.GetFilterName`).
- `GD\TaleWorlds.Core\TaleWorlds.Core\TroopTraitsMask.cs` — `[Flags] enum TroopTraitsMask : ushort { None=0, Melee=1, Ranged=2, Mount=4, Armor=8, Thrown=0x10, Spear=0x20, Shield=0x40, LowTier=0x80, HighTier=0x100, All=0x1FF }`

### 1.2 The scoring — `TaleWorlds.MountAndBlade.TroopFilteringUtilities` (static, TaleWorlds.MountAndBlade.dll)
File: `GD\TaleWorlds.MountAndBlade\TaleWorlds.MountAndBlade\TroopFilteringUtilities.cs`
```csharp
public static TroopTraitsMask GetFilter(params FormationClass[] formationClasses)  // Infantry->Melee, Ranged->Ranged, Cavalry->Melee|Mount, HA->Ranged|Mount
public static TroopTraitsMask GetFilter(params FormationFilterType[] filterTypes)  // Thrown -> TroopTraitsMask.Thrown, etc.

public static void GetPriorityFunction(TroopTraitsMask filter, out Func<Agent, int> priorityFunc)
{
    priorityFunc = (Agent agent) => (agent == null || agent.Character == null)
        ? GetMaxPriority(filter)
        : GetTroopPriority(agent.GetTraitsMask(), agent.Character.GetBattleTier(), filter);
}
public static void GetPriorityFunction(TroopTraitsMask filter, out Func<IAgentOriginBase, int> priorityFunc) // same, origin-based; NO vanilla caller

public static int GetTroopPriority(TroopTraitsMask troopMask, int battleTier, TroopTraitsMask filter)
{
    int num = 1;
    if ((filter & HighTier) != 0) num += battleTier;
    if ((filter & LowTier) != 0)  num += 7 - battleTier;
    TroopTraitsMask m = filter & troopMask;
    if ((m & Shield) != 0) num += 10;
    if ((m & Spear)  != 0) num += 10;
    if ((m & Thrown) != 0) num += 10;   // <-- the whole thrown preference: a flat boolean +10
    if ((m & Armor)  != 0) num += 10;
    if ((m & Melee) != 0 || (m & Ranged) != 0) num += 100;
    if ((m & Mount) != 0) num += 1000;
    return num;
}
public static int GetMaxPriority(TroopTraitsMask filter) // 1 + 7(HighTier) + 7(LowTier) + 10 per Shield/Spear/Thrown/Armor + 100(Melee|Ranged) + 1000(Mount)
```
**Root cause:** thrown is a boolean bit worth +10, so a Legionary with 2 pila scores exactly the same as a
Battanian Skirmisher with two javelin stacks.

### 1.3 Agent traits — `Agent.GetTraitsMask()` (`GD\...\TaleWorlds.MountAndBlade\Agent.cs` ~l.2545)
```csharp
public bool IsRangedCached => Equipment.ContainsNonConsumableRangedWeaponWithAmmo();   // l.891
public bool HasThrownCached => Equipment.ContainsThrownWeapon();                       // l.911
public TroopTraitsMask GetTraitsMask() {
    ... HasMount -> Mount; IsRangedCached ? Ranged : Melee; HasShieldCached -> Shield; HasSpearCached -> Spear;
    if (HasThrownCached) mask |= TroopTraitsMask.Thrown;
    if (MissionGameModels.Current.AgentStatCalculateModel.HasHeavyArmor(this)) mask |= Armor; ...
}
```
`MissionEquipment.GatherInformation` → `MissionWeapon.GatherInformationFromWeapon` (`MissionWeapon.cs` l.479)
iterates **all usages** of every weapon slot (0..4):
```csharp
foreach (WeaponComponentData weapon in _weapons) {
    ...
    if (weapon.IsRangedWeapon) { weaponHasThrown = weapon.IsConsumable; weaponHasNonConsumableRanged = !weaponHasThrown; ... }
}
```
So any item with a `RangedWeapon|Consumable` usage — including the pilum's *secondary* throw usage — sets the
Thrown bit. (Throwing troops without bows stay `Melee`, i.e. Infantry/Cavalry filter class.)

Origin-level equivalent (NOT used by the OOB path, only for spawn-side/naval code):
`GD\TaleWorlds.Core\TaleWorlds.Core\AgentOriginUtilities.cs` `GetDefaultTroopTraits(BasicCharacterObject troop, out bool hasThrownWeapon, ...)`
— checks only `FirstBattleEquipment[i].Item.PrimaryWeapon.WeaponClass` ∈ {ThrowingAxe, ThrowingKnife, Javelin}
(so origin-level traits do NOT count a pilum as thrown — it counts as Spear). Used by PartyAgentOrigin,
PartyGroupAgentOrigin, SimpleAgentOrigin, BasicBattleAgentOrigin, CustomBattleAgentOrigin.

### 1.4 The distribution algorithm — `Team.RearrangeFormationsAccordingToFilter`
File: `GD\TaleWorlds.MountAndBlade\TaleWorlds.MountAndBlade\Team.cs` l.~476. Signature:
```csharp
public void RearrangeFormationsAccordingToFilter(
    List<(Formation formation, int troopCount, TroopTraitsMask troopFilter, List<Agent> excludedAgents)> MassTransferData)
```
Core (abridged):
```csharp
for (int j = 0; j < MassTransferData.Count; j++) {
    TroopTraitsMask item = MassTransferData[j].troopFilter;
    TroopFilteringUtilities.GetPriorityFunction(item, out Func<Agent, int> priorityFunc);   // <-- patch target call site
    int maxPriority = TroopFilteringUtilities.GetMaxPriority(item);
    list2.Add(new FormationPocket(priorityFunc, maxPriority, MassTransferData[j].troopCount, j));
}
list2.RemoveAll(p => p.TroopCount <= 0);
list2 = list2.OrderBy(p => p.TroopCount).ToList();
list2 = list2.OrderByDescending(p => p.ScoreToSeek).ToList();
list3 = all units of all involved formations (DetachedUnits + Arrangement units) except excludedAgents;
int scoreToSeek = list2[0].ScoreToSeek;
while (num2 > 0) {                         // num2 = agents left to place
    for (k...) { Agent agent = list3[k];
        for (l...) { FormationPocket p = list2[l];
            int num3 = p.PriorityFunction(agent);
            if (scoreToSeek <= p.ScoreToSeek && num3 >= scoreToSeek) { assign agent to p; if (p.IsFormationPocketFilled()) list2.RemoveAt(l); ...; break; }
            if (num3 > p.BestScoreSoFar) p.SetBestScoreSoFar(num3);
        } }
    if (list2.Count == 0) break;
    foreach p: p.UpdateScoreToSeek();      // ScoreToSeek = BestScoreSoFar (best UNPLACED score seen); BestScoreSoFar = 0
    list2.OrderByDescending(p => p.ScoreToSeek);   // (vanilla bug: result discarded, list not re-sorted)
    scoreToSeek = list2[0].ScoreToSeek;
}
// then agent.Formation = target for every assignment; TriggerOnFormationsChanged; OnMassUnitTransferEnd ...
```
`FormationPocket` (`FormationPocket.cs`): `ScoreToSeek` starts at `maxValue`; `UpdateScoreToSeek(){ ScoreToSeek = BestScoreSoFar; BestScoreSoFar = 0; }`.

**So it is a descending-tier fill, not a boolean filter:** pass 1 takes only agents scoring exactly the
pocket's max; each later pass drops ScoreToSeek to the best remaining score. Graded scores therefore
work naturally — every distinct score value becomes its own tier, filled best-first until the
pocket's troop count (from the formation weight %) is met.

### 1.5 Who calls it (all Order-of-Battle, player team only)
- `OrderController.RearrangeFormationsAccordingToFilters(Team team, List<...> data)` → `team.RearrangeFormationsAccordingToFilter(data)` (`OrderController.cs` ~l.930).
- `TaleWorlds.MountAndBlade.ViewModelCollection.OrderOfBattle.OrderOfBattleVM`
  (`GD\TaleWorlds.MountAndBlade.ViewModelCollection\...OrderOfBattle\OrderOfBattleVM.cs`):
  - `Initialize(...)` → `LoadConfiguration()` then `DistributeAllTroops()` (mission start; loads saved filters from `OrderOfBattleCampaignBehavior`).
  - `DistributeAllTroops()`, `DistributeTroops(OrderOfBattleFormationClassVM)` (weight slider / class change), `OnFilterUseToggled(OrderOfBattleFormationItemVM)` (filter checkbox), `TransferAllAvailableTroopsToFormation(...)`.
  - Filters built in `GetMassTransferDataForFormation` / `GetMassTransferDataForFormationClass`:
    ```csharp
    TroopTraitsMask filter = TroopFilteringUtilities.GetFilter(<formation classes>);
    filter |= TroopFilteringUtilities.GetFilter((from f in item.FilterItems where f.IsActive select f.FilterType).ToArray());
    ```
    e.g. Infantry + "Thrown" → `Melee|Thrown` (max 111); plain Infantry → `Melee` (max 101).
  - `GetTroopCountWithFilter(DeploymentFormationClass, FormationFilterType)` (private, cosmetic count shown in the filter UI):
    `case FormationFilterType.Thrown: num += formation.GetCountOfUnitsWithCondition((Agent a) => a.HasThrownCached);`
- `OrderController.TransferUnitWithPriorityFunction(...)` (`OrderController.cs` l.866) also uses `GetPriorityFunction`, but its only vanilla caller (OrderOfBattleVM l.1749) passes `hasThrown: false` — irrelevant.

### 1.6 Not affected by filters (FYI)
- Reinforcements: `MissionReinforcementsHelper.GetReinforcementAssignments` (via `BattleSpawnModel.GetReinforcementAssignments`) assigns by `Mission.GetAgentTroopClass` + formation class ratios only — filters are ignored.
- In-battle `MissionOrderVM.FormationConfiguration.Filters` / `OrderTroopItemVM.UpdateFilterData` only display filters.
- NavalDLC `NavalShipAgents` (l.195–231) calls `TroopFilteringUtilities.GetTroopPriority` directly for ship assignment (would only be affected by a `GetTroopPriority` patch — another reason not to patch that).
- No reference mod (RBM, RBMAI, RTSCamera, RTSCamera.CommandSystem, PartyAI) touches TroopFilteringUtilities / RearrangeFormationsAccordingToFilter / HasThrownCached → no known conflicts.

---

## 2. What counts as "has throwing weapons"; pila vs javelins

### Data model
- `WeaponComponentData` (`GD\TaleWorlds.Core\TaleWorlds.Core\WeaponComponentData.cs`): `WeaponClass WeaponClass`, `WeaponFlags`, `bool IsRangedWeapon => WeaponFlags.HasAllFlags(RangedWeapon)`, `bool IsConsumable => WeaponFlags.HasAllFlags(Consumable)`, `short MaxDataValue` (from `ammo_limit` / `stack_amount` / `hit_points`).
- `ItemObject.PrimaryWeapon => WeaponComponent?.PrimaryWeapon` = `Weapons[0]`; `ItemObject.Weapons` = all usages.
- `WeaponClass` thrown values: `ThrowingAxe(21), ThrowingKnife(22), Javelin(23)`; also `Stone(19)`, `Boulder(20)` (siege / special). There is **no Pila class** — a pilum's throw usage is `WeaponClass.Javelin`.
- Runtime: `MissionWeapon` (`GD\TaleWorlds.MountAndBlade\TaleWorlds.MountAndBlade\MissionWeapon.cs`): `Item`, `IsEmpty`, `short Amount` (current), `short ModifiedMaxAmount`, `CurrentUsageItem`. Ctor (l.138): `_modifiedMaxDataValue` = `MaxDataValue` of the **last** usage that is consumable/ranged/has-HP (item modifier applied via `GetModifiedStackCount`); `_dataValue = _modifiedMaxDataValue`. So for a pilum `Amount == 1`, for a javelin stack `Amount == stack size`.
- Agent slots: `agent.Equipment[EquipmentIndex]` for `EquipmentIndex.WeaponItemBeginSlot(0) .. < EquipmentIndex.NumAllWeaponSlots(5)` (0–3 + ExtraWeaponSlot 4).

### Crafted throwing items (stack decided at generation)
`Crafting.GenerateCraftedItem` (`Crafting.cs` l.570) adds one usage per template `WeaponDescription` whose pieces match; **first matching = primary, later ones `isAlternative = true`**. `CraftingStats.SetWeaponData` (l.148):
```csharp
if (WeaponClass is Javelin/ThrowingAxe/ThrowingKnife) { short num = (short)(isAlternative ? 1 : bladeData.StackAmount); maxDataValue = num; ... }
```
- Template `Javelin` (`item_type="Thrown"`): descriptions `Javelin` (primary, thrown) + `OneHandedPolearm_JavelinAlternative` → stack = blade `stack_amount` (4–5).
- Template `TwoHandedPolearm` (`item_type="Polearm"`): descriptions `OneHandedPolearm, TwoHandedPolearm, TwoHandedPolearm_Couchable, TwoHandedPolearm_Bracing, TwoHandedPolearm_Thrown` → the thrown usage (`TwoHandedPolearm_Thrown`, weapon_class `Javelin`, flags RangedWeapon|Consumable) is an **alternative ⇒ MaxDataValue forced to 1**, even though the pilum blade `spear_blade_38` says `stack_amount="2"`.
- Templates ThrowingAxe/ThrowingKnife: primary thrown, stack from blade (3, some 5).

### Game data (SandBoxCore\ModuleData\items\weapons.xml + spnpccharacters.xml, first equipment roster)
| Item | Template / ItemType | Thrown usage | Amount per item |
|---|---|---|---|
| `imperial_throwing_spear_1_t4`, `_t4_2` "Pilum" | TwoHandedPolearm / Polearm | alternative | **1** |
| `eastern_throwing_spear_1_t3`, `_2_t4` (Khuzait) | TwoHandedPolearm / Polearm | alternative | **1** |
| `western_javelin_1_t2` Simple Javelin | Javelin / Thrown | primary | 4 |
| `western_javelin_3_t4`, `generic_javelin_1_t3`, `northern_javelin_2_t3/3_t4`, `eastern_javelin_2_t3/3_t4`, `nord_spear_javelin_1_t3` | Javelin / Thrown | primary | 5 |
| `northern_javelin_1_t2`, `eastern_javelin_1_t2` | Javelin / Thrown | primary | 4 |
| throwing axes (`northern_throwing_axe_1_t1`, `western_throwing_axe_1_t1`, `highland_*`, `woodland_*`, ...) | ThrowingAxe / Thrown | primary | 3 (nord t5: 5) |
| throwing knives/daggers | ThrowingKnife / Thrown | primary | 3 |
| `sling_*` | ItemType Thrown, but usage is non-consumable ranged (Sling) | — | → Ranged, not Thrown |

Troops (slot items): `imperial_legionary` Infantry = 2× Pilum (+sword, kite shield); `imperial_elite_menavliaton` = 1× Pilum (+polearm, sword) — plain `imperial_menavliaton` has no throwables; `imperial_veteran_infantryman` 1× Pilum; `khuzait_spear_infantry`/`khuzait_darkhan` 1× throwing spear; `battanian_skirmisher` 2× western_javelin_1_t2; `battanian_veteran_skirmisher` 2× generic_javelin_1_t3; `battanian_wildling` 2× western_javelin_3_t4; `sturgian_veteran_warrior` 2× throwing axe; `sturgian_brigand` 2× javelin; `battanian_falxman (veteran)` 2× throwing axe; many t2–t4 infantry/cavalry 1 stack (aserai_infantry, sturgian_spearman, battanian_woodrunner, imperial_trained_infantryman, ...).

### How to count (per agent, at deployment)
```csharp
int stacks = 0, singles = 0, total = 0;
for (var i = EquipmentIndex.WeaponItemBeginSlot; i < EquipmentIndex.NumAllWeaponSlots; i++) {
    MissionWeapon w = agent.Equipment[i];
    if (w.IsEmpty || w.Item?.Weapons == null) continue;
    int throwUsage = -1;
    for (int u = 0; u < w.Item.Weapons.Count; u++) {
        var d = w.Item.Weapons[u];
        if (d.IsRangedWeapon && d.IsConsumable) { throwUsage = u; break; }   // same definition vanilla uses for Thrown
    }
    if (throwUsage < 0) continue;
    if (throwUsage == 0) stacks++;   // primary usage is thrown => a real stack (javelins/axes/knives)
    else singles++;                  // thrown only as alternative usage => pilum / heavy throwing spear (amount 1)
    total += w.Amount;               // current ammo; = ModifiedMaxAmount before battle
}
```
(Optionally treat `throwUsage == 0 && w.ModifiedMaxAmount <= 1` as a single too, to catch modded one-shot items.
Equivalent item-level check: `w.Item.ItemType == ItemObject.ItemTypeEnum.Thrown` ⇔ stack, but the usage check
excludes slings correctly; use the usage check.)

---

## 3. Patch point and design

### Recommendation: Transpiler on `Team.RearrangeFormationsAccordingToFilter` swapping one call
- Target: `AccessTools.Method(typeof(Team), nameof(Team.RearrangeFormationsAccordingToFilter))` (public instance, single overload).
- In its IL, replace the `call` whose operand is
  `AccessTools.Method(typeof(TroopFilteringUtilities), "GetPriorityFunction", new[] { typeof(TroopTraitsMask), typeof(Func<Agent,int>).MakeByRefType() })`
  with `call ThrownPriority.GetPriorityFunction(TroopTraitsMask, out Func<Agent,int>)` (identical static signature, so stack is unchanged). If the call is not found, log and leave IL untouched (fail-safe = vanilla).
- Why here and not a postfix on `TroopFilteringUtilities.GetPriorityFunction`: that method is tiny (~26 bytes IL: new closure + ldftn + newobj + stind) and a JIT-inlining candidate, so a Harmony patch on it may silently never run. The caller is large (never inlined) and is the only vanilla consumer of the agent-overload that matters. Also avoids touching `GetTroopPriority` (used by NavalDLC ship assignment) and keeps every other filter (Shield/Spear/Heavy/Tier) bit-for-bit vanilla.
- Scope = Order of Battle screen only (mission-start distribution, weight sliders, filter toggles, class changes). Player team only. No AI / reinforcement / save-data side effects.

Replacement method:
```csharp
public static void GetPriorityFunction(TroopTraitsMask filter, out Func<Agent, int> priorityFunc)
{
    TroopFilteringUtilities.GetPriorityFunction(filter, out Func<Agent, int> vanilla);
    if ((filter & TroopTraitsMask.Thrown) == 0) { priorityFunc = vanilla; return; }
    var cache = new Dictionary<Agent, int>();                    // one rearrange call; func is hit many times per agent
    priorityFunc = agent => {
        int score = vanilla(agent);
        if (agent == null || agent.Character == null || !agent.HasThrownCached) return score; // vanilla gave +0 for thrown
        if (!cache.TryGetValue(agent, out int tier)) cache[agent] = tier = ThrownTier(agent);   // 0..10
        return score - 10 + tier;                                 // replace vanilla's flat +10 with the graded tier
    };
}
static int ThrownTier(Agent a) // from the counting loop in §2
{   // stacks>=2 -> 10 (== vanilla max, so pass 1 takes only true skirmishers)
    // stacks==1 -> 7
    // singles>=1 (pila / throwing spears only) -> 3
    // else -> 0
}
```
Notes on the numbers:
- Must stay in 0..10 so `GetMaxPriority` (unchanged, +10 for Thrown) is reached only by the top tier, and so thrown never outweighs the +100 class / +1000 mount terms.
- With an Infantry+Thrown pocket (max 111) vs a plain Infantry pocket (max 101): skirmishers 111 fill first, then 1-stack 108, then pila 104, then non-throwers 101 — each a separate pass (§1.4). The plain-infantry pocket only takes agents once the scan reaches its own ScoreToSeek, so pila troops are left for the "no preference" formation unless the thrown formation still has room.
- Optional finer ordering inside a tier (e.g. 2 stacks of 5 > 2 stacks of 3, or 1 stack + pila > 1 stack): use spare values, e.g. `stacks>=2: 10`, `stacks==1 && (singles>0 || total>=5): 8`, `stacks==1: 7`, `singles>=2: 4`, `singles==1: 3`. Keep the top value exactly 10.
- Mounted throwers (Cavalry + Thrown filter) work the same way.

Optional cosmetic patch: `OrderOfBattleVM.GetTroopCountWithFilter` (private, `int (DeploymentFormationClass, FormationFilterType)`) counts `a.HasThrownCached` for the UI number; a postfix could recount with `stacks >= 1` when `filterType == Thrown`. Not required for behaviour.

Alternative (if transpiler is unwanted): Harmony prefix on `Team.RearrangeFormationsAccordingToFilter` that sets a `[ThreadStatic] bool` + postfix on `FormationPocket..ctor(Func<Agent,int>, int, int, int)` wrapping `ref priorityFunction` — but the ctor doesn't get the filter (would need to stash `MassTransferData` filters in the prefix and index by the `index` arg). Workable, more moving parts; transpiler is cleaner.

---

## 4. Build facts (copy from TrainingBattlesMod / trax_combat_enhancements)

- **Game:** `D:\SteamLibrary\steamapps\common\Mount & Blade II Bannerlord`, version **v1.4.8** (`bin\Win64_Shipping_Client\Version.xml`: `<Singleplayer Value="v1.4.8"/>`).
- **Binaries:** `$(GameFolder)\bin\Win64_Shipping_Client\TaleWorlds.*.dll`; ViewModelCollection is `TaleWorlds.MountAndBlade.ViewModelCollection.dll` in that same main bin (only needed for the optional cosmetic patch). Needed for core patch: `TaleWorlds.Core`, `TaleWorlds.Library`, `TaleWorlds.MountAndBlade`, (`TaleWorlds.Engine`, `TaleWorlds.DotNet` if compiler asks), all `<Private>false</Private>`.
- **Directory.Build.props** (TrainingBattlesMod): `LangVersion 10.0`, `Nullable enable`, `TreatWarningsAsErrors false`, `<GameFolder>D:\SteamLibrary\steamapps\common\Mount &amp; Blade II Bannerlord</GameFolder>`, `McmBinFolder` (only if MCM used). trax_combat_enhancements adds: version read from `module\SubModule.xml` via regex into `$(TraxModVersion)`, and `<Import Project="Directory.Build.props.user" Condition="Exists(...)"/>` for personal overrides.
- **csproj:** `<Project Sdk="Microsoft.NET.Sdk">`, `<TargetFramework>net472</TargetFramework>`, `<AppendTargetFrameworkToOutputPath>false</AppendTargetFrameworkToOutputPath>`, `<PackageReference Include="Microsoft.NETFramework.ReferenceAssemblies" Version="1.0.3" PrivateAssets="all" />`. (Pure-logic Core libs are `netstandard2.0`.)
- **Harmony:** TrainingBattlesMod does **not** use Harmony (nor does TraxCombatEnhancements). Two in-house precedents:
  - ImmersiveAI bundles `lib\0Harmony.dll` (v2.4.2.0) with `<Private>true</Private>`; patches via `new Harmony("mod.immersiveai...").Patch(target, prefix: new HarmonyMethod(...))`.
  - Recommended for this mod: reference the **Bannerlord.Harmony** workshop module (id 2859188632, `v2.4.2.248`, `0Harmony.dll` FileVersion 2.4.2.0) at `D:\SteamLibrary\steamapps\workshop\content\261550\2859188632\bin\Win64_Shipping_Client\0Harmony.dll`, `<Private>false</Private>`, and declare the module dependency (MCM already requires it, so most players have it). smart_steward's McmProbe uses this path as `HarmonyBinFolder`. Alternatively NuGet `Lib.Harmony` 2.4.x with `ExcludeAssets=runtime`.
- **SubModule.xml** format (from TrainingBattlesMod `module\SubModule.xml`):
```xml
<?xml version="1.0" encoding="UTF-8"?>
<Module xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="https://raw.githubusercontent.com/BUTR/Bannerlord.XmlSchemas/master/SubModule.xsd">
  <Id value="..." /> <Name value="..." /> <Version value="v1.0.0" />
  <DefaultModule value="false" /> <ModuleCategory value="Singleplayer" /> <ModuleType value="Community" />
  <DependedModules>
    <DependedModule Id="Native" /> <DependedModule Id="SandBoxCore" /> <DependedModule Id="Sandbox" /> <DependedModule Id="StoryMode" />
  </DependedModules>
  <DependedModuleMetadatas>
    <DependedModuleMetadata id="Bannerlord.Harmony" order="LoadBeforeThis" />   <!-- add for this mod -->
    <DependedModuleMetadata id="Native" order="LoadBeforeThis" /> ... (same for SandBoxCore, Sandbox, StoryMode)
  </DependedModuleMetadatas>
  <SubModules><SubModule>
    <Name value="..." /> <DLLName value="X.dll" /> <SubModuleClassType value="Ns.SubModule" /> <Tags />
  </SubModule></SubModules>
</Module>
```
  (Also add `<DependedModule Id="Bannerlord.Harmony" />` to DependedModules. The mod works in custom battle too — Native-only is enough for the core patch; Sandbox deps are optional.)
- **Entry point:** `public class SubModule : MBSubModuleBase` — apply Harmony in `OnSubModuleLoad()` (TrainingBattles uses `OnGameStart`, `OnBeforeInitialModuleScreenSetAsRoot`, `OnMissionBehaviorInitialize`).
- **Deploy** (`TrainingBattlesMod\tools\deploy.ps1`): `dotnet build <csproj> -c Release`, copy `module\SubModule.xml` into `$GameFolder\Modules\<Id>.Dev\` with Id/Name rewritten to `<Id>.Dev` / `<Name> (dev)`, copy DLLs from `src\<Module>\bin\Release\` to `Modules\<Id>.Dev\bin\Win64_Shipping_Client\`. `tools\package.ps1` builds the release zip into `dist\`.
