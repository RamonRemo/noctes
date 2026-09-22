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
to reload. Each sheet can override the plugin-wide switch with its own
*Always* / *Never*.

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
click, already tilted, colored and without the host background. Everything in
the panel's list is therefore something that exists on screen, and deleting a
note takes its sheet off the desktop too. Same thing over IPC:

```sh
noctalia msg plugin remo/noctes:service all desk
```

The desktop-widget editor still works, and `tools/noctes-scatter` fixes up what
it produces (see below), but the editor's own output is always an untilted,
keyless, backgrounded sheet, because those three fields are host state a plugin
cannot set.

Screenshots and a walk through the first setup are in the
[repository README](../README.md).

## One post-it per widget

A desktop widget instance is one note, not a board. Add a second widget for a
second note, a third for a third. Each instance is bound to a note by its `key`
setting: a short handle such as `shopping` or `work`, which keeps the binding
stable no matter how the note list reorders.

The key exists because a desktop widget has no identity of its own - the host
hands a widget entry no id, so two sheets run the same code with no way to tell
themselves apart, and the only thing that differs between them is their own
settings. Nobody has to type one: creating a post-it generates `nota-N`, and so
do the stick button and `noctes-scatter`. Set one by hand only to point a
particular sheet at a particular note, in that widget's settings.

A post-it whose key matches no note yet is blank; clicking it creates the note
and opens the editor.

## Why the editing lives in the panel

Noctalia desktop widgets are background layer-shell surfaces. They receive
clicks but **never keyboard focus**, so text cannot be typed into one. The paper
is a single click target that publishes its note on `noctes.editing`; the panel
is the only surface that can take the keyboard, and it does the typing.

All four entries are thin clients of the `service` entry, which owns the note
list and is the only one that touches disk. Writes are debounced onto a two
second tick, so a minute of typing costs a couple of writes rather than sixty,
and each sheet skips redrawing when the publish that woke it did not change the
note it shows.

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
- **Folded corner** - off by default. The vocabulary has no rotation, no
  clipping and no vector primitive, so a diagonal can only be a stack of
  rectangles; at one pixel a step it is as smooth as it gets, and the host's
  rotation still resamples it into visible hatching. A dog-ear that reads as a
  rendering artifact is worse than no dog-ear. Still selectable per sheet, in
  either bottom corner.
- **Tape** - a translucent strip near the top edge, present and positioned by
  the same key-derived choice.
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

Two ways around that, both of which edit `settings.toml` directly:

- `noctes/tools/noctes-widget`, which the panel's New button runs. It appends
  the widget itself, so nothing needs fixing afterwards, and `remove --key`
  takes one back off.
- `tools/noctes-scatter`, for widgets that came from the desktop-widget editor.
  Its systemd path unit runs it whenever `settings.toml` changes, so an editor
  sheet is tilted, keyed and unbackgrounded a couple of seconds later.

The host centers a plugin widget's tree at its natural size, so the paper
carries its own size through `paper_width` / `paper_height` rather than
stretching to the widget box.

## Usage

### Desktop post-it

Add the `note` desktop widget from Noctalia's desktop-widget editor
(`noctalia msg desktop-widgets-edit`), then set its `key`. Clicking the paper
opens the panel on that note.

Deleting is deliberately panel-only: a desktop widget has no confirmation step,
and a stray click on the wallpaper should not destroy a note.

Post-its are background surfaces, so they sit above the wallpaper and below
every window. On a tiling compositor they are visible on empty workspaces and in
the overview.

### Bar widget

Shows the note count and opens the panel. Middle click opens the plugin's
settings, as with every Noctalia bar widget.

### Panel

Floating and centered by default; Noctalia's own per-plugin `panel_position`
overrides it.

The move button - in both the list header and the editor, since that is where
someone already is when they decide a sheet sits wrong - hands the desk to
Noctalia's widget editor - the only
thing that can move, resize or rotate a sheet - and closes the panel, which
otherwise floats over the desk being rearranged. Press Done in the editor when
finished; leaving it writes `settings.toml`, which is what the scatter watcher
listens for.

Each row says which output its sheet is on, or *not on screen* for a note that
has no widget - a post-it on the other monitor is the usual reason a note looks
like it exists nowhere. A row with no sheet gets a board button that sticks it
to the desktop.

The full CRUD surface: create, retitle, edit the body, recolor and delete. The editor has its own New button, so a run of notes does not
need a trip back to the list between each one. There is no pinning: every note
is a sheet at a fixed place on the desktop already. Edits autosave about a second after typing stops, and on
close, and the Save button writes and closes the panel. Autosave will not empty a note that had text in it - `ui.input` is
uncontrolled, and a stray empty change should not erase a note - so clearing one
on purpose needs the Save button. The first color chip is *automatic*, which
clears a note's color and lets the post-it derive one from its key.

### IPC

