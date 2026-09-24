"""The five subcommands, against a settings file in a temp directory.

Every one of these asserts the result still parses as TOML. A settings file
that does not parse is one the shell refuses to load, so "the tool never writes
something unparseable" is the invariant worth guarding hardest.
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

    def test_it_lands_on_the_screen_it_was_asked_for(self):
        # Not on the screen the other sheets are on: the caller sends the output
        # someone is looking at, and a new sheet has to appear there.
        self.write(fixtures.settings([
            fixtures.sheet(fixtures.wid(1), key="a", output="HDMI-A-1"),
        ]))
        self.run_tool("add", "--output", "DP-2", "--screen", "3440x1440")

        widgets = self.assertValidToml()["desktop_widgets"]["widget"]
        fresh = [w for wid, w in widgets.items() if wid != fixtures.wid(1)]
        self.assertEqual(fresh[0]["output"], "DP-2")
        self.assertEqual(widgets[fixtures.wid(1)]["output"], "HDMI-A-1")

    def test_near_lands_on_the_screen_that_sheet_is_on(self):
        # The reason --near exists: clicking a sheet or the panel never moves
        # window focus, so the output the caller sends is the screen holding
        # whatever window is open behind them, not the one being looked at.
        self.write(fixtures.settings([
            fixtures.sheet(fixtures.wid(1), key="a", output="HDMI-A-1"),
        ]))
        self.run_tool("add", "--output", "DP-2", "--screen", "3440x1440",
                      "--near", "a")

        widgets = self.assertValidToml()["desktop_widgets"]["widget"]
        fresh = [w for wid, w in widgets.items() if wid != fixtures.wid(1)][0]
        self.assertEqual(fresh["output"], "HDMI-A-1")

    def test_near_measures_against_that_screens_own_size(self):
        self.write(fixtures.settings([
            fixtures.sheet(fixtures.wid(1), key="a", output="HDMI-A-1"),
        ]))
        self.run_tool("add", "--output", "DP-2", "--screen", "3440x1440",
                      "--near", "a",
                      "--geometry", "DP-2=3440x1440,HDMI-A-1=1280x1024")

        widgets = self.assertValidToml()["desktop_widgets"]["widget"]
        fresh = [w for wid, w in widgets.items() if wid != fixtures.wid(1)][0]
        self.assertEqual(fresh["placement_width"], 1280.0)
        self.assertEqual(fresh["placement_height"], 1024.0)

    def test_near_a_key_with_no_sheet_uses_the_output_given(self):
        self.write(fixtures.settings([
            fixtures.sheet(fixtures.wid(1), key="a", output="HDMI-A-1"),
        ]))
        self.run_tool("add", "--output", "DP-2", "--screen", "3440x1440",
                      "--near", "gone")

        widgets = self.assertValidToml()["desktop_widgets"]["widget"]
        fresh = [w for wid, w in widgets.items() if wid != fixtures.wid(1)][0]
        self.assertEqual(fresh["output"], "DP-2")

    def test_an_unknown_target_screen_keeps_the_size_it_was_given(self):
        self.write(fixtures.settings([
            fixtures.sheet(fixtures.wid(1), key="a", output="HDMI-A-1"),
        ]))
        self.run_tool("add", "--output", "DP-2", "--screen", "3440x1440",
                      "--near", "a", "--geometry", "DP-2=3440x1440")

        widgets = self.assertValidToml()["desktop_widgets"]["widget"]
        fresh = [w for wid, w in widgets.items() if wid != fixtures.wid(1)][0]
        self.assertEqual(fresh["output"], "HDMI-A-1")
        self.assertEqual(fresh["placement_width"], 3440.0)

    def test_a_bad_geometry_entry_stops_before_writing(self):
        original = self.write(fixtures.settings([
            fixtures.sheet(fixtures.wid(1), key="a", output="HDMI-A-1"),
        ]))
        with self.assertRaises(SystemExit):
            self.run_tool("add", "--output", "DP-2", "--screen", "3440x1440",
                          "--near", "a", "--geometry", "HDMI-A-1=wide")
        self.assertEqual(self.read(), original)

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

    def test_the_output_is_printed_second(self):
        self.write(fixtures.settings())
        self.run_tool("add", "--output", "DP-2", "--screen", "3440x1440", "--key", "work")
        self.assertEqual(self.output.splitlines()[1], "output=DP-2")

    def test_a_key_already_on_the_desk_gets_no_second_sheet(self):
        # A double click on "put on the desk" sends the same key twice.
        original = self.write(fixtures.settings([
            fixtures.sheet(fixtures.wid(1), key="work", output="HDMI-A-1"),
        ]))
        self.run_tool("add", "--output", "DP-2", "--screen", "3440x1440", "--key", "work")

        self.assertEqual(self.read(), original)
        self.assertEqual(self.output.splitlines()[:2], ["key=work", "output=HDMI-A-1"])

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


class TestOrderShapes(ToolCase):
    """widget_order as the shell actually writes it: on one line for up to two
    widgets, wrapped past that, and not there at all on a fresh install."""

    def test_add_extends_a_one_line_order(self):
        self.write(fixtures.settings([fixtures.foreign(fixtures.wid(1))], inline=True))
        self.run_tool("add", "--output", "DP-2", "--screen", "3440x1440")

        desktop = self.assertValidToml()["desktop_widgets"]
        self.assertEqual(desktop["widget_order"], [fixtures.wid(1), fixtures.wid(2)])
        self.assertIn(fixtures.wid(2), desktop["widget"])

    def test_add_on_a_fresh_install_creates_the_table(self):
        self.write('[bar]\nposition = "top"\n\n[dock]\nenabled = false\n')
        self.run_tool("add", "--output", "DP-2", "--screen", "3440x1440")

        parsed = self.assertValidToml()
        desktop = parsed["desktop_widgets"]
        self.assertEqual(desktop["widget_order"], [fixtures.wid(1)])
        self.assertEqual(desktop["widget"][fixtures.wid(1)]["settings"]["key"], "nota-1")
        self.assertEqual(desktop["schema_version"], 2)
        self.assertIs(parsed["dock"]["enabled"], False)

    def test_add_when_the_table_has_no_order_yet(self):
        self.write('[desktop_widgets]\nschema_version = 2\n\n[dock]\nenabled = false\n')
        self.run_tool("add", "--output", "DP-2", "--screen", "3440x1440")

        desktop = self.assertValidToml()["desktop_widgets"]
        self.assertEqual(desktop["widget_order"], [fixtures.wid(1)])

    def test_add_to_a_file_with_no_trailing_newline(self):
        self.write(fixtures.settings().rstrip("\n"))
        self.run_tool("add", "--output", "DP-2", "--screen", "3440x1440")
        self.assertIn(fixtures.wid(1), self.assertValidToml()["desktop_widgets"]["widget"])

    def test_remove_takes_the_id_out_of_a_one_line_order(self):
        self.write(fixtures.settings([
            fixtures.sheet(fixtures.wid(1), key="drop"),
            fixtures.foreign(fixtures.wid(2)),
        ], inline=True))
        self.run_tool("remove", "--key", "drop")

        desktop = self.assertValidToml()["desktop_widgets"]
        self.assertEqual(desktop["widget_order"], [fixtures.wid(2)])

    def test_the_lockscreen_order_is_never_the_one_edited(self):
        # Its widget_order is wrapped with three entries while the desktop one
        # is on a single line: an unscoped match finds the lockscreen array.
        self.write(fixtures.settings([fixtures.foreign(fixtures.wid(1))],
                                     inline=True, lockscreen="wrapped"))
        self.run_tool("add", "--output", "DP-2", "--screen", "3440x1440", "--key", "k")

        parsed = self.assertValidToml()
        self.assertEqual(parsed["lockscreen_widgets"]["widget_order"], fixtures.LOCKSCREEN_IDS)
        self.assertEqual(parsed["desktop_widgets"]["widget_order"],
                         [fixtures.wid(1), fixtures.wid(2)])

        self.run_tool("remove", "--key", "k")

        parsed = self.assertValidToml()
        self.assertEqual(parsed["lockscreen_widgets"]["widget_order"], fixtures.LOCKSCREEN_IDS)
        self.assertEqual(parsed["desktop_widgets"]["widget_order"], [fixtures.wid(1)])


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

    def test_a_keyed_sheet_squared_by_hand_stays_square(self):
        # A keyed sheet was placed by `add` or adopted before, so a square one
        # is square because its owner made it so in the editor.
        original = self.write(fixtures.settings([
            fixtures.sheet(fixtures.wid(1), key="a", rotation=0.0),
            fixtures.sheet(fixtures.wid(2), key="", background=True),
        ]))
        self.run_tool("scatter")

        widgets = self.assertValidToml()["desktop_widgets"]["widget"]
        self.assertEqual(widgets[fixtures.wid(1)]["rotation"], 0.0)
        self.assertNotEqual(self.read(), original)

    def test_a_keyed_sheet_framed_by_hand_keeps_its_frame(self):
        self.write(fixtures.settings([
            fixtures.sheet(fixtures.wid(1), key="a", background=True, rotation=0.03),
        ]))
        self.run_tool("scatter")

        widget = self.assertValidToml()["desktop_widgets"]["widget"][fixtures.wid(1)]
        self.assertIs(widget["settings"]["background"], True)
        self.assertFalse(self.noctalia.validated)

    def test_all_redoes_keyed_sheets_too(self):
        self.write(fixtures.settings([
            fixtures.sheet(fixtures.wid(1), key="a", background=True, rotation=0.0),
        ]))
        self.run_tool("scatter", "--all")

        widget = self.assertValidToml()["desktop_widgets"]["widget"][fixtures.wid(1)]
        self.assertIs(widget["settings"]["background"], False)
        self.assertNotEqual(widget["rotation"], 0.0)
        self.assertEqual(widget["settings"]["key"], "a")

    def test_an_adopted_key_avoids_the_keys_the_caller_holds(self):
        # A note whose sheet was deleted in the editor still holds its key. A
        # new sheet taking that key would show the old note instead of a blank.
        self.write(fixtures.settings([
            fixtures.sheet(fixtures.wid(1), key="", background=True),
        ]))
        self.run_tool("scatter", "--avoid", "nota-1,nota-2")

        widget = self.assertValidToml()["desktop_widgets"]["widget"][fixtures.wid(1)]
        self.assertEqual(widget["settings"]["key"], "nota-3")

    def test_a_sheet_turned_in_the_editor_keeps_its_angle(self):
        self.write(fixtures.settings([
            fixtures.sheet(fixtures.wid(1), key="", background=True, rotation=0.03),
        ]))
        self.run_tool("scatter")

        widget = self.assertValidToml()["desktop_widgets"]["widget"][fixtures.wid(1)]
        self.assertEqual(widget["rotation"], 0.03)
        self.assertEqual(widget["settings"]["key"], "nota-1")


class TestOldBackups(ToolCase):
    """Older versions backed settings.toml up beside itself, one file per day
    and later one fixed name. Nothing removed them."""

    def test_they_are_removed(self):
        self.write(fixtures.settings())
        for name in ("settings.toml.bak-noctes", "settings.toml.bak-noctes-2026-09-22"):
            (self.tmp / name).write_text("old")
        self.run_tool("scatter")
        self.assertEqual(self.files(), ["settings.toml"])
        self.assertFalse(self.noctalia.validated)

    def test_nobody_elses_backup_is_touched(self):
        self.write(fixtures.settings())
        for name in ("settings.toml.bak-screenshot-2026-09-14", "settings.toml.bak-noctes-mine",
                     "settings.toml.bak"):
            (self.tmp / name).write_text("theirs")
        self.run_tool("scatter")
        self.assertEqual(len(self.files()), 4)

    def test_dry_run_only_reports_them(self):
        self.write(fixtures.settings())
        (self.tmp / "settings.toml.bak-noctes").write_text("old")
        self.run_tool("scatter", "--dry-run")
        self.assertIn("settings.toml.bak-noctes", self.files())
        self.assertIn("remove old backup settings.toml.bak-noctes", self.output)


class TestStaleSettings(ToolCase):
    """Settings an older noctes wrote, which the host now flags as unknown.

    The keys are made up rather than real retired ones, so the tests do not
    depend on what the manifest happens to declare today."""

    def warn(self, wid, key):
        return (f"WARN  {self.settings}:1:1: desktop_widgets.widget.{wid}"
                f".settings.{key}: unknown setting\n")

    def with_extra(self, wid, extra, **kwargs):
        sheet_id, block = fixtures.sheet(wid, **kwargs)
        return sheet_id, block + "".join(f"        {line}\n" for line in extra)

    def test_a_setting_the_manifest_dropped_is_removed(self):
        self.write(fixtures.settings([
            self.with_extra(fixtures.wid(1), ['retired_one = "none"', "retired_two = 14"],
                            key="a", rotation=0.03),
        ]))
        self.noctalia.validate_stdout = (self.warn(fixtures.wid(1), "retired_one")
                                         + self.warn(fixtures.wid(1), "retired_two"))
        self.run_tool("scatter")

        settings = self.assertValidToml()["desktop_widgets"]["widget"][fixtures.wid(1)]["settings"]
        self.assertEqual(settings, {"background": False, "key": "a"})

    def test_another_plugins_settings_are_never_pruned(self):
        original = self.write(fixtures.settings([fixtures.foreign(fixtures.wid(1))]))
        self.noctalia.validate_stdout = self.warn(fixtures.wid(1), "stat")
        self.run_tool("scatter")
        self.assertEqual(self.read(), original)

    def test_nothing_is_pruned_when_the_host_does_not_know_the_plugin(self):
        # If `key` itself is flagged, the host has not loaded noctes' schema and
        # every setting looks unknown. Pruning then would unbind every sheet.
        original = self.write(fixtures.settings([
            self.with_extra(fixtures.wid(1), ['retired_one = "none"'], key="a", rotation=0.03),
        ]))
        self.noctalia.validate_stdout = (self.warn(fixtures.wid(1), "key")
                                         + self.warn(fixtures.wid(1), "retired_one"))
        self.run_tool("scatter")
        self.assertEqual(self.read(), original)

    def test_dry_run_reports_the_prune_without_writing(self):
        original = self.write(fixtures.settings([
            self.with_extra(fixtures.wid(1), ['retired_one = "none"'], key="a", rotation=0.03),
        ]))
        self.noctalia.validate_stdout = self.warn(fixtures.wid(1), "retired_one")
        self.run_tool("scatter", "--dry-run")

        self.assertEqual(self.read(), original)
        self.assertIn("drop retired_one", self.output)


class TestGather(ToolCase):
    """A monitor that goes away leaves its sheets bound to a connector nothing
    draws: the notes are there, the widgets are there, and nothing shows.
    """

    def gather(self, *extra, live="DP-2", onto="DP-2"):
        return self.run_tool("gather", "--outputs", live, "--output", onto,
                             "--screen", "3440x1440", *extra)

    def test_a_sheet_on_a_dead_output_comes_home(self):
        self.write(fixtures.settings([
            fixtures.sheet(fixtures.wid(1), key="shopping", output="HDMI-A-1"),
        ]))
        self.gather()

        widget = self.assertValidToml()["desktop_widgets"]["widget"][fixtures.wid(1)]
        self.assertEqual(widget["output"], "DP-2")
        self.assertEqual(widget["settings"]["key"], "shopping")

    def test_a_sheet_on_a_live_output_is_left_alone(self):
        # This runs on every output change, so staying put has to be free.
        original = self.write(fixtures.settings([
            fixtures.sheet(fixtures.wid(1), key="a", output="DP-2", cx=900.0, cy=400.0),
        ]))
        self.gather(live="DP-2,HDMI-A-1")

        self.assertEqual(self.read(), original)
        self.assertFalse(self.noctalia.validated)

    def test_it_keeps_the_angle_and_the_key(self):
        self.write(fixtures.settings([
            fixtures.sheet(fixtures.wid(1), key="shopping", output="DP-9", rotation=0.037),
        ]))
        self.gather()

        widget = self.assertValidToml()["desktop_widgets"]["widget"][fixtures.wid(1)]
        self.assertEqual(widget["rotation"], 0.037)
        self.assertEqual(widget["settings"]["key"], "shopping")

    def test_it_re_places_against_the_screen_it_moves_to(self):
        # The old position was measured against a screen that is not there.
        self.write(fixtures.settings([
            fixtures.sheet(fixtures.wid(1), key="a", output="DP-9", cx=5000.0, cy=3000.0),
        ]))
        self.gather()

        widget = self.assertValidToml()["desktop_widgets"]["widget"][fixtures.wid(1)]
        self.assertLess(widget["cx"], 3440.0)
        self.assertLess(widget["cy"], 1440.0)
        self.assertEqual(widget["placement_width"], 3440.0)
        self.assertEqual(widget["placement_height"], 1440.0)

    def test_two_adrift_sheets_do_not_stack(self):
        self.write(fixtures.settings([
            fixtures.sheet(fixtures.wid(1), key="a", output="DP-9", cx=100.0, cy=100.0),
            fixtures.sheet(fixtures.wid(2), key="b", output="DP-9", cx=100.0, cy=100.0),
        ]))
        self.gather()

        widgets = self.assertValidToml()["desktop_widgets"]["widget"]
        spots = [(w["cx"], w["cy"]) for w in widgets.values()]
        self.assertEqual(len(set(spots)), 2)

    def test_it_never_moves_another_plugins_widget(self):
        self.write(fixtures.settings([fixtures.foreign(fixtures.wid(1), output="DP-9")]))
        self.gather()

        widget = self.assertValidToml()["desktop_widgets"]["widget"][fixtures.wid(1)]
        self.assertEqual(widget["output"], "DP-9")
        self.assertFalse(self.noctalia.validated)

    def test_dry_run_reports_without_writing(self):
        original = self.write(fixtures.settings([
            fixtures.sheet(fixtures.wid(1), key="a", output="DP-9"),
        ]))
        self.gather("--dry-run")

        self.assertEqual(self.read(), original)
        self.assertFalse(self.noctalia.validated)
        self.assertIn("DP-9 -> DP-2", self.output)

    def test_a_sheet_goes_home_when_its_output_returns(self):
        # A monitor switched off can drop off the output list like an unplugged
        # one. When it is back, so is the wall its owner arranged on it.
        self.write(fixtures.settings([
            fixtures.sheet(fixtures.wid(1), key="a", output="HDMI-A-1", cx=900.0, cy=400.0),
        ]))
        homes = self.tmp / "homes.json"
        self.gather("--homes", str(homes))
        moved = self.assertValidToml()["desktop_widgets"]["widget"][fixtures.wid(1)]
        self.assertEqual(moved["output"], "DP-2")
        self.assertTrue(homes.exists())

        self.gather("--homes", str(homes), live="DP-2,HDMI-A-1")

        back = self.assertValidToml()["desktop_widgets"]["widget"][fixtures.wid(1)]
        self.assertEqual(back["output"], "HDMI-A-1")
        self.assertEqual((back["cx"], back["cy"]), (900.0, 400.0))
        self.assertEqual((back["placement_width"], back["placement_height"]), (3440.0, 1440.0))
        self.assertFalse(homes.exists())

    def test_a_second_trip_keeps_the_first_home(self):
        self.write(fixtures.settings([
            fixtures.sheet(fixtures.wid(1), key="a", output="HDMI-A-1", cx=900.0, cy=400.0),
        ]))
        homes = self.tmp / "homes.json"
        self.gather("--homes", str(homes), live="DP-3", onto="DP-3")
        self.gather("--homes", str(homes), live="DP-2", onto="DP-2")
        self.gather("--homes", str(homes), live="DP-2,HDMI-A-1")

        back = self.assertValidToml()["desktop_widgets"]["widget"][fixtures.wid(1)]
        self.assertEqual((back["output"], back["cx"]), ("HDMI-A-1", 900.0))

    def test_a_sheet_moved_home_by_hand_is_just_forgotten(self):
        self.write(fixtures.settings([
            fixtures.sheet(fixtures.wid(1), key="a", output="HDMI-A-1", cx=900.0, cy=400.0),
        ]))
        homes = self.tmp / "homes.json"
        self.gather("--homes", str(homes))
        self.write(self.read().replace('output = "DP-2"', 'output = "HDMI-A-1"')
                   .replace("cx = 170.0", "cx = 50.0"))

        self.noctalia.seen_at_validate.clear()
        self.gather("--homes", str(homes), live="DP-2,HDMI-A-1")

        widget = self.assertValidToml()["desktop_widgets"]["widget"][fixtures.wid(1)]
        self.assertEqual(widget["cx"], 50.0)
        self.assertFalse(self.noctalia.validated)
        self.assertFalse(homes.exists())

    def test_the_home_of_a_deleted_sheet_is_dropped(self):
        self.write(fixtures.settings([
            fixtures.sheet(fixtures.wid(1), key="a", output="HDMI-A-1"),
        ]))
        homes = self.tmp / "homes.json"
        self.gather("--homes", str(homes))
        self.run_tool("remove", "--key", "a")
        self.gather("--homes", str(homes))
        self.assertFalse(homes.exists())

    def test_it_refuses_a_target_that_is_not_connected(self):
        self.write(fixtures.settings([
            fixtures.sheet(fixtures.wid(1), key="a", output="DP-9"),
        ]))
        with self.assertRaises(SystemExit):
            self.gather(live="DP-2", onto="HDMI-A-1")
        self.assertFalse(self.noctalia.validated)


if __name__ == "__main__":
    unittest.main()
