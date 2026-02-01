// --- INITIALIZATION ---
const tg = window.Telegram.WebApp;
tg.expand();
tg.headerColor = '#000000';

const API_URL = "https://my-tg-cloud-api.onrender.com"; 
const REAL_USER_ID = tg.initDataUnsafe?.user?.id; 
let USER_ID = REAL_USER_ID;
const BOT_USERNAME = "RusanCloudBot"; 
const ADMIN_USERNAME = "astermaneiro";

// --- USER SETTINGS & PREFERENCES ---
let currentLang = localStorage.getItem('tg_cloud_lang') || 'ru';
let currentTheme = localStorage.getItem('tg_cloud_theme') || 'dark';
let currentGrid = parseInt(localStorage.getItem('tg_cloud_grid') || '3');
let currentSort = localStorage.getItem('tg_cloud_sort') || 'date';

// --- LOCALIZATION ---
const translations = {
    ru: {
        loading: "Загрузка...", empty: "Пусто", back: "Назад", save_all: "Сохр. всё",
        settings_title: "Настройки", stat_photos: "Фото", stat_videos: "Видео", stat_files: "Файлы", stat_folders: "Папки",
        used: "Занято", unlimited: "Безлимит",
        theme: "Тема", theme_dark: "Тёмная", theme_light: "Светлая",
        grid_size: "Сетка", sort: "Сортир.",
        language: "Язык", delete_all: "Удалить все данные", 
        action_info: "Инфо", action_share: "Поделиться", action_move: "В папку", action_rename: "Переименовать", action_remove: "Убрать", action_delete: "Удалить", action_delete_rec: "Удалить с файлами",
        file_info: "Свойства", info_name: "Имя", info_type: "Тип", info_size: "Размер", info_date: "Дата",
        modal_new_folder: "Новая папка", modal_add_files: "Добавить файлы", modal_move_to: "Переместить в...",
        btn_cancel: "Отмена", btn_create: "Создать", btn_add: "Добавить", btn_close: "Закрыть", btn_ok: "ОК", btn_delete: "Удалить",
        prompt_rename: "Новое имя", prompt_folder_name: "Имя папки",
        confirm_title: "Удаление", confirm_msg_file: "Удалить этот файл навсегда?", confirm_msg_folder: "Удалить папку? Файлы переместятся в корень.", confirm_msg_recursive: "Удалить папку и ВСЕ файлы внутри?", confirm_msg_all: "Стереть ВСЕ данные?",
        alert_copied: "Ссылка скопирована!", 
        tab_all: "Все файлы", tab_image: "Фото", tab_video: "Видео", tab_doc: "Документы", tab_folders: "Папки", app_title: "Tg Cloud", donate_title: "Донат", invoice_error: "Ошибка создания платежа",
        welcome_title: "Как это работает?",
        welcome_step1: "1. Отправьте файл (фото, видео, документ) боту.",
        welcome_step2: "2. Он автоматически сохранится в облаке.",
        welcome_step3: "3. Нажмите на файл в приложении, чтобы получить его обратно.",
        empty_all: "Нет элементов",
        empty_image: "Фотографии отсутствуют",
        empty_video: "Видеозаписи отсутствуют",
        empty_doc: "Документы отсутствуют",
        empty_folders: "Папок нет",
        empty_folder_content: "Эта папка пуста",
        selected_txt: "выбрано",
        bulk_del_confirm: "Удалить выбранные объекты?",
        bulk_deleted: "Удалено",
        bulk_moved: "Перемещено",
    },
    en: {
        loading: "Loading...", empty: "Empty", back: "Back", save_all: "Save all",
        settings_title: "Settings", stat_photos: "Photos", stat_videos: "Videos", stat_files: "Files", stat_folders: "Folders",
        used: "Used", unlimited: "Unlimited",
        theme: "Theme", theme_dark: "Dark", theme_light: "Light",
        grid_size: "Grid", sort: "Sort",
        language: "Language", delete_all: "Delete All Data", 
        action_info: "Info", action_share: "Share", action_move: "Move", action_rename: "Rename", action_remove: "Remove", action_delete: "Delete", action_delete_rec: "Delete with files",
        file_info: "Properties", info_name: "Name", info_type: "Type", info_size: "Size", info_date: "Date",
        modal_new_folder: "New Folder", modal_add_files: "Add Files", modal_move_to: "Move to...",
        btn_cancel: "Cancel", btn_create: "Create", btn_add: "Add", btn_close: "Close", btn_ok: "OK", btn_delete: "Delete",
        prompt_rename: "New name", prompt_folder_name: "Folder name",
        confirm_title: "Deletion", confirm_msg_file: "Delete this file permanently?", confirm_msg_folder: "Delete folder? Files will move to root.", confirm_msg_recursive: "Delete folder and ALL content?", confirm_msg_all: "Wipe ALL data?",
        alert_copied: "Link copied!", 
        tab_all: "All Files", tab_image: "Photos", tab_video: "Videos", tab_doc: "Documents", tab_folders: "Folders", app_title: "Tg Cloud", donate_title: "Donate", invoice_error: "Payment error",
        welcome_title: "How does it work?",
        welcome_step1: "1. Send a file (photo, video, doc) to the bot.",
        welcome_step2: "2. It automatically saves to your cloud.",
        welcome_step3: "3. Tap the file in the app to retrieve it.",
        empty_all: "No items yet",
        empty_image: "No photos yet",
        empty_video: "No videos yet",
        empty_doc: "No documents yet",
        empty_folders: "No folders yet",
        empty_folder_content: "This folder is empty",
        selected_txt: "selected",
        bulk_del_confirm: "Delete selected items?",
        bulk_deleted: "Deleted",
        bulk_moved: "Moved",
    }
};

