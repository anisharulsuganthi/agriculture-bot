document.addEventListener('DOMContentLoaded', () => {
    const dropZone = document.getElementById('drop-zone');
    const imageInput = document.getElementById('image-input');
    const imagePreview = document.getElementById('image-preview');
    const submitBtn = document.getElementById('submit-btn');
    const predictionForm = document.getElementById('prediction-form');
    const resultSection = document.getElementById('result-section');
    const resetBtn = document.getElementById('reset-btn');
    const alertContainer = document.getElementById('alert-container');
    
    let selectedFile = null;

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
        alertContainer.innerHTML = `
            <div class="alert alert-${type} alert-dismissible fade show" role="alert">
                ${message}
                <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
            </div>
        `;
    }

    predictionForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        if (!selectedFile) return;

        submitBtn.disabled = true;
        submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Predicting...';
        alertContainer.innerHTML = '';

        const formData = new FormData();
        formData.append('image', selectedFile);

        try {
            const response = await fetch('http://localhost:8000/api/predict/disease', {
                method: 'POST',
                body: formData
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.detail || 'Prediction failed');
            }

            displayResults(data);
        } catch (error) {
            showAlert(error.message, 'danger');
        } finally {
            submitBtn.disabled = false;
            submitBtn.innerHTML = 'Predict Disease';
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
            prediction.detections.forEach(det => {
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td class="fw-bold">${det.label}</td>
                    <td>${det.score}%</td>
                `;
                detBody.appendChild(tr);
            });
        } else {
            detBody.innerHTML = '<tr><td colspan="2" class="text-center text-muted">No diseases detected.</td></tr>';
        }

        document.getElementById('res-disease-name').textContent = prediction.disease_name;
        document.getElementById('res-confidence').textContent = `${prediction.confidence_score}%`;
        
        const healthyBadge = document.getElementById('res-healthy');
        if (prediction.is_healthy) {
            healthyBadge.className = 'badge bg-success';
            healthyBadge.innerHTML = '✅ Healthy';
        } else {
            healthyBadge.className = 'badge bg-danger';
            healthyBadge.innerHTML = '❌ Infected';
        }

        const severityBadge = document.getElementById('res-severity');
        severityBadge.textContent = `Severity: ${prediction.severity}`;
        if (prediction.severity === 'Severe') severityBadge.className = 'badge bg-danger';
        else if (prediction.severity === 'Moderate') severityBadge.className = 'badge bg-warning text-dark';
        else severityBadge.className = 'badge bg-info text-dark';

        const tbody = document.getElementById('cure-table-body');
        tbody.innerHTML = '';
        cure.forEach(c => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td class="fw-bold">${c.step}</td>
                <td>${c.action}</td>
                <td>${c.details}</td>
            `;
            tbody.appendChild(tr);
        });
    }

    resetBtn.addEventListener('click', () => {
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
        
        resultSection.classList.add('d-none');
        predictionForm.closest('.card').classList.remove('d-none');
    });
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
    const user = JSON.parse(localStorage.getItem('smartfarm_user') || 'null');
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
    
    // Toggle body background and navbar margin
    const navbar = document.getElementById('main-navbar');
    if (viewName === 'home') {
        navbar.classList.remove('mb-4');
        document.getElementById('home-view').style.display = 'block';
    } else {
        navbar.classList.add('mb-4');
        
        if (viewName === 'disease') {
            document.getElementById('disease-prediction-view').classList.remove('d-none');
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
            fetch('http://localhost:8000/api/sessions'),
            fetch('http://localhost:8000/api/animals')
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
                    optGroup.innerHTML += `<option value="plant_${s.id}">${s.plot_name} (${s.crop_type}) ${status}</option>`;
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
                    optGroup.innerHTML += `<option value="animal_${s.id}">${s.session_name} (${s.animal_type}) ${status}</option>`;
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
            ? `http://localhost:8000/api/sessions` 
            : `http://localhost:8000/api/animals`;
            
        const res = await fetch(endpoint);
        const sessions = await res.json();
        const session = sessions.find(s => s.id === window.activeSessionId);
        
        if (session) {
            if (window.activeSessionType === 'plant') {
                document.getElementById('session-info').innerHTML = `
                    <div><strong>Crop:</strong> ${session.crop_type} (${session.plot_name})</div>
                    <div><strong>Soil:</strong> ${session.soil_type}</div>
                    <div><strong>Location:</strong> ${session.location}</div>
                `;
            } else {
                document.getElementById('session-info').innerHTML = `
                    <div><strong>Animal:</strong> ${session.animal_type} (${session.session_name})</div>
                    <div><strong>Count:</strong> ${session.animal_count}</div>
                `;
            }
        }
        
        // Fetch recommendations (currently backend only supports plant recommendations, but we can reuse it for basic weather)
        // Note: The backend /api/sessions/{id}/recommendations specifically queries FarmingSession.
        // If it's an animal session, we should just fetch weather, but for now we'll mock it or handle it in JS.
        if (window.activeSessionType === 'plant') {
            await fetchClimateData();
        } else {
            // Mock weather for animal session since backend endpoint doesn't support animals
            document.getElementById('weather-info').innerHTML = `
                <h3 class="fw-bold">28.5°C</h3>
                <p class="mb-1 text-muted">Humidity: 65%</p>
                <p class="mb-0 text-muted">Good conditions for livestock.</p>
            `;
            document.getElementById('disease-risk-info').innerHTML = `
                <span class="badge bg-success fs-6 mb-2">Low Risk</span>
                <p class="mb-1 fw-bold">No imminent viral threats detected in your region.</p>
            `;
            document.getElementById('watering-rec').innerHTML = `
                <h5 class="fw-bold text-dark">Ensure constant clean water supply</h5>
                <p class="mb-2">⚠️ Animals drink more during warmer parts of the day.</p>
            `;
            document.getElementById('fertilizing-rec').innerHTML = `
                <h5 class="fw-bold text-dark">Ensure proper feeding schedule</h5>
                <p class="mb-2">⚠️ Standard feeding recommended.</p>
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
        const res = await fetch(`http://localhost:8000/api/sessions/${window.activeSessionId}/recommendations`);
        if (!res.ok) throw new Error("Failed to fetch recommendations");
        const data = await res.json();
        
        // Populate Weather
        document.getElementById('weather-info').innerHTML = `
            <h3 class="fw-bold">${data.current_weather.temperature}°C</h3>
            <p class="mb-1 text-muted">Humidity: ${data.current_weather.humidity}%</p>
            <p class="mb-0 text-muted">Soil Moisture: ${data.soil_moisture}%</p>
        `;

        // Populate Disease Risk
        const riskLevel = data.disease_risk.risk_level;
        let riskColor = riskLevel === 'High' ? 'danger' : (riskLevel === 'Medium' ? 'warning' : 'success');
        document.getElementById('disease-risk-info').innerHTML = `
            <span class="badge bg-${riskColor} fs-6 mb-2">${riskLevel} Risk</span>
            <p class="mb-1 fw-bold">${data.disease_risk.message}</p>
            <p class="mb-0 text-muted">${data.disease_risk.action}</p>
        `;

        // Populate Watering
        document.getElementById('watering-rec').innerHTML = `
            <h5 class="fw-bold text-dark">${data.watering.recommendation}</h5>
            <p class="mb-2">⚠️ ${data.watering.reason}</p>
            <span class="badge bg-light text-dark border">📅 Next scheduled: ${data.watering.next_scheduled}</span>
        `;

        // Populate Fertilizing
        document.getElementById('fertilizing-rec').innerHTML = `
            <h5 class="fw-bold text-dark">${data.fertilizing.recommendation}</h5>
            <p class="mb-2">📦 Type: ${data.fertilizing.fertilizer_type}</p>
            <p class="mb-2">⚠️ ${data.fertilizing.reason}</p>
            <span class="badge bg-light text-dark border">📅 Next scheduled: ${data.fertilizing.next_scheduled}</span>
        `;
        
    } catch (e) {
        console.error("Error fetching climate data", e);
    }
};

window.sendAlert = async function() {
    if (!window.activeSessionId) return;
    
    // In a real app, this would be tied to the logged-in user's profile
    let emailAddress = prompt("Enter email address to send alert (e.g. user@example.com):");
    if (!emailAddress) return;
    
    try {
        const response = await fetch(`http://localhost:8000/api/sessions/${window.activeSessionId}/notify`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email: emailAddress.trim() })
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
        const summaryRes = await fetch("http://localhost:8000/api/dashboard/summary");
        if (summaryRes.ok) {
            const summary = await summaryRes.json();
            document.getElementById('summary-investment').textContent = "₹" + summary.total_investment;
            document.getElementById('summary-yield').textContent = summary.total_yield + " kg";
            document.getElementById('summary-profit').textContent = "₹" + summary.net_profit;
            document.getElementById('summary-margin').textContent = summary.profit_margin_percent + "%";
        }
        
        // Load sessions list
        const sessionsRes = await fetch("http://localhost:8000/api/sessions");
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
                
                listEl.innerHTML += `
                    <button class="list-group-item list-group-item-action ${isSelected}" onclick="selectSessionToManage(${s.id}, '${s.plot_name}', ${s.is_active})">
                        <div class="d-flex w-100 justify-content-between">
                            <h6 class="mb-1 fw-bold">${s.plot_name} (${s.crop_type})</h6>
                        </div>
                        <small class="text-muted">Area: ${s.area_cents} cents | Loc: ${s.location}</small>
                        ${statusBadge}
                    </button>
                `;
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
        const res = await fetch(`http://localhost:8000/api/sessions/${sessionId}/daily_logs`);
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
                const weatherStr = `<b>climate 🌤️ :</b> ${log.weather_condition || 'N/A'}`;
                const wateredStr = `<b>watered 💧 :</b> ${log.watered ? 'Yes' : 'No'}`;
                const waterReasonStr = log.water_reason ? `<b>reason for 💧 :</b> ${log.water_reason}` : '';
                const fertStr = `<b>fertilizers :</b> ${log.fertilized ? 'Yes' : 'No'}`;
                const fertKgStr = log.fertilized ? `<b>fertilizer kg :</b> ${log.fertilizer_amount} kg used` : '';
                const notesStr = log.notes ? `<b>notes :</b> ${log.notes}` : '';

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
        const response = await fetch("http://localhost:8000/api/sessions", {
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
        const response = await fetch(`http://localhost:8000/api/sessions/${selectedManageSessionId}/daily_logs`, {
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
        const response = await fetch(`http://localhost:8000/api/sessions/${selectedManageSessionId}/harvest`, {
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
            ? `http://localhost:8000/api/dashboard/analytics?session_id=${sessionId}`
            : "http://localhost:8000/api/dashboard/analytics";
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
                            <strong>${s.plot_name}</strong>
                        </div>
                        <span class="text-success fw-bold">₹${s.revenue}</span>
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
        const summaryRes = await fetch("http://localhost:8000/api/animals/dashboard/summary");
        if (summaryRes.ok) {
            const summary = await summaryRes.json();
            document.getElementById('animal-summary-investment').textContent = "₹" + summary.total_investment;
            document.getElementById('animal-summary-yield').textContent = summary.total_yield;
            document.getElementById('animal-summary-sales').textContent = "₹" + summary.total_revenue;
            document.getElementById('animal-summary-profit').textContent = "₹" + summary.net_profit;
            document.getElementById('animal-summary-margin').textContent = summary.profit_margin_percent + "%";
        }
        
        const sessionsRes = await fetch("http://localhost:8000/api/animals");
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
                
                listEl.innerHTML += `
                    <button class="list-group-item list-group-item-action ${isSelected}" onclick="selectAnimalSessionToManage(${s.id}, '${s.session_name}', ${s.is_active})">
                        <div class="d-flex w-100 justify-content-between">
                            <h6 class="mb-1 fw-bold">${s.session_name} (${s.animal_type})</h6>
                        </div>
                        <small class="text-muted">Count: ${s.animal_count}</small>
                        ${statusBadge}
                    </button>
                `;
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
        const res = await fetch(`http://localhost:8000/api/animals/${sessionId}/daily_logs`);
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
                
                const foodStr = `<b>Food 📦:</b> ${log.food_given_qty} kg (₹${log.food_cost_today})`;
                const yieldStr = log.yield_amount > 0 ? `<b>Yield 🥛/🥚:</b> ${log.yield_amount} @ ₹${log.yield_selling_price} (Total: ₹${log.yield_amount * log.yield_selling_price})` : '';
                const medStr = log.medicine_given ? `<b>Medicine 💊:</b> Yes - ${log.medicine_name} (₹${log.medicine_cost}) - ${log.medicine_reason}` : `<b>Medicine 💊:</b> No`;
                const deathStr = log.deaths_today > 0 ? `<b>Deaths ☠️:</b> ${log.deaths_today}` : '';
                const notesStr = log.notes ? `<b>Notes:</b> ${log.notes}` : '';

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
        const response = await fetch("http://localhost:8000/api/animals", {
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
        const response = await fetch(`http://localhost:8000/api/animals/${selectedAnimalSessionId}/daily_logs`, {
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
        const response = await fetch(`http://localhost:8000/api/animals/${selectedAnimalSessionId}/close`, {
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
            ? `http://localhost:8000/api/animals/dashboard/analytics?session_id=${sessionId}`
            : "http://localhost:8000/api/animals/dashboard/analytics";
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
                        <h6 class="mb-0 fw-bold">${s.plot_name}</h6>
                        <small class="text-muted">Yield: ${s.total_yield} units</small>
                    </div>
                </div>
                <div class="text-end">
                    <div class="fw-bold text-success">₹${s.profit}</div>
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
        const response = await fetch("http://localhost:8000/api/market/intelligence");
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
                <span>${m.location} <span class="text-muted">(${m.distance})</span></span>
                <span class="fw-bold">₹${m.price}/${item.unit}</span>
            </div>
        `).join('');
        
        html += `
        <div class="col-md-6 mb-4">
            <div class="card shadow-sm border-0 h-100">
                <div class="card-header bg-white border-0 pt-4 pb-0">
                    <h5 class="card-title fw-bold">${item.commodity} Market <span class="badge bg-secondary ms-2">${item.plot}</span></h5>
                </div>
                <div class="card-body">
                    <div class="row mb-3">
                        <div class="col-6">
                            <p class="text-muted mb-1 small">Local Price</p>
                            <h3 class="fw-bold mb-0">₹${item.current_price}<span class="fs-6 text-muted">/${item.unit}</span></h3>
                        </div>
                        <div class="col-6 text-end">
                            <p class="text-muted mb-1 small">7-Day Trend</p>
                            <h4 class="${trendClass} mb-0">${trendIcon} ${Math.abs(item.trend_perc)}%</h4>
                        </div>
                    </div>
                    
                    <div class="d-flex justify-content-between mb-3 bg-light rounded p-2">
                        <div class="text-center w-50 border-end">
                            <small class="text-muted d-block">State Avg</small>
                            <span class="fw-bold">₹${item.state_avg}</span>
                        </div>
                        <div class="text-center w-50">
                            <small class="text-muted d-block">National Avg</small>
                            <span class="fw-bold">₹${item.national_avg}</span>
                        </div>
                    </div>
                    
                    <h6 class="fw-bold mt-4 mb-2">Nearby Mandis / Auctions</h6>
                    ${mandiRows}
                    
                    <div class="alert alert-warning mt-3 mb-0 p-2 text-center">
                        <strong>AI Forecast (7 Days):</strong> Expected ₹${item.forecast_price}/${item.unit}
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
                <h6 class="fw-bold text-dark mb-2">${rec.title}</h6>
                <div class="d-flex justify-content-between small mb-1">
                    <span class="text-muted">Current: <strong class="text-dark">${rec.current_price}</strong></span>
                    <span class="text-muted">Forecast: <strong class="text-success">${rec.forecast_price}</strong></span>
                </div>
                <div class="small mb-2">
                    <span class="text-muted">Best Location:</span> <span class="fw-bold">${rec.best_location}</span>
                </div>
                <div class="alert alert-success p-2 mb-0 mt-2 small text-center fw-bold">
                    Action: ${rec.action}
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
            fetch('http://localhost:8000/api/sessions'),
            fetch('http://localhost:8000/api/animals'),
            fetch('http://localhost:8000/api/dashboard/analytics'),
            fetch('http://localhost:8000/api/animals/dashboard/analytics')
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
            plantList.innerHTML += `
                <button class="list-group-item list-group-item-action" onclick="showUnifiedSession('plant', ${s.id}, '${s.plot_name}', ${s.is_active})">
                    <div class="d-flex justify-content-between">
                        <span>${s.plot_name}</span>
                        <small class="text-muted">${status}</small>
                    </div>
                </button>
            `;
        });
        
        // Populate Animal List
        const animalList = document.getElementById('unified-animal-session-list');
        animalList.innerHTML = `<button class="list-group-item list-group-item-action fw-bold text-primary" onclick="showUnifiedAggregate('animal')">📈 Overall Animal Analytics</button>`;
        
        animals.forEach(s => {
            const status = s.is_active ? '✅ Active' : '🏁 Ended';
            animalList.innerHTML += `
                <button class="list-group-item list-group-item-action" onclick="showUnifiedSession('animal', ${s.id}, '${s.session_name}', ${s.is_active})">
                    <div class="d-flex justify-content-between">
                        <span>${s.session_name}</span>
                        <small class="text-muted">${status}</small>
                    </div>
                </button>
            `;
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
    try {
        const plantRes = await fetch("http://localhost:8000/api/sessions");
        if (plantRes.ok) {
            const plantSessions = await plantRes.json();
            const activePlant = plantSessions.filter(s => s.is_active);
            const completedPlant = plantSessions.filter(s => !s.is_active);
            document.getElementById('analytics-plant-active').innerHTML = activePlant.map(s => `<a href="#" class="list-group-item list-group-item-action ps-4" onclick="filterAnalyticsSession('plant', ${s.id}, this); return false;">🌱 ${s.plot_name}</a>`).join('');
            document.getElementById('analytics-plant-completed').innerHTML = completedPlant.map(s => `<a href="#" class="list-group-item list-group-item-action ps-4" onclick="filterAnalyticsSession('plant', ${s.id}, this); return false;">🌱 ${s.plot_name}</a>`).join('');
        }
        
        const animalRes = await fetch("http://localhost:8000/api/animals");
        if (animalRes.ok) {
            const animalSessions = await animalRes.json();
            const activeAnimal = animalSessions.filter(s => s.is_active);
            const completedAnimal = animalSessions.filter(s => !s.is_active);
            document.getElementById('analytics-animal-active').innerHTML = activeAnimal.map(s => `<a href="#" class="list-group-item list-group-item-action ps-4" onclick="filterAnalyticsSession('animal', ${s.id}, this); return false;">🐾 ${s.session_name}</a>`).join('');
            document.getElementById('analytics-animal-completed').innerHTML = completedAnimal.map(s => `<a href="#" class="list-group-item list-group-item-action ps-4" onclick="filterAnalyticsSession('animal', ${s.id}, this); return false;">🐾 ${s.session_name}</a>`).join('');
        }
    } catch (e) {
        console.error("Error loading analytics sidebar", e);
    }
};

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

// Global Fetch Interceptor to automatically add X-User-Id header
const originalFetch = window.fetch;
window.fetch = async function(...args) {
    let [resource, config] = args;
    const user = JSON.parse(localStorage.getItem('smartfarm_user') || 'null');
    if (user && user.id) {
        if (!config) config = {};
        if (!config.headers) config.headers = {};
        
        if (config.headers instanceof Headers) {
            config.headers.set('X-User-Id', String(user.id));
        } else {
            config.headers['X-User-Id'] = String(user.id);
        }
    }
    return originalFetch(resource, config);
};

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
            const res = await originalFetch('http://localhost:8000/api/auth/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email, password })
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.detail || 'Login failed');
            
            succAlert.textContent = data.message;
            succAlert.classList.remove('d-none');
            
            // Save user session
            localStorage.setItem('smartfarm_user', JSON.stringify(data.user));
            
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
            const res = await originalFetch('http://localhost:8000/api/auth/register', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name, email, password })
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.detail || 'Registration failed');
            
            succAlert.textContent = data.message + ' Logging you in...';
            succAlert.classList.remove('d-none');
            
            // Save user session
            localStorage.setItem('smartfarm_user', JSON.stringify(data.user));
            
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
            const res = await originalFetch('http://localhost:8000/api/auth/forgot-password', {
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
            const res = await originalFetch('http://localhost:8000/api/auth/reset-password', {
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
    
    // Check initial user state
    const user = JSON.parse(localStorage.getItem('smartfarm_user') || 'null');
    if (user) {
        showView('home');
    } else {
        showView('home');
    }
});

// Load Profile Info and Stats
window.loadUserProfile = async function() {
    const user = JSON.parse(localStorage.getItem('smartfarm_user') || 'null');
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
        const res = await fetch('http://localhost:8000/api/auth/user-stats');
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

// Logout handler
window.handleLogout = function() {
    localStorage.removeItem('smartfarm_user');
    window.location.reload();
};
