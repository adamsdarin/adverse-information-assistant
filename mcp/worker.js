// Cloudflare Worker `adverse-information-assistant`: the hosted, stateless MCP
// reference server at https://fsotools.ai/adverse/mcp.
//
// - Loads the release from the static-assets binding (env.ASSETS) once per
//   isolate and verifies every file's SHA-256 against manifest.json; a file
//   that fails is never served (release.js).
// - Binds the Adjudication Atlas's D1 shards (env.S1..S3) read-only for the
//   three decision tools (d1.js); everything else is served from the release.
// - GET with Accept: text/html → the connection guide; POST → MCP Streamable
//   HTTP (http.js), rate-limited through env.MCP_LIMIT.
// - No logging anywhere on the request path; observability is off in
//   wrangler.jsonc. The Worker makes no outbound request except env.ASSETS.

import { assetsFetcher, loadRelease } from './release.js';
import { handleMcpHttpRequest } from './http.js';
import { createAdverseMcpServer } from './server.js';
import { renderGuide } from './guide.js';

let cachedPromise = null;

async function init(env) {
  const release = await loadRelease(assetsFetcher(env.ASSETS));
  const server = createAdverseMcpServer(release, {
    env,
    vars: { RELEASE_ID: env.RELEASE_ID, CORPUS_VERSION: env.CORPUS_VERSION, REPO_COMMIT: env.REPO_COMMIT },
  });
  const guide = renderGuide(release, server);
  return { release, server, guide };
}

export function getOrInitWorker(env) {
  if (!cachedPromise) {
    cachedPromise = init(env).catch((err) => {
      cachedPromise = null;
      throw err;
    });
  }
  return cachedPromise;
}

/** Reset the isolate cache (unit tests). */
export function resetWorkerCache() {
  cachedPromise = null;
}

const RATE_LIMITED = JSON.stringify({
  jsonrpc: '2.0',
  id: null,
  error: { code: -32000, message: 'Rate limit exceeded (60 requests/minute). Please wait and retry.' },
});

export default {
  async fetch(request, env) {
    if (request.method === 'POST' && env.MCP_LIMIT) {
      const who = request.headers.get('cf-connecting-ip') ?? 'unknown';
      const { success } = await env.MCP_LIMIT.limit({ key: who });
      if (!success) {
        return new Response(RATE_LIMITED, {
          status: 429,
          headers: {
            'content-type': 'application/json; charset=utf-8',
            'retry-after': '60',
            'cache-control': 'no-store',
            'access-control-allow-origin': '*',
          },
        });
      }
    }

    let worker;
    try {
      worker = await getOrInitWorker(env);
    } catch {
      // The release failed to load or verify: serve nothing.
      return new Response(
        JSON.stringify({ jsonrpc: '2.0', id: null, error: { code: -32603, message: 'The reference release is unavailable; nothing is served until it verifies.' } }),
        { status: 503, headers: { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'no-store', 'retry-after': '300' } },
      );
    }

    if (request.method === 'GET') {
      const accept = request.headers.get('accept') ?? '';
      if (accept.includes('text/html') && !accept.includes('text/event-stream')) {
        return new Response(worker.guide, {
          status: 200,
          headers: {
            'content-type': 'text/html; charset=utf-8',
            'x-content-type-options': 'nosniff',
            'cache-control': 'public, max-age=3600',
          },
        });
      }
    }

    return handleMcpHttpRequest(request, worker.server);
  },
};
