// MedChronicle Doctor Review & Consultation Readiness UI — Final Frontend & Integration Pass

const PATIENT_ID = "SYN-CANCER-001";
let briefData = null;
let reviewData = null;
let timelineData = null;
let changesData = null;
let flagsData = null;
let stagedFiles = [];
let currentReviewFilter = "all";

// Route / Hash mapping for proper section navigation
const HASH_TAB_MAP = {
  "overview": "tab-overview",
  "upload": "tab-upload",
  "timeline": "tab-timeline",
  "changes": "tab-changes",
  "flags": "tab-flags",
  "medications": "tab-medications",
  "investigations": "tab-investigations",
  "pending": "tab-investigations",
  "sources": "tab-sources",
  "review": "tab-review",
  "evaluation": "tab-evaluation"
};

const TAB_HASH_MAP = {
  "tab-overview": "overview",
  "tab-upload": "upload",
  "tab-timeline": "timeline",
  "tab-changes": "changes",
  "tab-flags": "flags",
  "tab-medications": "medications",
  "tab-investigations": "pending",
  "tab-sources": "sources",
  "tab-review": "review",
  "tab-evaluation": "evaluation"
};

// Initialize
document.addEventListener("DOMContentLoaded", () => {
  initTabs();
  initUpload();
  loadData();
});

// Tab & Route Navigation
function initTabs() {
  const tabs = document.querySelectorAll(".tab-btn");
  tabs.forEach(tab => {
    tab.addEventListener("click", () => {
      const targetId = tab.getAttribute("data-tab");
      switchToTab(targetId, true);
    });
  });

  // Modal close handlers
  const closeBtn = document.getElementById("close-modal-btn");
  if (closeBtn) closeBtn.addEventListener("click", closeModal);

  const modal = document.getElementById("pdf-modal");
  if (modal) {
    modal.addEventListener("click", (e) => {
      if (e.target.id === "pdf-modal") closeModal();
    });
  }

  // Handle URL hash on initial load
  const hash = window.location.hash.replace(/^#/, "").toLowerCase();
  const initialTab = HASH_TAB_MAP[hash] || "tab-overview";
  switchToTab(initialTab, false);
}

function switchToTab(targetId, updateHash = true) {
  if (!targetId) targetId = "tab-overview";

  document.querySelectorAll(".tab-btn").forEach(t => {
    const isTarget = t.getAttribute("data-tab") === targetId;
    t.classList.toggle("active", isTarget);
    t.setAttribute("aria-selected", isTarget ? "true" : "false");
  });

  document.querySelectorAll(".tab-pane").forEach(p => {
    p.classList.toggle("active", p.id === targetId);
  });

  if (updateHash) {
    const newHash = TAB_HASH_MAP[targetId] || "overview";
    if (window.location.hash !== `#${newHash}`) {
      window.location.hash = newHash;
    }
  }

  window.scrollTo({ top: 0, behavior: "instant" });
}

function handleHashChange() {
  const hash = window.location.hash.replace(/^#/, "").toLowerCase();
  const targetId = HASH_TAB_MAP[hash] || "tab-overview";
  switchToTab(targetId, false);
}

window.addEventListener("hashchange", handleHashChange);

// Helpers for clean clinical formatting
function formatDisplayDate(dateStr) {
  if (!dateStr) return "Undated";
  try {
    const parts = String(dateStr).split("-");
    if (parts.length === 3 && parts[0].length === 4) {
      const year = parts[0];
      const monthIdx = parseInt(parts[1], 10) - 1;
      const day = parts[2];
      const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
      if (monthIdx >= 0 && monthIdx < 12) {
        return `${day} ${months[monthIdx]} ${year}`;
      }
    }
  } catch (e) {}
  return String(dateStr);
}

function getEventDocumentType(typeOrCat) {
  if (!typeOrCat) return "Documented Record";
  const s = String(typeOrCat).toLowerCase();
  if (s.includes("visit") || s.includes("consult")) return "Consultation Note";
  if (s.includes("pathology")) return "Pathology Report";
  if (s.includes("lab")) return "Laboratory Report";
  if (s.includes("imaging")) return "Imaging Report";
  if (s.includes("medication") || s.includes("rx") || s.includes("prescription")) return "Prescription";
  if (s.includes("procedure") || s.includes("surg")) return "Procedure Note";
  if (s.includes("discharge")) return "Discharge Summary";
  if (s.includes("referral")) return "Referral Note";
  if (s.includes("investigation")) return "Investigation Order";
  return s.charAt(0).toUpperCase() + s.slice(1);
}

// Data Fetching & Authoritative State Refresh
async function refreshPatientData() {
  try {
    const t = Date.now();
    const [briefRes, reviewRes, timelineRes, changesRes, flagsRes] = await Promise.all([
      fetch(`/api/patient/${PATIENT_ID}/brief?_t=${t}`, { cache: "no-store" }),
      fetch(`/api/patient/${PATIENT_ID}/review?_t=${t}`, { cache: "no-store" }),
      fetch(`/api/patient/${PATIENT_ID}/timeline?_t=${t}`, { cache: "no-store" }),
      fetch(`/api/patient/${PATIENT_ID}/changes?_t=${t}`, { cache: "no-store" }),
      fetch(`/api/patient/${PATIENT_ID}/flags?_t=${t}`, { cache: "no-store" })
    ]);

    if (!briefRes.ok) throw new Error(`Brief load failed: ${briefRes.status}`);
    briefData = await briefRes.json();

    if (reviewRes.ok) {
      reviewData = await reviewRes.json();
    } else {
      reviewData = { patient_id: PATIENT_ID, review_status: "pending", reviewed_items: {} };
    }

    if (timelineRes.ok) {
      timelineData = await timelineRes.json();
    } else {
      timelineData = { events: [], total_events: 0 };
    }

    if (changesRes.ok) {
      changesData = await changesRes.json();
    } else {
      changesData = { changes: [], total_changes: 0 };
    }

    if (flagsRes.ok) {
      flagsData = await flagsRes.json();
    } else {
      flagsData = { flags: [], total_flags: 0 };
    }

    renderAll();
  } catch (err) {
    console.error("Failed to refresh MedChronicle data:", err);
    const main = document.getElementById("main-content");
    if (main && !briefData) {
      main.innerHTML = `
        <div style="padding: 40px; text-align: center; color: #991b1b;">
          <h3 style="margin-bottom: 8px;">Unable to load patient brief</h3>
          <p style="font-size: 0.9rem; color: #475569;">Unable to complete request. Please verify the backend server is running and retry.</p>
          <button class="btn btn-primary" onclick="location.reload()" style="margin-top: 16px;">Retry Loading</button>
        </div>
      `;
    }
  }
}

async function loadData() {
  await refreshPatientData();
}

// Filter out unchanged comparisons (ALT: 22 -> 22, CA 15-3: 22.4 -> 22.4)
function getGenuineChanges() {
  const raw = (changesData && changesData.changes && changesData.changes.length > 0)
    ? changesData.changes
    : (briefData?.what_changed || []);

  return raw.filter(ch => {
    const p = String(ch.previous_value || "").trim().toLowerCase();
    const l = String(ch.latest_value || "").trim().toLowerCase();
    if (p === l) return false;
    const pNum = parseFloat(p);
    const lNum = parseFloat(l);
    if (!isNaN(pNum) && !isNaN(lNum) && pNum === lNum) return false;
    return true;
  });
}

function renderAll() {
  renderReviewBar();
  renderOverviewTab();
  renderRecentTimeline();
  renderWhatChanged();
  renderFlags();
  renderMedications();
  renderInvestigations();
  renderSources();
  renderDoctorReviewTab();
  updateTabCounters();
}

// 1. Header & Review Status Bar
function renderReviewBar() {
  if (!reviewData) return;
  const isReviewed = reviewData.review_status === "reviewed";
  const pill = document.getElementById("review-status-pill");
  const toggleBtn = document.getElementById("toggle-review-btn");
  const paneToggleBtn = document.getElementById("pane-toggle-review-btn");
  const heroReviewPill = document.getElementById("hero-review-pill");
  const overviewReviewPill = document.getElementById("overview-review-pill");
  const reviewChecklistPill = document.getElementById("review-checklist-pill");

  const statusClass = isReviewed ? "review-status-pill status-reviewed" : "review-status-pill status-pending";
  const statusText = isReviewed ? "REVIEWED" : "PENDING REVIEW";

  if (pill) {
    pill.className = statusClass;
    pill.textContent = statusText;
  }
  if (heroReviewPill) {
    heroReviewPill.className = statusClass;
    heroReviewPill.textContent = statusText;
  }
  if (overviewReviewPill) {
    overviewReviewPill.className = statusClass;
    overviewReviewPill.textContent = statusText;
  }
  if (reviewChecklistPill) {
    reviewChecklistPill.className = statusClass;
    reviewChecklistPill.textContent = statusText;
  }

  const btnLabel = isReviewed ? "Revert to Pending Review" : "Mark Overall Brief as Reviewed";
  const btnClass = isReviewed ? "btn btn-secondary" : "btn btn-primary";

  if (toggleBtn) {
    toggleBtn.textContent = btnLabel;
    toggleBtn.className = btnClass;
    toggleBtn.onclick = toggleOverallReview;
  }
  if (paneToggleBtn) {
    paneToggleBtn.textContent = btnLabel;
    paneToggleBtn.className = btnClass;
    paneToggleBtn.onclick = toggleOverallReview;
  }

  // Count reviewed items
  const items = reviewData.reviewed_items || {};
  const totalReviewed = Object.keys(items).length;
  const verifiedCount = Object.values(items).filter(v => v === "verified").length;
  const needsReviewCount = Object.values(items).filter(v => v === "needs_review").length;

  const countLabel = document.getElementById("verified-count-label");
  if (countLabel) {
    countLabel.textContent = `${totalReviewed} items reviewed (${verifiedCount} verified, ${needsReviewCount} flagged)`;
  }

  const overviewCountLabel = document.getElementById("overview-review-count-label");
  if (overviewCountLabel) {
    overviewCountLabel.textContent = `${verifiedCount} verified, ${needsReviewCount} flagged (${totalReviewed} reviewed)`;
  }

  const checklistCount = document.getElementById("review-checklist-count");
  if (checklistCount) {
    checklistCount.textContent = `${verifiedCount} verified, ${needsReviewCount} flagged for review (${totalReviewed} reviewed)`;
  }
}

async function toggleOverallReview() {
  const isReviewed = reviewData.review_status === "reviewed";
  const nextStatus = isReviewed ? "pending" : "reviewed";
  try {
    const res = await fetch(`/api/patient/${PATIENT_ID}/review`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ review_status: nextStatus })
    });
    if (!res.ok) throw new Error("Failed to update status");
    reviewData = await res.json();
    renderAll();
  } catch (e) {
    alert("Unable to update review status. Please retry.");
  }
}

