let currentStream = null;
let currentCounter = 1;
let currentMode = "face";
let faceId = "---";
let barcodeId = "---";
let verificationTimeout = null;

// When the app start
document.addEventListener('DOMContentLoaded', function() {
  loadSettings();
  showCounter(1, "face");
  setInterval(updateRecognition, 3000);
});

// Change between counter
function showCounter(counterNum, mode = "face") {
  currentCounter = counterNum;
  currentMode = mode;

  document.querySelectorAll(".counter-view").forEach(el => el.classList.remove("active"));
  const counterDiv = document.getElementById(`counter${counterNum}`);
  counterDiv.classList.add("active");

  const img = counterDiv.querySelector(".camera-feed img");
  if (currentStream) currentStream.src = "";
  if (img) {
    img.src = `/video/${counterNum}?mode=${encodeURIComponent(mode)}&t=${Date.now()}`;
    currentStream = img;
  }
}

// --- Setting Section---
function saveSettings() {
  const faceModel = document.getElementById("face-recognition").value;
  const barcodeModel = document.getElementById("barcode-detection").value;

  fetch("/save-settings", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ face: faceModel, barcode: barcodeModel })
  });
}

function loadSettings() {
  fetch("/get-settings")
    .then(res => res.json())
    .then(data => {
      document.getElementById("face-recognition").value = data.face;
      document.getElementById("barcode-detection").value = data.barcode;
    });
}

function updateRecognition() {
  fetch(`/recognition/${currentCounter}`)
    .then(res => res.json())
    .then(data => {
      document.getElementById(`personId${currentCounter === 1 ? "" : currentCounter}`).textContent = data.id || "---";
      document.getElementById(`personName${currentCounter === 1 ? "" : currentCounter}`).textContent = data.name || "---";
      
      // Store the face ID when detected at counter 1
      if (currentCounter === 1 && data.id && data.id !== "---") {
        faceId = data.id;
        // Enable barcode scan button
        document.getElementById("barcodeBtn").disabled = false;
      }
      
      // For counter 2, automatically add to queue when QR is scanned
      if (currentCounter === 2 && data.id && data.id !== "---") {
        addToQueue(data.id);
      }
    })
    .catch(() => {
      document.getElementById(`personId${currentCounter === 1 ? "" : currentCounter}`).textContent = "---";
      document.getElementById(`personName${currentCounter === 1 ? "" : currentCounter}`).textContent = "---";
    });
}

function scanBarcode() {
  // Switch to barcode scanning mode
  showCounter(1, "barcode");
  
  // Start checking for barcode results
  const barcodeCheckInterval = setInterval(() => {
    fetch('/recognition/2')  // Use counter 2 which handles barcode
      .then(res => res.json())
      .then(data => {
        if (data.id && data.id !== "---") {
          barcodeId = data.id;
          clearInterval(barcodeCheckInterval);
          verifyIdentity();
        }
      });
  }, 1000);
}

function verifyIdentity() {
  fetch("/verify-identity", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ face_id: faceId, barcode_id: barcodeId })
  })
  .then(res => res.json())
  .then(data => {
    const modal = document.getElementById("verificationModal");
    const resultDiv = document.getElementById("verificationResult");
    const qrDiv = document.getElementById("qrDisplay");
    
    if (data.status === "success") {
      resultDiv.innerHTML = '<p class="success">${data.message}</p>';
      qrDiv.classList.remove("hidden");
      showQRCode(data.id);
      startCountdown();
      
      // Send email with QR code
      sendEmailWithQR(data.id, data.name);
    } else {
      resultDiv.innerHTML = '<p class="error">${data.message}</p>';
      qrDiv.classList.add("hidden");
    }
    
    modal.classList.remove("hidden");
  })
  .catch(error => {
    console.error("Verification error:", error);
  });
}

// Add this function to add to queue (for counter 2)
function addToQueue(qrId) {
  fetch("/add-to-queue", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ qr_id: qrId })
  })
  .then(res => res.json())
  .then(data => {
    if (data.status === "success") {
      // Update queue display
      updateQueueDisplay();
    } else {
      console.error("Failed to add to queue:", data.message);
    }
  })
  .catch(error => {
    console.error("Queue error:", error);
  });
}

// Add this function to update queue display
function updateQueueDisplay() {
  fetch("/get-queue")
    .then(res => res.json())
    .then(data => {
      const queueList = document.getElementById("queueList");
      queueList.innerHTML = "";
      
      data.forEach(person => {
        const li = document.createElement("li");
        li.textContent = `${person.name} (${person.id}) - ${person.is_current === "Y" ? "Current" : "Waiting"}`;
        queueList.appendChild(li);
      });
      
      // Show queue display on counter 3
      if (currentCounter === 3) {
        document.getElementById("queueDisplay").classList.remove("hidden");
      }
    });
}

// Add this function for countdown
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
      // Reset and switch back to face recognition
      resetScan();
      showCounter(1, "face");
    }
  }, 1000);
}

// Add this function to reset scan
function resetScan() {
  fetch("/reset-scan")
    .then(() => {
      faceId = "---";
      barcodeId = "---";
      document.getElementById("barcodeBtn").disabled = true;
    });
}

// Add this function to send email with QR code
function sendEmailWithQR(studentId, studentName) {
  // You'll need to implement this based on your email service
  console.log(`Sending email to ${studentName} with QR code for ID: ${studentId}`);
  // Implementation will depend on your email service
}

// Add modal close functionality
document.addEventListener('DOMContentLoaded', function() {
  const modal = document.getElementById("verificationModal");
  const span = document.getElementsByClassName("close")[0];
  
  span.onclick = function() {
    modal.classList.add("hidden");
    if (verificationTimeout) clearInterval(verificationTimeout);
    resetScan();
    showCounter(1, "face");
  }
  
  // Initialize queue display
  updateQueueDisplay();
});

function sendEmail() {
  fetch("/send-graduation-emails", { method: "POST" })
    .then(res => res.json())
    .then(data => alert(data.message))
    .catch(() => alert("Failed to send graduation emails!"));
}
