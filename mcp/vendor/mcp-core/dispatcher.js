// The JSON-RPC 2.0 / MCP dispatcher shared by the three fsotools.ai MCP servers
// (doha-atlas-mcp here, clearance-question-mcp and adverse-information-assistant,
// which vendor this file under mcp/vendor/mcp-core/ with a hash check).
//
// This copy is the canonical one. After changing it: `npm run mcp-core-bundle`
// here, then `node mcp/vendor/import-mcp-core.mjs` in each of the other repos.
//
// What lives here is only what the three servers did identically: the envelope
// check, notifications, batches and their caps, protocol-version negotiation,
// ping, tools/list, resources/list, the resources/read envelope, routing, and
// the rule that an unexpected failure is answered with a fixed message. Tools,
// resources, wording and logging belong to each server and arrive as options.
//
// Plain ES module: no dependencies, no platform APIs, and no logging of its own
// (one server forbids any logging in its Worker; the others pass a logger).

const isPlainObject = (v) => v !== null && typeof v === 'object' && !Array.isArray(v);

/** Throw from a hook to answer with a JSON-RPC error instead of a result. */
export class RpcError extends Error {
  constructor(code, message) {
    super(message);
    this.name = 'RpcError';
    this.code = code;
  }
}

/** A successful tools/call result: the output as pretty JSON text and as structuredContent. */
export function toolResult(output) {
  return { content: [{ type: 'text', text: JSON.stringify(output, null, 2) }], structuredContent: output, isError: false };
}

/** A failed tools/call result: the payload as compact JSON text; `structured` also returns it as structuredContent. */
export function toolErrorResult(payload, { structured = false } = {}) {
  const content = [{ type: 'text', text: JSON.stringify(payload) }];
  return structured ? { content, structuredContent: payload, isError: true } : { content, isError: true };
}

/**
 * Build a dispatcher. Options:
 *   protocolVersions   supported MCP versions; the first answers an unsupported request
 *   serverInfo, capabilities, instructions   returned by initialize, as given
 *   tools, resources   the arrays returned by tools/list and resources/list
 *   callTool(name, args)   -> the tools/call result (see toolResult / toolErrorResult);
 *                          receives params.name and params.arguments unchecked
 *   readResource(uri)  -> { mimeType, text }, or a falsy value when there is no such resource
 *   methods            further methods, { 'prompts/list': (params) => result }
 *   maxBatch, maxBatchToolCalls   batch caps
 *   messages           this server's wording: invalidRequest, batchToolCalls,
 *                      resourceUriRequired, internalError (strings);
 *                      resourceNotFound(uri), methodNotFound(method) (functions)
 *   onInternalError(method, err)   optional; called before an unexpected failure is
 *                      answered with messages.internalError. Omit it to log nothing.
 * Any hook may throw an RpcError to answer with that code and message; anything
 * else a hook throws is an unexpected failure, and its message is never returned.
 */
export function createDispatcher({
  protocolVersions,
  serverInfo,
  capabilities,
  instructions,
  tools,
  resources,
  callTool,
  readResource,
  methods = {},
  maxBatch,
  maxBatchToolCalls,
  messages,
  onInternalError,
}) {
  const ok = (id, result) => ({ jsonrpc: '2.0', id, result });
  const fail = (id, code, message) => ({ jsonrpc: '2.0', id, error: { code, message } });

  async function handleRpcMessage(msg) {
    if (!isPlainObject(msg) || msg.jsonrpc !== '2.0') {
      return fail(isPlainObject(msg) ? msg.id ?? null : null, -32600, messages.invalidRequest);
    }
    if (msg.id === undefined) return null; // a notification is never answered
    const { id, method, params = {} } = msg;
    try {
      switch (method) {
        case 'initialize': {
          const requested = params?.protocolVersion;
          return ok(id, {
            protocolVersion: protocolVersions.includes(requested) ? requested : protocolVersions[0],
            capabilities,
            serverInfo,
            instructions,
          });
        }
        case 'ping':
          return ok(id, {});
        case 'tools/list':
          return ok(id, { tools });
        case 'tools/call':
          return ok(id, await callTool(params?.name, params?.arguments));
        case 'resources/list':
          return ok(id, { resources });
        case 'resources/read': {
          const uri = params?.uri;
          if (typeof uri !== 'string') return fail(id, -32602, messages.resourceUriRequired);
          const data = await readResource(uri);
          if (!data) return fail(id, -32002, messages.resourceNotFound(uri));
          return ok(id, { contents: [{ uri, mimeType: data.mimeType, text: data.text }] });
        }
        default:
          if (typeof method === 'string' && Object.hasOwn(methods, method)) return ok(id, await methods[method](params));
          return fail(id, -32601, messages.methodNotFound(method));
      }
    } catch (err) {
      if (err instanceof RpcError) return fail(id, err.code, err.message);
      if (onInternalError) onInternalError(method, err);
      return fail(id, -32603, messages.internalError);
    }
  }

  /** One message or a batch. Returns the response, an array of responses, or null when nothing is owed. */
  async function handleMessage(payload) {
    if (!Array.isArray(payload)) return handleRpcMessage(payload);
    if (payload.length === 0) return fail(null, -32600, 'Invalid Request: empty batch.');
    if (payload.length > maxBatch) return fail(null, -32600, `Invalid Request: batch exceeds ${maxBatch} messages.`);
    const toolCalls = payload.filter((item) => isPlainObject(item) && item.method === 'tools/call').length;
    if (toolCalls > maxBatchToolCalls) return fail(null, -32600, messages.batchToolCalls);
    const responses = (await Promise.all(payload.map((item) => handleRpcMessage(item)))).filter(Boolean);
    return responses.length > 0 ? responses : null;
  }

  return { handleMessage, handleRpcMessage };
}
