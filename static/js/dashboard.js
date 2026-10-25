/**
 * Staff dashboard — calls Python Flask API (MySQL backend).
 */

let selectedQueueId = null;
let currentUserRole = "Staff";
let callNextInProgress = false;
const defaultCatalog = {
  rooms: [
    { roomId: null, roomName: "Room 1" },
    { roomId: null, roomName: "Room 2" },
    { roomId: null, roomName: "Room 3" },
    { roomId: null, roomName: "Room 4" },
  ],
  services: [
    { serviceId: null, serviceName: "X-Ray" },
    { serviceId: null, serviceName: "Ultrasound" },
    { serviceId: null, serviceName: "CT Scan" },
    { serviceId: null, serviceName: "MRI" },
    { serviceId: null, serviceName: "Mammography" },
    { serviceId: null, serviceName: "Fluoroscopy" },
  ],
};
let currentCatalog = {
  rooms: [...defaultCatalog.rooms],
  services: [...defaultCatalog.services],
};

const registerModal = document.getElementById("modalRegister");
const configModal = document.getElementById("modalConfig");
const receiptModal = document.getElementById("modalReceipt");
let registeredReceiptPatient = null;

document.addEventListener("DOMContentLoaded", async function () {
  try {
    const session = await apiGetSession();
    if (!session) {
      window.location.href = "/";
      return;
    }
    currentUserRole = session.role || "Staff";
    document.getElementById("lblStaff").textContent =
      session.fullName + " (" + currentUserRole + ")";

    if (currentUserRole !== "Admin") {
      document.getElementById("btnManageConfig").style.display = "none";
    }
  } catch {
    window.location.href = "/";
    return;
  }

  bindNavigation();
  bindActions();
  bindModal();
  await loadCatalogs();
  await refreshDashboard();
  startClock();
  setInterval(refreshDashboard, 5000);
});

function bindNavigation() {
  document.getElementById("menuLogout").addEventListener("click", performLogout);
  document.getElementById("menuDisplay").addEventListener("click", function () {
    window.open("/display", "_blank");
  });
  document.getElementById("menuTestDb").addEventListener("click", async function () {
    const result = await apiTestConnection();
    alert(result.connected ? result.message : "Database connection failed.\n" + result.message);
  });
  document.getElementById("menuAbout").addEventListener("click", function () {
    alert(
      "RQMS — St. Paul Hospital\nPython Flask + MySQL + HTML/CSS/JavaScript"
    );
  });
}

function bindActions() {
  document.getElementById("btnRegister").addEventListener("click", openRegisterModal);
  document.getElementById("btnCallNext").addEventListener("click", callNextPatient);
  document.getElementById("btnSkip").addEventListener("click", skipPatient);
  document.getElementById("btnRecall").addEventListener("click", recallPatient);
  document.getElementById("btnComplete").addEventListener("click", completePatient);
  document.getElementById("btnManageConfig").addEventListener("click", openManageConfigModal);
  document.getElementById("btnRefresh").addEventListener("click", refreshDashboard);
  document.getElementById("btnEmergency").addEventListener("click", toggleEmergency);
  document.getElementById("btnAddRoom").addEventListener("click", addRoom);
  document.getElementById("btnAddService").addEventListener("click", addService);
}

function bindModal() {
  document.getElementById("btnModalCancel").addEventListener("click", closeRegisterModal);
  document.getElementById("btnModalSubmit").addEventListener("click", submitRegister);
  document.getElementById("btnReceiptPrint").addEventListener("click", function () {
    printQueueSlip(registeredReceiptPatient);
  });
  document.getElementById("btnReceiptClose").addEventListener("click", closeReceiptModal);
  document.getElementById("btnConfigCancel").addEventListener("click", closeManageConfigModal);
  document.getElementById("chkSmsNotify").addEventListener("change", togglePhoneField);

  registerModal.addEventListener("click", function (e) {
    if (e.target === registerModal) closeRegisterModal();
  });
  configModal.addEventListener("click", function (e) {
    if (e.target === configModal) closeManageConfigModal();
  });
  receiptModal.addEventListener("click", function (e) {
    if (e.target === receiptModal) closeReceiptModal();
  });
}

async function loadCatalogs() {
  try {
    const config = await apiGetConfiguration();
    if (config && Array.isArray(config.rooms) && Array.isArray(config.services)) {
      currentCatalog = {
        rooms: config.rooms.map((room) => ({
          roomId: room.roomId,
          roomName: room.roomName,
        })),
        services: config.services.map((service) => ({
          serviceId: service.serviceId,
          serviceName: service.serviceName,
        })),
      };
      return;
    }
  } catch {
    // fall back to defaults below
  }

  currentCatalog = {
    rooms: [...defaultCatalog.rooms],
    services: [...defaultCatalog.services],
  };
}

