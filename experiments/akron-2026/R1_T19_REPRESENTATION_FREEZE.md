# R1.T19 representation freeze marker

The T19 representation is frozen by the commit that introduces this file together with:

- `experiments/akron-2026/R1_T19_LOCAL_GROUPING_DEVELOPMENT.md`
- `experiments/akron-2026/r1_t19_local_grouping_development_summary.json`
- `tests/test_t19_freeze.py`

The implementation being frozen is `proofline-local-grouping/nearest-components-v1`, introduced at `59f995686a62962281ec780f4a9afa1857449681` after the ranks 65–96 identity-only holdout freeze at `e3e56210b092ee8758ce2c06e3a20c1ee212f8b0`.

After this marker commit, ranks 65–96 may be resolved only for the preregistered structural-transfer evaluation described in the T19 development receipt. Any later representation change must be treated as post-holdout development and must not be reported as the frozen v1 holdout result.
