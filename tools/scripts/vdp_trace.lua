-- luacheck: globals vdp_trace_tap vdp_trace_frames, read globals manager emu CAPFRAMES CAPOUT
local frame = 0
local mach <const> = manager.machine
local io_space <const> = mach.devices[":maincpu"].spaces["io"]
local cpu <const> = mach.devices[":maincpu"].state
local lines <const> = {}

local function note(port, value)
  local now <const> = mach.time
  lines[#lines + 1] = string.format("%d %d %d %d %d %d %d",
    frame, port, value, io_space:read_u8(0x7E), cpu["PC"].value, now.seconds, now.attoseconds)
end

vdp_trace_tap = io_space:install_write_tap(0x00, 0xFF, "vdptrace", function(offset, data)
  local port <const> = offset & 0xFF
  if port == 0xBE or port == 0xBF or port == 0x7E then
    note(port, data & 0xFF)
  end
  return data
end)

vdp_trace_frames = emu.add_machine_frame_notifier(function()
  frame = frame + 1
  if frame == CAPFRAMES then
    local out <const> = io.open(CAPOUT, "w")
    out:write(table.concat(lines, "\n"))
    out:write("\n")
    out:close()
    mach:exit()
  end
end)