function t(key) { return translations[currentLang][key] || key; }

function updateLanguage() {
    document.querySelectorAll('[data-i18n]').forEach(el => el.innerText = t(el.dataset.i18n));
    updateSlider('lang-switch', 'lang-glider', currentLang);
    if (!currentState.folderId) updateHeaderTitle();
}
function changeLanguage(lang) {
    currentLang = lang; localStorage.setItem('tg_cloud_lang', lang);
    updateLanguage(); loadData();
}

function setTheme(theme) {
    currentTheme = theme; localStorage.setItem('tg_cloud_theme', theme);
    document.body.setAttribute('data-theme', theme);
    if(tg) { tg.headerColor = (theme === 'dark') ? '#000000' : '#ffffff'; tg.backgroundColor = (theme === 'dark') ? '#000000' : '#f2f2f7'; }
    updateSlider('theme-switch', 'theme-glider', theme);
}

function setGridSize(size) { currentGrid = size; localStorage.setItem('tg_cloud_grid', size); updateSlider('grid-switch', 'grid-glider', size.toString()); renderGrid(); }
function setSort(type) { currentSort = type; localStorage.setItem('tg_cloud_sort', type); updateSlider('sort-switch', 'sort-glider', type); renderGrid(); }

function updateSlider(cId, gId, val) {
    const c = document.getElementById(cId); const g = document.getElementById(gId);
    if(!c || !g) return;
    const opts = c.querySelectorAll('.segmented-option');
    opts.forEach((opt, i) => { if(opt.dataset.val === val) { opt.classList.add('active'); g.style.transform = `translateX(${i * 100}%)`; } else opt.classList.remove('active'); });
}

// --- STATE ---
let currentState = { 
    tab: 'all', 
    folderId: null, 
    folderName: null, 
    cache: [], 
    selectedFiles: new Set(),
    isSelectionMode: false,
    contextItem: null 
};
setTheme(currentTheme); setGridSize(currentGrid); setSort(currentSort); updateLanguage();

function updateHeaderTitle() {
    const h = document.getElementById('header-title');
    if (currentState.folderId && currentState.folderName) {
        h.innerHTML = `<i class="fas fa-folder-open"></i> ${currentState.folderName}`;
    } else {
        let k = 'app_title';
        let iconHtml = '';

        if (currentState.tab === 'all') {
            k = 'tab_all';
            iconHtml = `<img src="logo.png" class="app-logo" alt="logo">`;
        } 
        else if (currentState.tab === 'image') { k='tab_image'; iconHtml='<i class="fas fa-image"></i>'; } 
        else if (currentState.tab === 'video') { k='tab_video'; iconHtml='<i class="fas fa-video"></i>'; } 
        else if (currentState.tab === 'doc') { k='tab_doc'; iconHtml='<i class="fas fa-file-alt"></i>'; } 
        else if (currentState.tab === 'folders') { k='tab_folders'; iconHtml='<i class="fas fa-folder"></i>'; }
        
        if (!currentState.tab) {
             iconHtml = `<img src="logo.png" class="app-logo" alt="logo">`;
        }

        h.innerHTML = `${iconHtml} ${t(k)}`;
    }
}

