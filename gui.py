import sys
import os
import subprocess
import urllib.request
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QLineEdit, QPushButton, QLabel, 
                            QListWidget, QListWidgetItem, QTextEdit, QSplitter,
                            QFrame, QFileDialog, QProgressBar, QComboBox)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize
from PyQt6.QtGui import QIcon, QFont, QPixmap
import core
import requests
from io import BytesIO
from user import MemberPage
from settings_page import SettingsPage 


CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

class DownloadWorker(QThread):
    """下載影片的工作執行緒"""
    finished = pyqtSignal(str, str, str) 
    progress = pyqtSignal(str)
    progress_percent = pyqtSignal(float) 
    
    def __init__(self, url, format_string):
        super().__init__()
        self.url = url
        self.format_string = format_string
        self.downloader = core.YouTubeDownloader(progress_hook=self.progress_hook)
        
    def progress_hook(self, d):
        if d['status'] == 'downloading':

            if 'total_bytes' in d and d['total_bytes'] > 0:
                percent = (d['downloaded_bytes'] / d['total_bytes']) * 100
                self.progress_percent.emit(percent)

            if 'speed' in d:
                speed = d['speed']
                if speed:
                    speed_mb = speed / 1024 / 1024
                    self.progress.emit(f"⬇️ Downloading... {speed_mb:.1f} MB/s")
        elif d['status'] == 'processing':

            message = d.get('message', 'Processing...')
            self.progress.emit(f"🖌️ {message}")
            self.progress_percent.emit(95)
        elif d['status'] == 'finished':

            message = d.get('message', 'Processing completed')
            self.progress.emit(f"✅ {message}")
            self.progress_percent.emit(100)
        elif d['status'] == 'error':

            message = d.get('message', 'Error')
            self.progress.emit(f"❌ {message}")
            self.progress_percent.emit(0)
        
    def run(self):
        try:
            info, video_title, file_path = self.downloader.download(self.url, self.format_string)
            
            if os.path.exists(file_path):
                self.progress.emit(f"✅ Download completed: {os.path.basename(file_path)}")
                self.finished.emit(self.url, "success", file_path)
            else:
                raise Exception(f"File not found: {file_path}")
                
        except Exception as e:
            self.progress.emit(f"❌ Error: {str(e)}")
            self.progress_percent.emit(0)
            self.finished.emit(self.url, "error", "")

