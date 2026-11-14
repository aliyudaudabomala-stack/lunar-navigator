"""PDF mission report generation with ReportLab.

The report is deliberately self-documenting: every score component, dataset
provenance record and limitation is included so a reviewer can reproduce the
conclusion without the web UI.
"""

from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
import math
from typing import Any

from reportlab.graphics.shapes import Circle, Drawing, Line, PolyLine, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Flowable,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

INK = colors.HexColor("#0b1220")
DIM = colors.HexColor("#4b5563")
SIGNAL = colors.HexColor("#0e7490")
SUN = colors.HexColor("#b45309")
EARTH = colors.HexColor("#0369a1")
BAD = colors.HexColor("#b91c1c")
GOOD = colors.HexColor("#047857")
LINE = colors.HexColor("#cbd5e1")
PANEL = colors.HexColor("#f1f5f9")


class TimelineChart(Flowable):
    """Sun and Earth elevation versus time, with the local horizon lines."""

    def __init__(self, rows: list[dict], width: float = 500, height: float = 150):
        super().__init__()
        self.rows = rows
        self.width = width
        self.height = height

    def wrap(self, available_width: float, available_height: float):
        self.width = min(self.width, available_width)
        return self.width, self.height

    def draw(self) -> None:
        c = self.canv
        rows = self.rows
        if len(rows) < 2:
            c.setFont("Helvetica", 8)
            c.setFillColor(DIM)
            c.drawString(4, self.height / 2, "No timeline samples were requested for this report.")
            return

        left, right, bottom, top = 34, 8, 26, 12
        plot_w = self.width - left - right
        plot_h = self.height - bottom - top

        sun_values = [r["sun_elevation_deg"] for r in rows]
        earth_values = [r["earth_elevation_deg"] for r in rows]
        horizons = [max(r["sun_horizon_deg"], r["earth_horizon_deg"]) for r in rows]
        minimum = min(min(sun_values), min(earth_values), min(horizons), -1.0)
        maximum = max(max(sun_values), max(earth_values), max(horizons), 1.0)
        pad = max((maximum - minimum) * 0.08, 0.6)
        lo, hi = minimum - pad, maximum + pad

        def x(index: int) -> float:
            return left + plot_w * index / (len(rows) - 1)

        def y(value: float) -> float:
            return bottom + plot_h * (value - lo) / (hi - lo)

        # grid + zero line
        c.setStrokeColor(LINE)
        c.setLineWidth(0.4)
        for frac in (0.0, 0.25, 0.5, 0.75, 1.0):
            yy = bottom + plot_h * frac
            c.line(left, yy, left + plot_w, yy)
            value = lo + (hi - lo) * frac
            c.setFillColor(DIM)
            c.setFont("Helvetica", 6)
            c.drawRightString(left - 3, yy - 2, f"{value:.0f}")

        c.setStrokeColor(colors.HexColor("#94a3b8"))
        c.setDash(2, 2)
        if lo < 0 < hi:
            c.line(left, y(0), left + plot_w, y(0))
        c.setDash()

        def polyline(values: list[float], color) -> None:
            c.setStrokeColor(color)
            c.setLineWidth(1.4)
            path = c.beginPath()
            path.moveTo(x(0), y(values[0]))
            for i in range(1, len(values)):
                path.lineTo(x(i), y(values[i]))
            c.drawPath(path)

        polyline(horizons, colors.HexColor("#a3a3a3"))
        polyline(sun_values, SUN)
        polyline(earth_values, EARTH)

        c.setFont("Helvetica", 6)
        c.setFillColor(DIM)
        c.drawString(left, 2, rows[0]["time"][:16].replace("T", " ") + " UTC")
        c.drawRightString(left + plot_w, 2, rows[-1]["time"][:16].replace("T", " ") + " UTC")

        legend_x = left + 6
        for label, color in (
            ("Sun elev.", SUN),
            ("Earth elev.", EARTH),
            ("terrain horizon", colors.HexColor("#a3a3a3")),
        ):
            c.setStrokeColor(color)
            c.setLineWidth(1.6)
            c.line(legend_x, self.height - 5, legend_x + 14, self.height - 5)
            c.setFillColor(DIM)
            c.setFont("Helvetica", 6.5)
            c.drawString(legend_x + 17, self.height - 7, label)
            legend_x += 78


