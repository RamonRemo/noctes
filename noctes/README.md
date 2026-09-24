# Noctes

Sticky notes pinned to the desktop, with a bar widget and a panel for editing.

| | |
| --- | --- |
| Id | `remo/noctes` |
| Entries | Service: `service`; bar widget: `bar`; panel: `panel`; desktop widget: `note` |

## Paper: dynamic by default, fixed on request

A note with no color of its own is **dynamic**: it generates its paper from its
key. Picking one of the eight named colors makes it **fixed** - that sheet stays
that color whatever the theme does, because picking "yellow" and watching it
turn green with the next wallpaper is not a color choice, it is a surprise.

**Paper follows the theme** (on by default) decides what dynamic means: on, the
sheets are painted from the Noctalia palette; off, from the classic papers. On a
generated scheme the palette tracks the wallpaper, so the whole wall recolors
when the wallpaper changes - the host resolves role names live, so nothing has
to reload.

There is also a **black** paper, the one sheet written in white ink rather than
dark, and a **glass** paper: a white veil at about a third alpha with a
hairline edge, text in `on_surface` so it flips with the scheme. The sheet reads
as a translucent pane rather than coloured paper. It is sharp, not frosted - the
plugin API exposes no blur, and noctalia's own blur is wired to its panels, not
to plugin widgets.

A dynamic sheet draws from four palette roles: `primary`, `secondary`,
`tertiary` and `error`, each with its own `on_*` for the text. Deliberately not
`surface_variant` - that is the panel background of whatever scheme is loaded,
so on a dark one it hands back a near-black sheet that reads as an unstyled UI
card rather than paper. Four looks instead of more is the better trade.

The picker's first chip is the dynamic one and the default; the rest are the
fixed papers. Every chip shows the color the sheet would actually be, and a
caption under the row says which mode the note is in. That caption is where a
tooltip would normally go: `tooltip` on a box or a flex container needs plugin
API 32, and this shell rejects a manifest above what it supports.

Toggling the switch repaints every sheet at once. Editing the plugin's `.luau`
files is different: a hot reload does not always reach every desktop widget
already on screen, and a sheet left on the old code keeps its old look until

```sh
noctalia msg plugins disable remo/noctes && noctalia msg plugins enable remo/noctes
```

## Adding one

The panel's **New** button creates the note *and* its desktop widget in one
click, already tilted, colored and without the host background, so every note
has paper on the desk, and deleting a note takes its sheet off the desktop too.
Same thing over IPC:

```sh
noctalia msg plugin remo/noctes:service all desk
```

The desktop-widget editor still works: its sheets arrive untilted, keyless and
framed, and the service adopts them.

A note made while python3 was missing has no sheet, and the panel says so where
it would name the screen.

Screenshots, the pitch and a walk through the first setup are in the
[repository README](../README.md). The host quirks this code is shaped around
are collected in [`docs/plugin-notes.md`](../docs/plugin-notes.md).

## One post-it per widget

A desktop widget instance is one note, not a board. Add a second widget for a
second note, a third for a third. Each instance is bound to a note by its `key`
setting: a short handle such as `shopping` or `work`, which keeps the binding
stable no matter how the note list reorders.

The key exists because a desktop widget has no identity of its own - the host
hands a widget entry no id, so two sheets run the same code with no way to tell
themselves apart, and the only thing that differs between them is their own
settings. Nobody has to type one: creating a post-it generates `nota-N`, and the field
is kept out of the widget editor. The host has no `hidden` flag, so it is hidden
by a `visible_when` that never matches.

A post-it whose key matches no note yet is blank; clicking it creates the note
and opens the editor.

## Why the editing lives in the panel

Noctalia desktop widgets are background layer-shell surfaces. They receive
clicks but **never keyboard focus**, so text cannot be typed into one. The paper
is a single click target that publishes its note on `noctes.editing`; the panel
is the only surface that can take the keyboard, and it does the typing.

All four entries are thin clients of the `service` entry, which owns the note
list and is the only one that touches disk. Writes are debounced onto a two
second tick, so a minute of typing costs a couple of writes rather than sixty.

The host wakes every watcher of a state key each time the key is set, whether
the value changed or not. So the service sets each key only when it changes -
no heartbeat, no republishing the unchanged keys next to the changed one - and
each sheet still checks that the note it shows is what changed before it
redraws.

