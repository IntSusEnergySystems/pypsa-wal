# SPDX-FileCopyrightText: Contributors to PyPSA-Eur <https://github.com/pypsa/pypsa-eur>
# SPDX-FileCopyrightText: Open Energy Transition gGmbH
#
# SPDX-License-Identifier: MIT

import logging
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

# Carriers treated as nuclear for the availability / must-run bounds.
# Retrofit links keep carrier ``nuclear``; the suffix is only on the name.
NUCLEAR_CARRIER_PREFIX = "nuclear"

# Default must-run margin, in per-unit of nameplate (percentage points).
# p_min_pu = p_max_pu - this. Not a fraction of the capacity factor.
DEFAULT_P_MIN_PU_MARGIN = 0.10


def _nuclear_index(static: pd.DataFrame) -> pd.Index:
    if static.empty or "carrier" not in static.columns:
        return pd.Index([])
    return static.index[static.carrier.str.startswith(NUCLEAR_CARRIER_PREFIX, na=False)]


def _resolve_data_path(spec: str) -> Path:
    path = Path(spec)
    if path.is_file():
        return path
    repo = Path(__file__).resolve().parents[2]
    alt = repo / spec
    if alt.is_file():
        return alt
    raise FileNotFoundError(
        f"nuclear p_max_pu file {spec!r} not found (cwd={Path.cwd()}, repo={repo})"
    )


def load_nuclear_p_max_pu(config: dict | None) -> pd.Series:
    """Country → availability from ``conventional.nuclear.p_max_pu``.

    The CSV is *not* 1.0: BE is 0.883, FR 0.616, GB 0.684, NL 0.901. A scalar
    in config is broadcast as a constant. Missing file → empty series (callers
    fall back to 1.0 per plant).
    """
    spec = ((config or {}).get("conventional") or {}).get("nuclear") or {}
    p_max = spec.get("p_max_pu", 1.0) if isinstance(spec, dict) else 1.0
    if isinstance(p_max, (int, float)):
        return pd.Series(dtype=float)
    try:
        table = pd.read_csv(_resolve_data_path(str(p_max)), index_col=0)
    except FileNotFoundError:
        logger.warning("Nuclear p_max_pu file %s is missing; using 1.0.", p_max)
        return pd.Series(dtype=float)
    series = table.iloc[:, 0].astype(float)
    series.index = series.index.astype(str)
    return series


def inflexible_nuclear_options(config: dict | None) -> dict:
    """``conventional.inflexible_nuclear`` — Walloon overlay, absent upstream."""
    opts = ((config or {}).get("conventional") or {}).get("inflexible_nuclear") or {}
    if not isinstance(opts, dict):
        return {}
    return opts


def _component_countries(n, names: pd.Index, component: str) -> pd.Series:
    """ISO country of each nuclear component via its electricity bus."""
    if component == "Link":
        buses = n.links.loc[names, "bus1"]
    else:
        buses = n.generators.loc[names, "bus"]
    if "country" in n.buses.columns:
        return buses.map(n.buses["country"])
    return pd.Series(index=names, dtype=object)


def _drop_time_varying(n, component: str, names: pd.Index) -> None:
    """Static p_min_pu / p_max_pu only take effect if no time series exists."""
    store = n.links_t if component == "Link" else n.generators_t
    for attr in ("p_max_pu", "p_min_pu"):
        df = getattr(store, attr, None)
        if df is None or df.empty:
            continue
        drop = df.columns.intersection(names)
        if len(drop):
            df.drop(columns=drop, inplace=True)


def apply_nuclear_inflexibility(n, config: dict | None) -> dict:
    """Must-run nuclear: ``p_min_pu = p_max_pu − margin`` on legacy *and* new plant.

    Sector-coupled nuclear is a Link (uranium → electricity). The country
    availability CSV is applied to Generators in ``add_electricity`` and those
    generators are then stripped, so without this hook the solved links have
    ``p_max_pu = 1`` and ``p_min_pu = 0`` (fully flexible, 100 % available).

    ``conventional.inflexible_nuclear.enable: true`` copies the CSV onto every
    nuclear link (and any leftover generator) as ``p_max_pu`` and sets
    ``p_min_pu = max(0, p_max_pu − p_min_pu_margin)``. The margin is in
    percentage points so a plant whose CF is already below 90 % stays feasible.

    ``enable: false`` restores the unconstrained formulation on links
    (``p_max_pu = 1``, ``p_min_pu = 0``). The key absent is a no-op, so
    unmodified PyPSA-Eur is unchanged.

    Returns a summary dict (applied / restored / skipped) for tests.
    """
    opts = inflexible_nuclear_options(config)
    if "enable" not in opts:
        return {"action": "skipped", "links": 0, "generators": 0}

    enabled = bool(opts.get("enable"))
    margin = float(opts.get("p_min_pu_margin", DEFAULT_P_MIN_PU_MARGIN))
    if margin < 0:
        raise ValueError(
            f"conventional.inflexible_nuclear.p_min_pu_margin must be >= 0, got {margin}"
        )

    availability = load_nuclear_p_max_pu(config)
    summary = {
        "action": "applied" if enabled else "restored",
        "margin": margin,
        "links": 0,
        "generators": 0,
        "p_max_pu": {},
        "p_min_pu": {},
    }

    for component in ("Link", "Generator"):
        static = n.links if component == "Link" else n.generators
        names = _nuclear_index(static)
        if names.empty:
            continue
        _drop_time_varying(n, component, names)
        if enabled:
            countries = _component_countries(n, names, component)
            p_max = countries.map(availability).astype(float)
            missing = p_max.isna()
            if missing.any():
                # LU is not in the CSV; keep a 1.0 cap so p_min_pu = 1 − margin.
                logger.info(
                    "Nuclear %s without a CSV availability (%s); using p_max_pu=1.0.",
                    component,
                    ", ".join(sorted(countries[missing].fillna("?").astype(str).unique())),
                )
                p_max = p_max.fillna(1.0)
            p_min = (p_max - margin).clip(lower=0.0, upper=p_max)
            static.loc[names, "p_max_pu"] = p_max
            static.loc[names, "p_min_pu"] = p_min
            summary["p_max_pu"].update(p_max.to_dict())
            summary["p_min_pu"].update(p_min.to_dict())
        else:
            static.loc[names, "p_min_pu"] = 0.0
            if component == "Link":
                # Generators already carry the CSV from add_electricity; only
                # the sector links need restoring to the previous default.
                static.loc[names, "p_max_pu"] = 1.0
        key = "links" if component == "Link" else "generators"
        summary[key] = int(len(names))

    n_comp = summary["links"] + summary["generators"]
    if n_comp:
        logger.info(
            "Nuclear inflexibility %s on %s link(s) and %s generator(s) "
            "(margin=%.2f p.u.).",
            summary["action"],
            summary["links"],
            summary["generators"],
            margin,
        )
    return summary


