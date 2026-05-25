/**
 * RQMS API client — Python Flask + MySQL backend.
 */

const QueueStatus = {
  Waiting: "Waiting",
  Called: "Called",
  Serving: "Serving",
  Completed: "Completed",
  Skipped: "Skipped",
};

async function apiFetch(url, options = {}) {
  const defaults = {
    headers: { "Content-Type": "application/json" },
    credentials: "same-origin",
  };
  const res = await fetch(url, { ...defaults, ...options });
  const data = await res.json().catch(() => ({}));
  if (res.status === 401) {
    window.location.href = "/";
    throw new Error("Session expired.");
  }
  return { ok: res.ok, status: res.status, data };
}

async function apiLogin(username, password, role) {
  const { ok, data } = await apiFetch("/api/login", {
    method: "POST",
    body: JSON.stringify({ username, password, role }),
  });
  return { success: ok && data.success, message: data.message, user: data.user };
}

async function apiLogout() {
  await apiFetch("/api/logout", { method: "POST" });
}

async function apiGetSession() {
  const { data } = await apiFetch("/api/session");
  return data.authenticated ? data.user : null;
}

async function apiTestConnection() {
  const { ok, data } = await apiFetch("/api/health");
  return { connected: data.connected, message: data.message };
}

async function apiGetDashboard() {
  const { data } = await apiFetch("/api/queue/dashboard");
  return data;
}

async function apiGetDisplay() {
  const { data } = await apiFetch("/api/queue/display");
  return data;
}

async function apiGetConfiguration() {
  const { data } = await apiFetch("/api/admin/config");
  return data;
}

async function apiGetNextNumber() {
  const { data } = await apiFetch("/api/queue/next-number");
  return data.queueNumber;
}

async function apiRegisterPatient(patientName, serviceType, assignedRoom, smsNotify, patientPhone, patientPriority) {
  const { ok, data } = await apiFetch("/api/queue/register", {
    method: "POST",
    body: JSON.stringify({ patientName, serviceType, assignedRoom, smsNotify, patientPhone, patientPriority }),
  });
  return { success: ok && data.success, message: data.message, patient: data.patient };
}

async function apiDispatchReminders() {
  const { ok, data } = await apiFetch("/api/queue/reminders", { method: "POST" });
  return { success: ok && data.success, reminders: data.reminders || [] };
}

async function apiSimulateReminder() {
  const { ok, data } = await apiFetch("/api/queue/reminders/simulate", { method: "POST" });
  return { success: ok && data.success, simulation: data.simulation || null };
}

async function apiSaveRoom(roomId, roomName) {
  const { ok, data } = await apiFetch("/api/admin/config/rooms", {
    method: "POST",
    body: JSON.stringify({ roomId: roomId || null, roomName }),
  });
  return { success: ok && data.success, message: data.message, rooms: data.rooms };
}

async function apiSaveService(serviceId, serviceName) {
  const { ok, data } = await apiFetch("/api/admin/config/services", {
    method: "POST",
    body: JSON.stringify({ serviceId: serviceId || null, serviceName }),
  });
  return { success: ok && data.success, message: data.message, services: data.services };
}

async function apiCallNext() {
  const { ok, data } = await apiFetch("/api/queue/call-next", { method: "POST" });
  return { success: ok && data.success, message: data.message, patient: data.patient };
}

async function apiSkip(queueId) {
  const { ok, data } = await apiFetch(`/api/queue/${queueId}/skip`, { method: "POST" });
  return { success: ok && data.success, message: data.message };
}

async function apiRecall(queueId) {
  const { ok, data } = await apiFetch(`/api/queue/${queueId}/recall`, { method: "POST" });
  return { success: ok && data.success, message: data.message };
}

async function apiComplete(queueId) {
  const { ok, data } = await apiFetch("/api/queue/complete", {
    method: "POST",
    body: JSON.stringify({ queueId: queueId || null }),
  });
  return { success: ok && data.success, message: data.message, patient: data.patient };
}

async function apiGetStaffAnalytics() {
  const { data } = await apiFetch("/api/analytics/staff");
  return data;
}

async function apiGetResultsList(filter) {
  const q = filter && filter !== "All" ? "?filter=" + encodeURIComponent(filter) : "?filter=All";
  const { data } = await apiFetch("/api/results" + q);
  return data;
}

async function apiMarkResultReady(queueId, sendNotification) {
  const { ok, data } = await apiFetch("/api/results/" + queueId + "/ready", {
    method: "POST",
    body: JSON.stringify({ sendNotification: sendNotification }),
  });
  return {
    success: ok && data.success,
    message: data.message,
    patient: data.patient,
    notificationMessage: data.notificationMessage,
  };
}

async function apiMarkResultReleased(queueId) {
  const { ok, data } = await apiFetch("/api/results/" + queueId + "/released", {
    method: "POST",
  });
  return { success: ok && data.success, message: data.message };
}

async function apiNotifyResult(queueId) {
  const { ok, data } = await apiFetch("/api/results/" + queueId + "/notify", {
    method: "POST",
  });
  return {
    success: ok && data.success,
    message: data.message,
    notificationMessage: data.notificationMessage,
  };
}

function stringIsNullOrEmpty(value) {
  return value === null || value === undefined || value === "";
}
