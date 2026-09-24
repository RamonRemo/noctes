-- A stand-in for Noctalia, to run the plugin's Luau outside the shell.
--
-- The Luau in noctes/ sticks to syntax Lua 5.4 also reads, so the real files
-- load here unchanged. What the shell provides is faked, on purpose where the
-- shell's behaviour is the thing under test:
--
--   * noctalia.state.set wakes every watcher of the key on every call, changed
--     value or not, as PluginStateStore::set does. Watchers get a copy, as they
--     get a fresh JSON decode in the shell, and run later, not inside set().
--   * runAsync and readFileAsync answer later too: a test decides when, and
--     with what, through host:resolve or an automatic responder.
--   * Files live in a table. Nothing here touches the disk.
--
-- Each entry (service, panel, sheet, bar) gets its own globals and its own
-- module cache, the way each runs in its own VM in the shell.

local M = {}

local here = debug.getinfo(1, "S").source:match("^@(.*)/[^/]*$") or "."
-- NOCTES_PLUGIN points the tests at another copy of the plugin, which is how a
-- change is checked to be what makes a test pass: revert it in a copy, run
-- against the copy, and the test has to fail.
M.PLUGIN = os.getenv("NOCTES_PLUGIN") or (here .. "/../../noctes")

-- ── JSON ────────────────────────────────────────────────────────────────────

local json = {}

local function encodeString(s)
  return '"' .. s:gsub('[%c"\\]', function(c)
    local named = { ['"'] = '\\"', ["\\"] = "\\\\", ["\n"] = "\\n", ["\r"] = "\\r", ["\t"] = "\\t" }
    return named[c] or string.format("\\u%04x", c:byte())
  end) .. '"'
end

function json.encode(value)
  local kind = type(value)
  if value == nil then
    return "null"
  elseif kind == "boolean" then
    return tostring(value)
  elseif kind == "number" then
    if math.type(value) == "integer" then
      return string.format("%d", value)
    end
    return string.format("%.17g", value)
  elseif kind == "string" then
    return encodeString(value)
  elseif kind == "table" then
    if #value > 0 or next(value) == nil then
      local parts = {}
      for _, item in ipairs(value) do
        table.insert(parts, json.encode(item))
      end
      return "[" .. table.concat(parts, ",") .. "]"
    end
    local keys = {}
    for key in pairs(value) do
      table.insert(keys, key)
    end
    table.sort(keys)
    local parts = {}
    for _, key in ipairs(keys) do
      table.insert(parts, encodeString(tostring(key)) .. ":" .. json.encode(value[key]))
    end
    return "{" .. table.concat(parts, ",") .. "}"
  end
  error("cannot encode " .. kind)
end

