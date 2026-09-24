"""The plugin's Luau, run under Lua 5.4 against a fake host.

The files in noctes/ use no syntax Lua 5.4 cannot read, so the real code runs
here unchanged; `lua/host.lua` stands in for the shell. Each `lua/test_*.lua`
is one test module and exits non-zero when anything in it fails. Skipped when
there is no Lua 5.4 to run them with.
"""

import shutil
import subprocess
import unittest
from pathlib import Path

LUA_DIR = Path(__file__).resolve().parent / "lua"


def lua54():
    for name in ("lua5.4", "lua54", "lua"):
        path = shutil.which(name)
        if path is None:
            continue
        version = subprocess.run([path, "-v"], capture_output=True, text=True)
        if "Lua 5.4" in version.stdout + version.stderr:
            return path
    return None


LUA = lua54()


@unittest.skipUnless(LUA, "no Lua 5.4 to run the Luau tests with")
class TestLuau(unittest.TestCase):
    def run_module(self, name):
        run = subprocess.run([LUA, str(LUA_DIR / name)], capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, f"\n{run.stdout}{run.stderr}")

    def test_store(self):
        self.run_module("test_store.lua")

    def test_service(self):
        self.run_module("test_service.lua")

    def test_surfaces(self):
        self.run_module("test_surfaces.lua")

    def test_every_module_is_run(self):
        run_here = {"test_store.lua", "test_service.lua", "test_surfaces.lua"}
        self.assertEqual({p.name for p in LUA_DIR.glob("test_*.lua")}, run_here)


if __name__ == "__main__":
    unittest.main()
