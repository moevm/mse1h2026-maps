const sidebar = document.getElementById('sidebar');
const toggleBtn = document.getElementById('sidebarToggle');
const mainContent = document.getElementById('mainContent');
const graphPlaceholder = document.querySelector('.graph-placeholder');

toggleBtn.addEventListener('click', function() {
    sidebar.classList.toggle('collapsed');
    if (sidebar.classList.contains('collapsed')) {
        toggleBtn.textContent = '▶';
        mainContent.classList.add('expanded');
    } else {
        toggleBtn.textContent = '◀';
        mainContent.classList.remove('expanded');
    }
});

let statusPollInterval = null;
let currentGraphWidget = null;

// ===== ФУНКЦИЯ ОПРОСА СТАТУСА =====
async function checkRequestStatus(requestId) {
    try {
        const response = await fetch(`/api/status/?id=${requestId}`);
        const status = await response.text();
        
        
        const graphPlaceholder = document.querySelector('.graph-placeholder');
        
        switch(status) {
            case 'pending':
                graphPlaceholder.innerHTML = `
                    <div style="padding: 20px; text-align: center;">
                        <div style="color: #FF9800;">Запрос в очереди (pending)</div>
                        <div>ID: ${requestId}</div>
                        <div>Ожидание начала обработки...</div>
                    </div>
                `;
                break;
                
            case 'processing':
                graphPlaceholder.innerHTML = `
                    <div style="padding: 20px; text-align: center;">
                        <div style="color: #2196F3;">Запрос обрабатывается (processing)</div>
                        <div>ID: ${requestId}</div>
                        <div>Идет построение графа...</div>
                    </div>
                `;
                break;
                
            case 'completed':
                await loadGraphWidget(requestId);
                stopStatusPolling();
                break;
                
            case 'error':
                graphPlaceholder.innerHTML = `
                    <div style="padding: 20px; text-align: center;">
                        <div style="color: #f44336;">Ошибка выполнения запроса (error)</div>
                        <div>ID: ${requestId}</div>
                        <div>Что-то пошло не так</div>
                    </div>
                `;
                stopStatusPolling();
                break;
                
            default:
                graphPlaceholder.innerHTML = `
                    <div style="padding: 20px; text-align: center;">
                        <div>Неизвестный статус: ${status}</div>
                        <div>ID: ${requestId}</div>
                    </div>
                `;
        }
        
    } catch (error) {
        const graphPlaceholder = document.querySelector('.graph-placeholder');
        graphPlaceholder.innerHTML = `
            <div style="padding: 20px; text-align: center; color: #f44336;">
                Ошибка соединения с сервером
            </div>
        `;
    }
}

// ===== ЗАГРУЗКА ИНТЕРАКТИВНОГО ГРАФА =====
async function loadGraphWidget(requestId) {
    try {
        const graphPlaceholder = document.querySelector('.graph-placeholder');
        graphPlaceholder.innerHTML = '<div style="text-align: center; padding: 20px;">Загрузка графа...</div>';
        
        const response = await fetch(`/api/graph-widget/?id=${requestId}`);
        const data = await response.json();
        
        if (data.html) {
            graphPlaceholder.innerHTML = data.html;
            
            setTimeout(() => {
                setupGraphEvents();
            }, 1000);
        } else {
            graphPlaceholder.innerHTML = '<div style="color: #f44336;">Ошибка: не удалось загрузить граф</div>';
        }
        
    } catch (error) {
        graphPlaceholder.innerHTML = `
            <div style="padding: 20px; text-align: center; color: #f44336;">
                Ошибка загрузки графа: ${error.message}
            </div>
        `;
    }
}

