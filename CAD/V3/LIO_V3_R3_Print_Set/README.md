# LIO V3 R3 - bottom-up consolidated print set

**Development CAD with checked nominal geometry. Not a physically qualified production release.**

The working `V2_01_motor_base_v16` is reused. It is embedded, unchanged apart from omission of the loose feet, as an assembly reference only. None of the eight print jobs reprints the motor base.

## 1. Open and export the files

Extract the **entire ZIP** first. Keep the numbered SCAD files next to `LIO_V3_R3_master.scad`. Do not open a launcher from inside a ZIP viewer. All eight launchers select geometry from the same master; there are no external CAD libraries or STL imports.

Open `01_Base_Mount_and_Nest.scad`, for example. F5 shows its print layout; F6 computes the final geometry. Export that layout to STL. Equivalent, already-rendered example STLs are in `STL/`. A layout contains several **separate** solid parts where appropriate; they must not be fused in the slicer.

Use `Assembly_Preview.scad` to understand the installed configuration. **Never print the assembly view:** its metal hardware and retained base are references. Edit `z_state`, `door_open`, or `show_electronics_cover` in the master for inspection. `part="optical_module"` and `part="sample_module"` show those subassemblies. Coincident mating faces can flicker in F5; inspect F6 or the individual STL rather than inferring material from preview colors.

`Single_Part.scad` exports just one replacement component. `00_Fit_Tests.scad` selects one test layout at a time. For command-line exports use the master's existing `part` parameter, for example:

```sh
openscad --export-format binstl -D 'part="door"' -o door.stl LIO_V3_R3_master.scad
```

Edit dimensions **only in the master**. After any dimensional change, regenerate all affected STLs and repeat the mating/layout checks. Supplied STLs reflect the supplied default parameters, not future edits.

## 2. Exact new printed-piece list

| Order / file | Contents | Quantity |
|---|---|---:|
| 01_Base_Mount_and_Nest.scad | One integrated base locator/saddle; one removable cup nest | 2 |
| 02_Motion_Interfaces.scad | 2 axial bridges, 2 axial caps, 4 spacers, 4 guide housings, 4 guide caps, 2 nut carriers | 18 |
| 03_Chamber_and_Door.scad | Stationary chamber and removable metal-fastened panel | 2 |
| 04_Carriage.scad | Moving top carriage | 1 |
| 05_Shroud.scad | Separate moving light shroud | 1 |
| 06_Optical_Head.scad | Integrated 16-seat deck, shared LED retainer, detector mount/light tube | 3 |
| 07_Electronics_Cover.scad | Opaque removable electronics cover | 1 |
| 08_Upper_Guide_Tie.scad | Independent upper rod tie, conditional on frame qualification | 1 |

**28 core pieces; 29 with the guide tie.** Coupons, spares, seals, bought hardware and future switch/controller mounts are not in that total. The final electronics and limit-switch inventory is not specified by this CAD.

In Job 02 the four guide housings, left to right in the source layout, are: primary/locating, X-accommodating, XY-accommodating, XY-accommodating. Keep them identified. Two caps at the upper right are axial caps, not guide caps. See the job preview.

## 3. What is implemented differently from R2

* The old locator and saddle are **one connected base adapter**. Their inter-part pins/holes are removed. Installed heights and anchor coordinates are unchanged. Print it inverted: broad saddle face against the bed, locating ring upward.
* The deck contains **16 actual angled, stepped LED seats**, not empty rectangular insert apertures. There are no separate LED inserts in the installed bill.
* The new shared retainer captures the **LED package flanges**. Its 4.2 mm example lead holes are smaller than the 6.2 mm example flanges. Tilted underside pockets clear the package backs; an asymmetric four-hole mounting pattern prevents the retainer being indexed by the wrong quarter turn.
* The port's clear rectangular height is **50 mm rather than R2's 45 mm**. This permits the example cup to lift 5 mm over the 4 mm nest rim before withdrawal, with additional vertical room. The 60 mm width and chamfered crown remain. This is a deliberate new design adjustment, not a recovered hardware dimension.
* All eight jobs are renumbered in the requested bottom-up order. **R2 numeric job meanings no longer apply.**

No printed screws, threads, hooks or bayonets are included. Door closure uses manufactured screws and verified inserts.

## 4. Frozen base datums and new nominal interfaces

