// Global state
let shelfData = [];
let progressData = {};
let player;
let currentActiveItem = null;
let activeTaskId = null;
let agentPollInterval = null;

// DOM Elements
const shelfGrid = document.getElementById('shelfGrid');
const searchInput = document.getElementById('searchInput');
const typeFilter = document.getElementById('typeFilter');
const statusFilter = document.getElementById('statusFilter');
const genreFilter = document.getElementById('genreFilter');

const ytModal = document.getElementById('ytModal');
const closeYtModal = document.getElementById('closeYtModal');
const modalTitle = document.getElementById('modalTitle');
const modalCreator = document.getElementById('modalCreator');
const openOriginalBtn = document.getElementById('openOriginalBtn');

// Notes Panel Elements
const newNoteInput = document.getElementById('newNoteInput');
const addNoteBtn = document.getElementById('addNoteBtn');
const notesList = document.getElementById('notesList');
const generateSummaryBtn = document.getElementById('generateSummaryBtn');
const aiSummaryOutput = document.getElementById('aiSummaryOutput');
const aiSummaryContent = document.getElementById('aiSummaryContent');

// Agent Panel Elements
const agentStatusPill = document.getElementById('agentStatusPill');
const activeTaskUrl = document.getElementById('activeTaskUrl');
const activeTaskGoalBadge = document.getElementById('activeTaskGoalBadge');
const activeTaskGoalText = document.getElementById('activeTaskGoalText');
const sourceCandidateCard = document.getElementById('sourceCandidateCard');
const sourceTitle = document.getElementById('sourceTitle');
const sourceChannel = document.getElementById('sourceChannel');
const sourceConfidence = document.getElementById('sourceConfidence');
const confidenceFill = document.getElementById('confidenceFill');
const sourceReasoning = document.getElementById('sourceReasoning');
const decisionList = document.getElementById('decisionList');

// Hero Summary Elements
const whileAwayText = document.getElementById('whileAwayText');
const distanceToGoalText = document.getElementById('distanceToGoalText');
const knowledgeDebtIndexText = document.getElementById('knowledgeDebtIndexText');

// Modals & Buttons
const submitModal = document.getElementById('submitModal');
const openSubmitModalBtn = document.getElementById('openSubmitModalBtn');
const closeSubmitModal = document.getElementById('closeSubmitModal');
const agentSubmitForm = document.getElementById('agentSubmitForm');
const taskUrlInput = document.getElementById('taskUrlInput');
const taskGoalInput = document.getElementById('taskGoalInput');

const missionsModal = document.getElementById('missionsModal');
const openMissionsBtn = document.getElementById('openMissionsBtn');
const closeMissionsModal = document.getElementById('closeMissionsModal');
const newMissionInput = document.getElementById('newMissionInput');
const createMissionBtn = document.getElementById('createMissionBtn');

// Navigation Tabs Handlers
const navTabs = [
    { btnId: 'tabMission', viewId: 'viewMission' },
    { btnId: 'tabDecisions', viewId: 'viewDecisions' },
    { btnId: 'tabEvidence', viewId: 'viewEvidence' },
    { btnId: 'tabShelf', viewId: 'viewShelf' },
    { btnId: 'tabMemory', viewId: 'viewMemory' }
];

navTabs.forEach(t => {
    const btnEl = document.getElementById(t.btnId);
    const viewEl = document.getElementById(t.viewId);
    if (btnEl && viewEl) {
        btnEl.addEventListener('click', () => {
            navTabs.forEach(x => {
                const b = document.getElementById(x.btnId);
                const v = document.getElementById(x.viewId);
                if (b) b.classList.remove('active');
                if (v) {
                    v.classList.remove('active-view');
                    v.classList.add('hidden');
                }
            });
            btnEl.classList.add('active');
            viewEl.classList.remove('hidden');
            viewEl.classList.add('active-view');
            if (t.btnId === 'tabMission') {
                setTimeout(() => {
                    if (typeof resizeGraphCanvas === 'function') resizeGraphCanvas();
                }, 50);
            }
        });
    }
});
const missionsList = document.getElementById('missionsList');

const openDemoBtn = document.getElementById('openDemoBtn');

// YouTube IFrame API Ready Callback
function onYouTubeIframeAPIReady() {
    console.log("YouTube API Ready");
}

// Fetch initial data
async function loadData() {
    try {
        const res = await fetch('/api/shelf');
        const json = await res.json();
        if (json.status === 'success') {
            shelfData = json.data;
            progressData = json.progress;
            renderGrid();
        }
    } catch (e) {
        shelfGrid.innerHTML = '<div class="loading-spinner"><i class="fas fa-exclamation-triangle"></i> Failed to load shelf data.</div>';
        console.error(e);
    }
}

function getThumbnailUrl(item) {
    if (item.thumbnail_url && item.thumbnail_url.trim().length > 0 && !item.thumbnail_url.includes('example.com')) {
        return item.thumbnail_url;
    }
    const url = item.url || item.instagram_url || '';
    if (url.includes('youtube.com') || url.includes('youtu.be')) {
        const vid = getYouTubeId(url);
        if (vid) return `https://img.youtube.com/vi/${vid}/hqdefault.jpg`;
    }
    const t = ((item.title || '') + ' ' + (item.tags || '') + ' ' + (item.creator || '')).toLowerCase();
    if (t.includes('mindset') || t.includes('strength') || t.includes('goggins') || t.includes('robbins') || t.includes('seduce') || t.includes('peterson')) {
        return 'https://images.unsplash.com/photo-1517838277536-f5f99be501cd?w=800&q=80';
    }
    if (t.includes('philosophy') || t.includes('read') || t.includes('book') || t.includes('intellectual') || t.includes('gandhi') || t.includes('youth')) {
        return 'https://images.unsplash.com/photo-1457369804613-52c61a468e7d?w=800&q=80';
    }
    if (t.includes('worldbuilding') || t.includes('anime') || t.includes('ghibli') || t.includes('story')) {
        return 'https://images.unsplash.com/photo-1578632767115-351597cf2477?w=800&q=80';
    }
    if (t.includes('finance') || t.includes('money') || t.includes('netflix') || t.includes('market') || t.includes('rockefeller')) {
        return 'https://images.unsplash.com/photo-1611974789855-9c2a0a7236a3?w=800&q=80';
    }
    return 'https://images.unsplash.com/photo-1516321318423-f06f85e504b3?w=800&q=80';
}

