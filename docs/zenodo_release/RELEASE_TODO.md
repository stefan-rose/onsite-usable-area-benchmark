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
- [ ] Code citation is the GitHub repo; no code DOI (decided 2026-11-12). Steps:
      - push the local commits;
      - create tag v1.0.0 and bump CITATION.cff (version/date);
      - add the commit hash to README/CODEBOOK;
      - the metadata already points to /tree/v1.0.0.
      Optional: attach `git archive v1.0.0` as a zip to this Zenodo record, so the code is
      also preserved under the dataset DOI.
- [ ] OEDI wind submission URL/DOI: README, CODEBOOK, `TODO-OEDI-wind-URL-or-DOI`.
- [ ] OEDI 8319: confirm the 90 m solar composites (Open/Reference/Limited) are
      posted. If NLR mints a DOI, switch the 8319 identifier to it.
- [ ] Reconcile the M-FIND v1.1 count: 87 CONUS obs_ids are not in the universe,
      but the paper footnote says 85 records / 84 parcels (CODEBOOK note).
- [ ] Versions and access dates for the federal layers (CODEBOOK provenance).
- [ ] `publication_date`. Then reserve the Zenodo DOI, put it in README
      "Citation" and in manuscript Data Availability, and rebuild with script 14.

Non-blocking:
- [ ] Consider whether `zenodo_metadata.json` should list M-FIND co-authors as
      contributors.
