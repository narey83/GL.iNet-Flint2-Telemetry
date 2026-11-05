-- OpenWrt hardware integration: replay a local TCP handshake through the installed
-- capture configuration into a separate loopback receiver; no telemetry is indexed.
local socket=require('socket')
local sources=require('flint2.sources')
local function read(path) local f=assert(io.open(path));local s=f:read('*a');f:close();return s end
local config=read(arg[1] or '/var/run/flint2/capture-1.conf')
config=config:gsub('pcap_interface: [^\n]+','pcap_interface: lo')
config=config:gsub('pcap_filter: [^\n]+','pcap_filter: ip and tcp port 43057')
config=config:gsub('nfprobe_receiver: [^\n]+','nfprobe_receiver: 127.0.0.1:43055')
config=config:gsub('pidfile: [^\n]+','pidfile: /tmp/flint2-capture-check/capture.pid')
config=config:gsub('syslog: [^\n]+\n','')
config=config:gsub('nfprobe_timeouts: [^\n]+','nfprobe_timeouts: tcp=1:tcp.rst=1:tcp.fin=1:udp=1:icmp=1:general=1:maxlife=1:expint=1')
assert(os.execute('mkdir -p /tmp/flint2-capture-check && chmod 700 /tmp/flint2-capture-check')==0)
local f=assert(io.open('/tmp/flint2-capture-check/capture.conf','w'));f:write(config);f:close()
local udp=assert(socket.udp());assert(udp:setsockname('127.0.0.1',43055));udp:settimeout(1)
local server=assert(socket.bind('127.0.0.1',43057));server:settimeout(2)
assert(os.execute('timeout -k 1 15 /usr/sbin/flint2-capture -f /tmp/flint2-capture-check/capture.conf >/tmp/flint2-capture-check/capture.log 2>&1 &')==0)
socket.sleep(1)
local client=assert(socket.tcp());client:settimeout(2);assert(client:connect('127.0.0.1',43057))
local accepted=assert(server:accept());accepted:settimeout(2)
assert(client:send('flint2 capture test\n'));assert(accepted:receive('*l')=='flint2 capture test')
client:close();accepted:close();server:close()
local deadline=socket.gettime()+10
local packets,nonzero,syn=0,0,0
while socket.gettime()<deadline do
    local data=udp:receive()
    if data then
        local records,err=sources.flows(data,'flow_lan');assert(records,err)
        for _,record in ipairs(records) do
            packets=packets+record['source.packets']
            local flags=record['flint2.tcp.flags'] or 0
            if flags>0 then nonzero=nonzero+1 end
            if math.floor(flags/2)%2==1 then syn=syn+1 end
        end
    end
end
udp:close()
assert(packets>0 and nonzero>0 and syn>0,'Live capture lost TCP flags; inspect the capture buffer size/alignment')
print('PASS: controlled live loopback handshake preserves TCP/SYN flags ('..nonzero..' flow records)')
