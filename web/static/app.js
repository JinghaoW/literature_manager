/* global fetch, setTimeout, clearTimeout, FileReader, FormData */

// ====================================================================
// State
// ====================================================================
const state = {
  papers: [],
  activeFilter: '',    // '' = all, or 'Unread'|'Reading'|'Read'
  searchText: '',
  selectedId: null,
  notesTimer: null,
};

// ====================================================================
// DOM refs
// ====================================================================
const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

const filterBtns = $$('.filter-btn');
const searchInput = $('#search-input');
const searchClear = $('#search-clear');
const paperList = $('#paper-list');
const importBtn = $('#import-btn');
const folderInput = $('#folder-input');
const detailEmpty = $('#detail-empty');
const detailContent = $('#detail-content');
const detailTitle = $('#detail-title');
const statusSelect = $('#status-select');
const detailSummary = $('#detail-summary');
const detailKeywords = $('#detail-keywords');
const detailNotes = $('#detail-notes');
const notesSaved = $('#notes-saved');
const analyzeBtn = $('#analyze-btn');
const analyzeStatus = $('#analyze-status');
const relatedList = $('#related-list');
const annotationsList = $('#annotations-list');
const importAnnotsBtn = $('#import-annots-btn');
const openPdfBtn = $('#open-pdf-btn');

// ====================================================================
// API helpers
// ====================================================================
async function api(url, opts = {}) {
  const res = await fetch(url, opts);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: res.statusText }));
    throw new Error(err.error || 'Request failed');
  }
  return res.json();
}

// ====================================================================
// Load data
// ====================================================================
async function loadPapers() {
  const params = new URLSearchParams();
  if (state.activeFilter) params.set('status', state.activeFilter);
  if (state.searchText) params.set('search', state.searchText);
  params.set('order_by', 'created_time');
  params.set('descending', 'true');

  const papers = await api('/api/papers?' + params);
  state.papers = papers;
  renderPaperList();

  // Preserve selection if still in list.
  if (state.selectedId && !papers.find(p => p.id === state.selectedId)) {
    clearDetail();
  }
}

async function loadCounts() {
  const counts = await api('/api/papers/counts');
  $$('.filter-btn').forEach(btn => {
    const s = btn.dataset.status; // '' = all
    const key = s === '' ? 'all' : s.toLowerCase();
    btn.querySelector('.count').textContent = `(${counts[key] || 0})`;
  });
}

async function loadDetail(paperId) {
  const paper = await api(`/api/papers/${paperId}`);
  state.selectedId = paper.id;
  renderDetail(paper);
  loadRelated(paperId);
  loadAnnotations(paperId);
}

async function loadRelated(paperId) {
  try {
    const data = await api(`/api/papers/${paperId}/related`);
    renderRelated(data);
  } catch {
    relatedList.innerHTML = '<div class="no-results">—</div>';
  }
}

// ====================================================================
// Render
// ====================================================================
function renderPaperList() {
  if (state.papers.length === 0) {
    paperList.innerHTML = '<div class="no-results">No papers found</div>';
    return;
  }
  paperList.innerHTML = state.papers.map(p => {
    const date = p.created_time ? p.created_time.slice(0, 10) : '';
    return `
      <div class="paper-item status-${p.status} ${p.id === state.selectedId ? 'active' : ''}"
           data-id="${p.id}">
        <div class="title">${esc(p.title)}</div>
        <div class="meta">
          <span class="status-badge status-${p.status}">${p.status}</span>
          ${date}
        </div>
      </div>`;
  }).join('');

  // Click / double-click handlers.
  paperList.querySelectorAll('.paper-item').forEach(el => {
    el.addEventListener('click', () => loadDetail(Number(el.dataset.id)));
    el.addEventListener('dblclick', async (e) => {
      e.preventDefault();
      const id = Number(el.dataset.id);
      await api(`/api/papers/${id}/view`, { method: 'POST' });
    });
  });
}

function renderDetail(paper) {
  detailEmpty.classList.add('hidden');
  detailContent.classList.remove('hidden');
  detailTitle.textContent = paper.title;
  statusSelect.value = paper.status;
  state.selectedId = paper.id;

  detailSummary.textContent = paper.summary || 'No summary yet.';
  detailSummary.classList.toggle('muted', !paper.summary);

  detailKeywords.textContent = paper.keywords || '—';
  detailKeywords.classList.toggle('muted', !paper.keywords);

  detailNotes.value = paper.notes || '';
  notesSaved.classList.add('hidden');

  // Scroll to top.
  document.getElementById('right-panel').scrollTop = 0;
}

function renderRelated(data) {
  if (!data.length) {
    relatedList.innerHTML = '<div class="no-results">No related papers</div>';
    return;
  }
  relatedList.innerHTML = data.map(r => `
    <div class="related-item" data-id="${r.paper.id}">
      ${esc(r.paper.title)}<span class="score">${Math.round(r.score * 100)}%</span>
    </div>
  `).join('');

  relatedList.querySelectorAll('.related-item').forEach(el => {
    el.addEventListener('click', () => loadDetail(Number(el.dataset.id)));
  });
}

async function loadAnnotations(paperId) {
  try {
    const data = await api(`/api/papers/${paperId}/annotations`);
    renderAnnotations(data);
  } catch {
    annotationsList.innerHTML = '<span class="muted">—</span>';
  }
}

