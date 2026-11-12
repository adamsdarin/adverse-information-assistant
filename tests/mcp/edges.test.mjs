// Edges the other suites leave open: the local Node HTTP server and its
// command-line entry point, the Worker's fail-closed recovery and rate-limit
// keying, the guide's escaping, malformed manifests, JSON-RPC framing
// corners, prompt preambles, and the promise that an internal failure never
// reaches the client as text. Tests only; no Worker code is changed here.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { readFile, rm } from 'node:fs/promises';
import { join } from 'node:path';

import { startHttpMcpServer } from '../../mcp/http.js';
import worker, { resetWorkerCache } from '../../mcp/worker.js';
import { renderGuide } from '../../mcp/guide.js';
import { MCP_PROTOCOL_VERSIONS, STANDING_RULES, createAdverseMcpServer } from '../../mcp/server.js';
import { ReleaseIntegrityError, loadRelease } from '../../mcp/release.js';
import { ROOT, fixtureRelease, fixtureReleaseDir, fixtureServer, makeShardEnv, rpc, tamperableCopy } from './helpers.mjs';

const SENTINEL = 'ZQX-SENTINEL-9913';
const URL_ = 'https://fsotools.ai/adverse/mcp';
const post = (body, headers = {}) =>
  new Request(URL_, { method: 'POST', headers: { 'content-type': 'application/json', ...headers }, body: JSON.stringify(body) });

function fakeAssets(dir) {
  return {
    async fetch(url) {
      try {
        return new Response(await readFile(join(dir, decodeURI(new URL(url).pathname.slice(1)))));
      } catch {
        return new Response('not found', { status: 404 });
      }
    },
  };
}

test('the local Node server listens on loopback and answers only on the MCP paths', async () => {
  const { server } = await fixtureServer();
  const srv = await startHttpMcpServer(server, { port: 0 });
  try {
    const { address, port } = srv.address();
    assert.equal(address, '127.0.0.1', 'local dev binds loopback unless told otherwise');
    const base = `http://127.0.0.1:${port}`;

    const other = await fetch(`${base}/etc/passwd`);
    assert.equal(other.status, 404);
    assert.equal(other.headers.get('cache-control'), 'no-store');
    assert.match((await other.json()).error, /Not found/);

    for (const path of ['/adverse/mcp', '/mcp', '/']) {
      const listed = await fetch(`${base}${path}`, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ jsonrpc: '2.0', id: 1, method: 'tools/list' }),
      });
      assert.equal(listed.status, 200, path);
      assert.equal((await listed.json()).result.tools.length, 17, path);
    }
    const card = await fetch(`${base}/adverse/mcp`, { headers: { accept: 'application/json' } });
    assert.equal((await card.json()).stateless, true);
    const options = await fetch(`${base}/adverse/mcp`, { method: 'OPTIONS' });
    assert.equal(options.status, 204);
    const bad = await fetch(`${base}/adverse/mcp`, { method: 'POST', body: '{nope' });
    assert.equal(bad.status, 400);
  } finally {
    await new Promise((r) => srv.close(r));
  }
});

test('a Worker GET that does not ask for HTML gets the JSON server card, not the guide', async () => {
  resetWorkerCache();
  const env = { ASSETS: fakeAssets(fixtureReleaseDir()) };
  const res = await worker.fetch(new Request(URL_, { headers: { accept: 'application/json' } }), env);
  assert.equal(res.status, 200);
  assert.match(res.headers.get('content-type'), /application\/json/);
  assert.equal(res.headers.get('cache-control'), 'no-store');
  const card = await res.json();
  assert.equal(card.tools.length, 17);
  assert.equal(card.stateless, true);
  resetWorkerCache();
});

