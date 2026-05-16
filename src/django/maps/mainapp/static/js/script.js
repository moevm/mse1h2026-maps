// Ждем загрузки DOM
document.addEventListener('DOMContentLoaded', () => {
    console.log('DOM загружен, инициализация...');

    const sidebar = document.getElementById('sidebar');
    const toggleBtn = document.getElementById('sidebarToggle');
    const mainContent = document.getElementById('mainContent');
    const graphPlaceholder = document.getElementById('graphPlaceholder');
    const searchButton = document.querySelector('.search-button');
    const searchField = document.getElementById('searchField');
    
    // Элементы прогресса (отдельный тост)
    const progressToast = document.getElementById('progressToast');
    const progressRequestIdSpan = document.getElementById('progressRequestId');
    const progressStatusValue = document.getElementById('progressStatusValue');
    const progressSourcesList = document.getElementById('progressSourcesList');
    const progressCloseBtn = document.getElementById('progressCloseBtn');

    let statusPollInterval = null;
    let network = null;
    let isAuthenticated = false;
    let currentRequestId = null;
    let lastInfoState = {};

    // Функции для управления клавиатурой графа
    function enableGraphKeyboard() {
        if (network && network.setOptions) {
            network.setOptions({ interaction: { keyboard: true } });
            console.log('Клавиатура графа ВКЛЮЧЕНА');
        }
    }

    function disableGraphKeyboard() {
        if (network && network.setOptions) {
            network.setOptions({ interaction: { keyboard: false } });
            console.log('Клавиатура графа ВЫКЛЮЧЕНА');
        }
    }

    // Настройка отслеживания фокуса на полях ввода
    function setupInputFocusTracking() {
        const inputs = document.querySelectorAll('input, textarea');
        
        inputs.forEach(input => {
            input.removeEventListener('focus', disableGraphKeyboard);
            input.removeEventListener('blur', enableGraphKeyboard);
            input.addEventListener('focus', disableGraphKeyboard);
            input.addEventListener('blur', enableGraphKeyboard);
        });
    }

    // ===== НАСТРОЙКА ОБРАБОТЧИКА КЛИКА =====
    function setupNetworkClickHandler(data, edges) {
        if (!network) return;
        
        network.off('click');
        
        network.on('click', function(params) {
            if (params.nodes.length > 0) {
                const nodeId = params.nodes[0];
                const originalNode = data.nodes.find(n => n.id === nodeId);
                if (originalNode) {
                    const props = originalNode.properties || {};
                    
                    const connectedRelationships = data.relationships.filter(rel => 
                        rel.from === nodeId || rel.to === nodeId
                    );
                    
                    const connectedNodes = connectedRelationships.map(rel => {
                        const targetId = rel.from === nodeId ? rel.to : rel.from;
                        const targetNode = data.nodes.find(n => n.id === targetId);
                        const targetProps = targetNode?.properties || {};
                        return {
                            type: rel.caption || rel.properties?.type || 'связь',
                            target: targetProps.label_en || targetNode?.caption || targetId
                        };
                    });
                    
                    const resources = [];
                    const addedUrls = new Set();
                    
                    if (props.url && !addedUrls.has(props.url)) {
                        resources.push({ name: 'Википедия', url: props.url });
                        addedUrls.add(props.url);
                    }
                    
                    if (props.wiki_url && !addedUrls.has(props.wiki_url)) {
                        resources.push({ name: 'Wikidata', url: props.wiki_url });
                        addedUrls.add(props.wiki_url);
                    }
                    
                    if (props.uid && props.uid.startsWith('wikidata:') && !addedUrls.has(`https://www.wikidata.org/wiki/${props.uid.split(':')[1]}`)) {
                        const wikidataId = props.uid.split(':')[1];
                        resources.push({ 
                            name: 'Wikidata', 
                            url: `https://www.wikidata.org/wiki/${wikidataId}` 
                        });
                        addedUrls.add(`https://www.wikidata.org/wiki/${wikidataId}`);
                    }
                    
                    if (originalNode.labels?.includes('Paper') && props.paperId && !addedUrls.has(props.paperId)) {
                        resources.push({ 
                            name: props.label_en || 'Научная статья', 
                            url: props.paperId 
                        });
                        addedUrls.add(props.paperId);
                    }
                    
                    openInfoPanel({
                        name: props.label_en || originalNode.caption || nodeId,
                        desc_en: props.desc_en || props.description || props.abstract || 'Нет описания',
                        info: props.info,
                        links: connectedNodes,
                        resources: resources,
                        ...props
                    });
                }
            } else if (params.edges.length > 0) {
                const edgeId = params.edges[0];
                const edge = edges.find(e => e.id === edgeId);
                if (edge) {
                    openInfoPanel({
                        name: `Связь: ${edge.label}`,
                        desc_en: `Тип: ${edge.caption || edge.label}\nОт: ${edge.from}\nК: ${edge.to}`,
                        info: `Тип связи: ${edge.caption || edge.label}`,
                        links: [],
                        resources: []
                    });
                }
            }
        });
    }

    // ===== АУТЕНТИФИКАЦИЯ =====

    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }

    async function checkAuthStatus() {
        try {
            const response = await fetch('/accounts/user-status/');
            if (response.ok) {
                const data = await response.json();
                isAuthenticated = data.is_authenticated;
                if (isAuthenticated) {
                    hideLoginModal();
                    showUserInfo(data.username);
                    console.log('Пользователь уже авторизован:', data.username);
                } else {
                    showLoginModal();
                    hideUserInfo();
                    console.log('Пользователь не авторизован');
                }
            } else {
                showLoginModal();
            }
        } catch (error) {
            console.error('Ошибка проверки аутентификации:', error);
            showLoginModal();
        }
    }

    function showLoginModal() {
        const modal = document.getElementById('loginModal');
        const registerModal = document.getElementById('registerModal');
        const overlay = document.getElementById('modalOverlay');
        const appContainer = document.querySelector('.app-container');
        
        if (registerModal) registerModal.style.display = 'none';
        if (modal && overlay) {
            modal.style.display = 'block';
            overlay.style.display = 'block';
            if (appContainer) {
                appContainer.classList.add('blurred');
            }
        }
    }

    function hideLoginModal() {
        const modal = document.getElementById('loginModal');
        const registerModal = document.getElementById('registerModal');
        const overlay = document.getElementById('modalOverlay');
        const appContainer = document.querySelector('.app-container');
        
        if (modal) modal.style.display = 'none';
        if (registerModal && registerModal.style.display === 'block') return;
        
        if (overlay) overlay.style.display = 'none';
        if (appContainer) appContainer.classList.remove('blurred');
    }

    function showRegisterModal() {
        const modal = document.getElementById('registerModal');
        const loginModal = document.getElementById('loginModal');
        const overlay = document.getElementById('modalOverlay');
        const appContainer = document.querySelector('.app-container');
        
        if (loginModal) loginModal.style.display = 'none';
        if (modal && overlay) {
            modal.style.display = 'block';
            overlay.style.display = 'block';
            if (appContainer) {
                appContainer.classList.add('blurred');
            }
            const errorDiv = document.getElementById('registerError');
            const successDiv = document.getElementById('registerSuccess');
            if (errorDiv) errorDiv.style.display = 'none';
            if (successDiv) successDiv.style.display = 'none';
        }
    }

    function hideRegisterModal() {
        const modal = document.getElementById('registerModal');
        const loginModal = document.getElementById('loginModal');
        const overlay = document.getElementById('modalOverlay');
        const appContainer = document.querySelector('.app-container');
        
        if (modal) modal.style.display = 'none';
        if (loginModal && loginModal.style.display === 'block') return;
        
        if (overlay) overlay.style.display = 'none';
        if (appContainer) appContainer.classList.remove('blurred');
    }

    function showUserInfo(username) {
        const userInfo = document.getElementById('userInfo');
        const usernameDisplay = document.getElementById('usernameDisplay');
        if (userInfo && usernameDisplay) {
            usernameDisplay.textContent = `Вы вошли как: ${username}`;
            userInfo.style.display = 'flex';
        }
        loadHistory(); // Загружаем историю при входе
    }

    function hideUserInfo() {
        const userInfo = document.getElementById('userInfo');
        if (userInfo) {
            userInfo.style.display = 'none';
        }
    }

    function showLoginError(message) {
        const errorDiv = document.getElementById('loginError');
        if (errorDiv) {
            errorDiv.textContent = message;
            errorDiv.style.display = 'block';
            setTimeout(() => {
                errorDiv.style.display = 'none';
            }, 3000);
        }
    }

    function showRegisterError(message) {
        const errorDiv = document.getElementById('registerError');
        const successDiv = document.getElementById('registerSuccess');
        if (errorDiv) {
            if (successDiv) successDiv.style.display = 'none';
            errorDiv.textContent = message;
            errorDiv.style.display = 'block';
            setTimeout(() => {
                errorDiv.style.display = 'none';
            }, 3000);
        }
    }

    function showRegisterSuccess(message) {
        const successDiv = document.getElementById('registerSuccess');
        const errorDiv = document.getElementById('registerError');
        if (successDiv) {
            if (errorDiv) errorDiv.style.display = 'none';
            successDiv.textContent = message;
            successDiv.style.display = 'block';
        }
    }

    async function handleLogin(event) {
        event.preventDefault();
        
        const username = document.getElementById('loginUsername').value;
        const password = document.getElementById('loginPassword').value;
        
        try {
            const formData = new URLSearchParams();
            formData.append('username', username);
            formData.append('password', password);
            
            const response = await fetch('/accounts/login/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'X-CSRFToken': getCookie('csrftoken')
                },
                body: formData
            });
            
            await new Promise(resolve => setTimeout(resolve, 200));
            
            const statusResponse = await fetch('/accounts/user-status/');
            const statusData = await statusResponse.json();
            
            if (statusData.is_authenticated) {
                isAuthenticated = true;
                hideLoginModal();
                showUserInfo(statusData.username);
                if (network) {
                    network.destroy();
                    network = null;
                }
                if (graphPlaceholder) {
                    graphPlaceholder.innerHTML = 'Введите запрос для поиска';
                }
                setTimeout(() => enableGraphKeyboard(), 100);
                console.log('Вход выполнен успешно');
            } else {
                showLoginError('Неверный логин или пароль');
            }
        } catch (error) {
            console.error('Ошибка входа:', error);
            showLoginError('Ошибка соединения с сервером');
        }
    }

    async function handleRegister(event) {
        event.preventDefault();
        
        const username = document.getElementById('regUsername').value;
        const password = document.getElementById('regPassword').value;
        const passwordConfirm = document.getElementById('regPasswordConfirm').value;
        
        if (password !== passwordConfirm) {
            showRegisterError('Пароли не совпадают');
            return;
        }
        
        try {
            const formData = new URLSearchParams();
            formData.append('username', username);
            formData.append('password', password);
            
            const response = await fetch('/accounts/register/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'X-CSRFToken': getCookie('csrftoken')
                },
                body: formData
            });
            
            if (response.ok) {
                showRegisterSuccess('Регистрация успешна! Теперь вы можете войти.');
                setTimeout(() => {
                    hideRegisterModal();
                    showLoginModal();
                    document.getElementById('registerForm').reset();
                }, 2000);
            } else {
                const errorText = await response.text();
                if (errorText.includes('already exists')) {
                    showRegisterError('Пользователь с таким именем уже существует');
                } else {
                    showRegisterError('Ошибка регистрации. Попробуйте снова.');
                }
            }
        } catch (error) {
            console.error('Ошибка регистрации:', error);
            showRegisterError('Ошибка соединения с сервером');
        }
    }

    async function handleLogout() {
        try {
            const response = await fetch('/logout/', {
                method: 'POST',
                headers: {
                    'X-CSRFToken': getCookie('csrftoken')
                }
            });
            
            if (response.ok) {
                isAuthenticated = false;
                hideUserInfo();
                showLoginModal();
                if (network) {
                    network.destroy();
                    network = null;
                }
                if (graphPlaceholder) {
                    graphPlaceholder.innerHTML = 'Войдите в систему для просмотра графа';
                }
                hideProgress();
            }
        } catch (error) {
            console.error('Ошибка выхода:', error);
        }
    }

    function requireAuth() {
        if (!isAuthenticated) {
            showLoginModal();
            return false;
        }
        return true;
    }

    // ===== УПРАВЛЕНИЕ ПРОГРЕССОМ (ТОСТ) =====
    function showProgress(requestId, status, info) {
        if (progressToast) {
            progressToast.style.display = 'block';
            if (progressRequestIdSpan) {
                progressRequestIdSpan.textContent = requestId;
            }
            if (progressStatusValue) {
                progressStatusValue.textContent = status;
                progressStatusValue.className = `status-${status}`;
            }
            updateProgressInfo(info);
        }
    }

    function updateProgressInfo(info) {
        if (!progressSourcesList) return;
        
        const sources = Object.entries(info);
        if (sources.length === 0) {
            progressSourcesList.innerHTML = '<li>Ожидание данных...</li>';
            return;
        }
        
        progressSourcesList.innerHTML = sources.map(([source, state]) => {
            let statusText = '';
            let statusClass = '';
            if (state === 'Done') {
                statusText = '✓ Готово';
                statusClass = 'done';
            } else if (state === 'Processing') {
                statusText = '⏳ Обработка...';
                statusClass = 'processing';
            } else {
                statusText = '⏸ Ожидание';
                statusClass = 'pending';
            }
            return `<li class="${statusClass}">${source}: ${statusText}</li>`;
        }).join('');
    }

    function hideProgress() {
        if (progressToast) {
            progressToast.style.display = 'none';
        }
    }

    if (progressCloseBtn) {
        progressCloseBtn.addEventListener('click', () => {
            hideProgress();
            if (statusPollInterval) {
                stopStatusPolling();
            }
        });
    }

    // ===== ФУНКЦИЯ ОПРОСА СТАТУСА =====
    async function checkRequestStatus(requestId) {
        if (!requireAuth()) return;
        
        try {
            const response = await fetch(`/api/status/?id=${requestId}`);
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            
            const data = await response.json();
            const status = data.Status;
            const info = data.Info || {};
            
            console.log('Статус запроса:', status, 'Info:', info);
            
            showProgress(requestId, status, info);
            
            const infoChanged = hasInfoChanged(info);
            
            if (status === 'processing' && infoChanged) {
                console.log('Info изменился, обновляем граф...');
                await loadGraphWidget(requestId);
            }
            
            if (status === 'completed') {
                console.log('Запрос завершен, финальное обновление графа...');
                await loadGraphWidget(requestId);
                if (progressStatusValue) {
                    progressStatusValue.textContent = 'completed';
                    progressStatusValue.className = 'status-completed';
                }
                setTimeout(() => {
                    hideProgress();
                }, 2000);
                stopStatusPolling();
            }
            
            if (status === 'error') {
                if (progressStatusValue) {
                    progressStatusValue.textContent = 'error';
                    progressStatusValue.className = 'status-error';
                }
                setTimeout(() => {
                    hideProgress();
                }, 3000);
                stopStatusPolling();
                if (graphPlaceholder) {
                    graphPlaceholder.innerHTML = `
                        <div style="padding: 20px; text-align: center; color: #f44336;">
                            <div>❌ Ошибка выполнения запроса</div>
                            <div>ID: ${requestId}</div>
                        </div>
                    `;
                }
            }
            
            lastInfoState = { ...info };

        } catch (error) {
            console.error('Ошибка в checkRequestStatus:', error);
            hideProgress();
            if (graphPlaceholder) {
                graphPlaceholder.innerHTML = `
                    <div style="padding: 20px; text-align: center; color: #f44336;">
                        Ошибка соединения с сервером: ${error.message}
                    </div>
                `;
            }
        }
    }

    function hasInfoChanged(newInfo) {
        const newSources = Object.keys(newInfo);
        const oldSources = Object.keys(lastInfoState);
        
        if (newSources.length !== oldSources.length) {
            return true;
        }
        
        for (const source of newSources) {
            if (newInfo[source] !== lastInfoState[source]) {
                return true;
            }
        }
        
        return false;
    }

    // ===== ОБНОВЛЕНИЕ ГРАФА =====
    function updateGraph(data) {
        if (!network) {
            createNewGraph(data);
            return;
        }
        
        try {
            const nodesDataSet = network.body.data.nodes;
            const edgesDataSet = network.body.data.edges;
            
            const nodes = data.nodes.map(node => ({
                id: node.id,
                label: node.properties?.label_en || node.caption || node.properties?.name || node.id,
                title: node.properties?.desc_en || node.properties?.info || 'Нет информации',
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
            
            const existingNodeIds = new Set(nodesDataSet.getIds());
            const existingEdgeIds = new Set(edgesDataSet.getIds());
            
            const newNodeIds = new Set(nodes.map(n => n.id));
            const newEdgeIds = new Set(edges.map(e => e.id));
            
            const nodesToRemove = [...existingNodeIds].filter(id => !newNodeIds.has(id));
            const edgesToRemove = [...existingEdgeIds].filter(id => !newEdgeIds.has(id));
            
            if (nodesToRemove.length) nodesDataSet.remove(nodesToRemove);
            if (edgesToRemove.length) edgesDataSet.remove(edgesToRemove);
            
            const nodesToAdd = nodes.filter(node => !existingNodeIds.has(node.id));
            if (nodesToAdd.length) nodesDataSet.add(nodesToAdd);
            
            const nodesToUpdate = nodes.filter(node => existingNodeIds.has(node.id));
            if (nodesToUpdate.length) nodesDataSet.update(nodesToUpdate);
            
            const edgesToAdd = edges.filter(edge => !existingEdgeIds.has(edge.id));
            if (edgesToAdd.length) edgesDataSet.add(edgesToAdd);
            
            const edgesToUpdate = edges.filter(edge => existingEdgeIds.has(edge.id));
            if (edgesToUpdate.length) edgesDataSet.update(edgesToUpdate);
            
            console.log('Граф обновлен');
            
            setupInputFocusTracking();
            
            setupNetworkClickHandler(data, edges);
            
            if (existingNodeIds.size === 0 && nodes.length > 0) {
                setTimeout(() => {
                    if (network) network.fit();
                }, 500);
            }
            
        } catch (error) {
            console.error('Ошибка обновления графа:', error);
            createNewGraph(data);
        }
    }

    function createNewGraph(data) {
        if (!graphPlaceholder) return;
        
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
            title: node.properties?.desc_en || node.properties?.info || 'Нет информации',
            group: node.labels?.[0] || 'default',
            font: { size: 14, color: '#000000' }
        }));
        
        const edges = data.relationships.map(rel => ({
            id: rel.id,
            from: rel.from,
            to: rel.to,
            label: rel.caption || rel.properties?.type || 'связь',
            caption: rel.caption,
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
                smooth: { type: 'continuous', roundness: 0.5 },
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
        
        setupInputFocusTracking();
        
        setupNetworkClickHandler(data, edges);
        
        setTimeout(() => {
            if (network) network.fit();
        }, 500);
    }

    // ===== ЗАГРУЗКА ИНТЕРАКТИВНОГО ГРАФА =====
    async function loadGraphWidget(requestId) {
        if (!requireAuth()) return;
        
        try {
            const response = await fetch(`/api/graph-widget/?id=${requestId}`);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const data = await response.json();
            console.log('Получены данные графа:', data);

            if (data.nodes && data.relationships) {
                if (data.nodes.length === 0) {
                    if (graphPlaceholder) {
                        graphPlaceholder.innerHTML = `
                            <div style="padding: 20px; text-align: center; color: #FF9800;">
                                <div>Граф не содержит узлов</div>
                                <div>Попробуйте изменить поисковый запрос</div>
                            </div>
                        `;
                    }
                    return;
                }

                if (network) {
                    updateGraph(data);
                } else {
                    createNewGraph(data);
                }
            } else {
                throw new Error('Неверный формат данных графа');
            }

        } catch (error) {
            console.error('Ошибка загрузки графа:', error);
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
        
        currentRequestId = requestId;
        lastInfoState = {};
        
        checkRequestStatus(requestId);
        statusPollInterval = setInterval(() => checkRequestStatus(requestId), 2000);
    }

    function stopStatusPolling() {
        if (statusPollInterval) {
            clearInterval(statusPollInterval);
            statusPollInterval = null;
        }
        currentRequestId = null;
        lastInfoState = {};
    }

    // ===== ОТПРАВКА ЗАПРОСА =====
    async function sendToDjango(keyWords, options) {
        if (!requireAuth()) return;
        
        try {
            if (network) {
                network.destroy();
                network = null;
            }

            if (graphPlaceholder) {
                graphPlaceholder.innerHTML = '<div style="text-align: center; padding: 20px;">Отправка запроса...</div>';
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
                graphPlaceholder.innerHTML = '<div style="text-align: center; padding: 20px;">Ожидание данных...</div>';
            }

            startStatusPolling(requestId);

        } catch (error) {
            console.error('Ошибка отправки запроса:', error);
            if (graphPlaceholder) {
                graphPlaceholder.innerHTML = `
                    <div style="padding: 20px; text-align: center; color: #ff6b6b;">
                        <div>Ошибка: ${error.message}</div>
                    </div>
                `;
            }
        }
    }

    function drawGraph(keyWords, options) {
        if (!requireAuth()) return;
        
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

        // Название
        if (entityName) {
            entityName.textContent = entityData.name || 
                                    entityData.label_en || 
                                    entityData.caption || 
                                    'Название не указано';
        }

        // Информация
        if (entityInfo) {
            let infoText = entityData.desc_en || entityData.info || entityData.abstract || 'Нет дополнительной информации';
            entityInfo.textContent = infoText;
            entityInfo.style.maxHeight = '200px';
            entityInfo.style.overflowY = 'auto';
            entityInfo.style.whiteSpace = 'normal';
            entityInfo.style.wordWrap = 'break-word';
        }

        // Связи
        if (linksList) {
            linksList.innerHTML = '';
            const links = entityData.links || [];
            
            if (links.length > 0) {
                linksList.style.maxHeight = '150px';
                linksList.style.overflowY = 'auto';
                
                links.forEach(link => {
                    const li = document.createElement('li');
                    if (typeof link === 'string') {
                        li.textContent = link;
                    } else if (link.type && link.target) {
                        li.textContent = `${link.type}: ${link.target}`;
                    } else if (link.name) {
                        li.textContent = link.name;
                    } else {
                        li.textContent = JSON.stringify(link);
                    }
                    linksList.appendChild(li);
                });
            } else {
                linksList.innerHTML = '<li>Нет связей</li>';
                linksList.style.maxHeight = '';
            }
        }

        // Ресурсы (ссылки)
        if (resourcesList) {
            resourcesList.innerHTML = '';
            const resources = entityData.resources || [];
            const uniqueResources = [];
            const seenUrls = new Set();
            
            for (const resource of resources) {
                const url = resource.url || resource;
                if (url && !seenUrls.has(url)) {
                    seenUrls.add(url);
                    uniqueResources.push(resource);
                }
            }
            
            if (uniqueResources.length > 0) {
                resourcesList.style.maxHeight = '150px';
                resourcesList.style.overflowY = 'auto';
                
                uniqueResources.forEach(resource => {
                    const li = document.createElement('li');
                    const a = document.createElement('a');
                    
                    if (typeof resource === 'string') {
                        a.href = resource;
                        a.textContent = resource;
                    } else if (resource.url) {
                        a.href = resource.url;
                        a.textContent = resource.name || resource.url;
                    } else if (resource.wiki_url) {
                        a.href = resource.wiki_url;
                        a.textContent = resource.label_en || resource.label_ru || 'Википедия';
                    } else {
                        a.href = '#';
                        a.textContent = resource.name || 'Ссылка';
                    }
                    
                    a.target = '_blank';
                    a.style.color = '#4CAF50';
                    a.style.textDecoration = 'none';
                    a.onmouseover = () => a.style.textDecoration = 'underline';
                    a.onmouseout = () => a.style.textDecoration = 'none';
                    
                    li.appendChild(a);
                    resourcesList.appendChild(li);
                });
            } else {
                resourcesList.innerHTML = '<li>Нет ссылок</li>';
                resourcesList.style.maxHeight = '';
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

    // ===== ИНИЦИАЛИЗАЦИЯ ОБРАБОТЧИКОВ =====
    
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

    const loginForm = document.getElementById('loginForm');
    if (loginForm) {
        loginForm.addEventListener('submit', handleLogin);
    }

    const registerForm = document.getElementById('registerForm');
    if (registerForm) {
        registerForm.addEventListener('submit', handleRegister);
    }

    const closeModalBtn = document.getElementById('closeLoginModal');
    if (closeModalBtn) {
        closeModalBtn.addEventListener('click', () => {
            hideLoginModal();
        });
    }

    const closeRegisterModal = document.getElementById('closeRegisterModal');
    if (closeRegisterModal) {
        closeRegisterModal.addEventListener('click', () => {
            hideRegisterModal();
        });
    }

    const logoutBtn = document.getElementById('logoutBtn');
    if (logoutBtn) {
        logoutBtn.addEventListener('click', handleLogout);
    }

    const showRegisterBtn = document.getElementById('showRegisterBtn');
    if (showRegisterBtn) {
        showRegisterBtn.addEventListener('click', (e) => {
            e.preventDefault();
            showRegisterModal();
        });
    }

    const showLoginBtn = document.getElementById('showLoginBtn');
    if (showLoginBtn) {
        showLoginBtn.addEventListener('click', (e) => {
            e.preventDefault();
            hideRegisterModal();
            showLoginModal();
        });
    }

    const modalOverlay = document.getElementById('modalOverlay');
    if (modalOverlay) {
        modalOverlay.addEventListener('click', () => {
            hideLoginModal();
            hideRegisterModal();
        });
    }

    // ===== ИСТОРИЯ ЗАПРОСОВ =====
    const showHistoryBtn = document.getElementById('showHistoryBtn');
    const historyPanel = document.getElementById('historyPanel');
    const closeHistoryBtn = document.getElementById('closeHistoryBtn');
    const historyList = document.getElementById('historyList');

    let historyData = [];

    async function loadHistory() {
        if (!isAuthenticated) return;
        
        try {
            const response = await fetch('/api/get-history/');
            if (response.ok) {
                const data = await response.json();
                historyData = Array.isArray(data) ? data : (data.history || []);
                console.log('Загружена история:', historyData);
                renderHistory();
            } else {
                console.error('Ошибка загрузки истории');
            }
        } catch (error) {
            console.error('Ошибка загрузки истории:', error);
        }
    }

    function formatDate(item) {
        const dateStr = item.created_at || item.date || item.timestamp;
        if (!dateStr) return 'Дата неизвестна';
        try {
            const date = new Date(dateStr);
            return isNaN(date.getTime()) ? 'Дата неизвестна' : date.toLocaleString();
        } catch (e) {
            return 'Дата неизвестна';
        }
    }

    function renderHistory() {
        if (!historyList) return;
        if (!historyData || historyData.length === 0) {
            historyList.innerHTML = '<div class="history-empty">История пуста</div>';
            return;
        }
        historyList.innerHTML = historyData.map(item => `
            <div class="history-item" data-query="${escapeHtml(item.query)}">
                <div class="history-item-query">${escapeHtml(item.query)}</div>
                <div class="history-item-date">${formatDate(item)}</div>
            </div>
        `).join('');
        
        document.querySelectorAll('.history-item').forEach(item => {
            item.addEventListener('click', () => {
                const query = item.dataset.query;
                if (query) {
                    searchField.value = query;
                    drawGraph(query, getOptions());
                    hideHistoryPanel();
                }
            });
        });
    }

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    function showHistoryPanel() {
        if (historyPanel) {
            loadHistory();
            historyPanel.style.display = 'block';
        }
    }

    function hideHistoryPanel() {
        if (historyPanel) historyPanel.style.display = 'none';
    }

    if (showHistoryBtn) showHistoryBtn.addEventListener('click', showHistoryPanel);
    if (closeHistoryBtn) closeHistoryBtn.addEventListener('click', hideHistoryPanel);

    document.addEventListener('click', function(event) {
        if (historyPanel && historyPanel.style.display === 'block') {
            if (!historyPanel.contains(event.target) && event.target !== showHistoryBtn) {
                hideHistoryPanel();
            }
        }
    });

    checkAuthStatus();

    console.log('Приложение полностью инициализировано');
});
