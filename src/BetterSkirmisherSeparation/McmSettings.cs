using System.Runtime.CompilerServices;
using MCM.Abstractions.FluentBuilder;
using MCM.Common;

namespace BetterSkirmisherSeparation
{
    // The in-game Mod Configuration Menu page, built with MCM's fluent API on purpose: an
    // AttributeGlobalSettings subclass would put a type with an MCM base class in our assembly, and without
    // MCM the game's own Module.CollectModuleAssemblyTypes (assembly.GetTypes(), no ReflectionTypeLoadException
    // handling) would then refuse to load the whole mod. No type here derives from or stores an MCM type; MCM
    // is only touched inside Register (not inlined), which Settings calls only once MCMv5 is loaded.
    internal static class McmSettings
    {
        private static object? _registered; // keeps the FluentGlobalSettings alive, typed object on purpose

        [MethodImpl(MethodImplOptions.NoInlining)]
        public static bool Register()
        {
            var builder = BaseSettingsBuilder.Create("BetterSkirmisherSeparation_v1", "Better Skirmisher Separation");
            if (builder == null)
                return false; // MCM not initialised yet
            var settings = builder
                .SetFolderName("BetterSkirmisherSeparation")
                .SetFormat("json2")
                .CreateGroup("General", group => group
                    .SetGroupOrder(0)
                    .AddBool("Enabled", "Enabled",
                        new ProxyRef<bool>(() => Settings.Enabled, v => Settings.Enabled = v),
                        b => b.SetOrder(0).SetRequireRestart(false).SetHintText(
                            "Grade throwers in the Order of Battle when a formation has the Thrown Weapons preference ticked. Off = vanilla troop sorting (every troop with any throwable counts the same). Takes effect the next time the Order of Battle sorts troops. Default on."))
                    .AddInteger("MinThrowables", "Minimum throwables to count as skirmisher", 1, 10,
                        new ProxyRef<int>(() => Settings.MinThrowables, v => Settings.MinThrowables = v),
                        b => b.SetOrder(1).SetRequireRestart(false).SetHintText(
                            "How many throwing weapons a troop must carry, counted across all slots (a stack of 3 javelins = 3, each pilum = 1), to get any Thrown Weapons bonus at all. Below it the troop is sorted like a non-thrower. 1 = anyone with a throwable counts (default). Set to 3+ to exclude pila carriers like Legionaries (1 pilum); a single stack of javelins still passes. Applies in the Order of Battle screen before a battle.")
                            .AddValueFormat("0")))
                .BuildAsGlobal();
            settings.Register(); // loads the saved values through the ProxyRefs
            _registered = settings;
            return true;
        }
    }
}