test('a failed release load is not cached: the Worker serves once the release verifies', async () => {
  resetWorkerCache();
  const broken = { ASSETS: { async fetch() { return new Response('nope', { status: 404 }); } } };
  const first = await worker.fetch(post({ jsonrpc: '2.0', id: 1, method: 'ping' }), broken);
  assert.equal(first.status, 503);
  assert.equal(first.headers.get('retry-after'), '300');
  assert.equal((await first.json()).error.code, -32603);
  // Same isolate, no reset: the next request must retry the load.
  const healed = await worker.fetch(post({ jsonrpc: '2.0', id: 2, method: 'ping' }), { ASSETS: fakeAssets(fixtureReleaseDir()) });
  assert.equal(healed.status, 200);
  assert.deepEqual((await healed.json()).result, {});
  resetWorkerCache();
});

test('a release missing DISCLAIMER.md withholds it from the guide rather than inventing one', async () => {
  resetWorkerCache();
  const dir = tamperableCopy();
  await rm(join(dir, 'DISCLAIMER.md'));
  const guide = await worker.fetch(new Request(URL_, { headers: { accept: 'text/html' } }), { ASSETS: fakeAssets(dir) });
  assert.equal(guide.status, 200);
  assert.ok((await guide.text()).includes('DISCLAIMER.md failed verification and is not shown.'));
  resetWorkerCache();
});

test('rate limiting keys on the connecting IP, covers POST only, and is skipped with no binding', async () => {
  resetWorkerCache();
  const keys = [];
  const limiter = { async limit({ key }) { keys.push(key); return { success: true }; } };
  const env = { ASSETS: fakeAssets(fixtureReleaseDir()), MCP_LIMIT: limiter };
  await worker.fetch(post({ jsonrpc: '2.0', id: 1, method: 'ping' }, { 'cf-connecting-ip': '198.51.100.7' }), env);
  await worker.fetch(post({ jsonrpc: '2.0', id: 2, method: 'ping' }), env);
  await worker.fetch(new Request(URL_, { headers: { accept: 'text/html' } }), env);
  await worker.fetch(new Request(URL_, { method: 'OPTIONS' }), env);
  assert.deepEqual(keys, ['198.51.100.7', 'unknown'], 'one key per POST, none for GET or OPTIONS');

  const unlimited = await worker.fetch(post({ jsonrpc: '2.0', id: 3, method: 'ping' }), { ASSETS: fakeAssets(fixtureReleaseDir()) });
  assert.equal(unlimited.status, 200);

  const denied = await worker.fetch(post({ jsonrpc: '2.0', id: 4, method: 'ping' }), {
    ASSETS: fakeAssets(fixtureReleaseDir()),
    MCP_LIMIT: { async limit() { return { success: false }; } },
  });
  assert.equal(denied.status, 429);
  assert.equal(denied.headers.get('access-control-allow-origin'), '*', 'a browser client can read the 429');
  resetWorkerCache();
});

test('the guide HTML-escapes every value it interpolates', async () => {
  const hostile = '<script>alert(1)</script>';
  const release = {
    manifest: {
      library_release: hostile,
      library_approval: { approved_utc: '"><img src=x onerror=1>', approved_by: "o'brien & co" },
      corpus_version: '<b>v</b>',
      repo_commit: '<i>c</i>',
      built_utc: '<u>t</u>',
      counts: { government_files: '<g>', maintainer_files: 3, maintainer_verified: 0, maintainer_unverified: 3 },
      cfr_117: { available: true },
    },
    has: () => true,
    text: () => `Disclaimer ${hostile}`,
  };
  const server = {
    tools: [{ name: '<tool>', description: 'reads & <writes>' }],
    prompts: [{ name: '<prompt>' }],
    resources: [],
  };
  const html = renderGuide(release, server);
  for (const raw of [hostile, '<img', '<b>v', '<i>c', '<u>t', '<tool>', '<writes>', '<prompt>', '<g>']) {
    assert.ok(!html.includes(raw), `unescaped: ${raw}`);
  }
  assert.ok(html.includes('&lt;script&gt;alert(1)&lt;/script&gt;'));
  assert.ok(html.includes('o&#39;brien &amp; co'));
  assert.ok(html.includes('32 CFR § 117.8: available'));
  assert.equal((html.match(/<script/g) ?? []).length, 0);

  const unsplit = renderGuide({ ...release, manifest: { ...release.manifest, cfr_117: { available: false } }, has: () => false }, server);
  assert.ok(unsplit.includes('unavailable in this release'));
  assert.ok(unsplit.includes('DISCLAIMER.md failed verification and is not shown.'));
});

