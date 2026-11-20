# Owner preferences (hard rules)

## Git / branches

- **One branch only: `main`.**
- Do **all** work on `main`. Never create `feature/*`, `fix/*`, or other side branches.
- **Only ever push to `main`** (`origin/main`). Never push other refs.
- Do not open PRs from side branches; land commits directly on `main` unless the owner explicitly says otherwise.
- Historical milestone branches were deleted (Nov 2026); do not recreate them.
- Commit when asked or when the owner says to push / save work; include related uncommitted fixes in the same push.
- Never `git push --force` to `main` unless the owner explicitly requests it.
- Never update git config.

## Scope of changes

- Prefer small, targeted fixes over refactors.
- Soften known V3 mechanical/optical limits to **WARN** rather than FAIL when the owner says the next build will be tighter (stage repeatability, weak InGaAs at sealed top, hole 16 plausibility, intermittent/select-only, bogus duty totals).
- Do not invent new product features unless asked; finish commissioning / scan / food-profile workflows first.

## Dashboard / hardware

- Prefer keeping the dashboard usable: after Stop mid-run, recover USB (reconnect / `link_lost`) instead of leaving a zombie “connected” port.
- When restarting the dashboard mid-suite, warn that the run aborts; prefer stop-then-restart over killing motors mid-move when possible.
- Serial port is typically `/dev/cu.usbmodem101` (Arduino Nano R4). Firmware target ≈ **2.5.2**.

## Communication

- Be direct and concise.
- Prefer actionable next steps for bench work (empty baseline → PTFE/black cup → food scans).
