from flask import Flask, render_template, request, jsonify
import yt_dlp
import os
import tempfile
import shutil
from tkinter import Tk, filedialog
import threading

app = Flask(__name__)

download_progress = {'percentage': 0, 'status': 'idle'}

def progress_hook(d):
    """Hook para capturar el progreso de descarga"""
    global download_progress
    
    if d['status'] == 'downloading':
        if 'total_bytes' in d:
            percentage = (d['downloaded_bytes'] / d['total_bytes']) * 100
        elif 'total_bytes_estimate' in d:
            percentage = (d['downloaded_bytes'] / d['total_bytes_estimate']) * 100
        else:
            percentage = 0
        
        download_progress['percentage'] = round(percentage, 1)
        download_progress['status'] = 'downloading'
        
    elif d['status'] == 'finished':
        download_progress['percentage'] = 100
        download_progress['status'] = 'processing'

def get_ydl_opts():
    """Configuración optimizada"""
    return {
        'quiet': True,
        'no_warnings': True,
        'nocheckcertificate': True,
        'ignoreerrors': False,
        'geo_bypass': True,
        'extractor_retries': 3,
        'fragment_retries': 10,
        'skip_unavailable_fragments': True,
        'progress_hooks': [progress_hook],
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-us,en;q=0.5',
            'Sec-Fetch-Mode': 'navigate',
        }
    }

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/video-info', methods=['POST'])
def get_video_info():
    try:
        data = request.get_json()
        url = data.get('url')
        
        if not url:
            return jsonify({'error': 'URL no proporcionada'}), 400
        
        ydl_opts = get_ydl_opts()
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            video_info = {
                'title': info.get('title', 'Sin título'),
                'thumbnail': info.get('thumbnail', ''),
                'duration': info.get('duration', 0),
                'author': info.get('uploader', 'Desconocido'),
                'views': info.get('view_count', 0),
            }
            
            video_formats = []
            audio_formats = []
            seen_qualities = set()
            
            for f in info.get('formats', []):
                if (f.get('vcodec') != 'none' and 
                    f.get('acodec') != 'none' and 
                    f.get('height')):
                    
                    height = f.get('height')
                    quality_str = f"{height}p"
                    
                    if quality_str not in seen_qualities and height >= 144:
                        seen_qualities.add(quality_str)
                        video_formats.append({
                            'format_id': f['format_id'],
                            'quality': quality_str,
                            'height': height,  # Agregar altura para filtrado
                            'ext': f.get('ext', 'mp4'),
                            'filesize': f.get('filesize') or f.get('filesize_approx', 0),
                            'fps': f.get('fps', 30),
                            'resolution': f"{f.get('width', 0)}x{height}",
                        })
                
                elif (f.get('acodec') != 'none' and 
                      f.get('vcodec') == 'none' and
                      f.get('abr')):
                    
                    bitrate = int(f.get('abr', 0))
                    if bitrate > 0 and bitrate <= 320:
                        audio_formats.append({
                            'format_id': f['format_id'],
                            'quality': f"{bitrate}kbps",
                            'bitrate': bitrate,
                            'ext': 'mp3',
                            'filesize': f.get('filesize') or f.get('filesize_approx', 0)
                        })
            
            video_formats.sort(key=lambda x: int(x['quality'].replace('p', '')), reverse=True)
            
            seen_bitrates = set()
            unique_audio = []
            for audio in sorted(audio_formats, key=lambda x: x['bitrate'], reverse=True):
                if audio['bitrate'] not in seen_bitrates:
                    seen_bitrates.add(audio['bitrate'])
                    unique_audio.append(audio)
            
            video_info['video_formats'] = video_formats[:8]
            video_info['audio_formats'] = unique_audio[:5]
            
            return jsonify({
                'success': True,
                **video_info
            })
            
    except Exception as e:
        print(f"Error: {str(e)}")
        return jsonify({'error': 'Error al obtener información del video'}), 500

@app.route('/api/select-folder', methods=['GET'])
def select_folder():
    try:
        root = Tk()
        root.withdraw()
        root.attributes('-topmost', True)
        
        folder_path = filedialog.askdirectory(
            title='Selecciona dónde guardar el archivo',
            mustexist=True
        )
        
        root.destroy()
        
        if folder_path:
            return jsonify({'success': True, 'path': folder_path})
        else:
            return jsonify({'success': False, 'message': 'No se seleccionó carpeta'}), 400
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/progress', methods=['GET'])
def get_progress():
    """Endpoint para obtener el progreso de descarga"""
    global download_progress
    return jsonify(download_progress)

