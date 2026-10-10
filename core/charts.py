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


def axis_ticks(ceiling, lowest):
    """Evenly-spaced tick values from `ceiling` down to a floor, always including $0.

    No chart has needed a floor below zero yet — every amount charted so far
    (sales, cash, losses) is a sum of non-negative figures — but a future
    chart might (e.g. net profit), so this keeps the axis correct for that
    case rather than breaking on it: it steps down in quarters of `ceiling`
    and, only once `lowest` is actually negative, keeps adding whole steps
    below zero until it reaches `lowest` — the same "$700k … $0 … -$175k"
    shape a spreadsheet would pick.
    """
    step = ceiling / 4
    values = [ceiling - i * step for i in range(5)]  # ceiling .. 0, 5 ticks
    if lowest < 0:
        n_below = math.ceil(round(-lowest / step, 6))
        values += [-i * step for i in range(1, n_below + 1)]
    return values


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


def _pct(value, floor, ceiling):
    span = ceiling - floor
    return round((float(value) - floor) / span * 100, 2) if span else 0


def _share_pct(value, whole):
    """value as a % of whole, floor-less — used by rank_bars/segments (always >= 0)."""
    return round(float(value) / whole * 100, 2) if whole else 0


def column_chart(months, series, stacked=False, today=None):
    """
    months: list of month-start dates.
    series: list of dicts {key, label, tone, values: {(y, m): Decimal}}.
    Returns geometry for partials/_column_chart.html.
    """
    totals, all_values = [], []
    for mo in months:
        k = month_key(mo)
        vals = [series_item["values"].get(k, Decimal("0")) for series_item in series]
        all_values.extend(vals)
        totals.append(sum(vals) if stacked else max(vals))
    ceiling = nice_max(max([*totals, 0]))
    lowest = min([*all_values, 0])
    tick_values = axis_ticks(ceiling, float(lowest))
    floor = tick_values[-1]
    span = ceiling - floor
    ticks = [
        {"label": fmt_compact(v), "pct": _pct(v, floor, ceiling), "zero": round(v, 6) == 0}
        for v in tick_values
    ]
    cols = []
    for i, mo in enumerate(months):
        k = month_key(mo)
        bars = []
        for s in series:
            v = s["values"].get(k, Decimal("0"))
            bars.append({
                "pct": _pct(v, floor, ceiling),
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
        "has_data": any(t != 0 for t in totals),
        "zero_pct": _pct(0, floor, ceiling),
        "dense": len(months) > 6,
    }


def line_chart(months, series, today=None):
    """One-series line chart: the column chart's axis, ticks and hover data, plus
    the polyline joining the month points for partials/_line_chart.html.

    Points sit at the centre of each month's column (the column gap is zero in
    CSS for this chart), so the line and the hover hit-areas line up exactly.
    """
    chart = column_chart(months, series[:1], today=today)
    count = len(chart["cols"])
    chart["points"] = " ".join(
        f"{(i + 0.5) / count * 100:.2f},{100 - col['bars'][0]['pct']:.2f}"
        for i, col in enumerate(chart["cols"])
    )
    chart["tone"] = series[0]["tone"]
    return chart


def profit_chart(months, values, today=None):
    """Diverging net profit/loss bars pinned to the zero line.

    `values` maps (y, m) -> net profit for that month, which may be negative.
    Each bar grows up from the zero line for a profit or down from it for a
    loss (green / red in the template), the way a spreadsheet's up-down bar
    chart reads. Reuses the same axis/tick maths as column_chart so the zero
    line and gridlines line up with the other charts.
    """
    month_vals = [values.get(month_key(m), Decimal("0")) for m in months]
    ceiling = nice_max(max([*month_vals, 0]))
    lowest = min([*month_vals, 0])
    tick_values = axis_ticks(ceiling, float(lowest))
    floor = tick_values[-1]
    ticks = [
        {"label": fmt_compact(v), "pct": _pct(v, floor, ceiling), "zero": round(v, 6) == 0}
        for v in tick_values
    ]
    zero_pct = _pct(0, floor, ceiling)
    cols = []
    for i, mo in enumerate(months):
        v = month_vals[i]
        v_pct = _pct(v, floor, ceiling)
        pos = v >= 0
        amount = fmt_money(abs(v))
        cols.append({
            "label": mo.strftime("%b"),
            "sub": mo.strftime("%y") if mo.month == 1 or mo == months[0] else "",
            "full": mo.strftime("%B %Y"),
            "value": amount if pos else f"({amount})",
            "pos": pos,
            "edge": v_pct,  # the bar's outer end: its top (profit) or bottom (loss)
            "bottom": zero_pct if pos else v_pct,
            "height": round(abs(v_pct - zero_pct), 2),
            "empty": v == 0,
            "current": today is not None and month_key(mo) == month_key(today),
            "flip": i >= len(months) / 2,
        })
    return {
        "cols": cols,
        "ticks": ticks,
        "zero_pct": zero_pct,
        "has_data": any(v != 0 for v in month_vals),
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
            "pct": max(_share_pct(r["value"], float(top)), 2 if r["value"] > 0 else 0),
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
            "pct": _share_pct(p["value"], float(total)) if total else 0,
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
