# Noctes - Stickers for Noctalia

**Noctes puts sticky notes on your desktop.** Not in a window, not in a list -
on the wallpaper itself, below every window, where you already look. Each note
is its own desktop widget: a sheet of paper at a small random angle, a strip of
tape on top, written in a handwriting font, in a colour the shell chooses.

![Noctes on the desktop](docs/hero.jpg)

## The paper can follow the wallpaper

**Optional, and on by default.** A note with no colour of its own draws from
Noctalia's palette, and on a generated theme that palette comes from the
wallpaper - so changing the wallpaper recolours the wall. Three wallpapers,
three palettes:

![Noctes under three wallpapers](docs/theme.jpg)

The bottom two are the same four notes, and two of them do not move: a sheet
whose colour was picked by hand keeps it whatever the theme does. Eight papers
to pick from, plus two that are not paper: **black**, the one sheet written in
white ink, and **glass**, a translucent pane whose text flips with the scheme.

Dropping the theme entirely is one plugin-wide switch - *Paper follows the
theme*. Off, the sheets that have no colour of their own draw from eight classic
papers instead of the palette.

## Writing on them

Clicking a sheet opens the panel on that note. That is the whole interface -
there is no note list, because the notes are already on screen.

| | |
| --- | --- |
| ![The note editor](docs/editor.png) | Title, body, colour. **+** creates the next sticker - note and sheet together, already tilted. The arrows hand the desk back to the widget editor for dragging and resizing. The gear opens the plugin settings. The bin deletes note and sheet as one. |

## In short

- One sheet per note. Size, font and font size are per sheet; the colour
  belongs to the note; opacity, tilt, theme following and the storage path are
  plugin-wide.
- Notes live in one plain JSON file, written through a rename so a crash cannot
  leave half of it. No database, no sync, no account - delete the plugin and
  your notes are still readable on disk.
- The sheets look after themselves. Delete one in Noctalia's widget editor and
  its note goes with it; switch a monitor off and its sheets move to one that
  is still on, then go back when it returns.
- A bar widget with the note count, which opens the panel.
- IPC, so a quick note can be one keybind away.
- In English, Portuguese, Spanish, French, German, Italian, Dutch, Polish,
  Russian, Ukrainian, Turkish, Japanese, Korean and Chinese. The catalog copy
  ships English and Portuguese; the rest are in this repository until reviewed.

## Install

Needs `python3`, which puts the sheets on the desktop - see
[Dependencies](noctes/README.md#dependencies).

Noctes is in the
[community catalog](https://github.com/noctalia-dev/community-plugins/tree/main/noctes),
which Noctalia ships as a default source. Enable it from **Settings -> Plugins
-> Browse Plugins**, or:

```sh
noctalia msg plugins enable remo/noctes
noctalia msg plugin remo/noctes:service all desk
```

For the newest code before it reaches the catalog, run this repository as a
local source instead; a local copy overrides the catalog one:

```sh
git clone https://github.com/RamonRemo/noctes.git ~/noctes
noctalia msg plugins source add noctes path ~/noctes
noctalia msg plugins enable remo/noctes
```

The `desk` line puts the first sheet on the screen you are working on, tilted and
coloured. Click it and write. Every sheet after that comes from the panel's
**+**, or from the same command again.

Noctalia's own **Settings -> Desktop -> Widgets -> Toggle Editor** works too, if
you would rather click: a widget added there arrives square and grey in a dark
frame, and the service adopts it a second later - key, angle, no frame.

## IPC

```sh
noctalia msg plugin remo/noctes:service all desk           # note + sheet
noctalia msg plugin remo/noctes:service all new "buy milk" # note + sheet, with text
noctalia msg plugin remo/noctes:service all open work      # select a note by key
noctalia msg plugin remo/noctes:service all move           # toggle the widget editor
noctalia msg plugin remo/noctes:service all stick work     # give a keyed note a sheet
noctalia msg plugin remo/noctes:service all gather         # sheets off a dead monitor
noctalia msg plugin remo/noctes:service all reload         # re-read notes.json
```

`desk` and `new` both select what they create, so pairing either with
`noctalia msg panel-open remo/noctes:panel` makes a one-keybind quick note.

## Read more

- [`noctes/README.md`](noctes/README.md) - every setting, in tables, and how the
  four entries fit together.
- [`docs/plugin-notes.md`](docs/plugin-notes.md) - what it took to make paper
  look like paper inside a plugin sandbox, and the dozen things about Noctalia's
  plugin API that are documented nowhere and cost an afternoon each. Writing a
  Noctalia plugin? Start there.
- [`tests/README.md`](tests/README.md) - `tests/run` covers the helper that
  edits Noctalia's `settings.toml`, the plugin's Luau against a stand-in for
  the shell, and the manifest against the translations and docs that have to
  agree with it. Python's standard library, plus Lua 5.4 for the Luau.

## License

MIT. The bundled Patrick Hand font is SIL OFL 1.1 - it is the handwriting the
notes are written in.