function renderGrid() {
    const searchTerm = searchInput.value.toLowerCase();
    const typeVal = typeFilter.value;
    const statusVal = statusFilter.value;

    shelfGrid.innerHTML = '';
    
    // Sort by saved_at descending (newest items first)
    const sortedData = [...shelfData].sort((a, b) => {
        const timeA = new Date(a.saved_at || 0).getTime();
        const timeB = new Date(b.saved_at || 0).getTime();
        return timeB - timeA;
    });

    const filtered = sortedData.filter(item => {
        const textMatch = !searchTerm || 
            (item.title && item.title.toLowerCase().includes(searchTerm)) ||
            (item.creator && item.creator.toLowerCase().includes(searchTerm)) ||
            (item.ai_summary && item.ai_summary.toLowerCase().includes(searchTerm));
        
        const typeMatch = typeVal === 'ALL' || item.content_type === typeVal;

        const prog = progressData[item.content_hash] || { is_completed: false };
        const isCompleted = prog.is_completed;
        let statusMatch = true;
        if (statusVal === 'UNREAD' && isCompleted) statusMatch = false;
        if (statusVal === 'COMPLETED' && !isCompleted) statusMatch = false;

        let genreMatch = true;
        if (genreFilter.value !== 'ALL') {
            const g = genreFilter.value;
            const t = item.tags ? String(item.tags).toLowerCase() : '';
            const s = item.ai_summary ? String(item.ai_summary).toLowerCase() : '';
            genreMatch = t.includes(g) || s.includes(g);
        }

        return textMatch && typeMatch && statusMatch && genreMatch;
    });

    if (filtered.length === 0) {
        shelfGrid.innerHTML = '<div class="loading-spinner">No items found matching your filters.</div>';
        return;
    }

    filtered.forEach((item, idx) => {
        const prog = progressData[item.content_hash] || { progress_seconds: 0, is_completed: false };
        
        const card = document.createElement('div');
        card.className = 'card';
        if (idx === 0) card.classList.add('newly-curated-card');
        
        const thumbUrl = getThumbnailUrl(item);
        const isFinished = prog.is_completed;
        const isAgentCurated = item.gemini_notes && item.gemini_notes.includes('Processed by InstaShelf Agent');

        card.innerHTML = `
            <div class="card-media">
                <img src="${thumbUrl}" alt="Thumbnail" onerror="this.src='https://images.unsplash.com/photo-1516321318423-f06f85e504b3?w=800&q=80'">
                <span class="badge-tag">${isAgentCurated ? '✨ AGENT CURATED' : (item.content_type || 'RESOURCE')}</span>
            </div>
            <div class="card-content">
                <h3 class="card-title">${item.title || 'Untitled Item'}</h3>
                <p class="card-creator">${item.creator || 'Unknown Source'}</p>
                <p class="card-summary">${item.ai_summary || item.raw_context || 'Curated item on shelf.'}</p>
            </div>
        `;

        card.addEventListener('click', () => openItemModal(item));
        shelfGrid.appendChild(card);
    });
}

function openItemModal(item) {
    currentActiveItem = item;
    modalTitle.textContent = item.title || 'Resource Details';
    modalCreator.textContent = item.creator || 'Creator/Author';
    openOriginalBtn.href = item.url || '#';

    const ytContainer = document.getElementById('playerContainer');
    if (item.url && (item.url.includes('youtube.com') || item.url.includes('youtu.be'))) {
        ytContainer.style.display = 'block';
        let vId = getYouTubeId(item.url);
        if (vId) {
            if (player) player.destroy();
            player = new YT.Player('ytPlayer', {
                height: '100%',
                width: '100%',
                videoId: vId,
                events: { 'onReady': onPlayerReady }
            });
        }
    } else {
        ytContainer.style.display = 'none';
    }

    loadNotes(item.content_hash);
    ytModal.classList.remove('hidden');
}

function getYouTubeId(url) {
    const regExp = /^.*(youtu.be\/|v\/|u\/\w\/|embed\/|watch\?v=|\&v=)([^#\&\?]*).*/;
    const match = url.match(regExp);
    return (match && match[2].length === 11) ? match[2] : null;
}

function onPlayerReady(event) {
    console.log("Player ready");
}

// Notes functions
async function loadNotes(contentHash) {
    notesList.innerHTML = '<div class="note-item">Loading notes...</div>';
    try {
        const res = await fetch(`/api/notes/${contentHash}`);
        const data = await res.json();
        if (data.status === 'success') {
            renderNotes(data.notes);
        }
    } catch (e) {
        notesList.innerHTML = '<div class="note-item">No notes taken yet.</div>';
    }
}

function renderNotes(notes) {
    notesList.innerHTML = '';
    if (!notes || notes.length === 0) {
        notesList.innerHTML = '<div class="note-item" style="color: var(--text-muted);">No notes yet. Add one above!</div>';
        return;
    }
    notes.forEach(n => {
        const div = document.createElement('div');
        div.className = 'note-item';
        const mins = Math.floor(n.timestamp_seconds / 60);
        const secs = n.timestamp_seconds % 60;
        const timeStr = `${mins}:${secs < 10 ? '0' : ''}${secs}`;
        div.innerHTML = `<span class="note-time">[${timeStr}]</span> ${n.note_text}`;
        notesList.appendChild(div);
    });
}

addNoteBtn.addEventListener('click', async () => {
    if (!currentActiveItem || !newNoteInput.value.trim()) return;
    let timeSecs = 0;
    if (player && typeof player.getCurrentTime === 'function') {
        timeSecs = Math.floor(player.getCurrentTime());
    }
    try {
        const res = await fetch('/api/notes', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                content_hash: currentActiveItem.content_hash,
                timestamp_seconds: timeSecs,
                note_text: newNoteInput.value.trim()
            })
        });
        const data = await res.json();
        if (data.status === 'success') {
            newNoteInput.value = '';
            loadNotes(currentActiveItem.content_hash);
        }
    } catch (e) {
        console.error(e);
    }
});

generateSummaryBtn.addEventListener('click', async () => {
    if (!currentActiveItem) return;
    aiSummaryOutput.classList.remove('hidden');
    aiSummaryContent.innerHTML = '<em>Generating AI Master Note...</em>';
    try {
        const res = await fetch(`/api/notes/${currentActiveItem.content_hash}/generate`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ title: currentActiveItem.title })
        });
        const data = await res.json();
        if (data.status === 'success') {
            aiSummaryContent.innerHTML = marked.parse(data.summary);
        } else {
            aiSummaryContent.innerHTML = 'Failed to generate Master Note.';
        }
    } catch (e) {
        aiSummaryContent.innerHTML = 'Error generating Master Note.';
    }
});

// Modal Close Listeners
closeYtModal.addEventListener('click', () => {
    ytModal.classList.add('hidden');
    if (player && typeof player.stopVideo === 'function') player.stopVideo();
});

// ---------------------------------------------------------------------------
// Real-Time Agent Activity & Task Streaming
// ---------------------------------------------------------------------------

async function checkRecentAgentTask() {
    try {
        const res = await fetch('/api/agent/tasks?limit=1');
        const data = await res.json();
        if (data.status === 'success' && data.tasks && data.tasks.length > 0) {
            const latestTask = data.tasks[0];
            activeTaskId = latestTask.task_id;
            updateAgentActivityUI(latestTask);
            if (latestTask.state !== 'COMPLETED' && latestTask.state !== 'FAILED') {
                startPollingAgentTask(latestTask.task_id);
            }
        }
    } catch (e) {
        console.error("Failed to fetch agent task state:", e);
    }
}

function startPollingAgentTask(taskId) {
    if (agentPollInterval) clearInterval(agentPollInterval);
    agentPollInterval = setInterval(async () => {
        try {
            const res = await fetch(`/api/agent/tasks/${taskId}`);
            const data = await res.json();
            if (data.status === 'success' && data.task) {
                updateAgentActivityUI(data.task);
                if (data.task.state === 'COMPLETED' || data.task.state === 'FAILED') {
                    clearInterval(agentPollInterval);
                    loadData();
                }
            }
        } catch (e) {
            console.error("Poll task error:", e);
        }
    }, 2000);
}

