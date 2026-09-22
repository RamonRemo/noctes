# noctes - stickers for noctalia

You know the notes. Fridge door, edge of a monitor, stuck to the page you meant
to come back to. You never *open* them. They are just there, in the corner of
your eye, until the thing is done and the paper comes off.

Software forgot that. Notes became apps: a window to raise, a list to scroll, a
sync icon. A sticky note has no inbox. It is a square of colored paper with four
words on it, stuck where you already look.

So: little sheets on your desktop, slightly crooked, a strip of tape on top,
written in a hand that is not your system font. Above the wallpaper, below every
window - never in the way, always there when you clear the screen.

And they take noctalia's colors. Change the wallpaper and the whole wall changes
with it. Nobody configures that. It just keeps happening.

![noctes on the desktop](docs/hero.jpg)

## What it is

A plugin for [Noctalia](https://noctalia.dev). Stickers on the desktop, a small
panel to write in, a bar widget with the count.

Notes are plain text in a plain JSON file. Nothing syncs. Delete the plugin and
they are still readable on disk.

## Install

```sh
git clone https://github.com/RamonRemo/noctes ~/Projetos/noctes
noctalia msg plugins source add noctes path ~/Projetos/noctes
noctalia msg plugins enable remo/noctes
```

Optional, and worth it - a watcher that tidies up sheets added through
noctalia's widget editor:

```sh
ln -s ~/Projetos/noctes/tools/systemd/noctes-scatter.{service,path} ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now noctes-scatter.path
```

## The first sticker

Fiddly once, then never again. A plugin cannot place a desktop widget on its
own, so noctalia's editor does the first one:

1. **Settings -> Desktop -> Widgets -> Toggle Editor**
2. Add a **Noctes** widget
3. **Done**

It shows up square and grey in a dark panel. Wait a second: closing the editor
is the watcher's cue to tilt it, colour it and drop the panel.

Now **click the sheet**. Everything else happens in the panel:

| | |
| --- | --- |
| ![The note editor](docs/editor.png) | Title, body, colour. **+** makes another sticker, sheet and all. The arrows hand the desk to noctalia's widget editor for dragging. The bin takes note and sheet together. |

Skipping the editor entirely also works:

```sh
noctalia msg plugin remo/noctes:service all desk
```

## Colours

Notes are **dynamic** by default: each picks its own paper and follows the
shell's palette, which on a generated theme follows your wallpaper.

Pick a chip and it stops following anything - groceries stay yellow forever.
There is a **glass** chip too: a translucent pane instead of paper, tinted by
the shell. Sharp, not blurred; a plugin gets no blur.

A line under the chips always says which mode the note is in.

## How it behaves

**You write in the panel, not on the sheet.** Sheets are painted below your
windows, where nothing can take the keyboard. Clicking one opens it.

**No list of notes.** They are already on screen. Pick one by looking at it.

**No folded corners.** They looked like a printing error. A plugin cannot draw a
clean diagonal; details in the notes below.

**Deleting takes the sheet with it.** The note and the sticker are one thing.

## Settings

Per sheet: size, font size, lines, colour, tape, opacity, title on or off.
Plugin-wide: default colour, opacity, follow the theme, where `notes.json`
lives.

Full tables and the IPC commands are in [`noctes/README.md`](noctes/README.md).

## For the curious

[`docs/plugin-notes.md`](docs/plugin-notes.md) collects what it took to make
paper look like paper inside a plugin sandbox, and the nine or so things about
noctalia's plugin API that are written down nowhere and cost an afternoon each.
Shadows that paint nothing, palette roles that do not exist, sliders with two
positions. Writing a noctalia plugin? Start there.

## License

MIT. The bundled Patrick Hand font is SIL OFL 1.1 - it is the handwriting the
notes are written in.
