document.addEventListener('DOMContentLoaded', () => {
    const dropZone = document.getElementById('drop-zone');
    const imageInput = document.getElementById('image-input');
    const imagePreview = document.getElementById('image-preview');
    const submitBtn = document.getElementById('submit-btn');
    const predictionForm = document.getElementById('prediction-form');
    const resultSection = document.getElementById('result-section');
    const resetBtns = document.querySelectorAll('.predict-reset-btn');
    const alertContainer = document.getElementById('alert-container');
    const modelBoxes = Array.from(document.querySelectorAll('.model-checkbox'));
    const modelHint = document.getElementById('model-mode-hint');
    const submitBtnHtml = submitBtn.innerHTML;

    let selectedFile = null;

    function selectedModels() {
        return modelBoxes.filter(box => box.checked).map(box => box.value);
    }

    function updateModelHint() {
        if (!modelHint) return;
        const count = selectedModels().length;
        modelHint.textContent = count > 1
            ? `${count} models enabled → hard voting ensemble`
            : '1 model enabled → single model prediction';
    }

    modelBoxes.forEach(box => {
        box.addEventListener('change', (e) => {
            if (selectedModels().length === 0) {
                e.target.checked = true;
            }
            updateModelHint();
        });
    });

    dropZone.addEventListener('click', () => imageInput.click());
    
    dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropZone.classList.add('dragover');
    });

    dropZone.addEventListener('dragleave', () => {
        dropZone.classList.remove('dragover');
    });

    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.classList.remove('dragover');
        if (e.dataTransfer.files.length) {
            handleFileSelection(e.dataTransfer.files[0]);
        }
    });

    imageInput.addEventListener('change', (e) => {
        if (e.target.files.length) {
            handleFileSelection(e.target.files[0]);
        }
    });

    function handleFileSelection(file) {
        if (!file.type.startsWith('image/')) {
            showAlert('Please select a valid image file.', 'danger');
            return;
        }
        if (file.size > 8 * 1024 * 1024) {
            showAlert('Image is too large. Maximum size is 8 MB.', 'danger');
            return;
        }
        selectedFile = file;
        const reader = new FileReader();
        reader.onload = (e) => {
            imagePreview.src = e.target.result;
            imagePreview.classList.remove('d-none');
            dropZone.querySelector('p').classList.add('d-none');
            submitBtn.disabled = false;
        };
        reader.readAsDataURL(file);
    }

    function showAlert(message, type) {
        // The message may originate from an API error, so it is inserted as text.
        const wrapper = document.createElement('div');
        wrapper.className = `alert alert-${type} alert-dismissible fade show`;
        wrapper.setAttribute('role', 'alert');
        const text = document.createElement('span');
        text.textContent = message;
        wrapper.appendChild(text);
        const close = document.createElement('button');
        close.type = 'button';
        close.className = 'btn-close';
        close.setAttribute('data-bs-dismiss', 'alert');
        close.setAttribute('aria-label', 'Close');
        wrapper.appendChild(close);
        alertContainer.innerHTML = '';
        alertContainer.appendChild(wrapper);
    }

    predictionForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        if (!selectedFile) return;

        submitBtn.disabled = true;
        submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Predicting...';
        alertContainer.innerHTML = '';

        const formData = new FormData();
        formData.append('image', selectedFile);
        formData.append('models', selectedModels().join(','));

        try {
            const response = await fetch(apiUrl('/api/predict/disease'), {
                method: 'POST',
                body: formData
            });

            let data;
            try {
                data = await response.json();
            } catch (parseError) {
                throw new Error(`Prediction failed (HTTP ${response.status})`);
            }

            if (!response.ok) {
                throw new Error(data.detail || 'Prediction failed');
            }

            displayResults(data);
        } catch (error) {
            showAlert(error.message, 'danger');
        } finally {
            submitBtn.disabled = false;
            submitBtn.innerHTML = submitBtnHtml;
        }
    });

    function displayResults(data) {
        predictionForm.closest('.card').classList.add('d-none');
        resultSection.classList.remove('d-none');

        const { prediction, cure } = data;
        
        const annotatedImg = document.getElementById('res-annotated-image');
        if (prediction.annotated_image_base64) {
            annotatedImg.src = `data:image/jpeg;base64,${prediction.annotated_image_base64}`;
            annotatedImg.classList.remove('d-none');
        } else {
            annotatedImg.classList.add('d-none');
        }
        
        const detBody = document.getElementById('detections-table-body');
        detBody.innerHTML = '';
        if (prediction.detections && prediction.detections.length > 0) {
            prediction.detections.forEach((det, idx) => {
                const tr = document.createElement('tr');
                const isTop = idx === 0;
                tr.style.borderBottom = '1px solid rgba(255,255,255,0.05)';
                tr.innerHTML = `
                    <td class="py-2" style="width: 75%;">
                        <div class="d-flex justify-content-between align-items-center mb-1">
                            <span class="${isTop ? 'fw-bold text-success' : 'text-light small'}">${isTop ? '⭐ ' : ''}${det.label}</span>
                            <span class="badge ${isTop ? 'bg-success' : 'bg-dark border border-secondary text-light'} px-2">${det.score}%</span>
                        </div>
                        <div class="progress" style="height: 6px; background: rgba(255,255,255,0.08); border-radius: 3px;">
                            <div class="progress-bar ${isTop ? 'bg-success' : 'bg-secondary'}" role="progressbar" style="width: ${Math.min(100, Math.max(1, det.score))}%;"></div>
                        </div>
                    </td>
                    <td class="py-2 text-end align-middle fw-bold ${isTop ? 'text-success' : 'text-muted small'}" style="width: 25%; font-family: monospace;">
                        ${det.score}%
                    </td>
                `;
                detBody.appendChild(tr);
            });
        } else {
            detBody.innerHTML = '<tr><td colspan="2" class="text-center text-muted py-3">No disease detections returned.</td></tr>';
        }

        document.getElementById('res-disease-name').textContent = prediction.disease_name;
        document.getElementById('res-confidence').textContent = `${prediction.confidence_score}%`;
        
        // The backend flags results below the confidence floor as "uncertain".
        // Showing them as a confirmed infection would be a false claim, so the
        // badge reflects the model status instead of only the healthy flag.
        const uncertain = prediction.status === 'uncertain' || prediction.confident === false;
        const healthyBadge = document.getElementById('res-healthy');
        if (uncertain) {
            healthyBadge.className = 'badge bg-warning text-dark';
            healthyBadge.textContent = '⚠️ Uncertain - Review Needed';
        } else if (prediction.is_healthy) {
            healthyBadge.className = 'badge bg-success';
            healthyBadge.textContent = '✅ Healthy Crop';
        } else {
            healthyBadge.className = 'badge bg-danger';
            healthyBadge.textContent = '❌ Infected Plant';
        }

        const severityBadge = document.getElementById('res-severity');
        severityBadge.textContent = uncertain
            ? `Severity: Unassessed`
            : `Severity: ${prediction.severity}`;
        if (uncertain) severityBadge.className = 'badge bg-secondary';
        else if (prediction.severity === 'Severe' || prediction.severity === 'High') severityBadge.className = 'badge bg-danger';
        else if (prediction.severity === 'Moderate') severityBadge.className = 'badge bg-warning text-dark';
        else severityBadge.className = 'badge bg-info text-dark';

        // Surface the model's own notice (low-confidence guidance) to the farmer.
        const noticeHost = document.getElementById('res-notice');
        if (noticeHost) {
            noticeHost.textContent = data.notice || '';
            noticeHost.classList.toggle('d-none', !data.notice);
        }

        const metaHost = document.getElementById('res-model-meta');
        if (metaHost) {
            const isVoting = prediction.mode === 'voting';
            const agreementPill = isVoting 
                ? `<span class="badge rounded-pill bg-success-subtle text-success border border-success px-3 py-1 small">🗳️ Hard Voting (${prediction.agreement}% Consensus)</span>`
                : `<span class="badge rounded-pill bg-info-subtle text-info border border-info px-3 py-1 small">🔬 Single Model Evaluation</span>`;
            const devicePill = `<span class="badge rounded-pill bg-dark border border-secondary text-light px-3 py-1 small">⚡ ${prediction.device ? prediction.device.toUpperCase() : 'CPU'}</span>`;
            const timePill = `<span class="badge rounded-pill bg-dark border border-secondary text-light px-3 py-1 small">⏱️ ${prediction.inference_ms || 0} ms</span>`;
            const classesPill = `<span class="badge rounded-pill bg-dark border border-secondary text-light px-3 py-1 small">🏷️ ${prediction.detections ? prediction.detections.length : 0} Candidates Evaluated</span>`;
            
            metaHost.innerHTML = `<div class="d-flex flex-wrap gap-2 align-items-center">${agreementPill}${devicePill}${timePill}${classesPill}</div>`;
        }

        const votesHost = document.getElementById('res-votes');
        if (votesHost) {
            if (prediction.votes && prediction.votes.length > 0) {
                votesHost.classList.remove('d-none');
                votesHost.innerHTML = '';
                
                const header = document.createElement('div');
                header.className = 'd-flex justify-content-between align-items-center mb-3 pb-2 border-bottom border-secondary border-opacity-25';
                header.innerHTML = `
                    <div class="fw-bold fs-6 text-light d-flex align-items-center gap-2">
                        <span>🗳️ AI Ensemble Model Votes</span>
                        <span class="badge bg-success-subtle text-success border border-success-subtle small">${prediction.mode === 'voting' ? 'Majority Consensus' : 'Single Evaluation'}</span>
                    </div>
                    <span class="text-muted small">${prediction.votes.filter(v => v.ok).length} of ${prediction.votes.length} models active</span>
                `;
                votesHost.appendChild(header);

                const grid = document.createElement('div');
                grid.className = 'row g-3';

                prediction.votes.forEach(vote => {
                    const col = document.createElement('div');
                    col.className = 'col-md-6 col-lg-4';
                    
                    const isWinner = vote.ok && (vote.label === prediction.disease_name);
                    const cardBg = isWinner 
                        ? 'background: linear-gradient(145deg, rgba(180, 230, 57, 0.14), rgba(0, 0, 0, 0.6)); border: 1px solid rgba(180, 230, 57, 0.45);'
                        : 'background: rgba(0, 0, 0, 0.45); border: 1px solid rgba(255, 255, 255, 0.08);';

                    if (vote.ok) {
                        col.innerHTML = `
                            <div class="p-3 rounded-3 h-100 shadow-sm position-relative" style="${cardBg}">
                                <div class="d-flex justify-content-between align-items-start mb-2">
                                    <span class="fw-bold small text-light text-truncate pe-1" title="${vote.model_label}">${vote.model_label}</span>
                                    ${isWinner ? '<span class="badge bg-success px-2 py-1"><i class="bi bi-trophy"></i> Winner</span>' : '<span class="badge bg-secondary px-2 py-1">Voted</span>'}
                                </div>
                                <div class="fs-6 fw-bold text-success mb-2 text-truncate" title="${vote.label}">${vote.label}</div>
                                <div class="d-flex justify-content-between small text-muted mb-1">
                                    <span>Confidence</span>
                                    <span class="fw-bold text-light">${vote.score}%</span>
                                </div>
                                <div class="progress mb-2" style="height: 6px; background: rgba(255,255,255,0.1); border-radius: 3px;">
                                    <div class="progress-bar ${isWinner ? 'bg-success' : 'bg-info'}" role="progressbar" style="width: ${Math.min(100, vote.score)}%;"></div>
                                </div>
                                <div class="text-end small text-muted opacity-75">⏱️ ${vote.ms} ms</div>
                            </div>
                        `;
                    } else {
                        let errText = (vote.error || 'Temporarily unavailable').trim();
                        if (errText.length > 45) errText = 'Model format incompatible';
                        col.innerHTML = `
                            <div class="p-3 rounded-3 h-100 shadow-sm" style="background: rgba(20, 20, 20, 0.4); border: 1px dashed rgba(255, 255, 255, 0.15);">
                                <div class="d-flex justify-content-between align-items-start mb-2">
                                    <span class="fw-bold small text-muted text-truncate" title="${vote.model_label}">${vote.model_label}</span>
                                    <span class="badge bg-secondary-subtle text-secondary px-2 py-1">Abstained</span>
                                </div>
                                <div class="small text-warning mt-2 mb-1">⚠️ ${errText}</div>
                                <div class="small text-muted opacity-75">Excluded from ensemble vote</div>
                            </div>
                        `;
                    }
                    grid.appendChild(col);
                });
                votesHost.appendChild(grid);
            } else {
                votesHost.classList.add('d-none');
            }
        }

        const tbody = document.getElementById('cure-table-body');
        tbody.innerHTML = '';
        (cure || []).forEach(c => {
            const tr = document.createElement('tr');
            const stepCell = document.createElement('td');
            stepCell.className = 'fw-bold';
            stepCell.textContent = c.step;
            const actionCell = document.createElement('td');
            actionCell.textContent = c.action;
            const detailsCell = document.createElement('td');
            detailsCell.textContent = c.details;
            tr.appendChild(stepCell);
            tr.appendChild(actionCell);
            tr.appendChild(detailsCell);
            tbody.appendChild(tr);
        });
    }

    function resetPrediction() {
        selectedFile = null;
        imagePreview.src = '';
        imagePreview.classList.add('d-none');
        dropZone.querySelector('p').classList.remove('d-none');
        submitBtn.disabled = true;
        imageInput.value = '';
        
        const annotatedImg = document.getElementById('res-annotated-image');
        if (annotatedImg) {
            annotatedImg.src = '';
            annotatedImg.classList.add('d-none');
        }

        const votesHost = document.getElementById('res-votes');
        if (votesHost) votesHost.classList.add('d-none');
        alertContainer.innerHTML = '';
        
        resultSection.classList.add('d-none');
        predictionForm.closest('.card').classList.remove('d-none');
    }

    resetBtns.forEach(btn => btn.addEventListener('click', resetPrediction));
});

