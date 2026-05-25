/**
 * RQMS data layer — uses localStorage as the connected database.
 * LINQ-style queries implemented with Array filter/map/orderBy.
 */

const DB_KEY = "rqms_data";

const QueueStatus = {
  Waiting: "Waiting",
  Called: "Called",
  Serving: "Serving",
  Completed: "Completed",
  Skipped: "Skipped",
};

/** Default seed data (first run). */
function getSeedData() {
  return {
    users: [
      { userId: 1, username: "admin", password: "1234", fullName: "Maria Santos", role: "Admin" },
      { userId: 2, username: "staff", password: "1234", fullName: "Juan Dela Cruz", role: "Staff" },
    ],
    patients: [
      {
        queueId: 1,
        queueNumber: "R-101",
        patientName: "Ana Reyes",
        serviceType: "X-Ray",
        assignedRoom: "Room 1",
        status: QueueStatus.Waiting,
        registeredAt: new Date(Date.now() - 45 * 60000).toISOString(),
        calledAt: null,
        completedAt: null,
        trackingCode: "TRK-101",
      },
      {
        queueId: 2,
        queueNumber: "R-102",
        patientName: "Pedro Gomez",
        serviceType: "Ultrasound",
        assignedRoom: "Room 2",
        status: QueueStatus.Waiting,
        registeredAt: new Date(Date.now() - 30 * 60000).toISOString(),
        calledAt: null,
        completedAt: null,
        trackingCode: "TRK-102",
      },
      {
        queueId: 3,
        queueNumber: "R-103",
        patientName: "Liza Tan",
        serviceType: "CT Scan",
        assignedRoom: "Room 3",
        status: QueueStatus.Called,
        registeredAt: new Date(Date.now() - 20 * 60000).toISOString(),
        calledAt: new Date(Date.now() - 5 * 60000).toISOString(),
        completedAt: null,
        trackingCode: "TRK-103",
      },
      {
        queueId: 4,
        queueNumber: "R-104",
        patientName: "Rosa Lim",
        serviceType: "MRI",
        assignedRoom: "Room 4",
        status: QueueStatus.Serving,
        registeredAt: new Date(Date.now() - 10 * 60000).toISOString(),
        calledAt: new Date(Date.now() - 8 * 60000).toISOString(),
        completedAt: null,
        trackingCode: "TRK-104",
      },
    ],
    nextUserId: 3,
    nextQueueId: 5,
  };
}

/** Load full database from localStorage. */
function loadDatabase() {
  const raw = localStorage.getItem(DB_KEY);
  if (!raw) {
    const seed = getSeedData();
    saveDatabase(seed);
    return seed;
  }
  return JSON.parse(raw);
}

/** Persist database to localStorage. */
function saveDatabase(data) {
  localStorage.setItem(DB_KEY, JSON.stringify(data));
}

/** Test database connection (localStorage available). */
function testConnection() {
  try {
    localStorage.setItem("rqms_test", "1");
    localStorage.removeItem("rqms_test");
    return true;
  } catch {
    return false;
  }
}

function getDatabasePath() {
  return "Browser localStorage (key: " + DB_KEY + ")";
}

/** Validate staff login using LINQ-style query. */
function tryLogin(username, password, selectedRole) {
  const db = loadDatabase();
  const match = db.users.find(
    (u) =>
      u.username.toLowerCase() === username.toLowerCase() &&
      u.password === password &&
      u.role.toLowerCase() === selectedRole.toLowerCase()
  );

  if (!match) {
    return { success: false, message: "Invalid username, password, or role." };
  }

  sessionStorage.setItem(
    "rqms_session",
    JSON.stringify({
      username: match.username,
      fullName: match.fullName,
      role: match.role,
    })
  );

  return { success: true, message: "Login successful." };
}

function getSession() {
  const raw = sessionStorage.getItem("rqms_session");
  return raw ? JSON.parse(raw) : null;
}

function clearSession() {
  sessionStorage.removeItem("rqms_session");
}

function requireAuth() {
  if (!getSession()) {
    window.location.href = "index.html";
    return false;
  }
  return true;
}

/** Read all patients (CRUD — Read). */
function getAllPatients() {
  const db = loadDatabase();
  return [...db.patients].sort(
    (a, b) => new Date(a.registeredAt) - new Date(b.registeredAt)
  );
}

/** LINQ: active queue (not completed/skipped). */
function getActiveQueue() {
  return getAllPatients().filter(
    (p) => p.status !== QueueStatus.Completed && p.status !== QueueStatus.Skipped
  );
}

/** LINQ: current serving patient. */
function getCurrentServing() {
  const active = getActiveQueue().filter(
    (p) => p.status === QueueStatus.Serving || p.status === QueueStatus.Called
  );
  return active.sort(
    (a, b) => new Date(b.calledAt || b.registeredAt) - new Date(a.calledAt || a.registeredAt)
  )[0] || null;
}

/** LINQ: queue statistics. */
function getQueueStats() {
  const all = getAllPatients();
  const today = new Date().toDateString();

  const todayPatients = all.filter(
    (p) => new Date(p.registeredAt).toDateString() === today
  );

  return {
    waitingCount: all.filter((p) => p.status === QueueStatus.Waiting).length,
    servingCount: all.filter((p) => p.status === QueueStatus.Serving).length,
    completedToday: todayPatients.filter((p) => p.status === QueueStatus.Completed).length,
    skippedToday: todayPatients.filter((p) => p.status === QueueStatus.Skipped).length,
    totalToday: todayPatients.length,
  };
}

/** Generate next queue number. */
function generateNextQueueNumber() {
  const all = getAllPatients();
  let max = 100;
  all.forEach((p) => {
    const num = parseInt(p.queueNumber.replace("R-", ""), 10);
    if (!isNaN(num)) max = Math.max(max, num);
  });
  return "R-" + (max + 1);
}

/** CRUD — Create */
function registerPatient(patient) {
  const db = loadDatabase();
  patient.queueId = db.nextQueueId++;
  db.patients.push(patient);
  saveDatabase(db);
  return patient;
}

/** CRUD — Update */
function updatePatient(patient) {
  const db = loadDatabase();
  const index = db.patients.findIndex((p) => p.queueId === patient.queueId);
  if (index >= 0) {
    db.patients[index] = patient;
    saveDatabase(db);
  }
}

function getPatientById(queueId) {
  return getAllPatients().find((p) => p.queueId === queueId) || null;
}
