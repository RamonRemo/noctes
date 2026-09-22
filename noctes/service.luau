--!nonstrict
-- Noctes service - the single owner of the note list.
--
-- Every surface (bar widget, panel, desktop post-it) is a thin client: it reads
-- noctes.* state and mutates through noctes.cmd. Only this entry touches disk.
--
-- Storage:
--   <save_path>/notes.json, or <pluginDataDir>/notes.json when save_path is empty.
--
-- State published:
--   noctes.notes    -> { { id, key, title, content, color, createdAt, updatedAt }, ... }
--   noctes.ready    -> boolean, true once the file has been read
--   noctes.editing  -> note id the panel should open in its editor ("" = list view)
--   noctes.savePath -> resolved directory, informational
--
-- A note's `key` is the handle a desktop post-it binds to, so it survives the
-- list reordering. Keys are unique; "" means the note is panel-only.
--
-- Commands accepted on noctes.cmd:
--   { op = "add", title?, content?, color?, key? }  -- creates and selects it
--   { op = "ensure", key }                          -- selects the note with that
--                                                   -- key, creating it if absent
--   { op = "update", id, title?, content?, color? }
--   { op = "remove", id }
--   { op = "set_color", id, color }   -- "" clears back to automatic
--   { op = "set_key", id, key }
--   { op = "reload" }
--
-- Order invariant: newest updatedAt first. Surfaces render noctes.notes
-- directly and never re-sort.

-- Mirrors colors.luau: the eight papers plus glass. The service does not draw
-- anything, but it validates what it stores, and a color it does not recognise
-- is quietly reset - which is how glass notes kept coming back blank.
local PALETTE = {
  "yellow", "orange", "pink", "red", "purple", "blue", "green", "gray", "glass",
}

local SETTINGS_PATH = "~/.local/state/noctalia/settings.toml"

local notes = {}
local boundKeys = {}
local resolvedDir = nil
local loaded = false
local idCounter = 0

local function isKnownColor(name)
  for _, c in ipairs(PALETTE) do
    if c == name then
      return true
    end
  end
  return false
end

-- "" means automatic: the desktop post-it then derives the paper color from its
-- key, so notes look different from each other without anyone picking colors.
local function defaultColor()
  local c = noctalia.getConfig("default_color")
  if type(c) == "string" and isKnownColor(c) then
    return c
  end
  return ""
end

local function notesFilePath()
  if resolvedDir == nil then
    return nil
  end
  return resolvedDir .. "/notes.json"
end

