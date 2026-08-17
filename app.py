"""
Hypothesis Testing Lab — Backend
---------------------------------
A small Flask API that takes two raw datasets (Sample A and Sample B)
and returns, for each one:
    - mean, median, mode
    - mean deviation
    - variance
    - standard deviation
    - coefficient of variation
Each result comes with a step-by-step "working" trail (as plain text
lines) so the frontend can show *how* each number was produced, plus
the raw numbers needed to draw charts.

Run with:  python app.py
Then open: http://127.0.0.1:5000
"""

from flask import Flask, request, jsonify, render_template
from collections import Counter
import math

app = Flask(__name__)


# ---------------------------------------------------------------------
# Core statistics engine
# ---------------------------------------------------------------------

def fmt(n, dp=4):
    """Format a number for display: trims trailing zeros, keeps it readable."""
    if isinstance(n, int):
        return str(n)
    rounded = round(n, dp)
    if rounded == int(rounded):
        return str(int(rounded))
    return f"{rounded:g}"


# ---------------------------------------------------------------------
# Distribution math for hypothesis testing (t-test / z-test)
# Implemented in plain Python (no scipy dependency) using the standard
# regularized incomplete beta function approach for the t-distribution,
# and math.erf for the normal distribution.
# ---------------------------------------------------------------------

def normal_cdf(z):
    """Standard normal CDF, P(Z <= z)."""
    return 0.5 * (1 + math.erf(z / math.sqrt(2)))


def normal_two_tailed_p(z):
    """Two-tailed p-value for a standard normal test statistic."""
    return 2 * (1 - normal_cdf(abs(z)))