// 2. Executive Consultation Overview Rendering
function renderOverviewTab() {
  if (!briefData) return;

  const docCount = (briefData.header?.source_documents_count !== undefined && briefData.header?.source_documents_count !== null)
    ? briefData.header.source_documents_count 
    : (briefData.source_documents?.length || 0);

  const authTimelineCount = (briefData.header?.total_timeline_events !== undefined && briefData.header?.total_timeline_events !== null)
    ? briefData.header.total_timeline_events
    : (timelineData?.total_events || briefData.recent_timeline?.length || 0);

  const genuineChanges = getGenuineChanges();
  const changesCount = genuineChanges.length;

  const flagsCount = (flagsData && flagsData.flags && flagsData.flags.length > 0)
    ? flagsData.flags.length
    : (briefData.documentation_flags?.length || 0);

  const medsCount = briefData.medications?.length || 0;
  const invsCount = briefData.investigations?.length || 0;

  const items = reviewData?.reviewed_items || {};
  const reviewedCount = Object.keys(items).length;

  // Header & Patient Strip
  const heroPatientId = document.getElementById("hero-patient-id");
  if (heroPatientId) heroPatientId.textContent = briefData.header?.patient_id || PATIENT_ID;

  const coverageDisplay = document.getElementById("coverage-display");
  if (coverageDisplay) coverageDisplay.textContent = `Based on ${docCount} documents`;

  const heroSourceStrip = document.getElementById("hero-source-docs-strip");
  if (heroSourceStrip) heroSourceStrip.textContent = `${docCount} Documents`;

  const heroBriefStrip = document.getElementById("hero-brief-status-strip");
  if (heroBriefStrip) {
    const genAt = briefData.header?.generated_at ? formatDisplayDate(briefData.header.generated_at.split("T")[0]) : "Generated";
    heroBriefStrip.textContent = genAt;
  }

  // Dynamic KPI Metric Boxes (No hardcoded values)
  const docBox = document.getElementById("hero-doc-count");
  if (docBox) docBox.textContent = docCount;

  const timelineBox = document.getElementById("hero-timeline-count");
  if (timelineBox) timelineBox.textContent = authTimelineCount;

  const changesBox = document.getElementById("hero-changes-count");
  if (changesBox) changesBox.textContent = changesCount;

  const flagsBox = document.getElementById("hero-flags-count");
  if (flagsBox) flagsBox.textContent = flagsCount;

  const medsBox = document.getElementById("hero-meds-count");
  if (medsBox) medsBox.textContent = medsCount;

  const invsBox = document.getElementById("hero-invs-count");
  if (invsBox) invsBox.textContent = invsCount;

  const reviewBox = document.getElementById("hero-review-count");
  if (reviewBox) reviewBox.textContent = `${reviewedCount} / ${authTimelineCount}`;

  const reviewText = document.getElementById("hero-review-status-text");
  if (reviewText) {
    reviewText.textContent = reviewData?.review_status === "reviewed" ? "Overall brief reviewed" : "Pending clinician review";
  }

  // Consultation Context Cards
  const ctxReason = document.getElementById("ctx-reason-for-visit");
  const ctxEncounter = document.getElementById("ctx-latest-encounter");
  const ctxHistory = document.getElementById("ctx-relevant-history");
  const ctxRecord = document.getElementById("ctx-latest-record");

  const fallbackText = "Not documented in currently processed records.";
  if (ctxReason) {
    const val = briefData.consultation_context?.reason_for_visit;
    ctxReason.textContent = val || fallbackText;
    ctxReason.className = (val && val !== fallbackText) ? "context-value" : "context-value empty-doc";
  }
  if (ctxEncounter) {
    const val = briefData.consultation_context?.latest_encounter;
    ctxEncounter.textContent = val || fallbackText;
    ctxEncounter.className = (val && val !== fallbackText) ? "context-value" : "context-value empty-doc";
  }
  if (ctxHistory) {
    const val = briefData.consultation_context?.relevant_history;
    ctxHistory.textContent = val || fallbackText;
    ctxHistory.className = (val && val !== fallbackText) ? "context-value" : "context-value empty-doc";
  }
  if (ctxRecord) {
    const val = briefData.consultation_context?.latest_record;
    ctxRecord.textContent = val || fallbackText;
    ctxRecord.className = (val && val !== fallbackText) ? "context-value" : "context-value empty-doc";
  }

  // --- Compact Previews ---

  // 1. Timeline Preview (4 most recent events)
  const timelinePreviewList = document.getElementById("overview-timeline-preview-list");
  const previewTimelineBtn = document.getElementById("preview-timeline-btn");
  if (previewTimelineBtn) previewTimelineBtn.textContent = `View all (${authTimelineCount}) →`;

  if (timelinePreviewList) {
    const rawEvents = (timelineData && timelineData.events && timelineData.events.length > 0)
      ? timelineData.events
      : (briefData.recent_timeline || []);

    const datedEvents = [...rawEvents].filter(ev => ev.date).sort((a, b) => String(b.date).localeCompare(String(a.date)));
    const previewEvents = datedEvents.slice(0, 4);

    if (previewEvents.length === 0) {
      timelinePreviewList.innerHTML = `<div class="empty-state">No timeline events documented.</div>`;
    } else {
      timelinePreviewList.innerHTML = previewEvents.map(ev => {
        const docType = getEventDocumentType(ev.event_type || ev.category);
        const displayDate = formatDisplayDate(ev.date);
        return `
          <div class="preview-item">
            <div class="preview-item-top">
              <span class="category-tag tag-${(ev.event_type || 'other').toLowerCase()}">${escapeHtml(docType)}</span>
              <span class="card-date">${escapeHtml(displayDate)}</span>
            </div>
            <div class="preview-item-title">${escapeHtml(ev.title || "Documented Clinical Event")}</div>
            <div style="margin-top: 4px;">
              <button class="btn btn-secondary" style="padding: 2px 7px; font-size: 0.72rem;" onclick="openSourceModal('${ev.source?.document_id || ''}', ${ev.source?.page_number || 1})">
                Open source page
              </button>
            </div>
          </div>
        `;
      }).join("");
    }
  }

  // 2. Documented Changes Preview (up to 3 genuine changes)
  const changesPreviewList = document.getElementById("overview-changes-preview-list");
  const previewChangesBtn = document.getElementById("preview-changes-btn");
  if (previewChangesBtn) previewChangesBtn.textContent = `View all (${changesCount}) →`;

  if (changesPreviewList) {
    const previewChanges = genuineChanges.slice(0, 3);
    if (previewChanges.length === 0) {
      changesPreviewList.innerHTML = `<div class="empty-state">No documented changes across records.</div>`;
    } else {
      changesPreviewList.innerHTML = previewChanges.map(ch => `
        <div class="preview-item">
          <div class="preview-item-top">
            <span class="category-tag tag-lab">${escapeHtml(ch.category || "Lab")}</span>
            <span class="card-date">${escapeHtml(formatDisplayDate(ch.latest_date))}</span>
          </div>
          <div class="preview-item-title">${escapeHtml(ch.entity_name)}</div>
          <div class="preview-item-diff">
            <span class="preview-diff-val">${escapeHtml(ch.previous_value)}</span>
            <span>→</span>
            <span class="preview-diff-val current">${escapeHtml(ch.latest_value)}</span>
          </div>
        </div>
      `).join("");
    }
  }

  // 3. Documentation Flags Preview (active flags)
  const flagsPreviewList = document.getElementById("overview-flags-preview-list");
  const previewFlagsBtn = document.getElementById("preview-flags-btn");
  if (previewFlagsBtn) previewFlagsBtn.textContent = `View all (${flagsCount}) →`;

  if (flagsPreviewList) {
    const rawFlags = (flagsData && flagsData.flags && flagsData.flags.length > 0)
      ? flagsData.flags
      : (briefData.documentation_flags || []);

    const previewFlags = rawFlags.slice(0, 3);
    if (previewFlags.length === 0) {
      flagsPreviewList.innerHTML = `<div class="empty-state">No documentation flags detected.</div>`;
    } else {
      flagsPreviewList.innerHTML = previewFlags.map(fl => {
        const src = (fl.sources && fl.sources.length > 0) ? fl.sources[0] : null;
        return `
          <div class="preview-item">
            <div class="preview-item-top">
              <span class="badge-status-missing" style="font-size: 0.72rem;">Information Check</span>
            </div>
            <div class="preview-item-title">${escapeHtml(fl.title || "Information Check")}</div>
            <div class="preview-item-desc">${escapeHtml(fl.description || "")}</div>
            ${src ? `
              <div style="margin-top: 4px;">
                <button class="btn btn-secondary" style="padding: 2px 7px; font-size: 0.72rem;" onclick="openSourceModal('${src.document_id}', ${src.page_number || 1})">
                  Open source p.${src.page_number || 1}
                </button>
              </div>
            ` : ''}
          </div>
        `;
      }).join("");
    }
  }
}