| Interface | R3 value |
|---|---|
| Coordinate origin | Optical axis; Z=0 at underside of retained base; front is -Y |
| Guide axes | (X,Y)=(+/-78,+/-55) mm |
| Drive/output axes | (X,Y)=(+/-74,0) mm |
| Base frame anchors | (X,Y)=(+/-98,+/-42) mm; nominal top Z=17 |
| Base recess | Diameter 92 mm, depth 0.8 mm |
| Integrated adapter | Pilot diameter 91.4; pilot bottom Z=9.3; saddle Z=17..23 |
| Fixed chamber | 107 OD / 100 ID / 140 high; world Z=23..163 |
| Shroud | 110 ID / 115 OD; 130 long below deck underside |
| Nominal running clearance | 1.5 mm radial; a design gap, not a printer accuracy claim |
| Low tube edge | Z=55; 2 mm above the existing collar tops at Z=53 |
| Carriage | 200 x 160 x 8; opening diameter 118 |
| Head interface | 117 pilot; 122 main flange; diagonal ears; M4 x4 on radius 66 |
| LED geometry | 16 seats, 22.5-degree spacing, radius 35; example tilt about 14.23 degrees |
| Deck / retainer | 10 mm deck; 3 mm retainer |

All new mating features share parameters and transformations. Do not mix R3 optical parts with the rejected V2 140 mm flange/126 mm bolt-circle parts.

With the **unverified example rod/thread endpoints**, deck underside low/mid/high/loading positions are 185/219/253/267 mm. Tube bottoms are 55/89/123/137 mm. Corresponding wall overlaps are 108/74/40/26 mm. Loading is **not** a measurement position under the provisional 40 mm overlap rule. Actual guide/thread limits and optical qualification can shorten the range.

The 115 mm tube must never descend into the retained base collars. Its apparent radial clearance to the motor bodies alone is not a valid collision check.

## 5. Hardware dimensions still requiring verification

`HARDWARE_INTERFACES.json` records the example profile and the measurements needed to replace it. The key unresolved items are:

| Item | Example only - NOT verified inventory |
|---|---|
| Screw | 8 mm visual envelope; no thread form/lead inferred |
| Lead nut | 10 mm barrel, 22 mm flange, 15 mm total height, 16 mm four-hole bolt circle |
| Guide bearing | 12 mm OD x 20 mm long for an 8 mm rod |
| Axial bearing | 8 ID / 22 OD / 7 wide; actual axial rating and race retention required |
| Door hardware | Low-profile M3 screw, example 6 mm under-head; 4.2 x 5 mm insert pilot |
| LED | 5 mm body, 6.2 mm flange, 1 mm flange thickness, 7 mm body length |
| Detector PCB | 28 x 22 mm legacy outline; 22 x 16 mm mounting centers |
| Cup | 50 mm OD x 40 mm high; nest 51 mm ID |
| Thread and rod Z | Unmeasured example endpoints, not a travel guarantee |

For different LED packages, fill **all 16 rows** of `led_profiles` in the master. Each row is `[body_d, flange_d, flange_t, body_length, lead_exit_d]`. An empty array uses the common example. It does not establish a wavelength list. The flange must be wider than its body bore and lead exit for mechanical capture.

The nominal 0.20 mm axial LED capture gap avoids requiring perfect hard contact across sixteen different packages. Determine any thin, opaque compliant retaining pads from the real packages and coupon; do not crush the LED bodies by forcing the plate down. Retention and optical seating repeatability need a physical test.

`production_release` remains false. Setting flags true does not perform their tests.

## 6. Bottom-up assembly

### Base adapter and nest

Seat the adapter's pilot in the existing base recess; four anchor arms sit on the existing frame bosses. It must sit without rocking or pulling those bosses upward. The center recess locates the part; the anchor hardware retains it. Verify the existing inserts and washer/bolt stack.

The four axial-support spacers share those anchor lines above the saddle. Final long fasteners clamp the support bridge/spacer/saddle/base stack. Calculate length from the actual stack and insert engagement; an overly long screw can bottom out and falsely feel tight. Do not load these supports until their anchors, bearings and collars are approved.

The sample nest bolts into the three saddle holes. Fit its nuts before covering underside tool access. Its seat is 18 mm above the saddle. The example cup sits within a 4 mm locating rim; lift it before pulling it sideways.

### Motion interfaces

Install the two screw-support bridges on their four spacers. The bridges are the same print; rotate the second 180 degrees around vertical for the opposite side. A selected bearing sits on a shoulder; its outer race is retained by the cap. Manufactured collars/shoulders must locate the inner race. The motor/coupler supplies rotation: do not assume the gearbox can support the carriage's axial load.

Use one primary guide housing at (-78,+55), one X-accommodating housing at (+78,+55), and the two XY-accommodating housings at the front (-Y) positions. Install actual bearings and their caps. Floating mounts require the specified metal shoulder/spacer arrangement; tightening an ordinary bolt directly against the moving flange defeats the float. The current example is a 4 mm OD shoulder with 4.15 mm effective length through a 4 mm flange; verify the actual stack.