function updateAgentActivityUI(task) {
    // 1. Status Pill
    if (agentStatusPill) {
        agentStatusPill.className = `status-pill status-${task.state.toLowerCase()}`;
        agentStatusPill.textContent = task.state;
    }

    // 2. Task Details
    if (activeTaskUrl) activeTaskUrl.textContent = task.content_url || 'No active URL';
    if (activeTaskGoalBadge && activeTaskGoalText) {
        if (task.learning_goal) {
            activeTaskGoalBadge.classList.remove('hidden');
            activeTaskGoalText.textContent = task.learning_goal;
        } else {
            activeTaskGoalBadge.classList.add('hidden');
        }
    }


    // 3. Step Progress Timeline
    const steps = ['Content Extraction', 'Research & Match Scoring', 'Knowledge Mapping', 'Study Material Generation', 'Storage & Sheets Sync'];
    const stepIds = ['step1', 'step2', 'step3', 'step4', 'step5'];

    stepIds.forEach((id, idx) => {
        const el = document.getElementById(id);
        if (!el) return;

        const isCompleted = task.completed_steps.some(s => s.toLowerCase().includes(steps[idx].toLowerCase().split(' ')[0]));
        const isCurrent = task.current_step && task.current_step.toLowerCase().includes(steps[idx].toLowerCase().split(' ')[0]);

        el.className = 'timeline-step';
        if (isCompleted) el.classList.add('completed');
        if (isCurrent && task.state !== 'COMPLETED') el.classList.add('active');
    });

    // 4. Source Candidate Preview
    if (task.selected_source) {
        sourceCandidateCard.classList.remove('hidden');
        sourceTitle.textContent = task.selected_source.title || 'Discovered Source';
        sourceChannel.textContent = `Channel: ${task.selected_source.channel || 'YouTube'}`;
        const pct = Math.round((task.selected_source.confidence || 0.85) * 100);
        sourceConfidence.textContent = `${pct}%`;
        confidenceFill.style.width = `${pct}%`;
        sourceReasoning.textContent = task.selected_source.reasoning || 'Source Match Score verified.';
    } else {
        sourceCandidateCard.classList.add('hidden');
    }

    // 5. Decision Audit Log
    if (task.decisions && task.decisions.length > 0) {
        decisionList.innerHTML = '';
        task.decisions.forEach(d => {
            const item = document.createElement('div');
            item.className = 'decision-item';
            const timeStr = d.timestamp ? d.timestamp.split('T')[1].slice(0, 8) : '';
            item.innerHTML = `
                <span class="decision-time">${timeStr}</span>
                <span class="decision-agent">[${d.agent}]</span> 
                <span class="decision-action">${d.action}</span>
                <p style="color: var(--text-muted); font-size: 0.75rem; margin-top: 2px;">${d.reasoning}</p>
            `;
            decisionList.appendChild(item);
        });
    }

    // 6. Direct Access Button on Task Completion
    const viewBtn = document.getElementById('viewCompletedCardBtn');
    if (viewBtn) {
        if (task.state === 'COMPLETED') {
            viewBtn.classList.remove('hidden');
            viewBtn.onclick = () => {
                const itemToOpen = shelfData.find(i => i.content_hash === task.saved_shelf_hash) || {
                    title: task.selected_source ? task.selected_source.title : (task.learning_goal || 'Curated Resource'),
                    creator: task.selected_source ? task.selected_source.channel : 'InstaShelf Agent',
                    url: task.selected_source ? task.selected_source.url : task.content_url,
                    ai_summary: task.master_note ? task.master_note.summary : 'Master Study Guide synthesized by InstaShelf Agent.',
                    content_hash: task.saved_shelf_hash || 'agent_item'
                };
                openItemModal(itemToOpen);
            };
        } else {
            viewBtn.classList.add('hidden');
        }
    }
}

// ---------------------------------------------------------------------------
// Modals & Demo Mode Handlers
// ---------------------------------------------------------------------------

if (openSubmitModalBtn) openSubmitModalBtn.addEventListener('click', () => submitModal && submitModal.classList.remove('hidden'));
if (closeSubmitModal) closeSubmitModal.addEventListener('click', () => submitModal && submitModal.classList.add('hidden'));

if (agentSubmitForm) {
    agentSubmitForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const url = taskUrlInput ? taskUrlInput.value.trim() : '';
        const goal = taskGoalInput ? taskGoalInput.value : '';

        if (!url) return;
        if (submitModal) submitModal.classList.add('hidden');

        try {
            const res = await fetch('/api/agent/process', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ url: url, learning_goal: goal })
            });
            const data = await res.json();
            if (data.status === 'success') {
                activeTaskId = data.task_id;
                if (taskUrlInput) taskUrlInput.value = '';
                startPollingAgentTask(data.task_id);
            }
        } catch (err) {
            console.error("Failed to deploy agent task:", err);
        }
    });
}

if (openMissionsBtn) {
    openMissionsBtn.addEventListener('click', () => {
        loadMissions();
        if (missionsModal) missionsModal.classList.remove('hidden');
    });
}

if (closeMissionsModal) {
    closeMissionsModal.addEventListener('click', () => {
        if (missionsModal) missionsModal.classList.add('hidden');
    });
}

async function loadMissions() {
    if (!missionsList) return;
    missionsList.innerHTML = '<div class="loading-spinner"><i class="fas fa-circle-notch fa-spin"></i> Loading missions...</div>';
    try {
        const res = await fetch('/api/agent/missions');
        const data = await res.json();
        if (data.status === 'success') {
            renderMissions(data.missions);
        }
    } catch (e) {
        missionsList.innerHTML = '<div class="empty-feed">Failed to load missions.</div>';
    }
}

function renderMissions(missions) {
    if (!missionsList) return;
    missionsList.innerHTML = '';
    if (!missions || missions.length === 0) {
        missionsList.innerHTML = '<div class="empty-feed">No active Learning Missions. Create one above!</div>';
        return;
    }
    missions.forEach(m => {
        const card = document.createElement('div');
        card.className = 'mission-card';
        card.innerHTML = `
            <div class="mission-title">🎯 ${m.topic}</div>
            <div class="mission-progress-bar">
                <div class="mission-progress-fill" style="width: ${m.progress_percentage}%"></div>
            </div>
            <div class="mission-steps">
                <strong>Completed:</strong> ${m.completed_concepts.join(', ') || 'None'}<br>
                <strong>Next:</strong> ${m.pending_concepts.join(', ') || 'Finished'}
            </div>
        `;
        missionsList.appendChild(card);
    });
}

if (createMissionBtn) {
    createMissionBtn.addEventListener('click', async () => {
        const topic = newMissionInput ? newMissionInput.value.trim() : '';
        if (!topic) return;
        try {
            const res = await fetch('/api/agent/missions', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ topic: topic })
            });
            const data = await res.json();
            if (data.status === 'success') {
                if (newMissionInput) newMissionInput.value = '';
                loadMissions();
            }
        } catch (e) {
            console.error(e);
        }
    });
}

