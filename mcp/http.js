// Streamable HTTP transport for the hosted reference server. Web-standard
// Request/Response, so it runs unchanged in the Cloudflare Worker and in Node.
//
// Every response is `cache-control: no-store` (design §4). The server issues no
// session id and never echoes one a client sends: there is no session.
//
// Local dev without wrangler (no decision shards; reference tools only):
//   node mcp/http.js [--release mcp/release] [--port 8789] [--host 127.0.0.1]

import { createAdverseMcpServer } from './server.js';
import { directoryFetcher, loadRelease } from './release.js';

export const CORS_HEADERS = {
  'access-control-allow-origin': '*',
  'access-control-allow-methods': 'GET, POST, OPTIONS',
  'access-control-allow-headers': 'content-type, accept, mcp-session-id, mcp-protocol-version',
  'x-content-type-options': 'nosniff',
  'cache-control': 'no-store',
};

export function jsonResponse(body, status = 200, extra = {}) {
  return new Response(body === null ? null : JSON.stringify(body), {
    status,
    headers: {
      ...(body !== null ? { 'content-type': 'application/json; charset=utf-8' } : {}),
      ...CORS_HEADERS,
      ...extra,
    },
  });
}

const rpcError = (code, message, status) => jsonResponse({ jsonrpc: '2.0', id: null, error: { code, message } }, status);
export const MAX_BODY_BYTES = 1_000_000;

/**
 * @param {Request} request
 * @param {ReturnType<typeof createAdverseMcpServer>} mcpServer
 */
export async function handleMcpHttpRequest(request, mcpServer) {
  if (request.method === 'OPTIONS') return new Response(null, { status: 204, headers: CORS_HEADERS });

  if (request.method === 'GET') {
    // MCP Streamable HTTP: a GET that asks for text/event-stream is a request
    // to open a server-initiated event stream. This server offers none, and
    // the spec's answer is 405, not a 200 body a client would try to parse.
    const accept = request.headers.get('accept') ?? '';
    if (accept.includes('text/event-stream')) {
      return rpcError(-32600, 'Method Not Allowed: this server does not open a server-sent event stream.', 405);
    }
    return jsonResponse({
      name: mcpServer.serverInfo.name,
      version: mcpServer.serverInfo.version,
      transport: 'streamable-http',
      stateless: true,
      tools: mcpServer.tools.map((t) => t.name),
      resources: mcpServer.resources.length,
      prompts: mcpServer.prompts.map((p) => p.name),
      guide: 'Request this address with Accept: text/html for the connection guide.',
    });
  }

  if (request.method !== 'POST') return rpcError(-32600, 'Method Not Allowed: use POST for JSON-RPC messages.', 405);

  // Reject an oversized body before reading it; the post-read check below is
  // the backstop for chunked requests that declare no length.
  const declared = Number(request.headers.get('content-length') ?? 0);
  if (Number.isFinite(declared) && declared > MAX_BODY_BYTES) return rpcError(-32600, 'Request body too large.', 413);
  let bodyText;
  try {
    bodyText = await request.text();
  } catch {
    return rpcError(-32700, 'Failed to read request body.', 400);
  }
  if (bodyText.length > MAX_BODY_BYTES) return rpcError(-32600, 'Request body too large.', 413);
  let payload;
  try {
    payload = JSON.parse(bodyText);
  } catch {
    return rpcError(-32700, 'Parse error: invalid JSON.', 400);
  }

  const response = await mcpServer.handleMessage(payload);
  if (response === null) return jsonResponse(null, 202);
  return jsonResponse(response, 200);
}

/** Node only. */
export async function startHttpMcpServer(mcpServer, { port = 8789, host = '127.0.0.1' } = {}) {
  const { createServer } = await import('node:http');
  const httpServer = createServer(async (req, res) => {
    const url = new URL(req.url ?? '/', `http://${req.headers.host ?? `${host}:${port}`}`);
    if (!['/mcp', '/adverse/mcp', '/'].includes(url.pathname)) {
      res.writeHead(404, { 'content-type': 'application/json; charset=utf-8', ...CORS_HEADERS });
      res.end(JSON.stringify({ error: 'Not found. Use /adverse/mcp.' }));
      return;
    }
    const chunks = [];
    for await (const chunk of req) chunks.push(chunk);
    const body = Buffer.concat(chunks);
    const webReq = new Request(url.toString(), {
      method: req.method,
      headers: req.headers,
      body: ['GET', 'HEAD', 'OPTIONS'].includes(req.method ?? 'GET') ? undefined : body,
    });
    const webRes = await handleMcpHttpRequest(webReq, mcpServer);
    res.writeHead(webRes.status, Object.fromEntries(webRes.headers.entries()));
    res.end(await webRes.text());
  });
  return new Promise((resolveServer) => httpServer.listen(port, host, () => resolveServer(httpServer)));
}

async function runningAsMain() {
  if (typeof process === 'undefined' || typeof import.meta.url !== 'string' || !process.argv?.[1]) return false;
  try {
    const { resolve } = await import('node:path');
    const { fileURLToPath } = await import('node:url');
    return resolve(process.argv[1]) === resolve(fileURLToPath(import.meta.url));
  } catch {
    return false;
  }
}

if (await runningAsMain()) {
  const args = process.argv.slice(2);
  const opt = (name, fallback) => {
    const i = args.indexOf(`--${name}`);
    return i >= 0 ? args[i + 1] : fallback;
  };
  const dir = opt('release', 'mcp/release');
  const release = await loadRelease(await directoryFetcher(dir));
  if (!release.integrity.ok) {
    process.stderr.write(`release integrity failures: ${JSON.stringify(release.integrity.failed)}\n`);
  }
  const mcpServer = createAdverseMcpServer(release, { env: {}, vars: {} });
  const srv = await startHttpMcpServer(mcpServer, { port: Number(opt('port', 8789)), host: opt('host', '127.0.0.1') });
  const addr = srv.address();
  process.stderr.write(
    `adverse-information-assistant MCP (reference tools only, no decision shards) at http://${addr.address}:${addr.port}/adverse/mcp — ` +
      `library ${release.manifest.library_release}, corpus ${release.manifest.corpus_version}\n`,
  );
}
