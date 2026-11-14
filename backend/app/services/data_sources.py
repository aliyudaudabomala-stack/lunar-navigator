"""Catalogue of every external dataset and model used by Lunar Navigator."""

from __future__ import annotations

from datetime import datetime, timezone

from ..scientific.time import isoformat_z
from .terrain_service import dem_info

DEFAULT_MISSION_TIME_UTC = "2026-11-24T12:00:00Z"


def data_sources_payload() -> dict:
    dem = dem_info()
    sources = [
        {
            "id": "lola-ldem-75s-240m",
            "name": "LRO Lunar Orbiter Laser Altimeter (LOLA) gridded topography",
            "provider": "NASA PDS Geosciences Node / LOLA Science Team",
            "url": dem["source_url"],
            "dataset_id": dem["dataset_id"],
            "product": dem["product_id"],
            "retrieved_at": dem["retrieved_at"],
            "status": "cached" if dem["available"] else "simulated",
            "units": "metres (radius above a 1737.4 km reference sphere)",
            "frame": "mean Earth/polar axis; planetocentric latitude, east longitude",
            "used_for": (
                "Site elevation, local slope/aspect, 240 m-scale roughness, terrain "
                "horizon ray-march, sky-view factor, polar hillshade basemap."
            ),
            "limitations": (
                "240 m/pixel; south polar coverage only (75S–90S); a shape model, not "
                "an optical image; cannot resolve lander-scale hazards; horizon rays are "
                "limited to a 30 km radius."
            ),
            "live": False,
            "attribution": "NASA / GSFC / MIT / LOLA Science Team; PDS Geosciences Node.",
        },
        {
            "id": "lola-label",
            "name": "LOLA PDS product label (LDEM_75S_240M)",
            "provider": "NASA PDS Geosciences Node",
            "url": (
                "https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/"
                "lrolol_1xxx/data/lola_gdr/polar/img/ldem_75s_240m.lbl"
            ),
            "dataset_id": dem["dataset_id"],
            "product": "LDEM_75S_240M label",
            "retrieved_at": dem["retrieved_at"],
            "status": "cached" if dem["label_file_present"] else "missing",
            "units": "n/a",
            "frame": "n/a",
            "used_for": "Verifying dimensions, scaling, offsets and projection metadata.",
            "limitations": "Archive metadata; not an independent measurement.",
            "live": False,
            "attribution": "NASA PDS Geosciences Node.",
        },
        {
            "id": "meeus-ephemeris",
            "name": "Geocentric Sun and Moon analytical ephemerides",
            "provider": "Implementation of Jean Meeus, Astronomical Algorithms (2nd ed.)",
            "url": "https://www.willbell.com/math/mc1.htm",
            "dataset_id": "Meeus ch. 25 (solar) and ch. 47 (lunar)",
            "product": "VSOP87 truncation + ELP-2000/82 truncation",
            "retrieved_at": None,
            "status": "modelled",
            "units": "degrees, kilometres, astronomical units",
            "frame": "geocentric ecliptic/equatorial of date, precessed to J2000",
            "used_for": (
                "Sun and Moon geocentric positions, sub-solar/sub-Earth points, phase, "
                "angular radii, and the direction vectors used for local az/el."
            ),
            "limitations": (
                "Analytical truncation. Validated against Meeus examples: solar longitude "
                "within 0.0001 deg; lunar longitude within 0.0007 deg and distance within "
                "25 km. No relativistic or light-time correction is applied to the local "
                "horizon geometry."
            ),
            "live": False,
            "attribution": "Meeus, J. (1998), Astronomical Algorithms, 2nd ed., Willmann-Bell.",
        },
        {
            "id": "iau-moon-orientation",
            "name": "IAU WGCCRE lunar rotation model",
            "provider": "International Astronomical Union WGCCRE / NAIF pck00010",
            "url": "https://naif.jpl.nasa.gov/pub/naif/generic_kernels/pck/pck00010.tpc",
            "dataset_id": "IAU 2015 Moon rotational elements",
            "product": "Euler angles + periodic libration terms (E1–E13)",
            "retrieved_at": None,
            "status": "modelled",
            "units": "degrees",
            "frame": "ICRF/J2000 to lunar body-fixed mean Earth/polar axis",
            "used_for": (
                "Local horizontal coordinates at a selenographic site, sub-Earth and "
                "sub-solar point geometry, and 3D Moon orientation."
            ),
            "limitations": (
                "Analytical IAU model including the principal periodic terms. Residual "
                "physical libration is below 0.01 deg in this implementation — far below "
                "the 240 m terrain resolution."
            ),
            "live": False,
            "attribution": "Archinal et al., IAU WGCCRE 2015 report; NAIF pck00010.",
        },
        {
            "id": "jpl-horizons",
            "name": "NASA/JPL Horizons system cross-check",
            "provider": "NASA Jet Propulsion Laboratory",
            "url": "https://ssd.jpl.nasa.gov/horizons/",
            "dataset_id": "Horizons API (observer ephemeris)",
            "product": "Apparent azimuth/elevation on demand",
            "retrieved_at": None,
            "status": "optional-live",
            "units": "degrees, kilometres",
            "frame": "observer topocentric, IAU_MOON body-fixed",
            "used_for": (
                "Optional independent cross-check requested explicitly by the user on "
                "the NASA Data Sources page. Never used to compute mission results."
            ),
            "limitations": (
                "Requires network access; may be rate-limited or unavailable. Differences "
                "against the analytical model are expected at the arcsecond-to-arcminute "
                "level because of light-time/aberration conventions."
            ),
            "live": True,
            "attribution": "NASA/JPL Solar System Dynamics.",
        },
        {
            "id": "usgs-gazetteer",
            "name": "USGS Gazetteer of Planetary Nomenclature",
            "provider": "USGS Astrogeology Science Center / IAU",
            "url": "https://planetarynames.wr.usgs.gov/",
            "dataset_id": "IAU-approved lunar feature names and centres",
            "product": "Named feature coordinates",
            "retrieved_at": None,
            "status": "historical",
            "units": "degrees, planetocentric east longitude",
            "frame": "mean Earth/polar axis",
            "used_for": "Reference context for candidate-region names and centres.",
            "limitations": "Feature centres are not landing ellipses or certified sites.",
            "live": False,
            "attribution": "IAU WGCCRE / USGS Astrogeology.",
        },
        {
            "id": "nasa-moon-trek",
            "name": "NASA Moon Trek",
            "provider": "NASA Solar System Treks / JPL",
            "url": "https://trek.nasa.gov/moon/",
            "dataset_id": "Moon Trek exploration portal",
            "product": "Reference visualization",
            "retrieved_at": None,
            "status": "reference",
            "units": "n/a",
            "frame": "n/a",
            "used_for": (
                "External reference for the user to inspect the same regions in NASA's "
                "official exploration portal."
            ),
            "limitations": (
                "This deployment does not stream Moon Trek tiles and never labels its own "
                "rasters as Moon Trek data."
            ),
            "live": False,
            "attribution": "NASA Solar System Treks.",
        },
    ]
    return {
        "sources": sources,
        "default_mission_time_utc": DEFAULT_MISSION_TIME_UTC,
        "generated_at_utc": isoformat_z(datetime.now(tz=timezone.utc)),
        "notes": [
            "Status vocabulary: live = network request made now; cached = local copy of a real product; "
            "historical = fixed published values; modelled = deterministic physics/model output; "
            "simulated = clearly-labelled synthetic fallback.",
            "The LOLA DEM is a static NASA archive product, not a live instrument feed.",
            "Mission analysis never depends on the JPL Horizons network check.",
            "The default mission time is a demonstration scenario chosen so that the Sun is up and "
            "Earth is above the south-polar horizon; change it in the mission context bar.",
        ],
    }