window.showAuthView = function(tab) {
    const authView = document.getElementById('auth-view');
    
    if (authView) authView.classList.remove('d-none');

    if (typeof switchAuthTab === 'function') {
        switchAuthTab(tab);
    }
};

window.closeAuthView = function() {
    const authView = document.getElementById('auth-view');
    if (authView) authView.classList.add('d-none');
};

// Climate Dashboard Navigation Logic
window.showView = function(viewName) {
    const user = getStoredUser();
    const authView = document.getElementById('auth-view');
    const mainNavbar = document.getElementById('main-navbar');
    
    if (!user && viewName !== 'home') {
        showAuthView('login');
        return;
    }
    
    // Always show main layout if we are not manually opening auth view
    if (authView) authView.classList.add('d-none');
    if (mainNavbar) mainNavbar.classList.remove('d-none');

    // Toggle nav items based on authentication status
    document.querySelectorAll('.auth-required').forEach(el => {
        if(user) el.classList.remove('d-none');
        else el.classList.add('d-none');
    });
    document.querySelectorAll('.unauth-only').forEach(el => {
        if(user) el.classList.add('d-none');
        else el.classList.remove('d-none');
    });

    // Remove active from all nav items
    document.getElementById('nav-home').classList.remove('active');
    document.getElementById('nav-disease').classList.remove('active');
    document.getElementById('nav-climate').classList.remove('active');
    if(document.getElementById('nav-plantfarm')) document.getElementById('nav-plantfarm').classList.remove('active');
    if(document.getElementById('nav-animalfarm')) document.getElementById('nav-animalfarm').classList.remove('active');
    if(document.getElementById('nav-animalanalytics')) document.getElementById('nav-animalanalytics').classList.remove('active');
    if(document.getElementById('nav-analysis')) document.getElementById('nav-analysis').classList.remove('active');
    if(document.getElementById('nav-unified')) document.getElementById('nav-unified').classList.remove('active');
    document.getElementById('nav-market').classList.remove('active');
    if(document.getElementById('nav-profile')) document.getElementById('nav-profile').classList.remove('active');
    
    // Set active on the current nav item
    const navEl = document.getElementById('nav-' + viewName);
    if (navEl) navEl.classList.add('active');
    
    // Hide all views
    document.getElementById('home-view').style.display = 'none';
    document.getElementById('disease-prediction-view').classList.add('d-none');
    document.getElementById('climate-prediction-view').classList.add('d-none');
    if(document.getElementById('plant-farm-view')) document.getElementById('plant-farm-view').classList.add('d-none');
    if(document.getElementById('animal-farm-view')) document.getElementById('animal-farm-view').classList.add('d-none');
    if(document.getElementById('animal-analysis-dashboard-view')) document.getElementById('animal-analysis-dashboard-view').classList.add('d-none');
    if(document.getElementById('analysis-dashboard-view')) document.getElementById('analysis-dashboard-view').classList.add('d-none');
    if(document.getElementById('unified-dashboard-view')) document.getElementById('unified-dashboard-view').classList.add('d-none');
    document.getElementById('market-intelligence-view').classList.add('d-none');
    if(document.getElementById('profile-view')) document.getElementById('profile-view').classList.add('d-none');
    if(document.getElementById('croprec-view')) document.getElementById('croprec-view').classList.add('d-none');
    if(document.getElementById('yield-view')) document.getElementById('yield-view').classList.add('d-none');
    if(document.getElementById('schemes-view')) document.getElementById('schemes-view').classList.add('d-none');
    if(document.getElementById('assistant-view')) document.getElementById('assistant-view').classList.add('d-none');
    
    // Toggle body background and navbar margin
    const navbar = document.getElementById('main-navbar');
    if (viewName === 'home') {
        navbar.classList.remove('mb-4');
        document.getElementById('home-view').style.display = 'block';
    } else {
        navbar.classList.add('mb-4');
        
        if (viewName === 'disease') {
            document.getElementById('disease-prediction-view').classList.remove('d-none');
        } else if (viewName === 'croprec') {
            if(document.getElementById('croprec-view')) document.getElementById('croprec-view').classList.remove('d-none');
        } else if (viewName === 'yield') {
            if(document.getElementById('yield-view')) document.getElementById('yield-view').classList.remove('d-none');
        } else if (viewName === 'schemes') {
            if(document.getElementById('schemes-view')) document.getElementById('schemes-view').classList.remove('d-none');
            loadSchemesDirectory();
        } else if (viewName === 'assistant') {
            if(document.getElementById('assistant-view')) document.getElementById('assistant-view').classList.remove('d-none');
        } else if (viewName === 'climate') {
            document.getElementById('climate-prediction-view').classList.remove('d-none');
            loadClimateView();
        } else if (viewName === 'unified') {
            document.getElementById('unified-dashboard-view').classList.remove('d-none');
            loadUnifiedDashboard();
        } else if (viewName === 'plantfarm') {
            if(document.getElementById('plant-farm-view')) document.getElementById('plant-farm-view').classList.remove('d-none');
            loadPlantFarmDashboard();
        } else if (viewName === 'animalfarm') {
            if(document.getElementById('animal-farm-view')) document.getElementById('animal-farm-view').classList.remove('d-none');
            loadAnimalDashboard();
        } else if (viewName === 'animalanalytics') {
            if(document.getElementById('animal-analysis-dashboard-view')) document.getElementById('animal-analysis-dashboard-view').classList.remove('d-none');
            loadAnimalAnalyticsDashboard();
        } else if (viewName === 'analysis') {
            if(document.getElementById('analysis-dashboard-view')) document.getElementById('analysis-dashboard-view').classList.remove('d-none');
            loadAnalyticsSidebar();
            switchAnalyticsTab('plant');
        } else if (viewName === 'market') {
            document.getElementById('market-intelligence-view').classList.remove('d-none');
            loadMarketIntelligence();
        } else if (viewName === 'profile') {
            if(document.getElementById('profile-view')) document.getElementById('profile-view').classList.remove('d-none');
            loadUserProfile();
        }
    }
    
    // Scroll to top
    window.scrollTo({ top: 0, behavior: 'smooth' });
    
    // Re-trigger scroll animations for home view
    if (viewName === 'home') {
        initScrollAnimations();
    }
};

// Scroll-triggered animations
function initScrollAnimations() {
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('visible');
            }
        });
    }, { threshold: 0.15, rootMargin: '0px 0px -50px 0px' });
    
    document.querySelectorAll('.animate-on-scroll').forEach(el => {
        el.classList.remove('visible');
        observer.observe(el);
    });
}

// Initialize scroll animations on page load
document.addEventListener('DOMContentLoaded', () => {
    initScrollAnimations();
    
    // Chart.js Dark Theme Defaults
    if (typeof Chart !== 'undefined') {
        Chart.defaults.color = 'rgba(255, 255, 255, 0.6)';
        Chart.defaults.borderColor = 'rgba(255, 255, 255, 0.06)'; // This handles grid lines in v4
        
        if (Chart.defaults.plugins && Chart.defaults.plugins.legend && Chart.defaults.plugins.legend.labels) {
            Chart.defaults.plugins.legend.labels.color = 'rgba(255, 255, 255, 0.6)';
            Chart.defaults.plugins.legend.labels.padding = 15;
        }
    }
});

// Global session variable
window.activeSessionId = null;
window.activeSessionType = null; // 'plant' or 'animal'

window.loadClimateView = async function() {
    // Fetch all sessions (plants and animals)
    try {
        const [plantsRes, animalsRes] = await Promise.all([
            fetch(apiUrl('/api/sessions')),
            fetch(apiUrl('/api/animals'))
        ]);
        
        const selector = document.getElementById('climate-session-selector');
        selector.innerHTML = '<option value="">Select a session...</option>';
        
        let hasSessions = false;

        if (plantsRes.ok) {
            const plants = await plantsRes.json();
            if (plants.length > 0) {
                const optGroup = document.createElement('optgroup');
                optGroup.label = "🌾 Plant Sessions";
                plants.forEach(s => {
                    const status = s.is_active ? '(Active)' : '(Ended)';
                    // textContent, never innerHTML: plot_name is user supplied.
                    const option = document.createElement('option');
                    option.value = `plant_${s.id}`;
                    option.textContent = `${s.plot_name} (${s.crop_type}) ${status}`;
                    optGroup.appendChild(option);
                });
                selector.appendChild(optGroup);
                hasSessions = true;
            }
        }
        
        if (animalsRes.ok) {
            const animals = await animalsRes.json();
            if (animals.length > 0) {
                const optGroup = document.createElement('optgroup');
                optGroup.label = "🐾 Animal Sessions";
                animals.forEach(s => {
                    const status = s.is_active ? '(Active)' : '(Ended)';
                    const option = document.createElement('option');
                    option.value = `animal_${s.id}`;
                    option.textContent = `${s.session_name} (${s.animal_type}) ${status}`;
                    optGroup.appendChild(option);
                });
                selector.appendChild(optGroup);
                hasSessions = true;
            }
        }

        if (!hasSessions) {
            selector.innerHTML = '<option value="">No sessions found...</option>';
        } else if (window.activeSessionId && window.activeSessionType) {
            selector.value = `${window.activeSessionType}_${window.activeSessionId}`;
        }
        
    } catch (e) {
        console.error("Error loading climate sessions", e);
    }
};

window.handleClimateSessionSelect = function() {
    const val = document.getElementById('climate-session-selector').value;
    if (!val) {
        document.getElementById('session-info').innerHTML = '<span class="text-muted">Please select a session from the dropdown above to view climate and recommendations.</span>';
        document.getElementById('weather-info').innerHTML = '<span class="text-muted">Loading weather...</span>';
        document.getElementById('disease-risk-info').innerHTML = '<span class="text-muted">Loading risk data...</span>';
        document.getElementById('watering-rec').innerHTML = '<span class="text-muted">Loading recommendation...</span>';
        document.getElementById('fertilizing-rec').innerHTML = '<span class="text-muted">Loading recommendation...</span>';
        window.activeSessionId = null;
        window.activeSessionType = null;
        return;
    }
    
    const parts = val.split('_');
    window.activeSessionType = parts[0];
    window.activeSessionId = parseInt(parts[1]);
    
    // Fetch info and climate data
    fetchSessionInfoAndClimate();
};

