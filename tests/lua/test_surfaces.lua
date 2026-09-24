-- The thin clients: panel.luau, note.luau and bar.luau, fed state the way the
-- service publishes it.

package.path = debug.getinfo(1, "S").source:match("^@(.*)/[^/]*$") .. "/?.lua;" .. package.path
local T = require("host")

local A = { id = "a", key = "ka", title = "A title", content = "A body", color = "", updatedAt = 3 }
local B = { id = "b", key = "kb", title = "B title", content = "B body", color = "", updatedAt = 2 }

local function withState(state)
  local host = T.new()
  local defaults = {
    ["noctes.notes"] = { A, B },
    ["noctes.ready"] = true,
    ["noctes.boundKeys"] = { { key = "ka", output = "DP-2" }, { key = "kb", output = "DP-2" } },
    ["noctes.sheetsReady"] = true,
    ["noctes.themeColors"] = false,
    ["noctes.paperOpacity"] = 0.96,
    ["noctes.editing"] = "",
  }
  for key, value in pairs(defaults) do
    host.state[key] = value
  end
  for key, value in pairs(state or {}) do
    host.state[key] = value
  end
  host.cmds = {}
  host:api({ config = {} }).state.watch("noctes.cmd", function(cmd)
    table.insert(host.cmds, cmd)
  end)
  return host
end

local function node(entry, predicate)
  return T.find(entry.tree, predicate)[1]
end

local function input(entry, prefix)
  return node(entry, function(n)
    return n.kind == "input" and tostring(n.props.key):sub(1, #prefix) == prefix
  end)
end

local function button(entry, predicate)
  return node(entry, function(n)
    return n.kind == "button" and predicate(n.props)
  end)
end

local function press(host, target)
  T.ok(target ~= nil, "nothing to press")
  target.props.onClick()
  host:drain()
end

local function lastCmd(host)
  return host.cmds[#host.cmds]
end

-- ── Panel ───────────────────────────────────────────────────────────────────

local function openPanel(state)
  local host = withState(state)
  local panel = host:load("panel.luau")
  host:call(panel, "onOpen")
  return host, panel
end

T.test("panel: deleting the open note moves the editor, drafts and all", function()
  local host, panel = openPanel()
  T.eq(input(panel, "title-").props.value, "A title", "opens on A")

  press(host, button(panel, function(p) return p.glyph == "trash" end))
  press(host, button(panel, function(p) return p.glyph == "check" end))
  T.eq(lastCmd(host).op, "remove", "remove sent")
  T.eq(lastCmd(host).id, "a", "for A")

  local title = input(panel, "title-")
  T.eq(title.props.key, "title-b", "editor on B")
  T.eq(title.props.value, "B title", "B's own text, not A's")

  title.props.onChange("B edited")
  press(host, button(panel, function(p) return p.text == "panel.save" end))
  T.eq(lastCmd(host).op, "update", "save sent")
  T.eq(lastCmd(host).id, "b", "to B")
  T.eq(lastCmd(host).title, "B edited", "with the edit")
end)

T.test("panel: a note gone in a reload takes its drafts with it", function()
  local host, panel = openPanel()
  host:set("noctes.notes", { B })
  T.eq(input(panel, "title-").props.value, "B title", "B's text")
end)

T.test("panel: reopening shows the note as it is now", function()
  local host, panel = openPanel()
  host:call(panel, "onClose")
  host:set("noctes.notes", { { id = "a", key = "ka", title = "A renamed", content = "", color = "" }, B })
  host:call(panel, "onOpen")
  T.eq(input(panel, "title-").props.value, "A renamed", "fresh text")
end)

T.test("panel: an unchanged switch does not redraw", function()
  local host, panel = openPanel()
  local renders = panel.renders
  host:set("noctes.themeColors", false)
  host:set("noctes.sheetsReady", true)
  T.eq(panel.renders, renders, "no redraw")
  host:set("noctes.themeColors", true)
  T.eq(panel.renders, renders + 1, "one redraw for a real change")
end)

T.test("panel: a note with no sheet says so, and that is all", function()
  -- Asked for twice: no button for this. A button here showed up at the wrong
  -- moments; a note gets its sheet back through the `stick` IPC event.
  local loose = { id = "l", key = "", title = "loose", content = "", color = "", updatedAt = 9 }
  local _, panel = openPanel({ ["noctes.notes"] = { loose } })
  T.ok(node(panel, function(n) return n.kind == "label" and n.props.text == "panel.not_on_screen" end),
    "says it is not on screen")

  local glyphs = {}
  for _, b in ipairs(T.find(panel.tree, function(n) return n.kind == "button" and n.props.glyph ~= nil end)) do
    table.insert(glyphs, b.props.glyph)
  end
  T.eq(table.concat(glyphs, ","), "settings,arrows-move,plus,trash", "toolbar buttons")
end)

T.test("panel: without the helper it says why", function()
  local loose = { id = "l", key = "", title = "loose", content = "", color = "", updatedAt = 9 }
  local _, panel = openPanel({ ["noctes.notes"] = { loose }, ["noctes.sheetsReady"] = false })
  T.ok(node(panel, function(n) return n.kind == "label" and n.props.text == "panel.no_helper" end),
    "says why")
end)

-- ── Sheet ───────────────────────────────────────────────────────────────────

local function sheet(key, state)
  local host = withState(state)
  local entry = host:load("note.luau", { key = key, paper_width = 220, paper_height = 200 })
  return host, entry
end

local function labelled(entry, text)
  return node(entry, function(n)
    return n.kind == "label" and n.props.text == text
  end)
end

T.test("sheet: republishing what it already shows does not redraw it", function()
  local host, entry = sheet("ka")
  local renders = entry.renders
  host:set("noctes.ready", true)
  host:set("noctes.notes", { A, B })
  host:set("noctes.notes", { A, { id = "b", key = "kb", title = "B", content = "changed", color = "" } })
  host:set("noctes.themeColors", false)
  host:set("noctes.paperOpacity", 0.96)
  T.eq(entry.renders, renders, "no redraw")

  host:set("noctes.notes", { { id = "a", key = "ka", title = "A title", content = "new", color = "" }, B })
  T.eq(entry.renders, renders + 1, "one redraw for its own note")
end)

T.test("sheet: a keyless sheet shows no note and asks for none", function()
  local loose = { id = "l", key = "", title = "Loose title", content = "loose body", color = "" }
  local host, entry = sheet("", { ["noctes.notes"] = { loose } })
  T.eq(labelled(entry, "loose body"), nil, "no stranger's text")

  press(host, node(entry, function(n) return n.props.onClick ~= nil end))
  T.eq(#host.cmds, 0, "no ensure for an empty key")
  T.eq(host.panels[1], "remo/noctes:panel", "panel opened")
end)

T.test("sheet: the look published before it started is the one it uses", function()
  local _, entry = sheet("ka", { ["noctes.themeColors"] = true, ["noctes.paperOpacity"] = 0.5 })
  local paper = node(entry, function(n) return n.props.onClick ~= nil end)
  T.ok(tostring(paper.props.fill):find("/0.50", 1, true), "fill " .. tostring(paper.props.fill))
end)

-- ── Bar ─────────────────────────────────────────────────────────────────────

T.test("bar: an edit that keeps the count does not redraw it", function()
  local host = withState()
  local bar = host:load("bar.luau", { show_count = true })
  local renders = bar.renders
  host:set("noctes.notes", { A, B })
  T.eq(bar.renders, renders, "no redraw")
  host:set("noctes.notes", { A })
  T.eq(bar.text, "1", "new count")
end)

T.run()
