#!/usr/bin/env python3
"""Route native Flint2 source events through the existing dashboard pipelines.

No legacy exporter/configuration is restored. Token is read from stdin.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("provision",ROOT/"scripts/provision-graylog.py")
provision=importlib.util.module_from_spec(spec)
spec.loader.exec_module(provision)
TITLE="Flint2 existing dashboard routing"


def routing_rules(input_id, targets):
    rules=[]
    for dataset, stream_id in targets.items():
        title="Flint2 route "+dataset
        condition=('to_string($message.event_dataset) == "flint2.router_log"' if dataset=="router_log" else
                   'to_string($message.event_dataset) == "flint2.network_flow" && '+
                   'to_string($message.flint2_capture_scope) == "'+("wan" if dataset=="flow_wan" else "lan")+'"')
        source=(f'rule "{title}"\nwhen\n'
                f'    has_field("event_dataset") &&\n'
                f'    to_string($message.gl2_source_input) == "{input_id}" &&\n'
                f'    {condition}\nthen\n'
                f'    route_to_stream(id: "{stream_id}");\nend')
        rules.append({"title":title,"description":"Optional backend routing of canonical events","source":source})
    return rules


# These are compatibility fields for the old Graylog pipelines, never the agent contract.
PROJECTIONS={
    "source_ip":"nf_src_address", "destination_ip":"nf_dst_address",
    "source_port":"nf_src_port", "destination_port":"nf_dst_port",
    "event_start":"nf_start", "event_end":"nf_stop", "network_direction":"flow_direction",
    "source_bytes":"nf_bytes", "source_packets":"nf_pkts", "network_iana_number":"nf_proto",
    "flint2_tcp_flags":"nf_tcp_flags", "flint2_local_device_ip":"lan_device_ip",
    "flint2_local_device_name":"lan_device_name", "flint2_local_device_mac":"lan_device_mac",
    "flint2_local_device_network":"lan_network", "flint2_peer_ip":"lan_peer_ip",
    "flint2_peer_name":"lan_peer_name"}
LOG_PROJECTIONS={
    "source_port":"src_port", "destination_port":"dst_port", "observer_ingress_zone":"fw_zone",
    "observer_ingress_interface_name":"in_iface", "observer_egress_interface_name":"out_iface",
    "flint2_packet_length":"pkt_len", "flint2_packet_ttl":"ttl", "flint2_tcp_window":"tcp_window",
    "flint2_packet_id":"ip_id", "flint2_packet_payload_length":"payload_len", "flint2_tcp_flag_names":"tcp_flags"}


def projection_rules(input_id):
    rules=[]
    for dataset, mapping in [("network_flow",PROJECTIONS),("router_log",LOG_PROJECTIONS)]:
        for src,dst in mapping.items():
            title="Flint2 legacy "+dataset+" "+dst
            source=(f'rule "{title}"\nwhen\n'
                    f'    to_string($message.gl2_source_input) == "{input_id}" &&\n'
                    f'    to_string($message.event_dataset) == "flint2.{dataset}" && has_field("{src}")\n'
                    f'then\n    set_field("{dst}", $message.{src});\nend')
            rules.append({"title":title,"description":"Backend-only compatibility projection","source":source})
    for src,dst in [("event_action","fw_action"),("network_transport","protocol")]:
        title="Flint2 legacy router_log "+dst
        source=(f'rule "{title}"\nwhen\n'
                f'    to_string($message.gl2_source_input) == "{input_id}" &&\n'
                f'    to_string($message.event_dataset) == "flint2.router_log" && has_field("{src}")\n'
                f'then\n    set_field("{dst}", uppercase(to_string($message.{src})));\nend')
        rules.append({"title":title,"description":"Backend-only uppercase legacy vocabulary","source":source})
    for direction,side,address in [("inbound","dst","destination_ip"),("outbound","src","source_ip")]:
        title="Flint2 legacy WAN "+direction
        source=(f'rule "{title}"\nwhen\n'
                f'    to_string($message.gl2_source_input) == "{input_id}" &&\n'
                f'    to_string($message.flint2_capture_scope) == "wan" &&\n'
                f'    to_string($message.network_direction) == "{direction}"\nthen\n'
                f'    set_field("flow_wan_side", "{side}");\n'
                f'    set_field("wan_ip", $message.{address});\nend')
        rules.append({"title":title,"description":"Backend projection of the observed perimeter direction","source":source})
    title="Flint2 legacy VPN service label"
    source=(f'rule "{title}"\nwhen\n'
            f'    to_string($message.gl2_source_input) == "{input_id}" &&\n'
            '    to_string($message.event_dataset) == "flint2.router_log" &&\n'
            '    to_string($message.observer_ingress_zone) == "vpn" &&\n'
            '    to_string($message.event_action) == "forward" && has_field("destination_port")\n'
            'then\n'
            '    set_field("fw_service", to_string(lookup_value("port-name", to_string($message.destination_port)), "Unregistered"));\nend')
    rules.append({"title":title,"description":"Port-derived legacy VPN service label for LAN and Internet destinations; not application identification","source":source})
    return rules


def connect(api):
    ids=json.loads((ROOT/"dist/graylog-resources.json").read_text())
    streams=api.request("GET","/streams")["streams"]
    by_title={stream["title"]:stream["id"] for stream in streams}
    targets={"router_log":by_title["Syslog"],"flow_wan":by_title["NetFlow"],"flow_lan":by_title["NetFlow LAN"]}
    rules=api.request("GET","/system/pipelines/rule")
    pipelines=api.request("GET","/system/pipelines/pipeline")
    connections=api.request("GET","/system/pipelines/connections")
    before=ROOT/"dist/graylog-processing-before-flint2-v3.json"
    if not before.exists():
        before.write_text(json.dumps({"rules":rules,"pipelines":pipelines,"connections":connections},indent=2)+"\n")
    projection=projection_rules(ids["input_id"])
    routing=routing_rules(ids["input_id"],targets)
    for rule in projection+routing:
        existing=next((x for x in rules if x["title"]==rule["title"]),None)
        if existing:api.request("PUT","/system/pipelines/rule/"+existing["id"],{**rule,"id":existing["id"]})
        else:api.request("POST","/system/pipelines/rule",rule)
    titles=[r["title"] for r in routing]
    pipeline={"title":TITLE,"description":"Native HTTPS source events use the established streams and enrichment",
              "source":'pipeline "'+TITLE+'"\nstage 0 match pass\n'+
              "\n".join('rule "'+r["title"]+'"' for r in projection)+'\nstage 1 match either\n'+
              "\n".join('rule "'+title+'"' for title in titles)+'\nend'}
    existing=next((x for x in pipelines if x["title"]==TITLE),None)
    if existing: saved=api.request("PUT","/system/pipelines/pipeline/"+existing["id"],{**pipeline,"id":existing["id"]})
    else:saved=api.request("POST","/system/pipelines/pipeline",pipeline)
    connection=next((c for c in connections if c["stream_id"]==ids["stream_id"]),None)
    pipeline_ids=set(connection["pipeline_ids"] if connection else [])
    pipeline_ids.add(saved["id"])
    api.request("POST","/system/pipelines/connections/to_stream",{"stream_id":ids["stream_id"],"pipeline_ids":sorted(pipeline_ids)})
    # Names supplied by the new agent are current; retain the old lookup as a fallback.
    for title, ip_field, name_field in [("LAN Device Name","lan_device_ip","lan_device_name"),
                                        ("LAN Peer Name","lan_peer_ip","lan_peer_name")]:
        existing=next(r for r in rules if r["title"]==title)
        guard='!has_field("'+name_field+'")'
        if guard not in existing["source"]:
            old='has_field("'+ip_field+'")'
            assert existing["source"].count(old)==1,"Unexpected existing rule shape: "+title
            changed={k:existing[k] for k in ["id","title","description","source"]}
            changed["source"]=changed["source"].replace(old,old+' && '+guard,1)
            api.request("PUT","/system/pipelines/rule/"+existing["id"],changed)
    result={"pipeline_id":saved["id"],"source_stream":ids["stream_id"],"targets":targets}
    (ROOT/"dist/graylog-source-routing.json").write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps(result,indent=2))


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply",action="store_true")
    args=parser.parse_args()
    if not args.apply:raise SystemExit("Use --apply to connect package-owned sources; token on stdin")
    connect(provision.Graylog(sys.stdin.read().strip()))
