(() => {
  const isRussian = document.documentElement.lang.toLowerCase().startsWith("ru");
  const ui = (english, russian) => isRussian ? russian : english;
  const panel = document.getElementById("metronomePanel");
  if (!panel) return;

  const MIN_BPM = 40;
  const MAX_BPM = 220;
  const LOOKAHEAD_MS = 25;
  const SCHEDULE_AHEAD_SECONDS = 0.1;

  const tempoInput = document.getElementById("tempoInput");
  const tempoDown = document.getElementById("tempoDown");
  const tempoUp = document.getElementById("tempoUp");
  const meterSelect = document.getElementById("meterSelect");
  const beatDisplay = document.getElementById("metronomeBeats");
  const toggleButton = document.getElementById("metronomeToggle");
  const tapButton = document.getElementById("tapTempoButton");
  const status = document.getElementById("metronomeStatus");

  let bpm = 90;
  let beatsPerBar = 4;
  let currentBeat = 0;
  let nextBeatTime = 0;
  let schedulerTimer = null;
  let audioContext = null;
  let isRunning = false;
  let tapTimes = [];
  let visualTimers = [];

  function clamp(value, min, max) {
    return Math.min(max, Math.max(min, value));
  }

  function setBpm(value) {
    const parsed = Number.parseInt(value, 10);
    if (!Number.isFinite(parsed)) return;

    bpm = clamp(parsed, MIN_BPM, MAX_BPM);
    tempoInput.value = String(bpm);
  }

  function renderBeats() {
    beatDisplay.replaceChildren();

    for (let index = 0; index < beatsPerBar; index += 1) {
      const beat = document.createElement("span");
      beat.className = "metronome-beat";
      beat.setAttribute("aria-label", ui(`Beat ${index + 1}`, `Доля ${index + 1}`));
      beatDisplay.appendChild(beat);
    }
  }

  function showBeat(beatIndex, delayMs) {
    const timer = window.setTimeout(() => {
      if (!isRunning) return;

      beatDisplay.querySelectorAll(".metronome-beat").forEach((beat, index) => {
        beat.classList.toggle("active", index === beatIndex);
        beat.classList.toggle("accent", index === beatIndex && beatIndex === 0);
      });
    }, Math.max(0, delayMs));

    visualTimers.push(timer);
  }

  function scheduleClick(beatIndex, time) {
    const oscillator = audioContext.createOscillator();
    const gain = audioContext.createGain();
    const isAccent = beatIndex === 0;

    oscillator.type = "sine";
    oscillator.frequency.setValueAtTime(isAccent ? 1320 : 880, time);
    gain.gain.setValueAtTime(isAccent ? 0.28 : 0.17, time);
    gain.gain.exponentialRampToValueAtTime(0.001, time + 0.045);

    oscillator.connect(gain);
    gain.connect(audioContext.destination);
    oscillator.start(time);
    oscillator.stop(time + 0.05);

    showBeat(beatIndex, (time - audioContext.currentTime) * 1000);
  }

  function advanceBeat() {
    nextBeatTime += 60 / bpm;
    currentBeat = (currentBeat + 1) % beatsPerBar;
  }

  function scheduler() {
    if (!isRunning || !audioContext) return;

    while (nextBeatTime < audioContext.currentTime + SCHEDULE_AHEAD_SECONDS) {
      scheduleClick(currentBeat, nextBeatTime);
      advanceBeat();
    }

    schedulerTimer = window.setTimeout(scheduler, LOOKAHEAD_MS);
  }

  async function startMetronome() {
    if (isRunning) return;

    audioContext = new (window.AudioContext || window.webkitAudioContext)();
    if (audioContext.state === "suspended") {
      await audioContext.resume();
    }

    isRunning = true;
    currentBeat = 0;
    nextBeatTime = audioContext.currentTime + 0.05;
    panel.classList.add("is-running");
    toggleButton.textContent = ui("Stop metronome", "Остановить метроном");
    status.textContent = `${bpm} BPM · ${beatsPerBar === 6 ? "6/8" : `${beatsPerBar}/4`}`;
    status.classList.add("active");
    scheduler();
  }

  async function stopMetronome() {
    isRunning = false;
    window.clearTimeout(schedulerTimer);
    schedulerTimer = null;
    visualTimers.forEach((timer) => window.clearTimeout(timer));
    visualTimers = [];

    if (audioContext) {
      await audioContext.close();
      audioContext = null;
    }

    panel.classList.remove("is-running");
    toggleButton.textContent = ui("Start metronome", "Запустить метроном");
    status.textContent = ui("Stopped", "Остановлен");
    status.classList.remove("active");
    beatDisplay.querySelectorAll(".metronome-beat").forEach((beat) => {
      beat.classList.remove("active", "accent");
    });
  }

  function updateRunningStatus() {
    if (isRunning) {
      status.textContent = `${bpm} BPM · ${beatsPerBar === 6 ? "6/8" : `${beatsPerBar}/4`}`;
    }
  }

  tempoDown.addEventListener("click", () => {
    setBpm(bpm - 1);
    updateRunningStatus();
  });

  tempoUp.addEventListener("click", () => {
    setBpm(bpm + 1);
    updateRunningStatus();
  });

  tempoInput.addEventListener("change", () => {
    setBpm(tempoInput.value);
    updateRunningStatus();
  });

  tempoInput.addEventListener("blur", () => setBpm(tempoInput.value));

  meterSelect.addEventListener("change", () => {
    beatsPerBar = Number.parseInt(meterSelect.value, 10);
    currentBeat = 0;
    renderBeats();
    updateRunningStatus();
  });

  toggleButton.addEventListener("click", () => {
    if (isRunning) {
      stopMetronome();
    } else {
      startMetronome().catch((error) => {
        status.textContent = ui("Audio unavailable", "Звук недоступен");
        console.error(error);
      });
    }
  });

  tapButton.addEventListener("click", () => {
    const now = performance.now();
    tapTimes = tapTimes.filter((time) => now - time < 2000);
    tapTimes.push(now);

    if (tapTimes.length >= 2) {
      const intervals = tapTimes.slice(1).map((time, index) => time - tapTimes[index]);
      const average = intervals.reduce((sum, value) => sum + value, 0) / intervals.length;
      setBpm(Math.round(60000 / average));
      updateRunningStatus();
    }

    tapButton.classList.add("tapped");
    window.setTimeout(() => tapButton.classList.remove("tapped"), 100);
  });

  window.addEventListener("pagehide", () => {
    if (isRunning) stopMetronome();
  });

  setBpm(tempoInput.value);
  renderBeats();
})();