test('JSON-RPC corners: protocol fallback, missing names, mixed batches, null arguments', async () => {
  const { server } = await fixtureServer();
  const init = await rpc(server, 'initialize', { protocolVersion: '1999-01-01' });
  assert.equal(init.result.protocolVersion, MCP_PROTOCOL_VERSIONS[0], 'an unknown version gets the newest supported one');
  assert.equal(init.result.instructions, STANDING_RULES.join(' '));
  assert.equal((await rpc(server, 'initialize')).result.protocolVersion, MCP_PROTOCOL_VERSIONS[0]);
  assert.deepEqual((await rpc(server, 'resources/templates/list')).result, { resourceTemplates: [] });

  for (const [method, params] of [['tools/call', {}], ['tools/call', { name: 7 }], ['resources/read', {}], ['prompts/get', { name: null }]]) {
    const res = await rpc(server, method, params);
    assert.equal(res.error.code, -32602, `${method} ${JSON.stringify(params)}`);
  }
  const nullArgs = await rpc(server, 'tools/call', { name: 'get_release', arguments: null });
  assert.equal(nullArgs.result.isError, false, 'null arguments mean no arguments');
  const nullParams = await server.handleMessage({ jsonrpc: '2.0', id: 9, method: 'tools/list', params: null });
  assert.equal(nullParams.result.tools.length, 17);

  const proto = await server.handleMessage(
    JSON.parse(`{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"get_release","arguments":{"__proto__":{"x":"${SENTINEL}"}}}}`),
  );
  assert.equal(proto.error.code, -32602, 'a __proto__ key is an unexpected parameter, not a prototype write');
  assert.ok(!JSON.stringify(proto).includes(SENTINEL));

  const mixed = await server.handleMessage([
    { jsonrpc: '2.0', method: 'notifications/initialized' },
    { jsonrpc: '2.0', id: 'a', method: 'ping' },
    { jsonrpc: '1.0', id: 'b', method: 'ping' },
    'not an object',
  ]);
  assert.equal(mixed.length, 3, 'the notification gets no response; every other item does');
  assert.deepEqual(mixed[0], { jsonrpc: '2.0', id: 'a', result: {} });
  assert.equal(mixed[1].id, 'b');
  assert.equal(mixed[1].error.code, -32600);
  assert.equal(mixed[2].id, null);
  assert.equal(await server.handleMessage([{ jsonrpc: '2.0', method: 'notifications/initialized' }]), null);
});

test('an unexpected failure inside a tool is "Internal error." and never its message', async () => {
  const release = await fixtureRelease();
  const leaky = Object.create(release);
  leaky.json = function (path) {
    if (path.includes('_SEVERITY_LADDERS')) throw new Error(`internal detail ${SENTINEL}`);
    return release.json(path);
  };
  const server = createAdverseMcpServer(leaky, {});
  const res = await rpc(server, 'tools/call', { name: 'get_severity_ladder', arguments: { guideline: 'G' } });
  assert.equal(res.error.code, -32603);
  assert.equal(res.error.message, 'Internal error.');
  assert.ok(!JSON.stringify(res).includes(SENTINEL));
});

