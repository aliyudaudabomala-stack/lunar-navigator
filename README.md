# Lunar Navigator

**NASA Space Apps Challenge Gombe 2026 — The Next Frontier**  
**Selected challenge:** Lunar Landing Site Navigator  
**Type:** Educational decision-support prototype

## Live demo
Enable GitHub Pages in repository Settings → Pages → Deploy from branch → `main` → `/ (root)`. After deployment, the site will be available at:
`https://aliyudaudabomala-stack.github.io/lunar-navigator/`

## Run locally
Open `index.html` in a modern browser. No package installation is required.

## Implemented
- Responsive mission-planning dashboard
- Three example candidate regions and custom coordinates
- Mission date and planning-hour controls
- Stylized Moon explorer and selected-location marker
- Simplified Sun and Earth angle estimates
- Scenario comparison with a transparent teaching indicator
- Downloadable mission summary
- NASA data-source and methodology references

## Scientific integrity
This is a functional educational prototype, **not a mission-grade lunar navigation tool**. It does not query live NASA services or download NASA datasets. The displayed Sun/Earth values are simplified illustrative estimates. The Moon graphic is a stylized drawing, not a LOLA-derived elevation map.

A scientifically stronger version should use:
- LOLA elevation products to derive terrain horizons.
- SPICE kernels and/or JPL Horizons for documented ephemerides, reference frames and geometry.
- Correct lunar body orientation, libration, time systems and local coordinate transformations.
- Terrain-aware Sun and Earth visibility windows.
- Independent validation and uncertainty reporting.

Earth geometric line-of-sight does not guarantee radio communications; antenna pointing, hardware, link budget, terrain and mission operations also matter. Example regions are areas for exploration, not approved landing sites. The teaching indicator is not a safety score or engineering certification.

## Data resources
- [LOLA](https://pds-geosciences.wustl.edu/missions/lro/lola.htm)
- [JPL Horizons](https://ssd.jpl.nasa.gov/horizons/)
- [NASA/JPL NAIF SPICE](https://naif.jpl.nasa.gov/naif/)
- [NASA Moon Trek](https://trek.nasa.gov/moon/)
- [LROC QuickMap](https://quickmap.lroc.asu.edu/)

## AI use declaration
AI tools assisted with code scaffolding, interface implementation and documentation. The team must review, test and understand the submitted work and update the declaration to name every AI tool actually used and describe its actual contribution. No AI-generated NASA logo or NASA branding is included.
