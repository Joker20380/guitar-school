(() => {
  const GUITAR_STRINGS = [
    { note: "E2", frequency: 82.41, label: "6-я струна · E2" },
    { note: "A2", frequency: 110.00, label: "5-я струна · A2" },
    { note: "D3", frequency: 146.83, label: "4-я струна · D3" },
    { note: "G3", frequency: 196.00, label: "3-я струна · G3" },
    { note: "B3", frequency: 246.94, label: "2-я струна · B3" },
    { note: "E4", frequency: 329.63, label: "1-я струна · E4" },
  ];

  const startButton = document.getElementById("startButton");
  const stopButton = document.getElementById("stopButton");
  const statusPill = document.getElementById("statusPill");
  const detectedNote = document.getElementById("detectedNote");
  const targetNote = document.getElementById("targetNote");
  const frequencyValue = document.getElementById("frequencyValue");
  const centsValue = document.getElementById("centsValue");
  const needle = document.getElementById("needle");
  const tuneHint = document.getElementById("tuneHint");
  const stringButtons = Array.from(document.querySelectorAll(".string-button"));

  let audioContext = null;
  let analyser = null;
  let mediaStream = null;
  let source = null;
  let rafId = null;
  let selectedString = null;

  function setStatus(active, text) {
    statusPill.textContent = text;
    statusPill.classList.toggle("active", active);
  }

  function frequencyToCents(frequency, targetFrequency) {
    return 1200 * Math.log2(frequency / targetFrequency);
  }

  function findClosestString(frequency) {
    return GUITAR_STRINGS.reduce((best, item) => {
      const currentDiff = Math.abs(Math.log2(frequency / item.frequency));
      const bestDiff = Math.abs(Math.log2(frequency / best.frequency));
      return currentDiff < bestDiff ? item : best;
    }, GUITAR_STRINGS[0]);
  }

  function setNeedle(cents) {
    const clamped = Math.max(-50, Math.min(50, cents));
    const percent = ((clamped + 50) / 100) * 100;
    needle.style.left = `${percent}%`;
  }

  function updateHint(cents) {
    tuneHint.classList.remove("ok", "bad");

    if (Math.abs(cents) <= 5) {
      tuneHint.textContent = "Точно. Струна настроена.";
      tuneHint.classList.add("ok");
      return;
    }

    if (cents < 0) {
      tuneHint.textContent = "Ниже нормы. Подтяни струну.";
      tuneHint.classList.add("bad");
      return;
    }

    tuneHint.textContent = "Выше нормы. Ослабь струну.";
    tuneHint.classList.add("bad");
  }

  function autoCorrelate(buffer, sampleRate) {
    const size = buffer.length;
    let rms = 0;

    for (let i = 0; i < size; i += 1) {
      rms += buffer[i] * buffer[i];
    }

    rms = Math.sqrt(rms / size);

    if (rms < 0.01) {
      return -1;
    }

    let r1 = 0;
    let r2 = size - 1;
    const threshold = 0.2;

    for (let i = 0; i < size / 2; i += 1) {
      if (Math.abs(buffer[i]) < threshold) {
        r1 = i;
        break;
      }
    }

    for (let i = 1; i < size / 2; i += 1) {
      if (Math.abs(buffer[size - i]) < threshold) {
        r2 = size - i;
        break;
      }
    }

    buffer = buffer.slice(r1, r2);

    const newSize = buffer.length;
    const correlations = new Array(newSize).fill(0);

    for (let lag = 0; lag < newSize; lag += 1) {
      for (let i = 0; i < newSize - lag; i += 1) {
        correlations[lag] += buffer[i] * buffer[i + lag];
      }
    }

    let d = 0;

    while (correlations[d] > correlations[d + 1]) {
      d += 1;
    }

    let maxValue = -1;
    let maxPosition = -1;

    for (let i = d; i < newSize; i += 1) {
      if (correlations[i] > maxValue) {
        maxValue = correlations[i];
        maxPosition = i;
      }
    }

    if (maxPosition <= 0) {
      return -1;
    }

    const x1 = correlations[maxPosition - 1] || 0;
    const x2 = correlations[maxPosition] || 0;
    const x3 = correlations[maxPosition + 1] || 0;

    const a = (x1 + x3 - 2 * x2) / 2;
    const b = (x3 - x1) / 2;

    if (a) {
      maxPosition = maxPosition - b / (2 * a);
    }

    return sampleRate / maxPosition;
  }

  function update() {
    if (!analyser || !audioContext) {
      return;
    }

    const buffer = new Float32Array(analyser.fftSize);
    analyser.getFloatTimeDomainData(buffer);

    const frequency = autoCorrelate(buffer, audioContext.sampleRate);

    if (frequency > 60 && frequency < 500) {
      const target = selectedString || findClosestString(frequency);
      const cents = frequencyToCents(frequency, target.frequency);

      detectedNote.textContent = target.note;
      targetNote.textContent = `Целевая струна: ${target.label}`;
      frequencyValue.textContent = `${frequency.toFixed(2)} Hz`;
      centsValue.textContent = `${cents > 0 ? "+" : ""}${cents.toFixed(1)} cents`;

      setNeedle(cents);
      updateHint(cents);
    } else {
      detectedNote.textContent = "—";
      frequencyValue.textContent = "0.00 Hz";
      centsValue.textContent = "0 cents";
      targetNote.textContent = selectedString
        ? `Целевая струна: ${selectedString.label}`
        : "Целевая струна: —";
      tuneHint.textContent = "Сыграй одну открытую струну";
      tuneHint.classList.remove("ok", "bad");
      setNeedle(0);
    }

    rafId = requestAnimationFrame(update);
  }

  async function startTuner() {
    try {
      mediaStream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: false,
          noiseSuppression: false,
          autoGainControl: false,
        },
      });

      audioContext = new AudioContext();
      analyser = audioContext.createAnalyser();
      analyser.fftSize = 4096;

      source = audioContext.createMediaStreamSource(mediaStream);
      source.connect(analyser);

      startButton.disabled = true;
      stopButton.disabled = false;

      setStatus(true, "Микрофон включен");
      tuneHint.textContent = "Сыграй открытую струну";

      update();
    } catch (error) {
      console.error(error);
      setStatus(false, "Нет доступа к микрофону");
      tuneHint.textContent = "Браузер не дал доступ к микрофону";
      tuneHint.classList.add("bad");
    }
  }

  function stopTuner() {
    if (rafId) {
      cancelAnimationFrame(rafId);
      rafId = null;
    }

    if (source) {
      source.disconnect();
      source = null;
    }

    if (mediaStream) {
      mediaStream.getTracks().forEach((track) => track.stop());
      mediaStream = null;
    }

    if (audioContext) {
      audioContext.close();
      audioContext = null;
    }

    analyser = null;

    startButton.disabled = false;
    stopButton.disabled = true;

    detectedNote.textContent = "—";
    frequencyValue.textContent = "0.00 Hz";
    centsValue.textContent = "0 cents";
    setNeedle(0);
    setStatus(false, "Микрофон выключен");
    tuneHint.textContent = "Нажми «Включить тюнер»";
    tuneHint.classList.remove("ok", "bad");
  }

  stringButtons.forEach((button) => {
    button.addEventListener("click", () => {
      const note = button.dataset.note;
      const frequency = Number(button.dataset.frequency);

      selectedString = GUITAR_STRINGS.find((item) => {
        return item.note === note && Number(item.frequency.toFixed(2)) === Number(frequency.toFixed(2));
      });

      stringButtons.forEach((item) => item.classList.remove("active"));
      button.classList.add("active");

      if (selectedString) {
        targetNote.textContent = `Целевая струна: ${selectedString.label}`;
        tuneHint.textContent = `Выбрана ${selectedString.label}`;
      }
    });
  });

  startButton.addEventListener("click", startTuner);
  stopButton.addEventListener("click", stopTuner);

  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    startButton.disabled = true;
    setStatus(false, "Микрофон не поддерживается");
    tuneHint.textContent = "Этот браузер не поддерживает доступ к микрофону";
    tuneHint.classList.add("bad");
  }
})();
