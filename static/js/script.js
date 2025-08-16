function showCounter(counterNum) {
    document.querySelectorAll('.counter-view').forEach(el => el.classList.remove('active'));
    document.getElementById(`counter${counterNum}`).classList.add('active');
}