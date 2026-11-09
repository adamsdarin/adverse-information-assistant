// Each tool's read path against the fixture release and synthetic D1 shards.
import { test } from 'node:test';
import assert from 'node:assert/strict';

import { callTool, fixtureServer, makeShardEnv, rpc } from './helpers.mjs';

const vars = { RELEASE_ID: 'synthetic-test-release', CORPUS_VERSION: '0.1.1-scaffold' };

test('get_release reports ids, counts from the shards, sections present and the Mode 1b disclosure', async () => {
  const { server } = await fixtureServer({ env: makeShardEnv(), vars });
  const { isError, out } = await callTool(server, 'get_release', {});
  assert.equal(isError, false);
  assert.equal(out.release.library_release, 'synthetic-test-release');
  assert.equal(out.release.doha_release, 'fixture-shards');
  assert.equal(out.library_approval.approved_by, 'synthetic-fixture');
  assert.equal(out.decisions.shards_available, true);
  assert.deepEqual(out.decisions.counts, { total: 6, parsed: 6, unique_cases: 5, invariant: out.decisions.counts.invariant });
  assert.equal(out.decisions.shards[0].metadata_release_id, 'fixture-meta');
  assert.equal(out.decisions.exclusions.count, 1);
  assert.deepEqual(out.directive_sections['sead-4'].guidelines, [...'ABCDEFGHIJKLM']);
  assert.deepEqual(out.directive_sections['isl-2021-02'].tables, ['1', '2', '3', '4']);
  assert.equal(out.directive_sections['cfr-117'].available, false);
  assert.equal(out.verification.maintainer_verified, 0);
  assert.equal(out.verification.integrity.ok, true);
  assert.equal(out.rate_limit.limit, 60);
  assert.match(out.mode.disclosure, /^Running locally\./);
  assert.equal(out.worker_vars.RELEASE_ID, 'synthetic-test-release');
  assert.equal(out.worker_vars.consistent_with_manifest, true);
  assert.equal(out.tools.length, 17);
  assert.equal(out.prompts.length, 16);
});

test('get_release flags Worker vars that disagree with the manifest', async () => {
  const { server } = await fixtureServer({ vars: { RELEASE_ID: 'some-other-release' } });
  const { out } = await callTool(server, 'get_release', {});
  assert.equal(out.worker_vars.consistent_with_manifest, false);
  assert.equal(out.decisions.shards_available, false);
});

test('get_guideline_text returns the named guidelines plus Appendix A and nothing else', async () => {
  const { server } = await fixtureServer();
  const { isError, out } = await callTool(server, 'get_guideline_text', { guidelines: ['G', 'J'] });
  assert.equal(isError, false);
  assert.deepEqual(
    out.sections.map((s) => s.file),
    [
      'government/sead-4/02_Appendix_A_Introduction_and_Adjudicative_Process.md',
      'government/sead-4/09_Guideline_G_Alcohol_Consumption.md',
      'government/sead-4/12_Guideline_J_Criminal_Conduct.md',
    ],
  );
  assert.ok(out.sections[1].text.includes('FIXTURE GUIDELINE G'));
  assert.ok(!JSON.stringify(out).includes('FIXTURE GUIDELINE L'), 'Guideline L is absent from a G/J matter');
  for (const s of out.sections) {
    assert.equal(s.verified, true);
    assert.equal(s.verified_by, 'custodian-release');
    assert.match(s.sha256, /^[0-9a-f]{64}$/);
  }
  assert.equal(out.release.file_sha256.length, 3);
  assert.equal(out.release.corpus_version, '0.1.1-scaffold');
});

test('get_reporting_requirements applies the additive rule (F + G or F + H, never a ladder)', async () => {
  const { server } = await fixtureServer();
  const ts = (await callTool(server, 'get_reporting_requirements', { access: 'ts_q' })).out.sections.map((s) => s.file);
  assert.deepEqual(ts, [
    'government/sead-3/01_Overview_Policy_and_General_Requirements.md',
    'government/sead-3/02_All_Covered_Individuals.md',
    'government/sead-3/04_Top_Secret_Q_Critical_Special.md',
    'government/sead-3/06_Appendix_A_Required_Data_Elements.md',
  ]);
  const base = (await callTool(server, 'get_reporting_requirements', { access: 'baseline', include_data_elements: false })).out.sections.map((s) => s.file);
  assert.deepEqual(base.slice(2), ['government/sead-3/03_Secret_Confidential_L_Noncritical.md']);
  const na = (await callTool(server, 'get_reporting_requirements', { access: 'not_applicable' })).out.sections.map((s) => s.file);
  assert.equal(na.length, 2);
});