// 3. Recent Timeline Pane
function renderRecentTimeline() {
  const container = document.getElementById("timeline-list");
  if (!container) return;

  const rawEvents = (timelineData && timelineData.events && timelineData.events.length > 0)
    ? timelineData.events
    : (briefData?.recent_timeline || []);

  // Sorted chronologically by date
  const events = [...rawEvents].filter(ev => ev.date).sort((a, b) => String(a.date).localeCompare(String(b.date)));

  if (events.length === 0) {
    container.innerHTML = `<div class="empty-state">No patient documents have been processed yet.</div>`;
    return;
  }

  container.innerHTML = events.map((ev, idx) => {
    const itemId = ev.event_id || `timeline_${idx}`;
    const itemStatus = (reviewData?.reviewed_items || {})[itemId];
    const isVerified = itemStatus === "verified";
    const isNeedsReview = itemStatus === "needs_review";

    const cardClass = isNeedsReview ? "brief-card needs-review" : "brief-card";
    const docType = getEventDocumentType(ev.event_type || ev.category);

    return `
      <div class="${cardClass}" id="card-${itemId}">
        <div class="card-meta-line">
          <div style="display: flex; align-items: center; gap: 8px;">
            <span class="category-tag tag-${(ev.event_type || 'other').toLowerCase()}">${escapeHtml(docType)}</span>
            <span class="card-date">${escapeHtml(formatDisplayDate(ev.date))}</span>
          </div>
          <div class="provenance-citation">
            Source: ${escapeHtml(ev.source?.file_name || 'document')}, p.${ev.source?.page_number || 1}
          </div>
        </div>

        <h3 class="card-title">${escapeHtml(ev.title || "Documented Encounter")}</h3>
        <p class="card-details">${escapeHtml(ev.description || ev.details || "")}</p>

        <div class="card-actions-bar">
          <button class="btn btn-secondary" onclick="openSourceModal('${ev.source?.document_id || ''}', ${ev.source?.page_number || 1})">
            Open source page
          </button>
          <div class="review-btn-group">
            <button class="btn btn-verify ${isVerified ? 'is-verified' : ''}" onclick="setItemReviewStatus('${itemId}', 'verified')">
              ${isVerified ? '✓ Verified' : 'Verify'}
            </button>
            <button class="btn btn-needs-review ${isNeedsReview ? 'is-needs-review' : ''}" onclick="setItemReviewStatus('${itemId}', 'needs_review')">
              ${isNeedsReview ? '⚠ Needs Review' : 'Needs Review'}
            </button>
          </div>
        </div>
      </div>
    `;
  }).join("");
}

