"""Small pure helpers that turn numbers into the dicts the chart partials render.

Charts are plain HTML/CSS (bars) and inline SVG (sparkline), so there is no JS
library and everything works offline. Money stays Decimal; floats are used only
for percentages of bar height/width.
"""

import math
from datetime import date
from decimal import Decimal


def fmt_money(value):
    return f"${Decimal(value):,.2f}"


def fmt_compact(value):
    """$1.2k style label for axis ticks."""
    value = float(value)
    if abs(value) >= 1_000_000:
        return f"${value / 1_000_000:.1f}M".replace(".0M", "M")
    if abs(value) >= 1_000:
        return f"${value / 1_000:.1f}k".replace(".0k", "k")
    return f"${value:,.0f}"


def nice_max(value):
    """Round a maximum up to a tidy axis ceiling (1, 2, 2.5, 5 x 10^n)."""
    value = float(value)
    if value <= 0:
        return 1.0
    exp = 10 ** math.floor(math.log10(value))
    for step in (1, 2, 2.5, 5, 10):
        if value <= step * exp:
            return step * exp
    return 10 * exp


def month_starts(today, count):
    """First day of each of the last `count` months, oldest first, ending this month."""
    y, m = today.year, today.month
    out = []
    for _ in range(count):
        out.append(date(y, m, 1))
        m -= 1
        if m == 0:
            m, y = 12, y - 1
    return list(reversed(out))


def month_key(d):
    return (d.year, d.month)


def _pct(value, ceiling):
    return round(float(value) / ceiling * 100, 2) if ceiling else 0


def column_chart(months, series, stacked=False, today=None):
    """
    months: list of month-start dates.
    series: list of dicts {key, label, tone, values: {(y, m): Decimal}}.
    Returns geometry for partials/_column_chart.html.
    """
    totals = []
    for mo in months:
        k = month_key(mo)
        vals = [series_item["values"].get(k, Decimal("0")) for series_item in series]
        totals.append(sum(vals) if stacked else max(vals))
    ceiling = nice_max(max(totals) if totals else 0)
    ticks = [
        {"label": fmt_compact(ceiling * f), "pct": f * 100}
        for f in (1, 0.75, 0.5, 0.25, 0)
    ]
    cols = []
    for i, mo in enumerate(months):
        k = month_key(mo)
        bars = []
        for s in series:
            v = s["values"].get(k, Decimal("0"))
            bars.append({
                "pct": _pct(v, ceiling),
                "tone": s["tone"],
                "label": s["label"],
                "value": fmt_money(v),
                "empty": v == 0,
            })
        is_current = today is not None and k == month_key(today)
        cols.append({
            "label": mo.strftime("%b"),
            "sub": mo.strftime("%y") if mo.month == 1 or mo == months[0] else "",
            "full": mo.strftime("%B %Y"),
            "bars": bars,
            "total": fmt_money(sum(s["values"].get(k, Decimal("0")) for s in series)),
            "current": is_current,
            "flip": i >= len(months) / 2,  # tooltip opens to the left on the right half
        })
    return {
        "cols": cols,
        "ticks": ticks,
        "stacked": stacked,
        "legend": [{"label": s["label"], "tone": s["tone"]} for s in series],
        "has_data": any(t > 0 for t in totals),
        "dense": len(months) > 6,
    }


def rank_bars(rows):
    """rows: list of dicts {label, value (Decimal), tone?, href?, note?}."""
    if not rows:
        return []
    top = max((r["value"] for r in rows), default=Decimal("0"))
    out = []
    for r in rows:
        out.append({
            **r,
            "pct": max(_pct(r["value"], float(top)), 2 if r["value"] > 0 else 0),
            "display": fmt_money(r["value"]),
            "tone": r.get("tone", "accent"),
        })
    return out


def segments(parts):
    """parts: list of dicts {label, value, tone}. Value may be Decimal or int."""
    total = sum(p["value"] for p in parts)
    out = []
    for p in parts:
        out.append({
            **p,
            "pct": _pct(p["value"], float(total)) if total else 0,
            "show": p["value"] > 0,
        })
    return {"segs": out, "total": total, "has_data": total > 0}


def sparkline(values, width=96, height=28, pad=2):
    """Return SVG polyline/area point strings for a list of numbers."""
    values = [float(v) for v in values]
    if len(values) < 2 or max(values) == min(values) == 0:
        return None
    lo, hi = min(values), max(values)
    span = (hi - lo) or 1
    step = (width - 2 * pad) / (len(values) - 1)
    pts = [
        (pad + i * step, height - pad - (v - lo) / span * (height - 2 * pad))
        for i, v in enumerate(values)
    ]
    line = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    area = f"{pad:.1f},{height} {line} {pts[-1][0]:.1f},{height}"
    return {"line": line, "area": area, "width": width, "height": height,
            "last_x": f"{pts[-1][0]:.1f}", "last_y": f"{pts[-1][1]:.1f}"}


def delta(current, previous):
    """Percent change as dict, or None when there is no meaningful baseline."""
    if not previous:
        return None
    change = (Decimal(current) - Decimal(previous)) / Decimal(previous) * 100
    return {"pct": f"{abs(change):.0f}", "up": change >= 0, "flat": round(change) == 0}
