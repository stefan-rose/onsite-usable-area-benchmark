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
- [x] OEDI wind release live: submission 11697 (no DOI), 2026-11-18. In README.txt, CODEBOOK,
      metadata, DATA_SOURCES.md, ZENODO_RELEASE.md, manuscript. All 8 OEDI files are
      pixel-identical to the rasters used (CRS, transform, nodata also equal). Add the
      11697 URL as an isDerivedFrom related identifier on the Zenodo draft and re-upload
      README.txt, CODEBOOK.txt, MD5SUMS.txt.
- [ ] OEDI 8319: confirm the 90 m solar composites (Open/Reference/Limited) are
      posted. If NLR mints a DOI, switch the 8319 identifier to it.
- [x] M-FIND count reconciled (2026-11-20). Universe obs_ids == M-FIND v1.1 CONUS by
      zero-padded FIPS (338,904; 0 missing, 0 extra). Both the "87" and the paper's
      "85 / 84" came from the STATE field: blank for 87 AK/HI records, and 2 WA/ID
      records labeled AK (kc4gz401cr, 4qgicqj9ct). CODEBOOK note and paper footnote
      rewritten. Tell the M-FIND team (STATE field fix for v1.2).
- [x] Federal layer versions and access dates in CODEBOOK provenance and DATA_SOURCES.md
      (2026-11-20, from the metadata XMLs and download logs in Data/wind_exclusions/).
- [x] RESOLVED 2026-11-20, option (a): paper reworded to all SUA types (32 CFR 211 rationale,
      R/P-only sensitivity ~1.56 M ac in Sec 3). Was: flag_dod_sua is ALL SUA types, not "DoD restricted" as the paper
      says. Of 13,122 flagged parcels only 735 touch R/P; with an R/P filter the 5-layer
      wind total would be about 1.559 M ac instead of 1.309. Decide: reword the paper or
      re-run. CODEBOOK now describes the data as it is ("polygon of any type").
      Airports similarly include heliports and private-use facilities.
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
| CODEBOOK vars 42-44 (solar reV) | cites OEDI 8319 only | Update OEDI file names/DOI once the 90 m composites replace the 92.11 m files |