function populateCatalogOptions() {
  const serviceSelect = document.getElementById("cboServiceType");
  const roomSelect = document.getElementById("cboRoom");
  const services = currentCatalog.services.length
    ? currentCatalog.services
    : defaultCatalog.services;
  const rooms = currentCatalog.rooms.length ? currentCatalog.rooms : defaultCatalog.rooms;

  roomSelect.innerHTML = "";
  rooms.forEach((item) => {
    const option = document.createElement("option");
    option.value = item.roomName;
    option.textContent = item.roomName;
    roomSelect.appendChild(option);
  });

  serviceSelect.innerHTML = "";
  services.forEach((item) => {
    const option = document.createElement("option");
    option.value = item.serviceName;
    option.textContent = item.serviceName;
    serviceSelect.appendChild(option);
  });
}

function togglePhoneField() {
  const phoneWrap = document.getElementById("phoneFieldWrap");
  const checked = document.getElementById("chkSmsNotify").checked;
  phoneWrap.style.display = checked ? "block" : "none";
  if (!checked) {
    document.getElementById("tbxPatientPhone").value = "";
  }
}

async function openRegisterModal() {
  document.getElementById("lblModalError").classList.remove("visible");
  document.getElementById("tbxPatientName").value = "";
  document.getElementById("tbxPatientPhone").value = "";
  document.getElementById("chkSmsNotify").checked = false;
  document.getElementById("cboPriority").value = "Regular";
  togglePhoneField();
  await loadCatalogs();
  populateCatalogOptions();

  try {
    const num = await apiGetNextNumber();
    document.getElementById("lblQueuePreview").textContent = "Next Queue #: " + num;
  } catch {
    document.getElementById("lblQueuePreview").textContent = "Next Queue #: ---";
  }
  registerModal.classList.add("visible");
}

function closeRegisterModal() {
  registerModal.classList.remove("visible");
}

async function submitRegister() {
  const lblError = document.getElementById("lblModalError");
  lblError.classList.remove("visible");

  const name = document.getElementById("tbxPatientName").value.trim();
  const service = document.getElementById("cboServiceType").value;
  const room = document.getElementById("cboRoom").value;
  const priority = document.getElementById("cboPriority").value;
  const sms = document.getElementById("chkSmsNotify").checked;
  const patientPhone = document.getElementById("tbxPatientPhone").value.trim();

  if (stringIsNullOrEmpty(name)) {
    showModalError("Patient name is required.");
    return;
  }

  if (sms && stringIsNullOrEmpty(patientPhone)) {
    showModalError("Patient number is required when SMS notification is enabled.");
    return;
  }

  const result = await apiRegisterPatient(name, service, room, sms, patientPhone, priority);
  if (!result.success) {
    showModalError(result.message || "Registration failed.");
    return;
  }

  closeRegisterModal();
  await refreshDashboard();
  openReceiptModal(result.patient);
  if (result.emergencyNotification) {
    showEmergencySmsResult(result.emergencyNotification);
  }
}

function openReceiptModal(patient) {
  if (!patient) return;
  registeredReceiptPatient = patient;
  document.getElementById("receiptQueueNumber").textContent = patient.queueNumber || "—";
  document.getElementById("receiptPatientName").textContent = patient.patientName || "—";
  document.getElementById("receiptService").textContent = patient.serviceType || "—";
  document.getElementById("receiptRoom").textContent = patient.assignedRoom || "—";
  document.getElementById("receiptRegisteredAt").textContent =
    formatReceiptDateTime(patient.registeredAt);
  receiptModal.classList.add("visible");
}

function closeReceiptModal() {
  receiptModal.classList.remove("visible");
  registeredReceiptPatient = null;
}

