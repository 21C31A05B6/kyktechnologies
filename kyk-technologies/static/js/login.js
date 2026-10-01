(() => {
  const loginPanel = document.getElementById('loginPanel');
  const signupPanel = document.getElementById('signupPanel');
  const loginButton = document.getElementById('loginBtn');
  const signupButton = document.getElementById('signupBtn');
  const adminLoginLink = document.getElementById('adminLoginLink');
  if (!loginPanel || !signupPanel || !loginButton || !signupButton || !adminLoginLink) return;

  function setAuthMode(mode, adminMode = false) {
    const showLogin = mode === 'login';
    document.body.dataset.authMode = mode;
    document.body.dataset.adminLogin = adminMode ? '1' : '0';
    document.querySelectorAll('.auth-tab').forEach((tab) => {
      const active = tab.dataset.authMode === mode;
      tab.classList.toggle('active', active);
      tab.setAttribute('aria-selected', String(active));
    });
    loginPanel.classList.toggle('active', showLogin);
    signupPanel.classList.toggle('active', !showLogin);
    loginButton.textContent = adminMode ? 'Admin login' : 'Login';
  }

  const params = new URLSearchParams(location.search);
  const redirect = params.get('redirect');
  if (params.get('mode') === 'signup') setAuthMode('signup');

  document.querySelectorAll('.auth-tab').forEach((tab) => {
    tab.addEventListener('click', () => setAuthMode(tab.dataset.authMode));
  });

  adminLoginLink.addEventListener('click', (event) => {
    event.preventDefault();
    setAuthMode('login', true);
  });

  signupButton.addEventListener('click', async () => {
    if (signupButton.disabled) return;
    const name = document.getElementById('signupName').value.trim();
    const email = document.getElementById('signupEmail').value.trim();
    const password = document.getElementById('signupPassword').value;
    const message = document.getElementById('signupMsg');
    signupButton.disabled = true;
    signupButton.classList.add('is-loading');
    signupButton.setAttribute('aria-busy', 'true');
    signupButton.textContent = 'Creating account';
    try {
      const response = await fetch('/api/auth/signup', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, email, password }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Signup failed');
      message.className = 'form-msg show ok';
      message.textContent = data.message || 'Account created successfully';
      setAuthMode('login');
      document.getElementById('loginEmail').value = email;
      document.getElementById('loginPassword').value = password;
    } catch (error) {
      message.className = 'form-msg show err';
      message.textContent = error.message;
    } finally {
      signupButton.disabled = false;
      signupButton.classList.remove('is-loading');
      signupButton.removeAttribute('aria-busy');
      signupButton.textContent = 'Create account';
    }
  });

  if (redirect && redirect.startsWith('/') && !redirect.startsWith('//') &&
      !/^\/(?:\/|https?:|javascript:|data:)/i.test(redirect)) {
    loginButton.dataset.redirect = redirect;
  }
})();