test('decision shards that stop answering fail closed and are not retried on every call', async () => {
  const release = await fixtureRelease();
  let calls = 0;
  const down = () => {
    calls += 1;
    throw new Error(`d1 down ${SENTINEL}`);
  };
  const dead = { prepare: down, batch: async () => down() };
  const server = createAdverseMcpServer(release, { env: { S1: dead, S2: dead, S3: dead } });
  const first = await rpc(server, 'tools/call', { name: 'get_release', arguments: {} });
  assert.equal(first.result.structuredContent.decisions.shards_available, false);
  assert.match(first.result.structuredContent.decisions.note, /did not answer/);
  const before = calls;
  const second = await rpc(server, 'tools/call', { name: 'get_release', arguments: {} });
  assert.match(second.result.structuredContent.decisions.note, /retry later/);
  assert.equal(calls, before, 'a recent failure is cached rather than retried against D1 on every call');
  assert.ok(!JSON.stringify([first, second]).includes(SENTINEL));

  const healthy = createAdverseMcpServer(release, { env: makeShardEnv() });
  const ok = await rpc(healthy, 'tools/call', { name: 'get_release', arguments: {} });
  assert.equal(ok.result.structuredContent.decisions.shards_available, true);
});

test('a manifest that is not JSON, or not a release manifest, refuses the whole release', async () => {
  const only = (text) => async (path) => (path === 'manifest.json' ? new TextEncoder().encode(text) : null);
  await assert.rejects(loadRelease(only('{nope')), (e) => e instanceof ReleaseIntegrityError && e.reason === 'not valid JSON');
  await assert.rejects(loadRelease(only('{"files": {}}')), (e) => e instanceof ReleaseIntegrityError && /not a hosted release manifest/.test(e.reason));
  await assert.rejects(loadRelease(only('null')), (e) => e instanceof ReleaseIntegrityError);
});

test('a Part 117 split with no file for §117.8 is a tool error, never a guess', async () => {
  const release = await fixtureRelease();
  const split = Object.create(release);
  split.manifest = { ...release.manifest, cfr_117: { available: true, sections: [{ section: '117.9', file: '117_9_Other.md' }] } };
  const server = createAdverseMcpServer(split, {});
  const res = await rpc(server, 'tools/call', { name: 'get_cfr_section', arguments: { section: '117.8' } });
  assert.equal(res.result.isError, true);
  assert.match(res.result.structuredContent.error, /no file for that section/);
});

test('each prompt carries its hosted-mode preamble ahead of the verbatim agent text', async () => {
  const { server, release } = await fixtureServer();
  const text = async (name, args) => (await rpc(server, 'prompts/get', { name, arguments: args })).result.messages[0].content.text;
  for (const p of server.prompts) {
    const t = await text(p.name);
    assert.ok(t.includes('\n\n---\n\n'), `${p.name}: preamble and agent body are separated`);
  }
  assert.ok((await text('intake')).includes('call get_release instead of check_corpus.py'));
  assert.ok((await text('documents-advisor')).includes('get_corpus_file(adjudicative-readiness)'));
  const scoped = await text('requirements-advisor', { population: 'military' });
  assert.ok(scoped.includes("This session's population is military"));
  assert.ok(!(await text('requirements-advisor')).includes("This session's population is"));
  const body = release.text('agents/core/triage.md');
  assert.ok((await text('triage')).endsWith(body), 'the agent text follows verbatim');
});

test('node mcp/http.js serves a release folder on loopback for local development', async () => {
  const child = spawn(process.execPath, [join(ROOT, 'mcp', 'http.js'), '--release', fixtureReleaseDir(), '--port', '0'], {
    stdio: ['ignore', 'ignore', 'pipe'],
  });
  try {
    const url = await new Promise((resolveUrl, reject) => {
      let err = '';
      const timer = setTimeout(() => reject(new Error(`no ready line: ${err}`)), 90_000);
      child.stderr.on('data', (d) => {
        err += d;
        const m = /(http:\/\/127\.0\.0\.1:\d+\/adverse\/mcp)/.exec(err);
        if (m) {
          clearTimeout(timer);
          resolveUrl(m[1]);
        }
      });
      child.on('exit', (code) => reject(new Error(`exited ${code}: ${err}`)));
    });
    const res = await fetch(url, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ jsonrpc: '2.0', id: 1, method: 'tools/list' }),
    });
    assert.equal((await res.json()).result.tools.length, 17);
  } finally {
    child.kill();
  }
});
