// Input validation: closed enums and patterns only, nothing free-text in the
// schema, and no error message ever echoes what was sent (design §0, §4).
import { test } from 'node:test';
import assert from 'node:assert/strict';

import { MAX_BATCH, MAX_TOOL_CALLS_PER_BATCH } from '../../mcp/server.js';
import { callTool, fixtureServer, makeShardEnv, rpc } from './helpers.mjs';

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

test('a batch cannot multiply tool calls behind one rate-limited request', async () => {
  const { server } = await fixtureServer();
  const call = (id) => ({ jsonrpc: '2.0', id, method: 'tools/call', params: { name: 'get_corpus_file', arguments: { file: 'coverage' } } });
  const atCap = await server.handleMessage(Array.from({ length: MAX_TOOL_CALLS_PER_BATCH }, (_, i) => call(i)));
  assert.equal(atCap.length, MAX_TOOL_CALLS_PER_BATCH);
  assert.ok(atCap.every((r) => r.result.isError === false));

  // One over the cap: the whole batch is refused and no tool runs.
  const over = await server.handleMessage(Array.from({ length: MAX_TOOL_CALLS_PER_BATCH + 1 }, (_, i) => call(i)));
  assert.ok(!Array.isArray(over));
  assert.equal(over.error.code, -32600);
  assert.match(over.error.message, /tools\/call/);

  // Id-less tools/call messages count too, so they cannot pad a batch.
  const padded = await server.handleMessage([...Array.from({ length: MAX_TOOL_CALLS_PER_BATCH }, (_, i) => call(i)), { jsonrpc: '2.0', method: 'tools/call', params: { name: 'get_release' } }]);
  assert.equal(padded.error.code, -32600);

  // Cheap messages still fill the rest of a batch.
  const mixed = await server.handleMessage([
    ...Array.from({ length: MAX_TOOL_CALLS_PER_BATCH }, (_, i) => call(i)),
    ...Array.from({ length: MAX_BATCH - MAX_TOOL_CALLS_PER_BATCH }, (_, i) => ({ jsonrpc: '2.0', id: 100 + i, method: 'ping' })),
  ]);
  assert.equal(mixed.length, MAX_BATCH);

  const { out } = await callTool(server, 'get_release', {});
  assert.match(out.rate_limit.batch, new RegExp(`at most ${MAX_TOOL_CALLS_PER_BATCH} may be tools/call`));
});

test('an unexpected exception reaches the caller as a fixed message, never its own text', async () => {
  // A shard that fails with text the caller must never see: an internal
  // message can carry a bound parameter or a database detail.
  const boom = () => { throw new Error(`D1_ERROR near ${SENTINEL}: no such table`); };
  const shards = makeShardEnv();
  const env = { ...shards, S2: { prepare: boom, batch: boom } };
  const { server } = await fixtureServer({ env });
  for (const [name, args] of [
    ['verify_case', { case_number: '90-00001' }],
    ['get_decision_text', { decision_id: '90-00003.h1' }],
    ['find_decisions', { guidelines: ['G'] }],
  ]) {
    const res = await rpc(server, 'tools/call', { name, arguments: args });
    const wire = JSON.stringify(res);
    assert.ok(!wire.includes(SENTINEL) && !wire.includes('D1_ERROR') && !wire.includes('no such table'), `${name} leaked an internal message: ${wire.slice(0, 200)}`);
    if (res.error) assert.deepEqual(res.error, { code: -32603, message: 'Internal error.' }, name);
  }
  // At least the direct read path must surface as the generic internal error.
  const direct = await rpc(server, 'tools/call', { name: 'get_decision_text', arguments: { decision_id: '90-00003.h1' } });
  assert.deepEqual(direct.error, { code: -32603, message: 'Internal error.' });
  // Intended validation errors still reach the caller, named by parameter.
  const invalid = await rpc(server, 'tools/call', { name: 'verify_case', arguments: { case_number: 'nope' } });
  assert.equal(invalid.error.code, -32602);
  assert.match(invalid.error.message, /case_number/);
});
