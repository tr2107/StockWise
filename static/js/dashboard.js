// dashboard.js - draws the "stock by category" chart with Chart.js.
// window.CATEGORY_DATA is filled in by the dashboard template from the database.
(function () {
  var canvas = document.getElementById("category-chart");
  if (!canvas) { return; }

  // If Chart.js could not be downloaded (for example, no internet), show a plain list instead.
  if (typeof Chart === "undefined") {
    canvas.parentElement.hidden = true;
    var fallback = document.getElementById("chart-fallback");
    if (fallback) { fallback.hidden = false; }
    return;
  }

  var data = window.CATEGORY_DATA || [];
  new Chart(canvas, {
    type: "bar",
    data: {
      labels: data.map(function (d) { return d.category; }),
      datasets: [{
        label: "Units in stock",
        data: data.map(function (d) { return d.units; }),
        backgroundColor: "#4f46e5",
        borderRadius: 6,
        maxBarThickness: 48
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        y: { beginAtZero: true, ticks: { precision: 0 }, grid: { color: "#eef0f6" } },
        x: { grid: { display: false } }
      }
    }
  });
})();
