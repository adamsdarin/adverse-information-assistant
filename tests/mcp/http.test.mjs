// Transport and Worker posture: no-store on every response, no session id,
// rate limit shape, guide page with the disclaimer verbatim, fail-closed load.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { join } from 'node:path';

import { handleMcpHttpRequest, MAX_BODY_BYTES } from '../../mcp/http.js';
import worker, { resetWorkerCache } from '../../mcp/worker.js';
import { renderGuide } from '../../mcp/guide.js';
import { fixtureReleaseDir, fixtureServer, makeShardEnv, ROOT } from './helpers.mjs';

const URL_ = 'https://fsotools.ai/adverse/mcp';
const post = (body, headers = {}) =>
  new Request(URL_, { method: 'POST', headers: { 'content-type': 'application/json', ...headers }, body: typeof body === 'string' ? body : JSON.stringify(body) });

test('every transport response is no-store and never carries a session id', async () => {
  const { server } = await fixtureServer();
  const listed = await handleMcpHttpRequest(post({ jsonrpc: '2.0', id: 1, method: 'tools/list' }, { 'mcp-session-id': 'client-sent-this' }), server);
  assert.equal(listed.status, 200);
  assert.equal(listed.headers.get('cache-control'), 'no-store');
  assert.equal(listed.headers.get('mcp-session-id'), null);
  assert.equal(listed.headers.get('set-cookie'), null);
  const tools = (await listed.json()).result.tools;
  assert.equal(tools.length, 17);
  // Every tool declares itself read-only, non-destructive and idempotent (closed world).
  for (const t of tools) assert.deepEqual(t.annotations, { readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: false }, `${t.name}: annotations`);

  const info = await handleMcpHttpRequest(new Request(URL_, { method: 'GET', headers: { accept: 'application/json' } }), server);
  assert.equal(info.headers.get('cache-control'), 'no-store');
  assert.equal((await info.json()).stateless, true);

  // MCP Streamable HTTP: no server-initiated event stream is offered, so a GET
  // asking for one is 405, never a 200 JSON body a client would try to parse.
  const stream = await handleMcpHttpRequest(new Request(URL_, { method: 'GET', headers: { accept: 'text/event-stream' } }), server);
  assert.equal(stream.status, 405);
  assert.equal(stream.headers.get('cache-control'), 'no-store');

  const declaredTooBig = await handleMcpHttpRequest(
    new Request(URL_, { method: 'POST', headers: { 'content-type': 'application/json', 'content-length': String(MAX_BODY_BYTES + 1) }, body: '{}' }),
    server,
  );
  assert.equal(declaredTooBig.status, 413);
  const actuallyTooBig = await handleMcpHttpRequest(post('x'.repeat(MAX_BODY_BYTES + 1)), server);
  assert.equal(actuallyTooBig.status, 413);

  const options = await handleMcpHttpRequest(new Request(URL_, { method: 'OPTIONS' }), server);
  assert.equal(options.status, 204);
  assert.equal(options.headers.get('cache-control'), 'no-store');

  const notification = await handleMcpHttpRequest(post({ jsonrpc: '2.0', method: 'notifications/initialized' }), server);
  assert.equal(notification.status, 202);

  const bad = await handleMcpHttpRequest(post('{not json'), server);
  assert.equal(bad.status, 400);
  assert.equal((await bad.json()).error.code, -32700);

  const put = await handleMcpHttpRequest(new Request(URL_, { method: 'PUT' }), server);
  assert.equal(put.status, 405);

  const tool = await handleMcpHttpRequest(post({ jsonrpc: '2.0', id: 2, method: 'tools/call', params: { name: 'get_corpus_file', arguments: { file: 'coverage' } } }), server);
  assert.equal(tool.headers.get('cache-control'), 'no-store');
  assert.equal((await tool.json()).result.isError, false);
});

function fakeAssets(dir) {
  return {
    async fetch(url) {
      const path = decodeURI(new URL(url).pathname.slice(1));
      try {
        return new Response(await readFile(join(dir, path)));
      } catch {
        return new Response('not found', { status: 404 });
      }
    },
  };
}

function fakeLimiter(results) {
  return { async limit() { return { success: results.shift() ?? true }; } };
}

test('the Worker serves the guide on GET text/html with DISCLAIMER.md verbatim, and MCP on POST', async () => {
  resetWorkerCache();
  const env = { ASSETS: fakeAssets(fixtureReleaseDir()), MCP_LIMIT: fakeLimiter([true, true, false]), ...makeShardEnv(), RELEASE_ID: 'synthetic-test-release' };
  const sse = await worker.fetch(new Request(URL_, { headers: { accept: 'text/event-stream' } }), env);
  assert.equal(sse.status, 405, 'an SDK client opening the event stream after initialize gets 405, not the guide');
  const guide = await worker.fetch(new Request(URL_, { headers: { accept: 'text/html,application/xhtml+xml' } }), env);
  assert.equal(guide.status, 200);
  assert.match(guide.headers.get('content-type'), /text\/html/);
  const html = await guide.text();
  const disclaimer = await readFile(join(ROOT, 'DISCLAIMER.md'), 'utf-8');
  const escaped = disclaimer.replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
  assert.ok(html.includes(escaped), 'DISCLAIMER.md appears verbatim (HTML-escaped) in the guide');
  assert.ok(html.includes('claude mcp add --transport http adverse-information-assistant https://fsotools.ai/adverse/mcp'));
  assert.ok(html.includes('mcp-remote'));
  assert.ok(html.includes('Mode 1b'));
  assert.ok(html.includes('<code>get_release</code>') && html.includes('<code>get_decision_text</code>'));
  assert.ok(!html.includes('<script'), 'no scripts, no analytics on the guide page');

  const first = await worker.fetch(post({ jsonrpc: '2.0', id: 1, method: 'tools/call', params: { name: 'get_release', arguments: {} } }, { 'cf-connecting-ip': '203.0.113.9' }), env);
  assert.equal(first.status, 200);
  assert.equal(first.headers.get('cache-control'), 'no-store');
  const body = await first.json();
  assert.equal(body.result.structuredContent.release.library_release, 'synthetic-test-release');
  assert.equal(body.result.structuredContent.decisions.counts.total, 6);
  assert.equal(body.result.structuredContent.worker_vars.consistent_with_manifest, true);

  const second = await worker.fetch(post({ jsonrpc: '2.0', id: 2, method: 'ping' }), env);
  assert.equal(second.status, 200);
  const limited = await worker.fetch(post({ jsonrpc: '2.0', id: 3, method: 'ping' }), env);
  assert.equal(limited.status, 429);
  assert.equal(limited.headers.get('retry-after'), '60');
  assert.equal(limited.headers.get('cache-control'), 'no-store');
  assert.equal((await limited.json()).error.code, -32000);
});

test('the Worker serves nothing when the release cannot be loaded', async () => {
  resetWorkerCache();
  const env = { ASSETS: { async fetch() { return new Response('nope', { status: 404 }); } } };
  const res = await worker.fetch(post({ jsonrpc: '2.0', id: 1, method: 'tools/list' }), env);
  assert.equal(res.status, 503);
  assert.equal(res.headers.get('cache-control'), 'no-store');
  resetWorkerCache();
});

test('the guide names every tool and prompt the server exposes', async () => {
  const { server, release } = await fixtureServer();
  const html = renderGuide(release, server);
  for (const t of server.tools) assert.ok(html.includes(`<code>${t.name}</code>`), t.name);
  for (const p of server.prompts) assert.ok(html.includes(`<code>${p.name}</code>`), p.name);
  assert.ok(html.includes(release.manifest.library_release));
});
