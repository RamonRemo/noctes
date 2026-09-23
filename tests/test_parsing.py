"""The settings file read as lines and spans.

Nothing here writes. These are the functions every command is built on, and a
wrong span here is how the tool ends up editing somebody else's widget.
"""

import unittest

import fixtures
from harness import ToolCase


class TestParse(ToolCase):
    def test_finds_widgets_in_document_order(self):
        text = fixtures.settings([
            fixtures.sheet(fixtures.wid(1), key="a"),
            fixtures.foreign(fixtures.wid(2)),
            fixtures.sheet(fixtures.wid(3), key="b"),
        ])
        found = [w.id for w in self.module.parse(text.splitlines(keepends=True))]
        self.assertEqual(found, [fixtures.wid(1), fixtures.wid(2), fixtures.wid(3)])

    def test_pairs_a_widget_with_its_settings_table(self):
        text = fixtures.settings([fixtures.sheet(fixtures.wid(1), key="a")])
        widget = self.module.parse(text.splitlines(keepends=True))[0]
        self.assertIsNotNone(widget.body)
        self.assertIsNotNone(widget.settings)

    def test_a_widget_with_no_settings_table_has_none(self):
        text = fixtures.settings([
            fixtures.sheet(fixtures.wid(1), settings_table=False),
        ])
        widget = self.module.parse(text.splitlines(keepends=True))[0]
        self.assertIsNotNone(widget.body)
        self.assertIsNone(widget.settings)

    def test_spans_cover_values_and_stop_at_the_next_table(self):
        text = fixtures.settings([
            fixtures.sheet(fixtures.wid(1), key="a"),
            fixtures.sheet(fixtures.wid(2), key="b"),
        ])
        lines = text.splitlines(keepends=True)
        first = self.module.parse(lines)[0]
        covered = "".join(lines[slice(*first.body)])
        self.assertIn("cx = ", covered)
        self.assertNotIn(fixtures.wid(2), covered)

    def test_an_empty_desktop_finds_nothing(self):
        self.assertEqual(self.module.parse(fixtures.settings().splitlines(keepends=True)), [])


class TestValueLookup(ToolCase):
    def setUp(self):
        super().setUp()
        self.text = fixtures.settings([
            fixtures.sheet(fixtures.wid(1), key="shopping", output="HDMI-A-1"),
        ])
        self.lines = self.text.splitlines(keepends=True)
        self.widget = self.module.parse(self.lines)[0]

    def test_returns_line_index_and_raw_value(self):
        index, raw = self.module.value(self.lines, self.widget.body, "cx")
        self.assertEqual(raw, "170.0")
        self.assertIn("cx", self.lines[index])

    def test_missing_key_is_none(self):
        self.assertIsNone(self.module.value(self.lines, self.widget.body, "nope"))

    def test_missing_span_is_none(self):
        self.assertIsNone(self.module.value(self.lines, None, "cx"))

    def test_text_of_strips_the_quotes(self):
        self.assertEqual(self.module.text_of(self.lines, self.widget.body, "output"), "HDMI-A-1")
        self.assertEqual(self.module.text_of(self.lines, self.widget.settings, "key"), "shopping")

    def test_text_of_is_empty_rather_than_none(self):
        self.assertEqual(self.module.text_of(self.lines, self.widget.settings, "nope"), "")

    def test_a_key_is_not_matched_inside_a_longer_one(self):
        # `cx` must not answer for `cx_offset`, or an edit lands on the wrong line.
        lines = ["    cx_offset = 9.0\n", "    cx = 170.0\n"]
        index, raw = self.module.value(lines, (0, 2), "cx")
        self.assertEqual((index, raw), (1, "170.0"))


class TestIndentAndInsertPoint(ToolCase):
    def test_indent_comes_from_the_span(self):
        text = fixtures.settings([fixtures.sheet(fixtures.wid(1), key="a")])
        lines = text.splitlines(keepends=True)
        widget = self.module.parse(lines)[0]
        self.assertEqual(self.module.indent_of(lines, widget.body, "?"), "    ")
        self.assertEqual(self.module.indent_of(lines, widget.settings, "?"), "        ")

    def test_indent_falls_back_when_there_is_no_span(self):
        self.assertEqual(self.module.indent_of([], None, "    "), "    ")

    def test_append_point_lands_inside_the_table(self):
        # Past the last value, not past the blank line that follows it: an
        # insertion after the blank would belong to the next table.
        lines = ["    a = 1\n", "    b = 2\n", "\n", "[next]\n"]
        self.assertEqual(self.module.append_point(lines, (0, 3)), 2)

    def test_append_point_of_no_span_is_none(self):
        self.assertIsNone(self.module.append_point([], None))


class TestNoteFilter(ToolCase):
    def test_only_noctes_widgets_count(self):
        text = fixtures.settings([
            fixtures.sheet(fixtures.wid(1), key="a"),
            fixtures.foreign(fixtures.wid(2), kind="sysmon"),
            fixtures.foreign(fixtures.wid(3), kind="remo/other:note"),
        ])
        found = [w.id for w in self.module.notes_in(text.splitlines(keepends=True))]
        self.assertEqual(found, [fixtures.wid(1)])

    def test_a_widget_with_no_type_is_not_a_note(self):
        lines = ["    [desktop_widgets.widget.x]\n", "    cx = 1.0\n"]
        self.assertEqual(self.module.notes_in(lines), [])


