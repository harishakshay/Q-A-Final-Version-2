/* 
============================================================
script.js — Document QA Dashboard
============================================================
*/

const API_BASE = '/api';
let currentSection = 'overview';
let charts = {};

// ============================================================
// Initialization
// ============================================================

document.addEventListener('DOMContentLoaded', () => {
    initNavigation();
    updateStatus();
    loadDashboardData();
    initUploads();

    setInterval(updateStatus, 30000);
});

// ============================================================
// Status & Overview
// ============================================================

async function updateStatus() {
    try {
        const response = await fetch(`${API_BASE}/status`);
        const data = await response.json();

        const setStatus = (id, online) => {
            const el = document.getElementById(`${id}-status`);
            if (el) el.className = `status-dot ${online ? 'online' : 'offline'}`;
        };

        setStatus('chromadb', data.components.chromadb);
        setStatus('neo4j', data.components.neo4j);
        setStatus('groq', data.components.groq);

        // Update Stats in Overview
        const gNodesEl = document.getElementById('stat-graph-nodes');
        const gRelsEl = document.getElementById('stat-graph-rels');
        if (gNodesEl && data.graph_stats) gNodesEl.textContent = data.graph_stats.total_nodes || 0;
        if (gRelsEl && data.graph_stats) gRelsEl.textContent = data.graph_stats.total_relationships || 0;

        // Update Vector DB health badge
        const vdbEl = document.getElementById('stat-embeddings'); // Reuse this for total items
        if (vdbEl) vdbEl.textContent = data.stats.total_items || 0;

    } catch (e) {
        console.error('Status check failed', e);
    }
}

async function loadDashboardData() {
    try {
        // 1. Get managed files count
        const filesResp = await fetch(`${API_BASE}/data/list`);
        const files = await filesResp.json();
        const docEl = document.getElementById('stat-total-docs');
        if (docEl) docEl.textContent = files.length;

        // 2. Get semantic detail for chunks
        const semResp = await fetch(`${API_BASE}/semantic/detail`);
        const semData = await semResp.json();

        const totalItems = (semData.stats || {}).total_items || 0;
        const chunksEl = document.getElementById('stat-total-chunks');
        if (chunksEl) chunksEl.textContent = totalItems;

        const embEl = document.getElementById('stat-embeddings');
        if (embEl) embEl.textContent = totalItems;

        // 3. Load Advanced Knowledge Analytics
        loadKnowledgeAnalytics();

    } catch (e) {
        console.error('Failed to load dashboard data', e);
    }
}

async function loadKnowledgeAnalytics() {
    try {
        const response = await fetch(`${API_BASE}/knowledge/analytics`);
        const data = await response.json();

        if (data.status === 'error') throw new Error(data.message);

        // 1. Influential Nodes (Filtered)
        const influentialList = document.getElementById('influential-nodes-list');
        if (influentialList) {
            influentialList.innerHTML = data.central_entities
                .filter(e => e.name && e.name.toLowerCase() !== 'unknown')
                .map(e => `
                <div class="analytics-item">
                    <div class="entity-info">
                        <div class="entity-icon" style="background: ${e.type === 'Category' ? '#10b981' : '#6366f1'}"></div>
                        <span>${e.name}</span>
                    </div>
                    <span class="entity-count">${e.connections} rels</span>
                </div>
            `).join('') || '<p class="loading-text">No significant entities found.</p>';
        }

        // 2. Knowledge Clusters
        const clusterList = document.getElementById('knowledge-clusters-list');
        if (clusterList) {
            clusterList.innerHTML = data.knowledge_clusters.map(c => `
                <div class="analytics-item">
                    <div class="entity-info">
                        <i class="fas fa-project-diagram" style="color: #f59e0b; font-size: 10px;"></i>
                        <span>${c.name}</span>
                    </div>
                    <span class="entity-count">${c.size} nodes</span>
                </div>
            `).join('') || '<p class="loading-text">No clusters detected.</p>';
        }

        // 3. Activity Feed
        const activityFeed = document.getElementById('extraction-activity-feed');
        if (activityFeed) {
            activityFeed.innerHTML = data.recent_activity.map(a => `
                <div class="activity-item">
                    <div class="activity-icon">
                        <i class="fas ${a.label === 'Article' ? 'fa-file-alt' : 'fa-atom'}"></i>
                    </div>
                    <div class="activity-content">
                        <div class="activity-title">${a.name}</div>
                        <div class="activity-desc">New ${a.label} added to graph</div>
                    </div>
                </div>
            `).join('') || '<p class="loading-text">No recent activity.</p>';
        }

        // 4. Graph Health
        const healthContainer = document.getElementById('graph-health-metrics');
        if (healthContainer) {
            const h = data.health_metrics;
            const s = data.graph_statistics;
            healthContainer.innerHTML = `
                <div class="health-metric-box">
                    <span class="health-metric-label">Avg Relationships</span>
                    <span class="health-metric-value">${s.avg_relationships}</span>
                </div>
                <div class="health-metric-box">
                    <span class="health-metric-label">Graph Density</span>
                    <span class="health-metric-value">${h.graph_density}</span>
                </div>
                <div class="health-metric-box">
                    <span class="health-metric-label">Centralized Nodes</span>
                    <span class="health-metric-value">${h.node_rel_ratio}</span>
                </div>
            `;
        }

        // 5. Initialize System Charts
        initSystemCharts(data);

    } catch (e) {
        console.error('Failed to load knowledge analytics', e);
    }
}