// 4. What Changed Pane
function renderWhatChanged() {
  const container = document.getElementById("changes-list");
  if (!container) return;

  const changes = getGenuineChanges();
  if (changes.length === 0) {
    container.innerHTML = `<div class="empty-state">No documented changes found in currently processed records.</div>`;
    return;
  }

  container.innerHTML = changes.map((ch, idx) => {
    const itemId = ch.change_id || `change_${idx}`;
    const itemStatus = (reviewData?.reviewed_items || {})[itemId];
    const isVerified = itemStatus === "verified";
    const isNeedsReview = itemStatus === "needs_review";

    const cardClass = isNeedsReview ? "brief-card change-card needs-review" : "brief-card change-card";

    return `
      <div class="${cardClass}" id="card-${itemId}">
        <div class="card-meta-line">
          <span class="category-tag tag-lab">${escapeHtml(ch.category || "Parameter")}</span>
          <div class="provenance-citation">
            Latest: ${escapeHtml(ch.latest_source?.file_name || 'document')}, p.${ch.latest_source?.page_number || 1}
          </div>
        </div>

        <h3 class="card-title" style="margin-bottom: 8px;">Documented Change: ${escapeHtml(ch.entity_name)}</h3>
        <div class="change-values-row">
          <div class="change-val-box">
            <div class="change-val-label">Previous (${escapeHtml(formatDisplayDate(ch.previous_date))})</div>
            <div class="change-val-text">${escapeHtml(ch.previous_value)}</div>
            <div style="font-size: 0.72rem; color: var(--color-text-subtle); margin-top: 4px;">${escapeHtml(ch.previous_source?.file_name || '')}, p.${ch.previous_source?.page_number || 1}</div>
          </div>
          <div class="change-arrow">→</div>
          <div class="change-val-box">
            <div class="change-val-label">Latest (${escapeHtml(formatDisplayDate(ch.latest_date))})</div>
            <div class="change-val-text current">${escapeHtml(ch.latest_value)}</div>
            <div style="font-size: 0.72rem; color: var(--color-text-subtle); margin-top: 4px;">${escapeHtml(ch.latest_source?.file_name || '')}, p.${ch.latest_source?.page_number || 1}</div>
          </div>
        </div>

        <div class="card-actions-bar" style="margin-top: 14px;">
          <button class="btn btn-secondary" onclick="openSourceModal('${ch.latest_source?.document_id || ''}', ${ch.latest_source?.page_number || 1})">
            Open source page
          </button>
          <div class="review-btn-group">
            <button class="btn btn-verify ${isVerified ? 'is-verified' : ''}" onclick="setItemReviewStatus('${itemId}', 'verified')">
              ${isVerified ? '✓ Verified' : 'Verify'}
            </button>
            <button class="btn btn-needs-review ${isNeedsReview ? 'is-needs-review' : ''}" onclick="setItemReviewStatus('${itemId}', 'needs_review')">
              ${isNeedsReview ? '⚠ Needs Review' : 'Needs Review'}
            </button>
          </div>
        </div>
      </div>
    `;
  }).join("");
}

