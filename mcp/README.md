# Hosted MCP reference server (`adverse-information-assistant`)

The Cloudflare Worker behind `https://fsotools.ai/adverse/mcp`. Design:
[`../docs/HOSTED-MCP-DESIGN.md`](../docs/HOSTED-MCP-DESIGN.md). Privacy
mode it enables: Mode 1b in [`../DEPLOYMENT.md`](../DEPLOYMENT.md).

It is a **reference service**: it serves directive text, the maintainer-
authored corpus files, the agent prompts and published DOHA decisions, all
selected by categorical keys. It never receives a narrative, keeps no session,
logs nothing and verifies nothing. The local tool does not depend on it;
`tests/run_tests.py` fails if anything under `agents/` or `scripts/` ever
references this folder.

| File | Role |
|---|---|
| `wrangler.jsonc` | Worker config: route, assets binding, three read-only D1 shard bindings, rate limit, observability off |
| `worker.js` | Entry point: loads and verifies the release once per isolate, guide page on `GET` text/html, MCP on `POST` |
| `server.js` | The 17 tools, resources and prompts; input validation against closed enums and patterns; JSON-RPC dispatch |
| `http.js` | Streamable HTTP transport (`cache-control: no-store`, no session id); also a Node dev server |
| `d1.js` | Every D1 statement, all `SELECT`, in one place |
| `release.js` | Loads `release/` and verifies each file's SHA-256 against `manifest.json`; fails closed per file |
| `guide.js` | The connection guide, with `DISCLAIMER.md` verbatim |
| `release/` | **Built, not committed.** Output of `scripts/hosted_release.py` |

## Build, test, run, deploy

```bash
python scripts/hosted_release.py --library "<DCSA Library root>" --dry-run   # rehearse
python scripts/hosted_release.py --library "<DCSA Library root>"             # write mcp/release/
npm run mcp:test                                                             # node --test tests/mcp/
node mcp/http.js --release mcp/release --port 8789                           # reference tools only, no shards
npm install && npm run mcp:worker:dev                                        # wrangler dev with remote D1 (needs a Cloudflare login)
npm run mcp:worker:deploy                                                    # owner's machine only
```

The build refuses an unapproved library release, re-verifies every Government
section against the Archivist's body hashes, converts the `corpus/` YAML to
JSON without touching a `maintainer_verified` flag, derives
`doha-exclusions.json` from the library manifest, and runs
`validate_corpus.py` and `tests/run_tests.py` first. It fetches nothing.
Exit codes: 0 built (or nothing changed), 2 refused, 3 deployed but the live
`get_release` does not report the new ids.

After a shard rebuild by `doha-decision-search`, pass the three new database
names: `--doha-shards <name>-s1,<name>-s2,<name>-s3` (or `name=id` pairs).
Without the flag the existing bindings stay and the script says so.
