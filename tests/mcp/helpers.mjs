// Shared helpers for the hosted MCP server tests (node --test tests/mcp/).
//
// - fixtureRelease(): a release built from the synthetic mini-library. Uses
//   AIA_FIXTURE_RELEASE when tests/run_tests.py has already built one,
//   otherwise builds into a temporary folder once per process.
// - makeShardEnv(): three fake D1 bindings backed by node:sqlite with the real
//   shard schema and synthetic decisions (case numbers 90-0000N), so the SQL
//   in mcp/d1.js runs for real.
// - rpc(): one JSON-RPC call against a server.

import { spawnSync } from 'node:child_process';
import { mkdtempSync, cpSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { DatabaseSync } from 'node:sqlite';

import { directoryFetcher, loadRelease } from '../../mcp/release.js';
import { createAdverseMcpServer } from '../../mcp/server.js';

export const ROOT = resolve(fileURLToPath(new URL('../..', import.meta.url)));
const PYTHON = process.env.PYTHON ?? (process.platform === 'win32' ? 'python' : 'python3');

let fixtureDir = null;

/** Path of a built fixture release (built once per process if needed). */
export function fixtureReleaseDir() {
  if (fixtureDir) return fixtureDir;
  if (process.env.AIA_FIXTURE_RELEASE) {
    fixtureDir = process.env.AIA_FIXTURE_RELEASE;
    return fixtureDir;
  }
  const out = join(mkdtempSync(join(tmpdir(), 'aia-mcp-fixture-')), 'release');
  const r = spawnSync(PYTHON, [join(ROOT, 'tests', 'mcp', 'build_fixture_release.py'), out], { encoding: 'utf-8' });
  if (r.status !== 0) throw new Error(`fixture release build failed (${r.status}):\n${r.stdout}\n${r.stderr}`);
  fixtureDir = out;
  return fixtureDir;
}

/** A verified Release over the fixture build. */
export async function fixtureRelease(dir = fixtureReleaseDir()) {
  return loadRelease(await directoryFetcher(dir));
}

/** Copy the fixture release to a fresh temp folder the test may tamper with. */
export function tamperableCopy() {
  const dest = join(mkdtempSync(join(tmpdir(), 'aia-mcp-tamper-')), 'release');
  cpSync(fixtureReleaseDir(), dest, { recursive: true });
  return dest;
}

export async function fixtureServer({ env = {}, vars = {} } = {}) {
  const release = await fixtureRelease();
  return { release, server: createAdverseMcpServer(release, { env, vars }) };
}

export async function rpc(server, method, params = {}, id = 1) {
  return server.handleMessage({ jsonrpc: '2.0', id, method, params });
}

export async function callTool(server, name, args) {
  const res = await rpc(server, 'tools/call', { name, arguments: args });
  if (res.error) return { error: res.error };
  return { isError: res.result.isError, out: res.result.structuredContent };
}

// ---------------------------------------------------------------------------
// Fake D1 over node:sqlite, real shard schema (doha-decision-search build_index.py)
// ---------------------------------------------------------------------------
const SCHEMA = `
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT) WITHOUT ROWID;
CREATE TABLE decisions (
  decision_id TEXT PRIMARY KEY, document_id TEXT NOT NULL,
  case_id TEXT, decision_level TEXT, decision_family TEXT, outcome TEXT, guideline_codes TEXT,
  case_year INTEGER, decision_date TEXT, decision_date_basis TEXT, era TEXT, source_url TEXT,
  content_sha256 TEXT NOT NULL, content_bytes INTEGER, pages INTEGER, damaged_chars INTEGER,
  first_rowid INTEGER NOT NULL, parts INTEGER NOT NULL
) WITHOUT ROWID;
CREATE VIRTUAL TABLE passages USING fts5(
  body, decision_id UNINDEXED, part UNINDEXED, first_page UNINDEXED, last_page UNINDEXED,
  outcome UNINDEXED, guideline_codes UNINDEXED, case_year UNINDEXED, decision_family UNINDEXED
);`;

function wrapD1(db) {
  const run = (sql, binds) => ({ results: db.prepare(sql).all(...binds), meta: { rows_read: 0 } });
  return {
    prepare(sql) {
      const exec = (binds) => ({
        all: async () => run(sql, binds),
        first: async () => run(sql, binds).results[0] ?? null,
      });
      return { ...exec([]), bind: (...binds) => exec(binds) };
    },
    async batch(statements) {
      return Promise.all(statements.map((s) => s.all()));
    },
  };
}

/**
 * @param {object[]} decisions rows: {decision_id, document_id, case_id, level, family, outcome, codes, era, date, parts}
 */
export function makeShard(decisions, meta = {}) {
  const db = new DatabaseSync(':memory:');
  db.exec(SCHEMA);
  const insertMeta = db.prepare('INSERT INTO meta VALUES (?, ?)');
  const totalParts = decisions.reduce((n, d) => n + d.parts, 0);
  for (const [k, v] of Object.entries({ release_id: 'fixture-shards', metadata_release_id: 'fixture-meta', decisions: String(decisions.length), passages: String(totalParts), ...meta })) {
    insertMeta.run(k, String(v));
  }
  const insertDecision = db.prepare(
    'INSERT INTO decisions (decision_id, document_id, case_id, decision_level, decision_family, outcome, guideline_codes, case_year, decision_date, era, source_url, content_sha256, pages, damaged_chars, first_rowid, parts) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
  );
  const insertPassage = db.prepare(
    'INSERT INTO passages (rowid, body, decision_id, part, first_page, last_page, outcome, guideline_codes, case_year, decision_family) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
  );
  let rowid = 0;
  for (const d of decisions) {
    const first = rowid + 1;
    for (let k = 1; k <= d.parts; k++) {
      rowid += 1;
      insertPassage.run(rowid, `SYNTHETIC passage ${k} of ${d.decision_id}.`, d.decision_id, k, k, k, d.outcome, d.codes, 2023, d.family);
    }
    insertDecision.run(
      d.decision_id, d.document_id ?? `test-${d.decision_id}`, d.case_id, d.level, d.family, d.outcome, d.codes, 2023, d.date ?? '2023-01-10',
      d.era, `https://doha.ogc.osd.mil/synthetic/${d.decision_id}`, 'deadbeef', d.parts, 0, first, d.parts,
    );
  }
  return wrapD1(db);
}

export const SYNTHETIC_DECISIONS = {
  S1: [
    { decision_id: '90-00001.h1', case_id: '90-00001', level: 'h1', family: 'hearing', outcome: 'denied', codes: 'G,J', era: 'POST_SEAD_4', parts: 2 },
    { decision_id: '90-00002.h1', case_id: '90-00002', level: 'h1', family: 'hearing', outcome: 'approved', codes: 'G,J', era: 'POST_SEAD_4', parts: 1 },
  ],
  S2: [
    { decision_id: '90-00002.a1', case_id: '90-00002', level: 'a1', family: 'appeal', outcome: 'approved', codes: 'G,J', era: 'POST_SEAD_4', parts: 1 },
    { decision_id: '90-00003.h1', case_id: '90-00003', level: 'h1', family: 'hearing', outcome: 'denied', codes: 'G', era: 'PRE_SEAD_4', date: '2015-03-03', parts: 1 },
  ],
  S3: [
    { decision_id: '90-00004.h1', case_id: '90-00004', level: 'h1', family: 'hearing', outcome: 'approved', codes: 'J', era: 'POST_SEAD_4', parts: 12 },
    // document_id matches the answer_eligible:false row the fixture builder adds.
    { decision_id: '90-00009.h1', document_id: 'test-90-00009.h1_denied_g', case_id: '90-00009', level: 'h1', family: 'hearing', outcome: 'denied', codes: 'G', era: 'POST_SEAD_4', parts: 1 },
  ],
};

export function makeShardEnv() {
  return {
    S1: makeShard(SYNTHETIC_DECISIONS.S1),
    S2: makeShard(SYNTHETIC_DECISIONS.S2),
    S3: makeShard(SYNTHETIC_DECISIONS.S3),
  };
}
