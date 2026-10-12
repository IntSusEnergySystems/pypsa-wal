# Optional pypsa2html integration. If the library is not importable the rules
# are not defined and the rest of the workflow is unaffected.
#
# Pages land in html/pypsa/ so html/index.html can stay a pypsa-wal hub that
# also links the TIMES Sankeys (html/times/) without patching the library.
#
# Two reports (pypsa2html D24, 2026-10-12):
#   generate_html_report      one run: its pages + html/pypsa/summary.{csv,json}.
#                             It loads that run's networks only -- before the
#                             split it also loaded every other configured run
#                             with a tree on disk, for the overview page (the
#                             single-bar central and the mixed vintages of the
#                             6 Oct log, I1/I2).
#   generate_html_comparison  the runs side by side, from their summary files
#                             only: results/<prefix>/compare/.

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


def _compared_runs():
    """Runs of the comparison: `pypsa2html: compare:`, else every `run.name`."""
    runs = config.get("pypsa2html", {}).get("compare") or config["run"]["name"]
    return [runs] if isinstance(runs, str) else list(runs)


COMPARE_DIR = "results/" + (config["run"].get("prefix") or "") + "/compare/"


if HAVE_PYPSA2HTML:

    PYPSA2HTML_CONFIG = (
        config.get("pypsa2html", {}).get("config") or "config/pypsa2html.yaml"
    )

    localrules:
        generate_html_report,
        generate_html_comparison,

    rule ptx_report:
        """The Walloon CO2 balance and power-to-X of one run, per horizon.

        scripts/walloon_scripts/ptx_report.py as a rule, so its tidy table is
        written for every run: the pypsa2html key figures read the CO2 export,
        the capture-cap dual and overage and the PtX throughput from it
        (`source: csv` KPIs of config/pypsa2html.yaml).
        """
        params:
            run_dir=lambda w: RESULTS.format(run=_html_scenario_name(w)).rstrip("/"),
            node="BEWAL",
        input:
            networks=expand(
                RESULTS
                + "networks/base_s_{clusters}_{opts}_{sector_opts}_{planning_horizons}.nc",
                **config["scenario"],
                allow_missing=True,
            ),
        output:
            RESULTS + "csvs/ptx_report.csv",
        log:
            RESULTS + "logs/ptx_report.log",
        threads: 1
        resources:
            mem_mb=6000,
        conda:
            "../envs/environment.yaml"
        shell:
            "PYTHONPATH=. python scripts/walloon_scripts/ptx_report.py {params.run_dir} "
            "--node {params.node} --out {output} > {log} 2>&1"

    rule generate_html_report:
        """One run's interactive HTML report and its summary files."""
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
            # Key figures read the Walloon CO2 balance and PtX from it.
            ptx_report=RESULTS + "csvs/ptx_report.csv",
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
            # What generate_html_comparison reads instead of the networks.
            summary=RESULTS + "html/pypsa/summary.json",
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
            # even when config/pypsa2html.yaml lists a scenario of the same
            # name pointing elsewhere (e.g. scen_demande_haute on the 10-year
            # tree while this run builds the 5-year overlay) -- seen
            # 2026-09-09, 82 pages of 10-year content in the 5y folder.
            # `with_scenario` replaces any same-named entry, keeps its label
            # and lands index.html on this run (the 2026-09-22 scen_central_6h
            # 404 front door).
            cfg = cfg.with_scenario(
                scenario,
                results_tree,
                resources_dir=str(results_tree).replace("results/", "resources/", 1),
            )
            report = build_site(cfg, scenarios=[scenario])
            logging.info(report.summary())


    rule generate_html_comparison:
        """The comparison report of the runs, from their summary files.

        Inputs are the runs' `summary.json` -- small, so the comparison is an
        ordinary Snakemake dependency and is rebuilt when any run's report is.
        It never loads a network. The runs are `pypsa2html: compare:` in the
        workflow config, else every `run.name`. To compare whatever is solved
        so far, without Snakemake:

            pypsa2html compare -c config/pypsa2html.yaml results/walloon/scen_*

        The pypsa2html config's `compare:` block sets the reference scenario
        (scen_central); runs of another vintage are flagged on the report's
        Scenarios page.
        """
        params:
            config_file=PYPSA2HTML_CONFIG,
        input:
            summaries=expand(
                "results/" + (config["run"].get("prefix") or "") + "/{run}/html/pypsa/summary.json",
                run=_compared_runs(),
            ),
            config_file=PYPSA2HTML_CONFIG,
        output:
            index=COMPARE_DIR + "index.html",
            table=COMPARE_DIR + "comparison.csv",
        log:
            "logs/pypsa2html_compare.log",
        threads: 1
        resources:
            mem_mb=2000,
        run:
            import logging
            from pathlib import Path

            from pypsa2html import compare_site, load_config

            logging.basicConfig(
                filename=log[0],
                level=logging.INFO,
                format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
            )
            cfg = load_config(params.config_file, overrides={"root": str(Path.cwd())})
            report = compare_site(
                cfg,
                [Path(p).parent for p in input.summaries],
                out_dir=Path(output.index).parent,
            )
            logging.info(report.summary())
