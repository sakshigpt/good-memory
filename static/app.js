"use strict";

/* ----------------------------- State ----------------------------- */
const state = {
  people: [],
  activePerson: null,
  editingPersonId: null,
  isRecording: false,
  mediaRecorder: null,
  audioChunks: [],
  audioStream: null,
};

/* ----------------------------- API helper ----------------------------- */
async function api(method, path, body) {
  const opts = { method, headers: { "Content-Type": "application/json" } };
  if (body !== undefined) opts.body = JSON.stringify(body);
  const res = await fetch("/api" + path, opts);
  const text = await res.text();
  let data;
  try { data = text ? JSON.parse(text) : {}; } catch { data = { error: text }; }
  if (!res.ok) throw new Error(data.error || ("HTTP " + res.status));
  return data;
}

/* ----------------------------- DOM helpers ----------------------------- */
const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => Array.from(document.querySelectorAll(sel));
function el(tag, attrs = {}, children = []) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") e.className = v;
    else if (k === "html") e.innerHTML = v;
    else if (k.startsWith("on")) e.addEventListener(k.slice(2), v);
    else e.setAttribute(k, v);
  }
  (Array.isArray(children) ? children : [children]).forEach((c) => {
    if (c == null) return;
    e.appendChild(typeof c === "string" ? document.createTextNode(c) : c);
  });
  return e;
}
function esc(s) {
  return String(s == null ? "" : s)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}
let toastTimer;
function toast(msg, isErr = false) {
  const t = $("#toast");
  t.textContent = msg;
  t.className = "toast" + (isErr ? " err" : "");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.add("hidden"), 3200);
}

/* ----------------------------- Navigation ----------------------------- */
function showView(id) {
  $$(".view").forEach((v) => v.classList.add("hidden"));
  $("#" + id).classList.remove("hidden");
}

// Highlight the matching sidebar nav button for the current view.
function setActiveNav(btnId) {
  $$(".navlink").forEach((n) => n.classList.remove("active"));
  const btn = btnId ? $("#" + btnId) : null;
  if (btn) btn.classList.add("active");
}

/* ----------------------------- People list ----------------------------- */
async function loadPeople() {
  state.people = await api("GET", "/people");
  renderSidebar();
  renderHome();
  await refreshConflictBadge();
}

function renderSidebar() {
  const filter = ($("#people-search").value || "").toLowerCase();
  const list = $("#people-list");
  list.innerHTML = "";
  state.people
    .filter((p) => p.name.toLowerCase().includes(filter))
    .forEach((p) => {
      const dot = p.pending_conflicts > 0 ? el("span", { class: "pi-dot" }, " ●") : null;
      const item = el("button", {
        class: "person-item" + (state.activePerson && state.activePerson.id === p.id ? " active" : ""),
        onclick: () => openPerson(p.id),
      }, [
        el("span", {}, [p.name, dot]),
        el("span", { class: "pi-sub" }, p.relationship_type),
      ]);
      list.appendChild(item);
    });
}

function renderHome() {
  const grid = $("#home-people");
  grid.innerHTML = "";
  $("#home-empty").classList.toggle("hidden", state.people.length > 0);
  state.people.forEach((p) => {
    const meta = p.last_note_at
      ? "Last note " + p.last_note_at.slice(0, 10)
      : "No notes yet";
    grid.appendChild(el("div", { class: "person-card", onclick: () => openPerson(p.id) }, [
      el("h3", {}, p.name),
      el("div", { class: "pc-meta" }, p.relationship_type + " · " + meta),
    ]));
  });
}

/* ----------------------------- Add / edit person ----------------------------- */
function openAddPerson() {
  state.editingPersonId = null;
  $("#add-person-title").textContent = "Add Someone";
  $("#ap-name").value = "";
  $("#ap-rel").value = "friend";
  $("#ap-context").value = "";
  setActiveNav("btn-add-person");
  showView("view-add-person");
  $("#ap-name").focus();
}

function openEditPerson(p) {
  state.editingPersonId = p.id;
  $("#add-person-title").textContent = "Edit person";
  $("#ap-name").value = p.name;
  $("#ap-rel").value = p.relationship_type;
  $("#ap-context").value = p.context || "";
  showView("view-add-person");
}