```sh
noctalia msg plugin remo/noctes:service all desk           # note + desktop widget
noctalia msg plugin remo/noctes:service all move           # toggle the widget editor
noctalia msg plugin remo/noctes:service all new            # empty note
noctalia msg plugin remo/noctes:service all new "buy milk" # note with a body
noctalia msg plugin remo/noctes:service all open work      # select the "work" note,
                                                           # creating it if absent
noctalia msg plugin remo/noctes:service all reload         # re-read notes.json
```

`new` and `open` both select the note, so opening the panel afterwards lands
straight in its editor. That makes a keybind of
`noctalia msg plugin remo/noctes:service all new` plus
`noctalia msg panel-open remo/noctes:panel` a one-shot quick-note.

## tools/noctes-scatter

```sh
tools/noctes-scatter              # scatter the post-its that are still untouched
tools/noctes-scatter --all        # re-randomize every post-it
tools/noctes-scatter --keep-tilt  # never touch rotation
tools/noctes-scatter --dry-run    # report only
```

Walks `settings.toml` and, for every post-it widget that is still untouched -
no key, or background still on, or rotation exactly zero - gives it a random
tilt between about 1 and 3 degrees, turns the host background off, and assigns a
`nota-N` key. The key is what the paper color, folded corner and tape are derived
from, so handing out distinct keys is what makes a fresh post-it look unlike its
neighbours. Widgets that already have all three are left alone, which makes the
command idempotent.

It backs the file up, validates with `noctalia config validate` before keeping
the change, restores the backup if validation fails, and reloads on success.

### Running it automatically

`tools/systemd/` holds a user path unit that runs the command two seconds after
`settings.toml` changes, which covers the desktop-widget editor writing on its
way out:

```sh
ln -s "$PWD"/tools/systemd/noctes-scatter.{service,path} ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now noctes-scatter.path
```

Stop it with `systemctl --user disable --now noctes-scatter.path`. The unit's own
write re-triggers the watch once, and that run finds nothing to change and exits
without writing, so it settles rather than looping.

### Which screen a new post-it lands on

The one that already holds the most post-its, falling back to the focused output
for the very first sheet. The focused output is usually the screen being worked
on, where a fullscreen window would hide a new post-it immediately.

## Storage

`notes.json` in the folder given by the `save_path` setting, or in the plugin's
own data directory (`~/.local/state/noctalia/plugins/data/remo/noctes`) when
that setting is empty. The file is a plain JSON array of notes, safe to edit by
hand while Noctalia is not running, or followed by an IPC `reload`.

## Settings

### Plugin

| Setting | Type | Default | Description |
| --- | --- | --- | --- |
| `default_color` | `select` | `auto` | Color new notes get; automatic leaves it to the post-it's key. |
| `paper_opacity` | `float` | `0.96` | How solid every post-it is; the text stays fully opaque. |
| `theme_colors` | `bool` | `true` | Paint every post-it from the Noctalia palette, which tracks the wallpaper. |
| `save_path` | `string` | *(empty)* | Folder for `notes.json`; empty uses the plugin data directory. |

### Bar widget

| Setting | Type | Default | Description |
| --- | --- | --- | --- |
| `show_count` | `bool` | `true` | Show the note count next to the glyph. |

### Desktop widget

| Setting | Type | Default | Description |
| --- | --- | --- | --- |
| `key` | `string` | *(empty)* | Which note this post-it shows. |
| `color` | `select` | `auto` | Paper color; automatic derives it from the key, and the note's own color wins over that. |
| `fold` | `select` | `none` | Which bottom corner is dog-eared. Off by default; see above. |
| `tape` | `select` | `auto` | Whether a strip of tape is drawn, and where. |
| `paper_width` | `int` | `220` | Paper width in px. |
| `paper_height` | `int` | `200` | Paper height in px. |
| `font_size` | `int` | `16` | Body font size; the title is three points larger. A handwriting font needs more size than a UI font to stay legible. |
| `max_lines` | `int` | `14` | Body lines drawn before the text is elided. |
| `show_title` | `bool` | `true` | Draw the note title above the body. |
| `paper_opacity` | `float` | `0.0` | Overrides the plugin-wide opacity for this sheet; 0 follows it. |
| `shadow` | `bool` | `true` | Draw the drop shadow. |
| `use_theme_colors` | `select` | `inherit` | Whether this sheet follows the theme: inherit the plugin-wide switch, or force it on or off. |
| `font_path` | `string` | `PatrickHand-Regular.ttf` | Font the note is drawn in. Plugin-relative, absolute or `~` path; empty falls back to the shell font. |

Every desktop-widget setting is per instance, so each post-it on the desktop can
look different from the next.

## Bundled font

`PatrickHand-Regular.ttf` ships with the plugin and is the default, because
handwriting is most of what separates a post-it from a UI card. It is Patrick
Hand by Patrick Wagesreiter, under the SIL Open Font License 1.1; the license
is `PatrickHand-OFL.txt` next to it. Point `font_path` somewhere else, or clear
it to use the shell font.

## Dependencies

`python3`, for `tools/noctes-widget`: the only process the plugin spawns, and the
only thing that writes outside the plugin's own data directory - it appends a
widget to `settings.toml`, backs the file up first, validates with
`noctalia config validate`, and restores the backup if that fails. No network
calls.
