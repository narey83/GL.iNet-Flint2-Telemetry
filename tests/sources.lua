local sources=require("flint2.sources")
local checks=0
local function check(value,why) checks=checks+1;assert(value,why) end
local function integer(n,bytes)
    local t={}
    for i=bytes-1,0,-1 do t[#t+1]=string.char(math.floor(n/256^i)%256) end
    return table.concat(t)
end
local record=string.char(192,168,0,12,8,8,8,8)..integer(0,4)..integer(0,2)..integer(0,2)..
    integer(7,4)..integer(9999,4)..integer(90000,4)..integer(99000,4)..integer(65535,2)..integer(443,2)..
    string.char(0,18,6,0)..integer(0,2)..integer(0,2)..integer(0,4)
local header=integer(5,2)..integer(1,2)..integer(100000,4)..integer(1700000000,4)..integer(0,4)..
    integer(0,4)..string.char(0,2)..integer(0,2)
check(#record==48 and #header==24,"fixture dimensions")
local flow=assert(sources.flows(header..record,"flow_lan"))[1]
check(flow["source.ip"]=="192.168.0.12" and flow["destination.ip"]=="8.8.8.8","addresses")
check(flow["source.port"]==65535 and flow["destination.port"]==443,"ports")
check(flow["source.packets"]==7 and flow["source.bytes"]==9999,"exact packet and byte counters")
check(flow["flint2.tcp.flags"]==18 and tonumber(flow["network.iana_number"])==6,"real TCP flags and protocol")
check(flow["event.start"]=="2023-11-14T22:13:10.000Z" and flow["event.end"]=="2023-11-14T22:13:19.000Z","capture timestamps")
check(sources.flows("bad","flow_lan")==nil,"truncated datagram")
check(sources.flows(header..record.."extra","flow_lan")==nil,"unexpected trailing bytes")
check(sources.flows(integer(9,2)..header:sub(3)..record,"flow_lan")==nil,"unsupported capture version")
check(sources.flows(header:sub(1,12)..integer(1000000000,4)..header:sub(17)..record,"flow_lan")==nil,"invalid nanoseconds")
local networks,routers=sources.networks({interface={{interface="lan",l3_device="br-lan",["ipv4-address"]={{address="192.168.0.1",mask=24}}}}},{"br-lan"})
sources.device_labels(flow,{["192.168.0.12"]={name="Laptop",mac="aa:bb:cc:dd:ee:ff"}},"203.0.113.1",networks,routers)
check(flow["flint2.local_device.name"]=="Laptop" and flow["flint2.local_device.mac"]=="AA-BB-CC-DD-EE-FF","device lookup from agent inventory")
local download={["flint2.capture.scope"]="lan",["source.ip"]="8.8.8.8",["destination.ip"]="192.168.0.12"}
sources.device_labels(download,{["192.168.0.12"]={name="Laptop",mac="aa:bb:cc:dd:ee:ff"}},"203.0.113.1",networks,routers)
check(download["flint2.local_device.name"]=="Laptop","download recipient lookup")
check(sources.overlap({"a","b","c"},{"b","c","d"})==2,"rotating log overlap")
check(sources.overlap({"a","a"},{"a","a","b"})==2,"duplicate log occurrences preserved")
check(sources.overlap({"a"},{"b"})==0,"missing overlap")
check(sources.overlap({},{"a"})==0,"first log snapshot")
local fields,message,time,severity=sources.log("Thu Nov  5 20:30:01 2026 kern.warn kernel: [123.45] FLINT2 FORWARD wan in: IN=pppoe-wan OUT=br-lan SRC=8.8.8.8 DST=192.168.0.12 LEN=60 TOS=0x00 TTL=55 ID=123 PROTO=TCP SPT=33333 DPT=443 WINDOW=1024 RES=0x00 SYN URGP=0","Router","pppoe-wan")
check(fields["event.action"]=="forward" and fields["observer.ingress.zone"]=="wan","native firewall action/zone")
check(fields["source.ip"]=="8.8.8.8" and fields["destination.ip"]=="192.168.0.12","firewall endpoints")
check(fields["source.port"]==33333 and fields["destination.port"]==443 and fields["flint2.packet.ttl"]==55 and fields["flint2.tcp.window"]==1024,"legacy extractor fields")
check(fields["flint2.tcp.flag_names"]=="SYN" and fields["flint2.packet.length"]==60 and fields["flint2.packet.id"]==123,"kernel fields")
check(severity==4 and fields["log.syslog.facility.code"]==0,"severity/facility")
check(message:match("^Router kernel:")~=nil and time>0,"existing processing message format")
fields=sources.log("Thu Nov  5 20:30:01 2026 kern.warn kernel: FLINT2 REJECT wan in: IN=eth0 OUT= SRC=8.8.8.8 DST=192.168.1.1 LEN=60 PROTO=UDP SPT=33333 DPT=443","Router","eth0")
check(fields["event.action"]=="reject" and fields["event.type"][2]=="denied","fw4 reject is a denial observation")
check(fields["source.ip"]=="8.8.8.8" and fields["destination.port"]==443,"fw4 log endpoint projection")
fields=sources.log("Thu Nov  5 20:30:01 2026 authpriv.notice dropbear[123]: Password auth succeeded for root","Router","pppoe-wan")
check(fields["process.name"]=="dropbear" and fields["process.pid"]==123,"process name and pid")
check(fields["event.action"]==nil,"ordinary logs are not fabricated firewall events")
check(sources.log("malformed","Router","wan")==nil,"reject malformed log line")
local bad_last=record:sub(1,28)..integer(1382455523,4)..record:sub(33)
check(sources.flows(header..bad_last,"flow_lan")==nil,"reject the observed corrupt flow-end timestamp")
local backwards=record:sub(1,28)..integer(89000,4)..record:sub(33)
check(sources.flows(header..backwards,"flow_lan")==nil,"reject an end preceding the start")
local future=record:sub(1,28)..integer(100001,4)..record:sub(33)
check(sources.flows(header..future,"flow_lan")==nil,"reject a future end without clamping it")
local wrap_header=header:sub(1,4)..integer(5,4)..header:sub(9)
local wrap_record=record:sub(1,24)..integer(4294967290,4)..integer(2,4)..record:sub(33)
local wrapped=assert(sources.flows(wrap_header..wrap_record,"flow_lan"))[1]
check(wrapped["event.duration"]>7000000 and wrapped["event.duration"]<9000000,"valid 32-bit exporter uptime wrap is retained")
print("PASS: "..checks.." source decoder checks")