-- Unique within a run: nowMs alone collides when two notes are added in the
-- same millisecond (double-click on the board's add button).
local function newId()
  idCounter = idCounter + 1
  return string.format("%d-%d", math.floor(noctalia.nowMs()), idCounter)
end

-- Newest first. There is no pinning any more: every note is a sheet stuck to
-- the desktop at a position of its own, so an extra "keep this one on top of a
-- list" flag meant nothing.
local function sortNotes()
  table.sort(notes, function(a, b)
    return (a.updatedAt or 0) > (b.updatedAt or 0)
  end)
end

-- The plugin-wide look, mirrored into state for the sheets. The tick below
-- republishes it: a sheet that loaded before the service's first publish would
-- otherwise sit on the defaults forever, and the watchers ignore a value that
-- has not changed, so the repeat costs nothing.
local function publishPluginPrefs()
  noctalia.state.set("noctes.themeColors", noctalia.getConfig("theme_colors") == true)
  noctalia.state.set("noctes.paperOpacity", tonumber(noctalia.getConfig("paper_opacity")) or 0.96)
end

local function publish()
  noctalia.state.set("noctes.notes", notes)
  noctalia.state.set("noctes.ready", loaded)
  noctalia.state.set("noctes.boundKeys", boundKeys)
  -- Published rather than read per widget: a desktop widget's getConfig sees
  -- its own settings, and this way toggling a switch repaints the wall at once
  -- instead of on the next reload.
  publishPluginPrefs()
end

-- Which keys actually have a post-it on the desktop. The widgets live in
-- Noctalia's settings.toml, not in this plugin's data, so the panel can only
-- tell a stuck note from a loose one by reading that file back.
local function refreshBoundKeys()
  noctalia.readFileAsync(noctalia.expandPath(SETTINGS_PATH), function(contents, err)
    if contents == nil then
      noctalia.log("noctes: cannot read settings: " .. tostring(err))
      return
    end

    -- id -> the output its sheet sits on, so the panel can say which screen a
    -- post-it is on. A sheet on another monitor is the usual reason a note
    -- looks like it exists nowhere.
    local isPostit = {}
    for id, body in string.gmatch(contents, "%[desktop_widgets%.widget%.([%w%-]+)%]([^%[]*)") do
      if string.find(body, 'type = "remo/noctes:note"', 1, true) then
        isPostit[id] = string.match(body, 'output%s*=%s*"([^"]*)"') or "?"
      end
    end

    local found = {}
    for id, body in string.gmatch(contents, "%[desktop_widgets%.widget%.([%w%-]+)%.settings%]([^%[]*)") do
      if isPostit[id] ~= nil then
        local key = string.match(body, 'key%s*=%s*"([^"]*)"')
        if key ~= nil and key ~= "" then
          table.insert(found, { key = key, output = isPostit[id] })
        end
      end
    end

    boundKeys = found
    noctalia.state.set("noctes.boundKeys", boundKeys)
  end)
end

-- Autosave fires about once a second while someone types, and each one would
-- otherwise rewrite the whole file. Mutations mark the list dirty instead, and
-- the tick below writes at most once every couple of seconds; onExit catches
-- whatever is still pending at teardown.
local saveDue = false

local function writeNotes()
  local path = notesFilePath()
  if path == nil then
    return
  end
  local encoded, err = noctalia.json.encode({ notes = notes }, true)
  if encoded == nil then
    noctalia.log("noctes: encode failed: " .. tostring(err))
    return
  end
  local ok, writeErr = noctalia.writeFile(path, encoded)
  if not ok then
    noctalia.log("noctes: write failed: " .. tostring(writeErr))
  end
end

local function save()
  saveDue = true
end

local function flushSave()
  if saveDue then
    saveDue = false
    writeNotes()
  end
end

function update()
  flushSave()
  publishPluginPrefs()
end

function onExit()
  flushSave()
end

noctalia.setUpdateInterval(2000)

local function normalize(raw)
  if type(raw) ~= "table" then
    return nil
  end
  local id = raw.id
  if type(id) ~= "string" or id == "" then
    id = newId()
  end
  local color = raw.color
  if type(color) ~= "string" or (color ~= "" and not isKnownColor(color)) then
    color = defaultColor()
  end
  return {
    id = id,
    key = type(raw.key) == "string" and raw.key or "",
    title = type(raw.title) == "string" and raw.title or "",
    content = type(raw.content) == "string" and raw.content or "",
    color = color,
    pinned = raw.pinned == true,
    createdAt = type(raw.createdAt) == "number" and raw.createdAt or os.time(),
    updatedAt = type(raw.updatedAt) == "number" and raw.updatedAt or os.time(),
  }
end

local function load()
  -- Re-reading replaces the in-memory list, so anything still waiting on the
  -- debounce has to reach disk first or it is simply gone.
  flushSave()

  local path = notesFilePath()
  if path == nil then
    loaded = true
    publish()
    return
  end
  if not noctalia.fileExists(path) then
    loaded = true
    publish()
    return
  end
  noctalia.readFileAsync(path, function(contents, err)
    if contents == nil then
      noctalia.log("noctes: read failed: " .. tostring(err))
      loaded = true
      publish()
      return
    end
    local decoded, decodeErr = noctalia.json.decode(contents)
    if decoded == nil then
      noctalia.log("noctes: decode failed: " .. tostring(decodeErr))
      loaded = true
      publish()
      return
    end
    local list = decoded.notes
    if type(list) ~= "table" then
      list = decoded
    end
    notes = {}
    if type(list) == "table" then
      for _, raw in ipairs(list) do
        local note = normalize(raw)
        if note ~= nil then
          table.insert(notes, note)
        end
      end
    end
    sortNotes()
    loaded = true
    publish()
  end)
end

local function initSavePath(callback)
  local configured = noctalia.string.trim(noctalia.getConfig("save_path") or "")
  local dir
  if configured ~= "" then
    dir = noctalia.expandPath(configured)
  else
    dir = noctalia.pluginDataDir()
  end
  if dir == nil or dir == "" then
    noctalia.log("noctes: no writable data directory")
    callback()
    return
  end
  local ok, err = noctalia.mkdirAll(dir)
  if not ok then
    noctalia.log("noctes: mkdir failed: " .. tostring(err))
  end
  resolvedDir = dir
  noctalia.state.set("noctes.savePath", resolvedDir)
  callback()
end

local function findIndex(id)
  for i, note in ipairs(notes) do
    if note.id == id then
      return i
    end
  end
  return nil
end

-- ── Mutations ───────────────────────────────────────────────────────────────

local function findByKey(key)
  for _, note in ipairs(notes) do
    if (note.key or "") == key then
      return note
    end
  end
  return nil
end

local function addNote(title, content, color, key)
  local now = os.time()
  local note = {
    id = newId(),
    key = type(key) == "string" and key or "",
    title = type(title) == "string" and title or "",
    content = type(content) == "string" and content or "",
    color = (type(color) == "string" and isKnownColor(color)) and color or defaultColor(),
    pinned = false,
    createdAt = now,
    updatedAt = now,
  }
  table.insert(notes, note)
  sortNotes()
  save()
  publish()
  -- Hand the new note straight to the panel: the post-it that created it cannot
  -- take keyboard focus, so something has to open the editor.
  noctalia.state.set("noctes.editing", note.id)
end

local function updateNote(id, title, content, color)
  local index = findIndex(id)
  if index == nil then
    return
  end
  local note = notes[index]
  if type(title) == "string" then
    note.title = title
  end
  if type(content) == "string" then
    note.content = content
  end
  -- An empty string clears the color back to automatic.
  if type(color) == "string" and (color == "" or isKnownColor(color)) then
    note.color = color
  end
  note.updatedAt = os.time()
  sortNotes()
  save()
  publish()
end

-- Forward declaration: removeNote takes the widget down with the note, and
-- dropWidget is defined further below with the other helpers that shell out.
local dropWidget

local function removeNote(id)
  local index = findIndex(id)
  if index == nil then
    return
  end
  local key = notes[index].key or ""
  table.remove(notes, index)
  if key ~= "" then
    dropWidget(key)
  end
  save()
  publish()
  if noctalia.state.get("noctes.editing") == id then
    noctalia.state.set("noctes.editing", "")
  end
end

-- A key binds a note to a desktop widget, so it has to stay unique: taking a
-- key frees it from whatever note held it before.
local function setKey(id, key)
  local index = findIndex(id)
  if index == nil or type(key) ~= "string" then
    return
  end
  key = noctalia.string.trim(key)
  for _, note in ipairs(notes) do
    if note.id ~= id and (note.key or "") == key and key ~= "" then
      note.key = ""
    end
  end
  notes[index].key = key
  notes[index].updatedAt = os.time()
  sortNotes()
  save()
  publish()
end

-- Creates the desktop widget itself, which Noctalia exposes no IPC for: the
-- helper edits settings.toml, so a post-it appears already tilted, colored and
-- without the host's background panel. Without this the only route is the
-- desktop-widget editor, which produces an untilted, keyless, backgrounded
-- sheet that looks like every other one.
local function spawnWidget()
  local dir = noctalia.pluginDir()
  if dir == nil then
    noctalia.log("noctes: no plugin dir, cannot add a widget")
    return
  end

  local output = noctalia.focusedOutputName()
  local width, height = 1920, 1080
  for _, screen in ipairs(noctalia.outputs()) do
    if output == nil then
      output = screen.name
    end
    if screen.name == output then
      width = math.floor(screen.width / (screen.scale or 1))
      height = math.floor(screen.height / (screen.scale or 1))
    end
  end
  if output == nil then
    noctalia.log("noctes: no output to place a widget on")
    return
  end

  -- The keys already spoken for are split across two places: notes here, and
  -- widget bindings in settings.toml. The helper reads the second set, so it
  -- picks the key and reports it back on its first stdout line.
  local avoid = {}
  for _, note in ipairs(notes) do
    if (note.key or "") ~= "" then
      table.insert(avoid, note.key)
    end
  end

  noctalia.runAsync({
    dir .. "/tools/noctes-widget", "add",
    "--output", output,
    "--screen", string.format("%dx%d", width, height),
    "--avoid", table.concat(avoid, ","),
  }, function(result)
    if result.exitCode ~= 0 then
      noctalia.log("noctes: noctes-widget failed: " .. tostring(result.stderr))
      noctalia.notifyError(noctalia.tr("notify.add_failed.title"),
        noctalia.tr("notify.add_failed.body"))
      return
    end
    local key = string.match(result.stdout or "", "key=([^\n]+)")
    if key == nil then
      noctalia.log("noctes: noctes-widget gave no key")
      return
    end
    addNote(nil, nil, nil, noctalia.string.trim(key))
    refreshBoundKeys()
  end, 10000)
end

-- Noctalia's desktop-widget editor is what moves, resizes and rotates a sheet,
-- and there is no Luau call for it - only the IPC command, so the plugin asks
-- its own CLI. Leaving the editor writes settings.toml, which is what the
-- scatter watcher listens for, so a sheet added while in there still ends up
-- tilted and keyed.
local function toggleWidgetEditor()
  noctalia.runAsync({ "noctalia", "msg", "desktop-widgets-toggle-edit" }, nil, 5000)
end

-- Sticks an existing note to the desktop, for notes that predate the widget or
-- were made with the panel alone.
local function stickNote(id)
  local index = findIndex(id)
  if index == nil then
    return
  end
  local note = notes[index]
  local dir = noctalia.pluginDir()
  if dir == nil then
    return
  end

  local output = noctalia.focusedOutputName()
  local width, height = 1920, 1080
  for _, screen in ipairs(noctalia.outputs()) do
    if output == nil then
      output = screen.name
    end
    if screen.name == output then
      width = math.floor(screen.width / (screen.scale or 1))
      height = math.floor(screen.height / (screen.scale or 1))
    end
  end
  if output == nil then
    return
  end

  local argv = {
    dir .. "/tools/noctes-widget", "add",
    "--output", output,
    "--screen", string.format("%dx%d", width, height),
  }
  -- A note that already has a key keeps it; a loose one gets whatever the
  -- helper picks, and the note is renamed to match.
  if (note.key or "") ~= "" then
    table.insert(argv, "--key")
    table.insert(argv, note.key)
  end

  noctalia.runAsync(argv, function(result)
    if result.exitCode ~= 0 then
      noctalia.notifyError(noctalia.tr("notify.add_failed.title"),
        noctalia.tr("notify.add_failed.body"))
      return
    end
    local key = string.match(result.stdout or "", "key=([^\n]+)")
    if key ~= nil and (note.key or "") == "" then
      setKey(id, noctalia.string.trim(key))
    end
    refreshBoundKeys()
  end, 10000)
end

-- Deleting a note takes its post-it off the desktop too: a widget bound to a
-- key nothing answers to is just a blank sheet nobody asked for.
dropWidget = function(key)
  local dir = noctalia.pluginDir()
  if dir == nil or key == nil or key == "" then
    return
  end
  noctalia.runAsync({ dir .. "/tools/noctes-widget", "remove", "--key", key },
    function()
      refreshBoundKeys()
    end, 10000)
end

-- Called by a post-it that has no note yet: the widget knows its key, not
-- whether anything answers to it.
local function ensureKey(key)
  if type(key) ~= "string" then
    return
  end
  local existing = findByKey(key)
  if existing ~= nil then
    noctalia.state.set("noctes.editing", existing.id)
    return
  end
  addNote(nil, nil, nil, key)
end

-- ── Wiring ──────────────────────────────────────────────────────────────────

noctalia.state.watch("noctes.cmd", function(cmd)
  if type(cmd) ~= "table" then
    return
  end
  local op = cmd.op
  if op == "add" then
    addNote(cmd.title, cmd.content, cmd.color, cmd.key)
  elseif op == "spawn_widget" then
    spawnWidget()
  elseif op == "toggle_edit" then
    toggleWidgetEditor()
  elseif op == "stick" then
    stickNote(cmd.id)
  elseif op == "refresh" then
    refreshBoundKeys()
  elseif op == "ensure" then
    ensureKey(cmd.key)
  elseif op == "update" then
    updateNote(cmd.id, cmd.title, cmd.content, cmd.color)
  elseif op == "remove" then
    removeNote(cmd.id)
  elseif op == "set_color" then
    updateNote(cmd.id, nil, nil, cmd.color)
  elseif op == "set_key" then
    setKey(cmd.id, cmd.key)
  elseif op == "reload" then
    load()
  end
  noctalia.state.set("noctes.cmd", nil)
end)

-- IPC, for keybinds and scripts:
--   noctalia msg plugin remo/noctes:service all new ["text"]
--   noctalia msg plugin remo/noctes:service all desk
--   noctalia msg plugin remo/noctes:service all move
--   noctalia msg plugin remo/noctes:service all open <key>
--   noctalia msg plugin remo/noctes:service all reload
function onIpc(event, payload)
  if event == "new" then
    addNote(nil, payload, nil, nil)
  elseif event == "desk" then
    spawnWidget()
  elseif event == "move" then
    toggleWidgetEditor()
  elseif event == "open" then
    ensureKey(noctalia.string.trim(payload or ""))
  elseif event == "reload" then
    load()
  end
end

-- Settings changed: save_path may now point somewhere else, so re-resolve and
-- re-read rather than writing the in-memory list to a stale directory.
function onConfigChanged()
  initSavePath(function()
    load()
  end)
end

noctalia.state.set("noctes.editing", "")
publish()
refreshBoundKeys()
initSavePath(function()
  load()
end)
