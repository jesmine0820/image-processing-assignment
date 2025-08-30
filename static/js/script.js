let currentStream = null;

function showCounter(counterNum, mode = "face") {
  // hide all counters
  document.querySelectorAll(".counter-view").forEach((el) => el.classList.remove("active"));

  // show selected
  const counterDiv = document.getElementById(`counter${counterNum}`);
  counterDiv.classList.add("active");

  // find camera <img>
  const img = counterDiv.querySelector(".camera-feed img");

  // stop previous stream
  if (currentStream) {
    currentStream.src = "about:blank";
  }

  // start new stream
  img.src = `/video/${counterNum}?mode=${encodeURIComponent(mode)}`;
  currentStream = img;
}

function switchToBarcode(counterNum) {
  showCounter(counterNum, "barcode");
}

function updateRecognition() {
    fetch("/recognition/1")
        .then(response => response.json())
        .then(data => {
            document.getElementById("personId").textContent = data.id;
            document.getElementById("personName").textContent = data.name;
        })
        .catch(err => console.error(err));
}

setInterval(updateRecognition, 500);

document.getElementById("saveSetting").addEventListener("click", () => {
  const faceModel = document.getElementById("face-recognition").value;
  const barcodeModel = document.getElementById("barcode-detection").value;

  fetch("/save-settings", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      face: faceModel,
      barcode: barcodeModel,
    }),
  })
    .then((res) => res.json())
    .then((data) => {
      console.log("Settings saved:", data);
      document.getElementById("settingModel").classList.add("hidden");
    })
    .catch((err) => console.error(err));
});

document.getElementById("cancelSetting").addEventListener("click", () => {
  document.getElementById("settingModel").classList.add("hidden");
});

window.onload = function () {
  showCounter(1, "face");
};