window.fetchSessionInfoAndClimate = async function() {
    if (!window.activeSessionId) return;
    
    try {
        // Find session details
        const endpoint = window.activeSessionType === 'plant' 
            ? apiUrl(`/api/sessions`) 
            : apiUrl(`/api/animals`);
            
        const res = await fetch(endpoint);
        const sessions = await res.json();
        const session = sessions.find(s => s.id === window.activeSessionId);
        
        if (session) {
            if (window.activeSessionType === 'plant') {
                document.getElementById('session-info').innerHTML = `
                    <div><strong>Crop:</strong> ${escapeHtml(session.crop_type)} (${escapeHtml(session.plot_name)})</div>
                    <div><strong>Soil:</strong> ${escapeHtml(session.soil_type)}</div>
                    <div><strong>Location:</strong> ${escapeHtml(session.location)}</div>
                `;
            } else {
                document.getElementById('session-info').innerHTML = `
                    <div><strong>Animal:</strong> ${escapeHtml(session.animal_type)} (${escapeHtml(session.session_name)})</div>
                    <div><strong>Count:</strong> ${escapeHtml(session.animal_count)}</div>
                `;
            }
        }
        
        // Fetch recommendations (currently backend only supports plant recommendations, but we can reuse it for basic weather)
        // Note: The backend /api/sessions/{id}/recommendations specifically queries FarmingSession.
        // If it's an animal session, the backend exposes no advisory endpoint, so the
        // cards below show STATIC GUIDANCE - not a computed assessment.
        if (window.activeSessionType === 'plant') {
            await fetchClimateData();
        } else {
            document.getElementById('weather-info').innerHTML = `
                <span class="badge bg-secondary mb-2">Not available for livestock sessions</span>
                <p class="mb-1 text-muted">Weather is currently fetched for plant sessions only.</p>
            `;
            document.getElementById('disease-risk-info').innerHTML = `
                <span class="badge bg-secondary fs-6 mb-2">Static guidance</span>
                <p class="mb-1 fw-bold">No disease-risk model is applied to livestock sessions.</p>
                <p class="mb-0 text-muted">Consult a veterinary officer for animal health decisions.</p>
            `;
            document.getElementById('watering-rec').innerHTML = `
                <h5 class="fw-bold text-dark">Ensure constant clean water supply</h5>
                <p class="mb-2">⚠️ General husbandry guidance (static, not a computed recommendation).</p>
            `;
            document.getElementById('fertilizing-rec').innerHTML = `
                <h5 class="fw-bold text-dark">Ensure proper feeding schedule</h5>
                <p class="mb-2">⚠️ General husbandry guidance (static, not a computed recommendation).</p>
            `;
        }
    } catch (e) {
        console.error("Error fetching info", e);
    }
};

window.createNewSession = async function() {
    alert("Please use the 'Plant Farm' or 'Animal Farm' tabs to create new sessions.");
};

window.fetchClimateData = async function() {
    if (!window.activeSessionId) return;

    try {
        const res = await fetch(apiUrl(`/api/sessions/${window.activeSessionId}/recommendations`));
        if (!res.ok) throw new Error("Failed to fetch recommendations");
        const data = await res.json();
        
        // Populate Weather. The provenance badge makes it explicit whether the
        // values came from the weather provider or from the labelled fallback.
        const weather = data.current_weather || {};
        const simulated = weather.simulated === true;
        const sourceBadge = simulated
            ? '<span class="badge bg-warning text-dark">Simulated data (weather provider unavailable)</span>'
            : '<span class="badge bg-success">Live weather</span>';
        const moistureDetail = data.soil_moisture_detail || {};
        const moistureNote = moistureDetail.source
            ? ` <span class="text-muted" title="No soil sensor is deployed; this is a documented estimate">(${escapeHtml(moistureDetail.source)})</span>`
            : '';
        document.getElementById('weather-info').innerHTML = `
            <div class="mb-1">${sourceBadge}</div>
            <h3 class="fw-bold">${escapeHtml(weather.temperature)}°C</h3>
            <p class="mb-1 text-muted">Humidity: ${escapeHtml(weather.humidity)}%</p>
            <p class="mb-0 text-muted">Soil Moisture: ${escapeHtml(data.soil_moisture)}%${moistureNote}</p>
        `;

        // Populate Disease Risk
        const riskLevel = data.disease_risk.risk_level;
        let riskColor = riskLevel === 'High' ? 'danger' : (riskLevel === 'Medium' ? 'warning' : 'success');
        document.getElementById('disease-risk-info').innerHTML = `
            <span class="badge bg-${riskColor} fs-6 mb-2">${escapeHtml(riskLevel)} Risk</span>
            <p class="mb-1 fw-bold">${escapeHtml(data.disease_risk.message)}</p>
            <p class="mb-0 text-muted">${escapeHtml(data.disease_risk.action)}</p>
        `;

        // Populate Watering
        document.getElementById('watering-rec').innerHTML = `
            <h5 class="fw-bold text-dark">${escapeHtml(data.watering.recommendation)}</h5>
            <p class="mb-2">⚠️ ${escapeHtml(data.watering.reason)}</p>
            <span class="badge bg-light text-dark border">📅 Next scheduled: ${escapeHtml(data.watering.next_scheduled)}</span>
        `;

        // Populate Fertilizing
        document.getElementById('fertilizing-rec').innerHTML = `
            <h5 class="fw-bold text-dark">${escapeHtml(data.fertilizing.recommendation)}</h5>
            <p class="mb-2">📦 Type: ${escapeHtml(data.fertilizing.fertilizer_type)}</p>
            <p class="mb-2">⚠️ ${escapeHtml(data.fertilizing.reason)}</p>
            <span class="badge bg-light text-dark border">📅 Next scheduled: ${escapeHtml(data.fertilizing.next_scheduled)}</span>
        `;
        
    } catch (e) {
        console.error("Error fetching climate data", e);
    }
};

window.sendAlert = async function() {
    if (!window.activeSessionId) return;
    
    // The advisory is always delivered to the signed-in account's own address
    // (the server ignores any client-supplied recipient), so no email prompt is
    // needed any more.
    try {
        const response = await fetch(apiUrl(`/api/sessions/${window.activeSessionId}/notify`), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({})
        });
        
        const data = await response.json();
        if (response.ok) {
            alert("✅ " + data.message);
        } else {
            alert("❌ Failed to send alert: " + (data.detail || 'Unknown error'));
        }
    } catch (e) {
        console.error("Error sending alert", e);
        alert("❌ Error sending alert. Make sure the backend is running.");
    }
};

// ==========================================
// Plant Farm Management Logic
// ==========================================

let selectedManageSessionId = null;

async function loadPlantFarmDashboard() {
    try {
        // Load summary
        const summaryRes = await fetch(apiUrl('/api/dashboard/summary'));
        if (summaryRes.ok) {
            const summary = await summaryRes.json();
            document.getElementById('summary-investment').textContent = "₹" + summary.total_investment;
            document.getElementById('summary-yield').textContent = summary.total_yield + " kg";
            document.getElementById('summary-profit').textContent = "₹" + summary.net_profit;
            document.getElementById('summary-margin').textContent = summary.profit_margin_percent + "%";
        }
        
        // Load sessions list
        const sessionsRes = await fetch(apiUrl('/api/sessions'));
        if (sessionsRes.ok) {
            const sessions = await sessionsRes.json();
            const listEl = document.getElementById('session-list');
            listEl.innerHTML = '';
            
            if (sessions.length === 0) {
                listEl.innerHTML = '<div class="p-3 text-muted text-center">No farming sessions found.</div>';
            }
            
            sessions.forEach(s => {
                const isSelected = s.id === selectedManageSessionId ? 'active' : '';
                const statusBadge = s.is_active 
                    ? '<span class="badge bg-success float-end">Active</span>' 
                    : '<span class="badge bg-secondary float-end">Harvested</span>';
                
                // data-* attributes + a delegated listener instead of an inline
                // onclick: a plot name containing a quote could otherwise break
                // out of the JavaScript string and execute script.
                listEl.insertAdjacentHTML('beforeend', `
                    <button type="button" class="list-group-item list-group-item-action ${isSelected}"
                            data-action="select-plant-session" data-session-id="${s.id}"
                            data-session-name="${escapeHtml(s.plot_name)}" data-active="${s.is_active}">
                        <div class="d-flex w-100 justify-content-between">
                            <h6 class="mb-1 fw-bold">${escapeHtml(s.plot_name)} (${escapeHtml(s.crop_type)})</h6>
                        </div>
                        <small class="text-muted">Area: ${escapeHtml(s.area_cents)} cents | Loc: ${escapeHtml(s.location)}</small>
                        ${statusBadge}
                    </button>
                `);
            });
        }
    } catch (e) {
        console.error("Error loading dashboard", e);
    }
}

window.selectSessionToManage = function(id, name, isActive) {
    selectedManageSessionId = id;
    document.getElementById('no-session-selected').classList.add('d-none');
    document.getElementById('manage-session-card').classList.remove('d-none');
    document.getElementById('manage-session-title').textContent = `Manage: ${name}`;
    
    // Disable inputs if not active
    const formInputs = document.getElementById('daily-log-form').querySelectorAll('input, select, button');
    formInputs.forEach(input => input.disabled = !isActive);
    
    // Disable harvest button if not active
    const harvestBtn = document.querySelector('button[onclick="harvestSession()"]');
    harvestBtn.style.display = isActive ? 'block' : 'none';
    
    // Refresh UI
    loadPlantFarmDashboard();
    loadDailyLogs(id);
};

async function loadDailyLogs(sessionId) {
    try {
        const res = await fetch(apiUrl(`/api/sessions/${sessionId}/daily_logs`));
        const logsEl = document.getElementById('daily-logs-history');
        logsEl.innerHTML = '';
        
        if (res.ok) {
            const logs = await res.json();
            if (logs.length === 0) {
                logsEl.innerHTML = '<li class="list-group-item text-muted text-center">No logs yet.</li>';
                return;
            }
            
            // Show newest first
            logs.reverse().forEach(log => {
                const dateStr = new Date(log.date).toLocaleDateString() + ' ' + new Date(log.date).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
                const weatherStr = `<b>climate 🌤️ :</b> ${escapeHtml(log.weather_condition || 'N/A')}`;
                const wateredStr = `<b>watered 💧 :</b> ${log.watered ? 'Yes' : 'No'}`;
                const waterReasonStr = log.water_reason ? `<b>reason for 💧 :</b> ${escapeHtml(log.water_reason)}` : '';
                const fertStr = `<b>fertilizers :</b> ${log.fertilized ? 'Yes' : 'No'}`;
                const fertKgStr = log.fertilized ? `<b>fertilizer kg :</b> ${escapeHtml(log.fertilizer_amount)} kg used` : '';
                const notesStr = log.notes ? `<b>notes :</b> ${escapeHtml(log.notes)}` : '';

                const details = [weatherStr, wateredStr, waterReasonStr, fertStr, fertKgStr, notesStr].filter(Boolean).join('<br>');
                
                logsEl.innerHTML += `
                    <li class="list-group-item">
                        <small class="fw-bold text-muted border-bottom d-block mb-2 pb-1">${dateStr}</small>
                        <div class="small text-dark lh-lg">
                            ${details}
                        </div>
                    </li>
                `;
            });
        }
    } catch (e) {
        console.error("Error loading logs", e);
    }
}

