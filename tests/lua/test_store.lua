-- store.luau: the note list and notes.json.

package.path = debug.getinfo(1, "S").source:match("^@(.*)/[^/]*$") .. "/?.lua;" .. package.path
local T = require("host")

local PATH = "/data/notes.json"

local function fresh(files)
  local host = T.new()
  for path, contents in pairs(files or {}) do
    host.files[path] = contents
  end
  local store = host:module("store.luau", { save_path = "" })
  store.useDirectory()
  return store, host
end

local function saved(host, path)
  local decoded = T.json.decode(host.files[path or PATH])
  return decoded and decoded.notes
end

T.test("an empty key names no note, even with sheetless notes around", function()
  local store = fresh()
  store.load()
  store.add({ title = "loose" })
  T.eq(store.byKey(""), nil, "byKey('')")
  T.eq(store.byKey(nil), nil, "byKey(nil)")
end)

T.test("an update that changes nothing is not a change", function()
  local store, host = fresh()
  store.load()
  local note = store.add({ title = "a", content = "b", color = "yellow" })
  store.flush()
  local before = host.files[PATH]
  host.time = host.time + 60

  T.eq(store.update(note.id, { title = "a", content = "b", color = "yellow" }), nil, "result")
  T.eq(note.updatedAt, 1700000000, "updatedAt")
  store.flush()
  T.eq(host.files[PATH], before, "file")
end)

T.test("an update that changes something bumps, sorts and saves", function()
  local store, host = fresh()
  store.load()
  local older = store.add({ title = "older" })
  host.time = host.time + 1
  store.add({ title = "newer" })
  host.time = host.time + 1

  T.ok(store.update(older.id, { content = "edited" }) ~= nil, "update returns the note")
  T.eq(store.notes[1].id, older.id, "edited note first")
  store.flush()
  T.eq(saved(host)[1].content, "edited", "saved content")
end)

T.test("notes touched in the same second keep one order", function()
  local store, host = fresh()
  store.load()
  local a = store.add({ title = "a" })
  host.clock = host.clock + 1
  local b = store.add({ title = "b" })
  host.clock = host.clock + 1
  local c = store.add({ title = "c" })
  for _ = 1, 5 do
    store.update(a.id, { title = "a" .. _ })
    store.update(a.id, { title = "a" })
  end
  -- Same updatedAt for all three; a was edited last but in the same second.
  local order = {}
  for _, note in ipairs(store.notes) do
    table.insert(order, note.title)
  end
  T.eq(table.concat(order, ","), "c,b,a", "order by creation, newest first")
  T.ok(b and c, "created")
end)

T.test("an unreadable file is moved aside, never written over", function()
  local store, host = fresh({ [PATH] = '{ "notes": [ { "title": "typo" ' })
  local problem = store.load()

  T.ok(problem ~= nil and problem.moved, "reported as moved")
  local aside = PATH .. ".unreadable-1700000000"
  T.eq(problem.path, aside, "aside path")
  T.eq(host.files[aside], '{ "notes": [ { "title": "typo" ', "aside file untouched")

  store.add({ title = "new" })
  store.flush()
  T.eq(saved(host)[1].title, "new", "fresh notes.json")
  T.eq(host.files[aside], '{ "notes": [ { "title": "typo" ', "aside file still untouched")
end)

T.test("a file that parses to something other than a list is set aside too", function()
  local store, host = fresh({ [PATH] = "42" })
  local problem = store.load()
  T.ok(problem ~= nil and problem.moved, "moved")
  T.eq(host.files[PATH], nil, "path freed")
end)

T.test("an unreadable file that cannot be moved blocks every save", function()
  local store, host = fresh({ [PATH] = "{ nope" })
  host.failRename = true
  local problem = store.load()

  T.ok(problem ~= nil and not problem.moved, "reported as stuck")
  store.add({ title = "would overwrite" })
  store.flush()
  T.eq(host.files[PATH], "{ nope", "file untouched")

  -- Fixed by hand and reloaded: saving resumes.
  host.failRename = false
  host.files[PATH] = '{ "version": 1, "notes": [] }'
  T.eq(store.load(), nil, "reload succeeds")
  store.add({ title = "after" })
  store.flush()
  T.eq(saved(host)[1].title, "after", "saved again")
end)

T.test("a reload that fails keeps the notes in memory and saves them", function()
  local store, host = fresh({ [PATH] = '{ "version": 1, "notes": [ { "id": "x", "title": "kept" } ] }' })
  T.eq(store.load(), nil, "first load")
  host.files[PATH] = "{ broken by hand"

  store.load()
  T.eq(store.notes[1].title, "kept", "in memory")
  store.flush()
  T.eq(saved(host)[1].title, "kept", "written to a fresh file")
end)

T.test("an empty folder receives the notes in memory", function()
  local store, host = fresh({ [PATH] = '{ "version": 1, "notes": [ { "id": "x", "title": "moving" } ] }' })
  store.load()
  store.useDirectory()

  host.files[PATH] = nil
  store.load()
  store.flush()
  T.eq(saved(host)[1].title, "moving", "copied into the new folder")
end)

T.test("a first start with no file writes nothing", function()
  local store, host = fresh()
  store.load()
  store.flush()
  T.eq(host.files[PATH], nil, "no file")
end)

T.test("older shapes of the file still load", function()
  local bare = '[ { "id": "1", "title": "bare" } ]'
  local store = fresh({ [PATH] = bare })
  T.eq(store.load(), nil, "bare array loads")
  T.eq(store.notes[1].title, "bare", "bare array note")

  store = fresh({ [PATH] = '{ "notes": [ { "id": "1", "title": "unversioned" } ] }' })
  store.load()
  T.eq(store.notes[1].title, "unversioned", "unversioned note")
end)

T.run()
