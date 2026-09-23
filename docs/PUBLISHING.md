# Public release checklist

The repository is structured for an initial `0.1.0` public release. Complete this checklist immediately before pushing the public tag.

## Repository settings

- Confirm the canonical repository URL in `CITATION.cff` and `package.json`.
- Set the description to the first sentence of `README.md`.
- Suggested topics: `vision-language-model`, `latency`, `apple-silicon`, `computer-vision`, `reproducible-research`.
- Enable Issues, private vulnerability reporting, and branch protection for `main`.
- Require the CI workflow before merge.

## Clean-checkout verification

```bash
git clone <final-repository-url> release-check
cd release-check
corepack enable
pnpm install --frozen-lockfile
pnpm check
```

Then configure `GLANCE_CORE`, reproduce at least one browser suite and one model suite, and verify the live UI at <http://127.0.0.1:8787>.

## Privacy and artifact audit

```bash
rg -n '/Users/|Documents/Codex|api[_-]?key|HF_TOKEN|sk-[A-Za-z0-9]' \
  -g '!node_modules/**' -g '!dist/**' -g '!.git/**' -g '!docs/PUBLISHING.md' .
git status --ignored --short research/runs
```

Inspect every committed JSON file. Confirm there are no camera frames, base64 image payloads, credentials, machine-specific absolute paths, or personal identifiers beyond the named author and citation metadata.

## Paper audit

- Verify every quantitative claim using `paper/ARTIFACTS.md`.
- Preserve failed guardrails and limitations.
- Do not promote the operational smoke tests into preregistered evidence.
- Freeze the Speedlab tag, Glance commit, model revisions, and environment versions.
- Add an archival identifier or DOI to `CITATION.cff` if one becomes available.

## Release

```bash
git tag -s v0.1.0 -m "Glance Speedlab v0.1.0"
git push origin main --follow-tags
```

Attach the paper draft, aggregate result artifacts, and a short release note based on `CHANGELOG.md`. Do not attach raw camera or ignored run data.