// Handle New Session Form (Plant Farm)
document.getElementById('new-session-form')?.addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const payload = {
        crop_type: document.getElementById('ns-crop').value,
        plot_name: document.getElementById('ns-plot').value,
        area_cents: parseFloat(document.getElementById('ns-area').value),
        soil_type: document.getElementById('ns-soil').value,
        location: document.getElementById('ns-location').value,
        seed_qty: parseFloat(document.getElementById('ns-seed-qty').value) || 0,
        cost_per_seed: parseFloat(document.getElementById('ns-seed-cost').value) || 0,
        total_land_cost: parseFloat(document.getElementById('ns-land-cost').value) || 0,
        fertilizer_qty: parseFloat(document.getElementById('ns-fert-qty').value) || 0,
        cost_per_fertilizer: parseFloat(document.getElementById('ns-fert-cost').value) || 0
    };
    
    try {
        const response = await fetch(apiUrl('/api/sessions'), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const data = await response.json();
        
        if (response.ok) {
            alert("Session Created Successfully!");
            window.activeSessionId = data.session_id; // Set as active
            
            // Hide modal
            const modal = bootstrap.Modal.getInstance(document.getElementById('newSessionModal'));
            if (modal) modal.hide();
            
            // Reset modal form
            document.getElementById('new-session-form').reset();
            
            // Refresh views
            if (!document.getElementById('plant-farm-view').classList.contains('d-none')) {
                loadPlantFarmDashboard();
            } else {
                showView('climate');
            }
            
            loadPlantFarmDashboard();
            selectSessionToManage(data.session_id, payload.plot_name, true);
        } else {
            alert("Error: " + JSON.stringify(data.detail));
        }
    } catch (error) {
        console.error("Error creating session", error);
        alert("Failed to connect to backend.");
    }
});

// Handle Daily Log Form
document.getElementById('daily-log-form')?.addEventListener('submit', async (e) => {
    e.preventDefault();
    if (!selectedManageSessionId) return;
    
    const payload = {
        watered: document.getElementById('log-watered').value === 'true',
        water_reason: document.getElementById('log-water-reason').value,
        fertilized: document.getElementById('log-fertilized').value === 'true',
        fertilizer_amount: parseFloat(document.getElementById('log-fert-amount').value) || 0,
        weather_condition: document.getElementById('log-weather').value,
        notes: document.getElementById('log-notes').value
    };
    
    try {
        const response = await fetch(apiUrl(`/api/sessions/${selectedManageSessionId}/daily_logs`), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        
        if (response.ok) {
            alert("Daily Log Submitted!");
            document.getElementById('daily-log-form').reset();
            loadDailyLogs(selectedManageSessionId);
            loadPlantFarmDashboard(); // Refresh costs
        }
    } catch (error) {
        console.error("Error submitting log", error);
    }
});

window.harvestSession = async function() {
    if (!selectedManageSessionId) return;
    
    const yieldQty = prompt("Enter total harvested yield (in kg):");
    if (yieldQty === null) return;
    
    const marketPrice = prompt("Enter market price per kg (in ₹):");
    if (marketPrice === null) return;
    
    const payload = {
        harvest_yield: parseFloat(yieldQty) || 0,
        market_price: parseFloat(marketPrice) || 0
    };
    
    try {
        const response = await fetch(apiUrl(`/api/sessions/${selectedManageSessionId}/harvest`), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        
        if (response.ok) {
            alert("🎉 Session Harvested & Completed Successfully!");
            loadPlantFarmDashboard();
            selectSessionToManage(selectedManageSessionId, document.getElementById('manage-session-title').textContent.replace('Manage: ', ''), false);
        }
    } catch (error) {
        console.error("Error harvesting", error);
    }
};

// ==========================================
// Plant Dash (Analytics) Logic
// ==========================================

let costChartInst = null;
let invRevChartInst = null;
let profitChartInst = null;
let scatterChartInst = null;
let cropDistributionChartInst = null;
let resourceTimelineChartInst = null;

async function loadAnalyticsDashboard(sessionId = null) {
    try {
        const url = sessionId 
            ? apiUrl(`/api/dashboard/analytics?session_id=${sessionId}`)
            : apiUrl('/api/dashboard/analytics');
        const res = await fetch(url);
        if (!res.ok) return;
        const data = await res.json();
        
        // 1. Cost Breakdown (Doughnut)
        const ctxCost = document.getElementById('costBreakdownChart').getContext('2d');
        if (costChartInst) costChartInst.destroy();
        costChartInst = new Chart(ctxCost, {
            type: 'doughnut',
            data: {
                labels: data.cost_breakdown.labels,
                datasets: [{
                    data: data.cost_breakdown.data,
                    backgroundColor: ['#28a745', '#17a2b8', '#ffc107']
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { position: 'bottom' },
                    tooltip: {
                        callbacks: {
                            label: function(context) { return ' ₹' + context.parsed; }
                        }
                    }
                }
            }
        });
        
        // Prepare data for session charts
        const labels = data.session_performance.map(s => s.plot_name);
        const invData = data.session_performance.map(s => s.investment);
        const revData = data.session_performance.map(s => s.revenue);
        const profData = data.session_performance.map(s => s.profit);
        
        // 2. Investment vs Revenue (Bar)
        const ctxInvRev = document.getElementById('invRevChart').getContext('2d');
        if (invRevChartInst) invRevChartInst.destroy();
        invRevChartInst = new Chart(ctxInvRev, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [
                    { label: 'Investment (₹)', data: invData, backgroundColor: '#dc3545' },
                    { label: 'Revenue (₹)', data: revData, backgroundColor: '#28a745' }
                ]
            },
            options: { responsive: true, maintainAspectRatio: false, scales: { y: { beginAtZero: true } } }
        });
        
        // 3. Profit (Bar/Line)
        const ctxProf = document.getElementById('profitChart').getContext('2d');
        if (profitChartInst) profitChartInst.destroy();
        profitChartInst = new Chart(ctxProf, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Net Profit (₹)',
                    data: profData,
                    backgroundColor: profData.map(p => p >= 0 ? '#198754' : '#dc3545')
                }]
            },
            options: { responsive: true, maintainAspectRatio: false, scales: { y: { beginAtZero: true } } }
        });
        
        // 4. Scatter Chart (Investment vs Profit)
        const scatterData = data.session_performance.map(s => ({
            x: s.investment,
            y: s.profit,
            plot: s.plot_name
        }));
        
        const ctxScatter = document.getElementById('scatterChart').getContext('2d');
        if (scatterChartInst) scatterChartInst.destroy();
        scatterChartInst = new Chart(ctxScatter, {
            type: 'scatter',
            data: {
                datasets: [{
                    label: 'Efficiency',
                    data: scatterData,
                    backgroundColor: '#6f42c1',
                    pointRadius: 6,
                    pointHoverRadius: 8
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    x: { title: { display: true, text: 'Total Investment (₹)' } },
                    y: { title: { display: true, text: 'Net Profit (₹)' } }
                },
                plugins: {
                    tooltip: {
                        callbacks: {
                            label: function(ctx) {
                                const pt = ctx.raw;
                                return `${pt.plot} - Inv: ₹${pt.x}, Profit: ₹${pt.y}`;
                            }
                        }
                    }
                }
            }
        });
        
        // 5. Populate Leaderboard (Already sorted descending by revenue in backend)
        const boardEl = document.getElementById('revenue-leaderboard');
        boardEl.innerHTML = '';
        
        if (data.session_performance.length === 0) {
            boardEl.innerHTML = '<li class="list-group-item text-center text-muted py-4">No completed sessions yet.</li>';
        } else {
            data.session_performance.forEach((s, index) => {
                let badge = '';
                if (index === 0) badge = '🥇';
                else if (index === 1) badge = '🥈';
                else if (index === 2) badge = '🥉';
                else badge = `<span class="badge bg-secondary rounded-pill">${index + 1}</span>`;
                
                boardEl.innerHTML += `
                    <li class="list-group-item d-flex justify-content-between align-items-center">
                        <div>
                            <span class="me-2 fs-5">${badge}</span>
                            <strong>${escapeHtml(s.plot_name)}</strong>
                        </div>
                        <span class="text-success fw-bold">₹${escapeHtml(s.revenue)}</span>
                    </li>
                `;
            });
        }
        
        // 6. Crop Distribution (Doughnut)
        const ctxCropDist = document.getElementById('cropDistributionChart').getContext('2d');
        if (cropDistributionChartInst) cropDistributionChartInst.destroy();
        cropDistributionChartInst = new Chart(ctxCropDist, {
            type: 'doughnut',
            data: {
                labels: data.crop_distribution.labels,
                datasets: [{
                    data: data.crop_distribution.data,
                    backgroundColor: ['#28a745', '#1cc88a', '#36b9cc', '#4e73df', '#f6c23e', '#e74a3b']
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { position: 'right' }
                }
            }
        });

        // 7. Resource Timeline (Line)
        const ctxTimeline = document.getElementById('resourceTimelineChart').getContext('2d');
        if (resourceTimelineChartInst) resourceTimelineChartInst.destroy();
        resourceTimelineChartInst = new Chart(ctxTimeline, {
            type: 'line',
            data: {
                labels: data.resource_timeline.dates,
                datasets: [
                    {
                        label: 'Water Events',
                        data: data.resource_timeline.water,
                        borderColor: '#36b9cc',
                        backgroundColor: 'rgba(54, 185, 204, 0.2)',
                        fill: true,
                        tension: 0.4,
                        yAxisID: 'y'
                    },
                    {
                        label: 'Fertilizer Cost (₹)',
                        data: data.resource_timeline.fertilizer,
                        borderColor: '#f6c23e',
                        backgroundColor: 'rgba(246, 194, 62, 0.2)',
                        fill: true,
                        tension: 0.4,
                        yAxisID: 'y1'
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        type: 'linear',
                        display: true,
                        position: 'left',
                        title: { display: true, text: 'Water Events' },
                        beginAtZero: true,
                        ticks: { stepSize: 1 }
                    },
                    y1: {
                        type: 'linear',
                        display: true,
                        position: 'right',
                        title: { display: true, text: 'Fertilizer Cost (₹)' },
                        beginAtZero: true,
                        grid: { drawOnChartArea: false }
                    }
                }
            }
        });
    } catch (e) {
        console.error("Error loading analytics:", e);
    }
}

// ==========================================
// Language Translation Logic
// ==========================================

window.changeLanguage = function(langCode) {
    const selectField = document.querySelector(".goog-te-combo");
    if (!selectField) {
        console.error("Google Translate widget not fully loaded yet.");
        alert("Translation is still loading... Please try again in a few seconds.");
        return;
    }
    
    selectField.value = langCode;
    selectField.dispatchEvent(new Event('change', { bubbles: true, cancelable: true }));
};

// ==========================================
// View Management
// ==========================================

// ==========================================
// Animal Farm Logic
// ==========================================

let selectedAnimalSessionId = null;

async function loadAnimalDashboard() {
    try {
        const summaryRes = await fetch(apiUrl('/api/animals/dashboard/summary'));
        if (summaryRes.ok) {
            const summary = await summaryRes.json();
            document.getElementById('animal-summary-investment').textContent = "₹" + summary.total_investment;
            document.getElementById('animal-summary-yield').textContent = summary.total_yield;
            document.getElementById('animal-summary-sales').textContent = "₹" + summary.total_revenue;
            document.getElementById('animal-summary-profit').textContent = "₹" + summary.net_profit;
            document.getElementById('animal-summary-margin').textContent = summary.profit_margin_percent + "%";
        }
        
        const sessionsRes = await fetch(apiUrl('/api/animals'));
        if (sessionsRes.ok) {
            const sessions = await sessionsRes.json();
            const listEl = document.getElementById('animal-session-list');
            listEl.innerHTML = '';
            
            if (sessions.length === 0) {
                listEl.innerHTML = '<div class="p-3 text-muted text-center">No animal sessions found.</div>';
            }
            
            sessions.forEach(s => {
                const isSelected = s.id === selectedAnimalSessionId ? 'active' : '';
                const statusBadge = s.is_active 
                    ? '<span class="badge bg-success float-end">Active</span>' 
                    : '<span class="badge bg-secondary float-end">Completed</span>';
                
                listEl.insertAdjacentHTML('beforeend', `
                    <button type="button" class="list-group-item list-group-item-action ${isSelected}"
                            data-action="select-animal-session" data-session-id="${s.id}"
                            data-session-name="${escapeHtml(s.session_name)}" data-active="${s.is_active}">
                        <div class="d-flex w-100 justify-content-between">
                            <h6 class="mb-1 fw-bold">${escapeHtml(s.session_name)} (${escapeHtml(s.animal_type)})</h6>
                        </div>
                        <small class="text-muted">Count: ${escapeHtml(s.animal_count)}</small>
                        ${statusBadge}
                    </button>
                `);
            });
        }
    } catch (e) {
        console.error("Error loading animal dashboard", e);
    }
}