// --- DONATIONS ---
async function actionDonate(amount) {
    tg.MainButton.showProgress();
    
    try {
        const res = await fetch(`${API_URL}/api/generate_invoice`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ amount: amount })
        });
        
        const data = await res.json();
        tg.MainButton.hideProgress();

        if (data.link) {
            tg.openInvoice(data.link, (status) => {
                if (status === 'paid') {
                    tg.close();
                    setTimeout(() => showToast("⭐ Спасибо за поддержку!"), 500);
                } else if (status === 'failed') {
                    showToast(t('invoice_error'));
                }
            });
        } else {
            showToast(t('invoice_error'));
        }
    } catch (e) {
        tg.MainButton.hideProgress();
        console.error(e);
        showToast(t('invoice_error'));
    }
}

// --- UI HELPERS ---
function showToast(text) {
    const el = document.getElementById('toast');
    el.innerText = text; el.classList.add('show');
    setTimeout(() => el.classList.remove('show'), 2000);
}

function openPrompt(title, placeholder, callback) {
    const modal = document.getElementById('modal-prompt');
    const input = document.getElementById('prompt-input');
    const btn = document.getElementById('prompt-submit-btn');
    document.getElementById('prompt-title').innerText = title;
    input.value = ""; input.placeholder = placeholder;
    modal.style.display = 'flex'; input.focus();
    
    const newBtn = btn.cloneNode(true); btn.parentNode.replaceChild(newBtn, btn);
    
    newBtn.onclick = () => {
        const val = input.value.trim();
        if(val) { callback(val); closeModals(); }
    };
}

function openConfirm(title, text, callback) {
    const modal = document.getElementById('modal-confirm');
    const btn = document.getElementById('confirm-submit-btn');
    document.getElementById('confirm-title').innerText = title;
    document.getElementById('confirm-text').innerText = text;
    modal.style.display = 'flex';
    
    const newBtn = btn.cloneNode(true); btn.parentNode.replaceChild(newBtn, btn);
    newBtn.onclick = () => { callback(); closeModals(); };
}

function closeModals() { document.querySelectorAll('.modal-overlay').forEach(el=>el.style.display='none'); }

// --- SETTINGS SCREEN ---
async function openSettings() {
    document.getElementById('settings-view').style.display = 'flex';
    updateSlider('theme-switch', 'theme-glider', currentTheme); updateSlider('lang-switch', 'lang-glider', currentLang);
    updateSlider('grid-switch', 'grid-glider', currentGrid.toString()); updateSlider('sort-switch', 'sort-glider', currentSort);
    
    try { 
        const res = await fetch(`${API_URL}/api/profile?user_id=${USER_ID}`);
        if(res.status === 403) {
            document.getElementById('blocked-screen').style.display = 'flex';
            return;
        }
        const s = await res.json();
        document.getElementById('stat-photos').innerText=s.counts.photos; document.getElementById('stat-videos').innerText=s.counts.videos;
        document.getElementById('stat-docs').innerText=s.counts.docs; document.getElementById('stat-folders').innerText=s.counts.folders;
        document.getElementById('storage-used').innerText=s.total_size_mb+' MB';
    } catch(e){}

    const user = tg.initDataUnsafe?.user;
    
    if (USER_ID === REAL_USER_ID && user) {
        document.getElementById('profile-name').innerText = (user.first_name + ' ' + (user.last_name||'')).trim();
        document.getElementById('profile-username').innerText = user.username ? '@'+user.username : 'ID: '+user.id;
        if(user.first_name) document.getElementById('profile-avatar').innerText = user.first_name[0];
    } else if (USER_ID !== REAL_USER_ID) {
        document.getElementById('profile-name').innerText = "Impersonated User";
        document.getElementById('profile-username').innerText = "ID: " + USER_ID;
        document.getElementById('profile-avatar').innerText = "?";
    }
}
function closeSettings() { document.getElementById('settings-view').style.display = 'none'; }
function confirmDeleteAll() {
    openConfirm(t('delete_all'), t('confirm_msg_all'), async () => {
        try { await fetch(`${API_URL}/api/delete_all`, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({user_id:USER_ID})}); closeSettings(); setTab('all'); } catch(e){}
    });
}


