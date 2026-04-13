// API Base URL
const API_URL = 'http://localhost:3000/api';

// Global state
let currentResume = null;
let currentStartups = [];
let allStartups = []; // For filtering
let currentEmails = [];
let selectedEmailIndices = new Set();
let currentConfig = null;

// ========== Utility Functions ==========

function showLoading(message = 'Chargement...') {
    document.getElementById('loading-message').textContent = message;
    document.getElementById('loading-overlay').classList.remove('hidden');
}

function hideLoading() {
    document.getElementById('loading-overlay').classList.add('hidden');
}

function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerHTML = `
        <div class="flex items-center">
            <i class="fas fa-${type === 'success' ? 'check-circle' : type === 'error' ? 'exclamation-circle' : 'info-circle'} mr-3 text-xl"></i>
            <div>
                <p class="font-semibold">${type === 'success' ? 'Succès' : type === 'error' ? 'Erreur' : 'Information'}</p>
                <p class="text-sm text-gray-600">${message}</p>
            </div>
        </div>
    `;
    document.body.appendChild(toast);
    
    setTimeout(() => {
        toast.style.animation = 'toastSlideIn 0.3s ease reverse';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

function showSection(sectionName) {
    // Hide all sections
    document.querySelectorAll('.section').forEach(section => {
        section.classList.add('hidden');
    });
    
    // Show selected section
    document.getElementById(`${sectionName}-section`).classList.remove('hidden');
    
    // Update nav buttons
    document.querySelectorAll('.nav-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    event.target.closest('.nav-btn').classList.add('active');
    
    // Load data for the section
    switch(sectionName) {
        case 'dashboard':
            loadDashboard();
            break;
        case 'resume':
            loadResume();
            break;
        case 'startups':
            loadStartups();
            break;
        case 'emails':
            loadEmails();
            break;
        case 'config':
            loadConfig();
            break;
    }
}

// ========== API Calls ==========

async function apiCall(endpoint, method = 'GET', data = null) {
    const options = {
        method,
        headers: {
            'Content-Type': 'application/json',
        },
    };
    
    if (data) {
        options.body = JSON.stringify(data);
    }
    
    try {
        const response = await fetch(`${API_URL}${endpoint}`, options);
        const result = await response.json();
        
        if (!response.ok) {
            throw new Error(result.error || 'Une erreur est survenue');
        }
        
        return result;
    } catch (error) {
        console.error('API Error:', error);
        throw error;
    }
}

// ========== Dashboard Functions ==========

async function loadDashboard() {
    try {
        showLoading('Chargement du tableau de bord...');
        
        const stats = await apiCall('/stats');
        
        document.getElementById('stat-startups').textContent = stats.totalStartups;
        document.getElementById('stat-generated').textContent = stats.emailsGenerated;
        document.getElementById('stat-sent').textContent = stats.emailsSent;
        document.getElementById('stat-pending').textContent = stats.emailsPending;
        
        // Load recent activity
        const tracking = await apiCall('/tracking');
        displayRecentActivity(tracking.sent_emails || []);
        
        hideLoading();
    } catch (error) {
        hideLoading();
        showToast(error.message, 'error');
    }
}

function displayRecentActivity(sentEmails) {
    const container = document.getElementById('recent-activity');
    
    if (!sentEmails || sentEmails.length === 0) {
        container.innerHTML = '<p class="text-gray-500">Aucune activité récente</p>';
        return;
    }
    
    const recentEmails = sentEmails.slice(-10).reverse();
    
    container.innerHTML = recentEmails.map(email => `
        <div class="flex items-center justify-between p-3 bg-gray-50 rounded-lg hover:bg-gray-100 transition">
            <div class="flex items-center space-x-3">
                <div class="bg-blue-100 p-2 rounded-full">
                    <i class="fas fa-paper-plane text-blue-600"></i>
                </div>
                <div>
                    <p class="font-medium text-gray-800">${email.company_name || email.startup_name || 'Inconnu'}</p>
                    <p class="text-sm text-gray-500">${email.timestamp ? new Date(email.timestamp).toLocaleString('fr-FR') : ''}</p>
                </div>
            </div>
            <span class="px-3 py-1 bg-green-100 text-green-700 rounded-full text-sm font-medium">
                <i class="fas fa-check mr-1"></i>Envoyé
            </span>
        </div>
    `).join('');
}

// ========== Resume Functions ==========

async function loadResume() {
    try {
        showLoading('Chargement du CV...');
        
        const resume = await apiCall('/resume');
        currentResume = resume;
        
        // Fill form
        document.getElementById('resume-name').value = resume.name || '';
        document.getElementById('resume-email').value = resume.email || '';
        document.getElementById('resume-phone').value = resume.phone || '';
        document.getElementById('resume-linkedin').value = resume.linkedin || '';
        document.getElementById('resume-skills').value = Array.isArray(resume.skills) ? resume.skills.join(', ') : '';
        
        // Load education
        const educationContainer = document.getElementById('education-container');
        educationContainer.innerHTML = '';
        if (resume.education && Array.isArray(resume.education)) {
            resume.education.forEach((edu, index) => {
                addEducation(edu);
            });
        }
        
        // Load experience
        const experienceContainer = document.getElementById('experience-container');
        experienceContainer.innerHTML = '';
        if (resume.experience && Array.isArray(resume.experience)) {
            resume.experience.forEach((exp, index) => {
                addExperience(exp);
            });
        }
        
        hideLoading();
    } catch (error) {
        hideLoading();
        showToast(error.message, 'error');
    }
}

function addEducation(data = null) {
    const container = document.getElementById('education-container');
    const index = container.children.length;
    
    const card = document.createElement('div');
    card.className = 'entry-card';
    card.innerHTML = `
        <button type="button" class="remove-btn" onclick="this.closest('.entry-card').remove()">
            <i class="fas fa-times"></i>
        </button>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">Diplôme</label>
                <input type="text" class="education-degree form-input w-full px-3 py-2 border border-gray-300 rounded-lg" value="${data?.degree || ''}">
            </div>
            <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">Institution</label>
                <input type="text" class="education-institution form-input w-full px-3 py-2 border border-gray-300 rounded-lg" value="${data?.institution || ''}">
            </div>
            <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">Année</label>
                <input type="text" class="education-year form-input w-full px-3 py-2 border border-gray-300 rounded-lg" value="${data?.year || ''}">
            </div>
        </div>
    `;
    
    container.appendChild(card);
}

function addExperience(data = null) {
    const container = document.getElementById('experience-container');
    const index = container.children.length;
    
    const card = document.createElement('div');
    card.className = 'entry-card';
    card.innerHTML = `
        <button type="button" class="remove-btn" onclick="this.closest('.entry-card').remove()">
            <i class="fas fa-times"></i>
        </button>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">Poste</label>
                <input type="text" class="experience-title form-input w-full px-3 py-2 border border-gray-300 rounded-lg" value="${data?.title || ''}">
            </div>
            <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">Entreprise</label>
                <input type="text" class="experience-company form-input w-full px-3 py-2 border border-gray-300 rounded-lg" value="${data?.company || ''}">
            </div>
            <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">Période</label>
                <input type="text" class="experience-period form-input w-full px-3 py-2 border border-gray-300 rounded-lg" value="${data?.period || ''}">
            </div>
            <div class="md:col-span-2">
                <label class="block text-sm font-medium text-gray-700 mb-1">Description</label>
                <textarea class="experience-description form-input w-full px-3 py-2 border border-gray-300 rounded-lg" rows="2">${data?.description || ''}</textarea>
            </div>
        </div>
    `;
    
    container.appendChild(card);
}

document.getElementById('resume-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    try {
        showLoading('Sauvegarde du CV...');
        
        // Collect education data
        const education = [];
        document.querySelectorAll('#education-container .entry-card').forEach(card => {
            education.push({
                degree: card.querySelector('.education-degree').value,
                institution: card.querySelector('.education-institution').value,
                year: card.querySelector('.education-year').value
            });
        });
        
        // Collect experience data
        const experience = [];
        document.querySelectorAll('#experience-container .entry-card').forEach(card => {
            experience.push({
                title: card.querySelector('.experience-title').value,
                company: card.querySelector('.experience-company').value,
                period: card.querySelector('.experience-period').value,
                description: card.querySelector('.experience-description').value
            });
        });
        
        const resumeData = {
            name: document.getElementById('resume-name').value,
            email: document.getElementById('resume-email').value,
            phone: document.getElementById('resume-phone').value,
            linkedin: document.getElementById('resume-linkedin').value,
            skills: document.getElementById('resume-skills').value.split(',').map(s => s.trim()).filter(s => s),
            education,
            experience
        };
        
        await apiCall('/resume', 'PUT', resumeData);
        
        hideLoading();
        showToast('CV sauvegardé avec succès', 'success');
    } catch (error) {
        hideLoading();
        showToast(error.message, 'error');
    }
});

// ========== Startups Functions ==========

async function loadStartups() {
    try {
        showLoading('Chargement des startups...');
        
        const result = await apiCall('/startups');
        currentStartups = result.data || [];
        allStartups = [...currentStartups]; // Keep a copy for filtering
        
        displayStartups();
        hideLoading();
    } catch (error) {
        hideLoading();
        showToast(error.message, 'error');
    }
}

function displayStartups() {
    const tbody = document.getElementById('startups-table-body');
    
    if (currentStartups.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="5" class="px-6 py-8 text-center text-gray-500">
                    <i class="fas fa-building text-4xl mb-2 block"></i>
                    Aucune startup enregistrée
                </td>
            </tr>
        `;
        return;
    }
    
    tbody.innerHTML = currentStartups.map(startup => `
        <tr>
            <td class="px-6 py-4 whitespace-nowrap">
                <div class="text-sm font-medium text-gray-900">${startup.name || 'N/A'}</div>
            </td>
            <td class="px-6 py-4 whitespace-nowrap">
                <div class="text-sm text-gray-600">${startup.email || 'N/A'}</div>
            </td>
            <td class="px-6 py-4 whitespace-nowrap">
                <div class="text-sm text-gray-600">${startup.domain || 'N/A'}</div>
            </td>
            <td class="px-6 py-4 whitespace-nowrap">
                <a href="${startup.website || '#'}" target="_blank" class="text-sm text-blue-600 hover:underline">
                    ${startup.website ? '<i class="fas fa-external-link-alt"></i>' : 'N/A'}
                </a>
            </td>
            <td class="px-6 py-4 whitespace-nowrap text-sm font-medium">
                <button onclick="editStartup(${startup.id})" class="text-blue-600 hover:text-blue-900 mr-3">
                    <i class="fas fa-edit"></i>
                </button>
                <button onclick="deleteStartup(${startup.id})" class="text-red-600 hover:text-red-900">
                    <i class="fas fa-trash"></i>
                </button>
            </td>
        </tr>
    `).join('');
}

// Filter startups
function filterStartups() {
    const searchTerm = document.getElementById('startup-search').value.toLowerCase();
    
    if (!searchTerm) {
        currentStartups = [...allStartups];
    } else {
        currentStartups = allStartups.filter(startup => {
            return (
                (startup.name && startup.name.toLowerCase().includes(searchTerm)) ||
                (startup.email && startup.email.toLowerCase().includes(searchTerm)) ||
                (startup.domain && startup.domain.toLowerCase().includes(searchTerm))
            );
        });
    }
    
    displayStartups();
}

function clearStartupFilter() {
    document.getElementById('startup-search').value = '';
    currentStartups = [...allStartups];
    displayStartups();
}

// Import/Export functions
function importStartups(event) {
    const file = event.target.files[0];
    if (!file) return;
    
    const reader = new FileReader();
    
    reader.onload = async function(e) {
        try {
            let importedData = [];
            
            if (file.name.endsWith('.json')) {
                const data = JSON.parse(e.target.result);
                importedData = data.data || data;
            } else if (file.name.endsWith('.csv')) {
                // Parse CSV
                const lines = e.target.result.split('\n');
                const headers = lines[0].split(',').map(h => h.trim());
                
                for (let i = 1; i < lines.length; i++) {
                    if (!lines[i].trim()) continue;
                    const values = lines[i].split(',').map(v => v.trim());
                    const startup = {};
                    headers.forEach((header, index) => {
                        startup[header] = values[index];
                    });
                    importedData.push(startup);
                }
            }
            
            // Add imported startups
            showLoading(`Importation de ${importedData.length} startups...`);
            
            for (const startup of importedData) {
                await apiCall('/startups', 'POST', startup);
            }
            
            hideLoading();
            showToast(`${importedData.length} startups importées avec succès`, 'success');
            loadStartups();
            
        } catch (error) {
            hideLoading();
            showToast('Erreur lors de l\'importation: ' + error.message, 'error');
        }
    };
    
    reader.readAsText(file);
    event.target.value = ''; // Reset input
}

function exportStartups() {
    const data = {
        data: allStartups
    };
    
    const dataStr = JSON.stringify(data, null, 2);
    const dataUri = 'data:application/json;charset=utf-8,' + encodeURIComponent(dataStr);
    
    const exportFileDefaultName = `startups_${new Date().toISOString().split('T')[0]}.json`;
    
    const linkElement = document.createElement('a');
    linkElement.setAttribute('href', dataUri);
    linkElement.setAttribute('download', exportFileDefaultName);
    linkElement.click();
    
    showToast('Export réussi', 'success');
}

function showAddStartupModal() {
    document.getElementById('modal-title').textContent = 'Ajouter Startup';
    document.getElementById('startup-form').reset();
    document.getElementById('startup-id').value = '';
    document.getElementById('startup-modal').classList.remove('hidden');
}

function editStartup(id) {
    const startup = currentStartups.find(s => s.id === id);
    if (!startup) return;
    
    document.getElementById('modal-title').textContent = 'Modifier Startup';
    document.getElementById('startup-id').value = startup.id;
    document.getElementById('startup-name').value = startup.name || '';
    document.getElementById('startup-email').value = startup.email || '';
    document.getElementById('startup-domain').value = startup.domain || '';
    document.getElementById('startup-website').value = startup.website || '';
    document.getElementById('startup-description').value = startup.description || '';
    
    document.getElementById('startup-modal').classList.remove('hidden');
}

function closeStartupModal() {
    document.getElementById('startup-modal').classList.add('hidden');
}

async function deleteStartup(id) {
    if (!confirm('Êtes-vous sûr de vouloir supprimer cette startup ?')) return;
    
    try {
        showLoading('Suppression...');
        await apiCall(`/startups/${id}`, 'DELETE');
        hideLoading();
        showToast('Startup supprimée avec succès', 'success');
        loadStartups();
    } catch (error) {
        hideLoading();
        showToast(error.message, 'error');
    }
}

document.getElementById('startup-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const startupId = document.getElementById('startup-id').value;
    const startupData = {
        name: document.getElementById('startup-name').value,
        email: document.getElementById('startup-email').value,
        domain: document.getElementById('startup-domain').value,
        website: document.getElementById('startup-website').value,
        description: document.getElementById('startup-description').value
    };
    
    try {
        showLoading(startupId ? 'Mise à jour...' : 'Ajout...');
        
        if (startupId) {
            await apiCall(`/startups/${startupId}`, 'PUT', startupData);
            showToast('Startup mise à jour avec succès', 'success');
        } else {
            await apiCall('/startups', 'POST', startupData);
            showToast('Startup ajoutée avec succès', 'success');
        }
        
        closeStartupModal();
        loadStartups();
        hideLoading();
    } catch (error) {
        hideLoading();
        showToast(error.message, 'error');
    }
});

// ========== Emails Functions ==========

async function loadEmails() {
    try {
        showLoading('Chargement des emails...');
        
        const emails = await apiCall('/emails');
        currentEmails = Array.isArray(emails) ? emails : [];
        
        displayEmails();
        updateEmailCounts();
        hideLoading();
    } catch (error) {
        hideLoading();
        showToast(error.message, 'error');
    }
}

function updateEmailCounts() {
    document.getElementById('emails-count').textContent = currentEmails.length;
    document.getElementById('selected-count').textContent = selectedEmailIndices.size;
}

function displayEmails() {
    const container = document.getElementById('emails-container');
    
    if (currentEmails.length === 0) {
        container.innerHTML = `
            <div class="text-center py-16">
                <i class="fas fa-envelope-open text-6xl text-gray-300 mb-4"></i>
                <p class="text-gray-500 text-lg">Aucun email généré</p>
                <p class="text-gray-400 text-sm mt-2">Cliquez sur "Générer Emails" pour commencer</p>
            </div>
        `;
        return;
    }
    
    container.innerHTML = currentEmails.map((email, index) => `
        <div class="email-card ${selectedEmailIndices.has(index) ? 'selected' : ''}" id="email-${index}">
            <div class="flex items-start justify-between mb-4">
                <div class="checkbox-container">
                    <input type="checkbox" id="checkbox-${index}" ${selectedEmailIndices.has(index) ? 'checked' : ''} 
                           onchange="toggleEmailSelection(${index})" class="mr-3">
                    <div>
                        <h3 class="text-lg font-bold text-gray-800">${email.startup_name || email.company_name || 'Inconnu'}</h3>
                        <p class="text-sm text-gray-500">
                            <i class="fas fa-envelope mr-1"></i>${email.startup_email || email.email || 'N/A'}
                        </p>
                    </div>
                </div>
                <div class="flex space-x-2">
                    <button onclick="editEmail(${index})" class="px-3 py-1 bg-blue-100 text-blue-600 rounded hover:bg-blue-200 transition text-sm">
                        <i class="fas fa-edit mr-1"></i>Modifier
                    </button>
                    <button onclick="regenerateEmail(${index})" class="px-3 py-1 bg-green-100 text-green-600 rounded hover:bg-green-200 transition text-sm">
                        <i class="fas fa-sync mr-1"></i>Régénérer
                    </button>
                </div>
            </div>
            
            <div class="bg-gray-50 rounded-lg p-4 mb-3">
                <p class="text-sm font-semibold text-gray-700 mb-2">
                    <i class="fas fa-tag mr-1"></i>Objet:
                </p>
                <p class="text-gray-800">${email.subject || 'Pas d\'objet'}</p>
            </div>
            
            <div class="bg-gray-50 rounded-lg p-4">
                <p class="text-sm font-semibold text-gray-700 mb-2">
                    <i class="fas fa-comment mr-1"></i>Message:
                </p>
                <div class="text-gray-800 whitespace-pre-wrap" id="email-body-${index}">${email.body || email.email_body || 'Pas de contenu'}</div>
            </div>
        </div>
    `).join('');
}

function toggleEmailSelection(index) {
    if (selectedEmailIndices.has(index)) {
        selectedEmailIndices.delete(index);
    } else {
        selectedEmailIndices.add(index);
    }
    
    const card = document.getElementById(`email-${index}`);
    card.classList.toggle('selected');
    updateEmailCounts();
}

function selectAllEmails() {
    currentEmails.forEach((_, index) => {
        selectedEmailIndices.add(index);
        const card = document.getElementById(`email-${index}`);
        if (card) card.classList.add('selected');
        const checkbox = document.getElementById(`checkbox-${index}`);
        if (checkbox) checkbox.checked = true;
    });
    updateEmailCounts();
}

function deselectAllEmails() {
    selectedEmailIndices.clear();
    currentEmails.forEach((_, index) => {
        const card = document.getElementById(`email-${index}`);
        if (card) card.classList.remove('selected');
        const checkbox = document.getElementById(`checkbox-${index}`);
        if (checkbox) checkbox.checked = false;
    });
    updateEmailCounts();
}

function editEmail(index) {
    const email = currentEmails[index];
    const bodyDiv = document.getElementById(`email-body-${index}`);
    
    const currentBody = bodyDiv.textContent;
    
    bodyDiv.innerHTML = `
        <textarea id="edit-body-${index}" class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500" rows="10">${currentBody}</textarea>
        <div class="flex justify-end space-x-2 mt-3">
            <button onclick="cancelEdit(${index}, \`${currentBody.replace(/`/g, '\\`')}\`)" class="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50">
                Annuler
            </button>
            <button onclick="saveEmail(${index})" class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700">
                Enregistrer
            </button>
        </div>
    `;
}

function cancelEdit(index, originalBody) {
    const bodyDiv = document.getElementById(`email-body-${index}`);
    bodyDiv.innerHTML = originalBody;
}

async function saveEmail(index) {
    const newBody = document.getElementById(`edit-body-${index}`).value;
    
    try {
        showLoading('Sauvegarde...');
        
        const updatedEmail = {
            ...currentEmails[index],
            body: newBody,
            email_body: newBody
        };
        
        await apiCall(`/emails/${index}`, 'PUT', updatedEmail);
        
        currentEmails[index] = updatedEmail;
        displayEmails();
        hideLoading();
        showToast('Email mis à jour avec succès', 'success');
    } catch (error) {
        hideLoading();
        showToast(error.message, 'error');
    }
}

async function generateEmails() {
    const confirmMsg = 'Cette action va générer de nouveaux emails pour toutes les startups non traitées.\n\nAssurez-vous que :\n- Votre clé API Gemini est configurée\n- Votre CV est à jour\n- La liste des startups est complète\n\nContinuer ?';
    
    if (!confirm(confirmMsg)) return;
    
    try {
        showLoading('Génération des emails en cours...\nCela peut prendre plusieurs minutes.');
        
        const result = await apiCall('/generate-emails', 'POST');
        
        hideLoading();
        showToast(`${result.count} emails générés avec succès !`, 'success');
        loadEmails();
        loadDashboard(); // Update stats
    } catch (error) {
        hideLoading();
        showToast('Erreur: ' + error.message, 'error');
    }
}

async function regenerateEmail(index) {
    showToast('Fonctionnalité de régénération individuelle à implémenter', 'info');
}

async function sendSelectedEmails() {
    if (selectedEmailIndices.size === 0) {
        showToast('⚠️ Veuillez sélectionner au moins un email à envoyer', 'error');
        return;
    }
    
    const confirmMsg = `Vous allez envoyer ${selectedEmailIndices.size} email(s).\n\nAssurez-vous que :\n- Vos credentials Gmail sont corrects\n- Vous avez vérifié le contenu des emails\n\nContinuer ?`;
    
    if (!confirm(confirmMsg)) return;
    
    try {
        showLoading(`Envoi de ${selectedEmailIndices.size} email(s) en cours...`);
        
        const result = await apiCall('/send-emails', 'POST', {
            indices: Array.from(selectedEmailIndices)
        });
        
        hideLoading();
        showToast(`✅ ${selectedEmailIndices.size} emails envoyés avec succès !`, 'success');
        
        // Clear selection
        selectedEmailIndices.clear();
        
        loadEmails();
        loadDashboard(); // Update stats
    } catch (error) {
        hideLoading();
        showToast('❌ Erreur: ' + error.message, 'error');
    }
}

// ========== Configuration Functions ==========

async function loadConfig() {
    try {
        showLoading('Chargement de la configuration...');
        
        const config = await apiCall('/config');
        currentConfig = config;
        
        // Fill AI config form
        if (config.gemini_api_key) {
            document.getElementById('gemini-api-key').value = config.gemini_api_key;
        }
        if (config.gemini_model) {
            document.getElementById('gemini-model').value = config.gemini_model;
        }
        if (config.email_prompt) {
            document.getElementById('email-prompt').value = config.email_prompt;
        }
        
        // Fill email config form
        if (config.gmail_user) {
            document.getElementById('gmail-user').value = config.gmail_user;
        }
        if (config.gmail_app_password) {
            document.getElementById('gmail-app-password').value = config.gmail_app_password;
        }
        if (config.resume_link) {
            document.getElementById('resume-link').value = config.resume_link;
        }
        
        // Update display
        updateConfigDisplay(config);
        
        hideLoading();
    } catch (error) {
        hideLoading();
        // Config might not exist yet, that's okay
        console.log('Config not loaded:', error);
    }
}

function updateConfigDisplay(config) {
    // API Key display
    const apiKeyDisplay = document.getElementById('display-api-key');
    if (config.gemini_api_key) {
        apiKeyDisplay.innerHTML = '<i class="fas fa-check-circle text-green-600 mr-1"></i>Configurée';
    } else {
        apiKeyDisplay.innerHTML = '<i class="fas fa-exclamation-circle text-orange-600 mr-1"></i>Non configurée';
    }
    
    // Gmail display
    const gmailDisplay = document.getElementById('display-gmail');
    if (config.gmail_user) {
        gmailDisplay.textContent = config.gmail_user;
    } else {
        gmailDisplay.innerHTML = '<i class="fas fa-exclamation-circle text-orange-600 mr-1"></i>Non configuré';
    }
    
    // Model display
    const modelDisplay = document.getElementById('display-model');
    modelDisplay.textContent = config.gemini_model || 'gemini-pro';
}

// AI Config Form
document.getElementById('ai-config-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    try {
        showLoading('Sauvegarde de la configuration IA...');
        
        const configData = {
            gemini_api_key: document.getElementById('gemini-api-key').value,
            gemini_model: document.getElementById('gemini-model').value,
            email_prompt: document.getElementById('email-prompt').value
        };
        
        await apiCall('/config', 'POST', configData);
        
        hideLoading();
        showToast('Configuration IA sauvegardée avec succès', 'success');
        loadConfig(); // Reload to update display
    } catch (error) {
        hideLoading();
        showToast(error.message, 'error');
    }
});

// Email Config Form
document.getElementById('email-config-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    try {
        showLoading('Sauvegarde de la configuration email...');
        
        const configData = {
            gmail_user: document.getElementById('gmail-user').value,
            gmail_app_password: document.getElementById('gmail-app-password').value,
            resume_link: document.getElementById('resume-link').value
        };
        
        await apiCall('/config', 'POST', configData);
        
        hideLoading();
        showToast('Configuration email sauvegardée avec succès', 'success');
        loadConfig(); // Reload to update display
    } catch (error) {
        hideLoading();
        showToast(error.message, 'error');
    }
});

async function testGmailConnection() {
    const gmailUser = document.getElementById('gmail-user').value;
    const gmailPassword = document.getElementById('gmail-app-password').value;
    
    if (!gmailUser || !gmailPassword) {
        showToast('Veuillez entrer votre email et mot de passe d\'application', 'error');
        return;
    }
    
    try {
        showLoading('Test de connexion Gmail...');
        
        const result = await apiCall('/test-gmail', 'POST', {
            gmail_user: gmailUser,
            gmail_app_password: gmailPassword
        });
        
        hideLoading();
        
        if (result.success) {
            document.getElementById('display-status').innerHTML = '<i class="fas fa-circle text-green-600 mr-1"></i>Connecté';
            showToast('✅ Connexion Gmail réussie !', 'success');
        } else {
            document.getElementById('display-status').innerHTML = '<i class="fas fa-circle text-red-600 mr-1"></i>Échec';
            showToast('❌ Connexion échouée: ' + result.error, 'error');
        }
    } catch (error) {
        hideLoading();
        document.getElementById('display-status').innerHTML = '<i class="fas fa-circle text-red-600 mr-1"></i>Erreur';
        showToast('❌ Erreur: ' + error.message, 'error');
    }
}

// ========== Initialization ==========

document.addEventListener('DOMContentLoaded', () => {
    // Load dashboard by default
    loadDashboard();
    
    // Set first nav button as active
    document.querySelector('.nav-btn').classList.add('active');
});