// Judge Demo Mode (/demo)
if (openDemoBtn) {
    openDemoBtn.addEventListener('click', async () => {
        try {
            const res = await fetch('/api/agent/demo/hero');
            const data = await res.json();
            if (data.status === 'success') {
                alert(`🏆 InstaShelf Agent Judge Demo Mode:\n\nScenario: ${data.demo_scenario}\nDistance to Goal: ${data.distance_to_goal_before} ➔ ${data.distance_to_goal_after}\nGoal Achievement: ${data.goal_achievement_pct}\nKnowledge Debt Index: ${data.knowledge_debt_index}\nAttention Saved: ${data.attention_saved}\nHuman Effort Reduced: ${data.human_effort_reduced}`);
            }
        } catch (e) {
            console.error("Demo endpoint error:", e);
        }
    });
}

// Controls Event Listeners
if (searchInput) searchInput.addEventListener('input', renderGrid);
if (typeFilter) typeFilter.addEventListener('change', renderGrid);
if (statusFilter) statusFilter.addEventListener('change', renderGrid);
if (genreFilter) genreFilter.addEventListener('change', renderGrid);

// ---------------------------------------------------------------------------
// Autonomous Knowledge Cartographer & Interactive 2D Force Graph Engine
// ---------------------------------------------------------------------------

let graphNodes = [];
let graphEdges = [];
let animFrameId = null;
let graphCanvas = null;
let graphCtx = null;

let zoomLevel = 1.0;
let panOffset = { x: 0, y: 0 };
let isDraggingGraph = false;
let dragStartMouse = { x: 0, y: 0 };
let draggedNode = null;
let hoveredNode = null;
let rawGraphData = null;

// DOM View Toggle Elements
const btnGraphView = document.getElementById('btnGraphView');
const btnGridView = document.getElementById('btnGridView');
const graphViewContainer = document.getElementById('graphViewContainer');
const gridViewContainer = document.getElementById('gridViewContainer');
const graphSearchInput = document.getElementById('graphSearchInput');

if (btnGraphView && btnGridView) {
    btnGraphView.addEventListener('click', () => {
        btnGraphView.classList.add('active');
        btnGridView.classList.remove('active');
        if (graphViewContainer) graphViewContainer.classList.remove('hidden');
        if (gridViewContainer) gridViewContainer.classList.add('hidden');
    });

    btnGridView.addEventListener('click', () => {
        btnGridView.classList.add('active');
        btnGraphView.classList.remove('active');
        if (gridViewContainer) gridViewContainer.classList.remove('hidden');
        if (graphViewContainer) graphViewContainer.classList.add('hidden');
    });
}

// Zoom & Graph Controls
const btnZoomIn = document.getElementById('btnZoomIn');
const btnZoomOut = document.getElementById('btnZoomOut');
const btnResetGraph = document.getElementById('btnResetGraph');

if (btnZoomIn) btnZoomIn.addEventListener('click', () => { zoomLevel = Math.min(zoomLevel * 1.25, 3.0); });
if (btnZoomOut) btnZoomOut.addEventListener('click', () => { zoomLevel = Math.max(zoomLevel / 1.25, 0.4); });
if (btnResetGraph) btnResetGraph.addEventListener('click', () => { zoomLevel = 1.0; panOffset = { x: 0, y: 0 }; graphAlpha = 0.8; });

async function loadCartographerMap() {
    try {
        const res = await fetch('/api/cartographer/map');
        const data = await res.json();
        console.log("Cartographer Map Data:", data);
        rawGraphData = data;

        const activeClustersCount = document.getElementById('activeClustersCount');
        const totalEntitiesCount = document.getElementById('totalEntitiesCount');
        const totalEdgesCount = document.getElementById('totalEdgesCount');

        if (data.clusters) {
            if (activeClustersCount) activeClustersCount.textContent = data.clusters.length;
            let totalItems = data.clusters.reduce((acc, c) => acc + (c.item_count || c.media_items?.length || 0), 0);
            if (totalEntitiesCount) totalEntitiesCount.textContent = totalItems;
            renderClusterCardsGrid(data.clusters);
            if (data.clusters.length > 0) {
                renderClusterMediaWorkspace(data.clusters[0]);
            }
        }

        if (data.edges && totalEdgesCount) {
            totalEdgesCount.textContent = data.edges.length;
        }

        // Initialize 2D Interactive Force-Directed Canvas Graph
        if (data.nodes && data.nodes.length > 0) {
            initKnowledgeGraphEngine(data.nodes, data.edges || []);
        }

        // Render Evolution Timeline
        if (data.history) {
            renderEvolutionTimeline(data.history);
        }

    } catch (e) {
        console.error("Failed to load Cartographer Map:", e);
    }
}

function renderClusterCardsGrid(clusters) {
    const clusterContainer = document.getElementById('gridViewContainer');
    if (!clusterContainer) return;
    clusterContainer.innerHTML = '';

    const colors = ['#a855f7', '#ec4899', '#3b82f6', '#10b981', '#f59e0b'];
    clusters.forEach((c, idx) => {
        const color = colors[idx % colors.length];
        const card = document.createElement('div');
        card.className = 'cluster-card glass-panel-inner';
        card.style.cssText = `border-left: 5px solid ${color};`;
        card.innerHTML = `
            <div style="display: flex; justify-content: space-between; align-items: flex-start;">
                <h4 style="font-size: 1.1rem; color: #fff; font-weight: 700;">${c.name}</h4>
                <span class="badge-tag" style="background: rgba(124, 58, 237, 0.2); color: #c4b5fd;">${c.item_count || 0} Items</span>
            </div>
            <p style="font-size: 0.85rem; color: var(--text-muted); margin-top: 8px; line-height: 1.4;">${c.description || 'Curated knowledge domain.'}</p>
            <div style="margin-top: 14px; display: flex; justify-content: space-between; align-items: center;">
                <span style="font-size: 0.8rem; color: ${color}; font-weight: 600;"><i class="fas fa-circle-nodes"></i> ${(c.entities || []).length} Concepts</span>
                <button class="btn btn-outline" style="padding: 4px 12px; font-size: 0.8rem;"><i class="fas fa-play"></i> Open Learning Path</button>
            </div>
        `;

        card.addEventListener('click', () => renderClusterMediaWorkspace(c));
        clusterContainer.appendChild(card);
    });
}