async function savePerson() {
  const name = $("#ap-name").value.trim();
  if (!name) return toast("Name is required", true);
  const payload = {
    name,
    relationship_type: $("#ap-rel").value,
    context: $("#ap-context").value.trim(),
  };
  try {
    if (state.editingPersonId) {
      await api("PUT", "/people/" + state.editingPersonId, payload);
      toast("Saved");
      await loadPeople();
      openPerson(state.editingPersonId);
    } else {
      const p = await api("POST", "/people", payload);
      toast("Added " + p.name);
      await loadPeople();
      openPerson(p.id);
    }
  } catch (e) { toast(e.message, true); }
}

/* ----------------------------- Person detail ----------------------------- */
async function openPerson(id) {
  try {
    state.activePerson = await api("GET", "/people/" + id);
  } catch (e) { return toast(e.message, true); }
  renderSidebar();
  renderPerson();
  setActiveNav(null);   // no top-level nav item active when viewing a person
  showView("view-person");
  switchTab("notes");
}

function renderPerson() {
  const p = state.activePerson;
  $("#p-name").textContent = p.name;
  $("#p-rel").textContent = p.relationship_type;
  $("#p-context").textContent = p.context || "";
  renderNotes();
  renderFacts();
  $("#note-result").classList.add("hidden");
  $("#note-input").value = "";
  $("#briefing-output").classList.add("hidden");
  $("#person-qa-log").innerHTML = "";
}

function switchTab(name) {
  $$(".tab").forEach((t) => t.classList.toggle("active", t.dataset.tab === name));
  $$(".tabpane").forEach((p) => p.classList.add("hidden"));
  $("#tab-" + name).classList.remove("hidden");
}

function renderNotes() {
  const wrap = $("#notes-list");
  wrap.innerHTML = "";
  const notes = state.activePerson.recent_notes || [];
  if (!notes.length) {
    wrap.appendChild(el("div", { class: "empty" }, "No notes yet — log your first one above."));
    return;
  }
  notes.forEach((n) => {
    const deleteBtn = el("button", {
      class: "note-delete",
      title: "Delete note",
      onclick: async () => {
        if (!confirm("Delete this note? Extracted facts from it will remain.")) return;
        try {
          await api("DELETE", "/notes/" + n.id);
          await refreshActivePerson();
          renderNotes();
          toast("Note deleted");
        } catch (e) { toast(e.message, true); }
      },
    }, "×");
    wrap.appendChild(el("div", { class: "note-item" }, [
      el("div", { class: "nmeta" }, [
        el("span", {}, (n.created_at || "").slice(0, 16).replace("T", " ")),
        el("span", { class: n.source === "voice" ? "src-voice" : "" },
           n.source === "voice" ? "🎙 voice" : "typed"),
        deleteBtn,
      ]),
      el("div", {}, n.raw_text),
    ]));
  });
}

function renderFacts() {
  const wrap = $("#facts-list");
  wrap.innerHTML = "";
  const facts = state.activePerson.facts || [];
  if (!facts.length) {
    wrap.appendChild(el("div", { class: "empty" }, "No facts extracted yet."));
    return;
  }
  const groups = {};
  facts.forEach((f) => (groups[f.category] = groups[f.category] || []).push(f));
  Object.entries(groups).forEach(([cat, items]) => {
    const g = el("div", { class: "fact-group" }, [el("h4", {}, cat)]);
    items.forEach((f) => {
      const val = el("span", { class: "fval", title: "Double-click to edit" }, f.value);
      val.addEventListener("dblclick", () => editFact(f, val));
      g.appendChild(el("div", { class: "fact-row" }, [
        el("span", { class: "fkey" }, f.key.replace(/_/g, " ")),
        val,
        el("button", { class: "fdel", title: "Delete", onclick: () => deleteFact(f.id) }, "×"),
      ]));
    });
    wrap.appendChild(g);
  });
}

async function editFact(f, valEl) {
  const next = prompt("Edit value for “" + f.key.replace(/_/g, " ") + "”:", f.value);
  if (next == null || next.trim() === "" || next.trim() === f.value) return;
  try {
    await api("PUT", "/facts/" + f.id, { value: next.trim() });
    valEl.textContent = next.trim();
    toast("Fact updated");
    await refreshActivePerson();
  } catch (e) { toast(e.message, true); }
}