// ===== НАСТРОЙКА ОБРАБОТЧИКОВ СОБЫТИЙ ДЛЯ ГРАФА =====
function setupGraphEvents() {
    
    document.addEventListener('nvl:node-click', function(event) {
        handleNodeInteraction(event.detail, 'node');
    });
    
    document.addEventListener('nvl:edge-click', function(event) {
        handleNodeInteraction(event.detail, 'edge');
    });
    
    window.addEventListener('message', function(event) {
        if (event.origin !== window.location.origin) return;
        
        const data = event.data;
        if (data && data.type === 'graph-click') {
            if (data.nodeId) {
                handleNodeInteraction({ id: data.nodeId }, 'node');
            } else if (data.edgeId) {
                handleNodeInteraction({ id: data.edgeId }, 'edge');
            }
        }
    });
    
    if (window.graphWidget) {
        window.graphWidget.onNodeClick = function(nodeId, nodeData) {
            handleNodeInteraction({ id: nodeId, data: nodeData }, 'node');
        };
        window.graphWidget.onEdgeClick = function(edgeId, edgeData) {
            handleNodeInteraction({ id: edgeId, data: edgeData }, 'edge');
        };
    }
    
    const graphContainer = document.querySelector('.graph-placeholder');
    if (graphContainer) {
        graphContainer.style.cursor = 'pointer';
        
        const tooltip = document.createElement('div');
        tooltip.textContent = 'Кликните по узлу для просмотра информации';
        tooltip.style.cssText = `
            position: absolute;
            bottom: 10px;
            right: 10px;
            background: rgba(0,0,0,0.7);
            color: white;
            padding: 5px 10px;
            border-radius: 5px;
            font-size: 12px;
            z-index: 100;
            pointer-events: none;
        `;
        graphContainer.style.position = 'relative';
        graphContainer.appendChild(tooltip);
        
        setTimeout(() => {
            tooltip.style.opacity = '0';
            tooltip.style.transition = 'opacity 1s';
            setTimeout(() => tooltip.remove(), 1000);
        }, 5000);
    }
}

// ===== ОБРАБОТКА ВЗАИМОДЕЙСТВИЯ С УЗЛОМ/РЕБРОМ =====
async function handleNodeInteraction(data, type) {
    
    let nodeId = data.id || data.nodeId;
    let nodeData = data.data || {};
    
    try {
        const entityName = document.getElementById('entityName');
        const entityInfo = document.getElementById('entityInfo');
        
        entityName.textContent = 'Загрузка...';
        entityInfo.textContent = 'Получение данных...';
        
        const response = await fetch(`/api/node-info/?id=${encodeURIComponent(nodeId)}&type=${type}`);
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        
        const nodeInfo = await response.json();
        
        openInfoPanel({
            name: nodeInfo.name || `Узел ${nodeId}`,
            info: nodeInfo.info || 'Информация отсутствует',
            links: nodeInfo.links || [],
            resources: nodeInfo.resources || []
        });
        
    } catch (error) {
        openInfoPanel({
            name: nodeData.name || `Узел ${nodeId}`,
            info: nodeData.info || 'Информация временно недоступна. Ошибка: ' + error.message,
            links: nodeData.links || [],
            resources: nodeData.resources || []
        });
    }
}

function startStatusPolling(requestId) {
    if (statusPollInterval) clearInterval(statusPollInterval);
    checkRequestStatus(requestId);
    statusPollInterval = setInterval(() => checkRequestStatus(requestId), 2000);
}

function stopStatusPolling() {
    if (statusPollInterval) {
        clearInterval(statusPollInterval);
        statusPollInterval = null;
    }
}

// ===== ОТПРАВКА ЗАПРОСА =====
async function sendToDjango(keyWords, options) {
    try {
        const graphPlaceholder = document.querySelector('.graph-placeholder');
        graphPlaceholder.innerHTML = 'Отправка запроса...';
        
        const params = new URLSearchParams();
        params.append('topic', keyWords);
        
        for (let [key, value] of Object.entries(options)) {
            params.append(key, value);
        }

        const response = await fetch(`/api/start/?${params.toString()}`);
        const requestId = await response.text();
        
        graphPlaceholder.innerHTML = `
            <div style="color: #44cc44;">Запрос отправлен!</div>
            <div>ID: ${requestId}</div>
            <div>Опрашиваем статус...</div>
        `;
        
        startStatusPolling(requestId);
        
    } catch (error) {
        document.querySelector('.graph-placeholder').innerHTML = `
            <div style="color: #ff6b6b;">Ошибка: ${error.message}</div>
        `;
    }
}

