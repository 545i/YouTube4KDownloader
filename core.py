import os
from urllib.parse import urlparse, parse_qs
import yt_dlp
import subprocess
import json

Debug = False
watermark_function = True

def check_ffmpeg_available():
    """檢查 FFmpeg 是否可用"""
    try:
        # 先嘗試本地路徑
        ffmpeg_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                 'bin', 'ffmpeg.exe')

        if os.path.exists(ffmpeg_path):
            result = subprocess.run([ffmpeg_path, '-version'],
                                  capture_output=True,
                                  text=True,
                                  timeout=5)
            if result.returncode == 0:
                print(f"[DEBUG] FFmpeg found at: {ffmpeg_path}")
                return True

        # 嘗試系統路徑
        result = subprocess.run(['ffmpeg', '-version'],
                              capture_output=True,
                              text=True,
                              timeout=5)
        if result.returncode == 0:
            print("[DEBUG] FFmpeg found in system PATH")
            return True

        print("[DEBUG] FFmpeg not found or failed to run")
        return False
    except FileNotFoundError:
        print("[DEBUG] FFmpeg not found (FileNotFoundError)")
        return False
    except Exception as e:
        print(f"[DEBUG] FFmpeg check failed: {e}")
        return False

def load_settings():
    settings_file = 'settings.json'
    default_settings = {
        'watermark_width': 300,
        'watermark_height': 10
    }
    
    if os.path.exists(settings_file):
        try:
            with open(settings_file, 'r') as f:
                return json.load(f)
        except:
            return default_settings
    return default_settings

def get_watermark_position():
    """获取水印位置和大小设置"""
    settings = load_settings()
    return {
        'x': '(W-w)-1',  # 从右边开始计算，减去浮水印宽度再减1像素
        'y': '(H-h)-1',  # 从底部开始计算，减去浮水印高度再减1像素
        'scale_width': settings.get('watermark_width', 300),
        'scale_height': settings.get('watermark_height', 10)
    }

