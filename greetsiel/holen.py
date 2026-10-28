#!/usr/bin/env python3
# Ostfriesen-Stübchen – Daten-Zwischenspeicher für die VRChat-Welt.
#
# Holt alle 15 Minuten (GitHub Actions):
#   • Wasserstand am Tidepegel KNOCK (Ems, WSV / PEGELONLINE), daraus letzte und nächste Hoch-/Niedrigwasser
#   • aktuelles Wetter an der DWD-Station Norden-Leybuchtpolder (1,6 km von Greetsiel) über Bright Sky,
#     bei Lücken automatisch Emden bzw. Norderney
# und schreibt eine kleine JSON-Datei, die VRChat von *.github.io laden darf.
#
# Nur Python-Standardbibliothek. Lokaler Test:  QUELLE_PEGEL=knock.json QUELLE_WETTER=wetter.json python3 holen.py
import json, math, os, sys, time, urllib.request
from datetime import datetime, timezone

PEGEL_URL = "https://www.pegelonline.wsv.de/webservices/rest-api/v2/stations/KNOCK/W/measurements.json?start=P2D"
WETTER_URL = "https://api.brightsky.dev/current_weather?lat=53.502&lon=7.098"
M2 = 12.4206012 * 3600.0          # mittlere Tidenperiode in Sekunden
MTHW, MTNW = 650.0, 346.0          # Kennwerte Knock (cm am Pegel, 2010–2020)
AUS = os.environ.get("AUSGABE", "public/greetsiel.json")


def laden(url, datei_env):
    datei = os.environ.get(datei_env)
    if datei:
        with open(datei, encoding="utf-8") as f:
            return json.load(f)
    req = urllib.request.Request(url, headers={"User-Agent": "OstfriesenStuebchen-VRChat (github.io Zwischenspeicher)"})
    for versuch in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:  # noqa
            fehler = e
            time.sleep(5 * (versuch + 1))
    raise fehler


def zeit(s):
    return datetime.fromisoformat(s).timestamp()


def gezeiten(messungen):
    pts = [(zeit(m["timestamp"]), float(m["value"])) for m in messungen if m.get("value") is not None]
    pts.sort()
    if len(pts) < 120:
        raise ValueError("zu wenige Pegelwerte")
    # 21-Minuten-Mittel glättet Wellen und Messrauschen
    t = [p[0] for p in pts]; w = [p[1] for p in pts]
    g = []
    j0 = 0; s = 0.0; q = []
    for i in range(len(pts)):
        lo, hi = t[i] - 630, t[i] + 630
        a = i; b = i
        while a > 0 and t[a - 1] >= lo: a -= 1
        while b < len(pts) - 1 and t[b + 1] <= hi: b += 1
        g.append(sum(w[a:b + 1]) / (b - a + 1))
    # Extrema: Maximum/Minimum in einem Fenster von ±3 h
    ext = []
    for i in range(len(pts)):
        lo, hi = t[i] - 3 * 3600, t[i] + 3 * 3600
        if t[i] - t[0] < 2 * 3600 or t[-1] - t[i] < 1.5 * 3600:
            continue  # am Rand nicht sicher
        a = i; b = i
        while a > 0 and t[a - 1] >= lo: a -= 1
        while b < len(pts) - 1 and t[b + 1] <= hi: b += 1
        fen = g[a:b + 1]
        if g[i] == max(fen) and (not ext or t[i] - ext[-1][0] > 4 * 3600 or ext[-1][2] != "HW"):
            ext.append((t[i], g[i], "HW"))
        elif g[i] == min(fen) and (not ext or t[i] - ext[-1][0] > 4 * 3600 or ext[-1][2] != "NW"):
            ext.append((t[i], g[i], "NW"))
    # gleiche Art direkt hintereinander zusammenfassen (Plateau)
    sauber = []
    for e in ext:
        if sauber and sauber[-1][2] == e[2]:
            if (e[2] == "HW" and e[1] > sauber[-1][1]) or (e[2] == "NW" and e[1] < sauber[-1][1]):
                sauber[-1] = e
        else:
            sauber.append(e)
    hw = [e for e in sauber if e[2] == "HW"]
    nw = [e for e in sauber if e[2] == "NW"]
    if not hw or not nw:
        raise ValueError("keine Hoch-/Niedrigwasser gefunden")
    letztes_hw, letztes_nw = hw[-1], nw[-1]
    # nächste Extrema: letzte + mittlere Periode, Höhen = Mittel aus den letzten Tiden
    hw_h = sum(e[1] for e in hw[-2:]) / len(hw[-2:])
    nw_h = sum(e[1] for e in nw[-2:]) / len(nw[-2:])
    jetzt_t, jetzt_w = pts[-1]
    nhw = letztes_hw[0]
    while nhw <= jetzt_t: nhw += M2
    nnw = letztes_nw[0]
    while nnw <= jetzt_t: nnw += M2
    steigt = g[-1] > g[max(0, len(g) - 16)]
    return {
        "pegel": "KNOCK",
        "messzeit": int(jetzt_t),
        "wasserstand_cm": round(jetzt_w, 1),
        "steigt": steigt,
        "letztes_hw": int(letztes_hw[0]), "letztes_hw_cm": round(letztes_hw[1], 1),
        "letztes_nw": int(letztes_nw[0]), "letztes_nw_cm": round(letztes_nw[1], 1),
        "naechstes_hw": int(nhw), "naechstes_hw_cm": round(hw_h, 1),
        "naechstes_nw": int(nnw), "naechstes_nw_cm": round(nw_h, 1),
        "mthw_cm": MTHW, "mtnw_cm": MTNW,
        # 0 = mittleres Niedrigwasser, 1 = mittleres Hochwasser (Sturmflut > 1, Extremebbe < 0)
        "anteil": round((jetzt_w - MTNW) / (MTHW - MTNW), 3),
    }


