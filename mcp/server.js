// Model Context Protocol server for the Adverse Information Assistant's hosted
// reference layer (`adverse-information-assistant`, fsotools.ai/adverse/mcp).
// Design: docs/HOSTED-MCP-DESIGN.md §§0, 2, 3 and 4.
//
// Pure, dependency-free ESM. Runs in the Cloudflare Worker, in Node (local
// HTTP) and under node --test.
//
// What this server is NOT: a session. It never receives a narrative, never
// classifies, never drafts, never verifies a package. Every input is a value
// from a closed set the server itself publishes (guideline letters, access
// tiers, populations, event ids, form names, state codes, decision ids). A
// string outside the enum or pattern is a JSON-RPC invalid-params error, and
// that error names the parameter, never what was sent.

import { ReleaseIntegrityError } from './release.js';
import { MAX_TEXT_PARTS, decisionText, findDecisions, hasShards, shardCounts, shardMeta, verifyCase } from './d1.js';

export const SERVER_INFO = { name: 'adverse-information-assistant', version: '0.1.1' };
// Every tool reads published reference material and changes nothing (design §2.1), and
// says so in MCP tool annotations: a client such as ChatGPT's chat mode then calls them
// without asking the user to confirm each one as a possible write.
export const READ_ONLY = Object.freeze({ readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: false });
export const MCP_PROTOCOL_VERSIONS = ['2025-06-18', '2025-03-26', '2024-11-05'];
// One rate-limited POST may carry a JSON-RPC batch; cap it so a batch cannot
// stand in for thousands of requests.
export const MAX_BATCH = 20;
export const RATE_LIMIT = {
  limit: 60,
  period_seconds: 60,
  keyed_on: 'the connecting IP address',
  scope: 'one shared limit across every tool, resource and prompt call',
};
export const ENDPOINT = 'https://fsotools.ai/adverse/mcp';

export const MODE_1B = {
  name: 'Mode 1b — local session, hosted reference',
  disclosure:
    'Running locally. Nothing you type is stored or transmitted by this tool. When I need reference material — ' +
    "a guideline's text, a reporting table, a published decision — I ask fsotools.ai for it by category (a guideline " +
    'letter, an event type), never in your words, and that server keeps no logs. Your words do go to the model ' +
    'provider you have configured, under their terms.',
  what_leaves_the_machine: [
    'the categorical queries themselves (for example a guideline letter, an access tier, a population), which reveal the shape of a matter; a client that wants to reveal nothing can call get_corpus_bundle once at intake and query decisions only if it chooses to',
    "the client's IP address, which Cloudflare sees at the edge and the rate limiter keys on; the Worker itself records nothing",
  ],
  server_keeps: 'no logs, no session, no state. Observability is off; the Worker has no writable binding.',
};

export const STANDING_RULES = [
  'Reference material only. This server does not adjudicate, predict, or state odds; the U.S. Government makes all determinations.',
  'It never receives a narrative and never verifies a package. The session, the agents and the deterministic gates run in the client.',
  'Maintainer-authored files are served with their maintainer_verified flag as it is. A file that is not verified cannot ground a "yes"; the answer stays "consult your security office".',
  'Decisions are contested SOR cases, a selection-biased sample. They generate interview questions and never a rate, a tendency or a likely outcome.',
  'Nothing here is legal advice.',
];

// ---------------------------------------------------------------------------
// Closed sets
// ---------------------------------------------------------------------------
export const GUIDELINES = [...'ABCDEFGHIJKLM'];
export const GUIDELINE_NAMES = {
  A: 'Allegiance to the United States', B: 'Foreign Influence', C: 'Foreign Preference', D: 'Sexual Behavior',
  E: 'Personal Conduct', F: 'Financial Considerations', G: 'Alcohol Consumption',
  H: 'Drug Involvement and Substance Misuse', I: 'Psychological Conditions', J: 'Criminal Conduct',
  K: 'Handling Protected Information', L: 'Outside Activities', M: 'Use of Information Technology',
};
export const ACCESS_TIERS = ['baseline', 'ts_q', 'not_applicable'];
export const POPULATIONS = ['industry', 'federal_civilian', 'military', 'applicant', 'in_process'];
export const FORMS = ['sf86', 'pvq', 'incident_report'];
export const OFFENSES = ['dui', 'owi', 'dwi', 'felony', 'misdemeanor'];
export const ISL_TABLES = [1, 2, 3, 4];
export const ISL_TABLE_NAMES = {
  1: 'Adverse Information Reporting Requirements', 2: 'Reporting Requirements for All Covered Individuals',
  3: 'Top Secret and "Q" Access', 4: 'Foreign Travel Reporting',
};
export const VERIFIES = ['all-covered-individuals', 'adverse-information', 'top-secret-q', 'channels'];
export const CFR_SECTIONS = ['117.8'];
export const CASE_NUMBER = /^\d{2}-\d{4,5}$/;
export const DECISION_ID = /^\d{2}-\d{4,5}\.[ah]\d$/;
export const CORPUS_FILES = {
  'privacy-tiers': 'corpus/privacy-tiers.json',
  plausibility: 'corpus/checks/plausibility.json',
  'collection-policy': 'corpus/forms/collection-policy.json',
  'entity-capture': 'corpus/forms/entity-capture.json',
  'diss-incident-types': 'corpus/forms/diss-incident-types.json',
  'incident-chronology': 'corpus/checklists/_INCIDENT_CHRONOLOGY.json',
  'incident-profiles': 'corpus/checklists/_INCIDENT_PROFILES.json',
  coverage: 'corpus/checklists/_COVERAGE.json',
  'pvq-preambles': 'corpus/forms/pvq-preambles.json',
  'events-index': 'corpus/checklists/events/_INDEX.json',
  'adjudicative-readiness': 'corpus/checklists/_ADJUDICATIVE_READINESS.json',
  'state-records-sources': 'corpus/courts/state-records-sources.json',
  'document-retrieval': 'corpus/documents/retrieval.json',
};
const TABLE_FILES = {
  'all-covered-individuals': 'corpus/reporting/tables/all-covered-individuals.json',
  'adverse-information': 'corpus/reporting/tables/adverse-information.json',
  'top-secret-q': 'corpus/reporting/tables/top-secret-q.json',
  channels: 'corpus/reporting/tables/channels.json',
};
const FORM_FILES = {
  sf86: 'corpus/forms/sf86-map.json',
  pvq: 'corpus/forms/pvq-map.json',
  incident_report: 'corpus/forms/incident-report-map.json',
};
const AUTHORITY_LAYERS = 'corpus/reporting/authority-layers.json';
const UNIVERSAL = 'corpus/checklists/_UNIVERSAL.json';
const COVERAGE = 'corpus/checklists/_COVERAGE.json';
const SEVERITY = 'corpus/checklists/_SEVERITY_LADDERS.json';
const DOCUMENTS = 'corpus/checklists/_DOCUMENT_EVIDENCE.json';
const COURTS = 'corpus/courts/state-courts.json';
const COLLECTION_POLICY = 'corpus/forms/collection-policy.json';
const ENTITY_CAPTURE = 'corpus/forms/entity-capture.json';
const DISS_TYPES = 'corpus/forms/diss-incident-types.json';
const EXCLUSIONS = 'doha-exclusions.json';

// Government text layout, identical to scripts/library_paths.py.
const GOV = {
  'sead-4': { dir: 'government/sead-4', directive: 'SEAD-4', always: ['02_Appendix_A_Introduction_and_Adjudicative_Process.md'] },
  'sead-3': {
    dir: 'government/sead-3', directive: 'SEAD-3',
    always: ['01_Overview_Policy_and_General_Requirements.md', '02_All_Covered_Individuals.md'],
    byAccess: { baseline: '03_Secret_Confidential_L_Noncritical.md', ts_q: '04_Top_Secret_Q_Critical_Special.md' },
    dataElements: '06_Appendix_A_Required_Data_Elements.md',
  },
  'isl-2021-02': { dir: 'government/isl-2021-02', directive: 'ISL-2021-02', always: ['01_Overview_and_Adverse_Information_Guidance.md'] },
  'cfr-117': { dir: 'government/cfr-117', directive: '32 CFR Part 117', always: [] },
};

