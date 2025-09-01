let currentStream = null;
let currentCounter = 1;
let currentMode = "face";
let faceID = "---";
let barcodeID = "---"
let verificationTimeout = null;

const counterDiv = document.getElementById(`counter${counterNum}`);
const img = counterDiv.querySelector(".camera-feed img");
const modal = document.getElementById("verificationModal");
const closeBtn = document.getElementsByClassName("close")[0];
const button = document.getElementById("barcodeBtn");
const resultDiv = document.getElementById("verificationResult");
const qrDiv = document.getElementById("qrDisplay");
const countdownElement = document.getElementById("countdown");
const faceModel = document.getElementById("face-recognition").value;
const barcodeModel = document.getElementById("barcode-detection").value;

// Start
document.addEventListener("DOMContentLoaded", () => {
  loadSettings();
  showCounter(1, "face");
  setInterval(updateRecognition, 3000);
  updateQueueDisplay();

  // Modal close button
  closeBtn.onclick = () => {
    modal.classList.add("hidden");
    if (verificationTimeout) clearInterval(verificationTimeout);
    resetScan();
    showCounter(1, "face");
  };
});


// --- Camera View ---
function showCounter(counterNum, mode) {
    currentCounter = counterNum;
    currentMode = mode;

    document.querySelectorAll(".counter-view").forEach((el) =>
        el.classList.remove("active")
    );

    counterDiv.classList.add("active");
    img.src = `/video/${counterNum}?mode=${mode}&t=${Date.now()}`;
    
    if(counterNum != 3) {
        updateRecognition();
    }
}

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
        button.disabled = false;
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

// --- Scan Barcode ---
function scanBarcode() {
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

// --- Identity verification ---
function verifyIdentity() {
  fetch("/verify-identity", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ face_id: faceId, barcode_id: barcodeId }),
  })
    .then((res) => res.json())
    .then((data) => {
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

// --- Verification Countdown ---
function startCountdown() {
  let seconds = 10;
  countdownElement.textContent = seconds;

  verificationTimeout = setInterval(() => {
    seconds--;
    countdownElement.textContent = seconds;

    if (seconds <= 0) {
      clearInterval(verificationTimeout);
      modal.classList.add("hidden");
      resetScan();
      showCounter(1, "face");
    }
  }, 1000);
}

function resetScan() {
  fetch("/reset-scan").then(() => {
    faceId = "---";
    barcodeId = "---";
    button.disabled = true;
    button.textContent = "Scan Barcode";
    currentMode = "face";
  });
}

// --- Setting ---
function saveSettings() {
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
      faceModel.value = data.face;
      barcodeModel.value = data.barcode;
    });
}

// --- Email ---
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

