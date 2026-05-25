/**
 * Staff dashboard — queue CRUD, actions, statistics.
 */

let selectedQueueId = null;

document.addEventListener("DOMContentLoaded", function () {
  if (!requireAuth()) return;

  const session = getSession();
  document.getElementById("lblStaff").textContent =
    session.fullName + " (" + session.role + ")";

  bindNavigation();
  bindActions();
  bindModal();
  refreshDashboard();
  startClock();

  setInterval(refreshDashboard, 5000);
});

function bindNavigation() {
  document.getElementById("menuLogout").addEventListener("click", performLogout);
  document.getElementById("menuDisplay").addEventListener("click", function () {
    window.open("display.html", "_blank");
  });
  document.getElementById("menuTestDb").addEventListener("click", function () {
    const ok = testConnection();
    alert(
      ok
        ? "Database connected: " + getDatabasePath()
        : "Database connection failed."
    );
  });
  document.getElementById("menuAbout").addEventListener("click", function () {
    alert(
      "Radiology Queue Management and Patient Notification System (RQMS)\n" +
        "St. Paul Hospital — Capstone Prototype\n\n" +
        "HTML, JavaScript, External CSS"
    );
  });
}

function bindActions() {
  document.getElementById("btnRegister").addEventListener("click", openRegisterModal);
  document.getElementById("btnCallNext").addEventListener("click", callNextPatient);
  document.getElementById("btnSkip").addEventListener("click", skipPatient);
  document.getElementById("btnRecall").addEventListener("click", recallPatient);
  document.getElementById("btnComplete").addEventListener("click", completePatient);
  document.getElementById("btnRefresh").addEventListener("click", refreshDashboard);
}

function bindModal() {
  const overlay = document.getElementById("modalRegister");
  document.getElementById("btnModalCancel").addEventListener("click", closeRegisterModal);
  document.getElementById("btnModalSubmit").addEventListener("click", submitRegister);

  overlay.addEventListener("click", function (e) {
    if (e.target === overlay) closeRegisterModal();
  });

  document.getElementById("modalRegister").addEventListener("show", function () {
    document.getElementById("lblQueuePreview").textContent =
      "Next Queue #: " + generateNextQueueNumber();
  });
}

function openRegisterModal() {
  document.getElementById("lblModalError").classList.remove("visible");
  document.getElementById("tbxPatientName").value = "";
  document.getElementById("cboServiceType").selectedIndex = 0;
  document.getElementById("cboRoom").selectedIndex = 0;
  document.getElementById("chkSmsNotify").checked = false;
  document.getElementById("lblQueuePreview").textContent =
    "Next Queue #: " + generateNextQueueNumber();
  document.getElementById("modalRegister").classList.add("visible");
}

function closeRegisterModal() {
  document.getElementById("modalRegister").classList.remove("visible");
}

function submitRegister() {
  const lblError = document.getElementById("lblModalError");
  lblError.classList.remove("visible");

  const name = document.getElementById("tbxPatientName").value.trim();
  const service = document.getElementById("cboServiceType").value;
  const room = document.getElementById("cboRoom").value;

  if (stringIsNullOrEmpty(name)) {
    showModalError("Patient name is required.");
    return;
  }

  const queueNumber = generateNextQueueNumber();
  const patient = {
    queueNumber: queueNumber,
    patientName: name,
    serviceType: service,
    assignedRoom: room,
    status: QueueStatus.Waiting,
    registeredAt: new Date().toISOString(),
    calledAt: null,
    completedAt: null,
    trackingCode: "TRK-" + queueNumber.replace("R-", ""),
  };

  registerPatient(patient);
  closeRegisterModal();
  refreshDashboard();

  const smsNote = document.getElementById("chkSmsNotify").checked
    ? "\nSMS notification queued."
    : "";

  alert(
    "Patient registered.\nQueue: " +
      queueNumber +
      "\nTracking: " +
      patient.trackingCode +
      smsNote
  );
}

function showModalError(msg) {
  const lbl = document.getElementById("lblModalError");
  lbl.textContent = msg;
  lbl.classList.add("visible");
  alert(msg);
}

function callNextPatient() {
  const queue = getActiveQueue();
  const next = queue.find((p) => p.status === QueueStatus.Waiting);

  if (!next) {
    alert("No waiting patients in queue.");
    return;
  }

  queue
    .filter((p) => p.status === QueueStatus.Called || p.status === QueueStatus.Serving)
    .forEach((p) => {
      p.status = QueueStatus.Waiting;
      updatePatient(p);
    });

  next.status = QueueStatus.Called;
  next.calledAt = new Date().toISOString();
  updatePatient(next);

  alert(
    'Calling queue ' +
      next.queueNumber +
      " — " +
      next.patientName +
      "\nRoom: " +
      next.assignedRoom +
      '\n[Audio: "Now serving ' +
      next.queueNumber +
      '"]'
  );

  refreshDashboard();
}

