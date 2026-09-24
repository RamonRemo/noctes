-- service.luau, with store.luau and desk.luau under it, against a fake host.

package.path = debug.getinfo(1, "S").source:match("^@(.*)/[^/]*$") .. "/?.lua;" .. package.path
local T = require("host")

local SETTINGS = "/home/test/.local/state/noctalia/settings.toml"
local NOTES = "/data/notes.json"
local PUBLISHED = {
  "noctes.notes", "noctes.ready", "noctes.boundKeys", "noctes.themeColors",
  "noctes.paperOpacity", "noctes.sheetsReady", "noctes.editing",
}

local function sheet(n, key, output)
  local id = string.format("desktop-widget-%016x", n)
  return string.format(
    '\n    [desktop_widgets.widget.%s]\n    output = "%s"\n    type = "remo/noctes:note"\n'
      .. '\n        [desktop_widgets.widget.%s.settings]\n        background = false\n        key = "%s"\n',
    id, output or "DP-2", id, key)
end

local function start(options)
  options = options or {}
  local host = T.new()
  host.files[NOTES] = T.json.encode({ version = 1, notes = options.notes or {} })
  host.files[SETTINGS] = "[desktop_widgets]\nwidget_order = []\n" .. table.concat(options.sheets or {})
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
  local host, service = start({ notes = { { id = "l", key = "", title = "loose" } } })
  host:call(service, "onIpc", "stick", "")
  T.eq(#host:runsOf("add"), 0, "add runs")
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
