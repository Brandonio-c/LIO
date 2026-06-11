<p align="center">
  <img src="images/LIO-Logo.png" alt="LIO logo" width="320">
</p>

**Lio** is an open hardware experiment to build a low-cost, 3D-printable multispectral diffuse-reflectance scanner for powdered food samples.

The project aims to collect repeatable optical reflectance data from controlled food powders and known mixtures using LED illumination, photodiode sensing, calibration references, and a motorized sample-height stage.

The core question LIO aims to answer is:

> Can a small, cheap, repeatable multispectral reflectance instrument produce enough signal to support useful closed-world food-powder classification or controlled-mixture experiments?

The honest answer is currently unknown. This repository documents the attempt.

---

## What Lio is trying to achieve

### Near-term goals

- Build a rigid, light-sealed optical chamber.
- Use one LED wavelength at a time to illuminate powdered samples.
- Measure reflected light using visible/NIR and SWIR detector paths.
- Normalize measurements using dark and PTFE white-reference readings.
- Create repeatable reflectance vectors for each sample.
- Validate mechanical repeatability before training any model.
- Test simple controlled mixtures before attempting complex packaged foods.

### Long-term goals

- Build a dataset of calibrated reflectance scans from known powders and mixtures.
- Compare simple models such as PCA, logistic regression, SVM, and PLS regression before trying neural networks.
- Evaluate whether additional SWIR wavelengths improve separability.
- Develop a closed-world composition-hypothesis workflow.
- Eventually detect whether unknown samples are optically consistent with trained known mixtures.

## Measurement concept

Lio uses **multispectral diffuse reflectance**.

A powdered sample sits in a controlled cup inside a dark, black-lined chamber. LEDs illuminate the sample one wavelength at a time. A detector measures reflected light from the sample. Each wavelength produces one channel value.

A scan sequence looks like this:

1. Record dark readings with all LEDs off.
2. Record white-reference readings using a PTFE reference insert.
3. Record sample readings using the food powder.
4. Normalize each channel:

```text
R_i = (S_i - D_i) / (W_i - D_i)
```

Where:

```text
R_i = normalized reflectance for wavelength i
S_i = sample reading
D_i = dark reading
W_i = white-reference reading
```

Optional absorbance-like transformation:

```text
A_i = -log10(R_i)
```

The output of one scan is a reflectance vector such as:

```text
[red, green, blue, 400, 890, 1020, 1200, 1300, 1450, 1550, 1650, 1760]
```

Exact channels depend on which LED modules are installed.

---

## Optical design

The optical system is built around a fixed top optical head and a moving bottom sample platform.

### Fixed optical section

- Top detector cap.
- Detector snout / aperture tube.
- LED ring with removable LED cartridges.
- Outer optical tube.
- Removable black flocked inner sleeve.
- Internal baffle rings.
- Bottom fixed collar / upper telescoping receiver.

### Moving sample section

- Moving sample platform.
- Powder sample cup.
- PTFE reference holder.
- Dark reference plug.
- Moving telescoping skirt / lower light-seal sleeve.

### Telescoping light-seal concept

The fixed optical chamber does not move. The sample platform moves up and down on a motorized Z-stage. A lower moving sleeve overlaps with an upper fixed collar so the optical path remains dark while the sample height changes.

```text
fixed optical tube
    ↓
bottom fixed collar / upper receiver
    ↓ overlaps with
moving telescoping skirt
    ↓ attached to
moving sample platform
    ↓ driven by
M6 threaded rod + 28BYJ motor
```

This is the physical mechanism referred to as the Lio telescoping focusing channel. It is not a lens. It is a light-sealed adjustable sample-height shroud.

---

## Mechanical architecture

The current mechanical architecture is a PETG 3D-printed tower with metal guide hardware.

### Motion system

- 28BYJ-48 5 V stepper motor.
- ULN2003 stepper driver board.
- M6 threaded rod as the vertical drive screw.
- M6 nut trapped in the moving platform.
- Two 8 mm guide rods.
- LM8UU linear bearings.
- Top guide bridge to keep rods parallel.
- Bottom motor base to hold rods, motor, screw, and endstop.
- Endstop switches for homing/safety.

### Coordinate logic

The mechanical drive axis and sample/optical axis are intentionally different:

