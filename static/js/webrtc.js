/*
  WebRTC mesh video calling.

  - Every browser tab connects to the same Flask-SocketIO server for SIGNALING only
    (exchanging offers/answers/ICE candidates). Actual audio/video never touches
    the server — it flows directly between browsers (peer-to-peer).
  - Whoever is the meeting's host always renders into the large "spotlight" tile.
    Everyone else renders into the small filmstrip tiles below.
*/

const ICE_SERVERS = {
  iceServers: [{ urls: "stun:stun.l.google.com:19302" }],
};

const socket = io();

let localStream = null;
const peerConnections = {}; // sid -> RTCPeerConnection
const peerMeta = {}; // sid -> { name, isHost }
window._remoteStreams = {}; // sid -> { stream, name, isHost } — read by recorder.js

const { roomCode, isHost, userName, hostName } = window.ROOM_CONFIG;

async function initMedia() {
  try {
    localStream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
  } catch (err) {
    console.warn("Camera/mic unavailable, joining audio/video-less:", err);
    localStream = new MediaStream();
  }

  window._localStreamRef = localStream;

  // Show my own video immediately: spotlight if I'm the host, filmstrip otherwise.
  if (isHost) {
    renderSpotlightStream(localStream, `${userName}`, true);
  } else {
    upsertFilmstripTile("local", localStream, `${userName} (you)`, false);
  }

  socket.emit("join", { room_code: roomCode });
}

function createPeerConnection(targetSid, meta) {
  const pc = new RTCPeerConnection(ICE_SERVERS);
  peerConnections[targetSid] = pc;
  peerMeta[targetSid] = meta;

  localStream.getTracks().forEach((track) => pc.addTrack(track, localStream));

  pc.onicecandidate = (event) => {
    if (event.candidate) {
      socket.emit("signal", {
        target: targetSid,
        signal: { type: "candidate", candidate: event.candidate },
      });
    }
  };

  pc.ontrack = (event) => {
    const stream = event.streams[0];
    window._remoteStreams[targetSid] = { stream, name: meta.name, isHost: meta.isHost };
    if (meta.isHost) {
      renderSpotlightStream(stream, meta.name, false);
    } else {
      upsertFilmstripTile(targetSid, stream, meta.name, true);
    }
  };

  pc.onconnectionstatechange = () => {
    if (["failed", "closed", "disconnected"].includes(pc.connectionState)) {
      teardownPeer(targetSid);
    }
  };

  return pc;
}

async function callPeer(targetSid, meta) {
  const pc = createPeerConnection(targetSid, meta);
  const offer = await pc.createOffer();
  await pc.setLocalDescription(offer);
  socket.emit("signal", { target: targetSid, signal: { type: "offer", sdp: offer } });
}

socket.on("existing_peers", async ({ peers }) => {
  for (const peer of peers) {
    await callPeer(peer.sid, { name: peer.name, isHost: peer.is_host });
  }
});

socket.on("peer_joined", ({ sid, name, is_host }) => {
  // The newcomer will call us (see existing_peers on their side), so we just wait.
  peerMeta[sid] = { name, isHost: is_host };
});

socket.on("signal", async ({ sender, signal }) => {
  let pc = peerConnections[sender];

  if (signal.type === "offer") {
    const meta = peerMeta[sender] || { name: "Participant", isHost: false };
    pc = pc || createPeerConnection(sender, meta);
    await pc.setRemoteDescription(new RTCSessionDescription(signal.sdp));
    const answer = await pc.createAnswer();
    await pc.setLocalDescription(answer);
    socket.emit("signal", { target: sender, signal: { type: "answer", sdp: answer } });
  } else if (signal.type === "answer") {
    if (pc) await pc.setRemoteDescription(new RTCSessionDescription(signal.sdp));
  } else if (signal.type === "candidate") {
    if (pc) {
      try {
        await pc.addIceCandidate(new RTCIceCandidate(signal.candidate));
      } catch (err) {
        console.warn("Failed to add ICE candidate", err);
      }
    }
  }
});

socket.on("peer_left", ({ sid }) => teardownPeer(sid));

function teardownPeer(sid) {
  const pc = peerConnections[sid];
  if (pc) {
    pc.close();
    delete peerConnections[sid];
  }
  const meta = peerMeta[sid];
  delete peerMeta[sid];
  delete window._remoteStreams[sid];

  if (meta && meta.isHost) {
    clearSpotlight();
  } else {
    removeFilmstripTile(sid);
  }
}

/* ---------------- DOM rendering ---------------- */

function renderSpotlightStream(stream, name, isSelf) {
  const tile = document.getElementById("spotlight-tile");
  const existingVideo = tile.querySelector("video");
  if (existingVideo) existingVideo.remove();
  const avatar = document.getElementById("spotlight-avatar");
  if (avatar) avatar.style.display = "none";

  const video = document.createElement("video");
  video.autoplay = true;
  video.playsInline = true;
  video.muted = isSelf;
  video.srcObject = stream;
  tile.insertBefore(video, tile.firstChild);

  const label = document.getElementById("spotlight-label");
  label.innerHTML = `<span class="host-badge">Host</span> ${name}${isSelf ? " (you)" : ""}`;
}

function clearSpotlight() {
  const tile = document.getElementById("spotlight-tile");
  const video = tile.querySelector("video");
  if (video) video.remove();
  const avatar = document.getElementById("spotlight-avatar");
  if (avatar) avatar.style.display = "flex";
  document.getElementById("spotlight-label").innerHTML =
    `<span class="host-badge">Host</span> ${hostName}`;
}

function upsertFilmstripTile(key, stream, name, isRemote) {
  const empty = document.getElementById("filmstrip-empty");
  if (empty) empty.remove();

  let tile = document.getElementById(`tile-${key}`);
  if (!tile) {
    tile = document.createElement("div");
    tile.className = "mini-tile";
    tile.id = `tile-${key}`;
    document.getElementById("filmstrip").appendChild(tile);
  }
  tile.innerHTML = "";

  const video = document.createElement("video");
  video.autoplay = true;
  video.playsInline = true;
  video.muted = !isRemote; // mute local self-view to avoid echo
  video.srcObject = stream;
  tile.appendChild(video);

  const label = document.createElement("div");
  label.className = "tile-label";
  label.textContent = name;
  tile.appendChild(label);
}

function removeFilmstripTile(key) {
  const tile = document.getElementById(`tile-${key}`);
  if (tile) tile.remove();

  const strip = document.getElementById("filmstrip");
  if (!strip.querySelector(".mini-tile")) {
    const empty = document.createElement("div");
    empty.className = "filmstrip-empty";
    empty.id = "filmstrip-empty";
    empty.textContent = "Waiting for others to join…";
    strip.appendChild(empty);
  }
}

initMedia();
