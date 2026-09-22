# Optional pypsa2html integration. If the library is not importable the rules
# are not defined and the rest of the workflow is unaffected.
#
# Pages land in html/pypsa/ so html/index.html can stay a pypsa-wal hub that
# also links the TIMES Sankeys (html/times/) without patching the library.

try:
    import pypsa2html as _pypsa2html  # noqa: F401

    HAVE_PYPSA2HTML = True
except ImportError:
    HAVE_PYPSA2HTML = False
    print(
        "pypsa2html not installed -- HTML report rule disabled. "
        "Install with: pip install -e /path/to/pypsa2html --no-deps"
    )


def _html_scenario_name(w):
    """Scenario id for this job: `{run}` wildcard, else the (single) run.name."""
    try:
        return w.run
    except (AttributeError, KeyError):
        pass
    name = config["run"]["name"]
    if isinstance(name, list):
        if len(name) != 1:
            raise ValueError(
                "pypsa2html needs the {run} wildcard or a single run.name, "
                f"got {name!r}"
            )
        return name[0]
    return name


def pypsa2html_targets():
    """`rule all` targets for the pypsa2html report ([] when it is off)."""
    if not HAVE_PYPSA2HTML:
        return []
    return expand(RESULTS + "html/pypsa/index.html", run=config["run"]["name"])


