-- service.luau, with store.luau and desk.luau under it, against a fake host.

package.path = debug.getinfo(1, "S").source:match("^@(.*)/[^/]*$") .. "/?.lua;" .. package.path
local T = require("host")

local SETTINGS = "/home/test/.local/state/noctalia/settings.toml"
local NOTES = "/data/notes.json"
local PUBLISHED = {
  "noctes.notes", "noctes.ready", "noctes.boundKeys", "noctes.themeColors",
  "noctes.paperOpacity", "noctes.sheetsReady", "noctes.editing",
}

-- One noctes sheet: its id, and its tables as Noctalia writes them.
local function sheet(n, key, output)
  local id = string.format("desktop-widget-%016x", n)
  return {
    id = id,
    text = string.format(
      '\n    [desktop_widgets.widget.%s]\n    output = "%s"\n    type = "remo/noctes:note"\n'
        .. '\n        [desktop_widgets.widget.%s.settings]\n        background = false\n        key = "%s"\n',
      id, output or "DP-2", id, key),
  }
end

-- A settings.toml holding `sheets`, with `listed` in widget_order (all of
-- them by default), on one line the way toml++ writes a short array.
local function settingsWith(sheets, listed)
  local ids, tables = {}, {}
  for _, s in ipairs(listed or sheets) do
    table.insert(ids, '"' .. s.id .. '"')
  end
  for _, s in ipairs(sheets) do
    table.insert(tables, s.text)
  end
  return "[desktop_widgets]\nwidget_order = [ " .. table.concat(ids, ", ") .. " ]\n"
    .. table.concat(tables) .. "\n[dock]\nenabled = true\n"
end

local function start(options)
  options = options or {}
  local host = T.new()
  host.files[NOTES] = T.json.encode({ version = 1, notes = options.notes or {} })
  host.files[SETTINGS] = settingsWith(options.sheets or {})
  if options.notesFile ~= nil then
    host.files[NOTES] = options.notesFile
  end
  if options.responder ~= nil then
    host.responder = options.responder
  end
  local config = { theme_colors = true, paper_opacity = 0.96, tilt = true, save_path = "" }
  for key, value in pairs(options.config or {}) do
    config[key] = value
  end
  local service = host:load("service.luau", config)
  return host, service, config
end

local function counts(host)
  local out = {}
  for _, key in ipairs(PUBLISHED) do
    out[key] = host:sets(key)
  end
  return out
end

local function assertSets(host, before, expected)
  for _, key in ipairs(PUBLISHED) do
    T.eq(host:sets(key) - before[key], expected[key] or 0, key .. " sets")
  end
end

local function has(argv, word)
  for _, part in ipairs(argv) do
    if part == word then
      return true
    end
  end
  return false
end

local function after(argv, flag)
  for index, part in ipairs(argv) do
    if part == flag then
      return argv[index + 1]
    end
  end
end

-- Index of the first set of `key` after position `mark`, or math.huge.
local function firstAfter(log, mark, key)
  for index = mark + 1, #log do
    if log[index] == key then
      return index
    end
  end
  return math.huge
end

local NOTE = { id = "a", key = "k1", title = "A", content = "", color = "" }

-- ── Publishing only what changed ────────────────────────────────────────────

T.test("an edit publishes the notes and nothing else", function()
  local host = start({ notes = { NOTE }, sheets = { sheet(1, "k1") } })
  local before = counts(host)
  host:set("noctes.cmd", { op = "update", id = "a", content = "new" })
  assertSets(host, before, { ["noctes.notes"] = 1 })
  T.eq(host.state["noctes.notes"][1].content, "new", "published content")
end)

T.test("an edit that changes nothing publishes nothing", function()
  local host = start({ notes = { NOTE } })
  local before = counts(host)
  host:set("noctes.cmd", { op = "update", id = "a", title = "A" })
  host:set("noctes.cmd", { op = "set_color", id = "a", color = "" })
  assertSets(host, before, {})
end)

