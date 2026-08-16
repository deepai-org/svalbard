# SVALBARD development plan

## Machine assumptions

This plan is tailored to the current host:

- Ubuntu 24.04 LTS on `aarch64` (AWS), with 32 CPUs and 123 GiB RAM.
- Docker 29 with the `overlay2` storage driver and systemd cgroups is installed and running. The `ubuntu` user can invoke it without `sudo`.
- The Docker daemon is rootful. Membership in the `docker` group is effectively root access, so containers must never receive the Docker socket, `--privileged`, or unnecessary host mounts.
- The root filesystem currently has roughly 233 GiB free. Builds, PDKs, extracted layouts, and waveforms need explicit storage limits and cleanup targets.
- Git, Python 3.12, Make, `systemd-run`, and `earlyoom` are present. Nix and Git LFS are not current host prerequisites.
- The repository is public and hosted on GitHub, but GitHub Actions is not used. All checks run locally through versioned Make targets.

These are bootstrap assumptions, not permanent hard-coded requirements. `./bootstrap.sh doctor` should report drift rather than silently changing the host.

## The repo: SVALBARD

The repository uses descriptive, stable project identifiers so that directory names, manifests, targets, dashboards, and technical discussions state what each design actually does:

| Project | Repository identifier |
|---|---|
| Process/device/passive characterization and model-correlation die | `process_characterization` |
| RTL-SDR-class 50 MHz–1.7 GHz tuner | `rtl_sdr_tuner` |
| CMOS image sensor | `cmos_image_sensor` |
| Gain-cell eDRAM | `gain_cell_edram` |
| Floating-gate analog NVM + compute | `floating_gate_analog_nvm` |
| Gigabit Ethernet MAC and integrated PHY | `ethernet_mac_phy` |
| 2.4 GHz WiFi + single-band NB-IoT radio SoC | `wifi_nbiot_radio` |
| PCIe Gen1 x1 endpoint | `pcie_gen1_endpoint` |
| Standalone 1–2k-LUT FPGA with open bitstream and nextpnr support | `standalone_fpga` |
| USB 2.0 device PHY + controller | `usb2_device` |
| LiDAR / quantum-optics SPAD chip | `spad_lidar` |
| DDR1 PHY + controller | `ddr1_phy_controller` |
| Neuromorphic spiking processor | `spiking_neural_processor` |

## Success levels and initial scope

Do not use “done” to conflate four different outcomes:

1. **O1 Flow-qualified:** a clean clone reproduces the required containerized smoke and verification targets.
2. **O2 Evidence-qualified:** the project passes its applicable open-flow gates and publishes reproducible pre-silicon claims with limitations.
3. **O3 Shuttle-accepted:** the fabrication provider accepts every committed design package and the exact shuttle manifest.
4. **O4 Measured:** packaged or probed silicon is brought up, raw measurements are preserved, claims are compared with silicon, and models are recalibrated.

The initial committed portfolio milestone is a flow-qualified public repository and one GF180 v1 shuttle containing ten design submissions. Every named project in this plan is active for v1: `process_characterization`, `rtl_sdr_tuner`, `cmos_image_sensor`, `gain_cell_edram`, `floating_gate_analog_nvm`, `ethernet_mac_phy`, `wifi_nbiot_radio`, `pcie_gen1_endpoint`, `standalone_fpga`, `usb2_device`, `spad_lidar`, `ddr1_phy_controller`, and `spiking_neural_processor`. Where ten provider slots cannot give all thirteen projects a separate die, compatible projects may share a die as isolated islands, share selected infrastructure, or form a coupled SoC when that materially saves area or makes a more useful chip. All v1 designs develop and close in parallel, and no project depends on measurements from another die in the same shuttle.

Same-shuttle characterization can guide safe bring-up, correlate local monitors, distinguish design from model failures, and improve a future respin, but it cannot de-risk circuits already fabricated in v1. Therefore every product die must be useful and diagnosable. Coupled SoCs may share control, memory, interconnect, converters, references, clocks, pads, or power infrastructure, but existential new blocks retain an appropriate raw interface, bypass, monitor, isolation control, or external injection path. The communication projects reuse qualified physical macros where requirements genuinely overlap; reuse is never a goal when it creates an unobservable common-mode existential failure. Their v1 objective is working fully integrated silicon at a deliberately narrow standards target, not maximum performance or feature breadth.

There is no project backlog inside the named v1 portfolio. The gates sequence and constrain work within each project; they do not defer a project to a later shuttle. Every committed v1 die is submitted. A missed internal gate changes its recorded evidence state and may force a safer reduced-feature configuration before freeze, but does not silently remove the project from the shuttle.

## Gate G0: submission and process/provider eligibility

This gate happens before Phase 0 locks the process baseline and before architecture, TCAD investment, or custom-device layout. Select the intended shuttle/fabrication path and record:

- The accepted PDK and Open PDKs/Volare revisions, GF180 process option/metal stack, allowed devices and layers, required cells, die/reticle limits, seal-ring/edge constraints, labels, submission format, and waiver policy.
- Packaging, probing, bond-pad, assembly, and test constraints that affect the padframe, die size, circuit-under-pad rules, or calibration structures.
- Written provider disposition for proposed SPAD, floating-gate, photodiode, gain-cell, nonstandard ESD, or circuit-under-pad structures. `accepted for submission`, `experimental at our risk`, and `not accepted` are distinct recorded outcomes.
- Foundry or provider availability and validity range for RF/noise, passive, statistical-mismatch, high-frequency interconnect, pad, and ESD models. Record the highest characterized frequency, device geometries, bias range, temperature range, extraction method, and any uses the model owner does not support. A model that is merely accepted by a simulator is not a qualified RF model.
- Availability of silicon-proven PLL, SerDes, data-converter, SRAM, I/O, ESD, or RF IP under terms compatible with the project. Prefer qualified foundry, licensed, or silicon-proven open-source IP over a new custom implementation when it materially improves first-silicon probability and can be independently verified; open GF180MCU blocks with working fabricated silicon count as proven, and the custom rewrite is the experiment.
- The exact legal standards sources and compliance-test access for Ethernet, PCIe Gen1, 802.11b, and the selected NB-IoT release, band, and UE category.
- Which open decks the provider accepts, what additional checks it performs, and what the project may publicly call signoff.

Initial Gate G0 completion is a reviewed decision record under `docs/roadmap/`. Once the Phase 0 repository skeleton exists, `make process-eligibility` validates that record against the canonical process lock and remains a permanent regression target. If no provider can yet be selected, generic environment work and ordinary standard-device experiments may continue, but no process baseline is frozen and exotic-device work remains explicitly exploratory.

## Phase 0 (portfolio milestone M0): make the machine hard to break (week 1–2)

The rule that protects the machine: **no EDA tool is installed directly on the host OS.** EDA tools run in Docker containers; the host-facing orchestration uses only Docker, Git, Python, and Make.

