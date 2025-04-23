import os
from urllib.parse import urlparse, parse_qs
import yt_dlp
import subprocess

Debug = False

def clean_url(raw_url):
    parsed = urlparse(raw_url)
    if "youtu.be" in raw_url:
        video_id = parsed.path.strip("/")
    else:
        query = parse_qs(parsed.query)
        video_id = query.get("v", [None])[0]
    if not video_id:
        print("❌ 無效的 YouTube 連結")
        return None
    return f"https://www.youtube.com/watch?v={video_id}"

def download_video(url):
    
    os.makedirs('Download', exist_ok=True)
    
    ydl_opts = {
        'outtmpl': 'Download/%(title)s.%(ext)s',
        'format': 'bestvideo+bestaudio/best',
        'merge_output_format': 'mp4',
        'quiet': False,
        'noplaylist': True,  
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            print("⬇️ 正在下載影片...")
            info = ydl.extract_info(url, download=True)
            video_path = ydl.prepare_filename(info)
            if not video_path.endswith('.mp4'):
                video_path = os.path.splitext(video_path)[0] + '.mp4'
            
            print("✅ 下載完成！")
            return video_path
                
        except Exception as e:
            print(f"❌ 發生錯誤：{e}")
            return None

def get_video_info(url):
    """獲取影片資訊（標題和封面URL）"""
    try:
        
        cleaned_url = clean_url(url)
        if not cleaned_url:
            return None, None
            
        
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,  
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(cleaned_url, download=False)
            video_title = info.get('title', 'Unknown Title')
            thumbnail_url = info.get('thumbnail', '')  
            return video_title, thumbnail_url
    except Exception as e:
        print(f"獲取影片資訊失敗：{str(e)}")
        return None, None

class YouTubeDownloader:
    def __init__(self, progress_hook=None):
        self.progress_hook = progress_hook
        
        os.makedirs('Download', exist_ok=True)
        self.ydl_opts = {
            'outtmpl': 'Download/%(title)s.%(ext)s',
            'format': 'bestvideo+bestaudio/best',  
            'merge_output_format': 'mp4',  
            'quiet': False,
            'noplaylist': True,  
        }
        if progress_hook:
            self.ydl_opts['progress_hooks'] = [progress_hook]

    def get_info(self, url):
        """獲取影片資訊"""
        return get_video_info(url)

    def get_format_string(self, height):
        """根據指定的高度獲取格式字串"""
        return f"bestvideo[height<={height}]+bestaudio[ext=m4a]/best[height<={height}]/best"

    def download(self, url, format_string="bestvideo+bestaudio/best"):
        """下載影片
        
        Args:
            url: YouTube影片URL
            format_string: 影片格式和畫質設置，例如：
                         "bestvideo[height<=1080][vcodec^=avc]+bestaudio[ext=m4a]/best[height<=1080]"
        """
        cleaned_url = clean_url(url)  
        if not cleaned_url:
            raise ValueError("無效的 YouTube 連結")
            
        
        output_format = 'mp4'  
        if 'vcodec^=hev' in format_string:
            output_format = 'mp4'  
        elif '[vcodec^=vp9]' in format_string:
            output_format = 'webm'  
        elif 'MKV' in format_string:
            output_format = 'mkv'
            
        
        self.ydl_opts.update({
            'format': format_string,
            'merge_output_format': output_format
        })
            
        with yt_dlp.YoutubeDL(self.ydl_opts) as ydl:
            try:
                
                info = ydl.extract_info(cleaned_url, download=False)
                video_title = info.get('title', 'Unknown Title')
                
                
                file_path = ydl.prepare_filename(info)
                if not file_path.endswith(f'.{output_format}'):
                    file_path = os.path.splitext(file_path)[0] + f'.{output_format}'
                
                
                ydl.download([cleaned_url])
                
                
                if not os.path.exists(file_path):
                    raise Exception(f"下載的文件不存在: {file_path}")
                
                if self.progress_hook:
                    self.progress_hook({'status': 'finished', 'message': '下載完成'})
                return info, video_title, file_path
                    
            except Exception as e:
                if self.progress_hook:
                    self.progress_hook({'status': 'error', 'message': str(e)})
                raise 