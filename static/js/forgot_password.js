(() => {
  // ---------- STATE ----------
  let mouseX = 0;
  let mouseY = 0;

  let isPurpleBlinking = false;
  let isBlackBlinking = false;
  let isLookingAtEachOther = false;
  let isPurplePeeking = false;

  let isTyping = false;
  let showPassword = false;
  let passwordLength = 0;

  let typingTimer = null;
  let peekTimer = null;
  let peekInnerTimer = null;

  // ---------- ELEMENTS ----------
  const purpleEl = document.getElementById('purple');
  const blackEl = document.getElementById('black');
  const orangeEl = document.getElementById('orange');
  const yellowEl = document.getElementById('yellow');

  const purpleFace = document.getElementById('purple-face');
  const blackFace = document.getElementById('black-face');
  const orangeFace = document.getElementById('orange-face');
  const yellowFace = document.getElementById('yellow-face');
  const yellowMouth = document.getElementById('yellow-mouth');

  const purpleEye1 = document.getElementById('purple-eye-1');
  const purpleEye2 = document.getElementById('purple-eye-2');
  const blackEye1 = document.getElementById('black-eye-1');
  const blackEye2 = document.getElementById('black-eye-2');
  const orangePupil1 = document.getElementById('orange-pupil-1');
  const orangePupil2 = document.getElementById('orange-pupil-2');
  const yellowPupil1 = document.getElementById('yellow-pupil-1');
  const yellowPupil2 = document.getElementById('yellow-pupil-2');

  function initEye(eyeEl) {
    if (!eyeEl) return;
    const size = eyeEl.dataset.size;
    const pupilSize = eyeEl.dataset.pupil;
    eyeEl.style.width = size + 'px';
    eyeEl.style.height = size + 'px';
    const pupil = eyeEl.querySelector('.pupil');
    if (pupil) {
      pupil.style.width = pupilSize + 'px';
      pupil.style.height = pupilSize + 'px';
    }
  }

  function initPupilOnly(el) {
    if (!el) return;
    const size = el.dataset.size;
    el.style.width = size + 'px';
    el.style.height = size + 'px';
  }

  [purpleEye1, purpleEye2, blackEye1, blackEye2].forEach(initEye);
  [orangePupil1, orangePupil2, yellowPupil1, yellowPupil2].forEach(initPupilOnly);

  // ---------- HELPERS ----------
  function clamp(v, min, max) {
    return Math.max(min, Math.min(max, v));
  }

  function calculatePosition(el) {
    if (!el) return { faceX: 0, faceY: 0, bodySkew: 0 };
    const rect = el.getBoundingClientRect();
    const centerX = rect.left + rect.width / 2;
    const centerY = rect.top + rect.height / 3;
    const deltaX = mouseX - centerX;
    const deltaY = mouseY - centerY;
    return {
      faceX: clamp(deltaX / 20, -15, 15),
      faceY: clamp(deltaY / 30, -10, 10),
      bodySkew: clamp(-deltaX / 120, -6, 6),
    };
  }

  function eyePupilPosition(eyeEl, maxDistance, forceX, forceY) {
    if (forceX !== undefined && forceY !== undefined) {
      return { x: forceX, y: forceY };
    }
    const rect = eyeEl.getBoundingClientRect();
    const centerX = rect.left + rect.width / 2;
    const centerY = rect.top + rect.height / 2;
    const deltaX = mouseX - centerX;
    const deltaY = mouseY - centerY;
    const distance = Math.min(Math.sqrt(deltaX ** 2 + deltaY ** 2), maxDistance);
    const angle = Math.atan2(deltaY, deltaX);
    return { x: Math.cos(angle) * distance, y: Math.sin(angle) * distance };
  }

  function setPupil(eyeEl, maxDistance, forceX, forceY) {
    if (!eyeEl) return;
    const pupil = eyeEl.classList.contains('eye') ? eyeEl.querySelector('.pupil') : eyeEl;
    if (!pupil) return;
    const pos = eyePupilPosition(eyeEl, maxDistance, forceX, forceY);
    pupil.style.transform = `translate(${pos.x}px, ${pos.y}px)`;
  }

  // ---------- BLINKING ----------
  function randomBlinkDelay() {
    return Math.random() * 4000 + 3000;
  }

  function startPurpleBlink() {
    setTimeout(() => {
      isPurpleBlinking = true;
      applyBlink(purpleEye1, true);
      applyBlink(purpleEye2, true);
      setTimeout(() => {
        isPurpleBlinking = false;
        applyBlink(purpleEye1, false);
        applyBlink(purpleEye2, false);
        startPurpleBlink();
      }, 150);
    }, randomBlinkDelay());
  }

  function startBlackBlink() {
    setTimeout(() => {
      isBlackBlinking = true;
      applyBlink(blackEye1, true);
      applyBlink(blackEye2, true);
      setTimeout(() => {
        isBlackBlinking = false;
        applyBlink(blackEye1, false);
        applyBlink(blackEye2, false);
        startBlackBlink();
      }, 150);
    }, randomBlinkDelay());
  }

  function applyBlink(eyeEl, blinking) {
    if (!eyeEl) return;
    const size = eyeEl.dataset.size;
    eyeEl.style.height = blinking ? '2px' : size + 'px';
    const pupil = eyeEl.querySelector('.pupil');
    if (pupil) pupil.style.display = blinking ? 'none' : 'block';
  }

  // ---------- TYPING / PEEK STATE ----------
  function setTyping(val) {
    isTyping = val;
    clearTimeout(typingTimer);
    if (val) {
      isLookingAtEachOther = true;
      typingTimer = setTimeout(() => {
        isLookingAtEachOther = false;
      }, 800);
    } else {
      isLookingAtEachOther = false;
    }
  }

  function schedulePeek() {
    peekTimer = setTimeout(() => {
      isPurplePeeking = true;
      peekInnerTimer = setTimeout(() => {
        isPurplePeeking = false;
        schedulePeek();
      }, 800);
    }, Math.random() * 3000 + 2000);
  }

  function updatePeekWatcher() {
    clearTimeout(peekTimer);
    clearTimeout(peekInnerTimer);
    if (passwordLength > 0 && showPassword) {
      schedulePeek();
    } else {
      isPurplePeeking = false;
    }
  }

  // ---------- MAIN RENDER LOOP ----------
  function render() {
    if (!purpleEl || !blackEl || !yellowEl || !orangeEl) return;
    const purplePos = calculatePosition(purpleEl);
    const blackPos = calculatePosition(blackEl);
    const yellowPos = calculatePosition(yellowEl);
    const orangePos = calculatePosition(orangeEl);

    const isHidingPassword = passwordLength > 0 && !showPassword;
    const passwordShown = passwordLength > 0 && showPassword;

    // PURPLE body
    purpleEl.style.height = (isTyping || isHidingPassword) ? '440px' : '400px';
    purpleEl.style.transform = passwordShown
      ? 'skewX(0deg)'
      : (isTyping || isHidingPassword)
        ? `skewX(${purplePos.bodySkew - 12}deg) translateX(40px)`
        : `skewX(${purplePos.bodySkew}deg)`;

    purpleFace.style.left = passwordShown ? '20px' : isLookingAtEachOther ? '55px' : `${45 + purplePos.faceX}px`;
    purpleFace.style.top = passwordShown ? '35px' : isLookingAtEachOther ? '65px' : `${40 + purplePos.faceY}px`;

    let pForceX, pForceY;
    if (passwordShown) {
      pForceX = isPurplePeeking ? 4 : -4;
      pForceY = isPurplePeeking ? 5 : -4;
    } else if (isLookingAtEachOther) {
      pForceX = 3; pForceY = 4;
    } else {
      pForceX = undefined; pForceY = undefined;
    }
    setPupil(purpleEye1, 5, pForceX, pForceY);
    setPupil(purpleEye2, 5, pForceX, pForceY);

    // BLACK body
    blackEl.style.transform = passwordShown
      ? 'skewX(0deg)'
      : isLookingAtEachOther
        ? `skewX(${blackPos.bodySkew * 1.5 + 10}deg) translateX(20px)`
        : (isTyping || isHidingPassword)
          ? `skewX(${blackPos.bodySkew * 1.5}deg)`
          : `skewX(${blackPos.bodySkew}deg)`;

    blackFace.style.left = passwordShown ? '10px' : isLookingAtEachOther ? '32px' : `${26 + blackPos.faceX}px`;
    blackFace.style.top = passwordShown ? '28px' : isLookingAtEachOther ? '12px' : `${32 + blackPos.faceY}px`;

    let bForceX, bForceY;
    if (passwordShown) {
      bForceX = -4; bForceY = -4;
    } else if (isLookingAtEachOther) {
      bForceX = 0; bForceY = -4;
    } else {
      bForceX = undefined; bForceY = undefined;
    }
    setPupil(blackEye1, 4, bForceX, bForceY);
    setPupil(blackEye2, 4, bForceX, bForceY);

    // ORANGE body
    orangeEl.style.transform = passwordShown ? 'skewX(0deg)' : `skewX(${orangePos.bodySkew}deg)`;
    orangeFace.style.left = passwordShown ? '50px' : `${82 + orangePos.faceX}px`;
    orangeFace.style.top = passwordShown ? '85px' : `${90 + orangePos.faceY}px`;
    const oForceX = passwordShown ? -5 : undefined;
    const oForceY = passwordShown ? -4 : undefined;
    setPupil(orangePupil1, 5, oForceX, oForceY);
    setPupil(orangePupil2, 5, oForceX, oForceY);

    // YELLOW body
    yellowEl.style.transform = passwordShown ? 'skewX(0deg)' : `skewX(${yellowPos.bodySkew}deg)`;
    yellowFace.style.left = passwordShown ? '20px' : `${52 + yellowPos.faceX}px`;
    yellowFace.style.top = passwordShown ? '35px' : `${40 + yellowPos.faceY}px`;
    const yForceX = passwordShown ? -5 : undefined;
    const yForceY = passwordShown ? -4 : undefined;
    setPupil(yellowPupil1, 5, yForceX, yForceY);
    setPupil(yellowPupil2, 5, yForceX, yForceY);

    yellowMouth.style.left = passwordShown ? '10px' : `${40 + yellowPos.faceX}px`;
    yellowMouth.style.top = passwordShown ? '88px' : `${88 + yellowPos.faceY}px`;
  }

  let rafScheduled = false;
  function scheduleRender() {
    if (rafScheduled) return;
    rafScheduled = true;
    requestAnimationFrame(() => {
      rafScheduled = false;
      render();
    });
  }

  window.addEventListener('mousemove', (e) => {
    mouseX = e.clientX;
    mouseY = e.clientY;
    scheduleRender();
  });

  setInterval(scheduleRender, 150);

  startPurpleBlink();
  startBlackBlink();
  render();

  // ---------- FORGOT PASSWORD FORM LOGIC ----------
  const form = document.getElementById('forgot-form');
  const emailInput = document.getElementById('email');
  const passwordInput = document.getElementById('password');

  const emailError = document.getElementById('email-error');
  const passwordError = document.getElementById('password-error');
  const formError = document.getElementById('form-error');

  const submitBtn = document.getElementById('submit-btn');
  const submitLabel = document.getElementById('submit-label');
  const submitLabelHover = document.getElementById('submit-label-hover');
  const togglePasswordBtn = document.getElementById('toggle-password');
  const eyeOpen = document.getElementById('eye-open');
  const eyeClosed = document.getElementById('eye-closed');

  function validateEmail() {
    const val = emailInput.value.trim();
    if (!val) {
      if (emailError) emailError.textContent = 'Email address is required.';
      return 'Email address is required.';
    }
    const ok = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(val);
    if (emailError) emailError.textContent = ok ? '' : 'Please enter a valid email address.';
    return ok ? '' : 'Please enter a valid email address.';
  }

  function validatePassword() {
    if (!passwordInput) return '';
    const val = passwordInput.value;
    if (val && val.length < 6) {
      if (passwordError) passwordError.textContent = 'New password must be at least 6 characters.';
      return 'New password must be at least 6 characters.';
    }
    if (passwordError) passwordError.textContent = '';
    return '';
  }

  if (emailInput) {
    emailInput.addEventListener('focus', () => { setTyping(true); scheduleRender(); });
    emailInput.addEventListener('blur', () => { setTyping(false); scheduleRender(); });
    emailInput.addEventListener('input', validateEmail);
  }

  if (passwordInput) {
    passwordInput.addEventListener('focus', () => { setTyping(true); scheduleRender(); });
    passwordInput.addEventListener('blur', () => { setTyping(false); scheduleRender(); });
    passwordInput.addEventListener('input', () => {
      validatePassword();
      passwordLength = passwordInput.value.length;
      updatePeekWatcher();
      scheduleRender();
    });
  }

  if (togglePasswordBtn && passwordInput) {
    togglePasswordBtn.addEventListener('click', () => {
      showPassword = !showPassword;
      passwordInput.type = showPassword ? 'text' : 'password';
      eyeOpen.style.display = showPassword ? 'block' : 'none';
      eyeClosed.style.display = showPassword ? 'none' : 'block';
      updatePeekWatcher();
      scheduleRender();
    });
  }

  function setLoading(loading) {
    submitBtn.disabled = loading;
    const text = loading ? 'Processing...' : 'Reset Password';
    if (submitLabel) submitLabel.textContent = text;
    if (submitLabelHover) submitLabelHover.textContent = text;
  }

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    formError.style.display = 'none';
    formError.textContent = '';
    formError.style.background = '';
    formError.style.borderColor = '';
    formError.style.color = '';

    const emailErr = validateEmail();
    const passErr = validatePassword();

    if (emailErr || passErr) {
      formError.textContent = emailErr || passErr;
      formError.style.display = 'block';
      return;
    }

    const payload = {
      email: emailInput.value.trim(),
      password: passwordInput ? passwordInput.value : ''
    };

    setLoading(true);

    try {
      const response = await fetch('/forgot-password', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Requested-With': 'XMLHttpRequest'
        },
        body: JSON.stringify(payload)
      });

      const data = await response.json();

      if (data.success) {
        formError.style.display = 'block';
        formError.style.background = 'rgba(16, 185, 129, 0.12)';
        formError.style.borderColor = 'rgba(16, 185, 129, 0.35)';
        formError.style.color = '#10B981';
        formError.textContent = data.message || 'Password reset link / update processed! Redirecting...';

        setTimeout(() => {
          window.location.href = data.redirect_url || '/login';
        }, 1500);
      } else {
        setLoading(false);
        formError.style.display = 'block';
        formError.textContent = data.message || 'Password reset failed.';
      }
    } catch (err) {
      setLoading(false);
      formError.style.display = 'block';
      formError.textContent = 'Server connection error. Please try again.';
      console.error('Forgot password error:', err);
    }
  });
})();