def add_BEWAL_nuclear(
    n,
    planning_horizon,
    extendable_nuclear_nodes: dict = {2040: ["BEWAL"], 2050: ["BEWAL"]},
):
    """
    Update the BEWAL nuclear link in the network to be extendable if 'nuclear' is
    listed for the given planning horizon and also update nuclear link costs from
    the processed cost table.

    Parameters
    ----------
    n : pypsa.Network
        The PyPSA network object whose links are being modified.
    planning_horizon : int
        The year to check and update.
    extendable_nuclear_nodes : Dict
        Dict, with planning horizons as keys, passing a list of name of the buses where the nuclear link shall be set to extendable
        (default ``{2040: ["BEWAL"], 2050: ["BEWAL"]}``).
    """

    if planning_horizon in extendable_nuclear_nodes.keys():
        extendable_nuclear_links = [f"{bus} nuclear-2025" for bus in extendable_nuclear_nodes[planning_horizon]]
        link_missing = [link for link in extendable_nuclear_links if link not in n.links.index]
        extendable_nuclear_links = list(set(extendable_nuclear_links) - set(link_missing))

        if link_missing != []:
            logger.warning(
                "Requested nuclear link '%s' not found; unable to update costs.", link_missing
            )

        if extendable_nuclear_links != []:
            n.links.loc[extendable_nuclear_links, "p_nom_extendable"] = True


def retrofit_retired_nuclear(
        n,
        decomissioned_nuclear,
        planning_horizon,
        costs,
        extendable_nuclear_nodes = ["BEWAL", "BEVLG"],
        retrofit_nuclear_once: bool = False,
        MILP = False):
    """
    Provide the option to a given set of nuclear links that are being decomissioned to be retrofitted
    and remain in the system.

    Parameters
    ----------
    n : pypsa.Network
        The PyPSA network object where retrofit nuclear links are being added.
    decomissioned_nuclear : pypsa.Network
        A PyPSA network object that contains only links of generators that are
        being decommissioned in the considered planning horizon.
    planning_horizon : int
        Will become the new build_year of the retrofitted plant.
    extendable_nuclear_nodes : list
        list ofs name of the buses where the nuclear link shall be made
        available for retrofitting (default ``["BEWAL"]``).
    MILP : bool
        True will only allow retrofitting the entire block or nothing at all
        Turning the problem essentially into a MILP.
    """
    if planning_horizon < 2040:
        logger.info(
            "Skipping nuclear retrofit: planning horizon %s is before the retrofit window.",
            planning_horizon,
        )
        return

    decomissioned_nuclear = decomissioned_nuclear.query("bus1 in @extendable_nuclear_nodes")
    if retrofit_nuclear_once:
        decomissioned_nuclear = decomissioned_nuclear[
            ~decomissioned_nuclear.index.str.contains("retrofit")
        ]
    retrofit_nuclear = decomissioned_nuclear.copy()
    retrofit_nuclear.index = retrofit_nuclear.index.astype(str) + " retrofit"
    retrofit_nuclear["p_nom_max"] = (
        retrofit_nuclear[["p_nom", "p_nom_opt"]]
        .apply(pd.to_numeric, errors="coerce")
        .max(axis=1)
        .fillna(0.0)
    )
    if MILP:
        retrofit_nuclear["p_nom_mod"] = retrofit_nuclear["p_nom_max"]
    retrofit_nuclear[["p_nom_opt", "p_nom", "p_nom_min"]] = 0.1
    retrofit_nuclear["p_nom_extendable"] = True
    retrofit_nuclear["build_year"] = planning_horizon

    # insert retrofit lifetime + capital cost here (take from costs_processed.csv, ideally represented as a separate technology "nuclear retrofit"?
    # in that case, add a new input argument costs. Otherwise, hardcode below
    lifetime_nuclear_retro = costs.loc["nuclear retrofit"].loc["lifetime"]
    capital_cost_nuclear_retro = costs.loc["nuclear retrofit"].loc["capital_cost"]
    retrofit_nuclear["lifetime"] = lifetime_nuclear_retro
    retrofit_nuclear["capital_cost"] = (capital_cost_nuclear_retro * retrofit_nuclear["efficiency"])

    logger.info(
        f"Adding the option to retrofit the following nuclear plants: {decomissioned_nuclear.index} "
        f"to increase their lifetime by {lifetime_nuclear_retro} years. "
        f"Assuming an annualized cost of capital of {capital_cost_nuclear_retro}."
    )

    for name, row in retrofit_nuclear.iterrows():
        attrs = row.dropna().to_dict()
        n.add("Link", name=name, **attrs)
