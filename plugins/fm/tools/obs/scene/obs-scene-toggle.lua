--
-- OBS Scene Toggle (Season 2) - dynamic apps
--   «Апп 1 / 2 / 3» = the 3 most recently focused apps (stable LRU slots; OBS and the shell excluded).
--   V1 / V1b show the focused app's slot.
--   Alt+F1  V1 · Идэвхтэй (square/cropped) · Alt+F6  V1b · Идэвхтэй (full)
--   Alt+F2  2 apps (V3 · Сүүлийн 2) · Alt+F3  3 apps (3 · Сүүлийн 3)
--   Alt+F5  swap monitors: the recent apps <-> OBS
--

local obs = obslua

-- Current program scene without the frontend API: obs_frontend_* calls block on the UI thread and can deadlock
-- OBS when made from a script timer / hotkey thread. Returns a source reference (release it) like the original.
function program_scene_source()
    local tr = obs.obs_get_output_source(0)
    if tr == nil then return nil end
    local s = tr
    if obs.obs_source_get_type(tr) == obs.OBS_SOURCE_TYPE_TRANSITION then
        s = obs.obs_transition_get_active_source(tr)
        obs.obs_source_release(tr)
    end
    return s
end
local ffi = require("ffi")

local CAPTURES = { "Апп 1", "Апп 2", "Апп 3" }
local ONE_CROP, ONE_FULL = "V1 · Идэвхтэй", "V1b · Идэвхтэй"
local CYCLE = { ONE_FULL, "V3 · Сүүлийн 2", "3 · Сүүлийн 3" }
-- never captured: OBS itself, the Windows shell / taskbar / start menu, lock & task switcher
local SKIP = { ["obs64.exe"] = true, ["explorer.exe"] = true, ["searchhost.exe"] = true, ["startmenuexperiencehost.exe"] = true,
    ["shellexperiencehost.exe"] = true, ["lockapp.exe"] = true, ["textinputhost.exe"] = true, ["applicationframehost.exe"] = false,
    ["screenclippinghost.exe"] = true, ["snippingtool.exe"] = true, ["shellhost.exe"] = true, ["taskmgr.exe"] = true,
    ["systemsettings.exe"] = true, ["sharex.exe"] = true, ["lightshot.exe"] = true }

ffi.cdef([[
    typedef struct { long x; long y; } POINT;
    typedef struct { long left; long top; long right; long bottom; } RECT;
    int GetCursorPos(POINT* p);
    void* WindowFromPoint(POINT Point);
    void* GetAncestor(void* hwnd, unsigned int gaFlags);
    void* GetForegroundWindow();
    unsigned long GetWindowThreadProcessId(void* hWnd, unsigned long* lpdwProcessId);
    void* OpenProcess(unsigned long dwDesiredAccess, int bInheritHandle, unsigned long dwProcessId);
    int QueryFullProcessImageNameA(void* hProcess, unsigned long dwFlags, char* lpExeName, unsigned long* lpdwSize);
    int CloseHandle(void* hObject);
    int GetWindowTextA(void* hWnd, char* s, int n);
    int GetWindowTextW(void* hWnd, uint16_t* s, int n);
    int WideCharToMultiByte(unsigned int cp, unsigned long flags, const uint16_t* w, int wn, char* out, int on, const char* d, int* used);
    int GetWindowTextLengthA(void* hWnd);
    int GetClassNameA(void* hWnd, char* s, int n);
    int IsWindowVisible(void* hWnd);
    void* GetWindow(void* hWnd, unsigned int uCmd);
    typedef int (__stdcall *WNDENUMPROC)(void* hwnd, intptr_t lParam);
    int EnumWindows(WNDENUMPROC cb, intptr_t lParam);
    void* MonitorFromWindow(void* hwnd, unsigned long dwFlags);
    typedef struct { unsigned long cbSize; RECT rcMonitor; RECT rcWork; unsigned long dwFlags; } MONITORINFO;
    int GetMonitorInfoA(void* hMonitor, MONITORINFO* lpmi);
    int SetWindowPos(void* hWnd, void* after, int X, int Y, int cx, int cy, unsigned int uFlags);
    int ShowWindow(void* hWnd, int nCmdShow);
    typedef int (__stdcall *MONITORENUMPROC)(void* hMon, void* hdc, RECT* rc, intptr_t lParam);
    int EnumDisplayMonitors(void* hdc, void* clip, MONITORENUMPROC cb, intptr_t lParam);
]])

