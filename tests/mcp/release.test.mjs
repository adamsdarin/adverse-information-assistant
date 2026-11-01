// The manifest check: every served file is verified against manifest.json
// once per load, and a file that fails is never served (design §1.4).
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { appendFileSync, rmSync } from 'node:fs';
import { join } from 'node:path';

import { directoryFetcher, loadRelease, ReleaseIntegrityError } from '../../mcp/release.js';
import { createAdverseMcpServer } from '../../mcp/server.js';
import { callTool, fixtureRelease, rpc, tamperableCopy } from './helpers.mjs';

test('a clean fixture release verifies completely', async () => {
  const release = await fixtureRelease();
  assert.equal(release.integrity.ok, true);
  assert.equal(release.failed.length, 0);
  assert.equal(release.manifest.library_release, 'synthetic-test-release');
  assert.equal(release.manifest.library_approval.approved_by, 'synthetic-fixture');
  assert.equal(release.manifest.cfr_117.available, false, 'the mini-library has no Part 117 split');
  assert.match(release.manifest.cfr_117.reason, /unsplit/);
  assert.equal(release.manifest.doha_exclusions.count, 1);
  assert.ok(release.manifest.counts.maintainer_files >= 40);
  assert.equal(release.manifest.counts.maintainer_verified, 0, 'the build never flips a verified flag');
  assert.ok(release.manifestSha256?.length === 64);
  for (const [path, meta] of Object.entries(release.manifest.files)) {
    assert.match(meta.sha256, /^[0-9a-f]{64}$/, path);
    if (meta.source.startsWith('library:')) assert.equal(meta.verified, true, path);
    if (meta.source.startsWith('repo:corpus/')) assert.equal(meta.verified, false, path);
  }
});

test('a tampered or missing file is reported and never served', async () => {
  const dir = tamperableCopy();
  appendFileSync(join(dir, 'corpus', 'privacy-tiers.json'), '\n{"tampered": true}\n');
  rmSync(join(dir, 'government', 'sead-3', '02_All_Covered_Individuals.md'));
  const release = await loadRelease(await directoryFetcher(dir));

  assert.equal(release.integrity.ok, false);
  assert.deepEqual(
    release.failed.map((f) => f.path),
    ['corpus/privacy-tiers.json', 'government/sead-3/02_All_Covered_Individuals.md'],
  );
  assert.throws(() => release.text('corpus/privacy-tiers.json'), ReleaseIntegrityError);
  assert.throws(() => release.text('government/sead-3/02_All_Covered_Individuals.md'), (e) => e.reason === 'missing');
  assert.throws(() => release.text('not/in/manifest.json'), (e) => e.reason === 'not in the release manifest');

  const server = createAdverseMcpServer(release, { env: {} });
  const tampered = await callTool(server, 'get_corpus_file', { file: 'privacy-tiers' });
  assert.equal(tampered.isError, true);
  assert.equal(tampered.out.file, 'corpus/privacy-tiers.json');
  assert.ok(!JSON.stringify(tampered.out).includes('default_tier'), 'the error names the file, never its content');

  const missing = await callTool(server, 'get_reporting_requirements', { access: 'baseline' });
  assert.equal(missing.isError, true);
  assert.deepEqual(missing.out.missing_files, ['government/sead-3/02_All_Covered_Individuals.md']);
  assert.ok(!JSON.stringify(missing.out).includes('FIXTURE'), 'no section text leaks into a quote-nothing error');

  const status = await callTool(server, 'get_release', {});
  assert.equal(status.out.verification.integrity.ok, false);
  assert.equal(status.out.verification.integrity.failed.length, 2);

  const res = await rpc(server, 'resources/read', { uri: 'adverse://corpus/privacy-tiers' });
  assert.equal(res.error.code, -32002);
  assert.match(res.error.message, /failed verification/);

  // Untouched files still serve.
  const ok = await callTool(server, 'get_guideline_text', { guidelines: ['G'] });
  assert.equal(ok.isError, false);
});

test('a release without a manifest is refused outright', async () => {
  const dir = tamperableCopy();
  rmSync(join(dir, 'manifest.json'));
  await assert.rejects(loadRelease(await directoryFetcher(dir)), (e) => e instanceof ReleaseIntegrityError && e.reason === 'missing');
});

test('the directory fetcher never leaves the release folder', async () => {
  const fetchBytes = await directoryFetcher(tamperableCopy());
  assert.equal(await fetchBytes('../../package.json'), null);
  assert.equal(await fetchBytes('..\\manifest.json'), null);
});
