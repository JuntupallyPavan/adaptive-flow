const ENERGY = {
  High: { mult: 1.0 },
  Medium: { mult: 0.6 },
  Low: { mult: 0.3 },
  Burnout: { mult: 0.05 },
};

const ENCOURAGEMENT = {
  High: [
    "You’ve got energy—spend it intentionally. One focused win.",
    "Momentum is here. Keep it clean and consistent.",
    "High energy day: do the important thing first.",
  ],
  Medium: [
    "Steady beats heroic. Show up and stack the points.",
    "Balanced day: aim for “done”, not “perfect”.",
    "Consistency is a skill—practice it today.",
  ],
  Low: [
    "Low energy is still energy. Keep it tiny and keep it real.",
    "Soft day, strong identity: you still showed up.",
    "Do the minimum version. Protect the streak.",
  ],
  Burnout: [
    "Burnout mode: 1% counts. Be kind to your brain.",
    "Rest is productive when it prevents collapse.",
    "Today’s win: the smallest possible action.",
  ],
};

function pick(arr) {
  return arr[Math.floor(Math.random() * arr.length)];
}

function setEnergy(energy) {
  const body = document.body;
  body.dataset.energy = energy;

  body.classList.remove("theme--high", "theme--medium", "theme--low", "theme--burnout");
  body.classList.add(`theme--${energy.toLowerCase()}`);

  const energyInputs = document.querySelectorAll('input[name="energy"]');
  energyInputs.forEach((input) => {
    input.value = energy;
  });

  const encouragementEl = document.getElementById("encouragement");
  if (encouragementEl && ENCOURAGEMENT[energy]) encouragementEl.textContent = pick(ENCOURAGEMENT[energy]);

  const buttons = document.querySelectorAll("[data-energy-btn]");
  buttons.forEach((btn) => {
    btn.classList.toggle("is-active", btn.dataset.energyBtn === energy);
  });

  updatePreview();
}

function getSelectedHabitMeta() {
  const select = document.querySelector('select[name="habit_id"]');
  if (!select) return null;

  const opt = select.options[select.selectedIndex];
  if (!opt || !opt.dataset) return null;

  const baseGoal = Number(opt.dataset.baseGoal || NaN);
  const unit = String(opt.dataset.unit || "units");
  if (!Number.isFinite(baseGoal) || baseGoal <= 0) return null;

  return { baseGoal, unit };
}

function updatePreview() {
  const energy = document.body.dataset.energy || "Medium";
  const mult = ENERGY[energy]?.mult ?? 0.6;

  const multiplierText = document.getElementById("multiplierText");
  if (multiplierText) multiplierText.textContent = `${mult}×`;

  const scaledPreview = document.getElementById("scaledPreview");
  if (!scaledPreview) return;

  const meta = getSelectedHabitMeta();
  if (!meta) {
    scaledPreview.textContent = "Select a habit";
    return;
  }

  const scaled = Math.max(1, Math.round(meta.baseGoal * mult));
  scaledPreview.textContent = `${scaled} ${meta.unit}`;
}

async function loadCharts() {
  const weeklyCanvas = document.getElementById("trendChart");
  const monthlyCanvas = document.getElementById("monthlyChart");
  if ((!weeklyCanvas && !monthlyCanvas) || typeof Chart === "undefined") return;

  try {
    const res = await fetch("/api/stats", { headers: { Accept: "application/json" } });
    if (!res.ok) return;
    const data = await res.json();

    if (weeklyCanvas) {
      const ctx = weeklyCanvas.getContext("2d");
      // eslint-disable-next-line no-new
      new Chart(ctx, {
        type: "line",
        data: {
          labels: data.labels,
          datasets: [
            {
              label: "Consistency score",
              data: data.scores,
              borderColor: "rgba(122,162,255,0.95)",
              backgroundColor: "rgba(122,162,255,0.16)",
              fill: true,
              tension: 0.35,
              pointRadius: 3,
              pointHoverRadius: 5,
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { display: false },
            tooltip: {
              callbacks: {
                label: (ctx2) => `Score: ${Number(ctx2.parsed.y).toFixed(2)}`,
              },
            },
          },
          scales: {
            x: {
              grid: { color: "rgba(255,255,255,0.06)" },
              ticks: { color: "rgba(255,255,255,0.65)" },
            },
            y: {
              grid: { color: "rgba(255,255,255,0.06)" },
              ticks: { color: "rgba(255,255,255,0.65)" },
              beginAtZero: true,
            },
          },
        },
      });
    }

    if (monthlyCanvas && data.monthly) {
      const total = (data.monthly.scores || []).reduce((sum, v) => sum + Number(v || 0), 0);
      const ctxMonth = monthlyCanvas.getContext("2d");
      const colors = [
        "#FF6B3D", // High
        "#34D2FF", // Medium
        "#C9A7FF", // Low
        "#B8C0D9", // Burnout
      ];

      if (!Number.isFinite(total) || total <= 0) {
        const wrap = monthlyCanvas.parentElement;
        if (wrap) {
          const msg = document.createElement("div");
          msg.textContent = "No monthly data yet – submit some check-ins.";
          msg.style.marginTop = "8px";
          msg.style.color = "rgba(255,255,255,0.7)";
          msg.style.fontSize = "13px";
          wrap.appendChild(msg);
        }
        // Still render an empty baseline chart so layout looks stable
      }

      // eslint-disable-next-line no-new
      new Chart(ctxMonth, {
        type: "bar",
        data: {
          labels: data.monthly.labels,
          datasets: [
            {
              label: "Monthly score (last 30 days)",
              data: data.monthly.scores,
              backgroundColor: colors,
              borderColor: colors.map((c) => c),
              borderWidth: 1,
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: {
              display: false,
            },
            tooltip: {
              callbacks: {
                label: (ctx2) => `${ctx2.label}: ${Number(ctx2.parsed.y).toFixed(2)}`,
                footer: () => `Range: ${data.monthly.start_date} – ${data.monthly.end_date}`,
              },
            },
          },
          scales: {
            x: {
              grid: { color: "rgba(255,255,255,0.06)" },
              ticks: { color: "rgba(255,255,255,0.85)" },
            },
            y: {
              beginAtZero: true,
              grid: { color: "rgba(255,255,255,0.06)" },
              ticks: { color: "rgba(255,255,255,0.85)" },
            },
          },
        },
      });
    }
  } catch {
    // Silent fail for hackathon demo stability
  }
}

function wireEnergyButtons() {
  const buttons = document.querySelectorAll("[data-energy-btn]");
  if (!buttons.length) return;

  buttons.forEach((btn) => {
    btn.addEventListener("click", () => setEnergy(btn.dataset.energyBtn));
  });
}

function wireHabitSelect() {
  const select = document.querySelector('select[name="habit_id"]');
  if (!select) return;
  select.addEventListener("change", updatePreview);
}

document.addEventListener("DOMContentLoaded", () => {
  wireEnergyButtons();
  wireHabitSelect();
  setEnergy(document.body.dataset.energy || "Medium");
  loadCharts();
});

