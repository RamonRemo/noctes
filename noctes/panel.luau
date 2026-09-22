--!nonstrict
-- Noctes panel - the only surface that can take keyboard focus, so it owns all
-- typing. A desktop post-it hands a note over by setting noctes.editing.
--
-- Two views:
--   list -> every post-it, click to edit, delete
--   edit -> title + body inputs, color picker, delete
--
-- Edits are kept as a local draft and flushed to the service on a second-tick
-- debounce, on view changes, and on close, so typing never round-trips through
-- state on every keystroke.

local colors = require("./colors.luau")

local FLUSH_AFTER_MS = 1200

local notes = {}
local boundKeys = {}
local themeColors = false
local view = "list"
local currentId = ""
local draftTitle = ""
local draftContent = ""
local dirty = false
local lastChangeMs = 0
local pendingDelete = ""

-- The seed a note's generated look hangs off: its key when it has one, so the
-- panel preview matches the desktop post-it, else its id.
local function seedOf(note)
  local key = note.key or ""
  return key ~= "" and key or note.id
end

-- A note is "on the wall" when some desktop widget is bound to its key. The
-- widgets live in Noctalia's settings, so the service reads them back and
-- publishes the list.
-- Returns the output the note's post-it sits on, or nil when no widget is
-- bound to it.
local function stuckOn(note)
  local key = note.key or ""
  if key == "" then
    return nil
  end
  for _, bound in ipairs(boundKeys) do
    if bound.key == key then
      return bound.output or "?"
    end
  end
  return nil
end

local function findNote(id)
  for _, note in ipairs(notes) do
    if note.id == id then
      return note
    end
  end
  return nil
end

-- `force` is the Save button. Autosave refuses to wipe a note that had text in
-- it: ui.input is uncontrolled, so a stray empty onChange would otherwise erase
-- the note silently. Clearing one on purpose still works, through Save.
local function flush(force)
  if not dirty or currentId == "" then
    dirty = false
    return
  end
  if not force then
    local stored = findNote(currentId)
    local wipes = noctalia.string.trim(draftTitle) == "" and noctalia.string.trim(draftContent) == ""
    local hadText = stored ~= nil and (noctalia.string.trim(stored.content or "") ~= ""
      or noctalia.string.trim(stored.title or "") ~= "")
    if wipes and hadText then
      return
    end
  end
  noctalia.state.set("noctes.cmd", {
    op = "update",
    id = currentId,
    title = draftTitle,
    content = draftContent,
  })
  dirty = false
end

local render

local function openEditor(id)
  if id == currentId and view == "edit" then
    return
  end
  flush()
  local note = findNote(id)
  if note == nil then
    return
  end
  currentId = id
  draftTitle = note.title or ""
  draftContent = note.content or ""
  dirty = false
  pendingDelete = ""
  view = "edit"
  render()
end

local function backToList()
  flush()
  view = "list"
  currentId = ""
  pendingDelete = ""
  noctalia.state.set("noctes.editing", "")
  render()
end

-- New means new post-it: the service creates the note and its desktop widget
-- together, so everything in this list is something that exists on screen.
local function addPostit()
  noctalia.state.set("noctes.cmd", { op = "spawn_widget" })
end

-- Hands the desk over to Noctalia's widget editor, which is the only thing that
-- can move, resize or rotate a sheet. The panel gets out of the way first: it
-- floats over the very desk being rearranged.
local function moveMode()
  noctalia.state.set("noctes.cmd", { op = "toggle_edit" })
  panel.close()
end

-- For notes that predate the widget, or whose post-it was deleted from the
-- desktop-widget editor.
local function stickNote(id)
  noctalia.state.set("noctes.cmd", { op = "stick", id = id })
end

local function removeNote(id)
  if currentId == id then
    dirty = false
  end
  noctalia.state.set("noctes.cmd", { op = "remove", id = id })
  if view == "edit" then
    view = "list"
    currentId = ""
  end
  pendingDelete = ""
  render()
end

local function setColor(id, color)
  noctalia.state.set("noctes.cmd", { op = "set_color", id = id, color = color })
end

-- ── List view ───────────────────────────────────────────────────────────────

local function previewOf(note)
  local content = noctalia.string.trim(note.content or "")
  if content == "" then
    return noctalia.tr("board.empty_note")
  end
  return (string.gsub(content, "%s+", " "))
end