local function exe_of(hwnd)
    if hwnd == nil then return nil end
    local pid = ffi.new("unsigned long[1]")
    ffi.C.GetWindowThreadProcessId(hwnd, pid)
    local h = ffi.C.OpenProcess(0x1000, 0, pid[0])
    if h == nil then return nil end
    local buf = ffi.new("char[520]"); local size = ffi.new("unsigned long[1]", 520)
    local ok = ffi.C.QueryFullProcessImageNameA(h, 0, buf, size)
    ffi.C.CloseHandle(h)
    if ok == 0 then return nil end
    return string.lower((string.gsub(ffi.string(buf, size[0]), ".*[/" .. string.char(92) .. "]", "")))
end

local function win_string(hwnd)
    -- UTF-8 title (an ANSI title with Cyrillic breaks obs-websocket's JSON and crashes OBS)
    local w = ffi.new("uint16_t[512]"); ffi.C.GetWindowTextW(hwnd, w, 512)
    local t = ffi.new("char[1536]"); ffi.C.WideCharToMultiByte(65001, 0, w, -1, t, 1536, nil, nil)
    local c = ffi.new("char[256]"); ffi.C.GetClassNameA(hwnd, c, 256)
    local exe = exe_of(hwnd) or ""
    -- OBS window_capture "window" setting: Title:Class:exe (':' escaped as '#3A')
    local esc = function(s) return (string.gsub(s, ":", "#3A")) end
    return esc(ffi.string(t)) .. ":" .. esc(ffi.string(c)) .. ":" .. exe, exe
end

local function set_scene(name)
    -- (itge.e: the last layout chosen in the dock stays across hotkey scene switches - no reset to defaults)
    local scenes = obs.obs_frontend_get_scenes()
    if scenes == nil then return end
    for _, s in ipairs(scenes) do
        if obs.obs_source_get_name(s) == name then obs.obs_frontend_set_current_scene(s) break end
    end
    obs.source_list_release(scenes)
end

local function current_scene_name()
    local cur = program_scene_source()
    if cur == nil then return "" end
    local n = obs.obs_source_get_name(cur); obs.obs_source_release(cur)
    return n
end

-- ---------------------------------------------------------------- recent apps -> captures
-- Stable slots (LRU): an app keeps its capture while it stays among the 3 most recent, so its zoom survives and
-- the panes don't reshuffle; a new app takes the least recently used slot. The one-app scenes (V1 / V1b) show the
-- slot of the focused app (all 3 captures sit in their group with the same transform; only one is visible).
SLOTS = {}    -- [i] = { exe=, win=, used= }
local last_fg, tick = nil, 0

local function set_capture(i, win)
    local src = obs.obs_get_source_by_name(CAPTURES[i])
    if src == nil then return end
    local up = obs.obs_data_create()
    obs.obs_data_set_string(up, "window", win)
    obs.obs_data_set_int(up, "priority", 2)
    obs.obs_data_set_int(up, "method", 2)
    obs.obs_source_update(src, up)
    obs.obs_data_release(up)
    local f = obs.obs_source_get_filter_by_name(src, "obs-zoom-to-mouse-crop")   -- old window's zoom
    if f ~= nil then obs.obs_source_filter_remove(src, f); obs.obs_source_release(f) end
    obs.obs_source_release(src)
end

-- the groups inside the one-app scenes: { scene = parent obs_scene_t, item = group sceneitem, group = obs_scene_t }
local function one_app_groups()
    local out = {}
    for _, sn in ipairs({ ONE_CROP, ONE_FULL }) do
        local ss = obs.obs_get_source_by_name(sn)
        if ss ~= nil then
            local parent = obs.obs_scene_from_source(ss)
            local items = obs.obs_scene_enum_items(parent)
            if items then
                for _, it in ipairs(items) do
                    local src = obs.obs_sceneitem_get_source(it)
                    if obs.obs_source_is_group(src) then
                        table.insert(out, { scene = parent, name = obs.obs_source_get_name(src), group = obs.obs_group_from_source(src) })
                    end
                end
                obs.sceneitem_list_release(items)
            end
            obs.obs_source_release(ss)
        end
    end
    return out
end

-- make sure each one-app group holds all 3 captures with the same transform as the one it has
-- (groups sit at 0,0 scale 1, so a parent-scene transform equals the group-local one)
function ensure_one_app_items()
    for _, g in ipairs(one_app_groups()) do
        local ref = nil
        for _, name in ipairs(CAPTURES) do
            local it = obs.obs_scene_find_source(g.group, name)
            if it ~= nil then ref = it; break end
        end
        local gitem = obs.obs_scene_find_source(g.scene, g.name)
        if ref ~= nil and gitem ~= nil then
            local info = obs.obs_transform_info(); obs.obs_sceneitem_get_info2(ref, info)
            for _, name in ipairs(CAPTURES) do
                if obs.obs_scene_find_source(g.group, name) == nil then
                    local src = obs.obs_get_source_by_name(name)
                    if src ~= nil then
                        local it = obs.obs_scene_add(g.scene, src)
                        if it ~= nil then
                            obs.obs_sceneitem_set_info2(it, info)
                            obs.obs_sceneitem_group_add_item(gitem, it)
                        end
                        obs.obs_source_release(src)
                    end
                end
            end
        end
    end
end

-- V3 (two panes): each pane holds one slot; a newly focused app takes the pane of the less recent of the two,
-- so the two panes always show the two most recent apps without swapping places.
local TWO_SCENE = "V3 · Сүүлийн 2"
PANES = nil      -- { {slot=, info=}, {slot=, info=} }
function two_group()
    local ss = obs.obs_get_source_by_name(TWO_SCENE)
    if ss == nil then return nil end
    local parent = obs.obs_scene_from_source(ss)
    local res = nil
    local items = obs.obs_scene_enum_items(parent)
    if items then
        for _, it in ipairs(items) do
            local src = obs.obs_sceneitem_get_source(it)
            -- the panes group (the camera card is a group too: skip it)
            if obs.obs_source_is_group(src) and obs.obs_scene_find_source(obs.obs_group_from_source(src), CAPTURES[1]) ~= nil then
                res = { scene = parent, name = obs.obs_source_get_name(src), group = obs.obs_group_from_source(src) }
            end
        end
        obs.sceneitem_list_release(items)
    end
    obs.obs_source_release(ss)
    return res
end

-- pane geometry inside the V3 group (canvas px; the group sits at 0,0): top and bottom card
PANE_Y = { 40, 654 }   -- Reels-safe default (gen_layouts.cjs «Кам 30%»): two 1000x594 panes

-- dock-ийн layout (Кам 20/30/40%, PiP) панелийн хэмжээг өөрчилдөг: харагдаж буй хоёр панелийн
-- одоогийн байрлал/хэмжээг (дээрээс доош) PANES-д авч, тогтмол 594-өөр дарахгүй
function sync_panes(g)
    local vis = {}
    for _, name in ipairs(CAPTURES) do
        local it = obs.obs_scene_find_source(g.group, name)
        if it ~= nil and obs.obs_sceneitem_visible(it) then
            local info = obs.obs_transform_info(); obs.obs_sceneitem_get_info2(it, info)
            table.insert(vis, info)
        end
    end
    if #vis ~= 2 then return end
    table.sort(vis, function(a, b) return a.pos.y < b.pos.y end)
    for p = 1, 2 do
        local d = PANES[p].info
        d.pos.x = vis[p].pos.x; d.pos.y = vis[p].pos.y; d.bounds.x = vis[p].bounds.x; d.bounds.y = vis[p].bounds.y
    end
end

function apply_panes(g)
    if PANES == nil or g == nil then return end
    for i, name in ipairs(CAPTURES) do
        local it = obs.obs_scene_find_source(g.group, name)
        if it ~= nil then
            local shown = false
            for _, pane in ipairs(PANES) do
                if pane.slot == i then obs.obs_sceneitem_set_info2(it, pane.info); shown = true end
            end
            obs.obs_sceneitem_set_visible(it, shown)
        end
    end
end

function setup_two()
    local g = two_group()
    if g == nil then return end
    local gitem = obs.obs_scene_find_source(g.scene, g.name)
    local ref = obs.obs_scene_find_source(g.group, CAPTURES[1])
    if ref == nil then return end
    -- fixed pane positions (reading them back from the items breaks once panes have been reassigned)
    PANES = {}
    for p = 1, 2 do
        local info = obs.obs_transform_info(); obs.obs_sceneitem_get_info2(ref, info)
        info.pos.x = 40; info.pos.y = PANE_Y[p]; info.bounds.x = 1000; info.bounds.y = 594
        PANES[p] = { slot = p, info = info }
    end
    for _, name in ipairs(CAPTURES) do
        if obs.obs_scene_find_source(g.group, name) == nil and gitem ~= nil then
            local src = obs.obs_get_source_by_name(name)
            if src ~= nil then
                local it = obs.obs_scene_add(g.scene, src)
                if it ~= nil then obs.obs_sceneitem_set_info2(it, PANES[2].info); obs.obs_sceneitem_group_add_item(gitem, it) end
                obs.obs_source_release(src)
            end
        end
    end
    -- start with the two most recently used slots
    local order = {}
    for i = 1, #CAPTURES do table.insert(order, i) end
    table.sort(order, function(a, b) return (SLOTS[a] and SLOTS[a].used or -1) > (SLOTS[b] and SLOTS[b].used or -1) end)
    PANES[1].slot, PANES[2].slot = order[1], order[2]
    sync_panes(g)
    apply_panes(g)
end

local function update_two(k)
    if PANES == nil then return end
    if PANES[1].slot == k or PANES[2].slot == k then return end
    local function u(s) if SLOTS[s] == nil then return -1 end; return SLOTS[s].exe == "fm_camera" and math.huge or SLOTS[s].used end
    local u1, u2 = u(PANES[1].slot), u(PANES[2].slot)
    local p = (u1 <= u2) and 1 or 2
    local g = two_group()
    if g ~= nil then
        local out = obs.obs_scene_find_source(g.group, CAPTURES[PANES[p].slot])
        if out ~= nil then obs.obs_sceneitem_get_info2(out, PANES[p].info) end   -- the pane's current box
        local other = obs.obs_scene_find_source(g.group, CAPTURES[PANES[3 - p].slot])
        if other ~= nil then obs.obs_sceneitem_get_info2(other, PANES[3 - p].info) end
    end
    PANES[p].slot = k
    apply_panes(g)
end

local function show_slot(k)
    for _, g in ipairs(one_app_groups()) do
        for i, name in ipairs(CAPTURES) do
            local it = obs.obs_scene_find_source(g.group, name)
            if it ~= nil then obs.obs_sceneitem_set_visible(it, i == k) end
        end
    end
end

-- fixed layout: V1/V1b show Апп 1, V3 shows Апп 1 (top) + Апп 2 (bottom), 3-split shows all three
function fixed_setup()
    if two_group() == nil then return end          -- collection not loaded yet: try again on the next tick
    obs.timer_remove(fixed_setup)
    ensure_one_app_items()
    setup_two()
    show_slot(1)
    local g = two_group()
    if g ~= nil and PANES ~= nil then
        for i, name in ipairs(CAPTURES) do
            local it = obs.obs_scene_find_source(g.group, name)
            if it ~= nil then
                if PANES[i] then obs.obs_sceneitem_set_info2(it, PANES[i].info) end
                obs.obs_sceneitem_set_visible(it, i <= 2)
            end
        end
    end
end

function late_setup()
    obs.timer_remove(late_setup)
    ensure_one_app_items()
    setup_two()
    last_fg = nil
end

local setup_done = false
function follow_focus()
    if not setup_done and two_group() ~= nil then   -- the collection is loaded: groups can be completed now
        setup_done = true
        ensure_one_app_items()
        setup_two()
    end
    local h = ffi.C.GetForegroundWindow()
    if h == nil then return end
    h = ffi.C.GetAncestor(h, 2)
    local key = tostring(ffi.cast("intptr_t", h))
    if key == last_fg then return end
    last_fg = key
    if ffi.C.GetWindowTextLengthA(h) == 0 then return end
    local win, exe = win_string(h)
    if exe == "" or SKIP[exe] then return end
    tick = tick + 1
    -- the dock may have put other windows into slots: re-read what each capture holds
    for i, name in ipairs(CAPTURES) do
        local src = obs.obs_get_source_by_name(name)
        if src ~= nil then
            local st = obs.obs_source_get_settings(src)
            local w = obs.obs_data_get_string(st, "window") or ""
            local e = string.lower(w:match("([^:]+)$") or "")
            if e ~= "" and (SLOTS[i] == nil or SLOTS[i].exe ~= e) then SLOTS[i] = { exe = e, win = w, used = tick - 1 } end
            obs.obs_data_release(st); obs.obs_source_release(src)
        end
    end
    local k = nil
    for i = 1, #CAPTURES do if SLOTS[i] and SLOTS[i].exe == exe then k = i end end
    if k == nil then
        k = nil
        for i = 1, #CAPTURES do
            if SLOTS[i] == nil then k = i; break end
            if SLOTS[i].exe ~= "fm_camera" and (k == nil or SLOTS[i].used < SLOTS[k].used) then k = i end
        end
        if k == nil then return end                   -- every slot holds the camera
        SLOTS[k] = { exe = exe, win = win, used = tick }
        set_capture(k, win)
    else
        SLOTS[k].used = tick
    end
    show_slot(k)
    update_two(k)
end

-- seed from the captures' current windows so a fresh start keeps what was there
local function seed_recent()
    SLOTS = {}
    for i, name in ipairs(CAPTURES) do
        local src = obs.obs_get_source_by_name(name)
        if src ~= nil then
            local st = obs.obs_source_get_settings(src)
            local w = obs.obs_data_get_string(st, "window")
            local exe = w and string.lower(w:match("([^:]+)$") or "") or ""
            if exe ~= "" then SLOTS[i] = { exe = exe, win = w, used = 0 } end
            obs.obs_data_release(st); obs.obs_source_release(src)
        end
    end
end

-- ---------------------------------------------------------------- camera as a slot
-- The dock can put «Камер» into a slot (capture window "...:fm_camera"). That slot keeps its place (never taken by
-- a newly focused app) and an extra camera item in each content group copies the slot's box, filled and cropped.
local CAM_SRC = "Video Capture Device"
local function is_cam_slot(i)
    local src = obs.obs_get_source_by_name(CAPTURES[i])
    if src == nil then return false end
    local st = obs.obs_source_get_settings(src)
    local w = obs.obs_data_get_string(st, "window") or ""
    obs.obs_data_release(st); obs.obs_source_release(src)
    return string.lower(w:match("([^:]+)$") or "") == "fm_camera"
end
local function content_groups()   -- the groups holding the captures, in every scene
    local out = {}
    for _, sn in ipairs({ ONE_CROP, ONE_FULL, CYCLE[2], CYCLE[3] }) do
        local ss = obs.obs_get_source_by_name(sn)
        if ss ~= nil then
            local parent = obs.obs_scene_from_source(ss)
            local items = obs.obs_scene_enum_items(parent)
            if items then
                for _, it in ipairs(items) do
                    local src = obs.obs_sceneitem_get_source(it)
                    if obs.obs_source_is_group(src) then
                        local g = obs.obs_group_from_source(src)
                        if obs.obs_scene_find_source(g, CAPTURES[1]) ~= nil then
                            table.insert(out, { scene = parent, name = obs.obs_source_get_name(src), group = g })
                        end
                    end
                end
                obs.sceneitem_list_release(items)
            end
            obs.obs_source_release(ss)
        end
    end
    return out
end
local function cam_item(g, i)
    local found = nil
    local items = obs.obs_scene_enum_items(g.group)
    if items then
        for _, it in ipairs(items) do
            if obs.obs_source_get_name(obs.obs_sceneitem_get_source(it)) == CAM_SRC then
                local ps = obs.obs_sceneitem_get_private_settings(it)
                if obs.obs_data_get_int(ps, "fm_slot") == i then found = it end
                obs.obs_data_release(ps)
            end
        end
        obs.sceneitem_list_release(items)
    end
    return found
end
function mirror_cams()
    local cams = {}
    for i = 1, #CAPTURES do cams[i] = is_cam_slot(i) end
    for _, g in ipairs(content_groups()) do
        for i, name in ipairs(CAPTURES) do
            local cap = obs.obs_scene_find_source(g.group, name)
            local ci = cam_item(g, i)
            if cams[i] and cap ~= nil then
                if ci == nil then
                    local src = obs.obs_get_source_by_name(CAM_SRC)
                    local gitem = obs.obs_scene_find_source(g.scene, g.name)
                    if src ~= nil and gitem ~= nil then
                        ci = obs.obs_scene_add(g.scene, src)
                        if ci ~= nil then
                            local ps = obs.obs_sceneitem_get_private_settings(ci)
                            obs.obs_data_set_int(ps, "fm_slot", i); obs.obs_data_release(ps)
                            obs.obs_sceneitem_group_add_item(gitem, ci)
                        end
                    end
                    if src ~= nil then obs.obs_source_release(src) end
                end
                if ci ~= nil then
                    local info = obs.obs_transform_info(); obs.obs_sceneitem_get_info2(cap, info)
                    info.bounds_type = obs.OBS_BOUNDS_SCALE_OUTER
                    obs.obs_sceneitem_set_info2(ci, info)
                    if obs.obs_sceneitem_set_bounds_crop then obs.obs_sceneitem_set_bounds_crop(ci, true) end
                    local vis = obs.obs_sceneitem_visible(cap)
                    if obs.obs_sceneitem_visible(ci) ~= vis then obs.obs_sceneitem_set_visible(ci, vis) end
                end
            elseif ci ~= nil then
                -- not a camera slot any more: remove the extra item, so the layouts' «Video Capture Device» box/vis ops
                -- only ever find the real camera card (a hidden copy made them move the wrong item)
                obs.obs_sceneitem_remove(ci)
            end
        end
    end
end

-- ---------------------------------------------------------------- hotkeys
local function on_one(pressed)   -- Alt+F1: one app, square (cropped) card
    if not pressed then return end
    set_scene(ONE_CROP)
end

local function on_one_full(pressed)  -- Alt+F6: one app, full width
    if not pressed then return end
    set_scene(ONE_FULL)
end

local function on_three(pressed) -- Alt+F3: straight to the 3-app scene
    if not pressed then return end
    set_scene(CYCLE[3])
end

local function on_cycle(pressed) -- Alt+F2: the 2-app scene
    if not pressed then return end
    if true then set_scene(CYCLE[2]) return end
    local name = current_scene_name()
    for i, c in ipairs(CYCLE) do
        if c == name then set_scene(CYCLE[i % #CYCLE + 1]) return end
    end
    if name == ONE_CROP then set_scene(CYCLE[2]) return end
    set_scene(CYCLE[1])
end

local function top_windows()
    local list = {}
    local cb = ffi.cast("WNDENUMPROC", function(h, _)
        if ffi.C.IsWindowVisible(h) ~= 0 and ffi.C.GetWindow(h, 4) == nil and ffi.C.GetWindowTextLengthA(h) > 0 then
            table.insert(list, h)
        end
        return 1
    end)
    ffi.C.EnumWindows(cb, 0)
    cb:free()
    return list
end

local function work_rect(h)
    local mon = ffi.C.MonitorFromWindow(h, 2)
    local mi = ffi.new("MONITORINFO[1]"); mi[0].cbSize = ffi.sizeof("MONITORINFO")
    if ffi.C.GetMonitorInfoA(mon, mi) == 0 then return nil end
    local r = mi[0].rcWork
    return { key = tostring(r.left) .. "," .. tostring(r.top), x = r.left, y = r.top, w = r.right - r.left, h = r.bottom - r.top }
end

local function move_to(h, r)
    ffi.C.ShowWindow(h, 9)
    ffi.C.SetWindowPos(h, nil, r.x, r.y, r.w, r.h, 0x0014)
    ffi.C.ShowWindow(h, 3)
end

local function on_swap(pressed)  -- Alt+F5
    if not pressed then return end
    local want = {}
    for i = 1, #CAPTURES do if SLOTS[i] then want[SLOTS[i].exe] = true end end
    local obs_win, apps = nil, {}
    for _, h in ipairs(top_windows()) do
        local exe = exe_of(h)
        if exe == "obs64.exe" then
            local buf = ffi.new("char[64]"); ffi.C.GetWindowTextA(h, buf, 64)
            if string.sub(ffi.string(buf), 1, 4) == "OBS " then obs_win = h end
        elseif exe and want[exe] then
            table.insert(apps, h)
        end
    end
    if obs_win == nil or #apps == 0 then return end
    -- the other monitor = any monitor that is not OBS's (works even when some apps already share OBS's monitor)
    local ro = work_rect(obs_win)
    if ro == nil then return end
    local other = nil
    local cb = ffi.cast("MONITORENUMPROC", function(hmon, _, _, _)
        local mi = ffi.new("MONITORINFO[1]"); mi[0].cbSize = ffi.sizeof("MONITORINFO")
        if ffi.C.GetMonitorInfoA(hmon, mi) ~= 0 then
            local r = mi[0].rcWork
            local key = tostring(r.left) .. "," .. tostring(r.top)
            if key ~= ro.key and other == nil then other = { key = key, x = r.left, y = r.top, w = r.right - r.left, h = r.bottom - r.top } end
        end
        return 1
    end)
    ffi.C.EnumDisplayMonitors(nil, nil, cb, 0)
    cb:free()
    if other == nil then return end
    move_to(obs_win, other)
    for _, h in ipairs(apps) do move_to(h, ro) end
    -- frozen zoom crops are in the old window size: clear them (the zoom script restarts tracking by itself)
    for _, name in ipairs(CAPTURES) do
        local src = obs.obs_get_source_by_name(name)
        if src ~= nil then
            local f = obs.obs_source_get_filter_by_name(src, "obs-zoom-to-mouse-crop")
            if f ~= nil then obs.obs_source_filter_remove(src, f); obs.obs_source_release(f) end
            obs.obs_source_release(src)
        end
    end
end

-- ---------------------------------------------------------------- OBS plumbing
local HOTKEYS = {
    { id = nil, name = "switch_to_app_under_mouse", label = "One app: full <-> cropped", cb = on_one, key = "OBS_KEY_F1" },
    { id = nil, name = "cycle_combo_scenes", label = "Cycle 1 / 2 / 3 apps", cb = on_cycle, key = "OBS_KEY_F2" },
    { id = nil, name = "one_app_full_scene", label = "1 app full", cb = on_one_full, key = "OBS_KEY_F6" },
    { id = nil, name = "three_apps_scene", label = "3 apps scene", cb = on_three, key = "OBS_KEY_F3" },
    { id = nil, name = "swap_monitors", label = "Swap monitors (apps <-> OBS)", cb = on_swap, key = "OBS_KEY_F5" },
}

function script_description()
    return "Season 2: Апп 1/2/3 follow the recently focused windows. Alt+F1 full/cropped, Alt+F2 1-2-3 apps, Alt+F5 swap monitors."
end

function script_load(settings)
    seed_recent()
    -- scenes/groups exist only after the collection has loaded (script_load runs earlier)
    -- (no frontend event callback: a scene switch from this script's hotkey would then wait on the UI thread
    -- while the UI thread waits on this script -> OBS freezes; a one-shot timer does the late setup instead)
    obs.timer_add(late_setup, 3000)
    ensure_one_app_items()
    -- recent apps follow the focused window (LRU slots); the «Апп-ууд» dock (E:/OBS Assets/app-panel.html) can
    -- also put any window into a slot by hand
    obs.timer_add(follow_focus, 250)
    obs.timer_add(mirror_cams, 150)
    for _, hk in ipairs(HOTKEYS) do
        hk.id = obs.obs_hotkey_register_frontend(hk.name, hk.label, hk.cb)
        local a = obs.obs_data_get_array(settings, hk.name)
        if obs.obs_data_array_count(a) == 0 then
            local k = obs.obs_data_create()
            obs.obs_data_set_string(k, "key", hk.key)
            obs.obs_data_set_bool(k, "alt", true)
            obs.obs_data_array_push_back(a, k)
            obs.obs_data_release(k)
        end
        obs.obs_hotkey_load(hk.id, a)
        obs.obs_data_array_release(a)
    end
end

function script_save(settings)
    for _, hk in ipairs(HOTKEYS) do
        if hk.id ~= nil then
            local a = obs.obs_hotkey_save(hk.id)
            obs.obs_data_set_array(settings, hk.name, a)
            obs.obs_data_array_release(a)
        end
    end
end

function script_unload()
    obs.timer_remove(fixed_setup)
    obs.timer_remove(late_setup)
    obs.timer_remove(follow_focus)
end