// --- ADMIN PANEL LOGIC ---
function handleAvatarClick() {
    const user = tg.initDataUnsafe?.user;
    if (user && user.username === ADMIN_USERNAME) {
        openAdminPanel();
    }
}

async function openAdminPanel() {
    document.getElementById('modal-admin').style.display = 'flex';
    const list = document.getElementById('admin-user-list');
    list.innerHTML = 'Загрузка...';
    
    try {
        const res = await fetch(`${API_URL}/api/admin/users`, {
            method: 'POST', 
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({admin_id: REAL_USER_ID})
        });
        
        if (res.status !== 200) throw new Error();
        
        const users = await res.json();
        list.innerHTML = '';
        
        users.forEach(u => {
            if (u.username === ADMIN_USERNAME) return;

            const row = document.createElement('div');
            row.className = 'admin-row';
            
            const blockedClass = u.is_blocked ? 'blocked' : '';
            const blockIcon = u.is_blocked ? 'fa-lock' : 'fa-unlock';

            row.innerHTML = `
                <div class="admin-user">
                    <span>${u.username || 'Unknown'}</span>
                    <small>ID: ${u.id}</small>
                </div>
                <div class="admin-actions">
                    <button class="btn-icon btn-view" onclick="impersonateUser(${u.id})"><i class="fas fa-eye"></i></button>
                    <button class="btn-icon btn-block ${blockedClass}" onclick="toggleBlockUser(this, ${u.id})"><i class="fas ${blockIcon}"></i></button>
                    <button class="btn-icon btn-del" onclick="deleteUserAdmin(${u.id})"><i class="fas fa-trash"></i></button>
                </div>
            `;
            list.appendChild(row);
        });
    } catch(e) { 
        list.innerHTML = 'Ошибка доступа или сети'; 
    }
}

function impersonateUser(targetId) {
    USER_ID = targetId;
    document.getElementById('admin-indicator').style.display = 'flex';
    closeModals();
    closeSettings();
    setTab('all');
    showToast(`Вошли как ID: ${targetId}`);
}

function exitAdminMode() {
    USER_ID = REAL_USER_ID;
    document.getElementById('admin-indicator').style.display = 'none';
    setTab('all');
    showToast("Возврат в свой аккаунт");
}

async function toggleBlockUser(btn, targetId) {
    if(!confirm("Изменить статус блокировки?")) return;
    try {
        const res = await fetch(`${API_URL}/api/admin/block`, {
            method: 'POST', headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({admin_id: REAL_USER_ID, target_user_id: targetId})
        });
        const data = await res.json();
        if(data.status === 'ok') {
            if(data.is_blocked) { btn.classList.add('blocked'); btn.innerHTML = '<i class="fas fa-lock"></i>'; }
            else { btn.classList.remove('blocked'); btn.innerHTML = '<i class="fas fa-unlock"></i>'; }
        }
    } catch(e) { showToast("Ошибка"); }
}

async function deleteUserAdmin(targetId) {
    if(!confirm("УДАЛИТЬ ПОЛЬЗОВАТЕЛЯ И ВСЕ ДАННЫЕ?")) return;
    try {
        await fetch(`${API_URL}/api/admin/delete_user`, {
            method: 'POST', headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({admin_id: REAL_USER_ID, target_user_id: targetId})
        });
        openAdminPanel();
    } catch(e) { showToast("Ошибка"); }
}


// --- CORE DATA & RENDERING LOGIC ---
function setTab(name, el) {
    document.querySelectorAll('.nav-item').forEach(i=>i.classList.remove('active'));
    if(el) el.classList.add('active');
    currentState.tab=name; currentState.folderId=null; currentState.folderName=null;
    updateUI(); loadData();
}

