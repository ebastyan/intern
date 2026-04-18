"""
Weather API - Meteo & Trafic analysis
Endpoints:
  GET /api/weather?type=ping
  GET /api/weather?type=residuals&metric=partners&date_from=X&date_to=Y
  GET /api/weather?type=buckets&variable=rain_sum&metric=partners
  GET /api/weather?type=lag_curve&variable=rain_sum&metric=partners
  GET /api/weather?type=extreme_days&metric=partners&limit=20
  GET /api/weather?type=overview&metric=partners
Metric options: partners | transactions | kg | ron
"""
from http.server import BaseHTTPRequestHandler
import json
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from urllib.parse import urlparse, parse_qs
from decimal import Decimal
from datetime import date, datetime

METRICS = {
    "partners":     ("COUNT(DISTINCT t.cnp)",                     "partners"),
    "transactions": ("COUNT(*)",                                  "transactions"),
    "kg":           ("COALESCE(SUM(i.weight_kg), 0)",             "kg"),
    "ron":          ("COALESCE(SUM(t.gross_value), 0)",           "ron"),
}

def get_db():
    url = os.environ.get("POSTGRES_URL") or os.environ.get("DATABASE_URL") or os.environ.get("POSTGRES_URL_NO_SSL")
    if not url:
        raise Exception("No database URL configured")
    return psycopg2.connect(url, cursor_factory=RealDictCursor)

def json_default(obj):
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, (date, datetime)):
        return obj.isoformat()
    raise TypeError(f"Not serializable: {type(obj)}")

def resolve_metric(name):
    if name not in METRICS:
        raise ValueError(f"Unknown metric: {name}")
    return METRICS[name]

BUCKET_SPECS = {
    "rain_sum":          [(None, 0.1, "0mm (uscat)"), (0.1, 2, "0.1-2mm (slab)"),
                          (2, 10, "2-10mm (mediu)"), (10, None, ">10mm (puternic)")],
    "snowfall_sum":      [(None, 0.1, "0cm"), (0.1, 2, "0.1-2cm"),
                          (2, 10, "2-10cm"), (10, None, ">10cm")],
    "temp_max":          [(None, -5, "<-5°C (geros)"), (-5, 0, "-5 - 0°C"),
                          (0, 10, "0-10°C"), (10, 20, "10-20°C"),
                          (20, 30, "20-30°C"), (30, None, ">30°C (canicula)")],
    "temp_min":          [(None, -10, "<-10°C"), (-10, 0, "-10 - 0°C"),
                          (0, 10, "0-10°C"), (10, 20, "10-20°C"),
                          (20, None, ">20°C")],
    "wind_gusts_max":    [(None, 30, "<30 km/h"), (30, 50, "30-50 km/h"),
                          (50, 70, "50-70 km/h"), (70, None, ">70 km/h")],
    "humidity_mean":     [(None, 50, "<50%"), (50, 70, "50-70%"),
                          (70, 85, "70-85%"), (85, None, ">85%")],
    "cloudcover_mean":   [(None, 30, "Senin (<30%)"), (30, 70, "Partial (30-70%)"),
                          (70, None, "Inchis (>70%)")],
}

DOW_NAMES_RO = ["Luni", "Marti", "Miercuri", "Joi", "Vineri", "Sambata", "Duminica"]

def _weather_desc(row):
    bits = []
    tmax = row.get("temp_max")
    tmin = row.get("temp_min")
    if tmax is not None:
        if tmin is not None:
            bits.append(f"{float(tmin):.0f}..{float(tmax):.0f}°C")
        else:
            bits.append(f"{float(tmax):.0f}°C")
    ps = row.get("precipitation_sum")
    if ps is not None and float(ps) >= 0.5:
        bits.append(f"{float(ps):.1f}mm ploaie")
    ss = row.get("snowfall_sum")
    if ss is not None and float(ss) >= 0.5:
        bits.append(f"{float(ss):.1f}cm zapada")
    sd = row.get("snow_depth_max")
    if sd is not None and float(sd) >= 0.02:
        bits.append(f"strat {float(sd)*100:.0f}cm")
    wsm = row.get("wind_speed_max")
    if wsm is not None and float(wsm) >= 30:
        bits.append(f"vant {float(wsm):.0f}km/h")
    wgm = row.get("wind_gusts_max")
    if wgm is not None and float(wgm) >= 50:
        bits.append(f"rafale {float(wgm):.0f}km/h")
    hum = row.get("humidity_mean")
    if hum is not None and float(hum) >= 85:
        bits.append(f"umed ({float(hum):.0f}%)")
    cc = row.get("cloudcover_mean")
    if cc is not None and float(cc) >= 80:
        bits.append("nori inchisi")
    elif cc is not None and float(cc) <= 25:
        bits.append("senin")
    return ", ".join(bits) if bits else "vreme calma"