function renderClusterMediaWorkspace(cluster) {
    const selectedTitle = document.getElementById('selectedClusterTitle');
    const selectedSub = document.getElementById('selectedClusterSub');
    const mediaList = document.getElementById('clusterMediaList');

    if (selectedTitle) selectedTitle.textContent = cluster.name;
    if (selectedSub) selectedSub.textContent = `${cluster.item_count || (cluster.media_items ? cluster.media_items.length : 0)} items in learning path • Watch/read in sequential order`;

    if (!mediaList) return;
    mediaList.innerHTML = '';

    const items = cluster.media_items || [];
    if (items.length === 0) {
        mediaList.innerHTML = `<p style="color: var(--text-muted); text-align: center; padding: 20px;">No media items found in this cluster.</p>`;
        return;
    }

    items.forEach((item, idx) => {
        const rowCard = document.createElement('div');
        rowCard.className = 'cluster-media-row';
        const thumbUrl = item.thumbnail_url || getThumbnailUrl(item);

        rowCard.innerHTML = `
            <div style="font-weight: 800; color: var(--accent-emerald); font-size: 1rem; min-width: 75px; text-transform: uppercase;">
                STEP 0${item.step || (idx + 1)}
            </div>
            <img src="${thumbUrl}" alt="Thumbnail" style="width: 110px; height: 65px; object-fit: cover; border-radius: 8px; border: 1px solid var(--border-color);" onerror="this.src='https://images.unsplash.com/photo-1516321318423-f06f85e504b3?w=800&q=80'">
            <div style="flex: 1;">
                <div style="display: flex; gap: 8px; align-items: center; margin-bottom: 4px;">
                    <span class="badge-tag badge-purple">${item.content_type || 'RESOURCE'}</span>
                    <span style="font-size: 0.8rem; color: var(--text-muted);">${item.creator || 'Curated Content'}</span>
                </div>
                <h4 style="font-size: 0.98rem; color: #fff; font-weight: 600;">${item.title}</h4>
                <p style="font-size: 0.82rem; color: var(--text-subtle); margin-top: 3px; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;">${item.ai_summary || 'Analyzed content item.'}</p>
            </div>
            <div>
                <a href="${item.url || '#'}" target="_blank" class="btn btn-primary" style="padding: 8px 14px; font-size: 0.82rem;">
                    <i class="fas fa-play"></i> Watch / Read
                </a>
            </div>
        `;
        mediaList.appendChild(rowCard);
    });
}

// ---------------------------------------------------------------------------
// 2D CANVAS FORCE-DIRECTED GRAPH PHYSICS ENGINE
// ---------------------------------------------------------------------------

function resizeGraphCanvas() {
    const viewport = document.getElementById('canvasViewport');
    graphCanvas = document.getElementById('knowledgeGraphCanvas');
    if (!graphCanvas || !viewport) return;
    const w = viewport.clientWidth || 1000;
    const h = viewport.clientHeight || 520;
    if (w > 0 && h > 0) {
        if (graphCanvas.width !== w * window.devicePixelRatio || graphCanvas.height !== h * window.devicePixelRatio) {
            graphCanvas.width = w * window.devicePixelRatio;
            graphCanvas.height = h * window.devicePixelRatio;
            graphCtx = graphCanvas.getContext('2d');
            if (graphCtx) {
                graphCtx.setTransform(1, 0, 0, 1, 0, 0);
                graphCtx.scale(window.devicePixelRatio, window.devicePixelRatio);
            }
        }
    }
}

let graphAlpha = 1.0; // Thermal simulation energy (decays to 0 for perfect stability)

function initKnowledgeGraphEngine(rawNodes, rawEdges) {
    const viewport = document.getElementById('canvasViewport');
    graphCanvas = document.getElementById('knowledgeGraphCanvas');
    if (!graphCanvas || !viewport) return;

    graphCtx = graphCanvas.getContext('2d');
    const width = viewport.clientWidth || 1000;
    const height = viewport.clientHeight || 520;
    
    resizeGraphCanvas();
    graphAlpha = 1.0; // Reset simulation temperature to initial settling state

    // Pre-calculate clean geometric pentagon positions for Cluster Hubs
    const hubNodes = rawNodes.filter(n => n.type === 'cluster');
    const hubCount = hubNodes.length;
    const hubPosMap = {};

    hubNodes.forEach((hNode, idx) => {
        const angle = (idx / Math.max(hubCount, 1)) * Math.PI * 2 - Math.PI / 2;
        const radiusX = width * 0.28;
        const radiusY = height * 0.28;
        const x = width / 2 + Math.cos(angle) * radiusX;
        const y = height / 2 + Math.sin(angle) * radiusY;
        hubPosMap[hNode.id] = { x, y };
    });

    graphNodes = rawNodes.map((n, i) => {
        let x, y;
        const isClusterHub = (n.type === 'cluster');

        if (isClusterHub) {
            const pos = hubPosMap[n.id] || { x: width / 2, y: height / 2 };
            x = pos.x;
            y = pos.y;
        } else {
            // Position satellite media node around its parent cluster hub anchor
            const parentHub = hubPosMap[n.cluster_id] || { x: width / 2, y: height / 2 };
            const angle = Math.random() * Math.PI * 2;
            const dist = 35 + Math.random() * 95;
            x = parentHub.x + Math.cos(angle) * dist;
            y = parentHub.y + Math.sin(angle) * dist;
        }

        return {
            ...n,
            x: x,
            y: y,
            vx: 0,
            vy: 0,
            isFixed: isClusterHub, // Fix/anchor main category cluster hubs for high stability
            radius: isClusterHub ? (n.size || 26) : 9,
            color: n.color || '#7c3aed'
        };
    });

    graphEdges = rawEdges.map(e => ({ ...e }));

    // Register Event Listeners
    setupGraphEventListeners(viewport, width, height);

    // Start 60FPS Physics & Render Loop
    if (animFrameId) cancelAnimationFrame(animFrameId);
    function animate() {
        resizeGraphCanvas();
        const curW = (viewport ? viewport.clientWidth : 0) || 1000;
        const curH = (viewport ? viewport.clientHeight : 0) || 520;
        updateGraphPhysics(curW, curH);
        drawGraphScene(curW, curH);
        animFrameId = requestAnimationFrame(animate);
    }
    animate();
}

function updateGraphPhysics(width, height) {
    if (graphAlpha < 0.002 && !draggedNode) return; // Physics frozen solid & completely stable!

    const kRepulsion = 1200 * graphAlpha;
    const kSpring = 0.08 * graphAlpha;
    const springLen = 75;
    const centerGravity = 0.008 * graphAlpha;
    const damping = 0.55; // High velocity absorption to eliminate wild movements

    const nodeMap = {};
    graphNodes.forEach(n => nodeMap[n.id] = n);

    // 1. Coulomb Repulsion between satellite media nodes
    for (let i = 0; i < graphNodes.length; i++) {
        for (let j = i + 1; j < graphNodes.length; j++) {
            const nodeA = graphNodes[i];
            const nodeB = graphNodes[j];
            if (nodeA.isFixed && nodeB.isFixed) continue;

            let dx = nodeB.x - nodeA.x;
            let dy = nodeB.y - nodeA.y;
            let dist = Math.sqrt(dx * dx + dy * dy) || 1;
            
            if (dist < 180) {
                let force = kRepulsion / (dist * dist);
                let fx = (dx / dist) * force;
                let fy = (dy / dist) * force;

                if (!nodeA.isFixed && nodeA !== draggedNode) { nodeA.vx -= fx; nodeA.vy -= fy; }
                if (!nodeB.isFixed && nodeB !== draggedNode) { nodeB.vx += fx; nodeB.vy += fy; }
            }
        }
    }

    // 2. Hooke Spring Attraction along edges
    graphEdges.forEach(edge => {
        const source = nodeMap[edge.source];
        const target = nodeMap[edge.target];
        if (source && target) {
            let dx = target.x - source.x;
            let dy = target.y - source.y;
            let dist = Math.sqrt(dx * dx + dy * dy) || 1;
            let delta = dist - springLen;
            let force = delta * kSpring;

            let fx = (dx / dist) * force;
            let fy = (dy / dist) * force;

            if (!source.isFixed && source !== draggedNode) { source.vx += fx; source.vy += fy; }
            if (!target.isFixed && target !== draggedNode) { target.vx -= fx; target.vy -= fy; }
        }
    });

    // 3. Center gravity & Position integration
    const cx = width / 2;
    const cy = height / 2;

    graphNodes.forEach(node => {
        if (node.isFixed || node === draggedNode) return;

        node.vx += (cx - node.x) * centerGravity;
        node.vy += (cy - node.y) * centerGravity;

        // Apply kinetic damping
        node.vx *= damping;
        node.vy *= damping;

        // Clamp max step velocity to eliminate wild jumping
        node.vx = Math.max(-1.5, Math.min(1.5, node.vx));
        node.vy = Math.max(-1.5, Math.min(1.5, node.vy));

        node.x += node.vx;
        node.y += node.vy;

        // Keep inside canvas bounds
        const pad = 35;
        node.x = Math.max(pad, Math.min(width - pad, node.x));
        node.y = Math.max(pad, Math.min(height - pad, node.y));
    });

    // Decay thermal simulation energy (alpha cooling)
    graphAlpha *= 0.94;
}


