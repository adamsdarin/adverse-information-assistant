// Input validation: closed enums and patterns only, nothing free-text in the
// schema, and no error message ever echoes what was sent (design §0, §4).
import { test } from 'node:test';
import assert from 'node:assert/strict';

import { MAX_BATCH } from '../../mcp/server.js';
import { callTool, fixtureServer, rpc } from './helpers.mjs';

const SENTINEL = 'ZQX-SENTINEL-4471';

test('no tool accepts a string the user could have typed', async () => {
  const { server } = await fixtureServer();
  assert.equal(server.tools.length, 17, 'design §2.2 defines seventeen tools');
  for (const tool of server.tools) {
    const schema = tool.inputSchema;
    assert.equal(schema.additionalProperties, false, tool.name);
    for (const [prop, def] of Object.entries(schema.properties)) {
      const leaf = def.type === 'array' ? def.items : def;
      if (leaf.type === 'string') {
        assert.ok(Array.isArray(leaf.enum) || typeof leaf.pattern === 'string', `${tool.name}.${prop} is a free string`);
      } else {
        assert.ok(['integer', 'boolean'].includes(leaf.type), `${tool.name}.${prop} has type ${leaf.type}`);
      }
    }
  }
});

test('values outside the closed sets are invalid-params errors that never echo the value', async () => {
  const { server } = await fixtureServer();
  const attempts = [
    ['get_guideline_text', { guidelines: [SENTINEL] }],
    ['get_guideline_text', { guidelines: ['G', 'G'] }],
    ['get_guideline_text', { guidelines: [] }],
    ['get_guideline_text', { guidelines: 'G' }],
    ['get_reporting_requirements', { access: SENTINEL }],
    ['get_reporting_requirements', { access: 'ts_q', include_data_elements: 'yes' }],
    ['get_isl_section', { table: 5 }],
    ['get_isl_section', { verifies: SENTINEL }],
    ['get_isl_section', {}],
    ['get_isl_section', { table: 1, verifies: 'channels' }],
    ['get_cfr_section', { section: '117.9' }],
    ['get_cfr_section', { section: SENTINEL }],
    ['get_reporting_tables', { population: SENTINEL, access: 'baseline' }],
    ['get_reporting_tables', { population: 'industry', access: 'baseline', event_ids: [SENTINEL] }],
    ['get_checklists', {}],
    ['get_checklists', { event_ids: [SENTINEL] }],
    ['get_form_map', { form: SENTINEL }],
    ['get_form_map', { form: 'sf86', sections: [SENTINEL] }],
    ['get_severity_ladder', { guideline: 'g' }],
    ['get_document_evidence', { guidelines: ['N'] }],
    ['court_lookup', { state: SENTINEL }],
    ['court_lookup', { state: 'IA', county: SENTINEL }],
    ['court_lookup', { state: 'IA', offense: SENTINEL }],
    ['get_corpus_file', { file: SENTINEL }],
    ['get_corpus_bundle', { [SENTINEL]: 1 }],
    ['find_decisions', { guidelines: ['G'], limit: 13 }],
    ['find_decisions', { guidelines: ['G'], limit: 0 }],
    ['find_decisions', { guidelines: ['G'], include_pre_sead4: 'no' }],
    ['verify_case', { case_number: SENTINEL }],
    ['verify_case', { case_number: '24-123' }],
    ['verify_case', { case_number: '24-01234 ' }],
    ['get_decision_text', { decision_id: SENTINEL }],
    ['get_decision_text', { decision_id: '24-01234' }],
    ['get_decision_text', { decision_id: '24-01234.h1', part_from: 0 }],
    ['get_decision_text', { decision_id: '24-01234.h1', part_from: 5, part_to: 4 }],
    ['get_decision_text', { decision_id: '24-01234.h1', part_from: 1, part_to: 11 }],
    ['get_release', { narrative: SENTINEL }],
    [SENTINEL, {}],
  ];
  for (const [name, args] of attempts) {
    const res = await callTool(server, name, args);
    assert.ok(res.error, `${name} ${JSON.stringify(args)} should be rejected`);
    assert.equal(res.error.code, -32602, `${name} ${JSON.stringify(args)}`);
    assert.ok(!JSON.stringify(res).includes(SENTINEL), `${name} echoed the input: ${res.error.message}`);
  }
  // Arguments that are not an object.
  const notObject = await rpc(server, 'tools/call', { name: 'get_release', arguments: [SENTINEL] });
  assert.equal(notObject.error.code, -32602);
  assert.ok(!JSON.stringify(notObject).includes(SENTINEL));
});

test('prompt arguments are categorical too', async () => {
  const { server } = await fixtureServer();
  const bad = await rpc(server, 'prompts/get', { name: 'conductor', arguments: { client_can_run_scripts: SENTINEL } });
  assert.equal(bad.error.code, -32602);
  assert.ok(!JSON.stringify(bad).includes(SENTINEL));
  const unknown = await rpc(server, 'prompts/get', { name: SENTINEL });
  assert.equal(unknown.error.code, -32602);
  assert.ok(!JSON.stringify(unknown).includes(SENTINEL));
  const extra = await rpc(server, 'prompts/get', { name: 'triage', arguments: { [SENTINEL]: 'x' } });
  assert.equal(extra.error.code, -32602);
  assert.ok(!JSON.stringify(extra).includes(SENTINEL));
});

test('JSON-RPC framing: batches are capped, notifications are silent, unknown methods are refused', async () => {
  const { server } = await fixtureServer();
  const big = Array.from({ length: MAX_BATCH + 1 }, (_, i) => ({ jsonrpc: '2.0', id: i, method: 'ping' }));
  const capped = await server.handleMessage(big);
  assert.equal(capped.error.code, -32600);
  const ok = await server.handleMessage(big.slice(0, MAX_BATCH));
  assert.equal(ok.length, MAX_BATCH);
  assert.equal(await server.handleMessage({ jsonrpc: '2.0', method: 'notifications/initialized' }), null);
  assert.equal((await server.handleMessage([])).error.code, -32600);
  assert.equal((await server.handleMessage({ jsonrpc: '1.0', id: 1, method: 'ping' })).error.code, -32600);
  assert.equal((await rpc(server, SENTINEL)).error.code, -32601);
  assert.ok(!JSON.stringify(await rpc(server, SENTINEL)).includes(SENTINEL));
  const init = await rpc(server, 'initialize', { protocolVersion: '2025-03-26', capabilities: {}, clientInfo: { name: 't', version: '0' } });
  assert.equal(init.result.protocolVersion, '2025-03-26');
  assert.equal(init.result.serverInfo.name, 'adverse-information-assistant');
  assert.ok(init.result.capabilities.prompts);
  const res = await rpc(server, 'resources/read', { uri: `adverse://corpus/${SENTINEL}` });
  assert.equal(res.error.code, -32002);
  assert.ok(!JSON.stringify(res).includes(SENTINEL));
});
