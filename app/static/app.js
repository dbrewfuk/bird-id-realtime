const frameInterval =
  Number.parseInt(document.body.dataset.frameInterval || "1200", 10) || 1200;

// ── DOM refs ──────────────────────────────────────────────────

const video           = document.getElementById("video");
const streamPreview   = document.getElementById("stream-preview");
const canvas          = document.getElementById("capture-canvas");
const toggleButton    = document.getElementById("source-toggle");
const sourceModeSelect = document.getElementById("source-mode");
const cameraDeviceField = document.getElementById("camera-device-field");
const cameraDeviceSelect = document.getElementById("camera-device");
const streamUrlField  = document.getElementById("stream-url-field");
const streamUrlInput  = document.getElementById("stream-url");
const birdName        = document.getElementById("bird-name");
const birdConfidence  = document.getElementById("bird-confidence");
const guidanceText    = document.getElementById("guidance-text");
const predictionList  = document.getElementById("prediction-list");
const bboxContainer   = document.querySelector(".viewport");
// Pool of bbox elements — grown on demand, never shrunk
const bboxPool = [{ el: document.getElementById("bbox"), label: document.getElementById("bbox-label") }];
const cameraControls  = document.getElementById("camera-controls");
const statusDot       = document.getElementById("status-dot");
const sightingsDrawer = document.getElementById("sightings-drawer");
const sightingsToggle = document.getElementById("sightings-toggle");
const closeDrawer     = document.getElementById("close-drawer");
const sightingsLog    = document.getElementById("sightings-log");
const clearSightings  = document.getElementById("clear-sightings");
const sightingCount   = document.getElementById("sighting-count");

// ── State ─────────────────────────────────────────────────────

let stream          = null;
let intervalId      = null;
let inflight        = false;
let rollingPredictions = [];
let activeSourceMode = null;
// Per-label cooldown so each species logs independently
const lastLoggedTimes = new Map(); // label → timestamp
let totalSightings  = 0;

const clientId = globalThis.crypto?.randomUUID?.() || `client-${Date.now()}`;

// ── Sightings drawer ──────────────────────────────────────────

sightingsToggle.addEventListener("click", () => {
  sightingsDrawer.classList.add("open");
  sightingsDrawer.setAttribute("aria-hidden", "false");
});

closeDrawer.addEventListener("click", () => {
  sightingsDrawer.classList.remove("open");
  sightingsDrawer.setAttribute("aria-hidden", "true");
});

clearSightings.addEventListener("click", () => {
  sightingsLog.innerHTML =
    '<p class="sightings-empty" id="sightings-empty">No sightings yet.</p>';
  totalSightings = 0;
  sightingCount.hidden = true;
  lastLoggedTimes.clear();
});

function logSighting(label, score, previewDataUrl) {
  const emptyMsg = document.getElementById("sightings-empty");
  if (emptyMsg) emptyMsg.remove();

  totalSightings++;
  sightingCount.textContent = totalSightings;
  sightingCount.hidden = false;

  const time = new Date().toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  });

  const entry = document.createElement("div");
  entry.className = "sighting-entry";
  entry.innerHTML = `
    ${previewDataUrl
      ? `<img class="sighting-thumb" src="${previewDataUrl}" alt="${label}" />`
      : `<div class="sighting-thumb sighting-thumb-empty"></div>`}
    <div class="sighting-info">
      <div class="sighting-label">${label}</div>
      <div class="sighting-meta">${score}% &middot; ${time}</div>
    </div>
  `;

  sightingsLog.insertBefore(entry, sightingsLog.firstChild);
}

// ── Status dot ────────────────────────────────────────────────

function setStatus(state) {
  statusDot.className = "status-dot";
  if (state) statusDot.classList.add(state);
}

// ── Camera controls ───────────────────────────────────────────

function buildCameraControls() {
  const track = stream?.getVideoTracks()[0];
  if (!track) return;

  const caps = track.getCapabilities?.() || {};
  const settings = track.getSettings?.() || {};

  const supported = [
    { key: "zoom",               label: "Zoom" },
    { key: "brightness",         label: "Brightness" },
    { key: "contrast",           label: "Contrast" },
    { key: "saturation",         label: "Saturation" },
    { key: "sharpness",          label: "Sharpness" },
    { key: "exposureCompensation", label: "Exposure" },
  ].filter(({ key }) => caps[key]?.min !== undefined);

  if (!supported.length) {
    cameraControls.hidden = true;
    return;
  }

  cameraControls.innerHTML = supported.map(({ key, label }) => {
    const { min, max, step } = caps[key];
    const value = settings[key] ?? min;
    return `
      <label class="control-field">
        <span class="muted-label">${label}</span>
        <input type="range" class="camera-slider" data-key="${key}"
          min="${min}" max="${max}" step="${step || 1}" value="${value}" />
      </label>`;
  }).join("");

  cameraControls.hidden = false;

  cameraControls.querySelectorAll(".camera-slider").forEach((slider) => {
    slider.addEventListener("input", () => {
      track.applyConstraints({
        advanced: [{ [slider.dataset.key]: Number(slider.value) }],
      });
    });
  });
}

