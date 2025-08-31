let currentStream = null;
let currentCounter = 1;
let currentMode = "face";
let faceId = "---";
let barcodeId = "---";
let verificationTimeout = null;

// -------------------- INITIALIZATION --------------------
document.addEventListener("DOMContentLoaded", () => {
  loadSettings();
  showCounter(1, "face");
  setInterval(updateRecognition, 3000);
  updateQueueDisplay();

  // Modal close button
  const modal = document.getElementById("verificationModal");
  const closeBtn = document.getElementsByClassName("close")[0];
  closeBtn.onclick = () => {
    modal.classList.add("hidden");
    if (verificationTimeout) clearInterval(verificationTimeout);
    resetScan();
    showCounter(1, "face");
  };
});

// -------------------- CAMERA VIEW --------------------
function showCounter(counterNum, mode = "face") {
  currentCounter = counterNum;
  currentMode = mode;

  document.querySelectorAll(".counter-view").forEach((el) =>
    el.classList.remove("active")
  );

  const counterDiv = document.getElementById(`counter${counterNum}`);
  counterDiv.classList.add("active");

  const img = counterDiv.querySelector(".camera-feed img");
  img.src = `/video/${counterNum}?mode=${mode}&t=${Date.now()}`;

  updateRecognition();
}

// -------------------- SETTINGS --------------------
function saveSettings() {
  const faceModel = document.getElementById("face-recognition").value;
  const barcodeModel = document.getElementById("barcode-detection").value;

  fetch("/save-settings", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ face: faceModel, barcode: barcodeModel }),
  });
}

function loadSettings() {
  fetch("/get-settings")
    .then((res) => res.json())
    .then((data) => {
      document.getElementById("face-recognition").value = data.face;
      document.getElementById("barcode-detection").value = data.barcode;
    });
}

// -------------------- RECOGNITION --------------------
function updateRecognition() {
  if (currentCounter === 3) {
    updateQueueDisplay();
    return;
  }

  fetch(`/recognition/${currentCounter}?mode=${encodeURIComponent(currentMode)}`)
    .then((res) => res.json())
    .then((data) => {
      updatePersonDisplay(data);

      // Capture face ID at Counter 1
      if (currentCounter === 1 && currentMode === "face" && data.id && data.id !== "---") {
        faceId = data.id;
        document.getElementById("barcodeBtn").disabled = false;
      }

      // Auto add to queue at Counter 2
      if (currentCounter === 2 && data.id && data.id !== "---") {
        addToQueue(data.id);
      }
    })
    .catch(() => updatePersonDisplay({ id: "---", name: "---" }));
}

// Update recognition display
function updatePersonDisplay(data) {
  const display = document.querySelector(
    `#counter${currentCounter} .recognition-display`
  );
  if (display) {
    display.innerHTML = `
      <p><strong>ID:</strong> ${data.id || "---"}</p>
      <p><strong>Name:</strong> ${data.name || "---"}</p>
    `;
  }
}

// -------------------- BARCODE SCANNING --------------------
function scanBarcode() {
  const button = document.getElementById("barcodeBtn");

  if (currentMode === "face") {
    // Switch to barcode scanning
    showCounter(1, "barcode");
    button.textContent = "Scan Face";

    const barcodeCheckInterval = setInterval(() => {
      fetch("/recognition/1?mode=barcode")
        .then((res) => res.json())
        .then((data) => {
          if (data.id && data.id !== "---") {
            barcodeId = data.id;
            clearInterval(barcodeCheckInterval);
            verifyIdentity();
          }
        });
    }, 1000);
  } else {
    // Back to face mode
    showCounter(1, "face");
    button.textContent = "Scan Barcode";
  }
}

// -------------------- IDENTITY VERIFICATION --------------------
function verifyIdentity() {
  fetch("/verify-identity", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ face_id: faceId, barcode_id: barcodeId }),
  })
    .then((res) => res.json())
    .then((data) => {
      const modal = document.getElementById("verificationModal");
      const resultDiv = document.getElementById("verificationResult");
      const qrDiv = document.getElementById("qrDisplay");

      if (data.status === "success") {
        resultDiv.innerHTML = `<p class="success">${data.message}</p>`;
        qrDiv.classList.remove("hidden");
        showQRCode(data.id);
        startCountdown();
        sendEmailWithQR(data.id, data.name);
      } else {
        resultDiv.innerHTML = `<p class="error">${data.message}</p>`;
        qrDiv.classList.add("hidden");
      }

      modal.classList.remove("hidden");
    })
    .catch((error) => console.error("Verification error:", error));
}

// -------------------- QUEUE --------------------
function addToQueue(qrId) {
  fetch("/add-to-queue", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ qr_id: qrId }),
  })
    .then((res) => res.json())
    .then((data) => {
      console.log("Queue update:", data);
      updateQueueDisplay();
    });
}

function updateQueueDisplay() {
  fetch("/get-queue")
    .then((res) => res.json())
    .then((queue) => {
      const container = document.querySelector("#counter3 .queue-display");
      if (!container) return;

      container.innerHTML = queue
        .map(
          (person, idx) => `
          <div class="queue-person ${person.is_current === "Y" ? "current" : ""}">
            <span>${idx + 1}. ${person.name} (${person.id})</span>
          </div>
        `
        )
        .join("");
    });
}

// -------------------- VERIFICATION COUNTDOWN --------------------
function startCountdown() {
  let seconds = 10;
  const countdownElement = document.getElementById("countdown");
  countdownElement.textContent = seconds;

  verificationTimeout = setInterval(() => {
    seconds--;
    countdownElement.textContent = seconds;

    if (seconds <= 0) {
      clearInterval(verificationTimeout);
      document.getElementById("verificationModal").classList.add("hidden");
      resetScan();
      showCounter(1, "face");
    }
  }, 1000);
}

function resetScan() {
  fetch("/reset-scan").then(() => {
    faceId = "---";
    barcodeId = "---";
    document.getElementById("barcodeBtn").disabled = true;
    document.getElementById("barcodeBtn").textContent = "Scan Barcode";
    currentMode = "face";
  });
}

// -------------------- EMAIL --------------------
function sendEmailWithQR(studentId, studentName) {
  console.log(`Sending email to ${studentName} with QR code for ID: ${studentId}`);
}

function sendEmail() {
  fetch("/send-graduation-emails", { method: "POST" })
    .then((res) => res.json())
    .then((data) => alert(data.message))
    .catch(() => alert("Failed to send graduation emails!"));
}

setInterval(updateRecognition, 3000);