def wetter(daten):
    w = daten["weather"]
    quelle = {s["id"]: s for s in daten.get("sources", [])}
    st = quelle.get(w.get("source_id"), {})
    wolken = w.get("cloud_cover")
    regen = w.get("precipitation_60") if w.get("precipitation_60") is not None else (w.get("precipitation_30") or 0.0)
    sicht = w.get("visibility")
    wind = w.get("wind_speed_10") if w.get("wind_speed_10") is not None else (w.get("wind_speed_60") or 0.0)
    boe = w.get("wind_gust_speed_10") if w.get("wind_gust_speed_10") is not None else (w.get("wind_gust_speed_60") or 0.0)
    bed = (w.get("condition") or "").lower()
    icon = (w.get("icon") or "").lower()
    gewitter = bed == "thunderstorm" or "thunder" in icon
    schnee = bed in ("snow", "sleet") or icon in ("snow", "sleet")
    # Zustände wie im Computerwetter: 0 sonnig, 1 bewölkt, 2 neblig, 3 Regen, 4 Sturm
    if gewitter or wind >= 50 or boe >= 75:
        z = 4
    elif bed == "fog" or icon == "fog" or (sicht is not None and sicht < 1000):
        z = 2
    elif (regen or 0) >= 0.2 or bed in ("rain", "sleet", "snow", "hail"):
        z = 3
    elif wolken is not None and wolken >= 60:
        z = 1
    else:
        z = 0
    return {
        "station": st.get("station_name", ""),
        "station_abstand_m": st.get("distance"),
        "messzeit": int(zeit(w["timestamp"])),
        "zustand": z,
        "zustand_name": ["sonnig", "bewölkt", "neblig", "Regen", "Sturm"][z],
        "wolken_prozent": wolken,
        "regen_mm_h": regen,
        "sicht_m": sicht,
        "wind_kmh": wind,
        "boe_kmh": boe,
        "windrichtung_grad": w.get("wind_direction_10") if w.get("wind_direction_10") is not None else w.get("wind_direction_60"),
        "temperatur_c": w.get("temperature"),
        "gewitter": gewitter,
        "schnee": schnee,
        "bedingung": bed,
    }


def main():
    aus = {"version": 1, "erstellt": int(time.time()),
           "quellen": "Wasserstand: WSV, PEGELONLINE (Pegel Knock). Wetter: Deutscher Wetterdienst, über Bright Sky (brightsky.dev)."}
    fehler = []
    try:
        aus["tide"] = gezeiten(laden(PEGEL_URL, "QUELLE_PEGEL"))
    except Exception as e:
        fehler.append("tide: %s" % e)
    try:
        aus["wetter"] = wetter(laden(WETTER_URL, "QUELLE_WETTER"))
    except Exception as e:
        fehler.append("wetter: %s" % e)
    aus["fehler"] = fehler
    # alte Werte behalten, wenn eine Quelle ausfällt (die Welt erkennt veraltete Daten an der Messzeit)
    if os.path.exists(AUS):
        try:
            with open(AUS, encoding="utf-8") as f:
                alt = json.load(f)
            for k in ("tide", "wetter"):
                if k not in aus and k in alt:
                    aus[k] = alt[k]
        except Exception:
            pass
    os.makedirs(os.path.dirname(AUS) or ".", exist_ok=True)
    with open(AUS, "w", encoding="utf-8") as f:
        json.dump(aus, f, ensure_ascii=False, separators=(",", ":"))
    print(json.dumps(aus, ensure_ascii=False, indent=1))
    if "tide" not in aus and "wetter" not in aus:
        sys.exit(1)


if __name__ == "__main__":
    main()
