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

        protected override void OnSubModuleLoad()
        {
            base.OnSubModuleLoad();
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
    }
}