// ── Camera devices ────────────────────────────────────────────

async function refreshCameraDevices() {
  if (!navigator.mediaDevices?.enumerateDevices) return;

  const devices = await navigator.mediaDevices.enumerateDevices();
  const cameras = devices.filter((d) => d.kind === "videoinput");
  const currentValue = cameraDeviceSelect.value;
  cameraDeviceSelect.innerHTML = '<option value="">Default camera</option>';

  cameras.forEach((cam, i) => {
    const opt = document.createElement("option");
    opt.value = cam.deviceId;
    opt.textContent = cam.label || `Camera ${i + 1}`;
    cameraDeviceSelect.appendChild(opt);
  });

  if ([...cameraDeviceSelect.options].some((o) => o.value === currentValue)) {
    cameraDeviceSelect.value = currentValue;
  }
}

// ── Start / stop ──────────────────────────────────────────────

async function startCamera() {
  try {
    const deviceId = cameraDeviceSelect.value;
    stream = await navigator.mediaDevices.getUserMedia({
      video: {
        ...(deviceId
          ? { deviceId: { exact: deviceId } }
          : { facingMode: "environment" }),
        width: { ideal: 1280 },
        height: { ideal: 720 },
      },
      audio: false,
    });

    video.srcObject = stream;
    video.hidden = false;
    streamPreview.hidden = true;
    activeSourceMode = "camera";

    toggleButton.textContent = "Stop";
    toggleButton.classList.add("running");
    setStatus("scanning");
    guidanceText.textContent = "Hold steady — the ID sharpens over a few frames.";

    await refreshCameraDevices();
    buildCameraControls();
    intervalId = window.setInterval(sampleFrame, frameInterval);
    sampleFrame();
  } catch {
    setStatus("error");
    guidanceText.textContent =
      "Camera access blocked. Allow permissions and try again.";
  }
}

async function startStream() {
  const url = streamUrlInput.value.trim();
  if (!url) {
    guidanceText.textContent =
      "Paste an RTSP or HLS URL from Scrypted or ring-mqtt.";
    setStatus("error");
    return;
  }

  stopMediaTracks();
  video.hidden = true;
  streamPreview.hidden = false;
  activeSourceMode = "stream";

  toggleButton.textContent = "Stop";
  toggleButton.classList.add("running");
  setStatus("scanning");
  guidanceText.textContent = "Sampling frames from the Ring stream.";

  intervalId = window.setInterval(sampleStream, frameInterval);
  sampleStream();
}

function stopMediaTracks() {
  if (stream) {
    stream.getTracks().forEach((t) => t.stop());
    stream = null;
  }
  video.srcObject = null;
}

function stopCamera() {
  if (intervalId) {
    window.clearInterval(intervalId);
    intervalId = null;
  }

  cameraControls.hidden = true;
  cameraControls.innerHTML = "";
  stopMediaTracks();
  inflight = false;
  rollingPredictions = [];
  activeSourceMode = null;

  toggleButton.textContent = "Start";
  toggleButton.classList.remove("running");
  setStatus(null);
  setBirdName("Waiting…");
  birdConfidence.textContent = "—";
  birdConfidence.classList.remove("high");
  guidanceText.textContent = "Start the camera to begin.";
  predictionList.innerHTML = "";
  renderDetections([]);

  streamPreview.hidden = true;
  streamPreview.removeAttribute("src");
  video.hidden = false;
}

// ── Frame sampling ────────────────────────────────────────────

async function sampleFrame() {
  if (!stream || inflight || video.readyState < 2) return;
  inflight = true;

  const ctx = canvas.getContext("2d");
  const w = video.videoWidth;
  const h = video.videoHeight;

  if (!w || !h) { inflight = false; return; }

  const scale = Math.min(1, 960 / Math.max(w, h));
  canvas.width  = Math.round(w * scale);
  canvas.height = Math.round(h * scale);
  ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

  try {
    const res = await fetch("/api/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ frame: canvas.toDataURL("image/jpeg", 0.84), client_id: clientId }),
    });

    if (!res.ok) throw new Error("analysis failed");
    consumeResult(await res.json());
  } catch {
    setStatus("error");
    guidanceText.textContent =
      "The server couldn't classify this frame. Check logs if it keeps happening.";
  } finally {
    inflight = false;
  }
}

async function sampleStream() {
  if (activeSourceMode !== "stream" || inflight) return;
  inflight = true;

  try {
    const res = await fetch("/api/analyze-stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        client_id: clientId,
        stream_url: streamUrlInput.value.trim(),
      }),
    });

    const result = await res.json();
    if (!res.ok) throw new Error(result.detail || "stream analysis failed");
    consumeResult(result);
  } catch (err) {
    setStatus("error");
    guidanceText.textContent =
      err.message || "Check the RTSP/HLS URL and whether the stream is reachable.";
    renderBoundingBox(null, false);
  } finally {
    inflight = false;
  }
}