def _day_example(row):
    d = row.get("date")
    date_str = d.isoformat() if hasattr(d, "isoformat") else str(d)
    dow_idx = row.get("dow")
    dow = DOW_NAMES_RO[(int(dow_idx) - 1) % 7] if dow_idx else ""
    return {
        "date": date_str,
        "dow": dow,
        "actual": float(row["value"]) if row.get("value") is not None else None,
        "baseline": float(row["baseline"]) if row.get("baseline") is not None else None,
        "residual": float(row["residual"]) if row.get("residual") is not None else None,
        "residual_pct": row.get("residual_pct"),
        "weather": _weather_desc(row),
    }

def find_threshold(pairs, min_pts_per_side=15):
    """Given list of (x, residual) pairs, find the split point that maximizes
    |t-statistic| of residual means. Returns dict or None."""
    if len(pairs) < 30:
        return None
    xs = sorted(set(p[0] for p in pairs))
    best = None
    for x in xs:
        below = [p[1] for p in pairs if p[0] < x]
        above = [p[1] for p in pairs if p[0] >= x]
        if len(below) < min_pts_per_side or len(above) < min_pts_per_side:
            continue
        mb = sum(below) / len(below); ma = sum(above) / len(above)
        vb = sum((b - mb) ** 2 for b in below) / (len(below) - 1) if len(below) > 1 else 1
        va = sum((a - ma) ** 2 for a in above) / (len(above) - 1) if len(above) > 1 else 1
        se = ((vb / len(below)) + (va / len(above))) ** 0.5
        if se == 0:
            continue
        t = abs(ma - mb) / se
        if best is None or t > best["t_stat"]:
            best = {"threshold": x, "above_mean": ma, "below_mean": mb,
                    "effect": ma - mb, "t_stat": t,
                    "n_above": len(above), "n_below": len(below)}
    return best


