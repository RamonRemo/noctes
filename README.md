# Noctes - Stickers for Noctalia

**Noctes puts sticky notes on your desktop.** Not in a window, not in a list -
on the wallpaper itself, below every window, where you already look. Each note
is its own desktop widget: a sheet of paper at a small random angle, a strip of
tape on top, written in a handwriting font, in a colour the shell chooses.

It is also properly configurable. Paper size, font size, tilt, tape, opacity and
colour are per sheet; defaults, theme following and storage path are plugin-wide.
Notes live in one plain JSON file - no database, no sync, no account. Delete the
plugin and your notes are still readable on disk.

The colours are the part people notice. A note with no colour of its own draws
from Noctalia's palette, and on a generated theme that palette follows your
wallpaper. Change the wallpaper and the whole wall recolours itself.

![Noctes on the desktop](docs/hero.jpg)

## What it ships

Four entries, all thin clients of one headless service that owns the note list
and is the only thing that touches disk:

| Entry | What it is |
| --- | --- |
| `service` | Owns `notes.json`, publishes state, runs the commands |
| `note` | The `[[desktop_widget]]` - one sheet per instance |
| `panel` | The editor, and the only surface that can take the keyboard |
| `bar` | Note count, opens the panel |

`noctes/tools/noctes-widget` is the one piece that writes outside the plugin's
own data: it adds, removes, tilts and tidies sheets in `settings.toml`, which is
where a widget's rotation, background and very existence are kept.

Writes to disk are debounced onto a two second tick, and each sheet skips
redrawing when a state publish did not change the note it shows - with a wall of
sheets, every keystroke would otherwise rebuild all of them.

## Install

```sh
git clone https://github.com/RamonRemo/noctes ~/Projetos/noctes
noctalia msg plugins source add noctes path ~/Projetos/noctes
noctalia msg plugins enable remo/noctes
```

Optional, and worth it. Rotation and the host's widget background are fields a
plugin cannot write, so a sheet added through Noctalia's own widget editor comes
out square and framed. This watcher fixes that a couple of seconds after the
editor closes:

```sh
ln -s ~/Projetos/noctes/noctes/tools/systemd/noctes-scatter.{service,path} ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now noctes-scatter.path
```

Without it, run `noctes/tools/noctes-widget scatter` by hand after using the
editor. Everything created from the panel is already correct.

## The first sticker

A plugin cannot place a desktop widget on its own, so the first one comes from
Noctalia:

1. **Settings -> Desktop -> Widgets -> Toggle Editor**
2. Add a **Noctes** widget
3. **Done**

It appears square and grey in a dark frame; closing the editor is the watcher's
cue to tilt it, colour it and drop the frame.

Then **click the sheet**. Everything after that happens in the panel:

| | |
| --- | --- |
| ![The note editor](docs/editor.png) | Title, body, colour. **+** creates the next sticker - note and widget together, already tilted. The arrows hand the desk back to the widget editor for dragging and resizing. The gear opens the plugin settings. The bin deletes note and sheet as one. |

Skipping the editor entirely:

```sh
noctalia msg plugin remo/noctes:service all desk
```

## Colours

A note with no colour of its own is **dynamic**: it derives one from its key, so
two sheets rarely match, and each sheet keeps its look across restarts. With
*Paper follows the theme* on (the default) that draws from four palette roles -
`primary`, `secondary`, `tertiary`, `error` - each paired with its own `on_*`
text role. Off, it draws from eight classic papers with a few points of per-note
tint jitter.

Pick a chip and the note stops following anything. Eight papers, plus two that
are not paper:

- **glass** - a white veil at about a third alpha with a hairline edge, text in
  `on_surface` so it flips with the scheme. Sharp, not frosted: the plugin API
  exposes no blur, and Noctalia's own blur is wired to its panels.
- **black** - `#1C1F26` with white ink, the one sheet that is written on rather
  than printed.

A caption under the chips always names the mode the note is in.

## Behaviour

**Typing happens in the panel.** Desktop widgets are background layer-shell
surfaces and cannot take keyboard focus - a property of the surface, not a
choice. Clicking a sheet opens the panel on that note.

**There is no note list.** The notes are already on screen; picking one means
clicking it. The panel is a single view.

**No folded corners.** The `ui.*` vocabulary has no rotation, clipping or vector
primitive, so a diagonal can only be a staircase of rectangles, and the host's
rotation resamples it into visible hatching. Off by default, selectable per
sheet.

**Deleting removes the widget too.** A note and its sticker are one object.

## Settings

Per sheet, in the widget's own settings: `key`, `color`, `fold`, `tape`,
`paper_width`, `paper_height`, `font_size`, `max_lines`, `show_title`,
`opacity_override`, `shadow`, `use_theme_colors`, `font_path`.

Plugin-wide: `default_color`, `theme_colors`, `tilt`, `paper_opacity`,
`save_path`. The gear in the editor opens them.

Full tables in [`noctes/README.md`](noctes/README.md).

## IPC

```sh
noctalia msg plugin remo/noctes:service all desk           # note + widget
noctalia msg plugin remo/noctes:service all new "buy milk" # note only
noctalia msg plugin remo/noctes:service all open work      # select a note by key
noctalia msg plugin remo/noctes:service all move           # toggle the widget editor
noctalia msg plugin remo/noctes:service all reload         # re-read notes.json
```

`desk` and `new` both select what they create, so pairing either with
`noctalia msg panel-open remo/noctes:panel` makes a one-keybind quick note.

## For the curious

[`docs/plugin-notes.md`](docs/plugin-notes.md) collects what it took to make
paper look like paper inside a plugin sandbox, and the dozen things about
Noctalia's plugin API that are documented nowhere and cost an afternoon each:
where the logs go, boxes that paint nothing, palette roles that do not exist,
sliders with two positions, settings whose effect lives outside the plugin.
Writing a Noctalia plugin? Start there.

## License

MIT. The bundled Patrick Hand font is SIL OFL 1.1 - it is the handwriting the
notes are written in.