function drawGraphScene(width, height) {
    if (!graphCtx) return;
    graphCtx.clearRect(0, 0, width, height);

    graphCtx.save();
    // Apply Pan & Zoom transformations
    graphCtx.translate(width / 2 + panOffset.x, height / 2 + panOffset.y);
    graphCtx.scale(zoomLevel, zoomLevel);
    graphCtx.translate(-width / 2, -height / 2);

    const searchTerm = (graphSearchInput ? graphSearchInput.value : '').toLowerCase().trim();

    // Map node objects for edge rendering
    const nodeMap = {};
    graphNodes.forEach(n => nodeMap[n.id] = n);

    // 1. Draw Edges
    graphEdges.forEach(edge => {
        const src = nodeMap[edge.source];
        const tgt = nodeMap[edge.target];
        if (!src || !tgt) return;

        graphCtx.beginPath();
        graphCtx.moveTo(src.x, src.y);
        graphCtx.lineTo(tgt.x, tgt.y);

        if (edge.dashed) {
            graphCtx.setLineDash([4, 6]);
            graphCtx.strokeStyle = 'rgba(255, 255, 255, 0.12)';
            graphCtx.lineWidth = 1;
        } else {
            graphCtx.setLineDash([]);
            const isHoveredEdge = hoveredNode && (hoveredNode.id === src.id || hoveredNode.id === tgt.id);
            graphCtx.strokeStyle = isHoveredEdge ? (src.color || '#7c3aed') : 'rgba(124, 58, 237, 0.25)';
            graphCtx.lineWidth = isHoveredEdge ? 2.5 : 1.5;
        }
        graphCtx.stroke();
    });

    graphCtx.setLineDash([]);

    // 2. Draw Nodes
    graphNodes.forEach(node => {
        const isHovered = hoveredNode === node;
        const isMatched = searchTerm && (
            (node.label && node.label.toLowerCase().includes(searchTerm)) ||
            (node.creator && node.creator.toLowerCase().includes(searchTerm)) ||
            (node.summary && node.summary.toLowerCase().includes(searchTerm))
        );

        const r = isHovered ? node.radius * 1.25 : node.radius;

        // Outer Glow for Cluster Nodes or Hovered Nodes
        if (node.type === 'cluster' || isHovered || isMatched) {
            graphCtx.beginPath();
            graphCtx.arc(node.x, node.y, r + 6, 0, Math.PI * 2);
            graphCtx.fillStyle = isMatched ? 'rgba(245, 158, 11, 0.3)' : (node.color + '33');
            graphCtx.fill();
        }

        // Inner Circle
        graphCtx.beginPath();
        graphCtx.arc(node.x, node.y, r, 0, Math.PI * 2);
        graphCtx.fillStyle = node.color;
        graphCtx.shadowColor = node.color;
        graphCtx.shadowBlur = isHovered ? 15 : (node.type === 'cluster' ? 10 : 0);
        graphCtx.fill();
        graphCtx.shadowBlur = 0;

        graphCtx.lineWidth = isHovered ? 3 : 1.5;
        graphCtx.strokeStyle = '#ffffff';
        graphCtx.stroke();

        // Selective Node Label Rendering
        if (node.type === 'cluster' || isHovered || isMatched || zoomLevel > 1.6) {
            graphCtx.font = node.type === 'cluster' ? 'bold 12px Outfit, sans-serif' : '10px Inter, sans-serif';
            
            // Draw background pill for cluster hub labels for legibility
            if (node.type === 'cluster') {
                const textWidth = graphCtx.measureText(node.label).width;
                graphCtx.fillStyle = 'rgba(8, 9, 13, 0.88)';
                graphCtx.beginPath();
                if (typeof graphCtx.roundRect === 'function') {
                    graphCtx.roundRect(node.x - textWidth / 2 - 8, node.y + r + 4, textWidth + 16, 20, 6);
                } else {
                    graphCtx.rect(node.x - textWidth / 2 - 8, node.y + r + 4, textWidth + 16, 20);
                }
                graphCtx.fill();
                graphCtx.strokeStyle = 'rgba(255,255,255,0.15)';
                graphCtx.lineWidth = 1;
                graphCtx.stroke();
            }

            graphCtx.fillStyle = isHovered ? '#ffffff' : (node.type === 'cluster' ? '#ffffff' : '#94a3b8');
            graphCtx.textAlign = 'center';

            const displayLabel = node.label.length > 24 ? node.label.slice(0, 22) + '...' : node.label;
            graphCtx.fillText(displayLabel, node.x, node.y + r + (node.type === 'cluster' ? 18 : 14));
        }
    });

    graphCtx.restore();
}


