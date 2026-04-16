# Demo parking lot

## Current non-demo issues to revisit
1. Plant grouping is wrong across files.
   - Solar and BESS files are being treated as separate plants.
   - Need cross-file merge by shared site identity.

2. Site identity extraction is noisy.
   - Bad plant names: AS BUILT, TITLE SHEET, FOR CONSTRUCTION, SYMBOL
   - Bad addresses and locations from vendor or drawing text

3. Hybrid classification is incomplete.
   - Need plant_type = hybrid when solar and BESS both exist

4. File filtering is weak.
   - Vendor datasheets, fire alarm, substation wiring, and unrelated docs pollute extraction

5. Capacity resolution now works better, but plant-level assignment is still wrong.
   - 200 MWAC solar found
   - 100 MWAC BESS found
   - final grouping still incorrect

## After demo
- Add source ranking
- Add negative filters for plant name, address, and location
- Merge plant candidates across files
- Split capacities into solar_ac, solar_dc, bess_power, bess_energy
- Re-run full hybrid onboarding flow