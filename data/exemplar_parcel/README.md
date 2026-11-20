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
