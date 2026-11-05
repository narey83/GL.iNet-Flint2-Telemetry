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
            const option = { type, choices: [], dependencies: [], value(value) { this.choices.push(value); }, depends(key, value) { this.dependencies.push([key, value]); } };
            options.set(name, option);
            return option;
        } }; }
        render() { return Promise.resolve(this); }
    },
    NamedSection: {}, DummyValue: {}, Value: function() {}, Flag: {}, ListValue: {}
};
form.Value.prototype.remove = function(section) { return 'removed:' + section; };
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
for (const name of ['enabled', 'metrics_enabled', 'metric_events_enabled']) {
    assert.equal(options.get(name).type, form.Flag);
    assert.equal(options.get(name).rmempty, false, 'Disabled flags must persist as zero');
}
assert.deepEqual(options.get('format').choices, ['otlp_http_json', 'ecs_ndjson', 'gelf']);
for (const name of ['endpoint', 'metrics_endpoint']) {
    const option = options.get(name);
    for (const url of ['https://collector.example.invalid/v1/logs', 'https://graylog.example.invalid:12201/gelf', 'https://192.0.2.1:4318/v1/metrics'])
        assert.equal(option.validate('main', url), true);
    for (const url of ['', 'http://collector.example.invalid/gelf', 'https://user:secret@collector.example.invalid/gelf',
        'https://collector.example.invalid/gelf?token=secret', 'https://collector.example.invalid/gelf#part',
        'https://collector.example.invalid:65536/gelf', 'https://collector.example.invalid:0/gelf',
        'https://collector.example.invalid/gelf\n', 'https://collector.example.invalid'])
        assert.notEqual(option.validate('main', url), true, url);
}
for (const name of ['metrics_endpoint', 'metrics_ca_file']) {
    assert.deepEqual(options.get(name).dependencies, [['metrics_enabled', '1']]);
    assert.equal(options.get(name).retain, true, 'Disabling metrics must preserve its destination settings');
}
for (const name of ['metrics_endpoint', 'metrics_ca_file', 'flow_lan_interface', 'vpn_interface']) {
    const option = options.get(name);
    option.isActive = () => false;
    assert.equal(option.remove('main'), undefined, 'Hidden values must survive legacy LuCI removal');
    option.isActive = () => true;
    assert.equal(option.remove('main'), 'removed:main', 'Visible empty fields must still be removable');
}
assert.equal(options.get('ca_file').validate('main', '/etc/ssl/certs/ca-certificates.crt'), true);
assert.notEqual(options.get('ca_file').validate('main', 'cert.pem'), true);
assert.notEqual(options.get('ca_file').validate('main', '/tmp/cert;reboot'), true);
assert.equal(options.get('metrics_ca_file').validate('main', ''), true);
const acl = JSON.parse(fs.readFileSync('package/files/usr/share/rpcd/acl.d/luci-app-flint2-telemetry.json', 'utf8'))['luci-app-flint2-telemetry'];
assert.deepEqual(acl.write, { uci: ['flint2'] }, 'The page must not grant network/firewall or shell write access');
const menu = JSON.parse(fs.readFileSync('package/files/usr/share/luci/menu.d/luci-app-flint2-telemetry.json', 'utf8'));
assert.deepEqual(menu['admin/services/flint2'].depends.acl, ['luci-app-flint2-telemetry']);
page.render([{}, []]).then(function(result) {
    assert.equal(result.tag, 'div');
    const help = JSON.stringify(result.children[0]);
    assert.ok(!/Graylog|Splunk/i.test(help), 'General capability guide must be backend-neutral');
    for (const phrase of ['What you can do with Flint2 Telemetry', 'How to choose interfaces', 'Connect to logging and monitoring platforms', 'OTLP/HTTP JSON', 'https://github.com/narey83/GL.iNet-Flint2-Telemetry#readme', 'noopener noreferrer', 'not WireGuard handshake'])
        assert.ok(help.includes(phrase), phrase);
    console.log('PASS: LuCI validation, restricted ACL, export controls and URL validation, legacy field retention and capability guide');
});
