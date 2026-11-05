#!/usr/bin/lua
local json = require("cjson")
local commands = require("flint2.nft").build(json.decode(io.read("*a")), arg[1]=="1",
    arg[2], {unpack(arg, 3)})
if #commands > 0 then print(json.encode({nftables=commands})) end