class ThumbnailWorker(QThread):
    """縮圖下載工作執行緒"""
    finished = pyqtSignal(str, QPixmap)

    def __init__(self, url, thumbnail_url):
        super().__init__()
        self.url = url
        self.thumbnail_url = thumbnail_url

    def run(self):
        try:
            response = requests.get(self.thumbnail_url)
            if response.status_code == 200:
                image_data = BytesIO(response.content)
                pixmap = QPixmap()
                pixmap.loadFromData(image_data.getvalue())

                pixmap = pixmap.scaled(120, 68, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                self.finished.emit(self.url, pixmap)
        except Exception as e:
            print(f"Error downloading thumbnail: {e}")

            self.finished.emit(self.url, QPixmap())

class TitleWorker(QThread):
    """獲取影片標題和封面的工作執行緒"""
    finished = pyqtSignal(str, str, str) 

    def __init__(self, url):
        super().__init__()
        self.url = url
        self.downloader = core.YouTubeDownloader()

    def run(self):
        try:

            title, thumbnail_url = self.downloader.get_info(self.url)
            if title and thumbnail_url:
                self.finished.emit(self.url, title, thumbnail_url)
            else:
                self.finished.emit(self.url, "Failed to get info", "")
        except Exception as e:
            self.finished.emit(self.url, f"Failed to get info: {str(e)}", "")

class YouTubeDownloaderGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("4K Downloader")
        self.setGeometry(100, 100, 1000, 700)
        self.setMinimumSize(900, 600)
        self.setWindowIcon(QIcon("icon.png"))

        self.member_button = None
        
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        
        main_layout = QHBoxLayout(main_widget)
        main_layout.setContentsMargins(0, 0, 0, 0) 
        main_layout.setSpacing(0)
        

        self.sidebar = QWidget()
        self.sidebar.setObjectName("sidebar")
        self.sidebar.setFixedWidth(280) 
        self.sidebar.setStyleSheet("""
            QWidget#sidebar {
                background-color: #2c3e50;
                color: white;
            }
            QLabel {
                color: white;
                font-size: 14px;
                margin-top: 10px;
            }
            QLineEdit {
                background-color: #34495e;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 8px;
                margin: 5px;
                margin-bottom: 15px;
            }
            QLineEdit:focus {
                background-color: #2c3e50;
                border: 2px solid #3498db;
            }
            QComboBox {
                background-color: #34495e;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 8px;
                margin: 5px;
                margin-bottom: 15px;
            }
            QComboBox::drop-down {
                border: none;
                width: 30px;
            }
            QComboBox::down-arrow {
                image: url(down_arrow.png);
                width: 12px;
                height: 12px;
            }
            QComboBox QAbstractItemView {
                background-color: #34495e;
                color: white;
                selection-background-color: #2c3e50;
                selection-color: white;
                border: none;
            }
            QPushButton#download_button {
                background-color: #27ae60;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 10px;
                font-weight: bold;
                margin: 5px;
                margin-bottom: 15px;
            }
            QPushButton#download_button:hover {
                background-color: #219a52;
            }
            QLineEdit, QComboBox, QPushButton#download_button {
                border: 1px solid rgba(0, 0, 0, 0.1);
            }
            QLineEdit {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #3a506b, stop:1 #34495e);
                border-bottom: 3px solid rgba(0, 0, 0, 0.2);
            }
            QComboBox {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #3a506b, stop:1 #34495e);
                border-bottom: 3px solid rgba(0, 0, 0, 0.2);
            }
            QPushButton#download_button {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #2ecc71, stop:1 #27ae60);
                border-bottom: 3px solid rgba(0, 0, 0, 0.2);
            }
            QLineEdit:hover, QComboBox:hover {
                border-bottom: 3px solid rgba(0, 0, 0, 0.3);
            }
            QPushButton#download_button:hover {
                border-bottom: 3px solid rgba(0, 0, 0, 0.3);
            }
            QPushButton#download_button:pressed {
                margin-top: 7px;
                margin-bottom: 13px;
                border-bottom: 1px solid rgba(0, 0, 0, 0.2);
            }
        """)
        

        self.sidebar.setLayout(self.create_sidebar_content())
        

        main_content = QWidget()
        main_content.setObjectName("main_content")
        main_content.setStyleSheet("""
            QWidget#main_content {
                background-color: white;
            }
            QLabel {
                color: #333;
                font-size: 16px;
                font-weight: bold;
            }
            QFrame {
                background-color: #ecf0f1;
                border-radius: 10px;
            }
        """)
        

        content_layout = QVBoxLayout(main_content)
        content_layout.setContentsMargins(20, 20, 20, 20)
        content_layout.setSpacing(15)
        

        content_title = QLabel("Download Queue")
        content_layout.addWidget(content_title)
        

        download_list_container = QWidget()
        download_list_container.setObjectName("download_list_container")
        download_list_layout = QVBoxLayout(download_list_container)
        download_list_layout.setContentsMargins(0, 0, 0, 0)
        
        self.download_list = QListWidget()
        self.download_list.setSpacing(10)
        self.download_list.setStyleSheet("""
            QListWidget {
                background-color: transparent;
                border: none;
                outline: none;
            }
            QListWidget::item {
                background-color: transparent;
                border: none;
                padding: 5px;
            }
        """)
        self.download_list.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        self.download_list.setHorizontalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        

        download_list_layout.addWidget(self.download_list)
        content_layout.addWidget(download_list_container, 1)
        

        self.output_text = QTextEdit()
        self.output_text.setReadOnly(True)
        self.output_text.setMaximumHeight(150)
        self.output_text.setStyleSheet("""
            QTextEdit {
                background-color: #f8f9f9;
                border: 1px solid #ddd;
                border-radius: 5px;
                padding: 5px;
            }
        """)
        if core.Debug:
            content_layout.addWidget(self.output_text)
        

        main_layout.addWidget(self.sidebar)
        main_layout.addWidget(main_content, 1)

        self.pending_items = []
        self.title_workers = {} 
        self.workers = {}
    
    def create_sidebar_content(self):
        """創建側邊欄內容"""

        sidebar_layout = QVBoxLayout()
        sidebar_layout.setContentsMargins(20, 20, 20, 20)
        sidebar_layout.setSpacing(5)
        

        title_label = QLabel("4K Downloader")
        title_label.setStyleSheet("font-size: 24px; font-weight: bold; margin-bottom: 20px;")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sidebar_layout.addWidget(title_label)

        url_label = QLabel("Video URL")
        sidebar_layout.addWidget(url_label)
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("Enter YouTube video URL")
        self.url_input.setObjectName("url_input")
        sidebar_layout.addWidget(self.url_input)
        

        quality_label = QLabel("Quality")
        sidebar_layout.addWidget(quality_label)
        self.quality_combo = QComboBox()
        self.quality_combo.setObjectName("quality_combo")
        self.quality_combo.addItems([
            "Best Quality (4K/2160p)", 
            "Ultra HD (1440p)", 
            "High Quality (1080p)", 
            "High Quality (720p)", 
            "Standard (480p)", 
            "Smooth (360p)"
        ])
        sidebar_layout.addWidget(self.quality_combo)
        

        format_label = QLabel("Format")
        sidebar_layout.addWidget(format_label)
        self.format_combo = QComboBox()
        self.format_combo.setObjectName("format_combo")
        self.format_combo.addItems([
            "MP4 (H.264)", 
            "MP4 (H.265/HEVC)", 
            "MKV (H.264)", 
            "MKV (H.265/HEVC)", 
            "WEBM (VP9)"
        ])
        sidebar_layout.addWidget(self.format_combo)
        

        self.download_button = QPushButton("Add to Queue")
        self.download_button.setObjectName("download_button")
        self.download_button.clicked.connect(self.add_url)
        sidebar_layout.addWidget(self.download_button)
        

        sidebar_layout.addStretch()
        
        return sidebar_layout
    
    def add_url(self):
        """添加URL到下載列表"""
        url = self.url_input.text().strip()
        if not url:
            return
            

        for i, (completed_url, _) in enumerate(self.completed_items):
            if completed_url == url:
                self.completed_items.pop(i)
                for j in range(self.download_list.count()):
                    if self.pending_items[j] == url:
                        item = self.download_list.item(j)
                        if item:
                            widget = self.create_pending_item_widget(url)
                            item.setSizeHint(widget.sizeHint())
                            self.download_list.setItemWidget(item, widget)
                            
                            title_worker = TitleWorker(url)
                            title_worker.finished.connect(lambda u, t, s: self.update_video_title(u, t, s))
                            self.title_workers[url] = title_worker
                            title_worker.start()
                            
                            self.update_output(f"✨ Reset download status for: {url}")
                            return

        existing_index = -1
        for i in range(len(self.pending_items)):
            if self.pending_items[i] == url:
                existing_index = i
                break
        
        if existing_index >= 0:
            item = self.download_list.item(existing_index)
            if item:
                widget = self.download_list.itemWidget(item)
                
                info_widget = widget.findChild(QWidget, "info_widget")
                if info_widget:
                    quality_label = info_widget.findChild(QLabel, "quality_label")
                    format_label = info_widget.findChild(QLabel, "format_label")
                    if quality_label and format_label:
                        quality_label.setText(f"🎥 Quality: {self.quality_combo.currentText()}")
                        format_label.setText(f"📁 Format: {self.format_combo.currentText()}")
                
                download_btn = widget.findChild(QPushButton, "download_btn")
                if download_btn:
                    download_btn.setEnabled(True)
                    download_btn.setText("⬇️ Download")
                    download_btn.setStyleSheet("""
                        QPushButton {
                            background-color: #3498db;
                            color: white;
                            border: none;
                            border-radius: 5px;
                            padding: 8px 15px;
                            font-weight: bold;
                            font-size: 13px;
                        }
                        QPushButton:hover {
                            background-color: #2980b9;
                        }
                        QPushButton:pressed {
                            background-color: #2475a8;
                        }
                    """)
                
                progress_bar = widget.findChild(QProgressBar)
                if progress_bar:
                    progress_bar.hide()
                    progress_bar.setValue(0)
                
                self.update_output(f"✨ Updated download settings: {url}")
            return
        
        item = QListWidgetItem()
        self.download_list.addItem(item)
        self.pending_items.append(url)
        
        self.url_input.clear()
        
        widget = self.create_pending_item_widget(url)
        item.setSizeHint(widget.sizeHint())
        self.download_list.setItemWidget(item, widget)
        
        title_worker = TitleWorker(url)
        title_worker.finished.connect(lambda u, t, s: self.update_video_title(u, t, s))
        self.title_workers[url] = title_worker
        title_worker.start()
    
    def update_video_title(self, url, title, thumbnail_url):
        """更新影片標題和封面"""

        for i in range(self.download_list.count()):
            item = self.download_list.item(i)
            if self.pending_items[i] == url:
                widget = self.download_list.itemWidget(item)
                

                title_label = widget.findChild(QLabel, "", options=Qt.FindChildOption.FindChildrenRecursively)
                if title_label and not title_label.objectName():
                    title_label.setText(title)
                
                cover_label = widget.findChild(QLabel, "cover")
                if cover_label and thumbnail_url:
                    thumbnail_worker = ThumbnailWorker(url, thumbnail_url)
                    thumbnail_worker.finished.connect(self.on_thumbnail_downloaded)
                    self.workers[f"{url}_thumbnail"] = thumbnail_worker
                    thumbnail_worker.start()
                break
        
        if url in self.title_workers:
            self.title_workers[url].deleteLater()
            del self.title_workers[url]
    
    def on_thumbnail_downloaded(self, url, pixmap):
        """當縮圖下載完成時更新UI"""
        for i in range(self.download_list.count()):
            item = self.download_list.item(i)
            if self.pending_items[i] == url:
                widget = self.download_list.itemWidget(item)
                cover_label = widget.findChild(QLabel, "cover")
                if cover_label and not pixmap.isNull():
                    cover_label.setPixmap(pixmap)
                break
        
        if f"{url}_thumbnail" in self.workers:
            self.workers[f"{url}_thumbnail"].deleteLater()
            del self.workers[f"{url}_thumbnail"]
    
    def create_pending_item_widget(self, url):
        """創建未下載項的卡片部件"""
        widget = QWidget()
        widget.setObjectName("card")
        widget.setStyleSheet("""
            QWidget#card {
                background-color: white;
                border: 1px solid #e0e0e0;
                border-radius: 10px;
            }
            QWidget#card:hover {
                border: 1px solid #bdc3c7;
                background-color: #f8f9f9;
            }
        """)
        

        widget.setFixedHeight(180)
        widget.setMinimumWidth(300)
        
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(15)
        
        cover_container = QWidget()
        cover_container.setFixedSize(120, 68)
        cover_container.setStyleSheet("background-color: #f5f5f5; border-radius: 5px;")
        cover_layout = QVBoxLayout(cover_container)
        cover_layout.setContentsMargins(0, 0, 0, 0)
        
        cover_label = QLabel()
        cover_label.setObjectName("cover")
        cover_label.setFixedSize(120, 68)
        cover_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cover_label.setStyleSheet("""
            QLabel#cover {
                background-color: #f5f5f5;
                border-radius: 5px;
            }
        """)
        cover_layout.addWidget(cover_label)
        layout.addWidget(cover_container)
        
        info_container = QWidget()
        info_layout = QVBoxLayout(info_container)
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(10)
        
        title_label = QLabel("Getting video info...")
        title_label.setWordWrap(True)
        title_label.setStyleSheet("""
            font-size: 16px;
            font-weight: bold;
            color: #2c3e50;
            background-color: white;
            padding: 0;
            margin: 0;
        """)
        title_label.setMinimumHeight(40)
        title_label.setMaximumHeight(50)
        info_layout.addWidget(title_label)
        
        info_widget = QWidget()
        info_widget.setObjectName("info_widget")
        info_widget.setStyleSheet("""
            background-color: white;
            border-radius: 5px;
            padding: 0;
            margin: 0;
        """)
        info_widget.setFixedHeight(30) 
        
        info_sub_layout = QHBoxLayout(info_widget)
        info_sub_layout.setContentsMargins(0, 0, 0, 0)
        info_sub_layout.setSpacing(15)
        
        quality_label = QLabel(f"🎥 Quality: {self.quality_combo.currentText()}")
        quality_label.setObjectName("quality_label") 
        format_label = QLabel(f"📁 Format: {self.format_combo.currentText()}")
        format_label.setObjectName("format_label")
        quality_label.setStyleSheet("color: #7f8c8d; font-size: 13px; background-color: white;")
        format_label.setStyleSheet("color: #7f8c8d; font-size: 13px; background-color: white;")
        
        info_sub_layout.addWidget(quality_label)
        info_sub_layout.addWidget(format_label)
        info_sub_layout.addStretch()
        info_layout.addWidget(info_widget)
        

        progress_container = QWidget()
        progress_container.setFixedHeight(20)
        progress_layout = QVBoxLayout(progress_container)
        progress_layout.setContentsMargins(0, 5, 0, 5)
        
        progress_bar = QProgressBar()
        progress_bar.setRange(0, 100)
        progress_bar.setValue(0)
        progress_bar.setTextVisible(True)
        progress_bar.setFixedHeight(6)
        progress_bar.setStyleSheet("""
            QProgressBar {
                border: none;
                background-color: #f0f0f0;
                border-radius: 3px;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #3498db;
                border-radius: 3px;
            }
        """)
        progress_bar.hide()
        progress_layout.addWidget(progress_bar)
        info_layout.addWidget(progress_container)
        
        button_widget = QWidget()
        button_widget.setFixedHeight(35)
        button_layout = QHBoxLayout(button_widget)
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.setSpacing(10)
        
        download_btn = QPushButton("⬇️ Start Download")
        download_btn.setObjectName("download_btn")
        download_btn.setFixedSize(120, 32)
        download_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        download_btn.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 8px 15px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
            QPushButton:pressed {
                background-color: #2475a8;
            }
        """)
        download_btn.clicked.connect(lambda: self.start_download(url))
        
        button_layout.addStretch()
        button_layout.addWidget(download_btn)
        info_layout.addWidget(button_widget)
        
        info_container.setMinimumWidth(400) 
        layout.addWidget(info_container, 1)
        return widget
    
    def create_completed_item_widget(self, url, file_path):
        """創建已下載項的卡片部件"""
        widget = QWidget()
        widget.setObjectName("card")
        widget.setStyleSheet("""
            QWidget#card {
                background-color: white;
                border: 1px solid #e0e0e0;
                border-radius: 10px;
            }
            QWidget#card:hover {
                border: 1px solid #bdc3c7;
                background-color: #f8f9f9;
            }
        """)
        
        widget.setFixedHeight(180)
        widget.setMinimumWidth(300)
        
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(15)
        
        cover_container = QWidget()
        cover_container.setFixedSize(120, 68)
        cover_container.setStyleSheet("background-color: #f5f5f5; border-radius: 5px;")
        cover_layout = QVBoxLayout(cover_container)
        cover_layout.setContentsMargins(0, 0, 0, 0)
        

        original_item = None
        original_widget = None
        for i in range(self.download_list.count()):
            if self.pending_items[i] == url:
                original_item = self.download_list.item(i)
                original_widget = self.download_list.itemWidget(original_item)
                break
        
        cover_label = QLabel()
        cover_label.setObjectName("cover")
        cover_label.setFixedSize(120, 68)
        cover_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cover_label.setStyleSheet("""
            QLabel#cover {
                background-color: #f5f5f5;
                border-radius: 5px;
            }
        """)
        
        if original_widget:
            original_cover = original_widget.findChild(QLabel, "cover")
            if original_cover and original_cover.pixmap():
                cover_label.setPixmap(original_cover.pixmap())
        
        cover_layout.addWidget(cover_label)
        layout.addWidget(cover_container)
        
        info_container = QWidget()
        info_layout = QVBoxLayout(info_container)
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(10)
        
        file_name = os.path.basename(file_path)
        file_label = QLabel(file_name)
        file_label.setWordWrap(True)
        file_label.setStyleSheet("""
            font-size: 16px;
            font-weight: bold;
            color: #2c3e50;
            background-color: white;
            padding: 0;
            margin: 0;
        """)
        file_label.setMinimumHeight(40)
        file_label.setMaximumHeight(50)
        info_layout.addWidget(file_label)

        status_widget = QWidget()
        status_widget.setStyleSheet("""
            background-color: white;
            border-radius: 5px;
            padding: 0;
            margin: 0;
        """)
        status_widget.setFixedHeight(30)
        
        status_layout = QHBoxLayout(status_widget)
        status_layout.setContentsMargins(0, 0, 0, 0)
        
        status_label = QLabel("✅ Download Complete")
        status_label.setStyleSheet("""
            color: #27ae60;
            font-weight: bold;
            font-size: 13px;
            background-color: white;
        """)
        status_layout.addWidget(status_label)
        status_layout.addStretch()
        info_layout.addWidget(status_widget)
        
        button_widget = QWidget()
        button_widget.setFixedHeight(35)
        button_layout = QHBoxLayout(button_widget)
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.setSpacing(10)
        
        play_btn = QPushButton("▶️ Play")
        play_btn.setFixedSize(100, 32)
        play_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        play_btn.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 8px 15px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
            QPushButton:pressed {
                background-color: #2475a8;
            }
        """)
        play_btn.clicked.connect(lambda: self.play_video(file_path))
        
        folder_btn = QPushButton("📁 Folder")
        folder_btn.setFixedSize(100, 32)
        folder_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        folder_btn.setStyleSheet("""
            QPushButton {
                background-color: #7f8c8d;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 8px 15px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #6c7a7d;
            }
            QPushButton:pressed {
                background-color: #5f6b6d;
            }
        """)
        folder_btn.clicked.connect(lambda: self.open_folder(file_path))
        
        button_layout.addStretch()
        button_layout.addWidget(play_btn)
        button_layout.addWidget(folder_btn)
        info_layout.addWidget(button_widget)
        
        info_container.setMinimumWidth(400)
        layout.addWidget(info_container, 1)
        
        return widget
    
    def get_format_string(self):
        """根據選擇的畫質和格式返回對應的format字串"""
        quality_map = {
            "Best Quality (4K/2160p)": 2160,
            "Ultra HD (1440p)": 1440,
            "High Quality (1080p)": 1080,
            "High Quality (720p)": 720,
            "Standard (480p)": 480,
            "Smooth (360p)": 360
        }
        selected_quality = self.quality_combo.currentText()
        height = quality_map.get(selected_quality, 2160)

        format_map = {
            "MP4 (H.264)": "bestvideo[height<={height}][vcodec^=avc]+bestaudio[ext=m4a]/best[height<={height}]",
            "MP4 (H.265/HEVC)": "bestvideo[height<={height}][vcodec^=hev]+bestaudio[ext=m4a]/best[height<={height}]",
            "MKV (H.264)": "bestvideo[height<={height}][vcodec^=avc]+bestaudio/best[height<={height}]",
            "MKV (H.265/HEVC)": "bestvideo[height<={height}][vcodec^=hev]+bestaudio/best[height<={height}]",
            "WEBM (VP9)": "bestvideo[height<={height}][vcodec^=vp9]+bestaudio[ext=webm]/best[height<={height}]"
        }
        selected_format = self.format_combo.currentText()
        format_string = format_map.get(selected_format, format_map["MP4 (H.264)"])
        
        return format_string.format(height=height)
    
    def start_download(self, url):
        """開始下載影片"""
        self.update_output(f"Starting download: {url}")
        
        for i in range(self.download_list.count()):
            item = self.download_list.item(i)
            if i < len(self.pending_items) and self.pending_items[i] == url:
                widget = self.download_list.itemWidget(item)
                progress_bar = widget.findChild(QProgressBar)
                progress_bar.show()
                
                download_btn = widget.findChildren(QPushButton)[0]
                download_btn.setEnabled(False)
                download_btn.setText("⏳ Downloading...")
                download_btn.setStyleSheet("""
                    QPushButton {
                        background-color: #95a5a6;
                        color: white;
                        border: none;
                        border-radius: 5px;
                        padding: 8px;
                        font-weight: bold;
                    }
                """)
                
                worker = DownloadWorker(url, self.get_format_string())
                self.workers[url] = worker
                worker.progress.connect(self.update_output)
                worker.progress_percent.connect(lambda p: progress_bar.setValue(int(p)))
                worker.finished.connect(self.on_download_finished)
                worker.start()
                
                break
    
    def on_download_finished(self, url, status, file_path):
        """下載完成後的處理"""
        self.update_output(f"DEBUG: Download finished callback - URL: {url}, Status: {status}, File path: {file_path}")
        if status == "success" and os.path.exists(file_path):
            try:

                self.update_output(f"DEBUG: Finding index of URL in pending_items: {url}")
                self.update_output(f"DEBUG: Current pending_items: {self.pending_items}")
                
                QApplication.processEvents()
                

                index = self.pending_items.index(url)
                self.update_output(f"DEBUG: Found index: {index}")
                
                item = self.download_list.item(index)
                if item is None:
                    raise ValueError(f"Cannot find item at index {index}")
                
                completed_widget = self.create_completed_item_widget(url, file_path)
                item.setSizeHint(completed_widget.sizeHint())
                self.download_list.setItemWidget(item, completed_widget)
                
                self.completed_items.append((url, file_path))
                self.update_output(f"DEBUG: Updated item status to completed")
                

                if url in self.workers:
                    self.workers[url].deleteLater()
                    del self.workers[url]
                    self.update_output(f"DEBUG: Cleaning worker")
                
                self.update_output(f"✅ Download completed: {os.path.basename(file_path)}")
                
                QApplication.processEvents()
                
            except ValueError as e:
                self.update_output(f"❌ No corresponding URL found: {url}, Error: {str(e)}")
            except Exception as e:
                self.update_output(f"❌ Error updating item status: {str(e)}")
        else:
            self.update_output(f"❌ Download failed or file does not exist: {file_path}")
    
    def update_output(self, message):
        """更新輸出區"""
        self.output_text.append(message)
    
    def play_video(self, file_path):
        """播放影片"""
        if os.path.exists(file_path):
            try:
                if sys.platform == 'win32':
                    os.startfile(file_path)
                elif sys.platform == 'darwin':
                    subprocess.call(['open', file_path])
                else:
                    subprocess.call(['xdg-open', file_path])
            except Exception as e:
                self.update_output(f"❌ Play failed: {str(e)}")
        else:
            self.update_output(f"❌ File not found: {file_path}")
    
    def open_folder(self, file_path):
        """打開文件所在文件夾"""
        folder_path = os.path.dirname(os.path.abspath(file_path))
        if os.path.exists(folder_path):
            try:
                if sys.platform == 'win32':
                    os.startfile(folder_path)
                elif sys.platform == 'darwin':
                    subprocess.call(['open', folder_path])
                else:
                    subprocess.call(['xdg-open', folder_path])
            except Exception as e:
                self.update_output(f"❌ Failed to open folder: {str(e)}")
        else:
            self.update_output(f"❌ Folder not found: {folder_path}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = YouTubeDownloaderGUI()
    window.show()
    sys.exit(app.exec())
