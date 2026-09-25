with open("frontend/js/app.js", "a", encoding="utf-8") as f:
    f.write("""
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
""")
