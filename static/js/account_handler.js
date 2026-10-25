document.addEventListener("DOMContentLoaded", async function () {
  try {
    const user = await apiGetSession();
    if (!user) {
      window.location.href = "/";
      return;
    }
    if (user.role !== "Admin") {
      window.location.href = "/dashboard";
      return;
    }

    document.getElementById("menuLogout").addEventListener("click", async function () {
      if (!confirm("Log out of RQMS?")) return;
      await apiLogout();
      window.location.href = "/";
    });

    const createForm = document.getElementById("createStaffForm");
    const editForm = document.getElementById("editStaffForm");
    const resetForm = document.getElementById("resetPasswordForm");
    const tbody = document.getElementById("staffAccountsBody");
    let editingUserId = null;
    let resettingUserId = null;

    createForm.addEventListener("submit", async function (event) {
      event.preventDefault();
      clearMessage("accountMessage");
      const formData = new FormData(createForm);
      try {
        await accountRequest("/api/admin/staff", {
          method: "POST",
          body: JSON.stringify({
            fullName: formData.get("fullName"),
            username: formData.get("username"),
            password: formData.get("password"),
          }),
        });
        createForm.reset();
        showMessage("accountMessage", "Staff account created.", true);
        await loadStaffAccounts();
      } catch (err) {
        showMessage("accountMessage", err.message);
      }
    });

    editForm.addEventListener("submit", async function (event) {
      event.preventDefault();
      if (editingUserId === null) return;
      const formData = new FormData(editForm);
      try {
        await accountRequest("/api/admin/staff/" + editingUserId, {
          method: "PUT",
          body: JSON.stringify({
            fullName: formData.get("fullName"),
            username: formData.get("username"),
          }),
        });
        closeModal("editStaffModal");
        await loadStaffAccounts();
      } catch (err) {
        showMessage("editStaffMessage", err.message);
      }
    });

    resetForm.addEventListener("submit", async function (event) {
      event.preventDefault();
      if (resettingUserId === null) return;
      const formData = new FormData(resetForm);
      try {
        await accountRequest("/api/admin/staff/" + resettingUserId + "/password", {
          method: "POST",
          body: JSON.stringify({ password: formData.get("password") }),
        });
        closeModal("resetPasswordModal");
        resetForm.reset();
        alert("Staff password reset successfully.");
      } catch (err) {
        showMessage("resetPasswordMessage", err.message);
      }
    });

    tbody.addEventListener("click", async function (event) {
      const button = event.target.closest("button[data-action]");
      if (!button) return;
      const userId = Number(button.dataset.userId);
      const account = accounts.find((item) => item.userId === userId);
      if (!account) return;

      if (button.dataset.action === "edit") {
        editingUserId = userId;
        editForm.elements.fullName.value = account.fullName;
        editForm.elements.username.value = account.username;
        clearMessage("editStaffMessage");
        openModal("editStaffModal");
      } else if (button.dataset.action === "password") {
        resettingUserId = userId;
        resetForm.reset();
        clearMessage("resetPasswordMessage");
        openModal("resetPasswordModal");
      } else if (button.dataset.action === "status") {
        const action = account.isActive ? "deactivate" : "activate";
        if (!confirm("Are you sure you want to " + action + " " + account.fullName + "'s account?")) {
          return;
        }
        try {
          await accountRequest("/api/admin/staff/" + userId + "/status", {
            method: "PATCH",
            body: JSON.stringify({ isActive: !account.isActive }),
          });
          await loadStaffAccounts();
        } catch (err) {
          alert(err.message);
        }
      } else if (button.dataset.action === "delete") {
        if (!confirm("Permanently delete Staff account " + account.fullName + "?")) return;
        try {
          await accountRequest("/api/admin/staff/" + userId, { method: "DELETE" });
          await loadStaffAccounts();
        } catch (err) {
          alert(err.message);
        }
      }
    });

    document.getElementById("btnRefreshAccounts").addEventListener("click", loadStaffAccounts);
    document.querySelectorAll("[data-close-modal]").forEach(function (button) {
      button.addEventListener("click", function () {
        closeModal(button.dataset.closeModal);
      });
    });
    document.querySelectorAll(".modal-overlay").forEach(function (modal) {
      modal.addEventListener("click", function (event) {
        if (event.target === modal) closeModal(modal.id);
      });
    });

    let accounts = [];
    await loadStaffAccounts();
    startAccountClock();

    async function loadStaffAccounts() {
      tbody.innerHTML = '<tr><td colspan="4" class="account-empty">Loading Staff accounts...</td></tr>';
      try {
        const data = await accountRequest("/api/admin/staff");
        accounts = data.staff || [];
        renderStaffAccounts(accounts);
      } catch (err) {
        accounts = [];
        tbody.innerHTML = "";
        const row = document.createElement("tr");
        const cell = document.createElement("td");
        cell.colSpan = 4;
        cell.className = "account-empty";
        cell.textContent = err.message;
        row.appendChild(cell);
        tbody.appendChild(row);
      }
    }

    function renderStaffAccounts(staffAccounts) {
      tbody.innerHTML = "";
      if (!staffAccounts.length) {
        tbody.innerHTML = '<tr><td colspan="4" class="account-empty">No Staff accounts found.</td></tr>';
        return;
      }

      staffAccounts.forEach(function (account) {
        const row = document.createElement("tr");
        appendTextCell(row, account.fullName);
        appendTextCell(row, account.username);

        const statusCell = document.createElement("td");
        const status = document.createElement("span");
        status.className = "account-status " +
          (account.isActive ? "account-status-active" : "account-status-inactive");
        status.textContent = account.isActive ? "Active" : "Inactive";
        statusCell.appendChild(status);
        row.appendChild(statusCell);

        const actionsCell = document.createElement("td");
        const actions = document.createElement("div");
        actions.className = "account-actions";
        actions.appendChild(createActionButton("Edit", "edit", account.userId));
        actions.appendChild(createActionButton("Reset Password", "password", account.userId));
        actions.appendChild(createActionButton(
          account.isActive ? "Deactivate" : "Activate",
          "status",
          account.userId,
          account.isActive ? "btn-secondary" : "btn-success"
        ));
        actions.appendChild(createActionButton("Delete", "delete", account.userId, "btn-danger"));
        actionsCell.appendChild(actions);
        row.appendChild(actionsCell);
        tbody.appendChild(row);
      });
    }
  } catch (err) {
    console.error("Account Handler initialization failed:", err);
    alert("Unable to initialize Account Handler. Check the server and try again.");
  }
});

async function accountRequest(url, options = {}) {
  const { ok, data } = await apiFetch(url, options);
  if (!ok) throw new Error(data.message || "Account request failed.");
  return data;
}

function appendTextCell(row, value) {
  const cell = document.createElement("td");
  cell.textContent = value || "";
  row.appendChild(cell);
}

function createActionButton(label, action, userId, styleClass = "btn-outline") {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "btn " + styleClass;
  button.textContent = label;
  button.dataset.action = action;
  button.dataset.userId = userId.toString();
  return button;
}

function openModal(modalId) {
  document.getElementById(modalId).classList.add("visible");
}

function closeModal(modalId) {
  document.getElementById(modalId).classList.remove("visible");
}

function showMessage(elementId, message, success = false) {
  const element = document.getElementById(elementId);
  element.textContent = message;
  element.classList.toggle("account-message-success", success);
}

function clearMessage(elementId) {
  showMessage(elementId, "");
}

function startAccountClock() {
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
