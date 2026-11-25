# Confirmed SWIR purchases: 7 May 2026

Recorded **25 November 2026** from the owner's supplied DigiKey product/order-history excerpts. Each listed item showed **Last purchased May 07, 2026**. These are purchase identities, replacing the earlier uncertainty about the purchased SWIR part numbers. Full private order pages were not accessed. Quantity, lot/bin and serialised identity were not supplied.

Hole assignments below follow LIO's current nominal wavelength map. Purchase confirmation does not independently prove that the same physical parts remain fitted after replacements or that their spectra have been measured. No hardware or operating setting was changed to create this record.

## Purchased items

| Intended role | Manufacturer | Exact manufacturer part | DigiKey part number | Package / nominal wavelength | Public product page |
|---|---|---|---|---|---|
| h12 | Quelighting Corp | **QLIR01MXGM** | **3970-QLIR01MXGM-ND** | 5 mm radial, 1450 nm | [DigiKey 28168147](https://www.digikey.com/en/products/detail/quelighting-corp/QLIR01MXGM/28168147) |
| h13 | Marktech Optoelectronics | **MTE5115D4** | **1125-1485-ND** | 3 mm plastic radial, 1550 nm | [DigiKey 9955413](https://www.digikey.com/en/products/detail/marktech-optoelectronics/MTE5115D4/9955413) |
| h14 | Marktech Optoelectronics | **MTE5116D4** | **1125-1489-ND** | 3 mm plastic radial, 1650 nm | [DigiKey 9955417](https://www.digikey.com/en/products/detail/marktech-optoelectronics/MTE5116D4/9955417) |
| h15 | Marktech Optoelectronics | **MTE2117C1** | **1125-MTE2117C1-ND** | 3 mm plastic radial, catalogued 1760 nm; see discrepancy below | [DigiKey 21853427](https://www.digikey.com/en/products/detail/marktech-optoelectronics/MTE2117C1/21853427) |
| InGaAs detector | Marktech Optoelectronics | **MTPD1346D-100** | **1125-1326-ND** | TO-46-3, 1.00 mm diameter active area | [DigiKey 5866635](https://www.digikey.com/en/products/detail/marktech-optoelectronics/MTPD1346D-100/5866635) |

**h16 / nominal 1850 nm:** its purchase part number was not included. Keep its source identity unresolved and its analysis role `proxy_unassigned`. A strong silicon signal cannot identify an 1850 nm component; it also does not prove that such a component is absent.

## Manufacturer specifications checked on 25 November 2026

These are typical specifications or absolute limits under the stated test conditions, **not measurements of LIO**. Absolute maximum current is not a recommended setpoint. Keep the existing current, duty and watchdog constraints; do not infer an output at the owner-declared approximately 30 mA from a rating at another current.

| Part | Manufacturer optical characteristics and conditions | DC absolute current limit | Datasheet / revision |
|---|---|---:|---|
| QLIR01MXGM | Peak 1450 nm; spectral width 75 nm; **20° full half-intensity angle** (`2θ1/2`); typical radiant intensity **6.8 mW/sr at 100 mA**, typical Vf 1.1 V at 100 mA | 150 mA | [Quelighting PDF](https://mm.digikey.com/Volume0/opasdata/d220001/medias/docus/7893/QLIR01MXGM.pdf), V1.0, initial release 10 Oct 2025, pp 2–5 |
| MTE5115D4 | Peak 1550 nm, spectral width 100 nm; power **3.6 mW at 20 mA**, **6.3 mW at 50 mA**; Vf 0.91 / 1.04 V respectively; manufacturer lists **Half Intensity Beam Angle θ = 120°** | 100 mA | [Marktech PDF](https://specs.marktechopto.com/pdf/products/datasheet/MTE5115D4.pdf), 15 Jan 2019, pp 1–3 |
| MTE5116D4 | Peak 1650 nm, spectral width 113 nm; power **3.0 mW at 20 mA**, **5.5 mW at 50 mA**; Vf 0.85 / 0.97 V respectively; manufacturer lists **Half Intensity Beam Angle θ = 120°** | 100 mA | [Marktech PDF](https://specs.marktechopto.com/pdf/products/datasheet/MTE5116D4.pdf), 15 Jan 2019, pp 1–3 |
| MTE2117C1 | Characteristic table: peak **1760 nm**, spectral width **225 nm**, typical power **3 mW at 50 mA**, Vf 0.95 V at 50 mA, half-intensity angle **±25°** (50° full). Heading/prose also say 1720 nm | 100 mA | [Marktech PDF](https://specs.marktechopto.com/pdf/products/datasheet/MTE2117C1.pdf), preliminary, 10 Dec 2025, pp 1–3 |
| MTPD1346D-100 | Manufacturer specifies **600–1750 nm**, typical responsivity **0.70 A/W at 1550 nm**, active diameter **1.0 mm**, junction capacitance 60 pF at zero reverse bias. No guaranteed package-FOV curve is supplied | Not an LED; no drive-current setting applies | [Marktech PDF](https://specs.marktechopto.com/pdf/products/datasheet/MTPD1346D-100.pdf), 3 Dec 2024, pp 1–3 |

### Preserve these catalog/manufacturer differences

| Item | Owner-supplied DigiKey field | Manufacturer PDF | How to use it |
|---|---|---|---|
| 1450 nm optical test current | 6.8 mW/sr at **150 mA** | 6.8 mW/sr at **100 mA** | Cite the PDF's test condition in optical budgets; keep 150 mA identified as the absolute DC limit, not the optical test current |
| D4 beam-angle convention | Both listings say **240°** | Both PDFs list **120°** under “Half Intensity Beam Angle θ” | Record both literally; full-angle/half-angle convention or a catalog error needs Marktech clarification. Both identify a **very broad source**, unlike the 20° h12. Do not silently treat 120° as a verified full angle or fit a narrow Gaussian to these D4 parts |
| MTE2117C1 wavelength | **1760 nm** | Characteristic table 1760 nm; heading/prose **1720 nm** | Retain nominal h15=1760 in existing records; seek lot/spec clarification before spectral modelling. Do not edit historical data or silently relabel it 1720 |
| Detector wavelength/range | “1300 nm”; spectral range **800–1750 nm** | Broad response **600–1750 nm**, with a 1550 nm responsivity specification | “1300 nm” is a catalog descriptor, **not a 1300 nm-only bandpass**. This distinction does not change compatibility at 1450/1550/1650 |
| Detector dark-current fields | Typical 200 nA; catalog max reverse voltage 5 V | PDF gives maximum dark current 2 µA at reverse bias 1 V | Different typical/maximum values and conditions are not interchangeable. They do not establish this zero-bias TIA's offset or authorise changing detector bias |

Radiant **intensity** (mW/sr, h12) and total radiant **power** (mW, D4/C1) cannot be compared numerically as the same quantity. These values also use different drive currents. No measured-output ranking at 30 mA follows from their tabulated numbers alone.

## Should this detector see reflected light from these LEDs?

| Source | Spectral compatibility with MTPD1346D-100 | What LIO has already shown |
|---|---|---|
| 1450 nm / QLIR01MXGM | **Yes**, inside the specified response range | Mounted white–black contrast **+51.08 counts** in the final 24 Nov all16 family |
| 1550 nm / MTE5115D4 | **Yes**; the detector explicitly specifies responsivity at this wavelength | **+2.67 counts**, small but resolved in the technical comparison; direct illumination was strong |
| 1650 nm / MTE5116D4 | **Yes**, within its specified range, approaching its long-wavelength edge | **+1.92 counts**, small but resolved technically; direct illumination was strong |
| Nominal 1760 nm / MTE2117C1 | **Partial spectrum only / cutoff-sensitive**. The broad LED spectrum extends below the detector's nominal 1750 nm endpoint | **+14.25 counts**, compatible with spectral-tail overlap; not a calibrated monochromatic 1760 nm channel |
| Nominal 1850 nm / unknown source | **Outside the detector's specified range at the nominal wavelength** | Unassigned proxy only; no primary-1850 interpretation |

Bench source: [all16 report](../research/LIO_V3_ALL16_DUAL_DETECTOR_BENCH_2026-11-24.md) and `test_results/bench_20261124_all16/runs/20261124-{162954,164006,165136,170431}_scan_protocol/cube.csv.gz`. The quoted intervals in that report describe technical repeats; no optical blocker separated return from pickup. White/black target association is not calibrated reflectance.

**Conclusion:** spectral incompatibility does not explain the weak 1550/1650 readings. The known detector can detect these bands. Source delivery, physical seating/obscuration, reflected-light collection, target spectrum and electrical noise remain relevant. This new purchase record supports a more specific mechanical hypothesis; it does not prove a unique cause.

## Important change to the optical interpretation

The purchased h13/h14 sources are **3 mm, very wide-angle D4 packages**, not the narrow-beam 5 mm example sources used for conditional budgets in earlier research. Those earlier example budgets must not be treated as models of the fitted parts. See [LED sourcing](../LED_SOURCING.md) for the distinction between purchases and candidates.

In the unmodified R3 CAD (`CAD/V3/LIO_V3_R3_Print_Set/LIO_V3_R3_master.scad`), the example LED body is 5 mm with 0.4 mm diametric hole allowance, flange 6.2 mm and keeper lead exit 4.2 mm. The D4 drawing instead shows body approximately **2.95 mm** and flange **3.75 mm**. Thus:

- A 2.95 mm body in a 5.4 mm bore has about **1.225 mm radial clearance** before any adapter/putty: it does not register as a 5 mm LED would.
- A nominal 3.75 mm D4 flange is smaller than the example 4.2 mm keeper exit; that keeper cannot positively retain the flange by diameter alone.
- A short, broad-emitting package recessed inside an opaque well can lose useful light into the surrounding plastic. Conversely, broad emission outside a restricted well can illuminate walls instead of the sample. Either can reduce useful sample illumination without a defective photodiode.

These are **nominal CAD/package comparisons**, not measurements of today's assembled seats. Putty, inserts and prior modifications may change the fit. The C1 is also a 3 mm package and needs its own measured fit. The D4 parts have milliwatt-class typical power at 20 mA, so “rated for 100 mA” does not imply they must be driven at 100 mA to function.

The practical next check is whether the actual 3 mm emitting surfaces are exposed toward the sample and held reproducibly, while keeping both detectors fixed. If an adapter is needed, design a package-specific locating/height adapter after measuring the stack; an opaque printed sleeve does **not** collimate light and can make obscuration worse. A permanent detector move is not established as the remedy by these part identities.

## Information still needed

1. The **1850 nm LED's exact purchased manufacturer part number/product link**.
2. Confirmation that these four purchased emitters are still the parts fitted at h12–h15 after bench replacements, plus a close-up or measured recess showing how the 3 mm h13/h14 packages sit in the head.
3. For quantitative optical modelling: D4 angular convention and C1 1720/1760 discrepancy clarified by the supplier/lot documentation; actual current, emitted output, detector input range and assembly geometry remain unmeasured. Owner-deferred checks remain deferred.

This documentation does not change Rf/current configuration, authorise bench work or claim measured SNR improvement, calibrated reflectance/photocurrent, SWIR chemistry or recovered 1850 nm measurement.