```text
M6 drive axis:       X = 0, Y = 0
left guide rod:      X = -45, Y = 0
right guide rod:     X = +45, Y = 0
sample/optical axis: X = 0, Y = +35
```

The sample cup is offset forward so the M6 threaded rod does not pass through the sample.

The fixed tower frame holds the optical tube over the sample axis, not over the M6 drive axis.

---

## Electronics architecture

### Control and acquisition

- Arduino Nano or compatible controller
- ADS1115 16-bit I2C ADC modules
- One-LED-at-a-time sequencing
- Dark / white / sample scan workflow

### Detector paths

- OPT101 module for visible and shorter NIR channels
- InGaAs photodiode with an OPA381 transimpedance amplifier for SWIR channels

### LED control

- Individually addressable LED channels
- MOSFET or LED-driver switching
- A single channel active at any moment
- Optional current control / PWM dimming once baseline stability is established

### Motor control

- 28BYJ-48 stepper motor
- ULN2003 driver board
- External 5 V supply or power bank for motor power
- Shared ground between the motor supply and the Arduino

---

## CAD file set

The CAD is authored in OpenSCAD. Most files generate printable STL parts; one file is a non-printing assembly preview.

```text
01_lio_fit_tests.scad
02_lio_outer_tube.scad
03_lio_inner_sleeve.scad
04_lio_baffle_rings.scad
05_lio_detector_cap.scad
06_lio_led_ring.scad
07_lio_led_cartridges.scad
08_lio_bottom_collar.scad
09_lio_motor_base.scad
10_lio_top_guide_bridge.scad
11_lio_moving_platform.scad
12_lio_moving_telescoping_skirt.scad
13_lio_sample_accessories.scad
14_lio_electronics_tray.scad
15_lio_fixed_tower_frame.scad
16_lio_assembly_preview.scad
```

### 01 — Fit tests

Small validation prints for LM8UU bearing bores, M6 nut traps, M3 heat-set inserts, and 8 mm rod spacing. Print these before committing to large mechanical parts.

### 02 — Outer optical tube

The main fixed optical chamber body: 80 mm outer tube, 60 mm inner bore, top and bottom flanges, M3 insert bosses, an inner-sleeve alignment feature, and baffle-retaining ledges.

### 03 — Removable inner sleeve

A thin PETG cylinder that carries the black telescope flocking and lifts out for cleaning or optical adjustment.

### 04 — Baffle rings

Internal annular baffles that suppress glancing wall reflections and stray light.

### 05 — Detector cap

The top detector cap, with a PCB pocket, aperture, detector snout, and a wire-exit light-trap feature.

### 06 — LED ring

A 16-slot modular LED-ring body that accepts removable LED cartridges rather than fixing LED types permanently.

### 07 — LED cartridges

Wedge/cartridge inserts sized for 3 mm LEDs, 5 mm LEDs, SMD LEDs, and TO-can / metal-can emitters.

### 08 — Bottom collar / upper receiver

The fixed half of the telescoping light seal, mounted beneath the optical tube to receive and overlap the moving skirt.

### 09 — Motor base

The base of the Z-stage: 28BYJ motor mount, lower 8 mm guide-rod sockets, M6/coupler clearance, bottom endstop area, and an optional ULN2003 mount region.

### 10 — Top guide bridge

Anchors the top ends of the guide rods and provides upper M6 clearance and support.

### 11 — Moving platform

The sample carriage: LM8UU bearing housings, an M6 nut trap, a sample-cup pocket, an endstop flag, a height pointer, and mounting holes for the telescoping skirt.

### 12 — Moving telescoping skirt

The moving lower half of the telescoping light seal, mounted to the platform and overlapping the fixed receiver.

### 13 — Sample accessories

A batch of sample-prep and calibration parts: powder sample cup, PTFE reference holder, dark reference plug, and a leveling ring / scraper guide.

### 14 — Electronics tray

An open service tray for the Arduino, ADS1115 modules, ULN2003 board, USB pigtail strain relief, wire clips, and an LED cable comb.

### 15 — Fixed tower frame

The structural bridge between the stationary optical chamber and the motorized Z-stage. It holds the fixed optical tube/collar above the offset sample axis and turns the telescoping seal into a mechanically constrained assembly.

### 16 — Assembly preview

