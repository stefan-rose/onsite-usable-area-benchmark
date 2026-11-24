# Exemplar parcel boundary (Figure 1)

`ogrip_39037_F27230906010110101.geojson` is the boundary of the
exemplar parcel used in the methods-conceptual figure
(`scripts/build_fig1_conceptual.py`). It is M-FIND v1.1 facility
`2n60pgp73g`, Darke County, Ohio.

- **Source.** Ohio Geographically Referenced Information Program
  (OGRIP), Ohio Statewide Parcels, feature service
  `OhioStatewidePacels_full_view`, layer 0 (ArcGIS item
  `26ab5fad8d5d4258a7492a14de83bc0e`, "Ohio Statewide Parcels Public
  View").
- **Query.** `LocalParcelID = 'F27230906010110101'`, output in
  CRS84. Downloaded 2026-11-20. Only the fields LocalParcelID,
  StateParcelID, StateLUC, LandArea, CurrentTo and County are kept.
  No owner fields are kept.
- **Terms.** OGRIP states the data are available for public use at
  the user's own risk and are provided as is.
- **Match to the analysis geometry.** The licensed parcel polygon used
  in the pipeline is not redistributed. This open boundary matches it
  (IoU 0.995; vertices within 1.3 m; 78.79 ac in EPSG:5070). The same
  39 reV cell centres fall inside both polygons, so cell-centre zonal
  means on this file reproduce the pipeline reV values. NLCD class
  acres come from the pipeline (Google Earth Engine), not this file.
- **Note.** The polygon has one interior ring of 0.0006 ac, a
  digitizing sliver. The figure draws the exterior ring only.

# Neighbouring parcels (graphical abstract, panel 1)

`ogrip_darke_neighbors.geojson`: all OGRIP parcels intersecting the
envelope lon -84.6073 to -84.5683, lat 40.0732 to 40.1032 (same feature
service as above), downloaded 2026-11-24, 382 features before filtering.
Fields kept: LocalParcelID, StateLUC, County (no owner or address fields).
Features with null StateLUC were dropped unless flagged below.

- `in_universe`: True if more than half of the OGRIP polygon's area lies
  inside one of the study's 305,123 licensed parcel polygons (EPSG:5070).
  All 11 licensed parcels in the envelope matched OGRIP polygons covering
  96.5-99.8% of their area. A 0.00 ac sliver inside the exemplar was
  unflagged by hand (area < 0.05 ac). Only this boolean is derived from
  the licensed data; no licensed geometry or attributes are stored.
- `is_exemplar`: LocalParcelID F27230906010110101.
- Note: one in-universe parcel (8.0 ac) is coded "100: Agr-Vacant Land"
  in OGRIP, and others outside the panel view are coded worship (685) and
  residential (511); universe membership comes from the M-FIND facility
  match, not the county land-use code.
