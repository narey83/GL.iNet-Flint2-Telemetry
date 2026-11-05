-- Current OpenWrt uses luaposix from the packages feed. Keep nixio support for
-- the existing vendor 21.02 package, without making LuCI a backend dependency.
local M = {}
local available, signal = pcall(require, "posix.signal")
if available then
    local stat = require("posix.sys.stat")
    local unistd = require("posix.unistd")
    function M.reset_sigterm()
        assert(signal.signal(signal.SIGTERM, signal.SIG_DFL))
    end
    function M.private_file(path)
        local info = stat.lstat(path)
        return info and stat.S_ISREG(info.st_mode) ~= 0 and
            info.st_uid == unistd.getuid() and info.st_mode % 64 == 0 or false
    end
else
    local nixio = require("nixio")
    local fs = require("nixio.fs")
    function M.reset_sigterm()
        assert(nixio.signal(nixio.const.SIGTERM, "default"))
    end
    function M.private_file(path)
        local info = fs.lstat(path)
        return info and info.type == "reg" and info.uid == nixio.getuid() and
            info.modestr:sub(4) == "------" or false
    end
end
return M