def add_watermark(input_file, output_file):
    """添加浮水印到影片"""
    try:
        # 檢查 FFmpeg 是否可用
        if not check_ffmpeg_available():
            print("⚠️ FFmpeg 不可用，跳過水印處理")
            return False

        # 設置ffmpeg路徑
        ffmpeg_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                 'bin', 'ffmpeg.exe')

        # 如果本地找不到，使用系統路徑
        if not os.path.exists(ffmpeg_path):
            ffmpeg_path = 'ffmpeg'

        # 浮水印圖片路徑
        logo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               'Logo.png')

        if not os.path.exists(logo_path):
            print("⚠️ 找不到浮水印圖片：Logo.png，跳過水印處理")
            return False
        
        # 檢查是否支持NVIDIA硬體加速
        try:
            result = subprocess.run([ffmpeg_path, '-hide_banner', '-encoders'], 
                                 capture_output=True, text=True, check=True)
            has_nvenc = 'h264_nvenc' in result.stdout
        except:
            has_nvenc = False
        
        # 使用ffmpeg添加浮水印，保持原始影片品質
        command = [
            ffmpeg_path, '-i', input_file,
            '-i', logo_path,
            '-filter_complex', '[1:v]scale={scale_width}:{scale_height}[watermark];[0:v][watermark]overlay={x}:{y}'.format(**get_watermark_position()),
        ]
        
        if has_nvenc:
            # 使用NVIDIA硬體加速
            command.extend([
                '-c:v', 'h264_nvenc',  # 使用NVENC編碼器
                '-preset', 'p7',  # 最高品質預設
                '-rc', 'constqp',  # 固定QP模式
                '-qp', '0',  # 最高品質
                '-profile:v', 'high',  # 高配置
                '-pixel_format', 'yuv420p',  # 標準像素格式
            ])
        else:
            # 使用CPU編碼
            command.extend([
                '-c:v', 'libx264',  # 使用x264編碼器
                '-preset', 'veryslow',  # 使用最慢的編碼預設以獲得最好的質量
                '-crf', '0',  # 設置最高品質（無損）
            ])
        
        # 確保音訊串流被正確複製
        command.extend([
            '-map', '0:a',  # 映射第一個輸入文件的音訊串流
            '-c:a', 'aac',  # 使用AAC編碼器
            '-b:a', '192k',  # 設置音訊位元率
            output_file
        ])
        
        # 使用Popen而不是run，以便可以获取进程对象
        process = subprocess.Popen(command)
        process.wait()  # 等待进程完成
        
        if process.returncode == 0:
            return True
        else:
            print(f"❌ 添加浮水印失敗：ffmpeg返回錯誤碼 {process.returncode}")
            return False
    except Exception as e:
        print(f"❌ 添加浮水印失敗：{e}")
        return False

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
    # 確保 Download 資料夾存在
    os.makedirs('Download', exist_ok=True)

    # 檢查 FFmpeg 是否可用
    ffmpeg_available = check_ffmpeg_available()

    # 根據 FFmpeg 可用性調整格式選擇
    if ffmpeg_available:
        format_string = 'bestvideo+bestaudio/best'
    else:
        print("⚠️ FFmpeg 不可用，將下載預先合併的格式（可能畫質較低）")
        format_string = 'best[ext=mp4]/best'

    ydl_opts = {
        'outtmpl': 'Download/%(title)s.%(ext)s',
        'format': format_string,
        'merge_output_format': 'mp4',
        'quiet': False,
        'noplaylist': True,  # 禁止整個播放清單
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-us,en;q=0.5',
            'Sec-Fetch-Mode': 'navigate',
        },
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'web'],
                'player_skip': ['webpage', 'configs'],
            }
        },
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            print("⬇️ 正在下載影片...")
            info = ydl.extract_info(url, download=True)
            video_path = ydl.prepare_filename(info)
            if not video_path.endswith('.mp4'):
                video_path = os.path.splitext(video_path)[0] + '.mp4'
            
            if watermark_function:
                # 檢查 FFmpeg 是否可用
                ffmpeg_available = check_ffmpeg_available()

                if ffmpeg_available:
                    # 添加浮水印
                    print("🖌️ 正在添加浮水印...")
                    watermarked_path = os.path.splitext(video_path)[0] + '_watermarked.mkv'
                    if add_watermark(video_path, watermarked_path):
                        # 刪除原始文件
                        os.remove(video_path)
                        print("✅ 下載完成並添加浮水印！")
                        return watermarked_path
                    else:
                        print("✅ 下載完成，但添加浮水印失敗！")
                        return video_path
                else:
                    # FFmpeg 不可用，直接返回原始文件
                    print("⚠️ FFmpeg 不可用，跳過水印處理")
                    print("✅ 下載完成！")
                    return video_path
            else:
                # 不添加浮水印
                print("✅ 下載完成！")
                return video_path
                
        except Exception as e:
            print(f"❌ 發生錯誤：{e}")
            return None

def get_video_info(url):
    """獲取影片資訊（標題和封面URL）"""
    try:
        # 清理URL
        cleaned_url = clean_url(url)
        if not cleaned_url:
            return None, None

        # 獲取影片資訊
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,  # 需要獲取完整資訊以取得封面
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-us,en;q=0.5',
                'Sec-Fetch-Mode': 'navigate',
            },
            'extractor_args': {
                'youtube': {
                    'player_client': ['android', 'web'],
                    'player_skip': ['webpage', 'configs'],
                }
            },
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(cleaned_url, download=False)
            video_title = info.get('title', 'Unknown Title')
            thumbnail_url = info.get('thumbnail', '')  # 獲取封面URL
            return video_title, thumbnail_url
    except Exception as e:
        print(f"獲取影片資訊失敗：{str(e)}")
        return None, None