def normal_ppf_two_tailed(alpha):
    """Critical z-value such that P(|Z| > z) = alpha (two-tailed), via bisection."""
    target = 1 - alpha / 2
    lo, hi = 0.0, 10.0
    for _ in range(100):
        mid = (lo + hi) / 2
        if normal_cdf(mid) < target:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def _betacf(x, a, b, max_iter=200, eps=3e-11):
    """Continued fraction for the incomplete beta function (Lentz's algorithm)."""
    qab = a + b
    qap = a + 1
    qam = a - 1
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < 1e-30:
        d = 1e-30
    d = 1.0 / d
    h = d
    for m in range(1, max_iter + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < 1e-30:
            d = 1e-30
        c = 1.0 + aa / c
        if abs(c) < 1e-30:
            c = 1e-30
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < 1e-30:
            d = 1e-30
        c = 1.0 + aa / c
        if abs(c) < 1e-30:
            c = 1e-30
        d = 1.0 / d
        de = d * c
        h *= de
        if abs(de - 1.0) < eps:
            break
    return h


def _regularized_incomplete_beta(x, a, b):
    """Regularized incomplete beta function I_x(a, b)."""
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    lbeta = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log(1 - x)
    front = math.exp(lbeta)
    if x < (a + 1) / (a + b + 2):
        return front * _betacf(x, a, b) / a
    else:
        return 1 - front * _betacf(1 - x, b, a) / b


def t_two_tailed_p(t_stat, df):
    """Two-tailed p-value for a t test statistic with the given degrees of freedom."""
    t_stat = abs(t_stat)
    x = df / (df + t_stat ** 2)
    return _regularized_incomplete_beta(x, df / 2, 0.5)


def t_critical_value(df, alpha):
    """Critical t-value such that P(|T| > t) = alpha (two-tailed), via bisection."""
    lo, hi = 0.0, 100.0
    for _ in range(100):
        mid = (lo + hi) / 2
        p = t_two_tailed_p(mid, df)
        if p > alpha:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def normal_pdf(x):
    return (1 / math.sqrt(2 * math.pi)) * math.exp(-x ** 2 / 2)


def t_pdf(x, df):
    coef = math.exp(math.lgamma((df + 1) / 2) - math.lgamma(df / 2)) / math.sqrt(df * math.pi)
    return coef * (1 + x ** 2 / df) ** (-(df + 1) / 2)


def compute_mean(data):
    n = len(data)
    total = sum(data)
    mean = total / n
    steps = [
        f"Add every value in the sample: {' + '.join(fmt(x) for x in data)} = {fmt(total)}",
        f"Divide the total by the number of values (n = {n}): {fmt(total)} ÷ {n} = {fmt(mean)}",
    ]
    return {
        "label": "Mean (x̄)",
        "formula": "x̄ = (Σx) / n",
        "value": round(mean, 4),
        "steps": steps,
    }, mean


def compute_median(data):
    n = len(data)
    sorted_data = sorted(data)
    steps = [f"Arrange the data in order: {', '.join(fmt(x) for x in sorted_data)}"]
    if n % 2 == 1:
        mid = n // 2
        median = sorted_data[mid]
        steps.append(f"n = {n} is odd, so the median is the middle value: position {mid + 1} = {fmt(median)}")
    else:
        mid1, mid2 = sorted_data[n // 2 - 1], sorted_data[n // 2]
        median = (mid1 + mid2) / 2
        steps.append(
            f"n = {n} is even, so the median is the average of the two middle values: "
            f"({fmt(mid1)} + {fmt(mid2)}) ÷ 2 = {fmt(median)}"
        )
    return {
        "label": "Median",
        "formula": "middle value of the ordered dataset",
        "value": round(median, 4),
        "steps": steps,
    }, median


def compute_mode(data):
    counts = Counter(data)
    max_freq = max(counts.values())
    modes = sorted([val for val, c in counts.items() if c == max_freq])
    freq_line = ", ".join(f"{fmt(v)} → {c}×" for v, c in sorted(counts.items()))
    if max_freq == 1:
        steps = [
            f"Count how often each value appears: {freq_line}",
            "Every value appears exactly once, so there is no mode.",
        ]
        value = None
        display = "No mode"
    elif len(modes) == len(counts):
        steps = [
            f"Count how often each value appears: {freq_line}",
            "All values share the same frequency, so there is no single mode.",
        ]
        value = None
        display = "No mode"
    else:
        steps = [
            f"Count how often each value appears: {freq_line}",
            f"The highest frequency is {max_freq}×, reached by: {', '.join(fmt(m) for m in modes)}",
        ]
        value = modes if len(modes) > 1 else modes[0]
        display = ", ".join(fmt(m) for m in modes)
    return {
        "label": "Mode",
        "formula": "most frequently occurring value(s)",
        "value": value,
        "display": display,
        "steps": steps,
    }, value


def compute_mean_deviation(data, mean):
    n = len(data)
    abs_devs = [abs(x - mean) for x in data]
    total = sum(abs_devs)
    md = total / n
    dev_line = ", ".join(f"|{fmt(x)} - {fmt(mean)}| = {fmt(abs(x - mean))}" for x in data)
    steps = [
        f"Find the absolute deviation of each value from the mean ({fmt(mean)}): {dev_line}",
        f"Sum the absolute deviations: {' + '.join(fmt(d) for d in abs_devs)} = {fmt(total)}",
        f"Divide by n ({n}): {fmt(total)} ÷ {n} = {fmt(md)}",
    ]
    return {
        "label": "Mean Deviation",
        "formula": "MD = Σ|x - x̄| / n",
        "value": round(md, 4),
        "steps": steps,
    }, md, abs_devs


def compute_variance(data, mean):
    n = len(data)
    sq_devs = [(x - mean) ** 2 for x in data]
    total = sum(sq_devs)
    variance = total / n
    dev_line = ", ".join(f"({fmt(x)} - {fmt(mean)})² = {fmt((x - mean) ** 2)}" for x in data)
    steps = [
        f"Square the deviation of each value from the mean ({fmt(mean)}): {dev_line}",
        f"Sum the squared deviations: {' + '.join(fmt(d) for d in sq_devs)} = {fmt(total)}",
        f"Divide by n ({n}) — population variance: {fmt(total)} ÷ {n} = {fmt(variance)}",
    ]
    return {
        "label": "Variance (σ²)",
        "formula": "σ² = Σ(x - x̄)² / n",
        "value": round(variance, 4),
        "steps": steps,
    }, variance, sq_devs


def compute_std_dev(variance):
    std = math.sqrt(variance)
    steps = [
        f"Take the square root of the variance: √{fmt(variance)} = {fmt(std)}",
    ]
    return {
        "label": "Standard Deviation (σ)",
        "formula": "σ = √(σ²)",
        "value": round(std, 4),
        "steps": steps,
    }, std


def compute_cv(std, mean):
    if mean == 0:
        return {
            "label": "Coefficient of Variation",
            "formula": "CV = (σ / x̄) × 100%",
            "value": None,
            "steps": ["Mean is 0, so the coefficient of variation is undefined."],
        }, None
    cv = (std / mean) * 100
    steps = [
        f"Divide the standard deviation by the mean: {fmt(std)} ÷ {fmt(mean)} = {fmt(std / mean)}",
        f"Multiply by 100 to express as a percentage: {fmt(std / mean)} × 100 = {fmt(cv)}%",
    ]
    return {
        "label": "Coefficient of Variation (CV)",
        "formula": "CV = (σ / x̄) × 100%",
        "value": round(cv, 4),
        "steps": steps,
    }, cv


# ---------------------------------------------------------------------
# Hypothesis testing: two-sample t-test and two-sample z-test
# Both compare the means of Sample A and Sample B.
# H0: μA = μB   (no real difference between the two sample means)
# H1: μA ≠ μB   (two-tailed test)
# ---------------------------------------------------------------------

def _sample_variance(data, mean):
    """Unbiased sample variance (divides by n - 1) — the standard choice
    for hypothesis testing, as opposed to the population variance (÷ n)
    used in the descriptive-statistics cards above."""
    n = len(data)
    if n < 2:
        return 0.0
    return sum((x - mean) ** 2 for x in data) / (n - 1)


def _curve_points(pdf_fn, lo=-4.5, hi=4.5, steps=90):
    """Sample a pdf across a grid, returned as {x, y} points for Chart.js."""
    step_size = (hi - lo) / steps
    return [{"x": round(lo + i * step_size, 4), "y": pdf_fn(lo + i * step_size)} for i in range(steps + 1)]


def compute_two_sample_t_test(data_a, data_b, alpha):
    n1, n2 = len(data_a), len(data_b)
    if n1 < 2 or n2 < 2:
        return {"error": "Each sample needs at least 2 values to run a t-test."}

    mean1, mean2 = sum(data_a) / n1, sum(data_b) / n2
    var1 = _sample_variance(data_a, mean1)
    var2 = _sample_variance(data_b, mean2)
    df = n1 + n2 - 2
    pooled_var = ((n1 - 1) * var1 + (n2 - 1) * var2) / df
    se = math.sqrt(pooled_var * (1 / n1 + 1 / n2))
    t_stat = 0.0 if se == 0 else (mean1 - mean2) / se

    p_value = t_two_tailed_p(t_stat, df)
    critical = t_critical_value(df, alpha)
    reject = p_value < alpha
    decision = "Reject H₀" if reject else "Fail to reject H₀"
    conclusion = (
        f"Since the p-value ({fmt(p_value)}) is less than α ({fmt(alpha)}), we reject H₀ — "
        f"there is a statistically significant difference between the two sample means."
        if reject else
        f"Since the p-value ({fmt(p_value)}) is not less than α ({fmt(alpha)}), we fail to reject H₀ — "
        f"there is not enough evidence of a difference between the two sample means."
    )

    steps = [
        f"H₀: μA = μB    H₁: μA ≠ μB (two-tailed test, α = {fmt(alpha)})",
        f"Sample means: x̄A = {fmt(mean1)}, x̄B = {fmt(mean2)}",
        f"Sample variances (n - 1 in the denominator): sA² = {fmt(var1)}, sB² = {fmt(var2)}",
        f"Pooled variance: sp² = (({n1}-1)×{fmt(var1)} + ({n2}-1)×{fmt(var2)}) / ({n1}+{n2}-2) = {fmt(pooled_var)}",
        f"Standard error: SE = √(sp² × (1/{n1} + 1/{n2})) = {fmt(se)}",
        f"Test statistic: t = (x̄A - x̄B) / SE = ({fmt(mean1)} - {fmt(mean2)}) / {fmt(se)} = {fmt(t_stat)}",
        f"Degrees of freedom: df = {n1} + {n2} - 2 = {df}",
        f"Two-tailed p-value for t = {fmt(t_stat)} at df = {df}: p = {fmt(p_value)}",
        f"Critical t-value at α = {fmt(alpha)}, df = {df}: t* = ±{fmt(critical)}",
        conclusion,
    ]

    curve = _curve_points(lambda x: t_pdf(x, df))
    rejection = [{"x": pt["x"], "y": (t_pdf(pt["x"], df) if abs(pt["x"]) >= critical else 0)} for pt in curve]

    return {
        "label": "Two-Sample t-Test",
        "formula": "t = (x̄A - x̄B) / √(sp²(1/nA + 1/nB))",
        "statistic": round(t_stat, 4),
        "df": df,
        "p_value": round(p_value, 6),
        "alpha": alpha,
        "critical_value": round(critical, 4),
        "decision": decision,
        "steps": steps,
        "chart": {"curve": curve, "rejection": rejection, "statistic": round(t_stat, 4), "critical": round(critical, 4)},
    }


def compute_two_sample_z_test(data_a, data_b, alpha):
    n1, n2 = len(data_a), len(data_b)
    if n1 < 2 or n2 < 2:
        return {"error": "Each sample needs at least 2 values to run a z-test."}

    mean1, mean2 = sum(data_a) / n1, sum(data_b) / n2
    var1 = _sample_variance(data_a, mean1)
    var2 = _sample_variance(data_b, mean2)
    se = math.sqrt(var1 / n1 + var2 / n2)
    z_stat = 0.0 if se == 0 else (mean1 - mean2) / se

    p_value = normal_two_tailed_p(z_stat)
    critical = normal_ppf_two_tailed(alpha)
    reject = p_value < alpha
    decision = "Reject H₀" if reject else "Fail to reject H₀"
    conclusion = (
        f"Since the p-value ({fmt(p_value)}) is less than α ({fmt(alpha)}), we reject H₀ — "
        f"there is a statistically significant difference between the two sample means."
        if reject else
        f"Since the p-value ({fmt(p_value)}) is not less than α ({fmt(alpha)}), we fail to reject H₀ — "
        f"there is not enough evidence of a difference between the two sample means."
    )

    steps = [
        f"H₀: μA = μB    H₁: μA ≠ μB (two-tailed test, α = {fmt(alpha)})",
        f"Sample means: x̄A = {fmt(mean1)}, x̄B = {fmt(mean2)}",
        f"Sample variances (used as estimates of population variance): sA² = {fmt(var1)}, sB² = {fmt(var2)}",
        f"Standard error: SE = √(sA²/{n1} + sB²/{n2}) = {fmt(se)}",
        f"Test statistic: z = (x̄A - x̄B) / SE = ({fmt(mean1)} - {fmt(mean2)}) / {fmt(se)} = {fmt(z_stat)}",
        f"Two-tailed p-value for z = {fmt(z_stat)}: p = {fmt(p_value)}",
        f"Critical z-value at α = {fmt(alpha)}: z* = ±{fmt(critical)}",
        conclusion,
    ]

    curve = _curve_points(normal_pdf)
    rejection = [{"x": pt["x"], "y": (normal_pdf(pt["x"]) if abs(pt["x"]) >= critical else 0)} for pt in curve]

    return {
        "label": "Two-Sample z-Test",
        "formula": "z = (x̄A - x̄B) / √(sA²/nA + sB²/nB)",
        "statistic": round(z_stat, 4),
        "p_value": round(p_value, 6),
        "alpha": alpha,
        "critical_value": round(critical, 4),
        "decision": decision,
        "steps": steps,
        "chart": {"curve": curve, "rejection": rejection, "statistic": round(z_stat, 4), "critical": round(critical, 4)},
    }


def analyze(data):
    """Run the full battery of descriptive statistics on one dataset."""
    n = len(data)
    mean_res, mean = compute_mean(data)
    median_res, median = compute_median(data)
    mode_res, mode_val = compute_mode(data)
    md_res, md, abs_devs = compute_mean_deviation(data, mean)
    var_res, variance, sq_devs = compute_variance(data, mean)
    std_res, std = compute_std_dev(variance)
    cv_res, cv = compute_cv(std, mean)

    return {
        "n": n,
        "raw": data,
        "sorted": sorted(data),
        "results": {
            "mean": mean_res,
            "median": median_res,
            "mode": mode_res,
            "mean_deviation": md_res,
            "variance": var_res,
            "std_dev": std_res,
            "cv": cv_res,
        },
        "chart_data": {
            "labels": [f"x{i+1}" for i in range(n)],
            "values": data,
            "mean": round(mean, 4),
            "abs_devs": [round(d, 4) for d in abs_devs],
            "sq_devs": [round(d, 4) for d in sq_devs],
        },
    }


# ---------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html")


def parse_dataset(raw):
    """Turn a comma/space/newline separated string OR a list into floats."""
    if isinstance(raw, list):
        values = raw
    else:
        cleaned = raw.replace("\n", ",").replace(" ", ",")
        values = [v for v in cleaned.split(",") if v.strip() != ""]

    numbers = []
    for v in values:
        try:
            numbers.append(float(v))
        except (ValueError, TypeError):
            raise ValueError(f"'{v}' is not a valid number")
    return numbers


@app.route("/calculate", methods=["POST"])
def calculate():
    payload = request.get_json(force=True, silent=True) or {}
    dataset_a_raw = payload.get("dataset_a", "")
    dataset_b_raw = payload.get("dataset_b", "")

    try:
        data_a = parse_dataset(dataset_a_raw)
        data_b = parse_dataset(dataset_b_raw)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    if len(data_a) < 1 or len(data_b) < 1:
        return jsonify({"error": "Both samples need at least one value."}), 400

    try:
        alpha = float(payload.get("alpha", 0.05))
    except (ValueError, TypeError):
        alpha = 0.05
    if not (0 < alpha < 1):
        alpha = 0.05

    response = {
        "sample_a": analyze(data_a),
        "sample_b": analyze(data_b),
        "hypothesis_tests": {
            "t_test": compute_two_sample_t_test(data_a, data_b, alpha),
            "z_test": compute_two_sample_z_test(data_a, data_b, alpha),
        },
    }
    return jsonify(response)


if __name__ == "__main__":
    app.run(debug=True, port=5000)