class TestTiltWanted(ToolCase):
    def test_true_when_the_plugin_has_no_settings_yet(self):
        self.assertTrue(self.module.tilt_wanted(fixtures.settings()))

    def test_reads_the_switch(self):
        self.assertTrue(self.module.tilt_wanted(fixtures.settings(plugin_tilt=True)))
        self.assertFalse(self.module.tilt_wanted(fixtures.settings(plugin_tilt=False)))

    def test_does_not_read_past_its_own_table(self):
        # A `tilt = false` belonging to another plugin must not straighten
        # these sheets.
        text = (
            '[plugin_settings."remo/noctes"]\n'
            'default_color = "auto"\n'
            "\n"
            '[plugin_settings."someone/else"]\n'
            "tilt = false\n"
        )
        self.assertTrue(self.module.tilt_wanted(text))


class TestKeyGeneration(ToolCase):
    def test_skips_keys_already_bound_to_a_sheet(self):
        text = fixtures.settings([
            fixtures.sheet(fixtures.wid(1), key="nota-1"),
            fixtures.sheet(fixtures.wid(2), key="nota-2"),
        ])
        key = self.module.free_key(text.splitlines(keepends=True), "nota", "")
        self.assertEqual(key, "nota-3")

    def test_skips_keys_the_caller_says_are_taken(self):
        # The service knows about notes that have no sheet yet; this file does not.
        text = fixtures.settings([fixtures.sheet(fixtures.wid(1), key="nota-1")])
        key = self.module.free_key(text.splitlines(keepends=True), "nota", "nota-2,nota-3")
        self.assertEqual(key, "nota-4")

    def test_an_empty_avoid_list_adds_nothing(self):
        key = self.module.free_key(fixtures.settings().splitlines(keepends=True), "nota", "")
        self.assertEqual(key, "nota-1")

    def test_honours_the_prefix(self):
        key = self.module.free_key(fixtures.settings().splitlines(keepends=True), "work", "")
        self.assertEqual(key, "work-1")


class TestWidgetId(ToolCase):
    def test_first_id_when_the_desktop_is_empty(self):
        self.assertEqual(self.module.next_widget_id(fixtures.settings()), fixtures.wid(1))

    def test_one_past_the_highest_in_use(self):
        text = fixtures.settings([
            fixtures.sheet(fixtures.wid(2), key="a"),
            fixtures.foreign(fixtures.wid(0x1F)),
        ])
        self.assertEqual(self.module.next_widget_id(text), fixtures.wid(0x20))

    def test_ids_stay_sixteen_hex_digits(self):
        self.assertRegex(self.module.next_widget_id(fixtures.settings()),
                         r"^desktop-widget-[0-9a-f]{16}$")


class TestBusiestOutput(ToolCase):
    def test_the_screen_holding_the_most_sheets_wins(self):
        text = fixtures.settings([
            fixtures.sheet(fixtures.wid(1), key="a", output="DP-2"),
            fixtures.sheet(fixtures.wid(2), key="b", output="DP-2"),
            fixtures.sheet(fixtures.wid(3), key="c", output="HDMI-A-1"),
        ])
        self.assertEqual(self.module.busiest_output(text.splitlines(keepends=True)), "DP-2")

    def test_none_when_there_are_no_sheets_yet(self):
        self.assertIsNone(self.module.busiest_output(fixtures.settings().splitlines(keepends=True)))

    def test_other_plugins_widgets_do_not_vote(self):
        text = fixtures.settings([
            fixtures.sheet(fixtures.wid(1), key="a", output="HDMI-A-1"),
            fixtures.foreign(fixtures.wid(2), output="DP-2"),
            fixtures.foreign(fixtures.wid(3), output="DP-2"),
        ])
        self.assertEqual(self.module.busiest_output(text.splitlines(keepends=True)), "HDMI-A-1")


class TestFreeSpot(ToolCase):
    def test_the_first_sheet_lands_on_the_margin(self):
        lines = fixtures.settings().splitlines(keepends=True)
        self.assertEqual(self.module.free_spot(lines, "DP-2", 3440, 1440),
                         (float(self.module.MARGIN), float(self.module.MARGIN)))

    def test_the_next_sheet_does_not_land_on_the_first(self):
        text = fixtures.settings([
            fixtures.sheet(fixtures.wid(1), key="a", cx=170.0, cy=170.0),
        ])
        spot = self.module.free_spot(text.splitlines(keepends=True), "DP-2", 3440, 1440)
        self.assertNotEqual(spot, (170.0, 170.0))

    def test_the_cascade_wraps_into_a_new_column(self):
        taken = [
            fixtures.sheet(fixtures.wid(n + 1), key=f"k{n}",
                           cx=float(self.module.MARGIN),
                           cy=float(self.module.MARGIN + n * self.module.CASCADE_Y))
            for n in range(self.module.PER_COLUMN)
        ]
        spot = self.module.free_spot(fixtures.settings(taken).splitlines(keepends=True),
                                     "DP-2", 3440, 1440)
        self.assertEqual(spot[0], float(self.module.MARGIN + self.module.CASCADE_X))

    def test_a_sheet_on_another_screen_does_not_block_a_spot(self):
        text = fixtures.settings([
            fixtures.sheet(fixtures.wid(1), key="a", output="HDMI-A-1", cx=170.0, cy=170.0),
        ])
        spot = self.module.free_spot(text.splitlines(keepends=True), "DP-2", 3440, 1440)
        self.assertEqual(spot, (170.0, 170.0))

    def test_a_spot_always_lands_on_screen(self):
        # Narrow enough that the cascade runs out and the random fallback takes over.
        lines = fixtures.settings().splitlines(keepends=True)
        for _ in range(20):
            cx, cy = self.module.free_spot(lines, "DP-2", 400, 300)
            self.assertGreaterEqual(cx, self.module.MARGIN)
            self.assertGreaterEqual(cy, self.module.MARGIN)


if __name__ == "__main__":
    unittest.main()
