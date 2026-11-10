// Import the shared MCP dispatcher into mcp/vendor/mcp-core/.
//
//   node mcp/vendor/import-mcp-core.mjs                   from ../doha-guidelines-nexus/mcp-core-bundle
//   node mcp/vendor/import-mcp-core.mjs <bundle-dir>      from somewhere else
//   ... --allow-dirty                                     accept a bundle built from uncommitted changes (local trials only)
//
// The canonical copy is doha-guidelines-nexus/mcp/core/. Produce the bundle
// there first: `npm run mcp-core-bundle`. Never edit mcp/vendor/mcp-core/ by
// hand: the vendored-core test fails when a file no longer matches the
// SHA-256 in mcp-core.json.
//
// The import refuses a bundle whose files do not match its manifest, and
// (unless --allow-dirty) one built from uncommitted changes, so the vendored
// copy can always be traced to a commit. Hashes are of the content with CRLF
// read as LF, so a Windows checkout and Linux CI agree on them.

import { createHash } from 'node:crypto';
import { existsSync, mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));
const args = process.argv.slice(2);
const allowDirty = args.includes('--allow-dirty');
const from = resolve(args.find((a) => !a.startsWith('--')) ?? join(HERE, '..', '..', '..', 'doha-guidelines-nexus', 'mcp-core-bundle'));
const to = join(HERE, 'mcp-core');
const stop = (message) => {
  process.stderr.write(`${message}\n`);
  process.exit(1);
};

const meta = join(from, 'mcp-core.json');
if (!existsSync(meta)) stop(`No MCP core bundle at ${from}. In doha-guidelines-nexus run: npm run mcp-core-bundle`);
const manifest = JSON.parse(readFileSync(meta, 'utf8'));
const texts = {};
for (const [name, hash] of Object.entries(manifest.files)) {
  if (!/^[\w.-]+\.js$/.test(name)) stop(`Bundle names a file this import does not accept: ${name}`);
  const file = join(from, name);
  if (!existsSync(file)) stop(`Bundle is inconsistent: ${name} is missing.`);
  texts[name] = readFileSync(file, 'utf8').replace(/\r\n/g, '\n');
  const sha = createHash('sha256').update(texts[name]).digest('hex');
  if (sha !== hash) stop(`Bundle is inconsistent: ${name} sha256 ${sha}, mcp-core.json says ${hash}.`);
}
if (manifest.dirty && !allowDirty) {
  stop(`Bundle was built from uncommitted changes (commit ${manifest.commit}). Commit them and re-bundle, or pass --allow-dirty for a local trial.`);
}

rmSync(to, { recursive: true, force: true });
mkdirSync(to, { recursive: true });
for (const [name, text] of Object.entries(texts)) writeFileSync(join(to, name), text);
writeFileSync(join(to, 'mcp-core.json'), `${JSON.stringify(manifest, null, 2)}\n`);
process.stdout.write(`Imported MCP core ${manifest.commit}${manifest.dirty ? ' (dirty)' : ''} · ${Object.keys(texts).length} file(s) -> mcp/vendor/mcp-core/\n`);
