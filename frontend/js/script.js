// боковая панель
const sidebar = document.getElementById('sidebar');
const toggleBtn = document.getElementById('sidebarToggle');
const mainContent = document.getElementById('mainContent');

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



function drawGraph(keyWords, options) {
    alert(keyWords);
    console.log(options);
    //рисует граф
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


// Поиск
const searchButton = document.querySelector('.search-button');
const searchField = document.getElementById('searchField');

if (searchButton && searchField) {
    searchButton.addEventListener('click', function() {
        const options = getOptions();
        drawGraph(searchField.value, options);
    });
    
    searchField.addEventListener('keypress', function(event) {
        if (event.key === 'Enter') {
            const options = getOptions();
            drawGraph(searchField.value, options);
        }
    });
}

