-- On-router quality check of a separate WAN probe. Does not send data to a SIEM.
local socket=require('socket')
local sources=require('flint2.sources')
local binary=arg[1] or '/usr/sbin/flint2-capture'
local port=tonumber(arg[2] or '43055')
local seconds=tonumber(arg[3] or '60')
assert(binary:match('^/[%w/_.-]+$'),'invalid binary path')
assert(port and port%1==0 and port>=43000 and port<=44000,'invalid test receiver port')
assert(seconds and seconds%1==0 and seconds>=15 and seconds<=300,'invalid test duration')
local runtime='/tmp/flint2-wan-test-'..port
local function read(path) local f=assert(io.open(path));local s=f:read('*a');f:close();return s end
assert(os.execute('mkdir -p '..runtime..' && chmod 700 '..runtime)==0)
local config=read('/var/run/flint2/capture-1.conf')
config=config:gsub('nfprobe_receiver: [^\n]+','nfprobe_receiver: 127.0.0.1:'..port)
config=config:gsub('pidfile: [^\n]+','pidfile: '..runtime..'/capture.pid')
config=config:gsub('syslog: [^\n]+\n','')
config=config:gsub('plugin_buffer_size: [^\n]+','plugin_buffer_size: 264')
config=config:gsub('nfprobe_timeouts: [^\n]+','nfprobe_timeouts: tcp=1:tcp.rst=1:tcp.fin=1:udp=1:icmp=1:general=1:maxlife=1:expint=1')
local file=assert(io.open(runtime..'/capture.conf','w'));file:write(config);file:close()
os.remove(runtime..'/capture.pid')
local receiver=assert(socket.udp());assert(receiver:setsockname('127.0.0.1',port));receiver:settimeout(0.1)
assert(os.execute('timeout -k 1 '..(seconds+3)..' '..binary..' -f '..runtime..'/capture.conf >'..runtime..'/capture.log 2>&1 &')==0)
local function uint(data,offset,size)
    local value=0
    for i=offset,offset+size-1 do value=value*256+data:byte(i) end
    return value
end
local records,invalid,stale,packets=0,0,0,0
local start=socket.gettime()
while socket.gettime()-start<seconds do
    local data=receiver:receive()
    if data then
        local flows=sources.flows(data,'flow_wan')
        if not flows then invalid=invalid+1
        else
            records=records+#flows
            for _,flow in ipairs(flows) do packets=packets+flow['source.packets'] end
        end
        if #data>=24 and uint(data,1,2)==5 and #data==24+48*uint(data,3,2) then
            local uptime=uint(data,5,4)
            for i=0,uint(data,3,2)-1 do
                local offset=25+i*48
                local first=(uptime-uint(data,offset+24,4))%4294967296
                local last=(uptime-uint(data,offset+28,4))%4294967296
                if first>(seconds+5)*1000 or last>(seconds+5)*1000 or last>first then stale=stale+1 end
            end
        end
    end
end
receiver:close()
-- The test probe is bounded by timeout and stops independently three seconds later.
print(string.format('WAN quality: %.1fs, %d records, %d packets, %d invalid datagrams, %d invalid/stale times',socket.gettime()-start,records,packets,invalid,stale))
assert(records>=100,'Insufficient WAN traffic for a meaningful quality check')
assert(invalid==0 and stale==0,'The capture exporter produced invalid or stale timestamps')
print('PASS: fresh and ordered flow timestamps through the live WAN capture/IPC path')
