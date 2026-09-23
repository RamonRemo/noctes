"""Settings files to run the tool against.

Shaped like Noctalia's own `settings.toml`: four-space indent under
`[desktop_widgets]`, eight under a widget's `.settings`, `widget_order` as a
multi-line array. The tool edits this file as lines rather than round-tripping
TOML, so the indentation and the blank lines are part of what is under test.
"""

HEAD = """\
[bar]
position = "top"

[dock]
enabled = false
"""


def settings(widgets=(), order=None, plugin_tilt=None, schema=2):
    """A settings file holding `widgets`, each a block of TOML text.

    `order` defaults to every widget id in the order given. `plugin_tilt`
    writes noctes' own `tilt` switch into `[plugin_settings]` when it is a bool.
    """
    ids = [wid for wid, _ in widgets]
    listed = ids if order is None else order

    entries = ",\n".join(f'    "{wid}"' for wid in listed)
    body = "".join(block for _, block in widgets)

    plugin = ""
    if plugin_tilt is not None:
        plugin = (
            '\n[plugin_settings."remo/noctes"]\n'
            f"tilt = {str(plugin_tilt).lower()}\n"
            'default_color = "auto"\n'
        )

    return (
        "[bar]\n"
        'position = "top"\n'
        "\n"
        "[desktop_widgets]\n"
        f"schema_version = {schema}\n"
        "widget_order = [\n"
        f"{entries}\n"
        "]\n"
        "\n"
        "    [desktop_widgets.grid]\n"
        "    cell_size = 16\n"
        "    visible = true\n"
        f"{body}"
        f"{plugin}"
        "\n[dock]\n"
        "enabled = false\n"
    )


def sheet(wid, key="", output="DP-2", cx=170.0, cy=170.0, rotation=0.0,
          background=False, settings_table=True):
    """A noctes sheet. `settings_table=False` is how Noctalia's widget editor
    leaves one: no settings table at all, so no key and no background flag."""
    block = (
        f"\n    [desktop_widgets.widget.{wid}]\n"
        "    box_height = 0.0\n"
        "    box_width = 0.0\n"
        f"    cx = {cx}\n"
        f"    cy = {cy}\n"
        f'    output = "{output}"\n'
        "    placement_height = 1440.0\n"
        "    placement_width = 3440.0\n"
        f"    rotation = {rotation:.6f}\n"
        '    type = "remo/noctes:note"\n'
    )
    if not settings_table:
        return wid, block

    block += f"\n        [desktop_widgets.widget.{wid}.settings]\n"
    block += f"        background = {str(background).lower()}\n"
    if key:
        block += f'        key = "{key}"\n'
    return wid, block


def foreign(wid, kind="sysmon", output="DP-2"):
    """Another plugin's widget. Nothing the tool does may touch one."""
    return wid, (
        f"\n    [desktop_widgets.widget.{wid}]\n"
        "    box_height = 128.0\n"
        "    box_width = 256.0\n"
        "    cx = 2952.0\n"
        "    cy = 160.0\n"
        f'    output = "{output}"\n'
        "    placement_height = 1440.0\n"
        "    placement_width = 3440.0\n"
        "    rotation = 0.0\n"
        f'    type = "{kind}"\n'
        "\n"
        f"        [desktop_widgets.widget.{wid}.settings]\n"
        "        background_opacity = 0.64\n"
        '        stat = "gpu_vram"\n'
    )


def wid(n):
    return f"desktop-widget-{n:016x}"
