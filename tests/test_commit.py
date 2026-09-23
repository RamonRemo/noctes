"""The write guard.

`commit()` is the only place noctes touches a file outside its own data
directory, so everything it promises is asserted here: back up, write, validate,
restore on rejection, reload on success. The backup naming tests are a
regression guard for noctalia-dev/community-plugins#828, where a dated name left
one stale copy of the user's settings behind per day of use.
"""

import unittest

import fixtures
from harness import ToolCase


class TestBackup(ToolCase):
    def test_one_fixed_name_rather_than_one_per_day(self):
        self.write(fixtures.settings())
        self.run_tool("add", "--output", "DP-2", "--screen", "3440x1440")
        self.assertEqual(self.backups(), ["settings.toml.bak-noctes"])

    def test_repeated_writes_do_not_accumulate_files(self):
        # Adding and deleting sheets is the normal loop for a sticky note
        # plugin, so this runs constantly over a plugin's life.
        self.write(fixtures.settings())
        for index in range(5):
            self.run_tool("add", "--output", "DP-2", "--screen", "3440x1440",
                          "--key", f"k{index}")
        self.assertEqual(self.backups(), ["settings.toml.bak-noctes"])

    def test_no_dated_backup_is_ever_written(self):
        self.write(fixtures.settings())
        self.run_tool("add", "--output", "DP-2", "--screen", "3440x1440")
        self.run_tool("tilt", "--square")
        for name in self.backups():
            self.assertNotRegex(name, r"\d{4}-\d{2}-\d{2}")

    def test_the_backup_holds_what_was_there_before_the_write(self):
        original = self.write(fixtures.settings([fixtures.sheet(fixtures.wid(1), key="a")]))
        self.run_tool("add", "--output", "DP-2", "--screen", "3440x1440")

        backup = (self.tmp / "settings.toml.bak-noctes").read_text()
        self.assertEqual(backup, original)
        self.assertNotEqual(self.read(), original)

    def test_the_second_write_backs_up_the_first_result(self):
        self.write(fixtures.settings())
        self.run_tool("add", "--output", "DP-2", "--screen", "3440x1440", "--key", "one")
        after_first = self.read()
        self.run_tool("add", "--output", "DP-2", "--screen", "3440x1440", "--key", "two")

        self.assertEqual((self.tmp / "settings.toml.bak-noctes").read_text(), after_first)


class TestValidation(ToolCase):
    def test_a_good_write_is_validated_and_reloaded(self):
        self.write(fixtures.settings())
        self.run_tool("add", "--output", "DP-2", "--screen", "3440x1440")
        self.assertTrue(self.noctalia.validated)
        self.assertTrue(self.noctalia.reloaded)

    def test_a_rejected_write_puts_the_old_file_back(self):
        original = self.write(fixtures.settings([fixtures.sheet(fixtures.wid(1), key="a")]))
        self.noctalia.validate_returncode = 1
        self.noctalia.validate_stderr = "unknown key"

        with self.assertRaises(SystemExit):
            self.run_tool("add", "--output", "DP-2", "--screen", "3440x1440")

        self.assertEqual(self.read(), original)

    def test_a_rejected_write_is_not_reloaded(self):
        self.write(fixtures.settings())
        self.noctalia.validate_returncode = 1

        with self.assertRaises(SystemExit):
            self.run_tool("add", "--output", "DP-2", "--screen", "3440x1440")

        self.assertFalse(self.noctalia.reloaded)

    def test_the_rejection_reason_reaches_the_caller(self):
        self.write(fixtures.settings())
        self.noctalia.validate_returncode = 1
        self.noctalia.validate_stderr = "unknown key `foo`"

        with self.assertRaises(SystemExit) as raised:
            self.run_tool("add", "--output", "DP-2", "--screen", "3440x1440")

        self.assertIn("unknown key `foo`", str(raised.exception))

    def test_validation_runs_before_the_reload(self):
        self.write(fixtures.settings())
        self.run_tool("add", "--output", "DP-2", "--screen", "3440x1440")

        names = [call[1] for call in self.noctalia.calls]
        self.assertEqual(names, ["config", "msg"])


class TestBlastRadius(ToolCase):
    def test_only_the_settings_file_and_its_backup_are_touched(self):
        self.write(fixtures.settings([fixtures.sheet(fixtures.wid(1), key="a")]))
        self.run_tool("add", "--output", "DP-2", "--screen", "3440x1440")
        self.run_tool("tilt", "--random")
        self.run_tool("remove", "--key", "a")

        self.assertEqual(sorted(p.name for p in self.tmp.iterdir()),
                         ["settings.toml", "settings.toml.bak-noctes"])

    def test_no_process_but_noctalia_is_spawned(self):
        self.write(fixtures.settings())
        self.run_tool("add", "--output", "DP-2", "--screen", "3440x1440")
        for call in self.noctalia.calls:
            self.assertEqual(call[0], "noctalia")

    def test_settings_outside_desktop_widgets_survive_every_command(self):
        self.write(fixtures.settings([fixtures.sheet(fixtures.wid(1), key="a")]))
        self.run_tool("add", "--output", "DP-2", "--screen", "3440x1440")
        self.run_tool("tilt", "--random")

        parsed = self.assertValidToml()
        self.assertEqual(parsed["bar"]["position"], "top")
        self.assertIs(parsed["dock"]["enabled"], False)
        self.assertEqual(parsed["desktop_widgets"]["grid"]["cell_size"], 16)
        self.assertEqual(parsed["desktop_widgets"]["schema_version"], 2)


if __name__ == "__main__":
    unittest.main()