T.test("the tick publishes nothing", function()
  local host, service = start({ notes = { NOTE } })
  local before = #host.setLog
  for _ = 1, 5 do
    host:call(service, "update")
  end
  T.eq(#host.setLog, before, "state sets on idle ticks")
end)

T.test("an unchanged sheet list is not republished", function()
  local host = start({ notes = { NOTE }, sheets = { sheet(1, "k1") } })
  T.eq(host.state["noctes.boundKeys"][1].key, "k1", "first read published")
  local before = counts(host)
  host:set("noctes.cmd", { op = "refresh" })
  host:set("noctes.cmd", { op = "refresh" })
  assertSets(host, before, {})
end)

-- ── Settings ────────────────────────────────────────────────────────────────

T.test("a settings change other than save_path does not reread the notes", function()
  local host, service, config = start({ notes = { NOTE } })
  host.files[NOTES] = T.json.encode({ version = 1, notes = { { id = "z", title = "on disk" } } })
  local before = counts(host)

  config.paper_opacity = 0.5
  host:call(service, "onConfigChanged")
  assertSets(host, before, { ["noctes.paperOpacity"] = 1 })
  T.eq(host.state["noctes.notes"][1].title, "A", "notes as they were")

  host:call(service, "onConfigChanged")
  assertSets(host, before, { ["noctes.paperOpacity"] = 1 })
end)

T.test("a new save_path reads the notes from there", function()
  local host, service, config = start({ notes = { NOTE } })
  host.files["/elsewhere/notes.json"] = T.json.encode({ version = 1, notes = { { id = "z", title = "there" } } })
  config.save_path = "/elsewhere"
  host:call(service, "onConfigChanged")
  T.eq(host.state["noctes.notes"][1].title, "there", "notes from the new folder")
end)

-- ── Keys ────────────────────────────────────────────────────────────────────

T.test("ensure with an empty key opens nothing and creates nothing", function()
  local loose = { id = "l", key = "", title = "loose" }
  local host = start({ notes = { loose } })
  host:set("noctes.cmd", { op = "ensure", key = "" })
  T.eq(#host.state["noctes.notes"], 1, "notes")
  T.eq(host.state["noctes.editing"], "", "editing")
end)

T.test("stick over IPC with no key sticks nothing", function()
  -- The loose note gets its own sheet at start; the IPC call adds nothing.
  local host, service = start({ notes = { { id = "l", key = "", title = "loose" } } })
  local before = #host:runsOf("add")
  host:call(service, "onIpc", "stick", "")
  T.eq(#host:runsOf("add"), before, "add runs")
end)

-- ── Sheets ──────────────────────────────────────────────────────────────────

local function pendingAdds(argv)
  if has(argv, "add") then
    return nil
  end
  return { exitCode = 0, stdout = "", stderr = "" }
end

T.test("a note whose sheet was deleted gets it back over IPC, under its own key", function()
  local host, service = start({ notes = { { id = "o", key = "k9", title = "orphan" } } })
  host:call(service, "onIpc", "stick", " k9 ")
  T.eq(#host:runsOf("add"), 1, "one add")
  local argv = host:runsOf("add")[1]
  T.eq(after(argv, "--key"), "k9", "asks for its own key")
end)

T.test("stick for a key already on the desk makes nothing", function()
  local host, service = start({ notes = { NOTE }, sheets = { sheet(1, "k1") } })
  host:call(service, "onIpc", "stick", "k1")
  T.eq(#host:runsOf("add"), 0, "add runs")
end)

T.test("there is no stick command for a surface to send", function()
  local host = start({ notes = { { id = "o", key = "k9", title = "orphan" } } })
  host:set("noctes.cmd", { op = "stick", id = "o" })
  T.eq(#host:runsOf("add"), 0, "add runs")
end)

T.test("a new post-it is on the desk before its note is published", function()
  local host = start({ responder = pendingAdds })
  host:set("noctes.cmd", { op = "spawn_widget" })
  local mark = #host.setLog
  host:resolve("add", { exitCode = 0, stdout = "key=nota-1\noutput=DP-2\n", stderr = "" })

  T.ok(firstAfter(host.setLog, mark, "noctes.boundKeys") < firstAfter(host.setLog, mark, "noctes.notes"),
    "boundKeys first")
  T.eq(host.state["noctes.editing"], host.state["noctes.notes"][1].id, "selected")
end)

T.test("startup adopts sheets without taking the notes' keys", function()
  local host = start({ notes = { NOTE, { id = "b", key = "k2", title = "B" } } })
  local scatter = host:runsOf("scatter")[1]
  T.ok(scatter ~= nil, "scatter ran once at start")
  local avoid = after(scatter, "--avoid")
  T.ok(avoid:find("k1", 1, true) and avoid:find("k2", 1, true), "avoid holds both keys: " .. avoid)
end)

T.test("gather passes the homes file", function()
  local host, service = start()
  host:call(service, "onOutputsChanged")
  T.eq(after(host:runsOf("gather")[1], "--homes"), "/data/homes.json", "homes path")
end)

-- ── Sheets deleted in the widget editor ─────────────────────────────────────

local function titles(host)
  local out = {}
  for _, note in ipairs(host.state["noctes.notes"]) do
    table.insert(out, note.title)
  end
  table.sort(out)
  return table.concat(out, ",")
end

local TWO = {
  { id = "a", key = "k1", title = "A", updatedAt = 2 },
  { id = "b", key = "k2", title = "B", updatedAt = 1 },
}

T.test("a sheet deleted in the widget editor takes its note with it", function()
  local one, two = sheet(1, "k1"), sheet(2, "k2")
  local host = start({ notes = TWO, sheets = { one, two } })
  host.files[SETTINGS] = settingsWith({ two })
  host:set("noctes.cmd", { op = "refresh" })
  T.eq(titles(host), "B", "notes left")
end)

T.test("the last sheet on the desk deleted takes its note too", function()
  local host = start({ notes = { TWO[1] }, sheets = { sheet(1, "k1") } })
  host.files[SETTINGS] = settingsWith({})
  host:set("noctes.cmd", { op = "refresh" })
  T.eq(titles(host), "", "no notes left")
end)

T.test("a sheet missing its table but still listed is a half-read file, not a deletion", function()
  local one, two = sheet(1, "k1"), sheet(2, "k2")
  local host = start({ notes = TWO, sheets = { one, two } })
  host.files[SETTINGS] = settingsWith({ two }, { one, two })
  host:set("noctes.cmd", { op = "refresh" })
  T.eq(titles(host), "A,B", "both kept")

  host.files[SETTINGS] = settingsWith({ two })
  host:set("noctes.cmd", { op = "refresh" })
  T.eq(titles(host), "B", "deleted once the order agrees")
end)

T.test("every known sheet gone at once keeps every note", function()
  local host = start({ notes = TWO, sheets = { sheet(1, "k1"), sheet(2, "k2") } })
  host.files[SETTINGS] = settingsWith({})
  host:set("noctes.cmd", { op = "refresh" })
  T.eq(titles(host), "A,B", "kept after the reset")

  host.files[SETTINGS] = settingsWith({ sheet(3, "k3") })
  host:set("noctes.cmd", { op = "refresh" })
  T.eq(titles(host), "A,B", "still kept once a new sheet appears")
end)

T.test("a note whose sheet this machine never saw is left alone", function()
  local notes = { TWO[1], { id = "c", key = "k9", title = "C", updatedAt = 0 } }
  local host = start({ notes = notes, sheets = { sheet(1, "k1") } })
  host:set("noctes.cmd", { op = "refresh" })
  T.eq(titles(host), "A,C", "both kept")
end)

T.test("a sheet deleted while the shell was off is noticed at the next start", function()
  local one, two = sheet(1, "k1"), sheet(2, "k2")
  local first = start({ notes = TWO, sheets = { one, two } })
  T.ok(first.files["/data/sheets.json"] ~= nil, "remembered on disk")

  local host = T.new()
  for path, contents in pairs(first.files) do
    host.files[path] = contents
  end
  host.files[SETTINGS] = settingsWith({ two })
  host:load("service.luau", { theme_colors = true, paper_opacity = 0.96, tilt = true, save_path = "" })
  T.eq(titles(host), "B", "deleted at start")
end)

T.test("the panel's bin still takes note and sheet together", function()
  local host = start({ notes = TWO, sheets = { sheet(1, "k1"), sheet(2, "k2") } })
  host:set("noctes.cmd", { op = "remove", id = "a" })
  T.eq(titles(host), "B", "note gone")
  local removal = host:runsOf("remove")[1]
  T.ok(removal ~= nil and after(removal, "--key") == "k1", "sheet removed by key")
end)

-- ── Notes with no sheet at all ──────────────────────────────────────────────

local function helperMissing(argv)
  if has(argv, "--help") then
    return { exitCode = 127, stdout = "", stderr = "python3: not found" }
  end
  return { exitCode = 0, stdout = "", stderr = "" }
end

T.test("new over IPC makes a note and its sheet, with the text", function()
  local host, service = start({ responder = pendingAdds })
  host:call(service, "onIpc", "new", "buy milk")
  T.eq(#host:runsOf("add"), 1, "a sheet is asked for")
  host:resolve("add", { exitCode = 0, stdout = "key=nota-1\noutput=DP-2\n", stderr = "" })

  local note = host.state["noctes.notes"][1]
  T.eq(note.content, "buy milk", "text")
  T.eq(note.key, "nota-1", "bound to the sheet")
  T.eq(host.state["noctes.editing"], note.id, "selected")
end)

T.test("new without the helper still makes the note", function()
  local host, service = start({ responder = helperMissing })
  host:call(service, "onIpc", "new", "buy milk")
  local note = host.state["noctes.notes"][1]
  T.eq(note.content, "buy milk", "text")
  T.eq(note.key, "", "no sheet yet")
end)

local LOOSE = {
  { id = "l1", key = "", title = "one", updatedAt = 2 },
  { id = "l2", key = "", title = "two", updatedAt = 1 },
}

T.test("notes with no sheet get one each once the helper runs, one at a time", function()
  local host = start({ notes = LOOSE, responder = pendingAdds })
  T.eq(#host:runsOf("add"), 1, "one at a time")
  T.eq(after(host:runsOf("add")[1], "--key"), nil, "the helper picks the key")

  host:resolve("add", { exitCode = 0, stdout = "key=nota-1\noutput=DP-2\n", stderr = "" })
  T.eq(#host:runsOf("add"), 2, "then the next")
  host:resolve("add", { exitCode = 0, stdout = "key=nota-2\noutput=DP-2\n", stderr = "" })
  T.eq(#host:runsOf("add"), 2, "and no more")

  local keys = {}
  for _, note in ipairs(host.state["noctes.notes"]) do
    keys[note.title] = note.key
  end
  T.eq(keys.one, "nota-1", "first note's key")
  T.eq(keys.two, "nota-2", "second note's key")
  local stamps = {}
  for _, note in ipairs(host.state["noctes.notes"]) do
    stamps[note.title] = note.updatedAt
  end
  T.eq(stamps.one, 2, "getting paper is not an edit")
  T.eq(stamps.two, 1, "getting paper is not an edit")
end)

T.test("a helper that fails stops the round after one notification", function()
  local host = start({ notes = LOOSE, responder = pendingAdds })
  host:resolve("add", { exitCode = 1, stdout = "", stderr = "boom" })
  T.eq(#host:runsOf("add"), 1, "no second try this start")
  T.eq(#host.errors, 1, "one notification")
end)

T.test("without the helper, notes with no sheet are left as they are", function()
  local host = start({ notes = LOOSE, responder = helperMissing })
  T.eq(#host:runsOf("add"), 0, "nothing asked for")
  T.eq(host.state["noctes.notes"][1].key, "", "still loose")
  T.eq(#host.errors, 0, "no notification on a start nobody acted in")
end)

-- ── The tilt switch ─────────────────────────────────────────────────────────

local function pendingTilts(argv)
  if has(argv, "tilt") then
    return nil
  end
  return { exitCode = 0, stdout = "", stderr = "" }
end

T.test("the tilt marker is written only once the helper succeeds", function()
  local host, service = start({ config = { tilt = false }, responder = pendingTilts })
  T.eq(#host:runsOf("tilt"), 1, "tilt ran")
  T.ok(has(host:runsOf("tilt")[1], "--square"), "squared")
  T.eq(host.files["/data/tilt.state"], nil, "no marker while it runs")

  host:resolve("tilt", { exitCode = 1, stdout = "", stderr = "boom" })
  T.eq(host.files["/data/tilt.state"], nil, "no marker after a failure")

  host:call(service, "onConfigChanged")
  T.eq(#host:runsOf("tilt"), 2, "tried again")
  host:resolve("tilt", { exitCode = 0, stdout = "", stderr = "" })
  T.eq(host.files["/data/tilt.state"], "square", "marker after success")
end)

T.test("a switch flipped while the helper runs is caught up", function()
  local host, service, config = start({ config = { tilt = false }, responder = pendingTilts })
  config.tilt = true
  host:call(service, "onConfigChanged")
  T.eq(#host:runsOf("tilt"), 1, "no second run while one is going")

  host:resolve("tilt", { exitCode = 0, stdout = "", stderr = "" })
  T.eq(#host:runsOf("tilt"), 2, "caught up")
  T.ok(has(host:runsOf("tilt")[2], "--random"), "back to crooked")
end)

-- ── A broken notes.json ─────────────────────────────────────────────────────

T.test("an unreadable notes.json is reported, not replaced", function()
  local host = start({ notesFile = "{ broken" })
  T.eq(#host.errors, 1, "one notification")
  T.eq(host.errors[1].title, "notify.unreadable.title", "title")
  T.ok(host.errors[1].body:find(".unreadable-", 1, true), "body names the aside file")
  T.eq(host.files[NOTES], nil, "nothing written in its place yet")
end)

T.run()
