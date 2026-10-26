import sys
import subprocess
import os
import time
import glob
import re

from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QTabWidget,
    QTextEdit,
    QLabel,
    QMessageBox,
    QInputDialog,
    QFileDialog,
    QSplitter,
    QComboBox,
    QToolButton,
    QStyle,
    QLineEdit,
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QSize

from PyQt5.QtGui import QTextCursor


class ScriptRunner(QThread):
    """后台线程执行脚本"""

    update_signal = pyqtSignal(str, str)  # (script_path, message)
    state_signal = pyqtSignal(str, str)  # (script_path, state)
    finished_signal = pyqtSignal(str, bool)  # (script_path, success)

    def __init__(self, script_path, python_path):
        super().__init__()
        self.script_path = script_path
        self.python_path = python_path
        self.process = None
        self.running = True

    def run(self):
        try:
            self.state_signal.emit(self.script_path, "运行中")
            self.update_signal.emit(self.script_path, f"[{self._get_time()}] 正在启动: {self.script_path}")
            self.update_signal.emit(self.script_path, f"[{self._get_time()}] 使用环境: {self.python_path}")

            # 确保不是 pythonw.exe（其可能吞掉控制台输出）
            exec_path = self.python_path
            try:
                if exec_path and exec_path.lower().endswith("pythonw.exe"):
                    candidate = os.path.join(os.path.dirname(exec_path), "python.exe")
                    if os.path.exists(candidate):
                        exec_path = candidate
            except Exception:
                pass

            # 使用无缓冲模式并统一编码，确保 print 可实时输出且不乱码
            cmd = [exec_path, "-u", self.script_path]
            env = os.environ.copy()
            env.setdefault("PYTHONUNBUFFERED", "1")
            env.setdefault("PYTHONIOENCODING", "utf-8")
            env["PYTHONNOUSERSITE"] = "1"

            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,  # 行缓冲（配合 text=True / universal_newlines=True）
                universal_newlines=True,
                encoding="utf-8",
                errors="replace",
                env=env,
                cwd=os.path.dirname(os.path.abspath(__file__)),
            )

            while self.running and self.process.poll() is None:
                output = self.process.stdout.readline()
                if output:
                    self.update_signal.emit(self.script_path, f"[{self._get_time()}] {output.strip()}")

            return_code = self.process.poll()
            if return_code is not None:
                if return_code == 0:
                    self.update_signal.emit(self.script_path, f"[{self._get_time()}] 执行完成")
                    self.state_signal.emit(self.script_path, "已完成")
                    self.finished_signal.emit(self.script_path, True)
                else:
                    self.update_signal.emit(
                        self.script_path,
                        f"[{self._get_time()}] 执行失败，返回码: {return_code}",
                    )
                    self.state_signal.emit(self.script_path, "已失败")
                    self.finished_signal.emit(self.script_path, False)
            else:
                self.update_signal.emit(self.script_path, f"[{self._get_time()}] 执行已停止")
                self.state_signal.emit(self.script_path, "已停止")

        except Exception as e:
            self.update_signal.emit(self.script_path, f"[{self._get_time()}] 错误: {str(e)}")
            self.state_signal.emit(self.script_path, "错误")
            self.finished_signal.emit(self.script_path, False)

    def stop(self):
        self.running = False
        if self.process and self.process.poll() is None:
            self.update_signal.emit(self.script_path, f"[{self._get_time()}] 正在终止...")
            self.process.terminate()
            try:
                # 等待进程结束
                for _ in range(10):  # 最多等待1秒
                    if self.process.poll() is not None:
                        break
                    time.sleep(0.1)
                if self.process.poll() is None:
                    self.process.kill()
                    self.update_signal.emit(self.script_path, f"[{self._get_time()}] 已强制终止")
            except Exception as e:
                self.update_signal.emit(self.script_path, f"[{self._get_time()}] 终止失败: {str(e)}")

    def _get_time(self):
        return time.strftime("%H:%M:%S")


