# All 16 LEDs on OPT101 and InGaAs

**Status: prepared and validated offline; not run on hardware.**

Read the [bench handoff](../../../handoffs/2026-11-24_all16_dual_detector_bench.md) before use.
The owner authorises stationary all 16-LED acquisition on both detectors with
real target-placement confirmations. Neither detector/head nor currents move.

| Run order | Target | Protocol |
|---|---|---|
|1|White, fresh placement|[all16_W1_n12.json](all16_W1_n12.json)|
|2|Black, same top surface plane|[all16_B1_n12.json](all16_B1_n12.json)|
|3|White, removed/reseated|[all16_W2_n12.json](all16_W2_n12.json)|
|4|Black, removed/reseated|[all16_B2_n12.json](all16_B2_n12.json)|

Each run: holes 1–16, both detectors, N=12 technical readings/hole, gain 1,
settle 8 ms, mains 60 Hz x2 periods; 192 managed MEAS operations /384 detector
rows. Four runs: 768 operations /1536 rows. Keep all raw rows and signed values.

Experiment caps per run: 24000 ms cumulative on-time;3600 s wall/cycle.
Existing rolling quotas, watchdogs, journal and admission are unchanged.
Nominal light 15872 ms and normal reservations 17664 ms per run are not
wall-time estimates. Allow tens of minutes for four passes and honour actual
cooldowns. Never clear a journal or relax limits to speed collection.

The black target must match the white target's TOP plane, backing and footprint.
If no matched black card is available BEFORE acquisition, use the declared
W1/W2-only fallback and mark black/white-minus-black results unavailable.
No optical blocker is required or claimed in this experiment.

H16 is included ONLY as proxy_unassigned, never primary1850 nm chemistry.
H15 is cutoff-sensitive; OPT101 h12–16 is not primary SWIR.
White/black differences do not by themselves prove claimed LED wavelength,
calibrated reflectance, chemical specificity or that an unresolved LED is dead.

SESSION_MANIFEST_NOT_A_PROTOCOL.json defines the prespecified 32-comparison
external analysis and fallback; it is not itself a CLI acquisition protocol.
OFFLINE_VALIDATION.json records four guarded actual CLI plan checks against
source fdcee9d77aa0288e0f453a95b3c2c7894cd913b3, with zero hardware calls.
Revalidate against the bench's actual installed build/config before light.
Do not interpret single-condition qualified-v2 UNRESOLVED as a failed LED.
