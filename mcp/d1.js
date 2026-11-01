// Every D1 statement the hosted server can run, in one place, so review is a
// diff (design §4). All of them are SELECTs over the Adjudication Atlas's three
// decision-text shards; the Worker holds no writable binding. Inputs reach a
// statement only as bound parameters, and only after server.js has validated
// them against a closed enum or pattern.
//
// Shard schema (doha-decision-search/scripts/build_index.py):
//   decisions(decision_id, document_id, case_id, decision_level,
//             decision_family, outcome, guideline_codes, case_year,
//             decision_date, era, source_url, content_sha256, pages,
//             damaged_chars, first_rowid, parts)
//   passages  FTS5(body, decision_id, part, first_page, last_page, …)
//             rowid = decisions.first_rowid + part - 1
//   meta(key, value)   release_id, metadata_release_id, decisions, passages

export const SHARDS = ['S1', 'S2', 'S3'];
export const MAX_TEXT_PARTS = 10;
export const POST_SEAD4 = 'POST_SEAD_4';
export const PRE_SEAD4 = 'PRE_SEAD_4';
const PARSED_OUTCOMES = ['approved', 'denied', 'remanded'];

const DECISION_COLUMNS =
  'decision_id, document_id, case_id, decision_level, decision_family, outcome, guideline_codes, era, decision_date, source_url, pages, parts';

export const STATEMENTS = {
  meta: 'SELECT key, value FROM meta',
  counts: `SELECT count(*) AS total, sum(CASE WHEN outcome IN (${PARSED_OUTCOMES.map((o) => `'${o}'`).join(', ')}) THEN 1 ELSE 0 END) AS parsed FROM decisions`,
  caseIds: 'SELECT DISTINCT case_id FROM decisions',
  /** n guideline LIKE patterns; postOnly adds the era filter. */
  byGuidelines: (n, postOnly) =>
    `SELECT ${DECISION_COLUMNS} FROM decisions WHERE (` +
    Array.from({ length: n }, (_, i) => `(',' || guideline_codes || ',') LIKE ?${i + 1}`).join(' OR ') +
    `)${postOnly ? ` AND era = '${POST_SEAD4}'` : ''}`,
  byCase: `SELECT ${DECISION_COLUMNS} FROM decisions WHERE case_id = ?1`,
  byDecision: `SELECT ${DECISION_COLUMNS}, first_rowid FROM decisions WHERE decision_id = ?1`,
  passages: 'SELECT rowid AS rid, part, first_page, last_page, body FROM passages WHERE rowid BETWEEN ?1 AND ?2 ORDER BY rowid',
};

export function hasShards(env) {
  return SHARDS.every((name) => env && env[name] && typeof env[name].prepare === 'function');
}

async function all(db, sql, binds = []) {
  const stmt = db.prepare(sql);
  const bound = binds.length ? stmt.bind(...binds) : stmt;
  const res = await bound.all();
  return res?.results ?? [];
}

async function eachShard(env, fn) {
  return Promise.all(SHARDS.map((name, i) => fn(env[name], name, i)));
}

export function splitCodes(codes) {
  return String(codes ?? '')
    .split(',')
    .map((c) => c.trim().toUpperCase())
    .filter((c) => /^[A-M]$/.test(c));
}

const LEVELS = { h: 'hearing', a: 'appeal' };

export function describeDecision(row) {
  const level = row.decision_level ?? (row.decision_id?.split('.')[1] ?? '');
  return {
    decision_id: row.decision_id,
    case_no: row.case_id,
    level: row.decision_family ?? LEVELS[String(level)[0]] ?? 'unknown',
    decision_level: row.decision_level ?? null,
    outcome: row.outcome ?? null,
    guidelines: splitCodes(row.guideline_codes),
    era: row.era ?? null,
    decision_date: row.decision_date ?? null,
    source_url: row.source_url ?? null,
    pages: row.pages ?? null,
    parts: row.parts ?? null,
  };
}

/** Each shard's meta table: release ids and row counts. */
export async function shardMeta(env) {
  return eachShard(env, async (db, name) => {
    const meta = Object.fromEntries((await all(db, STATEMENTS.meta)).map((r) => [r.key, r.value]));
    return {
      binding: name,
      release_id: meta.release_id ?? null,
      metadata_release_id: meta.metadata_release_id ?? null,
      decisions: meta.decisions ? Number(meta.decisions) : null,
      passages: meta.passages ? Number(meta.passages) : null,
      built_utc: meta.built_utc ?? null,
    };
  });
}

/**
 * The three counts doha_retrieval.py documents: total >= parsed >= unique.
 * Computed from the shards, never hardcoded.
 */
