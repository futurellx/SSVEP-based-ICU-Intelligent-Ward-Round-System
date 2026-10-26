import glob
import io
import json
import os
import time
from functools import partial
from queue import Queue
import pyqtgraph as pg
import socketio
from PyQt5.QtGui import *
from PyQt5.QtCore import *
from PyQt5.QtWidgets import *
from PyQt5.QtCore import Qt, QRect
from PyQt5.QtGui import QFont, QPixmap, QPainter, QBrush, QColor
from PyQt5.QtWidgets import QFrame, QApplication, QMenuBar, QAction, QVBoxLayout, QDesktopWidget, QTextEdit, \
    QHBoxLayout, QPushButton, QSizePolicy, QLabel, QWidget, QGridLayout, QComboBox, QLineEdit, QSpacerItem, QWidget
import sys
import threading
from datetime import datetime, date
import numpy as np
from collections import deque
from matplotlib.animation import FuncAnimation
import matplotlib.pyplot as plt
import csv
import requests
# from psychopy.gui import QtWidgets
from ratelimiter import RateLimiter
from scipy import signal
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
import itertools
import matplotlib.lines as line
from threading import Thread
from multiprocessing import Process, Pipe
from scipy.fftpack import fft
from scipy.signal import hilbert
current_dir = os.path.dirname(os.path.abspath(__file__))
# 获取上级目录
parent_dir = os.path.dirname(current_dir)
# 将上级目录添加到 sys.path
sys.path.insert(0, parent_dir)
from wordTexts import WordTextS
from 放大器13 import Ui_MainWindow
from pyqtgraph.Qt import QtCore
import select
import serial
import serial.tools.list_ports
from functools import partial
global IMPEDANCE_VALUE, is_Admin

def convert_to_custom_format(time_str):
    # 移除输入字符串两端的空白字符
    time_str = time_str.strip()

    # 将yyyy/m/d h:mm:ss.000时间转换为XXXXX.XXXXXXXXXX的时间戳
    dt = datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S.%f')
    # 计算距离1900-1-1的天数
    days_since_1900 = (dt.date() - date(1900, 1, 1)).days + 2
    # 计算当天的毫秒数
    milliseconds_since_midnight = dt.hour * 3600 * 1000 + dt.minute * 60 * 1000 + dt.second * 1000 + dt.microsecond // 1000
    # 计算全天的毫秒数
    milliseconds_in_day = 24 * 3600 * 1000
    # 计算毫秒数占全天的比值
    ratio_of_day = milliseconds_since_midnight / milliseconds_in_day
    # 格式化输出
    formatted_output = f"{days_since_1900}.{ratio_of_day:.10f}".replace('.0.', '.')
    return formatted_output


def get_path(base_name):
    if getattr(sys, 'frozen', False):
        # 如果是打包后的可执行文件，获取可执行文件的目录
        application_path = os.path.dirname(sys.executable)
    else:
        # 如果是在开发环境中，获取脚本文件的目录
        application_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(application_path, base_name)


# with open('./Experimental_paradigm/configure.json', 'r') as f1:
configure_json_path = get_path('Experimental_paradigm/configure.json')
with open(configure_json_path, 'r') as f1:
    # 从文件对象中读取JSON数据，并反序列化为Python对象
    init_configure = json.load(f1)
    is_Admin = init_configure['Admin']
    # IMPEDANCE_VALUE = [250 for i in range(16)] #各阻抗值，默认250K欧姆
    IMPEDANCE_VALUE = [250 for i in range(32)]
    allAttributes = ['colorOnBegin', 'colorOnEnd', 'colorOffBegin', 'colorOffEnd', 'colorBorderIn', 'colorBorderOut',
                     'radiusBorderOut', 'radiusBorderIn', 'radiusCircle']
    allDefaultVal = [QColor(0, 240, 0), QColor(0, 160, 0), QColor(0, 68, 0), QColor(0, 28, 0), QColor(140, 140, 140),
                     QColor(100, 100, 100),
                     500, 450, 400]
    allLabelNames = [u'灯亮圆心颜色：', u'灯亮边缘颜色：', u'灯灭圆心颜色：', u'灯灭边缘颜色：', u'边框内测颜色：',
                     u'边框外侧颜色：',
                     u'边框外侧半径：', u'边框内侧半径：', u'中间圆灯半径：']


class SerialClass:
    _instance = None
    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(SerialClass, cls).__new__(cls, *args, **kwargs)
            cls._instance.client = client
            # 自动获取端口号
            port_name = None
            for port in serial.tools.list_ports.comports():
                if "USB-Enhanced-SERIAL CH343" in port.description or "USB-SERIAL CH340K" in port.description:
                    port_name = port.device
                    break
            try:
                if port_name is None:
                    print("Could not find USB-Enhanced-SERIAL CH343 port or USB-SERIAL CH340K.")
                    # 获取 MyMainForm 实例并发送 False 到服务器
                    if hasattr(cls._instance, 'client'):
                        cls._instance.client.send_to_server('port_status', {'status': False})
            finally:
                print(f"Using port: {port_name}")
            # 打开串口
            try:
                cls._instance.ser = serial.Serial(
                    port=port_name,
                    baudrate=921600,
                    # baudrate=460800,
                    bytesize=serial.EIGHTBITS,  # 数据位，16，32导是8
                    parity=serial.PARITY_NONE,  # 校验位,16，32导是NONE
                    stopbits=serial.STOPBITS_ONE  # 停止位，16,32导是1
                )
            except Exception as e:
                print(f"Failed to open serial port: {e}")
                if hasattr(cls._instance, 'client'):
                    cls._instance.client.send_to_server('port_status', {'status': False})
            # 设置缓冲区大小,根据要发送的字节串大小设置，否则数据会打乱
            # cls._instance.ser.set_buffer_size(rx_size=14250, tx_size=14250)   #设置串口的接收和发送缓冲区大小，57*250（采样率）
            cls._instance.ser.set_buffer_size(rx_size=1050, tx_size=1050)
        return cls._instance

# def convert_to_custom_format(time_str):
#     # 解析时间字符串
#     dt = datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S.%f')
#     # 计算距离1900-1-1的天数
#     days_since_1900 = (dt.date() - date(1900, 1, 1)).days
#     # 计算当天的毫秒数
#     milliseconds_since_midnight = dt.hour * 3600 * 1000 + dt.minute * 60 * 1000 + dt.second * 1000 + dt.microsecond // 1000
#     # 计算全天的毫秒数
#     milliseconds_in_day = 24 * 3600 * 1000
#     # 计算毫秒数占全天的比值
#     ratio_of_day = milliseconds_since_midnight / milliseconds_in_day
#     # 格式化输出
#     formatted_output = f"{days_since_1900}.{ratio_of_day:.10f}".replace('.0.', '.')
#     return formatted_output