async function loadData() {
    document.getElementById('file-grid').classList.add('blurred');
    document.getElementById('loading-overlay').style.display='flex';
    document.getElementById('blocked-screen').style.display = 'none';

    try {
        let url = `${API_URL}/api/files?user_id=${USER_ID}`;
        if(currentState.tab==='folders') url+=currentState.folderId ? `&folder_id=${currentState.folderId}&mode=strict` : `&folder_id=null&mode=strict`;
        else url+=`&mode=global`;
        
        const res = await fetch(url);
        
        if(res.status === 403) {
            document.getElementById('loading-overlay').style.display='none';
            document.getElementById('blocked-screen').style.display = 'flex';
            return;
        }

        currentState.cache = await res.json();
        renderGrid();
    } catch(e){ console.error(e); } 
    finally { 
        document.getElementById('file-grid').classList.remove('blurred'); 
        if(document.getElementById('blocked-screen').style.display !== 'flex') {
            document.getElementById('loading-overlay').style.display='none'; 
        }
    }
}

function renderGrid() {
    const grid = document.getElementById('file-grid');
    grid.innerHTML = ''; 
    grid.className = 'grid';
    grid.classList.add(`cols-${currentGrid}`);
    if(currentState.folderId) grid.classList.add('with-nav');
    
    // Add selection class if active
    if(currentState.isSelectionMode) grid.classList.add('selection-mode');

    let items = currentState.cache;
    
    // FILTERING LOGIC START
    if(!currentState.folderId) {
        if(currentState.tab==='folders') items=items.filter(i=>i.type==='folder');
        else if(currentState.tab==='image') items=items.filter(i=>i.name.match(/\.(jpg|jpeg|png)$/i));
        else if(currentState.tab==='video') items=items.filter(i=>i.name.match(/\.(mp4|mov)$/i));
        else if(currentState.tab==='doc') items=items.filter(i=>i.type==='file' && !i.name.match(/\.(jpg|png|mp4)$/i));
        else items=items.filter(i=>i.type!=='folder');
    }
    items.sort((a,b)=>{ 
        if(currentSort==='name') return a.name.localeCompare(b.name); 
        if(currentSort==='size') return (b.size||0)-(a.size||0); 
        return new Date(b.created_at)-new Date(a.created_at); 
    });
    // FILTERING LOGIC END

    if(items.length === 0) { 
        if(currentState.folderId) { grid.innerHTML = `<div class="empty-pro"><i class="far fa-folder-open"></i><p>${t('empty_folder_content')}</p></div>`; return; }
        if(currentState.tab === 'folders') { grid.innerHTML = `<div class="empty-pro"><i class="fas fa-folder-open"></i><p>${t('empty_folders')}</p></div>`; return; }
        if (items.length === 0 && currentState.cache.length === 0) { /* Welcome screen code */ }
        grid.innerHTML = `<div class="empty-pro"><i class="fas fa-inbox"></i><p>${t('empty_all')}</p></div>`;
        return; 
    }

    items.forEach(item => {
        const el=document.createElement('div'); 
        el.className='item'; 
        el.id=`item-${item.id}`;
        
        // Selection state class
        if (currentState.selectedFiles.has(item.id)) {
            el.classList.add('selected');
        }

        let c='';
        if(item.type==='folder') {
            c=`<i class="icon fas fa-folder folder-icon"></i>`;
        } else {
            if(item.name.match(/\.(jpg|png)$/i)) c=`<img src="${API_URL}/api/preview/${item.file_id}" class="item-preview" loading="lazy">`;
            else if(item.name.match(/\.mp4$/i)) c=`<i class="icon fas fa-video icon-video"></i>`;
            else c=`<i class="icon fas fa-file file-icon"></i>`;
        }
        
        // Icon for selection mode
        const checkIcon = currentState.selectedFiles.has(item.id) ? 'fa-check-circle' : 'fa-circle';
        
        el.innerHTML = `
            ${c}
            <div class="success-overlay"><i class="fas fa-check"></i></div>
            <div class="select-indicator"><i class="far ${checkIcon}"></i></div>
            <div class="name">${item.name}</div>
            <div class="menu-btn" onclick="openContextMenu(event, '${encodeURIComponent(JSON.stringify(item))}')">
                <i class="fas fa-ellipsis-v"></i>
            </div>
        `;

        // CLICK & TOUCH LOGIC
        
        // 1. Click Handler
        el.onclick = (e) => { 
            if(e.target.closest('.menu-btn')) return; 
            
            if (currentState.isSelectionMode) {
                toggleSelection(item.id);
            } else {
                if(item.type==='folder') openFolder(item.id, item.name); 
                else downloadFile(item, el); 
            }
        };

        // 2. Long Press Handler
        let pressTimer;
        el.addEventListener('touchstart', (e) => {
            if (currentState.isSelectionMode) return;
            pressTimer = setTimeout(() => {
                enterSelectionMode(item.id);
                if (navigator.vibrate) navigator.vibrate(10);
            }, 600);
        }, {passive: true});

        el.addEventListener('touchend', () => clearTimeout(pressTimer));
        el.addEventListener('touchmove', () => clearTimeout(pressTimer));
        el.addEventListener('contextmenu', (e) => {
             e.preventDefault(); // Prevent native menu on long press
             return false;
        });

        grid.appendChild(el);
    });
}