test('get_isl_section selects by table number or by the corpus table it verifies', async () => {
  const { server } = await fixtureServer();
  const byTable = await callTool(server, 'get_isl_section', { table: 4 });
  assert.deepEqual(byTable.out.sections.map((s) => s.file), [
    'government/isl-2021-02/01_Overview_and_Adverse_Information_Guidance.md',
    'government/isl-2021-02/05_Table_4_Foreign_Travel.md',
  ]);
  assert.equal(byTable.out.table.number, 4);
  const byVerifies = await callTool(server, 'get_isl_section', { verifies: 'top-secret-q' });
  assert.equal(byVerifies.out.sections[1].file, 'government/isl-2021-02/04_Table_3_Top_Secret_Q.md');
  const channels = await callTool(server, 'get_isl_section', { verifies: 'channels' });
  assert.equal(channels.isError, true, 'no ISL table backs channels.yaml');
});

test('get_cfr_section fails closed when the library has no Part 117 split', async () => {
  const { server } = await fixtureServer();
  const { isError, out } = await callTool(server, 'get_cfr_section', { section: '117.8' });
  assert.equal(isError, false);
  assert.equal(out.status, 'unavailable');
  assert.match(out.reason, /unsplit/);
  assert.match(out.rule, /consult_fso/);
  assert.equal(out.sections, undefined, 'no slice of the whole Part is ever served');
});

test('get_reporting_tables resolves layers, tables, channel family and flags', async () => {
  const { server } = await fixtureServer();
  const ind = (await callTool(server, 'get_reporting_tables', { population: 'industry', access: 'ts_q', event_ids: ['aci.criminal.arrest'] })).out;
  assert.deepEqual(ind.layers_in_scope, ['sead-3', 'isl-2021-02']);
  assert.deepEqual(ind.tables.map((t) => t.table), ['all-covered-individuals', 'adverse-information', 'top-secret-q']);
  assert.equal(ind.tables.reduce((n, t) => n + t.data.entries.length, 0), 1);
  assert.equal(ind.channels.data.family, 'industry_channels');
  assert.equal(ind.attribution_status, 'needs_maintainer_split');
  for (const t of ind.tables) {
    assert.equal(t.maintainer_verified, false);
    assert.equal(t.citable, false);
    assert.match(t.unverified_note, /consult your security office/);
  }
  const fed = (await callTool(server, 'get_reporting_tables', { population: 'federal_civilian', access: 'baseline' })).out;
  assert.deepEqual(fed.layers_in_scope, ['sead-3']);
  assert.deepEqual(fed.tables.map((t) => t.table), ['all-covered-individuals', 'adverse-information']);
  assert.equal(fed.channels.data.family, 'federal_military_channels');
  const app = (await callTool(server, 'get_reporting_tables', { population: 'in_process', access: 'baseline' })).out;
  assert.equal(app.channels.data.family, 'applicant_channels');
  assert.ok(app.layers_note);
});

test('list_event_types is the closed set event_ids draws from, with the claiming checklist', async () => {
  const { server } = await fixtureServer();
  const { out } = await callTool(server, 'list_event_types', {});
  assert.ok(out.count >= 20);
  assert.deepEqual(out.events.map((e) => e.id).sort(), [...server.eventIds].sort());
  const arrest = out.events.find((e) => e.id === 'aci.criminal.arrest');
  assert.equal(arrest.event_checklist, 'event-arrest');
  assert.equal(arrest.reportable, 'yes');
  assert.ok(out.events.every((e) => e.event_checklist), 'every table entry is claimed by an event checklist');
});

test('get_checklists loads both axes, universal and coverage, and indexes elements by id', async () => {
  const { server } = await fixtureServer();
  const { out } = await callTool(server, 'get_checklists', { guidelines: ['G'], event_ids: ['aci.criminal.arrest'] });
  assert.deepEqual(out.guideline_checklists.map((b) => b.file), ['corpus/checklists/guideline-G.json']);
  assert.deepEqual(out.event_checklists.map((b) => b.file), ['corpus/checklists/events/event-arrest.json']);
  assert.equal(out.universal.file, 'corpus/checklists/_UNIVERSAL.json');
  assert.equal(out.coverage.file, 'corpus/checklists/_COVERAGE.json');
  assert.ok(Object.keys(out.element_index).length > 30);
  assert.ok(out.guidelines_named_by_event_checklists_not_requested.includes('J'));
  const onlyEvents = await callTool(server, 'get_checklists', { event_ids: ['tsq.marriage'] });
  assert.equal(onlyEvents.out.guideline_checklists.length, 0);
  assert.equal(onlyEvents.out.event_checklists.length, 1);
});

