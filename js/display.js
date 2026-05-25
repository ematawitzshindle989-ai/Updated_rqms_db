/**
 * Public queue display monitor — waiting area screen.
 */

document.addEventListener("DOMContentLoaded", function () {
  refreshDisplay();
  setInterval(refreshDisplay, 1000);
});

function refreshDisplay() {
  const current = getCurrentServing();

  document.getElementById("lblNowNumber").textContent = current
    ? current.queueNumber
    : "---";
  document.getElementById("lblNowRoom").textContent = current
    ? "Please proceed to " + current.assignedRoom
    : "Please wait for your number";

  document.getElementById("lblClock").textContent = new Date().toLocaleTimeString(
    "en-PH",
    { hour: "2-digit", minute: "2-digit", second: "2-digit" }
  );

  const list = document.getElementById("lstUpcoming");
  list.innerHTML = "";

  getActiveQueue()
    .filter((p) => p.status === QueueStatus.Waiting)
    .slice(0, 6)
    .forEach(function (p) {
      const li = document.createElement("li");
      li.textContent =
        p.queueNumber + "  |  " + p.serviceType + "  |  " + p.assignedRoom;
      list.appendChild(li);
    });
}
