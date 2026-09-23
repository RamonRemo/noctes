"""The four subcommands, against a settings file in a temp directory.

Every one of these asserts the result still parses as TOML. Noctalia does not
fail gracefully on a malformed settings file - it breaks the parse and takes the
shell down - so "the tool never writes something unparseable" is the invariant
worth guarding hardest.
"""

import unittest

import fixtures
from harness import ToolCase


class TestAdd(ToolCase):
    def test_writes_a_sheet_the_parser_accepts(self):
        self.write(fixtures.settings())
        self.run_tool("add", "--output", "DP-2", "--screen", "3440x1440")

        parsed = self.assertValidToml()
        widgets = parsed["desktop_widgets"]["widget"]
        self.assertEqual(len(widgets), 1)
        self.assertEqual(next(iter(widgets.values()))["type"], "remo/noctes:note")

    def test_the_new_sheet_joins_widget_order(self):
        self.write(fixtures.settings())
        self.run_tool("add", "--output", "DP-2", "--screen", "3440x1440")

        parsed = self.assertValidToml()
        order = parsed["desktop_widgets"]["widget_order"]
        self.assertEqual(order, list(parsed["desktop_widgets"]["widget"]))

    def test_order_keeps_its_commas_when_it_already_had_entries(self):
        # The previous last entry has to gain a comma, or the array stops parsing.
        self.write(fixtures.settings([
            fixtures.sheet(fixtures.wid(1), key="a"),
            fixtures.sheet(fixtures.wid(2), key="b"),
        ]))
        self.run_tool("add", "--output", "DP-2", "--screen", "3440x1440")

        order = self.assertValidToml()["desktop_widgets"]["widget_order"]
        self.assertEqual(len(order), 3)

    def test_the_sheet_arrives_unframed_and_keyed(self):
        self.write(fixtures.settings())
        self.run_tool("add", "--output", "DP-2", "--screen", "3440x1440")

        widget = next(iter(self.assertValidToml()["desktop_widgets"]["widget"].values()))
        self.assertIs(widget["settings"]["background"], False)
        self.assertEqual(widget["settings"]["key"], "nota-1")

    def test_an_explicit_key_is_kept(self):
        self.write(fixtures.settings())
        self.run_tool("add", "--output", "DP-2", "--screen", "3440x1440", "--key", "shopping")

        widget = next(iter(self.assertValidToml()["desktop_widgets"]["widget"].values()))
        self.assertEqual(widget["settings"]["key"], "shopping")

    def test_it_lands_on_the_screen_the_other_sheets_are_on(self):
        self.write(fixtures.settings([
            fixtures.sheet(fixtures.wid(1), key="a", output="HDMI-A-1"),
        ]))
        self.run_tool("add", "--output", "DP-2", "--screen", "3440x1440")

        outputs = {w["output"] for w in self.assertValidToml()["desktop_widgets"]["widget"].values()}
        self.assertEqual(outputs, {"HDMI-A-1"})

    def test_force_output_overrides_that(self):
        self.write(fixtures.settings([
            fixtures.sheet(fixtures.wid(1), key="a", output="HDMI-A-1"),
        ]))
        self.run_tool("add", "--output", "DP-2", "--screen", "3440x1440", "--force-output")

        outputs = {w["output"] for w in self.assertValidToml()["desktop_widgets"]["widget"].values()}
        self.assertIn("DP-2", outputs)

    def test_a_sheet_is_tilted_unless_the_switch_is_off(self):
        self.write(fixtures.settings(plugin_tilt=True))
        self.run_tool("add", "--output", "DP-2", "--screen", "3440x1440")
        widget = next(iter(self.assertValidToml()["desktop_widgets"]["widget"].values()))
        self.assertNotEqual(widget["rotation"], 0.0)

    def test_the_switch_off_means_square(self):
        self.write(fixtures.settings(plugin_tilt=False))
        self.run_tool("add", "--output", "DP-2", "--screen", "3440x1440")
        widget = next(iter(self.assertValidToml()["desktop_widgets"]["widget"].values()))
        self.assertEqual(widget["rotation"], 0.0)

    def test_the_key_is_printed_first_for_the_service_to_read(self):
        self.write(fixtures.settings())
        self.run_tool("add", "--output", "DP-2", "--screen", "3440x1440", "--key", "work")
        self.assertEqual(self.output.splitlines()[0], "key=work")

    def test_a_bad_screen_argument_stops_before_writing(self):
        original = self.write(fixtures.settings())
        with self.assertRaises(SystemExit):
            self.run_tool("add", "--output", "DP-2", "--screen", "wide")
        self.assertEqual(self.read(), original)

    def test_another_plugins_widget_is_left_alone(self):
        self.write(fixtures.settings([fixtures.foreign(fixtures.wid(1))]))
        self.run_tool("add", "--output", "DP-2", "--screen", "3440x1440")

        foreign = self.assertValidToml()["desktop_widgets"]["widget"][fixtures.wid(1)]
        self.assertEqual(foreign["type"], "sysmon")
        self.assertEqual(foreign["settings"]["stat"], "gpu_vram")