function printQueueSlip(patient) {
  if (!patient) return;
  const printWindow = window.open("", "_blank", "width=700,height=700");
  if (!printWindow) {
    alert("Please allow pop-ups to print the queue slip.");
    return;
  }

  printWindow.document.write(
    "<!DOCTYPE html><html><head><title>Radiology Queue Ticket</title><style>" +
    "body{font-family:Arial,sans-serif;margin:0;padding:32px;background:#f4f6f8;color:#1e293b;}" +
    ".ticket{max-width:420px;margin:0 auto;padding:28px;border:1px solid #dbe4ee;border-radius:12px;background:#fff;text-align:center;}" +
    ".hospital{margin:0;color:#0f3460;font-size:20px;}.department{margin:6px 0 24px;color:#64748b;font-size:13px;}" +
    ".queue-label{margin:0;color:#64748b;font-size:12px;font-weight:bold;letter-spacing:1.5px;text-transform:uppercase;}" +
    ".queue-number{margin:4px 0 22px;color:#1e5aa0;font-size:56px;font-weight:bold;line-height:1.1;}" +
    ".details{padding-top:14px;border-top:1px solid #e2e8f0;text-align:left;}.details p{margin:9px 0;font-size:14px;}" +
    ".instruction{margin:22px 0 0;padding:12px;border-radius:8px;background:#e8f1fb;color:#0f3460;font-size:13px;}" +
    "@media print{body{padding:0;background:#fff}.ticket{border:0;border-radius:0;}}" +
    "</style></head><body><main class=\"ticket\">" +
    "<h1 class=\"hospital\">St. Paul Hospital</h1>" +
    "<p class=\"department\">Radiology Department · Queue Ticket</p>" +
    "<p class=\"queue-label\">Your Queue Number</p>" +
    "<p class=\"queue-number\">" + escapeHtml(patient.queueNumber) + "</p>" +
    "<section class=\"details\">" +
    "<p><strong>Patient:</strong> " + escapeHtml(patient.patientName) + "</p>" +
    "<p><strong>Service:</strong> " + escapeHtml(patient.serviceType) + "</p>" +
    "<p><strong>Room:</strong> " + escapeHtml(patient.assignedRoom || "To be announced") + "</p>" +
    "<p><strong>Registered:</strong> " + escapeHtml(formatReceiptDateTime(patient.registeredAt)) + "</p>" +
    "</section>" +
    "<p class=\"instruction\">Please wait for your queue number to be called.</p>" +
    "</main>" +
    "</body></html>"
  );
  printWindow.document.close();
  printWindow.focus();
  setTimeout(function () {
    printWindow.print();
    printWindow.onafterprint = function () { printWindow.close(); };
  }, 300);
}

function showModalError(msg) {
  document.getElementById("lblModalError").textContent = msg;
  document.getElementById("lblModalError").classList.add("visible");
  alert(msg);
}

function showConfigError(msg) {
  document.getElementById("lblConfigError").textContent = msg;
  document.getElementById("lblConfigError").classList.add("visible");
}

function clearConfigError() {
  document.getElementById("lblConfigError").classList.remove("visible");
  document.getElementById("lblConfigError").textContent = "";
}

async function openManageConfigModal() {
  clearConfigError();
  await loadCatalogs();
  renderConfigEditor();
  configModal.classList.add("visible");
}

function closeManageConfigModal() {
  configModal.classList.remove("visible");
}

function renderConfigEditor() {
  const roomsList = document.getElementById("configRoomsList");
  const servicesList = document.getElementById("configServicesList");

  roomsList.innerHTML = "";
  servicesList.innerHTML = "";

  (currentCatalog.rooms.length ? currentCatalog.rooms : defaultCatalog.rooms).forEach((room) => {
    roomsList.appendChild(createConfigRow("room", room.roomId, room.roomName));
  });
  (currentCatalog.services.length ? currentCatalog.services : defaultCatalog.services).forEach((service) => {
    servicesList.appendChild(createConfigRow("service", service.serviceId, service.serviceName));
  });
}

function createConfigRow(type, id, name) {
  const wrapper = document.createElement("div");
  wrapper.className = "config-row";

  const input = document.createElement("input");
  input.type = "text";
  input.value = name;
  if (id) {
    input.dataset.itemId = id.toString();
  }

  const button = document.createElement("button");
  button.type = "button";
  button.className = "btn btn-secondary btn-sm";
  button.textContent = "Save";
  button.addEventListener("click", async function () {
    const value = input.value.trim();
    if (!value) {
      showConfigError("Name cannot be empty.");
      return;
    }
    clearConfigError();
    const saved = type === "room"
      ? await apiSaveRoom(id || null, value)
      : await apiSaveService(id || null, value);
    if (!saved.success) {
      showConfigError(saved.message || "Could not save changes.");
      return;
    }
    await loadCatalogs();
    renderConfigEditor();
    if (registerModal.classList.contains("visible")) {
      populateCatalogOptions();
    }
  });

  wrapper.appendChild(input);
  wrapper.appendChild(button);
  return wrapper;
}

