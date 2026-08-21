# SPDX-License-Identifier: MIT
"""
Extract the Elia AdeqFlex 2025 EV charging tables into CSV.

Source: ``AdeqFlex2025_AssumptionsWorkbook.xlsx``, sheet ``3.3. DSR end-user``
(Adequacy and Flexibility study 2026-2036). The workbook is **not** redistributed
in this repository; point ``--workbook`` at a local copy.

Four tables are extracted, all Belgium-wide. Wallonia is assumed to share them —
Elia only regionalises the smart-meter driver (§3.3.1), not the profiles.

===============================================  ==============================
``ev_operation_mode_shares.csv``                 V0 / V1H / V2H / V1M / V2M
                                                 share of the EV fleet, per Elia
                                                 scenario, 2023-2036
``ev_v0_location_shares.csv``                    home / work / public split
                                                 *inside* V0, 2025-2036
``ev_daily_profiles.csv``                        24-hour normalised charging
                                                 profiles for V0 and V1H/V2H
``ev_availability.csv``                          plugged-in share available to
                                                 V1M / V2M, 24 hours
===============================================  ==============================

The workbook rounds every profile to 3 decimals, so a daily profile sums to
0.995-1.002 rather than 1.000. Normalise before use — ``build_transport_demand.py``
already does (`shape / shape.sum()`).

Usage::

    python scripts/walloon_scripts/extract_elia_adeqflex_ev.py \
        --workbook ~/temp/AdeqFlex2025_AssumptionsWorkbook.xlsx
"""

from __future__ import annotations

import argparse
from pathlib import Path

import openpyxl
import pandas as pd

SHEET = "3.3. DSR end-user"
DEFAULT_OUT = Path("data/walloon/elia_adeqflex2025")

#: Operation-mode block: first data row per scenario, and the row labels.
_MODE_SCENARIOS = {
    52: "Current commitments",
    57: "Constrained Transition",
    62: "Prosumer Power",
    67: "Current commitments - High Flex",
    72: "Current commitments - Low Flex",
}
_MODES = ["V0", "V1H", "V2H", "V1M", "V2M"]
_MODE_YEAR_ROW = 51  # 2023 … 2036 in columns 4..17
_MODE_SHARE_OFFSET = 26  # the "% of the fleet" block sits 26 rows below

#: V0 location shares (rows 194-196), years in row 193 columns 3..14.
_V0_SHARE_ROWS = {194: "home", 195: "work", 196: "public"}
_V0_SHARE_YEAR_ROW = 193

#: V0 hourly profiles: rows 200-223, hour in column 3.
_V0_PROFILE_FIRST_ROW = 200
_V0_PROFILE_COLUMNS = {
    4: ("home", ""),
    5: ("work", ""),
    6: ("public", ""),
    7: ("aggregate", "2026"),
    8: ("aggregate", "2036"),
}

#: V1H/V2H hourly profiles: rows 235-258. Home is crossed
#: tariff × sky × PV; work has a single column.
_V1H_PROFILE_FIRST_ROW = 235
_V1H_PROFILE_COLUMNS = {
    4: ("home", "capacity_tariff:sunny:with_pv"),
    5: ("home", "capacity_tariff:sunny:without_pv"),
    6: ("home", "capacity_tariff:cloudy:with_pv"),
    7: ("home", "capacity_tariff:cloudy:without_pv"),
    8: ("home", "time_of_use:sunny:with_pv"),
    9: ("home", "time_of_use:sunny:without_pv"),
    10: ("home", "time_of_use:cloudy:with_pv"),
    11: ("home", "time_of_use:cloudy:without_pv"),
    12: ("work", "with_pv"),
}

#: EV availability for V1M/V2M: rows 374-397.
_AVAIL_FIRST_ROW = 374
_AVAIL_COLUMNS = {4: "2026", 5: "2036"}

_HOURS = 24


def _cells(workbook: Path) -> dict[int, tuple]:
    wb = openpyxl.load_workbook(workbook, read_only=True, data_only=True)
    ws = wb[SHEET]
    return {
        i: row
        for i, row in enumerate(ws.iter_rows(max_row=400, max_col=20, values_only=True), 1)
    }


def _num(value: object) -> float | None:
    return float(value) if isinstance(value, (int, float)) else None


def operation_mode_shares(rows: dict[int, tuple]) -> pd.DataFrame:
    years = [int(y) for y in rows[_MODE_YEAR_ROW][3:17] if isinstance(y, (int, float))]
    out = []
    for first, scenario in _MODE_SCENARIOS.items():
        for offset, mode in enumerate(_MODES):
            units = rows[first + offset]
            share = rows[first + offset + _MODE_SHARE_OFFSET]
            for col, year in enumerate(years, start=3):
                out.append(
                    {
                        "scenario": scenario,
                        "mode": mode,
                        "year": year,
                        "share": _num(share[col]),
                        "units_kveh": _num(units[col]),
                    }
                )
    return pd.DataFrame(out)


def v0_location_shares(rows: dict[int, tuple]) -> pd.DataFrame:
    years = [int(y) for y in rows[_V0_SHARE_YEAR_ROW][2:14] if isinstance(y, (int, float))]
    out = []
    for row, location in _V0_SHARE_ROWS.items():
        for col, year in enumerate(years, start=2):
            out.append(
                {"location": location, "year": year, "share": _num(rows[row][col])}
            )
    return pd.DataFrame(out)


def _profiles(
    rows: dict[int, tuple], first_row: int, columns: dict, mode: str
) -> pd.DataFrame:
    out = []
    for hour in range(_HOURS):
        row = rows[first_row + hour]
        assert int(row[2]) == hour, f"hour column drifted at row {first_row + hour}"
        for col, (location, variant) in columns.items():
            out.append(
                {
                    "mode": mode,
                    "location": location,
                    "variant": variant,
                    "hour": hour,
                    "value": _num(row[col - 1]),
                }
            )
    return pd.DataFrame(out)


def daily_profiles(rows: dict[int, tuple]) -> pd.DataFrame:
    return pd.concat(
        [
            _profiles(rows, _V0_PROFILE_FIRST_ROW, _V0_PROFILE_COLUMNS, "V0"),
            _profiles(rows, _V1H_PROFILE_FIRST_ROW, _V1H_PROFILE_COLUMNS, "V1H_V2H"),
        ],
        ignore_index=True,
    )


def availability(rows: dict[int, tuple]) -> pd.DataFrame:
    out = []
    for hour in range(_HOURS):
        row = rows[_AVAIL_FIRST_ROW + hour]
        assert int(row[2]) == hour, f"hour column drifted at row {_AVAIL_FIRST_ROW + hour}"
        for col, year in _AVAIL_COLUMNS.items():
            out.append({"year": year, "hour": hour, "availability": _num(row[col - 1])})
    return pd.DataFrame(out)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workbook", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    rows = _cells(args.workbook)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    tables = {
        "ev_operation_mode_shares.csv": operation_mode_shares(rows),
        "ev_v0_location_shares.csv": v0_location_shares(rows),
        "ev_daily_profiles.csv": daily_profiles(rows),
        "ev_availability.csv": availability(rows),
    }
    for name, df in tables.items():
        df.to_csv(args.out_dir / name, index=False)
        print(f"{name}: {len(df)} rows")

    prof = tables["ev_daily_profiles.csv"]
    sums = prof.groupby(["mode", "location", "variant"])["value"].sum()
    print("\ndaily profile sums (workbook rounds to 3 decimals):")
    print(sums.round(4).to_string())


if __name__ == "__main__":
    main()