function updateUI() {
    document.getElementById('top-nav').style.display = currentState.folderId ? 'flex' : 'none';
    document.getElementById('fab-add').style.display = (currentState.tab==='folders') ? 'flex' : 'none';
    updateHeaderTitle();
}
function openFolder(id, name) { currentState.folderId=id; currentState.folderName=name; updateUI(); loadData(); }
function goBack() { currentState.folderId=null; currentState.folderName=null; updateUI(); loadData(); }

async function downloadFile(item, el) {
    if(el) { 
        el.classList.add('downloaded'); 
        setTimeout(()=>el.classList.remove('downloaded'), 700); 
    }
    
    try { 
        await fetch(`${API_URL}/api/download`, {
            method: 'POST', 
            headers: {'Content-Type': 'application/json'}, 
            body: JSON.stringify({
                user_id: USER_ID,
                file_id: item.file_id, 
                file_name: item.name,
                recipient_id: REAL_USER_ID
            })
        }); 
        
        if (USER_ID !== REAL_USER_ID) {
            showToast("Отправлено вам (Admin)");
        }
    } catch(e) {
        console.error(e);
    } 
}
async function downloadAllInFolder() {
    if (!currentState.folderId) return;
    const items = currentState.cache.filter(i=>i.type!=='folder');
    for(let i=0; i<items.length; i++) { setTimeout(()=>downloadFile(items[i], document.getElementById(`item-${items[i].id}`)), i*300); }
}

// --- INFO FORMATTING ---
function formatDateTime(isoStr) {
    const d = new Date(isoStr);
    const date = ('0' + d.getDate()).slice(-2) + '.' + ('0' + (d.getMonth()+1)).slice(-2) + '.' + d.getFullYear();
    const time = ('0' + d.getHours()).slice(-2) + ':' + ('0' + d.getMinutes()).slice(-2);
    return { date, time };
}

function actionInfo() {
    const item = currentState.contextItem; closeContextMenu();
    document.getElementById('modal-info').style.display='flex';
    document.getElementById('info-name').innerText = item.name;
    document.getElementById('info-type').innerText = item.type==='folder' ? 'Папка' : item.name.split('.').pop().toUpperCase();
    let s='0 B'; if(item.size){ if(item.size>1024*1024) s=(item.size/(1024*1024)).toFixed(2)+' MB'; else s=(item.size/1024).toFixed(2)+' KB'; }
    document.getElementById('info-size').innerText = s;
    const dt = formatDateTime(item.created_at);
    document.getElementById('info-date').innerText = `${dt.date} ${dt.time}`;
}

// --- CONTEXT MENU & ACTIONS ---
function openContextMenu(e, itemStr) {
    e.stopPropagation();
    const item = JSON.parse(decodeURIComponent(itemStr));
    currentState.contextItem = item;
    
    document.getElementById('btn-remove-from-folder').style.display = (currentState.folderId && item.type==='file') ? 'flex' : 'none';
    document.getElementById('btn-delete-recursive').style.display = (item.type==='folder') ? 'flex' : 'none';
    
    const menu = document.getElementById('context-menu');
    let left = e.clientX - 140; if(left<10) left=10; if(e.clientX+50>window.innerWidth) left=window.innerWidth-170;
    menu.style.left = `${left}px`; menu.style.top = `${e.clientY+10}px`;
    menu.style.display='flex'; document.getElementById('menu-overlay').style.display='block';
}
function closeContextMenu() { document.getElementById('context-menu').style.display='none'; document.getElementById('menu-overlay').style.display='none'; }