local function listRow(note)
  local screen = stuckOn(note)
  local armed = pendingDelete == note.id
  local hasTitle = (note.title or "") ~= ""

  return ui.row({
    key = "row-" .. note.id,
    gap = 8,
    padding = 8,
    radius = 10,
    fill = "surface_container",
    align = "center",
    onClick = function()
      openEditor(note.id)
    end,
  }, {
    ui.box({
      width = 6,
      height = 34,
      radius = 3,
      fill = colors.swatch(note.color, seedOf(note), themeColors),
    }),
    ui.column({ gap = 2, flexGrow = 1 }, {
      ui.row({ gap = 6, align = "center" }, {
        ui.label({
          text = hasTitle and note.title or noctalia.tr("board.untitled"),
          fontWeight = "semibold",
          color = hasTitle and "on_surface" or "on_surface/0.6",
          maxLines = 1,
        }),
        -- Which screen the sheet is on, or that it is not on any: a post-it on
        -- the other monitor is the usual reason a note looks like it is
        -- nowhere.
        ui.label({
          text = screen ~= nil and screen or noctalia.tr("panel.not_on_screen"),
          fontSize = 10,
          color = screen ~= nil and "primary" or "on_surface/0.45",
          maxLines = 1,
        }),
      }),
      ui.label({
        text = previewOf(note),
        fontSize = 11,
        color = "on_surface/0.65",
        maxLines = 1,
      }),
    }),
    ui.button({
      key = "stick-" .. note.id,
      glyph = "layout-board",
      variant = "secondary",
      controlSize = "sm",
      visible = screen == nil,
      tooltip = noctalia.tr("panel.stick"),
      onClick = function()
        stickNote(note.id)
      end,
    }),
    ui.button({
      key = "del-" .. note.id,
      glyph = armed and "check" or "trash",
      variant = armed and "destructive" or "ghost",
      controlSize = "sm",
      tooltip = armed and noctalia.tr("panel.delete_confirm") or noctalia.tr("panel.delete"),
      onClick = function()
        if armed then
          removeNote(note.id)
        else
          pendingDelete = note.id
          render()
        end
      end,
    }),
  })
end

local function listView()
  local rows = {}
  for _, note in ipairs(notes) do
    table.insert(rows, listRow(note))
  end

  if #rows == 0 then
    table.insert(rows, ui.column({ padding = 16, align = "center", gap = 4 }, {
      ui.glyph({ name = "note", size = 28, color = "on_surface/0.4" }),
      ui.label({ text = noctalia.tr("panel.empty"), color = "on_surface/0.6" }),
    }))
  end

  return ui.column({ gap = 10, flexGrow = 1, align = "stretch" }, {
    ui.row({ gap = 8, align = "center" }, {
      ui.label({ text = noctalia.tr("panel.title"), fontSize = 15, fontWeight = "bold", flexGrow = 1 }),
      ui.button({
        glyph = "arrows-move",
        variant = "secondary",
        controlSize = "sm",
        tooltip = noctalia.tr("panel.move"),
        onClick = moveMode,
      }),
      ui.button({
        text = noctalia.tr("panel.new"),
        glyph = "plus",
        variant = "primary",
        controlSize = "sm",
        onClick = addPostit,
      }),
    }),
    ui.scroll({ gap = 6, flexGrow = 1, align = "stretch" }, rows),
  })
end

-- ── Edit view ───────────────────────────────────────────────────────────────

local function colorPicker(note)
  local isAuto = not colors.isKnown(note.color)

  -- The first chip is the dynamic one and the default: the sheet generates its
  -- own paper, following the theme when that is on. The rest are the fixed
  -- papers, which stay put whatever the theme does.
  local swatches = {
    ui.row({
      key = "swatch-auto",
      width = 24,
      height = 24,
      radius = 12,
      align = "center",
      justify = "center",
      fill = colors.swatch("", seedOf(note), themeColors),
      border = isAuto and "on_surface" or "outline/0.4",
      borderWidth = isAuto and 2 or 1,
      onClick = function()
        setColor(note.id, "")
      end,
    }, {
      ui.glyph({ name = "wand", size = 12, color = themeColors and "on_surface" or "#22262F" }),
    }),
  }

  for _, name in ipairs(colors.NAMES) do
    local selected = note.color == name
    table.insert(swatches, ui.box({
      key = "swatch-" .. name,
      width = 24,
      height = 24,
      radius = 12,
      fill = colors.swatch(name, seedOf(note), themeColors),
      border = selected and "on_surface" or "outline/0.4",
      borderWidth = selected and 2 or 1,
      onClick = function()
        setColor(note.id, name)
      end,
    }))
  end
  -- A tooltip would be the obvious place for this, but `tooltip` on a box or a
  -- flex container needs plugin API 32 and this shell caps out below that. A
  -- caption under the chips says the same thing without a hover, and it says it
  -- to someone who never thinks to hover.
  local caption
  if isAuto then
    caption = themeColors and noctalia.tr("panel.color_dynamic_theme")
      or noctalia.tr("panel.color_dynamic_classic")
  else
    caption = noctalia.tr("panel.color_fixed")
  end

  return ui.column({ gap = 4, align = "stretch" }, {
    ui.row({ gap = 6, align = "center" }, swatches),
    ui.label({
      text = caption,
      fontSize = 10,
      color = "on_surface/0.6",
      maxLines = 2,
    }),
  })
