# Zenodo dataset release — pre-upload checklist (not uploaded)

The `TODO-*` strings in `zenodo_metadata.json` are deliberately invalid so a
Zenodo API upload fails until each is filled in or removed.

Blocking items:
- [ ] LightBox DUA check. Confirm that LightBox permits per-parcel derived values
      keyed to M-FIND obs_id, with no parcel IDs and no geometry. Confirm
      that revPJ aggregates are allowed. Per-parcel revPJ stays out
      (`--include-revpj` stays off) unless the DUA allows it.
- [ ] PNNL/NLR release clearance.
- [ ] Paper DOI: README, CODEBOOK header, `TODO-paper-DOI`.
- [ ] Code release DOI (tag + Zenodo GitHub integration): README, CODEBOOK, `TODO-code-DOI`.
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