A non-printing OpenSCAD file that visualizes the full assembly. A `stage_z` parameter previews the platform at different heights. This file is for visualization only and is not sliced or printed.

---

## Recommended printing order

Mechanical geometry and fit tolerances take priority over the cosmetic optical shell, so print in this order:

```text
01 fit tests
09 motor base
10 top guide bridge
11 moving platform
12 moving telescoping skirt
15 fixed tower frame
08 bottom fixed collar
02 outer optical tube
03 inner sleeve
04 baffle rings
05 detector cap
06 LED ring
07 LED cartridges
13 sample accessories
14 electronics tray
16 assembly preview (visualization only)
```

---

## Print settings

Baseline settings for PETG on the Ender-3 V3 SE:

```text
Nozzle: 235–245 °C
Bed: 75–85 °C
Layer height: 0.20 mm
Walls: 4 for structural parts
Infill: 35–45% for mechanical parts
Supports: OFF where geometry is supportless
Brim: ON for tall/thin parts
First layer speed: 15–20 mm/s
Fan: low/off for first layers, then moderate
Bed prep: clean plate + thin glue-stick layer
```

Tall, thin parts such as the inner sleeve and baffle rings benefit from additional brim, sacrificial carrier strips, or shorter test prints.

---

## Data collection workflow

A complete scan session follows this sequence:

1. Home the Z-stage.
2. Set a known sample height.
3. Record a dark scan with LEDs off.
4. Insert the PTFE reference holder.
5. Record a white-reference scan.
6. Insert the sample cup.
7. Fire each LED one at a time.
8. Record detector readings.
9. Normalize using dark/white calibration.
10. Save raw and normalized data with metadata.

Each record carries metadata for full traceability:

```text
sample ID
batch ID
operator
timestamp
sample mass
sample cup depth
grind/sieve method
LED channel
LED current/PWM
detector used
TIA gain setting
ADC gain setting
sample height
temperature/humidity if available
white reference ID
firmware version
CAD revision
```

---

## Validation plan

Repeatability is verified before any modeling begins.

### Mechanical repeatability

- The Z-stage homes consistently.
- The platform moves smoothly without binding.
- The moving skirt overlaps the fixed receiver across all usable heights.
- The sample cup stays centered under the optical axis.

### Optical repeatability

- Dark readings hold steady over time.
- PTFE reference readings repeat across insert/remove cycles.
- A given powder yields repeatable normalized reflectance vectors.
- The chamber, wire exits, and telescoping sleeve stay light-tight.

### Dataset integrity

- Controlled binary mixtures precede complex packaged foods.
- Validation uses held-out batches and days.
- Repeated scans of the same physical sample are kept together rather than split across train and test sets.

---

## Modeling plan

Modeling starts with interpretable methods and adds complexity only as the data justifies it:

- PCA for visualization.
- Logistic regression, SVM, and random forest for classification.
- PLS regression for controlled concentration estimation.
- Neural networks introduced once enough independent, repeatable data exists to support them.

The first concrete targets are:

```text
Can Lio distinguish known powder classes under controlled preparation?
```

and:

```text
Can Lio estimate the percentage of one ingredient in a controlled binary mixture?
```

---

## Repository structure

```text
lio/
├── README.md
├── cad/
│   ├── 01_lio_fit_tests.scad
│   ├── 02_lio_outer_tube.scad
│   ├── 03_lio_inner_sleeve.scad
│   ├── 04_lio_baffle_rings.scad
│   ├── 05_lio_detector_cap.scad
│   ├── 06_lio_led_ring.scad
│   ├── 07_lio_led_cartridges.scad
│   ├── 08_lio_bottom_collar.scad
│   ├── 09_lio_motor_base.scad
│   ├── 10_lio_top_guide_bridge.scad
│   ├── 11_lio_moving_platform.scad
│   ├── 12_lio_moving_telescoping_skirt.scad
│   ├── 13_lio_sample_accessories.scad
│   ├── 14_lio_electronics_tray.scad
│   ├── 15_lio_fixed_tower_frame.scad
│   └── 16_lio_assembly_preview.scad
├── stl/
├── gcode/
├── firmware/
├── electronics/
├── data/
│   ├── raw/
│   ├── processed/
│   └── metadata/
├── notebooks/
├── docs/
└── photos/
```

---

## Current status

Lio is in early mechanical prototyping.

