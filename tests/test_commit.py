"""The write guard.

`commit()` is the only place noctes writes a file outside its own data
directory, so everything it promises is asserted here: the candidate is
validated before it replaces anything, a rejected one leaves settings.toml
exactly as it was, nothing is left behind either way, and two commands started
together cannot undo each other. "Nothing left behind" is a regression guard
for noctalia-dev/community-plugins#828, where a dated backup name left one
stale copy of the user's settings per day of use.
"""

import os
import subprocess
import sys
import tempfile
import shutil
import tomllib
import unittest
from pathlib import Path

import fixtures
from harness import TOOL, ToolCase


class TestNothingLeftBehind(ToolCase):
    def test_a_write_leaves_only_the_settings_file(self):
        self.write(fixtures.settings())
        self.run_tool("add", "--output", "DP-2", "--screen", "3440x1440")
        self.assertEqual(self.files(), ["settings.toml"])

    def test_repeated_writes_do_not_accumulate_files(self):
        # Adding and deleting sheets is the normal loop for a sticky note
        # plugin, so this runs constantly over a plugin's life.
        self.write(fixtures.settings())
        for index in range(5):
            self.run_tool("add", "--output", "DP-2", "--screen", "3440x1440",
                          "--key", f"k{index}")
        self.run_tool("tilt", "--square")
        self.run_tool("remove", "--key", "k0")
        self.assertEqual(self.files(), ["settings.toml"])

    def test_a_rejected_write_leaves_nothing_either(self):
        self.write(fixtures.settings())
        self.noctalia.validate_returncode = 1

        with self.assertRaises(SystemExit):
            self.run_tool("add", "--output", "DP-2", "--screen", "3440x1440")

        self.assertEqual(self.files(), ["settings.toml"])


class TestValidation(ToolCase):
    def test_the_candidate_is_validated_before_it_replaces_the_file(self):
        original = self.write(fixtures.settings())
        self.run_tool("add", "--output", "DP-2", "--screen", "3440x1440", "--key", "k")

        [(live, candidate)] = self.noctalia.seen_at_validate
        self.assertEqual(live, original)
        self.assertEqual(candidate, self.read())

    def test_a_rejected_write_leaves_the_file_as_it_was(self):
        original = self.write(fixtures.settings([fixtures.sheet(fixtures.wid(1), key="a")]))
        self.noctalia.validate_returncode = 1
        self.noctalia.validate_stderr = "unknown key"

        with self.assertRaises(SystemExit):
            self.run_tool("add", "--output", "DP-2", "--screen", "3440x1440")

        self.assertEqual(self.read(), original)

    def test_the_rejection_reason_reaches_the_caller(self):
        self.write(fixtures.settings())
        self.noctalia.validate_returncode = 1
        self.noctalia.validate_stderr = "unknown key `foo`"

        with self.assertRaises(SystemExit) as raised:
            self.run_tool("add", "--output", "DP-2", "--screen", "3440x1440")

        self.assertIn("unknown key `foo`", str(raised.exception))

    def test_the_shell_is_not_asked_to_reload(self):
        # It watches settings.toml and reloads when the rename lands. Asking as
        # well made it reload twice, rebuilding every desktop widget twice.
        self.write(fixtures.settings())
        self.run_tool("add", "--output", "DP-2", "--screen", "3440x1440")
        self.assertTrue(self.noctalia.validated)
        self.assertFalse(self.noctalia.reloaded)

    def test_the_file_keeps_its_mode(self):
        self.write(fixtures.settings())
        self.settings.chmod(0o600)
        self.run_tool("add", "--output", "DP-2", "--screen", "3440x1440")
        self.assertEqual(self.settings.stat().st_mode & 0o777, 0o600)

    def test_a_symlinked_settings_file_keeps_its_link(self):
        # Dotfile managers link settings.toml into a repository. Replacing the
        # link with a plain file would quietly detach it from there.
        real = self.tmp / "dotfiles" / "settings.toml"
        real.parent.mkdir()
        real.write_text(fixtures.settings())
        self.settings.symlink_to(real)

        self.run_tool("add", "--output", "DP-2", "--screen", "3440x1440", "--key", "k")

        self.assertTrue(self.settings.is_symlink())
        self.assertIn('key = "k"', real.read_text())


class TestConcurrency(unittest.TestCase):
    """Two real processes against one file, the way a double click on New
    starts them. Without the lock both read the same original, and the second
    write silently drops the first sheet."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="noctes-race-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.state = self.tmp / "home/.local/state/noctalia"
        self.state.mkdir(parents=True)
        (self.state / "settings.toml").write_text(fixtures.settings())

        # A validate slow enough that the two runs overlap for certain.
        bin_dir = self.tmp / "bin"
        bin_dir.mkdir()
        fake = bin_dir / "noctalia"
        fake.write_text("#!/bin/sh\nsleep 0.3\nexit 0\n")
        fake.chmod(0o755)
        self.env = dict(os.environ, HOME=str(self.tmp / "home"),
                        PATH=f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
                        PYTHONDONTWRITEBYTECODE="1")

    def test_two_adds_started_together_both_land(self):
        runs = [
            subprocess.Popen([sys.executable, str(TOOL), "add", "--output", "DP-2",
                              "--screen", "3440x1440"],
                             env=self.env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            for _ in range(2)
        ]
        for run in runs:
            _, err = run.communicate(timeout=20)
            self.assertEqual(run.returncode, 0, err.decode())

        parsed = tomllib.loads((self.state / "settings.toml").read_text())
        widgets = parsed["desktop_widgets"]["widget"]
        self.assertEqual(len(widgets), 2)
        self.assertEqual(len({w["settings"]["key"] for w in widgets.values()}), 2)
        self.assertEqual(sorted(parsed["desktop_widgets"]["widget_order"]), sorted(widgets))


class TestBlastRadius(ToolCase):
    def test_no_process_but_noctalia_is_spawned(self):
        self.write(fixtures.settings())
        self.run_tool("add", "--output", "DP-2", "--screen", "3440x1440")
        for call in self.noctalia.calls:
            self.assertEqual(call[0], "noctalia")

    def test_settings_outside_desktop_widgets_survive_every_command(self):
        self.write(fixtures.settings([fixtures.sheet(fixtures.wid(1), key="a")],
                                     lockscreen="wrapped"))
        self.run_tool("add", "--output", "DP-2", "--screen", "3440x1440")
        self.run_tool("tilt", "--random")
        self.run_tool("remove", "--key", "a")

        parsed = self.assertValidToml()
        self.assertEqual(parsed["bar"]["position"], "top")
        self.assertIs(parsed["dock"]["enabled"], False)
        self.assertEqual(parsed["desktop_widgets"]["grid"]["cell_size"], 16)
        self.assertEqual(parsed["desktop_widgets"]["schema_version"], 2)
        self.assertEqual(parsed["lockscreen_widgets"]["widget_order"], fixtures.LOCKSCREEN_IDS)

    def test_help_exits_cleanly_without_a_settings_file(self):
        # The service's probe: `--help` answering 0 is how it learns the helper
        # runs at all, before any settings file is involved.
        home = self.tmp / "empty-home"
        home.mkdir()
        run = subprocess.run([sys.executable, str(TOOL), "--help"],
                             env=dict(os.environ, HOME=str(home), PYTHONDONTWRITEBYTECODE="1"),
                             capture_output=True, text=True)
        self.assertEqual(run.returncode, 0)
        self.assertIn("add", run.stdout)
        self.assertEqual(list(home.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