function setupGraphEventListeners(viewport, width, height) {
    const tooltip = document.getElementById('graphTooltip');

    function getGraphCoords(e) {
        const rect = viewport.getBoundingClientRect();
        const clientX = e.clientX - rect.left;
        const clientY = e.clientY - rect.top;

        // Invert Pan and Zoom transformations
        const x = (clientX - width / 2 - panOffset.x) / zoomLevel + width / 2;
        const y = (clientY - height / 2 - panOffset.y) / zoomLevel + height / 2;

        return { x, y, clientX, clientY };
    }

    viewport.addEventListener('mousedown', (e) => {
        const { x, y } = getGraphCoords(e);
        const hitNode = graphNodes.find(n => {
            const dx = n.x - x;
            const dy = n.y - y;
            return Math.sqrt(dx * dx + dy * dy) <= n.radius + 4;
        });

        if (hitNode) {
            draggedNode = hitNode;
        } else {
            isDraggingGraph = true;
            dragStartMouse = { x: e.clientX, y: e.clientY };
        }
    });

    viewport.addEventListener('mousemove', (e) => {
        const { x, y, clientX, clientY } = getGraphCoords(e);

        if (draggedNode) {
            draggedNode.x = x;
            draggedNode.y = y;
            draggedNode.vx = 0;
            draggedNode.vy = 0;
            graphAlpha = Math.max(graphAlpha, 0.25);
        } else if (isDraggingGraph) {
            panOffset.x += (e.clientX - dragStartMouse.x);
            panOffset.y += (e.clientY - dragStartMouse.y);
            dragStartMouse = { x: e.clientX, y: e.clientY };
        } else {
            // Hover Detection
            const hitNode = graphNodes.find(n => {
                const dx = n.x - x;
                const dy = n.y - y;
                return Math.sqrt(dx * dx + dy * dy) <= n.radius + 4;
            });

            hoveredNode = hitNode || null;
            viewport.style.cursor = hitNode ? 'pointer' : 'grab';

            if (hitNode && tooltip) {
                tooltip.classList.remove('hidden');
                tooltip.style.left = `${clientX}px`;
                tooltip.style.top = `${clientY}px`;

                tooltip.innerHTML = `
                    <span class="tooltip-badge" style="color: ${hitNode.color}">${hitNode.type === 'cluster' ? 'KNOWLEDGE CLUSTER HUB' : (hitNode.content_type || 'MEDIA NODE')}</span>
                    <div class="tooltip-title">${hitNode.label}</div>
                    ${hitNode.creator ? `<div class="tooltip-creator">Creator: ${hitNode.creator}</div>` : ''}
                    <div class="tooltip-desc">${hitNode.summary || hitNode.description || 'Analyzed node in living graph.'}</div>
                `;
            } else if (tooltip) {
                tooltip.classList.add('hidden');
            }
        }
    });

    viewport.addEventListener('mouseup', () => {
        draggedNode = null;
        isDraggingGraph = false;
    });

    viewport.addEventListener('mouseleave', () => {
        draggedNode = null;
        isDraggingGraph = false;
        hoveredNode = null;
        if (tooltip) tooltip.classList.add('hidden');
    });

    viewport.addEventListener('wheel', (e) => {
        e.preventDefault();
        if (e.deltaY < 0) {
            zoomLevel = Math.min(zoomLevel * 1.1, 3.0);
        } else {
            zoomLevel = Math.max(zoomLevel / 1.1, 0.4);
        }
    }, { passive: false });

    // Click Node Handling
    viewport.addEventListener('click', (e) => {
        const { x, y } = getGraphCoords(e);
        const hitNode = graphNodes.find(n => {
            const dx = n.x - x;
            const dy = n.y - y;
            return Math.sqrt(dx * dx + dy * dy) <= n.radius + 4;
        });

        if (hitNode) {
            if (hitNode.type === 'cluster' && rawGraphData && rawGraphData.clusters) {
                const targetCluster = rawGraphData.clusters.find(c => c.cluster_id === hitNode.id);
                if (targetCluster) {
                    renderClusterMediaWorkspace(targetCluster);
                    document.getElementById('clusterMediaWorkspace')?.scrollIntoView({ behavior: 'smooth' });
                }
            } else if (hitNode.type === 'media') {
                const itemToOpen = shelfData.find(i => i.content_hash === hitNode.id.replace(/^N-/, '').split('-')[0]) || {
                    title: hitNode.label,
                    creator: hitNode.creator || 'Creator',
                    url: hitNode.url || '#',
                    ai_summary: hitNode.summary || 'Discovered entity in knowledge graph.'
                };
                openItemModal(itemToOpen);
            }
        }
    });
}

// ---------------------------------------------------------------------------
// MAIN VIEW 3: RECOMMENDED CONSUMPTION PATH (DAG) FLOW ENGINE
// ---------------------------------------------------------------------------

let currentPathTopic = "ALL";
let currentPathMode = "BALANCED";

const dagTopicSelect = document.getElementById('dagTopicSelect');
const dagModeQuick = document.getElementById('dagModeQuick');
const dagModeBalanced = document.getElementById('dagModeBalanced');
const dagModeDeep = document.getElementById('dagModeDeep');

if (dagTopicSelect) {
    dagTopicSelect.addEventListener('change', () => {
        currentPathTopic = dagTopicSelect.value;
        loadCartographerPath(currentPathTopic, currentPathMode);
    });
}

const modePills = [
    { el: dagModeQuick, mode: "QUICK" },
    { el: dagModeBalanced, mode: "BALANCED" },
    { el: dagModeDeep, mode: "DEEP" }
];

modePills.forEach(p => {
    if (p.el) {
        p.el.addEventListener('click', () => {
            modePills.forEach(x => x.el && x.el.classList.remove('active'));
            p.el.classList.add('active');
            currentPathMode = p.mode;
            loadCartographerPath(currentPathTopic, currentPathMode);
        });
    }
});

async function loadCartographerPath(topic = "ALL", mode = "BALANCED") {
    try {
        const res = await fetch(`/api/cartographer/path?topic=${encodeURIComponent(topic)}&mode=${encodeURIComponent(mode)}`);
        const data = await res.json();
        console.log("Cartographer Path Data:", data);

        const pathList = document.getElementById('pathNodesList');
        const flowContainer = document.getElementById('dagGraphContainer');
        const pathTotalTime = document.getElementById('pathTotalTime');
        const pathStepCount = document.getElementById('pathStepCount');

        if (!data.path || data.path.length === 0) return;

        const pathNodes = data.path;
        if (pathStepCount) pathStepCount.textContent = pathNodes.length;
        
        let totalMins = pathNodes.reduce((acc, p) => acc + (p.estimated_minutes || 15), 0);
        if (pathTotalTime) pathTotalTime.textContent = totalMins;

        // 1. Render Interactive Visual DAG Flowchart
        if (flowContainer) {
            flowContainer.innerHTML = '';
            pathNodes.forEach((node, idx) => {
                const stageCard = document.createElement('div');
                stageCard.className = 'dag-stage-node';
                
                const purposeClass = (node.purpose || 'CORE').toLowerCase();

                stageCard.innerHTML = `
                    <div class="dag-stage-header">
                        <span class="stage-badge ${purposeClass}">STAGE 0${node.step || (idx + 1)} — ${node.purpose}</span>
                        <span style="font-size: 0.75rem; color: var(--text-muted);"><i class="fas fa-clock"></i> ${node.estimated_minutes}m</span>
                    </div>
                    <h4 style="font-size: 0.92rem; color: #fff; font-weight: 600; line-height: 1.3;">${node.title}</h4>
                    <p style="font-size: 0.78rem; color: var(--text-subtle); display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;">${node.justification}</p>
                `;

                stageCard.addEventListener('click', () => {
                    const rowEl = document.getElementById(`pathRow-${idx}`);
                    if (rowEl) rowEl.scrollIntoView({ behavior: 'smooth' });
                });

                flowContainer.appendChild(stageCard);

                // Add Flow Connector Arrow if not last node
                if (idx < pathNodes.length - 1) {
                    const arrow = document.createElement('div');
                    arrow.className = 'dag-connector-arrow';
                    arrow.innerHTML = `<i class="fas fa-chevron-right"></i>`;
                    flowContainer.appendChild(arrow);
                }
            });
        }

        // 2. Render Sequential Node Roadmap Breakdown
        if (pathList) {
            pathList.innerHTML = '';
            pathNodes.forEach((p, idx) => {
                const card = document.createElement('div');
                card.id = `pathRow-${idx}`;
                card.className = 'path-card';
                
                const prereqStr = (p.prerequisites && p.prerequisites.length > 0) 
                    ? p.prerequisites.join(', ') 
                    : 'None (Foundational Entrypoint)';

                card.innerHTML = `
                    <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 8px; flex-wrap: wrap; gap: 8px;">
                        <div style="display: flex; gap: 8px; align-items: center;">
                            <span class="badge-tag badge-purple">STEP 0${p.step} — ${p.purpose}</span>
                            <span class="badge-tag badge-subtle">${p.difficulty || 'BEGINNER'}</span>
                        </div>
                        <span style="font-size: 0.8rem; color: var(--text-muted);"><i class="fas fa-link"></i> Prerequisites: <strong style="color: #c4b5fd;">${prereqStr}</strong></span>
                    </div>
                    <h3 style="font-size: 1.05rem; color: #fff; font-weight: 700; margin-bottom: 4px;">${p.title}</h3>
                    <p style="font-size: 0.85rem; color: var(--text-muted); line-height: 1.4; margin-bottom: 12px;">${p.justification}</p>
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <span style="font-size: 0.8rem; color: var(--accent-emerald);"><i class="fas fa-hourglass-half"></i> Estimated Duration: ${p.estimated_minutes} minutes</span>
                        <a href="${p.url || '#'}" target="_blank" class="btn btn-outline" style="padding: 5px 14px; font-size: 0.8rem;">
                            <i class="fas fa-play-circle"></i> Launch Concept Step
                        </a>
                    </div>
                `;
                pathList.appendChild(card);
            });
        }
    } catch (e) {
        console.error("Failed to load Cartographer Path:", e);
    }
}