async function deleteFact(id) {
  if (!confirm("Delete this fact?")) return;
  try {
    await api("DELETE", "/facts/" + id);
    await refreshActivePerson();
    renderFacts();
    toast("Fact deleted");
  } catch (e) { toast(e.message, true); }
}

async function refreshActivePerson() {
  if (!state.activePerson) return;
  state.activePerson = await api("GET", "/people/" + state.activePerson.id);
}

/* ----------------------------- Save note + extraction pipeline ----------------------------- */
async function saveNote(source = "text") {
  const text = $("#note-input").value.trim();
  if (!text) return toast("Write or record a note first", true);
  const btn = $("#btn-save-note");
  btn.disabled = true; btn.textContent = "Saving...";
  try {
    const res = await api("POST", "/people/" + state.activePerson.id + "/notes",
      { raw_text: text, source });
    $("#note-input").value = "";
    await refreshActivePerson();
    renderNotes();
    renderFacts();
    renderNoteResult(res);
    await loadPeople();
    toast("Note saved");
  } catch (e) {
    toast(e.message, true);
  } finally {
    btn.disabled = false; btn.textContent = "Save note";
  }
}

function renderNoteResult(res) {
  const box = $("#note-result");
  box.innerHTML = "";
  box.classList.remove("hidden");

  if (res.extraction_error) {
    box.appendChild(el("div", { class: "answer-card" },
      "Saved your note, but fact extraction failed: " + res.extraction_error));
  }

  const facts = res.extracted_facts || [];
  if (facts.length) {
    box.appendChild(el("div", { class: "answer-card" }, [
      el("strong", {}, "Captured " + facts.length + " new detail" + (facts.length > 1 ? "s" : "") + ": "),
      el("span", {}, facts.map((f) => f.key.replace(/_/g, " ") + " = " + f.value).join(", ")),
    ]));
  }

  const conflicts = res.conflicts || [];
  conflicts.forEach((c) => box.appendChild(renderConflictCard({
    conflict_id: c.conflict_id,
    new_key: c.key,
    existing_value: c.existing_value,
    new_value: c.new_value,
  }, true)));

  if (!facts.length && !conflicts.length && !res.extraction_error) {
    box.appendChild(el("div", { class: "answer-card" }, "Note saved. No new facts to extract."));
  }
}

/* ----------------------------- Voice recording ----------------------------- */
async function toggleRecording() {
  if (state.isRecording) return stopRecording();
  try {
    state.audioStream = await navigator.mediaDevices.getUserMedia({ audio: true });
  } catch (e) {
    return toast("Microphone access denied", true);
  }
  state.audioChunks = [];
  const mime = MediaRecorder.isTypeSupported("audio/webm") ? "audio/webm" : "";
  state.mediaRecorder = new MediaRecorder(state.audioStream, mime ? { mimeType: mime } : undefined);
  state.mediaRecorder.ondataavailable = (e) => { if (e.data.size) state.audioChunks.push(e.data); };
  state.mediaRecorder.onstop = onRecordingStopped;
  state.mediaRecorder.start();
  state.isRecording = true;
  const b = $("#btn-record");
  b.classList.add("recording"); b.textContent = "■ Stop";
  $("#rec-status").textContent = "Recording...";
}

function stopRecording() {
  if (state.mediaRecorder && state.isRecording) state.mediaRecorder.stop();
  state.isRecording = false;
  const b = $("#btn-record");
  b.classList.remove("recording"); b.textContent = "● Record";
  $("#rec-status").textContent = "Transcribing...";
}

async function onRecordingStopped() {
  if (state.audioStream) state.audioStream.getTracks().forEach((t) => t.stop());
  const blob = new Blob(state.audioChunks, { type: "audio/webm" });
  try {
    // Decode the recorded audio and re-encode as 16kHz mono WAV. The backend
    // reads WAV directly (no ffmpeg needed on this machine).
    const wavBlob = await blobToWav16k(blob);
    const form = new FormData();
    form.append("audio_file", wavBlob, "recording.wav");
    const res = await fetch("/api/voice/transcribe", { method: "POST", body: form });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "transcription failed");
    const cur = $("#note-input").value;
    $("#note-input").value = (cur ? cur + " " : "") + (data.transcript || "");
    $("#rec-status").textContent = data.transcript ? "Transcribed ✓" : "No speech detected";
    state._lastWasVoice = true;
  } catch (e) {
    $("#rec-status").textContent = "";
    toast(e.message, true);
  }
}