- Hardware components have been sourced.
- 3D-printer setup is underway.
- OpenSCAD files are evolving iteratively.
- The design now includes a fixed tower frame and assembly preview, which add the assembly constraints the original part list lacked.
- Current focus is mechanical fit and light sealing.
- Electronics and data collection follow once the physical platform is stable.

---

## Safety and operating notes

Lio is an experimental research prototype intended for controlled laboratory and educational use.

LEDs across the visible, UV, NIR, and SWIR ranges can deliver significant optical power, and some wavelengths are invisible while still being energetic. Handle the optics with appropriate care: avoid looking directly into LEDs, use current limiting, keep the optical path enclosed, and treat unknown high-power emitters with caution.

Results from Lio are research data. Keep them within the closed-world experimental context the instrument is built for.

---

## References

- Near-infrared spectroscopy in food quality assurance (review): https://www.mdpi.com/3022876
- NIST PTFE 45°/0° reflectance reference work: https://nvlpubs.nist.gov/nistpubs/jres/104/2/html/nad-k/nad.htm
- OpenSCAD documentation: https://openscad.org/documentation.html
- Creality Ender-3 V3 SE specifications: https://store.creality.com/products/ender-3-v3-se-3d-printer
- STL file format reference: https://www.xometry.com/resources/3d-printing/stl-file-format/

---

## License

A license has not yet been selected. Before the project opens to outside contributions, a license will be chosen deliberately. Candidate options include:

- MIT License for code
- CERN Open Hardware License for hardware/CAD
- Creative Commons license for documentation

---

## Project philosophy

Lio is an exercise in disciplined instrument design: build a controlled, repeatable measurement platform, collect clean data, and map out exactly what low-cost multispectral reflectance can do for closed-world food analysis. The work centers on repeatable measurements, well-characterized limits, and a clear, incremental path from mechanical validation to controlled-mixture discrimination and narrow classification.D_i = dark reading
W_i = white-reference reading
```

An optional absorbance-like transform is also available:

```text
A_i = -log10(R_i)
```

Each scan produces a reflectance vector, for example:

```text
[red, green, blue, 400, 890, 1020, 1200, 1300, 1450, 1550, 1650, 1760]
```

The exact channel set depends on which LED modules are installed.

---

## Optical design

The optical system pairs a fixed top optical head with a moving bottom sample platform.

### Fixed optical section

- Top detector cap
- Detector snout / aperture tube
- LED ring with removable LED cartridges
- Outer optical tube
- Removable black-flocked inner sleeve
- Internal baffle rings
- Bottom fixed collar / upper telescoping receiver

### Moving sample section

- Moving sample platform
- Powder sample cup
- PTFE reference holder
- Dark reference plug
- Moving telescoping skirt / lower light-seal sleeve

### Telescoping light seal

The optical chamber stays stationary while the sample platform travels vertically on a motorized Z-stage. A lower moving sleeve overlaps a fixed upper collar, keeping the optical path sealed against ambient light across the full range of sample heights.

```text
fixed optical tube
    ↓
bottom fixed collar / upper receiver
    ↓ overlaps with
moving telescoping skirt
    ↓ attached to
moving sample platform
    ↓ driven by
