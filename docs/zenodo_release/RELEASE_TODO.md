# Zenodo dataset release — pre-upload checklist (not uploaded)

The `TODO-*` strings in `zenodo_metadata.json` are deliberately invalid so a
Zenodo API upload fails until each is filled in or removed.

Blocking items:
- [x] LightBox DUA (confirmed by Stefan, 2026-11-12). Results without geometry can be reported,
      and this extends to summarized revPJ totals. Per-parcel revPJ stays out (`--include-revpj` off).
- [ ] PNNL clearance (Stefan is requesting it). Send the outputs/zenodo_release/v1.0/ contents.
- [ ] NLR sign-off if needed: the release includes reV-derived values and revPJ aggregates.
- [ ] Sequence: upload BEFORE paper submission. Steps:
      - after clearance, reserve the Zenodo DOI;
      - cite it in the manuscript Data Availability;
      - publish.
      The paper DOI is NOT needed to upload. Add it after publication with a metadata-only edit
      (related identifier `isSupplementTo`, plus README/CODEBOOK text) or as v1.1.
- [ ] Code citation is the GitHub repo URL (main branch); no code DOI and no release tag
      (decided 2026-11-12; tag dropped 2026-11-18). Reproduction instructions live in
      docs/ZENODO_RELEASE.md, which README.txt and CODEBOOK.txt point to. Steps:
      - commit and push docs/ZENODO_RELEASE.md, scripts/validation/verify_zenodo_release.py,
        the pixi tasks and the script 03 output-folder fix before the files go out for review
        (otherwise the links in README.txt/CODEBOOK.txt 404).
      Note: main can change after upload; the Zenodo files then describe an earlier state of
      the code. Optional: attach a `git archive` zip of the uploaded commit to the record.
- [ ] OEDI wind submission URL/DOI: README, CODEBOOK, `TODO-OEDI-wind-URL-or-DOI`.
- [ ] OEDI 8319: confirm the 90 m solar composites (Open/Reference/Limited) are
      posted. If NLR mints a DOI, switch the 8319 identifier to it.
- [ ] Reconcile the M-FIND v1.1 count: 87 CONUS obs_ids are not in the universe,
      but the paper footnote says 85 records / 84 parcels (CODEBOOK note).
- [ ] Versions and access dates for the federal layers (CODEBOOK provenance).
- [ ] `publication_date`.
- [x] Zenodo DOI reserved on the draft record: 10.5281/zenodo.24354306 (2026-11-18).
      Now in README.txt "Citation", repo README, docs/ZENODO_RELEASE.md, PIPELINE.md and
      manuscript Data Availability. Re-upload README.txt and MD5SUMS.txt to the draft.
      The DOI resolves only after publishing (API returned 404 on 2026-11-18).

Non-blocking:
- [ ] Consider whether `zenodo_metadata.json` should list M-FIND co-authors as
      contributors.

## Deferred public-text edits (placeholders removed from README/CODEBOOK on 2026-11-18)

The public files now use neutral wording so they can go out for review. Restore the
specifics below when they become available, then rebuild with script 14 (MD5SUMS changes).

| Where | Current public wording | Fill in when available |
|---|---|---|
| README "This dataset accompanies..." (para 2); CODEBOOK header `Paper:` | "Applied Energy (under review)" | Paper DOI after publication (metadata-only edit or v1.1) |
| README "Inputs" wind bullet; CODEBOOK vars 45-52 note; CODEBOOK provenance | "public release on OEDI pending" | OEDI wind submission URL/DOI |
| CODEBOOK vars 42-44 (solar reV) | cites OEDI 8319 only | Update OEDI file names/DOI once the 90 m composites replace the 92.11 m files |
| CODEBOOK handling notes, M-FIND count | "87 CONUS facility records that are not in this parcel universe" | Reconcile with paper footnote (85 records / 84 parcels); public text and paper currently disagree |
| CODEBOOK provenance summary | federal layers listed without versions | Add release versions and access dates once fixed in paper Section 2 |
