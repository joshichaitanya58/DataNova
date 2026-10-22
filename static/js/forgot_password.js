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

  // ---------- FORGOT PASSWORD 2-STEP OTP & RESET LOGIC ----------
  let activeResetEmail = '';
  let resendInterval = null;

  // Step 1 Elements
  const stepEmail = document.getElementById('forgot-step-email');
  const emailForm = document.getElementById('forgot-email-form');
  const emailInput = document.getElementById('email');
  const emailError = document.getElementById('email-error');
  const emailFormError = document.getElementById('email-form-error');
  const sendOtpBtn = document.getElementById('send-otp-btn');
  const sendOtpLabel = document.getElementById('send-otp-label');
  const sendOtpLabelHover = document.getElementById('send-otp-label-hover');

  // Step 2 Elements
  const stepReset = document.getElementById('forgot-step-reset');
  const resetForm = document.getElementById('forgot-reset-form');
  const resetDisplayEmail = document.getElementById('reset-display-email');
  const otpDigits = Array.from(document.querySelectorAll('#forgot-otp-inputs .otp-digit'));
  const resendTimerText = document.getElementById('reset-resend-timer-text');
  const resendCountdown = document.getElementById('reset-resend-countdown');
  const btnResendOtp = document.getElementById('btn-reset-resend');
  const btnChangeEmail = document.getElementById('btn-reset-change-email');

  const passwordInput = document.getElementById('password');
  const confirmPasswordInput = document.getElementById('confirm_password');
  const passwordError = document.getElementById('password-error');
  const confirmPasswordError = document.getElementById('confirm-password-error');
  const resetFormError = document.getElementById('reset-form-error');

  const resetSubmitBtn = document.getElementById('reset-submit-btn');
  const resetSubmitLabel = document.getElementById('reset-submit-label');
  const resetSubmitLabelHover = document.getElementById('reset-submit-label-hover');

  const togglePasswordBtn = document.getElementById('toggle-password');
  const eyeOpen = document.getElementById('eye-open');
  const eyeClosed = document.getElementById('eye-closed');

  function validateEmail() {
    if (!emailInput) return '';
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
    if (!val) {
      if (passwordError) passwordError.textContent = 'New password is required.';
      return 'New password is required.';
    }
    if (val.length < 6) {
      if (passwordError) passwordError.textContent = 'New password must be at least 6 characters.';
      return 'New password must be at least 6 characters.';
    }
    if (passwordError) passwordError.textContent = '';
    return '';
  }

  function validateConfirmPassword() {
    if (!confirmPasswordInput || !passwordInput) return '';
    const val = confirmPasswordInput.value;
    const orig = passwordInput.value;
    if (!val) {
      if (confirmPasswordError) confirmPasswordError.textContent = 'Please confirm your new password.';
      return 'Please confirm your new password.';
    }
    if (orig && val !== orig) {
      if (confirmPasswordError) confirmPasswordError.textContent = 'Passwords do not match.';
      return 'Passwords do not match.';
    }
    if (confirmPasswordError) confirmPasswordError.textContent = '';
    return '';
  }

  function startResendTimer(seconds = 30) {
    clearInterval(resendInterval);
    if (btnResendOtp) btnResendOtp.style.display = 'none';
    if (resendTimerText) resendTimerText.style.display = 'inline';
    let timeLeft = seconds;
    if (resendCountdown) resendCountdown.textContent = `00:${timeLeft < 10 ? '0' : ''}${timeLeft}`;

    resendInterval = setInterval(() => {
      timeLeft -= 1;
      if (timeLeft <= 0) {
        clearInterval(resendInterval);
        if (resendTimerText) resendTimerText.style.display = 'none';
        if (btnResendOtp) {
          btnResendOtp.style.display = 'inline-flex';
          btnResendOtp.disabled = false;
        }
      } else {
        if (resendCountdown) resendCountdown.textContent = `00:${timeLeft < 10 ? '0' : ''}${timeLeft}`;
      }
    }, 1000);
  }

  function getEnteredOtp() {
    return otpDigits.map(d => d.value.trim()).join('');
  }

  function clearOtpInputs() {
    otpDigits.forEach(d => {
      d.value = '';
      d.classList.remove('filled');
    });
    if (otpDigits[0]) otpDigits[0].focus();
  }

  function showResetStep(email) {
    activeResetEmail = email;
    if (resetDisplayEmail) resetDisplayEmail.textContent = email;
    if (stepEmail) stepEmail.style.display = 'none';
    if (stepReset) stepReset.style.display = 'block';
    if (resetFormError) {
      resetFormError.style.display = 'none';
      resetFormError.textContent = '';
      resetFormError.style.background = '';
      resetFormError.style.borderColor = '';
      resetFormError.style.color = '';
    }
    clearOtpInputs();
    if (passwordInput) passwordInput.value = '';
    if (confirmPasswordInput) confirmPasswordInput.value = '';
    startResendTimer(30);
  }

  function showEmailStep() {
    clearInterval(resendInterval);
    if (stepReset) stepReset.style.display = 'none';
    if (stepEmail) stepEmail.style.display = 'block';
    if (emailInput) emailInput.focus();
  }

  function setupOtpDigitInputs() {
    otpDigits.forEach((input, index) => {
      input.addEventListener('focus', () => {
        input.select();
        setTyping(true);
        scheduleRender();
      });

      input.addEventListener('blur', () => {
        setTyping(false);
        scheduleRender();
      });

      input.addEventListener('input', () => {
        const val = input.value.replace(/[^0-9]/g, '');
        input.value = val ? val[val.length - 1] : '';
        if (input.value) {
          input.classList.add('filled');
          if (index < otpDigits.length - 1) {
            otpDigits[index + 1].focus();
          } else {
            if (passwordInput) passwordInput.focus();
          }
        } else {
          input.classList.remove('filled');
        }
      });

      input.addEventListener('keydown', (e) => {
        if (e.key === 'Backspace') {
          if (!input.value && index > 0) {
            otpDigits[index - 1].focus();
            otpDigits[index - 1].value = '';
            otpDigits[index - 1].classList.remove('filled');
            e.preventDefault();
          }
        } else if (e.key === 'ArrowLeft' && index > 0) {
          otpDigits[index - 1].focus();
        } else if (e.key === 'ArrowRight' && index < otpDigits.length - 1) {
          otpDigits[index + 1].focus();
        }
      });

      input.addEventListener('paste', (e) => {
        e.preventDefault();
        const text = (e.clipboardData || window.clipboardData).getData('text').trim();
        const numeric = text.replace(/[^0-9]/g, '').slice(0, 6);
        if (numeric) {
          numeric.split('').forEach((ch, i) => {
            if (otpDigits[i]) {
              otpDigits[i].value = ch;
              otpDigits[i].classList.add('filled');
            }
          });
          const nextIdx = Math.min(numeric.length, 5);
          if (numeric.length === 6 && passwordInput) {
            passwordInput.focus();
          } else if (otpDigits[nextIdx]) {
            otpDigits[nextIdx].focus();
          }
        }
      });
    });
  }

  setupOtpDigitInputs();

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
      validateConfirmPassword();
      passwordLength = passwordInput.value.length;
      updatePeekWatcher();
      scheduleRender();
    });
  }

  if (confirmPasswordInput) {
    confirmPasswordInput.addEventListener('focus', () => { setTyping(true); scheduleRender(); });
    confirmPasswordInput.addEventListener('blur', () => { setTyping(false); scheduleRender(); });
    confirmPasswordInput.addEventListener('input', validateConfirmPassword);
  }

  if (togglePasswordBtn && passwordInput) {
    togglePasswordBtn.addEventListener('click', () => {
      showPassword = !showPassword;
      passwordInput.type = showPassword ? 'text' : 'password';
      if (confirmPasswordInput) confirmPasswordInput.type = showPassword ? 'text' : 'password';
      if (eyeOpen) eyeOpen.style.display = showPassword ? 'block' : 'none';
      if (eyeClosed) eyeClosed.style.display = showPassword ? 'none' : 'block';
      updatePeekWatcher();
      scheduleRender();
    });
  }

  if (btnChangeEmail) {
    btnChangeEmail.addEventListener('click', showEmailStep);
  }

  if (btnResendOtp) {
    btnResendOtp.addEventListener('click', async () => {
      btnResendOtp.disabled = true;
      if (resetFormError) {
        resetFormError.style.display = 'none';
        resetFormError.textContent = '';
      }

      try {
        const response = await fetch('/forgot-password/resend-otp', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-Requested-With': 'XMLHttpRequest'
          },
          body: JSON.stringify({ email: activeResetEmail })
        });
        const data = await response.json();

        if (data.success) {
          if (resetFormError) {
            resetFormError.style.display = 'block';
            resetFormError.style.background = 'rgba(16, 185, 129, 0.12)';
            resetFormError.style.borderColor = 'rgba(16, 185, 129, 0.35)';
            resetFormError.style.color = '#10B981';
            resetFormError.textContent = data.message || 'A new verification code has been sent!';
          }
          clearOtpInputs();
          startResendTimer(30);
        } else {
          btnResendOtp.disabled = false;
          if (resetFormError) {
            resetFormError.style.display = 'block';
            resetFormError.style.background = '';
            resetFormError.style.borderColor = '';
            resetFormError.style.color = '';
            resetFormError.textContent = data.message || 'Failed to resend reset code.';
          }
        }
      } catch (err) {
        btnResendOtp.disabled = false;
        if (resetFormError) {
          resetFormError.style.display = 'block';
          resetFormError.textContent = 'Server connection error. Please try again.';
        }
      }
    });
  }

  function setSendLoading(loading) {
    if (sendOtpBtn) sendOtpBtn.disabled = loading;
    const text = loading ? 'Sending Verification Code...' : 'Send Verification Code';
    if (sendOtpLabel) sendOtpLabel.textContent = text;
    if (sendOtpLabelHover) sendOtpLabelHover.textContent = text;
  }

  function setResetLoading(loading) {
    if (resetSubmitBtn) resetSubmitBtn.disabled = loading;
    const text = loading ? 'Updating Password...' : 'Verify & Reset Password';
    if (resetSubmitLabel) resetSubmitLabel.textContent = text;
    if (resetSubmitLabelHover) resetSubmitLabelHover.textContent = text;
  }

  // STEP 1 FORM SUBMISSION
  if (emailForm) {
    emailForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      if (emailFormError) {
        emailFormError.style.display = 'none';
        emailFormError.textContent = '';
      }

      const emailErr = validateEmail();
      if (emailErr) {
        if (emailFormError) {
          emailFormError.textContent = emailErr;
          emailFormError.style.display = 'block';
        }
        return;
      }

      const emailVal = emailInput.value.trim();
      setSendLoading(true);

      try {
        const response = await fetch('/forgot-password/send-otp', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-Requested-With': 'XMLHttpRequest'
          },
          body: JSON.stringify({ email: emailVal })
        });

        const data = await response.json();
        setSendLoading(false);

        if (data.success && data.otp_sent) {
          showResetStep(emailVal);
        } else {
          if (emailFormError) {
            emailFormError.style.display = 'block';
            emailFormError.textContent = data.message || 'Failed to send reset code.';
          }
        }
      } catch (err) {
        setSendLoading(false);
        if (emailFormError) {
          emailFormError.style.display = 'block';
          emailFormError.textContent = 'Server connection error. Please try again.';
        }
        console.error('Forgot password send OTP error:', err);
      }
    });
  }

  // STEP 2 FORM SUBMISSION
  if (resetForm) {
    resetForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      if (resetFormError) {
        resetFormError.style.display = 'none';
        resetFormError.textContent = '';
        resetFormError.style.background = '';
        resetFormError.style.borderColor = '';
        resetFormError.style.color = '';
      }

      const code = getEnteredOtp();
      if (code.length !== 6) {
        if (resetFormError) {
          resetFormError.style.display = 'block';
          resetFormError.textContent = 'Please enter the complete 6-digit verification code.';
        }
        return;
      }

      const passErr = validatePassword();
      const confirmErr = validateConfirmPassword();
      if (passErr || confirmErr) {
        if (resetFormError) {
          resetFormError.style.display = 'block';
          resetFormError.textContent = passErr || confirmErr;
        }
        return;
      }

      setResetLoading(true);

      try {
        const response = await fetch('/forgot-password/verify-otp', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-Requested-With': 'XMLHttpRequest'
          },
          body: JSON.stringify({
            email: activeResetEmail,
            otp_code: code,
            password: passwordInput.value,
            confirm_password: confirmPasswordInput.value
          })
        });

        const data = await response.json();

        if (data.success) {
          if (resetFormError) {
            resetFormError.style.display = 'block';
            resetFormError.style.background = 'rgba(16, 185, 129, 0.12)';
            resetFormError.style.borderColor = 'rgba(16, 185, 129, 0.35)';
            resetFormError.style.color = '#10B981';
            resetFormError.textContent = data.message || 'Password reset successfully! Redirecting to login...';
          }

          setTimeout(() => {
            window.location.href = data.redirect_url || '/login';
          }, 1500);
        } else {
          setResetLoading(false);
          if (resetFormError) {
            resetFormError.style.display = 'block';
            resetFormError.style.background = '';
            resetFormError.style.borderColor = '';
            resetFormError.style.color = '';
            resetFormError.textContent = data.message || 'Password reset failed.';
          }
        }
      } catch (err) {
        setResetLoading(false);
        if (resetFormError) {
          resetFormError.style.display = 'block';
          resetFormError.style.background = '';
          resetFormError.style.borderColor = '';
          resetFormError.style.color = '';
          resetFormError.textContent = 'Server connection error. Please try again.';
        }
        console.error('Password reset verify error:', err);
      }
    });
  }
})();