// Decode any browser-recorded audio blob -> 16kHz mono 16-bit PCM WAV blob.
async function blobToWav16k(blob) {
  const arrayBuf = await blob.arrayBuffer();
  const AC = window.AudioContext || window.webkitAudioContext;
  const decodeCtx = new AC();
  const decoded = await decodeCtx.decodeAudioData(arrayBuf);
  decodeCtx.close();

  const targetRate = 16000;
  const frames = Math.ceil(decoded.duration * targetRate);
  const offline = new OfflineAudioContext(1, Math.max(1, frames), targetRate);
  const src = offline.createBufferSource();
  src.buffer = decoded;
  src.connect(offline.destination);
  src.start();
  const rendered = await offline.startRendering();
  return encodeWav(rendered.getChannelData(0), targetRate);
}

function encodeWav(samples, sampleRate) {
  const buffer = new ArrayBuffer(44 + samples.length * 2);
  const view = new DataView(buffer);
  const writeStr = (off, s) => { for (let i = 0; i < s.length; i++) view.setUint8(off + i, s.charCodeAt(i)); };
  writeStr(0, "RIFF");
  view.setUint32(4, 36 + samples.length * 2, true);
  writeStr(8, "WAVE");
  writeStr(12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);       // PCM
  view.setUint16(22, 1, true);       // mono
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  writeStr(36, "data");
  view.setUint32(40, samples.length * 2, true);
  let off = 44;
  for (let i = 0; i < samples.length; i++, off += 2) {
    const s = Math.max(-1, Math.min(1, samples[i]));
    view.setInt16(off, s < 0 ? s * 0x8000 : s * 0x7fff, true);
  }
  return new Blob([view], { type: "audio/wav" });
}

/* ----------------------------- Briefing ----------------------------- */
async function getBriefing() {
  const out = $("#briefing-output");
  out.classList.remove("hidden");
  out.innerHTML = '<span class="loading">Thinking...</span>';
  try {
    const res = await api("POST", "/people/" + state.activePerson.id + "/brief",
      { focus: $("#brief-focus").value.trim() });
    out.textContent = res.briefing;
  } catch (e) {
    out.textContent = "Error: " + e.message;
  }
}

/* ----------------------------- Q&A ----------------------------- */
async function askGlobal() {
  const q = $("#global-q").value.trim();
  if (!q) return;
  const box = $("#global-answer");
  box.classList.remove("hidden");
  box.innerHTML = '<span class="loading">Thinking...</span>';
  try {
    const res = await api("POST", "/qa", { question: q });
    box.textContent = res.answer;
  } catch (e) {
    box.textContent = "Error: " + e.message;
  }
}

async function askPerson() {
  const q = $("#person-q").value.trim();
  if (!q) return;
  const log = $("#person-qa-log");
  const entry = el("div", { class: "qa-entry" }, [
    el("div", { class: "qa-q" }, q),
    el("div", { class: "qa-a loading" }, "Thinking..."),
  ]);
  log.prepend(entry);
  $("#person-q").value = "";
  try {
    const res = await api("POST", "/qa", { question: q, person_id: state.activePerson.id });
    entry.querySelector(".qa-a").classList.remove("loading");
    entry.querySelector(".qa-a").textContent = res.answer;
  } catch (e) {
    entry.querySelector(".qa-a").textContent = "Error: " + e.message;
  }
}

