from pathlib import Path

app_js_path = Path("frontend/app.js")
content = app_js_path.read_text(encoding="utf-8")

# 1. Replace renderOverviewTab block
overview_start = content.find("// 2. Overview Tab Rendering")
overview_end = content.find("// 3. Recent Timeline Pane")

if overview_start == -1 or overview_end == -1:
    raise ValueError(f"Could not find overview boundaries: start={overview_start}, end={overview_end}")

new_overview_fn = """// 2. Executive Consultation Overview Rendering
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

"""

content = content[:overview_start] + new_overview_fn + content[overview_end:]

# 2. Update renderWhatChanged to use getGenuineChanges()
content = content.replace(
    "const changes = briefData?.what_changed || [];",
    "const changes = getGenuineChanges();"
)

# 3. Update updateTabCounters to be 100% dynamic
counters_start = content.find("function updateTabCounters()")
counters_end = content.find("// Modal Viewers", counters_start)
if counters_start != -1 and counters_end != -1:
    new_counters_fn = """function updateTabCounters() {
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

"""
    content = content[:counters_start] + new_counters_fn + content[counters_end:]

# 4. In handleDemoReset, make sure it refreshes and switches to tab-overview
old_reset = "await loadData();\n    switchToTab(\"tab-overview\");"
new_reset = "await refreshPatientData();\n    switchToTab(\"tab-overview\");"
content = content.replace(old_reset, new_reset)

# 5. In processDocuments, make sure it calls await refreshPatientData();
old_upload_finish = "await loadData();"
new_upload_finish = "await refreshPatientData();"
content = content.replace(old_upload_finish, new_upload_finish)

app_js_path.write_text(content, encoding="utf-8")
print("Successfully updated frontend/app.js")
