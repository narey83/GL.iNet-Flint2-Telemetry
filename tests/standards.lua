local core=require('flint2.core')
local json=require('cjson')
local record={version='1.1',host='test-router',timestamp=1793907000.25,short_message='Flow observed',level=6,
    _agent_version='0.3.0',_flint2='telemetry',_event_kind='flow',
    ['_event.kind']='event',['_event.category']={'network'},['_event.type']={'connection','denied'},
    ['_source.ip']='198.51.100.2',['_source.bytes']=1234,['_network.transport']='tcp',
    ['_flint2.capture.unidirectional']=true}
local document=core.ecs_document(record)
assert(document.ecs.version=='8.17.0')
assert(document['@timestamp']=='2026-11-05T19:30:00.250Z')
assert(document.event.category[1]=='network' and document.event.type[2]=='denied')
assert(document.source.bytes==1234 and document.network.bytes==nil)
assert(document.flint2.capture.unidirectional==true)
assert(document.flint2.component=='telemetry' and document.agent.version=='0.3.0')
assert(document.nf_src_address==nil and document.flow_bytes==nil)
local gelf=json.decode(core.gelf_encode(record))
assert(gelf._source_bytes==1234 and gelf._flint2_capture_unidirectional==1)
assert(json.decode(gelf._event_type)[2]=='denied')
local roundtrip=json.decode(gelf._ecs_document)
assert(roundtrip.event.type[2]=='denied' and roundtrip.flint2.capture.unidirectional==true)
local log=core.otlp({record}).resourceLogs[1].scopeLogs[1].logRecords[1]
local attributes={}
for _, attribute in ipairs(log.attributes) do attributes[attribute.key]=attribute.value end
assert(attributes['source.bytes'].intValue=='1234')
assert(attributes['event.type'].arrayValue.values[2].stringValue=='denied')
assert(attributes['flint2.capture.unidirectional'].boolValue==true)
assert(attributes['flint2.source.ip']==nil)
assert(not pcall(core.any_value,0/0) and not pcall(core.any_value,math.huge))
assert(core.otlp_result('400','{}','rejectedLogRecords')=='drop')
assert(core.otlp_result('503','{}','rejectedLogRecords')=='retry')
assert(core.otlp_result('200','{"partialSuccess":{"rejectedLogRecords":"1"}}','rejectedLogRecords')=='accepted')
if arg[1]=='--otlp' then print(json.encode(core.otlp({record}))) else
    print('PASS: ECS fields, arrays, typed OTLP values, GELF round-trip and response contract')
end