class handler(BaseHTTPRequestHandler):
    def _send(self, status, payload):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(payload, default=json_default).encode("utf-8"))

    def residuals(self, cur, metric_name, date_from, date_to):
        agg_sql, label = resolve_metric(metric_name)
        where = ["EXTRACT(ISODOW FROM t.date) <> 7"]
        args = []
        if date_from: where.append("t.date >= %s"); args.append(date_from)
        if date_to:   where.append("t.date <= %s"); args.append(date_to)
        where_sql = " AND ".join(where)

        cur.execute(f"""
            WITH daily AS (
              SELECT t.date,
                     EXTRACT(ISODOW FROM t.date)::int AS dow,
                     {agg_sql} AS value
              FROM transactions t
              LEFT JOIN transaction_items i ON i.document_id = t.document_id
              WHERE {where_sql}
              GROUP BY t.date
            )
            SELECT d.date, d.dow, d.value,
                   (
                     SELECT PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY d2.value)
                     FROM daily d2
                     WHERE d2.dow = d.dow
                       AND d2.date <> d.date
                       AND d2.date BETWEEN d.date - INTERVAL '28 days' AND d.date - INTERVAL '1 day'
                   ) AS baseline,
                   w.temp_max, w.temp_min, w.temp_mean, w.precipitation_sum, w.rain_sum,
                   w.snowfall_sum, w.snow_depth_max, w.wind_speed_max, w.wind_gusts_max,
                   w.pressure_mean, w.humidity_mean, w.cloudcover_mean, w.weather_code
            FROM daily d
            LEFT JOIN weather_oradea w ON w.date = d.date
            ORDER BY d.date
        """, args)
        out = []
        for r in cur.fetchall():
            rec = dict(r)
            if rec["baseline"] is not None:
                rec["residual"] = float(rec["value"]) - float(rec["baseline"])
                rec["residual_pct"] = (rec["residual"] / float(rec["baseline"]) * 100.0) if rec["baseline"] else None
            else:
                rec["residual"] = None
                rec["residual_pct"] = None
            out.append(rec)
        return {"metric": label, "residuals": out}

    def buckets(self, cur, metric_name, variable, date_from, date_to):
        if variable not in BUCKET_SPECS:
            return {"error": f"No bucket spec for variable {variable}",
                    "available": list(BUCKET_SPECS.keys())}
        data = self.residuals(cur, metric_name, date_from, date_to)
        rows = [r for r in data["residuals"] if r["residual"] is not None and r.get(variable) is not None]
        out = []
        for lo, hi, label in BUCKET_SPECS[variable]:
            in_bucket_res = []
            in_bucket_base = []
            for r in rows:
                v = float(r[variable])
                if lo is not None and v < lo: continue
                if hi is not None and v >= hi: continue
                in_bucket_res.append(r["residual"])
                if r["baseline"] is not None:
                    in_bucket_base.append(float(r["baseline"]))
            if not in_bucket_res:
                out.append({"bucket": label, "lo": lo, "hi": hi, "n": 0,
                            "mean_residual": None, "mean_residual_pct": None})
                continue
            mean = sum(in_bucket_res) / len(in_bucket_res)
            mean_b = sum(in_bucket_base) / len(in_bucket_base) if in_bucket_base else None
            pct = (mean / mean_b * 100.0) if mean_b else None
            out.append({"bucket": label, "lo": lo, "hi": hi, "n": len(in_bucket_res),
                        "mean_residual": round(mean, 2),
                        "mean_residual_pct": round(pct, 2) if pct is not None else None})
        return {"metric": data["metric"], "variable": variable, "buckets": out}

    def lag_curve(self, cur, metric_name, variable, date_from, date_to):
        supported = set(BUCKET_SPECS.keys()) | {"temp_max", "temp_min", "temp_mean",
                                                 "rain_sum", "snowfall_sum",
                                                 "wind_speed_max", "wind_gusts_max",
                                                 "humidity_mean"}
        if variable not in supported:
            return {"error": f"Variable not supported: {variable}"}
        data = self.residuals(cur, metric_name, date_from, date_to)
        rows = data["residuals"]
        by_date = {}
        for r in rows:
            d = r["date"].isoformat() if hasattr(r["date"], "isoformat") else r["date"]
            by_date[d] = r
        sorted_dates = sorted(by_date.keys())
        lags = list(range(-2, 4))
        out = []
        for lag in lags:
            pairs = []
            for idx, d in enumerate(sorted_dates):
                tgt_idx = idx + lag
                if tgt_idx < 0 or tgt_idx >= len(sorted_dates):
                    continue
                src = by_date[d]
                tgt = by_date[sorted_dates[tgt_idx]]
                if src.get(variable) is None or tgt.get("residual") is None:
                    continue
                pairs.append((float(src[variable]), float(tgt["residual"])))
            if len(pairs) < 10:
                out.append({"lag": lag, "n": len(pairs), "correlation": None})
                continue
            n = len(pairs)
            sx = sum(p[0] for p in pairs); sy = sum(p[1] for p in pairs)
            sxx = sum(p[0] * p[0] for p in pairs); syy = sum(p[1] * p[1] for p in pairs)
            sxy = sum(p[0] * p[1] for p in pairs)
            denom = ((n * sxx - sx * sx) * (n * syy - sy * sy)) ** 0.5
            r = (n * sxy - sx * sy) / denom if denom else 0
            out.append({"lag": lag, "n": n, "correlation": round(r, 3)})
        return {"metric": data["metric"], "variable": variable, "lags": out}

    def extreme_days(self, cur, metric_name, date_from, date_to, limit=20):
        data = self.residuals(cur, metric_name, date_from, date_to)
        rows = [r for r in data["residuals"] if r["residual"] is not None]
        rows.sort(key=lambda r: abs(r["residual"]), reverse=True)
        return {"metric": data["metric"], "extreme_days": rows[:limit]}

    def overview(self, cur, metric_name, date_from, date_to):
        data = self.residuals(cur, metric_name, date_from, date_to)
        rows = [r for r in data["residuals"] if r["residual"] is not None]
        if len(rows) < 30:
            return {"metric": data["metric"], "insights": [], "note": "Nu sunt suficiente date"}
        insights = []

        # Plain-language labels for narratives
        METRIC_LABEL = {"partners": "parteneri", "transactions": "tranzactii",
                        "kg": "kg de material", "ron": "RON"}
        mlabel = METRIC_LABEL.get(metric_name, metric_name)
        VAR_LABEL = {
            "rain_sum": "ploaia",
            "snowfall_sum": "zapada",
            "temp_max": "temperatura maxima",
            "temp_min": "temperatura minima",
            "wind_gusts_max": "rafalele de vant",
            "wind_speed_max": "viteza vantului",
            "humidity_mean": "umiditatea",
            "cloudcover_mean": "norii",
            "precipitation_sum": "precipitatiile totale",
        }
        VAR_UNIT = {
            "rain_sum": "mm", "snowfall_sum": "cm", "temp_max": "°C", "temp_min": "°C",
            "wind_gusts_max": "km/h", "wind_speed_max": "km/h",
            "humidity_mean": "%", "cloudcover_mean": "%", "precipitation_sum": "mm",
        }

        # Family A: bucket comparisons — narrative form with example days
        for var in ["rain_sum", "temp_max", "wind_gusts_max", "snowfall_sum",
                    "humidity_mean", "cloudcover_mean"]:
            bres = self.buckets(cur, metric_name, var, date_from, date_to)
            candidates = [b for b in bres.get("buckets", [])
                          if b.get("mean_residual_pct") is not None and b.get("n", 0) >= 10]
            if not candidates:
                continue
            top = max(candidates, key=lambda b: abs(b["mean_residual_pct"]))
            pct = top["mean_residual_pct"]
            if abs(pct) < 5:
                continue
            direction = "mai multi" if pct > 0 else "mai putini"
            vlbl = VAR_LABEL.get(var, var)
            text = (f"Cand {vlbl} e in categoria \"{top['bucket']}\", "
                    f"vin cu {abs(pct):.0f}% {direction} {mlabel} decat intr-o zi normala. "
                    f"Observat pe {top['n']} zile din perioada selectata.")
            # Find top example days in this bucket
            lo, hi = top["lo"], top["hi"]
            bucket_rows = []
            for r in rows:
                if r.get(var) is None: continue
                v = float(r[var])
                if lo is not None and v < lo: continue
                if hi is not None and v >= hi: continue
                bucket_rows.append(r)
            # Sort by residual in the direction of the effect
            bucket_rows.sort(key=lambda r: r["residual"], reverse=(pct > 0))
            examples = [_day_example(r) for r in bucket_rows[:8]]
            insights.append({
                "kind": "bucket",
                "variable": var,
                "bucket": top["bucket"],
                "effect_pct": pct,
                "n": top["n"],
                "text": text,
                "examples": examples,
            })

        # Family B: threshold detection — narrative + examples above the threshold
        for var in ["temp_max", "temp_min", "wind_speed_max", "wind_gusts_max",
                    "precipitation_sum", "humidity_mean"]:
            pairs = [(float(r[var]), r["residual"]) for r in rows if r.get(var) is not None]
            t = find_threshold(pairs)
            if not t or t["t_stat"] < 2.0:
                continue
            above_minus_below = t["above_mean"] - t["below_mean"]
            direction = "CRESTE" if above_minus_below > 0 else "SCADE"
            diff_abs = abs(above_minus_below)
            vlbl = VAR_LABEL.get(var, var)
            unit = VAR_UNIT.get(var, "")
            text = (f"Am gasit un prag la {vlbl} = {t['threshold']:.1f}{unit}. "
                    f"Cand e peste acest prag, traficul {direction} cu ~{diff_abs:.0f} {mlabel}/zi "
                    f"fata de zilele sub prag. ({t['n_above']} zile peste, {t['n_below']} sub.)")
            # Example days above the threshold, sorted by residual in effect direction
            above_rows = [r for r in rows if r.get(var) is not None and float(r[var]) >= t["threshold"]]
            above_rows.sort(key=lambda r: r["residual"], reverse=(above_minus_below > 0))
            examples = [_day_example(r) for r in above_rows[:8]]
            insights.append({
                "kind": "threshold",
                "variable": var,
                "threshold": round(t["threshold"], 2),
                "above_effect": round(t["above_mean"], 1),
                "below_effect": round(t["below_mean"], 1),
                "t_stat": round(t["t_stat"], 2),
                "n_above": t["n_above"],
                "n_below": t["n_below"],
                "text": text,
                "examples": examples,
            })

        # Family C: lag analysis — narrative form
        for var in ["rain_sum", "snowfall_sum", "temp_max", "wind_gusts_max"]:
            lc = self.lag_curve(cur, metric_name, var, date_from, date_to)
            lags = [l for l in lc.get("lags", []) if l.get("correlation") is not None]
            if not lags:
                continue
            peak = max(lags, key=lambda l: abs(l["correlation"]))
            zero = next((l for l in lags if l["lag"] == 0), None)
            if peak["lag"] == 0 or abs(peak["correlation"]) < 0.15 or \
               not zero or abs(peak["correlation"]) <= abs(zero["correlation"]):
                continue
            vlbl = VAR_LABEL.get(var, var)
            lag_label = (f"{peak['lag']} zile dupa" if peak["lag"] > 0
                         else f"{abs(peak['lag'])} zile inainte")
            direction_desc = ("creste" if peak["correlation"] > 0 else "scade")
            text = (f"{vlbl.capitalize()} NU are efect imediat, dar la {lag_label} "
                    f"traficul {direction_desc} (corelatie {peak['correlation']:+.2f} la lag={peak['lag']} "
                    f"vs {zero['correlation']:+.2f} in aceeasi zi). "
                    f"Oamenii reactioneaza cu intarziere.")
            # Lag examples: find days where extreme weather was followed (peak["lag"] later)
            # by large residual in the expected direction
            sorted_rows = sorted(rows, key=lambda r: str(r["date"]))
            lag_val = peak["lag"]
            sign = 1 if peak["correlation"] > 0 else -1
            pair_scores = []
            for idx, src in enumerate(sorted_rows):
                if src.get(var) is None: continue
                tgt_idx = idx + lag_val
                if tgt_idx < 0 or tgt_idx >= len(sorted_rows): continue
                tgt = sorted_rows[tgt_idx]
                if tgt.get("residual") is None: continue
                score = float(src[var]) * tgt["residual"] * sign
                pair_scores.append((src, tgt, score))
            pair_scores.sort(key=lambda p: p[2], reverse=True)
            lag_examples = []
            for src, tgt, _ in pair_scores[:8]:
                ex = _day_example(tgt)
                ex["lag_trigger"] = {
                    "date": src["date"].isoformat() if hasattr(src["date"], "isoformat") else str(src["date"]),
                    "variable": var,
                    "value": float(src[var]) if src.get(var) is not None else None,
                    "weather": _weather_desc(src),
                    "lag": lag_val,
                }
                lag_examples.append(ex)
            insights.append({
                "kind": "lag",
                "variable": var,
                "lag": peak["lag"],
                "correlation_at_peak": peak["correlation"],
                "correlation_at_zero": zero["correlation"],
                "text": text,
                "examples": lag_examples,
            })

        # Family D: curated interaction patterns — narrative form
        def avg_res(filter_fn):
            vals = [r["residual"] for r in rows if filter_fn(r)]
            n = len(vals)
            return (sum(vals) / n if n else None), n

        cold_wet_fn = lambda r: (r.get("temp_max") is not None and float(r["temp_max"]) < 5
                                 and r.get("precipitation_sum") is not None and float(r["precipitation_sum"]) > 2)
        hot_dry_fn = lambda r: (r.get("temp_max") is not None and float(r["temp_max"]) > 30
                                and r.get("precipitation_sum") is not None and float(r["precipitation_sum"]) < 0.5)
        patterns = []
        cw = avg_res(cold_wet_fn)
        hd = avg_res(hot_dry_fn)
        if cw[1] >= 5:
            patterns.append(("Frig + ploaie (sub 5°C si peste 2mm)", cw[0], cw[1], cold_wet_fn))
        if hd[1] >= 5:
            patterns.append(("Canicula uscata (peste 30°C, fara ploaie)", hd[0], hd[1], hot_dry_fn))

        for name, val, n, fn in patterns:
            if val is None or abs(val) < 3:
                continue
            direction = "mai multi" if val > 0 else "mai putini"
            text = (f"{name}: au venit in medie {abs(val):.0f} {mlabel} {direction} "
                    f"decat intr-o zi normala. Observat pe {n} zile.")
            matching = [r for r in rows if fn(r)]
            matching.sort(key=lambda r: r["residual"], reverse=(val > 0))
            examples = [_day_example(r) for r in matching[:8]]
            insights.append({
                "kind": "interaction",
                "pattern": name,
                "effect": round(val, 1),
                "n": n,
                "text": text,
                "examples": examples,
            })

        def score(i):
            return abs(i.get("effect_pct") or i.get("above_effect") or
                       (i.get("correlation_at_peak") or 0) * 100 or
                       i.get("effect") or 0)
        insights.sort(key=lambda i: -score(i))

        # Ranking: head-to-head of weather categories (narrower for resolution)
        CATEGORIES = [
            # Precipitation (rain)
            ("🌧️", "Ploaie torentiala", ">20mm",
             lambda r: r.get("precipitation_sum") is not None and float(r["precipitation_sum"]) > 20),
            ("🌧️", "Ploaie puternica", "10-20mm",
             lambda r: r.get("precipitation_sum") is not None and 10 < float(r["precipitation_sum"]) <= 20),
            ("🌧️", "Ploaie moderata", "5-10mm",
             lambda r: r.get("precipitation_sum") is not None and 5 < float(r["precipitation_sum"]) <= 10),
            ("🌧️", "Ploaie usoara", "2-5mm",
             lambda r: r.get("precipitation_sum") is not None and 2 < float(r["precipitation_sum"]) <= 5),
            ("🌧️", "Ploaie fina", "0.5-2mm",
             lambda r: r.get("precipitation_sum") is not None and 0.5 < float(r["precipitation_sum"]) <= 2),
            # Snow
            ("❄️", "Zapada abundenta", ">10cm",
             lambda r: r.get("snowfall_sum") is not None and float(r["snowfall_sum"]) > 10),
            ("❄️", "Zapada medie", "3-10cm",
             lambda r: r.get("snowfall_sum") is not None and 3 < float(r["snowfall_sum"]) <= 10),
            ("❄️", "Ninsoare usoara", "1-3cm",
             lambda r: r.get("snowfall_sum") is not None and 1 < float(r["snowfall_sum"]) <= 3),
            # Cold
            ("🥶", "Ger extrem", "<-10°C max",
             lambda r: r.get("temp_max") is not None and float(r["temp_max"]) < -10),
            ("🥶", "Ger", "-10..-5°C max",
             lambda r: r.get("temp_max") is not None and -10 <= float(r["temp_max"]) < -5),
            ("🥶", "Frig intens", "-5..0°C max",
             lambda r: r.get("temp_max") is not None and -5 <= float(r["temp_max"]) < 0),
            ("🥶", "Frig", "0..5°C max",
             lambda r: r.get("temp_max") is not None and 0 <= float(r["temp_max"]) < 5),
            ("🥶", "Rece", "5..10°C max",
             lambda r: r.get("temp_max") is not None and 5 <= float(r["temp_max"]) < 10),
            # Hot
            ("🔥", "Canicula extrema", ">35°C max",
             lambda r: r.get("temp_max") is not None and float(r["temp_max"]) > 35),
            ("🔥", "Canicula", "32..35°C max",
             lambda r: r.get("temp_max") is not None and 32 < float(r["temp_max"]) <= 35),
            ("🔥", "Foarte cald", "30..32°C max",
             lambda r: r.get("temp_max") is not None and 30 < float(r["temp_max"]) <= 32),
            ("🔥", "Cald", "25..30°C max",
             lambda r: r.get("temp_max") is not None and 25 < float(r["temp_max"]) <= 30),
            # Wind
            ("💨", "Furtuna", ">90km/h rafale",
             lambda r: r.get("wind_gusts_max") is not None and float(r["wind_gusts_max"]) > 90),
            ("💨", "Rafale mari", "70-90km/h",
             lambda r: r.get("wind_gusts_max") is not None and 70 < float(r["wind_gusts_max"]) <= 90),
            ("💨", "Rafale medii", "50-70km/h",
             lambda r: r.get("wind_gusts_max") is not None and 50 < float(r["wind_gusts_max"]) <= 70),
            # Humidity / sky
            ("💧", "Umiditate extrema", ">92%",
             lambda r: r.get("humidity_mean") is not None and float(r["humidity_mean"]) > 92),
            ("💧", "Umiditate ridicata", "85-92%",
             lambda r: r.get("humidity_mean") is not None and 85 < float(r["humidity_mean"]) <= 92),
            ("💧", "Umiditate scazuta", "<45%",
             lambda r: r.get("humidity_mean") is not None and float(r["humidity_mean"]) < 45),
            ("☀️", "Senin", "nori <20%",
             lambda r: r.get("cloudcover_mean") is not None and float(r["cloudcover_mean"]) < 20),
            ("☁️", "Mohorat", "nori >90%",
             lambda r: r.get("cloudcover_mean") is not None and float(r["cloudcover_mean"]) > 90),
        ]

        STRONG = 15.0  # |residual_pct| >= 15% = strong individual-day effect
        ranking = []
        for emoji, name, range_str, fn in CATEGORIES:
            matching = [r for r in rows if fn(r) and r.get("residual_pct") is not None]
            if len(matching) < 3:
                continue
            avg_pct = sum(float(r["residual_pct"]) for r in matching) / len(matching)
            n_strong_neg = sum(1 for r in matching if float(r["residual_pct"]) <= -STRONG)
            n_strong_pos = sum(1 for r in matching if float(r["residual_pct"]) >= STRONG)
            if avg_pct < 0:
                sorted_matching = sorted(matching, key=lambda r: float(r["residual"]))
            else:
                sorted_matching = sorted(matching, key=lambda r: float(r["residual"]), reverse=True)
            examples = [_day_example(r) for r in sorted_matching[:8]]
            ranking.append({
                "emoji": emoji,
                "name": name,
                "range": range_str,
                "effect_pct": round(avg_pct, 1),
                "n": len(matching),
                "n_strong_neg": n_strong_neg,
                "n_strong_pos": n_strong_pos,
                "examples": examples,
                "worst_day": _day_example(sorted_matching[0]) if avg_pct < 0 else None,
                "best_day":  _day_example(sorted_matching[0]) if avg_pct > 0 else None,
            })

        ranking.sort(key=lambda r: r["effect_pct"])

        return {"metric": data["metric"], "ranking": ranking, "insights": insights}

    def do_GET(self):
        try:
            parsed = urlparse(self.path)
            params = parse_qs(parsed.query)
            qtype = params.get("type", [""])[0]

            conn = get_db()
            cur = conn.cursor()

            if qtype == "ping":
                result = {"ok": True, "endpoint": "weather"}
            elif qtype == "residuals":
                metric = params.get("metric", ["partners"])[0]
                df = params.get("date_from", [None])[0]
                dt = params.get("date_to", [None])[0]
                result = self.residuals(cur, metric, df, dt)
            elif qtype == "buckets":
                metric = params.get("metric", ["partners"])[0]
                variable = params.get("variable", ["rain_sum"])[0]
                df = params.get("date_from", [None])[0]
                dt = params.get("date_to", [None])[0]
                result = self.buckets(cur, metric, variable, df, dt)
            elif qtype == "lag_curve":
                metric = params.get("metric", ["partners"])[0]
                variable = params.get("variable", ["rain_sum"])[0]
                df = params.get("date_from", [None])[0]
                dt = params.get("date_to", [None])[0]
                result = self.lag_curve(cur, metric, variable, df, dt)
            elif qtype == "extreme_days":
                metric = params.get("metric", ["partners"])[0]
                df = params.get("date_from", [None])[0]
                dt = params.get("date_to", [None])[0]
                lim = int(params.get("limit", ["20"])[0])
                result = self.extreme_days(cur, metric, df, dt, lim)
            elif qtype == "overview":
                metric = params.get("metric", ["partners"])[0]
                df = params.get("date_from", [None])[0]
                dt = params.get("date_to", [None])[0]
                result = self.overview(cur, metric, df, dt)
            else:
                result = {"error": "Unknown query type", "got": qtype}

            conn.close()
            self._send(200, result)
        except Exception as e:
            self._send(500, {"error": str(e)})

    def do_POST(self):
        self._send(405, {"error": "POST not supported on /api/weather"})