class HorizonPolarPlot(Flowable):
    """Terrain horizon elevation by azimuth, drawn as a polar profile."""

    def __init__(self, azimuths: list[float], elevations: list[float], width: float = 150, height: float = 150):
        super().__init__()
        self.azimuths = azimuths
        self.elevations = elevations
        self.width = width
        self.height = height

    def wrap(self, available_width: float, available_height: float):
        return self.width, self.height

    def draw(self) -> None:
        c = self.canv
        cx, cy = self.width / 2, self.height / 2
        radius = min(self.width, self.height) / 2 - 12
        max_el = max(max(self.elevations), 5.0)
        scale = radius / (max_el * 1.15)

        c.setStrokeColor(LINE)
        c.setLineWidth(0.4)
        for frac in (0.25, 0.5, 0.75, 1.0):
            c.circle(cx, cy, radius * frac, stroke=1, fill=0)
        c.setStrokeColor(colors.HexColor("#cbd5e1"))
        c.line(cx - radius, cy, cx + radius, cy)
        c.line(cx, cy - radius, cx, cy + radius)

        points = []
        for az, el in zip(self.azimuths, self.elevations):
            angle = math.radians(90.0 - az)
            r = max(0.0, el) * scale
            points.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))
        if points:
            points.append(points[0])
            c.setFillColor(colors.HexColor("#e0f2fe"))
            c.setStrokeColor(SIGNAL)
            c.setLineWidth(1.2)
            path = c.beginPath()
            path.moveTo(cx, cy)
            path.lineTo(*points[0])
            for point in points[1:]:
                path.lineTo(*point)
            path.close()
            c.drawPath(path, stroke=1, fill=1)

        c.setFillColor(DIM)
        c.setFont("Helvetica", 6)
        c.drawCentredString(cx, cy + radius + 3, "N")
        c.drawCentredString(cx, cy - radius - 8, "S")
        c.drawString(cx + radius + 3, cy - 2, "E")
        c.drawRightString(cx - radius - 3, cy - 2, "W")
        c.drawCentredString(cx, 1, f"max {max_el:.1f} deg")


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "LNTitle", parent=base["Title"], fontName="Helvetica-Bold", fontSize=20, leading=24, textColor=INK, spaceAfter=2
        ),
        "subtitle": ParagraphStyle(
            "LNSub", parent=base["Normal"], fontName="Helvetica", fontSize=9, leading=12, textColor=DIM
        ),
        "h1": ParagraphStyle(
            "LNH1", parent=base["Heading1"], fontName="Helvetica-Bold", fontSize=12.5, leading=15, textColor=INK, spaceBefore=10, spaceAfter=4
        ),
        "h2": ParagraphStyle(
            "LNH2", parent=base["Heading2"], fontName="Helvetica-Bold", fontSize=10, leading=13, textColor=SIGNAL, spaceBefore=7, spaceAfter=2
        ),
        "body": ParagraphStyle(
            "LNBody", parent=base["Normal"], fontName="Helvetica", fontSize=8.5, leading=11.5, textColor=ink_body()
        ),
        "small": ParagraphStyle(
            "LNSmall", parent=base["Normal"], fontName="Helvetica", fontSize=7, leading=9, textColor=DIM
        ),
        "bullet": ParagraphStyle(
            "LNBullet", parent=base["Normal"], fontName="Helvetica", fontSize=8.3, leading=10.8, textColor=ink_body(), leftIndent=9, bulletIndent=1
        ),
        "cell": ParagraphStyle(
            "LNCell", parent=base["Normal"], fontName="Helvetica", fontSize=7.4, leading=9.2, textColor=ink_body()
        ),
        "cellb": ParagraphStyle(
            "LNCellB", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=7.4, leading=9.2, textColor=INK
        ),
    }


def ink_body():
    return colors.HexColor("#1f2937")


def _p(text: str, style: ParagraphStyle) -> Paragraph:
    return Paragraph(str(text), style)


def _table(data: list[list[Any]], widths: list[float], *, header: bool = True) -> Table:
    table = Table(data, colWidths=widths, repeatRows=1 if header else 0)
    style = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.35, LINE),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 2.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
    ]
    if header:
        style.extend(
            [
                ("BACKGROUND", (0, 0), (-1, 0), PANEL),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ]
        )
    table.setStyle(TableStyle(style))
    return table


def _fmt(value: Any, suffix: str = "", digits: int = 1) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, (int, float)):
        return f"{value:.{digits}f}{suffix}"
    return f"{value}{suffix}"


