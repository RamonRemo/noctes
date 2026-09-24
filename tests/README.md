# Tests

```sh
tests/run              # everything
tests/run test_commit  # one module
tests/run -v           # name each test
```

Python's standard library, plus Lua 5.4 for the Luau modules (skipped when
there is none), and no test runner to install. They live outside `noctes/` on
purpose: that directory is what ships to
[community-plugins](https://github.com/noctalia-dev/community-plugins), and
nothing here belongs in a user's plugin folder.

## What is covered

| Module | What it holds |
| --- | --- |
| `test_parsing.py` | The line and span reader `noctes-widget` is built on: finding widgets, reading a key out of a table, working out where an insertion goes, picking a free key, an id, an output and a spot on screen. No writes. |
| `test_commands.py` | `add`, `remove`, `tilt`, `scatter` and `gather` against a settings file in a temp directory, with `widget_order` in both shapes the shell writes. |
| `test_commit.py` | The write guard: the candidate is validated before it replaces anything, a rejected one changes nothing, nothing is left behind, and two helpers started together cannot undo each other - that last one with two real processes. |
| `test_manifest.py` | `plugin.toml` against the files, translations and documentation that have to agree with it, and `noctalia plugins lint` when the binary is installed. Reads only. |
| `test_luau.py` | Runs `lua/test_*.lua`: `store.luau`, `service.luau` with `desk.luau` under it, and the panel, sheet and bar, under Lua 5.4. |

`fixtures.py` builds settings files shaped like Noctalia's own. `harness.py`
loads the tool and takes the dangerous parts away from it; its stand-in for
`noctalia config validate` rejects a candidate that does not parse.

`lua/host.lua` stands in for the shell. The plugin's Luau uses no syntax Lua
5.4 cannot read, so the real files run unchanged, each entry in its own globals
the way each runs in its own VM. Where the shell's behaviour is the thing under
test, the stand-in copies it: `state.set` wakes every watcher on every call,
changed value or not, and delivers later rather than inside the call;
`runAsync` answers when a test says so.

## What is not covered

**The real host.** `lua/host.lua` is a model of the shell, built from reading
its source, not the shell itself. Behaviour it does not model - layout, input
focus, what a widget looks like - is still tested by hand, with the logs on
(see `docs/plugin-notes.md`).

**Anything drawn.** Whether paper looks like paper is a screenshot question.

## The two things worth keeping

**Every write has to parse.** A `settings.toml` that does not parse is one the
shell refuses to load, so the change never takes effect. `assertValidToml` runs
after every command that writes, and a new test for a new command should call it
too.

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
the shell to do, `self.noctalia.validated` whether it tried to write at all, and
`self.files()` what it left in the state directory.

A Luau test is a function passed to `T.test` in one of the `lua/test_*.lua`
files. `NOCTES_PLUGIN=<copy of noctes/>` runs them against another copy of the
plugin: revert a fix there, and the test written for it has to fail.

A fixed bug is worth a test that fails against the old code. Both findings from
[community-plugins#828](https://github.com/noctalia-dev/community-plugins/pull/828)
have one: `TestNothingLeftBehind` for the backup that accumulated per day, and
`test_setting_types_are_ones_the_host_knows` plus
`test_every_documented_tool_path_exists` for the manifest.