/* ----------------------------- Conflicts ----------------------------- */
function renderConflictCard(c, inline = false) {
  const card = el("div", { class: "conflict-card" });
  card.appendChild(el("div", { class: "ckey" },
    "Conflict on “" + (c.new_key || c.key || "").replace(/_/g, " ") + "”"
    + (c.person_name ? " — " + c.person_name : "")));
  card.appendChild(el("div", { class: "conflict-vals" }, [
    el("div", { class: "cv" }, [
      el("div", { class: "lbl" }, "Currently saved"),
      el("div", { class: "cv-val" }, c.existing_value),
    ]),
    el("div", { class: "cv" }, [
      el("div", { class: "lbl" }, "New from note"),
      el("div", { class: "cv-val" }, c.new_value),
    ]),
  ]));
  const merge = el("input", { type: "text", placeholder: "Type a merged value…" });
  const resolve = async (resolution) => {
    try {
      const body = { resolution };
      if (resolution === "merge") {
        if (!merge.value.trim()) return toast("Enter a merged value", true);
        body.merge_value = merge.value.trim();
      }
      await api("POST", "/conflicts/" + c.conflict_id + "/resolve", body);
      toast("Resolved ✓");
      card.remove();
      await loadPeople();
      if (state.activePerson) { await refreshActivePerson(); renderFacts(); }
      if (!inline) loadConflicts();
    } catch (e) { toast(e.message, true); }
  };
  card.appendChild(el("div", { class: "conflict-actions" }, [
    el("button", { class: "btn ghost small", onclick: () => resolve("old") }, "Keep current"),
    el("button", { class: "btn primary small", onclick: () => resolve("new") }, "Use new"),
  ]));
  card.appendChild(el("div", { class: "conflict-merge" }, [
    merge, el("button", { class: "btn ghost small", onclick: () => resolve("merge") }, "Save merge"),
  ]));
  return card;
}

async function loadConflicts() {
  setActiveNav("nav-conflicts");
  showView("view-conflicts");
  const res = await api("GET", "/conflicts");
  const wrap = $("#conflicts-list");
  wrap.innerHTML = "";
  $("#conflicts-empty").classList.toggle("hidden", res.count > 0);
  (res.conflicts || []).forEach((c) => wrap.appendChild(renderConflictCard({
    conflict_id: c.id,
    new_key: c.new_key,
    existing_value: c.existing_value,
    new_value: c.new_value,
    person_name: c.person_name,
  })));
  await refreshConflictBadge(res.count);
}

async function refreshConflictBadge(count) {
  if (count === undefined) {
    const res = await api("GET", "/conflicts");
    count = res.count;
  }
  const badge = $("#conflict-badge");
  badge.textContent = count;
  badge.classList.toggle("hidden", !count);
}

/* ----------------------------- Wire up events ----------------------------- */
function bind() {
  $("#btn-add-person").addEventListener("click", openAddPerson);
  $("#nav-home").addEventListener("click", () => {
    setActiveNav("nav-home");
    renderHome();
    showView("view-home");
  });
  $("#nav-ask").addEventListener("click", () => {
    setActiveNav("nav-ask");
    showView("view-ask");
    $("#global-q").focus();
  });
  $("#nav-conflicts").addEventListener("click", loadConflicts);
  $("#people-search").addEventListener("input", renderSidebar);

  $("#ap-save").addEventListener("click", savePerson);
  $("#ap-cancel").addEventListener("click", () => showView("view-home"));

  $("#p-edit").addEventListener("click", () => openEditPerson(state.activePerson));
  $("#p-delete").addEventListener("click", async () => {
    if (!confirm("Delete " + state.activePerson.name + " and all their notes?")) return;
    await api("DELETE", "/people/" + state.activePerson.id);
    state.activePerson = null;
    await loadPeople();
    showView("view-home");
    toast("Deleted");
  });

  $$(".tab").forEach((t) => t.addEventListener("click", () => switchTab(t.dataset.tab)));

  $("#btn-record").addEventListener("click", toggleRecording);
  $("#btn-save-note").addEventListener("click", () => {
    const wasVoice = state._lastWasVoice;
    state._lastWasVoice = false;
    saveNote(wasVoice ? "voice" : "text");
  });

  $("#btn-brief").addEventListener("click", getBriefing);
  $("#global-ask").addEventListener("click", askGlobal);
  $("#global-q").addEventListener("keydown", (e) => { if (e.key === "Enter") askGlobal(); });
  $("#btn-person-ask").addEventListener("click", askPerson);
  $("#person-q").addEventListener("keydown", (e) => { if (e.key === "Enter") askPerson(); });
}

bind();
loadPeople().then(() => {
  setActiveNav("nav-home");
  showView("view-home");
});