// 5. Documentation Flags Pane
function renderFlags() {
  const container = document.getElementById("flags-list");
  if (!container) return;

  const flags = briefData?.documentation_flags || [];
  if (flags.length === 0) {
    container.innerHTML = `<div class="empty-state">No documentation flags currently generated.</div>`;
    return;
  }

  container.innerHTML = flags.map((fl, idx) => {
    const itemId = fl.flag_id || `flag_${idx}`;
    const itemStatus = (reviewData?.reviewed_items || {})[itemId];
    const isVerified = itemStatus === "verified";
    const isNeedsReview = itemStatus === "needs_review";

    const cardClass = isNeedsReview ? "brief-card flag-card needs-review" : "brief-card flag-card";
    const src = (fl.sources && fl.sources.length > 0) ? fl.sources[0] : null;

    return `
      <div class="${cardClass}" id="card-${itemId}">
        <div class="flag-alert-header">
          <span>Information Flag: ${escapeHtml(fl.title || "Information Check")}</span>
        </div>
        <p class="card-details" style="margin: 8px 0;">${escapeHtml(fl.description || "")}</p>
        ${src ? `
          <div class="provenance-citation" style="margin-bottom: 12px;">
            Source: ${escapeHtml(src.file_name || 'document')}, p.${src.page_number || 1}
          </div>
        ` : ''}

        <div class="card-actions-bar">
          ${src ? `
            <button class="btn btn-secondary" onclick="openSourceModal('${src.document_id}', ${src.page_number || 1})">
              Open source page
            </button>
          ` : '<span></span>'}
          <div class="review-btn-group">
            <button class="btn btn-verify ${isVerified ? 'is-verified' : ''}" onclick="setItemReviewStatus('${itemId}', 'verified')">
              ${isVerified ? '✓ Verified' : 'Verify'}
            </button>
            <button class="btn btn-needs-review ${isNeedsReview ? 'is-needs-review' : ''}" onclick="setItemReviewStatus('${itemId}', 'needs_review')">
              ${isNeedsReview ? '⚠ Needs Review' : 'Needs Review'}
            </button>
          </div>
        </div>
      </div>
    `;
  }).join("");
}

// 6. Medications Table Pane
function renderMedications() {
  const tbody = document.getElementById("meds-table-body");
  if (!tbody) return;

  const meds = briefData?.medications || [];
  if (meds.length === 0) {
    tbody.innerHTML = `<tr><td colspan="6" class="empty-state">No medications documented in currently processed records.</td></tr>`;
    return;
  }

  tbody.innerHTML = meds.map((m, idx) => {
    const itemId = m.medication_id || `med_${idx}`;
    const itemStatus = (reviewData?.reviewed_items || {})[itemId];
    const isVerified = itemStatus === "verified";
    const isNeedsReview = itemStatus === "needs_review";

    return `
      <tr id="row-${itemId}">
        <td><strong>${escapeHtml(m.medicine_name)}</strong></td>
        <td><span class="category-tag tag-medication">${escapeHtml(m.status || "Documented")}</span></td>
        <td>${escapeHtml(m.dose || m.strength || "—")}</td>
        <td>${escapeHtml(formatDisplayDate(m.date))}</td>
        <td>
          <button class="btn btn-secondary" style="padding: 2px 8px; font-size: 0.75rem;" onclick="openSourceModal('${m.source?.document_id || ''}', ${m.source?.page_number || 1})">
            ${escapeHtml(m.source?.file_name || 'source')}, p.${m.source?.page_number || 1}
          </button>
        </td>
        <td>
          <div class="review-btn-group">
            <button class="btn btn-verify ${isVerified ? 'is-verified' : ''}" style="padding: 2px 8px; font-size: 0.75rem;" onclick="setItemReviewStatus('${itemId}', 'verified')">
              ${isVerified ? '✓' : 'Verify'}
            </button>
            <button class="btn btn-needs-review ${isNeedsReview ? 'is-needs-review' : ''}" style="padding: 2px 8px; font-size: 0.75rem;" onclick="setItemReviewStatus('${itemId}', 'needs_review')">
              ${isNeedsReview ? '⚠' : 'Flag'}
            </button>
          </div>
        </td>
      </tr>
    `;
  }).join("");
}

// 7. Investigations Table Pane
function renderInvestigations() {
  const tbody = document.getElementById("invs-table-body");
  if (!tbody) return;

  const invs = briefData?.investigations || [];
  if (invs.length === 0) {
    tbody.innerHTML = `<tr><td colspan="6" class="empty-state">No investigations documented in currently processed records.</td></tr>`;
    return;
  }

  tbody.innerHTML = invs.map((inv, idx) => {
    const itemId = inv.investigation_id || `inv_${idx}`;
    const itemStatus = (reviewData?.reviewed_items || {})[itemId];
    const isVerified = itemStatus === "verified";
    const isNeedsReview = itemStatus === "needs_review";
    const isAvail = inv.result_status_text === "RESULT AVAILABLE";
    const badgeClass = isAvail ? "badge-status-avail" : "badge-status-missing";

    return `
      <tr id="row-${itemId}">
        <td><strong>${escapeHtml(inv.investigation_name)}</strong></td>
        <td><span class="badge-status-ordered">${escapeHtml(inv.status || "ORDERED")}</span></td>
        <td>${escapeHtml(formatDisplayDate(inv.order_date))}</td>
        <td><span class="${badgeClass}">${escapeHtml(inv.result_status_text || "ORDERED")}</span></td>
        <td>
          <button class="btn btn-secondary" style="padding: 2px 8px; font-size: 0.75rem;" onclick="openSourceModal('${inv.source?.document_id || ''}', ${inv.source?.page_number || 1})">
            ${escapeHtml(inv.source?.file_name || 'source')}, p.${inv.source?.page_number || 1}
          </button>
        </td>
        <td>
          <div class="review-btn-group">
            <button class="btn btn-verify ${isVerified ? 'is-verified' : ''}" style="padding: 2px 8px; font-size: 0.75rem;" onclick="setItemReviewStatus('${itemId}', 'verified')">
              ${isVerified ? '✓' : 'Verify'}
            </button>
            <button class="btn btn-needs-review ${isNeedsReview ? 'is-needs-review' : ''}" style="padding: 2px 8px; font-size: 0.75rem;" onclick="setItemReviewStatus('${itemId}', 'needs_review')">
              ${isNeedsReview ? '⚠' : 'Flag'}
            </button>
          </div>
        </td>
      </tr>
    `;
  }).join("");
}