async function addRoom() {
  const input = document.getElementById("tbxAddRoom");
  const value = input.value.trim();
  if (!value) {
    showConfigError("Room name is required.");
    return;
  }
  clearConfigError();
  const saved = await apiSaveRoom(null, value);
  if (!saved.success) {
    showConfigError(saved.message || "Could not add room.");
    return;
  }
  input.value = "";
  await loadCatalogs();
  renderConfigEditor();
  if (registerModal.classList.contains("visible")) {
    populateCatalogOptions();
  }
}

async function addService() {
  const input = document.getElementById("tbxAddService");
  const value = input.value.trim();
  if (!value) {
    showConfigError("Service name is required.");
    return;
  }
  clearConfigError();
  const saved = await apiSaveService(null, value);
  if (!saved.success) {
    showConfigError(saved.message || "Could not add service.");
    return;
  }
  input.value = "";
  await loadCatalogs();
  renderConfigEditor();
  if (registerModal.classList.contains("visible")) {
    populateCatalogOptions();
  }
}

let announcementSequence = 0;

function getRoomSpeech(roomName) {
  return (roomName || "").trim();
}

function speakText(text, repetitions = 1) {
  if (!window.speechSynthesis) return;
  const sequence = ++announcementSequence;
  window.speechSynthesis.cancel();

  function speakNext(remaining) {
    if (sequence !== announcementSequence) return;
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = "en-US";
    utterance.rate = 0.95;
    utterance.pitch = 1.0;
    utterance.onend = function () {
      if (remaining > 1) {
        setTimeout(function () {
          speakNext(remaining - 1);
        }, 700);
      }
    };
    window.speechSynthesis.speak(utterance);
  }

  speakNext(repetitions);
}

async function callNextPatient() {
  if (callNextInProgress) return;
  callNextInProgress = true;
  const button = document.getElementById("btnCallNext");
  button.disabled = true;
  try {
    const result = await apiCallNext();
    if (!result.success) {
      alert(result.message);
      return;
    }
    const p = result.patient;
    const roomSpeech = getRoomSpeech(p.assignedRoom);
    const announcement = p.queueNumber + ", please proceed to room " + roomSpeech + ".";

    alert(
      'Calling queue ' + p.queueNumber + " — " + p.patientName +
      "\nRoom: " + p.assignedRoom +
      "\n\n" + announcement +
      (result.smsNotification && result.smsNotification.status === "Failed"
        ? "\n\nSMS could not be sent: " + result.smsNotification.message
        : "")
    );

    speakText(announcement, 2);
    await refreshDashboard();
  } finally {
    callNextInProgress = false;
    button.disabled = false;
  }
}

async function simulateReminder() {
  const result = await apiSimulateReminder();
  if (!result.success) {
    alert(result.message || "Unable to simulate reminder.");
    return;
  }

  const simulation = result.simulation;
  if (!simulation || !simulation.available) {
    showReminderNotice([{ message: simulation?.message || "No reminder simulation is available right now." }]);
    return;
  }

  showReminderNotice([{ message: simulation.message }]);
}

async function skipPatient() {
  if (!selectedQueueId) {
    alert("Select a patient to skip.");
    return;
  }
  const row = document.querySelector(`tr[data-queue-id="${selectedQueueId}"]`);
  const name = row ? row.cells[1].textContent : "";
  const num = row ? row.cells[0].textContent : "";
  if (!confirm("Skip " + num + " (" + name + ")?")) return;

  const result = await apiSkip(selectedQueueId);
  if (!result.success) alert(result.message);
  await refreshDashboard();
}

async function recallPatient() {
  if (!selectedQueueId) {
    alert("Select a patient to recall.");
    return;
  }
  const result = await apiRecall(selectedQueueId);
  if (!result.success) {
    alert(result.message);
    return;
  }
  alert("Patient recalled to waiting queue.");
  await refreshDashboard();
}

async function completePatient() {
  const result = await apiComplete(selectedQueueId);
  if (!result.success) {
    alert(result.message);
    return;
  }
  alert(
    "Queue " +
    result.patient.queueNumber +
    " marked complete.\nResult status: Processing (manage under Results Release)."
  );
  await refreshDashboard();
}

async function refreshDashboard() {
  try {
    const data = await apiGetDashboard();
    const reminderResult = await apiDispatchReminders();
    renderDashboard(data);
    showReminderNotice(reminderResult.reminders || []);
  } catch (err) {
    console.error(err);
  }
}