M6 threaded rod + 28BYJ motor
```

This mechanism is referred to as the Lio telescoping focusing channel: a light-sealed, adjustable sample-height shroud that maintains a dark optical path as the sample height changes.

---

## Mechanical architecture

The mechanical platform is a PETG 3D-printed tower built around metal guide hardware.

### Motion system

- 28BYJ-48 5 V stepper motor
- ULN2003 stepper driver board
- M6 threaded rod as the vertical drive screw
- M6 nut captured in the moving platform
- Two 8 mm guide rods
- LM8UU linear bearings
- Top guide bridge to keep the rods parallel
- Bottom motor base holding the rods, motor, screw, and endstop
- Endstop switches for homing and travel limits

### Coordinate logic

The mechanical drive axis and the sample/optical axis are intentionally separated:

```text
M6 drive axis:       X = 0, Y = 0
left guide rod:      X = -45, Y = 0
right guide rod:     X = +45, Y = 0
sample/optical axis: X = 0, Y = +35
```

Offsetting the sample cup forward keeps the M6 threaded rod clear of the sample. The fixed tower frame positions the optical tube direct# Lio

**Lio** is an open-hardware research instrument: a low-cost, 3D-printable multispectral diffuse-reflectance scanner for powdered food samples.

We are building a benchtop optical instrument that shines light through a sequence of individual LED wavelengths onto a prepared food powder, measures how much light each wavelength reflects back, and turns that into a calibrated spectral signature for the sample. By collecting these signatures across many known powders and controlled mixtures, we can train models that recognize what a sample is, or estimate how much of one ingredient is present in a blend. The entire instrument — optical chamber, motorized sample stage, electronics housing — is 3D-printable and built from inexpensive, widely available parts, so the whole design can be reproduced on a hobbyist printer for a fraction of the cost of a commercial spectrometer.

The work spans three layers that come together into a single platform:

- **Hardware** — a rigid, light-sealed optical chamber paired with a motorized Z-stage that raises and lowers the sample while keeping the optical path dark. LEDs illuminate one wavelength at a time; visible/NIR and SWIR detectors capture the reflected light.
- **Acquisition** — a calibrated scan workflow that normalizes every reading against dark and white references, producing repeatable reflectance vectors with full metadata for traceability.
- **Modeling** — a data pipeline that starts with interpretable methods (PCA, regression, SVM, PLS) to classify known powders and estimate controlled-mixture ratios, expanding toward more complex models as the dataset grows.

The scope is deliberately focused:

> A repeatable, closed-world optical data-collection platform for evaluating whether low-cost multispectral reflectance can classify known powdered foods and estimate changes in controlled mixtures.

---

## Motivation

Visible/NIR/SWIR spectroscopy is a well-established approach to food analysis. Near-infrared methods are widely deployed for rapid quality control, origin and authenticity screening, and broad compositional analysis, typically paired with chemometric calibration models. These techniques are indirect and calibration-driven by nature: the instrument measures reflected light, and a trained model maps that signal to a property of interest.

Lio brings that idea down to a hobbyist-accessible price point by replacing a full commercial spectrometer with a set of discrete, individually addressable LEDs. The central research question is straightforward:

> Can a small, inexpensive, repeatable multispectral reflectance instrument produce enough usable signal to support closed-world food-powder classification or controlled-mixture estimation?

This repository documents the design, build, and experimental program developed to answer that question.

---

## Objectives

### Near-term

- Build a rigid, light-sealed optical chamber.
- Illuminate powdered samples one LED wavelength at a time.
- Measure reflected light across visible/NIR and SWIR detector paths.
- Normalize every measurement against dark and PTFE white-reference readings.
- Produce repeatable reflectance vectors for each sample.
- Establish mechanical repeatability as a precondition for any modeling.
- Characterize simple controlled mixtures before moving to complex packaged foods.

### Long-term

- Assemble a calibrated dataset of reflectance scans from known powders and mixtures.
- Benchmark interpretable models (PCA, logistic regression, SVM, PLS regression) before exploring neural networks.
- Quantify how additional SWIR wavelengths affect class separability.
- Develop a closed-world composition-hypothesis workflow.
- Determine whether unknown samples are optically consistent with trained known mixtures.

---

## Scope

Lio is a research-grade instrument for controlled, closed-world experiments. It is purpose-built to:

- Acquire calibrated reflectance data from prepared powdered samples.
- Discriminate among a known, trained set of powder classes.
- Estimate mixture ratios within controlled binary systems.

Its design priority is measurement integrity: prove repeatability first, then controlled-mixture discrimination, then narrow closed-world classification. The instrument is intended for experimental and educational use rather than food-safety, medical, or regulatory applications.

---

## Measurement principle

Lio operates on **multispectral diffuse reflectance**.

A powdered sample sits in a controlled cup inside a dark, black-lined chamber. LEDs illuminate the sample one wavelength at a time, and a detector measures the diffusely reflected light. Each wavelength contributes one channel to the resulting spectral vector.

A scan sequence proceeds as follows:

1. Record dark readings with all LEDs off.
2. Record white-reference readings using a PTFE reference insert.
3. Record sample readings from the food powder.
4. Normalize each channel:

```text
R_i = (S_i - D_i) / (W_i - D_i)
```

Where:

```text
R_i = normalized reflectance for wavelength i
S_i = sample reading
D_i = dark reading
W_i = white
