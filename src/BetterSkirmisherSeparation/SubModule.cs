using System;
using HarmonyLib;
using TaleWorlds.Library;
using TaleWorlds.MountAndBlade;

namespace BetterSkirmisherSeparation
{
    public class SubModule : MBSubModuleBase
    {
        internal const string HarmonyId = "trax.bannerlord.betterskirmisherseparation";

        private static string? _pendingWarning;
        private static bool _mcmTried;
        private static bool _patched;
        private static bool _onceLogged;

        // NOT patched in OnSubModuleLoad on purpose. Harmony/MonoMod JIT-compiles the original method
        // (RuntimeHelpers.PrepareMethod) when it detours it, and Team.RearrangeFormationsAccordingToFilter reads
        // MovementOrder.MovementOrderStop. MovementOrder is beforefieldinit, so that JIT runs its static
        // constructor right then; at the main menu Mission.Current is null, the cctor throws a
        // NullReferenceException (swallowed by the JIT) and the type stays broken for the whole process: the first
        // battle then dies with TypeInitializationException in Team/Formation setup. Patching once a mission exists
        // (Mission.Initialize has set Mission.Current) lets the cctor run exactly as vanilla's first touch would.
        public override void OnBeforeMissionBehaviorInitialize(Mission mission)
        {
            base.OnBeforeMissionBehaviorInitialize(mission);
            if (_patched || Mission.Current == null)
                return;
            _patched = true;
            try
            {
                PriorityFunctionPatch.Apply(new Harmony(HarmonyId));
            }
            catch (Exception e)
            {
                Warn("patching failed, vanilla troop sorting stays in effect: " + e);
            }
        }

        protected override void OnBeforeInitialModuleScreenSetAsRoot()
        {
            base.OnBeforeInitialModuleScreenSetAsRoot();
            if (!_mcmTried)
            {
                _mcmTried = true;
                Settings.TryRegisterMcm();
            }
            if (_pendingWarning == null)
                return;
            InformationManager.DisplayMessage(new InformationMessage(_pendingWarning, Colors.Yellow));
            _pendingWarning = null;
        }

        internal static void Warn(string message)
        {
            Debug.Print("[BetterSkirmisherSeparation] " + message);
            _pendingWarning ??= "Better Skirmisher Separation: " + message.Split('\n')[0];
        }

        // For the code that runs inside the game's own methods: log the first failure only, never rethrow.
        internal static void LogOnce(string where, Exception e)
        {
            if (_onceLogged)
                return;
            _onceLogged = true;
            Debug.Print("[BetterSkirmisherSeparation] " + where + " failed, using vanilla behaviour: " + e);
        }
    }
}
