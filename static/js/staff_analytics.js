/**
 * AHM Staff Analytics — loads report from Flask /api/analytics/staff
 */

document.addEventListener("DOMContentLoaded", async function () {
  const session = await apiGetSession();
  if (!session) {
    window.location.href = "/";
    return;
  }

  document.getElementById("menuLogout").addEventListener("click", async function () {
    if (!confirm("Log out of RQMS?")) return;
    await apiLogout();
    window.location.href = "/";
  });

  document.getElementById("menuDisplay").addEventListener("click", function () {
    window.open("/display", "_blank");
  });

  document.getElementById("btnRefreshReport").addEventListener("click", loadReport);

  startClock();
  await loadReport();
});

async function loadReport() {
  try {
    const data = await apiGetStaffAnalytics();
    renderReport(data);
  } catch (err) {
    console.error(err);
    alert("Could not load analytics. Check Flask server and MySQL.");
  }
}

function renderReport(data) {
  const s = data.summary || {};

  document.getElementById("lblReportDate").textContent =
    "Report date: " + (data.reportDate || "—");

  document.getElementById("lblTotalToday").textContent = (s.totalToday ?? 0).toString();
  document.getElementById("lblCompletedToday").textContent = (s.completedToday ?? 0).toString();
  document.getElementById("lblSkippedToday").textContent = (s.skippedToday ?? 0).toString();
  document.getElementById("lblWaitingNow").textContent = (s.waitingNow ?? 0).toString();
  document.getElementById("lblAvgWait").textContent = (s.avgWaitMinutes ?? 0).toString();
  document.getElementById("lblCompletionRate").textContent =
    (s.completionRate ?? 0).toString() + "%";

  renderBarChart("chartByService", data.byService || []);
  renderBarChart("chartByRoom", data.byRoom || []);
  renderBarChart("chartByStatus", data.byStatus || []);
  renderHourlyChart("chartHourly", data.hourlyVolume || []);
  renderRecentTable(data.recentCompleted || []);
}

function renderBarChart(containerId, items) {
  const el = document.getElementById(containerId);
  el.innerHTML = "";

  if (!items.length) {
    el.innerHTML = '<p class="analytics-empty">No data for this report.</p>';
    return;
  }

  const max = Math.max(...items.map((i) => i.count), 1);

  items.forEach(function (item) {
    const row = document.createElement("div");
    row.className = "bar-row";
    const pct = Math.round((item.count / max) * 100);
    row.innerHTML =
      '<span class="bar-label">' +
      escapeHtml(item.label) +
      '</span><div class="bar-track"><div class="bar-fill" style="width:' +
      pct +
      '%"></div></div><span class="bar-count">' +
      item.count.toString() +
      "</span>";
    el.appendChild(row);
  });
}

function renderHourlyChart(containerId, items) {
  const el = document.getElementById(containerId);
  el.innerHTML = "";

  if (!items.length) {
    el.innerHTML = '<p class="analytics-empty">No hourly data.</p>';
    return;
  }

  const max = Math.max(...items.map((i) => i.count), 1);
  const wrap = document.createElement("div");
  wrap.className = "hourly-bars";

  items.forEach(function (item) {
    const col = document.createElement("div");
    col.className = "hourly-col";
    const height = Math.max(8, Math.round((item.count / max) * 120));
    col.innerHTML =
      '<div class="hourly-bar" style="height:' +
      height +
      'px" title="' +
      item.count +
      ' patients"></div><span class="hourly-label">' +
      escapeHtml(item.hour) +
      "</span>";
    wrap.appendChild(col);
  });

  el.appendChild(wrap);
}

function renderRecentTable(patients) {
  const tbody = document.getElementById("tblRecentCompleted");
  tbody.innerHTML = "";

  if (!patients.length) {
    const tr = document.createElement("tr");
    tr.innerHTML = '<td colspan="5">No completed patients today.</td>';
    tbody.appendChild(tr);
    return;
  }

  patients.forEach(function (p) {
    const tr = document.createElement("tr");
    tr.innerHTML =
      "<td>" +
      escapeHtml(p.queueNumber) +
      "</td><td>" +
      escapeHtml(p.patientName) +
      "</td><td>" +
      escapeHtml(p.serviceType) +
      "</td><td>" +
      escapeHtml(p.assignedRoom) +
      "</td><td>" +
      formatDateTime(p.completedAt) +
      "</td>";
    tbody.appendChild(tr);
  });
}

function startClock() {
  function tick() {
    document.getElementById("lblClock").textContent = new Date().toLocaleString("en-PH", {
      weekday: "long",
      year: "numeric",
      month: "long",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  }
  tick();
  setInterval(tick, 1000);
}

function formatDateTime(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("en-PH", {
    hour: "2-digit",
    minute: "2-digit",
  });
}

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}
