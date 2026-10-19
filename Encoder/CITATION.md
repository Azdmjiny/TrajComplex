# Data and method sources

- ATFMTraj author-provided dataset: https://huggingface.co/datasets/petchthwr/ATFMTraj , DOI `10.57967/hf/3356`. This experiment used only the six local RKSIa TSV files and stats labels. The actual version is identified by file SHA256 values in `reports/data_audit.json`, not by the current online version.
- Thaweerath Phisannupawong, Joshua Julian Damanik, and Han-Lim Choi. *ATFMTraj: Aircraft Trajectory Classification Data for Air Traffic Management*, 2024.
- The same authors, *Aircraft Trajectory Segmentation-based Contrastive Coding: A Framework for Self-supervised Trajectory Representation*. arXiv:2407.20028; published DOI `10.1109/OJITS.2025.3574746`.
- Official implementation: https://github.com/petchthwr/ATSCC , pinned commit `789ccd72b7496b52e03df7d8599d8c9e6659bdb9`. The full MIT license for the reference code is retained in THIRD_PARTY_LICENSE_ATSCC.md.
- Pages 3–4 of the user-provided `ITSC_2026_ZhiJunLim.pdf` were used to check the smaller backbone, input/output normalization, and signed GeM formula. That paper is not redistributed here.

According to the authors' dataset card, RKSI data originate from OpenSky and Airportal. Coordinates were converted to ENU, resampled at one-second intervals, smoothed, divided by 120 km, and padded with NaN. This project restores metre units, samples every five seconds, and retains the endpoint. Class labels combine STAR, IAF, and runway information; they are used only for evaluation grouping, not self-supervised training.

Official documentation for the runtime telemetry issue: https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_telemetry . The outbound-blocking launcher affects only the experiment process tree and does not change the user's global configuration.
