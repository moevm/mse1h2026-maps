// Ждем загрузки DOM

document.addEventListener('DOMContentLoaded', () => {
    console.log('DOM загружен, инициализация...');
    
    const sidebar = document.getElementById('sidebar');
    const toggleBtn = document.getElementById('sidebarToggle');
    const mainContent = document.getElementById('mainContent');
    const graphPlaceholder = document.querySelector('.graph-placeholder');
    const searchButton = document.querySelector('.search-button');
    const searchField = document.getElementById('searchField');

    let statusPollInterval = null;
    let network = null;
    
    if (typeof vis === 'undefined') {
        console.error('vis.js не загружена!');
        if (graphPlaceholder) {
            graphPlaceholder.innerHTML = `
                <div style="padding: 20px; text-align: center; color: #f44336;">
                    <div>Ошибка: vis.js библиотека не загружена</div>
                    <div>Проверьте файл static/libs/vis-network.min.js</div>
                </div>
            `;
        }
        return;
    }
    
    console.log('vis.js загружена успешно, версия:', vis.version);
    
    // Toggle sidebar
    if (toggleBtn) {
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
    }
    
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
            console.error('Ошибка в checkRequestStatus:', error);
            const graphPlaceholder = document.querySelector('.graph-placeholder');
            if (graphPlaceholder) {
                graphPlaceholder.innerHTML = `
                    <div style="padding: 20px; text-align: center; color: #f44336;">
                        Ошибка соединения с сервером: ${error.message}
                    </div>
                `;
            }
        }
    }
    
    // ===== ЗАГРУЗКА ИНТЕРАКТИВНОГО ГРАФА =====
    async function loadGraphWidget(requestId) {
        try {
            const graphPlaceholder = document.querySelector('.graph-placeholder');
            graphPlaceholder.innerHTML = '<div style="text-align: center; padding: 20px;">Загрузка графа...</div>';
            
            const response = await fetch(`/api/graph-widget/?id=${requestId}`);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const data = await response.json();
            console.log('Получены данные графа:', data);
            
            if (data.nodes && data.relationships) {
                if (data.nodes.length === 0) {
                    graphPlaceholder.innerHTML = `
                        <div style="padding: 20px; text-align: center; color: #FF9800;">
                            <div>Граф не содержит узлов</div>
                            <div>Попробуйте изменить поисковый запрос</div>
                        </div>
                    `;
                    return;
                }
                
                graphPlaceholder.innerHTML = '';
                
                const graphContainer = document.createElement('div');
                graphContainer.id = 'graph-container';
                graphContainer.style.width = '100%';
                graphContainer.style.height = '100%';
                graphContainer.style.minHeight = '600px';
                graphContainer.style.position = 'relative';
                graphContainer.style.border = '1px solid #ddd';
                graphContainer.style.borderRadius = '4px';
                graphContainer.style.backgroundColor = '#f5f5f5';
                graphPlaceholder.appendChild(graphContainer);
                
                const nodes = data.nodes.map(node => ({
                    id: node.id,
                    label: node.properties?.label_en || node.caption || node.properties?.name || node.id,
                    title: node.properties?.info || 'Нет информации',
                    group: node.labels?.[0] || 'default',
                    font: { size: 14, color: '#000000' }
                }));
                
                const edges = data.relationships.map(rel => ({
                    id: rel.id,
                    from: rel.from,
                    to: rel.to,
                    label: rel.caption || rel.properties?.type || 'связь',
                    arrows: 'to',
                    font: { size: 12, align: 'middle' }
                }));
                
                console.log('Создание графа:', { nodesCount: nodes.length, edgesCount: edges.length });
                
                const nodesDataSet = new vis.DataSet(nodes);
                const edgesDataSet = new vis.DataSet(edges);
                
                const options = {
                    nodes: {
                        shape: 'dot',
                        size: 25,
                        borderWidth: 2,
                        borderWidthSelected: 3,
                        shadow: true,
                        font: { size: 14, color: '#000000' }
                    },
                    edges: {
                        width: 2,
                        shadow: true,
                        smooth: {
                            type: 'continuous',
                            roundness: 0.5
                        },
                        font: { size: 12, align: 'middle' }
                    },
                    physics: {
                        enabled: true,
                        stabilization: true,
                        barnesHut: {
                            gravitationalConstant: -8000,
                            springConstant: 0.001,
                            springLength: 200
                        }
                    },
                    interaction: {
                        hover: true,
                        tooltipDelay: 200,
                        navigationButtons: true,
                        keyboard: true
                    }
                };
                
                network = new vis.Network(graphContainer, { nodes: nodesDataSet, edges: edgesDataSet }, options);
                
                network.on('click', function(params) {
                    if (params.nodes.length > 0) {
                        const nodeId = params.nodes[0];
                        const node = nodes.find(n => n.id === nodeId);
                        if (node) {
                            openInfoPanel({
                                name: node.label,
                                info: node.title || 'Нет дополнительной информации',
                                links: [],
                                resources: []
                            });
                        }
                    } else if (params.edges.length > 0) {
                        const edgeId = params.edges[0];
                        const edge = edges.find(e => e.id === edgeId);
                        if (edge) {
                            openInfoPanel({
                                name: `Связь: ${edge.label}`,
                                info: `Связь между узлами`,
                                links: [],
                                resources: []
                            });
                        }
                    }
                });
                
                // Центрируем граф
                setTimeout(() => {
                    if (network) {
                        network.fit();
                    }
                }, 500);
                
            } else {
                throw new Error('Неверный формат данных графа');
            }
            
        } catch (error) {
            console.error('Ошибка загрузки графа:', error);
            const graphPlaceholder = document.querySelector('.graph-placeholder');
            if (graphPlaceholder) {
                graphPlaceholder.innerHTML = `
                    <div style="padding: 20px; text-align: center; color: #f44336;">
                        <div>Ошибка загрузки графа: ${error.message}</div>
                    </div>
                `;
            }
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
            // Уничтожаем предыдущий граф
            if (network) {
                network.destroy();
                network = null;
            }
            
            const graphPlaceholder = document.querySelector('.graph-placeholder');
            if (graphPlaceholder) {
                graphPlaceholder.innerHTML = `
                    <div style="padding: 20px; text-align: center;">
                        <div>Отправка запроса...</div>
                        <div style="color: #2196F3;">Тема: ${keyWords}</div>
                    </div>
                `;
            }
            
            const params = new URLSearchParams();
            params.append('topic', keyWords);
            
            for (let [key, value] of Object.entries(options)) {
                params.append(key, value);
            }
            
            const response = await fetch(`/api/start/?${params.toString()}`);
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            
            const requestId = await response.text();
            console.log('Получен requestId:', requestId);
            
            if (graphPlaceholder) {
                graphPlaceholder.innerHTML = `
                    <div style="padding: 20px; text-align: center;">
                        <div style="color: #44cc44;">✓ Запрос отправлен!</div>
                        <div>ID: ${requestId}</div>
                        <div>Опрашиваем статус...</div>
                    </div>
                `;
            }
            
            startStatusPolling(requestId);
            
        } catch (error) {
            console.error('Ошибка отправки запроса:', error);
            const graphPlaceholder = document.querySelector('.graph-placeholder');
            if (graphPlaceholder) {
                graphPlaceholder.innerHTML = `
                    <div style="padding: 20px; text-align: center; color: #ff6b6b;">
                        <div>❌ Ошибка: ${error.message}</div>
                    </div>
                `;
            }
        }
    }
    
    function drawGraph(keyWords, options) {
        if (!keyWords || keyWords.trim() === '') {
            alert('Пожалуйста, введите поисковый запрос');
            return;
        }
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
    if (searchButton && searchField) {
        console.log('Навешиваем обработчики на кнопку поиска');
        
        const handleSearch = () => {
            console.log('Поиск:', searchField.value);
            drawGraph(searchField.value, getOptions());
        };
        
        searchButton.addEventListener('click', handleSearch);
        searchField.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                console.log('Enter нажат');
                handleSearch();
            }
        });
    } else {
        console.error('Кнопка или поле поиска не найдены!');
    }
    
    // ===== ВЫДВИЖНАЯ ПАНЕЛЬ =====
    const infoPanel = document.getElementById('infoPanel');
    const closeInfoPanel = document.getElementById('closeInfoPanel');
    
    const overlay = document.createElement('div');
    overlay.className = 'info-panel-overlay';
    overlay.style.cssText = `
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background: rgba(0,0,0,0.5);
        z-index: 999;
        display: none;
    `;
    document.body.appendChild(overlay);
    
    function openInfoPanel(entityData) {
        console.log('Открываем панель:', entityData);
        
        const entityName = document.getElementById('entityName');
        const entityInfo = document.getElementById('entityInfo');
        const linksList = document.getElementById('entityLinks');
        const resourcesList = document.getElementById('entityResources');
        
        if (entityName) entityName.textContent = entityData.name || 'Название не указано';
        if (entityInfo) entityInfo.textContent = entityData.info || 'Информация отсутствует';
        
        if (linksList) {
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
        }
        
        if (resourcesList) {
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
        }
        
        if (infoPanel) {
            infoPanel.classList.add('open');
            infoPanel.style.display = 'block';
        }
        if (overlay) overlay.style.display = 'block';
    }
    
    function closeInfoPanelFunction() {
        if (infoPanel) {
            infoPanel.classList.remove('open');
            infoPanel.style.display = 'none';
        }
        if (overlay) overlay.style.display = 'none';
    }
    
    if (closeInfoPanel) {
        closeInfoPanel.addEventListener('click', closeInfoPanelFunction);
    }
    
    if (overlay) {
        overlay.addEventListener('click', closeInfoPanelFunction);
    }
    
    document.addEventListener('keydown', function(event) {
        if (event.key === 'Escape' && infoPanel && infoPanel.classList.contains('open')) {
            closeInfoPanelFunction();
        }
    });
    
    console.log('Приложение полностью инициализировано');
});
