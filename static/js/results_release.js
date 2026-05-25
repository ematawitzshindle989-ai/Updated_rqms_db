/**
 * Results Ready for Release — staff list and patient notifications.
 */

let currentFilter = "All";
let selectedQueueId = null;
let allResults = [];

document.addEventListener("DOMContentLoaded", async function () {
  const session = await apiGetSession();
  if (!session) {
    window.location.href = "/";
    return;
  }

  document.querySelectorAll(".filter-tab").forEach(function (btn) {
    btn.addEventListener("click", async function () {
      document.querySelectorAll(".filter-tab").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      currentFilter = btn.dataset.filter;
      await loadResults();
    });
  });

  document.getElementById("searchResults").addEventListener("input", function () {
    renderTable(filterResults(allResults));
  });

  document.getElementById("btnRefreshList").addEventListener("click", loadResults);
  document.getElementById("menuLogout").addEventListener("click", async function () {
    if (!confirm("Log out?")) return;
    await apiLogout();
    window.location.href = "/";
  });
  document.getElementById("menuDisplay").addEventListener("click", function () {
    window.open("/display", "_blank");
  });

  startClock();
  await loadResults();
  setInterval(loadResults, 10000);
});

async function loadResults() {
  try {
    const data = await apiGetResultsList(currentFilter);
    allResults = data.results || [];
    renderCounts(data.counts || {});
    renderTable(filterResults(allResults));
  } catch (err) {
    console.error(err);
  }
}

function filterResults(results) {
  const query = document.getElementById("searchResults").value.trim().toLowerCase();
  if (!query) {
    return results;
  }

  return results.filter(function (p) {
    return [p.queueNumber, p.patientName, p.serviceType, p.resultStatus]
      .join(" ")
      .toLowerCase()
      .includes(query);
  });
}

function renderCounts(c) {
  document.getElementById("lblCountReady").textContent = (c.readyForRelease ?? 0).toString();
  document.getElementById("lblCountProcessing").textContent = (c.processing ?? 0).toString();
  document.getElementById("lblCountReleased").textContent = (c.released ?? 0).toString();
  document.getElementById("lblCountTotal").textContent = (c.total ?? 0).toString();
}

function renderTable(results) {
  const tbody = document.getElementById("tblResults");
  tbody.innerHTML = "";

  if (!results.length) {
    tbody.innerHTML =
      '<tr><td colspan="8">No records for this filter.</td></tr>';
    return;
  }

  results.forEach(function (p) {
    const tr = document.createElement("tr");
    if (selectedQueueId === p.queueId) tr.classList.add("selected");

    const statusClass = resultStatusClass(p.resultStatus);
    const notified = p.resultNotifySent
      ? '<span class="notify-yes">Yes</span>'
      : '<span class="notify-no">No</span>';

    tr.innerHTML =
      "<td>" + escapeHtml(p.queueNumber) + "</td>" +
      "<td>" + escapeHtml(p.patientName) + "</td>" +
      "<td>" + escapeHtml(p.serviceType) + "</td>" +
      "<td>" + formatDateTime(p.completedAt) + "</td>" +
      '<td><span class="result-badge ' + statusClass + '">' + escapeHtml(p.resultStatus) + "</span></td>" +
      "<td>" + formatDateTime(p.resultReadyAt) + "</td>" +
      "<td>" + notified + "</td>" +
      '<td class="action-cell">' + buildActions(p) + "</td>";

    tr.addEventListener("click", function (e) {
      if (e.target.tagName === "BUTTON") return;
      selectedQueueId = p.queueId;
      document.querySelectorAll("#tblResults tr").forEach((r) => r.classList.remove("selected"));
      tr.classList.add("selected");
    });

    tbody.appendChild(tr);
  });

  bindActionButtons();
}

function buildActions(p) {
  let html = "";
  if (p.resultStatus === "Processing") {
    html +=
      '<button type="button" class="btn btn-sm btn-success btn-mark-ready" data-id="' +
      p.queueId +
      '">Mark Ready</button>';
  }
  if (p.resultStatus === "Ready for Release") {
    html +=
      '<button type="button" class="btn btn-sm btn-primary btn-notify" data-id="' +
      p.queueId +
      '">Notify Patient</button> ';
    html +=
      '<button type="button" class="btn btn-sm btn-secondary btn-released" data-id="' +
      p.queueId +
      '">Mark Released</button>';
  }
  if (!html) html = '<span class="stat-label">—</span>';
  return html;
}

function bindActionButtons() {
  document.querySelectorAll(".btn-mark-ready").forEach(function (btn) {
    btn.addEventListener("click", async function () {
      const id = parseInt(btn.dataset.id, 10);
      const sendSms = confirm(
        "Mark results READY FOR RELEASE and send SMS notification to patient?"
      );
      const result = await apiMarkResultReady(id, sendSms);
      if (!result.success) {
        alert(result.message);
        return;
      }
      if (result.notificationMessage) {
        alert("Results marked ready.\n\n" + result.notificationMessage);
      } else {
        alert("Results marked ready for release.");
      }
      await loadResults();
    });
  });

  document.querySelectorAll(".btn-notify").forEach(function (btn) {
    btn.addEventListener("click", async function () {
      const id = parseInt(btn.dataset.id, 10);
      const result = await apiNotifyResult(id);
      if (!result.success) {
        alert(result.message);
        return;
      }
      alert("Notification sent:\n\n" + (result.notificationMessage || "SMS queued."));
      await loadResults();
    });
  });

  document.querySelectorAll(".btn-released").forEach(function (btn) {
    btn.addEventListener("click", async function () {
      const id = parseInt(btn.dataset.id, 10);
      if (!confirm("Confirm patient has claimed / released their results?")) return;
      const result = await apiMarkResultReleased(id);
      if (!result.success) {
        alert(result.message);
        return;
      }
      alert("Result marked as released (claimed).");
      await loadResults();
    });
  });
}

function resultStatusClass(status) {
  if (status === "Ready for Release") return "result-ready";
  if (status === "Processing") return "result-processing";
  if (status === "Released") return "result-released";
  return "";
}

function startClock() {
  function tick() {
    document.getElementById("lblClock").textContent = new Date().toLocaleString("en-PH", {
      weekday: "long", year: "numeric", month: "long", day: "numeric",
      hour: "2-digit", minute: "2-digit", second: "2-digit",
    });
  }
  tick();
  setInterval(tick, 1000);
}

function formatDateTime(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("en-PH", {
    month: "short", day: "numeric", hour: "2-digit", minute: "2-digit",
  });
}

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}