// ── Bbox pool ─────────────────────────────────────────────────

function getBbox(index) {
  if (bboxPool[index]) return bboxPool[index];
  const el = document.createElement("div");
  el.className = "bbox";
  el.hidden = true;
  el.style.zIndex = "10";
  const label = document.createElement("div");
  label.className = "bbox-label";
  el.appendChild(label);
  bboxContainer.appendChild(el);
  bboxPool[index] = { el, label };
  return bboxPool[index];
}

function renderDetections(detections) {
  detections.forEach((det, i) => {
    const { el, label } = getBbox(i);
    const box = det.detection?.bbox;
    if (!box) { el.hidden = true; return; }
    el.hidden = false;
    el.style.left   = `${box.x * 100}%`;
    el.style.top    = `${box.y * 100}%`;
    el.style.width  = `${box.width * 100}%`;
    el.style.height = `${box.height * 100}%`;
    el.classList.toggle("bbox--confident", det.confident);
    label.textContent = `${det.best_match.label} · ${Math.round(det.best_match.confidence_percent)}%`;
  });
  // Hide unused pool slots
  for (let i = detections.length; i < bboxPool.length; i++) {
    bboxPool[i].el.hidden = true;
  }
}

// ── Consume result ────────────────────────────────────────────

function consumeResult(result) {
  if (result.preview_frame) {
    streamPreview.src = result.preview_frame;
  }

  const detections = result.detections?.length ? result.detections : [];

  if (!detections.length) {
    rollingPredictions = [];
    setBirdName(result.person_detected ? "Person detected" : "No bird in frame");
    birdConfidence.textContent = "—";
    birdConfidence.classList.remove("high");
    guidanceText.textContent = result.guidance;
    setStatus("scanning");
    predictionList.innerHTML = "";
    renderDetections([]);
    return;
  }

  // Log any detection above 50% with per-label cooldown
  detections.forEach((det) => {
    const label = det.best_match.label;
    const score = det.best_match.confidence_percent;
    const last  = lastLoggedTimes.get(label) || 0;
    if (score >= 50 && Date.now() - last > 30000) {
      logSighting(label, Math.round(score), result.preview_frame);
      lastLoggedTimes.set(label, Date.now());
    }
  });

  const primary = detections[0];
  setBirdName(primary.best_match.label);
  birdConfidence.textContent = `${Math.round(primary.best_match.confidence_percent)}%`;
  birdConfidence.classList.toggle("high", primary.confident);
  guidanceText.textContent = result.guidance;
  setStatus(primary.confident ? "confident" : "scanning");

  predictionList.innerHTML = "";
  if (detections.length > 1) {
    // Multi-bird: one row per detected bird
    detections.forEach((det, i) => {
      const li = document.createElement("li");
      li.className = "prediction-item";
      li.innerHTML = `
        <span class="prediction-rank">${i + 1}</span>
        <span class="prediction-label">${det.best_match.label}</span>
        <span class="prediction-score">${Math.round(det.best_match.confidence_percent)}%</span>
      `;
      predictionList.appendChild(li);
    });
  } else {
    // Single bird: top species candidates
    primary.predictions.forEach((p, i) => {
      const li = document.createElement("li");
      li.className = "prediction-item";
      li.innerHTML = `
        <span class="prediction-rank">${i + 1}</span>
        <span class="prediction-label">${p.label}</span>
        <span class="prediction-score">${Math.round(p.confidence_percent)}%</span>
      `;
      predictionList.appendChild(li);
    });
  }

  renderDetections(detections);
}

// ── Species name cross-fade ───────────────────────────────────

let nameTimer = null;

function setBirdName(name) {
  if (birdName.textContent === name) return;
  clearTimeout(nameTimer);
  birdName.classList.add("updating");
  nameTimer = setTimeout(() => {
    birdName.textContent = name;
    birdName.classList.remove("updating");
  }, 180);
}

// ── Source controls ───────────────────────────────────────────

function syncSourceControls() {
  const mode = sourceModeSelect.value;
  cameraDeviceField.hidden = mode !== "camera";
  streamUrlField.hidden    = mode !== "stream";
  video.hidden = mode === "stream" && !activeSourceMode;
  if (mode === "camera" && !streamPreview.hidden && !activeSourceMode) {
    streamPreview.hidden = true;
  }
}

toggleButton.addEventListener("click", () => {
  if (activeSourceMode) { stopCamera(); return; }
  sourceModeSelect.value === "stream" ? startStream() : startCamera();
});

sourceModeSelect.addEventListener("change", () => {
  if (activeSourceMode) stopCamera();
  syncSourceControls();
});

navigator.mediaDevices?.addEventListener?.("devicechange", () => {
  refreshCameraDevices().catch(() => {});
});

syncSourceControls();
refreshCameraDevices().catch(() => {});