window.selectAnimalSessionToManage = function(id, name, isActive) {
    selectedAnimalSessionId = id;
    document.getElementById('animal-no-session-selected').classList.add('d-none');
    document.getElementById('manage-animal-session-card').classList.remove('d-none');
    document.getElementById('manage-animal-session-title').textContent = `Manage: ${name}`;
    
    const formInputs = document.getElementById('animal-daily-log-form').querySelectorAll('input, select, button');
    formInputs.forEach(input => input.disabled = !isActive);
    
    const closeBtn = document.querySelector('button[onclick="closeAnimalSession()"]');
    closeBtn.style.display = isActive ? 'block' : 'none';
    
    loadAnimalDashboard();
    loadAnimalDailyLogs(id);
};

async function loadAnimalDailyLogs(sessionId) {
    try {
        const res = await fetch(apiUrl(`/api/animals/${sessionId}/daily_logs`));
        const logsEl = document.getElementById('animal-daily-logs-history');
        logsEl.innerHTML = '';
        
        if (res.ok) {
            const logs = await res.json();
            if (logs.length === 0) {
                logsEl.innerHTML = '<li class="list-group-item text-muted text-center">No logs yet.</li>';
                return;
            }
            
            logs.reverse().forEach(log => {
                const dateStr = new Date(log.date).toLocaleDateString() + ' ' + new Date(log.date).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
                
                const foodStr = `<b>Food 📦:</b> ${escapeHtml(log.food_given_qty)} kg (₹${escapeHtml(log.food_cost_today)})`;
                const yieldStr = log.yield_amount > 0 ? `<b>Yield 🥛/🥚:</b> ${escapeHtml(log.yield_amount)} @ ₹${escapeHtml(log.yield_selling_price)} (Total: ₹${escapeHtml(log.yield_amount * log.yield_selling_price)})` : '';
                const medStr = log.medicine_given ? `<b>Medicine 💊:</b> Yes - ${escapeHtml(log.medicine_name)} (₹${escapeHtml(log.medicine_cost)}) - ${escapeHtml(log.medicine_reason)}` : `<b>Medicine 💊:</b> No`;
                const deathStr = log.deaths_today > 0 ? `<b>Deaths ☠️:</b> ${escapeHtml(log.deaths_today)}` : '';
                const notesStr = log.notes ? `<b>Notes:</b> ${escapeHtml(log.notes)}` : '';

                const details = [foodStr, yieldStr, medStr, deathStr, notesStr].filter(Boolean).join('<br>');
                
                logsEl.innerHTML += `
                    <li class="list-group-item">
                        <small class="fw-bold text-muted border-bottom d-block mb-2 pb-1">${dateStr}</small>
                        <div class="small text-dark lh-lg">
                            ${details}
                        </div>
                    </li>
                `;
            });
        }
    } catch (e) {
        console.error("Error loading animal logs", e);
    }
}

document.getElementById('new-animal-session-form')?.addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const payload = {
        animal_type: document.getElementById('nas-type').value,
        session_name: document.getElementById('nas-name').value,
        animal_count: parseInt(document.getElementById('nas-count').value) || 0,
        cost_per_animal: parseFloat(document.getElementById('nas-cost').value) || 0,
        initial_food_qty: parseFloat(document.getElementById('nas-food-qty').value) || 0,
        cost_per_food_qty: parseFloat(document.getElementById('nas-food-cost').value) || 0,
        medicine_cost: parseFloat(document.getElementById('nas-med-cost').value) || 0,
        shelter_cost: parseFloat(document.getElementById('nas-shelter-cost').value) || 0
    };
    
    try {
        const response = await fetch(apiUrl('/api/animals'), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const data = await response.json();
        
        if (response.ok) {
            alert("Animal Session Started!");
            const modal = bootstrap.Modal.getInstance(document.getElementById('newAnimalSessionModal'));
            if (modal) modal.hide();
            document.getElementById('new-animal-session-form').reset();
            
            loadAnimalDashboard();
            selectAnimalSessionToManage(data.session_id, payload.session_name, true);
        } else {
            alert("Error: " + JSON.stringify(data.detail));
        }
    } catch (error) {
        console.error("Error creating animal session", error);
    }
});

document.getElementById('animal-daily-log-form')?.addEventListener('submit', async (e) => {
    e.preventDefault();
    if (!selectedAnimalSessionId) return;
    
    const payload = {
        food_given_qty: parseFloat(document.getElementById('animal-log-food').value) || 0,
        food_cost_today: parseFloat(document.getElementById('animal-log-food-cost').value) || 0,
        yield_amount: parseFloat(document.getElementById('animal-log-yield').value) || 0,
        yield_selling_price: parseFloat(document.getElementById('animal-log-yield-price').value) || 0,
        medicine_given: document.getElementById('animal-log-medicine').value === 'true',
        medicine_name: document.getElementById('animal-log-med-name').value,
        medicine_cost: parseFloat(document.getElementById('animal-log-med-cost').value) || 0,
        medicine_reason: document.getElementById('animal-log-med-reason').value,
        deaths_today: parseInt(document.getElementById('animal-log-deaths').value) || 0,
        notes: document.getElementById('animal-log-notes').value
    };
    
    try {
        const response = await fetch(apiUrl(`/api/animals/${selectedAnimalSessionId}/daily_logs`), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        
        if (response.ok) {
            alert("Animal Daily Log Submitted!");
            document.getElementById('animal-daily-log-form').reset();
            document.getElementById('animal-log-med-details').classList.add('d-none');
            loadAnimalDailyLogs(selectedAnimalSessionId);
            loadAnimalDashboard(); 
        }
    } catch (error) {
        console.error("Error submitting animal log", error);
    }
});

window.closeAnimalSession = function() {
    if (!selectedAnimalSessionId) return;
    const modal = new bootstrap.Modal(document.getElementById('closeAnimalSessionModal'));
    modal.show();
};

document.getElementById('close-animal-session-form')?.addEventListener('submit', async (e) => {
    e.preventDefault();
    if (!selectedAnimalSessionId) return;
    
    const payload = {
        animals_sold: parseInt(document.getElementById('cas-animals-sold').value) || 0,
        sell_price_per_animal: parseFloat(document.getElementById('cas-animal-price').value) || 0
    };
    
    try {
        const response = await fetch(apiUrl(`/api/animals/${selectedAnimalSessionId}/close`), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        
        if (response.ok) {
            alert("🐾 Session Closed Successfully!");
            const modal = bootstrap.Modal.getInstance(document.getElementById('closeAnimalSessionModal'));
            if (modal) modal.hide();
            document.getElementById('close-animal-session-form').reset();
            
            loadAnimalDashboard();
            selectAnimalSessionToManage(selectedAnimalSessionId, document.getElementById('manage-animal-session-title').textContent.replace('Manage: ', ''), false);
        }
    } catch (error) {
        console.error("Error closing animal session", error);
    }
});

// ==========================================
// Animal Analytics Dashboard Logic
// ==========================================

let animalCostChartInstance = null;
let animalEfficiencyChartInstance = null;
let animalProfitChartInstance = null;
let animalDistributionChartInstance = null;
let animalTimelineChartInstance = null;

async function loadAnimalAnalyticsDashboard(sessionId = null) {
    try {
        const url = sessionId 
            ? apiUrl(`/api/animals/dashboard/analytics?session_id=${sessionId}`)
            : apiUrl('/api/animals/dashboard/analytics');
        const res = await fetch(url);
        if (res.ok) {
            const data = await res.json();
            renderAnimalCostBreakdownChart(data.cost_breakdown);
            renderAnimalEfficiencyScatterChart(data.session_performance);
            renderAnimalProfitBarChart(data.session_performance);
            renderAnimalHighYieldBoard(data.session_performance);
            
            if (data.animal_distribution) renderAnimalDistributionChart(data.animal_distribution);
            if (data.resource_timeline) renderAnimalTimelineChart(data.resource_timeline);
        }
    } catch (e) {
        console.error("Error loading animal analytics:", e);
    }
}

function renderAnimalCostBreakdownChart(costData) {
    const ctx = document.getElementById('animalCostBreakdownChart').getContext('2d');
    if (animalCostChartInstance) animalCostChartInstance.destroy();
    
    animalCostChartInstance = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: costData.labels,
            datasets: [{
                data: costData.data,
                backgroundColor: ['#f6c23e', '#1cc88a', '#36b9cc', '#4e73df'],
                hoverOffset: 4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { position: 'right' }
            }
        }
    });
}

function renderAnimalEfficiencyScatterChart(sessions) {
    const ctx = document.getElementById('animalEfficiencyScatterChart').getContext('2d');
    if (animalEfficiencyChartInstance) animalEfficiencyChartInstance.destroy();
    
    const maxProfit = Math.max(...sessions.map(s => Math.abs(s.profit)), 1);
    const scatterData = sessions.map(s => ({
        x: s.investment,
        y: s.revenue,
        r: 5 + (Math.max(0, s.profit) / maxProfit) * 20
    }));

    animalEfficiencyChartInstance = new Chart(ctx, {
        type: 'bubble',
        data: {
            datasets: [{
                label: 'Livestock Sessions',
                data: scatterData,
                backgroundColor: 'rgba(78, 115, 223, 0.6)',
                borderColor: '#4e73df'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                x: { title: { display: true, text: 'Total Investment (₹)' } },
                y: { title: { display: true, text: 'Total Revenue (₹)' } }
            },
            plugins: {
                tooltip: {
                    callbacks: {
                        label: (context) => {
                            const idx = context.dataIndex;
                            return `${sessions[idx].plot_name}: Invest ₹${sessions[idx].investment}, Rev ₹${sessions[idx].revenue}`;
                        }
                    }
                }
            }
        }
    });
}

function renderAnimalProfitBarChart(sessions) {
    const ctx = document.getElementById('animalProfitBarChart').getContext('2d');
    if (animalProfitChartInstance) animalProfitChartInstance.destroy();
    
    animalProfitChartInstance = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: sessions.map(s => s.plot_name),
            datasets: [{
                label: 'Net Profit (₹)',
                data: sessions.map(s => s.profit),
                backgroundColor: sessions.map(s => s.profit >= 0 ? '#1cc88a' : '#e74a3b'),
                borderRadius: 4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: { y: { beginAtZero: true } }
        }
    });
}

function renderAnimalHighYieldBoard(sessions) {
    const listEl = document.getElementById('animal-leaderboard-list');
    listEl.innerHTML = '';
    
    if (sessions.length === 0) {
        listEl.innerHTML = '<li class="list-group-item text-center text-muted">No completed sessions yet.</li>';
        return;
    }
    
    const medals = ['🥇', '🥈', '🥉'];
    
    sessions.forEach((s, index) => {
        const medal = index < 3 ? `<span class="fs-4 me-2">${medals[index]}</span>` : `<span class="fs-5 me-3 ms-2 fw-bold text-muted">#${index+1}</span>`;
        
        listEl.innerHTML += `
            <li class="list-group-item d-flex justify-content-between align-items-center py-3 border-bottom border-light">
                <div class="d-flex align-items-center">
                    ${medal}
                    <div>
                        <h6 class="mb-0 fw-bold">${escapeHtml(s.plot_name)}</h6>
                        <small class="text-muted">Yield: ${escapeHtml(s.total_yield)} units</small>
                    </div>
                </div>
                <div class="text-end">
                    <div class="fw-bold text-success">₹${escapeHtml(s.profit)}</div>
                    <small class="text-muted">Profit</small>
                </div>
            </li>
        `;
    });
}