function skipPatient() {
  const patient = getSelectedPatient();
  if (!patient) {
    alert("Select a patient to skip.");
    return;
  }

  if (!confirm("Skip " + patient.queueNumber + " (" + patient.patientName + ")?")) {
    return;
  }

  patient.status = QueueStatus.Skipped;
  updatePatient(patient);
  refreshDashboard();
}

function recallPatient() {
  const patient = getSelectedPatient();
  if (!patient) {
    alert("Select a patient to recall.");
    return;
  }

  patient.status = QueueStatus.Waiting;
  patient.calledAt = null;
  patient.completedAt = null;
  updatePatient(patient);

  alert(patient.queueNumber + " recalled to waiting queue.");
  refreshDashboard();
}

function completePatient() {
  let patient = getSelectedPatient();
  if (!patient) patient = getCurrentServing();

  if (!patient) {
    alert("Select a patient or call next before completing.");
    return;
  }

  patient.status = QueueStatus.Completed;
  patient.completedAt = new Date().toISOString();
  if (!patient.calledAt) patient.calledAt = new Date().toISOString();
  updatePatient(patient);

  alert("Queue " + patient.queueNumber + " marked complete.");
  refreshDashboard();
}

function getSelectedPatient() {
  if (!selectedQueueId) return null;
  return getPatientById(selectedQueueId);
}

function refreshDashboard() {
  const queue = getActiveQueue();
  const stats = getQueueStats();
  const current = getCurrentServing();

  document.getElementById("lblNowServing").textContent = current
    ? current.queueNumber
    : "---";
  document.getElementById("lblNowRoom").textContent = current
    ? current.assignedRoom
    : "---";
  document.getElementById("lblNowPatient").textContent = current
    ? current.patientName
    : "No active patient";
  document.getElementById("lblNowService").textContent = current
    ? current.serviceType
    : "---";

  document.getElementById("lblStatWaiting").textContent = stats.waitingCount.toString();
  document.getElementById("lblStatServing").textContent = stats.servingCount.toString();
  document.getElementById("lblStatCompleted").textContent = stats.completedToday.toString();
  document.getElementById("lblStatTotal").textContent = stats.totalToday.toString();

  const tbody = document.getElementById("queueTableBody");
  tbody.innerHTML = "";

  queue.forEach(function (p) {
    const tr = document.createElement("tr");
    tr.dataset.queueId = p.queueId.toString();
    if (selectedQueueId === p.queueId) tr.classList.add("selected");

    tr.innerHTML =
      "<td>" +
      escapeHtml(p.queueNumber) +
      "</td>" +
      "<td>" +
      escapeHtml(p.patientName) +
      "</td>" +
      "<td>" +
      escapeHtml(p.serviceType) +
      "</td>" +
      "<td>" +
      escapeHtml(p.assignedRoom) +
      "</td>" +
      '<td><span class="status-badge status-' +
      p.status.toLowerCase() +
      '">' +
      escapeHtml(p.status) +
      "</span></td>" +
      "<td>" +
      formatTime(p.registeredAt) +
      "</td>" +
      "<td>" +
      escapeHtml(p.trackingCode) +
      "</td>";

    tr.addEventListener("click", function () {
      selectedQueueId = p.queueId;
      document.querySelectorAll("#queueTableBody tr").forEach((r) =>
        r.classList.remove("selected")
      );
      tr.classList.add("selected");
    });

    tbody.appendChild(tr);
  });

  const upcoming = document.getElementById("lstUpcoming");
  upcoming.innerHTML = "";
  queue
    .filter((p) => p.status === QueueStatus.Waiting)
    .slice(0, 5)
    .forEach(function (p) {
      const li = document.createElement("li");
      li.textContent =
        p.queueNumber + " — " + p.patientName + " (" + p.serviceType + ")";
      upcoming.appendChild(li);
    });
}

function performLogout() {
  if (!confirm("Log out of RQMS?")) return;
  clearSession();
  window.location.href = "index.html";
}

function startClock() {
  function tick() {
    document.getElementById("lblClock").textContent = new Date().toLocaleString(
      "en-PH",
      {
        weekday: "long",
        year: "numeric",
        month: "long",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
      }
    );
  }
  tick();
  setInterval(tick, 1000);
}

function stringIsNullOrEmpty(value) {
  return value === null || value === undefined || value === "";
}

function formatTime(iso) {
  return new Date(iso).toLocaleTimeString("en-PH", {
    hour: "2-digit",
    minute: "2-digit",
  });
}

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}
