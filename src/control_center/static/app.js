// CVVF Control Center Frontend Logic

let allVideos = [];

async function fetchVideos() {
  const platform = document.getElementById("filter-platform").value;
  const rights = document.getElementById("filter-rights").value;
  const status = document.getElementById("filter-status").value;

  const params = new URLSearchParams();
  if (platform) params.append("platform", platform);
  if (rights) params.append("rights_status", rights);
  if (status) params.append("processing_status", status);

  try {
    const res = await fetch(`/api/videos?${params.toString()}`);
    const data = await res.json();
    allVideos = data.videos || [];
    renderVideos();
  } catch (err) {
    console.error("Failed to fetch videos:", err);
  }
}

async function fetchAuditLogs() {
  try {
    const res = await fetch("/api/audit-logs");
    const logs = await res.json();
    const tbody = document.getElementById("log-table-body");
    tbody.innerHTML = "";

    if (!logs.length) {
      tbody.innerHTML = `<tr><td colspan="5" style="text-align: center; color: var(--text-dim);">Chưa có nhật ký hoạt động nào.</td></tr>`;
      return;
    }

    logs.forEach(log => {
      const tr = document.createElement("tr");
      const timeStr = new Date(log.timestamp).toLocaleTimeString();
      const statusBadge = log.status === "COMPLETED" || log.status === "APPROVED"
        ? `<span style="color: #34d399; font-weight: 600;">${log.status}</span>`
        : log.status === "FAILED" || log.status === "REJECTED"
        ? `<span style="color: #fb7185; font-weight: 600;">${log.status}</span>`
        : `<span style="color: #38bdf8; font-weight: 600;">${log.status}</span>`;

      tr.innerHTML = `
        <td style="color: var(--text-muted); font-family: monospace;">${timeStr}</td>
        <td><strong>${log.action}</strong></td>
        <td style="color: var(--accent-cyan); font-family: monospace;">${log.target}</td>
        <td>${statusBadge}</td>
        <td style="color: var(--text-muted);">${log.details}</td>
      `;
      tbody.appendChild(tr);
    });
  } catch (err) {
    console.error("Failed to fetch audit logs:", err);
  }
}

function renderVideos() {
  const query = (document.getElementById("search-query").value || "").toLowerCase();
  const grid = document.getElementById("video-grid");
  grid.innerHTML = "";

  const filtered = allVideos.filter(v => {
    const titleMatch = (v.title || "").toLowerCase().includes(query);
    const authorMatch = (v.author && v.author.name || "").toLowerCase().includes(query);
    return titleMatch || authorMatch;
  });

  if (!filtered.length) {
    grid.innerHTML = `
      <div style="grid-column: 1 / -1; text-align: center; padding: 40px; color: var(--text-dim);">
        Không tìm thấy video nào phù hợp với bộ lọc hiện tại. Nhấn <strong>"Quét Video Nguồn"</strong> để thu thập dữ liệu mới.
      </div>
    `;
    return;
  }

  filtered.forEach(v => {
    const card = document.createElement("article");
    card.className = "video-card";
    const scored = v.scored || {};
    const viralScore = scored.measured_viral_score !== null ? scored.measured_viral_score : "N/A";
    const category = scored.category || "other";
    const views = v.metrics && v.metrics.views ? v.metrics.views.toLocaleString() : "0";
    const likes = v.metrics && v.metrics.likes ? v.metrics.likes.toLocaleString() : "0";
    const shares = v.metrics && v.metrics.shares ? v.metrics.shares.toLocaleString() : "0";
    const comments = v.metrics && v.metrics.comments ? v.metrics.comments.toLocaleString() : "0";

    const isApproved = v.rights_status === "APPROVED_BY_USER";
    const isRendered = v.processing_status === "RENDERED";

    card.innerHTML = `
      <div>
        <div class="card-header">
          <div style="display: flex; gap: 8px; flex-wrap: wrap;">
            <span class="badge-platform">${v.source_platform}</span>
            <span class="badge-category">${category}</span>
          </div>
          <div class="viral-score-tag">
            <span>🔥</span> ${viralScore}
          </div>
        </div>

        <h3 class="video-title" title="${v.title}">${v.title}</h3>
        <div class="video-author">👤 ${v.author ? v.author.name : 'Unknown Creator'}</div>

        <div class="metrics-row">
          <div>
            <div class="metric-item-value">${views}</div>
            <div class="metric-item-label">Views</div>
          </div>
          <div>
            <div class="metric-item-value">${likes}</div>
            <div class="metric-item-label">Likes</div>
          </div>
          <div>
            <div class="metric-item-value">${shares}</div>
            <div class="metric-item-label">Shares</div>
          </div>
          <div>
            <div class="metric-item-value">${comments}</div>
            <div class="metric-item-label">Comments</div>
          </div>
        </div>
      </div>

      <div>
        <div style="font-size: 12px; margin-bottom: 12px; display: flex; justify-content: space-between;">
          <span style="color: var(--text-dim);">Quyền: <strong>${v.rights_status}</strong></span>
          <span style="color: var(--text-dim);">Trạng thái: <strong>${v.processing_status}</strong></span>
        </div>

        <div class="card-actions">
          ${!isApproved ? `
            <button class="btn-approve" onclick="approveRights('${v.dedup_key}')">Duyệt Quyền</button>
            <button class="btn-reject" onclick="rejectVideo('${v.dedup_key}')">Từ Chối</button>
          ` : `
            <button class="btn-process" onclick="processPipeline('${v.dedup_key}')" ${isRendered ? 'style="background: #10b981;"' : ''}>
              ${isRendered ? '✓ Đã Render' : '⚡ Xử Lý Toàn Bộ'}
            </button>
          `}
          <button class="btn-outline" onclick="openDetailModal('${v.dedup_key}')">Chi tiết</button>
        </div>
      </div>
    `;

    grid.appendChild(card);
  });
}

