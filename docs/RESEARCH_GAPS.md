# Research gap audit and acceptance criteria

Checked 2026-10-03 against publisher or source pages. The comparative claims supplied with the project are hypotheses, not evidence that the software has already achieved them.

## Source corrections

| Item | Verified finding |
| --- | --- |
| Safety DT review | [Zio and Miqueles, *Reliability Engineering & System Safety* (2024)](https://www.sciencedirect.com/science/article/pii/S0951832024001157) is a review in volume 246, article 110040. It identifies twinning and interoperability challenges. It does not establish this project's forecasting accuracy. |
| Chemical industry review | [Mane et al., *Digital Twins and Applications* (2024)](https://ietresearch.onlinelibrary.wiley.com/doi/10.1049/dgt2.12019) was first published 11 December 2024. It discusses monitoring, failure prediction and simulation, so saying such work is absent from the literature is too broad. |
| AR review | [Moreira et al., *Applied Sciences* (2024)](https://www.mdpi.com/2076-3417/14/24/11607) is a review/conceptual framework. It discusses smartphones and tablets as alternatives to headsets; an absolute claim that it *requires* AR headsets is unsupported. |
| TEP benchmark | [Reinartz et al., *Computers & Chemical Engineering* (2021)](https://www.sciencedirect.com/science/article/pii/S0098135421000594) is a benchmark paper. The local files are [Rieth et al. Harvard Dataverse v1.0](https://doi.org/10.7910/DVN/6C3JR1), with 41 measured and 11 manipulated variables, plus run/sample/fault identifiers. The local release has fault numbers 0–20. |
| PHM synthetic data | The cited ResearchGate item is linked to [IEEE Access DOI 10.1109/ACCESS.2026.3678177](https://doi.org/10.1109/ACCESS.2026.3678177), not a mid-2024 publication. Its exact methods should be checked from the publisher full text before comparing performance. |
| AI-driven DT paper | “AI-Driven Digital Twin for Process Safety in Chemical Engineering” is an [MDPI special issue](https://www.mdpi.com/journal/ChemEngineering/special_issues/497QTU5TT4), not an identified July 2025 research article with autoencoder results. |
| Pipeline leak study | [Hamilton et al., ADIPEC 2025](https://pure.kfupm.edu.sa/en/publications/digital-twin-for-pipeline-leak-monitoring/) combines experimental pipeline data, simulation, ML operations, and leak visualization. It is a conference contribution; the supplied Journal of Hydroinformatics attribution is incorrect. |
| Human interaction | [Shahab et al., arXiv 2504.00286](https://arxiv.org/pdf/2504.00286) addresses human–machine collaboration in biopharma digital twins. Its main lesson is the need for operator oversight, not simply a gap to replace with automation. |
| Mamba citation | The supplied `Processes 14/18/2973` link did not resolve during this audit. Do not use its claimed GPU cost, model metrics, or publication date as verified evidence. |

The remaining supplied paper summaries need a separate full-text check before a formal literature review. Absence of a particular feature in one paper is not proof of novelty across all prior work.

## What is implemented now

| Capability | Evidence | Status |
| --- | --- | --- |
| Source provenance | Official AI4I and TEP downloads, hashes and local manifests | Implemented |
| Plant-like visualization | Animated React/Three.js view, clickable 2D route, three-asset inspector, bounded pressure chart and source-separated AI4I explorer | Prototype |
| Recorded process playback | `/api/v1/tep/dataset/frame` for any published partition/fault/run, synchronized playback and JSON snapshot export; fixed replay retained as legacy | Implemented locally |
| CPU fault detection | `ml/train_tep_detector.py`, held-out run evaluation and `docs/models/TEP_fault_detector.json`; per-fault recall, score-bin calibration evidence, and per-sample median-replacement sensitivity shown in the UI | Research benchmark only; explanations are non-causal |
| +20-minute reactor pressure | `ml/train_tep_pressure_forecast.py`, held-out run evaluation and `docs/models/TEP_pressure_20m.json` | Simulation regression only; no hazard label |
| TEP run-to-failure remaining time | Separate official archive, resumable/checksummed ingestion, grouped current-and-past model, API/UI/evaluation report | Estimates time to simulated endpoint only |
| Next equipment to reach shutdown | UI/API warning path is implemented but terminal-unit label is absent from the published CSV schema | Correctly abstains; no equipment is highlighted |
| Labelled equipment prognosis lab | 1,200 dynamic-surrogate run families, five units, ten degradation modes, censored controls, past-only grouped models and fail-closed UI highlighting | Implemented as synthetic research evidence only; does not validate official RTF or a physical plant |
| 20-minute forward failure probability | No valid event-time labels or calibrated forecast model | Not implemented |
| Leak/over-pressure prediction | No labeled leak outcomes, asset topology ground truth or validated operating limits | Not implemented |
| Industrial connection and control | No plant sensor interface, writeback, authentication, historian, or independent safety system | Not implemented |

## Gates for a defensible 20-minute forecast

1. Define a target event precisely: equipment, failure mode, start time, and what counts as a true alert. Obtain authorized time-stamped process data with validated sample cadence and event records.
2. Construct labels using only information observable **at prediction time**. Separate plant/run groups and calendar periods before fitting, and prevent any scenario identifier or future sample from entering features.
3. Evaluate lead-time recall and false alerts per operating hour across normal, fault, sensor-dropout and process-change cases. Report precision-recall curves, calibration, confidence intervals, and detection latency on an untouched test set.
4. Map the physical asset graph, units, sensor quality flags, and engineer-approved operating limits. Validate proposed cross-asset correlations against process engineering models and incident evidence.
5. For any operational pilot, add authenticated ingestion, timestamp and sequence checks, stale-data handling, audit logs, model rollback, latency/availability monitoring, access control and an independent safety review. Keep recommendations advisory until site engineers authorize use.

The published TEP fault is injected at a known simulation sample. That benchmark supports fault-detection research; it does not by itself establish that an event could be anticipated 20 minutes before onset. A 3-minute TEP sample interval is documented in [simulator measurement documentation](https://github.com/jkitchin/tennessee-eastman-profbraatz/blob/master/docs/api.md); replay speed is an application display setting.

## Detector evidence added in this audit

The current held-out card reports 99.68% precision but only 54.63% recall at its 0.5 threshold. Faults 3, 9, 15 and 19 each have less than 2% recall (800 evaluated fault-labeled samples per scenario). This is a serious coverage limitation, not an acceptable safety detector. Its Brier score is 0.179 and equal-width-bin expected calibration error is 15.4 percentage points on a fault-enriched TEP test set; these figures do **not** calibrate the score as a plant failure probability. The dashboard now exposes these results and a one-feature-at-a-time median-replacement sensitivity for each sample. Tree-score spread and feature sensitivity are exploratory diagnostics, not physical causes or uncertainty guarantees.

The two supplied attachments contain paper *summaries*, not complete article text. Therefore this audit can test the claims in those summaries against the project and verify selected bibliographic details, but it cannot claim a line-by-line review of each full paper or declare every research gap solved. Full texts, event-labeled plant data, validated topology and operating limits remain necessary for the corresponding gates above.
