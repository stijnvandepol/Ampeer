# Ampeer frontend

A statically exported Next.js site. There is no Node process in production: the
browser talks to the advice API directly, `next.config.ts` sets
`output: "export"`, and what ships is the contents of `out/`.

Read `CLAUDE.md` in this directory before changing anything here. It holds the
five rules the advice page exists to keep, and they are product rules rather
than style preferences.

## Running it

pnpm, not npm. The version is pinned in `package.json` by a sha512 digest, so
`corepack enable` fetches exactly one build of it and verifies the tarball
before running it.

```bash
corepack enable
pnpm install --frozen-lockfile
pnpm dev
```

There is no `pnpm start`. `pnpm build` writes `out/`, and `pnpm e2e` serves that
directory rather than a dev server, because a dev server behaves differently
enough that testing it proves less than it looks.

## The gates

| command                                  | what it is                                                                  | CI job             |
| ---------------------------------------- | --------------------------------------------------------------------------- | ------------------ |
| `pnpm lint`                              | eslint                                                                      | `frontend-quality` |
| `pnpm typecheck`                         | `next typegen` then `tsc --noEmit`, strict, with `noUncheckedIndexedAccess` | `frontend-quality` |
| `pnpm test`                              | vitest with coverage, against four thresholds                               | `frontend-test`    |
| `pnpm build`                             | the static export                                                           | `frontend-test`    |
| `pnpm e2e`                               | playwright against the built output                                         | `frontend-test`    |
| `pnpm audit --audit-level low`           | every advisory at any severity                                              | `dependencies`     |
| `semgrep --config .semgrep/frontend.yml` | the repository's own ruleset                                                | `sast`             |

All four job names are required status checks in the `main` ruleset. They are an
interface with `scripts/setup_rulesets.sh`; renaming one produces a pull request
that waits forever for a check that never arrives.

The coverage thresholds in `vitest.config.ts` may rise and may never fall.
`tests/test_pipeline_contract.py` enforces that, the same way it enforces the
Python floor, so lowering a number there is a red build rather than a
configuration change nobody reviewed.

## Two things that go wrong silently

**Amounts are strings and stay strings.** JSON has floats and no decimals, so an
amount that goes through a JSON number is rounded by whichever parser touches it
last. `components/band/position.ts` is the one place that parses one, and what
it produces is a CSS offset that never reaches the screen as a number. There is
a semgrep rule on the rest. On the API side,
`tests/test_frontend_contract.py::test_every_amount_on_the_wire_is_machine_parseable`
pins the wire format, because a Dutch-formatted `"1.684,85"` would parse to
`1.684`, which is finite, so that file's guard would never fire and the band
marker would sit on its clamp while the three amounts printed correctly beside
it.

**No Dutch advice text in this source tree.** `title`, `text`,
`confidence_label`, `basis_text`, `varied_text`, `pinned_text` and
`production_source_text` come from the API, which is the language boundary. The
frontend writes navigation, form labels and messages about the request, and
nothing else.

That rule is checked twice, in `e2e/language.spec.ts`, by two checks that read no
words. The first walks `src/**` with the TypeScript compiler API, collects every
string that can reach a DOM text node or an accessible name, and compares the
sorted set against `tests/ui-strings.txt`. The second serves the advice page a
response whose Dutch fields have all been replaced by sentinels, opens every
disclosure, and asserts both that every sentinel appears exactly once and that
what is left over contains no letters the allowlist does not account for.

Regenerating the allowlist is deliberate:

```bash
UPDATE_UI_STRINGS=1 pnpm e2e language
```

That run rewrites the file and then fails, so a regeneration can never be the
thing that made a build green. Read the diff, and read the header of the file
before adding a line to it.

## The seam with the API

`src/lib/types.ts` is the response shape and four lanes read it. It is checked
from the Python side, in `tests/test_frontend_contract.py`, against what the
renderer actually produces: every key at every depth, the length and shape of
every list, the union members against the Python enums, and the fixture in
`tests/fixtures/advice-response.json` against a payload built by the real code.

Regenerate that fixture, never edit it:

```bash
uv run --no-sync python tests/helpers/advice_fixture.py
```
