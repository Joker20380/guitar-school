(() => {
  const BASE_REFERENCE_PITCH = 440;
  const SUPPORTED_REFERENCE_PITCHES = [432, 440];
  let storedReferencePitch = null;
  try {
    storedReferencePitch = Number(window.localStorage.getItem("tunerReferencePitch"));
  } catch (error) {
    console.warn("Could not read tuner reference pitch:", error);
  }
  let referencePitch = SUPPORTED_REFERENCE_PITCHES.includes(storedReferencePitch)
    ? storedReferencePitch
    : 432;

  const STRINGS = [
    { label: "6-я струна", note: "E2", baseFrequency: 82.41 },
    { label: "5-я струна", note: "A2", baseFrequency: 110.00 },
    { label: "4-я струна", note: "D3", baseFrequency: 146.83 },
    { label: "3-я струна", note: "G3", baseFrequency: 196.00 },
    { label: "2-я струна", note: "B3", baseFrequency: 246.94 },
    { label: "1-я струна", note: "E4", baseFrequency: 329.63 },
  ].map((item) => ({
    ...item,
    frequency: item.baseFrequency * referencePitch / BASE_REFERENCE_PITCH,
  }));

  const noteNames = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"];

  const detectedNote = document.getElementById("detectedNote");
  const targetNote = document.getElementById("targetNote");
  const frequencyValue = document.getElementById("frequencyValue");
  const centsValue = document.getElementById("centsValue");

  const tuneNeedle = document.getElementById("tuneNeedle");
  const stabilityNeedle = document.getElementById("stabilityNeedle");
  const tuneLedSegments = Array.from(document.querySelectorAll("#tuneLedStrip span"));

  const tuneHint = document.getElementById("tuneHint");
  const statusPill = document.getElementById("statusPill");
  const startButton = document.getElementById("startButton");
  const stopButton = document.getElementById("stopButton");

  const stringButtons = document.querySelectorAll(".string-button");
  const referenceButtons = document.querySelectorAll(".reference-pitch-button");
  const referencePitchValue = document.getElementById("referencePitchValue");
  const fretStrings = document.querySelectorAll(".fret-string");

  const stabilityLamp = document.getElementById("stabilityLamp");
  const mainTuneMeter = document.querySelector(".vu-meter-main");

  let audioContext = null;
  let analyser = null;
  let source = null;
  let stream = null;
  let buffer = null;
  let rafId = null;

  let selectedTarget = null;
  let lastCents = null;
  let smoothedTune = 0;
  let smoothedStability = 0;
  let displayedCents = 0;
  let missedFrames = 0;

  let centsHistory = [];
  let lockFrames = 0;
  let wasLocked = false;
  let lastLockSoundAt = 0;

  function clamp(value, min, max) {
    return Math.min(max, Math.max(min, value));
  }

  function median(values) {
    if (!values.length) return 0;
    const sorted = [...values].sort((a, b) => a - b);
    return sorted[Math.floor(sorted.length / 2)];
  }

  function setNeedle(element, normalized) {
    if (!element) return;

    const value = clamp(normalized, -1, 1);
    const angle = value * 42;

    element.style.setProperty("--needle-angle", `${angle}deg`);
  }

  function frequencyToNoteName(frequency) {
    if (!frequency || frequency <= 0) return "—";

    const midi = Math.round(69 + 12 * Math.log2(frequency / referencePitch));
    const name = noteNames[((midi % 12) + 12) % 12];
    const octave = Math.floor(midi / 12) - 1;

    return `${name}${octave}`;
  }

  function centsBetween(frequency, targetFrequency) {
    return 1200 * Math.log2(frequency / targetFrequency);
  }

  function getClosestString(frequency) {
    return STRINGS.reduce((closest, item) => {
      const currentDistance = Math.abs(centsBetween(frequency, item.frequency));
      const closestDistance = Math.abs(centsBetween(frequency, closest.frequency));
      return currentDistance < closestDistance ? item : closest;
    }, STRINGS[0]);
  }

  function smoothCents(rawCents) {
    centsHistory.push(rawCents);

    if (centsHistory.length > 7) {
      centsHistory.shift();
    }

    const filtered = median(centsHistory);
    const distance = Math.abs(filtered - displayedCents);
    const factor = distance > 18 ? 0.42 : distance > 7 ? 0.30 : 0.20;

    displayedCents = displayedCents * (1 - factor) + filtered * factor;

    if (Math.abs(displayedCents) < 0.8) {
      displayedCents = 0;
    }

    return displayedCents;
  }

  function setTuneNeedle(cents) {
    const target = clamp(cents, -50, 50) / 50;
    const distance = Math.abs(target - smoothedTune);
    const factor = distance > 0.35 ? 0.34 : 0.24;

    smoothedTune = smoothedTune * (1 - factor) + target * factor;

    if (Math.abs(smoothedTune) < 0.01) {
      smoothedTune = 0;
    }

    setNeedle(tuneNeedle, smoothedTune);
  }

  function setStabilityNeedle(cents) {
    if (lastCents === null) {
      lastCents = cents;
      smoothedStability = 0.2;
    }

    const movement = Math.abs(cents - lastCents);
    const stability = clamp(1 - movement / 12, 0, 1);

    smoothedStability = smoothedStability * 0.82 + stability * 0.18;
    setNeedle(stabilityNeedle, smoothedStability * 2 - 1);

    if (stabilityLamp) {
      stabilityLamp.classList.toggle("active", smoothedStability > 0.70);
    }

    lastCents = cents;
  }

  function updateTuneLedStrip(cents) {
    if (!tuneLedSegments.length) return;

    const abs = Math.abs(cents);
    const direction = cents < 0 ? -1 : cents > 0 ? 1 : 0;
    const strength = Math.min(12, Math.ceil(abs / 4));

    tuneLedSegments.forEach((segment) => {
      segment.classList.remove("on-flat", "on-sharp", "on-lock", "on-near", "warn", "hot");

      const pos = Number(segment.dataset.pos);
      const distance = Math.abs(pos);

      if (abs <= 4 && pos === 0) {
        segment.classList.add("on-lock");
        return;
      }

      if (abs <= 9 && distance <= 1) {
        segment.classList.add("on-near");
        return;
      }

      if (direction < 0 && pos < 0 && distance <= strength) {
        segment.classList.add("on-flat");

        if (distance >= 9) {
          segment.classList.add("hot");
        } else if (distance >= 5) {
          segment.classList.add("warn");
        }
      }

      if (direction > 0 && pos > 0 && distance <= strength) {
        segment.classList.add("on-sharp");

        if (distance >= 9) {
          segment.classList.add("hot");
        } else if (distance >= 5) {
          segment.classList.add("warn");
        }
      }
    });
  }

  function clearTuneLedStrip() {
    tuneLedSegments.forEach((segment) => {
      segment.classList.remove("on-flat", "on-sharp", "on-lock", "on-near", "warn", "hot");
    });
  }

  function playTone(frequency = 784, duration = 0.32, volume = 0.13) {
    if (!audioContext) return;

    try {
      const start = audioContext.currentTime;

      const master = audioContext.createGain();
      master.gain.setValueAtTime(0.0001, start);
      master.gain.exponentialRampToValueAtTime(volume, start + 0.018);
      master.gain.exponentialRampToValueAtTime(0.0001, start + duration);

      const filter = audioContext.createBiquadFilter();
      filter.type = "lowpass";
      filter.frequency.setValueAtTime(5200, start);
      filter.Q.setValueAtTime(0.7, start);

      filter.connect(master);
      master.connect(audioContext.destination);

      const osc1 = audioContext.createOscillator();
      osc1.type = "triangle";
      osc1.frequency.setValueAtTime(frequency, start);
      osc1.connect(filter);
      osc1.start(start);
      osc1.stop(start + duration + 0.03);

      const osc2 = audioContext.createOscillator();
      osc2.type = "sine";
      osc2.frequency.setValueAtTime(frequency * 2, start);
      osc2.connect(filter);
      osc2.start(start + 0.02);
      osc2.stop(start + duration * 0.72);
    } catch (error) {
      console.warn("Tone failed:", error);
    }
  }

  function playLockSound() {
    if (!audioContext) return;

    const now = performance.now();

    if (now - lastLockSoundAt < 1900) return;

    lastLockSoundAt = now;

    try {
      if (audioContext.state === "suspended") {
        audioContext.resume();
      }

      const start = audioContext.currentTime;
      const duration = 0.68;

      const master = audioContext.createGain();
      master.gain.setValueAtTime(0.0001, start);
      master.gain.exponentialRampToValueAtTime(0.16, start + 0.018);
      master.gain.exponentialRampToValueAtTime(0.055, start + 0.28);
      master.gain.exponentialRampToValueAtTime(0.0001, start + duration);

      const filter = audioContext.createBiquadFilter();
      filter.type = "lowpass";
      filter.frequency.setValueAtTime(6400, start);
      filter.Q.setValueAtTime(0.55, start);

      filter.connect(master);
      master.connect(audioContext.destination);

      const notes = [
        { frequency: 880.00, delay: 0.00, length: 0.46, type: "triangle", gain: 1.00 },
        { frequency: 1174.66, delay: 0.09, length: 0.46, type: "sine", gain: 0.72 },
        { frequency: 1760.00, delay: 0.18, length: 0.34, type: "sine", gain: 0.38 },
      ];

      notes.forEach((note) => {
        const noteGain = audioContext.createGain();
        const t = start + note.delay;

        noteGain.gain.setValueAtTime(0.0001, t);
        noteGain.gain.exponentialRampToValueAtTime(note.gain, t + 0.016);
        noteGain.gain.exponentialRampToValueAtTime(0.0001, t + note.length);

        noteGain.connect(filter);

        const osc = audioContext.createOscillator();
        osc.type = note.type;
        osc.frequency.setValueAtTime(note.frequency, t);
        osc.connect(noteGain);
        osc.start(t);
        osc.stop(t + note.length + 0.04);
      });

      if (navigator.vibrate) {
        navigator.vibrate([35, 25, 35]);
      }
    } catch (error) {
      console.warn("Lock sound failed:", error);
    }
  }

  function setFeedback(cents) {
    const isLocked = Math.abs(cents) <= 4;
    const isNear = !isLocked && Math.abs(cents) <= 9;

    updateTuneLedStrip(cents);

    if (mainTuneMeter) {
      mainTuneMeter.classList.toggle("is-locked", isLocked);
      mainTuneMeter.classList.toggle("is-near", isNear);
    }

    if (isLocked) {
      lockFrames += 1;

      if (lockFrames >= 5 && !wasLocked) {
        playLockSound();
        wasLocked = true;
      }

      return;
    }

    lockFrames = 0;

    if (Math.abs(cents) > 11) {
      wasLocked = false;
    }
  }

  function clearFeedback() {
    clearTuneLedStrip();

    if (stabilityLamp) {
      stabilityLamp.classList.remove("active");
    }

    if (mainTuneMeter) {
      mainTuneMeter.classList.remove("is-locked");
      mainTuneMeter.classList.remove("is-near");
    }

    lockFrames = 0;
  }

  function setHint(cents) {
    if (!tuneHint) return;

    tuneHint.className = "hint";

    if (Math.abs(cents) <= 4) {
      tuneHint.textContent = "Точно. Струна настроена.";
      tuneHint.classList.add("ok");
      return;
    }

    if (Math.abs(cents) <= 9) {
      tuneHint.textContent = "Почти точно. Доведи стрелку в центр.";
      tuneHint.classList.add("near");
      return;
    }

    tuneHint.classList.add("bad");

    if (cents < 0) {
      tuneHint.textContent = "Ниже нужной ноты. Подтяни струну.";
    } else {
      tuneHint.textContent = "Выше нужной ноты. Немного ослабь струну.";
    }
  }

  function highlightTarget(note) {
    stringButtons.forEach((button) => {
      if (selectedTarget) {
        button.classList.toggle("active", button.dataset.note === note);
      } else {
        button.classList.toggle("active", button.dataset.note === "AUTO");
      }
    });

    fretStrings.forEach((string) => {
      string.classList.toggle("active", string.dataset.note === note);
    });
  }

  function clearFretboard() {
    fretStrings.forEach((string) => string.classList.remove("active"));
  }

  function setWaitingState(message = "Сыграй открытую струну") {
    detectedNote.textContent = "—";
    frequencyValue.textContent = "0.00 Hz";
    centsValue.textContent = "0 cents";

    smoothedTune = smoothedTune * 0.96;
    setNeedle(tuneNeedle, smoothedTune);
    setNeedle(stabilityNeedle, -1);

    clearFeedback();

    tuneHint.className = "hint";
    tuneHint.textContent = message;

    if (!selectedTarget) {
      targetNote.textContent = "Автоопределение";
      clearFretboard();
    }
  }

  function applyReferencePitch(nextPitch, persist = true) {
    const parsedPitch = Number(nextPitch);
    if (!SUPPORTED_REFERENCE_PITCHES.includes(parsedPitch)) return;

    referencePitch = parsedPitch;
    STRINGS.forEach((item) => {
      item.frequency = item.baseFrequency * referencePitch / BASE_REFERENCE_PITCH;
    });

    stringButtons.forEach((button) => {
      const string = STRINGS.find((item) => item.note === button.dataset.note);
      if (string) button.dataset.frequency = string.frequency.toFixed(2);
    });

    referenceButtons.forEach((button) => {
      const isActive = Number(button.dataset.referencePitch) === referencePitch;
      button.classList.toggle("active", isActive);
      button.setAttribute("aria-pressed", String(isActive));
    });

    if (referencePitchValue) {
      referencePitchValue.textContent = `A4 = ${referencePitch} Гц`;
    }

    if (selectedTarget) {
      selectedTarget = STRINGS.find((item) => item.note === selectedTarget.note) || null;
    }

    centsHistory = [];
    displayedCents = 0;
    lastCents = null;
    setWaitingState("Сыграй открытую струну");

    if (persist) {
      try {
        window.localStorage.setItem("tunerReferencePitch", String(referencePitch));
      } catch (error) {
        console.warn("Could not save tuner reference pitch:", error);
      }
    }
  }

  function updateDisplay(frequency) {
    const detected = frequencyToNoteName(frequency);
    const target = selectedTarget || getClosestString(frequency);
    const rawCents = centsBetween(frequency, target.frequency);
    const cents = smoothCents(rawCents);

    missedFrames = 0;

    detectedNote.textContent = detected;
    targetNote.textContent = `${target.label} · ${target.note}`;
    frequencyValue.textContent = `${frequency.toFixed(2)} Hz`;
    centsValue.textContent = `${cents > 0 ? "+" : ""}${cents.toFixed(1)} cents`;

    setTuneNeedle(cents);
    setStabilityNeedle(cents);
    setFeedback(cents);
    setHint(cents);
    highlightTarget(target.note);
  }

  function calculateRms(inputBuffer) {
    let rms = 0;

    for (let i = 0; i < inputBuffer.length; i += 1) {
      rms += inputBuffer[i] * inputBuffer[i];
    }

    return Math.sqrt(rms / inputBuffer.length);
  }

  function autoCorrelate(inputBuffer, sampleRate, rms) {
    if (rms < 0.008) return null;

    let start = 0;
    let end = inputBuffer.length - 1;
    const threshold = 0.2;

    for (let i = 0; i < inputBuffer.length / 2; i += 1) {
      if (Math.abs(inputBuffer[i]) < threshold) {
        start = i;
        break;
      }
    }

    for (let i = 1; i < inputBuffer.length / 2; i += 1) {
      if (Math.abs(inputBuffer[inputBuffer.length - i]) < threshold) {
        end = inputBuffer.length - i;
        break;
      }
    }

    const trimmed = inputBuffer.slice(start, end);
    const size = trimmed.length;

    if (size < 2) return null;

    const correlations = new Array(size).fill(0);

    for (let lag = 0; lag < size; lag += 1) {
      for (let i = 0; i < size - lag; i += 1) {
        correlations[lag] += trimmed[i] * trimmed[i + lag];
      }
    }

    let d = 0;

    while (d + 1 < correlations.length && correlations[d] > correlations[d + 1]) {
      d += 1;
    }

    let maxValue = -1;
    let maxPosition = -1;

    for (let i = d; i < size; i += 1) {
      if (correlations[i] > maxValue) {
        maxValue = correlations[i];
        maxPosition = i;
      }
    }

    if (maxPosition <= 0 || maxPosition + 1 >= correlations.length) {
      return null;
    }

    const x1 = correlations[maxPosition - 1];
    const x2 = correlations[maxPosition];
    const x3 = correlations[maxPosition + 1];
    const divisor = 2 * (2 * x2 - x1 - x3);

    if (!divisor) {
      return sampleRate / maxPosition;
    }

    const correction = (x3 - x1) / divisor;
    return sampleRate / (maxPosition + correction);
  }

  function tick() {
    if (!analyser || !audioContext || !buffer) return;

    analyser.getFloatTimeDomainData(buffer);

    const rms = calculateRms(buffer);
    const pitch = autoCorrelate(buffer, audioContext.sampleRate, rms);

    if (pitch && pitch > 60 && pitch < 420) {
      updateDisplay(pitch);
    } else {
      missedFrames += 1;

      if (missedFrames > 18) {
        setWaitingState();
        lastCents = null;
        centsHistory = [];
      } else {
        smoothedTune = smoothedTune * 0.985;
        setNeedle(tuneNeedle, smoothedTune);
      }
    }

    rafId = requestAnimationFrame(tick);
  }

  async function startTuner() {
    try {
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        throw new Error("getUserMedia is not supported");
      }

      audioContext = new (window.AudioContext || window.webkitAudioContext)();

      if (audioContext.state === "suspended") {
        await audioContext.resume();
      }

      playTone(784, 0.28, 0.12);

      stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: false,
          noiseSuppression: false,
          autoGainControl: false,
        },
      });

      analyser = audioContext.createAnalyser();
      analyser.fftSize = 8192;

      buffer = new Float32Array(analyser.fftSize);
      source = audioContext.createMediaStreamSource(stream);
      source.connect(analyser);

      statusPill.textContent = "Микрофон включён";
      statusPill.classList.add("active");

      startButton.disabled = true;
      stopButton.disabled = false;

      missedFrames = 0;
      centsHistory = [];
      lockFrames = 0;
      wasLocked = false;

      setWaitingState("Сыграй открытую струну");
      tick();
    } catch (error) {
      statusPill.textContent = "Нет доступа к микрофону";
      statusPill.classList.remove("active");
      tuneHint.textContent = "Разреши доступ к микрофону в браузере.";
      console.error(error);
    }
  }

  async function stopTuner() {
    if (rafId) {
      cancelAnimationFrame(rafId);
      rafId = null;
    }

    if (stream) {
      stream.getTracks().forEach((track) => track.stop());
      stream = null;
    }

    if (audioContext) {
      await audioContext.close();
      audioContext = null;
    }

    analyser = null;
    source = null;
    buffer = null;
    lastCents = null;
    smoothedTune = 0;
    smoothedStability = 0;
    displayedCents = 0;
    missedFrames = 0;
    centsHistory = [];
    lockFrames = 0;
    wasLocked = false;

    statusPill.textContent = "Микрофон выключен";
    statusPill.classList.remove("active");

    startButton.disabled = false;
    stopButton.disabled = true;

    setWaitingState("Нажми «Включить тюнер»");
  }

  stringButtons.forEach((button) => {
    button.addEventListener("click", () => {
      const note = button.dataset.note;

      centsHistory = [];
      displayedCents = 0;
      lockFrames = 0;
      wasLocked = false;

      if (note === "AUTO") {
        selectedTarget = null;

        stringButtons.forEach((item) => item.classList.remove("active"));
        button.classList.add("active");

        targetNote.textContent = "Автоопределение";
        clearFretboard();
        return;
      }

      selectedTarget = STRINGS.find((item) => item.note === note) || null;

      stringButtons.forEach((item) => item.classList.remove("active"));
      button.classList.add("active");

      targetNote.textContent = `${selectedTarget.label} · ${selectedTarget.note}`;
      highlightTarget(note);
    });
  });

  referenceButtons.forEach((button) => {
    button.addEventListener("click", () => {
      applyReferencePitch(button.dataset.referencePitch);
    });
  });

  startButton.addEventListener("click", startTuner);
  stopButton.addEventListener("click", stopTuner);

  applyReferencePitch(referencePitch, false);
  setNeedle(tuneNeedle, 0);
  setNeedle(stabilityNeedle, -1);
  setWaitingState("Нажми «Включить тюнер»");
})();
