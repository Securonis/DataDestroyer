import os
import random
import string
import threading
import sys
import datetime
import hashlib
import subprocess
import pwd
import grp
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QLineEdit, QPushButton, 
                             QRadioButton, QButtonGroup, QSpinBox, QTextEdit, 
                             QProgressBar, QFileDialog, QMessageBox, QCheckBox,
                             QTreeWidget, QTreeWidgetItem, QTabWidget)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QSize, QTimer
from PyQt5.QtGui import QIcon, QFont, QColor, QPalette

# Core functionality
def overwrite_file(file_path, passes=3, mode="standard", update_callback=None):
    try:
        # Check if file exists and is accessible
        if not os.path.exists(file_path):
            if update_callback:
                update_callback(0, passes, "Error: File does not exist.")
            return False
            
        # Check file permissions (important for Linux)
        if not os.access(file_path, os.W_OK):
            if update_callback:
                update_callback(0, passes, "Error: No write permission for this file.")
            return False
            
        file_size = os.path.getsize(file_path)
        
        # Ensure we have enough disk space for overwriting
        try:
            fs_stats = os.statvfs(os.path.dirname(file_path))
            free_space = fs_stats.f_frsize * fs_stats.f_bavail
            if mode == "nsa" and free_space < file_size * 4:
                if update_callback:
                    update_callback(0, passes, "Error: Not enough disk space for NSA mode.")
                return False
            elif free_space < file_size * passes:
                if update_callback:
                    update_callback(0, passes, "Error: Not enough disk space for overwrite passes.")
                return False
        except Exception as e:
            if update_callback:
                update_callback(0, passes, f"Error checking disk space: {e}")
            return False

        # Flush filesystem buffers to ensure all previous changes are written
        try:
            os.fsync(os.open(os.path.dirname(file_path), os.O_RDONLY))
        except (AttributeError, OSError):
            # Not all platforms support this
            pass

        with open(file_path, "ba+", buffering=0) as d:
            if mode == "nsa":
                # NSA recommended pattern (4 passes with specific patterns)
                # Pass 1: Random data
                if update_callback:
                    update_callback(1, 4, "Overwriting pass 1/4: Random data...")
                d.seek(0)
                d.write(os.urandom(file_size))
                d.flush()
                os.fsync(d.fileno())
                
                # Pass 2: All zeros (0x00)
                if update_callback:
                    update_callback(2, 4, "Overwriting pass 2/4: All zeros...")
                d.seek(0)
                d.write(b'\x00' * file_size)
                d.flush()
                os.fsync(d.fileno())
                
                # Pass 3: All ones (0xFF)
                if update_callback:
                    update_callback(3, 4, "Overwriting pass 3/4: All ones...")
                d.seek(0)
                d.write(b'\xFF' * file_size)
                d.flush()
                os.fsync(d.fileno())
                
                # Pass 4: Random data again
                if update_callback:
                    update_callback(4, 4, "Overwriting pass 4/4: Random data...")
                d.seek(0)
                d.write(os.urandom(file_size))
                d.flush()
                os.fsync(d.fileno())
            else:  # Standard mode: multiple random passes
                for i in range(passes):
                    if update_callback:
                        update_callback(i+1, passes, f"Overwriting pass {i+1}/{passes}...")
                    d.seek(0)
                    d.write(os.urandom(file_size))
                    d.flush()
                    os.fsync(d.fileno())
                    
        return True
    except PermissionError as e:
        if update_callback:
            update_callback(0, passes, f"Permission denied: {e}")
            if platform.system() == "Linux":
                update_callback(0, passes, "Try running with sudo or as root for system files.")
        return False
    except OSError as e:
        if update_callback:
            update_callback(0, passes, f"OS Error: {e}")
            if "No space left" in str(e):
                update_callback(0, passes, "Error: No disk space left.")
        return False
    except Exception as e:
        if update_callback:
            update_callback(0, passes, f"Error overwriting file: {e}")
        return False

def rename_file(file_path, update_callback=None):
    dir_name = os.path.dirname(file_path)
    random_name = ''.join(random.choices(string.ascii_letters + string.digits, k=12))
    new_path = os.path.join(dir_name, random_name)
    try:
        os.rename(file_path, new_path)
        if update_callback:
            update_callback(f"File renamed to: {new_path}")
        return new_path
    except Exception as e:
        if update_callback:
            update_callback(f"Error renaming file: {e}")
        return file_path