async function toggleEmergency() {
  const emergency = document.getElementById("btnEmergency").dataset.active === "true";
  const result = await apiSetEmergency(!emergency);
  if (!result.success) {
    alert(result.message || "Unable to update emergency mode.");
    return;
  }
  renderEmergency(result.emergency);
  if (result.smsNotification) {
    showEmergencySmsResult(result.smsNotification);
  }
}

function showEmergencySmsResult(notification) {
  const details = (notification.failures || [])
    .map(function (failure) {
      return failure.queueNumber + ": " + failure.message;
    })
    .join("\n");
  const summary = notification.message +
    "\nSent: " + notification.sent +
    "\nFailed: " + notification.failed +
    "\nSkipped (not opted in/invalid number): " + notification.skipped;
  alert(summary + (details ? "\n\n" + details : ""));
}

function showReminderNotice(reminders) {
  const notice = document.getElementById("reminderNotice");
  if (!reminders.length) {
    notice.classList.add("hidden");
    notice.textContent = "";
    return;
  }

  notice.textContent = reminders.map((item) => item.message).join(" ");
  notice.classList.remove("hidden");
  clearTimeout(showReminderNotice.timerId);
  showReminderNotice.timerId = setTimeout(function () {
    notice.classList.add("hidden");
    notice.textContent = "";
  }, 7000);
}

function renderDashboard(data) {
  const queue = data.activeQueue || [];
  const stats = data.stats || {};
  const current = data.current;
  renderEmergency(data.emergency);

  document.getElementById("lblNowServing").textContent = current ? current.queueNumber : "---";
  document.getElementById("lblNowRoom").textContent = current ? current.assignedRoom : "---";
  document.getElementById("lblNowPatient").textContent = current ? current.patientName : "No active patient";
  document.getElementById("lblNowService").textContent = current ? current.serviceType : "---";

  document.getElementById("lblStatWaiting").textContent = (stats.waitingCount ?? 0).toString();
  document.getElementById("lblStatServing").textContent = (stats.servingCount ?? 0).toString();
  document.getElementById("lblStatCompleted").textContent = (stats.completedToday ?? 0).toString();
  document.getElementById("lblStatTotal").textContent = (stats.totalToday ?? 0).toString();

  const tbody = document.getElementById("queueTableBody");
  tbody.innerHTML = "";

  queue.forEach(function (p) {
    const tr = document.createElement("tr");
    tr.dataset.queueId = p.queueId.toString();
    if (selectedQueueId === p.queueId) tr.classList.add("selected");

    tr.innerHTML =
      "<td>" + escapeHtml(p.queueNumber) + "</td>" +
      "<td>" + escapeHtml(p.patientName) + "</td>" +
      "<td>" + escapeHtml(p.serviceType) + "</td>" +
      "<td>" + escapeHtml(p.assignedRoom) + "</td>" +
      '<td><span class="status-badge status-' + p.status.toLowerCase() + '">' + escapeHtml(p.status) + "</span></td>" +
      "<td>" + formatTime(p.registeredAt) + "</td>" +
      "<td>" + escapeHtml(p.trackingCode) + "</td>";

    tr.addEventListener("click", function () {
      selectedQueueId = p.queueId;
      document.querySelectorAll("#queueTableBody tr").forEach((r) => r.classList.remove("selected"));
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
      li.textContent = p.queueNumber + " — " + p.patientName + " (" + p.serviceType + ")";
      upcoming.appendChild(li);
    });
}

function renderEmergency(emergency) {
  const active = Boolean(emergency && emergency.active);
  const button = document.getElementById("btnEmergency");
  const buttonLabel = button.querySelector(".action-label");
  const status = document.getElementById("emergencyStatus");
  const times = document.getElementById("emergencyTimes");
  button.dataset.active = active.toString();
  buttonLabel.textContent = active ? "End Emergency" : "Emergency Case";
  button.classList.toggle("btn-emergency-active", active);
  status.textContent = active
    ? "Status: 🚨 EMERGENCY IN PROGRESS"
    : "Emergency Mode is inactive";
  times.textContent = active && emergency.activatedAt
    ? "Started " + formatTime(emergency.activatedAt)
    : "";
}

async function performLogout() {
  if (!confirm("Log out of RQMS?")) return;
  await apiLogout();
  window.location.href = "/";
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

function formatTime(iso) {
  return new Date(iso).toLocaleTimeString("en-PH", { hour: "2-digit", minute: "2-digit" });
}

function formatReceiptDateTime(iso) {
  if (!iso) return "—";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleString("en-PH", {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}
