# HTML report layout under results/<run>/html/:
#
#   index.html     pypsa-wal hub (this file's write_html_hub rule)
#   pypsa/         pypsa2html (untouched library; its own index.html)
#   times/         TIMES Sankey pages (times_pypsa)
#
# publish_html rsyncs that whole folder to
# https://pypsa.squoilin.eu/intervec/<scenario>_<YYYYMMDD>/

def html_hub_inputs():
    """Sentinels the hub page links to. Empty when nothing builds html/."""
    files = []
    if HAVE_PYPSA2HTML:
        files.append(RESULTS + "html/pypsa/index.html")
    if TIMES_SANKEY:
        files.append(RESULTS + "html/times/times_sankey_index.html")
    return files


def html_hub_targets():
    """`rule all` targets for the hub page ([] when html/ is empty)."""
    if not html_hub_inputs():
        return []
    return expand(RESULTS + "html/index.html", run=config["run"]["name"])


if html_hub_inputs():

    localrules:
        write_html_hub,

    rule write_html_hub:
        """Tiny landing page that links pypsa2html and TIMES Sankeys."""
        params:
            scenario=_html_scenario_name,
            has_pypsa=HAVE_PYPSA2HTML,
            has_times=bool(TIMES_SANKEY),
        input:
            html_hub_inputs(),
        output:
            index=RESULTS + "html/index.html",
        run:
            from pathlib import Path

            scenario = params.scenario
            items = []
            if params.has_pypsa:
                items.append(
                    '  <li><a href="pypsa/">PyPSA report</a></li>'
                )
            if params.has_times:
                items.append(
                    '  <li><a href="times/times_sankey_index.html">'
                    "TIMES Sankey diagrams</a></li>"
                )
            Path(output.index).write_text(
                "<!DOCTYPE html>\n"
                '<html lang="en">\n'
                "<head>\n"
                '<meta charset="utf-8">\n'
                '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
                f"<title>{scenario}</title>\n"
                "<style>\n"
                "  body { font-family: system-ui, sans-serif; max-width: 40rem;"
                " margin: 3rem auto; padding: 0 1.5rem; line-height: 1.5; }\n"
                "  a { color: #0b57d0; }\n"
                "</style>\n"
                "</head>\n"
                "<body>\n"
                f"<h1>{scenario}</h1>\n"
                "<ul>\n"
                + "\n".join(items)
                + "\n</ul>\n"
                "</body>\n"
                "</html>\n",
                encoding="utf-8",
            )


def _publish_html_cfg():
    return dict(config.get("html_publish") or {})


def _publish_html_enabled():
    return bool(_publish_html_cfg().get("enable", False))


def _publish_html_inputs():
    """Publish the hub; it already depends on pypsa/ and times/."""
    if not html_hub_inputs():
        return []
    return [RESULTS + "html/index.html"]


def html_publish_targets():
    """`rule all` targets for the HTML upload ([] when it is off)."""
    if not _publish_html_enabled() or not _publish_html_inputs():
        return []
    return expand(
        RESULTS + "logs/html_published.url",
        run=config["run"]["name"],
    )


if _publish_html_enabled() and _publish_html_inputs():

    localrules:
        publish_html,

    rule publish_html:
        message:
            "Publishing HTML report for {params.scenario} to "
            "{params.public_url}/{params.scenario}_{params.date}/"
        params:
            scenario=_html_scenario_name,
            ssh_host=lambda w: _publish_html_cfg().get(
                "ssh_host", "negawatt.squoilin.eu"
            ),
            ssh_user=lambda w: _publish_html_cfg().get("ssh_user", "negawatt"),
            identity_file=lambda w: _publish_html_cfg().get(
                "identity_file", "~/.ssh/rsa_nopasswd"
            ),
            remote_dir=lambda w: _publish_html_cfg().get(
                "remote_dir", "/home/negawatt/public_html/intervec"
            ),
            public_url=lambda w: _publish_html_cfg().get(
                "public_url", "https://pypsa.squoilin.eu/intervec"
            ),
            date=lambda w: (
                _publish_html_cfg().get("date")
                or __import__("os").environ.get("HTML_PUBLISH_DATE")
                or __import__("datetime").date.today().strftime("%Y%m%d")
            ),
        input:
            _publish_html_inputs(),
        output:
            url=RESULTS + "logs/html_published.url",
        log:
            RESULTS + "logs/publish_html.log",
        threads: 1
        run:
            import logging
            import subprocess
            from pathlib import Path

            logging.basicConfig(
                filename=log[0],
                level=logging.INFO,
                format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
                force=True,
            )
            logg = logging.getLogger("publish_html")

            html_dir = Path(input[0]).resolve().parent
            key = Path(params.identity_file).expanduser()
            date = params.date
            folder = f"{params.scenario}_{date}"
            remote_folder = f"{params.remote_dir.rstrip('/')}/{folder}"
            url = f"{params.public_url.rstrip('/')}/{folder}/"
            target = f"{params.ssh_user}@{params.ssh_host}"
            ssh_opts = [
                "-i",
                str(key),
                "-o",
                "BatchMode=yes",
                "-o",
                "IdentitiesOnly=yes",
                "-o",
                "ConnectTimeout=8",
            ]

            def skip(reason):
                msg = f"skipped: {reason}"
                logg.warning(msg)
                print(msg)
                Path(output.url).parent.mkdir(parents=True, exist_ok=True)
                Path(output.url).write_text(msg + "\n")

            if not html_dir.is_dir():
                skip(f"html folder missing: {html_dir}")
                return
            if not key.is_file():
                skip(f"SSH key not found: {key}")
                return

            probe = subprocess.run(
                ["ssh", *ssh_opts, target, "test", "-d", params.remote_dir],
                capture_output=True,
                text=True,
            )
            if probe.returncode != 0:
                err = (probe.stderr or probe.stdout or "").strip()
                skip(
                    f"no passwordless SSH as {target} with {key}"
                    + (f" ({err})" if err else "")
                    + ". Run sudo bash /home/sylvain/scripts/add-pypsa-alias.sh "
                    "on the server if the key is not yet installed."
                )
                return

            mkdir = subprocess.run(
                ["ssh", *ssh_opts, target, "mkdir", "-p", remote_folder],
                capture_output=True,
                text=True,
            )
            if mkdir.returncode != 0:
                raise RuntimeError(
                    f"mkdir {remote_folder} on {target} failed: "
                    f"{(mkdir.stderr or mkdir.stdout).strip()}"
                )

            ssh_cmd = "ssh " + " ".join(ssh_opts)
            rsync = subprocess.run(
                [
                    "rsync",
                    "-a",
                    "--delete",
                    "--chmod=D755,F644",
                    "-e",
                    ssh_cmd,
                    f"{html_dir}/",
                    f"{target}:{remote_folder}/",
                ],
                capture_output=True,
                text=True,
            )
            if rsync.stdout:
                logg.info(rsync.stdout)
            if rsync.returncode != 0:
                raise RuntimeError(
                    f"rsync to {target}:{remote_folder}/ failed: "
                    f"{(rsync.stderr or rsync.stdout).strip()}"
                )

            Path(output.url).parent.mkdir(parents=True, exist_ok=True)
            Path(output.url).write_text(url + "\n")
            logg.info("published %s -> %s", html_dir, url)
            print(f"Published HTML to {url}")
