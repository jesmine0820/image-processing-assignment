let currentCounter = 1;
let currentMode = "face";
let faceId = "---";
let barcodeId = "---";
let queue_list = [];
let verificationTimeout;
let clearTimeoutHandle = null;
let displayedCounter2Id = null;

// DOM refs
let barcodeBtn, resultDiv, qrDiv, countdownElement;

document.addEventListener("DOMContentLoaded", () => {
  barcodeBtn = document.getElementById("barcodeBtn");
  resultDiv = document.getElementById("verificationResult");
  qrDiv = document.getElementById("qrDisplay");
  countdownElement = document.getElementById("countdown");

  // bind start button
  const startBtn = document.getElementById("startButton");
  if (startBtn) startBtn.addEventListener("click", startTracking);

  showCounter(1, "face");
  setInterval(updateRecognition, 3000);
});

/* ---------------- COUNTER HANDLING ---------------- */
function showCounter(counterNum, mode = "face") {
  if (counterNum === 2) {
    clearCounter2Display();
    displayedCounter2Id = null;
    fetch("/reset-scan").catch(() => {});
  }

  currentCounter = counterNum;
  currentMode = mode;

  document.querySelectorAll(".counter-view").forEach((el) =>
    el.classList.remove("active")
  );
  const counterDiv = document.getElementById(`counter${counterNum}`);
  if (counterDiv) counterDiv.classList.add("active");

  const img = document.querySelector(`#counter${counterNum} .camera-feed img`);
  if (img)
    img.src = `/video/${counterNum}?mode=${encodeURIComponent(mode)}&t=${Date.now()}`;

  if (counterNum === 3) {
    updateQueueDisplay();
  } else {
    updateRecognition();
  }
}

function updateRecognition() {
  if (currentCounter === 3) return;

  fetch(`/recognition/${currentCounter}?mode=${encodeURIComponent(currentMode)}`)
    .then((res) => res.json())
    .then((data) => {
      if (currentCounter === 1) {
        updatePersonDisplay(data);
        if (currentMode === "face" && data.id && data.id !== "---") {
          faceId = data.id;
          if (barcodeBtn) barcodeBtn.disabled = false;
        }
      }

      if (currentCounter === 2) {
        if (data && data.id && data.id !== "---" && data.id !== displayedCounter2Id) {
          handleQrScan(data);
        }
      }
    })
    .catch(() => {
      if (currentCounter === 1) updatePersonDisplay({ id: "---", name: "---" });
    });
}

function updatePersonDisplay(data) {
  if (currentCounter === 1) {
    const idEl = document.getElementById("personId");
    const nameEl = document.getElementById("personName");
    if (idEl) idEl.textContent = data.id || "---";
    if (nameEl) nameEl.textContent = data.name || "---";
  }
}

/* ---------------- BARCODE + FACE VERIFICATION ---------------- */
function scanBarcode() {
  if (currentMode === "face") {
    showCounter(1, "barcode");
    barcodeBtn.textContent = "Scan Face";

    const interval = setInterval(() => {
      fetch("/recognition/1?mode=barcode")
        .then((res) => res.json())
        .then((data) => {
          if (data && data.id && data.id !== "---") {
            barcodeId = data.id;
            clearInterval(interval);
            verifyIdentity();
          }
        })
        .catch(() => {});
    }, 1000);
  } else {
    showCounter(1, "face");
    barcodeBtn.textContent = "Scan Barcode";
  }
}

function verifyIdentity() {
  fetch("/verify-identity", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ face_id: faceId, barcode_id: barcodeId }),
  })
    .then((res) => res.json())
    .then((data) => {
      if (data.status === "success") {
        const banner = document.getElementById("successMessage");
        if (banner) {
          banner.classList.remove("hidden");
          setTimeout(() => banner.classList.add("hidden"), 5000);
        }
      } else {
        alert(`Verification failed: ${data.message}`);
      }
    })
    .catch((err) => {
      console.error("verifyIdentity error:", err);
    });
}

/* ---------------- COUNTER 2 DISPLAY ---------------- */
function displayPersonPhoto(personId) {
  const photoEl = document.getElementById("personPhoto");
  if (!photoEl) return;
  photoEl.src = `/photos/${personId}.jpg`;
  photoEl.onerror = () => (photoEl.src = "static/images/logo.png");
}

function clearCounter2Display() {
  const idEl = document.getElementById("personId2");
  const nameEl = document.getElementById("personName2");
  const photoEl = document.getElementById("personPhoto");
  if (idEl) idEl.textContent = "---";
  if (nameEl) nameEl.textContent = "---";
  if (photoEl) photoEl.src = "static/images/logo.png";
  displayedCounter2Id = null;
  if (clearTimeoutHandle) {
    clearTimeout(clearTimeoutHandle);
    clearTimeoutHandle = null;
  }
}

