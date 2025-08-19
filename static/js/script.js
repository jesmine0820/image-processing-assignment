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

window.onload = function () {
  showCounter(1, "face");
};