end

local function editView()
  local note = findNote(currentId)
  if note == nil then
    view = "list"
    return listView()
  end

  local armed = pendingDelete == note.id

  return ui.column({ gap = 10, flexGrow = 1, align = "stretch" }, {
    ui.row({ gap = 6, align = "center" }, {
      ui.button({
        glyph = "arrow-left",
        variant = "ghost",
        controlSize = "sm",
        onClick = backToList,
      }),
      -- No title here: a back arrow, a body full of text inputs and a delete
      -- button already say what this screen is.
      ui.spacer({ flexGrow = 1 }),
      ui.button({
        glyph = "arrows-move",
        variant = "secondary",
        controlSize = "sm",
        tooltip = noctalia.tr("panel.move"),
        onClick = moveMode,
      }),
      ui.button({
        glyph = "plus",
        variant = "primary",
        controlSize = "sm",
        tooltip = noctalia.tr("panel.new"),
        onClick = addPostit,
      }),
      ui.button({
        glyph = armed and "check" or "trash",
        variant = armed and "destructive" or "ghost",
        controlSize = "sm",
        onClick = function()
          if armed then
            removeNote(note.id)
          else
            pendingDelete = note.id
            render()
          end
        end,
      }),
    }),
    ui.input({
      key = "title-" .. note.id,
      value = draftTitle,
      placeholder = noctalia.tr("panel.title_placeholder"),
      controlSize = "md",
      focus = true,
      onChange = function(value)
        draftTitle = value
        dirty = true
        lastChangeMs = noctalia.nowMs()
      end,
      onSubmit = function(value)
        draftTitle = value
        dirty = true
        flush()
      end,
    }),
    ui.input({
      key = "content-" .. note.id,
      value = draftContent,
      placeholder = noctalia.tr("panel.content_placeholder"),
      multiline = true,
      flexGrow = 1,
      onChange = function(value)
        draftContent = value
        dirty = true
        lastChangeMs = noctalia.nowMs()
      end,
      onSubmit = function(value)
        draftContent = value
        dirty = true
        flush()
      end,
    }),
    colorPicker(note),
    ui.row({ gap = 8, align = "center" }, {
      ui.label({
        text = dirty and noctalia.tr("panel.unsaved") or noctalia.tr("panel.saved"),
        fontSize = 11,
        color = "on_surface/0.6",
        flexGrow = 1,
      }),
      ui.button({
        text = noctalia.tr("panel.save"),
        variant = "primary",
        controlSize = "sm",
        onClick = function()
          -- Save is the end of the errand: write it and get out of the way.
          flush(true)
          panel.close()
        end,
      }),
    }),
  })
end

-- ── Wiring ──────────────────────────────────────────────────────────────────

render = function()
  if view == "edit" then
    panel.render(ui.column({ padding = 12, gap = 10, flexGrow = 1, align = "stretch" }, { editView() }))
  else
    panel.render(ui.column({ padding = 12, gap = 10, flexGrow = 1, align = "stretch" }, { listView() }))
  end
end

noctalia.state.watch("noctes.notes", function(value)
  notes = type(value) == "table" and value or {}
  render()
end)

noctalia.state.watch("noctes.boundKeys", function(value)
  boundKeys = type(value) == "table" and value or {}
  render()
end)

noctalia.state.watch("noctes.themeColors", function(value)
  themeColors = value == true
  render()
end)

-- The board (and the service, after an add) selects a note here.
noctalia.state.watch("noctes.editing", function(value)
  if type(value) == "string" and value ~= "" then
    openEditor(value)
  end
end)

function onOpen()
  noctalia.state.set("noctes.panelOpen", true)
  -- The desktop-widget editor can add or delete post-its behind this plugin's
  -- back, so the bound-key list is re-read every time the panel opens.
  noctalia.state.set("noctes.cmd", { op = "refresh" })
  local wanted = noctalia.state.get("noctes.editing")
  if type(wanted) == "string" and wanted ~= "" then
    openEditor(wanted)
  else
    render()
  end
end

function onClose()
  flush()
  noctalia.state.set("noctes.panelOpen", false)
  noctalia.state.set("noctes.editing", "")
  view = "list"
  currentId = ""
  pendingDelete = ""
end

-- Debounced autosave: typing marks the draft dirty, the tick flushes it once
-- the user pauses.
function update()
  if dirty and (noctalia.nowMs() - lastChangeMs) >= FLUSH_AFTER_MS then
    flush()
    render()
  end
end

panel.setWantsSecondTicks(true)

local initial = noctalia.state.get("noctes.notes")
notes = type(initial) == "table" and initial or {}
local initialBound = noctalia.state.get("noctes.boundKeys")
boundKeys = type(initialBound) == "table" and initialBound or {}
themeColors = noctalia.state.get("noctes.themeColors") == true
noctalia.state.set("noctes.panelOpen", false)
render()
