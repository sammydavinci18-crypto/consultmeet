document.addEventListener("DOMContentLoaded", () => {
  const btnMic = document.getElementById("btn-mic");
  const btnCam = document.getElementById("btn-cam");
  const btnLeave = document.getElementById("btn-leave");
  const btnEndMeeting = document.getElementById("btn-end-meeting");
  const btnNotes = document.getElementById("btn-notes");
  const notesPanel = document.getElementById("notes-panel");
  const notesClose = document.getElementById("notes-close");
  const notesForm = document.getElementById("notes-form");
  const notesInput = document.getElementById("notes-input");
  const notesList = document.getElementById("notes-list");

  let micOn = true;
  let camOn = true;

  btnMic.addEventListener("click", () => {
    if (!window.localStream) return;
    micOn = !micOn;
    window.localStream.getAudioTracks().forEach((t) => (t.enabled = micOn));
    btnMic.classList.toggle("active-off", !micOn);
    btnMic.textContent = micOn ? "🎤" : "🔇";
  });

  btnCam.addEventListener("click", () => {
    if (!window.localStream) return;
    camOn = !camOn;
    window.localStream.getVideoTracks().forEach((t) => (t.enabled = camOn));
    btnCam.classList.toggle("active-off", !camOn);
    btnCam.textContent = camOn ? "📷" : "🚫";
  });

  if (btnLeave) {
    btnLeave.addEventListener("click", () => {
      window.location.href = "/dashboard";
    });
  }

  if (btnEndMeeting) {
    btnEndMeeting.addEventListener("click", async () => {
      btnEndMeeting.disabled = true;
      btnEndMeeting.textContent = "Ending…";
      try {
        if (window.stopRecordingAndWait) {
          await window.stopRecordingAndWait();
        }
        const res = await fetch(`/room/${window.ROOM_CONFIG.roomCode}/end`, { method: "POST" });
        const data = await res.json();
        window.location.href = data.redirect || "/dashboard";
      } catch (err) {
        console.error("Failed to end meeting cleanly:", err);
        window.location.href = "/dashboard";
      }
    });
  }

  function loadNotes() {
    fetch(`/room/${window.ROOM_CONFIG.roomCode}/notes`)
      .then((r) => r.json())
      .then((data) => renderNotes(data.notes));
  }

  function renderNotes(notes) {
    notesList.innerHTML = "";
    if (!notes.length) {
      notesList.innerHTML = '<div class="filmstrip-empty">No notes yet for this consultation.</div>';
      return;
    }
    notes.forEach((n) => {
      const item = document.createElement("div");
      item.className = "note-item";
      item.innerHTML = `
        <div class="note-meta">${escapeHtml(n.author)} · ${escapeHtml(n.created_at)}</div>
        <div class="note-content"></div>
      `;
      item.querySelector(".note-content").textContent = n.content;
      notesList.appendChild(item);
    });
    notesList.scrollTop = notesList.scrollHeight;
  }

  function escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
  }

  btnNotes.addEventListener("click", () => {
    notesPanel.classList.add("open");
    loadNotes();
  });
  notesClose.addEventListener("click", () => notesPanel.classList.remove("open"));

  notesForm.addEventListener("submit", (e) => {
    e.preventDefault();
    const content = notesInput.value.trim();
    if (!content) return;
    fetch(`/room/${window.ROOM_CONFIG.roomCode}/notes`, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: `content=${encodeURIComponent(content)}`,
    })
      .then((r) => r.json())
      .then((data) => {
        notesInput.value = "";
        renderNotes(data.notes);
      });
  });
});

// expose localStream to main.js once webrtc.js sets it up
Object.defineProperty(window, "localStream", {
  get() {
    return window._localStreamRef;
  },
});