test('get_form_map filters to the requested sections and refuses a section another form defines', async () => {
  const { server } = await fixtureServer();
  const sf = (await callTool(server, 'get_form_map', { form: 'sf86', sections: ['22'] })).out;
  assert.deepEqual(Object.keys(sf.map.data.sections), ['22']);
  assert.equal(sf.collection_policy.file, 'corpus/forms/collection-policy.json');
  assert.equal(sf.entity_capture.file, 'corpus/forms/entity-capture.json');
  assert.equal(sf.diss_incident_types, undefined);
  const ir = (await callTool(server, 'get_form_map', { form: 'incident_report' })).out;
  assert.ok(ir.diss_incident_types);
  assert.ok(Object.keys(ir.map.data.fields).includes('event_date'));
  const pvqOnly = server.formSections.pvq.find((s) => !server.formSections.sf86.includes(s));
  const foreign = await callTool(server, 'get_form_map', { form: 'sf86', sections: [pvqOnly] });
  assert.equal(foreign.isError, true);
});

test('get_severity_ladder and get_document_evidence return one guideline at a time', async () => {
  const { server } = await fixtureServer();
  const a = (await callTool(server, 'get_severity_ladder', { guideline: 'A' })).out;
  assert.equal(a.severity.data.ladder.ladder, false);
  assert.ok(Array.isArray(a.severity.data.ladder.fact_dimensions));
  const g = (await callTool(server, 'get_severity_ladder', { guideline: 'G' })).out;
  assert.ok(Array.isArray(g.severity.data.ladder.tiers));
  assert.equal(g.severity.citable, false);
  const docs = (await callTool(server, 'get_document_evidence', { guidelines: ['G', 'F'] })).out;
  assert.deepEqual(Object.keys(docs.documents.data.guidelines), ['G', 'F']);
  assert.ok(docs.documents.data.guidelines.G.documents.length > 0);
});

