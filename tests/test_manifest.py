"""The manifest against everything that has to agree with it.

These are the checks that rot on their own as the plugin grows: a setting added
to `plugin.toml` with no translation shows up in Noctalia's settings panel as a
raw key, and a renamed entry id silently breaks the IPC in the README. Nothing
here runs the tool; it reads the files that ship.
"""

import json
import re
import shutil
import subprocess
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLUGIN = ROOT / "noctes"
MANIFEST = PLUGIN / "plugin.toml"
TRANSLATIONS = PLUGIN / "translations"


def manifest():
    with MANIFEST.open("rb") as handle:
        return tomllib.load(handle)


def setting_keys(data):
    """Every `label_key` and `description_key` the manifest refers to."""
    wanted = set()

    def walk(node):
        if isinstance(node, dict):
            for name, value in node.items():
                if name in ("label_key", "description_key") and isinstance(value, str):
                    wanted.add(value)
                else:
                    walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(data)
    return wanted


def flatten(tree, prefix=""):
    """A nested translation file as dotted keys."""
    flat = {}
    for name, value in tree.items():
        path = f"{prefix}{name}"
        if isinstance(value, dict):
            flat.update(flatten(value, f"{path}."))
        else:
            flat[path] = value
    return flat


class TestManifest(unittest.TestCase):
    def setUp(self):
        self.data = manifest()

    def test_it_parses(self):
        self.assertIn("id", self.data)

    def test_the_id_matches_the_directory(self):
        self.assertEqual(self.data["id"].split("/", 1)[1], PLUGIN.name)

    def test_the_version_is_semver(self):
        self.assertRegex(self.data["version"], r"^\d+\.\d+\.\d+$")

    def test_the_files_the_submission_requires_are_all_here(self):
        for name in ("plugin.toml", "README.md", "translations/en.json"):
            self.assertTrue((PLUGIN / name).exists(), f"missing {name}")

    def test_every_entry_points_at_a_file_that_exists(self):
        groups = ("service", "widget", "panel", "desktop_widget")
        entries = [(group, entry) for group in groups for entry in self.data.get(group, [])]
        # Every group this manifest declares, so a group renamed in the host's
        # schema cannot leave its entries silently unchecked here again.
        self.assertEqual({group for group, _ in entries}, set(groups))
        for group, entry in entries:
            with self.subTest(f"{group}:{entry.get('id')}"):
                self.assertTrue((PLUGIN / entry["entry"]).exists(), f"missing {entry['entry']}")

    @unittest.skipUnless(shutil.which("noctalia"), "no noctalia binary to lint with")
    def test_the_host_linter_is_clean(self):
        # Cross-checks every declared setting against the getConfig calls in the
        # code: a setting read but not declared, or declared and never read.
        run = subprocess.run(["noctalia", "plugins", "lint", str(PLUGIN)],
                             capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        self.assertIn("0 errors, 0 warnings", run.stdout, run.stdout)

    def test_the_bundled_font_default_exists(self):
        fonts = [s for s in self._all_settings() if s.get("key") == "font_path"]
        self.assertTrue(fonts, "no font_path setting to check")
        self.assertTrue((PLUGIN / fonts[0]["default"]).exists())

    def _all_settings(self):
        found = []

        def walk(node):
            if isinstance(node, dict):
                if "key" in node and "type" in node:
                    found.append(node)
                for value in node.values():
                    walk(value)
            elif isinstance(node, list):
                for item in node:
                    walk(item)

        walk(self.data)
        return found

    def test_setting_types_are_ones_the_host_knows(self):
        # `float` is not one of them: the host spells it `double`, and a wrong
        # type here is invisible until the settings panel renders nothing.
        allowed = {"bool", "int", "double", "string", "select", "color"}
        for setting in self._all_settings():
            self.assertIn(setting["type"], allowed,
                          f"{setting['key']}: unknown type {setting['type']}")

    def test_every_setting_has_a_default(self):
        for setting in self._all_settings():
            self.assertIn("default", setting, f"{setting['key']}: no default")


class TestTranslations(unittest.TestCase):
    def setUp(self):
        self.wanted = setting_keys(manifest())
        self.files = sorted(TRANSLATIONS.glob("*.json"))

    def test_there_is_at_least_english(self):
        self.assertIn("en.json", [p.name for p in self.files])

    def test_every_file_is_valid_json(self):
        for path in self.files:
            with self.subTest(path.name):
                json.loads(path.read_text())

    def test_every_key_the_manifest_asks_for_is_translated(self):
        for path in self.files:
            flat = flatten(json.loads(path.read_text()))
            missing = sorted(self.wanted - set(flat))
            with self.subTest(path.name):
                self.assertEqual(missing, [], f"{path.name} is missing {missing}")

    def test_the_locales_agree_on_which_keys_exist(self):
        # A key in one file and not the other means one language falls back to
        # a raw dotted string in the panel.
        sets = {path.name: set(flatten(json.loads(path.read_text()))) for path in self.files}
        english = sets.get("en.json", set())
        for name, keys in sets.items():
            with self.subTest(name):
                self.assertEqual(sorted(keys ^ english), [])

    def test_every_translation_is_used(self):
        # A key nothing asks for is a string translated into every locale for
        # nobody. Plural keys are asked for by their stem, through trp.
        code = MANIFEST.read_text() + "".join(p.read_text() for p in PLUGIN.glob("*.luau"))
        english = flatten(json.loads((TRANSLATIONS / "en.json").read_text()))
        for key in english:
            stem = re.sub(r"\.(one|other)$", "", key)
            with self.subTest(key):
                self.assertIn(f'"{stem}"', code, f"{key} is never used")

    def test_every_key_the_code_asks_for_is_translated(self):
        english = flatten(json.loads((TRANSLATIONS / "en.json").read_text()))
        stems = set(english) | {re.sub(r"\.(one|other)$", "", k) for k in english}
        for path in PLUGIN.glob("*.luau"):
            for key in re.findall(r'noctalia\.trp?\("([^"]+)"', path.read_text()):
                with self.subTest(f"{path.name}:{key}"):
                    self.assertIn(key, stems)

    def test_no_translation_is_left_empty(self):
        for path in self.files:
            for key, value in flatten(json.loads(path.read_text())).items():
                with self.subTest(f"{path.name}:{key}"):
                    self.assertTrue(str(value).strip())


class TestDocumentation(unittest.TestCase):
    """The README is what a reviewer reads, and it goes stale quietly."""

    def setUp(self):
        self.data = manifest()
        self.plugin_readme = (PLUGIN / "README.md").read_text()
        self.repo_readme = (ROOT / "README.md").read_text()

    def test_the_readme_names_the_plugin_id(self):
        self.assertIn(self.data["id"], self.plugin_readme)

    def test_every_documented_tool_path_exists(self):
        # The manifest comments and both READMEs point at helper scripts. A
        # renamed one leaves a path that reads as real and is not.
        haystack = self.plugin_readme + self.repo_readme + MANIFEST.read_text()
        for path in set(re.findall(r"tools/[a-z0-9][a-z0-9._-]*", haystack)):
            with self.subTest(path):
                self.assertTrue((PLUGIN / path).exists(), f"{path} does not ship")

    def test_documented_ipc_commands_are_ones_the_service_handles(self):
        service = (PLUGIN / "service.luau").read_text()
        commands = set(re.findall(
            r"noctalia msg plugin remo/noctes:service all (\w+)", self.repo_readme
        ))
        self.assertTrue(commands, "no IPC commands documented")
        for command in commands:
            with self.subTest(command):
                self.assertIn(f'"{command}"', service)


if __name__ == "__main__":
    unittest.main()
