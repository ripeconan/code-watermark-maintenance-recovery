# Code-Watermark Recovery under Maintenance

This repository accompanies the manuscript **Code-Watermark Recovery under Maintenance: Search, Calibration, and Replay**. It contains the study's analysis and recovery code, source-redacted score records, frozen numerical summaries, sampling metadata, and manuscript table inputs.

## Verify

Use Python 3.11 and install `requirements-analysis.txt`. Run `python -X utf8 verify_public.py` for file integrity and headline checks. Run `python -X utf8 verify_public.py --full` to recompute 11 numerical summaries and the finite-pool resampling arrays in an isolated temporary directory, without executing subject programs, accessing a server, or requiring a GPU. The full check may take several minutes.

## Data and reproduction scope

The controlled cohort consists of 693 language--problem carriers (2,079 records with three fixed keys); the temporal cohort comprises 688 earlier and 687 later file transitions. The 144-transition functional subsample has 432 transition--key attempts. Keys do not create independent source files. The recorded replay-policy joint yields are 183 and 85, respectively, out of all 432 attempts.

Public release includes per-record numerical scores and test outcomes. Third-party program bodies, contest fixtures, captured test output, model weights and binaries are excluded. `publication_revision_2026-10-28/data/selection_manifest.json` supplies the dataset split, problem ID, language, solution index and hashes of the selected code and fixtures. Obtain the pinned source snapshots and check their hashes from the CodeContests manifest and the upstream dataset, subject to applicable source terms. The repository-pair metadata likewise retain repository URLs or names, parent/child revisions, paths and source hashes. Original sources can be obtained from those public repositories under their applicable licenses.

Historical generated-code outcomes are represented by the source-redacted SEW records and numerical tables. Full raw historic model outputs and subject code are not included. Frozen test outcomes are auditable as recorded outcomes; the numerical checks do not rerun project tests or prove semantic equivalence. Complete fresh scoring or test execution requires the public datasets, fixed upstream SEW commit `3c873186a56033e73347391b7aedebce1f7f71d0`, parser/formatter/compilation dependencies and a suitable isolated Linux environment. Research code may require adapting paths in the historical execution scripts.

Historical protocol and reproduction files document the actual original execution; any statements in those files about bundled source code or old server paths describe the original review artifact, not the inventory of this public release. Use this README for the public release's present contents.

The earlier 88-file patch study includes identifiers and hashes but not source, because source-level redistribution conditions were not established. Paths and checksums of the original confidential review bundle are not required for the public numerical check. The original paper-asset mapping is supplied as historical context; its paths refer to the separately maintained review artifact, not to this redacted repository.

Data source: [DeepMind CodeContests](https://github.com/google-deepmind/code_contests), Y. Li et al., *Competition-level code generation with AlphaCode*, Science 378, 1092–1097 (2022), DOI 10.1126/science.abq1158. The upstream project describes different terms for code, non-code material, and third-party contributions; this repository does not relicense those materials. The repository source projects and conditions are listed in the metadata and `maintenance_upgrade_2026-10-28/DATA_PROVENANCE.txt`.

`LICENSE-CODE` applies only to the authors' implementation and analysis scripts supplied here. Third-party software, data, names, and model outputs retain their own terms. No third-party program bodies are included.