// ---------------------------------------------------------------------------
// MAIN VIEW 4: EVOLUTION TIMELINE STREAM ENGINE
// ---------------------------------------------------------------------------

let timelineFilter = "ALL";

function renderEvolutionTimeline(events) {
    const timelineList = document.getElementById('evolutionTimelineList');
    const totalMutationsCount = document.getElementById('totalMutationsCount');

    if (!timelineList) return;
    timelineList.innerHTML = '';

    if (!events || events.length === 0) {
        timelineList.innerHTML = `<p style="color: var(--text-muted); padding: 20px;">No graph mutation events recorded yet.</p>`;
        return;
    }

    if (totalMutationsCount) totalMutationsCount.textContent = events.length;

    const filteredEvents = events.filter(e => timelineFilter === "ALL" || e.event_type === timelineFilter);

    filteredEvents.forEach(evt => {
        const card = document.createElement('div');
        card.className = 'timeline-event-card';

        const typeColor = evt.event_type === 'LINK' ? '#10b981' : (evt.event_type === 'CLASSIFY' ? '#3b82f6' : '#a855f7');
        const timeStr = evt.timestamp ? new Date(evt.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : 'Just now';

        const affectedBadges = (evt.affected_nodes || []).map(n => `<span class="badge-tag badge-subtle" style="font-size: 0.7rem;">${n}</span>`).join(' ');
        const evidencePills = (evt.evidence || []).map(ev => `<span class="evidence-pill"><i class="fas fa-shield"></i> ${ev}</span>`).join(' ');

        card.innerHTML = `
            <div class="event-header">
                <div style="display: flex; gap: 8px; align-items: center;">
                    <span class="event-id-badge">${evt.event_id || 'EVT-01'}</span>
                    <span class="badge-tag" style="background: ${typeColor}22; color: ${typeColor}; border: 1px solid ${typeColor}44;">${evt.event_type}</span>
                </div>
                <span class="event-timestamp"><i class="fas fa-clock"></i> ${timeStr}</span>
            </div>
            <div class="event-desc">${evt.description}</div>
            <div class="event-meta">
                ${affectedBadges}
                ${evidencePills}
            </div>
        `;

        timelineList.appendChild(card);
    });
}

// Timeline Filters Handler
const timelineFilterBtns = document.querySelectorAll('.timeline-filters .filter-pill');
timelineFilterBtns.forEach(btn => {
    btn.addEventListener('click', () => {
        timelineFilterBtns.forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        timelineFilter = btn.getAttribute('data-filter') || "ALL";
        if (rawGraphData && rawGraphData.history) {
            renderEvolutionTimeline(rawGraphData.history);
        }
    });
});

// Simulate AI Mutation Event Handler
const simulateMutationBtn = document.getElementById('simulateMutationBtn');
if (simulateMutationBtn) {
    simulateMutationBtn.addEventListener('click', async () => {
        simulateMutationBtn.disabled = true;
        simulateMutationBtn.innerHTML = `<i class="fas fa-circle-notch fa-spin"></i> Mutating...`;

        try {
            const res = await fetch('/api/cartographer/mutate', { method: 'POST' });
            const data = await res.json();
            if (data.status === 'success' && data.event) {
                if (!rawGraphData.history) rawGraphData.history = [];
                rawGraphData.history.unshift(data.event);
                renderEvolutionTimeline(rawGraphData.history);
                // Also trigger live graph refetch
                await loadCartographerMap();
            }
        } catch (e) {
            console.error("Mutation simulation failed:", e);
        } finally {
            simulateMutationBtn.disabled = false;
            simulateMutationBtn.innerHTML = `<i class="fas fa-wand-magic-sparkles"></i> Simulate AI Mutation`;
        }
    });
}

// Quick URL Map Handler
const quickMapBtn = document.getElementById('quickMapBtn');
const quickUrlInput = document.getElementById('quickUrlInput');

if (quickMapBtn && quickUrlInput) {
    quickMapBtn.addEventListener('click', async () => {
        const url = quickUrlInput.value.trim();
        if (!url) return;
        
        quickMapBtn.disabled = true;
        quickMapBtn.innerHTML = '<i class="fas fa-circle-notch fa-spin"></i> Mapping...';
        
        try {
            const res = await fetch('/api/cartographer/process', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ url: url })
            });
            const data = await res.json();
            if (data.status === 'success') {
                quickUrlInput.value = '';
                alert(`✨ Knowledge Cartographer successfully mapped input!\n\nExtracted ${data.container.entities.length} entities.\nPrimary Source: ${data.primary_source.title} (Quality Score: ${data.primary_source.overall_score}%)\n\nNew card added to your Shelf!`);
                await loadData();
                await loadCartographerMap();
            }
        } catch (e) {
            console.error("Quick map failed:", e);
        } finally {
            quickMapBtn.disabled = false;
            quickMapBtn.innerHTML = '<i class="fas fa-wand-magic-sparkles"></i> Map Content';
        }
    });
}

// Initial Load
document.addEventListener('DOMContentLoaded', () => {
    loadData();
    checkRecentAgentTask();
    loadCartographerMap();
    loadCartographerPath();
});

