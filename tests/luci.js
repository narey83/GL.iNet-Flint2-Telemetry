// Exercise the actual LuCI view validators using a minimal form harness.
'use strict';
const fs = require('node:fs');
const assert = require('node:assert/strict');
const source = fs.readFileSync('package/files/www/luci-static/resources/view/flint2/interfaces.js', 'utf8');
const options = new Map();
let config = { enabled: '1' };
const form = {
    Map: class {
        constructor(name) { assert.equal(name, 'flint2'); }
        section() { return { option(type, name) {
            const option = { type, value() {}, depends() {} };
            options.set(name, option);
            return option;
        } }; }
        render() { return Promise.resolve(this); }
    },
    NamedSection: {}, DummyValue: {}, Value: {}, Flag: {}
};
const widgets = { DeviceSelect: {} };
const L = { toArray(value) { return Array.isArray(value) ? value : typeof value === 'string' && value.trim() ? value.trim().split(/\s+/) : []; } };
String.prototype.format = function(value) { return this.replace('%d', value); };
const page = new Function('view', 'form', 'uci', 'network', 'widgets', 'L', '_', 'E', source)(
    { extend: value => value }, form, { get: (a, b, key) => config[key] }, {}, widgets, L, value => value, (tag, attributes, children) => ({ tag, attributes, children }));
page.render([{}, []]);
for (const [name, limit] of [['interface', 32], ['flow_lan_interface', 8], ['vpn_interface', 8]]) {
    const option = options.get(name);
    assert.equal(option.type, widgets.DeviceSelect);
    assert.equal(option.multiple, true);
    assert.equal(option.validate('main', []), true, 'Empty selections must be supported');
    assert.equal(option.validate('main', ['br-lan', 'eth0.20', 'wgserver']), true);
    assert.notEqual(option.validate('main', ['eth0', 'eth0']), true);
    for (const invalid of ['../etc/passwd', 'eth0;reboot', 'interface-name-too-long', '<script>'])
        assert.notEqual(option.validate('main', [invalid]), true);
    assert.notEqual(option.validate('main', Array.from({ length: limit + 1 }, (_, i) => `eth${i}`)), true);
}
const wan = options.get('wan_interface');
assert.equal(wan.validate('main', 'auto'), true);
assert.equal(wan.validate('main', 'pppoe-wan'), true);
assert.notEqual(wan.validate('main', ''), true);
assert.notEqual(wan.validate('main', 'eth0 eth1'), true);
assert.equal(options.get('_telemetry_enabled').cfgvalue(), 'Enabled in configuration');
config.enabled = '0';
assert.equal(options.get('_telemetry_enabled').cfgvalue(), 'Disabled in configuration');
const acl = JSON.parse(fs.readFileSync('package/files/usr/share/rpcd/acl.d/luci-app-flint2-telemetry.json', 'utf8'))['luci-app-flint2-telemetry'];
assert.deepEqual(acl.write, { uci: ['flint2'] }, 'The page must not grant network/firewall or shell write access');
const menu = JSON.parse(fs.readFileSync('package/files/usr/share/luci/menu.d/luci-app-flint2-telemetry.json', 'utf8'));
assert.deepEqual(menu['admin/services/flint2'].depends.acl, ['luci-app-flint2-telemetry']);
config.format = 'otlp_http_json';
config.endpoint = 'https://collector.example.invalid/v1/logs';
assert.equal(options.get('_export_destination').cfgvalue(), 'OpenTelemetry logs — https://collector.example.invalid/v1/logs');
page.render([{}, []]).then(function(result) {
    assert.equal(result.tag, 'div');
    const help = JSON.stringify(result.children[0]);
    assert.ok(!/Graylog|Splunk/i.test(help), 'General capability guide must be backend-neutral');
    for (const phrase of ['What you can do with Flint2 Telemetry', 'How to choose interfaces', 'Connect to logging and monitoring platforms', 'OTLP/HTTP JSON', 'https://github.com/narey83/flint2-telemetry#readme', 'noopener noreferrer', 'not WireGuard handshake'])
        assert.ok(help.includes(phrase), phrase);
    console.log('PASS: LuCI validation, restricted ACL, destination display and capability guide');
});