- **Base environment: IIC-OSIC-TOOLS** (JKU's all-in-one EDA container — xschem, ngspice, Magic, KLayout, Netgen, OpenROAD, CACE, and the PDKs preinstalled). Use its `aarch64` image and pin it by digest in `env/images.lock`; never use `:latest` in a committed target.
- **LibreLane via Docker** for the digital flow. Use LibreLane's supported `--dockerized` mode on arm64, with its Python launcher isolated in a repo-local virtual environment. Pin both the launcher version and resolved image digest; do not add Nix as a host dependency.
- **Custom Docker images** (Dockerfiles committed under `env/images/`): Xyce (+OpenMPI), Charon (the Trilinos stack — the worst build on the list; optional until an exotic-device project needs it), openEMS, DEVSIM, GNU Radio, and FastHenry/FasterCap. Every image must build for `linux/arm64`; emulation is for experiments, not evidence runs.
- **Explicit verification toolset:** inventory and pin, whether supplied by IIC-OSIC-TOOLS, LibreLane, or a small supplemental image: Verible and/or Slang for RTL parsing/lint; Yosys for synthesis and structural checks; SymbiYosys with Boolector and Z3 for formal; Verilator, Icarus Verilog, cocotb, and pytest for RTL and gate-netlist regression; OpenSTA/OpenROAD for STA; OpenROAD DFT for scan insertion; Magic and KLayout for independent geometry checks; Netgen and KLayout extraction for LVS/PEX; KLayout's connectivity, density, fill, and antenna decks; and PDNSim for digital static IR-drop/current-density analysis. Record the exact executable and version serving each role in `env/tools.lock`; a tool merely being present in a large image does not make it part of the qualified flow.
- **Repository and supply-chain toolset:** pin ShellCheck for host wrappers, Hadolint for Dockerfiles, gitleaks for local secret scanning, Syft for SPDX/CycloneDX SBOM generation, REUSE for source-license compliance, git-sizer for repository-growth checks, and Minisign for release/signoff manifests. Lock Python dependencies with hashes in a repo-local virtual environment. Run these tools from pinned containers where practical so a public reproducer does not need them installed globally.
- **Model compiler split:** OpenVAF/OSDI models run through ngspice. Any model used by Xyce must be compiled separately through Xyce/ADMS as a plugin and correlated against the ngspice implementation over a checked operating envelope. Do not treat an OpenVAF binary as directly loadable by Xyce.
- **Trust boundary:** the current rootful Docker daemon is for reviewed, trusted revisions only. Never execute an arbitrary public pull request, contributed Makefile, or contributed Dockerfile on this host. During Phase 0, qualify rootless Docker with cgroup v2 limits on a separate Docker data directory; if required EDA/GUI flows cannot use it, retain rootful Docker only for trusted work and use a disposable worker VM for untrusted contributions. Rootless migration must not duplicate the existing image store onto the already-constrained root filesystem.
- **Container isolation:** run with a non-root container UID matching the host user, drop capabilities, set `no-new-privileges`, use a read-only root filesystem where the tool permits it, and mount only the repo plus a dedicated scratch directory. Never mount `/var/run/docker.sock`, `/`, or the user's home directory wholesale. LibreLane's launcher mounts more by default, so wrap it and explicitly document the mounts it cannot avoid.
- **Resource guardrails:** make the initial normal-job defaults `--cpus=16 --memory=48g --memory-swap=56g --pids-limit=4096`; allow explicitly marked heavy jobs up to 28 CPUs and 96 GiB, leaving headroom for the host. Docker's systemd-backed cgroups are the enforcement mechanism; `earlyoom` is already active as the last line of defense.
- **Bounded orchestration:** use `flock` to allow only one heavy job by default and GNU `timeout` to bound every non-interactive flow. Apply limits to image construction too: use a dedicated BuildKit/buildx builder with bounded parallelism, CPU/memory limits, log sizing, and a documented garbage-collection policy. `docker run` limits do not by themselves constrain every image-build worker.
- **Scratch and storage:** put disposable output on one configurable path, preferably a dedicated EBS volume mounted outside the repository; allow repo-local `scratch/` only for smoke tests. Add `make scratch-report`, project-scoped cleanup targets, and preflights for both the scratch filesystem and `/var/lib/docker` that refuse heavy jobs when less than 100 GiB is free. Snapshot valuable uncommitted layout work. Do not automate global `docker system prune`; shared Docker data may belong to other work.
- **Public-repo hygiene:** no credentials, foundry-restricted material, machine-local paths, or licensed PDK/tool files may enter the worktree or Git history. Keep an allowlist-based `.gitignore`, provide `.env.example` files with placeholders only, and make `make check-public` scan staged/tracked files for accidental secrets and oversized artifacts before pushing to GitHub.
- Big generated artifacts (waveforms, GDS, S-parameters, full evidence bundles) stay out of ordinary Git. Track compact summaries, plots, datasheets, checksums, and reproduction commands in the public repository. Publish intentionally selected immutable evidence bundles as GitHub Release assets; adopt content-addressed object storage or DVC later if Releases no longer fit the artifact model. Git LFS remains reserved for human-authored binary source, not reproducible generated output.

**Exit criterion:** a fresh clone + `./bootstrap.sh doctor` + `./bootstrap.sh pull` + `make smoke` runs a known-good inverter through the *entire Chain 1 loop* — xschem netlist → ngspice → Magic layout → DRC → extraction → Netgen LVS → post-layout re-sim → result compared against a golden JSON — inside Docker containers, on this arm64 machine, from scratch. The smoke test is the permanent local canary; if a tool upgrade breaks anything, it catches the problem before it eats a workday.

## Repo layout

```
svalbard/
  registry/           # canonical IDs and indexes for programs, products, blocks, and releases
  env/                # Dockerfiles, tool/image locks, wrappers
  processes/
    gf180/            # PDK/process/library locks and flow overlays; no installed PDK files
  schemas/            # component, variant, spec, claim, run, waiver, shuttle, and power schemas
  ip/
    blocks/            # reusable designs, organized by owning block then by view
      analog/ digital/ mixed_signal/ rf/ io/
    macros/
      gf180/           # immutable process-specific hardened block releases
    models/           # TCAD decks, compact models, and calibration data
    twins/            # svalbard_twins, the shared behavioral-twin Python package
    em/               # FastHenry/openEMS harnesses and channel models
  projects/
    process_characterization/
    rtl_sdr_tuner/ cmos_image_sensor/ gain_cell_edram/
    floating_gate_analog_nvm/ ethernet_mac_phy/ wifi_nbiot_radio/
    pcie_gen1_endpoint/ standalone_fpga/ usb2_device/
    spad_lidar/ ddr1_phy_controller/ spiking_neural_processor/
  programs/
    silicon_v1/       # schedule, staffing, cross-project risks, and slot decisions
  shuttles/
    sh1_gf180_v1/     # shuttle manifest plus one immutable package per design submission
  flows/              # shared make rules: sim, mc, drc, lvs, pex, cace, evidence
  testlib/            # shared RTL, analog, integration, and signoff harnesses
  evidence/           # dashboards, release indexes, and tracked run/artifact manifests
  third_party/        # source/license manifests and patches, not copied dependency trees
  docs/
    adr/              # architecture decision records
    policies/         # stable repository, naming, evidence, and release policies
    roadmap/          # portfolio status and project sequencing
```

Every reusable block and project has a validated `component.yaml` recording its stable ID, kind, owner, lifecycle state, process compatibility, license, dependencies, public interfaces, and verification targets. Run-specific evidence is linked from `claims.yaml` and immutable run manifests, not written back as a "latest result" field that would make every run dirty a source manifest. Do not create a full empty directory skeleton for every component. A project has only the common minimum—`README.md`, `component.yaml`, `risks.yaml`, `spec/`, `verification/`, and `claims.yaml`—and adds `rtl/`, `schematic/`, `layout/`, `model/`, `firmware/`, `hardware/`, or `measure/` only when it owns source of that kind. Reusable blocks use the same manifest contract and only the view directories they implement. Organize by owning block first and representation second; do not place one block's RTL, schematic, and model in distant global trees. `sim/` holds exploratory simulation decks, `cace/` holds CACE datasheet configurations, `verification/` holds pass/fail regression suites, `hardware/` holds evaluation-board and fixture design sources, and `measure/` holds bring-up scripts, instrument automation, and measured-data schemas. A testbench has one owning directory; other components reference its stable test ID instead of copying it. `risks.yaml` is canonical; README and program risk summaries link to or generate from it rather than duplicating live status prose.

Use one canonical GF180MCU lock for analog and digital work: PDK source revision, Open PDKs/Volare revision, process option and metal stack, voltage/device families, standard-cell library, and I/O library. Container-internal PDK copies and LibreLane's downloaded PDK must be checked against that lock before a flow starts; a mismatch is a hard failure.

The shuttle is a first-class entity under `shuttles/sh1_gf180_v1/`. Its `shuttle.yaml` records provider/run data, the ten-slot budget, deadlines, and links to one immutable submission manifest per die. Each submission owns its exact layout package, checksums, waivers, package/bond plan, and bring-up plan. Projects own reusable design source; the shuttle directory owns what was actually sent. Slot numbers are allocation metadata and never part of a project's or die's stable identity, so provider reordering does not rename source or evidence.

### Naming conventions

Use these canonical nouns consistently:

| Noun | Meaning | Example |
|---|---|---|
| **portfolio** | Everything governed by this repository | SVALBARD |
| **program** | A funded/scheduled body of work spanning products or submissions | `silicon_v1` |
| **project** | One independently specified product or characterization vehicle | `pcie_gen1_endpoint` |
| **shuttle** | One provider manufacturing opportunity carrying several designs | `sh1_gf180_v1` |
| **submission** | One immutable design package delivered into a shuttle slot | `pcie_gen1_endpoint-main-A0` |
| **die** | One fabricated top-level layout and padframe | `pcie_gen1_endpoint-main-A0` |
| **block** | A reusable logical or circuit design with a declared interface | `serdes_lane` |
| **macro** | A block released as process-specific hardened layout | `serdes_lane.gf180` |
| **view** | One representation of a block | RTL, schematic, layout, model, firmware |
| **instance** | One use of a block or macro inside a design | `u_pcie_lane0` |

`IP`, `core`, `module`, `tile`, and `tapeout` may appear in explanatory prose, but they are not registry kinds. Hardened physical blocks live under `ip/macros/`; a directory name does not define lifecycle or reuse semantics. A project is not a die, a submission is not a shuttle, and a program is neither. This distinction allows one project to produce multiple focused dies or revisions without cloning its source tree.

- **Stable IDs are namespaced and never encode mutable location or maturity:** `project.<name>`, `block.<domain>.<name>`, `macro.<process>.<name>`, `die.<project>.<role>`, `submission.<die>.<revision>`, `shuttle.<name>`, `test.<owner>.<name>`, `claim.<project>.<name>`, and `run.<ulid>`. Human-facing snake-case directory names remain short; manifests carry the canonical ID.
- **Variants describe one controlled axis:** append manifest fields such as `process: gf180`, `corner: ss_125c`, `mode: wifi_dsss`, and `revision: A0`; do not concatenate an ever-growing set of attributes into filenames. Use explicit variant directories only for human-authored implementations, such as `variants/reference_assisted/`.
- **Hardware identifiers follow local conventions:** RTL modules and packages use `lower_snake_case`; module instances use `u_<role>`; active-low signals end `_n`; clocks begin `clk_`; resets begin `rst_`; power domains, clock domains, and reset domains have registered IDs. Analog nets use role-based names with units kept in specs, not names. These conventions are linted at boundaries, not imposed on vendored sources.
- **Interfaces are versioned separately from implementations.** An interface ID and compatibility version live in `component.yaml`; consumers depend on that contract and an immutable release digest, not a relative path or branch head.
- **No overloaded release word:** `release` means an immutable source or macro bundle, `candidate` means inputs under review, and `waiver` means an accepted exception. `signoff` is reserved for a named, scoped check set (`open_flow_signoff` or `provider_signoff`), never an unqualified assertion.
- **Gate IDs include scope in machine-readable data:** `gate.portfolio.g0`, `gate.project.g1` through `gate.project.g5`, and `ladder.silicon.l1` through `ladder.silicon.l7`. Short forms such as G3 and L2 are allowed only where the project or die is already explicit. This prevents unrelated projects' "G3" results from colliding in dashboards and issue searches.

- **Ordinal scales are prefixed** so a bare number is never ambiguous: portfolio outcomes are `O1`–`O4`, project gates are `G0`–`G5`, the first-silicon bring-up ladder is `L1`–`L7`, and Phase 0 is portfolio milestone `M0`. Gate G0 and Phase 0 are portfolio-scoped; Gates G1–G5 are per-project. Issues, claims, and reviews use the prefixed forms.
- **"Process" means fabrication technology and "macro" means a process-specific hardened block.** The word "platform" is retired from directories, targets, and documentation because it previously meant both. Use `block` when the abstraction may have several views or process implementations.
- **Hardened-macro releases are immutable and process-qualified.** Tags use `macro-<name>-<process>-vX.Y.Z`, while consumers pin the release-manifest digest and exact layout checksum. A semantic version is a navigation aid, not evidence that two layouts, metal stacks, or PDK revisions are interchangeable.
- **Silicon revisions** use `<project>-<die-role>-A0`; a metal-only respin increments the number (`A1`) and an all-layer respin increments the letter (`B0`). The stable die role distinguishes `wifi_nbiot_radio-combined-A0` from `wifi_nbiot_radio-wifi_focused-A0`. "v1" names the shuttle program, never a die revision.
- **Multi-mode projects use dotted mode identifiers** in specs, claims, waivers, and labels: `wifi_nbiot_radio.wifi_dsss` and `wifi_nbiot_radio.nbiot`.
- **Make-target grammar:** selectors use canonical IDs: `make COMPONENT=<id> <verb>` for a project or block, `make SUBMISSION=<id> <verb>` for one die package, and `make SHUTTLE=<id> <verb>` for the complete set. `PROJECT=<id>` remains a convenience alias restricted to project IDs. Plain verbs are selector-scoped (`check`, `claims`, `spec`, `open-flow-signoff`); portfolio-wide check suites use `check-<suite>` (`check-fast`, `check-digital`, `check-analog`, `check-integration`); repository and infrastructure maintenance uses `<noun>-<action>` (`process-eligibility`, `repo-audit`, `scratch-report`, `gc-dry-run`). `smoke`, `graph`, and `reproduce` are grandfathered portfolio verbs; new targets follow the grammar.

## Keeping the repository manageable

SVALBARD remains a **source monorepo** while the projects share flows, models, cells, and evidence schemas. Generated data is addressed by manifest and stored elsewhere. The default clone must stay useful without downloading PDKs, container images, waveforms, or old tapeout bundles.

### Dependency and ownership rules

- Dependencies form one direction: `projects/` may depend on `ip/`, `testlib/`, `flows/`, and `processes/`; reusable `ip/` may depend on lower-level `ip/`; no project may import files from another project. Promote shared work into `ip/` with a stable interface instead.
- Each `component.yaml` declares direct dependencies. `make graph` validates paths, reports cycles, and emits the compact dependency/ownership graph used to select affected checks.
- Give every shared block a stable ID independent of its directory name. Interface or evidence-breaking changes require a recorded architecture decision under `docs/adr/` and a compatibility note.
- Use maturity states `experimental`, `qualified`, `frozen`, and `retired`. Only `qualified` or explicitly frozen IP may enter a tapeout candidate. Frozen tapeout sources change only through a recorded waiver/re-spin decision.
- Keep a small root `portfolio.yaml` with program/project membership, state, next gate, and selected process. Component owners and dependencies remain canonical in their distributed `component.yaml` files. Generate `registry/index.json`, the roadmap, and status dashboards from those sources; never hand-edit the generated index or maintain a second status table. This avoids turning one registry file into a merge hotspot.
- Maintain `CODEOWNERS` on component boundaries and use one root build dispatcher; individual components expose standard targets rather than inventing unrelated build systems. GitHub issues use consistent `project:*`, `ip:*`, `gate:*`, `type:*`, and `priority:*` labels plus project/gate milestones.
- Assign a directly responsible owner and an independent reviewer to every tapeout-bound block, interface, top-level integration, and waiver. Generate ownership, orphan, and review-load reports from the registry. Shared ownership without one accountable approver is treated as missing ownership.
- Keep source close to its owner and evidence close to the claim index. The central `evidence/` tree stores manifests and dashboards only; a component owns its tests and compact reference results. This prevents a second shadow hierarchy organized by tool or project name.
- Split policy from execution documentation as the repository is bootstrapped: this file becomes the portfolio strategy and sequence; stable rules move to `docs/policies/`; G0–G5 criteria move to `docs/gates/`; the active v1 schedule and risk register move to `programs/silicon_v1/`; command details live beside `flows/`. Each fact has one canonical source and generated summaries link back to it.

### What belongs in Git

- Track human-authored source, schematics/layout source, RTL, compact-model source, configuration, schemas, small deterministic test vectors, compact plots/tables, claims, manifests, documentation, and scripts.
- Do not track installed PDK trees, cloned tool sources, Python virtual environments, Docker layers, build trees, generated netlists, PEX decks, simulation raw files, waveforms, Monte Carlo samples, temporary GDS/OASIS, or full run directories.
- Track a generated result only when it is small, reviewable, and part of the public argument. Every tracked result names its generator target and input manifest; otherwise it will become an unexplained stale binary.
- Treat final tapeout layouts, full evidence bundles, measured raw data, and reproducibility bundles as immutable release artifacts. Split release files below GitHub's per-asset limit and attach checksums plus a Minisign signature. Their small manifests remain in Git.
- Do not adopt Git LFS for reproducible generated output. Consider it only for versioned, human-authored binary source that cannot reasonably use a text format; LFS transfers consume the repository owner's quota and are awkward in public forks.

### Local artifact and cache layout

Use paths outside the Git worktree, all configurable by `bootstrap.sh`:

```text
SVALBARD_PDK_CACHE/       # immutable PDK installs keyed by lock digest
SVALBARD_TOOL_CACHE/      # downloaded sources/packages keyed by digest
SVALBARD_ARTIFACTS/       # content-addressed completed outputs
SVALBARD_SCRATCH/         # disposable active runs
```

Every run gets a unique ID and immutable `run.json` containing component ID, target, source commit/dirty state, input hashes, tool/image/PDK locks, seed, resource limits, start/end time, result, and artifact hashes. Identical content is stored once; project views reference hashes rather than copying files. `make reproduce RUN=<id>` reconstructs a released run from its manifest. `make gc-dry-run` reports unreachable local artifacts, and deletion requires an explicit second command with a retention policy; released or pinned artifacts are never collected.

Use four retention classes:

- **Scratch:** failed/intermediate runs, disposable after 14 days unless pinned.
- **Candidate evidence:** complete outputs retained locally until the related claim is accepted, superseded, or released.
- **Released evidence:** immutable manifest plus public release bundle; never garbage-collected automatically.
- **Irreplaceable measured data:** raw instrument output preserved with checksums in at least two independent locations, one of which is not this machine. Publish the legally shareable bundle or a redacted manifest with access/provenance notes.

### Repository health budgets

- Keep ordinary tracked files below 5 MiB and reject files above 25 MiB unless an allowlist explains why. GitHub blocks normal Git objects at 100 MiB, but waiting for that limit would already damage clone and review performance.
- Aim to keep `.git` below 1 GiB and treat 2 GiB as a stop-work cleanup threshold, well below GitHub's 10 GiB recommended on-disk ceiling. `make repo-audit` reports Git size, largest blobs, ignored-output leaks, directory width, dependency cycles, stale generated summaries, and missing licenses.
- Keep generated sweeps out of branches, use short-lived topic branches, and tag immutable environment, IP, evidence, and tapeout releases. Never solve growth by routinely rewriting public history; prevention is the policy.
- Provide project-scoped entry points such as `make PROJECT=standalone_fpga check` and `./bootstrap.sh pull --project standalone_fpga` so contributors fetch only the relevant images and PDK. Add sparse-checkout guidance only if source growth makes a normal clone meaningfully slow.
- Split a project into its own repository only when it has an independent maintainer/release cadence, no cross-project source imports, a stable versioned dependency on SVALBARD IP/flows, and source history large enough to harm the monorepo. Publish shared dependencies as immutable releases rather than creating a nest of Git submodules.

## First-silicon v1 program

The v1 program spans communications, sensing, memories, programmable logic, analog compute, and neuromorphic designs. It is designed around one fact: exhaustive verification cannot recover information absent from the process, device, pad, package, passive, mismatch, retention, optical, or reliability models. The highest-leverage first-silicon work is therefore to use qualified models and proven IP where available, constrain each v1 claim, add safe calibration range and architectural diversity, and make every uncertain block independently observable.

### V1 success budget, slot plan, and design diversity

Optimize first silicon for the probability of useful, diagnosable operation, not the number of features placed on the reticle. Before Gate G1, maintain a ranked top-risk register for each die and one program-level register for common-mode failures. Every existential risk has an owner, an independent reviewer, a retirement experiment, a deadline, a measurable margin, and a fallback. Verification activity without a decision threshold does not retire a risk.

Partition every die into three explicit classes in its floorplan and manifest:

1. **Must-work island:** only qualified pads, conservative supplies and clocks, scan/JTAG or SPI access, a tiny ROM or hardwired sequencer, known-good oscillator, reset status, and basic monitors. It must operate without firmware loading, external memory, a recovered clock, or any experimental analog block.
2. **Product path:** the minimum circuitry needed for the frozen integrated v1 claim. Each existential stage has raw observation or bypass access and safe manual control.
3. **Experiment area:** alternate architectures and stretch features. It has separate enables and cannot load, back-power, clock, reset, or block the must-work island when disabled.

### Six cross-die design-assurance rules

Implement these as shared blocks and fields in existing manifests, not as six new documentation systems. One `make design-assurance` target validates them for a component, submission, or the whole shuttle.

1. **Golden path:** every project defines `golden_path` in `spec.yaml`: the minimum fully integrated v1 mode, its exact block and clock/power dependencies, conservative configuration, required margin, raw diagnostic path, and forbidden dependencies on experimental features. `make design-assurance` rejects a golden path that depends on unqualified IP, a stretch feature, or an undocumented calibration state. External firmware or FPGA configuration is allowed only when it is an explicit product interface with a frozen image/bitstream, verified loader, failure recovery, and a lower-level debug path that remains available if loading fails.
2. **Boundary access:** every digital product die instantiates the shared test-access block with JTAG IDCODE, BYPASS, SAMPLE/PRELOAD, and EXTEST behavior plus scan access. Call it IEEE 1149.1-compatible only after a compliance review against the legally sourced standard. If pad pressure prevents dedicated JTAG pins, the SPI debug bridge must provide equivalent pad sample/drive and scan functions without weakening the normal SPI recovery path.
3. **Event trace:** every control island includes a small shared trace block storing at least 64 timestamped events in a circular buffer. Standard events include reset and power-good causes, clock/PLL lock changes, calibration state transitions, interrupts, protocol/FIFO errors, watchdogs, and software markers. A trigger freezes the buffer; SPI or JTAG can read it; soft reset does not erase the recorded cause unless explicitly commanded.
4. **Reset/clock supervisor:** every die has one conservative supervisor owning reset causes, safe clock selection, external-reset override, external reference-clock mode, the proven diagnostic ring oscillator, clock-present/lock status, and safe-reset configuration selection. Use qualified/proven POR or an external supervisor path; an experimental POR or brownout detector may be monitored but is never the only way to release or hold reset. Clock switching is glitch-free or occurs only while affected domains are held in reset.
5. **One interface source:** each submission owns one `interfaces.yaml` containing pad name and direction, voltage domain, reset state, drive/pull policy, package pin, bond option, PCB net, connector pin, RTL port, register-visible function, and firmware alias. Generate padframe tables, package/bond tables, PCB pin lists, constraints, documentation, and software constants from it. `make pin-audit` rejects missing or contradictory mappings and compares the final layout, package, and board netlists.
6. **FMEA without another database:** extend each existing `risks.yaml` entry with `failure_mode`, `local_effect`, `system_effect`, `criticality`, `common_cause_id`, `observable`, `control_or_bypass`, `fallback`, `owner`, reviewer, and evidence. Generate per-die FMEA and one cross-shuttle common-cause report. Scores prioritize work but never override a critical undetectable failure; that requires a monitor, escape path, design change, or explicit red status.

The shared JTAG/SPI test-access, trace, supervisor, and schema generators are frozen reusable blocks. Projects configure event sources and pad mappings instead of writing local versions. This keeps the assurance logic small enough to verify exhaustively and prevents ten slightly different debug systems.

Apply these closure rules to every committed v1 submission:

- Finalize the ten committed die roles at G1. After slot lock, scope reduction must preserve the die's primary experiment or integrated claim; replacing or removing a role requires a program decision record. The goal is to close every committed design, not quietly drop the difficult ones.
- No submission reaches candidate freeze until its final RTL, register map, boot image, package model, board, and external components have passed the declared hardware-in-the-loop and extracted co-simulation tests. "Nearly final" is not an accepted configuration.
- Close nominal performance with explicit design margin before counting calibration. Calibration covers residual PVT, mismatch, and bounded model error; it is not the primary means of making a nominal circuit meet its requirement.
- Prefer a proven lower-performance implementation as the required path and place a new high-performance implementation as an independently isolatable option. Diversity matters more than duplicating the same schematic.
- Define freeze dates for specification, interfaces, RTL/ROM, schematic, floorplan, layout, package/board, and submission. After each freeze, changes require a named change request, impact analysis, re-run set, and approver; waivers cannot create new functionality.
- Limit simultaneous physical integration to what the named owners and reviewers can close. A shared block counts once for design effort but once per consumer for integration, package, supply-noise, and bring-up review.
- Hold pre-mortem reviews at G1, before layout, and before candidate freeze: assume the die failed at L1, L3, and L6 and demonstrate how the available pins, monitors, bypasses, and power partitions distinguish the likely causes.

The provisional ten-slot allocation is:

| Die role | Primary purpose |
|---|---|
| `process_characterization-main-A0` | Device, passive, pad, interconnect, variation, and exact local product-replica correlation |
| `rtl_sdr_tuner-main-A0` | Complete 50 MHz–1.7 GHz tuner with selectable LNA, mixer, filter, oscillator, and gain variants |
| `cmos_image_sensor-main-A0` | Image-sensor array with pixel, readout, dark-reference, and test-injection variants |
| `silicon_v1-analog_neural_compute-A0` | Floating-gate analog NVM weights + spiking neural processor, with separate program/verify and digital-event test modes |
| `silicon_v1-wireline_networking-A0` | Gigabit Ethernet + PCIe endpoint SoC, optionally sharing control/DMA/clocking while retaining raw PHY diagnostics |
| `wifi_nbiot_radio-combined-A0` | One-die WiFi + NB-IoT product with isolated mode paths, RF variants, and external converter/LO escape modes |
| `silicon_v1-programmable_memory-A0` | Standalone 1–2k-LUT FPGA + optional gain-cell eDRAM block memory, open bitstream, and nextpnr flow |
| `silicon_v1-wired_io-A0` | USB 2.0 + DDR1 peripheral SoC with shared control/test infrastructure and direct PHY test modes |
| `spad_lidar-main-A0` | SPAD arrays, quench/readout, timing, optical test, and guard-ring variants |
| `process_characterization-risk_macro_matrix-A0` | Directly bonded PLL/CDR, ADC/DAC, RF, pad, reference, memory, and optical high-risk variants |

This table is finalized only after G0 confirms that the provider counts and accepts ten designs and after die-size, package, pad, and staffing budgets are assigned. Combining projects does not erase their identities: each retains its component manifest, allocated requirements, claims, owner, and verification evidence even when the silicon implementation is a coupled SoC.

Every combined die declares one integration class in its manifest:

- **`isolated_islands`:** projects share only die/package area and have separate operating infrastructure.
- **`shared_services`:** projects share named services such as control, memory, clocking, references, converters, interconnect, pads, or test logic.
- **`integrated_soc`:** projects intentionally depend on each other to deliver the primary system use case.

For `shared_services` and `integrated_soc`, record the dependency graph, area saved, interfaces removed, shared failure domains, power-up order, project claims that remain independently measurable, and system-level claims created by the coupling. Coupling is favored when it removes duplicated infrastructure or enables a valuable end-to-end demonstration. It is rejected when the saved area is small but one immature block would make every project on the die unobservable.

The coupled-die contracts are explicit: the FPGA must configure and run ordinary user logic without gain-cell eDRAM succeeding; eDRAM is optional block memory. Floating-gate arrays must support direct program/verify and analog compute measurements without the spiking network, while the spiking network retains digital weight/event injection without floating-gate operation. USB and DDR1 retain direct PHY modes around their shared bridge/control path. Ethernet and PCIe retain raw PHY and traffic-generator modes around shared DMA or clock services.

Use a separate die when shared pads, supplies, clocks, substrate, package parasitics, destructive/high-current behavior, or a common control path could prevent independent diagnosis. Put variants on one die when they benefit from matched local process conditions and can be independently powered, reset, selected, observed, and bonded without a measurement-invalidating multiplexer. Existential variants should normally exist both as selectable product-die fallbacks and as directly bonded structures on a focused or macro-matrix die.

Every variant has a stable ID and `variant.yaml` recording its parent block, hypothesis, intentionally changed axes, intentionally held-constant axes, expected discriminating measurement, safe operating limits, selection method, and owning claims. Prefer controlled diversity over arbitrary duplication. Useful diversity axes include circuit topology, device family and geometry, bias/reference generation, clock source and recovery method, passive implementation, pad/ESD option, orientation and neighborhood, and calibration range. Two copies sharing the same reference, state machine, supply switch, or unobservable output do not count as independent fallbacks.

Cost-independent replication also applies after fabrication. At G1, set a sample-size and packaging matrix for each submission: wafer-probe quantity, packaged-unit quantity, package type, alternate bond-outs, environmental range, and minimum number of dies/sites needed for each claim. Where the provider permits it, probe first and package known-good dies; retain unbonded samples for failure analysis. Do not package every sample with the same bond-out when alternate pads can expose independent clocks, references, raw data, or fallback circuits. A single working sample demonstrates possibility, not yield or robustness.

### Designing around genuinely missing calibration data

Maintain `uncertainties.yaml` per project. Each entry names the uncertain physical parameter or behavior, available evidence and its validity range, conservative bound or statement that no defensible bound exists, sensitivity of each top-level claim, correlated blocks, observable silicon quantity, available control, safe fallback, and the v1 measurement that will resolve it. Keep model uncertainty separate from PVT, mismatch, numerical error, and package tolerance. When no defensible probability distribution exists, use bounded sweeps, sensitivity analysis, and adversarial combinations; do not invent a Gaussian Monte Carlo distribution to produce a comforting yield number.

### GF180 public technical-data gaps and forced mitigations

Treat this as an audit of the **exact pinned public GF180MCU release**, not a claim that GlobalFoundries never generated the information. The public documentation describes itself as an experimental preview and work in progress, and the public repository was archived read-only in April 2026. It does publish substantial material—including compact models, some measured 1/f-noise data, statistical models, EM and reliability guidance, device-level TLP data, I/O and SRAM libraries, eFuse rules, and RF/inductor recognition layers—so those items must not be mislabeled as wholly absent. What is missing for this portfolio is often the measured distribution, correlation, qualified operating envelope, package context, or model for a non-standard device. A marker layer or legal layout rule establishes recognition and manufacturability constraints; it does not establish electrical performance.

The initial public audit baseline, dated 2026-08-16, is the archived [GF180MCU PDK repository](https://github.com/google/gf180mcu-pdk), [documentation status](https://gf180mcu-pdk.readthedocs.io/en/latest/), [high-voltage model features and limitations](https://gf180mcu-pdk.readthedocs.io/en/latest/analog/model_parameters/HV/HV_2_2.html), [low-voltage statistical-model guide](https://gf180mcu-pdk.readthedocs.io/en/latest/analog/model_parameters/LV/LV_9.html), [reliability guidance](https://gf180mcu-pdk.readthedocs.io/en/latest/physical_verification/design_manual/drm_14.html), [ESD characterization](https://gf180mcu-pdk.readthedocs.io/en/latest/physical_verification/design_manual/drm_14_5.html), [published IP list](https://gf180mcu-pdk.readthedocs.io/en/latest/IPs/ips.html), and the [drawn-layer catalogue](https://gf180mcu-pdk.readthedocs.io/en/latest/physical_verification/design_manual/drm_04_1.html). Gate G0 must replace broad documentation URLs with exact commit/file checksums and correct any link or conclusion that does not match the selected provider release.

At Gate G0, create `processes/gf180/data_gaps.yaml` as the canonical register and generate the readable table below from it. Every required datum has exactly one disposition: `public_qualified` (present and valid over the project's geometry, bias, frequency, temperature, layout, and simulator range), `provider_supplied` (received under controlled access and revision-locked), `bounded` (not available, but an independently reviewed conservative bound supports the claim), or `unavailable`. “A similar plot exists” and “simulation converged” are not dispositions. Each entry records source and revision, validity envelope, affected projects and claims, owner, decision deadline, fallback, required silicon structure, and evidence link. `unavailable` is allowed at tapeout only when the associated claim survives the forced mitigation; otherwise it is a red gate.

The following data is not established by the pinned public release for the uses in this portfolio unless Gate G0 records contrary evidence:

| Missing or insufficiently scoped technical data | Why the public material is not enough | Required v1 de-risking when it remains unavailable |
|---|---|---|
| **Measured production distributions and correlations** across lots, wafers, die position, orientations, device families, passives, and environmental corners | Public statistical models exist, but some high-voltage global models are target-based rather than silicon-verified, and a Monte Carlo model does not by itself disclose lot history, spatial covariance, tails, or cross-device correlation | Use worst-case bounded sensitivity in addition to Monte Carlo; replicate exact local geometries at die center/edge and beside each critical block; use common-centroid/local references; provide trim range with margin at both rails; package and test enough dies/sites to distinguish local mismatch from global shift |
| **RF compact-model validation envelopes** for every MOS geometry, bias, noise metric, and simulator through 1.7 GHz, 2.4 GHz, 1.25 GBd, and 2.5 GT/s | Published DC/temperature and 1/f-noise characterization does not establish S-parameters, noise parameters, large-signal behavior, or accuracy for every portfolio operating point | Use conservative device sizes and bandwidth targets; compare at least two model/simulator paths; include direct transistor, LNA, mixer, sampler, driver, ring/LC oscillator, and CML structures; expose external LO/clock and raw nodes; provide wide bias, gain, bandwidth, phase, and termination trims |
| **Qualified scalable models or measured S-parameter libraries for custom inductors, transformers, transmission lines, varactors, and RF interconnect**, including density-fill and substrate effects | Public rules contain inductor/RF marking and fill guidance, but recognition layers do not supply a qualified component library or prove a custom geometry's Q, self-resonance, coupling, or variation | Keep match-sensitive networks off chip where possible; EM-simulate post-fill geometry with documented stack assumptions; fabricate geometry sweeps plus open/short/thru/load and de-embedding structures; include external matching and alternate bond-outs; never make a single custom inductor existential |
| **Package, bond-wire, bump, lead-frame, socket, connector, and board parasitic distributions** for the selected assembly | The PDK gives pad/bond geometry rules and explicitly leaves assembly capability and some bond optimization to the customer; the actual package is not a transistor-process model | Select assembly and package before padframe freeze; obtain vendor stack/material/tolerance data or bound it; co-simulate package and board; add package coupons and de-embedding paths; provide series/shunt DNP footprints, alternate bond lengths/bond-outs, external terminations, and lower-rate modes |
| **Substrate-coupling and simultaneous-switching data** for the actual combination of radios, converters, clocks, memories, digital logic, pads, and package | Deep-N-well and latch-up rules provide legal isolation practice, not a predictive portfolio-specific noise-transfer or ground-bounce model | Partition supplies and returns; use deep wells, guard rings, spacing, quiet modes, staggered switching, programmable edge rate, and local decoupling; place aggressor/victim and substrate-transfer monitors; make every sensitive block testable with noisy neighbors disabled and with external clean references |
| **Full-chip ESD/latch-up immunity and high-frequency pad behavior for each custom pad network and package** | Device-level TLP data, I/O-library targets, and layout rules do not establish HBM/CDM performance, latch-up immunity, pad capacitance, leakage, or bandwidth for an arbitrary top-level network; published guidance warns that TLP-to-HBM correlation can vary | Default to provider-qualified I/O cells and their permitted application; obtain provider review of the assembled pad ring; model and directly measure pad capacitance/leakage; include pad-only chains and alternate ESD/load variants on the macro die; apply current-limited bring-up; claim no ESD rating without system-level evidence |
| **Optical-device data for custom image photodiodes and SPADs**: spectral quantum efficiency/PDE, breakdown distribution, dark current/count, afterpulsing, optical/electrical crosstalk, timing jitter, dead time, radiation response, and temperature dependence | No public compact model or qualified SPAD/image-sensor PCell establishes these properties for the proposed geometries and guard rings | Obtain explicit provider acceptance before layout; tape geometry/implant/guard-ring/pitch arrays rather than one pixel; include dark/reference rows, shielded devices, electrical charge/event injection, direct-device pads, tunable current-limited bias/quench/dead time/threshold, temperature sensing, and conventional photodiode or electrical-test fallbacks where useful |
| **Floating-gate analog NVM program/erase physics and distributions**: injection/tunneling conditions, coupling ratios, verify behavior, retention, endurance, disturb, cycling drift, and safe oxide stress | Public OTP/eFuse/MTP layers and rules do not qualify a custom analog floating-gate cell; some MTP-specific layers are explicitly described as IP-vendor structures not supported in the public PDK release | Treat the cell as experimental and obtain written provider disposition; use legal standard devices unless approved otherwise; isolate every pulse domain; generate pulses externally in early bring-up; enforce hardware voltage/current/time clamps; include cell/coupling/reference sweeps, direct terminals, per-cell program/verify, reference cells, and a digital-weight injection path so compute does not depend on NVM |
| **eFuse/OTP/MTP macro characterization beyond layout legality**, when any such feature is used: programming window/current, resistance distributions, read margin, yield, retention, endurance, disturb, and qualified driver/sense circuits | The public kit exposes rules and some library-related layers, but a legal fuse geometry is not a characterized memory macro and vendor-specific MTP support cannot be inferred | Use a qualified licensed macro if obtainable; otherwise keep the feature non-essential, add redundant bits and ECC/majority coding, external current-limited programming, resistance readback, verify-after-write, programmable sense references, raw test access, and an ordinary volatile or package-level configuration fallback |
| **Gain-cell eDRAM distributions**: state-dependent leakage, retention tails versus temperature, read/write disturb, coupling, sense offset, refresh interaction, and aging | Gain-cell eDRAM is a custom circuit built from ordinary devices, not a characterized public GF180 memory primitive | Include multiple cell and sense topologies, geometry sweeps, monitor rows, raw bit-line access where practical, programmable write/read/restore timing, sense threshold, refresh and supply; use BIST, ECC and redundancy; keep conventional SRAM/register memory available and make FPGA operation independent of eDRAM |
| **Bit-failure/yield, Vmin, retention, dynamic-margin, and lot-tail data for the exact public SRAM macro integration** | Public SRAM views and timing/power corners do not by themselves provide the bit-level production distribution needed to predict yield in this die, supply network, and use mode | Prefer several smaller independently powerable macros; run foundry test modes if supported; add March BIST, address/data diagnostics, parity/ECC, spare capacity or graceful capacity reduction, voltage/frequency sweep, and a small flop/register fallback for boot and control |
| **Compact aging and lifetime models** for BTI, HCI, TDDB, dielectric breakdown, hot-carrier duty cycle, analog drift, memory cycling, and electromigration under each waveform | Published operating/reliability limits and EM rules are valuable constraints but are not a complete predictive aging model for arbitrary waveforms or a warranty for a custom circuit | Stay inside published limits with explicit voltage/current/duty-cycle derating; avoid bootstrap or over-voltage dependence; add stress replicas, counters and reference monitors; provide lower-stress modes; plan burn-in and accelerated characterization; make no lifetime claim until measured or provider-qualified evidence exists |
| **Thermal model of the completed die/package/board and local self-heating/cross-heating** | Process temperature corners do not predict spatial temperature rise from the portfolio's PAs, drivers, memories, or programming circuits | Budget average and peak power by island; instrument representative hot and quiet locations; provide duty-cycle/current limits and thermal shutdown; separate hot blocks physically; test with package thermometry/IR methods; preserve reduced-rate and reduced-power modes |
| **Signoff-grade variation context for digital timing/power/noise**, including any required OCV/AOCV/POCV assumptions, SRAM/interface interaction, IR-drop dynamics, and clock jitter correlation | Liberty corners and open-flow STA enable design, but do not automatically provide all production-signoff correlation and variation methodology used by a commercial reference flow | Use conservative clock targets and uncertainty, multi-corner STA, independent clock monitors, post-layout extracted simulation, vectorless plus activity-based IR analysis, scan/BIST, programmable dividers and wait states, and provider review of the final methodology; boot and debug must work at the slowest mode |
| **Post-fill and neighborhood-dependent parasitic/model error** for precision analog, RF, optical, memory, and matched structures | Density rules and exclusions constrain layout, but do not quantify every local STI/CMP/fill-induced shift or coupling effect; published model limitations note incomplete STI-stress fitting | Insert final fill before the last extraction and review; keep controlled symmetric neighborhoods; use legal fill-exclusion marks only where justified; replicate structures with product-like fill and at least one deliberate neighborhood variant; reserve trim for residual systematic error |
| **Radiation/soft-error behavior**, if any project later makes a radiation, space, safety, or long-retention integrity claim | The public MCU PDK is not a radiation-qualified data set, and ordinary memory models do not establish SEU, TID, SEL, or displacement-damage performance | Make no radiation claim in v1; if the claim becomes required, add dedicated test vehicles, TMR/ECC/scrubbing and current limiting, obtain a qualified test plan and facility, and treat results as empirical for the exact layout and lot |

Absence itself must be verified reproducibly. `make process-data-audit` checks every portfolio requirement against the pinned model manuals, design manual, IP/library documentation, model files, extraction rules, provider documents, and assembly data; it emits a coverage report and rejects uncited `public_qualified` entries. A search returning no result is not proof of absence: two reviewers must record the sources and scopes checked, and provider questions must be captured with their exact answers and permitted disclosure level. Restricted data can satisfy an internal gate without being published, but the public repository then records its checksum, scope, reviewer, and a non-confidential statement of the conclusion.

The mitigation is part of the design, not a future characterization promise. Gate G1 maps every top-level claim to its data dependencies and forced mitigations. Gate G3 verifies the selected bounds and all legal trim/fallback modes post-layout. Gate G4 requires the directly bonded structures, monitors, safe clamps, package/board options, and bring-up procedures to exist in the final layout and test collateral. No same-shuttle measurement may be listed as evidence that a v1 product circuit will work; it can only explain, select, calibrate, or improve silicon that already tolerates the declared uncertainty.

For each existential uncertainty, prefer a portfolio of four implementations where area and pins permit:

1. **Conservative baseline:** the simplest topology using qualified devices and the widest defensible margin.
2. **Controlled sweep:** several geometries or component values changing one dominant axis while holding the neighborhood and interface constant.
3. **Topology-diverse fallback:** a physically different implementation whose dominant failure mechanism is not shared with the baseline.
4. **Local replica:** a small directly measurable structure placed near the product block with matching orientation, density, guard rings, and routing context.

Do not multiply variants blindly. A variant must distinguish a named hypothesis, and its expected measurement must be able to select between those hypotheses. The cross-die diversity matrix reports coverage of failure mechanisms rather than merely counting schematics.

Every trim or calibration control has a machine-readable contract containing units, encoding, expected monotonicity, safe and forbidden codes, reset value, readback, manual override, resolution, modeled useful range, parasitic cost, and the uncertainty budget it covers. Use coarse/fine or thermometer-plus-binary structures where they avoid large discontinuities. Provide hardware clamps for unsafe bias, voltage, current, PA power, SPAD excess bias, floating-gate programming pulses, and clock configurations; software must not be able to select a destructive combination. Keep v1 calibration volatile and repeatable.

Size trim range from separate allowances for modeled PVT, mismatch, package/board variation, aging or stress where relevant, and missing-model error. The normal target must lie away from both trim rails; a nominal design that works only at the last code has no useful calibration margin. At G3, report post-layout range, monotonicity, resolution, coverage, and performance at every legal code, including switch parasitics and disabled-branch loading.

Build a small always-on measurement fabric around the conservative control island: frequency/period counters, divided clock outputs, temperature and supply monitors, bias/reference readback, scan-visible calibration state, event/error counters, timestamped reset/lock-loss causes, and a buffered low-bandwidth analog monitor bus. High-frequency, high-impedance, optical, and noise-critical nodes use dedicated pads or local detectors because a general analog mux can invalidate the measurement. Every monitor has an input-loading budget and a way to prove that its disabled state does not compromise the product path.

Before layout freeze, generate a **control-to-observable identifiability matrix**. Each dominant uncertain parameter or failure class must affect at least one reachable observable, and at least one control, bypass, or variant must change the outcome. Fault-inject behavioral twins and mixed-signal tests with opens, stuck trim bits, dead clocks, saturated amplifiers, leaky cells, bad references, excessive offsets, and failed shared services. If two likely failures produce the same observations and require different remedies, add a monitor or raw test path before tapeout.

Use package and board variation as part of the experiment. Reserve alternate bond-outs, external reference/clock/LO injection, separately adjustable supply and bias rails where safe, and DNP/selectable matching, termination, filtering, and decoupling footprints. Keep model-sensitive matching off chip in v1 unless integration is itself the experiment. Board variants are cheaper and faster to search than irreversible on-die matching choices.

Tunability has a cost. Each project sets budgets for trim bits, switches in the signal path, monitor loading, extra area, static current, pad count, calibration time, and verification combinations. Use sensitivity ranking and covering arrays or designed experiments to choose regression combinations; still test every legal code for electrical safety. Freeze a small set of named configurations—`safe_reset`, `external_debug`, `conservative`, `nominal`, and `performance`—so bring-up does not begin with an unbounded search through thousands of undocumented settings.

The highest-value project-specific controls and variants are:

| Project/die | Variants and tunable controls to prioritize |
|---|---|
| `rtl_sdr_tuner` | LNA topology/geometry, mixer topology and phase correction, switched RF/baseband filter banks, gain distribution, bias currents, VCO bands, external LO, and direct mixer/baseband outputs |
| `cmos_image_sensor` | Pixel geometry and device options, conversion gain/capacitance, reset and source-follower bias, integration time, row timing, column amplifier/ADC offset trims, dark rows/columns, and electrical charge injection |
| `gain_cell_edram` + FPGA | Cell geometry/layout variants, boosted/non-boosted access where legal, word/bit-line timing, sense threshold, retention monitor rows, programmable refresh, voltage margins, bypassable eDRAM blocks, and conventional small-memory fallback |
| Floating-gate + spiking compute | Cell/reference variants, isolated program/erase pulse amplitude/width/count, verify thresholds, read bias, ADC/DAC references, neuron/synapse bias and time constants, digital weight/event injection, and direct array/neuron observation |
| Ethernet + PCIe | Diverse clock/CDR paths, TX current/swing/deemphasis, termination, RX bandwidth/threshold/phase, reference-assisted modes, PRBS/eye scan, raw symbols, external clocks, and near/far loopbacks |
| WiFi + NB-IoT | LNA/mixer/PA variants, synthesizer bands and loop settings, RF/baseband gain and bandwidth, I/Q/DC/LO-leakage correction, converter references and phase, PA segmentation/ramp, external LO/converter access, and RF/baseband loopbacks |
| USB 2.0 + DDR1 | Driver strength/slew and impedance codes, receiver thresholds, USB HS/FS modes, DDR output drive and external termination options, DLL phase/bypass, sampling phase, training patterns, and direct PHY loopbacks |
| `spad_lidar` | Guard-ring and active-area variants, externally limited excess bias, passive/active quench variants, recharge/dead time, discriminator threshold, dark-count isolation, TDC topology/bin calibration, electrical event injection, and direct SPAD outputs |
| High-risk macro matrix | Device geometry/orientation arrays, pad/ESD alternatives, reference topologies, oscillators, PLL/CDR, ADC/DAC, memory cells, transmission lines/passives, and structures replicated at center/edge and beside relevant noisy blocks |

### Processor-friendly external and on-die interfaces

Base the common host interface on processors and SoCs that have actually entered wafer.space GF180 fabrication, not on a hypothetical development board. The wafer.space Run 1 registry includes KianV, RISCBoy-180, three Racquet configurations, and TinyQV RISC-V designs. KianV is an RV32IMA/Sv32 Linux-capable SoC with UART, two four-wire SPI controllers, GPIO, a NOR-flash controller, and external 16-bit SDRAM under a strict 58-signal I/O budget. TinyQV is an RV32EC SoC with UART, SPI, PWM, programmable I/O, QSPI flash/PSRAM, and a documented 3.3 V, nominal 24 MHz operating point. Racquet boots SERV cores from SPI flash and exposes UART/timer-oriented peripherals; RISCBoy uses an AHB-Lite/APB-style internal fabric and includes UART/SPI/GPIO-class peripherals. The Run 1 FABulous FPGA also uses active or passive SPI configuration, reinforcing SPI as the ecosystem's practical low-pin-count control interface.

Primary sources for the compatibility lock are the [wafer.space Run 1 registry](https://github.com/wafer-space/ws-run1), [KianV GF180 design](https://github.com/splinedrive/gf180mcu-kianv-rv32ima-sv32), [KianV interface description](https://www.crowdsupply.com/wafer-space/gf180mcu-run-2/updates/taping-out-kianv-a-linux-xv6-capable-risc-v-soc), [TinyQV GF180 design](https://github.com/MichaelBell/ws01-tinyQV), [Racquet GF180 design](https://github.com/gregdavill/gf180mcu-racquet), and [RISCBoy-180](https://github.com/Wren6991/RISCBoy-180). Pin and voltage compatibility is locked to exact repository revisions during G0/G1; a core appearing in the run registry does not prove that every peripheral is bonded out or electrically compatible in every configuration.

Every SVALBARD die intended to be controlled by a processor implements the versioned `svalbard_host_v1` contract:

- **Primary board transport:** four-wire SPI peripheral mode with `host_cs_n`, `host_sclk`, `host_mosi`, and tri-stated `host_miso`. The processor is controller. Mode 0 is mandatory; operation starts at or below 1 MHz and the characterized maximum is reported per die. Transactions are byte-oriented and tolerate arbitrary pauses between bytes.
- **Optional event pin:** active-low level `host_irq_n`, with mask, status, and write-one-to-clear registers. Every function remains usable by polling because KianV exposes only one general GPIO and may need it elsewhere.
- **Reset and readiness:** `host_reset_n` is optional when package pins permit; otherwise the interface uses the chip reset. A readable boot-state register and bounded startup time replace a mandatory `READY` pin. No output drives during reset, and MISO is high impedance whenever chip select is inactive.
- **UART fallback:** processor-facing dies include a compact 8-N-1 UART packet transport where its two pads and clock tolerance are affordable. It exposes the same register and FIFO operations as SPI, starts at a documented conservative baud rate, and exists for Racquet/RISCBoy-class hosts or emergency bring-up rather than bulk data.
- **Electrical profile:** default to a provider-qualified 3.3 V CMOS pad interface compatible with TinyQV's documented operating point. Any direct 5 V compatibility, power-off tolerance, pulls, drive strength, or level shifting is claimed only after the exact pads and host I/O levels are checked. G0 records whether a zero-component connection is safe or a simple board level shifter is required.

This management contract is required for the tuner, image sensor, analog-neural accelerator, wireline-networking SoC, WiFi/NB-IoT radio, programmable-memory FPGA, USB/DDR SoC, SPAD/LiDAR die, and characterization/macro-matrix dies. A die may omit UART or the optional streaming bus through a recorded pin-budget decision, but it may not omit the four-wire SPI control path unless its standards-native interface is itself the explicit processor connection and a reviewed recovery/debug path exists.

All transports expose one little-endian, 32-bit logical register ABI. Offset zero begins a read-only capability block containing magic `SVBD`, ABI major/minor, project and die IDs, silicon revision, register-map hash, feature bits, legal transport speeds, FIFO sizes, reset cause, and build identifier. Common registers cover scratch/readback, global status, interrupt status/mask, soft reset, named configuration selection, command mailbox, response mailbox, and byte FIFOs. Project registers start at a generated aligned offset. Unknown registers read as zero and ignored writes set a sticky protocol-error bit; ABI-major changes are incompatible, while ABI-minor additions preserve existing offsets and behavior.

SPI is the universal control and low-rate data plane, not a substitute for every native interface. Camera frames, RF I/Q, LiDAR events, FPGA configuration at scale, memory traffic, and accelerator data use the optional `svalbard_stream_v1` family. Ethernet, PCIe, USB, and DDR retain their standards-native data interfaces plus the common management transport where pins permit.

The normative high-rate profile is **`svalbard_stream8_sdr_v1`**, a unidirectional 8-bit source-synchronous SDR channel targeted at 50 MHz and 50 MB/s raw throughput. It consists of `stream_data[7:0]`, forwarded `stream_clk`, `stream_valid`, returned `stream_ready`, and `stream_last`. The producer changes data and sidebands on the falling edge; one transfer occurs on a rising edge when both valid and ready are high. The consumer changes registered ready on a falling edge of the received clock, and the producer samples it on a rising edge. The forwarded clock runs continuously from training through the end of an enabled session. A channel can be die-to-host or host-to-die. Designs needing full duplex instantiate two independent channels rather than a bidirectional bus with turnaround states.

The same RTL supports width profiles `stream4`, `stream8`, and `stream16`, providing raw rates of 25, 50, and 100 MB/s respectively at 50 MHz. Eight bits is the interoperability default. Width changes are physical-interface variants, not runtime modes. SDR is mandatory; DDR sampling and serialized extensions are deferred until SDR silicon and board measurements justify them.

Every stream source supports 1, 10, 25, and 50 MHz rates selected through the SPI control plane, begins at 1 MHz for bring-up, and emits continuous training, walking-bit, counter, PRBS, and idle patterns without the application block running. The receiver reports byte/word count, packet count, overflow, underflow, sequence error, framing error, and CRC error through `svalbard_host_v1`. A failed or absent stream never prevents SPI access.

Streams use a small versioned packet header containing type, flags, stream ID, sequence number, payload length, and optional timestamp, followed by payload and CRC32. `stream_last` marks the final transfer. Backpressure may occur on any transfer; producers contain a sized elastic FIFO and report data loss rather than silently overwriting samples. Continuous-rate sources whose physics cannot pause declare their minimum FIFO depth and maximum host-service latency at G1.

Use provider-qualified 3.3 V pads with programmable drive/slew where available, source-series termination footprints, short point-to-point board routing, adjacent grounds, and a defined simultaneous-switching budget. Fifty MHz is a required target only after post-layout pad/package/board timing closes across the declared environment; 25 and 10 MHz remain required fallback modes. The forwarded clock and training patterns allow a future host to qualify sampling phase without relying on matched internal oscillators.

The source repository provides parameterized producer/consumer RTL, asynchronous and synchronous FIFO options, APB3 and Wishbone DMA wrappers, FPGA reference endpoints, a loopback test design, timing constraints, and a shared connector definition. A future processor chip can therefore add the link as a FIFO-backed peripheral without implementing PCIe, USB, or a complex SerDes.

Apply `stream8` by default to CMOS image output, RTL-SDR I/Q capture, WiFi/NB-IoT raw I/Q debug, SPAD event output, analog-neural input/output, FPGA configuration/debug, and macro-matrix capture. Use `stream16` only where the bandwidth calculation and pin/package budget require it. Processor hosts lacking the parallel interface use SPI diagnostic operation or a SVALBARD FPGA bridge; compatibility with existing wafer.space RISC-V chips is preserved without constraining future chips to SPI bandwidth.

For same-die RISC-V integration, implement the register file and FIFOs once behind a bus-neutral request/response core, then provide checked wrappers for APB3 and Wishbone B4 plus the SPI/UART bridges. Do not expose AHB, APB, or Wishbone as board-level parallel pins. The wrappers share generated register semantics and pass transaction-level equivalence tests, allowing RISCBoy/APB-like, SERV/Wishbone-like, or future SVALBARD control fabrics to reuse the same block without forking its register map.

Generate from the canonical register schema: synthesizable RTL, C headers and a freestanding no-allocation driver, a Rust register crate, Python bring-up bindings, a Linux SPI driver and device-tree binding where appropriate, protocol documentation, and cocotb/Verilator host models. Gate G2 requires the final device RTL and software to operate against emulated KianV-style SPI/GPIO constraints and TinyQV-style 3.3 V/24 MHz timing assumptions. Reference boards use the same connector pin order for SPI, UART, IRQ/reset, ground, and selectable I/O voltage so one wafer.space RISC-V host adapter can control every applicable SVALBARD die.

### Exact v1 targets and integration boundary

Freeze these deliberately modest targets in each project's Gate G1 specification:

| Project | Required fully integrated v1 target | Stretch target | Explicitly deferred |
|---|---|---|---|
| `ethernet_mac_phy` | Gigabit Ethernet MAC, PCS, and complete on-chip 1000BASE-X 1.25 GBd SerDes/PMA | Integrated 10BASE-T/100BASE-TX fallback path with external magnetics | 1000BASE-T copper, multi-port switching |
| `pcie_gen1_endpoint` | PCIe Gen1 x1 endpoint with one diagnostic BAR, common-clock short-channel operation, and complete on-chip 2.5 GT/s PHY | Wider protocol feature coverage after basic enumeration and data transfer | Gen2+, multiple lanes, root-complex mode |
| `wifi_nbiot_radio.wifi_dsss` | 2.4 GHz legacy DSSS station interoperating at 1 and 2 Mbit/s under the exact selected IEEE profile | 802.11b 5.5/11 Mbit/s CCK after the basic rates work | OFDM modes, 5 GHz, MIMO |
| `wifi_nbiot_radio.nbiot` | Half-duplex UE for one selected band, release, deployment mode, and power class | Additional channels within the same band | Cat-M, broadband LTE, multi-band operation |

The other product projects also receive explicit, measurable G1 targets rather than being treated as background experiments: full-range tuner operation for `rtl_sdr_tuner`; captured images and characterized pixel/readout behavior for `cmos_image_sensor`; write/read/retention operation for `gain_cell_edram`; program/verify plus analog vector-matrix operation for `floating_gate_analog_nvm`; a standalone 1–2k-LUT configured FPGA running user logic for `standalone_fpga`; USB 2.0 device enumeration and transfers for `usb2_device`; photon detection and time-resolved readout for `spad_lidar`; transfers against real DDR1 memory for `ddr1_phy_controller`; and programmable spiking-network operation for `spiking_neural_processor`. Array sizes, rates, accuracy, retention, optical range, and environmental limits must be frozen at G1 and may not be replaced by a vague "test chip works" claim.

“Fully integrated” means that the protocol engine, baseband/PCS, data converters or SerDes, clock generation, and active RF or line interface required for the declared mode are on die. Conventional external crystals or references, antenna matching and filtering, Ethernet isolation magnetics, connectors, and legally required duplexing components remain outside the die. Gate G1 must state explicitly whether the cellular PA and antenna switch in `wifi_nbiot_radio` are inside the integration boundary; changing that boundary later is a specification change, not a clarification.

Every project may also expose external-PHY, external-converter, external-LO, and raw parallel test boundaries. These are bring-up and diagnostic paths and do not satisfy the fully integrated claim, but they keep the digital subsystem independently verifiable and distinguish a protocol failure from an analog failure.

### Reusable physical macros

Build shared blocks under `ip/`, harden qualified process-specific implementations under `ip/macros/`, release their exact GDS with immutable manifests, and instantiate them without project-local layout forks:

1. **`wireline_serdes`:** the portfolio's first reusable frontier high-speed dependency. PCIe Gen1 at 2.5 GT/s is the demanding design anchor; 1000BASE-X at 1.25 GBd is the lower-rate silicon-confidence and integration milestone. The family provides static-CML TX/RX, serializer/deserializer, PLL/dividers, phase interpolation, phase detection and CDR, elastic buffering, programmable termination/swing/emphasis/threshold, PRBS, eye scan, loopbacks, and shared 8b/10b primitives. `ethernet_mac_phy` and `pcie_gen1_endpoint` add their protocol-specific PCS, training, receiver-detect, electrical-idle, and state controls around it.
2. **`radio_frontend` + `radio_baseband`:** the second reusable frontier track, shared by `wifi_nbiot_radio` and `rtl_sdr_tuner`. WiFi at 2.4 GHz anchors maximum RF frequency and the complete TX/PA path; the tuner anchors wideband 50 MHz–1.7 GHz receive coverage. Reuse ADC/DAC, voltage/current references, AGC, DC/I-Q/LO-leakage correction, sample capture/playback, NCOs, multirate filtering, calibration, and only RF cells whose characterized frequency and impedance envelopes genuinely overlap. Keep frequency-specific LNAs, mixers, VCO bands, PAs, matching networks, and antenna interfaces as separate macros rather than forcing a nominally universal RF front end.

These names describe integration assemblies, not indivisible release units. Release the smallest independently verifiable physical unit—for example `serdes_tx`, `serdes_rx`, `cdr`, `pll`, `phase_interpolator`, `termination`, `adc`, `dac`, `reference`, `lna`, and `mixer`—plus a separately versioned assembly manifest. This limits the blast radius of a change and avoids forcing unrelated consumers to accept an entire floorplanned tile. USB 2.0 and DDR1 may reuse PLL, phase-control, bias/reference, calibration, pad-analysis, and test techniques, but their current-mode half-duplex and source-synchronous electrical interfaces remain separate physical macros; superficial similarity is not physical-IP compatibility.

Close the shared wireline work in this order, while all consumer projects continue in parallel:

1. Externally clocked static TX/RX, PRBS, and loopback at 1.25 GBd.
2. Extracted 1000BASE-X lane and Ethernet operation at 1.25 GBd.
3. Externally clocked static TX/RX and eye margin at 2.5 GT/s.
4. Autonomous and reference-assisted CDR, calibration, and recovery at 2.5 GT/s.
5. PCIe electrical-idle/receiver-detect behavior, link training, enumeration, and data transfer.

This order does not reduce the PCIe v1 requirement. It creates useful intermediate evidence and ensures that a marginal 2.5 GT/s CDR cannot erase the value of an otherwise working 1.25 GBd SerDes. The shared macro must support both rates without making the Ethernet mode depend on the PCIe protocol engine, receiver detection, or autonomous 2.5 GT/s clock recovery.

Sharing reduces the amount of unreviewed custom circuitry; it also creates common-mode risk. Preserve at least two independently selectable implementations of each existential analog function. Silicon-proven open GF180MCU blocks with working fabricated silicon (Caravel/ChipFoundry-era I/O cells, ring oscillators, SRAM macros, PLLs) are the default choice for a redundant variant; the new custom implementation is the experiment, not the baseline. Candidates include alternate CDR or reference-assisted sampling paths, two serializer drive/load variants, independently designed VCO cores or a diagnostic ring oscillator, alternate LNA/mixer sizing, segmented PA cells, and a reduced-performance diagnostic converter. A backup must not depend on the power, clock, state machine, or signal path of the block it is intended to diagnose. In addition, every product die instantiates a silicon-proven ring oscillator and uses proven pad-ring cells as its default I/O, giving each die a known-good is-the-die-alive reference that shares nothing with the new circuits and directly supports ladder levels L1–L2.

### Calibration is part of the architecture

Convert device uncertainty into a digitally searchable configuration space. At minimum provide safe, independently controllable trims for:

- CML current, swing, common-mode, source/load termination, deemphasis, and edge rate.
- Sampler gain, offset, bandwidth, decision threshold, and clock phase.
- PLL charge-pump current, loop settings, divider path, switched VCO band, and coarse/fine capacitance.
- LNA and mixer bias, RF/baseband gain, baseband bandwidth, and I/Q balance.
- ADC/DAC reference, offset, gain, sampling phase, comparator or interstage correction, and reconstruction filtering.
- PA cell segmentation, bias, power ramp, matching-bank selection, and power-detector calibration.
- On-chip RC time constants, impedance standards, and delay-line settings.

Each trim must have a characterized encoding, a range covering modeled PVT plus a separately budgeted model-error allowance, safe reset defaults, and direct JTAG/SPI override. Automatic calibration may select a setting, but it may never be the only way to reach it. Calibration outputs remain volatile and firmware-controlled until silicon data justifies programming OTP or eFuse.

A small always-available calibration controller performs PLL band search, receiver-offset nulling, SerDes eye/phase scans, termination calibration, I/Q and LO-leakage correction, converter loopback calibration, PA power sweeps, and selection among redundant lanes or blocks. Its ROM boot path, clock, reset, and debug interface must not depend on the RF PLL, SerDes CDR, external memory, or the main application CPU.

### Clock, reset, and power escape paths

Every existential clock domain supports normal internal generation, a reference-derived diagnostic mode, and direct external injection at an appropriate divided or high-speed node. Radio blocks accept external I/Q LO and sample-clock inputs in addition to internal synthesis. VCOs use coarse switched bands before fine-loop acquisition, expose divided outputs and lock metrics, and use integer-N operation for the first supported channels wherever the frequency plan permits.

`pcie_gen1_endpoint` is optimized first for a common-reference, short, low-loss channel while retaining the CDR and elastic buffering required by the selected PCIe specification. `ethernet_mac_phy` and `pcie_gen1_endpoint` both support TX-only, RX-only, raw symbol, compliance-pattern, PRBS, near-end loopback, and external loopback modes.

Give PLL, SerDes, converters, RF, PA, digital core, and calibration logic independently controllable supplies or isolation switches where the process permits. Power-up begins with only the conservative control island. No first observation may require every supply, PLL, SRAM, processor, and PHY to succeed simultaneously.

### Die, package, board, and external-component co-design

The package and evaluation hardware are schematic inputs, not post-layout accessories. Select the package, bond-wire plan, external passives, reference source, connectors, antenna network, Ethernet magnetics, and representative channels before analog sizing freezes. Obtain or extract frequency-dependent package and board models and co-simulate the extracted die, ESD network, pad, package, board, connector, matching network, and channel.

Use provider-qualified high-speed/RF pads and ESD structures whenever available. Any custom alternative requires written Gate G0 acceptance, modeled capacitance and resistance, latch-up review, and a test plan that does not imply an unmeasured ESD rating. Place dedicated supply and ground bonds around SerDes, PLL, ADC/DAC, RF, and PA regions; provide local decoupling and substrate/well isolation based on extracted coupling rather than schematic intent.

Keep RF matching and other model-sensitive networks externally adjustable on v1. Include adjacent open, short, thru, known-load, transmission-line, pad-chain, and package/board de-embedding structures. Do not multiplex multiple GHz experiments behind one pad when the multiplexer parasitic would invalidate the measurement.

### `process_characterization` correlation contract

Every product-critical device or passive recipe has both a measurable `process_characterization` structure and a compact local product-die replica. Match device geometry, orientation, guard rings, neighborhood, metal density, and routing context closely enough that the correlation has a defensible physical meaning. Each replica must map to a product trim, model parameter, or explicit design decision; ornamental process monitors are not sufficient.

`process_characterization` covers the exact geometries used for MOS speed/current/capacitance, matching, resistors, capacitors, varactors, inductors, transmission lines, pad capacitance, CML swing/delay, sampler offset/metastability, ring and LC oscillator tuning, LNA/mixer gain and noise, data-converter behavior, and permitted ESD/pad experiments. Because all v1 dies share one shuttle, these results cannot change same-shuttle circuits. They choose safe initial trim regions, correlate local monitors and matched variants, interpret failures, update models, and identify evidence-led respin changes. Product designs must carry pre-silicon model uncertainty without assuming characterization results will rescue marginal nominal performance.

### Pre-silicon proof on real peers

Before analog top-level freeze, run the exact digital RTL, firmware, register map, calibration algorithms, and protocol state machines in FPGA hardware against multiple real peers:

- `ethernet_mac_phy` against commercial PHYs, switches, packet generators, and adverse traffic patterns.
- `pcie_gen1_endpoint` against multiple root complexes plus a protocol analyzer, with malformed traffic, reset, retry, and recovery testing.
- `wifi_nbiot_radio.wifi_dsss` against an SDR RF front end and controlled 802.11b peers, including recorded-channel replay.
- `wifi_nbiot_radio.nbiot` against an SDR or commercial network emulator for acquisition, attach, transfer, loss, and reacquisition.

Maintain bit-exact executable PHY models and differential-test RTL against them. Use formal proofs for queues, framing, resets, credit/accounting rules, synchronizers, and critical protocol state transitions. Long randomized FPGA runs, injected clock/supply/link failures, malformed packets, saturation, and interrupted calibration are release gates, not optional demonstrations.

Full-protocol transistor simulation is neither tractable nor necessary. Use a checked hierarchy: transistor blocks generate parameter envelopes; behavioral twins are fitted to those envelopes; full-chip mixed-signal tests use the twins; adversarial intervals substitute extracted transistor netlists; and FPGA hardware-in-the-loop supplies realistic protocol duration. A contract test fails when any abstraction understates the circuit's delay, noise, distortion, saturation, startup, or failure behavior.

### First-silicon success ladder

The required claim remains the fully integrated target, but bring-up records the deepest achieved ladder level (`L1`–`L7`) rather than collapsing every shortfall into “dead”:

1. **L1** — safe power-up; control, scan, and monitor access.
2. **L2** — independent clocks, references, converters, TX, RX, RF, and line-interface activity.
3. **L3** — raw symbols or complex samples traverse internal and external loopbacks.
4. **L4** — protocol operation through an external PHY/RF/converter boundary.
5. **L5** — fully integrated link with a controlled peer at a fallback rate or constrained channel.
6. **L6** — fully integrated operation at the declared v1 target across the specified environment.
7. **L7** — interoperability and compliance evidence across the required peer and test matrix.

Levels L1–L5 are valuable diagnostic outcomes but do not satisfy a Level L6 fully integrated claim.

## The evidence framework: how "convincing" gets built in

A claim nobody can re-run is an anecdote. So:

1. **`claims.yaml` per project** — every technical claim (for example, a minimum extracted CML eye opening over the complete declared PVT, package, channel, jitter, and trim envelope) maps to a make target, a spec limit, and a generated artifact. A single favorable or nominal corner is never evidence for a communications claim. `make claims` re-verifies all claims and emits a pass/fail dashboard into `evidence/`.
2. **CACE datasheets** for every applicable shared block under `ip/blocks/` — corners + Monte Carlo, rendered as datasheet-style tables. These become the public face of the repo.
3. **Provenance stamped on every artifact**: container digest, commit hash, PDK version, RNG seeds, and host architecture — embedded in the output JSON. A stranger with the repo and Docker reproduces any number in the datasheets with one command. That reproducibility *is* the proof standard, pre-silicon.
4. **Behavioral-twin contract tests**: for each analog block, an automated check that the SPICE result lies inside its Python twin's declared parameter envelope. When a twin drifts from its circuit, the local regression fails — this is what keeps the system-level sims (Verilator/GNU Radio/Brian2) honest.
5. **Local verification instead of GitHub Actions:** `make check-fast` runs formatting, schema checks, unit tests, the public-repo hygiene check, and the smoke loop; `make check-digital` runs RTL/formal regressions; `make check-analog` runs bounded analog regressions; and `make claims` runs the expensive evidence suite. Record compact results under `evidence/runs/` with provenance and a machine-readable summary; keep bulky raw output in ignored scratch storage or attach a curated bundle to a GitHub Release. A local pre-push hook may call `make check-fast`, but the Make targets—not the hook—remain authoritative. GitHub hosts code, issues, reviews, and releases only; no workflow files or Actions-specific assumptions are required.
6. **One design-assurance report:** `make design-assurance` composes the golden-path check, test-access/trace/supervisor inventory, `make pin-audit`, per-die FMEA, and cross-shuttle common-cause report. It links to existing evidence rather than copying it into a new hierarchy.

### Lessons imported from fabricated GF180 references

Keep a revision-pinned `references/fabricated_gf180.yaml` ledger of public designs that have returned working GF180 silicon. For each reference record repository commit, process/PDK and provider-flow revisions, fabricated run, functions actually measured, known failures or tuning needs, reusable artifacts, and the SVALBARD requirement it supports. “Fabricated” is not a blanket endorsement: evidence transfers only to the same cell, view, voltage, process option, flow context, and operating envelope.

The first ledger entry is [Cloneless1](https://github.com/ThorbenMoos/Cloneless1) at commit `fdc35ddf99bf0d936911396b2e95981a30878882`. It is a useful working-silicon reference because it used GF180MCU, wafer.space Run 1, LibreLane, a version-pinned provider PDK and precheck, hardened custom macros, foundry I/O cells, and an end-to-end reproducible public flow. Adopt these practices:

| Observed practice | SVALBARD rule |
|---|---|
| One top-level command runs source simulation, language conversion, converted-RTL simulation, pad-model simulation, macro hardening, top-level implementation, post-layout netlist simulation, and provider precheck | `make reproduce SUBMISSION=<id>` is a thin dependency graph over separately runnable stages. A clean invocation builds the exact release candidate and evidence; no manual GUI edit or undocumented intermediate file is allowed |
| Tool environment, PDK, and provider precheck are revision-pinned | Preserve the existing Docker/image-digest strategy, but verify the PDK commit and provider-precheck commit at runtime. Record both in the run and submission manifests; a tag alone is insufficient if it can move |
| Custom carry-chain and ring-oscillator structures are hardened as macros before top-level assembly | Release every non-synthesizable or placement-sensitive digital structure as an immutable GF180 macro. Its bundle includes GDS/OASIS, LEF, black-box and powered simulation models, logical and physical netlists, SPEF by extraction corner, Liberty by PVT/extraction corner where timing applies, DRC/LVS/antenna reports, pin/power contract, and characterization test |
| Four oscillator lengths and many repeated, explicitly placed instances explore physical variation; raw outputs remain externally readable | Use generated placement tables for controlled geometry arrays and local replicas. Record intended length/topology, coordinates, orientation, neighborhood, supply, and readout channel in `variant.yaml`; verify the final GDS against the table. Keep raw measurements reachable instead of exposing only corrected or post-processed results |
| The complete chip instantiates real pad-cell models before layout, and post-layout functionality is simulated with standard-cell, I/O, and macro models | Require the same logical transaction or golden vector to pass at behavioral/RTL, converted or generated RTL, synthesized netlist, pad-integrated netlist, and final post-layout netlist stages. Compare stage outputs automatically so conversion, wrapper, polarity, power-pin, or macro-black-box mistakes cannot hide behind a different testbench |
| The pad ring deliberately intersperses numerous supply/ground pads; the physical design has an explicit core ring, PDN straps, macro grids, and halos | Make pad-ring topology and PDN parameters generated review artifacts. Verify power-pad count and alternation, current per pad/bond, return paths, macro PDN connectivity, ring/strap width and slotting, IR drop, and macro halos. Copy neither Cloneless1's count nor its 5 V choices; derive them for each die's domains and package |
| The design uses a conservative 4 MHz external clock and exposes experimental raw data | Every die retains a deliberately slow control/diagnostic configuration independent of its performance clocking. Statistical or calibration-sensitive functions expose raw samples, counters, error flags, and configuration state so a marginal v1 result can be tuned and understood |
| The public project released PCB, FPGA-controller, verification, and software collateral alongside the chip | Treat board sources, FPGA bridge/peer bitstreams, host software, test vectors, instrument scripts, and raw-data schemas as release-blocking Gate G5 artifacts. Run a dry bring-up against emulation or FPGA before submission and archive the exact versions with the die manifest |
| Actual silicon showed that most PUF configurations were promising while most TRNG configurations needed more tuning | For any entropy-, oscillator-, delay-, memory-, sensor-, or analog-variation-dependent block, tape a controlled parameter matrix rather than a single nominal point, retain manual bias/timing/threshold control, and preserve raw output. A corrected output alone cannot diagnose whether physics, sampling, or correction logic failed |

Cloneless1 also provides a warning more important than its particular configuration. Its maintainers found that an in-flow KLayout DRC step made minor GDS changes relative to the submitted layout and introduced an antenna error; they changed the flow to run the wafer.space precheck separately and used KLayout Diff/XOR against the submitted GDS. Therefore SVALBARD distinguishes the immutable **release candidate** from analysis copies. Once `make candidate SUBMISSION=<id>` emits a candidate, every subsequent checker mounts it read-only or first copies it to scratch, records input and output checksums, and is tested for mutation. `make verify-candidate SUBMISSION=<id>` runs the provider's exact pinned precheck plus independent checks, then proves by byte hash and layout-aware XOR that the candidate is unchanged and equal to the file named in the signed submission manifest. The upload tool accepts only that content-addressed path. Any geometry repair, fill insertion, label edit, stream-out, or waiver-driven change creates a new candidate ID and invalidates all downstream approvals.

Import the lessons, not incidental implementation choices. Do not copy Cloneless1's 5 V library selection, 4 MHz product limit, density/fill exceptions, Magic flatten lists, disabled in-flow checks, floorplan coordinates, Nix environment, shell `sed` netlist rewriting, or `RUN*` globs. Those are design- and release-specific. SVALBARD uses validated structural transforms, explicit immutable run IDs, the provider's current accepted check order, and recorded waivers; a check disabled in one phase remains mandatory in the appropriate non-mutating verification phase.

## Required engineering gates

A green DRC/LVS result is necessary but not sufficient. Gate G0 above qualifies the process and provider before the baseline is locked; each project then advances only when the applicable gate below has a versioned specification, a reproducible Make target, machine-readable results, and linked claims. `waived` is a recorded result with an owner and rationale; it never means a check silently disappeared.

### Gate G1: specification and budgets

After Gate G0, and before architecture or schematic work, freeze a reviewable `spec/spec.yaml` validated by JSON Schema. It must define:

- Functional behavior and external interfaces, including protocol/standards revision and legal source of each limit.
- Performance budgets with units, tolerance, measurement method, and operating mode.
- Power by supply and mode, area/die/pad budgets, clock and reset plan, and test access.
- GF180 process option and metal stack, allowed device/voltage families, supply range, temperature range, and all required PVT corners.
- Allocation from top-level requirements to blocks, with margin and an owner for every unallocated or violated budget.
- For communications projects, the exact v1 mode, standards clauses, interoperability peers, compliance tests, integration boundary, permitted external components, package/channel envelope, calibration assumptions, fallback modes, and success-ladder level required for the fully integrated claim.
- Separate modeled process variation, mismatch, package/passive tolerance, protocol/channel stress, and model-uncertainty budgets. Do not hide an unknown model-validity range inside ordinary Monte Carlo variation.
- A reviewed `uncertainties.yaml`, cross-die diversity matrix, provisional control-to-observable identifiability matrix, per-trim contracts and budgets, named safe configurations, and the hypothesis/measurement contract for every silicon variant.
- For every processor-facing die, its `svalbard_host_v1` pin budget, pad voltage/drive profile, reset behavior, minimum and target SPI rates, UART decision, interrupt/polling behavior, register ABI version, and the exact wafer.space RISC-V host configurations used for compatibility testing. Where `svalbard_stream_v1` applies, also freeze channel direction/width, payload format, sustained and burst bandwidth, fallback rates, backpressure behavior, FIFO depth, and maximum host-service latency.
- A complete golden-path declaration, test-access/trace/reset-supervisor budget, canonical `interfaces.yaml`, and FMEA fields sufficient for `make design-assurance` to emit a green or explicitly red result; missing assurance data is not a waiver.

Use Python, JSON Schema, and Pint for schema/unit validation and generated specification tables. `make spec` is blocking and emits a normalized JSON snapshot used by every downstream comparison; handwritten values duplicated in testbenches are not authoritative.

### Gate G2: RTL and digital implementation

Every digital block and the assembled digital subsystem must pass:

- RTL formatting, parsing, lint, and synthesizability with Verible/Slang, Verilator, and Yosys; warnings are either errors or explicit waivers.
- A machine-readable clock/reset/domain inventory. CDC and RDC checks combine structural synchronizer/reset rules, assertions, formal proofs for crossings, and manual review. The repository must not call this signoff-grade CDC/RDC unless a qualified signoff tool is later added.
- SymbiYosys proofs for block invariants, interface properties, FIFO/counter safety, reset behavior, and selected liveness properties, using pinned Boolector/Z3 engines.
- Cocotb/pytest and Verilator regression with deterministic seeds, coverage goals, negative tests, and behavioral-twin comparisons where applicable.
- Generated-register and transport equivalence tests across APB3, Wishbone B4, SPI, and UART wrappers; protocol fault tests for truncated/paused transactions, inactive-chip-select MISO behavior, reset during access, illegal addresses, FIFO overflow, polling-only operation, and driver compatibility with KianV- and TinyQV-shaped host models.
- Stream-link tests at 1/10/25/50 MHz for training patterns, arbitrary backpressure, clock start/stop, packet boundaries, CRC and sequence errors, FIFO overflow/underflow, independent reset, asynchronous host clocks, and exact application-rate traffic. Gate-level and post-layout timing include forwarded-clock output and input-delay constraints.
- FPGA hardware-in-the-loop equivalence for each communications project using the tapeout RTL, firmware, register map, and calibration algorithms against the real-peer matrix declared at Gate G1. Preserve traces and seeds for malformed traffic, loss of clock/link, reset, retry, saturation, and recovery cases.
- Synthesis and equivalence checks, constrained STA across required modes/corners using OpenSTA/OpenROAD, including clock definitions, generated clocks, false/multicycle paths, unconstrained-path checks, and setup/hold reports.
- Clock/reset sanity after implementation: clock-tree checks, reset release sequencing, recovery/removal timing, and no unintended combinational clocks or asynchronous reset logic.
- DFT plan and scan insertion using the pinned OpenROAD DFT implementation, followed by scan-chain connectivity, shift/capture simulation, test-mode STA, and a documented fault-coverage limitation. Open-source scan insertion alone is not a claim of production ATPG coverage.
- Shared test-access, event-trace, and reset/clock-supervisor regressions: JTAG/SPI instruction and boundary behavior, pad-safe EXTEST states, trace trigger/wrap/readout and soft-reset retention, every reset cause, missing/stopped clocks, external-clock takeover, and glitch-free or reset-guarded clock switching.
- Stage-equivalent simulation: the same generated vectors and scoreboard pass behavioral/RTL, any language-converted or generated RTL, synthesized netlist, real-pad-model top level, and final post-layout netlist. Zero-delay gate-level regression is mandatory; SDF-annotated simulation is required only after the selected open-source simulator has been qualified against the GF180 standard-cell and I/O models. STA remains the timing authority.

`make check-rtl` covers lint, unit simulation, formal, and CDC/RDC policies. `make check-digital` additionally covers synthesis, equivalence, STA, DFT, and gate-level regression.

### Gate G3: analog and mixed-signal verification

Every analog block, shared cell, and analog top level must pass a CACE-driven verification matrix derived from `spec.yaml`:

- PVT across every required process corner, supply extreme, temperature extreme, and relevant load/mode combination.
- Separate mismatch Monte Carlo and process Monte Carlo campaigns with recorded seeds, sample-count justification, confidence/yield statistics, and convergence/failure accounting. Do not merge solver failures into passing statistics.
- Noise appropriate to the circuit: operating-point/device contribution, integrated input/output noise, transient noise or phase noise where required, and noise-to-system-budget propagation.
- Stability and transient behavior: loop gain/phase margin where meaningful, startup from adverse initial conditions, settling/recovery, overload, mode switching, and power sequencing.
- Solver robustness: tolerances, timestep sensitivity, alternate initial conditions, and cross-simulator correlation for claims that depend on custom compact models.
- Supply sensitivity: DC line regulation or gain, PSRR versus frequency, supply noise injection, ground movement, and interaction between power domains.
- Pre-layout versus extracted simulation with named extraction corner, coupling policy, and an explicit delta budget. Critical claims require post-layout PEX results; schematic-only evidence is labeled as such.
- A model-validity matrix for every RF/high-speed device, passive, pad, ESD element, and package model, including characterized frequency, geometry, bias, temperature, statistical coverage, source, and known limitation. Extrapolation outside that matrix is a named risk, not a passing corner.
- Calibration verification proving range, resolution, monotonicity or characterized code map, convergence, safe behavior at every code, manual override, interrupted-calibration recovery, and margin remaining after modeled PVT plus the separate model-error allowance.
- Robust bounded sweeps and sensitivity analysis for parameters without defensible distributions, including adversarial correlated combinations, variant discrimination, identifiability fault injection, and explicit claims that remain unprovable until silicon.
- Block-level statistical yield propagation into a system yield estimate. Identify dominant physical failure variables and demonstrate that trim or architectural redundancy actually covers them; reporting only the number of Monte Carlo passes is insufficient.
- For clocks, converters, SerDes, RF, and PA blocks: external-injection modes, redundant paths, BIST, raw observation, and every specified loopback must be simulated at the transistor or checked behavioral level appropriate to the claim.

Use xschem/ngspice, CACE, OpenVAF/OSDI, Xyce/ADMS where separately qualified, NumPy/SciPy/pandas for analysis, and pytest for result assertions. `make check-analog` runs a bounded regression; `make claims` runs the full PVT/Monte Carlo/noise/extracted evidence matrix.

### Gate G4: full-chip integration and physical signoff

Before a tapeout candidate is tagged, the assembled chip must cover:

- A reviewed padframe and bond/package plan: signal/power/ground pads, ESD structures, pad current limits, simultaneous-switching assumptions, test access, and no unsupported circuit-under-pad use.
- A clean `make pin-audit` against final RTL, filled layout, package/bond netlist, PCB netlist, connector tables, and generated firmware names; JTAG/SPI boundary access, trace readout, external reset/clock, and safe supervisor controls must remain reachable in every supported bond option.
- For processor-facing dies, post-layout and board-level validation of the common host connector, exact I/O voltages and thresholds, power-off/back-power behavior, SPI timing and MISO tri-state contention, interrupt/reset pulls, and pin-compatible adapter-board mapping. Stream-equipped dies additionally require extracted pad/package/board timing, simultaneous-switching and return-path review, source-termination options, crosstalk checks, and hardware loopback at every required rate.
- For communications projects, a frozen package/board/external-component design and frequency-dependent co-simulation of extracted die, ESD, pad, package, bond wires or bumps, board, connector, matching network, and worst declared channel. Package or board placeholders are not sufficient for analog-top freeze.
- ESD and latch-up review using the GF180 rules and characterized I/O structures; guard rings, taps, isolation, injection paths, and domain-crossing behavior are explicit. Geometric DRC is not evidence of an ESD rating.
- Level shifters and isolation for every voltage-domain crossing; power-up/down states and back-powering paths are simulated.
- Power intent: domain ownership, power/ground connectivity, decoupling budget and placement, power sequencing, reset behavior, and always-on/test supplies. Keep a machine-readable power-intent table even if a complete open UPF flow is unavailable.
- Antenna, connectivity, off-grid, density, and dummy-fill checks using the pinned GF180 KLayout decks. Re-run extraction and timing/analog checks after fill when fill changes parasitics materially.
- EM/IR analysis: OpenROAD PDNSim for characterized digital rails and extracted resistance/current checks for analog, pad, and high-current nets. FastHenry/openEMS may support critical interconnect studies, but they do not substitute for missing foundry reliability data. Uncovered analog EM/IR cases require conservative hand calculations and a recorded limitation.
- ERC for shorts between supplies, missing well/substrate ties, floating gates/nets, illegal device voltages, bulk connections, and unpowered-domain paths. Implement available checks with KLayout/Netgen and project-specific scripts; record gaps because the open GF180 flow does not provide a complete commercial-grade ERC solution.
- Hierarchical and flattened top-level DRC, independent-deck comparison where available, LVS, PEX, extracted analog re-simulation, post-layout STA, and final GDS/OASIS hierarchy/property sanity checks.
- Reliability and manufacturability review covering electromigration, antenna/PID, latch-up, ESD, stress/slotting, redundant vias, seal-ring/edge constraints, and foundry or shuttle-specific density/fill requirements.
- Verification that redundant variants, external clock/LO/converter access, raw test paths, calibration controller, monitor routing, and every isolation or power/reset control promised by the die's integration contract remain reachable in the final filled layout and package bond plan.
- Post-tapeout fixability provisions, frozen before layout freeze: spare logic cells or gate-array fillers distributed through the digital blocks for metal-only ECOs, spare pads and alternate bond-out options, uncommitted top-metal routing resources near high-risk analog regions, and a reviewed inventory of which anticipated failure classes are recoverable with a metal-only respin (`A1`) versus an all-layer respin (`B0`).

`make check-integration` runs fast connectivity, power-intent, padframe, ERC, and hierarchical physical checks. `make signoff SUBMISSION=<id>` starts from a clean worktree and pinned inputs, runs the complete top-level suite, and emits a signed manifest of PDK/tool/image/precheck digests, waivers, reports, final layout checksum, layout-aware XOR reference, package/bond plan, and reproduction command. `make candidate SUBMISSION=<id>` is the only target allowed to create the release layout; `make verify-candidate SUBMISSION=<id>` and the upload path are non-mutating consumers of that exact content-addressed file and fail on any byte or geometric delta. Because the open GF180MCU PDK is an experimental preview, this result must be described as **open-flow signoff** until the selected shuttle/foundry accepts the exact decks and PDK revision.

### Gate G5: tapeout and post-silicon readiness

Before submission, re-confirm that the Gate G0 provider decision, accepted PDK/decks, die/reticle limits, required cells and labels, submission format, waiver policy, packaging constraints, and final checklist have not changed. Resolve every delta before generating the final candidate. Exotic structures must match their recorded provider disposition exactly; TCAD plus DRC does not establish manufacturability.

The final candidate must also pass `make design-assurance` from clean, immutable inputs. The signed result records each project's golden path, test-access/trace/supervisor reachability, final pin audit, unresolved FMEA entries, and cross-shuttle common causes. A red item remains visible in the submission evidence and requires an owner-approved disposition; submitting all ten dies does not permit an assurance check to disappear.

Rehearse each submission and the shuttle assembly itself. Well before the real deadline, run complete dress-rehearsal packages—final decks, labels, fill, seal rings, formats, checksums, slot mapping, and paperwork—through the provider's actual intake process using dummy or early candidate layouts, and record every finding under the shuttle directory. The handoff must be a tested pipeline before the deadline, not a first attempt at it; Gate G5 for a real candidate does not open until its rehearsal package has passed intake.

Each submission also needs a versioned bring-up plan: probe/PCB and socket or bond plan, firmware/bitstreams, instrument requirements, safe power-up limits, named safe configurations, variant-selection map, calibration structures, automated bounded-search scripts, raw-data schema, device/wafer identifiers, and a path for measured results to update `ip/models`, `ip/twins`, and public evidence. Bring-up follows the first-silicon success ladder in order, powers the conservative control island first, starts from external clocks/references and raw injection or loopbacks where applicable, records every trim and variant selection, and attempts autonomous fully integrated operation only after electrical limits and thermal behavior are established.

## Execution order and parallel work

The gates describe the lifecycle of each project; they are not the portfolio schedule. Execute the portfolio in this dependency order:

1. Define the overall success levels: environment demonstration, reproducible pre-silicon evidence, accepted tapeout, and measured silicon are separate outcomes.
2. Complete Gate G0 for the intended shared shuttle. Resolve the process/deck lock, RF and high-speed model validity, qualified or licensed IP, pad/ESD options, packages, standards sources, compliance access, die/reticle budget, and exotic-device eligibility before architecture freezes. If RF/noise/passive or pad data is inadequate, escalate model acquisition, IP licensing, provider engineering support, or a process decision; do not substitute more nominal simulation.
3. Complete Phase 0 machine/storage protection, repository skeleton, process/tool locks, and the inverter smoke loop.
4. Establish the registry, evidence schemas, run manifests, ownership report, program risk register, variant schema, and provisional ten-slot manifest. Complete Gate G1 for every v1 project and die role. Freeze exact standards profiles, integration boundaries, external-component assumptions, interoperability peers, variant hypotheses, success claims, and per-die closure deadlines.
5. Start bounded domain workstreams after the smoke loop:
   - **Programmable-memory track:** build the FABulous → nextpnr → bitstream → Verilator equivalence vertical slice, qualify gain-cell eDRAM as optional block memory, and prove that the FPGA configures and runs without the eDRAM path.
   - **Process-characterization/model track:** qualify the minimum DEVSIM/Charon, compact-model, ngspice, extraction, RF/noise/passive, package, and calibration path; define the product-to-characterization and cross-die variant matrix before any v1 layout freezes.
   - **Communications digital track:** implement bit-exact reference models, protocol RTL, firmware, calibration software, and full FPGA hardware-in-the-loop rigs for `ethernet_mac_phy`, `pcie_gen1_endpoint`, and `wifi_nbiot_radio`. A project does not enter analog-top integration until it works for long randomized runs against its declared real peers through external PHY/converter/RF equipment.
   - **Shared physical-block track:** prioritize the PCIe-anchored `wireline_serdes` family as the first reusable high-speed dependency, closing its externally clocked 1.25 GBd and Ethernet milestones before autonomous 2.5 GT/s PCIe operation. In parallel, build the WiFi-anchored `radio_frontend` and shared `radio_baseband` for reuse by the tuner; also develop the independent 10/100 line PHY, qualified pads/ESD, references, clocking, converters, calibration controller, diverse fallback variants, raw access, and dedicated high-risk macro-matrix die through Gate G3. Harden and release each independently verifiable macro rather than one monolith.
   - **Sensor/optical track:** develop the CMOS pixel/readout chain and SPAD/quench/TDC chain with dark references, electrical injection, guard-ring variants, and independently observable array slices.
   - **Analog-neural-compute track:** develop floating-gate program/verify/compute arrays and the spiking network as a coupled accelerator while preserving direct array measurement, digital event/weight injection, neuron/synapse observation, endurance experiments, and safe high-voltage isolation where permitted.
   - **Wired-I/O track:** close USB 2.0 and DDR1 RTL/firmware in FPGA hardware, define the useful USB-to-DDR bridge demonstration, and qualify direct PHY, pad, DLL/clock, and recovery modes.
6. Assign one directly responsible integrator and one independent reviewer to each of the ten dies. Shared-block owners do not replace die-level ownership. Track review load and physical-design capacity as closure constraints.
7. Freeze the package, board, channels, matching/filter networks, clock sources, magnetics, and instrument fixtures for every product and focused die while the circuits are still being sized. Measured or conservatively bounded frequency-dependent models become inputs to every extracted claim.
8. Freeze the cross-die diversity matrix before layout. For every existential failure class, show which on-die fallback and which independently bonded die can diagnose or survive it. Flag common references, pads, ESD, supplies, clocks, firmware, and extraction assumptions that could defeat several nominal variants at once.
9. Harden each macro GDS only after schematic and extracted statistical yield, calibration range, model-validity, and independent-review gates pass. Consumers pin immutable releases; a local ECO requires requalification and a new macro release. Same-shuttle characterization is not treated as prior qualification.
10. Integrate every committed die according to its declared integration class. Re-run per-project and SoC-level mixed-signal contracts, post-layout digital checks, die-package-board co-simulation, supply/substrate-noise analysis, shared-service failure injection, test-path reachability, and FPGA equivalence against each final register map and immutable boot image.
11. Run a formal candidate review for every die and a separate common-mode review across all ten. Resolve failed gates by fixing the design or making a pre-freeze, recorded scope reduction that preserves its primary purpose; do not hide a failure with a waiver, and do not let one die weaken another die's checks.
12. Rehearse all ten provider submissions early, then rehearse the complete `shuttle.sh1_gf180_v1` manifest: exact layouts, labels, fill, seal rings, checksums, paperwork, and slot mapping. Track provider findings per submission and at shuttle level.
13. Before the shuttle deadline, fabricate and validate all boards and fixtures, rehearse safe power-up on emulators or packaged surrogates, freeze instrument automation, test firmware recovery paths, and validate raw-data ingestion with synthetic datasets.
14. Submit all ten committed and closed design packages under `shuttles/sh1_gf180_v1/`. Each retains an independent checksum, evidence state, package plan, claims, and bring-up plan even if the provider presents them as one order.
15. During fabrication, continue only work that cannot invalidate frozen silicon: peer-matrix expansion, calibration search within frozen interfaces, fixture production, automation robustness, and bring-up rehearsals.
16. On silicon arrival, bring up characterization and directly bonded macro dies first where logistics permit, use their measurements to choose safe product trim searches, then bring up every product and focused die through L1–L7. Preserve raw sweeps and identities and compare matched variants and predicted versus measured distributions before choosing any respin.

The early dependency graph is therefore:

```text
success definition
       |
Gate G0: process + model/IP + pad/package + standards eligibility
       |
Phase 0: safe, locked, smoke-tested flow
       |
       +-------------------- standalone FPGA vertical slice
       |
       +---- project design/verification ---- real peers + test vectors --+
       |                                                                 |
       +---- characterization + macro matrices ---------------------------+
       |                                                                 |
       +---- ten independent die integrations + boards/packages ----------+
                                                                         |
                                             cross-die diversity review --+
                                                                         |
                                        ten independent G1–G5 closures
                                                                         |
                                             one v1 shuttle / ten designs
                                                                         |
                                      laddered bring-up + matched correlation
                                                                         |
                                                evidence-led respin decisions
```

## Riskiest-first project milestones

Every v1 project advances in parallel with `process_characterization`, and its first milestone attacks an existential risk before full-chip integration:

- `ethernet_mac_phy`: close the complete extracted 1000BASE-X path through the 1.25 GBd SerDes, selected pad/ESD, package, and worst declared channel; keep the 10/100 copper line interface as an independently testable fallback rather than the primary v1 claim.
- `pcie_gen1_endpoint`: enumerate and transfer data with the final endpoint RTL/firmware in FPGA, then demonstrate the extracted shared lane at 2.5 GT/s over the declared short common-clock channel with CDR/reference-assisted operation, receiver detection, calibration, and recovery.
- `wifi_nbiot_radio.wifi_dsss`: exchange 802.11b 1/2 Mbit/s packets using the final digital baseband against real peers, then close the extracted 2.4 GHz RF-to-bits chain including LO, converter, package, matching network, impairments, calibration range, and PA limits.
- `wifi_nbiot_radio.nbiot`: complete acquisition, attach, transfer, loss, and reacquisition in hardware-in-the-loop for the exact selected profile, then close the extracted single-band RF-to-bits and bits-to-RF chains including synthesizer acquisition, blockers, PA/ramp, package/filter network, and calibration.
- `process_characterization`: freeze the exact product correlation matrix, prove every structure is independently measurable, and validate that each result maps to a product trim, model update, or respin decision.
- `rtl_sdr_tuner`: wideband LNA noise figure and harmonic-rejection mixer phase accuracy under mismatch.
- `cmos_image_sensor`: 3T pixel dark-current/FPN Monte Carlo on the calibrated model.
- `gain_cell_edram`: retention Monte Carlo across leakage corners, with programmable refresh as the stated mitigation.
- `floating_gate_analog_nvm`: program/verify convergence in ngspice with the OpenVAF/OSDI model, optionally correlated against a separately built Xyce/ADMS plugin.
- `usb2_device`: high-speed driver against the legally sourced USB-IF limits; full-speed mode can proceed through the digital flow.
- `spad_lidar`: SPAD guard-ring breakdown study and Vernier-TDC mismatch Monte Carlo.
- `ddr1_phy_controller`: custom SSTL-2 pad against the legally sourced JEDEC limits and the 90-degree DLL phase generator.
- `spiking_neural_processor`: subthreshold-neuron Monte Carlo distributions feeding a Brian2 network that still computes.
- `standalone_fpga`: after the first vertical slice, fabric scaling, configuration integrity, timing closure, and test coverage.

Honest expectations: Phase 0 is a solid week even with IIC-OSIC-TOOLS (the Xyce/Charon builds are the pain); Charon may fight you on Trilinos for days, which is why it is optional until the minimum analog-model path requires it. The full v1 portfolio adds a much larger burden: standards interpretation, FPGA rigs, independent verification, custom analog and memory IP, optical structures, packages and boards, field-solver work, statistical campaigns, and interoperability equipment. Massive upfront engineering improves the v1 probability only if all thirteen projects and ten die integrations have named staff and independent review; a large project list without closure ownership does not.

This host has ample CPU and RAM, but only about 233 GiB of free disk at the time of planning; image layers, PDK copies, waveforms, extraction output, RF sweeps, and long FPGA traces make storage—not memory—the first likely bottleneck. One machine also means the Monte Carlo and extraction queue is shared, so Make-based job discipline and per-project cutoffs are throughput rather than bureaucracy.

The first physical deliverable is the single `sh1_gf180_v1` shuttle with ten submissions carrying all thirteen named projects. Four submissions combine compatible projects: floating-gate NVM + spiking compute, Gigabit Ethernet + PCIe, standalone FPGA + gain-cell eDRAM, and USB 2.0 + DDR1. The remaining submissions provide the main characterization die, RTL-SDR tuner, CMOS image sensor, WiFi + NB-IoT product, SPAD LiDAR, and a directly bonded high-risk macro matrix. On-die variants, directly bonded monitors, alternate bond-outs, shared-service tests, and appropriate per-block escape paths maximize the chance that v1 produces working systems and actionable measurements. Same-shuttle characterization improves safe bring-up, diagnosis, and a respin rather than changing already-fabricated v1 circuits.
