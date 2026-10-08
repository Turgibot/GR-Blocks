"""The paper's shifted positive-Poisson cost model and survival function (Parts 18-21)."""
import math


def pmf(x, c, lam):
    """P(real plan cost = x | G) when the optimal cost is c. Zero below c."""
    if x < c:
        return 0.0
    k, l = x - c + 1, lam + 1
    return l ** k / (math.factorial(k) * (math.exp(l) - 1))


def survival(tp, c, lam):
    """P(the plan is still running at tp) = P(cost >= tp)."""
    if tp <= c:
        return 1.0
    return max(1.0 - sum(pmf(x, c, lam) for x in range(c, tp)), 1e-12)