export async function shardCounts(env) {
  const perShard = await eachShard(env, async (db) => {
    const [c] = await all(db, STATEMENTS.counts);
    const ids = await all(db, STATEMENTS.caseIds);
    return { total: Number(c?.total ?? 0), parsed: Number(c?.parsed ?? 0), ids: ids.map((r) => r.case_id) };
  });
  const unique = new Set();
  for (const s of perShard) for (const id of s.ids) if (id) unique.add(id);
  return {
    total: perShard.reduce((n, s) => n + s.total, 0),
    parsed: perShard.reduce((n, s) => n + s.parsed, 0),
    unique_cases: unique.size,
    invariant:
      'total >= parsed >= unique_cases; the three legitimately differ (unparseable stems are dropped, a case can carry several decisions)',
  };
}

/**
 * Port of doha_retrieval.select(): rank by guideline overlap, post-SEAD 4
 * first, tight matches first, then alternate denied/approved so no caller
 * taking the top N gets a one-sided sample. Exclusions are the document ids
 * the library marks answer_eligible: false.
 */
export async function findDecisions(env, guidelines, { limit = 6, includePreSead4 = false, excluded = new Set() } = {}) {
  const want = [...new Set(guidelines.map((g) => g.toUpperCase()))];
  const binds = want.map((g) => `%,${g},%`);
  const sql = STATEMENTS.byGuidelines(want.length, !includePreSead4);
  const rows = (await eachShard(env, (db) => all(db, sql, binds))).flat();

  const wantSet = new Set(want);
  const scored = [];
  for (const r of rows) {
    const codes = splitCodes(r.guideline_codes);
    if (!PARSED_OUTCOMES.includes(r.outcome)) continue;
    if (excluded.has(r.document_id) && !(includePreSead4 && r.era === PRE_SEAD4)) continue;
    const overlap = codes.filter((c) => wantSet.has(c)).length;
    if (!overlap) continue;
    if (r.era !== POST_SEAD4 && !includePreSead4) continue;
    const score = overlap * 10 + (r.era === POST_SEAD4 ? 5 : 0) - Math.abs(codes.length - want.length);
    scored.push({ score, row: r });
  }
  scored.sort((a, b) => b.score - a.score || String(a.row.case_id).localeCompare(String(b.row.case_id)));

  const denied = scored.filter((s) => s.row.outcome === 'denied').map((s) => s.row);
  const approved = scored.filter((s) => s.row.outcome === 'approved').map((s) => s.row);
  const other = scored.filter((s) => !['denied', 'approved'].includes(s.row.outcome)).map((s) => s.row);
  const out = [];
  while (out.length < limit && (denied.length || approved.length)) {
    if (denied.length) out.push(denied.shift());
    if (out.length < limit && approved.length) out.push(approved.shift());
  }
  if (out.length < limit) out.push(...other.slice(0, limit - out.length));
  return {
    candidates: scored.length,
    cases: out.slice(0, limit).map(describeDecision),
  };
}

/** Every decision filed under a case number, across the shards. */
export async function verifyCase(env, caseNumber) {
  const rows = (await eachShard(env, (db) => all(db, STATEMENTS.byCase, [caseNumber]))).flat();
  rows.sort((a, b) => String(a.decision_id).localeCompare(String(b.decision_id)));
  return rows.map(describeDecision);
}

/**
 * Passages for one decision, by part range (1-based, inclusive), capped at
 * MAX_TEXT_PARTS. Looked up by rowid range, which FTS5 serves without a scan.
 */
export async function decisionText(env, decisionId, partFrom, partTo) {
  const located = await eachShard(env, async (db, name) => {
    const rows = await all(db, STATEMENTS.byDecision, [decisionId]);
    return rows.length ? { db, name, row: rows[0] } : null;
  });
  const hit = located.find(Boolean);
  if (!hit) return null;
  const parts = Number(hit.row.parts ?? 0);
  const from = Math.max(1, partFrom);
  const to = Math.min(parts, partTo, from + MAX_TEXT_PARTS - 1);
  let passages = [];
  if (parts > 0 && from <= to) {
    const first = Number(hit.row.first_rowid) + from - 1;
    const last = Number(hit.row.first_rowid) + to - 1;
    passages = (await all(hit.db, STATEMENTS.passages, [first, last])).filter((p) => p.part >= from && p.part <= to);
  }
  return {
    decision: describeDecision(hit.row),
    shard: hit.name,
    parts_total: parts,
    part_from: from,
    part_to: parts > 0 ? to : 0,
    passages: passages.map((p) => ({
      part: p.part,
      first_page: p.first_page,
      last_page: p.last_page,
      text: String(p.body ?? ''),
    })),
  };
}