## Making it look stuck to the screen

The declarative UI has no z-stacking and no blur, so the paper is built out of
plain flex nodes:

- **Drop shadow** - one thin, faint box down the right edge and one along the
  bottom, inset at the top-left so the sheet reads as lifted. It started as
  three stacked bands imitating a falloff; the host rotates the whole sheet, and
  rotating crisp stripes resampled them into a staircase, so what looked like a
  soft shadow up close looked like a black slab on screen. One low-alpha edge is
  both cleaner and more convincing. Every box needs an explicit width *and*
  height - one sized on a single axis paints nothing, silently.
- **Tape** - a translucent strip near the top edge, present and positioned by
  a choice derived from the key. Not a setting.
- **Paper color** - a note with no color of its own gets one derived from its
  key, plus a few points of per-note tint jitter, so a wall of post-its is not a
  wall of identical yellow.

Two things that matter for the look are host state, not plugin settings, so the
plugin cannot default them and cannot randomize them at creation:

- **Background: off.** Noctalia draws a rounded panel behind every desktop
  widget. Turn it off under "Background" in the widget's settings, or the paper
  sits inside a dark frame. A manifest-level default does not reach it.
- **Rotation.** The desktop-widget editor rotates a widget freely, in radians
  (`0.05` is about 3 degrees). A couple of degrees either way is what stops a
  row of post-its from looking like a grid.

The way around both is `tools/noctes-widget`, which edits that file directly.
Each change is written beside it first, checked with `noctalia config validate`,
and renamed into place only when it passes, so the shell never loads a file it
would reject; the shell sees the rename and reloads by itself. Commands take a
lock, so two started at once - a double click on **New** - run one after the
other instead of both editing the same original. It is the only thing here that
writes outside the plugin's own data directory.

Sheets added through Noctalia's widget editor arrive square, keyless and framed.
The service notices them on its next look at the settings file and adopts them:
a key, an angle unless the sheet was already turned, no frame. A sheet that
already has a key is left as its owner set it, square or framed. Once per start
the same pass also clears what an older noctes left behind: settings on its
sheets that the host would otherwise warn about on every load - it asks
`noctalia config validate` which ones are unknown, and removes only those, only
on noctes' own sheets - and the `settings.toml.bak-noctes*` backups older
versions wrote beside the settings file.

## Storage

`notes.json` in the folder given by the `save_path` setting, or in the plugin's
own data directory (`~/.local/state/noctalia/plugins/data/remo/noctes`) when
that setting is empty. The file is `{ "version": 1, "notes": [ ... ] }`, safe to
edit by hand while Noctalia is not running, or followed by an IPC `reload`. A
bare array and a file with no `version` both still load, so a file written by an
older noctes is read as it is.

A `notes.json` that will not parse - a hand edit one comma short - is never
written over. It is renamed to `notes.json.unreadable-<time>`, a notification
names it, and the notes in memory carry on in a fresh `notes.json`. If it cannot
even be renamed, nothing is saved until it loads.

Pointing `save_path` at a folder with no `notes.json` takes the current notes
along; pointing it at one that has notes shows those.

Every write goes to `notes.json.tmp` and is renamed over the real file, which is
the one filesystem operation that either happens or does not: a crash, a full
disk or the OOM killer leaves the previous file whole rather than half a JSON
document. A `.tmp` left behind with no `notes.json` beside it is the newer copy,
and is adopted on the next load.

### Deleting

Deleting takes the note and its sheet together, and both are gone for good:
there is no trash and no undo. The bin asks twice - the first click arms it, the
second deletes - and that is the whole safety net a post-it gets.

Deleting a sheet in Noctalia's widget editor deletes its note too, the next time
the service reads the settings file: when the panel opens, or at the next start.
A note is only reached through its sheet, so one whose sheet is gone is a note
nobody would see again. Two things are never taken for a deletion: a sheet this
machine never had - a synced `notes.json` carries notes whose sheets live on
another machine - and every known sheet vanishing at once, which is a reset
settings file rather than someone deleting post-its. The notes stay in both
cases.

## Where sheets go

### Which screen a new sheet lands on