function actionShare() { 
    const item = currentState.contextItem; closeContextMenu();
    const prefix = item.type === 'folder' ? 'folder_' : 'file_';
    navigator.clipboard.writeText(`https://t.me/${BOT_USERNAME}?start=${prefix}${item.id}`).then(()=>showToast(t('alert_copied')));
}

function actionRenamePrompt() {
    const item = currentState.contextItem; closeContextMenu();
    let oldName = item.name;
    openPrompt(t('prompt_rename'), oldName, async (val) => {
        if(item.type!=='folder' && oldName.includes('.')) { 
            const ext = '.' + oldName.split('.').pop();
            if(!val.endsWith(ext)) val += ext;
        }
        await fetch(`${API_URL}/api/rename`, { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({item_id:item.id, new_name:val})});
        loadData();
    });
}

function confirmDelete(recursive) {
    const item = currentState.contextItem; closeContextMenu();
    let msgKey = 'confirm_msg_file';
    if (item.type === 'folder') msgKey = recursive ? 'confirm_msg_recursive' : 'confirm_msg_folder';
    
    openConfirm(t('confirm_title'), t(msgKey), async () => {
        const url = recursive ? `${API_URL}/api/delete_folder_recursive` : `${API_URL}/api/delete`;
        await fetch(url, { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({item_id:item.id})});
        loadData();
    });
}

async function actionRemoveFromFolder() {
    const item = currentState.contextItem; closeContextMenu();
    await fetch(`${API_URL}/api/move_file`, { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({file_id:item.id, folder_id:null})});
    loadData();
}

async function actionMove() {
    const item = currentState.contextItem; closeContextMenu();
    const modal = document.getElementById('modal-select-folder'); const list = document.getElementById('folder-list');
    modal.style.display = 'flex'; list.innerHTML = t('loading');
    const res = await fetch(`${API_URL}/api/files?user_id=${USER_ID}&mode=folders`); const folders = await res.json();
    list.innerHTML = '';
    
    const div = document.createElement('div'); div.className = 'modal-item'; div.innerHTML = `<i class="fas fa-plus"></i> <b>${t('modal_new_folder')}</b>`;
    div.onclick = () => {
        modal.style.display = 'none';
        openCreateFolderModal((newId) => {
             moveFileAPI(item.id, newId);
        });
    };
    list.appendChild(div);

    folders.filter(f=>f.id!==item.id).forEach(f => {
        const d = document.createElement('div'); d.className='modal-item'; d.innerHTML=`<i class="fas fa-folder text-yellow"></i> ${f.name}`;
        d.onclick = () => moveFileAPI(item.id, f.id);
        list.appendChild(d);
    });
}
async function moveFileAPI(fileId, folderId) {
    closeModals(); tg.MainButton.showProgress();
    await fetch(`${API_URL}/api/move_file`, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({file_id:fileId, folder_id:folderId})});
    tg.MainButton.hideProgress(); loadData();
}

function openCreateFolderModal(cb) {
    openPrompt(t('modal_new_folder'), t('prompt_folder_name'), async (val) => {
        await fetch(`${API_URL}/api/create_folder`, { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({user_id:USER_ID, name:val, parent_id:currentState.folderId})});
        if(cb) {}
        loadData();
    });
}

// --- MULTI-SELECTION LOGIC ---

function enterSelectionMode(initialItemId) {
    currentState.isSelectionMode = true;
    currentState.selectedFiles.clear();
    currentState.selectedFiles.add(initialItemId);
    
    // UI Updates
    document.getElementById('selection-header').style.display = 'flex';
    document.querySelector('.app-header:not(.selection-header)').style.display = 'none'; // Hide normal header
    
    // Hide bottom bar (optional, better UX)
    document.querySelector('.bottom-bar').style.display = 'none';
    document.querySelector('.fab-add').style.display = 'none';
    
    updateSelectionUI();
    renderGrid(); // Re-render to show checkboxes
}

function exitSelectionMode() {
    currentState.isSelectionMode = false;
    currentState.selectedFiles.clear();
    
    // UI Updates
    document.getElementById('selection-header').style.display = 'none';
    document.querySelector('.app-header:not(.selection-header)').style.display = 'flex';
    document.querySelector('.bottom-bar').style.display = 'flex';
    if(currentState.tab === 'folders') document.querySelector('.fab-add').style.display = 'flex';
    
    renderGrid();
}