### Chamber and panel

Bolt the chamber feet to the matching saddle holes. Seal the chamber/saddle interface as required; the gasket is not included as printed material. Fit the four real inserts to their verified pilot holes.

The panel seats straight into the recessed frame and is removed straight forward after removing its four screws. There are no hidden rails or lock tabs. It has hard seating stops plus a nominal 0.6 mm radial allowance for a **selected opaque compliant perimeter seal**. It must reject ambient light even at high Z when the outer tube no longer covers the panel.

With the example screw: 4 mm panel minus 2.2 mm head recess leaves about 1.8 mm between head seat and insert mouth; a 6 mm screw gives about 4.2 mm nominal engagement into the 5 mm pilot. This is a geometric example, not a release of an unidentified insert. Do not substitute long M3 screws without checking.

### Carriage and Z drive

Attach the two matching manufactured lead nuts by their flange screws to the two carriers; the carriers attach under the carriage. The flange screws provide positive antirotation. The carrier slots permit alignment around the real screw axes before tightening; they are not an excuse to bend the screws.

Guide housings fit the carriage's **housing-sized** openings. With power isolated and the load supported, verify smooth travel and equal side heights. Test with a protected dummy load before installing the final optics. Verify stopping, homing and load retention; those electrical/safety functions are not supplied by this print kit.

### Shroud and optical head

Drop the shroud through the carriage. Its pilot enters the center opening and its flange rests on top. The separate optical deck seats on the shroud flange. Four M4 bolts with captured metal nuts secure this shared stack. Verify bolt length and tool access.

Insert each LED lens-first into its angled seat from above. Bend/route leads only as permitted by its package and do not use the leads as alignment springs. Slide the shared retainer over the leads. Align its asymmetric bolt pattern and the +X datum marks. Its small holes pass the lead pair but cannot pass the flange. Tighten evenly against the deck; verify each emitter's capture and seating individually.

Install the detector mount, board and purchased spacers. Use the actual board and active detector location, not only the legacy outline. Attach the opaque cover after wiring. Seal and strain-relieve the cable outlet; it is otherwise a light leak.

Install the upper guide tie if the frame test requires it. If needed for safe/stable movement, install it before motion testing, even though its file is last in bottom-up order. Collar holding capability is not established by a preview.

## 7. Print orientations and acceptance

Every production job is laid out with each part on Z=0. Confirm the actual bed, brim and purge path in the slicer.

| Job | Orientation / inspection |
|---|---|
| 01 | Adapter broad saddle face down/pilot up; nest upright. Approximately 208 x 204 mm envelope: limited brim space. |
| 02 | Guide flanges down, housings up; bridges/caps/carriers flat; spacers upright. Preserve housing identities. |
| 03 | Chamber upright; panel standing on straight lower edge. Inspect the crown bridge, rebate and radial holes. |
| 04 | Carriage flat. Review underside nut-pocket roofs. |
| 05 | Shroud flange down, tube upward. |
| 06 | Deck flat; retainer inverted with flange reliefs upward; detector plate down/light tube up. Inspect the small angled seats and retained wall thickness. |
| 07 | Cover roof down, open cavity upward. |
| 08 | Tie flat. |

No blanket support-free claim is made. Inspect actual layer paths and run representative bridge/fit coupons. Do not apply indiscriminate internal supports that cannot be removed from the optical bores. Material, nozzle, layer height and slicer compensation must be recorded with the accepted coupon.

First use `00_Fit_Tests.scad`: datum template, short full-diameter cylinder pair, curved door corner, hardware seats, and the actual integrated LED-seat/retainer coupon. A diameter coupon does not establish full-height straightness. A passed coupon can be reused only if its exact geometry/material remain valid.

## 8. Validation and limitations

See `VALIDATION.md` and the machine-readable records under `Validation/`. Checks include full STL renders, connected-body counts, mesh closure, bed bounds, sample/door access poses and specified nominal intersections. Test SCADs under `Validation/` are **not production prints**; empty intersections are expected successful outcomes.

These tests do not establish physical dimensional accuracy, bearing or motor capacity, insert retention, fatigue, temperature performance, light rejection, beam/FOV validity, electrical safety or calibrated data. Actual hardware dimensions remain the blocking inputs. Use the retained-base engineering baseline's test gates before powered operation.

Any change to the base reference, hardware profile, LED geometry or print compensation invalidates the corresponding checks. Archive the supplied revision and regenerate affected parts as one matched set.
