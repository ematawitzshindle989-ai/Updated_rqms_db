/**
 * Login page — posts to Flask /api/login (MySQL session).
 */

document.addEventListener("DOMContentLoaded", async function () {
  const form = document.getElementById("loginForm");
  const lblError = document.getElementById("lblError");
  const tbxUsername = document.getElementById("tbxUsername");
  const tbxPassword = document.getElementById("tbxPassword");

  const session = await apiGetSession();
  if (session) {
    window.location.href = "/dashboard";
    return;
  }

  form.addEventListener("submit", async function (e) {
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

    try {
      const result = await apiLogin(username, password, role);

      if (!result.success) {
        showError(result.message);
        alert(result.message);
        return;
      }

      alert("Welcome, " + result.user.fullName + "! (" + result.user.role + ")");
      window.location.href = "/dashboard";
    } catch (err) {
      console.error(err);
      showError("Account not registered, or username or password is incorrect.");
      alert("Account not registered, or username or password is incorrect.");
    }
  });

  document.getElementById("btnExit").addEventListener("click", function () {
    window.location.href = "/";
  });

  function showError(message) {
    lblError.textContent = message;
    lblError.classList.add("visible");
  }
});