@app.route('/api/download', methods=['POST'])
def download_video():
    global download_progress
    download_progress = {'percentage': 0, 'status': 'idle'}
    
    temp_dir = None
    try:
        data = request.get_json()
        url = data.get('url')
        download_type = data.get('type', 'video')
        save_path = data.get('save_path')
        selected_quality = data.get('quality')
        
        if not url or not save_path:
            return jsonify({'error': 'Datos incompletos'}), 400
        
        temp_dir = tempfile.mkdtemp()
        
        base_opts = get_ydl_opts()
        base_opts['quiet'] = False
        base_opts['outtmpl'] = os.path.join(temp_dir, '%(title)s.%(ext)s')
        
        if download_type == 'audio':
            base_opts['format'] = 'bestaudio/best'
            base_opts['postprocessors'] = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }]
        else:
            if selected_quality:
                quality_height = int(selected_quality.replace('p', ''))
                base_opts['format'] = f'best[height<={quality_height}]'
                print(f"📊 Descargando en calidad: {selected_quality}")
            else:
                base_opts['format'] = 'best'
                print(f"📊 Descargando en mejor calidad disponible")
        
        print(f"\n{'='*60}")
        print(f"📥 Iniciando descarga de {download_type.upper()}")
        print(f"📁 Carpeta temporal: {temp_dir}")
        print(f"{'='*60}\n")
        
        download_progress['status'] = 'downloading'
        
        with yt_dlp.YoutubeDL(base_opts) as ydl:
            info = ydl.extract_info(url, download=True)
        
        download_progress['status'] = 'processing'
        
        print(f"\n{'='*60}")
        print(f"🔍 Buscando archivo descargado...")
        
        all_files = []
        if os.path.exists(temp_dir):
            all_files = os.listdir(temp_dir)
            if all_files:
                for i, file in enumerate(all_files, 1):
                    file_path = os.path.join(temp_dir, file)
                    file_size = os.path.getsize(file_path) / (1024 * 1024)
                    print(f"  {i}. {file} ({file_size:.2f} MB)")
        
        temp_file = None
        
        if download_type == 'audio':
            extensions = ['.mp3', '.m4a', '.webm', '.opus']
        else:
            extensions = ['.mp4', '.webm', '.mkv', '.avi', '.mov']
        
        for ext in extensions:
            for file in all_files:
                if file.lower().endswith(ext):
                    temp_file = os.path.join(temp_dir, file)
                    print(f"\n✅ Archivo encontrado: {file}")
                    break
            if temp_file:
                break
        
        print(f"{'='*60}\n")
        
        if not temp_file or not os.path.exists(temp_file):
            download_progress['status'] = 'error'
            raise Exception("No se pudo descargar el archivo")
        
        final_filename = os.path.basename(temp_file)
        final_path = os.path.join(save_path, final_filename)
        
        base, ext = os.path.splitext(final_path)
        counter = 1
        while os.path.exists(final_path):
            final_path = f"{base} ({counter}){ext}"
            counter += 1
        
        shutil.move(temp_file, final_path)
        
        download_progress['percentage'] = 100
        download_progress['status'] = 'completed'
        
        print(f"✅ Archivo guardado en: {final_path}\n")
        
        return jsonify({
            'success': True,
            'message': 'Descarga completada',
            'filename': os.path.basename(final_path),
            'path': save_path
        })
        
    except Exception as e:
        download_progress['status'] = 'error'
        print(f"\n❌ ERROR: {str(e)}\n")
        return jsonify({'error': f'Error al descargar: {str(e)}'}), 500
    
    finally:
        if temp_dir and os.path.exists(temp_dir):
            try:
                shutil.rmtree(temp_dir, ignore_errors=True)
                print(f"🗑️  Limpieza completada\n")
            except:
                pass

if __name__ == '__main__':
    print("\n" + "="*60)
    print("🚀 YouTube Downloader - Servidor iniciado")
    print("="*60 + "\n")
    app.run(debug=True, port=5000, host='127.0.0.1')