The panel sends the key of the note it is showing, and the new sheet lands on
that sheet's output, measured against that output's own logical size. The output
is read out of the settings file at that moment, so a sheet dragged to another
screen counts as being where it is now, not where it was when the panel opened.

The focused output is the fallback, for the first sheet and for the `desk` IPC
event, and it is only a fallback: it follows the focused window, and neither a
post-it nor the panel takes window focus, so on its own it puts every new sheet
on the screen last typed in.

Sheets never move on their own, so a monitor layout that changes does not drag
the existing wall along: old sheets stay where they were put.

### Sheets on a screen that went away

A widget bound to a connector the compositor no longer reports is drawn nowhere:
the note exists, the sheet exists, and nothing shows. Unplugging a monitor
therefore triggers `gather`, which moves exactly those sheets to a connected
output and leaves every other one where its owner put it.

A connector also disappears for reasons that are not an unplug: a monitor
switched off, a KVM switched away. So `gather` remembers where each sheet it
moved was, in `homes.json` in the plugin's data directory, and when that output
is connected again the sheets go back to exactly where they were. By hand:

```sh
noctalia msg plugin remo/noctes:service all gather
```

## Settings

### Plugin

| Setting | Type | Default | Description |
| --- | --- | --- | --- |
| `default_color` | `select` | `auto` | Color new notes get; automatic leaves it to the post-it's key. |
| `paper_opacity` | `double` | `0.96` | How solid every post-it is; the text stays fully opaque. Step 0.02. |
| `tilt` | `bool` | `true` | Sheets sit at a small random angle. Off squares every one; on gives each a new angle. |
| `theme_colors` | `bool` | `true` | Paint every post-it from the Noctalia palette, which tracks the wallpaper. |
| `save_path` | `string` | *(empty)* | Folder for `notes.json`; empty uses the plugin data directory. |

### Bar widget

| Setting | Type | Default | Description |
| --- | --- | --- | --- |
| `show_count` | `bool` | `true` | Show the note count next to the glyph. |

### Desktop widget

| Setting | Type | Default | Description |
| --- | --- | --- | --- |
| `key` | `string` | *(empty)* | Which note this post-it shows. Generated, and hidden from the editor. |
| `paper_width` | `int` | `220` | Paper width in px. |
| `paper_height` | `int` | `200` | Paper height in px. |
| `font_size` | `int` | `16` | Body font size; the title is three points larger. A handwriting font needs more size than a UI font to stay legible. |
| `font_path` | `string` | `PatrickHand-Regular.ttf` | Font the note is drawn in. Plugin-relative, absolute or `~` path; empty falls back to the shell font. |

Every desktop-widget setting is per instance, so each post-it on the desktop can
look different from the next. What belongs to the note rather than to the sheet
is not here: the paper color is picked in the panel, and the opacity and the
theme switch are plugin-wide, so each of those has one home and one control.

## Languages

English, Portuguese (Brazil), Spanish, French, German, Italian, Dutch, Polish,
Russian, Ukrainian, Turkish, Japanese, Korean and Simplified Chinese, picked by
the shell's own language setting. A file in `translations/` is named after the
shell's language code exactly (`pt-BR`, `zh-Hans`); there is no fallback from
`pt` to `pt-BR`, so a language the shell does not name the same way stays in
English.

## Bundled font

`PatrickHand-Regular.ttf` ships with the plugin and is the default, because
handwriting is most of what separates a post-it from a UI card. It is Patrick
Hand by Patrick Wagesreiter, under the SIL Open Font License 1.1; the license
is `PatrickHand-OFL.txt` next to it. Point `font_path` somewhere else, or clear
it to use the shell font.

## Dependencies

`python3`, for `tools/noctes-widget`: the only thing that writes outside the
plugin's own data directory. It edits `settings.toml` through a candidate file
that `noctalia config validate` has to pass before it replaces the real one.
Besides the helper, the plugin only ever runs `noctalia` itself, to open the
widget editor. No network calls.

Only the paper needs it. The service asks once at startup whether the helper
runs at all, and without it the notes still open, save and edit: **New** creates
a note with no sheet, and the panel says so.

A note that has a key but no sheet on this machine - from a synced
`notes.json`, say - gets paper by key:

```sh
noctalia msg plugin remo/noctes:service all stick work
```
