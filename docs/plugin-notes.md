# Notes from inside the sandbox

Everything here was learned the slow way, building noctes against Noctalia 5's
plugin API. None of it is in the docs. Most of it fails silently, which is the
part that costs the afternoon.

If you are writing a noctalia plugin, this is the page worth skimming first.

## A desktop widget has no identity

The `desktopWidget` API is three functions: `render`, `setWantsSecondTicks`,
`setNeedsFrameTick`. No instance id. No output name. Two sheets on screen run
the same code with no way to tell themselves apart.

So a plugin cannot bind "this widget" to "that record" on its own. The only
thing that differs between two instances is their settings, which is why every
noctes sheet carries a `key` - a short handle the widget stores and the service
looks up. Nobody types one; they are generated. But the mechanism has to exist,
and it is the first thing to design around if your widget is anything other
than stateless.

## Three fields a plugin cannot write

A desktop widget's **rotation**, its **background panel**, and **the widget
entry itself** are host state in `settings.toml`. Nothing in the plugin API
touches them. If your plugin wants a widget that is tilted, or without the
rounded panel noctalia draws behind everything, or wants to create a widget at
all, the only route is editing that file.

noctes does exactly that, in `tools/noctes-scatter` and
`noctes/tools/noctes-widget`. Both back the file up, run
`noctalia config validate`, and restore on failure - because:

> An unrecognized key inside a widget's settings table does not fail
> gracefully. It breaks the parse and takes the whole shell down with it: bar,
> dock, wallpaper, everything, until the file is fixed.

Validate before reloading. Always.

## `rotation` is radians

Not degrees. `0.05` is about three degrees. `-3.0` is upside down, which is how
this was discovered.

## A plugin widget is centered at its natural size

The host measures your tree and centers it in the widget box. `flexGrow` does
not stretch it to fill. If you want a specific size, the tree has to carry it -
in noctes that is the `paper_width` / `paper_height` settings, and the widget
box is left on auto.

## `ui.box` needs both a width and a height

A box sized on one axis only paints **nothing**. No warning, no log line, just
an invisible node. This hid the drop shadow for four versions; the code looked
right and the screen was empty.

## Numeric settings need an explicit `step`

Leaving `step` off does not mean "continuous". The parser defaults it to `1.0`,
so a float slider from 0 to 1 has exactly two reachable positions and reads as a
broken control rather than a coarse one.

Declare `step` on every `float`, finer than the range, with the default landing
on a boundary. There is a ready-made test suite for this and neighbouring
manifest mistakes in the community repo, at
`claude-companion/tests/manifest_spec.py` - worth running against your own
manifest before a PR.

## Two ways a colour quietly becomes another colour

Both of these cost an evening on the same feature.

An alpha helper that *sets* alpha rather than *multiplying* it throws away the
alpha a colour already had. A glass paper defined as `#FFFFFF52` came out opaque
white the moment the sheet's own opacity was applied on top of it.

And a service that validates what it stores will reset a colour it does not
recognise. The renderer knew about glass; the service did not, so every glass
note came back from disk as a plain one, and the bug looked like a rendering
problem for a good while. Keep the two lists in one place, or at least check
both when adding a value.

## The palette is fourteen roles

`primary`, `on_primary`, `secondary`, `on_secondary`, `tertiary`, `on_tertiary`,
`error`, `on_error`, `surface`, `on_surface`, `surface_variant`,
`on_surface_variant`, `outline`, `shadow`.

The Material *container* roles - `primary_container` and friends - **do not
exist here**, and naming one paints transparent. Silently, again. noctes shipped
a "follow the theme" switch that did nothing for several versions for exactly
this reason.

Two more colour notes: hex takes its alpha as `#rrggbbaa`, while only role names
take the `role/0.6` form. And `surface_variant` is the panel background of
whatever scheme is loaded - fine for a card, wrong for paper, since on a dark
scheme it hands back a near-black sheet.

## This build caps below plugin API 32

Declaring `plugin_api = 32` gets the plugin marked `incompatible` and disabled.
That puts `tooltip` on a box or a flex container out of reach, since it is an
API 32 prop. Only `ui.button` has a tooltip.

When you need to explain a control and cannot hover, a caption label under it
works better anyway - it also reaches the person who never thinks to hover.

## Hot reload is partial

Editing a `.luau` does not reliably reach every desktop widget already on
screen. You can end up with two sheets on the new code and two on the old, no
error anywhere, and spend a while debugging a difference that does not exist in
the source.

```sh
noctalia msg plugins disable remo/noctes && noctalia msg plugins enable remo/noctes
```

Toggling a plugin *setting* is different - that repaints everything at once and
is the reliable path.

## The widget editor holds new widgets in memory

A widget added in the editor is not in `settings.toml` until Done is pressed.
Anything of yours that reads that file - a watcher, a tool, the plugin itself -
sees nothing until then. Two separate "it is broken" reports turned out to be
this.

## Drawing paper with rectangles

The `ui.*` vocabulary has no rotation, no clipping, no blur and no vector
primitive. Everything below follows from that.

**The shadow** started as three stacked bands of falling alpha, faking a
falloff. It looked right in a static mock and terrible on screen: the host
rotates the whole sheet, and rotating crisp stripes resamples them into a
staircase. One low-alpha box per edge with a wide `softness` - which feathers -
is both cleaner and more convincing than the thing it replaced.

**The folded corner** never worked. A diagonal can only be a staircase of
rectangles; at one pixel a step it is as smooth as it can get, and the host's
rotation still resamples it into visible hatching. It is off by default. The
only real fix would be shipping an image per colour, which kills the dynamic
palette - a bad trade for a dog-ear.

**The tape** is just a translucent white strip, and it is the piece that does
the most work per line of code. Worth remembering when a shadow is fighting you.

## The shape that survived

One headless service owns the data and the file. Every surface - bar widget,
panel, each sheet - is a thin client that reads published state and sends
commands back. Nothing but the service touches disk.

That is not a noctalia requirement, it is just what stops four copies of a note
list from disagreeing with each other. Writes are debounced onto a two second
tick, and each sheet skips redrawing when the publish that woke it did not
change the note it shows - with a wall of sheets, every keystroke would
otherwise rebuild all of them.
