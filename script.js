document.addEventListener('DOMContentLoaded', function () {

  // ── Global variables ────────────────────────────────────────
  let currentUserId   = null;
  let currentUserName = null;
  let selectedGender  = null;

  // ── Gender button selection ──────────────────────────────────
  document.querySelectorAll('.gender-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.gender-btn')
              .forEach(b => b.classList.remove('sel'));
      btn.classList.add('sel');
      selectedGender = btn.getAttribute('data-val');
    });
  });

  // ── Option button selection (assessment questions) ───────────
  document.addEventListener('click', function (e) {
    if (e.target.classList.contains('opt')) {          // ✅ was 'opt-btn'
      const group = e.target.closest('.opts');          // ✅ was '.option-group'
      group.querySelectorAll('.opt').forEach(b => b.classList.remove('sel')); // ✅ was '.opt-btn'
      e.target.classList.add('sel');
    }
  });

  // ── Register user ────────────────────────────────────────────
  window.registerUser = function () {
    const name = document.getElementById('reg-name').value.trim();
    const age  = document.getElementById('reg-age').value.trim();
    const err  = document.getElementById('reg-error');

    if (!name || !age || !selectedGender) {
      err.classList.remove('hidden');
      return;
    }
    err.classList.add('hidden');

    fetch('/register', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({
        name:   name,
        age:    parseInt(age),
        gender: selectedGender
      })
    })
    .then(res => res.json())
    .then(data => {
      console.log('Server response:', data);
      if (data.error) {
        err.textContent = '⚠️ ' + data.error;
        err.classList.remove('hidden');
        return;
      }
      currentUserId   = data.user_id;
      currentUserName = data.name;
      document.getElementById('register-page').classList.add('hidden');
      document.getElementById('form-page').classList.remove('hidden');
      console.log(`✅ Registered: ${currentUserName} (id=${currentUserId})`);
    })
    .catch(error => {
      alert('Connection error. Make sure Flask server is running!');
      console.error(error);
    });
  };

  // ── Submit assessment ────────────────────────────────────────
  window.submitAssessment = function () {
    const err = document.getElementById('form-error');

    const answers   = {};
    let allAnswered = true;

    document.querySelectorAll('.opts').forEach(group => {          // ✅ was '.option-group'
      const key      = group.getAttribute('data-key');
      const selected = group.querySelector('.opt.sel');             // ✅ was '.opt-btn.sel'
      if (!selected) {
        allAnswered = false;
      } else {
        answers[key] = selected.getAttribute('data-val');
      }
    });

    if (!allAnswered) {
      err.classList.remove('hidden');
      return;
    }
    err.classList.add('hidden');

    fetch('/predict', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({
        user_id: currentUserId,
        answers: answers
      })
    })
    .then(res => res.json())
    .then(data => {
      document.getElementById('form-page').classList.add('hidden');
      document.getElementById('result-page').classList.remove('hidden');

      document.getElementById('result-condition').textContent  = data.condition;
      document.getElementById('result-confidence').textContent =
        `Confidence: ${data.confidence}%`;

      const barsDiv = document.getElementById('result-probs');
      barsDiv.innerHTML = '';
      for (const [label, prob] of Object.entries(data.probabilities)) {
        barsDiv.innerHTML += `
          <div class="prob-row">
            <span class="prob-label">${label}</span>
            <div class="prob-bar-bg">
              <div class="prob-bar-fill" style="width:${prob}%"></div>
            </div>
            <span class="prob-pct">${prob}%</span>
          </div>`;
      }
    })
    .catch(error => {
      alert('Connection error. Make sure Flask server is running!');
      console.error(error);
    });
  };

}); // ── end DOMContentLoaded ────────────────────────────────────
