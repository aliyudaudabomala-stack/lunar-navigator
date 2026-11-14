# Scientific Methodology and Limitations

## Current prototype
The app accepts a lunar latitude, longitude, date and planning hour. It produces simplified illustrative Sun/Earth angle values using elementary periodic functions. These values demonstrate the intended interaction and are not derived from a validated lunar ephemeris.

## Why local terrain matters
Near the lunar south pole, crater rims and ridges can dominate the local horizon. An object may be above a spherical reference horizon but blocked by nearby terrain. Accurate visibility analysis requires a terrain horizon profile derived from elevation data.

## Recommended calculation pipeline
1. Define the site in a documented lunar coordinate system.
2. Define epoch, time system and reference frame.
3. Obtain Moon, Sun and Earth geometry using validated SPICE kernels or JPL Horizons.
4. Transform directions into the local site frame.
5. Derive terrain elevation versus azimuth from LOLA data.
6. Compare Sun/Earth directions against the local terrain horizon through time.
7. Report windows, data provenance, sampling cadence and uncertainty.
8. Validate against independent reference cases.

## Communication caveat
Earth line-of-sight is not a guarantee of communications. Antenna pointing, lander orientation, radio hardware, link budget, terrain blockage, relay availability and operational constraints matter.

## Restriction
Do not use this prototype for actual landing-site selection, mission operations or safety-critical decisions.