function drawGraph(keyWords, options) {
    stopStatusPolling();
    sendToDjango(keyWords, options);
}

function getOptions() {
    const checkboxes = document.querySelectorAll('.sidebar-content input[type="checkbox"]');
    const options = {};
    
    checkboxes.forEach(checkbox => {
        const label = document.querySelector(`label[for="${checkbox.id}"]`);
        const key = label ? label.textContent.trim() : checkbox.id;
        options[key] = checkbox.checked;
    });
    
    return options;
}

// ===== ПОИСК =====
const searchButton = document.querySelector('.search-button');
const searchField = document.getElementById('searchField');

if (searchButton && searchField) {
    searchButton.addEventListener('click', () => {
        drawGraph(searchField.value, getOptions());
    });
    
    searchField.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') drawGraph(searchField.value, getOptions());
    });
}

// ===== ВЫДВИЖНАЯ ПАНЕЛЬ =====
const infoPanel = document.getElementById('infoPanel');
const closeInfoPanel = document.getElementById('closeInfoPanel');

const overlay = document.createElement('div');
overlay.className = 'info-panel-overlay';
document.body.appendChild(overlay);

function openInfoPanel(entityData) {
    document.getElementById('entityName').textContent = entityData.name || 'Название не указано';
    document.getElementById('entityInfo').textContent = entityData.info || 'Информация отсутствует';
    
    const linksList = document.getElementById('entityLinks');
    linksList.innerHTML = '';
    if (entityData.links && entityData.links.length > 0) {
        entityData.links.forEach(link => {
            const li = document.createElement('li');
            li.textContent = link;
            linksList.appendChild(li);
        });
    } else {
        linksList.innerHTML = '<li>Нет связей</li>';
    }
    
    const resourcesList = document.getElementById('entityResources');
    resourcesList.innerHTML = '';
    if (entityData.resources && entityData.resources.length > 0) {
        entityData.resources.forEach(resource => {
            const li = document.createElement('li');
            const a = document.createElement('a');
            a.href = resource.url || '#';
            a.textContent = resource.name || resource;
            a.target = '_blank';
            li.appendChild(a);
            resourcesList.appendChild(li);
        });
    } else {
        resourcesList.innerHTML = '<li>Нет ссылок</li>';
    }
    
    infoPanel.classList.add('open');
    overlay.classList.add('active');
}

function closeInfoPanelFunction() {
    infoPanel.classList.remove('open');
    overlay.classList.remove('active');
}

graphPlaceholder.addEventListener('click', function(event) {
    const isGraphLoaded = document.querySelector('.graph-placeholder canvas, .graph-placeholder iframe');
    
    if (!isGraphLoaded) {
        const testEntityData = {
            name: 'Пример сущности (тест)',
            info: 'Это демонстрационная информация. Когда граф загрузится, клики по узлам будут показывать реальные данные.',
            links: ['Связанная сущность 1', 'Связанная сущность 2', 'Связанная сущность 3'],
            resources: [
                { name: 'Википедия', url: 'https://ru.wikipedia.org' },
                { name: 'Официальный сайт', url: 'https://example.com' },
                { name: 'Документация', url: 'https://docs.example.com' }
            ]
        };
        openInfoPanel(testEntityData);
    }
});

if (closeInfoPanel) {
    closeInfoPanel.addEventListener('click', closeInfoPanelFunction);
}

overlay.addEventListener('click', closeInfoPanelFunction);

document.addEventListener('keydown', function(event) {
    if (event.key === 'Escape' && infoPanel.classList.contains('open')) {
        closeInfoPanelFunction();
    }
});