def delete_file(file_path, update_callback=None):
    try:
        os.remove(file_path)
        if update_callback:
            update_callback("File deleted successfully.")
        
        # Verify deletion
        if not os.path.exists(file_path):
            if update_callback:
                update_callback("Verified: File no longer exists.")
            return True
        else:
            if update_callback:
                update_callback("Warning: File still exists after deletion attempt.")
            return False
    except Exception as e:
        if update_callback:
            update_callback(f"Error deleting file: {e}")
        return False

def get_file_info(file_path):
    """Get detailed information about a file"""
    try:
        if not os.path.exists(file_path):
            return {"error": "File does not exist"}
        
        stat_info = os.stat(file_path)
        file_size = stat_info.st_size
        
        change_time = datetime.datetime.fromtimestamp(stat_info.st_ctime).strftime('%Y-%m-%d %H:%M:%S')
        modified_time = datetime.datetime.fromtimestamp(stat_info.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
        access_time = datetime.datetime.fromtimestamp(stat_info.st_atime).strftime('%Y-%m-%d %H:%M:%S')
        
        # Calculate file hash (for small files only, to avoid performance issues)
        file_hash = "Not calculated (file too large)"
        if file_size < 10 * 1024 * 1024:  # Only for files < 10MB
            try:
                with open(file_path, 'rb') as f:
                    file_hash = hashlib.md5(f.read()).hexdigest()
            except Exception:
                file_hash = "Error calculating hash"
        
        permissions = oct(stat_info.st_mode)[-3:]
        permissions_text = ""
        try:
            import pwd, grp
            user = pwd.getpwuid(stat_info.st_uid).pw_name
            group = grp.getgrgid(stat_info.st_gid).gr_name
            permissions_text = f"{user}:{group}"
        except (ImportError, KeyError):
            permissions_text = f"UID:{stat_info.st_uid} GID:{stat_info.st_gid}"
        
        # Sembolik bağlantı kontrolü
        link_target = ""
        if os.path.islink(file_path):
            try:
                link_target = os.readlink(file_path)
            except:
                link_target = "Error reading link"
        
        # Check if file is executable
        is_executable = "Yes" if os.access(file_path, os.X_OK) else "No"
        
        return {
            "name": os.path.basename(file_path),
            "path": os.path.dirname(file_path) or "./",
            "size": file_size,
            "size_human": format_size(file_size),
            "mod": permissions,
            "owner": permissions_text,
            "status_change": change_time,
            "modified": modified_time,
            "last_access": access_time,
            "executable": is_executable,
            "symlink": link_target if link_target else "No", 
            "hash": file_hash,
            "filesystem": get_filesystem_type(file_path)
        }
    except Exception as e:
        return {"error": str(e)}
        
def get_filesystem_type(path):
    """Get the filesystem type for a given path"""
    try:
        import subprocess
        mount_point = subprocess.check_output(["df", "--output=fstype", path]).decode().split("\n")[1].strip()
        return mount_point
    except:
        return "Unknown"

def format_size(size_bytes):
    """Format file size to human-readable format"""
    if size_bytes < 1024:
        return f"{size_bytes} bytes"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.2f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.2f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"

def secure_delete(file_path, passes, mode="standard", update_callback=None):
    if not os.path.isfile(file_path):
        if update_callback:
            update_callback("Not a valid file.")
        return False

    success = overwrite_file(file_path, passes, mode, update_callback)
    if success:
        renamed_path = rename_file(file_path, update_callback)
        return delete_file(renamed_path, update_callback)
    return False

# Worker thread for file processing
class DestructionWorker(QThread):
    progress_update = pyqtSignal(int, int, str)
    status_update = pyqtSignal(str)
    operation_complete = pyqtSignal(bool)
    
    def __init__(self, files_to_process, passes):
        super().__init__()
        self.files_to_process = files_to_process
        self.passes = passes
        self.deletion_mode = "standard"
    
    def run(self):
        total_files = len(self.files_to_process)
        
        for idx, file_path in enumerate(self.files_to_process):
            self.status_update.emit(f"Processing file {idx+1} of {total_files}: {os.path.basename(file_path)}")
            
            # Define a callback for progress updates
            def update_callback(current=0, total=0, message=""):
                if isinstance(current, str):  # For string messages
                    self.status_update.emit(current)
                else:  # For progress updates
                    progress_percent = int((idx * self.passes + current) / (total_files * self.passes) * 100)
                    self.progress_update.emit(progress_percent, idx+1, message)
            
            # Process the file
            success = secure_delete(file_path, self.passes, self.deletion_mode, update_callback)
            if not success:
                self.status_update.emit(f"Failed to destroy: {file_path}")
        
        self.progress_update.emit(100, total_files, "All files processed")
        self.operation_complete.emit(True)

# Modern UI
class SecuronisDataDestroyer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.init_ui()
        
    def init_ui(self):
        # Set window properties
        self.setWindowTitle("Securonis Data Destroyer")
        self.setMinimumSize(700, 600)
        self.setStyleSheet("""
            QMainWindow {
                background-color: #1e1e1e;
            }
            QWidget {
                background-color: #1e1e1e;
                color: #ffffff;
                font-family: 'Segoe UI', Arial;
                font-size: 10pt;
            }
            QLabel {
                color: #ffffff;
            }
            QLineEdit, QTextEdit, QSpinBox {
                background-color: #2d2d2d;
                border: 1px solid #3d3d3d;
                border-radius: 4px;
                padding: 5px;
                selection-background-color: #0078d7;
            }
            QPushButton {
                background-color: #0078d7;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: #1e88e5;
            }
            QPushButton:pressed {
                background-color: #005fb8;
            }
            QPushButton#destroyBtn {
                background-color: #e81123;
                font-weight: bold;
                padding: 10px 20px;
            }
            QPushButton#destroyBtn:hover {
                background-color: #f25056;
            }
            QProgressBar {
                border: 1px solid #3d3d3d;
                border-radius: 4px;
                text-align: center;
                background-color: #2d2d2d;
            }
            QProgressBar::chunk {
                background-color: #0078d7;
                width: 1px;
            }
            QRadioButton {
                color: #ffffff;
                spacing: 5px;
            }
            QRadioButton::indicator {
                width: 18px;
                height: 18px;
            }
        """)
        
        # Create central widget and main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)
        
        # Header section
        header_layout = QVBoxLayout()
        title_label = QLabel("DATA DESTROYER")
        title_label.setAlignment(Qt.AlignCenter)
        title_font = QFont("Segoe UI", 22, QFont.Bold)
        title_label.setFont(title_font)
        title_label.setStyleSheet("color: #e81123; margin-bottom: 10px;")
        
        desc_label = QLabel("Securely delete files by overwriting, renaming, and removing them")
        desc_label.setAlignment(Qt.AlignCenter)
        desc_label.setWordWrap(True)
        
        header_layout.addWidget(title_label)
        header_layout.addWidget(desc_label)
        main_layout.addLayout(header_layout)
        
        # Mode selection section
        mode_layout = QHBoxLayout()
        mode_label = QLabel("Mode:")
        
        self.single_radio = QRadioButton("Single File")
        self.single_radio.setChecked(True)
        self.folder_radio = QRadioButton("Folder")
        
        mode_layout.addWidget(mode_label)
        mode_layout.addWidget(self.single_radio)
        mode_layout.addWidget(self.folder_radio)
        mode_layout.addStretch(1)
        main_layout.addLayout(mode_layout)
        
        # Connect radio buttons
        self.single_radio.toggled.connect(self.toggle_mode)
        
        # Create tabbed layout for main content area
        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet("""
            QTabWidget::pane { 
                border: 1px solid #3d3d3d; 
                background-color: #1e1e1e; 
            }
            QTabBar::tab { 
                background-color: #2d2d2d; 
                color: #9e9e9e; 
                padding: 8px 20px; 
            }
            QTabBar::tab:selected { 
                background-color: #0078d7; 
                color: white; 
            }
            QTabBar::tab:hover:!selected { 
                background-color: #3d3d3d; 
            }
        """)
        
        # Main tab
        main_tab = QWidget()
        main_tab_layout = QVBoxLayout(main_tab)
        
        # File selection section
        file_layout = QHBoxLayout()
        self.file_label = QLabel("Selected File:")
        
        self.file_path_input = QLineEdit()
        self.file_path_input.setReadOnly(True)
        self.file_path_input.setMinimumWidth(400)
        
        self.browse_button = QPushButton("Browse")
        self.browse_button.clicked.connect(self.browse_file)
        
        file_layout.addWidget(self.file_label)
        file_layout.addWidget(self.file_path_input)
        file_layout.addWidget(self.browse_button)
        main_tab_layout.addLayout(file_layout)
        
        # Add file info display
        self.file_info_tree = QTreeWidget()
        self.file_info_tree.setHeaderLabel("File Information")
        self.file_info_tree.setMinimumHeight(120)
        self.file_info_tree.setColumnCount(2)
        self.file_info_tree.setHeaderLabels(["Property", "Value"])
        self.file_info_tree.setAlternatingRowColors(True)
        self.file_info_tree.setStyleSheet("""
            QTreeWidget {
                background-color: #2d2d2d;
                alternate-background-color: #333333;
                color: #e0e0e0;
                border: 1px solid #3d3d3d;
            }
            QHeaderView::section {
                background-color: #424242;
                color: white;
                padding: 4px;
                border: 1px solid #3d3d3d;
            }
        """)
        main_tab_layout.addWidget(self.file_info_tree)
        
        # Add view file info button
        info_button_layout = QHBoxLayout()
        self.view_info_button = QPushButton("View File Details")
        self.view_info_button.clicked.connect(self.show_file_info)
        self.verify_button = QPushButton("Verify File Exists")
        self.verify_button.clicked.connect(self.verify_file)
        
        info_button_layout.addWidget(self.view_info_button)
        info_button_layout.addWidget(self.verify_button)
        info_button_layout.addStretch(1)
        main_tab_layout.addLayout(info_button_layout)
        
        # Add the main tab to tab widget
        self.tab_widget.addTab(main_tab, "File Selection")
        
        # Log tab
        log_tab = QWidget()
        log_tab_layout = QVBoxLayout(log_tab)
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMinimumHeight(150)
        log_tab_layout.addWidget(self.log_text)
        
        self.tab_widget.addTab(log_tab, "Operation Log")
        
        # Add tab widget to main layout
        main_layout.addWidget(self.tab_widget)
        
        # Options section
        options_layout = QHBoxLayout()
        
        # Deletion mode options
        mode_group_layout = QVBoxLayout()
        deletion_mode_label = QLabel("Deletion Mode:")
        
        self.mode_standard_radio = QRadioButton("Standard (Random Data)")
        self.mode_standard_radio.setChecked(True)
        self.mode_nsa_radio = QRadioButton("NSA-Recommended Pattern")
        
        # Create a button group for deletion modes
        deletion_mode_group = QButtonGroup(self)
        deletion_mode_group.addButton(self.mode_standard_radio)
        deletion_mode_group.addButton(self.mode_nsa_radio)
        
        # Connect mode selection change
        self.mode_standard_radio.toggled.connect(self.toggle_deletion_mode)
        
        mode_group_layout.addWidget(deletion_mode_label)
        mode_group_layout.addWidget(self.mode_standard_radio)
        mode_group_layout.addWidget(self.mode_nsa_radio)
        
        # Standard mode options
        passes_layout = QHBoxLayout()
        passes_label = QLabel("Overwrite Passes:")
        
        self.passes_spinbox = QSpinBox()
        self.passes_spinbox.setRange(1, 10)
        self.passes_spinbox.setValue(3)
        
        passes_layout.addWidget(passes_label)
        passes_layout.addWidget(self.passes_spinbox)
        
        # Add all to main options layout
        options_layout.addLayout(mode_group_layout)
        options_layout.addLayout(passes_layout)
        options_layout.addStretch(1)
        main_layout.addLayout(options_layout)
        
        # Progress section
        progress_layout = QVBoxLayout()
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        
        self.status_label = QLabel("Ready")
        
        progress_layout.addWidget(self.progress_bar)
        progress_layout.addWidget(self.status_label)
        main_layout.addLayout(progress_layout)
        
        # Actions section
        actions_layout = QHBoxLayout()
        actions_layout.setContentsMargins(0, 10, 0, 0)
        
        self.destroy_button = QPushButton("DESTROY")
        self.destroy_button.setObjectName("destroyBtn")
        self.destroy_button.setMinimumHeight(50)
        self.destroy_button.clicked.connect(self.start_destruction)
        
        actions_layout.addStretch(1)
        actions_layout.addWidget(self.destroy_button)
        actions_layout.addStretch(1)
        main_layout.addLayout(actions_layout)
        
        # Initialize variables
        self.files_to_process = []
        self.process_mode = "single"
        self.deletion_mode = "standard"
        
        # Log initial message
        self.log_message("Application started. Ready for operation.")
    
    def toggle_mode(self):
        if self.single_radio.isChecked():
            self.process_mode = "single"
            self.file_label.setText("Selected File:")
            self.browse_button.clicked.disconnect()
            self.browse_button.clicked.connect(self.browse_file)
        else:
            self.process_mode = "folder"
            self.file_label.setText("Selected Folder:")
            self.browse_button.clicked.disconnect()
            self.browse_button.clicked.connect(self.browse_folder)
        
        self.file_path_input.clear()
    
    def toggle_deletion_mode(self):
        if self.mode_standard_radio.isChecked():
            self.deletion_mode = "standard"
            self.passes_spinbox.setEnabled(True)
            self.log_message("Standard deletion mode selected: Multiple random passes")
        else:
            self.deletion_mode = "nsa"
            self.passes_spinbox.setEnabled(False)  # NSA mode uses fixed 4 passes
            self.log_message("NSA-recommended deletion mode selected: 4 specific pattern passes")
    
    def browse_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select File to Destroy")
        if file_path:
            self.file_path_input.setText(file_path)
            self.log_message(f"Selected file: {file_path}")
    
    def browse_folder(self):
        folder_path = QFileDialog.getExistingDirectory(self, "Select Folder to Process")
        if folder_path:
            self.file_path_input.setText(folder_path)
            self.log_message(f"Selected folder: {folder_path}")
    
    def log_message(self, message):
        self.log_text.append(message)
        # Auto scroll to bottom
        self.log_text.verticalScrollBar().setValue(self.log_text.verticalScrollBar().maximum())
    
    def show_file_info(self):
        file_path = self.file_path_input.text().strip()
        if not file_path:
            QMessageBox.warning(self, "Warning", "Please select a file first.")
            return
            
        if os.path.isfile(file_path):
            # Get file information
            info = get_file_info(file_path)
            self.display_file_info(info)
            self.log_message(f"Displayed information for file: {file_path}")
        elif os.path.isdir(file_path):
            QMessageBox.information(self, "Information", "Selected path is a directory. File information is only available for individual files.")
        else:
            QMessageBox.critical(self, "Error", "The selected file does not exist.")
    
    def display_file_info(self, info):
        # Clear previous info
        self.file_info_tree.clear()
        
        if "error" in info:
            item = QTreeWidgetItem(["Error", info["error"]])
            self.file_info_tree.addTopLevelItem(item)
            return
            
        # Add file information to tree
        for prop, value in info.items():
            if prop != "size":  # Skip raw size in bytes, we already have human-readable size
                item = QTreeWidgetItem([prop.capitalize(), str(value)])
                self.file_info_tree.addTopLevelItem(item)
                
        # Resize columns to content
        for i in range(self.file_info_tree.columnCount()):
            self.file_info_tree.resizeColumnToContents(i)
    
    def verify_file(self):
        file_path = self.file_path_input.text().strip()
        if not file_path:
            QMessageBox.warning(self, "Warning", "Please select a file first.")
            return
            
        if os.path.exists(file_path):
            if os.path.isfile(file_path):
                self.log_message(f"File verification: {file_path} exists.")
                QMessageBox.information(self, "File Verification", f"The file {os.path.basename(file_path)} exists.")
            else:
                self.log_message(f"Path verification: {file_path} exists (directory).")
                QMessageBox.information(self, "Directory Verification", f"The path exists but is a directory, not a file.")
        else:
            self.log_message(f"File verification: {file_path} does not exist.")
            QMessageBox.warning(self, "File Verification", f"The file {file_path} does not exist.")

    
    def find_files_in_folder(self, folder_path):
        files = []
        for root, _, filenames in os.walk(folder_path):
            for filename in filenames:
                files.append(os.path.join(root, filename))
        return files
    
    def start_destruction(self):
        path = self.file_path_input.text().strip()
        if not path:
            QMessageBox.warning(self, "Warning", "Please select a file or folder first.")
            return
        
        # Prepare files list based on mode
        self.files_to_process = []
        if self.process_mode == "single":
            if os.path.isfile(path):
                self.files_to_process = [path]
            else:
                QMessageBox.critical(self, "Error", "The selected path is not a valid file.")
                return
        else:  # folder mode
            if os.path.isdir(path):
                self.files_to_process = self.find_files_in_folder(path)
                if not self.files_to_process:
                    QMessageBox.information(self, "Information", "No files found in the selected folder.")
                    return
            else:
                QMessageBox.critical(self, "Error", "The selected path is not a valid folder.")
                return
        
        # Confirm destruction
        file_count = len(self.files_to_process)
        confirm_message = f"Are you sure you want to permanently destroy {file_count} file{'s' if file_count > 1 else ''}?\n\n"
        
        if file_count == 1:
            confirm_message += f"{self.files_to_process[0]}\n"
        else:
            confirm_message += f"{file_count} files in {path}\n"
            
        confirm_message += "\nThis action CANNOT be undone!"
        
        reply = QMessageBox.question(self, "Confirm Destruction", confirm_message, 
                                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            # Disable UI elements during processing
            self.destroy_button.setEnabled(False)
            self.browse_button.setEnabled(False)
            self.progress_bar.setValue(0)
            self.status_label.setText("Starting destruction process...")
            self.log_message("---- Starting new destruction process ----")
            
            # Setup and start worker thread
            passes = self.passes_spinbox.value() if self.deletion_mode == "standard" else 4  # NSA mode has fixed 4 passes
            self.worker = DestructionWorker(self.files_to_process, passes)
            self.worker.progress_update.connect(self.update_progress)
            self.worker.status_update.connect(self.log_message)
            self.worker.operation_complete.connect(self.process_complete)
            
            # Set deletion mode property on worker
            self.worker.deletion_mode = self.deletion_mode
            self.worker.start()
    
    def update_progress(self, percent, file_num, message):
        self.progress_bar.setValue(percent)
        self.status_label.setText(message)
    
    def process_complete(self, success):
        # Re-enable UI elements
        self.destroy_button.setEnabled(True)
        self.browse_button.setEnabled(True)
        
        # Show completion message
        file_count = len(self.files_to_process)
        QMessageBox.information(self, "Process Complete", 
                              f"Completed processing {file_count} file{'s' if file_count > 1 else ''}.")
        self.log_message("---- Destruction process completed ----")

# Main execution
if __name__ == "__main__":
    # Linux dağıtım bilgilerini al
    try:
        with open('/etc/os-release', 'r') as f:
            distro_info = dict(line.strip().split('=', 1) for line in f if '=' in line)
        distro_name = distro_info.get('NAME', 'Linux').strip('"')
        distro_version = distro_info.get('VERSION', 'Unknown').strip('"')
        distro_codename = distro_info.get('VERSION_CODENAME', '').strip('"')
        
        # Eğer kod adı varsa, parantez içinde göster
        version_display = distro_version
        if distro_codename:
            version_display += f" ({distro_codename})"
    except Exception:
        distro_name = "Linux"
        version_display = ""
    
    # Print a banner with application info
    print("="*60)
    print("               SECURONIS")
    print("         Data Destruction Utility Pro")
    print(f"         {distro_name} {version_display}")
    print("="*60)
    
    # Check if we're running with the right permissions (root required)
    if os.geteuid() != 0:
        print("\nWARNING: Not running as root. Some system files may not be accessible.")
        print("For full functionality, consider running with 'sudo python3 modern_data_destroyer.py'\n")
        print("Continuing with limited permissions...")
    else:
        print("\nRunning with root privileges. Full system access enabled.\n")
    
    # Handle high DPI screens better
    if hasattr(Qt, 'AA_EnableHighDpiScaling'):
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    if hasattr(Qt, 'AA_UseHighDpiPixmaps'):
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    
    # Check for required packages
    required_packages = ['python3-pyqt5', 'python3-pyqt5.qtsvg']
    missing_packages = []
    
    for pkg in required_packages:
        try:
            if subprocess.call(['dpkg', '-s', pkg], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) != 0:
                missing_packages.append(pkg)
        except Exception:
            pass
    
    if missing_packages:
        print("Warning: The following required packages are missing:")
        for pkg in missing_packages:
            print(f" - {pkg}")
        print("\nTo install them, run: sudo apt install " + " ".join(missing_packages))
        print("\nContinuing anyway, but the application may not work correctly.\n")
    
    # Initialize application
    app = QApplication(sys.argv)
    window = SecuronisDataDestroyer()
    window.show()
    sys.exit(app.exec_())