function showCounter2Result(data) {
  if (!data || !data.id) return;
  displayedCounter2Id = data.id;
  const idEl = document.getElementById("personId2");
  const nameEl = document.getElementById("personName2");
  if (idEl) idEl.textContent = data.id;
  if (nameEl) nameEl.textContent = data.name || "---";
  displayPersonPhoto(data.id);

  if (clearTimeoutHandle) {
    clearTimeout(clearTimeoutHandle);
    clearTimeoutHandle = null;
  }

  clearTimeoutHandle = setTimeout(() => {
    clearCounter2Display();
    fetch("/reset-scan").catch(() => {});
  }, 5000);
}

function handleQrScan(data) {
  showCounter2Result(data);

  if (data && data.id) {
    fetch("/add-to-queue", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ qr_id: data.id })
    })
      .then((res) => res.json())
      .then((result) => {
        if (result.status === "success") {
          console.log("Added to queue:", result);
          updateQueueDisplay();
        } else {
          console.warn("Queue add failed:", result.message);
        }
      })
      .catch((err) => console.error("add-to-queue error:", err));
  }
}

/* ---------------- QUEUE DISPLAY (COUNTER 3) ---------------- */
function updateQueueDisplay() {
  fetch("/get-queue")
    .then((res) => res.json())
    .then((queue) => {
      queue_list = queue || [];
      const list = document.getElementById("queueList");
      if (!list) return;

      list.innerHTML = queue
        .map(
          (p, i) =>
            `<li class="${p.is_current === "Y" ? "current" : ""}">
               ${i + 1}. ${p.name} (${p.id})
             </li>`
        )
        .join("");

      updateCurrentPersonDisplay();
    })
    .catch((err) => console.error("updateQueueDisplay error:", err));
}

function updateCurrentPersonDisplay() {
  const currentSpan = document.getElementById("currentPerson");
  const nextSpan = document.getElementById("nextPerson");

  if (!queue_list || queue_list.length === 0) {
    if (currentSpan) currentSpan.textContent = "---";
    if (nextSpan) nextSpan.textContent = "---";
    return;
  }

  const currentIndex = queue_list.findIndex((p) => p.is_current === "Y");
  if (currentIndex !== -1) {
    const currentPerson = queue_list[currentIndex];
    if (currentSpan) currentSpan.textContent = `${currentPerson.name} (${currentPerson.id})`;

    const nextPerson = queue_list[currentIndex + 1];
    if (nextSpan) nextSpan.textContent = nextPerson ? `${nextPerson.name} (${nextPerson.id})` : "No more people";
  } else {
    if (currentSpan) currentSpan.textContent = "---";
    const nextPerson = queue_list[0];
    if (nextSpan) nextSpan.textContent = nextPerson ? `${nextPerson.name} (${nextPerson.id})` : "---";
  }
}

function startTracking() {
  fetch("/update-current-person", { method: "POST" })
    .then((res) => res.json())
    .then((data) => {
      updateQueueDisplay();
    })
    .catch((err) => console.error("startTracking error:", err));
}

/* ---------------- DEBUG TOOLS ---------------- */
function checkQueue() {
  fetch("/get-queue")
    .then((res) => res.json())
    .then((queue) => {
      console.log("Current Queue:", queue);
      alert("Queue size: " + queue.length + "\n" +
            queue.map((p, i) => `${i+1}. ${p.name} (${p.id}) [${p.is_current}]`).join("\n"));
    })
    .catch((err) => console.error("checkQueue error:", err));
}

/* ---------------- SETTINGS + EMAIL ---------------- */
function saveSettings() {
  const faceModel = document.getElementById("face-recognition").value;
  const barcodeModel = document.getElementById("barcode-detection").value;

  fetch("/save-settings", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ face: faceModel, barcode: barcodeModel })
  })
    .then(res => res.json())
    .then(data => {
      console.log("Settings saved:", data);
      const saveStatus = document.getElementById("save-status");
      if (saveStatus) {
        saveStatus.textContent = "✅ Settings saved!";
        setTimeout(() => (saveStatus.textContent = ""), 3000);
      }
    })
    .catch(err => console.error("saveSettings error:", err));
}

function sendEmail() {
  fetch("/send-email", { method: "POST" })
    .then(res => res.json())
    .then(data => {
      if (data.status === "success") {
        alert("📩 Graduation email sent successfully!");
      } else {
        alert("Failed to send email: " + data.message);
      }
    })
    .catch(err => console.error("sendEmail error:", err));
}

/* ---------------- AUTO REFRESH ---------------- */
setInterval(() => {
  if (currentCounter === 3) {
    updateQueueDisplay();
  }
}, 5000);
