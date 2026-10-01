using System;
using System.Collections.Generic;
using System.Linq;
using TaleWorlds.Core;
using TaleWorlds.MountAndBlade;

namespace BetterSkirmisherSeparation
{
    public static class ThrownPriority
    {
        public const int TierTwoStacks = 10; // must equal vanilla's flat Thrown bonus, so only this tier reaches max priority
        public const int TierOneStack = 7;
        public const int TierSinglesOnly = 3;

        // Same signature as TroopFilteringUtilities.GetPriorityFunction(TroopTraitsMask, out Func<Agent, int>).
        public static void GetPriorityFunction(TroopTraitsMask filter, out Func<Agent, int> priorityFunc)
        {
            TroopFilteringUtilities.GetPriorityFunction(filter, out Func<Agent, int> vanilla);
            priorityFunc = vanilla;
            try
            {
                var settings = Settings.Read(); // once per distribution, so MCM changes apply without a restart
                if (settings.Enabled && (filter & TroopTraitsMask.Thrown) != 0)
                    priorityFunc = new GradedPriority(vanilla, settings.MinThrowables).Score;
            }
            catch (Exception e)
            {
                SubModule.LogOnce("GetPriorityFunction", e);
            }
        }

        // Replaces the discarded `list2.OrderByDescending(p => p.ScoreToSeek)` inside the fill loop of
        // Team.RearrangeFormationsAccordingToFilter. Vanilla then seeks list2[0].ScoreToSeek, which is fine
        // with its flat scores but lets another pocket at the same base (e.g. Infantry+Shield) drop the
        // threshold to the floor and skip our middle tiers. Sorting in place makes it seek the best remaining
        // score. Only done when a graded (Thrown) pocket is present, so other distributions (and the mod
        // switched off in MCM: no GradedPriority is ever built) stay vanilla.
        public static IOrderedEnumerable<FormationPocket> SortPockets(IEnumerable<FormationPocket> pockets, Func<FormationPocket, int> keySelector)
        {
            var sorted = pockets.OrderByDescending(keySelector);
            try
            {
                if (pockets is List<FormationPocket> list && list.Exists(p => p.PriorityFunction?.Target is GradedPriority))
                {
                    var copy = sorted.ToList(); // stable, ties keep vanilla's order; built before the list is touched
                    list.Clear();
                    list.AddRange(copy);
                }
            }
            catch (Exception e)
            {
                SubModule.LogOnce("SortPockets", e); // list untouched unless the copy succeeded
            }
            return sorted; // popped by the caller, never enumerated
        }

        private sealed class GradedPriority
        {
            private readonly Func<Agent, int> _vanilla;
            private readonly int _minThrowables;
            // Lives only as long as one rearrange/transfer call, so it never outlasts a mission or goes stale.
            private readonly Dictionary<Agent, int> _tiers = new Dictionary<Agent, int>();

            public GradedPriority(Func<Agent, int> vanilla, int minThrowables)
            {
                _vanilla = vanilla;
                _minThrowables = minThrowables;
            }

            public int Score(Agent agent)
            {
                int score = _vanilla(agent); // vanilla's own exceptions stay vanilla's
                try
                {
                    if (agent?.Character == null || agent.Equipment == null || !agent.HasThrownCached)
                        return score;
                    if (!_tiers.TryGetValue(agent, out int tier))
                    {
                        tier = GetTier(agent.Equipment, _minThrowables);
                        _tiers[agent] = tier;
                    }
                    return score - TierTwoStacks + tier;
                }
                catch (Exception e)
                {
                    SubModule.LogOnce("Score", e);
                    return score; // vanilla score for this agent
                }
            }
        }

        // minThrowables: total thrown ammo carried (a stack of 3 javelins = 3, a pilum = 1) needed for any tier;
        // below it the agent scores as a non-thrower. 1 = every thrower qualifies (the behaviour without MCM).
        public static int GetTier(MissionEquipment equipment, int minThrowables = 1)
        {
            int stacks = 0, singles = 0, count = 0;
            for (var i = EquipmentIndex.WeaponItemBeginSlot; i < EquipmentIndex.NumAllWeaponSlots; i++)
            {
                MissionWeapon weapon = equipment[i];
                if (weapon.IsEmpty || weapon.Amount <= 0)
                    continue;
                var usages = weapon.Item?.Weapons;
                if (usages == null)
                    continue;
                for (int u = 0; u < usages.Count; u++)
                {
                    // Vanilla's own definition of a thrown usage (MissionWeapon.GatherInformationFromWeapon)
                    if (usages[u].IsRangedWeapon && usages[u].IsConsumable)
                    {
                        count += weapon.Amount;
                        // javelins, throwing axes, knives; a one-shot primary throwable (modded) counts as a single
                        if (u == 0 && weapon.ModifiedMaxAmount > 1) stacks++;
                        else singles++;         // pila, heavy throwing spears: thrown only as an alternative use
                        break;
                    }
                }
            }
            if (count < minThrowables) return 0;
            if (stacks >= 2) return TierTwoStacks;
            if (stacks == 1) return TierOneStack;
            return singles > 0 ? TierSinglesOnly : 0;
        }
    }
}
