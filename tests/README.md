# Tests

```sh
tests/run              # everything
tests/run test_commit  # one module
tests/run -v           # name each test
```

Python standard library only, no dependencies, no test runner to install. They
live outside `noctes/` on purpose: that directory is what ships to
[community-plugins](https://github.com/noctalia-dev/community-plugins), and
nothing here belongs in a user's plugin folder.

## What is covered

| Module | What it holds |
| --- | --- |
| `test_parsing.py` | The line and span reader `noctes-widget` is built on: finding widgets, reading a key out of a table, working out where an insertion goes, picking a free key, an id, an output and a spot on screen. No writes. |
| `test_commands.py` | `add`, `remove`, `tilt` and `scatter` against a settings file in a temp directory. |
| `test_commit.py` | The write guard: back up, validate, restore on rejection, reload on success, and what the tool is allowed to touch. |
| `test_manifest.py` | `plugin.toml` against the files, translations and documentation that have to agree with it. Reads only. |

`fixtures.py` builds settings files shaped like Noctalia's own. `harness.py`
loads the tool and takes the dangerous parts away from it.

## What is not covered

**The Luau.** `service.luau`, `note.luau`, `panel.luau`, `bar.luau` and
`colors.luau` need the host runtime to do anything, and there is no headless
Noctalia to run them against. `luau-analyze` would at least typecheck them
against `noctalia.d.luau`, but that file is generated locally and gitignored, so
it is not something CI can do today. Changes there are still tested by hand.

**Anything drawn.** Whether paper looks like paper is a screenshot question.

## The two things worth keeping

**Every write has to parse.** Noctalia does not fail gracefully on a malformed
`settings.toml` - an unrecognised key breaks the parse and takes the shell down
with it. `assertValidToml` runs after every command that writes, and a new test
for a new command should call it too.

**The tool must not touch what is not ours.** The fixtures put another plugin's
widget next to noctes' own, and the tests assert it comes out unchanged. This
file belongs to the whole shell; noctes is a guest in it.

## Adding a test

`ToolCase` gives a temp settings file, a stubbed `noctalia`, and pinned random
angles so output is comparable. Build the input with `fixtures.settings(...)`:

```python
class TestSomething(ToolCase):
    def test_it_does_the_thing(self):
        self.write(fixtures.settings([
            fixtures.sheet(fixtures.wid(1), key="shopping"),
            fixtures.foreign(fixtures.wid(2)),          # must survive untouched
        ]))
        self.run_tool("tilt", "--square")

        parsed = self.assertValidToml()
        self.assertEqual(parsed["desktop_widgets"]["widget"][fixtures.wid(1)]["rotation"], 0.0)
```

`self.output` holds what the tool printed, `self.noctalia.calls` what it asked
the shell to do, and `self.backups()` what it left in the state directory.

A fixed bug is worth a test that fails against the old code. Both findings from
[community-plugins#828](https://github.com/noctalia-dev/community-plugins/pull/828)
have one: `TestBackup` for the backup that accumulated per day, and
`test_setting_types_are_ones_the_host_knows` plus
`test_every_documented_tool_path_exists` for the manifest.
