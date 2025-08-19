let currentStream = null;

function showCounter(counterNum, mode="face") {
    // Hidde all counters
    document.querySelectorAll('.counter-view').forEach(el => el.classList.remove('active'));

    // Show selected counter
    const counterDiv = document.getElementById(`counter${counterNum}`);
    counterDiv.classList.add('active');

    // Find camera <img> inside
    let img = counterDiv.querySelector(".camera-feed img");

    // Stop previous stream
    if (currentStream) {
        currentStream.src = "";
    }

    // Start new stream
    img.src = `/video/${counterNum}?mode=${mode}`;
    currentStream = img;
}

window.onload = function() {
    showCounter(1, "face");
};

