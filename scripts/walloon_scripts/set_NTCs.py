# SPDX-FileCopyrightText: Contributors to PyPSA-Eur <https://github.com/pypsa/pypsa-eur>
# SPDX-FileCopyrightText: Open Energy Transition gGmbH
#
# SPDX-License-Identifier: MIT

"""Turn the NTC tables into *upper bounds* on usable cross-border capacity.

This used to write the NTC straight into ``s_nom`` / ``p_nom`` and pin the
capacity there. Two things went wrong with that.

First, the number the model delivered was not the number in the file. PyPSA
derates AC lines by ``lines.s_max_pu`` (0.7 here) as an N-1 margin, so writing
an NTC of 5 150 MW into ``s_nom`` leaves only 3 605 MW usable — the
"AC borders deliver 41-73 % of their stated NTC" finding of
``docs/logs/2026-08-18_scen_demande_haute_2010_1h.md``. The NTC is a transfer
capability, so it is compared against the *usable* figure and ``s_nom_max`` is
raised by ``1 / s_max_pu`` to compensate.

Second, pinning the capacity meant the grid could not grow. Every corridor came
out non-extendable, eight of ten AC lines sat at 96-99 % loading, and the 2050
solve carried 12.3 bn EUR/a of congestion rent. The NTC is now a ceiling the
optimiser may build up to, not a fixed value.

Region codes (``BEWAL``, ``BEVLG``, ``BEBRU``) are accepted alongside ISO-3
country codes, so the internal Belgian corridors can be bounded in the same
file rather than being left to the 20 GW ``lines.max_extension`` default.

Third, a border is represented by whichever frame carries it. The DC frame
holds TYNDP candidate projects at ``p_nom = 0`` (``DC2`` on DE-FR,
``TYNDP2020_32`` on DE-GB), and the AC lines used to be dropped against those
placeholders as "already represented" -- which deleted DE-FR's real 6.3 GW
corridor and left the border at zero once the NTC stopped being written into
``p_nom``.
"""

import logging

import country_converter as coco
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# a line with no security margin recorded should not silently get an infinite cap
DEFAULT_S_MAX_PU = 0.7

# Walloon clustering names the three Belgian AC buses after the regions. Their
# `country` field may still be BE, or it may have been rewritten to the region
# name (custom_clustering, add_CCL_constraints). A BEL/BE selector must catch
# all three, or Wallonia's FR/LU/DE branches are left at lines.max_extension.
BE_REGION_BUSES = ("BEWAL", "BEVLG", "BEBRU")


def read_ntc_pairs(ntc_fn):
    """Undirected border -> NTC in MW, as the model applies it.

    The file may hold both directions of a border with different values (it
    does: BEL->FRA is 6 100 MW in 2050 while FRA->BEL is 8 500 MW), so the two
    are averaged into one symmetric figure. Exposed so that `review_run.py`
    checks the number the model actually used rather than one direction of it.
    """
    df = pd.read_csv(ntc_fn)
    df["pair"] = [
        tuple(sorted([row.source_country_code, row.target_country_code]))
        for row in df.itertuples()
    ]
    return df.groupby("pair")["NTC_MW"].mean()


def _bus_selector(n, code, iso2_by_code):
    """Buses a border code refers to: a single region bus, or a whole country."""
    if code in n.buses.index:
        return pd.Index([code])
    iso2 = iso2_by_code.get(code)
    if iso2 is None:
        return pd.Index([])
    buses = n.buses.index[n.buses.country == iso2]
    if iso2 == "BE":
        extra = [b for b in BE_REGION_BUSES if b in n.buses.index]
        buses = buses.union(extra)
    return buses


def _share(current, total, cap, count):
    """Split `cap` across parallel branches in proportion to what is there."""
    if total > 0:
        return cap * current / total
    return pd.Series(cap / count, index=current.index)


