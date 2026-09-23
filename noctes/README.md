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
click, already tilted, colored and without the host background. Everything in
the panel's list is therefore something that exists on screen, and deleting a
note takes its sheet off the desktop too. Same thing over IPC:

```sh
noctalia msg plugin remo/noctes:service all desk
```

The desktop-widget editor still works: its sheets arrive untilted, keyless and
framed, and the service adopts them.

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
settings. Nobody has to type one: creating a post-it generates `nota-N`, and so
does the stick button. Set one by hand only to point a
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

The way around both is `tools/noctes-widget`, which edits that file directly -
backing it up, validating with `noctalia config validate` and restoring on
failure. It is the only thing here that writes outside the plugin's own data
directory, and the only process the plugin spawns.

Sheets added through Noctalia's widget editor arrive square, keyless and framed.
The service notices them on its next look at the settings file and adopts them:
a key, an angle, no frame.

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
| `paper_opacity` | `float` | `0.96` | How solid every post-it is; the text stays fully opaque. Step 0.02. |
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
| `key` | `string` | *(empty)* | Which note this post-it shows. |
| `color` | `select` | `auto` | Paper color; automatic derives it from the key, and the note's own color wins over that. |
| `fold` | `select` | `none` | Which bottom corner is dog-eared. Off by default; see above. |
| `tape` | `select` | `auto` | Whether a strip of tape is drawn, and where. |
| `paper_width` | `int` | `220` | Paper width in px. |
| `paper_height` | `int` | `200` | Paper height in px. |
| `font_size` | `int` | `16` | Body font size; the title is three points larger. A handwriting font needs more size than a UI font to stay legible. |
| `max_lines` | `int` | `14` | Body lines drawn before the text is elided. |
| `show_title` | `bool` | `true` | Draw the note title above the body. |
| `opacity_override` | `float` | `0.0` | Overrides the plugin-wide opacity for this sheet; 0 follows it. Step 0.02. |
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
