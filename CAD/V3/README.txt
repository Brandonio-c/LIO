LIO V3 R2 - refreshed standalone SCAD download

Open LIO_V3_master.scad in OpenSCAD. No external libraries or assets are required.
This is an unchanged copy of the previous R2 master, under a shorter filename.
The default is part="assembly", z_state="loading".

For printable layouts change part="job" and select job=1 through job=10.
Job 1: hardware/closure coupons
Job 2: carriage
Job 3: guide/nut interfaces
Job 4: base saddle
Job 5: chamber and panel
Job 6: moving shroud
Job 7: optical components
Job 8: axial-support components
Job 9: optional upper guide tie
Job 10: locator, nest, cover

Use part="sample_module" and door_open=true to inspect the open sample enclosure.
Use part="section" or part="exploded" to inspect assembly relationships.
Do NOT slice the assembly as one printed object. The retained V2 motor base is
reference geometry and is not included in the new print layouts.

Status: DEVELOPMENT CAD. Actual screw/nut, bearing, LED, detector board and cup
interfaces remain unverified examples. Verify actual hardware and fit coupons
before large prints. Mechanical strength, fit, optics, and motor-load capability
have not been physically validated.

This reissued file was CSG-compiled and its default OpenCSG assembly preview
rendered successfully in OpenSCAD 2021.01. The preview normalization has 810
elements. That software check is not a production or physical-fit qualification.