// 8. Sources Grid Pane
function renderSources() {
  const container = document.getElementById("sources-grid");
  if (!container) return;

  const sources = briefData?.source_documents || [];
  if (sources.length === 0) {
    container.innerHTML = `<div class="empty-state">No source documents available.</div>`;
    return;
  }

  container.innerHTML = sources.map(doc => `
    <div class="brief-card">
      <div class="card-meta-line" style="margin-bottom: 8px;">
        <span class="category-tag tag-other">${escapeHtml(doc.title || "Document")}</span>
        <span class="card-date">${doc.pages || 1} page${(doc.pages || 1) > 1 ? 's' : ''}</span>
      </div>
      <h4 style="font-size: 0.95rem; font-weight: 600; margin-bottom: 6px; word-break: break-all;">${escapeHtml(doc.file_name)}</h4>
      <p style="font-size: 0.78rem; color: var(--color-text-subtle); margin-bottom: 12px;">ID: ${escapeHtml(doc.document_id)}</p>
      <button class="btn btn-secondary" style="width: 100%; justify-content: center;" onclick="openSourceModal('${doc.document_id}', 1)">
        Open source
      </button>
    </div>
  `).join("");
}

// 9. Doctor Review Checklist Pane
function renderDoctorReviewTab() {
  const container = document.getElementById("review-items-container");
  if (!container || !briefData) return;

  const allItems = [];

  (briefData.recent_timeline || []).forEach((ev, idx) => {
    allItems.push({
      id: ev.event_id || `timeline_${idx}`,
      category: getEventDocumentType(ev.event_type || ev.category),
      title: ev.title || "Timeline Encounter",
      details: ev.description || ev.details || "",
      date: formatDisplayDate(ev.date),
      source: ev.source
    });
  });

  (briefData.what_changed || []).forEach((ch, idx) => {
    allItems.push({
      id: ch.change_id || `change_${idx}`,
      category: "Change",
      title: `Documented Change: ${ch.entity_name}`,
      details: `${ch.previous_value} (${formatDisplayDate(ch.previous_date)}) → ${ch.latest_value} (${formatDisplayDate(ch.latest_date)})`,
      date: formatDisplayDate(ch.latest_date),
      source: ch.latest_source
    });
  });

  (briefData.documentation_flags || []).forEach((fl, idx) => {
    allItems.push({
      id: fl.flag_id || `flag_${idx}`,
      category: "Flag",
      title: `Information Flag: ${fl.title}`,
      details: fl.description || "",
      date: "Information Check",
      source: (fl.sources && fl.sources.length > 0) ? fl.sources[0] : null
    });
  });

  (briefData.medications || []).forEach((m, idx) => {
    allItems.push({
      id: m.medication_id || `med_${idx}`,
      category: "Medication",
      title: `Medication: ${m.medicine_name}`,
      details: `Status: ${m.status || 'Documented'}, Dose: ${m.dose || m.strength || '—'}, Date: ${formatDisplayDate(m.date)}`,
      date: formatDisplayDate(m.date),
      source: m.source
    });
  });

  (briefData.investigations || []).forEach((inv, idx) => {
    allItems.push({
      id: inv.investigation_id || `inv_${idx}`,
      category: "Investigation",
      title: `Investigation: ${inv.investigation_name}`,
      details: `Status: ${inv.status || 'ORDERED'}, Ordered: ${formatDisplayDate(inv.order_date)}, Result: ${inv.result_status_text || 'Pending'}`,
      date: formatDisplayDate(inv.order_date),
      source: inv.source
    });
  });

  // Filter items
  const reviewed = reviewData?.reviewed_items || {};
  const filtered = allItems.filter(item => {
    const status = reviewed[item.id] || "pending";
    if (currentReviewFilter === "pending") return status === "pending";
    if (currentReviewFilter === "verified") return status === "verified";
    if (currentReviewFilter === "needs_review") return status === "needs_review";
    return true; // "all"
  });

  if (filtered.length === 0) {
    container.innerHTML = `<div class="empty-state">No items found matching filter "${escapeHtml(currentReviewFilter)}".</div>`;
    return;
  }

  container.innerHTML = filtered.map(item => {
    const itemStatus = reviewed[item.id];
    const isVerified = itemStatus === "verified";
    const isNeedsReview = itemStatus === "needs_review";

    const cardClass = isNeedsReview ? "brief-card needs-review" : "brief-card";

    return `
      <div class="${cardClass}" id="checklist-${item.id}">
        <div class="card-meta-line">
          <div style="display: flex; align-items: center; gap: 8px;">
            <span class="category-tag tag-${(item.category || 'other').toLowerCase()}">${escapeHtml(item.category)}</span>
            <span class="card-date">${escapeHtml(item.date)}</span>
          </div>
          <div class="provenance-citation">
            Source: ${escapeHtml(item.source?.file_name || 'document')}, p.${item.source?.page_number || 1}
          </div>
        </div>

        <h3 class="card-title">${escapeHtml(item.title)}</h3>
        <p class="card-details">${escapeHtml(item.details)}</p>

        <div class="card-actions-bar">
          <button class="btn btn-secondary" onclick="openSourceModal('${item.source?.document_id || ''}', ${item.source?.page_number || 1})">
            Open source page
          </button>
          <div class="review-btn-group">
            <button class="btn btn-verify ${isVerified ? 'is-verified' : ''}" onclick="setItemReviewStatus('${item.id}', 'verified')">
              ${isVerified ? '✓ Verified' : 'Verify'}
            </button>
            <button class="btn btn-needs-review ${isNeedsReview ? 'is-needs-review' : ''}" onclick="setItemReviewStatus('${item.id}', 'needs_review')">
              ${isNeedsReview ? '⚠ Needs Review' : 'Needs Review'}
            </button>
          </div>
        </div>
      </div>
    `;
  }).join("");
}

function filterReviewItems(filter) {
  currentReviewFilter = filter;
  document.querySelectorAll(".filter-chip").forEach(chip => {
    chip.classList.toggle("active", chip.getAttribute("data-filter") === filter);
  });
  renderDoctorReviewTab();
}

async function setItemReviewStatus(itemId, newStatus) {
  const current = (reviewData?.reviewed_items || {})[itemId];
  const targetStatus = current === newStatus ? null : newStatus;

  try {
    const res = await fetch(`/api/patient/${PATIENT_ID}/review`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        item_id: itemId,
        item_status: targetStatus || "pending"
      })
    });
    if (!res.ok) throw new Error("Failed to update item status");
    reviewData = await res.json();
    renderAll();
  } catch (e) {
    alert("Unable to record item review status. Please retry.");
  }
}

