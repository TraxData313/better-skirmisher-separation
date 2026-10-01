using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using System.Reflection.Emit;
using HarmonyLib;
using TaleWorlds.Core;
using Debug = TaleWorlds.Library.Debug;
using TaleWorlds.MountAndBlade;

namespace BetterSkirmisherSeparation
{
    // Swaps TroopFilteringUtilities.GetPriorityFunction(filter, out Func<Agent,int>) for ThrownPriority's
    // wrapper inside the two vanilla methods that build an agent priority function from a filter.
    internal static class PriorityFunctionPatch
    {
        private static readonly MethodInfo Vanilla = AccessTools.Method(typeof(TroopFilteringUtilities),
            nameof(TroopFilteringUtilities.GetPriorityFunction),
            new[] { typeof(TroopTraitsMask), typeof(Func<Agent, int>).MakeByRefType() });

        private static readonly MethodInfo Replacement = AccessTools.Method(typeof(ThrownPriority),
            nameof(ThrownPriority.GetPriorityFunction));

        private static readonly MethodInfo SortPockets = AccessTools.Method(typeof(ThrownPriority),
            nameof(ThrownPriority.SortPockets));

        public static void Apply(Harmony harmony)
        {
            if (Vanilla == null)
            {
                SubModule.Warn("TroopFilteringUtilities.GetPriorityFunction(Agent) not found; nothing patched.");
                return;
            }
            var transpiler = new HarmonyMethod(AccessTools.Method(typeof(PriorityFunctionPatch), nameof(Transpiler)));
            // Order of Battle distribution (mission start, weight sliders, filter toggles)
            PatchOne(harmony, AccessTools.Method(typeof(Team), nameof(Team.RearrangeFormationsAccordingToFilter)), transpiler);
            // Transfer with a filter (vanilla passes hasThrown: false, so this only matters for other mods)
            PatchOne(harmony, AccessTools.Method(typeof(OrderController), nameof(OrderController.TransferUnitWithPriorityFunction)), transpiler);
        }

        private static void PatchOne(Harmony harmony, MethodInfo? target, HarmonyMethod transpiler)
        {
            if (target == null)
            {
                SubModule.Warn("a patch target is missing in this game version; it stays vanilla.");
                return;
            }
            try
            {
                harmony.Patch(target, transpiler: transpiler);
            }
            catch (Exception e)
            {
                SubModule.Warn("could not patch " + target.DeclaringType?.Name + "." + target.Name + ": " + e);
            }
        }

        private static IEnumerable<CodeInstruction> Transpiler(IEnumerable<CodeInstruction> instructions, MethodBase original)
        {
            var codes = new List<CodeInstruction>(instructions);
            int replaced = 0, resorts = 0;
            for (int i = 0; i < codes.Count; i++)
            {
                var code = codes[i];
                if (code.Calls(Vanilla))
                {
                    code.operand = Replacement;
                    replaced++;
                }
                // `list2.OrderByDescending(p => p.ScoreToSeek);` whose result vanilla throws away (call; pop)
                else if (code.operand is MethodInfo m && m.Name == nameof(Enumerable.OrderByDescending)
                    && m.DeclaringType == typeof(Enumerable) && m.IsGenericMethod
                    && m.GetGenericArguments()[0] == typeof(FormationPocket)
                    && i + 1 < codes.Count && codes[i + 1].opcode == OpCodes.Pop)
                {
                    code.operand = SortPockets;
                    resorts++;
                }
            }
            if (replaced == 0)
                SubModule.Warn(original.DeclaringType?.Name + "." + original.Name
                    + " no longer calls GetPriorityFunction; it stays vanilla.");
            if (original.DeclaringType == typeof(Team) && resorts == 0)
                Debug.Print("[BetterSkirmisherSeparation] pocket re-sort not found in Team.RearrangeFormationsAccordingToFilter; "
                    + "tiers may merge when several filtered formations share a class.");
            return codes;
        }
    }
}