class MyMainForm(QMainWindow, Ui_MainWindow):
    def __init__(self, client, parent=None):
        super(QMainWindow, self).__init__(parent)
        self.setupUi(self)  # 调用 Ui_MainWindow 类（可能是由Qt Designer生成的UI类）中的 setupUi 方法，来初始化并设置GUI的界面布局。
        self.qtWin_edit()  # 对页面部分进行编辑
        self.client = client
        try:
            self.sc = SerialClass()  # 创建一个 SerialClass 的实例sc，这个类是用于串口通信的
            self.sc.client = self.client
        finally:
            pass
        self.b_notch, self.a_notch = signal.iirnotch(50 / (250 / 2), 30)  # 50Hz工频陷波，256是采样率，30是质量因子
        self.b_design = signal.firwin(65, [8 / (250 / 2), 40 / (250 / 2)], pass_zero=False)  # 设计8-30Hz带通滤波器
        # self.b_design, self.a_design = signal.butter(5, [2 / (250 / 2), 45 / (250 / 2)], 'bandpass')
        self.b_impedance = signal.firwin(65, [30 / (250 / 2), 33 / (250 / 2)], pass_zero=False)  # 阻抗检测时的带通滤波器
        self.eeg = np.zeros((32, 1000))  # 32导
        # self.all_channels = ['Fp1','Fp2',' F7',' F3',' Fz',' F4',' F8','FT7','FC3','FCz','FC4','FT8',' A1',' T7',' C3',' Cz',' C4',' T8',' A2','TP7','CP3','CPz','CP4','TP8',' P7',' P3',' Pz',' P4',' P8',' O1',' Oz',' O2']
        # self.all_channels = ['Fp1', 'Fp2', 'F7', 'F3', 'Fz', 'F4', 'F8', 'FT7', 'FC3', 'FCz', 'FC4', 'FT8', 'T7', 'C3',
        #                      'Cz', 'C4', 'T8', 'TP7', 'CP3', 'CPz', 'CP4', 'TP8', 'P7', 'P3', 'Pz', 'P4', 'P8', 'O1',
        #                      'Oz', 'O2', 'HEOR', 'VEOU']
        # 对应自研放大器 黑色电极帽
        # self.all_channels = ['Fp1', 'Fp2', 'F7', 'F3', 'Fz', 'F4', 'F8', 'FT7', 'FC3', 'FCz', 'FC4', 'FT8', 'T3', 'C3',
        #                      'Cz', 'C4', 'T4', 'TP7', 'CP3', 'CPz', 'CP4', 'TP8', 'T5', 'P3', 'Pz', 'P4', 'T6', 'O1',
        #                      'Oz', 'O2', 'HEOR', 'VEOU']
        self.all_channels = ['T5', 'TP7', 'O1', 'P3', 'CP3', 'C3', 'CZ', 'CPZ', 'PZ', 'OZ', 'C4', 'CP4', 'P4', 'O2',
                             'TP8', 'T6', 'T3', 'FT7',
                             'F7', 'FC3', 'F3', 'FP1', 'FZ', 'FCZ', 'FP2', 'F4', 'FC4', 'HEOR', 'F8', 'FT8', 'T4',
                             'VEOU']  # 放大器输出导联
        # self.enabled_Channels = [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1] #32导
        self.enabled_Channels = [1, 0, 1, 1, 0, 0, 0, 1, 1, 1, 0, 0, 1, 1, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
                                 0, 0, 0]  # 32导中的9导
        self.sc_isopen = False  # 手动设置是否接收来自串口通信的数据，默认关闭
        self.isAcquition = False  # 采集状态，False为关闭，True为开启，默认关闭
        self.impedance_detection = 0  # 阻抗检测是否开启，0为关闭，1为开启，默认关闭
        self.isDataRecording = 0  # 数据记录开关，0为关闭，1为开启，默认关闭
        self.isSendData = 0  # 是否发送数据，0为关闭，1为开启，默认关闭
        self.timer = QtCore.QTimer()  # 定时器，刷新脑电图
        self.impedanceTimer = QtCore.QTimer()  # 定时器，刷新阻抗显示
        self.plot_EEG()  # 画脑电图
        self.plot_FFT()  # 画频谱图
        self.electrode_buttons = {}
        self.checkedchannels = []
        self.buttons_to_process = self.all_channels
        self.setup_electrode_buttons()
        self.discard_initial_second = True  # 标记是否需要丢弃初始一秒的数据

    def trigger_message(self, target, message):
        # 模拟来自不同线程的调用
        threading.Thread(target=self.client.async_send,
                         args=(target, message)).start()

    def sever_message(self, event_name, message):
        # 模拟来自不同线程的调用
        threading.Thread(target=self.client.send_to_server,
                         args=(event_name, message)).start()

    def qtWin_edit(self):  # 对界面的部分编辑
        # -----日志输出------#
        self.logTextEdit.setReadOnly(True)  # 只读类型
        # font = QFont("Source Code Pro", 12)  # 使用 Arial 字体，字号为 12
        self.fileButton = QPushButton('文件')  # 创建多个 QPushButton 控件，包括 '文件'、'开始采集'、'显示阻抗' 和 '记录数据
        self.stackedWidget.setCurrentWidget(self.eeg_page)
        is_Admin = 1
        if is_Admin:  # 这个is_Admin在最后，控制 recordButton（记录数据）按钮的可见性。如果是管理员，则按钮可见，否则不可见
            self.recordButton.setVisible(True)
        else:
            self.recordButton.setVisible(False)
        self.recordButton.setEnabled(False)  #初始化时，'记录数据' 和 '建立连接' 按钮被禁用
        self.sendDataButton.setEnabled(False)
        self.fileButton.clicked.connect(self.file_option)
        self.startButton.clicked.connect(self.start_acquisition)
        self.recordButton.clicked.connect(self.data_record)
        self.sendDataButton.clicked.connect(self.send_data)
        self.markerButton.setVisible(False)
        self.impedanceButton.clicked.connect(self.impedance_state)
        self.paradimSelect = self.dropDownBox()  # 范式选择下拉框
        self.paradimSelect.setCurrentText('SSVEP-9导联')  # 并设置其当前文本为 'SSVEP-9导联'
        self.horizontalLayout.addWidget(self.paradimSelect)

    def setup_electrode_buttons(self):
        for button_name in self.all_channels:
            button = getattr(self, button_name, None)
            if button:
                button.setCheckable(True)
                self.electrode_buttons[button_name] = button
                button.clicked.connect(
                    lambda checked, name=button_name: self.on_electrode_clicked(name, checked)
                )

    def on_electrode_clicked(self, electrode_name, checked):
        if checked:
            # 选中时显示绿电极
            self.electrode_buttons[electrode_name].setStyleSheet(
                "border-image: url(:/imgs/imgs/绿电极.png);\n"
                "font: 10pt \"Arial\";"
            )
            if electrode_name not in self.checkedchannels:
                self.checkedchannels.append(electrode_name)
        else:
            # 未选中时显示红电极
            self.electrode_buttons[electrode_name].setStyleSheet(
                "border-image: url(:/imgs/imgs/红电极.png);\n"
                "font: 10pt \"Arial\";"
            )
            if electrode_name in self.checkedchannels:
                self.checkedchannels.remove(electrode_name)

        # 更新按钮状态
        self.update_button_states()

    def file_option(self):  # 对应fileButton
        self.log_edit('文件操作')

    def start_acquisition(self):  # 对应startButton(开始采集)
        if self.sc_isopen == False:  # 手动设置是否接收来自串口通信的数据，默认关闭
            self.stackedWidget.setCurrentWidget(self.eeg_page)
            if not self.sc.ser.isOpen():
                self.sc.ser.open()
            self.eeg = np.empty(shape=[32, 0])
            self.allEEG = np.empty(shape=[32, 0])
            self.sc_isopen = True  #将 self.sc_isopen 设置为 True，表示开始采集
            self.sc.ser.write(b'B')  # 向串口发送字节 b'B'，可能是告诉数据采集设备开始采集的命令
            self.startButton.setText('停止采集')  #修改 startButton 的文本为“停止采集”
            self.startButton.setStyleSheet('background-color: red;')  #并改变其背景颜色为红色，以反映当前状态
            self.paradimSelect.setEnabled(False) #设置范式不可改变
            self.impedanceButton.setEnabled(False) #设置阻抗不可显示
            self.log_edit('开始采集')  #在日志编辑框（log_edit）中添加“开始采集”的记录
            self.recordButton.setEnabled(True) #设置记录数据按钮可用
            self.sendDataButton.setEnabled(True)
            self.impedanceButton.setEnabled(False)
        elif self.sc_isopen == True:
            if not self.sc.ser.isOpen():
                self.sc.ser.open()
            # self.timer.stop()
            self.sc_isopen = False  # 将 self.sc_isopen 设置为 False，表示停止采集
            self.sc.ser.write(b's')  # 停止采集  ，向串口发送字节 b's'，可能是告诉数据采集设备停止采集的命令
            self.startButton.setText('开始采集')  # 修改 startButton 的文本为“开始采集”，并清除其背景颜色设置
            self.startButton.setStyleSheet('')
            self.paradimSelect.setEnabled(True)  # 启用 paradimSelect，允许在停止采集后更改设置
            self.impedanceButton.setEnabled(True)  # 设置阻抗可显示
            self.log_edit('停止采集')
            for j in range(len(self.eeg_lines)):
                self.eeg_lines[j].setPen(color='b')
            self.recordButton.setEnabled(False)  # 设置记录数据按钮不可用
            self.sendDataButton.setEnabled(False)  # 在停止采集后，不应再进行数据记录和发送
            # 新增停止记录和发送的控制
            if self.isDataRecording == 1:
                self.isDataRecording = 0
                self.log_edit('停止记录数据')
                self.recordButton.setText('开始记录')
                self.recordButton.setStyleSheet('')
            if self.isSendData == 1:
                self.isSendData = 0
                self.log_edit('停止发送数据')
                self.sendDataButton.setText('发送数据')
                self.sendDataButton.setStyleSheet('')

    def impedance_state(self):  # 对应impedanceButton，阻抗显示
        if self.impedance_detection == 0:  # 当前未进行阻抗检测 #阻抗检测是否开启，0为关闭，1为开启，默认关闭
            self.impedanceTimer.timeout.connect(self.calculate_impedance)
            self.stackedWidget.setCurrentWidget(self.impedance_page)
            self.impedanceTimer.start(500)
            self.show_impedance()  # 调用 self.show_impedance() 方法，用于在GUI上显示阻抗值
            self.impedance_detection = 1  # 将 self.impedance_detection 设置为 1，表示开始阻抗检测
            self.startButton.setEnabled(False)
            self.paradimSelect.setEnabled(False)  # 设置范式不可改变
            if not self.sc.ser.isOpen():
                self.sc.ser.open()
            self.sc.ser.write(b'STT') #测量阻抗 #向串口发送字节 b'Set-T'，可能是命令数据采集设备开始测量阻抗
            self.impedanceButton.setText('停止检测阻抗')  #修改 阻抗检测按钮文本为“停止”，以反映当前状态
            self.log_edit('开始检测阻抗')
        elif self.impedance_detection == 1:  #当前正在进行阻抗检测
            self.stackedWidget.setCurrentWidget(self.eeg_page)
            self.impedanceTimer.stop()
            self.show_impedance()  # 再次调用 self.show_impedance() 方法，可能是为了更新或确认阻抗值
            self.impedance_detection = 0  # 将 self.impedance_detection 设置为 0，表示停止阻抗检测
            if not self.sc.ser.isOpen():
                self.sc.ser.open()
            self.sc.ser.write(b'SCC')  #向串口发送字节 b'Set-C'，命令数据采集设备停止测量阻抗
            self.impedanceButton.setText('显示阻抗')  #修改 impedanceButton 的文本为“阻抗”，以反映当前状态
            self.log_edit('停止检测阻抗')
            self.startButton.setEnabled(True)
            self.paradimSelect.setEnabled(True)  # 设置范式不可改变

    def data_record(self):  # 对应recordButton
        if self.isDataRecording == 0:
            self.log_edit('开始记录数据')
            self.recordButton.setText('停止记录')
            self.recordButton.setStyleSheet('background-color: red;')
            self.isDataRecording = 1
            now = datetime.now()  # 获取当前时间，并将其格式化为字符串，存储在 self.time_str 中，为了后续用于文件名或日志记录
            # 将时间转换为字符串
            self.time_str = now.strftime("%Y-%m-%d-%H.%M.%S")
        elif self.isDataRecording == 1:
            self.log_edit('停止记录数据')
            self.recordButton.setText('开始记录')
            self.recordButton.setStyleSheet('')  # 清除 recordButton 的背景颜色设置，恢复为默认颜色
            self.isDataRecording = 0  # 将 self.isDataRecording 设置为 0，表示停止记录数据

    def send_data(self):  # 对应sendDataButton   # 建立连接
        self.dataBuffer = np.zeros((sum(self.enabled_Channels), 50))  # 只发0.2s的数据，最小单位
        self.send_index = 0  # 用于计数，每次收到的数据为(Channel，10)，采样率为250，因此self.send_index==25时为1秒数据
        if self.isSendData == 0:
            self.log_edit('开始发送数据')
            self.sendDataButton.setText('停止发送')
            self.sendDataButton.setStyleSheet('background-color: red;')
            self.isSendData = 1
            self.sever_message('port_status', {'status': True})
        elif self.isSendData == 1:
            self.log_edit('停止发送数据')
            self.sendDataButton.setText('发送数据')
            self.sendDataButton.setStyleSheet('')
            self.isSendData = 0
            self.sever_message('port_status', {'status': False})

    # def write_data(self, data):  # 记录带标签的脑电数据  #将带标签的脑电数据写入CSV文件
    #     with open('./Recorded_Data/{}.csv'.format(self.time_str), 'a', newline='') as file:
    #         writer = csv.writer(file)  # 通过 csv.writer(file) 创建一个CSV写入器对象，这个对象允许你将数据以CSV格式写入文件
    #         writer.writerows(data)

    def write_data(self, data):  # 加时间戳版本
        # 获取当前时间戳
        now = datetime.now()
        current_ms = int(now.timestamp() * 1000)

        # 打开文件，以追加模式写入数据
        with open('./Recorded_Data/{}.csv'.format(self.time_str), 'a', newline='', encoding='utf-8') as file:
            writer = csv.writer(file, quoting=csv.QUOTE_NONE)

            # 遍历数据并写入文件
            for row in data:
                current_datetime = datetime.fromtimestamp(current_ms / 1000)
                formatted_date = current_datetime.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                transfer_time = convert_to_custom_format(formatted_date)
                # print(f"transfer_time: {transfer_time}, row: {row}")
                writer.writerow([transfer_time] + list(row))
                current_ms += 4


    def log_edit(self, message):  # 图形用户界面（GUI）中的 QTextEdit 组件中添加日志消息，并确保 QTextEdit 的滚动条滚动到底部，以便用户可以立即看到新添加的消息
        now = datetime.now()  # 获取当前时间，并将其格式化为字符串，存储在 self.time_str 中，为了后续用于文件名或日志记录
        # 将时间转换为字符串
        time_str = now.strftime("%Y-%m-%d-%H.%M.%S")
        self.logTextEdit.append(str(message) + '   ' + time_str)  # 将消息添加到 QTextEdit 组件的末尾
        # 将 QTextEdit 滚动到底部
        cursor = self.logTextEdit.textCursor()  # 创建一个文本光标对象 cursor，它代表 QTextEdit 组件中的当前文本光标位置
        cursor.movePosition(cursor.End)  # 使用 cursor.movePosition(cursor.End) 将光标移动到 QTextEdit 组件的文本末尾
        self.logTextEdit.setTextCursor(
            cursor)  # 通过 self.logTextEdit.setTextCursor(cursor) 将 QTextEdit 组件的文本光标设置为新位置（即文本的末尾）

    def get_message(self, connLeft):  # connLeft 是一个参数，预期是一个网络连接对象，可能是一个套接字对象
        while True:  # 这意味着根据从 connLeft 接收到的消息，程序会向串行端口发送相应的命令或数据
            message = connLeft.recv()  # 从 connLeft 连接中接收消息。recv 方法通常用于从套接字接收数据
            if message['order'] != None:  # 假设 connLeft.recv() 返回的是一个字典，其中包含一个 'order' 键
                order = message['order']  # 从消息中提取 'order' 字段的值，并将其存储在 order 变量中
                if not self.sc.ser.isOpen():
                    self.sc.ser.open()
                print('收到消息：', message['order'])
                self.sc.ser.write(order)  # 使用 self.sc.ser 对象（可能是一个串行端口对象）的 write 方法将 order 写入串行端口

    def receive_data(self):  # 是接收串行端口（可能是EEG设备）的数据，对其进行一系列处理，并可能将数据发送到Flask应用程序或保存到文件中
        try:
            while True:
                # 检查输入缓冲区中是否有数据
                if self.sc.ser.in_waiting > 0:
                    # 读取并打印接收到的数据
                    if self.discard_initial_second:
                        # 读取一秒钟的数据并丢弃
                        _ = self.sc.ser.read(size=1050)
                        self.discard_initial_second = False
                        continue
                    data = self.sc.ser.read(size=1050)  # 32导 105*250
                    myeeg, eegWithLabel = self.bytes2data(data)  # 从串行端口读取数据，并调用 bytes2data 方法将数据转换为适当的格式
                    channelsIndex = [i for i, val in enumerate(self.enabled_Channels) if val == 1]  # 创建一个列表，其中包含所有启用的通道索引
                    myeeg = myeeg[np.array(channelsIndex)]
                    # # 确保 channelsIndex 是一维数组
                    # channelsIndex = np.array(channelsIndex)
                    # myeeg = myeeg[channelsIndex]
                    if self.isSendData:  # 发送数据到Flask应用程序（如果启用）
                        self.dataBuffer[:, self.send_index * 10:self.send_index * 10 + 10] = myeeg
                        self.send_index += 1
                        if self.send_index == 5:  # 只发0.2s的数据，10*5 = 50个采样点
                            try:
                                last_row = self.dataBuffer[-1, :]
                                sendData = np.vstack([self.dataBuffer, last_row])
                                data = {"eeg": sendData.T.tolist()}
                                self.sever_message("eeg", data)
                            except:
                                print('服务器未开启！')
                            self.send_index = 0
                    channelsIndex.append(-1) #读取最后一列标签位
                    # eegWithLabel = eegWithLabel[:,np.array(channelsIndex)]
                    eegWithLabel = np.array(eegWithLabel)
                    eegWithLabel = eegWithLabel[:, np.array(channelsIndex)]
                    if self.isDataRecording:
                        self.write_data(eegWithLabel)

                    if self.eeg.shape[0] == sum(self.enabled_Channels):
                        if self.eeg.shape[1] < 1000:
                            self.eeg = np.hstack((self.eeg, myeeg))
                        else:
                            self.eeg[:, :-10] = self.eeg[:, 10:]
                            self.eeg[:, -10:] = myeeg
                    else:
                        self.eeg = np.empty(shape=[sum(self.enabled_Channels), 0])

        except KeyboardInterrupt:
            # 当用户按下Ctrl+C时，退出循环
            pass

        finally:
            self.sever_message('port_status', {'status': False})
            print('发生错误')
            # 关闭串口
            self.sc.ser.close()

    def bytes2data(self, byte_string):  # 是一个将字节流转换为EEG（脑电图）数据的函数
        eegWithLabel = []  # 初始化一个空列表，用于存储转换后的EEG数据和标签。
        if len(byte_string) % 105 == 0:  # 32导有105个字节
            byte_string = [byte_string[i:i + 105] for i in range(0, len(byte_string), 105)]
            for index, byte_frame in enumerate(byte_string):
                byte_head = byte_frame[0]  # 帧头
                # byte_loff = byte_frame[-5:-3] #LOFF导联检测，2字节 16位，“1”代表失联，“0”代表导联,-5~-4
                byte_loff = byte_frame[-6:-2]  # 32导,-6~-3
                # 转换为二进制数，
                bin_loff = ''.join(f'{i:08b}' for i in byte_loff)  # 将LOFF转换为二进制字符串
                bin_loff = bin_loff[:8][::-1] + bin_loff[8:16][::-1] + bin_loff[16:24][::-1] + bin_loff[24:][::-1]
                bin_loff = [bin_loff[j] for j in [i for i, val in enumerate(self.enabled_Channels) if val == 1]]
                # print('导联情况：',bin_loff)
                self.invalid_channels = [i for i, letter in enumerate(bin_loff) if letter == '1']
                byte_label = byte_frame[-2]  # 标签，16、32一样
                byte_end = byte_frame[-1]  # 帧尾，16、32一样
                byte_eeg = byte_frame[3:-6]  # 去除帧头（0）、序号（1）、备用空间（-7：-1）、帧尾（-1）
                if len(byte_eeg) % 3 == 0 and byte_head == 187 and byte_end == 10:  # byte_head-b'\xbb',byte_end-b'\x0a'，#16,32导帧头和帧尾标志一样
                    byte_eeg = [byte_eeg[j:j + 3] for j in
                                range(0, len(byte_eeg), 3)]  # 每三个字节表示一个通道的数据，将数据分成3字节一组
                    eeg_frame = [int.from_bytes(chdata_i, byteorder='big', signed=True) for chdata_i in
                                 byte_eeg]  # 按大端字节序的有符号整型转换为十进制数
                    eegWithLabel.extend(eeg_frame)
                    eegWithLabel.append(byte_label)
                else:
                    print("数据长度错误", len(byte_eeg), byte_head, byte_end)
            try:
                eegWithLabel = np.array(eegWithLabel, dtype=np.float64).reshape((10, 33))
                eegWithLabel[:, :32] *= (-0.022351744455307063)
                eeg = eegWithLabel[:, :32]
                eeg = np.transpose(eeg, (1, 0))
            except Exception as e:
                print('异常 :', e)
                eeg = np.zeros((32, 10))
                if not self.sc.ser.isOpen():
                    self.sc.ser.open()
                self.sc.ser.write(b's')  # 引发异常，停止采集
        else:
            self.log_edit("接收数据有误")
            print("接收数据有误")
            exit()
        return eeg, eegWithLabel

    def spec_init(self):  # 频谱初始图
        # self.fft_ax.set_xticks(np.arange(0, (250 / 10)+1, 1))  # 设置横坐标的刻度为0-125，每25画一个刻度
        self.fft_ax.set_xticks(np.arange(0, 60 + 1, 5))  # 设置横坐标的刻度为0-125，每25画一个刻度
        for line in self.fft_line:
            self.fft_ax.add_line(line)
        return self.fft_line

    def spec_update(self):  # 频谱图更新
        if len(self.eeg) != 0:
            tmpEEG = self.eeg[self.fft_index, :]
            if self.sc_isopen == False:
                tmpEEG = np.zeros((1000,))
            tmpEEG = signal.lfilter(self.b_notch, self.a_notch, tmpEEG)  # 工频陷波
            if tmpEEG.shape[0] > 500:
                tmpEEG = signal.filtfilt(self.b_design, 1, tmpEEG)  # 带通滤波
                # tmpEEG = signal.filtfilt(self.b_design, self.a_design, tmpEEG) #巴特沃斯带通滤波
            if tmpEEG.size > 0:  # 添加判断条件，确保tmpEEG不是空数组
                mean_value = np.mean(tmpEEG)
                tmpEEG = tmpEEG - mean_value
                y = abs(fft(tmpEEG, 1000))
                # 计算信号的包络
                envelope = np.abs(hilbert(y))
                self.fft_line.setData(np.arange(240), envelope[:240])
        return self.fft_line

    def update_plot(self):
        tmpEEG = self.eeg
        if self.sc_isopen == False:
            tmpEEG = np.zeros((sum(self.enabled_Channels), 1000))  # 32导
        tmpEEG = signal.lfilter(self.b_notch, self.a_notch, tmpEEG)  # 工频陷波
        if tmpEEG.shape[1] > 500:
            tmpEEG = signal.filtfilt(self.b_design, 1, tmpEEG)  # 带通滤波
            mean_x = np.mean(tmpEEG, axis=1, keepdims=True)
            tmpEEG = tmpEEG - mean_x
            for i, curve in enumerate(self.eeg_lines):
                curve.setData(tmpEEG[i, 100:])
                index = [idx for idx, val in enumerate(self.enabled_Channels) if val == 1][i]
                if index < len(IMPEDANCE_VALUE):
                    # 检查 tmpEEG 中是否有小于- 20000 的值
                    if np.any(self.eeg[i, 100:] < -20000):
                        curve.setPen(color='r')
                    else:
                        curve.setPen(color='b')
                    curve.update()
                else:
                    print(f"Index {index} out of range for IMPEDANCE_VALUE")

    def plot_EEG(self):
        # 清空原有布局
        self.clear_layout(self.wavePlotLay)
        # 创建新的波形曲线
        plot_widgets = [myCurves(self.all_channels[idx]).create_curve()
                        for idx, val in enumerate(self.enabled_Channels) if val == 1]
        self.eeg_lines = []
        # 将波形添加到eeg_page的布局
        for index, plot_widget in enumerate(plot_widgets):
            self.wavePlotLay.addLayout(plot_widget[0], stretch=1)
            self.eeg_lines.append(plot_widget[1])
        # 设置定时器更新
        self.timer.timeout.connect(self.update_plot)
        self.timer.start(20)

    def plot_FFT(self):  # 创建一个图形界面用于展示FFT（快速傅里叶变换）的结果，并启动一个动画来不断更新这个FFT图形
        self.fft_index = 0
        self.fft_combo.addItems(self.all_channels)
        self.fft_combo.currentIndexChanged.connect(lambda index: setattr(self, 'fft_index', index))
        self.fft_layout.addSpacing(8)  # 这里的8表示间距的像素值
        self.fft_widget = pg.PlotWidget()
        self.fft_widget.plotItem.showAxis('left', False)  # 隐藏左侧Y轴
        self.fft_widget.hideButtons()
        # 禁止鼠标缩放和拖动
        self.fft_widget.setMouseEnabled(x=False, y=False)
        self.fft_widget.getAxis("bottom").setTicks([[(i, str(i // 6)) for i in range(0, 361, 36)]])
        self.fft_widget.setSizePolicy(
            pg.QtWidgets.QSizePolicy.Expanding,
            pg.QtWidgets.QSizePolicy.Expanding
        )
        self.fft_layout.addWidget(self.fft_widget)
        self.fft_line = self.fft_widget.plot()
        self.fftTimer = QTimer()
        self.fftTimer.timeout.connect(self.spec_update)
        self.fftTimer.start(200)

    def dropDownBox(self):  # 范式选择的下拉框，这应该要改，添加32导
        paradigmFiles = []
        # 创建一个QComboBox对象
        self.combo = QComboBox()  # 它是一个下拉框控件，用于显示一个可选项的列表
        # 匹配目录下的所有文件
        files = glob.glob('./Experimental_paradigm' + "/*.*")  # 在项目里面的文件夹，把全导联改一下
        # 对每个文件进行处理
        for file in files:
            # 分割文件名和扩展名
            filename, extension = os.path.splitext(file)
            paradigmFiles.append(filename)
            filename = os.path.basename(filename)
            self.combo.addItem(filename)
        self.combo.addItem("自定义导联范式")
        # 为每个选项设置触发函数
        self.combo.activated[int].connect(lambda x: self.on_activated(x, paradigmFiles))
        return self.combo

    def on_activated(self, index,paradigmFiles):  # 范式选择下拉框对应的触发函数
        if index == self.paradimSelect.count()-1:  # 点击了新建
            self.select_channels()  # 判断用户是否选择了下拉框中的最后一个选项，即“自定义导联范式”或“新建”
        else:
            with open('{}.json'.format(paradigmFiles[index]), 'r') as f1:  # 打开用户选择的范式对应的 JSON 文件
                # 从文件对象中读取JSON数据，并反序列化为Python对象
                configure = json.load(f1)
            self.enabled_Channels = configure['Enabled_Channels']  #用来存储哪些导联通道被启用
            self.clear_layout(self.wavePlotLay)
            plot_widgets = [myCurves(self.all_channels[idx]).create_curve() for idx, value in
                            enumerate(self.enabled_Channels) if value == 1]
            self.eeg_lines = []
            for index, plot_widget in enumerate(plot_widgets):
                self.wavePlotLay.addLayout(plot_widget[0], stretch=1)
                self.eeg_lines.append(plot_widget[1])
            self.fft_combo.clear()
            self.fft_combo.addItems([self.all_channels[idx] for idx, value in enumerate(self.enabled_Channels) if value == 1])

    def show_impedance(self):  # 显示阻抗
        if self.impedance_detection == 0:
            self.plot_montage(is_impedance=True)
            for i, enabled in enumerate(self.enabled_Channels):
                button_name = f"{self.all_channels[i]}_3"
                button = getattr(self, button_name, None)
                if button:
                    if enabled:
                        # impedance = IMPEDANCE_VALUE[i]
                        # button.setText(f"{self.all_channels[i]}\n{impedance}KΩ")
                        button.setVisible(True)
                    else:
                        button.setVisible(False)
            self.stackedWidget.setCurrentWidget(self.impedance_page)
        else:
            self.stackedWidget.setCurrentWidget(self.eeg_page)

    def calculate_impedance(self):
        if self.impedance_detection:
            re_data = self.eeg
            if re_data.shape[1] > 500:
                re_data = signal.filtfilt(self.b_impedance, 1, re_data)  # 带通滤波
                global IMPEDANCE_VALUE
                # 只计算启用通道的阻抗值
                enabled_indices = [i for i, val in enumerate(self.enabled_Channels) if val == 1]
                # 确保索引不会超出 re_data 的边界
                valid_indices = range(re_data.shape[0])  # re_data 的索引从 0 开始
                # print("calculate_impedance有效索引", enabled_indices)
                # 计算启用通道的阻抗值
                impedance_values = [round((1.414 * 3.14 / 4 / 6 * np.max(re_data[x, :]) - 25.8997) / 20.946606, 1)
                                    for x
                                    in valid_indices]
                # 更新启用的通道的阻抗值

                for i, impedance in zip(enabled_indices, impedance_values):
                    IMPEDANCE_VALUE[i] = impedance
            self.update_label()

    def hide_layout(self, layout):  # 隐藏给定的布局（layout）中的所有 widgets，并用一个空的 QWidget 作为占位符替换它们，需要临时隐藏某些界面元素但保持布局结构不变的情况下非常有用
        for i in range(layout.count()):
            widget = layout.itemAt(i).widget()
            if widget:
                widget.hide()
                placeholder = QWidget()
                layout.addWidget(placeholder)

    def clear_layout(self, thisLayout):  # 完全清空layout
        item_list = list(range(thisLayout.count()))
        item_list.reverse()  # 倒序删除，避免影响布局顺序

        for i in item_list:
            item = thisLayout.itemAt(i)
            if item is not None:
                if item.widget() is not None:
                    item.widget().deleteLater()
                elif isinstance(item, QSpacerItem):
                    thisLayout.removeItem(item)
                else:
                    self.clear_layout(item.layout())
                thisLayout.removeItem(item)

    def select_channels(self):  #主要目的是创建一个新的界面部件，用于选择或输入通道名称，并提供几个按钮供用户操作，大概不需要改
        for button in self.electrode_buttons.values():
            button.setChecked(False)
            button.setStyleSheet("border-image: url(:/imgs/imgs/红电极.png);\nfont: 10pt \"Arial\";")
        self.checkedchannels = []
        # 清空 self.lineEdit
        self.lineEdit.clear()

        # 禁用初始状态
        self.paradimSelect.setEnabled(False)
        self.startButton.setEnabled(False)
        self.impedanceButton.setEnabled(False)
        self.stackedWidget.setCurrentWidget(self.centralwidget_page)
        self.affirmButton.setEnabled(False)  # 初始化禁用
        self.affirmAndSave.setEnabled(False)  # 初始化禁用
        font = QFont()
        font.setPixelSize(20)

        self.plot_montage(is_impedance=False)
        self.cancelButton.clicked.connect(self.param_cancel)
        self.affirmButton.clicked.connect(
            lambda: self.param_affirm(self.lineEdit.text(), False))
        self.affirmAndSave.clicked.connect(
            lambda: self.param_affirm(self.lineEdit.text(), True))

    def update_button_states(self):
        """根据选中的通道数量更新确认按钮状态"""
        has_selected = len(self.checkedchannels) > 0
        self.affirmButton.setEnabled(has_selected)
        self.affirmAndSave.setEnabled(has_selected)

    def plot_montage(self, is_impedance):  # 选择可用导联，这个需要改，我们现在有32个导联
        self.channels = []  # 初始化 self.channels 列表
        for button_name in self.all_channels:
            self.channels.append(button_name)
        # print("self.channels",self.channels)
    def param_affirm(self,text,isSave):
        self.startButton.setEnabled(True)
        self.impedanceButton.setEnabled(True)  # 设置阻抗可显示
        if not self.checkedchannels:  # 没有选中任何通道
            self.log_edit("请至少选择一个导联")
            return
        self.enabled_Channels = [1 if ch in self.checkedchannels else 0 for ch in self.all_channels]
        print(self.enabled_Channels ,"self.enabled_Channels")
        print("self.checkedchannels", self.checkedchannels)
        if isSave:
            configure = {
                'Fs': 250,
                'Enabled_Channels': self.enabled_Channels,
            }
            with open('./Experimental_paradigm/{}.json'.format(text), 'w') as f1:
                json.dump(configure, f1)
        # 添加一个新的选项
        self.combo.insertItem(self.combo.count() - 1, f"{text}")
        # 将当前选择的选项设置为刚新增的那个选项
        self.combo.setCurrentIndex(self.combo.count() - 2)
        self.paradimSelect.setEnabled(True)
        self.stackedWidget.setCurrentWidget(self.eeg_page)
        indices = [index for index, value in enumerate(self.enabled_Channels) if value == 1]
        channels = [self.all_channels[index] for index in indices]
        self.clear_layout(self.wavePlotLay)
        plot_widgets = [myCurves(self.all_channels[idx]).create_curve() for idx,value in enumerate(self.enabled_Channels) if value == 1]
        self.eeg_lines = []
        for index, plot_widget in enumerate(plot_widgets):
            self.wavePlotLay.addLayout(plot_widget[0], stretch=1)
            self.eeg_lines.append(plot_widget[1])

        self.fft_combo.clear()
        self.fft_combo.addItems(
            [self.all_channels[idx] for idx, value in enumerate(self.enabled_Channels) if value == 1])

    def param_cancel(self):
        self.paradimSelect.setEnabled(True)
        self.startButton.setEnabled(True)
        self.impedanceButton.setEnabled(True)  # 设置阻抗可显示
        self.stackedWidget.setCurrentWidget(self.eeg_page)

    def update_label(self):
        global IMPEDANCE_VALUE
        for i, enabled in enumerate(self.enabled_Channels):
            button_name = f"{self.all_channels[i]}_3"
            button = getattr(self, button_name, None)
            if button:
                if enabled:
                    impedance = IMPEDANCE_VALUE[i]
                    if impedance > 80 or impedance < 12:
                        button.setStyleSheet("border-image: url(:/imgs/imgs/红电极.png);\n"
                                             "font: 10pt \"Arial\";")
                    else:
                        button.setStyleSheet("border-image: url(:/imgs/imgs/绿电极.png);\n"
                                             "font: 10pt \"Arial\";")
                    if abs(impedance) > 250 or impedance < 0:
                        button.setText(f"{self.all_channels[i]}\n>250KΩ")
                    else:
                        button.setText(f"{self.all_channels[i]}\n{impedance}KΩ")
                    # button.setVisible(True)
                # else:
                #     button.setVisible(False)
        self.update()

class myCurves():  # 波形曲线
    def __init__(self, channelName):
        self.hlayout = QHBoxLayout()
        self.channel_name = QLabel()
        self.channel_name.setText(channelName)
        font = QFont()
        font.setPointSize(14)
        self.channel_name.setFont(font)
        self.p = pg.PlotWidget()
        self.p.setMinimumHeight(1)  # 设置最小高度
        self.p.setBackground('w')
        self.p.setXRange(0, 900, padding=0)  # 设置X轴显示范围
        self.p.plotItem.showAxis('left', False)  # 隐藏左侧Y轴
        self.p.plotItem.showAxis('bottom', False)  # 隐藏X轴
        self.center_y = 0.5
        self.p.getPlotItem().vb.wheelEvent = self.wheelEvent
        self.p.hideButtons()
        # 禁用拖动平移
        self.p.getPlotItem().vb.mousePressEvent = self._custom_mousePressEvent
        self.p.getPlotItem().vb.mouseMoveEvent = self._custom_mouseMoveEvent

        self.hlayout.addWidget(self.channel_name)
        self.hlayout.addWidget(self.p)
        self.hlayout.setStretch(0, 1)  # 0是索引，3是 3/(3+...)
        self.hlayout.setStretch(1, 25)

    def _custom_mousePressEvent(self, ev):
        # 覆盖默认的鼠标按下事件处理，阻止平移开始
        pass
    def _custom_mouseMoveEvent(self, ev):
        # 覆盖默认的鼠标移动事件处理，阻止平移继续
        pass
    def wheelEvent(self, event):
        # 获取滚轮滚动的方向
        delta = event.delta()
        # 获取当前视图的范围
        x_range, y_range = self.p.getPlotItem().getViewBox().viewRange()
        # 计算缩放的中心点坐标
        y_center = y_range[0] + (y_range[1] - y_range[0]) * self.center_y
        # 设置Y轴缩放因子
        y_scale_factor = 1.1 if delta > 0 else 0.9
        global wavePlotLay
        for i in range(self.wavePlotLay.count()):
            item = self.wavePlotLay.itemAt(i)
            item = item.itemAt(1)
            if item.widget():
                widget = item.widget()
                # 进行Y轴缩放
                widget.getPlotItem().getViewBox().scaleBy((1, y_scale_factor), (0, y_center))

    def create_curve(self):
        initData = np.zeros((900,))
        line = self.p.plot(pen='b')
        line.setData(initData)
        return self.hlayout, line



class WelcomeDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent, Qt.Window | Qt.FramelessWindowHint)  # 隐藏边框
        self.initUI()

    def initUI(self):
        # 创建一个 QLabel 用于显示图片
        self.label = QLabel(self)

        # 加载图片
        pixmap = QPixmap('imgs/welcome.png')

        # 设置 QLabel 的 pixmap 属性以显示图片
        self.label.setPixmap(pixmap)

        # 设置窗口大小以适应图片（可选）
        self.setFixedSize(pixmap.size())

        # 创建一个 QTimer，2秒后触发 timeout 信号
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.accept)  # 2秒后关闭对话框
        self.timer.start(2000)  # 2000毫秒 = 2秒

class CLIChatClient:
    def __init__(self, server_url, user_id):
        # 连接配置
        self.server_url = server_url
        self.user_id = user_id

        # Socket.IO 客户端
        self.sio = socketio.Client(reconnection=True, reconnection_attempts=20, reconnection_delay=1)

        # 线程安全机制
        self.send_lock = threading.RLock()  # 递归锁用于发送操作
        self.conn_lock = threading.Lock()  # 连接状态操作锁
        self.send_queue = Queue()  # 消息发送队列

        # 控制参数
        self.max_retries = 20  # 最大重试次数
        self.running = True  # 运行状态标志

        # 初始化连接
        self._setup_handlers()
        self._start_workers()

    def _setup_handlers(self):
        """配置Socket.IO事件处理器"""

        @self.sio.event
        def connect():
            print(f"\n[系统] 已连接到服务器 {self.server_url}")
            self.sio.emit('register', self.user_id)

        @self.sio.on('private_msg')
        def on_private_message(data):
            print(f"\n[新消息] 来自 {data['from']}: {data['message']}")

        @self.sio.event
        def disconnect():
            print("\n[系统] 与服务器断开连接")
            if self.running:  # 非主动关闭时尝试重连
                self._safe_connect()

        @self.sio.on('processing_result')
        def on_processing_result(data):
            print(f"\n[处理结果] {data['result']}")

        @self.sio.on('status_update')
        def on_status(data):
            print(f"\n[状态更新] {data['status']}")

    def send_eeg(self, eeg_data):
        """发送EEG数据"""
        self.sio.emit('eeg', {'eeg': eeg_data})

    def _start_workers(self):
        """启动后台工作线程"""
        # 队列处理线程
        threading.Thread(target=self._process_queue, daemon=True).start()
        # 心跳线程
        threading.Thread(target=self._keepalive, daemon=True).start()

    def _keepalive(self):
        """维持连接的心跳检测"""
        while self.running:
            time.sleep(5)
            if not self.sio.connected:
                self._safe_connect()

    def _safe_connect(self):
        """带锁的安全连接方法"""
        with self.conn_lock:
            if not self.sio.connected:
                try:
                    self.sio.connect(self.server_url)
                except Exception as e:
                    print(f"连接失败: {str(e)}")

    @RateLimiter(max_calls=10, period=1)  # 每秒最多10条消息
    def async_send(self, target, message):
        """
        异步消息发送入口
        :param target: 接收方ID
        :param message: 消息内容
        """
        self.send_queue.put({
            'target': target,
            'message': message,
            'retries': 0
        })

    def _process_queue(self):
        """消息队列处理核心"""
        while self.running:
            item = self.send_queue.get()
            self._send_with_retry(item)

    def send_to_server(self, event_name, data):
        """
        发送自定义事件及数据到服务器
        :param event_name: Socket.IO 事件名称
        :param data: 要发送的数据（字典格式）
        """
        self.send_queue.put({
            'event': event_name,
            'data': data,
            'status': data['status'],
            'retries': 0
        })

    def _send_with_retry(self, item):
        """带重试机制的发送逻辑（已适配通用事件）"""
        while item['retries'] <= self.max_retries and self.running:
            try:
                with self.send_lock:
                    if not self.sio.connected:
                        self._safe_connect()

                    if self.sio.connected:
                        # 判断是否为通用事件格式
                        if 'event' in item and 'data' in item:
                            self.sio.emit(item['event'], item['data'])
                            print(f"[成功] 事件 {item['event']}")
                        else:
                            # 原有私聊消息逻辑
                            self.sio.emit('private_msg', {
                                'from': self.user_id,
                                'target': item['target'],
                                'message': item['message'],
                                'timestamp': int(time.time())
                            })
                            print(f"成功发送至 {item['target']}: {item['message']}")
                        return
            except Exception as e:
                print(f"发送异常: {str(e)}")

            item['retries'] += 1
            if item['retries'] <= self.max_retries:
                time.sleep(2 ** item['retries'])  # 指数退避
            else:
                print(f"发送失败: {item}")

    def start(self):
        """启动客户端"""
        self.running = True
        self._safe_connect()
        try:
            self.sio.wait()
        except KeyboardInterrupt:
            self.shutdown()

    def shutdown(self):
        """安全关闭客户端"""
        self.running = False
        self.sio.disconnect()


if __name__ == "__main__":

    # 创建一个进程通信管道
    SERVER_URL = WordTextS.main_ip  # 服务器ip地址
    USER_ID = "EEG"  # 用户名

    # 初始化客户端
    client = CLIChatClient(SERVER_URL, USER_ID)
    left, right = Pipe()
    # 固定的，PyQt5程序都需要QApplication对象。sys.argv是命令行参数列表，确保程序可以双击运行
    app = QApplication(sys.argv)
    # #初始化
    myWin = MyMainForm(client)
    # 获取屏幕的尺寸
    screen = QDesktopWidget().screenGeometry()
    width, height = screen.width(), screen.height()
    # 设置窗口尺寸
    myWin.setGeometry(0, 0, width, 950)
    # myWin.setGeometry(0,0,1920,1080)
    # #将窗口控件显示在屏幕上
    myWin.show()

    ad_rdy_ev = threading.Event()
    ad_rdy_ev.set()  # 设置线程运行
    t = Thread(target=myWin.receive_data, args=())
    t.daemon = True
    t.start()

    ad_rdy_ev2 = threading.Event()
    ad_rdy_ev2.set()  # 设置线程运行
    t = Thread(target=myWin.get_message, args=(left,))
    t.daemon = True
    t.start()

    # #程序运行，sys.exit方法确保程序完整退出。
    sys.exit(app.exec_())
