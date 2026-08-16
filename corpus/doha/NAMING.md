# DOHA case file naming convention

## Format

```
ISCR-<case-number>_<GUIDELINES>_<outcome>_<level>.md
```

| Segment | Values | Notes |
|---|---|---|
| `case-number` | e.g. `24-01234` | From the published decision. Hyphens only. |
| `GUIDELINES` | `A`–`M`, **uppercase**, alphabetized, no separator | The **adjudicated** guidelines — the ones the judge actually analyzed. `GJ`, not `JG`. |
| `outcome` | `granted` \| `denied` \| `remanded` | **lowercase** |
| `level` | `hearing` \| `appeal` | **lowercase** |

Examples:

```
ISCR-24-01234_GJ_denied_hearing.md
ISCR-23-00456_F_granted_hearing.md
ISCR-22-00789_BC_granted_appeal.md
ISCR-24-02001_EFJ_denied_appeal.md
```

## Why the tags are in the filename

So a guideline's relevant cases can be found without opening a single file.
`index.json` is faster still (one read instead of a directory walk) but it is
*generated* — it goes stale the moment someone adds a case and forgets to
rebuild. The filename cannot go stale, because it *is* the file.

Both exist on purpose, and `validate_corpus.py` **fails the build if they
disagree**. A rename that changes a tag is caught, not silently obeyed.

## Adjudicated, not alleged

If an SOR alleged Guidelines E, F, G, and J but the judge only reasoned
through F and J, the filename carries `FJ`. The adjudicated set is what makes
a case useful as a source of interview questions — it's where the judge
actually said what mattered. Keep the alleged set in frontmatter
(`alleged_guidelines`) if you want it later; it does not drive retrieval.

## Case-sensitivity warning

Guidelines are uppercase and outcome/level are lowercase specifically so a
naive glob for `G` doesn't also match `granted`. That protection depends on a
case-sensitive filesystem — it holds on Linux and fails silently on a default
macOS volume.

**Do not rely on shell globs for retrieval.** Use:

```bash
python scripts/find_cases.py --guideline G --outcome denied
python scripts/find_cases.py --guideline G --guideline J --any
```

which reads the validated index and is correct everywhere. Globs are for
humans browsing the folder.

## Renaming an existing file

Change the frontmatter and the filename in the same commit, then run:

```bash
python scripts/build_index.py && python scripts/validate_corpus.py
```
