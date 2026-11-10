// The shared MCP dispatcher under mcp/vendor/mcp-core/ is a copy of
// doha-guidelines-nexus/mcp/core/. It is replaced only by
// `node mcp/vendor/import-mcp-core.mjs`, never edited here.
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFileSync, readdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { test } from 'node:test';
import { fileURLToPath } from 'node:url';

const DIR = join(dirname(fileURLToPath(import.meta.url)), '..', '..', 'mcp', 'vendor', 'mcp-core');
// CRLF is read as LF, so a Windows checkout and Linux CI compute the same hash.
const sha = (path) => createHash('sha256').update(readFileSync(path, 'utf8').replace(/\r\n/g, '\n')).digest('hex');

test('MCP core: every vendored file matches mcp-core.json and comes from a committed build', () => {
  const manifest = JSON.parse(readFileSync(join(DIR, 'mcp-core.json'), 'utf8'));
  assert.equal(manifest.bundle, 'mcp-core');
  assert.equal(manifest.dirty, false, 'imported from uncommitted changes');
  assert.match(manifest.commit, /^[0-9a-f]{7,40}$/);
  assert.ok(Object.keys(manifest.files).includes('dispatcher.js'));
  for (const [name, hash] of Object.entries(manifest.files)) assert.equal(sha(join(DIR, name)), hash, `${name} differs from the import: re-import it, do not edit it`);
  assert.deepEqual(readdirSync(DIR).sort(), [...Object.keys(manifest.files), 'mcp-core.json'].sort(), 'no file outside the manifest');
});

test('MCP core: the vendored dispatcher logs nothing and fetches nothing (design §4)', () => {
  for (const name of readdirSync(DIR).filter((n) => n.endsWith('.js'))) {
    const code = readFileSync(join(DIR, name), 'utf8');
    assert.ok(!/\bconsole\b/.test(code), `${name} mentions console`);
    assert.ok(!/\bfetch\(/.test(code), `${name} calls fetch`);
  }
});