class YouTubeDownloader:
    def __init__(self, progress_hook=None):
        self.progress_hook = progress_hook
        # 確保Download目錄存在
        os.makedirs('Download', exist_ok=True)

        # 檢查 FFmpeg 是否可用
        self.ffmpeg_available = check_ffmpeg_available()

        self.ydl_opts = {
            'outtmpl': 'Download/%(title)s.%(ext)s',
            'format': 'bestvideo+bestaudio/best',  # 默認下載最佳音視頻
            'merge_output_format': 'mp4',  # 輸出為mp4格式
            'quiet': False,
            'noplaylist': True,  # 禁止整個播放清單
            # 添加以下選項來繞過 403 錯誤
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-us,en;q=0.5',
                'Sec-Fetch-Mode': 'navigate',
            },
            'extractor_args': {
                'youtube': {
                    'player_client': ['android', 'web'],
                    'player_skip': ['webpage', 'configs'],
                }
            },
        }

        # 如果 FFmpeg 不可用，移除 abort_on_error 並調整格式選擇
        if not self.ffmpeg_available:
            print("⚠️ FFmpeg 不可用，將下載預先合併的格式（可能畫質較低）")
            # 優先選擇已合併的格式，避免需要 FFmpeg 合併
            self.ydl_opts['format'] = 'best[ext=mp4]/best'

        if progress_hook:
            self.ydl_opts['progress_hooks'] = [progress_hook]

    def get_info(self, url):
        """獲取影片資訊"""
        return get_video_info(url)

    def get_format_string(self, height):
        """根据指定的高度获取格式字符串"""
        return f"bestvideo[height<={height}]+bestaudio[ext=m4a]/best[height<={height}]/best"

    def download(self, url, format_string="bestvideo+bestaudio/best"):
        """下載影片

        Args:
            url: YouTube視頻URL
            format_string: 影片格式和畫質設置，例如：
                         "bestvideo[height<=1080][vcodec^=avc]+bestaudio[ext=m4a]/best[height<=1080]"
                         或 "bestaudio/best" 用於只下載音頻
        """
        cleaned_url = clean_url(url)  # 使用全局的clean_url函數
        if not cleaned_url:
            raise ValueError("無效的 YouTube 連結")

        # 檢查是否為音頻下載
        is_audio_only = format_string.startswith("bestaudio")
        print(f"[DEBUG core] is_audio_only: {is_audio_only}")
        print(f"[DEBUG core] format_string: {format_string}")
        print(f"[DEBUG core] ffmpeg_available: {self.ffmpeg_available}")

        # 根据format_string确定输出格式
        if is_audio_only:
            output_format = 'bestaudio'  # 音頻保留原始格式，不轉換
        else:
            output_format = 'mp4'  # 默认为mp4
            if 'vcodec^=hev' in format_string:
                output_format = 'mp4'  # H.265默认使用mp4
            elif '[vcodec^=vp9]' in format_string:
                output_format = 'webm'  # VP9默认使用webm
            elif 'MKV' in format_string:
                output_format = 'mkv'

        # 如果 FFmpeg 不可用，調整格式字串
        if not self.ffmpeg_available:
            print(f"[DEBUG core] FFmpeg not available, adjusting format")
            if is_audio_only:
                # 音頻下載：不限制擴展名，讓 yt-dlp 選擇最佳音頻
                # YouTube 通常提供 m4a (AAC), opus (WEBM), 或其他格式
                format_string = 'bestaudio'
                output_format = 'bestaudio'  # 保留原始格式
                print(f"[DEBUG core] Adjusted to audio format: {format_string}")
                if self.progress_hook:
                    self.progress_hook({
                        'status': 'downloading',
                        'message': '⚠️ FFmpeg 不可用，下載最佳音頻格式'
                    })
            else:
                # 視頻下載：從格式字串中提取畫質要求
                if 'height<=' in format_string:
                    # 提取畫質限制，例如從 "bestvideo[height<=1080]..." 提取 1080
                    import re
                    match = re.search(r'height<=(\d+)', format_string)
                    if match:
                        height = match.group(1)
                        # 使用已合併的格式，但限制畫質
                        format_string = f'best[height<={height}][ext=mp4]/best[ext=mp4]/best'
                    else:
                        format_string = 'best[ext=mp4]/best'
                else:
                    format_string = 'best[ext=mp4]/best'

                if self.progress_hook:
                    self.progress_hook({
                        'status': 'downloading',
                        'message': '⚠️ FFmpeg 不可用，下載預合併格式'
                    })

        # 手動創建下載選項，避免 deepcopy 無法複製 progress_hook
        print(f"[DEBUG core] Final format_string before creating opts: {format_string}")
        print(f"[DEBUG core] Final output_format: {output_format}")
        download_opts = {
            'outtmpl': self.ydl_opts['outtmpl'],
            'format': format_string,
            'quiet': self.ydl_opts.get('quiet', False),
            'noplaylist': self.ydl_opts.get('noplaylist', True),
        }
        print(f"[DEBUG core] download_opts format: {download_opts['format']}")

        # 複製 HTTP headers
        if 'http_headers' in self.ydl_opts:
            download_opts['http_headers'] = self.ydl_opts['http_headers'].copy()

        # 複製 extractor_args
        if 'extractor_args' in self.ydl_opts:
            download_opts['extractor_args'] = {
                'youtube': self.ydl_opts['extractor_args']['youtube'].copy()
            }

        # 複製 progress_hooks（這是無法 deepcopy 的部分）
        if 'progress_hooks' in self.ydl_opts:
            download_opts['progress_hooks'] = self.ydl_opts['progress_hooks']

        # 只在非音頻模式下設置 merge_output_format
        if output_format != 'bestaudio':
            download_opts['merge_output_format'] = output_format

        # 如果是音頻下載且有 FFmpeg，添加音頻提取後處理器
        if is_audio_only and self.ffmpeg_available:
            download_opts['postprocessors'] = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'm4a',  # 使用 M4A（兼容 Apple 設備）
                'preferredquality': '0',   # 0 = 最佳音質，不重新編碼
            }]
            # 設置 FFmpeg 位置
            ffmpeg_location = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'bin')
            download_opts['ffmpeg_location'] = ffmpeg_location
            print(f"[DEBUG core] Added FFmpegExtractAudio postprocessor, ffmpeg at: {ffmpeg_location}")

        with yt_dlp.YoutubeDL(download_opts) as ydl:
            try:
                # 獲取影片資訊
                info = ydl.extract_info(cleaned_url, download=False)
                video_title = info.get('title', 'Unknown Title')

                # 下載影片
                ydl.download([cleaned_url])

                # 準備文件路徑
                file_path = ydl.prepare_filename(info)

                # 對於音頻下載，需要找到實際下載的文件
                if output_format == 'bestaudio':
                    # 如果使用了 FFmpeg 提取，文件會是 .m4a
                    base_path = os.path.splitext(file_path)[0]

                    if self.ffmpeg_available:
                        # 有 FFmpeg 時，文件會被提取為 .m4a
                        file_path = base_path + '.m4a'
                        print(f"[DEBUG core] Looking for extracted audio: {file_path}")
                    else:
                        # 沒有 FFmpeg 時，嘗試找原始音頻格式
                        possible_extensions = ['.m4a', '.webm', '.opus', '.mp4', '.aac']
                        file_found = False
                        for ext in possible_extensions:
                            test_path = base_path + ext
                            if os.path.exists(test_path):
                                file_path = test_path
                                file_found = True
                                print(f"[DEBUG core] Found audio file: {file_path}")
                                break

                        if not file_found and not os.path.exists(file_path):
                            raise Exception(f"找不到下載的音頻文件。嘗試過的路徑: {base_path}{{.m4a,.webm,.opus,.mp4,.aac}}")
                else:
                    # 視頻下載：調整擴展名
                    if not file_path.endswith(f'.{output_format}'):
                        file_path = os.path.splitext(file_path)[0] + f'.{output_format}'

                    # 確認文件存在
                    if not os.path.exists(file_path):
                        raise Exception(f"下載的文件不存在: {file_path}")

                # 音頻文件不需要水印處理
                if is_audio_only:
                    if self.progress_hook:
                        self.progress_hook({'status': 'finished', 'message': '音頻下載完成'})
                    return info, video_title, file_path

                # 根據watermark_function決定是否添加浮水印
                if watermark_function:
                    # 檢查 FFmpeg 是否可用
                    ffmpeg_available = check_ffmpeg_available()

                    if ffmpeg_available:
                        # FFmpeg 可用，添加浮水印
                        if self.progress_hook:
                            self.progress_hook({'status': 'processing', 'message': '正在添加浮水印...'})

                        watermarked_path = os.path.splitext(file_path)[0] + '_watermarked.mp4'
                        if add_watermark(file_path, watermarked_path):
                            # 刪除原始文件
                            os.remove(file_path)
                            if self.progress_hook:
                                self.progress_hook({'status': 'finished', 'message': '浮水印添加完成'})
                            return info, video_title, watermarked_path
                        else:
                            if self.progress_hook:
                                self.progress_hook({'status': 'finished', 'message': '浮水印添加失敗，使用原始文件'})
                            return info, video_title, file_path
                    else:
                        # FFmpeg 不可用，直接返回原始文件
                        if self.progress_hook:
                            self.progress_hook({'status': 'finished', 'message': '⚠️ FFmpeg 不可用，跳過水印處理'})
                        return info, video_title, file_path
                else:
                    # 不添加浮水印
                    if self.progress_hook:
                        self.progress_hook({'status': 'finished', 'message': '下載完成'})
                    return info, video_title, file_path
                    
            except Exception as e:
                if self.progress_hook:
                    self.progress_hook({'status': 'error', 'message': str(e)})
                raise 