// 10. Demo Data Reset Action (Task 13)
async function handleDemoReset() {
  const confirmed = confirm(
    "Reset the synthetic demo environment to its baseline state?\n\n" +
    "This will remove any uploaded documents, restore the 10-document synthetic dataset, " +
    "and reset doctor review status to pending."
  );
  if (!confirmed) return;

  try {
    const res = await fetch(`/api/patient/${PATIENT_ID}/reset`, {
      method: "POST"
    });
    if (!res.ok) throw new Error(`Reset failed: ${res.status}`);
    const data = await res.json();
    alert("Synthetic demo environment successfully reset to 10-document baseline.");

    // Clear local staged files and reload
    stagedFiles = [];
    renderStagedFiles();
    await refreshPatientData();
    switchToTab("tab-overview");
  } catch (err) {
    alert("Unable to complete demo reset: " + err.message);
  }
}

// 11. Multi-Document Upload & Processing Flow
function initUpload() {
  const dropzone = document.getElementById("upload-dropzone");
  const fileInput = document.getElementById("file-input");
  const clearBtn = document.getElementById("clear-staged-btn");
  const processBtn = document.getElementById("process-documents-btn");

  if (!dropzone || !fileInput) return;

  dropzone.addEventListener("click", () => fileInput.click());
  dropzone.addEventListener("keydown", (e) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      fileInput.click();
    }
  });

  dropzone.addEventListener("dragover", (e) => {
    e.preventDefault();
    dropzone.classList.add("drag-over");
  });

  dropzone.addEventListener("dragleave", () => {
    dropzone.classList.remove("drag-over");
  });

  dropzone.addEventListener("drop", (e) => {
    e.preventDefault();
    dropzone.classList.remove("drag-over");
    if (e.dataTransfer.files) {
      handleFilesSelected(Array.from(e.dataTransfer.files));
    }
  });

  fileInput.addEventListener("change", () => {
    if (fileInput.files) {
      handleFilesSelected(Array.from(fileInput.files));
      fileInput.value = "";
    }
  });

  if (clearBtn) {
    clearBtn.addEventListener("click", () => {
      stagedFiles = [];
      renderStagedFiles();
    });
  }

  if (processBtn) {
    processBtn.addEventListener("click", processDocuments);
  }
}

function handleFilesSelected(newFiles) {
  const allowed = [".pdf", ".png", ".jpg", ".jpeg"];
  const validFiles = [];
  const rejectedFiles = [];

  newFiles.forEach(f => {
    const ext = "." + f.name.split(".").pop().toLowerCase();
    if (allowed.includes(ext)) {
      validFiles.push(f);
    } else {
      rejectedFiles.push(f.name);
    }
  });

  if (rejectedFiles.length > 0) {
    alert("Unsupported file type. Please upload PDF, PNG, JPG, or JPEG.\nRejected: " + rejectedFiles.join(", "));
  }

  stagedFiles = stagedFiles.concat(validFiles);
  renderStagedFiles();
}

function renderStagedFiles() {
  const container = document.getElementById("staged-container");
  const list = document.getElementById("staged-files-list");
  const countBadge = document.getElementById("count-staged");

  if (countBadge) countBadge.textContent = stagedFiles.length;

  if (!container || !list) return;

  if (stagedFiles.length === 0) {
    container.style.display = "none";
    return;
  }

  container.style.display = "block";
  list.innerHTML = stagedFiles.map((file, idx) => {
    const sizeKb = (file.size / 1024).toFixed(1);
    const ext = file.name.split(".").pop().toUpperCase();
    return `
      <div class="staged-file-row">
        <div class="staged-file-meta">
          <span class="category-tag tag-other">${ext}</span>
          <span class="staged-file-name">${escapeHtml(file.name)}</span>
          <span class="staged-file-size">(${sizeKb} KB)</span>
        </div>
        <button class="btn-remove-staged" onclick="removeStagedFile(${idx})" aria-label="Remove ${escapeHtml(file.name)}">✕</button>
      </div>
    `;
  }).join("");
}

function removeStagedFile(idx) {
  stagedFiles.splice(idx, 1);
  renderStagedFiles();
}

async function processDocuments() {
  if (stagedFiles.length === 0) {
    alert("Please select at least one document before processing.");
    return;
  }

  const panel = document.getElementById("processing-panel");
  const overallPill = document.getElementById("processing-overall-pill");
  const summaryBox = document.getElementById("batch-summary-box");
  const summaryText = document.getElementById("batch-summary-text");
  const durationBox = document.getElementById("processing-duration-box");
  const durationText = document.getElementById("processing-duration-text");

  if (panel) panel.style.display = "block";
  if (summaryBox) summaryBox.style.display = "none";
  if (durationBox) durationBox.style.display = "none";
  if (overallPill) {
    overallPill.className = "review-status-pill status-pending";
    overallPill.textContent = "PROCESSING";
  }

  resetPipelineStages();

  // Progress simulation for user feedback
  setStageStatus(1, "processing");
  await sleep(250);
  setStageStatus(1, "completed");

  setStageStatus(2, "processing");
  await sleep(200);
  setStageStatus(2, "completed");

  setStageStatus(3, "processing");

  const formData = new FormData();
  stagedFiles.forEach(f => formData.append("files", f));

  try {
    const res = await fetch(`/api/patient/${PATIENT_ID}/documents/upload`, {
      method: "POST",
      body: formData
    });

    if (!res.ok) {
      const errJson = await res.json().catch(() => ({}));
      throw new Error(errJson.detail || "Unable to complete document processing. Please check the server status.");
    }

    const data = await res.json();

    // Advance stages
    setStageStatus(3, "completed");
    setStageStatus(4, "processing");
    await sleep(200);
    setStageStatus(4, "completed");

    setStageStatus(5, "processing");
    await sleep(150);
    setStageStatus(5, "completed");

    setStageStatus(6, "completed");
    setStageStatus(7, "completed");
    setStageStatus(8, "completed");
    setStageStatus(9, "completed");
    setStageStatus(10, "completed");

    if (overallPill) {
      overallPill.className = "review-status-pill status-reviewed";
      overallPill.textContent = "COMPLETED";
    }

    // Display measured processing time if available (Task 21)
    if (data.processing_time_seconds !== undefined && data.processing_time_seconds !== null) {
      if (durationBox && durationText) {
        durationText.textContent = `Processing completed in ${data.processing_time_seconds} seconds.`;
        durationBox.style.display = "flex";
      }
    }

    // Render batch summary
    if (summaryBox && summaryText) {
      const s = data.summary || {
        documents_received: stagedFiles.length,
        successfully_processed: stagedFiles.length,
        warnings: 0,
        failed: 0
      };
      summaryText.textContent = `Document processed successfully. MedChronicle updated. (Received: ${s.documents_received}, Processed: ${s.successfully_processed}${s.warnings ? `, Warnings: ${s.warnings}` : ''})`;
      summaryBox.style.display = "flex";
    }

    // Render processed results table (Task 6)
    renderProcessedTable(data.documents || []);

    // Clear staged files and reload brief data
    stagedFiles = [];
    renderStagedFiles();
    await refreshPatientData();

  } catch (err) {
    setStageStatus(3, "failed");
    if (overallPill) {
      overallPill.className = "review-status-pill status-pending";
      overallPill.style.background = "#fee2e2";
      overallPill.style.color = "#991b1b";
      overallPill.textContent = "FAILED";
    }
    alert(err.message || "Unable to complete document processing. Please retry.");
  }
}