if HAVE_PYPSA2HTML:

    PYPSA2HTML_CONFIG = (
        config.get("pypsa2html", {}).get("config") or "config/pypsa2html.yaml"
    )

    localrules:
        generate_html_report,
        generate_html_report_all_scenarios,

    rule generate_html_report:
        """Build the interactive HTML report from the solved networks."""
        params:
            config_file=PYPSA2HTML_CONFIG,
            scenario=_html_scenario_name,
        input:
            networks=expand(
                RESULTS
                + "networks/base_s_{clusters}_{opts}_{sector_opts}_{planning_horizons}.nc",
                **config["scenario"],
                allow_missing=True,
            ),
            # pypsa2html reads csvs/ as well as the networks, and caches each
            # file on first use. Without these inputs Snakemake is free to run
            # the report alongside `make_global_summary`, and the report is
            # then built from the PREVIOUS run's summary tables while its file
            # timestamps look fresh. Seen 2026-09-05 on the 6h test: the
            # capacity pages carried the 3 Sept run's PV fleet (BEWAL 4 088 MW
            # of ground PV, zero rooftop) although csvs/nodal_capacities.csv on
            # disk was correct. Declare what is actually read.
            nodal_capacities=RESULTS + "csvs/nodal_capacities.csv",
            nodal_costs=RESULTS + "csvs/nodal_costs.csv",
            nodal_energy_balance=RESULTS + "csvs/nodal_energy_balance.csv",
            nodal_capacity_factors=RESULTS + "csvs/nodal_capacity_factors.csv",
            costs=RESULTS + "csvs/costs.csv",
            capacities=RESULTS + "csvs/capacities.csv",
            energy_balance=RESULTS + "csvs/energy_balance.csv",
            metrics=RESULTS + "csvs/metrics.csv",
            # Reporting-only: lets the EV charts show Elia's three charging
            # modes instead of two. pypsa2html reads it from resources_dir and
            # degrades to the old natural/smart split when it is absent, so an
            # older results tree still reports.
            ev_mode_split=expand(
                resources(
                    "ev_charging_mode_split_s_{clusters}_{planning_horizons}.csv"
                ),
                clusters=config["scenario"]["clusters"],
                planning_horizons=config["scenario"]["planning_horizons"],
                allow_missing=True,
            ),
            config_file=PYPSA2HTML_CONFIG,
        output:
            index=RESULTS + "html/pypsa/index.html",
        log:
            RESULTS + "logs/pypsa2html.log",
        benchmark:
            RESULTS + "benchmarks/pypsa2html"
        threads: 1
        resources:
            mem_mb=8000,
        conda:
            "../envs/environment.yaml"
        run:
            import logging
            from pathlib import Path

            from pypsa2html import build_site, load_config

            logging.basicConfig(
                filename=log[0],
                level=logging.INFO,
                format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
            )

            pypsa_dir = Path(output.index).parent  # .../html/pypsa
            # Scenario results dir is the parent of html/, not of pypsa/.
            results_tree = pypsa_dir.parent.parent
            scenario = params.scenario
            cfg = load_config(
                params.config_file,
                overrides={
                    "root": str(Path.cwd()),
                    "output": {"dir": str(pypsa_dir)},
                },
            )
            # This rule always reports the tree it was given (results_tree),
            # even when config/pypsa2html.yaml already lists a scenario of
            # the same name pointing elsewhere (e.g. scen_demande_haute on
            # the 10-year tree while this run builds the 5-year overlay).
            # A conditional inject-only-if-missing silently reports the wrong
            # tree — seen 2026-09-09, 82 pages of 10-year content in the 5y
            # folder. So replace any same-named entry, keeping its label.
            from pypsa2html.config import ScenarioConfig

            existing = next(
                (s for s in cfg.scenarios if s.name == scenario), None
            )
            cfg.scenarios = [s for s in cfg.scenarios if s.name != scenario]
            cfg.scenarios.append(
                ScenarioConfig(
                    name=scenario,
                    label=existing.label if existing is not None else scenario,
                    results_dir=str(results_tree),
                    resources_dir=str(results_tree).replace(
                        "results/", "resources/", 1
                    ),
                )
            )
            # `landing.scenario` names the page html/pypsa/index.html
            # redirects to. This rule builds ONE scenario, so the landing page
            # must be that one; the value configured in config/pypsa2html.yaml
            # is for the cross-scenario site. Left alone, a run whose name is
            # not the configured landing scenario produced a report whose
            # entry point 404s — index.html redirected to
            # BEWAL_overview_scen_central.html while the pages on disk were
            # ..._scen_central_6h.html (seen 2026-09-22 on scen_central_6h:
            # all 82 pages present, only the front door wrong). Set here and
            # not through `load_config` overrides, because load_config
            # validates landing.scenario against the configured scenario list
            # and this run's scenario is appended just above.
            cfg.landing.scenario = scenario
            report = build_site(cfg, scenarios=[scenario])
            logging.info(report.summary())


    rule generate_html_report_all_scenarios:
        """Cross-scenario report, including the comparison overview page.

        Not wired into `all`: sibling scenario trees are not a Snakemake
        input of this rule.
        """
        params:
            config_file=PYPSA2HTML_CONFIG,
        output:
            index="results/walloon/index.html",
        log:
            "logs/pypsa2html_all.log",
        threads: 1
        run:
            import logging
            from pathlib import Path

            from pypsa2html import build_site, load_config

            logging.basicConfig(filename=log[0], level=logging.INFO)
            cfg = load_config(
                params.config_file,
                overrides={"root": str(Path.cwd())},
            )
            # ADDITIVE: report every scenario that is SOLVED, skip the rest.
            #
            # config/pypsa2html.yaml lists every scenario the project knows
            # about, including ones not run yet and retired ones whose trees
            # were deleted. Handing that whole list to build_site aborts on the
            # first missing tree, which would mean the combined report can only
            # ever be built once, at the very end of a batch. Filtering here
            # lets the same rule be re-run after each scenario lands, each time
            # producing a report over everything finished so far — which is how
            # a 14-scenario batch is actually watched.
            #
            # "Solved" = at least one network in <results_dir>/networks/. A
            # scenario whose solve is still running has no network yet, so a
            # half-written tree cannot enter the report.
            available, skipped = [], []
            for s in cfg.scenarios:
                nets = Path(cfg.root) / s.results_dir / "networks"
                if nets.is_dir() and any(nets.glob("*.nc")):
                    available.append(s)
                else:
                    skipped.append(s.name)
            if not available:
                raise RuntimeError(
                    "no solved scenario found for the combined report; "
                    f"looked for */networks/*.nc under: "
                    f"{', '.join(s.results_dir for s in cfg.scenarios)}"
                )
            cfg.scenarios = available
            if skipped:
                logging.info(
                    "skipping %d scenario(s) with no solved network: %s",
                    len(skipped), ", ".join(sorted(skipped)),
                )
            logging.info(
                "building combined report over %d scenario(s): %s",
                len(available), ", ".join(s.name for s in available),
            )
            logging.info(build_site(cfg).summary())
