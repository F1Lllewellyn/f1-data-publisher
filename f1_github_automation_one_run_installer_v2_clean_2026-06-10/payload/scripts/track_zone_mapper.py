#!/usr/bin/env python3
"""
Track-zone mapper skeleton.

Input:
- location feature rows with x/y coordinates
- a track zone map CSV

Output:
- rows tagged with zone_id/zone_name/zone_type

This is intentionally simple: rectangular bounding boxes first. Later versions can use polygons.
"""

import argparse
import pandas as pd

def map_zone(row, zones):
    x = row.get("x")
    y = row.get("y")
    for _, z in zones.iterrows():
        try:
            if (
                float(z["x_min"]) <= float(x) <= float(z["x_max"]) and
                float(z["y_min"]) <= float(y) <= float(z["y_max"])
            ):
                return z.to_dict()
        except Exception:
            continue
    return {"zone_id": "unknown", "zone_name": "unknown", "zone_type": "unknown", "sector": ""}

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--location-csv", required=True)
    p.add_argument("--zone-map-csv", required=True)
    p.add_argument("--output-csv", required=True)
    args = p.parse_args()

    loc = pd.read_csv(args.location_csv)
    zones = pd.read_csv(args.zone_map_csv)
    out = []
    for _, r in loc.iterrows():
        z = map_zone(r, zones)
        row = r.to_dict()
        row.update({f"track_{k}": v for k, v in z.items()})
        out.append(row)
    pd.DataFrame(out).to_csv(args.output_csv, index=False)

if __name__ == "__main__":
    main()