class TestRemove(ToolCase):
    def test_the_sheet_and_its_order_entry_both_go(self):
        self.write(fixtures.settings([
            fixtures.sheet(fixtures.wid(1), key="keep"),
            fixtures.sheet(fixtures.wid(2), key="drop"),
        ]))
        self.run_tool("remove", "--key", "drop")

        parsed = self.assertValidToml()
        self.assertEqual(list(parsed["desktop_widgets"]["widget"]), [fixtures.wid(1)])
        self.assertEqual(parsed["desktop_widgets"]["widget_order"], [fixtures.wid(1)])

    def test_removing_the_last_entry_leaves_no_trailing_comma(self):
        self.write(fixtures.settings([
            fixtures.sheet(fixtures.wid(1), key="keep"),
            fixtures.sheet(fixtures.wid(2), key="drop"),
        ]))
        self.run_tool("remove", "--key", "drop")
        self.assertValidToml()

    def test_removing_the_only_sheet_leaves_an_empty_order(self):
        self.write(fixtures.settings([fixtures.sheet(fixtures.wid(1), key="only")]))
        self.run_tool("remove", "--key", "only")

        parsed = self.assertValidToml()
        self.assertEqual(parsed["desktop_widgets"]["widget_order"], [])

    def test_an_unknown_key_writes_nothing(self):
        original = self.write(fixtures.settings([fixtures.sheet(fixtures.wid(1), key="a")]))
        self.run_tool("remove", "--key", "nope")
        self.assertEqual(self.read(), original)
        self.assertFalse(self.noctalia.validated)

    def test_it_does_not_take_a_neighbour_with_it(self):
        self.write(fixtures.settings([
            fixtures.sheet(fixtures.wid(1), key="drop"),
            fixtures.foreign(fixtures.wid(2)),
            fixtures.sheet(fixtures.wid(3), key="keep"),
        ]))
        self.run_tool("remove", "--key", "drop")

        widgets = self.assertValidToml()["desktop_widgets"]["widget"]
        self.assertEqual(sorted(widgets), sorted([fixtures.wid(2), fixtures.wid(3)]))


class TestTilt(ToolCase):
    def test_square_zeroes_every_sheet(self):
        self.write(fixtures.settings([
            fixtures.sheet(fixtures.wid(1), key="a", rotation=0.04),
            fixtures.sheet(fixtures.wid(2), key="b", rotation=-0.03),
        ]))
        self.run_tool("tilt", "--square")

        widgets = self.assertValidToml()["desktop_widgets"]["widget"]
        self.assertEqual({w["rotation"] for w in widgets.values()}, {0.0})

    def test_random_gives_every_sheet_an_angle(self):
        self.write(fixtures.settings([
            fixtures.sheet(fixtures.wid(1), key="a", rotation=0.0),
            fixtures.sheet(fixtures.wid(2), key="b", rotation=0.0),
        ]))
        self.run_tool("tilt", "--random")

        widgets = self.assertValidToml()["desktop_widgets"]["widget"]
        for widget in widgets.values():
            self.assertNotEqual(widget["rotation"], 0.0)
            self.assertLessEqual(abs(widget["rotation"]), self.module.MAX_TILT)

    def test_it_does_not_rotate_another_plugins_widget(self):
        self.write(fixtures.settings([
            fixtures.sheet(fixtures.wid(1), key="a", rotation=0.0),
            fixtures.foreign(fixtures.wid(2)),
        ]))
        self.run_tool("tilt", "--random")

        widgets = self.assertValidToml()["desktop_widgets"]["widget"]
        self.assertEqual(widgets[fixtures.wid(2)]["rotation"], 0.0)

    def test_it_changes_only_the_rotation_line(self):
        self.write(fixtures.settings([
            fixtures.sheet(fixtures.wid(1), key="shopping", cx=900.0, cy=400.0),
        ]))
        self.run_tool("tilt", "--random")

        widget = self.assertValidToml()["desktop_widgets"]["widget"][fixtures.wid(1)]
        self.assertEqual((widget["cx"], widget["cy"]), (900.0, 400.0))
        self.assertEqual(widget["settings"]["key"], "shopping")

    def test_nothing_to_tilt_writes_nothing(self):
        original = self.write(fixtures.settings())
        self.run_tool("tilt", "--square")
        self.assertEqual(self.read(), original)
        self.assertFalse(self.noctalia.validated)