function renderAnimalDistributionChart(distData) {
    const ctx = document.getElementById('animalDistributionChart').getContext('2d');
    if (animalDistributionChartInstance) animalDistributionChartInstance.destroy();
    
    animalDistributionChartInstance = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: distData.labels,
            datasets: [{
                data: distData.data,
                backgroundColor: ['#e74a3b', '#f6c23e', '#1cc88a', '#36b9cc', '#4e73df'],
                hoverOffset: 4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { position: 'right' }
            }
        }
    });
}

function renderAnimalTimelineChart(timelineData) {
    const ctx = document.getElementById('animalTimelineChart').getContext('2d');
    if (animalTimelineChartInstance) animalTimelineChartInstance.destroy();
    
    animalTimelineChartInstance = new Chart(ctx, {
        type: 'line',
        data: {
            labels: timelineData.dates,
            datasets: [
                {
                    label: 'Cumulative Yield',
                    data: timelineData.yield,
                    borderColor: '#1cc88a',
                    backgroundColor: 'rgba(28, 200, 138, 0.2)',
                    fill: true,
                    tension: 0.4,
                    yAxisID: 'y'
                },
                {
                    label: 'Cumulative Food Cost (₹)',
                    data: timelineData.food_cost,
                    borderColor: '#f6c23e',
                    backgroundColor: 'rgba(246, 194, 62, 0.2)',
                    fill: true,
                    tension: 0.4,
                    yAxisID: 'y1'
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: {
                    type: 'linear',
                    display: true,
                    position: 'left',
                    title: { display: true, text: 'Cumulative Yield' },
                    beginAtZero: true
                },
                y1: {
                    type: 'linear',
                    display: true,
                    position: 'right',
                    title: { display: true, text: 'Cumulative Food Cost (₹)' },
                    beginAtZero: true,
                    grid: { drawOnChartArea: false }
                }
            }
        }
    });
}

// ==========================================
// Market Intelligence Logic
// ==========================================

async function loadMarketIntelligence() {
    try {
        const response = await fetch(apiUrl('/api/market/intelligence'));
        if (response.ok) {
            const data = await response.json();
            renderMarketCommodities(data.market_data);
            renderMarketRecommendations(data.recommendations);
            renderMarketNews(data.news_feed);
        }
    } catch (e) {
        console.error("Error loading market intelligence:", e);
        document.getElementById('market-commodities-container').innerHTML = `
            <div class="alert alert-danger">Unable to load market data. Ensure backend is running.</div>
        `;
    }
}

function renderMarketCommodities(marketData) {
    const container = document.getElementById('market-commodities-container');
    container.innerHTML = '';
    
    if (!marketData || marketData.length === 0) {
        container.innerHTML = '<div class="alert alert-info">No farm sessions found. Start a plant or animal session to see market data!</div>';
        return;
    }
    
    let html = '<div class="row">';
    
    marketData.forEach(item => {
        const trendClass = item.trend_perc > 0 ? 'text-success' : 'text-danger';
        const trendIcon = item.trend_perc > 0 ? '↑' : '↓';
        const mandiRows = item.mandis.map(m => `
            <div class="d-flex justify-content-between small border-bottom py-1">
                <span>${escapeHtml(m.location)} <span class="text-muted">(${escapeHtml(m.distance)})</span></span>
                <span class="fw-bold">₹${escapeHtml(m.price)}/${escapeHtml(item.unit)}</span>
            </div>
        `).join('');
        
        html += `
        <div class="col-md-6 mb-4">
            <div class="card shadow-sm border-0 h-100">
                <div class="card-header bg-white border-0 pt-4 pb-0">
                    <h5 class="card-title fw-bold">${escapeHtml(item.commodity)} Market <span class="badge bg-secondary ms-2">${escapeHtml(item.plot)}</span></h5>
                </div>
                <div class="card-body">
                    <div class="row mb-3">
                        <div class="col-6">
                            <p class="text-muted mb-1 small">Local Price <span class="badge bg-warning text-dark">simulated</span></p>
                            <h3 class="fw-bold mb-0">₹${escapeHtml(item.current_price)}<span class="fs-6 text-muted">/${escapeHtml(item.unit)}</span></h3>
                        </div>
                        <div class="col-6 text-end">
                            <p class="text-muted mb-1 small">7-Day Trend <span class="badge bg-warning text-dark">simulated</span></p>
                            <h4 class="${trendClass} mb-0">${trendIcon} ${escapeHtml(Math.abs(item.trend_perc))}%</h4>
                        </div>
                    </div>
                    
                    <div class="d-flex justify-content-between mb-3 bg-light rounded p-2">
                        <div class="text-center w-50 border-end">
                            <small class="text-muted d-block">State Avg</small>
                            <span class="fw-bold">₹${escapeHtml(item.state_avg)}</span>
                        </div>
                        <div class="text-center w-50">
                            <small class="text-muted d-block">National Avg</small>
                            <span class="fw-bold">₹${escapeHtml(item.national_avg)}</span>
                        </div>
                    </div>
                    
                    <h6 class="fw-bold mt-4 mb-2">Nearby Mandis / Auctions <span class="badge bg-warning text-dark">simulated</span></h6>
                    ${mandiRows}
                    
                    <div class="alert alert-warning mt-3 mb-0 p-2 text-center">
                        <strong>Scenario Projection (7 Days, simulated):</strong> Expected ₹${escapeHtml(item.forecast_price)}/${escapeHtml(item.unit)}
                    </div>
                </div>
            </div>
        </div>
        `;
    });
    
    html += '</div>';
    container.innerHTML = html;
}

function renderMarketRecommendations(recommendations) {
    const listEl = document.getElementById('market-recommendations-list');
    listEl.innerHTML = '';
    
    if (!recommendations || recommendations.length === 0) {
        listEl.innerHTML = '<p class="text-muted">No recommendations available at this time.</p>';
        return;
    }
    
    recommendations.forEach(rec => {
        listEl.innerHTML += `
            <div class="border rounded p-3 mb-3 bg-white shadow-sm">
                <h6 class="fw-bold text-dark mb-2">${escapeHtml(rec.title)}</h6>
                <div class="d-flex justify-content-between small mb-1">
                    <span class="text-muted">Current: <strong class="text-dark">${escapeHtml(rec.current_price)}</strong></span>
                    <span class="text-muted">Scenario: <strong class="text-success">${escapeHtml(rec.forecast_price)}</strong></span>
                </div>
                <div class="small mb-2">
                    <span class="text-muted">Best Location:</span> <span class="fw-bold">${escapeHtml(rec.best_location)}</span>
                </div>
                <div class="alert alert-success p-2 mb-0 mt-2 small text-center fw-bold">
                    Action: ${escapeHtml(rec.action)}
                </div>
            </div>
        `;
    });
}

function renderMarketNews(newsFeed) {
    const listEl = document.getElementById('market-news-list');
    listEl.innerHTML = '';
    
    if (!newsFeed || newsFeed.length === 0) {
        listEl.innerHTML = '<p class="text-muted text-center py-4">No recent news for your commodities.</p>';
        return;
    }
    
    newsFeed.forEach(news => {
        const badgeColor = news.headline.includes('rising') ? 'bg-success' : 'bg-danger';
        listEl.innerHTML += `
            <div class="p-3 border rounded bg-light">
                <div class="d-flex justify-content-between align-items-start mb-2">
                    <span class="badge ${badgeColor}">${news.commodity}</span>
                    <small class="text-muted">${news.source}</small>
                </div>
                <h6 class="fw-bold mb-2">${news.headline}</h6>
                <p class="small text-muted mb-2"><strong>Reason:</strong> ${news.reason}</p>
                <div class="d-flex justify-content-between small mt-3 pt-2 border-top">
                    <span class="text-primary"><i class="bi bi-graph-up"></i> ${news.forecast}</span>
                    <span class="fw-bold text-dark"><i class="bi bi-check-circle-fill text-success"></i> ${news.recommendation}</span>
                </div>
            </div>
        `;
    });
}


// ==========================================
// UNIFIED FARM DASHBOARD LOGIC
// ==========================================

let globalPlantPerformance = [];
let globalAnimalPerformance = [];

window.loadUnifiedDashboard = async function() {
    // Fetch both plant and animal sessions and performance
    try {
        const [plantsRes, animalsRes, plantDashRes, animalDashRes] = await Promise.all([
            fetch(apiUrl('/api/sessions')),
            fetch(apiUrl('/api/animals')),
            fetch(apiUrl('/api/dashboard/analytics')),
            fetch(apiUrl('/api/animals/dashboard/analytics'))
        ]);
        
        let plants = [];
        let animals = [];
        
        if (plantsRes.ok) plants = await plantsRes.json();
        if (animalsRes.ok) animals = await animalsRes.json();
        
        if (plantDashRes.ok) {
            const pData = await plantDashRes.json();
            globalPlantPerformance = pData.session_performance || [];
        }
        if (animalDashRes.ok) {
            const aData = await animalDashRes.json();
            globalAnimalPerformance = aData.session_performance || [];
        }
        
        // Populate Plant List
        const plantList = document.getElementById('unified-plant-session-list');
        plantList.innerHTML = `<button class="list-group-item list-group-item-action fw-bold text-success" onclick="showUnifiedAggregate('plant')">📊 Overall Plant Analytics</button>`;
        
        plants.forEach(s => {
            const status = s.is_active ? '✅ Active' : '🏁 Ended';
            plantList.insertAdjacentHTML('beforeend', `
                <button type="button" class="list-group-item list-group-item-action"
                        data-action="unified-session" data-session-type="plant" data-session-id="${s.id}"
                        data-session-name="${escapeHtml(s.plot_name)}" data-active="${s.is_active}">
                    <div class="d-flex justify-content-between">
                        <span>${escapeHtml(s.plot_name)}</span>
                        <small class="text-muted">${status}</small>
                    </div>
                </button>
            `);
        });
        
        // Populate Animal List
        const animalList = document.getElementById('unified-animal-session-list');
        animalList.innerHTML = `<button class="list-group-item list-group-item-action fw-bold text-primary" onclick="showUnifiedAggregate('animal')">📈 Overall Animal Analytics</button>`;
        
        animals.forEach(s => {
            const status = s.is_active ? '✅ Active' : '🏁 Ended';
            animalList.insertAdjacentHTML('beforeend', `
                <button type="button" class="list-group-item list-group-item-action"
                        data-action="unified-session" data-session-type="animal" data-session-id="${s.id}"
                        data-session-name="${escapeHtml(s.session_name)}" data-active="${s.is_active}">
                    <div class="d-flex justify-content-between">
                        <span>${escapeHtml(s.session_name)}</span>
                        <small class="text-muted">${status}</small>
                    </div>
                </button>
            `);
        });
        
    } catch (e) {
        console.error("Error loading unified dashboard", e);
    }
};

window.showUnifiedAggregate = function(type) {
    const contentArea = document.getElementById('unified-content-area');
    contentArea.innerHTML = '';
    
    const view = document.getElementById('analysis-dashboard-view');
    if (view) {
        contentArea.appendChild(view);
        view.classList.remove('d-none');
        switchAnalyticsTab(type);
    }
};

window.showUnifiedSession = function(type, id, name, isActive) {
    const contentArea = document.getElementById('unified-content-area');
    contentArea.innerHTML = '';
    
    // Inject Session Performance Stats block dynamically
    let perf = null;
    let statsHtml = '';
    
    if (type === 'plant') {
        perf = globalPlantPerformance.find(p => p.session_id === id);
        if (perf) {
            statsHtml = `
            <div class="row mb-4">
                <div class="col-md-4"><div class="card bg-danger text-white"><div class="card-body py-2 text-center"><h6>Investment</h6><h4 class="mb-0">₹${perf.investment}</h4></div></div></div>
                <div class="col-md-4"><div class="card bg-success text-white"><div class="card-body py-2 text-center"><h6>Revenue</h6><h4 class="mb-0">₹${perf.revenue}</h4></div></div></div>
                <div class="col-md-4"><div class="card ${perf.profit >= 0 ? 'bg-primary' : 'bg-warning text-dark'} text-white"><div class="card-body py-2 text-center"><h6>Net Profit</h6><h4 class="mb-0">₹${perf.profit}</h4></div></div></div>
            </div>`;
        }
        
        const view = document.getElementById('manage-session-card');
        
        // Wrap in a div to include stats
        const wrapper = document.createElement('div');
        wrapper.innerHTML = statsHtml;
        wrapper.appendChild(view);
        
        contentArea.appendChild(wrapper);
        view.classList.remove('d-none');
        selectSessionToManage(id, name, isActive);
        
    } else {
        perf = globalAnimalPerformance.find(p => p.session_id === id);
        if (perf) {
            statsHtml = `
            <div class="row mb-4">
                <div class="col-md-4"><div class="card bg-danger text-white"><div class="card-body py-2 text-center"><h6>Investment</h6><h4 class="mb-0">₹${perf.investment}</h4></div></div></div>
                <div class="col-md-4"><div class="card bg-success text-white"><div class="card-body py-2 text-center"><h6>Revenue</h6><h4 class="mb-0">₹${perf.revenue}</h4></div></div></div>
                <div class="col-md-4"><div class="card ${perf.profit >= 0 ? 'bg-primary' : 'bg-warning text-dark'} text-white"><div class="card-body py-2 text-center"><h6>Net Profit</h6><h4 class="mb-0">₹${perf.profit}</h4></div></div></div>
            </div>`;
        }
        
        const view = document.getElementById('manage-animal-session-card');
        
        const wrapper = document.createElement('div');
        wrapper.innerHTML = statsHtml;
        wrapper.appendChild(view);
        
        contentArea.appendChild(wrapper);
        view.classList.remove('d-none');
        selectAnimalSessionToManage(id, name, isActive);
    }
};




window.loadAnalyticsSidebar = async function() {
    const sidebarLink = (type, session, icon) => `
        <a href="#" class="list-group-item list-group-item-action ps-4"
           data-action="filter-analytics" data-session-type="${type}" data-session-id="${session.id}">
            ${icon} ${escapeHtml(type === 'plant' ? session.plot_name : session.session_name)}
        </a>`;

    try {
        const plantRes = await fetch(apiUrl('/api/sessions'));
        if (plantRes.ok) {
            const plantSessions = await plantRes.json();
            const activePlant = plantSessions.filter(s => s.is_active);
            const completedPlant = plantSessions.filter(s => !s.is_active);
            document.getElementById('analytics-plant-active').innerHTML = activePlant.map(s => sidebarLink('plant', s, '🌱')).join('');
            document.getElementById('analytics-plant-completed').innerHTML = completedPlant.map(s => sidebarLink('plant', s, '🌱')).join('');
        }
        
        const animalRes = await fetch(apiUrl('/api/animals'));
        if (animalRes.ok) {
            const animalSessions = await animalRes.json();
            const activeAnimal = animalSessions.filter(s => s.is_active);
            const completedAnimal = animalSessions.filter(s => !s.is_active);
            document.getElementById('analytics-animal-active').innerHTML = activeAnimal.map(s => sidebarLink('animal', s, '🐾')).join('');
            document.getElementById('analytics-animal-completed').innerHTML = completedAnimal.map(s => sidebarLink('animal', s, '🐾')).join('');
        }
    } catch (e) {
        console.error("Error loading analytics sidebar", e);
    }
};

/**
 * Delegated click handler for the session lists.
 *
 * Version 1 built inline onclick="fn(id, 'plot name')" strings. A plot name
 * containing an apostrophe terminated the JavaScript string and the remainder of
 * the name was executed as code (stored XSS). The lists now carry data-*
 * attributes and every action is dispatched from here, so user data is only ever
 * read as a value, never as code.
 */
document.addEventListener('click', event => {
    const trigger = event.target.closest('[data-action]');
    if (!trigger) return;

    const action = trigger.getAttribute('data-action');
    const sessionId = parseInt(trigger.getAttribute('data-session-id'), 10);
    const sessionName = trigger.getAttribute('data-session-name') || '';
    const isActive = trigger.getAttribute('data-active') === 'true';
    const sessionType = trigger.getAttribute('data-session-type') || 'plant';

    switch (action) {
        case 'select-plant-session':
            if (typeof selectSessionToManage === 'function') {
                selectSessionToManage(sessionId, sessionName, isActive);
            }
            break;
        case 'select-animal-session':
            if (typeof selectAnimalSessionToManage === 'function') {
                selectAnimalSessionToManage(sessionId, sessionName, isActive);
            }
            break;
        case 'unified-session':
            if (typeof showUnifiedSession === 'function') {
                showUnifiedSession(sessionType, sessionId, sessionName, isActive);
            }
            break;
        case 'filter-analytics':
            event.preventDefault();
            if (typeof filterAnalyticsSession === 'function') {
                filterAnalyticsSession(sessionType, sessionId, trigger);
            }
            break;
        default:
            break;
    }
});

window.filterAnalyticsSession = function(type, sessionId, element) {
    document.getElementById('plant-analytics-section').classList.add('d-none');
    document.getElementById('animal-analytics-section').classList.add('d-none');
    document.querySelectorAll('#analyticsSidebarAccordion .list-group-item').forEach(el => el.classList.remove('active'));
    if (element) {
        element.classList.add('active');
    }
    if (type === 'plant') {
        document.getElementById('plant-analytics-section').classList.remove('d-none');
        loadAnalyticsDashboard(sessionId);
    } else {
        document.getElementById('animal-analytics-section').classList.remove('d-none');
        loadAnimalAnalyticsDashboard(sessionId);
    }
};

window.switchAnalyticsTab = function(tabName) {
    document.getElementById('plant-analytics-section').classList.add('d-none');
    document.getElementById('animal-analytics-section').classList.add('d-none');
    document.querySelectorAll('#analyticsSidebarAccordion .list-group-item').forEach(el => el.classList.remove('active'));
    
    if (tabName === 'plant') {
        document.getElementById('plant-analytics-section').classList.remove('d-none');
        document.querySelector('#analytics-plant-nav > a').classList.add('active');
        loadAnalyticsDashboard(null);
    } else if (tabName === 'animal') {
        document.getElementById('animal-analytics-section').classList.remove('d-none');
        document.querySelector('#analytics-animal-nav > a').classList.add('active');
        loadAnimalAnalyticsDashboard(null);
    }
};

// ==========================================
// Authentication Interceptors & Logic
// ==========================================
// The Bearer token is attached by js/api.js, which replaces window.fetch.
// Version 1 injected a client-asserted `X-User-Id` header: any caller could set
// it to another account's id and read that account's data. The server now
// requires a signed JWT, and the token is stored on login/register below.

function currentUser() {
    return getStoredUser();
}

// Toggle Auth panel forms & tabs
window.switchAuthTab = function(mode) {
    const loginForm = document.getElementById('login-form');
    const registerForm = document.getElementById('register-form');
    const forgotForm = document.getElementById('forgot-form');
    const resetForm = document.getElementById('reset-form');
    
    const tabLogin = document.getElementById('tab-login');
    const tabRegister = document.getElementById('tab-register');
    const tabsContainer = document.getElementById('auth-tabs-container');
    
    // Reset alert boxes
    document.getElementById('auth-error-alert').classList.add('d-none');
    document.getElementById('auth-success-alert').classList.add('d-none');
    
    // Hide all forms
    loginForm.classList.add('d-none');
    registerForm.classList.add('d-none');
    forgotForm.classList.add('d-none');
    resetForm.classList.add('d-none');
    
    // Default active tabs styling
    tabLogin.classList.remove('active');
    tabRegister.classList.remove('active');
    tabsContainer.classList.remove('d-none');
    
    if (mode === 'login') {
        loginForm.classList.remove('d-none');
        tabLogin.classList.add('active');
    } else if (mode === 'register') {
        registerForm.classList.remove('d-none');
        tabRegister.classList.add('active');
    } else if (mode === 'forgot') {
        forgotForm.classList.remove('d-none');
        tabsContainer.classList.add('d-none');
    } else if (mode === 'reset') {
        resetForm.classList.remove('d-none');
        tabsContainer.classList.add('d-none');
    }
};

// Form submits
document.addEventListener('DOMContentLoaded', () => {
    // 1. Handle Login Form Submit
    document.getElementById('login-form')?.addEventListener('submit', async (e) => {
        e.preventDefault();
        const email = document.getElementById('login-email').value;
        const password = document.getElementById('login-password').value;
        const btn = document.getElementById('login-btn');
        const errAlert = document.getElementById('auth-error-alert');
        const succAlert = document.getElementById('auth-success-alert');
        
        errAlert.classList.add('d-none');
        succAlert.classList.add('d-none');
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status"></span> Signing In...';
        
        try {
            const res = await rawFetch(apiUrl('/api/auth/login'), {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email, password })
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.detail || 'Login failed');
            
            succAlert.textContent = data.message;
            succAlert.classList.remove('d-none');
            
            // Persist the signed access token alongside the display profile.
            setSession(data.access_token, data.user);
            
            setTimeout(() => {
                document.getElementById('login-form').reset();
                showView('home');
            }, 1000);
            
        } catch (error) {
            errAlert.textContent = error.message;
            errAlert.classList.remove('d-none');
        } finally {
            btn.disabled = false;
            btn.innerHTML = 'Sign In';
        }
    });

    // 2. Handle Register Form Submit
    document.getElementById('register-form')?.addEventListener('submit', async (e) => {
        e.preventDefault();
        const name = document.getElementById('register-name').value;
        const email = document.getElementById('register-email').value;
        const password = document.getElementById('register-password').value;
        const btn = document.getElementById('register-btn');
        const errAlert = document.getElementById('auth-error-alert');
        const succAlert = document.getElementById('auth-success-alert');
        
        if (password.length < 6) {
            errAlert.textContent = 'Password must be at least 6 characters.';
            errAlert.classList.remove('d-none');
            return;
        }
        
        errAlert.classList.add('d-none');
        succAlert.classList.add('d-none');
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status"></span> Registering...';
        
        try {
            const res = await rawFetch(apiUrl('/api/auth/register'), {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name, email, password })
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.detail || 'Registration failed');
            
            succAlert.textContent = data.message + ' Logging you in...';
            succAlert.classList.remove('d-none');
            
            // Persist the signed access token alongside the display profile.
            setSession(data.access_token, data.user);
            
            setTimeout(() => {
                document.getElementById('register-form').reset();
                showView('home');
            }, 1500);
            
        } catch (error) {
            errAlert.textContent = error.message;
            errAlert.classList.remove('d-none');
        } finally {
            btn.disabled = false;
            btn.innerHTML = 'Create Account';
        }
    });

    // 3. Handle Forgot Password Form Submit (Request OTP)
    document.getElementById('forgot-form')?.addEventListener('submit', async (e) => {
        e.preventDefault();
        const email = document.getElementById('forgot-email').value;
        const btn = document.getElementById('forgot-btn');
        const errAlert = document.getElementById('auth-error-alert');
        const succAlert = document.getElementById('auth-success-alert');
        
        errAlert.classList.add('d-none');
        succAlert.classList.add('d-none');
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status"></span> Sending OTP...';
        
        try {
            const res = await rawFetch(apiUrl('/api/auth/forgot-password'), {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email })
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.detail || 'OTP request failed');
            
            succAlert.textContent = data.message;
            succAlert.classList.remove('d-none');
            
            // Set forgot-email placeholder or store in memory for reset form
            window.resetEmailVal = email;
            
            setTimeout(() => {
                switchAuthTab('reset');
            }, 2000);
            
        } catch (error) {
            errAlert.textContent = error.message;
            errAlert.classList.remove('d-none');
        } finally {
            btn.disabled = false;
            btn.innerHTML = 'Send OTP';
        }
    });

    // 4. Handle Reset Password Form Submit (Verify OTP)
    document.getElementById('reset-form')?.addEventListener('submit', async (e) => {
        e.preventDefault();
        const otp = document.getElementById('reset-otp').value;
        const newPassword = document.getElementById('reset-password').value;
        const btn = document.getElementById('reset-btn');
        const errAlert = document.getElementById('auth-error-alert');
        const succAlert = document.getElementById('auth-success-alert');
        const email = window.resetEmailVal;
        
        if (!email) {
            errAlert.textContent = 'Session lost. Please request OTP again.';
            errAlert.classList.remove('d-none');
            setTimeout(() => switchAuthTab('forgot'), 2000);
            return;
        }
        
        if (newPassword.length < 6) {
            errAlert.textContent = 'Password must be at least 6 characters.';
            errAlert.classList.remove('d-none');
            return;
        }
        
        errAlert.classList.add('d-none');
        succAlert.classList.add('d-none');
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status"></span> Updating...';
        
        try {
            const res = await rawFetch(apiUrl('/api/auth/reset-password'), {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email, otp, new_password: newPassword })
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.detail || 'Failed to reset password');
            
            succAlert.textContent = data.message;
            succAlert.classList.remove('d-none');
            
            setTimeout(() => {
                document.getElementById('reset-form').reset();
                switchAuthTab('login');
            }, 2000);
            
        } catch (error) {
            errAlert.textContent = error.message;
            errAlert.classList.remove('d-none');
        } finally {
            btn.disabled = false;
            btn.innerHTML = 'Verify & Reset Password';
        }
    });
    
    // Restore the session: the stored token decides whether the user is signed
    // in, and an invalid/expired token is discarded by the fetch layer on the
    // first request.
    showView('home');
    if (isAuthenticated()) {
        rawFetch(apiUrl('/api/auth/me'), { method: 'GET' })
            .then(res => (res.ok ? res.json() : null))
            .then(data => {
                if (data && data.user) {
                    setSession(getToken(), data.user);
                    loadUserProfile();
                } else {
                    clearSession();
                }
            })
            .catch(() => clearSession());
    }
});