async function approveRights(dedupKey) {
  try {
    const res = await fetch(`/api/videos/${encodeURIComponent(dedupKey)}/approve`, { method: "POST" });
    if (res.ok) {
      await fetchVideos();
      await fetchAuditLogs();
    }
  } catch (err) {
    alert("Lỗi khi duyệt bản quyền: " + err);
  }
}

async function rejectVideo(dedupKey) {
  try {
    const res = await fetch(`/api/videos/${encodeURIComponent(dedupKey)}/reject`, { method: "POST" });
    if (res.ok) {
      await fetchVideos();
      await fetchAuditLogs();
    }
  } catch (err) {
    alert("Lỗi khi từ chối video: " + err);
  }
}

async function processPipeline(dedupKey) {
  try {
    const btn = event.target;
    btn.textContent = "⏳ Đang xử lý...";
    btn.disabled = true;

    const res = await fetch(`/api/videos/${encodeURIComponent(dedupKey)}/process-all`, { method: "POST" });
    const data = await res.json();
    if (res.ok) {
      alert(`Đã hoàn tất quy trình xử lý và render cho ${dedupKey}!\nTệp xuất: ${data.rendered_video}`);
      await fetchVideos();
      await fetchAuditLogs();
    } else {
      alert("Lỗi: " + data.detail);
    }
  } catch (err) {
    alert("Lỗi quy trình: " + err);
  }
}

function openDetailModal(dedupKey) {
  const video = allVideos.find(v => v.dedup_key === dedupKey);
  if (!video) return;

  const modal = document.getElementById("detail-modal");
  const modalBody = document.getElementById("modal-body");
  const scored = video.scored || {};

  modalBody.innerHTML = `
    <div style="margin-bottom: 16px;">
      <h4 style="font-size: 16px; margin-bottom: 6px;">${video.title}</h4>
      <div style="font-size: 13px; color: var(--text-muted);">URL gốc: <a href="${video.canonical_url}" target="_blank" style="color: var(--accent-cyan);">${video.canonical_url}</a></div>
    </div>

    <div style="background: rgba(0,0,0,0.3); padding: 16px; border-radius: 8px; margin-bottom: 20px;">
      <div style="font-weight: 700; margin-bottom: 10px; color: var(--accent-primary);">GIẢI THÍCH CHẤM ĐIỂM VIRAL:</div>
      <ul style="padding-left: 20px; font-size: 13px; color: var(--text-main); line-height: 1.8;">
        ${(scored.scoring_explanation || []).map(exp => `<li>${exp}</li>`).join("")}
      </ul>
    </div>

    <div style="font-size: 13px; color: var(--text-dim); margin-bottom: 10px;">
      <div>Trường nguồn không cung cấp: <strong>${(video.missing_fields || []).join(", ") || "Không có"}</strong></div>
      <div>Thời điểm phát hiện: <strong>${video.discovery_timestamp}</strong></div>
    </div>
  `;

  modal.style.display = "flex";
}

document.getElementById("btn-modal-close").addEventListener("click", () => {
  document.getElementById("detail-modal").style.display = "none";
});

document.getElementById("btn-trigger-discovery").addEventListener("click", async () => {
  const btn = document.getElementById("btn-trigger-discovery");
  btn.textContent = "⏳ Đang quét...";
  btn.disabled = true;

  try {
    const res = await fetch("/api/discovery/trigger", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ platform: "bilibili", page: 1, page_size: 5, dry_run: false }),
    });
    const result = await res.json();
    alert(`Quét hoàn tất!\nThu thập: ${result.total_fetched} video\nBản ghi mới: ${result.new_unique_added}\nTrùng lặp đã lọc: ${result.duplicates_filtered}`);
    await fetchVideos();
    await fetchAuditLogs();
  } catch (err) {
    alert("Quét thất bại: " + err);
  } finally {
    btn.innerHTML = `<span>🔍</span> Quét Video Nguồn`;
    btn.disabled = false;
  }
});

document.getElementById("filter-platform").addEventListener("change", fetchVideos);
document.getElementById("filter-rights").addEventListener("change", fetchVideos);
document.getElementById("filter-status").addEventListener("change", fetchVideos);
document.getElementById("search-query").addEventListener("input", renderVideos);
document.getElementById("btn-refresh").addEventListener("click", () => {
  fetchVideos();
  fetchAuditLogs();
});

// Initial load
fetchVideos();
fetchAuditLogs();
setInterval(fetchAuditLogs, 15000); // Polling audit log every 15s