function json.decode(text)
  local at = 1
  local parseValue

  local function fail(why)
    error({ json = why .. " at " .. at }, 0)
  end
  local function skip()
    at = text:find("[^ \t\r\n]", at) or #text + 1
  end
  local function literal(word, result)
    if text:sub(at, at + #word - 1) ~= word then
      fail("bad literal")
    end
    at = at + #word
    return result
  end
  local function parseString()
    local out = {}
    at = at + 1
    while true do
      local c = text:sub(at, at)
      if c == "" then
        fail("unterminated string")
      elseif c == '"' then
        at = at + 1
        return table.concat(out)
      elseif c == "\\" then
        local e = text:sub(at + 1, at + 1)
        local simple = { ['"'] = '"', ["\\"] = "\\", ["/"] = "/", b = "\b", f = "\f", n = "\n", r = "\r", t = "\t" }
        if simple[e] then
          table.insert(out, simple[e])
          at = at + 2
        elseif e == "u" then
          table.insert(out, utf8.char(tonumber(text:sub(at + 2, at + 5), 16)))
          at = at + 6
        else
          fail("bad escape")
        end
      else
        table.insert(out, c)
        at = at + 1
      end
    end
  end
  parseValue = function()
    skip()
    local c = text:sub(at, at)
    if c == "{" then
      local object = {}
      at = at + 1
      skip()
      if text:sub(at, at) == "}" then
        at = at + 1
        return object
      end
      while true do
        skip()
        if text:sub(at, at) ~= '"' then
          fail("expected key")
        end
        local key = parseString()
        skip()
        if text:sub(at, at) ~= ":" then
          fail("expected ':'")
        end
        at = at + 1
        object[key] = parseValue()
        skip()
        local sep = text:sub(at, at)
        at = at + 1
        if sep == "}" then
          return object
        elseif sep ~= "," then
          fail("expected ',' or '}'")
        end
      end
    elseif c == "[" then
      local array = {}
      at = at + 1
      skip()
      if text:sub(at, at) == "]" then
        at = at + 1
        return array
      end
      while true do
        table.insert(array, parseValue())
        skip()
        local sep = text:sub(at, at)
        at = at + 1
        if sep == "]" then
          return array
        elseif sep ~= "," then
          fail("expected ',' or ']'")
        end
      end
    elseif c == '"' then
      return parseString()
    elseif c == "t" then
      return literal("true", true)
    elseif c == "f" then
      return literal("false", false)
    elseif c == "n" then
      return literal("null", nil)
    end
    local number = text:match("^-?%d+%.?%d*[eE]?[-+]?%d*", at)
    if number == nil or number == "" then
      fail("unexpected character")
    end
    at = at + #number
    return math.tointeger(tonumber(number)) or tonumber(number)
  end

  local ok, result = pcall(function()
    local value = parseValue()
    skip()
    if at <= #text then
      fail("trailing characters")
    end
    return value
  end)
  if ok then
    return result
  end
  return nil, type(result) == "table" and result.json or tostring(result)
end

M.json = json

local function copy(value)
  if type(value) ~= "table" then
    return value
  end
  local out = {}
  for key, item in pairs(value) do
    out[key] = copy(item)
  end
  return out
end

-- ── ui ──────────────────────────────────────────────────────────────────────

-- Every ui.* call returns a plain node, so a test can walk the tree that was
-- rendered and press what is in it.
local ui = setmetatable({}, {
  __index = function(_, kind)
    return function(props, children)
      return { kind = kind, props = props or {}, children = children or {} }
    end
  end,
})

function M.find(tree, predicate, found)
  found = found or {}
  if type(tree) ~= "table" then
    return found
  end
  if tree.kind ~= nil and predicate(tree) then
    table.insert(found, tree)
  end
  for _, child in ipairs(tree.children or {}) do
    M.find(child, predicate, found)
  end
  return found
end

-- ── The host ────────────────────────────────────────────────────────────────

local Host = {}
Host.__index = Host

function M.new()
  local host = setmetatable({}, Host)
  host.files = {}
  host.state = {}
  host.watchers = {}
  host.queue = {}
  host.setLog = {}
  host.runs = {}
  host.pending = {}
  host.logs = {}
  host.errors = {}
  host.panels = {}
  host.clock = 1000
  host.time = 1700000000
  host.failRename = false
  host.outputs = { { name = "DP-2", width = 3440, height = 1440, scale = 1, focused = true } }
  -- argv -> result, or nil to leave the run pending for host:resolve.
  host.responder = function()
    return { exitCode = 0, stdout = "", stderr = "" }
  end
  return host
end

function Host:sets(key)
  local count = 0
  for _, name in ipairs(self.setLog) do
    if name == key then
      count = count + 1
    end
  end
  return count
end

function Host:later(fn, ...)
  local args = table.pack(...)
  table.insert(self.queue, function()
    fn(table.unpack(args, 1, args.n))
  end)
end

-- Runs everything that was waiting, including what that sets off in turn.
function Host:drain()
  local guard = 0
  while #self.queue > 0 do
    guard = guard + 1
    assert(guard < 10000, "the queue never empties: something re-arms itself forever")
    table.remove(self.queue, 1)()
  end
end

-- Answers the first pending run whose argv contains `word`.
function Host:resolve(word, result)
  for index, pending in ipairs(self.pending) do
    for _, part in ipairs(pending.argv) do
      if part == word then
        table.remove(self.pending, index)
        self:later(pending.callback, result)
        self:drain()
        return pending.argv
      end
    end
  end
  error("no pending run with " .. word)
end

function Host:runsOf(word)
  local found = {}
  for _, argv in ipairs(self.runs) do
    for _, part in ipairs(argv) do
      if part == word then
        table.insert(found, argv)
        break
      end
    end
  end
  return found
end

function Host:api(entry)
  local host = self
  local api = {}

  api.state = {
    set = function(key, value)
      host.state[key] = copy(value)
      table.insert(host.setLog, key)
      for _, watcher in ipairs(host.watchers[key] or {}) do
        host:later(watcher, copy(value))
      end
    end,
    get = function(key)
      return copy(host.state[key])
    end,
    watch = function(key, fn)
      host.watchers[key] = host.watchers[key] or {}
      table.insert(host.watchers[key], fn)
    end,
  }

  api.string = {
    trim = function(s)
      return (tostring(s):match("^%s*(.-)%s*$"))
    end,
  }
  api.json = {
    encode = function(value)
      return json.encode(value)
    end,
    decode = json.decode,
  }

  api.getConfig = function(key)
    return entry.config[key]
  end
  api.log = function(message)
    table.insert(host.logs, message)
  end
  api.notifyError = function(title, body)
    table.insert(host.errors, { title = title, body = body })
  end
  api.notify = api.notifyError
  api.tr = function(key, subst)
    if subst ~= nil and subst.path ~= nil then
      return key .. " " .. subst.path
    end
    return key
  end
  api.trp = function(key)
    return key
  end
  api.nowMs = function()
    return host.clock
  end
  api.setUpdateInterval = function() end
  api.expandPath = function(path)
    return (path:gsub("^~", "/home/test"))
  end
  api.pluginDir = function()
    return "/plugin"
  end
  api.pluginDataDir = function()
    return "/data"
  end
  api.mkdirAll = function()
    return true
  end
  api.fileExists = function(path)
    return host.files[path] ~= nil
  end
  api.readFile = function(path)
    if host.files[path] == nil then
      return nil, "cannot open file"
    end
    return host.files[path]
  end
  api.readFileAsync = function(path, callback)
    local contents = host.files[path]
    host:later(callback, contents, contents == nil and "cannot open file" or nil)
  end
  api.writeFile = function(path, contents)
    host.files[path] = contents
    return true
  end
  api.removeFile = function(path)
    host.files[path] = nil
    return true
  end
  api.renameFile = function(from, to)
    if host.failRename or host.files[from] == nil then
      return false, "rename failed"
    end
    host.files[to], host.files[from] = host.files[from], nil
    return true
  end
  api.runAsync = function(argv, callback)
    table.insert(host.runs, argv)
    local result = host.responder(argv)
    if callback ~= nil then
      if result ~= nil then
        host:later(callback, result)
      else
        table.insert(host.pending, { argv = argv, callback = callback })
      end
    end
    return true
  end
  api.focusedOutputName = function()
    for _, output in ipairs(host.outputs) do
      if output.focused then
        return output.name
      end
    end
    return nil
  end
  api.outputs = function()
    return copy(host.outputs)
  end
  api.togglePanel = function(id)
    table.insert(host.panels, id)
  end
  api.openSettings = function() end
  api.loadFont = function()
    return "Patrick Hand"
  end
  return api
end

-- A fresh VM: its own globals and module cache. `config` is what its
-- getConfig sees.
function Host:entry(config)
  local entry = { config = config or {}, modules = {}, renders = 0 }
  local env = setmetatable({}, { __index = _G })
  entry.env = env

  local function rendered(tree)
    entry.tree = tree
    entry.renders = entry.renders + 1
  end
  env.noctalia = self:api(entry)
  env.ui = ui
  env.panel = {
    render = rendered,
    close = function()
      entry.closed = true
    end,
    setWantsSecondTicks = function() end,
  }
  env.desktopWidget = {
    render = rendered,
    setWantsSecondTicks = function() end,
    setNeedsFrameTick = function() end,
  }
  env.barWidget = {
    setGlyph = function() end,
    setText = function(text)
      entry.text = text
      entry.renders = entry.renders + 1
    end,
    setTooltip = function() end,
    isVertical = function()
      return false
    end,
  }
  local host = self
  env.os = setmetatable({
    time = function()
      return host.time
    end,
  }, { __index = os })
  env.require = function(name)
    local path = M.PLUGIN .. "/" .. name:gsub("^%./", "")
    if entry.modules[path] == nil then
      entry.modules[path] = assert(loadfile(path, "t", env))()
    end
    return entry.modules[path]
  end

  return entry
end

-- Loads one entry file of the plugin, as the shell does when it starts it.
function Host:load(file, config)
  local entry = self:entry(config)
  assert(loadfile(M.PLUGIN .. "/" .. file, "t", entry.env))()
  self:drain()
  return entry
end

-- One module on its own, for testing it without an entry around it.
function Host:module(file, config)
  local entry = self:entry(config)
  return entry.env.require("./" .. file), entry
end

-- Calls a global the entry defined (update, onOpen, onIpc...) and lets
-- whatever it set off run.
function Host:call(entry, name, ...)
  entry.env[name](...)
  self:drain()
end

function Host:set(key, value)
  self:api({ config = {} }).state.set(key, value)
  self:drain()
end

-- ── Running tests ───────────────────────────────────────────────────────────

local tests = {}

function M.test(name, fn)
  table.insert(tests, { name = name, fn = fn })
end

function M.eq(actual, expected, what)
  if actual ~= expected then
    error(string.format("%s: expected %s, got %s", what or "value",
      tostring(expected), tostring(actual)), 2)
  end
end

function M.ok(condition, what)
  if not condition then
    error(what or "expected true", 2)
  end
end

function M.run()
  local failed = 0
  for _, t in ipairs(tests) do
    local ok, err = xpcall(t.fn, debug.traceback)
    if ok then
      print("ok    " .. t.name)
    else
      failed = failed + 1
      print("FAIL  " .. t.name .. "\n" .. tostring(err))
    end
  end
  print(string.format("%d tests, %d failed", #tests, failed))
  os.exit(failed == 0 and 0 or 1)
end

return M