// Load Profile Info and Stats
window.loadUserProfile = async function() {
    const user = getStoredUser();
    if (!user) return;
    
    // Populate simple info
    document.getElementById('profile-name').textContent = user.name;
    document.getElementById('profile-email').textContent = user.email;
    document.getElementById('profile-avatar-letter').textContent = user.name.charAt(0).toUpperCase();
    
    if (user.created_at) {
        const joinDate = new Date(user.created_at).toLocaleDateString(undefined, { year: 'numeric', month: 'long', day: 'numeric' });
        document.getElementById('profile-joined').textContent = joinDate;
    } else {
        document.getElementById('profile-joined').textContent = 'N/A';
    }
    
    // Fetch stats
    try {
        const res = await fetch(apiUrl('/api/auth/user-stats'));
        if (res.ok) {
            const stats = await res.json();
            document.getElementById('stat-plant-count').textContent = stats.plant_count;
            document.getElementById('stat-active-plant').textContent = stats.active_plant;
            document.getElementById('stat-animal-count').textContent = stats.animal_count;
            document.getElementById('stat-active-animal').textContent = stats.active_animal;
            document.getElementById('stat-predictions').textContent = stats.predictions;
        }
    } catch (e) {
        console.error("Error loading user profile stats", e);
    }
};

// Demo login helper: skips JWT requirements and logs directly in with demo farmer
window.handleDemoLogin = function() {
    const demoUser = {
        id: 1,
        name: "Demo Farmer",
        email: "farmer@harvestiq.ai",
        role: "farmer",
        farm_location: "North Sector Farm",
        land_area_cents: 50.0,
        soil_type: "Loamy",
        primary_crop: "Tomato",
        irrigation_source: "Drip Irrigation"
    };
    setSession("dummy_demo_token", demoUser);
    closeAuthView();
    showView('home');
    loadUserProfile();
};