function renderProcessedTable(docs) {
  const container = document.getElementById("processed-results-container");
  const tbody = document.getElementById("processed-table-body");
  if (!container || !tbody) return;

  if (docs.length === 0) {
    container.style.display = "none";
    return;
  }

  container.style.display = "block";
  tbody.innerHTML = docs.map(doc => {
    const hasWarnings = doc.technical_status === "needs_review" || (doc.quality_issues && doc.quality_issues.length > 0);
    const statusPill = doc.technical_status === "success" 
      ? '<span class="stage-badge completed">Completed</span>'
      : (doc.technical_status === "needs_review"
          ? '<span class="stage-badge warning">Warning</span>'
          : '<span class="stage-badge failed">Failed</span>');

    const qualityText = hasWarnings 
      ? `<span style="color: #b45309; font-size: 0.8rem;">Technical Warning: ${escapeHtml((doc.quality_issues || []).join('; ') || 'Low OCR confidence')}</span>`
      : `<span style="color: #059669; font-size: 0.8rem;">Good</span>`;

    const ocrText = doc.ocr_used ? "OCR extraction" : "Native text extraction";

    return `
      <tr>
        <td><strong>${escapeHtml(doc.file_name)}</strong></td>
        <td><span class="category-tag tag-other">${escapeHtml(doc.classification)}</span></td>
        <td>${statusPill}</td>
        <td>${ocrText}</td>
        <td>${qualityText}</td>
        <td>${doc.facts_extracted_count || 0}</td>
        <td>
          <button class="btn btn-secondary" style="padding: 2px 8px; font-size: 0.75rem;" onclick="openSourceModal('${doc.document_id}', 1)">
            Open source
          </button>
        </td>
      </tr>
    `;
  }).join("");
}

function resetPipelineStages() {
  for (let i = 1; i <= 10; i++) {
    setStageStatus(i, "pending");
  }
}

function setStageStatus(stageNum, status) {
  const el = document.getElementById(`stage-${stageNum}`);
  if (!el) return;

  el.className = `stage-item ${status}`;
  const badge = el.querySelector(".stage-badge");
  if (badge) {
    badge.className = `stage-badge ${status}`;
    badge.textContent = status.charAt(0).toUpperCase() + status.slice(1);
  }
}

function updateTabCounters() {
  if (!briefData) return;
  const docCount = (briefData.header?.source_documents_count !== undefined && briefData.header?.source_documents_count !== null)
    ? briefData.header.source_documents_count 
    : (briefData.source_documents?.length || 0);

  const authTimelineCount = (briefData.header?.total_timeline_events !== undefined && briefData.header?.total_timeline_events !== null)
    ? briefData.header.total_timeline_events
    : (timelineData?.total_events || briefData.recent_timeline?.length || 0);

  const countTimeline = document.getElementById("count-timeline");
  if (countTimeline) countTimeline.textContent = authTimelineCount;

  const countChanges = document.getElementById("count-changes");
  if (countChanges) countChanges.textContent = getGenuineChanges().length;

  const countFlags = document.getElementById("count-flags");
  if (countFlags) {
    const flagsCount = (flagsData && flagsData.flags && flagsData.flags.length > 0)
      ? flagsData.flags.length
      : (briefData.documentation_flags?.length || 0);
    countFlags.textContent = flagsCount;
  }

  const countMeds = document.getElementById("count-meds");
  if (countMeds) countMeds.textContent = briefData.medications?.length || 0;

  const countInvs = document.getElementById("count-invs");
  if (countInvs) countInvs.textContent = briefData.investigations?.length || 0;

  const countSources = document.getElementById("count-sources");
  if (countSources) countSources.textContent = docCount;

  const countReviews = document.getElementById("count-reviews");
  if (countReviews) {
    const reviewed = Object.keys(reviewData?.reviewed_items || {}).length;
    countReviews.textContent = reviewed;
  }
}

// Modal Viewers
function openSourceModal(docId, pageNumber) {
  const modal = document.getElementById("pdf-modal");
  const frame = document.getElementById("pdf-frame");
  const label = document.getElementById("modal-source-label");

  if (!modal || !frame) return;

  const targetDoc = (briefData?.source_documents || []).find(d => d.document_id === docId || d.file_name === docId);
  const fname = targetDoc ? targetDoc.file_name : (docId || "Source Document");
  const isImage = fname.toLowerCase().endsWith(".jpg") || fname.toLowerCase().endsWith(".jpeg") || fname.toLowerCase().endsWith(".png");

  if (label) {
    label.textContent = isImage ? `${fname} (Source Image Document)` : `${fname} (Page ${pageNumber || 1})`;
  }
  frame.src = `/api/patient/${PATIENT_ID}/documents/${docId}#page=${pageNumber || 1}`;
  modal.classList.add("active");
}

function closeModal() {
  const modal = document.getElementById("pdf-modal");
  const frame = document.getElementById("pdf-frame");
  if (modal) modal.classList.remove("active");
  if (frame) frame.src = "about:blank";
}

// Helpers
function escapeHtml(text) {
  if (text === null || text === undefined) return "";
  return String(text)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}
