'use strict';
'require view';
'require form';
'require uci';
'require network';
'require tools.widgets as widgets';

function validateDevices(value, maximum, optional) {
    var values = L.toArray(value);
    if (!optional && values.length === 0)
        return _('Select an interface.');
    if (values.length > maximum)
        return _('Too many interfaces selected (maximum %d).').format(maximum);
    for (var i = 0; i < values.length; i++) {
        if (!/^[A-Za-z0-9_.:-]{1,15}$/.test(values[i]))
            return _('Use an interface name of 1–15 letters, digits, underscores, dots, colons or hyphens.');
        if (values.indexOf(values[i]) !== i)
            return _('Each interface may be selected only once.');
    }
    return true;
}

return view.extend({
    load: function() {
        return Promise.all([uci.load('flint2'), network.getDevices()]);
    },

    render: function(data) {
        var m = new form.Map('flint2', _('Flint2 Telemetry'),
            _('Choose existing network devices to monitor, or enter a device name for a VPN or VLAN that is currently absent. Save & Apply reloads telemetry. These settings do not create or reconfigure network interfaces.'));
        var s = m.section(form.NamedSection, 'main', 'agent');
        s.addremove = false;
        var o;

        o = s.option(form.DummyValue, '_telemetry_enabled', _('Telemetry'));
        o.cfgvalue = function() {
            return uci.get('flint2', 'main', 'enabled') === '1' ? _('Enabled in configuration') : _('Disabled in configuration');
        };

        o = s.option(form.DummyValue, '_export_destination', _('Configured log destination'));
        o.description = _('Read from this router’s configuration. Each installation configures its own collector or SIEM endpoint.');
        o.cfgvalue = function() {
            var names = { gelf: 'GELF over HTTPS', otlp_http_json: 'OpenTelemetry logs', ecs_ndjson: 'ECS NDJSON' };
            var format = uci.get('flint2', 'main', 'format') || 'gelf';
            return (names[format] || format) + ' — ' + (uci.get('flint2', 'main', 'endpoint') || _('Not configured'));
        };

        o = s.option(widgets.DeviceSelect, 'interface', _('Statistics interfaces'),
            _('Collect interface counters and rates. WAN counters are added automatically. Bridge and physical-port counters can describe the same traffic; do not add their totals together.'));
        o.multiple = true;
        o.noaliases = true;
        o.rmempty = true;
        o.validate = function(section, value) { return validateDevices(value, 32, true); };

        o = s.option(form.Value, 'wan_interface', _('WAN interface'),
            _('Automatic detection follows the current WAN device, including PPPoE. Choose a device name to override detection.'));
        o.value('auto', _('Automatic WAN detection'));
        (data[1] || []).forEach(function(device) {
            if (device.getName() !== 'lo')
                o.value(device.getName());
        });
        o.default = 'auto';
        o.rmempty = false;
        o.validate = function(section, value) { return validateDevices(value, 1, false); };

        o = s.option(form.Flag, 'flow_capture', _('Capture network flows'),
            _('Observe IPv4 flow metadata on the WAN and selected local interfaces.'));
        o.default = '1';
        o.rmempty = false;

        o = s.option(widgets.DeviceSelect, 'flow_lan_interface', _('Local flow interfaces'),
            _('Normally select LAN, guest or IoT bridges. An empty selection captures WAN only. The WAN device is skipped here if also selected. Capturing a bridge and its physical port observes overlapping traffic.'));
        o.multiple = true;
        o.noaliases = true;
        o.rmempty = true;
        o.retain = true;
        o.depends('flow_capture', '1');
        o.validate = function(section, value) { return validateDevices(value, 8, true); };

        o = s.option(form.Flag, 'firewall_events', _('Observe firewall events'),
            _('Collect rate-limited WAN drops and forwarded connection attempts. An observed attempt does not prove the connection was accepted.'));
        o.default = '1';
        o.rmempty = false;

        o = s.option(widgets.DeviceSelect, 'vpn_interface', _('VPN event interfaces'),
            _('Observe forwarded attempts arriving on these VPN devices. Leave empty to disable VPN event observations. To capture VPN flow metadata as well, select the device under Local flow interfaces.'));
        o.multiple = true;
        o.noaliases = true;
        o.rmempty = true;
        o.retain = true;
        o.depends('firewall_events', '1');
        o.validate = function(section, value) { return validateDevices(value, 8, true); };

        return m.render().then(function(settings) {
            return E('div', {}, [
                E('section', { 'class': 'cbi-section' }, [
                    E('h2', {}, _('What you can do with Flint2 Telemetry')),
                    E('p', {}, _('Send structured router observations to dashboards, searches and alerts in your monitoring platform.')),
                    E('ul', {}, [
                        E('li', {}, _('Monitor router health: CPU, memory, temperature, uptime, connection-table capacity and WAN availability.')),
                        E('li', {}, _('Track traffic: interface counters and rates, plus IPv4 flow observations showing addresses, ports, protocol, bytes and packets.')),
                        E('li', {}, _('Identify local devices using DHCP, static leases and available GL.iNet device names. Inventory is not proof that a device is online.')),
                        E('li', {}, _('Search router logs and rate-limited firewall observations to investigate drops and forwarded connection attempts.'))
                    ]),
                    E('details', {}, [
                        E('summary', {}, _('How to choose interfaces')),
                        E('ul', {}, [
                            E('li', {}, _('Statistics interfaces collect counters and rates. WAN counters are included automatically.')),
                            E('li', {}, _('Keep WAN on automatic detection unless you need to override the observed WAN device.')),
                            E('li', {}, _('Local flow interfaces normally use your LAN, guest and IoT bridges. Add a VLAN or VPN device here if you also want its flow metadata.')),
                            E('li', {}, _('VPN event interfaces observe forwarded attempts entering those devices. Selecting a name does not enable a VPN server.')),
                            E('li', {}, _('Save & Apply reloads the telemetry service. Missing devices remain configured and can be monitored when they become available.'))
                        ])
                    ]),
                    E('details', {}, [
                        E('summary', {}, _('Connect to logging and monitoring platforms')),
                        E('p', {}, _('Send logs and flow observations as OpenTelemetry logs, ECS NDJSON or GELF over HTTPS. Send native metrics using OTLP/HTTP JSON to a metrics-capable destination. Use a compatible OpenTelemetry Collector when your logging or monitoring platform needs a supported exporter or adapter.')),
                        E('p', {}, _('This page controls monitored interfaces. Configure your own HTTPS endpoints and delivery settings in /etc/config/flint2. Optional metric event copies let logging platforms search measurements as log records; native metrics remain a separate signal. Destination support depends on the formats it accepts.'))
                    ]),
                    E('p', {}, [E('a', { href: 'https://github.com/narey83/GL.iNet-Flint2-Telemetry#readme', target: '_blank', rel: 'noopener noreferrer' }, _('Documentation, setup and supported destinations on GitHub'))]),
                    E('details', {}, [
                        E('summary', {}, _('Collection limits and VPN connection logging')),
                        E('p', {}, _('Current VPN observations cover forwarded traffic, not WireGuard handshake or tunnel connection events. Switching on a WireGuard client alone does not produce a VPN connection event here.')),
                        E('p', {}, _('Flow capture currently covers IPv4. Hardware acceleration, capture drops and rejected timestamps can reduce visibility. A forwarded attempt is not proof of acceptance. Bridge and physical-port observations can overlap.')),
                        E('p', {}, _('Exported records may include IP and MAC addresses, device names and router logs. Configure a trusted destination and suitable retention.'))
                    ])
                ]),
                settings
            ]);
        });
    }
});