export const COURT_FALLBACK =
  'Contact the clerk of court in the county or city where the arrest happened and ask for a certified copy of the ' +
  "disposition. If you are not sure which court that was, the clerk's office can tell you from your name and the " +
  'approximate date.';
const COURT_USAGE_RULE =
  "Ask the user first. Offer the nudge ONLY if they don't know. Record what they say, never this suggestion. " +
  'If this entry is unverified, present it explicitly as a guess to check.';
const DECISIONS_REMINDER =
  'These are contested SOR cases — a selection-biased sample. Use them to generate questions. Never to state a ' +
  'rate, a tendency, or a likely outcome.';

// ---------------------------------------------------------------------------
// Errors
// ---------------------------------------------------------------------------
export class InvalidParams extends Error {
  constructor(message) {
    super(message);
    this.name = 'InvalidParams';
    this.code = -32602;
  }
}

/** A tool that ran but cannot answer; returned as an isError result. */
export class ToolError extends Error {
  constructor(message, detail = {}) {
    super(message);
    this.name = 'ToolError';
    this.detail = detail;
  }
}

// ---------------------------------------------------------------------------
// Validation — every message names the parameter, never the value
// ---------------------------------------------------------------------------
const isPlainObject = (v) => v !== null && typeof v === 'object' && !Array.isArray(v);

function validate(args, spec) {
  if (args === undefined || args === null) args = {};
  if (!isPlainObject(args)) throw new InvalidParams('arguments must be a JSON object');
  const allowed = Object.keys(spec);
  const unknown = Object.keys(args).filter((k) => !allowed.includes(k));
  if (unknown.length) {
    throw new InvalidParams(`unexpected parameter present; this tool accepts only: ${allowed.join(', ') || 'no parameters'}`);
  }
  const out = {};
  for (const [name, rule] of Object.entries(spec)) {
    const value = args[name];
    if (value === undefined) {
      if (rule.required) throw new InvalidParams(`${name} is required`);
      if ('default' in rule) out[name] = typeof rule.default === 'function' ? rule.default(out) : rule.default;
      continue;
    }
    out[name] = rule.check(value, name, out);
  }
  return out;
}

const enumOf = (values) => (v, name) => {
  if (!values.includes(v)) throw new InvalidParams(`${name} must be one of: ${values.join(', ')}`);
  return v;
};
const enumArray = (values, { min = 1, max = values.length, describe } = {}) => (v, name) => {
  if (!Array.isArray(v) || v.length < min || v.length > max || v.some((x) => !values.includes(x))) {
    const what = describe ?? `values from: ${values.join(', ')}`;
    throw new InvalidParams(`${name} must be an array of ${min}–${max} distinct ${what}`);
  }
  const unique = [...new Set(v)];
  if (unique.length !== v.length) throw new InvalidParams(`${name} must not repeat a value`);
  return unique;
};
const intRange = (min, max) => (v, name) => {
  if (!Number.isInteger(v) || v < min || v > max) throw new InvalidParams(`${name} must be an integer from ${min} to ${max}`);
  return v;
};
const boolean = (v, name) => {
  if (typeof v !== 'boolean') throw new InvalidParams(`${name} must be true or false`);
  return v;
};
const pattern = (re, describe) => (v, name) => {
  if (typeof v !== 'string' || !re.test(v)) throw new InvalidParams(`${name} must be ${describe}`);
  return v;
};

// ---------------------------------------------------------------------------
// Server
// ---------------------------------------------------------------------------
/**
 * @param {import('./release.js').Release} release verified release
 * @param {{ env?: object, vars?: Record<string, string> }} options
 *   env carries the D1 bindings S1..S3 when present; vars are the Worker's
 *   RELEASE_ID / CORPUS_VERSION / REPO_COMMIT for the consistency report.
 */
