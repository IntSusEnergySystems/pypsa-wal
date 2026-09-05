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
            # A scenario overlay not yet listed in config/pypsa2html.yaml still
            # has to resolve: inject it so build_site can find the networks.
            if scenario not in cfg.scenario_names:
                from pypsa2html.config import ScenarioConfig

                cfg.scenarios.append(
                    ScenarioConfig(
                        name=scenario,
                        label=scenario,
                        results_dir=str(results_tree),
                        resources_dir=str(results_tree).replace(
                            "results/", "resources/", 1
                        ),
                    )
                )
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
            logging.info(build_site(cfg).summary())