function toggleSelection(itemId) {
    if (currentState.selectedFiles.has(itemId)) {
        currentState.selectedFiles.delete(itemId);
    } else {
        currentState.selectedFiles.add(itemId);
    }
    
    if (currentState.selectedFiles.size === 0) {
        exitSelectionMode(); // Exit if nothing selected
    } else {
        updateSelectionUI();
        const el = document.getElementById(`item-${itemId}`);
        const icon = el.querySelector('.select-indicator i');
        if (currentState.selectedFiles.has(itemId)) {
            el.classList.add('selected');
            icon.classList.remove('fa-circle');
            icon.classList.add('fa-check-circle');
        } else {
            el.classList.remove('selected');
            icon.classList.remove('fa-check-circle');
            icon.classList.add('fa-circle');
        }
    }
}

function updateSelectionUI() {
    document.getElementById('selection-count').innerText = `${currentState.selectedFiles.size} ${t('selected_txt')}`;
}

// --- BULK ACTIONS ---

function bulkShare() {
    const ids = Array.from(currentState.selectedFiles);
    if (!ids.length) return;
    
    const links = ids.map(id => {
        const item = currentState.cache.find(i => i.id === id);
        const prefix = item.type === 'folder' ? 'folder_' : 'file_';
        return `https://t.me/${BOT_USERNAME}?start=${prefix}${id}`;
    }).join('\n');
    
    navigator.clipboard.writeText(links).then(() => {
        showToast(t('alert_copied') + ` (${ids.length})`);
        exitSelectionMode();
    });
}

function bulkDelete() {
    const count = currentState.selectedFiles.size;
    openConfirm(t('confirm_title'), `${t('bulk_del_confirm')} (${count})`, async () => {
        tg.MainButton.showProgress();
        const ids = Array.from(currentState.selectedFiles);
        
        // Execute sequentially to avoid rate limits or overwhelming backend
        for (const id of ids) {
             const item = currentState.cache.find(i => i.id === id);
             if (!item) continue;
             
             let url = `${API_URL}/api/delete`;
             if (item.type === 'folder') url = `${API_URL}/api/delete_folder_recursive`;
             
             await fetch(url, { 
                 method:'POST', 
                 headers:{'Content-Type':'application/json'}, 
                 body:JSON.stringify({item_id: id})
             });
        }
        
        tg.MainButton.hideProgress();
        showToast(`${t('bulk_deleted')}: ${count}`);
        exitSelectionMode();
        loadData();
    });
}

async function bulkMove() {
    const modal = document.getElementById('modal-select-folder'); 
    const list = document.getElementById('folder-list');
    modal.style.display = 'flex'; 
    list.innerHTML = t('loading');
    
    // Get Folders
    const res = await fetch(`${API_URL}/api/files?user_id=${USER_ID}&mode=folders`); 
    const folders = await res.json();
    list.innerHTML = '';

    // Create New Folder option
    const div = document.createElement('div'); div.className = 'modal-item'; div.innerHTML = `<i class="fas fa-plus"></i> <b>${t('modal_new_folder')}</b>`;
    div.onclick = () => {
        modal.style.display = 'none';
        openCreateFolderModal((newFolderId) => {
             processBulkMove(newFolderId);
        });
    };
    list.appendChild(div);

    const availableFolders = folders.filter(f => !currentState.selectedFiles.has(f.id));

    availableFolders.forEach(f => {
        const d = document.createElement('div'); d.className='modal-item'; d.innerHTML=`<i class="fas fa-folder text-yellow"></i> ${f.name}`;
        d.onclick = () => {
            closeModals();
            processBulkMove(f.id);
        };
        list.appendChild(d);
    });
}

async function processBulkMove(targetFolderId) {
    tg.MainButton.showProgress();
    const ids = Array.from(currentState.selectedFiles);
    
    for (const id of ids) {
        await fetch(`${API_URL}/api/move_file`, {
            method:'POST', 
            headers:{'Content-Type':'application/json'}, 
            body:JSON.stringify({file_id: id, folder_id: targetFolderId})
        });
    }
    
    tg.MainButton.hideProgress();
    showToast(`${t('bulk_moved')}: ${ids.length}`);
    exitSelectionMode();
    loadData();
}

setTab('all', document.querySelector('.nav-item'));