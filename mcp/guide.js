// The human-readable connection guide served on GET /adverse/mcp with
// Accept: text/html (design §5.1). Built once per isolate from the verified
// release so the disclaimer is DISCLAIMER.md verbatim, not a copy.

import { ENDPOINT, MODE_1B, STANDING_RULES } from './server.js';

const escapeHtml = (s) =>
  String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);

export function renderGuide(release, mcpServer) {
  const m = release.manifest;
  const disclaimer = release.has('DISCLAIMER.md') ? release.text('DISCLAIMER.md') : 'DISCLAIMER.md failed verification and is not shown.';
  const tools = mcpServer.tools.map((t) => `<li><code>${escapeHtml(t.name)}</code> — ${escapeHtml(t.description)}</li>`).join('\n      ');
  const prompts = mcpServer.prompts.map((p) => `<code>${escapeHtml(p.name)}</code>`).join(', ');
  const counts = m.counts ?? {};
  const cfr = m.cfr_117?.available ? 'available' : 'unavailable in this release (the library carries 32 CFR Part 117 unsplit)';
  return `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Adverse Information Assistant MCP Server — FSOtools</title>
  <style>
    :root { --bg: #f6f1e3; --sheet: #fffdf5; --ink: #0f1b2d; --muted: #4b5563; --blue: #1648b8; --accent: #d95d1e; }
    body { margin: 0; font-family: system-ui, -apple-system, sans-serif; background: var(--bg); color: var(--ink); line-height: 1.55; }
    header { background: var(--blue); color: #fff; padding: 18px 24px; border-bottom: 3px solid var(--ink); }
    header a { color: #fff; text-decoration: underline; font-size: 0.9rem; }
    main { max-width: 880px; margin: 28px auto; background: var(--sheet); border: 2px solid var(--ink); padding: 28px 32px; box-shadow: 4px 4px 0 var(--ink); }
    h1 { margin: 0 0 6px; font-size: 1.65rem; }
    h2 { margin-top: 28px; border-bottom: 2px solid var(--ink); padding-bottom: 4px; font-size: 1.2rem; }
    pre { background: #0f1b2d; color: #f8fafc; padding: 14px 16px; overflow-x: auto; border: 1px solid var(--ink); font-size: 0.88rem; white-space: pre-wrap; }
    pre.disclaimer { background: #fff7ed; color: var(--ink); border-left: 4px solid var(--accent); }
    code { font-family: ui-monospace, SFMono-Regular, Consolas, monospace; }
    .endpoint { background: #eef2ff; border: 2px solid var(--ink); padding: 10px 14px; font-weight: 600; display: inline-block; margin: 8px 0; }
    ul { padding-left: 20px; } li { margin-bottom: 6px; }
    .note { border-left: 4px solid var(--accent); padding: 8px 14px; background: #fff7ed; margin: 16px 0; font-size: 0.93rem; }
    table { border-collapse: collapse; width: 100%; font-size: 0.93rem; } td, th { border: 1px solid var(--ink); padding: 6px 8px; text-align: left; vertical-align: top; }
  </style>
</head>
<body>
  <header>
    <div><strong>FSO TOOLS</strong> · Adverse Information Assistant Model Context Protocol (MCP) Server</div>
    <div><a href="https://fsotools.ai/mcp/">← All fsotools.ai connectors</a> · <a href="https://github.com/adamsdarin/adverse-information-assistant">The tool (GitHub)</a></div>
  </header>
  <main>
    <h1>adverse-information-assistant</h1>
    <p>A <strong>read-only reference endpoint</strong> for the Adverse Information Assistant, the local tool that helps a clearance holder prepare a complete, candid adverse-information self-report. Your own AI assistant runs the session; this server only answers reference questions by category — a guideline letter, an access tier, an event type, a decision id. It accepts no narrative, keeps no session, writes no logs and predicts nothing.</p>

    <div class="note">
      <strong>${escapeHtml(MODE_1B.name)}.</strong> ${escapeHtml(MODE_1B.disclosure)}<br><br>
      What leaves your machine: ${escapeHtml(MODE_1B.what_leaves_the_machine.join(' · '))}<br>
      The server keeps: ${escapeHtml(MODE_1B.server_keeps)}
    </div>

    <h2>Connect</h2>
    <p>Streamable HTTP MCP clients point at:</p>
    <div class="endpoint"><code>${escapeHtml(ENDPOINT)}</code></div>
    <p><strong>Claude.ai / Claude Desktop:</strong> Settings → Connectors → Add custom connector → name it <em>Adverse Information Assistant</em> and paste the address above. No authentication is needed.</p>
    <p><strong>Claude Code:</strong></p>
    <pre><code>claude mcp add --transport http adverse-information-assistant ${escapeHtml(ENDPOINT)}</code></pre>
    <p><strong>stdio-only clients</strong> (bridge with <code>mcp-remote</code> in <code>claude_desktop_config.json</code> or <code>.cursor/mcp.json</code>):</p>
    <pre><code>{
  "mcpServers": {
    "adverse-information-assistant": {
      "command": "npx",
      "args": ["-y", "mcp-remote", "${escapeHtml(ENDPOINT)}"]
    }
  }
}</code></pre>

    <h2>What it serves</h2>
    <table>
      <tr><th>Release</th><td>Library <code>${escapeHtml(m.library_release)}</code> (approved ${escapeHtml(m.library_approval?.approved_utc ?? '')} by ${escapeHtml(m.library_approval?.approved_by ?? '')}) · corpus <code>${escapeHtml(m.corpus_version)}</code> · commit <code>${escapeHtml(m.repo_commit)}</code> · built ${escapeHtml(m.built_utc)}</td></tr>
      <tr><th>Government text</th><td>${escapeHtml(String(counts.government_files ?? ''))} files: SEAD 4 (one file per guideline plus the adjudicative-process appendix), SEAD 3 (by access tier), ISL 2021-02 (by table). 32 CFR § 117.8: ${escapeHtml(cfr)}. Copied byte-for-byte from the approved DCSA Library release and hash-checked on every load.</td></tr>
      <tr><th>Maintainer-authored files</th><td>${escapeHtml(String(counts.maintainer_files ?? ''))} files (${escapeHtml(String(counts.maintainer_verified ?? 0))} verified, ${escapeHtml(String(counts.maintainer_unverified ?? 0))} unverified). Each is served with its <code>maintainer_verified</code> flag exactly as the repository carries it; an unverified file cannot ground a "yes".</td></tr>
      <tr><th>Decision text</th><td>The Adjudication Atlas's D1 shards of published DOHA decisions, read by decision id and guideline letter only. No full-text search exists on this endpoint; use <a href="https://fsotools.ai/atlas/mcp">/atlas/mcp</a> knowingly if you want it.</td></tr>
      <tr><th>Rate limit</th><td>60 requests per minute per connecting IP, shared across all tools.</td></tr>
    </table>

    <h2>Tools (${mcpServer.tools.length})</h2>
    <ul>
      ${tools}
    </ul>

    <h2>Prompts (${mcpServer.prompts.length})</h2>
    <p>The tool's agent prompts, verbatim from the release, each with a short hosted-mode preamble: ${prompts}. A client runs them; the server never does.</p>

    <h2>Resources (${mcpServer.resources.length})</h2>
    <p><code>adverse://release</code>, <code>adverse://corpus/&lt;file&gt;</code> for the standalone maintainer files, and <code>adverse://government/&lt;directive&gt;/&lt;section&gt;</code> for every directive section.</p>

    <h2>Standing rules</h2>
    <ul>
      ${STANDING_RULES.map((r) => `<li>${escapeHtml(r)}</li>`).join('\n      ')}
    </ul>

    <h2>Disclaimer (DISCLAIMER.md, verbatim)</h2>
    <pre class="disclaimer">${escapeHtml(disclaimer)}</pre>
  </main>
</body>
</html>`;
}