class ScriptItemWidget(QWidget):
    """脚本列表项控件，包含状态和操作按钮"""

    start_signal = pyqtSignal(str, str)
    stop_signal = pyqtSignal(str, str)
    restart_signal = pyqtSignal(str, str)
    change_path_signal = pyqtSignal(str, str)  # 新增修改路径信号

    def __init__(self, script_path, display_name, parent=None):
        super().__init__(parent)
        self.script_path = script_path
        self.display_name = display_name
        self.state = "就绪"

        # 主布局
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(12)

        # 脚本名称标签
        self.name_label = QLabel(self.display_name)
        self.name_label.setToolTip(script_path)
        self.name_label.setStyleSheet("font-size: 16px; font-weight: 500;")
        layout.addWidget(self.name_label, 1)

        # 状态标签
        self.state_label = QLabel(self.state)
        self.state_label.setAlignment(Qt.AlignCenter)
        self.state_label.setMinimumWidth(100)
        self.state_label.setStyleSheet(self._get_state_style())
        layout.addWidget(self.state_label)

        # 操作按钮
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        # 启动按钮
        self.start_btn = QToolButton()
        self.start_btn.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
        self.start_btn.setToolTip("启动")
        self.start_btn.setFixedSize(32, 32)
        self.start_btn.setStyleSheet("border-radius: 6px;")
        self.start_btn.clicked.connect(lambda: self.start_signal.emit(self.script_path, self.display_name))
        btn_layout.addWidget(self.start_btn)

        # 停止按钮
        self.stop_btn = QToolButton()
        self.stop_btn.setIcon(self.style().standardIcon(QStyle.SP_MediaStop))
        self.stop_btn.setToolTip("停止")
        self.stop_btn.setFixedSize(32, 32)
        self.stop_btn.setStyleSheet("border-radius: 6px;")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(lambda: self.stop_signal.emit(self.script_path, self.display_name))
        btn_layout.addWidget(self.stop_btn)

        # 重启按钮
        self.restart_btn = QToolButton()
        self.restart_btn.setIcon(self.style().standardIcon(QStyle.SP_BrowserReload))
        self.restart_btn.setToolTip("重启")
        self.restart_btn.setFixedSize(32, 32)
        self.restart_btn.setStyleSheet("border-radius: 6px;")
        self.restart_btn.setEnabled(False)
        self.restart_btn.clicked.connect(
            lambda: self.restart_signal.emit(self.script_path, self.display_name)
        )
        btn_layout.addWidget(self.restart_btn)

        # 修改路径按钮
        self.change_path_btn = QToolButton()
        self.change_path_btn.setIcon(self.style().standardIcon(QStyle.SP_DirOpenIcon))
        self.change_path_btn.setToolTip("修改脚本路径")
        self.change_path_btn.setFixedSize(32, 32)
        self.change_path_btn.setStyleSheet("border-radius: 6px;")
        self.change_path_btn.clicked.connect(
            lambda: self.change_path_signal.emit(self.script_path, self.display_name)
        )
        btn_layout.addWidget(self.change_path_btn)

        layout.addLayout(btn_layout)

        # 设置布局
        self.setLayout(layout)

    def update_state(self, state):
        """更新状态并设置样式"""
        self.state = state
        self.state_label.setText(state)
        self.state_label.setStyleSheet(self._get_state_style())

        # 根据状态启用/禁用按钮
        self.start_btn.setEnabled(state != "运行中")
        self.stop_btn.setEnabled(state == "运行中")
        self.restart_btn.setEnabled(state == "运行中")

    def _get_state_style(self):
        """根据状态返回样式表"""
        styles = {
            "就绪": "background-color: #e6f7ff; color: #1890ff; border-radius: 6px; padding: 4px 10px; font-size: 14px;",
            "运行中": "background-color: #f6ffed; color: #52c41a; border-radius: 6px; padding: 4px 10px; font-size: 14px;",
            "已完成": "background-color: #f0f2f5; color: #8c8c8c; border-radius: 6px; padding: 4px 10px; font-size: 14px;",
            "已停止": "background-color: #fff2e8; color: #fa8c16; border-radius: 6px; padding: 4px 10px; font-size: 14px;",
            "已失败": "background-color: #fff1f0; color: #f5222d; border-radius: 6px; padding: 4px 10px; font-size: 14px;",
            "错误": "background-color: #fff1f0; color: #f5222d; border-radius: 6px; padding: 4px 10px; font-size: 14px;",
        }
        return styles.get(self.state, "border-radius: 6px; padding: 4px 10px; font-size: 14px;")


