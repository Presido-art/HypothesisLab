# Hypothesis Testing Lab

A small full-stack tool for a statistics project: enter two datasets (Sample A and
Sample B), and get mean, median, mode, mean deviation, variance, standard
deviation, and coefficient of variation for each — with the working shown step
by step, plus a chart per statistic.

**Frontend:** HTML/CSS/JS (`templates/index.html`, `static/`)
**Backend:** Python + Flask (`app.py`) — does all the calculating
**How they're connected:** the page's JavaScript (`static/js/script.js`) sends
your two datasets to the Flask server at `POST /calculate`, and the server
sends back the results as JSON, which the JavaScript then turns into the
drop-down cards and charts. This is already wired up — you don't need to
touch the connection code.

## Project structure

```
hypothesis-stats/
├── app.py                  ← Flask backend (routes + all statistics math)
├── templates/
│   └── index.html          ← page structure
├── static/
│   ├── css/style.css       ← styling + drop-down animation
│   └── js/script.js        ← talks to the backend, builds cards & charts
└── README.md
```

## How to run it

**1. Make sure Python 3 is installed**, then install Flask (only needed once):

```bash
pip install flask
```

(If that command fails on your machine, try `pip3 install flask` or
`pip install flask --break-system-packages`.)

**2. Start the server** — from inside the `hypothesis-stats` folder:

```bash
python app.py
```

You should see something like:

```
 * Running on http://127.0.0.1:5000
```

**3. Open the site.** Go to `http://127.0.0.1:5000` in your browser. Flask is
serving the HTML/CSS/JS itself, so there's nothing separate to open — that one
URL is the whole app.

**4. Use it.** Type numbers into Sample A and Sample B (comma, space, or
newline separated), click **Run analysis**, and seven readout cards will drop
down one by one, each showing the value, the worked steps, and a chart for
that statistic, side by side for both samples.

To stop the server, go back to the terminal and press `Ctrl+C`.

## Hypothesis testing (t-test / z-test)

Below the seven descriptive-statistics cards, the page now runs two more tests
comparing Sample A against Sample B directly:

- **Two-Sample t-Test** (pooled/Student's t-test, assumes equal variances)
- **Two-Sample z-Test** (uses each sample's variance as an estimate of the
  population variance — appropriate when your samples are reasonably large)

Both test: **H₀: μA = μB** vs **H₁: μA ≠ μB** (two-tailed). You can choose the
significance level (α = 0.10, 0.05, or 0.01) with the dropdown above the "Run
analysis" button — it's sent to the backend and used for both tests.

Each card shows the test statistic, degrees of freedom (t-test only), exact
p-value, critical value, and a plain "Reject H₀" / "Fail to reject H₀" badge,
plus a chart of the relevant distribution curve with the rejection region
shaded and your test statistic marked as a dashed line — so you can see
visually whether it falls inside or outside the rejection zone.

All the p-values and critical values are computed from scratch in `app.py`
(regularized incomplete beta function for the t-distribution, `erf`-based
normal CDF for the z-test) — no `scipy` dependency required. They were
cross-checked against `scipy.stats.ttest_ind` during development and matched
exactly.

Note: for the hypothesis tests, sample variance is calculated with **n - 1**
in the denominator (the unbiased estimator), which is standard for t-tests
and z-tests — this is intentionally different from the **n**-denominator
population variance shown in the Variance card above. Both conventions are
labelled explicitly in each card's working steps so it's clear which is which.

## Notes for your project write-up

- Variance and standard deviation are calculated as **population** statistics
  (divided by `n`, not `n - 1`). If your course wants the **sample** version
  (`n - 1`, Bessel's correction), that only needs a one-line change in
  `compute_variance()` inside `app.py` — happy to adjust it if you tell me
  which convention your class uses.
- Mode reports "No mode" when every value appears once, or when all values
  tie in frequency, and lists more than one value when there's a tie for the
  most frequent.
- All the math is done in `app.py`; the JavaScript never calculates anything
  itself, it only displays what the backend sends back.
# HypothesisLab
# HypothesisLab
# HypothesisLab
# HypothesisLab
