# Greetsiel-Daten für das Ostfriesen-Stübchen

`greetsiel.json` wird alle 15 Minuten vom Ablauf `.github/workflows/greetsiel-daten.yml` neu geschrieben.
Die VRChat-Welt lädt sie von `https://oliverds80.github.io/Club-Plakate/greetsiel/greetsiel.json`.

- Wasserstand: WSV, PEGELONLINE, Tidepegel Knock (Ems)
- Wetter: Deutscher Wetterdienst, Station Norden-Leybuchtpolder (ersatzweise Emden/Norderney), über Bright Sky (brightsky.dev)

Felder: `tide.anteil` (0 = mittleres Niedrigwasser, 1 = mittleres Hochwasser), Zeitpunkte in Sekunden seit 1970 (UTC),
`wetter.zustand` (0 sonnig, 1 bewölkt, 2 neblig, 3 Regen, 4 Sturm). Die Plakate in diesem Repository werden nicht verändert.