async function initSystemCharts(data) {
    // Destroy old charts if they exist
    ['entityDistChart', 'clusterChart', 'compositionChart'].forEach(id => {
        const existing = Chart.getChart(id);
        if (existing) existing.destroy();
    });

    // ---- Shared Chart.js defaults for dark theme ----
    Chart.defaults.color = '#94a3b8';
    Chart.defaults.font.family = "'Inter', sans-serif";

    const typeColors = ['#6366f1', '#10b981', '#f59e0b', '#ec4899', '#3b82f6', '#8b5cf6', '#14b8a6', '#f97316'];
    const tooltipStyle = {
        backgroundColor: 'rgba(13, 14, 18, 0.95)',
        borderWidth: 1,
        padding: 12,
        titleFont: { size: 13, weight: '600' },
        bodyFont: { size: 12 },
        cornerRadius: 8
    };

    // ---- 1. Entity Distribution Donut (from graph node-type counts) ----
    try {
        const graphResp = await fetch(`${API_BASE}/status`);
        const statusData = await graphResp.json();
        const nodesByType = statusData.graph_stats?.nodes || {};

        // Filter out internal/unwanted labels, keep meaningful ones
        const skipLabels = new Set(['_unknown']);
        const typeLabels = [];
        const typeValues = [];

        Object.entries(nodesByType)
            .filter(([label]) => !skipLabels.has(label.toLowerCase()))
            .sort((a, b) => b[1] - a[1])
            .forEach(([label, count]) => {
                typeLabels.push(label);
                typeValues.push(count);
            });

        const entityCtx = document.getElementById('entityDistChart');
        if (entityCtx && typeLabels.length > 0) {
            new Chart(entityCtx, {
                type: 'doughnut',
                data: {
                    labels: typeLabels,
                    datasets: [{
                        data: typeValues,
                        backgroundColor: typeColors.slice(0, typeLabels.length),
                        borderColor: 'rgba(13, 14, 18, 0.8)',
                        borderWidth: 3,
                        hoverBorderColor: '#ffffff',
                        hoverBorderWidth: 2,
                        hoverOffset: 8
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    cutout: '62%',
                    plugins: {
                        legend: {
                            position: 'bottom',
                            labels: {
                                padding: 14,
                                usePointStyle: true,
                                pointStyle: 'circle',
                                font: { size: 11, weight: '500' }
                            }
                        },
                        tooltip: {
                            ...tooltipStyle,
                            borderColor: 'rgba(99, 102, 241, 0.3)',
                            callbacks: {
                                label: (ctx) => {
                                    const total = ctx.dataset.data.reduce((a, b) => a + b, 0);
                                    const pct = total > 0 ? ((ctx.raw / total) * 100).toFixed(1) : 0;
                                    return ` ${ctx.label}: ${ctx.raw.toLocaleString()} (${pct}%)`;
                                }
                            }
                        }
                    }
                }
            });
        }
    } catch (e) {
        console.error('Entity distribution chart error:', e);
    }

    // ---- 2. Top Entities by Connections (bar chart) ----
    const entities = (data.central_entities || [])
        .filter(e => e.name && e.name.toLowerCase() !== 'unknown')
        .slice(0, 8);
    const entLabels = entities.map(e => e.name.length > 22 ? e.name.substring(0, 20) + '…' : e.name);
    const entValues = entities.map(e => e.connections);
    const barColors = entities.map((_, i) => typeColors[i % typeColors.length]);

    const clusterCtx = document.getElementById('clusterChart');
    if (clusterCtx && entities.length > 0) {
        new Chart(clusterCtx, {
            type: 'bar',
            data: {
                labels: entLabels,
                datasets: [{
                    label: 'Connections',
                    data: entValues,
                    backgroundColor: barColors,
                    borderRadius: 6,
                    borderSkipped: false,
                    barThickness: 22,
                    maxBarThickness: 30
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                indexAxis: 'y',
                scales: {
                    x: {
                        grid: { color: 'rgba(255,255,255,0.04)', drawBorder: false },
                        ticks: { font: { size: 10 } },
                        border: { display: false }
                    },
                    y: {
                        grid: { display: false },
                        ticks: { font: { size: 11, weight: '500' } },
                        border: { display: false }
                    }
                },
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        ...tooltipStyle,
                        borderColor: 'rgba(139, 92, 246, 0.3)',
                        callbacks: {
                            label: (ctx) => ` ${ctx.raw} relationships`
                        }
                    }
                }
            }
        });
    }

    // ---- 3. System Composition Donut (docs, chunks, graph nodes, relationships) ----
    const docCount = parseInt(document.getElementById('stat-total-docs')?.textContent || '0');
    const chunkCount = parseInt(document.getElementById('stat-total-chunks')?.textContent || '0');
    const graphNodes = parseInt(document.getElementById('stat-graph-nodes')?.textContent || '0');
    const graphRels = parseInt(document.getElementById('stat-graph-rels')?.textContent || '0');

    const compCtx = document.getElementById('compositionChart');
    if (compCtx) {
        new Chart(compCtx, {
            type: 'doughnut',
            data: {
                labels: ['Documents', 'Chunks', 'Graph Nodes', 'Relationships'],
                datasets: [{
                    data: [docCount, chunkCount, graphNodes, graphRels],
                    backgroundColor: ['#3b82f6', '#10b981', '#f59e0b', '#ec4899'],
                    borderColor: 'rgba(13, 14, 18, 0.8)',
                    borderWidth: 3,
                    hoverBorderColor: '#ffffff',
                    hoverBorderWidth: 2,
                    hoverOffset: 8
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: '62%',
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: {
                            padding: 14,
                            usePointStyle: true,
                            pointStyle: 'circle',
                            font: { size: 11, weight: '500' }
                        }
                    },
                    tooltip: {
                        backgroundColor: 'rgba(13, 14, 18, 0.95)',
                        borderColor: 'rgba(236, 72, 153, 0.3)',
                        borderWidth: 1,
                        padding: 12,
                        cornerRadius: 8,
                        callbacks: {
                            label: (ctx) => ` ${ctx.label}: ${ctx.raw.toLocaleString()}`
                        }
                    }
                }
            }
        });
    }
}

// ============================================================
// Navigation
// ============================================================

const SECTION_TITLES = {
    'overview': 'System Overview',
    'content': 'Documents',
    'data-management': 'Upload Documents',
    'semantic-explorer': 'Retrieval Explorer',
    'graph-explorer': 'Knowledge Graph',
    'pipeline-status': 'AI Pipeline',
    'insights': 'Question Answering'
};

function initNavigation() {
    const navItems = document.querySelectorAll('.sidebar nav ul li');
    const sections = document.querySelectorAll('.dashboard-section');
    const title = document.getElementById('section-title');

    navItems.forEach(item => {
        item.addEventListener('click', () => {
            const sectionId = item.getAttribute('data-section');
            currentSection = sectionId;

            navItems.forEach(i => i.classList.remove('active'));
            item.classList.add('active');

            sections.forEach(s => s.classList.remove('active'));
            document.getElementById(sectionId).classList.add('active');

            title.textContent = SECTION_TITLES[sectionId] || item.textContent.trim();

            switch (sectionId) {
                case 'overview':
                    loadDashboardData();
                    break;
                case 'content':
                    loadDocuments();
                    break;
                case 'data-management':
                    loadDataList();
                    break;
                case 'semantic-explorer':
                    loadSemanticExplorer();
                    break;
                case 'graph-explorer':
                    loadGraphExplorer();
                    break;
                case 'pipeline-status':
                    updatePipelineStatus();
                    break;
                case 'insights':
                    if (!qaInitialized) initQA();
                    break;
            }
        });
    });
}

// ============================================================
// Documents Page
// ============================================================

async function loadDocuments() {
    const wrapper = document.getElementById('doc-list-wrapper');
    if (!wrapper) return;
    wrapper.innerHTML = '<p style="padding:24px;color:var(--text-secondary)">Loading documents...</p>';

    try {
        const response = await fetch(`${API_BASE}/data/list`);
        const files = await response.json();

        if (files.length === 0) {
            wrapper.innerHTML = `
                <div class="empty-state">
                    <i class="fas fa-folder-open"></i>
                    <p>No documents ingested yet. Go to <strong>Upload Documents</strong> to add files.</p>
                </div>
            `;
            return;
        }

        files.sort((a, b) => new Date(b.added_at) - new Date(a.added_at));

        wrapper.innerHTML = `
            <table class="data-table">
                <thead>
                    <tr>
                        <th>Document ID</th>
                        <th>Document Name</th>
                        <th>File Type</th>
                        <th>Date Added</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody id="documents-table-body"></tbody>
            </table>
        `;

        const tbody = document.getElementById('documents-table-body');
        files.forEach(file => {
            const tr = document.createElement('tr');
            const date = new Date(file.added_at).toLocaleDateString();
            const shortId = file.id ? file.id.slice(0, 8) + '...' : 'N/A';

            tr.innerHTML = `
                <td><code title="${file.id || ''}">${shortId}</code></td>
                <td><strong>${file.filename}</strong></td>
                <td><span class="badge badge-uploaded">${(file.type || 'file').toUpperCase()}</span></td>
                <td>${date}</td>
                <td class="actions-cell">
                    <button class="btn btn-sm btn-secondary" onclick="goToChunks('${file.id}')">
                        <i class="fas fa-puzzle-piece"></i> View Chunks
                    </button>
                    <button class="btn btn-sm btn-danger" onclick="deleteData('${file.id}')" title="Delete Document">
                        <i class="fas fa-trash"></i> Delete
                    </button>
                </td>
            `;
            tbody.appendChild(tr);
        });
    } catch (e) {
        wrapper.innerHTML = '<p style="padding:24px;color:var(--danger)">Error loading documents.</p>';
    }
}

function goToChunks(fileId) {
    document.querySelector('[data-section="semantic-explorer"]').click();
}

// ============================================================
// Upload Documents
// ============================================================

function initUploads() {
    const dataInput = document.getElementById('data-input');
    if (dataInput) {
        dataInput.onchange = (e) => handleDataUpload(e.target.files);
    }

    // Drag and drop
    const dropzone = document.getElementById('upload-dropzone');
    if (dropzone) {
        dropzone.addEventListener('dragover', (e) => {
            e.preventDefault();
            dropzone.classList.add('drag-over');
        });
        dropzone.addEventListener('dragleave', () => dropzone.classList.remove('drag-over'));
        dropzone.addEventListener('drop', (e) => {
            e.preventDefault();
            dropzone.classList.remove('drag-over');
            handleDataUpload(e.dataTransfer.files);
        });
    }
}

async function handleDataUpload(files) {
    if (!files.length) return;

    for (const file of files) {
        const formData = new FormData();
        formData.append('file', file);

        const name = file.name.toLowerCase();
        let endpoint = '/upload_document';

        showNotification(`Uploading ${file.name}...`, 'info');
        try {
            const response = await fetch(`${API_BASE}${endpoint}`, {
                method: 'POST',
                body: formData
            });
            const data = await response.json();
            if (data.status === 'success') {
                showNotification(`Uploaded: ${file.name}. Processing started!`, 'success');

                // Start polling automatically to watch the status change
                const pollInterval = setInterval(async () => {
                    const statusChanged = await loadDataList();

                    // Proactive Refresh: If status changed to 'ready', refresh the whole dashboard
                    if (statusChanged) {
                        updateStatus();
                        loadDashboardData();
                    }

                    // Stop polling if there are no files in converting, chunking, or embedding states
                    const tbody = document.getElementById('data-list-body');
                    if (tbody && !tbody.innerHTML.includes('badge-converting') &&
                        !tbody.innerHTML.includes('badge-chunking') &&
                        !tbody.innerHTML.includes('badge-embedding')) {
                        clearInterval(pollInterval);
                        // Final sync
                        updateStatus();
                        loadDashboardData();
                    }
                }, 2000);

                loadDataList();
            } else {
                showNotification(data.message || 'Upload failed', 'error');
            }
        } catch (e) {
            showNotification(`Upload failed for ${file.name}`, 'error');
        }
    }
}

async function loadDataList() {
    const tbody = document.getElementById('data-list-body');
    if (!tbody) return false;

    // Keep track if any file just turned 'ready' so we can refresh the dashboard
    let newlyReady = false;

    try {
        const response = await fetch(`${API_BASE}/data/list`);
        const files = await response.json();

        if (files.length === 0) {
            tbody.innerHTML = '<tr><td colspan="4" style="text-align:center;padding:24px;color:var(--text-secondary)">No files uploaded yet.</td></tr>';
            return false;
        }

        const oldHtml = tbody.innerHTML;
        tbody.innerHTML = '';
        files.sort((a, b) => new Date(b.added_at) - new Date(a.added_at));

        files.forEach(file => {
            const tr = document.createElement('tr');
            const status = file.status || 'uploaded';
            let badgeClass = 'badge-uploaded';
            let statusLabel = 'UPLOADED';

            if (status === 'converting') {
                badgeClass = 'badge-converting';
                statusLabel = 'CONVERTING';
            } else if (status === 'chunking') {
                badgeClass = 'badge-chunking';
                statusLabel = 'CHUNKING';
            } else if (status === 'embedding') {
                badgeClass = 'badge-embedding';
                statusLabel = 'EMBEDDING';
            } else if (status === 'ready' || status === 'processed' || status === 'fully_processed') {
                badgeClass = 'badge-ready';
                statusLabel = 'READY';
                newlyReady = true;
            } else if (status === 'failed') {
                badgeClass = 'badge-failed';
                statusLabel = 'FAILED';
            }

            const date = new Date(file.added_at).toLocaleDateString();

            tr.innerHTML = `
                <td><strong>${file.filename}</strong></td>
                <td><span class="badge badge-uploaded">${(file.type || 'file').toUpperCase()}</span></td>
                <td><span class="badge ${badgeClass}">${statusLabel}</span></td>
                <td>${date}</td>
                <td class="actions-cell">
                    <button class="btn btn-sm btn-danger" onclick="deleteData('${file.id}')" title="Delete Uploaded File">
                        <i class="fas fa-trash"></i>
                    </button>
                </td>
            `;
            tbody.appendChild(tr);
        });

        return newlyReady; // Tell the caller if we have ready files to trigger a refresh
    } catch (e) {
        tbody.innerHTML = '<tr><td colspan="4" style="text-align:center;color:var(--danger)">Failed to load files.</td></tr>';
        return false;
    }
}

async function processData(id) {
    const btn = document.getElementById(`btn-process-${id}`);
    const originalContent = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Processing...';
    showNotification('Starting RAG pipeline...', 'info');

    // Poll for status updates
    const pollInterval = setInterval(() => {
        loadDataList();
    }, 2000);

    try {
        const response = await fetch(`${API_BASE}/data/process/${id}`, { method: 'POST' });
        const data = await response.json();
        if (data.status === 'success') {
            showNotification('Document fully processed and indexed!', 'success');
            updateStatus();
            loadDashboardData();
        } else {
            showNotification(data.message || 'Processing failed', 'error');
            btn.disabled = false;
            btn.innerHTML = originalContent;
        }
    } catch (e) {
        showNotification('Pipeline execution failed', 'error');
        btn.disabled = false;
        btn.innerHTML = originalContent;
    } finally {
        clearInterval(pollInterval);
        loadDataList();
    }
}

async function deleteData(id) {
    if (!confirm('Delete this file and all its associated data?')) return;
    try {
        const response = await fetch(`${API_BASE}/data/delete/${id}`, { method: 'DELETE' });
        const data = await response.json();
        if (data.status === 'success') {
            showNotification('File deleted', 'success');
            loadDataList();
        } else {
            showNotification(data.message, 'error');
        }
    } catch (e) {
        showNotification('Deletion failed', 'error');
    }
}

// ============================================================
// Retrieval Explorer
// ============================================================

async function loadSemanticExplorer() {
    const tbody = document.getElementById('semantic-explorer-body');
    const statsSummary = document.getElementById('explorer-stats-summary');
    if (!tbody) return;

    tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;padding:24px;color:var(--text-secondary)">Loading retrieval data...</td></tr>';

    try {
        const response = await fetch(`${API_BASE}/semantic/detail`);
        const data = await response.json();

        const stats = data.stats || {};
        const sources = stats.sources || {};
        const fullyIndexed = (data.managed_files || []).filter(f => f.status === 'fully_processed' || f.status === 'processed').length;

        statsSummary.innerHTML = `
            <div class="stats-grid">
                <div class="stat-card"><h3>Total Chunks</h3><p>${stats.total_items || 0}</p></div>
                <div class="stat-card"><h3>Documents Indexed</h3><p>${fullyIndexed}</p></div>
                <div class="stat-card"><h3>Embeddings Generated</h3><p>${(data.chroma_items || []).length || stats.total_items || 0}</p></div>
            </div>
        `;

        tbody.innerHTML = '';

        // Embedded chunks
        (data.chroma_items || []).forEach(item => {
            const tr = document.createElement('tr');
            const meta = item.metadata || {};
            // Try title, source, or filename
            const docName = meta.title || meta.source || meta.filename || 'Unknown';
            // The text is returned in 'document' by the new SemanticMemory backend
            const textContent = item.document || item.document_preview || '';
            const shortPreview = textContent.length > 100 ? textContent.slice(0, 100) + '…' : textContent;
            const score = meta.health_score !== undefined ? parseFloat(meta.health_score).toFixed(3) : '—';

            tr.innerHTML = `
                <td><code title="${item.id}">${item.id ? item.id.slice(0, 10) + '…' : 'N/A'}</code></td>
                <td><strong>${docName}</strong></td>
                <td class="chunk-text-cell" title="${textContent.replace(/"/g, '&quot;')}">${shortPreview || '<em style="color:#64748b">No text</em>'}</td>
                <td><span class="badge badge-indexed">EMBEDDED</span></td>
                <td>${score}</td>
            `;
            tbody.appendChild(tr);
        });

        // Pending files (show files that haven't been chunked/embedded yet)
        (data.managed_files || []).forEach(file => {
            const isEmbedded = (data.chroma_items || []).some(item => {
                const m = item.metadata || {};
                return m.parent_post_id === file.filename || m.source === file.filename || m.source_file === file.filename;
            });

            if (!isEmbedded) {
                const status = file.status || 'pending';
                // If the file is marked as processed/ready in manifest, show it as EMBEDDED in this view
                let label = 'EMBEDDED';
                let badge = 'badge-ready';

                if (status !== 'ready' && status !== 'processed' && status !== 'fully_processed') {
                    label = status.toUpperCase();
                    badge = 'badge-processing';
                }

                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td><code>—</code></td>
                    <td><strong>${file.filename}</strong></td>
                    <td class="chunk-text-cell" style="color:var(--text-secondary)">Document fully indexed</td>
                    <td><span class="badge ${badge}">${label}</span></td>
                    <td>—</td>
                `;
                tbody.appendChild(tr);
            }
        });

        if (tbody.children.length === 0) {
            tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;padding:24px;color:var(--text-secondary)">No chunks found. Upload and process a document first.</td></tr>';
        }

    } catch (e) {
        console.error(e);
        tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;color:var(--danger);padding:24px">Failed to load retrieval data.</td></tr>';
    }
}

// ============================================================
// Question Answering (RAG)
// ============================================================

let qaInitialized = false;

function fillQuery(el) {
    const input = document.getElementById('ai-search-input');
    if (input) input.value = el.textContent;
    input.focus();
}

function initQA() {
    if (qaInitialized) return;
    qaInitialized = true;

    const input = document.getElementById('ai-search-input');
    const btn = document.getElementById('btn-ai-search');
    if (!input || !btn) return;

    input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            performQA();
        }
    });

    input.addEventListener('input', () => {
        input.style.height = 'auto';
        input.style.height = (input.scrollHeight) + 'px';
    });

    btn.onclick = performQA;
}

async function performQA() {
    const input = document.getElementById('ai-search-input');
    const question = input.value.trim();
    if (!question) return;

    const welcome = document.getElementById('chat-welcome');
    const resultsContainer = document.getElementById('chat-results');

    welcome.style.display = 'none';
    input.value = '';
    input.style.height = 'auto';

    // User bubble
    addChatMessage(question, 'user');

    // Loading bubble
    const loadingId = 'qa-loading-' + Date.now();
    addChatMessage('<i class="fas fa-spinner fa-spin"></i> Searching your documents...', 'ai', loadingId);

    const btn = document.getElementById('btn-ai-search');
    btn.disabled = true;

    try {
        const response = await fetch(`${API_BASE}/ask`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ question })
        });
        const data = await response.json();

        const loadingEl = document.getElementById(loadingId);
        if (loadingEl) {
            if (data.status === 'error') {
                loadingEl.innerHTML = `<span style="color:var(--danger)"><i class="fas fa-exclamation-circle"></i> Error: ${data.message}</span>`;
            } else if (data.no_relevant_info || !data.answer) {
                loadingEl.innerHTML = `
                    <div class="qa-no-info">
                        <i class="fas fa-search"></i>
                        <p>I could not find this in the provided documents. Can you share the relevant document?</p>
                    </div>
                `;
            } else {
                loadingEl.innerHTML = buildQAResponse(data);
            }
        }

        resultsContainer.scrollTop = resultsContainer.scrollHeight;
    } catch (e) {
        const loadingEl = document.getElementById(loadingId);
        if (loadingEl) loadingEl.innerHTML = '<span style="color:var(--danger)"><i class="fas fa-exclamation-circle"></i> Request failed. Please try again.</span>';
    } finally {
        btn.disabled = false;
    }
}

function buildQAResponse(data) {
    const confidenceColors = {
        high: { bg: 'rgba(16,185,129,0.12)', border: '#10b981', text: '#10b981', label: 'Answer Confidence: High' },
        medium: { bg: 'rgba(245,158,11,0.12)', border: '#f59e0b', text: '#f59e0b', label: 'Answer Confidence: Medium' },
        low: { bg: 'rgba(239,68,68,0.12)', border: '#ef4444', text: '#ef4444', label: 'Answer Confidence: Low' }
    };
    const conf = confidenceColors[data.confidence] || confidenceColors.low;
    const sourcesHtml = (data.sources || []).map(s => {
        const confLevel = (s.confidence || 'low').toLowerCase();
        const confClass = `conf-${confLevel}`;
        const confLabel = confLevel.charAt(0).toUpperCase() + confLevel.slice(1);

        // Determine the display label for the source
        let displayLabel = 'Unknown';
        if (s.label) {
            displayLabel = s.label;
        } else if (s.document) {
            displayLabel = s.document;
            if (s.section) {
                displayLabel += ` > ${s.section}`;
            }
        }

        return `
            <div class="source-card">
                <div class="source-card-header">
                    <i class="fas fa-file-alt" style="margin-right: 8px;"></i>
                    <strong>${displayLabel}</strong>
                    <div style="display: flex; gap: 8px;">
                        <span class="source-confidence" style="background: rgba(255,255,255,0.05); color: var(--text-secondary); border: 1px solid var(--border-color);">Similarity: ${s.score !== undefined ? s.score.toFixed(1) : 'N/A'}%</span>
                    </div>
                </div>
                ${s.snippet ? `
                <div class="source-body" style="margin-top: 10px;">
                    <div class="source-snippet-label" style="font-size: 0.7rem; text-transform: uppercase; color: var(--text-secondary); letter-spacing: 0.05em; margin-bottom: 4px;">Retrieved Text Passage</div>
                    <p class="source-snippet" style="font-size: 13px; line-height: 1.5; color: #d1d5db; font-style: normal; padding-left: 0; border-left: none;">"${s.snippet}"</p>
                </div>` : ''}
            </div>
        `;
    }).join('');

    const randomId = Math.random().toString(36).substring(7);

    return `
        <div class="qa-response">
            <!-- AI Answer Content -->
            <div class="qa-section qa-answer-section">
                <div class="qa-section-label"><i class="fas fa-comment-dots"></i> AI Response</div>
                <div class="markdown-content">${formatMarkdown(data.answer || 'No answer retrieved.')}</div>
            </div>

            <!-- Section 2: Sources -->
            ${data.sources && data.sources.length > 0 ? `
            <div class="qa-section qa-sources-section">
                <div class="qa-section-label"><i class="fas fa-book-open"></i> Sources (${data.sources.length})</div>
                <div class="sources-grid">${sourcesHtml}</div>
            </div>` : ''}

            <!-- Section 3: Confidence -->
            <div class="qa-confidence-badge" style="background:${conf.bg};border:1px solid ${conf.border};color:${conf.text}">
                <i class="fas fa-chart-bar"></i> ${conf.label}
            </div>
        </div>
    `;
}



function addChatMessage(content, type, id = null) {
    const container = document.getElementById('chat-results');
    const msg = document.createElement('div');
    msg.className = `chat-message message-${type}`;
    if (id) msg.id = id;
    if (type === 'user') {
        msg.textContent = content;
    } else {
        msg.innerHTML = content;
    }
    container.appendChild(msg);
    container.scrollTop = container.scrollHeight;
}

function formatMarkdown(text) {
    if (!text) return '';
    return text
        .replace(/^### (.*$)/gim, '<h3>$1</h3>')
        .replace(/^## (.*$)/gim, '<h2>$1</h2>')
        .replace(/^# (.*$)/gim, '<h1>$1</h1>')
        .replace(/^\* (.*$)/gim, '<li>$1</li>')
        .replace(/^\- (.*$)/gim, '<li>$1</li>')
        .replace(/\*\*(.*)\*\*/gim, '<strong>$1</strong>')
        .replace(/\*(.*)\*/gim, '<em>$1</em>')
        .replace(/\n/g, '<br>');
}

// ============================================================
// UI Utilities
// ============================================================

function showNotification(message, type = 'info') {
    const container = document.getElementById('notification-container');
    const n = document.createElement('div');
    n.className = 'notification';

    const icons = { info: 'fa-info-circle', success: 'fa-check-circle', error: 'fa-exclamation-circle' };
    const colors = { info: '#6366f1', success: '#10b981', error: '#ef4444' };

    n.style.borderLeftColor = colors[type];
    n.innerHTML = `<i class="fas ${icons[type]}" style="color:${colors[type]}"></i> ${message}`;

    container.appendChild(n);
    setTimeout(() => { n.style.opacity = '0'; setTimeout(() => n.remove(), 300); }, 4000);
}
// ============================================================
// Knowledge Graph Explorer
// ============================================================

async function loadGraphExplorer() {
    const tbody = document.getElementById('graph-entities-body');
    if (!tbody) return;

    tbody.innerHTML = '<tr><td colspan="4" style="text-align:center;padding:24px;">Loading graph statistics...</td></tr>';

    try {
        const response = await fetch(`${API_BASE}/graph/details`);
        const data = await response.json();

        // Update stats
        const nodes = data.stats.nodes || {};
        document.getElementById('graph-stat-concepts').textContent = nodes['Concept'] || 0;
        document.getElementById('graph-stat-persons').textContent = nodes['Person'] || 0;
        document.getElementById('graph-stat-tools').textContent = nodes['Tool'] || 0;
        document.getElementById('graph-stat-total-rels').textContent = data.stats.total_relationships || 0;

        // Update entities table
        tbody.innerHTML = '';
        if (data.entities && data.entities.length > 0) {
            data.entities.forEach(ent => {
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td><strong>${ent.name}</strong></td>
                    <td><span class="badge badge-uploaded">${ent.type}</span></td>
                    <td>${ent.connections} connections</td>
                    <td>
                        <button class="btn btn-sm btn-secondary" onclick="fillQueryAndGo('${ent.name}')">
                            <i class="fas fa-search"></i> Ask About
                        </button>
                    </td>
                `;
                tbody.appendChild(tr);
            });
        } else {
            tbody.innerHTML = '<tr><td colspan="4" style="text-align:center;padding:24px;">No entities found in the graph.</td></tr>';
        }

    } catch (e) {
        console.error('Failed to load graph explorer', e);
        tbody.innerHTML = '<tr><td colspan="4" style="text-align:center;color:var(--danger);">Error loading graph data.</td></tr>';
    }
}

function fillQueryAndGo(query) {
    document.querySelector('[data-section="insights"]').click();
    setTimeout(() => {
        const input = document.getElementById('ai-search-input');
        if (input) {
            input.value = `Tell me about ${query}`;
            input.focus();
        }
    }, 100);
}

// ============================================================
// AI Pipeline Status
// ============================================================

async function updatePipelineStatus() {
    try {
        const response = await fetch(`${API_BASE}/data/list`);
        const files = await response.json();

        const total = files.length;
        const processed = files.filter(f => f.status === 'processed' || f.status === 'fully_processed' || f.status === 'ready').length;

        document.getElementById('pipe-total-docs').textContent = total;

        // Calculate average chunks
        const semResp = await fetch(`${API_BASE}/semantic/detail`);
        const semData = await semResp.json();
        const totalChunks = (semData.stats || {}).total_items || 0;

        document.getElementById('pipe-avg-chunks').textContent = total > 0 ? (totalChunks / total).toFixed(1) : 0;

        // Update visual steps based on aggregate status
        updateStep('step-ingest', total > 0);
        updateStep('step-chunk', totalChunks > 0);
        updateStep('step-embed', totalChunks > 0);
        updateStep('step-graph', processed > 0);

    } catch (e) {
        console.error('Failed to update pipeline status', e);
    }
}

function updateStep(id, active) {
    const el = document.getElementById(id);
    if (!el) return;
    if (active) {
        el.classList.add('success');
        el.querySelector('.step-status').textContent = 'Active / Verified';
    } else {
        el.classList.remove('success');
        el.querySelector('.step-status').textContent = 'Pending';
    }
}
