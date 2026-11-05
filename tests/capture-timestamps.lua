-- OpenWrt live regression: many short UDP flows through the real capture/IPC path.
-- Uses loopback only, a separate receiver and no Graylog ingestion.
local socket=require('socket')
local sources=require('flint2.sources')
local binary=arg[1] or '/usr/sbin/flint2-capture'
assert(binary:match('^/[%w/_.-]+$'),'invalid capture binary path')
local function read(path) local f=assert(io.open(path));local s=f:read('*a');f:close();return s end
local runtime='/tmp/flint2-timestamp-test'
assert(os.execute('mkdir -p '..runtime..' && chmod 700 '..runtime)==0)
local config=read('/var/run/flint2/capture-1.conf')
config=config:gsub('pcap_interface: [^\n]+','pcap_interface: lo')
config=config:gsub('pcap_filter: [^\n]+','pcap_filter: ip and udp dst port 43057')
config=config:gsub('nfprobe_receiver: [^\n]+','nfprobe_receiver: 127.0.0.1:43055')
config=config:gsub('pidfile: [^\n]+','pidfile: '..runtime..'/capture.pid')
config=config:gsub('syslog: [^\n]+\n','')
config=config:gsub('nfprobe_timeouts: [^\n]+','nfprobe_timeouts: tcp=1:tcp.rst=1:tcp.fin=1:udp=1:icmp=1:general=1:maxlife=1:expint=1')
local file=assert(io.open(runtime..'/capture.conf','w'));file:write(config);file:close()
os.remove(runtime..'/capture.pid')
local exporter=assert(socket.udp());assert(exporter:setsockname('127.0.0.1',43055));exporter:settimeout(0)
local sink=assert(socket.udp());assert(sink:setsockname('127.0.0.1',43057));sink:settimeout(0)
assert(os.execute('timeout -k 1 45 '..binary..' -f '..runtime..'/capture.conf >'..runtime..'/capture.log 2>&1 &')==0)
socket.sleep(1)
local function uint(d,o,n) local v=0;for i=o,o+n-1 do v=v*256+d:byte(i) end;return v end
local records,invalid,packets,stale,datagrams=0,0,0,0,0
local function receive()
    for _=1,128 do
        local data=exporter:receive()
        if not data then break end
        datagrams=datagrams+1
        local decoded=sources.flows(data,'flow_lan')
        if not decoded then invalid=invalid+1
        else
            records=records+#decoded
            for _,record in ipairs(decoded) do packets=packets+record['source.packets'] end
        end
        if #data>=24 and uint(data,1,2)==5 and #data==24+48*uint(data,3,2) then
            local uptime=uint(data,5,4)
            for i=0,uint(data,3,2)-1 do
                local offset=25+48*i
                local first=(uptime-uint(data,offset+24,4))%4294967296
                local last=(uptime-uint(data,offset+28,4))%4294967296
                -- This probe has just started; an ancient or future record is corruption.
                if first>60000 or last>60000 or last>first then stale=stale+1 end
            end
        end
    end
end
local started=socket.gettime()
-- Bound conntrack use: keep only 128 client sockets while exercising many writes.
local clients={}
for i=1,128 do
    local client=assert(socket.udp());assert(client:setsockname('127.0.0.1',0));client:settimeout(0)
    clients[i]=client
end
for round=1,160 do
    for _,client in ipairs(clients) do
        assert(client:sendto('timestamp-test','127.0.0.1',43057))
        sink:receive()
    end
    receive();socket.sleep(0.001)
end
for _,client in ipairs(clients) do client:close() end
local deadline=socket.gettime()+8
while socket.gettime()<deadline do receive();socket.sleep(0.01) end
exporter:close();sink:close()
-- Stop only the test's parent process; it owns and stops its own probe child.
local pid=read(runtime..'/capture.pid'):match('^(%d+)%s*$')
if pid then os.execute('kill -TERM '..pid..' 2>/dev/null') end
print(string.format('Capture stress: %.1fs, %d datagrams, %d records, %d packets, %d invalid datagrams, %d invalid/stale times',socket.gettime()-started,datagrams,records,packets,invalid,stale))
assert(records>=100 and packets>=1000,'Insufficient captured traffic to exercise the shared-memory ring')
assert(invalid==0 and stale==0,'Capture exported torn or invalid timestamps')
print('PASS: live capture preserves recent, ordered flow timestamps under repeated UDP flows')