test('court_lookup serves one state without a county and labels the guess', async () => {
  const { server } = await fixtureServer();
  const { out } = await callTool(server, 'court_lookup', { state: 'NJ', offense: 'dui' });
  assert.equal(out.court.data.state_name, 'New Jersey');
  assert.equal(out.court.data.confidence, 'unverified_guess');
  assert.ok(out.court.data.court_for_offense);
  assert.equal(out.ask_first, 'What court did your case go through?');
  assert.match(out.fallback_if_still_unknown, /clerk of court/);
  assert.match(out.usage_rule, /never this suggestion/);
  const plain = (await callTool(server, 'court_lookup', { state: 'IA' })).out;
  assert.equal(plain.court.data.court_for_offense, null);
  assert.equal(plain.court.data.dui_note, null);
  // The same state's other custodians ride along, labelled unverified, so the
  // documents advisor has the driver-record and tax agencies without a second call.
  assert.equal(plain.records_sources.data.verified, false);
  assert.match(plain.records_sources.data.dmv.url, /^https:\/\//);
  assert.ok(plain.records_sources.data.tax.name);
  assert.equal(plain.records_sources.file, 'corpus/courts/state-records-sources.json');
});

test('get_corpus_file and the corpus resources agree', async () => {
  const { server } = await fixtureServer();
  const { out } = await callTool(server, 'get_corpus_file', { file: 'privacy-tiers' });
  assert.equal(out.file, 'corpus/privacy-tiers.json');
  assert.equal(out.data.default_tier, 'high');
  assert.equal(out.maintainer_verified, false);
  const res = await rpc(server, 'resources/read', { uri: 'adverse://corpus/privacy-tiers' });
  assert.equal(JSON.parse(res.result.contents[0].text).data.default_tier, 'high');
  const preambles = (await callTool(server, 'get_corpus_file', { file: 'pvq-preambles' })).out;
  assert.ok(preambles.data.body_markdown.length > 100);
  // DCSA's adjudicatively-ready standard and the per-state custodian directory
  // ship as standalone files, unverified, with the audience translation intact.
  const readiness = (await callTool(server, 'get_corpus_file', { file: 'adjudicative-readiness' })).out;
  assert.equal(readiness.maintainer_verified, false);
  assert.equal(Object.keys(readiness.data.guidelines).length, 13);
  for (const g of Object.values(readiness.data.guidelines)) {
    for (const d of g.documents) assert.ok(['subject', 'security_office', 'either'].includes(d.obtain_by), d.type);
  }
  const sources = (await callTool(server, 'get_corpus_file', { file: 'state-records-sources' })).out;
  assert.equal(Object.keys(sources.data.states).length, 51);
  assert.ok(sources.data.national.some((n) => n.id === 'irs-transcript'));
  const retrieval = (await callTool(server, 'get_corpus_file', { file: 'document-retrieval' })).out;
  assert.equal(retrieval.maintainer_verified, false);
  assert.ok(Object.keys(retrieval.data.entries).length >= 40);
  assert.deepEqual(retrieval.data.obtainable_by_values, ['subject', 'security_office', 'third_party_only']);
});

test('get_corpus_bundle carries every Government section and maintainer file', async () => {
  const { server, release } = await fixtureServer();
  const { out } = await callTool(server, 'get_corpus_bundle', {});
  assert.equal(out.government['sead-4'].length, 17);
  assert.equal(out.government['sead-3'].length, 6);
  assert.equal(out.government['isl-2021-02'].length, 5);
  assert.equal(out.government['cfr-117'], undefined);
  assert.equal(out.corpus.length, release.manifest.maintainer.files.length);
  assert.ok(JSON.stringify(out).length < 2_000_000);
});

test('find_decisions ranks, alternates outcomes, applies exclusions and the era rule', async () => {
  const { server } = await fixtureServer({ env: makeShardEnv() });
  const g = (await callTool(server, 'find_decisions', { guidelines: ['G'] })).out;
  assert.equal(g.scope, 'POST_SEAD_4');
  assert.equal(g.exclusions_applied, 1);
  const ids = g.cases.map((c) => c.decision_id);
  assert.ok(!ids.includes('90-00009.h1'), 'the answer_eligible:false decision is excluded');
  assert.ok(!ids.includes('90-00003.h1'), 'pre-SEAD 4 decisions are out of the default scope');
  assert.equal(g.cases[0].outcome, 'denied');
  assert.equal(g.cases[1].outcome, 'approved');
  assert.ok(ids.includes('90-00001.h1') && ids.includes('90-00002.h1') && ids.includes('90-00002.a1'));
  assert.equal(g.cases[0].parts, 2);
  assert.match(g.cases[0].source_url, /^https:\/\/doha\.ogc\.osd\.mil\//);
  assert.match(g.reminder, /Never to state a rate/);
  assert.equal(g.release.doha_release, 'fixture-shards');
  const pre = (await callTool(server, 'find_decisions', { guidelines: ['G'], include_pre_sead4: true, limit: 12 })).out;
  assert.ok(pre.cases.map((c) => c.decision_id).includes('90-00003.h1'));
  const j = (await callTool(server, 'find_decisions', { guidelines: ['J'], limit: 1 })).out;
  assert.equal(j.cases.length, 1);
  const none = (await callTool(server, 'find_decisions', { guidelines: ['L'] })).out;
  assert.equal(none.cases.length, 0, 'an empty result is a valid result');
  for (const c of [...g.cases, ...pre.cases]) {
    assert.ok(!('rate' in c) && !('count' in c), 'no rates, no counts by outcome');
  }
});

test('verify_case reports membership and the decisions under a case number', async () => {
  const { server } = await fixtureServer({ env: makeShardEnv() });
  const yes = (await callTool(server, 'verify_case', { case_number: '90-00002' })).out;
  assert.equal(yes.in_library, true);
  assert.deepEqual(yes.decisions.map((d) => d.decision_id), ['90-00002.a1', '90-00002.h1']);
  assert.equal(yes.unique_case_count, 5);
  const no = (await callTool(server, 'verify_case', { case_number: '99-99999' })).out;
  assert.equal(no.in_library, false);
  assert.deepEqual(no.decisions, []);
});

test('get_decision_text pages through parts by rowid, capped at ten per call', async () => {
  const { server } = await fixtureServer({ env: makeShardEnv() });
  const first = (await callTool(server, 'get_decision_text', { decision_id: '90-00004.h1' })).out;
  assert.equal(first.parts_total, 12);
  assert.equal(first.part_from, 1);
  assert.equal(first.part_to, 10);
  assert.equal(first.passages.length, 10);
  assert.equal(first.passages[0].text, 'SYNTHETIC passage 1 of 90-00004.h1.');
  assert.equal(first.passages[9].part, 10);
  const rest = (await callTool(server, 'get_decision_text', { decision_id: '90-00004.h1', part_from: 11, part_to: 12 })).out;
  assert.deepEqual(rest.passages.map((p) => p.part), [11, 12]);
  const beyond = await callTool(server, 'get_decision_text', { decision_id: '90-00004.h1', part_from: 20 });
  assert.equal(beyond.isError, true);
  const other = (await callTool(server, 'get_decision_text', { decision_id: '90-00001.h1', part_from: 2, part_to: 2 })).out;
  assert.equal(other.passages.length, 1);
  assert.equal(other.passages[0].text, 'SYNTHETIC passage 2 of 90-00001.h1.');
  const missing = await callTool(server, 'get_decision_text', { decision_id: '99-99999.h1' });
  assert.equal(missing.isError, true);
});

test('decision tools fail closed without shards', async () => {
  const { server } = await fixtureServer();
  for (const [name, args] of [
    ['find_decisions', { guidelines: ['G'] }],
    ['verify_case', { case_number: '90-00001' }],
    ['get_decision_text', { decision_id: '90-00001.h1' }],
  ]) {
    const res = await callTool(server, name, args);
    assert.equal(res.isError, true, name);
    assert.match(res.out.error, /not bound/);
  }
});

test('resources: three families, all readable', async () => {
  const { server } = await fixtureServer();
  const list = (await rpc(server, 'resources/list')).result.resources;
  assert.ok(list.some((r) => r.uri === 'adverse://release'));
  assert.equal(list.filter((r) => r.uri.startsWith('adverse://corpus/')).length, 13);
  assert.equal(list.filter((r) => r.uri.startsWith('adverse://government/')).length, 17 + 6 + 5);
  for (const r of list) {
    const read = await rpc(server, 'resources/read', { uri: r.uri });
    assert.ok(read.result, r.uri);
    assert.equal(read.result.contents[0].mimeType, r.mimeType, r.uri);
  }
  const manifest = JSON.parse((await rpc(server, 'resources/read', { uri: 'adverse://release' })).result.contents[0].text);
  assert.equal(manifest.library_release, 'synthetic-test-release');
  const g = (await rpc(server, 'resources/read', { uri: 'adverse://government/sead-4/09_Guideline_G_Alcohol_Consumption' })).result.contents[0].text;
  assert.ok(g.includes('FIXTURE GUIDELINE G'));
});

test('prompts: the sixteen agents, verbatim, behind a hosted-mode preamble', async () => {
  const { server, release } = await fixtureServer();
  const list = (await rpc(server, 'prompts/list')).result.prompts.map((p) => p.name);
  assert.deepEqual(list, [
    'conductor', 'intake', 'triage', 'requirements-advisor', 'classifier', 'incident-developer', 'gap-analyst',
    'interviewer', 'thread-detector', 'narrative-writer', 'precedent-miner', 'answer-integrator',
    'consistency-checker', 'candor-reviewer', 'documents-advisor', 'entity-resolver',
  ]);
  const conductor = (await rpc(server, 'prompts/get', { name: 'conductor', arguments: { client_can_run_scripts: 'no' } })).result;
  const text = conductor.messages[0].content.text;
  assert.ok(text.startsWith('HOSTED MODE (Mode 1b'));
  assert.ok(text.includes('Running locally. Nothing you type is stored'));
  assert.ok(text.includes('→ get_guideline_text(["G","J"])'));
  assert.ok(text.includes('I could not run the verification script here'));
  assert.ok(text.endsWith('---\n\n' + release.text('agents/conductor.md')), 'the agent body is served verbatim');
  const withShell = (await rpc(server, 'prompts/get', { name: 'conductor', arguments: { client_can_run_scripts: 'yes' } })).result.messages[0].content.text;
  assert.ok(!withShell.includes('I could not run the verification script here'));
  const miner = (await rpc(server, 'prompts/get', { name: 'precedent-miner' })).result.messages[0].content.text;
  assert.ok(miner.includes('find_decisions') && miner.includes('get_decision_text'));
  assert.ok(miner.endsWith(release.text('agents/optional/precedent-miner.md')));
  const resolver = (await rpc(server, 'prompts/get', { name: 'entity-resolver' })).result.messages[0].content.text;
  assert.ok(resolver.includes('does NOT search'));
});