class TestScatter(ToolCase):
    """Sheets added through Noctalia's own widget editor arrive square, keyless
    and framed, because those are fields a plugin cannot set as one is created.
    """

    def test_it_adopts_a_sheet_the_editor_left_behind(self):
        self.write(fixtures.settings([
            fixtures.sheet(fixtures.wid(1), key="", background=True, rotation=0.0),
        ]))
        self.run_tool("scatter")

        widget = self.assertValidToml()["desktop_widgets"]["widget"][fixtures.wid(1)]
        self.assertEqual(widget["settings"]["key"], "nota-1")
        self.assertIs(widget["settings"]["background"], False)
        self.assertNotEqual(widget["rotation"], 0.0)

    def test_it_builds_a_settings_table_when_there_is_none(self):
        self.write(fixtures.settings([
            fixtures.sheet(fixtures.wid(1), settings_table=False),
        ]))
        self.run_tool("scatter")

        widget = self.assertValidToml()["desktop_widgets"]["widget"][fixtures.wid(1)]
        self.assertEqual(widget["settings"]["key"], "nota-1")
        self.assertIs(widget["settings"]["background"], False)

    def test_an_adopted_key_does_not_collide(self):
        self.write(fixtures.settings([
            fixtures.sheet(fixtures.wid(1), key="nota-1"),
            fixtures.sheet(fixtures.wid(2), key="", background=True),
        ]))
        self.run_tool("scatter")

        widgets = self.assertValidToml()["desktop_widgets"]["widget"]
        keys = [w["settings"]["key"] for w in widgets.values()]
        self.assertEqual(len(set(keys)), 2)

    def test_a_settled_sheet_is_left_alone(self):
        # This runs on every settings write, so it has to be a no-op once
        # everything has been adopted.
        self.write(fixtures.settings([
            fixtures.sheet(fixtures.wid(1), key="a", background=False, rotation=0.04),
        ]))
        self.run_tool("scatter")
        self.assertFalse(self.noctalia.validated)

    def test_dry_run_reports_without_writing(self):
        original = self.write(fixtures.settings([
            fixtures.sheet(fixtures.wid(1), key="", background=True),
        ]))
        self.run_tool("scatter", "--dry-run")
        self.assertEqual(self.read(), original)
        self.assertFalse(self.noctalia.validated)

    def test_keep_tilt_leaves_the_angle_where_it_was(self):
        self.write(fixtures.settings([
            fixtures.sheet(fixtures.wid(1), key="", background=True, rotation=0.0),
        ]))
        self.run_tool("scatter", "--keep-tilt")

        widget = self.assertValidToml()["desktop_widgets"]["widget"][fixtures.wid(1)]
        self.assertEqual(widget["rotation"], 0.0)
        self.assertEqual(widget["settings"]["key"], "nota-1")

    def test_the_tilt_switch_off_is_honoured(self):
        self.write(fixtures.settings(
            [fixtures.sheet(fixtures.wid(1), key="", background=True, rotation=0.0)],
            plugin_tilt=False,
        ))
        self.run_tool("scatter")
        widget = self.assertValidToml()["desktop_widgets"]["widget"][fixtures.wid(1)]
        self.assertEqual(widget["rotation"], 0.0)

    def test_it_never_adopts_another_plugins_widget(self):
        self.write(fixtures.settings([fixtures.foreign(fixtures.wid(1))]))
        self.run_tool("scatter")

        widget = self.assertValidToml()["desktop_widgets"]["widget"][fixtures.wid(1)]
        self.assertNotIn("key", widget["settings"])
        self.assertFalse(self.noctalia.validated)


if __name__ == "__main__":
    unittest.main()
