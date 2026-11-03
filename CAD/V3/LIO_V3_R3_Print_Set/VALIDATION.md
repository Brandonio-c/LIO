# R3 validation record

These checks apply to the exact default master and meshes in this package. They are not evidence of a physical build.

## Results

* **32 full STL render outputs passed**: 19 individual production part types, 5 test/coupon layouts, and all 8 production job layouts.
* Every production output is watertight, has positive volume, and has its expected connected-body count. There are no extra floating solids in these meshes.
* Job counts are **2, 18, 2, 1, 1, 3, 1, 1** in order. Seven core jobs produce 28 installed pieces; the guide tie adds one.
* All 8 layouts lie within a nominal 220 x 220 bed with at least **6 mm geometric edge margin** before brims/purge paths, and every component starts at Z=0.
* The minimum separation of conservative convex projected footprints in the multi-part jobs is approximately **6.11 mm**. This is not permission to add arbitrary wide brims.
* **60 specified nominal intersection cases** showed no positive-volume interference after expected contact resolution. These include the retained base, merged adapter, door seating/removal, shroud at four heights, raised-cup withdrawal, optical retainer, LED package examples, guide/nut/bearing fits and example door screws.
* The full assembly F5 preview normalized to **751 CSG elements**, rather than the old normalization failure.
* The retained base source was checked for exact equality to the supplied V2 base after accounting for omission of the already-existing loose feet.

## Contact surfaces are not printable solids

Six raw boolean intersection exports triggered non-manifold warnings because they contained **only intentional coplanar seating surfaces**, not a three-dimensional part. Each was independently checked by vertex-plane analysis at its expected contact plane (deviation below 0.00001 mm and zero thickness). Raw results remain in `nominal_interference_checks.json`; resolutions are in `resolved_interference_checks.json`.

This does **not** excuse non-manifold production meshes. All of the actual individual-part and print-layout STLs passed their own watertightness checks. The zero-thickness intersection meshes are excluded from the package's printable STL folders.

## What was not established

Printer dimensional bias, full-height warping, bearing and insert fit, actual LED packages, cup size, motor torque, screw thread identity, axial load capability, fastening strength, fatigue, thermal behavior, homing/limits, power-loss behavior, opacity, light leakage and optical calibration remain unverified. Do not power a loaded Z stage from CAD evidence alone.

The 60 checks are the explicitly recorded cases, not a proof covering every possible parameter change or hardware item. The rod/screw endpoints are still examples. Face-contact geometry can flicker in F5; consult F6 and the actual STL.

## Reproduction

Optional Python checks require `numpy`, `trimesh` and `shapely`, plus OpenSCAD on PATH. `rerender_meshes.py` regenerates mesh records; `rerun_interference.py` reconstructs the specified native-CSG intersections. Run `resolve_contact_surfaces.py` after that to classify the expected contact surfaces. Interference SCADs are tests, not production prints. Local paths are relative to this extracted folder.

The supplied nominal model was checked with OpenSCAD 2021.01. Hashes in `FILE_HASHES.json` identify the delivered CAD and meshes.
