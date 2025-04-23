from PyQt6.QtWidgets import QApplication
import sys
from gui import YouTubeDownloaderGUI


if __name__ == "__main__":
    
    if not hasattr(sys, 'frozen'):
        import multiprocessing
        multiprocessing.freeze_support()
    
    app = QApplication(sys.argv)
    window = YouTubeDownloaderGUI()
    window.show()
    sys.exit(app.exec())