def _header_footer(canvas, doc) -> None:
    canvas.saveState()
    width, height = A4
    canvas.setStrokeColor(LINE)
    canvas.setLineWidth(0.5)
    canvas.line(18 * mm, height - 14 * mm, width - 18 * mm, height - 14 * mm)
    canvas.setFont("Helvetica", 6.5)
    canvas.setFillColor(DIM)
    canvas.drawString(18 * mm, height - 11.5 * mm, "LUNAR NAVIGATOR  |  SOUTH-POLE LANDING-SITE ASSESSMENT")
    canvas.drawRightString(width - 18 * mm, height - 11.5 * mm, "NASA Space Apps Challenge 2026")
    canvas.line(18 * mm, 13 * mm, width - 18 * mm, 13 * mm)
    canvas.drawString(18 * mm, 9 * mm, "Planning aid only — not a flight certification.")
    canvas.drawRightString(width - 18 * mm, 9 * mm, f"Page {doc.page}")
    canvas.restoreState()


def build_report(payload: dict) -> bytes:
    """Return a PDF byte string for an ``analyze`` payload."""

    styles = _styles()
    site = payload["site"]
    time = payload["time"]
    sky = payload["sky"]
    terrain = payload["terrain"]
    assessment = payload["assessment"]
    illumination = payload["illumination"]
    comms = payload["comms"]
    horizon = payload["horizon"]["profile"]

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=20 * mm,
        bottomMargin=17 * mm,
        title=f"Lunar Navigator — {site['short_name']}",
        author="Lunar Navigator (NASA Space Apps Challenge 2026)",
        subject="Lunar south-pole landing-site assessment",
        creator="Lunar Navigator 1.0",
    )

    story: list[Any] = []
    story.append(_p("Lunar Navigator", styles["title"]))
    story.append(
        _p(
            f"Landing-site assessment — {site['short_name']}",
            styles["subtitle"],
        )
    )
    story.append(
        _p(
            f"Mission instant {time['display_utc']} &nbsp;|&nbsp; window {time['window_days']:g} days "
            f"@ {time['step_minutes']:g} min &nbsp;|&nbsp; generated {payload.get('generated_at_utc', '')}",
            styles["subtitle"],
        )
    )
    story.append(Spacer(1, 5 * mm))

    score = assessment["score"]
    score_color = GOOD if score >= 70 else (colors.HexColor("#b45309") if score >= 50 else BAD)
    banner = Table(
        [
            [
                _p(
                    f"<font size='26'><b>{score:.1f}</b></font><font size='10'> / 100</font><br/>"
                    f"<font color='{score_color.hexval()}'><b>Grade {assessment['grade']}</b></font>",
                    styles["body"],
                ),
                _p(
                    f"<b>{site['name']}</b><br/>"
                    f"Lat {site['lat']:.4f}° &nbsp; Lon {site['lon']:.4f}° E<br/>"
                    f"Elevation {_fmt(terrain['elevation_m'], ' m', 0)} &nbsp;|&nbsp; "
                    f"Slope {_fmt(terrain['slope_deg'], '°')} &nbsp;|&nbsp; "
                    f"Sky view {_fmt(terrain['sky_view_factor'], '', 2)}<br/>"
                    f"{site['coordinate_confidence']} — {site['source_note']}",
                    styles["body"],
                ),
            ]
        ],
        colWidths=[42 * mm, 130 * mm],
    )
    banner.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("BOX", (0, 0), (-1, -1), 0.6, LINE),
                ("BACKGROUND", (0, 0), (0, 0), PANEL),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(banner)
    story.append(Spacer(1, 3 * mm))
    story.append(
        _p(
            "<b>Planning aid only.</b> This report combines measured LOLA topography with analytical "
            "ephemerides and a transparent heuristic score. It is not a certified landing-site safety "
            "assessment, a flight rule, or a terrain-hazard map.",
            styles["small"],
        )
    )

    story.append(_p("1. Mission snapshot", styles["h1"]))
    snapshot_rows = [
        [_p("Metric", styles["cellb"]), _p("Value", styles["cellb"]), _p("Metric", styles["cellb"]), _p("Value", styles["cellb"])],
        [
            _p("Sunlight fraction", styles["cell"]),
            _p(f"{illumination['sun_visible_fraction'] * 100:.1f}%", styles["cell"]),
            _p("Direct-to-Earth fraction", styles["cell"]),
            _p(f"{comms['earth_visible_fraction'] * 100:.1f}%", styles["cell"]),
        ],
        [
            _p("Full-disk sunlight", styles["cell"]),
            _p(f"{illumination['sun_full_disk_fraction'] * 100:.1f}%", styles["cell"]),
            _p("Longest Earth window", styles["cell"]),
            _p(f"{comms['longest_window_hours']:.1f} h", styles["cell"]),
        ],
        [
            _p("Mean Sun elevation", styles["cell"]),
            _p(_fmt(illumination["mean_sun_elevation_deg"], "°"), styles["cell"]),
            _p("Mean Earth elevation", styles["cell"]),
            _p(_fmt(comms["mean_earth_elevation_deg"], "°"), styles["cell"]),
        ],
        [
            _p("Mean terrain horizon", styles["cell"]),
            _p(_fmt(illumination["mean_horizon_deg"], "°"), styles["cell"]),
            _p("Roughness (240 m)", styles["cell"]),
            _p(_fmt(terrain["roughness_m"], " m", 0), styles["cell"]),
        ],
        [
            _p("Next sunset in window", styles["cell"]),
            _p(illumination.get("next_sunset_utc") or "none sampled", styles["cell"]),
            _p("Next Earthset in window", styles["cell"]),
            _p(comms.get("next_earthset_utc") or "none sampled", styles["cell"]),
        ],
    ]
    story.append(_table(snapshot_rows, [41 * mm, 45 * mm, 41 * mm, 45 * mm]))
    story.append(Spacer(1, 2 * mm))
    story.append(_p(assessment["explanation"], styles["body"]))

    story.append(_p("2. Landing-instant geometry", styles["h1"]))
    geometry_rows = [
        [_p("Body", styles["cellb"]), _p("Azimuth", styles["cellb"]), _p("Elevation", styles["cellb"]),
         _p("Terrain horizon", styles["cellb"]), _p("Margin", styles["cellb"]), _p("Visible", styles["cellb"])],
        [
            _p("Sun", styles["cell"]),
            _p(f"{sky['sun']['azimuth_deg']:.2f}°", styles["cell"]),
            _p(f"{sky['sun']['elevation_deg']:.3f}°", styles["cell"]),
            _p(f"{sky['sun']['horizon_deg']:.2f}°", styles["cell"]),
            _p(f"{sky['sun']['margin_deg']:.3f}°", styles["cell"]),
            _p(_fmt(sky["sun"]["above_horizon"]), styles["cell"]),
        ],
        [
            _p("Earth", styles["cell"]),
            _p(f"{sky['earth']['azimuth_deg']:.2f}°", styles["cell"]),
            _p(f"{sky['earth']['elevation_deg']:.3f}°", styles["cell"]),
            _p(f"{sky['earth']['horizon_deg']:.2f}°", styles["cell"]),
            _p(f"{sky['earth']['margin_deg']:.3f}°", styles["cell"]),
            _p(_fmt(sky["earth"]["above_horizon"]), styles["cell"]),
        ],
    ]
    story.append(_table(geometry_rows, [18 * mm, 25 * mm, 25 * mm, 32 * mm, 25 * mm, 24 * mm]))
    story.append(
        _p(
            "Azimuth is measured clockwise from local north. Terrain horizon comes from a 240 m LOLA "
            "ray-march to 30 km with lunar curvature correction. No atmospheric refraction is applied.",
            styles["small"],
        )
    )

    story.append(_p("3. Weighted score breakdown", styles["h1"]))
    weights = assessment["weights"]
    component_labels = {
        "power": "Solar power / illumination",
        "comms": "Direct-to-Earth geometry",
        "terrain": "Terrain suitability (slope, roughness, sky view)",
        "timing": "Conditions at landing instant",
    }
    component_rows = [
        [_p("Component", styles["cellb"]), _p("Weight", styles["cellb"]), _p("Score /100", styles["cellb"]),
         _p("Weighted", styles["cellb"]), _p("Formula", styles["cellb"])],
    ]
    for key in ("power", "comms", "terrain", "timing"):
        component = assessment["components"][key]
        component_rows.append(
            [
                _p(component_labels[key], styles["cell"]),
                _p(f"{weights[key] * 100:.0f}%", styles["cell"]),
                _p(f"{component['score']:.1f}", styles["cell"]),
                _p(f"{component['score'] * weights[key]:.1f}", styles["cell"]),
                _p(component["formula"], styles["cell"]),
            ]
        )
    story.append(_table(component_rows, [43 * mm, 15 * mm, 20 * mm, 18 * mm, 76 * mm]))
    story.append(_p(f"Overall score = sum(weight × component score) = <b>{score:.1f}/100</b>.", styles["body"]))

    story.append(_p("4. Advantages, disadvantages and risks", styles["h1"]))
    for label, key, color in (
        ("Advantages", "advantages", GOOD),
        ("Disadvantages", "disadvantages", colors.HexColor("#b45309")),
        ("Risks / cautions", "risks", BAD),
    ):
        story.append(_p(f"<font color='{color.hexval()}'>{label}</font>", styles["h2"]))
        items = assessment.get(key) or ["None flagged."]
        for item in items:
            story.append(Paragraph(str(item), styles["bullet"], bulletText="•"))
    if not assessment.get("advantages"):
        story.append(Paragraph("No advantage cleared the heuristic thresholds.", styles["bullet"], bulletText="•"))

    story.append(PageBreak())
    story.append(_p("5. Sun and Earth timeline", styles["h1"]))
    timeline = payload.get("timeline") or []
    if timeline:
        story.append(TimelineChart(timeline, width=173 * mm, height=55 * mm))
        story.append(
            _p(
                f"{len(timeline)} samples at {time['step_minutes']:g} min spacing over {time['window_days']:g} days. "
                "Grey line is the maximum of the Sun/Earth terrain horizons at each sample; the shaded "
                "values above the horizon line represent geometric visibility.",
                styles["small"],
            )
        )
    else:
        story.append(_p("Timeline sampling was disabled for this request.", styles["body"]))

    story.append(_p("6. Terrain horizon (polar view)", styles["h1"]))
    horizon_flow = [
        HorizonPolarPlot(horizon["azimuths_deg"], horizon["elevations_deg"], 45 * mm, 45 * mm),
        Table(
            [
                [_p("Sky-view factor", styles["cell"]), _p(_fmt(terrain["sky_view_factor"], "", 3), styles["cell"])],
                [_p("Mean horizon", styles["cell"]), _p(_fmt(horizon["mean_elevation_deg"], "°"), styles["cell"])],
                [_p("Maximum horizon", styles["cell"]), _p(_fmt(horizon["max_elevation_deg"], "°"), styles["cell"])],
                [_p("Ray-march range", styles["cell"]), _p(f"{horizon['max_range_km']:g} km", styles["cell"])],
                [_p("Azimuth step", styles["cell"]), _p(f"{horizon['azimuth_step_deg']:g}°", styles["cell"])],
                [_p("Terrain source", styles["cell"]), _p(terrain["data_quality"], styles["cell"])],
            ],
            colWidths=[34 * mm, 40 * mm],
        ),
    ]
    story.append(
        Table(
            [horizon_flow],
            colWidths=[70 * mm, 80 * mm],
            style=[("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("BOTTOMPADDING", (0, 0), (-1, -1), 0)],
        )
    )
    story.append(
        _p(
            f"{terrain['coverage_note']} Product {terrain['product_id']} ({terrain['dataset_id']}), "
            f"{terrain['resolution_m']:g} m/pixel, retrieved {terrain.get('retrieved_at') or 'n/a'}.",
            styles["small"],
        )
    )

    story.append(_p("7. Data provenance", styles["h1"]))
    provenance_rows = [
        [_p("Source / product", styles["cellb"]), _p("Status", styles["cellb"]), _p("Units / frame", styles["cellb"]),
         _p("Retrieved", styles["cellb"]), _p("Limitations", styles["cellb"])],
    ]
    for record in payload.get("provenance", []):
        provenance_rows.append(
            [
                _p(f"<b>{record['name']}</b><br/><font size='6.2'>{record.get('product', '')}<br/>{record.get('url', '')}</font>", styles["cell"]),
                _p(record.get("status", ""), styles["cell"]),
                _p(f"{record.get('units', '')}<br/>{record.get('frame', '')}", styles["cell"]),
                _p(record.get("retrieved_at") or "n/a", styles["cell"]),
                _p(record.get("limitations", ""), styles["cell"]),
            ]
        )
    story.append(_table(provenance_rows, [47 * mm, 15 * mm, 30 * mm, 20 * mm, 60 * mm]))

    story.append(_p("8. Assumptions and limitations", styles["h1"]))
    for item in payload.get("assumptions", []):
        story.append(Paragraph(str(item), styles["bullet"], bulletText="•"))
    for item in payload.get("limitations", []):
        story.append(Paragraph(str(item), styles["bullet"], bulletText="–"))

    story.append(Spacer(1, 4 * mm))
    story.append(
        _p(
            "<b>Decision disclaimer.</b> "
            + assessment.get("disclaimer", "")
            + " Candidate coordinates are approximate regions, not certified landing ellipses. "
            "Nothing in this report supersedes a project-specific hazard analysis, power model, "
            "thermal model or communications link budget.",
            styles["small"],
        )
    )

    doc.build(story, onFirstPage=_header_footer, onLaterPages=_header_footer)
    return buffer.getvalue()