class ScriptLauncherApp(QMainWindow):
    """Python脚本启动器（增强版）"""

    def __init__(self):
        super().__init__()
        # 初始化变量
        self.script_list = []  # 脚本路径列表
        self.script_display_names = {}  # {script_path: display_name}
        self.script_widgets = {}  # {script_path: ScriptItemWidget}
        self.running_scripts = {}  # {script_path: ScriptRunner}
        self.script_outputs = {}  # {script_path: QTextEdit}
        self.main_script_path = None
        self.server_address_line_edit = None
        self.patient_status_label = None
        self.doctor_status_label = None
        self.eeg_status_label = None
        self.server_running = False

        # 环境设置
        self.available_pythons = self._detect_python_environments()
        self.selected_python_path = self.available_pythons[0][1] if self.available_pythons else sys.executable

        # 默认脚本列表
        project_dir = os.path.dirname(os.path.abspath(__file__))
        self.default_scripts = {
            os.path.join(project_dir, "main.py"): "服务器端",
            os.path.join(project_dir, "智能查房患者端cs.py"): "患者端",
            os.path.join(project_dir, "run_1cs.py"): "医护端",
            os.path.join(project_dir, "SerialPort32", "Afy_2cs.py"): "脑电采集端",
        }

        # 窗口设置
        self.setWindowTitle("脑机互联查房系统启动终端")
        self.setGeometry(100, 100, 1300, 800)
        self.setMinimumSize(1100, 700)

        # 中心部件与布局
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(15, 15, 15, 15)
        self.main_layout.setSpacing(15)

        # 创建UI组件
        self._create_env_section()  # 环境选择区域
        self._create_script_list_section()  # 脚本列表区域
        self._create_global_controls()  # 全局控制按钮
        # 添加服务器地址文本行和连接状态检测
        self._create_server_address_section()
        self._create_output_section()  # 输出区域

        # 加载默认脚本
        self._load_default_scripts()

        # 应用样式
        self._apply_styles()

    def _apply_styles(self):
        """应用样式表美化界面"""
        self.setStyleSheet("""
            /* 全局样式 */
            QMainWindow, QWidget {
                background-color: #f5f7fa;
                color: #333333;
                font-family: "Microsoft YaHei", "Segoe UI", sans-serif;
                font-size: 16px;  /* 基础字体大小 */
            }

            /* 标题标签 */
            QLabel[font-weight="bold"] {
                font-size: 18px;
                color: #2c3e50;
                padding: 8px 0;
            }

            /* 按钮样式 */
            QPushButton {
                background-color: #4a90e2;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 18px;
                font-size: 16px;
                min-width: 100px;
            }
            QPushButton:hover {
                background-color: #5b9def;
            }
            QPushButton:pressed {
                background-color: #3a80d2;
            }
            QPushButton:disabled {
                background-color: #b8c6d8;
                color: #888888;
            }

            /* 特殊按钮 */
            QPushButton#start_btn {
                background-color: #2ecc71;
            }
            QPushButton#start_btn:hover {
                background-color: #34d986;
            }
            QPushButton#start_btn:pressed {
                background-color: #27ae60;
            }

            QPushButton#stop_btn {
                background-color: #e74c3c;
            }
            QPushButton#stop_btn:hover {
                background-color: #ec5c4e;
            }
            QPushButton#stop_btn:pressed {
                background-color: #c0392b;
            }

            QPushButton#clear_btn {
                background-color: #95a5a6;
            }
            QPushButton#clear_btn:hover {
                background-color: #a5b5b6;
            }
            QPushButton#clear_btn:pressed {
                background-color: #859596;
            }

            /* 工具按钮 */
            QToolButton {
                background-color: #f0f2f5;
                border-radius: 6px;
            }
            QToolButton:hover {
                background-color: #e6e8eb;
            }
            QToolButton:pressed {
                background-color: #d6d8db;
            }

            /* 列表样式 */
            QListWidget {
                background-color: white;
                border: 1px solid #dcdfe6;
                border-radius: 6px;
                padding: 8px;
            }

            /* 文本编辑框 */
            QTextEdit {
                background-color: white;
                border: 1px solid #dcdfe6;
                border-radius: 6px;
                padding: 12px;
                font-family: "Consolas", "Monaco", monospace;
                font-size: 14px;  /* 输出字体大小 */
            }

            /* 标签页样式 */
            QTabWidget::pane {
                border: 1px solid #dcdfe6;
                border-radius: 0 6px 6px 6px;
                background-color: white;
                margin-top: -1px;
            }
            QTabBar::tab {
                background-color: #eaecef;
                color: #666666;
                border: none;
                border-radius: 6px 6px 0 0;
                padding: 10px 18px;
                margin-right: 4px;
                font-size: 16px;
            }
            QTabBar::tab:selected {
                background-color: white;
                color: #2c3e50;
                font-weight: 500;
            }
            QTabBar::tab:hover:!selected {
                background-color: #dcdfe6;
            }

            /* 下拉框 */
            QComboBox {
                border: 1px solid #dcdfe6;
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 16px;
                min-height: 38px;
            }
            QComboBox::drop-down {
                border: none;
            }

            /* 分隔器 */
            QSplitter::handle {
                background-color: #e0e0e0;
                width: 6px;
                height: 6px;
                border-radius: 3px;
            }
            QSplitter::handle:hover {
                background-color: #bbbbbb;
            }
            QLineEdit {
                background-color: white;
                border: 1px solid #dcdfe6;
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 16px;
            }
            QLabel.status-label {
                border-radius: 6px;
                padding: 4px 10px;
                font-size: 14px;
                min-width: 80px;
                text-align: center;
            }
            QLabel.status-label.connected {
                background-color: #52c41a;
                color: white;
            }
            QLabel.status-label.disconnected {
                background-color: #f5222d;
                color: white;
            }
            QLabel.status-label.gray {
                background-color: #cccccc;
                color: white;
            }
        """)

    def _detect_python_environments(self):
        """自动检测系统上的Python环境"""
        environments = []

        # 添加当前环境
        current_python = sys.executable
        current_version = self._get_python_version(current_python)
        environments.append((f"当前环境 ({current_version})", current_python))

        # 尝试在常见位置查找Python
        if os.name == "nt":  # Windows
            # 查找Python安装目录
            for python_path in glob.glob(r"C:\Python*\python.exe"):
                if python_path != current_python:
                    version = self._get_python_version(python_path)
                    environments.append((f"Python {version} ({python_path})", python_path))

            # 查找conda环境
            conda_path = os.path.join(os.environ.get("USERPROFILE", ""), "miniconda3", "envs")
            if os.path.exists(conda_path):
                for env_name in os.listdir(conda_path):
                    env_python = os.path.join(conda_path, env_name, "python.exe")
                    if os.path.exists(env_python) and env_python != current_python:
                        version = self._get_python_version(env_python)
                        environments.append((f"conda: {env_name} ({version})", env_python))
        else:  # Linux/Mac
            # 查找系统Python
            for python_path in ["/usr/bin/python3", "/usr/local/bin/python3"]:
                if os.path.exists(python_path) and python_path != current_python:
                    version = self._get_python_version(python_path)
                    environments.append((f"系统Python {version} ({python_path})", python_path))

            # 查找pyenv环境
            pyenv_path = os.path.join(os.environ.get("HOME", ""), ".pyenv", "shims", "python")
            if os.path.exists(pyenv_path) and pyenv_path != current_python:
                version = self._get_python_version(pyenv_path)
                environments.append((f"pyenv ({version})", pyenv_path))

        return environments

    def _get_python_version(self, python_path):
        """获取Python版本信息"""
        try:
            result = subprocess.run(
                [python_path, "--version"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=3,
            )
            return result.stdout.strip().replace("Python ", "")
        except Exception:
            return "未知版本"

    def _create_env_section(self):
        """创建环境选择区域"""
        env_section = QHBoxLayout()

        # 标题
        env_label = QLabel("执行环境:")
        env_label.setStyleSheet("font-weight: bold;")
        env_section.addWidget(env_label)

        # 环境下拉框
        self.env_combo = QComboBox()
        for name, path in self.available_pythons:
            self.env_combo.addItem(name, path)
        self.env_combo.setCurrentIndex(0)
        self.env_combo.currentIndexChanged.connect(self._env_changed)
        env_section.addWidget(self.env_combo, 1)

        # 浏览按钮
        self.browse_env_btn = QPushButton("浏览...")
        self.browse_env_btn.clicked.connect(self._browse_python_env)
        env_section.addWidget(self.browse_env_btn)

        # 验证按钮
        self.verify_env_btn = QPushButton("验证")
        self.verify_env_btn.clicked.connect(self._verify_python_env)
        env_section.addWidget(self.verify_env_btn)

        self.main_layout.addLayout(env_section)

    def _create_script_list_section(self):
        """创建脚本列表区域"""
        list_splitter = QSplitter(Qt.Vertical)
        # 列表容器
        list_container = QWidget()
        list_layout = QVBoxLayout(list_container)
        list_layout.setContentsMargins(0, 0, 0, 0)

        # 标题
        title_label = QLabel("已选择的脚本")
        title_label.setStyleSheet("font-weight: bold;")
        list_layout.addWidget(title_label)

        # 脚本列表（使用自定义项）
        self.script_list_widget = QListWidget()
        self.script_list_widget.setSelectionMode(QListWidget.ExtendedSelection)
        list_layout.addWidget(self.script_list_widget)

        # 列表操作按钮
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)

        self.add_btn = QPushButton("添加脚本")
        self.add_btn.clicked.connect(self._add_script)
        btn_layout.addWidget(self.add_btn)

        self.remove_btn = QPushButton("移除脚本")
        self.remove_btn.clicked.connect(self._remove_script)
        btn_layout.addWidget(self.remove_btn)

        self.clear_btn = QPushButton("清空列表")
        self.clear_btn.clicked.connect(self._clear_script_list)
        btn_layout.addWidget(self.clear_btn)

        list_layout.addLayout(btn_layout)
        list_splitter.addWidget(list_container)

        self.main_layout.addWidget(list_splitter, 2)

    def _create_global_controls(self):
        """创建全局控制按钮"""
        controls_layout = QHBoxLayout()
        controls_layout.setSpacing(15)

        self.start_all_btn = QPushButton("全部启动")
        self.start_all_btn.setObjectName("start_btn")
        self.start_all_btn.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
        self.start_all_btn.clicked.connect(self._start_all_scripts)
        controls_layout.addWidget(self.start_all_btn)

        self.stop_all_btn = QPushButton("全部停止")
        self.stop_all_btn.setObjectName("stop_btn")
        self.stop_all_btn.setIcon(self.style().standardIcon(QStyle.SP_MediaStop))
        self.stop_all_btn.clicked.connect(self._stop_all_scripts)
        self.stop_all_btn.setEnabled(False)
        controls_layout.addWidget(self.stop_all_btn)

        controls_layout.addStretch(1)  # 弹性空间

        self.clear_output_btn = QPushButton("清空输出")
        self.clear_output_btn.setObjectName("clear_btn")
        self.clear_output_btn.clicked.connect(self._clear_all_outputs)
        controls_layout.addWidget(self.clear_output_btn)

        self.main_layout.addLayout(controls_layout)

    def _create_server_address_section(self):
        """创建服务器地址文本行区域和连接状态检测"""
        server_section = QHBoxLayout()
        server_label = QLabel("服务器地址:")
        server_label.setStyleSheet("font-weight: bold;")
        server_section.addWidget(server_label)

        self.server_address_line_edit = QLineEdit("服务器未启动")
        self.server_address_line_edit.setReadOnly(True)
        self.server_address_line_edit.setMaximumWidth(200)  # 设置服务器地址文本框最大宽度
        server_section.addWidget(self.server_address_line_edit)

        # 患者端连接状态
        self.patient_status_label = QLabel("患者端 未连接")
        self.patient_status_label.setObjectName("status-label")
        self.patient_status_label.setProperty("class", "status-label gray")
        server_section.addWidget(self.patient_status_label)

        # 医护端连接状态
        self.doctor_status_label = QLabel("医护端 未连接")
        self.doctor_status_label.setObjectName("status-label")
        self.doctor_status_label.setProperty("class", "status-label gray")
        server_section.addWidget(self.doctor_status_label)

        # 脑电采集端连接状态
        self.eeg_status_label = QLabel("脑电采集端 未连接")
        self.eeg_status_label.setObjectName("status-label")
        self.eeg_status_label.setProperty("class", "status-label gray")
        server_section.addWidget(self.eeg_status_label)

        self.main_layout.addLayout(server_section)

    def _create_output_section(self):
        """创建输出区域"""
        output_splitter = QSplitter(Qt.Vertical)

        # 输出容器
        output_container = QWidget()
        output_layout = QVBoxLayout(output_container)
        output_layout.setContentsMargins(0, 0, 0, 0)

        # 标题
        output_label = QLabel("执行输出")
        output_label.setStyleSheet("font-weight: bold;")
        output_layout.addWidget(output_label)

        # 输出标签页
        self.output_tabs = QTabWidget()
        self.output_tabs.setTabsClosable(True)
        self.output_tabs.tabCloseRequested.connect(self._close_output_tab)
        output_layout.addWidget(self.output_tabs)

        # 添加"全部输出"标签页
        self.all_output_text = QTextEdit()
        self.all_output_text.setReadOnly(True)
        self.all_output_text.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.output_tabs.addTab(self.all_output_text, "全部输出")

        output_splitter.addWidget(output_container)
        self.main_layout.addWidget(output_splitter, 2)

    def _env_changed(self, index):
        """环境选择变更"""
        self.selected_python_path = self.env_combo.currentData()

    def _browse_python_env(self):
        """浏览选择Python环境"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择Python解释器",
            "",
            "Python Executable (python.exe;python3.exe;python);;All Files (*)",
        )
        if file_path:
            version = self._get_python_version(file_path)
            env_name = f"自定义 ({version})"

            # 检查是否已存在
            for i in range(self.env_combo.count()):
                if self.env_combo.itemData(i) == file_path:
                    self.env_combo.setCurrentIndex(i)
                    return

            # 添加到下拉框
            self.env_combo.addItem(env_name, file_path)
            self.env_combo.setCurrentIndex(self.env_combo.count() - 1)

    def _verify_python_env(self):
        """验证Python环境"""
        python_path = self.selected_python_path
        if not python_path:
            QMessageBox.warning(self, "警告", "请选择Python环境")
            return

        version = self._get_python_version(python_path)
        QMessageBox.information(self, "环境信息", f"Python环境: {python_path}\n版本: {version}")

    def _load_default_scripts(self):
        """加载默认脚本"""
        for script_path, display_name in self.default_scripts.items():
            # 检查脚本是否存在
            if os.path.exists(script_path) and os.path.isfile(script_path):
                self._add_script_to_list(script_path, display_name)
            else:
                # 检查相对路径
                relative_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), script_path)
                if os.path.exists(relative_path) and os.path.isfile(relative_path):
                    self._add_script_to_list(relative_path, display_name)

    def _add_script(self):
        """添加脚本到列表"""
        file_paths, _ = QFileDialog.getOpenFileNames(
            self, "选择Python脚本", "", "Python Files (*.py);;All Files (*)"
        )

        for file_path in file_paths:
            if not file_path:
                continue

            if file_path in self.script_list:
                continue  # 跳过重复脚本

            if not os.path.isfile(file_path):
                QMessageBox.warning(self, "警告", f"无效文件: {file_path}")
                continue

            if not file_path.endswith(".py"):
                reply = QMessageBox.question(
                    self,
                    "确认",
                    f"[{os.path.basename(file_path)}] 不是.py文件，仍要添加？",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No,
                )
                if reply != QMessageBox.Yes:
                    continue

            display_name, ok = QInputDialog.getText(self, "输入脚本名称", "请输入脚本显示名称:")
            if ok and display_name:
                self._add_script_to_list(file_path, display_name)

    def _add_script_to_list(self, script_path, display_name):
        """将脚本添加到列表并创建自定义项"""
        self.script_list.append(script_path)
        self.script_display_names[script_path] = display_name

        # 创建列表项
        item = QListWidgetItem()
        item.setSizeHint(QSize(0, 50))  # 设置项高度

        # 创建自定义控件
        widget = ScriptItemWidget(script_path, display_name)
        widget.start_signal.connect(self._start_script)
        widget.stop_signal.connect(self._stop_script)
        widget.restart_signal.connect(self._restart_script)
        widget.change_path_signal.connect(self._change_script_path)  # 连接修改路径信号
        # 添加到列表
        self.script_list_widget.addItem(item)
        self.script_list_widget.setItemWidget(item, widget)
        self.script_widgets[script_path] = widget

        if display_name == "服务器端":
            self.main_script_path = script_path

    def _remove_script(self):
        """移除选中的脚本"""
        selected_items = self.script_list_widget.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "警告", "请先选择脚本")
            return

        for item in selected_items:
            # 获取对应控件
            widget = self.script_list_widget.itemWidget(item)
            if not widget:
                continue

            script_path = widget.script_path

            # 停止运行中的脚本
            if script_path in self.running_scripts:
                self.running_scripts[script_path].stop()
                self.running_scripts.pop(script_path)

            # 移除输出标签页
            self._remove_output_tab(script_path)

            # 从列表和字典中移除
            self.script_list.remove(script_path)
            self.script_display_names.pop(script_path, None)
            self.script_widgets.pop(script_path, None)
            self.script_outputs.pop(script_path, None)

            if script_path == self.main_script_path:
                self.main_script_path = None
                self.server_running = False
                self._set_connection_status_gray()
                self.server_address_line_edit.setText("服务器未启动")
                self.server_address_line_edit.setReadOnly(True)

            # 从UI移除
            row = self.script_list_widget.row(item)
            self.script_list_widget.takeItem(row)

    def _clear_script_list(self):
        """清空脚本列表"""
        if not self.script_list:
            return

        # 确认对话框
        reply = QMessageBox.question(
            self,
            "确认清空",
            "确定要清空所有脚本吗？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        # 停止所有运行中的脚本
        for script_path in list(self.running_scripts.keys()):
            self.running_scripts[script_path].stop()
            self.running_scripts.pop(script_path)
            self._remove_output_tab(script_path)

        if self.main_script_path:
            self.server_running = False
            self._set_connection_status_gray()
            self.server_address_line_edit.setText("服务器未启动")
            self.server_address_line_edit.setReadOnly(True)
            self.main_script_path = None

        # 清空列表
        self.script_list.clear()
        self.script_display_names.clear()
        self.script_widgets.clear()
        self.script_outputs.clear()
        self.script_list_widget.clear()

    def _start_all_scripts(self):
        """启动所有脚本"""
        if not self.script_list:
            QMessageBox.warning(self, "警告", "脚本列表为空")
            return

        # 验证环境
        self._verify_python_env()

        # 清空所有输出
        self._clear_all_outputs()

        # 启动所有脚本
        for script_path in self.script_list:
            if script_path not in self.running_scripts:
                self._start_script(script_path, self.script_display_names[script_path])

    def _stop_all_scripts(self):
        """停止所有脚本"""
        if not self.running_scripts:
            QMessageBox.information(self, "提示", "没有正在运行的脚本")
            return

        # 停止所有脚本
        for script_path, runner in list(self.running_scripts.items()):
            runner.stop()
            self.running_scripts.pop(script_path)

            # 更新状态
            if script_path in self.script_widgets:
                self.script_widgets[script_path].update_state("已停止")

            # 移除输出标签页
            self._remove_output_tab(script_path)

        if self.main_script_path:
            self.server_running = False
            self._set_connection_status_gray()
            self.server_address_line_edit.setText("服务器未启动")
            self.server_address_line_edit.setReadOnly(True)

        self.script_outputs.clear()
        self.all_output_text.append("\n===== 所有脚本已停止 =====")
        self.stop_all_btn.setEnabled(False)

    def _start_script(self, script_path, display_name):
        """启动单个脚本"""
        if script_path in self.running_scripts:
            return

        if script_path not in self.script_list:
            return

        # 检查文件是否存在
        if not os.path.exists(script_path) or not os.path.isfile(script_path):
            QMessageBox.warning(self, "错误", f"脚本不存在: {script_path}")
            return

        # 更新状态
        if script_path in self.script_widgets:
            self.script_widgets[script_path].update_state("运行中")

        if display_name == "服务器端":
            self.server_running = True

        # 创建输出标签页（如果不存在）
        if script_path not in self.script_outputs:
            output_text = QTextEdit()
            output_text.setReadOnly(True)
            output_text.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)

            # 添加标签页
            self.output_tabs.addTab(output_text, display_name)
            self.script_outputs[script_path] = output_text

            # 切换到新标签页
            index = self.output_tabs.indexOf(output_text)
            self.output_tabs.setCurrentIndex(index)

            # 初始化输出
            output_text.append(f"准备执行: {script_path}")
            output_text.append(f"使用环境: {self.selected_python_path}")

        # 创建并启动线程
        runner = ScriptRunner(script_path, self.selected_python_path)
        runner.update_signal.connect(self._update_output)
        runner.state_signal.connect(self._update_script_state)
        runner.finished_signal.connect(self._script_finished)
        runner.start()

        self.running_scripts[script_path] = runner
        self.all_output_text.append(f"已启动脚本: {display_name}")
        self.stop_all_btn.setEnabled(True)

    def _stop_script(self, script_path, display_name):
        """停止单个脚本"""
        if script_path not in self.running_scripts:
            return

        # 停止线程
        self.running_scripts[script_path].stop()
        self.running_scripts.pop(script_path)

        # 更新状态
        if script_path in self.script_widgets:
            self.script_widgets[script_path].update_state("已停止")

        # 移除输出标签页
        self._remove_output_tab(script_path)
        self.script_outputs.pop(script_path, None)

        if display_name == "服务器端":
            self.server_running = False
            self._set_connection_status_gray()
            self.server_address_line_edit.setText("服务器未启动")
            self.server_address_line_edit.setReadOnly(True)

        # 检查是否还有运行中的脚本
        if not self.running_scripts:
            self.stop_all_btn.setEnabled(False)
            self.all_output_text.append("\n===== 所有脚本已停止 =====")

    def _restart_script(self, script_path, display_name):
        """重启单个脚本"""
        self._stop_script(script_path, display_name)
        # 延迟一下再重启
        QApplication.processEvents()
        self._start_script(script_path, display_name)

    def _change_script_path(self, old_script_path, display_name):
        """修改脚本路径"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择新的Python脚本", "", "Python Files (*.py);;All Files (*)"
        )
        if file_path:
            if not os.path.isfile(file_path):
                QMessageBox.warning(self, "警告", f"无效文件: {file_path}")
                return

            # 停止正在运行的脚本
            if old_script_path in self.running_scripts:
                self.running_scripts[old_script_path].stop()
                self.running_scripts.pop(old_script_path)

            if old_script_path == self.main_script_path:
                self.server_running = False
                self._set_connection_status_gray()
                self.server_address_line_edit.setText("服务器未启动")
                self.server_address_line_edit.setReadOnly(True)
                self.main_script_path = file_path

            # 移除旧的输出标签页
            self._remove_output_tab(old_script_path)

            # 更新脚本列表和字典
            self.script_list.remove(old_script_path)
            self.script_list.append(file_path)
            self.script_display_names[file_path] = display_name
            self.script_display_names.pop(old_script_path, None)

            # 更新脚本控件
            widget = self.script_widgets[old_script_path]
            widget.script_path = file_path
            widget.name_label.setToolTip(file_path)
            self.script_widgets[file_path] = widget
            self.script_widgets.pop(old_script_path, None)

            # 重置状态
            widget.update_state("就绪")

    def _update_output(self, script_path, message):
        """更新输出文本"""
        # 更新单个脚本输出
        if script_path in self.script_outputs:
            self.script_outputs[script_path].append(message)
            # 自动滚动到底部
            cursor = self.script_outputs[script_path].textCursor()
            cursor.movePosition(QTextCursor.End)
            self.script_outputs[script_path].setTextCursor(cursor)

        # 更新全部输出
        display_name = self.script_display_names.get(script_path, os.path.basename(script_path))
        self.all_output_text.append(f"[{display_name}] {message}")
        # 自动滚动到底部
        cursor = self.all_output_text.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.all_output_text.setTextCursor(cursor)

        if script_path == self.main_script_path:
            # 患者端连接状态
            if "用户 patient_ui 已注册" in message:
                self._update_status_label("患者端 已连接", self.patient_status_label, "connected")
            elif "客户端断开: patient_ui" in message:
                self._update_status_label("患者端 已断开", self.patient_status_label, "disconnected")

            # 医护端连接状态
            if "用户 doctor 已注册" in message:
                self._update_status_label("医护端 已连接", self.doctor_status_label, "connected")
            elif "客户端断开: doctor" in message:
                self._update_status_label("医护端 已断开", self.doctor_status_label, "disconnected")

            # 脑电采集端连接状态
            if "用户 EEG 已注册" in message:
                self._update_status_label("脑电采集端 已连接", self.eeg_status_label, "connected")
            elif "客户端断开: EEG" in message:
                self._update_status_label("脑电采集端 已断开", self.eeg_status_label, "disconnected")

            if "端口状态异常" in message:
                self._update_status_label("脑电采集端 端口异常", self.eeg_status_label, "disconnected")
            elif "端口状态正常" in message:
                self._update_status_label("脑电采集端 数据正常", self.eeg_status_label, "connected")

            match = re.search(r"服务器启动在: (\d+\.\d+\.\d+\.\d+:\d+)", message)
            if match:
                server_address = match.group(1)
                self.server_address_line_edit.setText(server_address)
                self.server_address_line_edit.setReadOnly(False)
        else:
            if not self.server_running:
                self._set_connection_status_gray()

    def _update_status_label_style(self, label):
        """更新状态标签样式"""
        self.style().unpolish(label)
        self.style().polish(label)
        label.update()

    def _update_script_state(self, script_path, state):
        """更新脚本状态"""
        if script_path in self.script_widgets:
            self.script_widgets[script_path].update_state(state)

    def _script_finished(self, script_path, success):
        """处理脚本完成事件"""
        if script_path in self.running_scripts:
            self.running_scripts.pop(script_path)

            # 更新状态
            if script_path in self.script_widgets:
                state = "已完成" if success else "已失败"
                self.script_widgets[script_path].update_state(state)

            if script_path == self.main_script_path:
                self.server_running = False
                self._set_connection_status_gray()
                self.server_address_line_edit.setText("服务器未启动")
                self.server_address_line_edit.setReadOnly(True)

            # 检查是否还有运行中的脚本
            if not self.running_scripts:
                self.stop_all_btn.setEnabled(False)
                self.all_output_text.append("\n===== 所有脚本执行完成 =====")

    def _remove_output_tab(self, script_path):
        """移除脚本对应的输出标签页"""
        display_name = self.script_display_names.get(script_path, os.path.basename(script_path))
        for i in range(self.output_tabs.count()):
            if self.output_tabs.tabText(i) == display_name:
                self.output_tabs.removeTab(i)
                break

    def _close_output_tab(self, index):
        """关闭输出标签页"""
        if self.output_tabs.tabText(index) == "全部输出":
            return

        # 找到对应的脚本路径
        tab_name = self.output_tabs.tabText(index)
        script_path = None
        for path, name in self.script_display_names.items():
            if name == tab_name:
                script_path = path
                break

        if script_path:
            # 如果脚本在运行，提示停止
            if script_path in self.running_scripts:
                reply = QMessageBox.question(
                    self,
                    "确认关闭",
                    f"脚本 [{tab_name}] 正在运行，关闭标签页将停止脚本，是否继续？",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No,
                )
                if reply != QMessageBox.Yes:
                    return

                # 停止脚本
                self._stop_script(script_path, tab_name)

            # 移除标签页和映射
            self.output_tabs.removeTab(index)
            self.script_outputs.pop(script_path, None)

    def _clear_all_outputs(self):
        """清空所有输出"""
        self.all_output_text.clear()
        for output_text in self.script_outputs.values():
            output_text.clear()

    def _set_connection_status_gray(self):
        """设置连接状态为灰色"""
        self._update_status_label("患者端 未连接", self.patient_status_label, "gray")
        self._update_status_label("医护端 未连接", self.doctor_status_label, "gray")
        self._update_status_label("脑电采集端 未连接", self.eeg_status_label, "gray")

    def _update_status_label(self, text, label, status_class):
        """更新状态标签文本和样式"""
        label.setText(text)
        label.setProperty("class", f"status-label {status_class}")
        self._update_status_label_style(label)

    def closeEvent(self, event):
        """关闭窗口事件"""
        if self.running_scripts:
            reply = QMessageBox.question(
                self,
                "确认关闭",
                f"有 {len(self.running_scripts)} 个脚本正在运行，关闭将终止所有脚本，是否继续？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if reply == QMessageBox.Yes:
                # 停止所有脚本
                self._stop_all_scripts()
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")  # 统一跨平台样式
    window = ScriptLauncherApp()
    window.show()
    sys.exit(app.exec_())
