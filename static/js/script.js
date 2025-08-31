let currentStream = null;
let currentCounter = 1;
let currentMode = "face";

function showCounter(counterNum, mode = "face") {
  // Update global variables
  currentCounter = counterNum;
  currentMode = mode;
  
  // hide all counters
  document.querySelectorAll(".counter-view").forEach((el) => el.classList.remove("active"));

  // show selected
  const counterDiv = document.getElementById(`counter${counterNum}`);
  if (counterDiv) {
    counterDiv.classList.add("active");

    // find camera <img>
    const img = counterDiv.querySelector(".camera-feed img");

    // stop previous stream
    if (currentStream) {
      currentStream.src = "";
    }

    // start new stream with cache busting
    if (img) {
      img.src = `/video/${counterNum}?mode=${encodeURIComponent(mode)}&t=${new Date().getTime()}`;
      currentStream = img;
      
      // Handle image loading errors
      img.onerror = function() {
        console.error("Failed to load camera stream");
        this.src = ""; // Clear the broken image
      };
    }
  }
}

function switchToBarcode(counterNum) {
  showCounter(counterNum, "barcode");
}

function saveSettings() {
  const faceModel = document.getElementById("face-recognition");
  const barcodeModel = document.getElementById("barcode-detection");
  const saveStatus = document.getElementById("save-status");

  if (!faceModel || !barcodeModel || !saveStatus) {
    console.error("Required elements not found");
    return;
  }

  fetch("/save-settings", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ face: faceModel.value, barcode: barcodeModel.value }),
  })
    .then((res) => {
      if (!res.ok) {
        throw new Error(`HTTP error! status: ${res.status}`);
      }
      return res.json();
    })
    .then((data) => {
      console.log("Settings saved:", data);
      saveStatus.textContent = "Settings saved! Restarting camera...";
      saveStatus.className = "save-status success";
      
      // Restart the current stream with new settings
      setTimeout(() => {
        showCounter(currentCounter, currentMode);
        saveStatus.textContent = "";
        saveStatus.className = "save-status";
      }, 1000);
    })
    .catch((err) => {
      console.error("Error saving settings:", err);
      saveStatus.textContent = "Error saving settings!";
      saveStatus.className = "save-status error";
      
      // Clear status message after 2 seconds
      setTimeout(() => {
        saveStatus.textContent = "";
        saveStatus.className = "save-status";
      }, 2000);
    });
}

function resetScan() {
  fetch("/reset-scan")
    .then((response) => {
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      return response.json();
    })
    .then((data) => {
      console.log("Scan reset:", data);
      // Update the display if needed
      const personId2 = document.getElementById("personId2");
      const personName2 = document.getElementById("personName2");
      if (personId2 && personName2) {
        personId2.textContent = "---";
        personName2.textContent = "---";
      }
    })
    .catch((err) => console.error("Error resetting scan:", err));
}

function updateRecognition() {
  // Only update if the element exists
  const personId = document.getElementById("personId");
  const personName = document.getElementById("personName");
  
  if (personId && personName) {
    fetch("/recognition/1")
      .then((response) => {
        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }
        return response.json();
      })
      .then((data) => {
        personId.textContent = data.id || "---";
        personName.textContent = data.name || "---";
      })
      .catch((err) => {
        console.error("Error updating recognition:", err);
        personId.textContent = "---";
        personName.textContent = "---";
      });
  }
  
  // Also update counter 2 recognition if it's active
  if (currentCounter === 2) {
    const personId2 = document.getElementById("personId2");
    const personName2 = document.getElementById("personName2");
    
    if (personId2 && personName2) {
      fetch("/recognition/2")
        .then((response) => {
          if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
          }
          return response.json();
        })
        .then((data) => {
          personId2.textContent = data.id || "---";
          personName2.textContent = data.name || "---";
        })
        .catch((err) => {
          console.error("Error updating recognition for counter 2:", err);
          personId2.textContent = "---";
          personName2.textContent = "---";
        });
    }
  }
}

// Load saved settings when page loads
function loadSettings() {
  fetch("/get-settings")
    .then((response) => {
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      return response.json();
    })
    .then((data) => {
      const faceModel = document.getElementById("face-recognition");
      const barcodeModel = document.getElementById("barcode-detection");
      
      if (faceModel && data.face) {
        faceModel.value = data.face;
      }
      if (barcodeModel && data.barcode) {
        barcodeModel.value = data.barcode;
      }
    })
    .catch((err) => pass);
}

// Initialize when DOM is fully loaded
document.addEventListener('DOMContentLoaded', function() {
  // Load saved settings
  loadSettings();
  
  // Start with counter 1
  showCounter(1, "face");
  
  // Set up periodic updates
  setInterval(updateRecognition, 5000); // Increased to 5 seconds to reduce load
});