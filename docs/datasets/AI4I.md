# AI4I 2020 Predictive Maintenance Dataset

## Source and license

* Official source: [UCI ML Repository dataset 601](https://archive.ics.uci.edu/dataset/601/ai4i+2020+predictive+maintenance+dataset)
* DOI: `10.24432/C5HS5C`; donated 2020-08-29.
* License: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
* Citation: Matzka, S. (2020). *AI4I 2020 Predictive Maintenance Dataset*. UCI Machine Learning Repository.

## Contents

The UCI release contains 10,000 records, no documented missing values, and 14 columns: a row ID and product ID; product quality type (`L`, `M`, `H`); air/process temperature (K); rotational speed (rpm); torque (Nm); tool wear (min); a composite machine-failure indicator; and five binary failure-mode indicators.

`Machine failure=1` means at least one of the documented failure modes occurred. `TWF`, `HDF`, `PWF`, `OSF`, and `RNF` denote tool-wear, heat-dissipation, power, overstrain, and random failures respectively. They are labels created by the dataset's published generation rules, not field-maintenance outcomes.

## Caveats and local acquisition

AI4I is **synthetic but intended to reflect industrial predictive-maintenance conditions**; it is not a record of a real chemical plant. Download its unmodified UCI CSV with `py -m ml.ingestion.fetch_ai4i`. The raw archive and CSV are ignored by Git under `data/raw/ai4i/`; the script records the source-file SHA-256 in the processed manifest.

