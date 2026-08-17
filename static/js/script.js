// ============================================================
// Hypothesis Testing Lab — frontend controller
// Talks to the Flask backend at POST /calculate and renders the
// results as a sequence of drop-down "readout" cards, each with
// a worked explanation and a small chart.
// ============================================================

const COLOR_A = "#e8a33d";
const COLOR_B = "#4bb3a9";

const form = document.getElementById("intake-form");
const datasetAInput = document.getElementById("dataset-a");
const datasetBInput = document.getElementById("dataset-b");
const countA = document.getElementById("count-a");
const countB = document.getElementById("count-b");
const runBtn = document.getElementById("run-btn");
const errorMsg = document.getElementById("error-msg");
const readouts = document.getElementById("readouts");
const alphaSelect = document.getElementById("alpha-select");

// The seven statistics, in the order they should appear/drop down.
const STAT_ORDER = [
  { key: "mean", chart: "mean" },
  { key: "median", chart: "median" },
  { key: "mode", chart: "mode" },
  { key: "mean_deviation", chart: "mean_deviation" },
  { key: "variance", chart: "variance" },
  { key: "std_dev", chart: "std_dev" },
  { key: "cv", chart: "cv" },
];

let activeCharts = [];

// ------------------------------------------------------------
// Live "values detected" counters
// ------------------------------------------------------------
function tokenCount(raw) {
  return raw
    .split(/[\s,]+/)
    .map((t) => t.trim())
    .filter((t) => t !== "").length;
}

datasetAInput.addEventListener("input", () => {
  countA.textContent = tokenCount(datasetAInput.value);
});
datasetBInput.addEventListener("input", () => {
  countB.textContent = tokenCount(datasetBInput.value);
});

