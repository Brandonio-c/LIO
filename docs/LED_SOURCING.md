# LIO V3 — LED Sourcing Notes

## Confirmed SWIR purchases (recorded 25 November 2026)

The owner supplied DigiKey purchase confirmations dated **7 May 2026** for h12 **Quelighting QLIR01MXGM**, h13 **Marktech MTE5115D4**, h14 **Marktech MTE5116D4**, h15 **Marktech MTE2117C1**, and detector **MTPD1346D-100**. See [the purchase record](hardware/SWIR_COMPONENTS_PURCHASED_2026-05-07.md) for exact DigiKey numbers, source links, test conditions and uncertainties. h16's exact purchased source remains unknown.

**Important:** h13/h14 are very wide-angle **3 mm D4** emitters. Narrow-beam Roithner/Marktech alternatives and example optical budgets from earlier research are not the purchased-part specifications. Package fit and exposure in the nominal 5 mm seats must be checked before attributing their weak return to detector position. The D4 angle convention, h15 wavelength discrepancy and fitted-part confirmation remain open.

## Earlier sourcing candidates (not purchase confirmation)

The following are leaded (through-hole) emitters researched as replacements for the SMD parts that could not be mounted. An entry here is not proof that the item was bought or fitted; use the confirmed record above for h12–h15.

> Links and prices come from research in late October / early November 2026. Check stock, lead time and the datasheet before ordering. On DigiKey, "Manufacturer Standard Lead Time" applies only when stock is zero. The **In Stock** quantity is what decides delivery.

## Through-hole candidates

| Wavelength | Part | Package | Link |
|---|---|---|---|
| 1200 nm | Marktech MTE1200N5 | 5 mm domed | https://www.digikey.com/en/products/detail/marktech-optoelectronics/MTE1200N5/11205354 |
| 1300 nm | Marktech MTE1300N5 (choose the N5 variant) | 5 mm domed | https://www.digikey.com/en/products/base-product/marktech-optoelectronics/1125/MTE1300/327345 |
| 1300 nm | Marktech MTE1300-WRC | TO-46 metal can | https://www.digikey.com/en/products/detail/marktech-optoelectronics/MTE1300-WRC/3863555 |
| 1050 nm (for "1000") | Marktech MTE5010-525-IR | 5 mm radial | https://www.digikey.com/en/products/detail/marktech-optoelectronics/MTE5010-525-IR/8565913 |
| 1070 nm (for "1100") | Marktech MTE7110N5 | 5 mm radial | https://www.digikey.com/en/products/detail/marktech-optoelectronics/MTE7110N5/11205108 |
| 940 nm | Marktech MTE9440M3A | T-1 radial | https://www.digikey.com/en/products/detail/marktech-optoelectronics/MTE9440M3A/2798891 |
| 940 nm (cheap) | Chanzon 5 mm, 100-pack | 5 mm | https://www.amazon.com/Infrared-Lighting-Electronics-Components-Emitting/dp/B01BVGIZGC |
| 850 nm (cheap) | Chanzon 5 mm, 100-pack | 5 mm | https://www.amazon.com/Infrared-Lighting-Electronics-Components-Emitting/dp/B01BVGIZIU |
| 395–400 nm | Any 5 mm UV LED (Chanzon 395 nm purchased) | 5 mm | DigiKey filter: https://www.digikey.com/en/products/filter/led-emitters-infrared-uv-visible/94 |
| 300 nm UVC | Marktech UV through-hole line (TO-39 with UV window) | TO-39 (≈9 mm) | https://marktechopto.com/uv-throughhole-leds/ (confirm a 300 nm variant) |

**Lens suffix:** N5 = 5 mm plastic domed (narrower beam, preferred for aiming at the sample); N2 = 5 mm flat lens.

## Cost notes

- The Marktech SWIR parts cost about $16–20 each. They are InGaAsP/InP devices made in small volumes, so they're expensive everywhere reputable.
- AliExpress "1050–1500 nm" emitters cost a few dollars each. Their wavelength accuracy and consistency are poor, and many are 3535 SMD. They're acceptable only as approximate prototype channels; filter for through-hole listings.
- 300 nm UVC parts cost roughly $30–70 or more. Epoxy absorbs UVC, so a 5 mm epoxy version doesn't exist.

## Electrical notes

- Measure each emitter's forward voltage with the meter's diode mode before use.
- Historical intended settings were RAIL A 30 mA and RAIL B about 45 mA. The owner later declared approximately 30 mA on both rails; that remains unmeasured and YAML still records B 45 mA. Preserve existing operating/duty restrictions. Purchased-part maximum currents are not proposed new drive settings.
- 300 nm parts need about 6.5 V or more, so they need a separate boost rail (for example an MT3608 set to about 9 V) and a hardware interlock.