def apply_ntc_limits(n, ntc_fn):
    """Bound usable cross-border transfer capability by the NTC table.

    For every border listed in `ntc_fn` and present in the network:

    * DC links are capped per direction: ``p_nom_max`` sums to the NTC.
    * AC lines are capped so that ``sum(s_nom_max * s_max_pu)`` equals the NTC,
      i.e. the *usable* capacity matches the file.
    * ``s_nom`` / ``p_nom`` keep their clustered values, scaled down only where
      the existing grid already exceeds the cap.
    * Where a border has both DC links and AC lines, only one frame is kept so
      the corridor is not counted twice: the DC links if they carry any
      capacity (AC lines are then dropped, as before), otherwise the AC lines
      with the zero-capacity DC candidates held at 0.

    Borders with an NTC of 0 are left untouched.

    Parameters
    ----------
    n : pypsa.Network
        Modified in place.
    ntc_fn : str or pathlib.Path
        CSV with `source_country_code`, `target_country_code` (ISO-3, or a
        region bus name) and `NTC_MW`. The two directions of a border are
        averaged, as they were before.
    """
    pair_to_ntc = read_ntc_pairs(ntc_fn)

    codes = pd.unique(np.concatenate([list(p) for p in pair_to_ntc.index]))
    region_codes = [c for c in codes if c in n.buses.index]
    country_codes = [c for c in codes if c not in n.buses.index]

    cc = coco.CountryConverter()
    iso2_by_code = {}
    if country_codes:
        converted = cc.convert(names=list(country_codes), src="ISO3", to="ISO2")
        if isinstance(converted, str):
            converted = [converted]
        iso2_by_code = {
            code: iso2
            for code, iso2 in zip(country_codes, converted)
            if isinstance(iso2, str) and iso2 != "not found"
        }
    if region_codes:
        logger.info(f"NTC file addresses region buses directly: {region_codes}")

    for (code1, code2), ntc in pair_to_ntc.items():
        if ntc == 0:
            continue

        buses1 = _bus_selector(n, code1, iso2_by_code)
        buses2 = _bus_selector(n, code2, iso2_by_code)
        if buses1.empty or buses2.empty:
            continue

        lines_between = n.lines.query(
            "(bus0 in @buses1 and bus1 in @buses2)"
            " or (bus0 in @buses2 and bus1 in @buses1)"
        )
        links_between = n.links.query(
            "carrier == 'DC' and ("
            "(bus0 in @buses1 and bus1 in @buses2)"
            " or (bus0 in @buses2 and bus1 in @buses1))"
        )

        # Prefer whichever frame actually carries the border today. The DC frame
        # also holds TYNDP candidate projects at p_nom = 0 (`DC2` on DE-FR,
        # `TYNDP2020_32` on DE-GB); letting one of those stand for the border
        # would delete a real AC corridor and leave the border at zero.
        dc_carries_border = float(links_between.p_nom.sum()) > 0 or lines_between.empty

        if not links_between.empty and dc_carries_border:
            _cap_dc_links(n, links_between, ntc, code1, code2)
            if not lines_between.empty:
                logger.info(
                    f"Removing AC lines {list(lines_between.index)} on the "
                    f"{code1}-{code2} border: DC links already represent it."
                )
                n.remove("Line", lines_between.index)
        elif not lines_between.empty:
            _cap_ac_lines(n, lines_between, ntc, code1, code2)
            if not links_between.empty:
                # the AC lines carry the cap, so hold the candidate HVDC at zero
                # rather than adding a second, uncapped corridor
                n.links.loc[
                    links_between.index, ["p_nom", "p_nom_min", "p_nom_max"]
                ] = 0.0
                logger.info(
                    f"Holding candidate DC links {list(links_between.index)} at "
                    f"0 MW on the {code1}-{code2} border: the AC lines carry the NTC."
                )
        else:
            logger.warning(f"No interconnections found between {code1} and {code2}")


def _cap_dc_links(n, links_between, ntc, code1, code2):
    """Cap each direction of a DC border at `ntc` MW."""
    for reverse in (False, True):
        direction = links_between.query("reversed == @reverse").index
        if direction.empty:
            continue
        current = n.links.loc[direction, "p_nom"]
        cap = _share(current, current.sum(), ntc, len(direction))
        n.links.loc[direction, "p_nom_max"] = cap
        # only shrink; a border below its NTC may grow up to it
        excess = current > cap
        if excess.any():
            n.links.loc[direction[excess], "p_nom"] = cap[excess]
            n.links.loc[direction[excess], "p_nom_min"] = np.minimum(
                n.links.loc[direction[excess], "p_nom_min"], cap[excess]
            )
    logger.info(
        f"Capped DC border {code1}-{code2} at {ntc:.0f} MW per direction "
        f"(base {links_between.query('reversed == False').p_nom.sum():.0f} MW)."
    )


def _cap_ac_lines(n, lines_between, ntc, code1, code2):
    """Cap an AC border so that the *usable* capacity equals `ntc` MW."""
    idx = lines_between.index
    s_max_pu = n.lines.loc[idx, "s_max_pu"].replace(0, np.nan).fillna(DEFAULT_S_MAX_PU)

    usable = lines_between.s_nom * s_max_pu
    cap_usable = _share(usable, usable.sum(), ntc, len(idx))
    cap_nominal = cap_usable / s_max_pu

    n.lines.loc[idx, "s_nom_max"] = cap_nominal
    excess = lines_between.s_nom > cap_nominal
    if excess.any():
        n.lines.loc[idx[excess], "s_nom"] = cap_nominal[excess]
        n.lines.loc[idx[excess], "s_nom_min"] = np.minimum(
            n.lines.loc[idx[excess], "s_nom_min"], cap_nominal[excess]
        )
    logger.info(
        f"Capped AC border {code1}-{code2} at {ntc:.0f} MW usable "
        f"({cap_nominal.sum():.0f} MW nominal at s_max_pu={s_max_pu.mean():.2f}; "
        f"base {usable.sum():.0f} MW usable)."
    )
