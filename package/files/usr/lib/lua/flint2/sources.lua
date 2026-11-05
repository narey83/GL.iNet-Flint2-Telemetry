-- Decoders for local capture and log sources. Remote delivery remains structured HTTPS.
local M = {}

local function uint(data, offset, size)
    local value = 0
    for i = offset, offset + size - 1 do value = value * 256 + data:byte(i) end
    return value
end

local function address(data, offset)
    return table.concat({data:byte(offset, offset + 3)}, ".")
end

local function iso(time)
    return os.date("!%Y-%m-%dT%H:%M:%S", math.floor(time)) .. string.format(".%03dZ", math.floor((time % 1) * 1000))
end

function M.flows(data, dataset)
    if #data < 24 or uint(data, 1, 2) ~= 5 then return nil, "invalid local capture version" end
    local count = uint(data, 3, 2)
    if count < 1 or count > 30 or #data ~= 24 + count * 48 then return nil, "invalid local capture length" end
    local uptime = uint(data, 5, 4)
    local nanos=uint(data,13,4)
    if nanos>=1000000000 then return nil,"invalid local capture timestamp" end
    local timestamp = uint(data, 9, 4) + nanos / 1000000000
    local result = {}
    for i = 0, count - 1 do
        local o = 25 + i * 48
        local start = timestamp - ((uptime - uint(data, o + 24, 4)) % 4294967296) / 1000
        local stop = timestamp - ((uptime - uint(data, o + 28, 4)) % 4294967296) / 1000
        if start < 0 or stop < start or stop > timestamp then return nil, "invalid local capture time" end
        local protocol = uint(data, o + 38, 1)
        local src,dst=address(data,o),address(data,o+4)
        local bytes,packets=uint(data,o+20,4),uint(data,o+16,4)
        local flow={['ecs.version']="8.17.0",['event.kind']="event",['event.category']={"network"},
            ['event.type']={"connection"},['event.action']="flow_observed",['event.dataset']="flint2.network_flow",
            ['event.start']=iso(start),['event.end']=iso(stop),['event.duration']=math.floor((stop-start)*1000000000),
            ['source.address']=src,['source.ip']=src,['destination.address']=dst,['destination.ip']=dst,
            ['source.bytes']=bytes,['source.packets']=packets,
            ['network.type']="ipv4",['network.iana_number']=tostring(protocol),
            ['network.transport']=({[1]="icmp",[6]="tcp",[17]="udp"})[protocol] or "unknown",
            ['flint2.capture.engine']="pmacct",['flint2.capture.engine_id']=data:byte(22),
            ['flint2.capture.scope']=dataset=="flow_wan" and "wan" or "lan",
            ['flint2.capture.unidirectional']=true,
            ['flint2.capture.export_time']=timestamp,
            ['flint2.capture.sequence']=(uint(data,17,4)+i)%4294967296}
        if protocol==6 then flow['flint2.tcp.flags']=uint(data,o+37,1) end
        if protocol==6 or protocol==17 then
            flow['source.port'],flow['destination.port']=uint(data,o+32,2),uint(data,o+34,2)
        end
        result[#result + 1]=flow
    end
    return result
end

-- Longest previous suffix/current prefix, retaining duplicate log occurrences.
function M.overlap(previous, current)
    local values = {}
    for _, line in ipairs(current) do values[#values + 1] = line end
    values[#values + 1] = {}
    for _, line in ipairs(previous) do values[#values + 1] = line end
    local prefix = {0}
    for i = 2, #values do
        local j = prefix[i - 1]
        while j > 0 and values[i] ~= values[j + 1] do j = prefix[j] end
        if values[i] == values[j + 1] then j = j + 1 end
        prefix[i] = j
    end
    return prefix[#values] or 0
end

local months = {Jan=1,Feb=2,Mar=3,Apr=4,May=5,Jun=6,Jul=7,Aug=8,Sep=9,Oct=10,Nov=11,Dec=12}
local levels = {emerg=0,alert=1,crit=2,err=3,warning=4,warn=4,notice=5,info=6,debug=7}
local facilities={kern=0,user=1,mail=2,daemon=3,auth=4,syslog=5,lpr=6,news=7,uucp=8,cron=9,authpriv=10,ftp=11}

function M.log(line, hostname, wan_interface)
    local month, day, hour, minute, second, year, facility, severity, program, body =
        line:match("^%a+%s+(%a+)%s+(%d+)%s+(%d+):(%d+):(%d+)%s+(%d+)%s+([%w_-]+)%.([%w_-]+)%s+([^:]+):%s*(.*)$")
    if not month or not months[month] then return nil end
    local fields = {['ecs.version']="8.17.0",['event.kind']="event",['event.category']={"host"},
        ['event.type']={"info"},['event.dataset']="flint2.router_log",['event.original']=line,
        ['process.name']=program:gsub("%[%d+%]$", ""),['process.pid']=tonumber(program:match("%[(%d+)%]$")),
        ['log.level']=severity,['log.syslog.facility.name']=facility,['log.syslog.facility.code']=facilities[facility],
        ['log.syslog.severity.code']=levels[severity] or 6}
    if fields['process.name']=="dropbear" then fields['event.category']={"authentication"} end
    local action, zone = body:match("FLINT2%s+(%u+)%s+([%w_-]+)%s+in:")
    if not action then action, zone = body:match("%]%s+(%u+)%s+([%w_-]+)%s+in:") end
    local values = {}
    for key, value in (" " .. body):gmatch("%s([A-Z]+)=(%S*)") do values[key] = value end
    if body:find("SYN_DROPPED:", 1, true) then
        action, zone = "DROP", values.IN == wan_interface and "wan" or "other"
    end
    if action == "DROP" or action == "FORWARD" or action == "REJECT" then
        fields['event.category']={"network"}
        fields['event.type']={"connection"}
        if action=="DROP" or action=="REJECT" then fields['event.type']={"connection","denied"} end
        fields['event.action']=action:lower()
        fields['observer.ingress.zone']=zone
        fields['source.address'],fields['source.ip']=values.SRC,values.SRC
        fields['destination.address'],fields['destination.ip']=values.DST,values.DST
        fields['source.port'],fields['destination.port']=tonumber(values.SPT),tonumber(values.DPT)
        fields['network.transport']=values.PROTO and values.PROTO:lower() or nil
        fields['observer.ingress.interface.name'],fields['observer.egress.interface.name']=values.IN,values.OUT
        fields['flint2.packet.length']=tonumber(body:match("%sLEN=(%d+)%s+TOS=")) or tonumber(values.LEN)
        fields['flint2.packet.ttl'],fields['flint2.tcp.window'],fields['flint2.packet.id']=tonumber(values.TTL),tonumber(values.WINDOW),tonumber(values.ID)
        fields['flint2.packet.payload_length']=tonumber(body:match("DPT=%d+%s+LEN=(%d+)"))
        fields['flint2.tcp.flag_names']=body:match("RES=0x[%x]+%s+([A-Z ]-)%s+URGP=")
    end
    local timestamp = os.time({year=tonumber(year),month=months[month],day=tonumber(day),
        hour=tonumber(hour),min=tonumber(minute),sec=tonumber(second)})
    return fields, hostname .. " " .. program .. ": " .. body, timestamp, levels[severity] or 6
end

local function ipv4(ip)
    local a,b,c,d=ip:match("^(%d+)%.(%d+)%.(%d+)%.(%d+)$")
    if not a then return nil end
    a,b,c,d=tonumber(a),tonumber(b),tonumber(c),tonumber(d)
    if a>255 or b>255 or c>255 or d>255 then return nil end
    return a*16777216+b*65536+c*256+d
end

function M.networks(dump, interfaces)
    local wanted,result,routers={},{},{}
    for _, name in ipairs(interfaces) do wanted[name]=true end
    for _, interface in ipairs(dump.interface or {}) do
        if wanted[interface.l3_device] then
            for _, address in ipairs(interface['ipv4-address'] or {}) do
                local value,mask=ipv4(address.address),tonumber(address.mask)
                if value and mask and mask>=0 and mask<=32 then
                    local size=2^(32-mask)
                    result[#result+1]={size=size,prefix=math.floor(value/size),name=interface.interface}
                    routers[address.address]=true
                end
            end
        end
    end
    return result,routers
end

function M.network_name(ip, networks)
    local value=ipv4(ip)
    if not value then return nil end
    for _, subnet in ipairs(networks or {}) do
        if math.floor(value/subnet.size)==subnet.prefix then return subnet.name end
    end
end

local function broadcast(ip, networks)
    local first=tonumber(ip:match("^(%d+)"))
    if (first and first>=224 and first<=239) or ip=="255.255.255.255" then return true end
    local value=ipv4(ip)
    for _, subnet in ipairs(networks or {}) do
        if value and subnet.size>2 and value==subnet.prefix*subnet.size+subnet.size-1 then return true end
    end
    return false
end

function M.device_labels(flow, devices, public_ip, networks, router_ips)
    local src, dst = flow['source.ip'], flow['destination.ip']
    if flow['flint2.capture.scope']=="wan" then
        flow['network.direction']=src==public_ip and "outbound" or dst==public_ip and "inbound" or "unknown"
        return
    end
    if flow['flint2.capture.scope'] ~= "lan" then return end
    local routers=router_ips or {}
    local function local_ip(ip)
        return M.network_name(ip,networks)~=nil
    end
    local device, peer
    if local_ip(src) and not routers[src] then device=src end
    if routers[src] and local_ip(dst) and not routers[dst] and not broadcast(dst,networks) then device=dst;peer=src end
    if local_ip(dst) and not routers[dst] and not local_ip(src) and src~=public_ip then device=dst end
    if local_ip(src) and local_ip(dst) and not routers[src] and not routers[dst] and not broadcast(dst,networks) then peer=dst end
    if dst==public_ip and local_ip(src) then device=src end
    if src==public_ip and local_ip(dst) then device=dst end
    if device then
        local known=devices[device]
        flow['flint2.local_device.ip']=device
        flow['flint2.local_device.name']=known and known.name or ("Unknown " .. device)
        flow['flint2.local_device.mac']=known and known.mac:upper():gsub(":","-") or nil
        flow['flint2.local_device.network']=M.network_name(device,networks)
    end
    if peer then flow['flint2.peer.ip']=peer;flow['flint2.peer.name']=devices[peer] and devices[peer].name or ("Unknown " .. peer) end
    flow['network.direction']=local_ip(src) and (local_ip(dst) and "internal" or "outbound") or local_ip(dst) and "inbound" or "unknown"
end

return M
