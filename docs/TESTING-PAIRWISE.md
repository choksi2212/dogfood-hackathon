# Test suite — pairwise

`tests/pairwise/test_pairwise.py` — `@pytest.mark.pairwise`

## What it covers

Bradley-Terry MM algorithm with phantom prior 0.5. `P(i beats j) = 1 / (1 + exp(θ_j − θ_i))`. MM updates, recentre to sum-to-zero, stop at max|Δθ| < 1e-9.

| Test | Asserts |
|---|---|
| Uniform preference (4 projects, A>B>C>D) | θ_A > θ_B > θ_C > θ_D recovered |
| All ties | θ equal for all projects (within tolerance) |
| Single pair dominance (100 voters prefer X over Y) | θ_X > θ_Y |
| Empty ballot set | Empty ranking, no error |
| Convergence in one iteration with phantom prior | θ equal by symmetry |
| Sum-to-zero recentring | sum(θ) = 0 to within tolerance |
| Tie votes count as half-win + half-loss | ballot winner='tie' increments both sides by 0.5 |
| Unknown winner value | winner='invalid' rejected (422 at view level) |
| Pairwise ranking endpoint | returns projects in θ order |
| Idempotent re-run | same ballots → same ranking |

## Run

```bash
make test-pairwise
```