export function createAdverseMcpServer(release, options = {}) {
  const env = options.env ?? {};
  const vars = options.vars ?? {};
  const manifest = release.manifest;
  const shards = hasShards(env);

  function safeJson(path) {
    try {
      return release.json(path);
    } catch {
      return null;
    }
  }

  // ---- release-derived closed sets ----
  // These files define tool input enums. A release that cannot supply them
  // would publish a parameter no value can satisfy, so their absence fails the
  // server's construction (ReleaseIntegrityError) rather than producing an
  // empty enum. release.json throws for a missing or unverified file.
  function closedSet(path, values) {
    if (!values.length) throw new ReleaseIntegrityError(path, 'yields an empty closed set');
    return values;
  }
  const eventIndex = buildEventIndex();
  const EVENT_IDS = closedSet(TABLE_FILES['all-covered-individuals'], eventIndex.map((e) => e.id));
  const STATES = closedSet(COURTS, Object.keys(release.json(COURTS).states ?? {}).sort());
  const FORM_SECTIONS = Object.fromEntries(
    FORMS.map((form) => {
      const data = release.json(FORM_FILES[form]);
      const keys = form === 'incident_report' ? Object.keys(data.fields ?? {}) : Object.keys(data.sections ?? {});
      return [form, closedSet(FORM_FILES[form], keys)];
    }),
  );
  const ALL_SECTIONS = [...new Set(FORMS.flatMap((f) => FORM_SECTIONS[f]))].sort();

  function buildEventIndex() {
    const claimedBy = new Map();
    for (const path of release.list('corpus/checklists/events/event-')) {
      const data = release.json(path);
      for (const id of data?.event_ids ?? []) claimedBy.set(id, data.event_checklist ?? path);
    }
    const rows = [];
    for (const [table, path] of Object.entries(TABLE_FILES)) {
      if (table === 'channels') continue;
      const data = release.json(path);
      for (const entry of data?.entries ?? []) {
        if (!entry?.id) continue;
        rows.push({
          id: entry.id,
          event: entry.event ?? null,
          reportable: entry.reportable ?? null,
          channel_ref: entry.channel_ref ?? null,
          basis: entry.basis ?? null,
          required_data_elements: entry.required_data_elements ?? [],
          applies_to: data.applies_to ?? null,
          table,
          table_file: path,
          table_maintainer_verified: data.maintainer_verified === true,
          event_checklist: claimedBy.get(entry.id) ?? null,
        });
      }
    }
    return rows;
  }

  // ---- shard metadata, resolved lazily by the tools that need it ----
  // Only get_release and the decision tools touch the shards. Reference tools
  // never wait on D1. A failure is cached for SHARD_RETRY_MS so a D1 outage does
  // not turn every call into a retry.
  const SHARD_RETRY_MS = 60_000;
  const NO_SHARDS = { available: false, note: 'decision text shards are not bound in this deployment', meta: [], counts: null };
  let shardInfo = shards ? null : NO_SHARDS;
  let shardFailedAt = 0;
  async function ensureShardInfo() {
    if (shardInfo) return shardInfo;
    if (shardFailedAt && Date.now() - shardFailedAt < SHARD_RETRY_MS) {
      return { available: false, note: 'decision text shards did not answer recently; retry later', meta: [], counts: null };
    }
    try {
      const [meta, counts] = await Promise.all([shardMeta(env), shardCounts(env)]);
      shardInfo = { available: true, meta, counts };
      return shardInfo;
    } catch {
      shardFailedAt = Date.now();
      return { available: false, note: 'decision text shards did not answer', meta: [], counts: null };
    }
  }

  let exclusionSet = null;
  function exclusions() {
    if (!exclusionSet) exclusionSet = new Set(release.json(EXCLUSIONS)?.document_ids ?? []);
    return exclusionSet;
  }

  // ---- blocks ----
  function fileMeta(path) {
    return release.meta(path) ?? {};
  }

  function fileBlock(path, data = undefined) {
    const meta = fileMeta(path);
    const citable = meta.verified === true;
    return {
      file: path,
      source: meta.source ?? null,
      sha256: meta.sha256 ?? null,
      source_sha256_yaml: meta.source_sha256_yaml ?? null,
      maintainer_verified: meta.maintainer_verified === true,
      citable,
      ...(citable ? {} : { unverified_note: manifest.unverified_sentence }),
      data: data === undefined ? release.json(path) : data,
    };
  }

  function govManifest(key) {
    return release.json(`${GOV[key].dir}/manifest.json`);
  }

  function govBlock(key, file) {
    const path = `${GOV[key].dir}/${file}`;
    const meta = fileMeta(path);
    const section = (govManifest(key).sections ?? []).find((s) => s.file === file) ?? {};
    return {
      directive: GOV[key].directive,
      file: path,
      title: section.title ?? file.replace(/\.md$/, ''),
      sha256: meta.sha256 ?? null,
      body_sha256: meta.body_sha256 ?? section.body_sha256 ?? null,
      verified: true,
      verified_by: 'custodian-release',
      text: release.text(path),
    };
  }

  function govSections(key, files) {
    const missing = files.filter((f) => !release.has(`${GOV[key].dir}/${f}`));
    if (missing.length) {
      throw new ToolError('a requested directive section is not available in this release; quote nothing and say the text is unavailable', {
        directive: GOV[key].directive,
        missing_files: missing.map((f) => `${GOV[key].dir}/${f}`),
        rule: 'Never substitute the whole directive for a missing section.',
      });
    }
    return files.map((f) => govBlock(key, f));
  }

  async function releaseBlock(filesUsed) {
    // Never waits on D1: doha_release is reported once a shard-reading tool
    // (get_release, find_decisions, verify_case, get_decision_text) has
    // resolved it in this isolate, and is null until then.
    const info = shardInfo;
    const ids = info ? [...new Set(info.meta.map((m) => m.release_id).filter(Boolean))] : [];
    return {
      corpus_version: manifest.corpus_version,
      library_release: manifest.library_release,
      repo_commit: manifest.repo_commit,
      doha_shards: manifest.doha_shards ?? [],
      doha_release: info?.available ? (ids.length === 1 ? ids[0] : ids) : null,
      ...(info?.available ? {} : { doha_release_note: 'resolved by get_release or a decision tool; see get_release for the shard metadata' }),
      file_sha256: filesUsed.map((f) => ({ file: f, sha256: f === 'manifest.json' ? release.manifestSha256 : fileMeta(f).sha256 ?? null })),
    };
  }

  const usedFiles = (blocks) => blocks.flat().map((b) => b.file);

  function requireShards() {
    if (!shards) throw new ToolError('decision text shards are not bound in this deployment; cite nothing from memory');
  }

  // ---- tools ----
  const toolDefs = [
    {
      name: 'get_release',
      description:
        'Release ids and approval receipt, decision counts computed from the shards, which directive sections are present, verified and unverified file counts, the rate limit and the Mode 1b disclosure. Intake stage 0 calls this first and relays it, as it relays check_library.py locally.',
      schema: {},
      spec: {},
      run: async () => {
        const info = await ensureShardInfo();
        const varsCheck = {
          RELEASE_ID: vars.RELEASE_ID ?? null,
          CORPUS_VERSION: vars.CORPUS_VERSION ?? null,
          REPO_COMMIT: vars.REPO_COMMIT ?? null,
        };
        const consistent =
          (!varsCheck.RELEASE_ID || varsCheck.RELEASE_ID === manifest.library_release) &&
          (!varsCheck.CORPUS_VERSION || varsCheck.CORPUS_VERSION === manifest.corpus_version) &&
          (!varsCheck.REPO_COMMIT || varsCheck.REPO_COMMIT === manifest.repo_commit);
        const sead4 = safeJson(`${GOV['sead-4'].dir}/manifest.json`);
        const sead3 = safeJson(`${GOV['sead-3'].dir}/manifest.json`);
        const isl = safeJson(`${GOV['isl-2021-02'].dir}/manifest.json`);
        return {
          release: await releaseBlock(['manifest.json']),
          library_approval: manifest.library_approval,
          library_published_utc: manifest.library_published_utc ?? null,
          built_utc: manifest.built_utc,
          build_checks: manifest.checks ?? null,
          worker_vars: { ...varsCheck, consistent_with_manifest: consistent },
          decisions: {
            shards_available: info.available,
            ...(info.available ? {} : { note: info.note }),
            shards: info.meta,
            counts: info.counts,
            exclusions: manifest.doha_exclusions ?? null,
          },
          directive_sections: {
            'sead-4': {
              present: Boolean(sead4),
              guidelines: (sead4?.sections ?? []).map((s) => s.guideline).filter(Boolean).sort(),
              sections: (sead4?.sections ?? []).length,
            },
            'sead-3': { present: Boolean(sead3), sections: (sead3?.sections ?? []).length },
            'isl-2021-02': {
              present: Boolean(isl),
              tables: (isl?.sections ?? []).map((s) => /Table_(\d)_/.exec(s.file)?.[1]).filter(Boolean),
            },
            'cfr-117': manifest.cfr_117 ?? { available: false },
          },
          verification: {
            ...(manifest.counts ?? {}),
            integrity: release.integrity,
            how_to_read: manifest.unverified_sentence,
          },
          rate_limit: RATE_LIMIT,
          mode: MODE_1B,
          standing_rules: STANDING_RULES,
          tools: toolDefs.map((t) => t.name),
          prompts: PROMPTS.map((p) => p.name),
        };
      },
    },
    {
      name: 'get_guideline_text',
      description:
        'SEAD 4 text for the named guidelines, one section each, plus Appendix A (the adjudicative process and whole-person concept), always. Nothing else. A missing section is an error for the whole call: quote nothing. The hosted form of `sead_lookup.py --guidelines`.',
      schema: { guidelines: { type: 'array', minItems: 1, maxItems: 13, items: { type: 'string', enum: GUIDELINES }, description: 'SEAD 4 guideline letters A–M.' } },
      spec: { guidelines: { required: true, check: enumArray(GUIDELINES, { describe: 'SEAD 4 guideline letters A–M' }) } },
      run: async ({ guidelines }) => {
        const m = govManifest('sead-4');
        const byLetter = Object.fromEntries((m.sections ?? []).filter((s) => s.guideline).map((s) => [s.guideline, s.file]));
        const files = [...GOV['sead-4'].always, ...guidelines.map((g) => byLetter[g] ?? `(no section for Guideline ${g})`)];
        const sections = govSections('sead-4', files);
        return {
          guidelines: guidelines.map((g) => ({ letter: g, name: GUIDELINE_NAMES[g] })),
          rule: 'Read exactly these sections. A guideline not named here is not part of the matter and its text must not appear in the output.',
          sections,
          release: await releaseBlock(usedFiles(sections)),
        };
      },
    },
    {
      name: 'get_reporting_requirements',
      description:
        'SEAD 3 reporting requirements for an access tier: the overview and all-covered-individuals sections, the one additive section for the tier (F + G or F + H, never a ladder), and Appendix A required data elements. `not_applicable` returns the overview and all-covered sections only. The hosted form of `sead_lookup.py --reporting --access`.',
      schema: {
        access: { type: 'string', enum: ACCESS_TIERS, description: 'baseline = Secret/Confidential/L; ts_q = Top Secret/Q; not_applicable = no additive section.' },
        include_data_elements: { type: 'boolean', description: 'Include Appendix A required data elements (default true).' },
      },
      spec: { access: { required: true, check: enumOf(ACCESS_TIERS) }, include_data_elements: { default: true, check: boolean } },
      run: async ({ access, include_data_elements }) => {
        const g = GOV['sead-3'];
        const files = [...g.always];
        if (g.byAccess[access]) files.push(g.byAccess[access]);
        if (include_data_elements && access !== 'not_applicable') files.push(g.dataElements);
        const sections = govSections('sead-3', files);
        return {
          access,
          additive_rule: 'Section G (Secret/Confidential/L) and Section H (Top Secret/Q) each apply in addition to Section F; neither builds on the other. A Top Secret holder reads F + H, not F + G + H.',
          sections,
          release: await releaseBlock(usedFiles(sections)),
        };
      },
    },
    {
      name: 'get_isl_section',
      description:
        "ISL 2021-02 (v2, May 2024), DCSA's implementation of SEAD 3 for cleared industry: the overview section plus one table, selected by table number or by the corpus reporting table it is the source of record for. Exactly one of `table` or `verifies`. The hosted form of `sead_lookup.py --isl`.",
      schema: {
        table: { type: 'integer', enum: ISL_TABLES, description: 'ISL table number 1–4.' },
        verifies: { type: 'string', enum: VERIFIES, description: 'Corpus reporting table whose ISL source-of-record section is wanted.' },
      },
      spec: { table: { check: enumOf(ISL_TABLES) }, verifies: { check: enumOf(VERIFIES) } },
      run: async ({ table, verifies }) => {
        if ((table === undefined) === (verifies === undefined)) {
          throw new InvalidParams('exactly one of table or verifies is required');
        }
        const m = govManifest('isl-2021-02');
        let file;
        if (table !== undefined) {
          file = (m.sections ?? []).find((s) => new RegExp(`Table_${table}_`).test(s.file))?.file;
          if (!file) throw new ToolError('no ISL section file exists for that table in this release', { table });
        } else {
          const hit = (m.sections ?? []).find((s) => String(s.verifies ?? '').replace(/\\/g, '/').toLowerCase().endsWith(`tables/${verifies}.yaml`));
          if (!hit) {
            throw new ToolError('no ISL section records itself as the source of record for that corpus table', {
              verifies,
              note: 'channels.yaml is a maintainer synthesis across the letter; no single ISL table backs it.',
            });
          }
          file = hit.file;
        }
        const sections = govSections('isl-2021-02', [...GOV['isl-2021-02'].always, file]);
        const tableNo = /Table_(\d)_/.exec(file)?.[1];
        return {
          selected_by: table !== undefined ? { table } : { verifies },
          table: tableNo ? { number: Number(tableNo), name: ISL_TABLE_NAMES[tableNo] } : null,
          sections,
          release: await releaseBlock(usedFiles(sections)),
        };
      },
    },
    {
      name: 'get_cfr_section',
      description:
        '32 CFR § 117.8 (NISPOM reporting requirements), the only section of Part 117 this tool needs. Returns the section text when the library release carries a section split of the Part, otherwise "unavailable" with the reason. The enum has one value by design.',
      schema: { section: { type: 'string', enum: CFR_SECTIONS, description: 'Only "117.8".' } },
      spec: { section: { required: true, check: enumOf(CFR_SECTIONS) } },
      run: async ({ section }) => {
        const cfr = manifest.cfr_117 ?? { available: false };
        if (!cfr.available) {
          return {
            section,
            status: 'unavailable',
            reason: cfr.reason ?? 'the library release has no section split of 32 CFR Part 117',
            library_has: cfr.library_has ?? null,
            rule: 'Say the regulation text is unavailable and return consult_fso for the obligation; do not quote the Part from memory.',
            release: await releaseBlock([]),
          };
        }
        const hit = (cfr.sections ?? []).find((s) => String(s.section) === section || /117[._-]8\b/.test(String(s.file)));
        if (!hit) throw new ToolError('the release has a Part 117 split but no file for that section', { section });
        const sections = govSections('cfr-117', [hit.file]);
        return { section, status: 'available', sections, release: await releaseBlock(usedFiles(sections)) };
      },
    },
    {
      name: 'get_reporting_tables',
      description:
        "The maintainer-authored reporting tables that apply to a population and access tier: the authority layers in scope, the table entries (optionally only the given event ids), the channel family for that population, the attribution status, and every file's maintainer_verified flag. Matching a narrative to an event id is the client's job; the server only filters by ids the client already chose.",
      schema: {
        population: { type: 'string', enum: POPULATIONS },
        access: { type: 'string', enum: ACCESS_TIERS },
        event_ids: { type: 'array', minItems: 1, maxItems: 64, items: { type: 'string', enum: EVENT_IDS }, description: 'Table entry ids from list_event_types.' },
      },
      spec: {
        population: { required: true, check: enumOf(POPULATIONS) },
        access: { required: true, check: enumOf(ACCESS_TIERS) },
        event_ids: { check: enumArray(EVENT_IDS, { max: 64, describe: 'event ids from list_event_types' }) },
      },
      run: async ({ population, access, event_ids }) => {
        const layersData = release.json(AUTHORITY_LAYERS);
        const keyed = layersData.population_to_layers?.[population];
        const layerKeys = keyed ?? ['sead-3'];
        const layersNote = keyed
          ? null
          : 'applicant and in_process are not keyed in population_to_layers; SEAD 3 binds every covered individual, which includes a person in process. Whether the ISL layer also applies turns on whether the sponsoring facility is cleared industry, which the client knows and the server does not.';
        const layers = fileBlock(AUTHORITY_LAYERS, {
          layers: Object.fromEntries(layerKeys.map((k) => [k, layersData.layers?.[k] ?? null])),
          population_to_layers: layersData.population_to_layers,
          attribution_status: layersData.attribution_status,
          attribution_note: layersData.attribution_note,
          federal_and_military_note: layersData.federal_and_military_note,
          degraded_behavior_federal: layersData.degraded_behavior_federal,
        });
        const tableKeys = ['all-covered-individuals', 'adverse-information', ...(access === 'ts_q' ? ['top-secret-q'] : [])];
        const tables = tableKeys.map((key) => {
          const data = release.json(TABLE_FILES[key]);
          const entries = event_ids ? (data.entries ?? []).filter((e) => event_ids.includes(e.id)) : data.entries ?? [];
          return { table: key, ...fileBlock(TABLE_FILES[key], { ...data, entries }) };
        });
        const channelsData = release.json(TABLE_FILES.channels);
        const family =
          population === 'industry' ? 'industry_channels' : population === 'applicant' || population === 'in_process' ? 'applicant_channels' : 'federal_military_channels';
        const channels = fileBlock(TABLE_FILES.channels, {
          family,
          channels: channelsData[family] ?? {},
          default_when_unmatched: channelsData.default_when_unmatched ?? null,
          default_for_federal_when_unmatched: channelsData.default_for_federal_when_unmatched ?? null,
          never_do: channelsData.never_do ?? null,
        });
        const unmatched = event_ids ? event_ids.filter((id) => !tables.some((t) => t.data.entries.some((e) => e.id === id))) : [];
        return {
          population,
          access,
          layers_in_scope: layerKeys,
          ...(layersNote ? { layers_note: layersNote } : {}),
          authority_layers: layers,
          tables,
          ...(unmatched.length
            ? { event_ids_not_in_these_tables: unmatched, note: 'Those ids belong to a table outside this access tier (for example a top-secret-q entry at baseline).' }
            : {}),
          channels,
          attribution_status: layersData.attribution_status,
          reportable_rule: 'reporting.reportable is only ever "yes" or "consult_fso", never "no"; an unverified table cannot ground a "yes".',
          release: await releaseBlock(usedFiles([layers, ...tables, channels])),
        };
      },
    },
    {
      name: 'list_event_types',
      description:
        'Every reporting-table entry id with its event description, applies_to, reportable value, channel_ref, required data elements, the table it comes from and the event checklist that claims it. This is the closed set `event_ids` draws from.',
      schema: {},
      spec: {},
      run: async () => {
        const files = [TABLE_FILES['all-covered-individuals'], TABLE_FILES['adverse-information'], TABLE_FILES['top-secret-q'], CORPUS_FILES['events-index']];
        return {
          count: eventIndex.length,
          events: eventIndex,
          files: files.map((f) => ({ file: f, maintainer_verified: fileMeta(f).maintainer_verified === true, citable: fileMeta(f).verified === true })),
          unverified_note: manifest.unverified_sentence,
          release: await releaseBlock(files),
        };
      },
    },
    {
      name: 'get_checklists',
      description:
        'Gap-analysis sources: the guideline checklists for the given letters, the event checklists claiming the given event ids, _UNIVERSAL and _COVERAGE, plus an index of element ids to the files each appears in so the gap analyst deduplicates by id. At least one of the two inputs is required.',
      schema: {
        guidelines: { type: 'array', minItems: 1, maxItems: 13, items: { type: 'string', enum: GUIDELINES } },
        event_ids: { type: 'array', minItems: 1, maxItems: 64, items: { type: 'string', enum: EVENT_IDS } },
      },
      spec: {
        guidelines: { check: enumArray(GUIDELINES, { describe: 'SEAD 4 guideline letters A–M' }) },
        event_ids: { check: enumArray(EVENT_IDS, { max: 64, describe: 'event ids from list_event_types' }) },
      },
      run: async ({ guidelines, event_ids }) => {
        if (!guidelines && !event_ids) throw new InvalidParams('at least one of guidelines or event_ids is required');
        const guidelineFiles = (guidelines ?? []).map((g) => fileBlock(`corpus/checklists/guideline-${g}.json`));
        const eventFiles = [];
        if (event_ids) {
          for (const path of release.list('corpus/checklists/events/event-')) {
            const data = release.json(path);
            if ((data.event_ids ?? []).some((id) => event_ids.includes(id))) eventFiles.push(fileBlock(path, data));
          }
        }
        const universal = fileBlock(UNIVERSAL);
        const coverage = fileBlock(COVERAGE);
        const elementIndex = {};
        for (const block of [...guidelineFiles, ...eventFiles, universal]) {
          for (const el of block.data.elements ?? []) {
            if (!el?.id) continue;
            (elementIndex[el.id] ??= []).push(block.file);
          }
        }
        const implied = [...new Set(eventFiles.flatMap((b) => b.data.guidelines ?? []))].filter((g) => !(guidelines ?? []).includes(g)).sort();
        return {
          guidelines: guidelines ?? [],
          event_ids: event_ids ?? [],
          guideline_checklists: guidelineFiles,
          event_checklists: eventFiles,
          ...(implied.length ? { guidelines_named_by_event_checklists_not_requested: implied } : {}),
          universal,
          coverage,
          element_index: elementIndex,
          dedupe_rule: 'Elements sharing an id across files are the same question: ask once.',
          release: await releaseBlock(usedFiles([...guidelineFiles, ...eventFiles, universal, coverage])),
        };
      },
    },
    {
      name: 'get_form_map',
      description:
        "A form's section map (SF-86, PVQ or the FSO incident report) with collection-policy and entity-capture, and for incident_report also diss-incident-types. Section ids are the keys the map file defines; omit `sections` for the whole map.",
      schema: {
        form: { type: 'string', enum: FORMS },
        sections: { type: 'array', minItems: 1, maxItems: 64, items: { type: 'string', enum: ALL_SECTIONS }, description: "Section ids defined by that form's map file." },
      },
      spec: {
        form: { required: true, check: enumOf(FORMS) },
        sections: { check: enumArray(ALL_SECTIONS, { max: 64, describe: 'section ids defined by the form map files' }) },
      },
      run: async ({ form, sections }) => {
        const path = FORM_FILES[form];
        const data = release.json(path);
        const key = form === 'incident_report' ? 'fields' : 'sections';
        let shaped = data;
        if (sections) {
          const defined = FORM_SECTIONS[form];
          if (sections.some((s) => !defined.includes(s))) throw new ToolError('a requested section is not defined by that form', { form, defined_sections: defined });
          shaped = { ...data, [key]: Object.fromEntries(sections.map((s) => [s, data[key][s]])) };
        }
        const map = fileBlock(path, shaped);
        const policy = fileBlock(COLLECTION_POLICY);
        const entity = fileBlock(ENTITY_CAPTURE);
        const diss = form === 'incident_report' ? fileBlock(DISS_TYPES) : null;
        return {
          form,
          section_ids: FORM_SECTIONS[form],
          map,
          collection_policy: policy,
          entity_capture: entity,
          ...(diss ? { diss_incident_types: diss } : {}),
          release: await releaseBlock(usedFiles([map, policy, entity, ...(diss ? [diss] : [])])),
        };
      },
    },
    {
      name: 'get_severity_ladder',
      description:
        "One guideline's severity ladder from _SEVERITY_LADDERS (or its fact_dimensions for `ladder: false` guidelines) with case_refs, plus the file's method and universal axis. Depth only ever decides how hard the interviewer presses on optional elements; it never scores, rates or predicts.",
      schema: { guideline: { type: 'string', enum: GUIDELINES } },
      spec: { guideline: { required: true, check: enumOf(GUIDELINES) } },
      run: async ({ guideline }) => {
        const data = release.json(SEVERITY);
        const block = fileBlock(SEVERITY, {
          guideline,
          ladder: data.guidelines?.[guideline] ?? null,
          depth_values: data.depth_values,
          universal_axis: data.universal_axis,
          method: data.method,
          source_corpus: data.source_corpus,
        });
        return { guideline, name: GUIDELINE_NAMES[guideline], severity: block, release: await releaseBlock(usedFiles([block])) };
      },
    },
    {
      name: 'get_document_evidence',
      description:
        'Per-guideline document entries and bare_claim_patterns from _DOCUMENT_EVIDENCE: which records judges discussed as corroboration, who holds them, and what each corroborates. Never a rate or a tendency.',
      schema: { guidelines: { type: 'array', minItems: 1, maxItems: 13, items: { type: 'string', enum: GUIDELINES } } },
      spec: { guidelines: { required: true, check: enumArray(GUIDELINES, { describe: 'SEAD 4 guideline letters A–M' }) } },
      run: async ({ guidelines }) => {
        const data = release.json(DOCUMENTS);
        const block = fileBlock(DOCUMENTS, {
          guidelines: Object.fromEntries(guidelines.map((g) => [g, data.guidelines?.[g] ?? null])),
          weight_values: data.weight_values,
          method: data.method,
          source_corpus: data.source_corpus,
        });
        return { guidelines, documents: block, release: await releaseBlock(usedFiles([block])) };
      },
    },
    {
      name: 'court_lookup',
      description:
        "Court recognition aid for one state: court names, unit_label, lower courts, dui_note, records custodian, verified flag and the ask-first sentence. County is not an input (the user typed it); the client composes the nudge from unit_label and the court names. The user's own answer is always what gets recorded.",
      schema: {
        state: { type: 'string', enum: STATES, description: 'Two-letter state or district code present in state-courts.yaml.' },
        offense: { type: 'string', enum: OFFENSES },
      },
      spec: { state: { required: true, check: enumOf(STATES) }, offense: { check: enumOf(OFFENSES) } },
      run: async ({ state, offense }) => {
        const data = release.json(COURTS);
        const st = data.states?.[state];
        if (!st) throw new ToolError('no entry for that state in this release', { fallback: COURT_FALLBACK });
        const felony = offense === 'felony';
        const block = fileBlock(COURTS, {
          state,
          state_name: st.name,
          verified: st.verified === true,
          confidence: st.verified === true ? 'verified' : 'unverified_guess',
          unit_label: st.unit_label ?? 'County',
          trial_court_felony: st.trial_court_felony ?? null,
          trial_court_misdemeanor: st.trial_court_misdemeanor ?? null,
          court_for_offense: offense ? (felony ? st.trial_court_felony : st.trial_court_misdemeanor) ?? null : null,
          lower_courts: st.lower_courts ?? [],
          dui_note: offense && ['dui', 'owi', 'dwi'].includes(offense) ? st.dui_note ?? null : null,
          records_custodian: st.records_custodian ?? null,
          statewide_portal: st.statewide_portal ?? null,
          judiciary_url: st.judiciary_url ?? null,
          notes: st.notes ?? null,
          source_url: st.source_url ?? null,
          verified_date: st.verified_date ?? null,
        });
        // The other state-held custodians for the same state (driver record,
        // state tax, criminal history, child welfare), when the release
        // carries the directory. Front doors only, unverified, never used to
        // look up anyone but the user.
        const sourcesPath = CORPUS_FILES['state-records-sources'];
        const src = release.has(sourcesPath) ? release.json(sourcesPath).states?.[state] : null;
        const sources = src
          ? fileBlock(sourcesPath, {
              state,
              verified: src.verified === true,
              dmv: src.dmv ?? null,
              tax: src.tax ?? null,
              criminal_history: src.criminal_history ?? null,
              child_welfare: src.child_welfare ?? null,
            })
          : null;
        return {
          state,
          offense: offense ?? null,
          court: block,
          records_sources: sources,
          ask_first: 'What court did your case go through?',
          nudge_template: "In {state_name}, that's usually the {court_for_offense} for {county} {unit_label}. {lower courts, if any} {dui_note, if any}",
          usage_rule: COURT_USAGE_RULE,
          fallback_if_still_unknown: COURT_FALLBACK,
          release: await releaseBlock(usedFiles(sources ? [block, sources] : [block])),
        };
      },
    },
    {
      name: 'get_corpus_file',
      description:
        'One standalone maintainer-authored file by name: privacy-tiers, plausibility, collection-policy, entity-capture, diss-incident-types, incident-chronology, incident-profiles, coverage, pvq-preambles, events-index, adjudicative-readiness (DCSA\'s adjudicatively-ready standard restated: statement factors and per-guideline supporting documents with obtain_by) state-records-sources (per-state motor-vehicle, tax, criminal-history and child-welfare custodians plus national sources) or document-retrieval (how each supporting document is requested or replaced, with obtainable_by and lead times; directory information, never fetched). Also available as resources adverse://corpus/<file>.',
      schema: { file: { type: 'string', enum: Object.keys(CORPUS_FILES) } },
      spec: { file: { required: true, check: enumOf(Object.keys(CORPUS_FILES)) } },
      run: async ({ file }) => {
        const block = fileBlock(CORPUS_FILES[file]);
        return { name: file, ...block, release: await releaseBlock([block.file]) };
      },
    },
    {
      name: 'get_corpus_bundle',
      description:
        'Every Government section and every maintainer-authored file in one response, so a privacy-maximising client can fetch the whole reference layer once at intake and reveal nothing about the matter in later calls. Decision text is not included (query it only if you choose to).',
      schema: {},
      spec: {},
      run: async () => {
        const government = {};
        for (const key of Object.keys(GOV)) {
          if (!release.has(`${GOV[key].dir}/manifest.json`)) continue;
          government[key] = (govManifest(key).sections ?? []).filter((s) => release.has(`${GOV[key].dir}/${s.file}`)).map((s) => govBlock(key, s.file));
        }
        const corpus = release.list('corpus/').map((p) => fileBlock(p));
        return {
          government,
          cfr_117: manifest.cfr_117 ?? { available: false },
          corpus,
          not_included: ['doha-exclusions.json (derived, applied server-side by find_decisions)', 'agents/* (served as MCP prompts)', 'decision text (D1 shards)'],
          release: await releaseBlock([...Object.values(government).flat().map((b) => b.file), ...corpus.map((b) => b.file)]),
        };
      },
    },
    {
      name: 'find_decisions',
      description:
        "Published DOHA decisions that adjudicated the given guidelines, ranked by guideline overlap, post-SEAD 4 era first, outcomes alternated denied/approved so the sample is never one-sided, with the library's ineligible decisions excluded. The hosted form of `doha_retrieval.py --guidelines`. No counts by outcome, no rates, no \"similar cases\": these generate interview questions only.",
      schema: {
        guidelines: { type: 'array', minItems: 1, maxItems: 13, items: { type: 'string', enum: GUIDELINES } },
        limit: { type: 'integer', minimum: 1, maximum: 12, description: 'Default 6.' },
        include_pre_sead4: { type: 'boolean', description: 'Include decisions decided under superseded criteria (historical context only). Default false.' },
      },
      spec: {
        guidelines: { required: true, check: enumArray(GUIDELINES, { describe: 'SEAD 4 guideline letters A–M' }) },
        limit: { default: 6, check: intRange(1, 12) },
        include_pre_sead4: { default: false, check: boolean },
      },
      run: async ({ guidelines, limit, include_pre_sead4 }) => {
        requireShards();
        await ensureShardInfo();
        const excluded = exclusions();
        const found = await findDecisions(env, guidelines, { limit, includePreSead4: include_pre_sead4, excluded });
        return {
          guidelines,
          scope: 'POST_SEAD_4' + (include_pre_sead4 ? ' + PRE_SEAD_4 (historical)' : ''),
          returned: found.cases.length,
          matched_before_exclusions: found.matched_before_exclusions,
          exclusions_applied: excluded.size,
          reminder: DECISIONS_REMINDER,
          cases: found.cases,
          read_with: `get_decision_text(decision_id, part_from, part_to) — at most ${MAX_TEXT_PARTS} parts per call; the precedent miner reads at most five decisions.`,
          release: await releaseBlock([EXCLUSIONS]),
        };
      },
    },
    {
      name: 'verify_case',
      description:
        "Whether a DOHA case number exists in the decision shards and which decisions sit under it. A case number is an identifier from the server's own output or a published decision, never narrative; the pattern check rejects anything else. The hosted form of `doha_retrieval.py --verify-case`, for a client-side verifier with no library on disk.",
      schema: { case_number: { type: 'string', pattern: CASE_NUMBER.source, description: 'DOHA case number: two digits, a hyphen, four or five digits.' } },
      spec: { case_number: { required: true, check: pattern(CASE_NUMBER, 'a DOHA case number: two digits, a hyphen, then four or five digits') } },
      run: async ({ case_number }) => {
        requireShards();
        const decisions = await verifyCase(env, case_number);
        const info = await ensureShardInfo();
        return {
          case_number,
          in_library: decisions.length > 0,
          decisions,
          unique_case_count: info.counts?.unique_cases ?? null,
          release: await releaseBlock([]),
        };
      },
    },
    {
      name: 'get_decision_text',
      description: `The text of one published decision, by decision id and part range (1-based, at most ${MAX_TEXT_PARTS} parts per call), with page numbers and the official DOHA source URL. Decision ids come from find_decisions or verify_case.`,
      schema: {
        decision_id: { type: 'string', pattern: DECISION_ID.source, description: 'Decision id: a case number followed by .h1, .h2, .a1 and so on.' },
        part_from: { type: 'integer', minimum: 1, maximum: 10000, description: 'First part (default 1).' },
        part_to: { type: 'integer', minimum: 1, maximum: 10000, description: `Last part (default part_from + ${MAX_TEXT_PARTS - 1}).` },
      },
      spec: {
        decision_id: { required: true, check: pattern(DECISION_ID, 'a decision id: a case number followed by .h or .a and a digit') },
        part_from: { default: 1, check: intRange(1, 10000) },
        part_to: {
          default: (out) => out.part_from + MAX_TEXT_PARTS - 1,
          check: (v, name, out) => {
            const n = intRange(1, 10000)(v, name);
            if (n < out.part_from) throw new InvalidParams(`${name} must not be less than part_from`);
            if (n - out.part_from + 1 > MAX_TEXT_PARTS) throw new InvalidParams(`${name} must be within ${MAX_TEXT_PARTS} parts of part_from`);
            return n;
          },
        },
      },
      run: async ({ decision_id, part_from, part_to }) => {
        requireShards();
        await ensureShardInfo();
        const text = await decisionText(env, decision_id, part_from, part_to);
        if (!text) throw new ToolError('no decision with that id is in the shards');
        if (text.parts_total > 0 && part_from > text.parts_total) {
          throw new ToolError('part_from is beyond the last part of that decision', { parts_total: text.parts_total });
        }
        return { ...text, reminder: DECISIONS_REMINDER, release: await releaseBlock([]) };
      },
    },
  ];

  const requiredOf = (spec) => Object.entries(spec).filter(([, r]) => r.required).map(([k]) => k);
  const tools = toolDefs.map((t) => ({
    name: t.name,
    description: t.description,
    annotations: { ...READ_ONLY },
    inputSchema: {
      type: 'object',
      additionalProperties: false,
      properties: t.schema,
      ...(requiredOf(t.spec).length ? { required: requiredOf(t.spec) } : {}),
    },
  }));

  // ---- resources ----
  const resources = [
    { uri: 'adverse://release', name: 'Release manifest', description: 'Release ids, approval receipt and the SHA-256 of every served file.', mimeType: 'application/json' },
    ...Object.entries(CORPUS_FILES).map(([name, path]) => ({
      uri: `adverse://corpus/${name}`,
      name: path,
      description: 'Maintainer-authored file, served with its maintainer_verified flag as it is.',
      mimeType: 'application/json',
    })),
    ...Object.keys(GOV).flatMap((key) => {
      if (!release.has(`${GOV[key].dir}/manifest.json`)) return [];
      return (govManifest(key).sections ?? [])
        .filter((s) => release.has(`${GOV[key].dir}/${s.file}`))
        .map((s) => ({
          uri: `adverse://government/${key}/${s.file.replace(/\.md$/, '')}`,
          name: `${GOV[key].directive} — ${s.title ?? s.file}`,
          description: 'Government text from the approved DCSA Library release, verified by the Custodian release hash chain.',
          mimeType: 'text/markdown',
        }));
    }),
  ];

  function readResource(uri) {
    if (uri === 'adverse://release') return { mimeType: 'application/json', text: JSON.stringify(manifest, null, 2) };
    let m = /^adverse:\/\/corpus\/([a-z-]+)$/.exec(uri);
    if (m && CORPUS_FILES[m[1]]) return { mimeType: 'application/json', text: JSON.stringify(fileBlock(CORPUS_FILES[m[1]]), null, 2) };
    m = /^adverse:\/\/government\/(sead-4|sead-3|isl-2021-02|cfr-117)\/([A-Za-z0-9_-]+)$/.exec(uri);
    if (m && release.has(`${GOV[m[1]].dir}/${m[2]}.md`)) return { mimeType: 'text/markdown', text: govBlock(m[1], `${m[2]}.md`).text };
    return null;
  }

  // ---- prompts ----
  const PROMPTS = buildPrompts();

  function buildPrompts() {
    const table = [
      'python scripts/check_corpus.py / check_library.py      → get_release',
      'python scripts/sead_lookup.py --guidelines G,J          → get_guideline_text(["G","J"])',
      'python scripts/sead_lookup.py --reporting --access ts_q → get_reporting_requirements("ts_q")',
      'python scripts/sead_lookup.py --isl --isl-tables 4      → get_isl_section(table=4)',
      'python scripts/sead_lookup.py --isl --verifies <table>  → get_isl_section(verifies=<table>)',
      'python scripts/doha_retrieval.py --guidelines G,J       → find_decisions(["G","J"])',
      'python scripts/doha_retrieval.py --verify-case 24-01234 → verify_case("24-01234")',
      'python scripts/court_lookup.py --state IA --offense owi → court_lookup("IA","owi")',
    ].join('\n');
    const gates =
      'The deterministic gates still run on your machine: validate_session.py, assemble_package.py and ' +
      'verify_output.py read the session, so they cannot be hosted. verify_output.py may check citations through ' +
      'verify_case when no library is on disk.';
    const noShell =
      "If you cannot run scripts here, say so in the user's first interaction and again at handoff: \"I could not run " +
      'the verification script here. Before you use this, run it yourself from a checkout of the tool, or treat every ' +
      'citation as unchecked." Point the user at the local tool. There is no hosted verify_package and there never will be.';
    const common = (lines) =>
      [
        `HOSTED MODE (${MODE_1B.name}). This prompt is served verbatim from the Adverse Information Assistant release ` +
          `(corpus ${manifest.corpus_version}, library ${manifest.library_release}, commit ${manifest.repo_commit}) by ${ENDPOINT}. ` +
          'The reference layer is a read-only MCP server; the session, every judgement and every gate stay in this client.',
        ...lines,
      ].join('\n\n');
    return [
      {
        name: 'conductor',
        file: 'agents/conductor.md',
        description: 'The session conductor, with the Mode 1b disclosure, the script-to-tool table and the gates rule.',
        arguments: [{ name: 'client_can_run_scripts', description: 'yes or no: whether this client can run the Python gates. Selects preamble text only.', required: false, enum: ['yes', 'no'] }],
        preamble: (a) =>
          common([
            `Stage 1 disclosure for this mode, said before anything is collected: "${MODE_1B.disclosure}"`,
            'Where the conductor says to run a script that reads reference material, call the tool instead:\n\n' + table,
            gates,
            ...(a.client_can_run_scripts === 'no' ? [noShell] : []),
          ]),
      },
      {
        name: 'intake',
        file: 'agents/core/intake.md',
        description: 'Intake, with stage 0 reading get_release instead of the two check scripts.',
        arguments: [],
        preamble: () =>
          common([
            'Stage 0: call get_release instead of check_corpus.py and check_library.py, and relay what it says — the library release and approval, which directive sections are present, the decision counts, the verified and unverified file counts, and the 32 CFR §117.8 availability. Say plainly what is unavailable.',
            noShell,
          ]),
      },
      { name: 'triage', file: 'agents/core/triage.md', description: 'Triage.', arguments: [], preamble: () => common([]) },
      {
        name: 'requirements-advisor',
        file: 'agents/core/requirements-advisor.md',
        description: 'Requirements advisor, with the corpus reads and directive lookups as tools.',
        arguments: [{ name: 'population', description: 'industry, federal_civilian, military, applicant or in_process. Selects preamble text only.', required: false, enum: POPULATIONS }],
        preamble: (a) =>
          common([
            "Corpus reads: get_reporting_tables(population, access, event_ids?) for authority-layers, the tables and channels; list_event_types() for the closed set of entry ids. Lookups: get_reporting_requirements(access) for SEAD 3, get_isl_section(table | verifies) for the letter's own words, get_cfr_section(\"117.8\") for the NISPOM reporting rule — when it returns \"unavailable\", say the regulation text cannot be quoted and return consult_fso for that obligation.",
            ...(a.population ? [`This session's population is ${a.population}; request that channel family and no other.`] : []),
          ]),
      },
      {
        name: 'classifier',
        file: 'agents/core/classifier.md',
        description: 'Classifier, quoting through get_guideline_text.',
        arguments: [],
        preamble: () => common(['Guideline text: get_guideline_text(letters) returns exactly the sections sead_lookup.py would list, Appendix A included. Read nothing else.']),
      },
      {
        name: 'incident-developer',
        file: 'agents/core/incident-developer.md',
        description: 'Incident developer.',
        arguments: [],
        preamble: () => common(['Read the chronology and profiles through get_corpus_file("incident-chronology") and get_corpus_file("incident-profiles").']),
      },
      {
        name: 'gap-analyst',
        file: 'agents/core/gap-analyst.md',
        description: 'Gap analyst.',
        arguments: [],
        preamble: () => common(['Sources 1–3 through get_checklists(guidelines, event_ids); source 4 through get_form_map(form, sections?); collection-policy and entity-capture come with the form map.']),
      },
      {
        name: 'interviewer',
        file: 'agents/core/interviewer.md',
        description: 'Interviewer.',
        arguments: [],
        preamble: () => common(['Depth: get_severity_ladder(guideline). Privacy tiers, plausibility and entity capture: get_corpus_file.']),
      },
      { name: 'thread-detector', file: 'agents/core/thread-detector.md', description: 'Thread detector.', arguments: [], preamble: () => common([]) },
      {
        name: 'narrative-writer',
        file: 'agents/core/narrative-writer.md',
        description: 'Narrative writer.',
        arguments: [],
        preamble: () => common(['When quoting a guideline, use get_guideline_text and quote only what it returned.']),
      },
      {
        name: 'precedent-miner',
        file: 'agents/optional/precedent-miner.md',
        description: 'Precedent question miner, over the decision shards.',
        arguments: [],
        preamble: () =>
          common([
            'The retired corpus/doha/index.json step is replaced: call find_decisions(guidelines) for a balanced sample, then get_decision_text(decision_id, part_from, part_to) for at most five of them. Every case you reference internally must come from those results; never recall a decision from memory. An empty result is a valid result.',
          ]),
      },
      { name: 'answer-integrator', file: 'agents/optional/answer-integrator.md', description: 'Answer integrator.', arguments: [], preamble: () => common([]) },
      {
        name: 'consistency-checker',
        file: 'agents/optional/consistency-checker.md',
        description: 'Consistency checker.',
        arguments: [],
        preamble: () => common(['Plausibility checks: get_corpus_file("plausibility").']),
      },
      { name: 'candor-reviewer', file: 'agents/optional/candor-reviewer.md', description: 'Candor reviewer.', arguments: [], preamble: () => common([]) },
      {
        name: 'documents-advisor',
        file: 'agents/optional/documents-advisor.md',
        description: 'Documents advisor.',
        arguments: [],
        preamble: () =>
          common([
            'Baseline documents per guideline, with obtain_by: get_corpus_file(adjudicative-readiness); how each is requested or replaced: get_corpus_file(document-retrieval). Document weight: get_document_evidence(guidelines). Court recognition: court_lookup(state, offense?) — compose the nudge from unit_label and the court names; the county stays in the client. Its records_sources carry the state\'s other custodians; the national list is get_corpus_file(state-records-sources).',
          ]),
      },
      {
        name: 'entity-resolver',
        file: 'agents/optional/entity-resolver.md',
        description: 'Entity resolver. The hosted server does not search.',
        arguments: [],
        preamble: () =>
          common([
            'The hosted server does NOT search and makes no outbound request. Your own consent-gated client-side web search for a business address is unchanged, and it is still the only network privilege in this tool.',
          ]),
      },
    ];
  }

  const prompts = PROMPTS.map((p) => ({
    name: p.name,
    description: p.description,
    arguments: p.arguments.map(({ name, description, required }) => ({ name, description, required })),
  }));

  function getPrompt(name, args) {
    const p = PROMPTS.find((x) => x.name === name);
    if (!p) throw new InvalidParams('unknown prompt');
    const spec = Object.fromEntries(p.arguments.map((a) => [a.name, { check: enumOf(a.enum) }]));
    const validated = validate(args, spec);
    const body = release.text(p.file);
    return {
      description: p.description,
      messages: [{ role: 'user', content: { type: 'text', text: `${p.preamble(validated)}\n\n---\n\n${body}` } }],
    };
  }

  // ---- JSON-RPC ----
  const rpcError = (id, code, message) => ({ jsonrpc: '2.0', id, error: { code, message } });

  async function callTool(name, args) {
    const def = toolDefs.find((t) => t.name === name);
    if (!def) throw new InvalidParams('unknown tool');
    const validated = validate(args, def.spec);
    try {
      const output = await def.run(validated);
      return { content: [{ type: 'text', text: JSON.stringify(output, null, 2) }], structuredContent: output, isError: false };
    } catch (err) {
      if (err instanceof InvalidParams) throw err;
      if (err instanceof ToolError) {
        const payload = { error: err.message, ...err.detail };
        return { content: [{ type: 'text', text: JSON.stringify(payload) }], structuredContent: payload, isError: true };
      }
      if (err instanceof ReleaseIntegrityError) {
        const payload = { error: 'a release file failed verification and was not served', file: err.path, reason: err.reason };
        return { content: [{ type: 'text', text: JSON.stringify(payload) }], structuredContent: payload, isError: true };
      }
      throw err;
    }
  }

  async function handleRpcMessage(msg) {
    if (!isPlainObject(msg) || msg.jsonrpc !== '2.0') {
      return rpcError(isPlainObject(msg) ? msg.id ?? null : null, -32600, 'Invalid Request: expected a JSON-RPC 2.0 object.');
    }
    if (msg.id === undefined) return null; // notification
    const { id, method, params = {} } = msg;
    try {
      switch (method) {
        case 'initialize': {
          const requested = params?.protocolVersion;
          return {
            jsonrpc: '2.0',
            id,
            result: {
              protocolVersion: MCP_PROTOCOL_VERSIONS.includes(requested) ? requested : MCP_PROTOCOL_VERSIONS[0],
              capabilities: { tools: { listChanged: false }, resources: { subscribe: false, listChanged: false }, prompts: { listChanged: false } },
              serverInfo: SERVER_INFO,
              instructions: STANDING_RULES.join(' '),
            },
          };
        }
        case 'ping':
          return { jsonrpc: '2.0', id, result: {} };
        case 'tools/list':
          return { jsonrpc: '2.0', id, result: { tools } };
        case 'tools/call': {
          if (typeof params?.name !== 'string') return rpcError(id, -32602, 'tools/call requires a string "name".');
          try {
            return { jsonrpc: '2.0', id, result: await callTool(params.name, params.arguments) };
          } catch (err) {
            if (err instanceof InvalidParams) return rpcError(id, err.code, err.message);
            throw err;
          }
        }
        case 'resources/list':
          return { jsonrpc: '2.0', id, result: { resources } };
        case 'resources/templates/list':
          return { jsonrpc: '2.0', id, result: { resourceTemplates: [] } };
        case 'resources/read': {
          if (typeof params?.uri !== 'string') return rpcError(id, -32602, 'resources/read requires a string "uri".');
          let data;
          try {
            data = readResource(params.uri);
          } catch (err) {
            if (err instanceof ReleaseIntegrityError) return rpcError(id, -32002, `Resource unavailable: ${err.path} failed verification (${err.reason}).`);
            throw err;
          }
          if (!data) return rpcError(id, -32002, 'Resource not found.');
          return { jsonrpc: '2.0', id, result: { contents: [{ uri: params.uri, mimeType: data.mimeType, text: data.text }] } };
        }
        case 'prompts/list':
          return { jsonrpc: '2.0', id, result: { prompts } };
        case 'prompts/get': {
          if (typeof params?.name !== 'string') return rpcError(id, -32602, 'prompts/get requires a string "name".');
          try {
            return { jsonrpc: '2.0', id, result: getPrompt(params.name, params.arguments) };
          } catch (err) {
            if (err instanceof InvalidParams) return rpcError(id, err.code, err.message);
            if (err instanceof ReleaseIntegrityError) return rpcError(id, -32002, `Prompt unavailable: ${err.path} failed verification (${err.reason}).`);
            throw err;
          }
        }
        default:
          return rpcError(id, -32601, 'Method not found.');
      }
    } catch {
      // Never surface an internal message: it could carry a bound parameter.
      return rpcError(id, -32603, 'Internal error.');
    }
  }

  async function handleMessage(payload) {
    if (Array.isArray(payload)) {
      if (payload.length === 0) return rpcError(null, -32600, 'Invalid Request: empty batch.');
      if (payload.length > MAX_BATCH) return rpcError(null, -32600, `Invalid Request: batch exceeds ${MAX_BATCH} messages.`);
      const responses = (await Promise.all(payload.map((item) => handleRpcMessage(item)))).filter(Boolean);
      return responses.length ? responses : null;
    }
    return handleRpcMessage(payload);
  }

  return {
    serverInfo: SERVER_INFO,
    tools,
    resources,
    prompts,
    handleMessage,
    callTool,
    readResource,
    getPrompt,
    eventIds: EVENT_IDS,
    states: STATES,
    formSections: FORM_SECTIONS,
  };
}
