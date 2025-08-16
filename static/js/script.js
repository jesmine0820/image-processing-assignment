function showCounter(counterNum) {
    document.querySelectorAll('.counter-view').forEach(el => el.classList.remove('active'));
    document.getElementById(`counter${counterNum}`).classList.add('active');
}

function switchToBarcode(counter) {
    let img = document.querySelector(`#counter${counter} .camera-feed img`);
    img.src = `/video/${counter}?mode=barcode`;
}