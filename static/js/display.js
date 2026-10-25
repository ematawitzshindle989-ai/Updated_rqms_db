/**
 * Public queue display — reads from Flask API (shared MySQL data).
 */

document.addEventListener("DOMContentLoaded", function () {
  refreshDisplay();
  setInterval(refreshDisplay, 2000);
  setInterval(function () {
    document.getElementById("lblClock").textContent = new Date().toLocaleTimeString("en-PH", {
      hour: "2-digit", minute: "2-digit", second: "2-digit",
    });
  }, 1000);
});

async function refreshDisplay() {
  try {
    const data = await apiGetDisplay();
    const current = data.current;
    const emergencyBanner = document.getElementById("emergencyBanner");
    emergencyBanner.classList.toggle("hidden", !(data.emergency && data.emergency.active));

    document.getElementById("lblNowNumber").textContent = current ? current.queueNumber : "---";
    document.getElementById("lblNowRoom").textContent = current
      ? "Please proceed to " + current.assignedRoom
      : "Please wait for your number";

    const list = document.getElementById("lstUpcoming");
    list.innerHTML = "";
    (data.upcoming || []).forEach(function (p) {
      const li = document.createElement("li");
      li.textContent = p.queueNumber + "  |  " + p.serviceType + "  |  " + p.assignedRoom;
      list.appendChild(li);
    });
  } catch (err) {
    console.error("Display refresh failed:", err);
  }
}
