using System;
using System.Linq;

namespace BetterSkirmisherSeparation
{
    // Live settings. Defaults without MCM; with MCM the menu page (McmSettings) reads and writes these fields
    // directly, so a read is two field loads and changes apply without a restart.
    internal static class Settings
    {
        public const bool DefaultEnabled = true;
        public const int DefaultMinThrowables = 1;

        private static volatile bool _enabled = DefaultEnabled;
        private static volatile int _minThrowables = DefaultMinThrowables;

        public static bool Enabled { get => _enabled; set => _enabled = value; }
        public static int MinThrowables { get => _minThrowables; set => _minThrowables = Math.Max(1, value); }

        public readonly struct Values
        {
            public readonly bool Enabled;
            public readonly int MinThrowables;
            public Values(bool enabled, int minThrowables) { Enabled = enabled; MinThrowables = Math.Max(1, minThrowables); }
        }

        public static Values Read() => new Values(_enabled, _minThrowables);

        // Called once from SubModule.OnBeforeInitialModuleScreenSetAsRoot. MCM types are only touched inside
        // McmSettings.Register, and only once the MCMv5 assembly is loaded. Any failure costs the menu, not the mod.
        public static void TryRegisterMcm()
        {
            bool mcmLoaded = AppDomain.CurrentDomain.GetAssemblies()
                .Any(a => string.Equals(a.GetName().Name, "MCMv5", StringComparison.OrdinalIgnoreCase));
            if (!mcmLoaded)
                return;
            try
            {
                if (!McmSettings.Register())
                    TaleWorlds.Library.Debug.Print("[BetterSkirmisherSeparation] MCM not ready; running on defaults.");
            }
            catch (Exception e)
            {
                TaleWorlds.Library.Debug.Print("[BetterSkirmisherSeparation] MCM page failed, running on defaults: " + e);
            }
        }
    }
}
