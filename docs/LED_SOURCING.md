# LIO V3 — LED Sourcing Notes

These are leaded (through-hole) emitters researched as replacements for the SMD parts that couldn't be mounted.

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
- RAIL A runs at the LD06AJSA's 30 mA minimum and RAIL B at about 45 mA. Set RAIL B at or below the lowest maximum rating among the SWIR LEDs fitted.
- 300 nm parts need about 6.5 V or more, so they need a separate boost rail (for example an MT3608 set to about 9 V) and a hardware interlock.
