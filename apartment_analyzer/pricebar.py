"""Google-Flights-like price indicator rendered as HTML."""

COLORS = {"low": "#188038", "typical": "#b06000", "high": "#c5221f"}
TEXT = {
    "low": "Price is <b>low</b> for this neighbourhood",
    "typical": "Price is <b>typical</b> for this neighbourhood",
    "high": "Price is <b>high</b> for this neighbourhood",
}


def _fmt(value):
    return f"{value:,.0f}".replace(",", " ")


def bar_position(price_m2, low_m2, high_m2):
    """Return the marker position in percent of the bar width.

    The bar spans from 15% under ``low`` to 15% over ``high``; the
    typical band occupies the middle of the bar.
    """
    start, end = low_m2 * 0.85, high_m2 * 1.15
    pos = (price_m2 - start) / (end - start) * 100
    return max(2.0, min(98.0, pos))


def price_bar_html(assessment):
    """Return an HTML snippet showing the price indicator."""
    a = assessment
    start, end = a.low_m2 * 0.85, a.high_m2 * 1.15
    low_pct = (a.low_m2 - start) / (end - start) * 100
    high_pct = (a.high_m2 - start) / (end - start) * 100
    pos = bar_position(a.price_m2, a.low_m2, a.high_m2)
    color = COLORS[a.label]
    gradient = (f"linear-gradient(90deg,#34a853 0%,#34a853 {low_pct}%,"
                f"#fbbc04 {low_pct}%,#fbbc04 {high_pct}%,"
                f"#ea4335 {high_pct}%,#ea4335 100%)")
    return f"""
<div style="font-family:sans-serif;max-width:560px;margin:8px 0 18px">
  <div style="font-size:15px;margin-bottom:4px">{TEXT[a.label]}
    <span style="color:{color};font-weight:600">
      ({a.delta_pct:+.1f}% vs reference)</span></div>
  <div style="font-size:12px;opacity:.75;margin-bottom:32px">
    Typical range: {_fmt(a.low_m2)} - {_fmt(a.high_m2)} EUR/m2</div>
  <div style="position:relative;height:8px;border-radius:4px;
              background:{gradient}">
    <div style="position:absolute;left:{pos}%;top:-22px;
                transform:translateX(-50%);font-size:12px;
                font-weight:700;color:{color};white-space:nowrap">
      {_fmt(a.price_m2)} EUR/m2</div>
    <div style="position:absolute;left:{pos}%;top:-5px;width:18px;
                height:18px;margin-left:-9px;border-radius:50%;
                background:#fff;border:4px solid {color};
                box-sizing:border-box"></div>
  </div>
  <div style="display:flex;justify-content:space-between;font-size:11px;
              opacity:.7;margin-top:8px">
    <span>Cheap</span><span>Typical</span><span>Expensive</span></div>
</div>"""
