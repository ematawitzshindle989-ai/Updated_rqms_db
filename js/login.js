/**
 * Login page logic — validation and redirect to dashboard.
 */

document.addEventListener("DOMContentLoaded", function () {
  const form = document.getElementById("loginForm");
  const lblError = document.getElementById("lblError");
  const tbxUsername = document.getElementById("tbxUsername");
  const tbxPassword = document.getElementById("tbxPassword");

  // Redirect if already logged in
  if (getSession()) {
    window.location.href = "dashboard.html";
    return;
  }

  form.addEventListener("submit", function (e) {
    e.preventDefault();
    lblError.classList.remove("visible");
    lblError.textContent = "";

    const username = tbxUsername.value.trim();
    const password = tbxPassword.value;
    const role = document.querySelector('input[name="role"]:checked').value;

    if (stringIsNullOrEmpty(username)) {
      showError("Username is required.");
      return;
    }

    if (stringIsNullOrEmpty(password)) {
      showError("Password is required.");
      return;
    }

    const result = tryLogin(username, password, role);

    if (!result.success) {
      showError(result.message);
      alert(result.message);
      return;
    }

    const session = getSession();
    alert("Welcome, " + session.fullName + "! (" + session.role + ")");
    window.location.href = "dashboard.html";
  });

  document.getElementById("btnExit").addEventListener("click", function () {
    if (confirm("Exit RQMS?")) {
      window.close();
    }
  });

  function showError(message) {
    lblError.textContent = message;
    lblError.classList.add("visible");
  }

  /** Same validation pattern as C# string.IsNullOrEmpty */
  function stringIsNullOrEmpty(value) {
    return value === null || value === undefined || value === "";
  }
});