// ------------------------------------------------------------
// Submit -> call backend -> render
// ------------------------------------------------------------
form.addEventListener("submit", async (e) => {
  e.preventDefault();
  errorMsg.textContent = "";

  const payload = {
    dataset_a: datasetAInput.value,
    dataset_b: datasetBInput.value,
    alpha: parseFloat(alphaSelect.value),
  };

  runBtn.disabled = true;
  const originalLabel = runBtn.querySelector(".btn-label").textContent;
  runBtn.querySelector(".btn-label").textContent = "Crunching numbers…";

  try {
    const res = await fetch("/calculate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    const data = await res.json();

    if (!res.ok) {
      errorMsg.textContent = data.error || "Something went wrong. Check your input.";
      return;
    }

    renderResults(data.sample_a, data.sample_b, data.hypothesis_tests);
  } catch (err) {
    errorMsg.textContent = "Could not reach the server. Is app.py running?";
    console.error(err);
  } finally {
    runBtn.disabled = false;
    runBtn.querySelector(".btn-label").textContent = originalLabel;
  }
});

// ------------------------------------------------------------
// Render the 7 drop-down readout cards
// ------------------------------------------------------------
function renderResults(sampleA, sampleB, hypothesisTests) {
  // Clear old cards & charts
  activeCharts.forEach((c) => c.destroy());
  activeCharts = [];
  readouts.innerHTML = "";

  STAT_ORDER.forEach((stat, i) => {
    const card = buildCard(stat, sampleA, sampleB, i);
    readouts.appendChild(card);
  });

  // Hypothesis testing section (t-test / z-test), appended after the
  // seven descriptive-statistics cards above.
  if (hypothesisTests) {
    readouts.appendChild(buildSectionDivider("Hypothesis Testing — Sample A vs Sample B"));
    if (hypothesisTests.t_test) {
      readouts.appendChild(buildHypothesisCard(hypothesisTests.t_test, "t_test", STAT_ORDER.length));
    }
    if (hypothesisTests.z_test) {
      readouts.appendChild(buildHypothesisCard(hypothesisTests.z_test, "z_test", STAT_ORDER.length + 1));
    }
  }

  // Stagger the drop-down open animation, then build charts once
  // each card is in the DOM (canvas needs layout to size correctly).
  const cards = readouts.querySelectorAll(".readout-card");
  cards.forEach((card, i) => {
    setTimeout(() => {
      card.classList.add("open");
      setTimeout(() => buildChartsForCard(card), 260);
    }, i * 130);
  });

  // Scroll the first card into a comfortable view
  setTimeout(() => {
    readouts.scrollIntoView({ behavior: "smooth", block: "start" });
  }, 100);
}

function buildSectionDivider(label) {
  const div = document.createElement("div");
  div.className = "section-divider";
  div.innerHTML = `<h2>${escapeHtml(label)}</h2><span class="line"></span>`;
  return div;
}

function buildCard(stat, sampleA, sampleB, index) {
  const resA = sampleA.results[stat.key];
  const resB = sampleB.results[stat.key];

  const card = document.createElement("article");
  card.className = "readout-card";
  card.dataset.chart = stat.chart;

  card.innerHTML = `
    <div class="readout-head">
      <div class="readout-title">
        <span class="stat-index">${String(index + 1).padStart(2, "0")}</span>
        <h3>${resA.label}</h3>
        <span class="readout-formula">${resA.formula}</span>
      </div>
    </div>
    <div class="readout-body">
      <div class="sample-col col-a">
        <div class="col-tag">Sample A</div>
        <div class="result-value">${displayValue(resA)}</div>
        <ol class="working-steps">
          ${resA.steps.map((s) => `<li>${escapeHtml(s)}</li>`).join("")}
        </ol>
        <div class="chart-wrap"><canvas class="stat-canvas" data-sample="a"></canvas></div>
      </div>
      <div class="sample-col col-b">
        <div class="col-tag">Sample B</div>
        <div class="result-value">${displayValue(resB)}</div>
        <ol class="working-steps">
          ${resB.steps.map((s) => `<li>${escapeHtml(s)}</li>`).join("")}
        </ol>
        <div class="chart-wrap"><canvas class="stat-canvas" data-sample="b"></canvas></div>
      </div>
    </div>
  `;

  // Stash the raw sample payloads on the element so buildChartsForCard can use them
  card._sampleA = sampleA;
  card._sampleB = sampleB;

  return card;
}

function displayValue(res) {
  if (res.value === null || res.value === undefined) {
    return res.display || "—";
  }
  if (res.display) return res.display;
  if (Array.isArray(res.value)) return res.value.join(", ");
  return String(res.value);
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

// ------------------------------------------------------------
// Hypothesis test cards (t-test / z-test)
// ------------------------------------------------------------
function buildHypothesisCard(result, kind, index) {
  const card = document.createElement("article");
  card.className = "readout-card hypothesis-card";
  card.dataset.chart = kind;

  if (result.error) {
    card.innerHTML = `
      <div class="readout-head">
        <div class="readout-title">
          <span class="stat-index">${String(index + 1).padStart(2, "0")}</span>
          <h3>${kind === "t_test" ? "Two-Sample t-Test" : "Two-Sample z-Test"}</h3>
        </div>
      </div>
      <div class="readout-body"><p class="hyp-error">${escapeHtml(result.error)}</p></div>
    `;
    return card;
  }

  const reject = result.decision.startsWith("Reject");
  const dfFigure =
    kind === "t_test"
      ? `<div class="stat-figure"><span class="figure-label">df</span><span class="figure-value">${result.df}</span></div>`
      : "";

  card.innerHTML = `
    <div class="readout-head">
      <div class="readout-title">
        <span class="stat-index">${String(index + 1).padStart(2, "0")}</span>
        <h3>${result.label}</h3>
        <span class="readout-formula">${result.formula}</span>
      </div>
    </div>
    <div class="readout-body">
      <div class="hyp-top">
        <div class="hyp-stat-block">
          <div class="stat-figure">
            <span class="figure-label">${kind === "t_test" ? "t statistic" : "z statistic"}</span>
            <span class="figure-value">${result.statistic}</span>
          </div>
          ${dfFigure}
          <div class="stat-figure">
            <span class="figure-label">p-value</span>
            <span class="figure-value">${result.p_value}</span>
          </div>
          <div class="stat-figure">
            <span class="figure-label">critical value</span>
            <span class="figure-value">±${result.critical_value}</span>
          </div>
        </div>
        <span class="decision-badge ${reject ? "reject" : "accept"}">${escapeHtml(result.decision)}</span>
      </div>
      <ol class="working-steps">
        ${result.steps.map((s) => `<li>${escapeHtml(s)}</li>`).join("")}
      </ol>
      <div class="chart-wrap"><canvas class="hyp-canvas"></canvas></div>
    </div>
  `;

  card._hypResult = result;
  return card;
}

// ------------------------------------------------------------
// Charts
// ------------------------------------------------------------
function buildChartsForCard(card) {
  const kind = card.dataset.chart;

  if (kind === "t_test" || kind === "z_test") {
    const canvas = card.querySelector(".hyp-canvas");
    if (canvas && card._hypResult) {
      const chart = makeDistributionChart(canvas, card._hypResult, kind);
      if (chart) activeCharts.push(chart);
    }
    return;
  }

  const canvases = card.querySelectorAll(".stat-canvas");
  canvases.forEach((canvas) => {
    const sample = canvas.dataset.sample === "a" ? card._sampleA : card._sampleB;
    const color = canvas.dataset.sample === "a" ? COLOR_A : COLOR_B;
    const chart = makeChart(canvas, kind, sample, color);
    if (chart) activeCharts.push(chart);
  });
}

function makeDistributionChart(canvas, result, kind) {
  const curve = result.chart.curve;
  const rejection = result.chart.rejection;
  const stat = result.chart.statistic;
  const peakY = Math.max(...curve.map((p) => p.y));
  const accentColor = kind === "t_test" ? COLOR_A : COLOR_B;

  const cfg = {
    type: "line",
    data: {
      datasets: [
        {
          label: "Rejection region",
          data: rejection,
          borderWidth: 0,
          backgroundColor: "rgba(232, 122, 61, 0.28)",
          fill: "origin",
          pointRadius: 0,
          tension: 0.15,
          order: 3,
        },
        {
          label: kind === "t_test" ? "t-distribution" : "Standard normal",
          data: curve,
          borderColor: "rgba(233, 236, 239, 0.55)",
          borderWidth: 1.5,
          backgroundColor: "transparent",
          fill: false,
          pointRadius: 0,
          tension: 0.15,
          order: 2,
        },
        {
          label: "Test statistic",
          data: [
            { x: stat, y: 0 },
            { x: stat, y: peakY * 1.05 },
          ],
          borderColor: accentColor,
          borderWidth: 2,
          borderDash: [4, 3],
          pointRadius: 0,
          fill: false,
          order: 1,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      parsing: false,
      plugins: {
        legend: {
          display: true,
          labels: { color: "#8b93a1", font: { family: "JetBrains Mono", size: 10 }, boxWidth: 12, filter: (item) => item.text !== "Rejection region" },
        },
        tooltip: { enabled: false },
      },
      scales: {
        x: {
          type: "linear",
          min: -4.5,
          max: 4.5,
          ticks: { color: "#5c6572", font: { family: "JetBrains Mono", size: 10 } },
          grid: { color: "rgba(255,255,255,0.04)" },
        },
        y: {
          min: 0,
          ticks: { color: "#5c6572", font: { family: "JetBrains Mono", size: 10 } },
          grid: { color: "rgba(255,255,255,0.06)" },
        },
      },
    },
  };

  return new Chart(canvas, cfg);
}

function hexAlpha(hex, alpha) {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

function baseOptions(yLabel) {
  return {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { display: false },
      tooltip: {
        backgroundColor: "#1b232c",
        borderColor: "#262f3a",
        borderWidth: 1,
        titleFont: { family: "JetBrains Mono", size: 11 },
        bodyFont: { family: "JetBrains Mono", size: 11 },
      },
    },
    scales: {
      x: {
        ticks: { color: "#5c6572", font: { family: "JetBrains Mono", size: 10 } },
        grid: { color: "rgba(255,255,255,0.04)" },
      },
      y: {
        ticks: { color: "#5c6572", font: { family: "JetBrains Mono", size: 10 } },
        grid: { color: "rgba(255,255,255,0.06)" },
        title: yLabel
          ? { display: true, text: yLabel, color: "#8b93a1", font: { family: "JetBrains Mono", size: 10 } }
          : undefined,
      },
    },
  };
}

function makeChart(canvas, kind, sample, color) {
  const cd = sample.chart_data;
  let cfg;

  switch (kind) {
    case "mean": {
      cfg = {
        type: "bar",
        data: {
          labels: cd.labels,
          datasets: [
            {
              type: "bar",
              label: "Value",
              data: cd.values,
              backgroundColor: hexAlpha(color, 0.55),
              borderRadius: 4,
              order: 2,
            },
            {
              type: "line",
              label: "Mean",
              data: cd.labels.map(() => cd.mean),
              borderColor: color,
              borderWidth: 2,
              pointRadius: 0,
              borderDash: [5, 4],
              order: 1,
            },
          ],
        },
        options: {
          ...baseOptions(),
          plugins: {
            ...baseOptions().plugins,
            legend: {
              display: true,
              labels: { color: "#8b93a1", font: { family: "JetBrains Mono", size: 10 }, boxWidth: 14 },
            },
          },
        },
      };
      break;
    }

    case "median": {
      const sorted = sample.sorted;
      const n = sorted.length;
      const mid = Math.floor(n / 2);
      const highlightIdx = n % 2 === 1 ? [mid] : [mid - 1, mid];
      const colors = sorted.map((_, i) =>
        highlightIdx.includes(i) ? color : "rgba(255,255,255,0.12)"
      );
      cfg = {
        type: "bar",
        data: {
          labels: sorted.map((_, i) => `#${i + 1}`),
          datasets: [{ data: sorted, backgroundColor: colors, borderRadius: 4 }],
        },
        options: baseOptions("sorted values"),
      };
      break;
    }

    case "mode": {
      const freq = {};
      cd.values.forEach((v) => {
        freq[v] = (freq[v] || 0) + 1;
      });
      const labels = Object.keys(freq).sort((a, b) => Number(a) - Number(b));
      const data = labels.map((l) => freq[l]);
      const maxFreq = Math.max(...data);
      const colors = data.map((d) => (d === maxFreq && maxFreq > 1 ? color : "rgba(255,255,255,0.12)"));
      cfg = {
        type: "bar",
        data: { labels, datasets: [{ data, backgroundColor: colors, borderRadius: 4 }] },
        options: baseOptions("frequency"),
      };
      break;
    }

    case "mean_deviation": {
      cfg = {
        type: "bar",
        data: {
          labels: cd.labels,
          datasets: [{ data: cd.abs_devs, backgroundColor: hexAlpha(color, 0.65), borderRadius: 4 }],
        },
        options: baseOptions("|x - mean|"),
      };
      break;
    }

    case "variance": {
      cfg = {
        type: "bar",
        data: {
          labels: cd.labels,
          datasets: [{ data: cd.sq_devs, backgroundColor: hexAlpha(color, 0.65), borderRadius: 4 }],
        },
        options: baseOptions("(x - mean)²"),
      };
      break;
    }

    case "std_dev": {
      const varVal = sample.results.variance.value;
      const stdVal = sample.results.std_dev.value;
      cfg = {
        type: "bar",
        data: {
          labels: ["Variance", "Std Dev"],
          datasets: [{ data: [varVal, stdVal], backgroundColor: [hexAlpha(color, 0.35), color], borderRadius: 4 }],
        },
        options: baseOptions(),
      };
      break;
    }

    case "cv": {
      const meanVal = sample.results.mean.value;
      const stdVal = sample.results.std_dev.value;
      cfg = {
        type: "bar",
        data: {
          labels: ["Mean", "Std Dev"],
          datasets: [{ data: [meanVal, stdVal], backgroundColor: [hexAlpha(color, 0.35), color], borderRadius: 4 }],
        },
        options: baseOptions(),
      };
      break;
    }

    default:
      return null;
  }

  return new Chart(canvas, cfg);
}
