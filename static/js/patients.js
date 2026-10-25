document.addEventListener("DOMContentLoaded", async function () {
  const searchInput = document.getElementById("patientSearch");
  let registeredPatients = [];

  const session = await apiGetSession();
  if (!session) {
    window.location.href = "/";
    return;
  }

  document.getElementById("lblStaff").textContent =
    session.fullName + " (" + (session.role || "Staff") + ")";
  document.getElementById("menuDisplay").addEventListener("click", function () {
    window.open("/display", "_blank");
  });
  document.getElementById("menuTestDb").addEventListener("click", async function () {
    const result = await apiTestConnection();
    alert(result.connected ? result.message : "Database connection failed.\n" + result.message);
  });
  document.getElementById("menuAbout").addEventListener("click", function () {
    alert("RQMS — St. Paul Hospital\nPython Flask + MySQL + HTML/CSS/JavaScript");
  });
  document.getElementById("menuLogout").addEventListener("click", async function () {
    if (!confirm("Log out?")) return;
    await apiLogout();
    window.location.href = "/";
  });
  searchInput.addEventListener("input", function () {
    renderPatients(registeredPatients, searchInput.value);
  });

  startClock();
  await loadPatients();
  setInterval(loadPatients, 5000);

  async function loadPatients() {
    try {
      const data = await apiGetRegisteredPatients();
      registeredPatients = data.patients || [];
      renderPatients(registeredPatients, searchInput.value);
    } catch (err) {
      console.error("Registered patient list refresh failed:", err);
    }
  }
});

function renderPatients(patients, searchTerm = "") {
  const tbody = document.getElementById("registeredPatientsBody");
  tbody.innerHTML = "";

  if (!patients.length) {
    tbody.innerHTML = '<tr><td colspan="7" class="empty-patients">No registered patients found.</td></tr>';
    return;
  }

  const normalizedSearch = searchTerm.trim().toLocaleLowerCase();
  const matchingPatients = patients.filter(function (patient) {
    const searchableValues = [
      patient.queueNumber,
      patient.patientName,
      patient.serviceType,
      patient.assignedRoom,
      formatDateTime(patient.registeredAt),
      patient.patientPhone,
      patient.smsEnabled ? "SMS Enabled" : "SMS Disabled",
      patient.reminderStatus,
    ];
    return searchableValues.some((value) =>
      String(value || "").toLocaleLowerCase().includes(normalizedSearch)
    );
  });

  if (!matchingPatients.length) {
    tbody.innerHTML = '<tr><td colspan="7" class="empty-patients">No patients match your search.</td></tr>';
    return;
  }

  matchingPatients.forEach(function (patient) {
    const row = document.createElement("tr");
    row.innerHTML =
      "<td>" + escapeHtml(patient.queueNumber) + "</td>" +
      "<td>" + escapeHtml(patient.patientName) + "</td>" +
      "<td>" + escapeHtml(patient.serviceType) + "</td>" +
      "<td>" + escapeHtml(patient.assignedRoom) + "</td>" +
      "<td>" + formatDateTime(patient.registeredAt) + "</td>" +
      "<td>" + (patient.smsEnabled ? escapeHtml(patient.patientPhone || "—") : "—") + "</td>" +
      '<td><span class="' + (patient.smsEnabled ? "sms-enabled" : "sms-disabled") + '">' +
        (patient.smsEnabled ? "SMS Enabled" : "SMS Disabled") + "</span>" +
        (patient.smsEnabled
          ? '<small class="sms-reminder-status">Reminder ' +
            escapeHtml(patient.reminderStatus || "Not Sent") + "</small>"
          : "") +
        "</td>";
    tbody.appendChild(row);
  });
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
    month: "short", day: "numeric", year: "numeric",
    hour: "2-digit", minute: "2-digit",
  });
}

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text == null ? "" : text;
  return div.innerHTML;
}
