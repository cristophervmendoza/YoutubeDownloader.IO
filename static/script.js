let currentVideoInfo = null;
let currentUrl = null;
let pendingDownload = null;
let progressInterval = null;

const urlInput = document.getElementById('urlInput');
const searchBtn = document.getElementById('searchBtn');
const loader = document.getElementById('loader');
const error = document.getElementById('error');
const videoInfo = document.getElementById('videoInfo');
const thumbnail = document.getElementById('thumbnail');
const title = document.getElementById('title');
const author = document.getElementById('author');
const duration = document.getElementById('duration');
const views = document.getElementById('views');
const videoFormats = document.getElementById('videoFormats');
const audioFormats = document.getElementById('audioFormats');
const downloadStatus = document.getElementById('downloadStatus');

const tabs = document.querySelectorAll('.tab');
const tabContents = document.querySelectorAll('.tab-content');

tabs.forEach(tab => {
    tab.addEventListener('click', () => {
        const tabName = tab.dataset.tab;
        
        tabs.forEach(t => t.classList.remove('active'));
        tabContents.forEach(tc => tc.classList.remove('active'));
        
        tab.classList.add('active');
        document.getElementById(`${tabName}-tab`).classList.add('active');
    });
});

searchBtn.addEventListener('click', searchVideo);
urlInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') searchVideo();
});

async function searchVideo() {
    const url = urlInput.value.trim();
    
    if (!url) {
        showNotification('Por favor ingresa una URL válida', 'error');
        return;
    }
    
    currentUrl = url;
    hideAll();
    loader.classList.remove('hidden');
    
    try {
        const response = await fetch('/api/video-info', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ url })
        });
        
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.error || 'Error al obtener información');
        }
        
        currentVideoInfo = data;
        displayVideoInfo(data);
        
    } catch (err) {
        showNotification(err.message, 'error');
    } finally {
        loader.classList.add('hidden');
    }
}

function displayVideoInfo(data) {
    thumbnail.src = data.thumbnail;
    title.textContent = data.title;
    author.textContent = data.author;
    duration.textContent = formatDuration(data.duration);
    views.textContent = formatNumber(data.views);
    
    videoFormats.innerHTML = '';
    data.video_formats.forEach(format => {
        const card = createFormatCard(format, 'video');
        videoFormats.appendChild(card);
    });
    
    audioFormats.innerHTML = '';
    data.audio_formats.forEach(format => {
        const card = createFormatCard(format, 'audio');
        audioFormats.appendChild(card);
    });
    
    videoInfo.classList.remove('hidden');
}

function createFormatCard(format, type) {
    const card = document.createElement('div');
    card.className = 'format-card';
    
    const quality = document.createElement('div');
    quality.className = 'quality';
    quality.textContent = format.quality;
    
    const details = document.createElement('div');
    details.className = 'details';
    
    if (type === 'video') {
        details.innerHTML = `
            ${format.resolution}<br>
            ${format.fps} FPS<br>
            ${formatFileSize(format.filesize)}
        `;
    } else {
        details.innerHTML = `
            MP3<br>
            ${formatFileSize(format.filesize)}
        `;
    }
    
    card.appendChild(quality);
    card.appendChild(details);
    
    card.addEventListener('click', () => downloadFormat(format, type));
    
    return card;
}

async function downloadFormat(format, type) {
    try {
        showNotification('Selecciona dónde guardar el archivo...', 'info');
        
        const response = await fetch('/api/select-folder');
        const data = await response.json();
        
        if (!response.ok || !data.success) {
            showNotification('No se seleccionó ninguna carpeta', 'info');
            return;
        }
        
        const savePath = data.path;
        
        downloadStatus.classList.remove('hidden');
        document.querySelector('.status-text').textContent = 'Iniciando descarga...';
        document.querySelector('.progress-fill').style.width = '0%';
        
        // Iniciar monitoreo de progreso
        startProgressMonitoring();
        
        const downloadResponse = await fetch('/api/download', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                url: currentUrl,
                format_id: format.format_id,
                type: type,
                save_path: savePath,
                quality: format.quality  // Enviar calidad seleccionada
            })
        });
        
        const downloadData = await downloadResponse.json();
        
        stopProgressMonitoring();
        
        if (!downloadResponse.ok) {
            throw new Error(downloadData.error || 'Error en la descarga');
        }
        
        document.querySelector('.status-text').textContent = `✅ Completado`;
        document.querySelector('.progress-fill').style.width = '100%';
        
        showNotification(
            `${type === 'video' ? 'Video' : 'Audio'} descargado correctamente`,
            'success'
        );
        
        setTimeout(() => {
            downloadStatus.classList.add('hidden');
            document.querySelector('.progress-fill').style.width = '0%';
        }, 2000);
        
    } catch (err) {
        stopProgressMonitoring();
        showNotification(`Error: ${err.message}`, 'error');
        downloadStatus.classList.add('hidden');
    }
}

function startProgressMonitoring() {
    progressInterval = setInterval(async () => {
        try {
            const response = await fetch('/api/progress');
            const data = await response.json();
            
            if (data.status === 'downloading') {
                document.querySelector('.progress-fill').style.width = `${data.percentage}%`;
                document.querySelector('.status-text').textContent = 
                    `Descargando... ${data.percentage}%`;
            } else if (data.status === 'processing') {
                document.querySelector('.progress-fill').style.width = '100%';
                document.querySelector('.status-text').textContent = 'Procesando archivo...';
            }
        } catch (err) {
            console.error('Error obteniendo progreso:', err);
        }
    }, 500); 
}

function stopProgressMonitoring() {
    if (progressInterval) {
        clearInterval(progressInterval);
        progressInterval = null;
    }
}

function showNotification(message, type = 'info') {
    const notification = document.getElementById('notification');
    notification.textContent = message;
    notification.className = `notification ${type}`;
    notification.classList.add('show');
    
    setTimeout(() => {
        notification.classList.remove('show');
    }, 5000);
}

function formatDuration(seconds) {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = seconds % 60;
    
    if (hours > 0) {
        return `${hours}:${String(minutes).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
    }
    return `${minutes}:${String(secs).padStart(2, '0')}`;
}

function formatNumber(num) {
    return new Intl.NumberFormat('es-ES').format(num);
}

function formatFileSize(bytes) {
    if (!bytes || bytes === 0) return 'Tamaño desconocido';
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(1024));
    return Math.round(bytes / Math.pow(1024, i) * 100) / 100 + ' ' + sizes[i];
}

function hideAll() {
    error.classList.add('hidden');
    videoInfo.classList.add('hidden');
    downloadStatus.classList.add('hidden');
}