function renderAnnotations(data) {
  const anns = data.annotations || [];
  const hl = data.highlighted_text || '';

  if (!anns.length && !hl) {
    annotationsList.innerHTML = '<span class="muted">No annotations found in PDF</span>';
    return;
  }

  let html = '';
  anns.forEach(a => {
    const colorDot = a.color ? `<span class="annot-color" style="background:${a.color}"></span>` : '';
    html += `
      <div class="annot-item">
        <div class="annot-header">
          ${colorDot}<span class="annot-type">${esc(a.type)}</span>
          <span class="annot-page">p.${a.page}</span>
        </div>
        <div class="annot-text">${esc(a.text)}</div>
      </div>`;
  });

  if (hl) {
    html += '<div class="annot-hl-label">Highlighted text from PDF:</div>';
    html += `<div class="annot-hl-text">${esc(hl)}</div>`;
  }

  annotationsList.innerHTML = html;
}

function clearDetail() {
  state.selectedId = null;
  detailEmpty.classList.remove('hidden');
  detailContent.classList.add('hidden');
  relatedList.innerHTML = '';
  annotationsList.innerHTML = '<span class="muted">—</span>';
  // Clear active item in list.
  paperList.querySelectorAll('.paper-item.active').forEach(el => el.classList.remove('active'));
}

// ====================================================================
// Actions
// ====================================================================
statusSelect.addEventListener('change', async () => {
  if (!state.selectedId) return;
  await api(`/api/papers/${state.selectedId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ status: statusSelect.value }),
  });
  await loadPapers();
  await loadCounts();
});

detailNotes.addEventListener('input', () => {
  notesSaved.classList.add('hidden');
  clearTimeout(state.notesTimer);
  state.notesTimer = setTimeout(saveNotes, 800);
});

async function saveNotes() {
  if (!state.selectedId) return;
  await api(`/api/papers/${state.selectedId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ notes: detailNotes.value }),
  });
  notesSaved.classList.remove('hidden');
}

filterBtns.forEach(btn => {
  btn.addEventListener('click', () => {
    filterBtns.forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    state.activeFilter = btn.dataset.status;
    clearDetail();
    loadPapers();
  });
});

searchInput.addEventListener('input', () => {
  state.searchText = searchInput.value.trim();
  clearDetail();
  loadPapers();
});

searchClear.addEventListener('click', () => {
  searchInput.value = '';
  state.searchText = '';
  clearDetail();
  loadPapers();
});

openPdfBtn.addEventListener('click', async () => {
  if (!state.selectedId) return;
  openPdfBtn.textContent = 'Opening...';
  try {
    await api(`/api/papers/${state.selectedId}/view`, { method: 'POST' });
  } catch (err) {
    alert('Failed to open: ' + err.message);
  }
  openPdfBtn.textContent = 'Open PDF';
});

importAnnotsBtn.addEventListener('click', async () => {
  if (!state.selectedId) return;
  try {
    const data = await api(`/api/papers/${state.selectedId}/annotations`);
    const anns = data.annotations || [];
    const hl = data.highlighted_text || '';
    const parts = [];
    if (anns.length) {
      parts.push('## PDF Annotations\n' + anns.map(a =>
        `- [${a.type}] p.${a.page}: ${a.text}`
      ).join('\n'));
    }
    if (hl) {
      parts.push('## Highlighted Text\n' + hl);
    }
    const newNotes = detailNotes.value
      ? detailNotes.value + '\n\n' + parts.join('\n\n')
      : parts.join('\n\n');
    detailNotes.value = newNotes;
    // Trigger save.
    clearTimeout(state.notesTimer);
    await saveNotes();
  } catch (err) {
    alert('Failed to load annotations: ' + err.message);
  }
});

analyzeBtn.addEventListener('click', async () => {
  if (!state.selectedId) return;
  analyzeBtn.disabled = true;
  analyzeStatus.textContent = 'Analyzing...';
  try {
    const result = await api(`/api/papers/${state.selectedId}/analyze`, { method: 'POST' });
    if (result.success) {
      analyzeStatus.textContent = 'Done!';
      loadDetail(state.selectedId);
    } else {
      analyzeStatus.textContent = 'Error: ' + result.error;
    }
  } catch (err) {
    analyzeStatus.textContent = 'Error: ' + err.message;
  }
  analyzeBtn.disabled = false;
});

// ====================================================================
// Import
// ====================================================================
importBtn.addEventListener('click', () => folderInput.click());

folderInput.addEventListener('change', async () => {
  const files = folderInput.files;
  if (!files.length) return;

  // Get the folder path from the first file's webkitRelativePath.
  const relPath = files[0].webkitRelativePath;
  // We can't read the actual folder path from browser file input.
  // Fallback: show a prompt for the folder path.
  const folderPath = prompt(
    'Enter the full path to the folder containing the PDFs:',
    ''
  );
  if (!folderPath) { folderInput.value = ''; return; }

  importBtn.textContent = 'Importing...';
  importBtn.disabled = true;
  try {
    const result = await api('/api/import', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ folder_path: folderPath }),
    });
    alert(`Import complete!\nImported: ${result.imported}\nSkipped: ${result.skipped}\nFailed: ${result.failed}`);
    await loadPapers();
    await loadCounts();
  } catch (err) {
    alert('Import failed: ' + err.message);
  }
  importBtn.textContent = '+ Import Folder';
  importBtn.disabled = false;
  folderInput.value = '';
});

// ====================================================================
// Utility
// ====================================================================
function esc(s) {
  const div = document.createElement('div');
  div.textContent = s;
  return div.innerHTML;
}

// ====================================================================
// Init
// ====================================================================
loadPapers();
loadCounts();