// Logout handler
window.handleLogout = function() {
    clearSession();
    window.location.reload();
};

// ========================================================
// PHASE 3-6 CLIENT HANDLERS
// ========================================================

// 1. Crop Recommendation Handler
document.addEventListener('DOMContentLoaded', () => {
    const cropRecForm = document.getElementById('croprec-form');
    if (cropRecForm) {
        cropRecForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const btn = document.getElementById('btn-run-croprec');
            btn.disabled = true;
            btn.textContent = 'Evaluating...';
            
            const payload = {
                n: parseFloat(document.getElementById('rec-n').value),
                p: parseFloat(document.getElementById('rec-p').value),
                k: parseFloat(document.getElementById('rec-k').value),
                ph: parseFloat(document.getElementById('rec-ph').value),
                temperature: parseFloat(document.getElementById('rec-temp').value),
                humidity: parseFloat(document.getElementById('rec-humidity').value),
                rainfall: parseFloat(document.getElementById('rec-rainfall').value),
                top_k: 3
            };

            try {
                const res = await fetch(apiUrl('/api/ml/crop-recommendation'), {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                const data = await res.json();
                if (!res.ok) throw new Error(data.detail || 'Evaluation failed');

                const container = document.getElementById('croprec-cards-container');
                container.innerHTML = '';
                data.recommendations.forEach(rec => {
                    const col = document.createElement('div');
                    col.className = 'col-md-4';
                    col.innerHTML = `
                        <div class="card bg-dark border-success h-100 p-3">
                            <div class="d-flex justify-content-between align-items-center mb-2">
                                <h5 class="fw-bold text-success mb-0">${escapeHtml(rec.crop)}</h5>
                                <span class="badge bg-success">${rec.confidence}% Match</span>
                            </div>
                            <p class="small text-muted mb-2"><strong>Season:</strong> ${escapeHtml(rec.season)}</p>
                            <p class="small text-light mb-2">${escapeHtml(rec.explanation)}</p>
                            <div class="mt-auto border-top border-secondary pt-2 small text-muted">
                                Soil: ${escapeHtml(rec.recommended_soil)}
                            </div>
                        </div>
                    `;
                    container.appendChild(col);
                });
                document.getElementById('croprec-results').classList.remove('d-none');
            } catch (err) {
                alert('Crop recommendation error: ' + err.message);
            } finally {
                btn.disabled = false;
                btn.textContent = '🔍 Evaluate Suitable Crops';
            }
        });
    }

    // 2. Yield Prediction Handler
    const yieldForm = document.getElementById('yield-form');
    if (yieldForm) {
        yieldForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const btn = document.getElementById('btn-run-yield');
            btn.disabled = true;
            btn.textContent = 'Calculating...';

            const payload = {
                crop: document.getElementById('yield-crop').value,
                area_cents: parseFloat(document.getElementById('yield-area').value),
                soil_type: document.getElementById('yield-soil').value,
                fertilizer_applied_kg: parseFloat(document.getElementById('yield-fert').value),
                rainfall_mm: parseFloat(document.getElementById('yield-rain').value),
                temperature_c: parseFloat(document.getElementById('yield-temp').value),
                irrigation_available: true
            };

            try {
                const res = await fetch(apiUrl('/api/ml/yield-prediction'), {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                const data = await res.json();
                if (!res.ok) throw new Error(data.detail || 'Prediction failed');

                const p = data.prediction;
                document.getElementById('yield-output-title').textContent = `Predicted Harvest Yield for ${p.crop}`;
                document.getElementById('yield-output-val').textContent = `${p.total_predicted_yield_kg} kg (~${p.predicted_yield_kg_per_ha} kg/ha)`;
                document.getElementById('yield-output-details').textContent = 
                    `Land Area: ${p.area_cents} cents (${p.area_hectares} ha) | Soil Multiplier: ${p.factors.soil_fertility_multiplier}x | Water Multiplier: ${p.factors.water_availability_multiplier}x`;
                document.getElementById('yield-results').classList.remove('d-none');
            } catch (err) {
                alert('Yield prediction error: ' + err.message);
            } finally {
                btn.disabled = false;
                btn.textContent = '📊 Predict Expected Yield';
            }
        });
    }

    // 3. RAG Query Handler
    const ragForm = document.getElementById('rag-query-form');
    if (ragForm) {
        ragForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const btn = document.getElementById('btn-run-rag');
            const q = document.getElementById('rag-query-input').value;
            btn.disabled = true;
            btn.textContent = 'Searching...';

            try {
                const res = await fetch(apiUrl('/api/knowledge/query'), {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ query: q })
                });
                const data = await res.json();
                if (!res.ok) throw new Error(data.detail || 'Query failed');

                document.getElementById('rag-answer-text').textContent = data.answer;
                const citBox = document.getElementById('rag-citations-container');
                citBox.innerHTML = '<strong class="small text-success d-block mb-1">Citations & Official Sources:</strong>';
                if (data.citations && data.citations.length) {
                    data.citations.forEach(c => {
                        const a = document.createElement('a');
                        a.href = c.source_url;
                        a.target = '_blank';
                        a.className = 'badge bg-secondary text-decoration-none me-2 p-2';
                        a.textContent = `🔗 ${c.title}`;
                        citBox.appendChild(a);
                    });
                } else {
                    citBox.innerHTML += '<span class="small text-muted">No external citations required.</span>';
                }
                document.getElementById('rag-result-box').classList.remove('d-none');
            } catch (err) {
                alert('Knowledge search error: ' + err.message);
            } finally {
                btn.disabled = false;
                btn.textContent = 'Search Knowledge Base';
            }
        });
    }

    // 4. Conversational Assistant Handler
    const chatForm = document.getElementById('assistant-form');
    if (chatForm) {
        chatForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const input = document.getElementById('assistant-input');
            const msg = input.value.trim();
            if (!msg) return;

            const chatMessages = document.getElementById('chat-messages');

            // Render User Bubble
            const userBubble = document.createElement('div');
            userBubble.className = 'd-flex justify-content-end mb-3';
            userBubble.innerHTML = `
                <div class="bg-success text-white p-3 rounded" style="max-width: 80%;">
                    <strong>You:</strong> ${escapeHtml(msg)}
                </div>
            `;
            chatMessages.appendChild(userBubble);
            input.value = '';
            chatMessages.scrollTop = chatMessages.scrollHeight;

            const btn = document.getElementById('btn-send-chat');
            btn.disabled = true;

            try {
                const res = await fetch(apiUrl('/api/assistant/chat'), {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ message: msg })
                });
                const data = await res.json();
                if (!res.ok) throw new Error(data.detail || 'Assistant error');

                const r = data.result;
                const aiBubble = document.createElement('div');
                aiBubble.className = 'd-flex mb-3';
                aiBubble.innerHTML = `
                    <div class="bg-dark border border-secondary text-light p-3 rounded" style="max-width: 80%;">
                        <strong>AI Assistant:</strong> <span class="badge bg-secondary mb-1">${escapeHtml(r.intent)}</span>
                        <div class="mt-1" style="white-space: pre-line;">${escapeHtml(r.response)}</div>
                    </div>
                `;
                chatMessages.appendChild(aiBubble);
                chatMessages.scrollTop = chatMessages.scrollHeight;
            } catch (err) {
                alert('Assistant error: ' + err.message);
            } finally {
                btn.disabled = false;
            }
        });
    }
});

// Load official schemes directory
window.loadSchemesDirectory = async function() {
    const container = document.getElementById('schemes-list-container');
    if (!container) return;
    try {
        const res = await fetch(apiUrl('/api/knowledge/schemes'));
        if (!res.ok) throw new Error('Failed to load schemes');
        const data = await res.json();
        container.innerHTML = '';
        data.schemes.forEach(s => {
            const col = document.createElement('div');
            col.className = 'col-md-6';
            col.innerHTML = `
                <div class="card bg-dark border-secondary p-3 h-100">
                    <h5 class="fw-bold text-success">${escapeHtml(s.title)}</h5>
                    <span class="badge bg-secondary mb-2 align-self-start">${escapeHtml(s.category)}</span>
                    <p class="small text-light">${escapeHtml(s.description)}</p>
                    <p class="small text-muted mb-2"><strong>Benefits:</strong> ${escapeHtml(s.benefits)}</p>
                    <div class="mt-auto pt-2 border-top border-secondary">
                        <a href="${s.source_url}" target="_blank" class="btn btn-outline-success btn-sm">Official Portal ↗</a>
                    </div>
                </div>
            `;
            container.appendChild(col);
        });
    } catch (err) {
        container.innerHTML = `<div class="text-danger small">Error loading schemes directory: ${escapeHtml(err.message)}</div>`;
    }
};
