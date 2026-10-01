# Better Skirmisher Separation — technical notes

For Bannerlord v1.4.8. When a formation in the Order of Battle has the **Thrown Weapons** preference
ticked, vanilla treats "has any throwable" as a yes/no, so Legionaries with one or two pila rank exactly
the same as Battanian Skirmishers with two stacks of javelins. This mod grades throwers by what they
actually carry, so the real skirmishers fill the formation first.

## Tiers

| Carries | Thrown score (vanilla: flat 10) |
|---|---|
| 2+ proper throwing stacks (javelins, throwing axes, throwing knives) | 10 |
| 1 proper stack | 7 |
| Only pila / heavy throwing spears (thrown as a secondary use) | 3 |
| Nothing throwable | 0 |

A "proper stack" is an item whose primary use is a consumable thrown weapon holding more than one
(vanilla stacks are 3-5). Everything else in the vanilla priority (formation class, mount, shield, spear,
heavy armor, tier filters) is unchanged, and formations without the Thrown Weapons filter sort exactly
as in vanilla.

## Settings (MCM)

With [Mod Configuration Menu](https://steamcommunity.com/sharedfiles/filedetails/?id=2859238197) installed,
*Options > Mod Options > Better Skirmisher Separation* has:

| Setting | Default | What it does |
|---|---|---|
| Enabled | on | Off = vanilla troop sorting. No restart needed. |
| Minimum throwables to count as skirmisher | 1 | Total throwing weapons carried across all slots (a stack of 3 javelins = 3, a pilum = 1). Below it a troop gets no Thrown bonus at all. Set to 3+ to leave Legionaries and other pila carriers out; a single stack of javelins still passes. |

Changes apply the next time the Order of Battle screen sorts troops (before a battle, or when you move a
weight slider or toggle a filter). Without MCM the mod runs on the defaults above. Load MCM above this mod.

Safe to add or remove mid-campaign: it changes no save data.

## How it works

A Harmony transpiler on `Team.RearrangeFormationsAccordingToFilter` (and `OrderController.TransferUnitWithPriorityFunction`)
swaps the call to `TroopFilteringUtilities.GetPriorityFunction` for a wrapper that replaces the flat +10
thrown bonus with the tier above. It also makes the fill loop actually re-sort its formations between
passes (vanilla computes the sort and throws it away), only when a Thrown formation is involved —
otherwise a second filtered formation of the same class (e.g. Infantry + Shield) could pull plain troops
into the thrown formation ahead of the 1-stack and pila tiers. If the game changes and the call can't be
found, the mod logs a warning and leaves vanilla behaviour in place.

The patch is applied when the first mission starts, not at game load: patching earlier makes the game
initialise `MovementOrder` with no mission running, which crashes the first battle.

## Limits

- Only the Order of Battle distribution is graded (mission start, weight sliders, filter toggles).
  Reinforcements arriving mid-battle join formations by troop class, as in vanilla, so a Legionary
  reinforcement can still land in an infantry skirmisher formation.
- Naval battles assign troops to ships through their own code and are not changed.
- The formation's size comes from its weight slider; if there aren't enough throwers to fill it, vanilla
  tops it up with the best remaining troops of that class.
- Combined with High/Low Tier, the tier points (up to 7) can outweigh the gaps between thrown grades.

## Build

`dotnet build src\BetterSkirmisherSeparation\BetterSkirmisherSeparation.csproj -c Release` outputs to
`module\bin\Win64_Shipping_Client` and copies `module\` into the game's `Modules\BetterSkirmisherSeparation`
(set `DeployToGame` to `false` to skip). Building needs MCM installed at `McmBinFolder` (referenced, never
copied). Paths live in `Directory.Build.props`; override them in `Directory.Build.props.user`.

## Release

- `tools\package.ps1` builds Release and writes `dist\BetterSkirmisherSeparation_v<version>.zip`.
- `tools\make_cover.py` builds `docs\cover.jpg` (README image and Steam preview) from two screenshots.
- `tools\WORKSHOP-UPLOAD.md` has the Steam Workshop steps.
