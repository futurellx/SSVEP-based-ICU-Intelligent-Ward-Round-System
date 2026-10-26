import glob
import io
import json
import os
from functools import partial
import pyqtgraph as pg
from PyQt5.QtGui import *
from PyQt5.QtCore import *
from PyQt5.QtWidgets import *
from PyQt5.QtCore import Qt, QRect
from PyQt5.QtGui import QFont, QPixmap, QPainter, QBrush, QColor
from PyQt5.QtWidgets import QFrame, QApplication, QMenuBar, QAction, QVBoxLayout, QDesktopWidget, QTextEdit, \
    QHBoxLayout, QPushButton, QSizePolicy, QLabel, QWidget, QGridLayout, QComboBox, QLineEdit, QSpacerItem, QWidget
import sys
import serial
import threading
from datetime import datetime
import numpy as np
from collections import deque
from matplotlib.animation import FuncAnimation
import matplotlib.pyplot as plt
import csv
import requests
from psychopy.gui import QtWidgets
from scipy import signal
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
import itertools
import matplotlib.lines as line
from threading import Thread
from multiprocessing import Process, Pipe
from scipy.fftpack import fft
from scipy.signal import hilbert
from .采集软件界面 import MainUi_Form
from pyqtgraph.Qt import QtCore
import select

global IMPEDANCE_VALUE,is_Admin
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
    #IMPEDANCE_VALUE = [250 for i in range(16)] #各阻抗值，默认250K欧姆
    IMPEDANCE_VALUE = [250 for i in range(32)]
    allAttributes = ['colorOnBegin', 'colorOnEnd', 'colorOffBegin', 'colorOffEnd', 'colorBorderIn', 'colorBorderOut',
                     'radiusBorderOut', 'radiusBorderIn', 'radiusCircle']
    allDefaultVal = [QColor(0, 240, 0), QColor(0, 160, 0), QColor(0, 68, 0), QColor(0, 28, 0), QColor(140, 140, 140),
                     QColor(100, 100, 100),
                     500, 450, 400]
    allLabelNames = [u'灯亮圆心颜色：', u'灯亮边缘颜色：', u'灯灭圆心颜色：', u'灯灭边缘颜色：', u'边框内测颜色：', u'边框外侧颜色：',
                     u'边框外侧半径：', u'边框内侧半径：', u'中间圆灯半径：']

class SerialClass:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(SerialClass, cls).__new__(cls, *args, **kwargs)
            #打开串口
            cls._instance.ser = serial.Serial(
                port='COM3',
                # baudrate=460800,
                baudrate=921600,
                bytesize=serial.EIGHTBITS,  # 数据位，16，32导是8
                parity=serial.PARITY_NONE,  # 校验位,16，32导是NONE
                stopbits=serial.STOPBITS_ONE  # 停止位，16,32导是1
            )
            # 设置缓冲区大小,根据要发送的字节串大小设置，否则数据会打乱
            #cls._instance.ser.set_buffer_size(rx_size=14250, tx_size=14250)   #设置串口的接收和发送缓冲区大小，57*250（采样率）
            cls._instance.ser.set_buffer_size(rx_size=1050, tx_size=1050)
        return cls._instance

class MyMainForm(QFrame, MainUi_Form):
    def __init__(self, parent=None):
        super(QFrame, self).__init__(parent)
        self.setupUi(self)  #调用 MainUi_Form 类（可能是由Qt Designer生成的UI类）中的 setupUi 方法，来初始化并设置GUI的界面布局。
        self.qtWin_edit()  #对页面部分进行编辑
        self.sc = SerialClass()  #创建一个 SerialClass 的实例sc，这个类是用于串口通信的
        self.b_notch, self.a_notch = signal.iirnotch(50 / (250 / 2), 30)  # 50Hz工频陷波，256是采样率，30是质量因子
        self.b_design = signal.firwin(65, [8 / (250 / 2), 40 / (250 / 2)], pass_zero=False)  # 设计8-30Hz带通滤波器
        # self.b_design, self.a_design = signal.butter(5, [2 / (250 / 2), 45 / (250 / 2)], 'bandpass')
        self.b_impedance = signal.firwin(65, [30 / (250 / 2), 33 / (250 / 2)], pass_zero=False) #阻抗检测时的带通滤波器
        self.eeg = np.zeros((32, 1000)) #32导
        # self.all_channels = ['Fp1','Fp2',' F7',' F3',' Fz',' F4',' F8','FT7','FC3','FCz','FC4','FT8',' A1',' T7',' C3',' Cz',' C4',' T8',' A2','TP7','CP3','CPz','CP4','TP8',' P7',' P3',' Pz',' P4',' P8',' O1',' Oz',' O2']
        # self.all_channels = ['Fp1', 'Fp2', 'F7', 'F3', 'Fz', 'F4', 'F8', 'FT7', 'FC3', 'FCz', 'FC4', 'FT8', 'T7', 'C3',
        #                      'Cz', 'C4', 'T8', 'TP7', 'CP3', 'CPz', 'CP4', 'TP8', 'P7', 'P3', 'Pz', 'P4', 'P8', 'O1',
        #                      'Oz', 'O2', 'HEOR', 'VEOU']
        # 对应自研放大器 黑色电极帽
        self.all_channels = ['Fp1', 'Fp2', 'F7', 'F3', 'Fz', 'F4', 'F8', 'FT7', 'FC3', 'FCz', 'FC4', 'FT8', 'T7', 'C3',
                             'Cz', 'C4', 'T4', 'TP7', 'CP3', 'CPz', 'CP4', 'TP8', 'T5', 'P3', 'Pz', 'P4', 'T6', 'O1',
                             'Oz', 'O2', 'HEOR', 'VEOU']
        # self.enabled_Channels = [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1] #32导
        self.enabled_Channels = [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,0,0,1,1,1,1,1,1,1,1,0,0] #32导中的9导
        # self.sc_isopen = False #手动设置是否接收来自串口通信的数据，默认关闭
        self.sc_isopen = False #手动设置是否接收来自串口通信的数据，默认关闭
        self.isAcquition = False #采集状态，False为关闭，True为开启，默认关闭
        self.impedance_detection = 0 #阻抗检测是否开启，0为关闭，1为开启，默认关闭
        self.isDataRecording = 0 #数据记录开关，0为关闭，1为开启，默认关闭
        self.isSendData = 0 #是否发送数据，0为关闭，1为开启，默认关闭
        self.timer = QtCore.QTimer() #定时器，刷新脑电图
        self.impedanceTimer = QtCore.QTimer() #定时器，刷新阻抗显示
        self.plot_EEG() #画脑电图
        self.plot_FFT() #画频谱图


    def qtWin_edit(self): #对界面的部分编辑
        #-----日志输出------#
        self.logTextEdit = QTextEdit()
        self.logTextEdit.setReadOnly(True) #只读类型
        font = QFont("Source Code Pro", 12)  # 使用 Arial 字体，字号为 12
        self.logTextEdit.setFont(font)  #设置字体字号
        groupBoxLayout = QVBoxLayout()  #创建一个垂直布局，vertical？
        groupBoxLayout.addWidget(self.logTextEdit)   #将上面的logTextEdit（日志）添加到groupBoxLayout
        self.groupBox_3.setLayout(groupBoxLayout)  #将 groupBoxLayout 设置为 self.groupBox_3 （一种QT布局）的布局

        #-----开始结束按钮-----#
        self.vlayout = QVBoxLayout(self.groupBox)  #创建一个垂直布局 self.vlayout，并设置它为 self.groupBox （一种QT布局）的布局
        self.hlayout = QHBoxLayout()
        self.vlayout.addLayout(self.hlayout)  #创建一个水平布局 self.hlayout，并将其添加到 self.vlayout 中，大概意思就是在左边放个水平的东西
        self.fileButton = QPushButton('文件')   #创建多个 QPushButton 控件，包括 '文件'、'开始采集'、'显示阻抗' 和 '记录数据
        self.startButton = QPushButton('开始采集')
        self.impedanceButton = QPushButton('显示阻抗')
        self.recordButton = QPushButton('记录数据')
        is_Admin = 1
        if is_Admin:   #这个is_Admin在最后，控制 recordButton（记录数据）按钮的可见性。如果是管理员，则按钮可见，否则不可见
            self.recordButton.setVisible(True)
        else:
            self.recordButton.setVisible(False)
        self.recordButton.setEnabled(False)  #初始化时，'记录数据' 和 '建立连接' 按钮被禁用
        self.sendDataButton = QPushButton('建立连接')
        self.sendDataButton.setEnabled(False)
        self.paradimSelect = self.dropDownBox() #范式选择下拉框
        # self.paradimSelect.setCurrentText('导联选择：全导联')  #并设置其当前文本为 '导联选择：全导联'
        self.paradimSelect.setCurrentText('SSVEP-9导联')  #并设置其当前文本为 'SSVEP-9导联'
        self.fileButton.setSizePolicy(QSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed))
        self.startButton.setFixedSize(100,30)
        self.impedanceButton.setFixedSize(100,30)
        self.recordButton.setFixedSize(100,30)
        self.sendDataButton.setFixedSize(100,30)
        self.paradimSelect.setFixedSize(100,30)
        self.startButton.setSizePolicy(QSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed))
        self.recordButton.setSizePolicy(QSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed))
        self.sendDataButton.setSizePolicy(QSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed))
        self.impedanceButton.setSizePolicy(QSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed))
        self.paradimSelect.setSizePolicy(QSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed))
        self.fileButton.clicked.connect(self.file_option)
        self.startButton.clicked.connect(self.start_acquisition)
        self.recordButton.clicked.connect(self.data_record)
        self.sendDataButton.clicked.connect(self.send_data)
        self.impedanceButton.clicked.connect(self.impedance_state)
        # self.hlayout.addWidget(self.fileButton)  #文件框没有加进来
        self.hlayout.addWidget(self.startButton)
        self.hlayout.addWidget(self.recordButton)
        self.hlayout.addWidget(self.sendDataButton)
        self.hlayout.addWidget(self.paradimSelect)
        self.hlayout.addWidget(self.impedanceButton)

        # 自动开始采集、建立连接、记录数据
        QTimer.singleShot(4000, self.startButton.click)  # 4秒后触发开始采集
        # QTimer.singleShot(7000, self.sendDataButton.click)  # 7秒后触发建立连接
        QTimer.singleShot(9000, self.recordButton.click)  # 9秒后触发记录数据

    def file_option(self):  #对应fileButton
        self.log_edit('文件操作')
    def start_acquisition(self):  #对应startButton(开始采集)
        if self.sc_isopen == False:  #手动设置是否接收来自串口通信的数据，默认关闭
            if not self.sc.ser.isOpen():
                self.sc.ser.open()
            self.eeg = np.empty(shape=[32, 0])
            # self.timer.timeout.connect(self.update_plot)
            # self.timer.start(40)
            self.sc_isopen = True  #将 self.sc_isopen 设置为 True，表示开始采集
            self.sc.ser.write(b'B')  # 向串口发送字节 b'B'，可能是告诉数据采集设备开始采集的命令
            self.startButton.setText('停止采集')  #修改 startButton 的文本为“停止采集”
            self.startButton.setStyleSheet('background-color: red;')  #并改变其背景颜色为红色，以反映当前状态
            self.paradimSelect.setEnabled(False) #设置范式不可改变
            self.log_edit('开始采集')  #在日志编辑框（log_edit）中添加“开始采集”的记录
            self.recordButton.setEnabled(True) #设置记录数据按钮可用
            self.sendDataButton.setEnabled(True)
        elif self.sc_isopen == True:
            if not self.sc.ser.isOpen():
                self.sc.ser.open()
            # self.timer.stop()
            self.sc_isopen = False  #将 self.sc_isopen 设置为 False，表示停止采集
            self.sc.ser.write(b's')  # 停止采集  ，向串口发送字节 b's'，可能是告诉数据采集设备停止采集的命令
            self.startButton.setText('开始采集')  #修改 startButton 的文本为“开始采集”，并清除其背景颜色设置
            self.startButton.setStyleSheet('')
            self.paradimSelect.setEnabled(True)  #启用 paradimSelect，允许在停止采集后更改设置
            self.log_edit('停止采集')
            for j in range(len(self.eeg_lines)):
                self.eeg_lines[j].setPen(color='b')
            self.recordButton.setEnabled(False)  # 设置记录数据按钮不可用
            self.sendDataButton.setEnabled(False)  #在停止采集后，不应再进行数据记录和发送
    def impedance_state(self):  #对应impedanceButton，阻抗显示
        if self.impedance_detection == 0:  #当前未进行阻抗检测 #阻抗检测是否开启，0为关闭，1为开启，默认关闭
            self.impedanceTimer.timeout.connect(self.calculate_impedance)
            self.impedanceTimer.start(500)
            self.show_impedance()  #调用 self.show_impedance() 方法，用于在GUI上显示阻抗值
            self.impedance_detection = 1  # 将 self.impedance_detection 设置为 1，表示开始阻抗检测
            if not self.sc.ser.isOpen():
                self.sc.ser.open()
            self.sc.ser.write(b'STT') #测量阻抗 #向串口发送字节 b'Set-T'，可能是命令数据采集设备开始测量阻抗
            self.impedanceButton.setText('停止')  #修改 阻抗检测按钮文本为“停止”，以反映当前状态
            self.log_edit('开始检测阻抗')
        elif self.impedance_detection == 1:  #当前正在进行阻抗检测
            self.impedanceTimer.stop()
            self.show_impedance()  #再次调用 self.show_impedance() 方法，可能是为了更新或确认阻抗值
            self.impedance_detection = 0  # 将 self.impedance_detection 设置为 0，表示停止阻抗检测
            if not self.sc.ser.isOpen():
                self.sc.ser.open()
            self.sc.ser.write(b'SCC')  #向串口发送字节 b'Set-C'，命令数据采集设备停止测量阻抗
            self.impedanceButton.setText('阻抗')  #修改 impedanceButton 的文本为“阻抗”，以反映当前状态
            self.log_edit('停止检测阻抗')

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
    def send_data(self):  #对应sendDataButton   # 建立连接
        self.dataBuffer = np.zeros((sum(self.enabled_Channels), 250))  # 发送1秒的数据
        self.send_index = 0 #用于计数，每次收到的数据为(Channel，10)，采样率为250，因此self.send_index==25时为1秒数据
        if self.isSendData == 0:
            self.log_edit('开始发送数据')
            self.sendDataButton.setText('停止发送')
            self.sendDataButton.setStyleSheet('background-color: red;')
            self.isSendData = 1
        elif self.isSendData == 1:
            self.log_edit('停止发送数据')
            self.sendDataButton.setText('发送数据')
            self.sendDataButton.setStyleSheet('')
            self.isSendData = 0

    def write_data(self, data):  # 记录带标签的脑电数据  #将带标签的脑电数据写入CSV文件
        with open('SerialPort32/Recorded_Data/{}.csv'.format(self.time_str), 'a', newline='') as file:
            writer = csv.writer(file)  # 通过 csv.writer(file) 创建一个CSV写入器对象，这个对象允许你将数据以CSV格式写入文件
            writer.writerows(data)

    def log_edit(self,message):  #图形用户界面（GUI）中的 QTextEdit 组件中添加日志消息，并确保 QTextEdit 的滚动条滚动到底部，以便用户可以立即看到新添加的消息
        now = datetime.now()  # 获取当前时间，并将其格式化为字符串，存储在 self.time_str 中，为了后续用于文件名或日志记录
        # 将时间转换为字符串
        time_str = now.strftime("%Y-%m-%d-%H.%M.%S")
        self.logTextEdit.append(str(message)+'   '+time_str)  #将消息添加到 QTextEdit 组件的末尾
        # 将 QTextEdit 滚动到底部
        cursor = self.logTextEdit.textCursor()  #创建一个文本光标对象 cursor，它代表 QTextEdit 组件中的当前文本光标位置
        cursor.movePosition(cursor.End)  # 使用 cursor.movePosition(cursor.End) 将光标移动到 QTextEdit 组件的文本末尾
        self.logTextEdit.setTextCursor(cursor)  #通过 self.logTextEdit.setTextCursor(cursor) 将 QTextEdit 组件的文本光标设置为新位置（即文本的末尾）

    def get_message(self,connLeft):  #connLeft 是一个参数，预期是一个网络连接对象，可能是一个套接字对象
        while True:   #这意味着根据从 connLeft 接收到的消息，程序会向串行端口发送相应的命令或数据
            message=connLeft.recv()  #从 connLeft 连接中接收消息。recv 方法通常用于从套接字接收数据
            if message['order'] != None:  #假设 connLeft.recv() 返回的是一个字典，其中包含一个 'order' 键
                order = message['order']  #从消息中提取 'order' 字段的值，并将其存储在 order 变量中
                if not self.sc.ser.isOpen():
                    self.sc.ser.open()
                print('收到消息：',message['order'])
                self.sc.ser.write(order)  #使用 self.sc.ser 对象（可能是一个串行端口对象）的 write 方法将 order 写入串行端口

    def flask_send(self,eegData):  #这是一个实例方法，它接受一个参数 eegData，预期是 EEG 数据的某种表示
        info = {}
        eegData = np.array(eegData.T, dtype='float64')
        info["channel"] = eegData.shape[0]
        info["samples"] = eegData.shape[1]
        bytes_data = eegData.tobytes() #转换为字节流，允许发送原始的二进制数据
        stream = io.BytesIO(bytes_data)  #创建一个字节流对象，可以像文件一样操作
        files = {"bytes_data": stream}   #希望将字节流作为一个文件发送
        res = requests.post("http://{}:{}/Demand".format("127.0.0.1", 9999), data=info, files=files)
        resultInFo = res.text  #从响应中获取文本内容，并将其存储在 resultInFo 变量中
        # print(resultInFo)

    def receive_data(self):  #是接收串行端口（可能是EEG设备）的数据，对其进行一系列处理，并可能将数据发送到Flask应用程序或保存到文件中
        try:
            while True:
                # 检查输入缓冲区中是否有数据
                if self.sc.ser.in_waiting > 0:
                    # 读取并打印接收到的数据
                    data = self.sc.ser.read(size=1050) #32导 105*250
                    myeeg,eegWithLabel = self.bytes2data(data)  #从串行端口读取数据，并调用 bytes2data 方法将数据转换为适当的格式
                    channelsIndex = [i for i, val in enumerate(self.enabled_Channels) if val == 1] #创建一个列表，其中包含所有启用的通道索引
                    # myeeg = myeeg[np.array(channelsIndex)]
                    # 确保 channelsIndex 是一维数组
                    channelsIndex = np.array(channelsIndex)

                    myeeg = myeeg[channelsIndex]
                    if self.isSendData:  #发送数据到Flask应用程序（如果启用）
                        self.dataBuffer[:,self.send_index*10:self.send_index*10+10] = myeeg
                        self.send_index += 1
                        if self.send_index == 25:
                            try:
                                last_row = self.dataBuffer[-1, :]
                                sendData = np.vstack([self.dataBuffer,last_row])
                                self.flask_send(sendData.T)
                            except:
                                print('服务器未开启！')
                            self.send_index = 0
                    # channelsIndex.append(-1) #读取最后一列标签位
                    # 添加最后一列标签位
                    channelsIndex = np.append(channelsIndex, -1)
                    # eegWithLabel = eegWithLabel[:,np.array(channelsIndex)]  # 所有行都要，只要启用的列
                    eegWithLabel = eegWithLabel[:, channelsIndex]
                    if self.isDataRecording:
                        self.write_data(eegWithLabel)

                    if self.eeg.shape[0] == sum(self.enabled_Channels):
                        if self.eeg.shape[1]<1000:
                            self.eeg = np.hstack((self.eeg,myeeg))
                        else:
                            self.eeg[:,:-10] = self.eeg[:,10:]
                            self.eeg[:,-10:] = myeeg
                    else:
                        self.eeg = np.empty(shape=[sum(self.enabled_Channels),0])

        except KeyboardInterrupt:
            # 当用户按下Ctrl+C时，退出循环
            pass

        finally:
            print('发生错误')
            # 关闭串口
            self.sc.ser.close()

    def bytes2data(self,byte_string):  #是一个将字节流转换为EEG（脑电图）数据的函数
        eegWithLabel = [] #初始化一个空列表，用于存储转换后的EEG数据和标签。
        if len(byte_string) % 105 == 0: #32导有105个字节
            byte_string = [byte_string[i:i + 105] for i in range(0, len(byte_string), 105)]
            for index, byte_frame in enumerate(byte_string):
                byte_head = byte_frame[0]  #帧头
                #byte_loff = byte_frame[-5:-3] #LOFF导联检测，2字节 16位，“1”代表失联，“0”代表导联,-5~-4
                byte_loff = byte_frame[-6:-2] #32导,-6~-3
                # 转换为二进制数，
                bin_loff = ''.join(f'{i:08b}' for i in byte_loff) #将LOFF转换为二进制字符串
                bin_loff = bin_loff[:8][::-1] + bin_loff[8:16][::-1] + bin_loff[16:24][::-1]+ bin_loff[24:][::-1]
                bin_loff = [bin_loff[j] for j in [i for i, val in enumerate(self.enabled_Channels) if val == 1]]
                # print('导联情况：',bin_loff)
                self.invalid_channels = [i for i, letter in enumerate(bin_loff) if letter == '1']
                byte_label= byte_frame[-2] #标签，16、32一样
                byte_end = byte_frame[-1]  #帧尾，16、32一样
                byte_eeg = byte_frame[3:-6]  # 去除帧头（0）、序号（1）、备用空间（-7：-1）、帧尾（-1）

                if len(byte_eeg) % 3 == 0 and byte_head == 187 and byte_end == 10: #byte_head-b'\xbb',byte_end-b'\x0a'，#16,32导帧头和帧尾标志一样
                    byte_eeg = [byte_eeg[j:j + 3] for j in
                              range(0, len(byte_eeg), 3)]  # 每三个字节表示一个通道的数据，将数据分成3字节一组
                    eeg_frame = [int.from_bytes(chdata_i, byteorder='big', signed=True) for chdata_i in
                              byte_eeg]  # 按大端字节序的有符号整型转换为十进制数
                    eegWithLabel.extend(eeg_frame)
                    eegWithLabel.append(byte_label)
                else:
                    print("数据长度错误",len(byte_eeg),byte_head,byte_end)
            try:
                eegWithLabel = np.array(eegWithLabel,dtype=np.float64).reshape((10,33))
                eegWithLabel[:, :32] *= (-0.022351744455307063)
                eeg = eegWithLabel[:, :32]
                eeg = np.transpose(eeg, (1, 0))
            except Exception as e:
                print('异常 :',e)
                eeg = np.zeros((32,10))
                if not self.sc.ser.isOpen():
                    self.sc.ser.open()
                self.sc.ser.write(b's') #引发异常，停止采集
        else:
            print("接收数据有误")
            exit()
        return eeg,eegWithLabel

    def spec_init(self): #频谱初始图
        # self.fft_ax.set_xticks(np.arange(0, (250 / 10)+1, 1))  # 设置横坐标的刻度为0-125，每25画一个刻度
        self.fft_ax.set_xticks(np.arange(0, 60 + 1, 5))  # 设置横坐标的刻度为0-125，每25画一个刻度
        for line in self.fft_line:
            self.fft_ax.add_line(line)
        return self.fft_line

    def spec_update(self): #频谱图更新
        if len(self.eeg)!=0:
            tmpEEG = self.eeg[self.fft_index,:]
            if self.sc_isopen == False:
                tmpEEG = np.zeros((1000,))

            tmpEEG = signal.lfilter(self.b_notch, self.a_notch, tmpEEG)  # 工频陷波
            if tmpEEG.shape[0]>500:
                tmpEEG = signal.filtfilt(self.b_design, 1, tmpEEG)  # 带通滤波
                # tmpEEG = signal.filtfilt(self.b_design, self.a_design, tmpEEG) #巴特沃斯带通滤波

            mean_value = np.mean(tmpEEG)
            tmpEEG = tmpEEG-mean_value
            y = abs(fft(tmpEEG,1000))
            # 计算信号的包络
            envelope = np.abs(hilbert(y))

            self.fft_line.setData(np.arange(240),envelope[:240])

        return self.fft_line

    def update_plot(self):
        tmpEEG = self.eeg
        if self.sc_isopen == False:
            tmpEEG = np.zeros((sum(self.enabled_Channels), 1000))  # 32导
        tmpEEG = signal.lfilter(self.b_notch, self.a_notch, tmpEEG)  # 工频陷波

        if tmpEEG.shape[1]>500:
            tmpEEG = signal.filtfilt(self.b_design, 1, tmpEEG)  # 带通滤波
            # tmpEEG = signal.filtfilt(self.b_design, self.a_design, tmpEEG)  # 巴特沃斯带通滤波
        #
        mean_x = np.mean(tmpEEG, axis=1, keepdims=True)
        tmpEEG = tmpEEG - mean_x

        for i, curve in enumerate(self.eeg_lines):
            curve.setData(tmpEEG[i,100:])

        if True and self.sc_isopen and len(self.invalid_channels) != 0: #筛选脱落的导联
            for i in range(len(self.eeg_lines)):
                if i in self.invalid_channels:
                    self.eeg_lines[i].setPen(color='r')  #将检测为导联脱落的导联置为红色
                else:
                    self.eeg_lines[i].setPen(color='b')


    def plot_EEG(self):
        self.eeg_layout = QHBoxLayout()  # 创建一个水平布局对象 self.eeg_layout
        self.wavePlotWidget = QWidget()
        self.eeg_layout.addWidget(self.wavePlotWidget)
        global wavePlotLayout
        wavePlotLayout = QVBoxLayout()
        wavePlotLayout.setSpacing(0)
        self.wavePlotWidget.setLayout(wavePlotLayout)
        plot_widgets = [myCurves(self.all_channels[idx]).create_curve() for idx,value in enumerate(self.enabled_Channels) if value == 1]
        self.eeg_lines = []
        for index,plot_widget in enumerate(plot_widgets):
            wavePlotLayout.addLayout(plot_widget[0], stretch=1)
            self.eeg_lines.append(plot_widget[1])
        self.vlayout.addLayout(self.eeg_layout)  # 将这个水平布局添加到已有的垂直布局 self.vlayout 中。这意味着EEG图形界面将作为垂直布局中的一个组件
        self.invalid_channels = []  #创建一个空列表，用于存储检测到的无效或脱落的通道

        self.timer.timeout.connect(self.update_plot)
        self.timer.start(40)

    def plot_FFT(self):  #创建一个图形界面用于展示FFT（快速傅里叶变换）的结果，并启动一个动画来不断更新这个FFT图形
        self.fft_layout = QVBoxLayout(self.groupBox_2)
        self.fft_index = 0
        hlayout = QHBoxLayout()
        # 创建一个下拉框
        self.fft_combo = QComboBox(self)
        self.fft_combo.addItems(self.all_channels)
        self.fft_combo.setFixedSize(100,30)
        # combo_box.setSizePolicy(QSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed))
        self.fft_combo.currentIndexChanged.connect(lambda index: setattr(self, 'fft_index', index))
        hlayout.addWidget(self.fft_combo)
        self.fft_layout.addLayout(hlayout)
        self.fft_layout.addSpacing(8)  # 这里的20表示间距的像素值
        self.fft_widget = pg.PlotWidget()
        self.fft_widget.plotItem.showAxis('left', False)  # 隐藏左侧Y轴
        # self.fft_widget.setBackground('w')
        self.fft_widget.hideButtons()
        # 禁止鼠标缩放和拖动
        self.fft_widget.setMouseEnabled(x=False, y=False)
        self.fft_widget.getAxis("bottom").setTicks([[(i, str(i // 4)) for i in range(0, 241, 20)]])
        self.fft_widget.setSizePolicy(
            pg.QtWidgets.QSizePolicy.Expanding,
            pg.QtWidgets.QSizePolicy.Expanding
        )
        self.fft_layout.addWidget(self.fft_widget)
        self.fft_line = self.fft_widget.plot()
        self.fftTimer = QTimer()
        self.fftTimer.timeout.connect(self.spec_update)
        self.fftTimer.start(200)

    def dropDownBox(self): #范式选择的下拉框，这应该要改，添加32导
        paradigmFiles = []
        # 创建一个QComboBox对象
        self.combo = QComboBox() #它是一个下拉框控件，用于显示一个可选项的列表
        # 匹配目录下的所有文件
        files = glob.glob('SerialPort32/Experimental_paradigm' + "/*.*")  #在项目里面的文件夹，把全导联改一下
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

    def on_activated(self, index,paradigmFiles): #范式选择下拉框对应的触发函数
        if index == self.combo.count()-1: #点击了新建
            self.select_channels()  #判断用户是否选择了下拉框中的最后一个选项，即“自定义导联范式”或“新建”
        else:
            with open('{}.json'.format(paradigmFiles[index]), 'r') as f1:  #打开用户选择的范式对应的 JSON 文件
                # 从文件对象中读取JSON数据，并反序列化为Python对象
                configure = json.load(f1)
            self.enabled_Channels = configure['Enabled_Channels']  #用来存储哪些导联通道被启用

            self.clear_layout(wavePlotLayout)
            plot_widgets = [myCurves(self.all_channels[idx]).create_curve() for idx, value in
                            enumerate(self.enabled_Channels) if value == 1]
            self.eeg_lines = []
            for index, plot_widget in enumerate(plot_widgets):
                wavePlotLayout.addLayout(plot_widget[0], stretch=1)
                self.eeg_lines.append(plot_widget[1])
            self.fft_combo.clear()
            self.fft_combo.addItems([self.all_channels[idx] for idx, value in enumerate(self.enabled_Channels) if value == 1])
    def show_impedance(self): #显示阻抗
        for i in range(self.eeg_layout.count() - 1, 0, -1):
            widget = self.eeg_layout.itemAt(i).widget()
            if widget:
                self.eeg_layout.removeWidget(widget)
                widget.deleteLater()  # 删除widget 以便展示阻抗
        # self.clear_layout(self.eeg_layout)
        if self.impedance_detection == 0:
            self.plot_montage(is_impedance=True)
            for index,element in enumerate(self.enabled_Channels):
                if element == 0:
                    self.hide_layout(self.channels[index])
            self.wavePlotWidget.setVisible(False)
            self.centralwidget.setVisible(True)
        else:
            # plot_widgets = [myCurves(self.all_channels[idx]).create_curve() for idx, value in
            #                 enumerate(self.enabled_Channels) if value == 1]
            # self.eeg_lines = []
            # for index, plot_widget in enumerate(plot_widgets):
            #     wavePlotLayout.addLayout(plot_widget[0], stretch=1)
            #     self.eeg_lines.append(plot_widget[1])
            self.wavePlotWidget.setVisible(True)
            self.centralwidget.setVisible(False)

    def calculate_impedance(self): #计算阻抗
        if self.impedance_detection:  # 如果阻抗检测被启用，对EEG数据进行滤波，并计算阻抗值
            re_data = self.eeg
            re_data = signal.filtfilt(self.b_impedance, 1, re_data)  # 带通滤波
            global IMPEDANCE_VALUE
            IMPEDANCE_VALUE = [round((1.414 * 3.14 / 4 / 6 * np.max(re_data[x, :]) - 25.8997) / 1.946606 + 1, 1) for x
                               in range(len(re_data))]
            print('阻抗值：', IMPEDANCE_VALUE)
    def hide_layout(self,layout):  #隐藏给定的布局（layout）中的所有 widgets，并用一个空的 QWidget 作为占位符替换它们，需要临时隐藏某些界面元素但保持布局结构不变的情况下非常有用
        for i in range(layout.count()):
            widget = layout.itemAt(i).widget()
            if widget:
                widget.hide()
                placeholder = QWidget()
                layout.addWidget(placeholder)

    def clear_layout(self, thisLayout): #完全清空layout
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
        self.paradimSelect.setEnabled(False)  #禁用范式选择
        for i in range(self.eeg_layout.count() - 1, 0, -1):  #清空 EEG 布局中的 Widgets
            widget = self.eeg_layout.itemAt(i).widget()
            if widget:
                self.eeg_layout.removeWidget(widget)
                widget.deleteLater()  # 删除widget
        self.motageOption_widget = QtWidgets.QWidget()  #这里创建了一个新的 QWidget 名为 self.motageOption_widget 和一个垂直布局 self.motageOption_layout
        self.motageOption_layout = QVBoxLayout()
        hLayout = QHBoxLayout()  #创建水平布局和其中的部件:
        font = QFont()
        font.setPixelSize(20)
        label = QLabel("名称:")
        label.setFont(font)
        label.setSizePolicy(QSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed))
        lineEdit = QLineEdit()
        lineEdit.setFixedSize(100,30)
        hLayout.addWidget(label)
        hLayout.addWidget(lineEdit)
        affirmButton = QPushButton("确定")  #创建按钮并设置其属性:
        affirmButton.setFont(font)
        affirmButton.setSizePolicy(QSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed))
        affirmButton.setFixedSize(160,50)
        affirmButton.setStyleSheet('background-color: rgb(213, 213, 213);border-radius: 20px; border: 2px groove gray;border-style: outset;')
        cancelButton = QPushButton("取消")
        cancelButton.setFont(font)
        cancelButton.setSizePolicy(QSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed))
        cancelButton.setFixedSize(160, 50)
        cancelButton.setStyleSheet('background-color: rgb(213, 213, 213);border-radius: 20px; border: 2px groove gray;border-style: outset;')
        cancelButton.clicked.connect(self.param_cancel)
        affirmAndSave = QPushButton("确定并保存文件")
        affirmAndSave.setFont(font)
        affirmAndSave.setSizePolicy(QSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed))
        affirmAndSave.setFixedSize(160, 50)
        affirmAndSave.setStyleSheet('background-color: rgb(213, 213, 213);border-radius: 20px; border: 2px groove gray;border-style: outset;')
        self.motageOption_layout.addLayout(hLayout)  #将部件添加到垂直布局中
        self.motageOption_layout.addWidget(affirmButton)
        self.motageOption_layout.addWidget(cancelButton)
        self.motageOption_layout.addWidget(affirmAndSave)
        self.motageOption_widget.setLayout(self.motageOption_layout)
        self.eeg_layout.addWidget(self.motageOption_widget)
        self.plot_montage(is_impedance=False)
        if self.eeg_layout.count()>2:
            self.eeg_layout.setStretch(1,1)
            self.eeg_layout.setStretch(2,5)
        self.wavePlotWidget.setVisible(False)
        self.centralwidget.setVisible(True)

        affirmButton.clicked.connect(
            lambda: self.param_affirm(lineEdit.text(),
            [channel.itemAt(0).widget().isClicked for channel in self.channels],False))
        affirmAndSave.clicked.connect(
            lambda: self.param_affirm(lineEdit.text(),
            [channel.itemAt(0).widget().isClicked for channel in self.channels],True))

    def plot_montage(self,is_impedance): #选择可用导联，这个需要改，我们现在有32个导联
        self.centralwidget = QtWidgets.QWidget()
        self.centralwidget.setObjectName("wkWgt")  # 替换背景图片只对当前窗口生效 核心代码
        self.centralwidget.setStyleSheet("#wkWgt{border-image:url(SerialPort32/imgs/brainMap.png);}")  # 替换图片路径  核心代码
        grid_layout = QGridLayout()

        element1 = ChannelLabel(imgPath='SerialPort32/imgs/红电极.png', text="Fp1", is_impedance=is_impedance, index=0).channelLabel()
        element2 = ChannelLabel(imgPath='SerialPort32/imgs/红电极.png', text="Fp2", is_impedance=is_impedance, index=1).channelLabel()
        element3 = ChannelLabel(imgPath='SerialPort32/imgs/红电极.png', text="F7", is_impedance=is_impedance, index=2).channelLabel()
        element4 = ChannelLabel(imgPath='SerialPort32/imgs/红电极.png', text="F3", is_impedance=is_impedance, index=3).channelLabel()
        element5 = ChannelLabel(imgPath='SerialPort32/imgs/红电极.png', text="Fz", is_impedance=is_impedance, index=4).channelLabel()
        element6 = ChannelLabel(imgPath='SerialPort32/imgs/红电极.png', text="F4", is_impedance=is_impedance, index=5).channelLabel()
        element7 = ChannelLabel(imgPath='SerialPort32/imgs/红电极.png', text="F8", is_impedance=is_impedance, index=6).channelLabel()
        element8 = ChannelLabel(imgPath='SerialPort32/imgs/红电极.png', text="FT7", is_impedance=is_impedance, index=7).channelLabel()
        element9 = ChannelLabel(imgPath='SerialPort32/imgs/红电极.png', text="FC3", is_impedance=is_impedance, index=8).channelLabel()
        element10 = ChannelLabel(imgPath='SerialPort32/imgs/红电极.png', text="FCz", is_impedance=is_impedance, index=9).channelLabel()
        element11 = ChannelLabel(imgPath='SerialPort32/imgs/红电极.png', text="FC4", is_impedance=is_impedance, index=10).channelLabel()
        element12 = ChannelLabel(imgPath='SerialPort32/imgs/红电极.png', text="FT8", is_impedance=is_impedance, index=11).channelLabel()
        element13 = ChannelLabel(imgPath='SerialPort32/imgs/红电极.png', text="T7", is_impedance=is_impedance, index=12).channelLabel()
        element14 = ChannelLabel(imgPath='SerialPort32/imgs/红电极.png', text="C3", is_impedance=is_impedance, index=13).channelLabel()
        element15 = ChannelLabel(imgPath='SerialPort32/imgs/红电极.png', text="Cz", is_impedance=is_impedance, index=14).channelLabel()
        element16 = ChannelLabel(imgPath='SerialPort32/imgs/红电极.png', text="C4", is_impedance=is_impedance, index=15).channelLabel()
        # element17 = ChannelLabel(imgPath='imgs/红电极.png', text="T8", is_impedance=is_impedance, index=16).channelLabel()
        element17 = ChannelLabel(imgPath='SerialPort32/imgs/红电极.png', text="T4", is_impedance=is_impedance,index=16).channelLabel()
        element18 = ChannelLabel(imgPath='SerialPort32/imgs/红电极.png', text="TP7", is_impedance=is_impedance, index=17).channelLabel()
        element19 = ChannelLabel(imgPath='SerialPort32/imgs/红电极.png', text="CP3", is_impedance=is_impedance, index=18).channelLabel()
        element20 = ChannelLabel(imgPath='SerialPort32/imgs/红电极.png', text="CPz", is_impedance=is_impedance, index=19).channelLabel()
        element21 = ChannelLabel(imgPath='SerialPort32/imgs/红电极.png', text="CP4", is_impedance=is_impedance, index=20).channelLabel()
        element22 = ChannelLabel(imgPath='SerialPort32/imgs/红电极.png', text="TP8", is_impedance=is_impedance, index=21).channelLabel()
        # element23 = ChannelLabel(imgPath='imgs/红电极.png', text="P7", is_impedance=is_impedance, index=22).channelLabel()
        element23 = ChannelLabel(imgPath='SerialPort32/imgs/红电极.png', text="T5", is_impedance=is_impedance,index=22).channelLabel()
        element24 = ChannelLabel(imgPath='SerialPort32/imgs/红电极.png', text="P3", is_impedance=is_impedance, index=23).channelLabel()
        element25 = ChannelLabel(imgPath='SerialPort32/imgs/红电极.png', text="Pz", is_impedance=is_impedance, index=24).channelLabel()
        element26 = ChannelLabel(imgPath='SerialPort32/imgs/红电极.png', text="P4", is_impedance=is_impedance, index=25).channelLabel()
        # element27 = ChannelLabel(imgPath='imgs/红电极.png', text="P8", is_impedance=is_impedance, index=26).channelLabel()
        element27 = ChannelLabel(imgPath='SerialPort32/imgs/红电极.png', text="T6", is_impedance=is_impedance, index=26).channelLabel()
        element28 = ChannelLabel(imgPath='SerialPort32/imgs/红电极.png', text="O1", is_impedance=is_impedance, index=27).channelLabel()
        element29 = ChannelLabel(imgPath='SerialPort32/imgs/红电极.png', text="OZ", is_impedance=is_impedance, index=28).channelLabel()
        element30 = ChannelLabel(imgPath='SerialPort32/imgs/红电极.png', text="O2", is_impedance=is_impedance, index=29).channelLabel()
        element31 = ChannelLabel(imgPath='SerialPort32/imgs/红电极.png', text="HEOR", is_impedance=is_impedance,
                                 index=30).channelLabel()
        element32 = ChannelLabel(imgPath='SerialPort32/imgs/红电极.png', text="VEOU", is_impedance=is_impedance,
                                 index=31).channelLabel()

        # 将每个元素添加到网格布局中
        # spacer = QWidget()
        # grid_layout.addWidget(spacer,1,0)
        # grid_layout.addWidget(spacer,1,1)
        grid_layout.addLayout(element1, 0, 2)
        grid_layout.addLayout(element2, 0, 4)
        grid_layout.addLayout(element3, 1, 1)
        grid_layout.addLayout(element4, 1, 2)
        grid_layout.addLayout(element5, 1, 3)
        grid_layout.addLayout(element6, 1, 4)
        grid_layout.addLayout(element7, 1, 5)
        grid_layout.addLayout(element8, 2, 0)
        grid_layout.addLayout(element9, 2, 2)
        grid_layout.addLayout(element10, 2, 3)
        grid_layout.addLayout(element11, 2, 4)
        grid_layout.addLayout(element12, 2, 6)
        grid_layout.addLayout(element13, 3, 0)
        grid_layout.addLayout(element14, 3, 2)
        grid_layout.addLayout(element15, 3, 3)
        grid_layout.addLayout(element16, 3, 4)
        grid_layout.addLayout(element17, 3, 6)
        grid_layout.addLayout(element18, 4, 0)
        grid_layout.addLayout(element19, 4, 2)
        grid_layout.addLayout(element20, 4, 3)
        grid_layout.addLayout(element21, 4, 4)
        grid_layout.addLayout(element22, 4, 6)
        grid_layout.addLayout(element23, 5, 1)
        grid_layout.addLayout(element24, 5, 2)
        grid_layout.addLayout(element25, 5, 3)
        grid_layout.addLayout(element26, 5, 4)
        grid_layout.addLayout(element27, 5, 5)
        grid_layout.addLayout(element28, 6, 2)
        grid_layout.addLayout(element29, 6, 3)
        grid_layout.addLayout(element30, 6, 4)
        grid_layout.addLayout(element31, 0, 0)
        grid_layout.addLayout(element32, 0, 6)
        self.centralwidget.setLayout(grid_layout)
        self.eeg_layout.addWidget(self.centralwidget)

        self.channels = [element1, element2, element3, element4, element5, element6, element7, element8, element9,
                         element10, element11, element12, element13, element14, element15, element16, element17,
                         element18, element19, element20, element21, element22, element23, element24, element25,
                         element26, element27, element28, element29, element30, element31, element32]

    def param_affirm(self,text,channels,isSave):
        self.enabled_Channels = [int(val) for val in channels]
        if isSave:
            configure = {
            'Fs': 250,
            'Enabled_Channels': self.enabled_Channels,
            }
            with open('SerialPort32/Experimental_paradigm/{}.json'.format(text), 'w') as f1:
                json.dump(configure, f1)
        # 添加一个新的选项
        self.combo.insertItem(self.combo.count() - 1, f"{text}")
        # 将当前选择的选项设置为刚新增的那个选项
        self.combo.setCurrentIndex(self.combo.count() - 2)
        self.paradimSelect.setEnabled(True)
        for i in range(self.eeg_layout.count() - 1, 0, -1):
            widget = self.eeg_layout.itemAt(i).widget()
            if widget:
                self.eeg_layout.removeWidget(widget)
                widget.deleteLater()  # 删除widget
        self.wavePlotWidget.setVisible(True)
        self.motageOption_widget.setVisible(False)
        self.centralwidget.setVisible(False)

        indices = [index for index, value in enumerate(self.enabled_Channels) if value == 1]
        channels = [self.all_channels[index] for index in indices]
        self.clear_layout(wavePlotLayout)
        plot_widgets = [myCurves(self.all_channels[idx]).create_curve() for idx,value in enumerate(self.enabled_Channels) if value == 1]
        self.eeg_lines = []
        for index, plot_widget in enumerate(plot_widgets):
            wavePlotLayout.addLayout(plot_widget[0], stretch=1)
            self.eeg_lines.append(plot_widget[1])

        self.fft_combo.clear()
        self.fft_combo.addItems(
            [self.all_channels[idx] for idx, value in enumerate(self.enabled_Channels) if value == 1])

    def param_cancel(self):
        self.paradimSelect.setEnabled(True)
        for i in range(self.eeg_layout.count()-1,0,-1):
            widget = self.eeg_layout.itemAt(i).widget()
            if widget:
                self.eeg_layout.removeWidget(widget)
                widget.deleteLater()  # 删除widget
        self.wavePlotWidget.setVisible(True)
        self.motageOption_widget.setVisible(False)
        self.centralwidget.setVisible(False)

class myCurves(): #波形曲线
    def __init__(self,channelName):
        self.hlayout = QHBoxLayout()
        self.channel_name = QLabel()
        self.channel_name.setText(channelName)
        self.p = pg.PlotWidget()
        self.p.setMinimumHeight(1)  # 设置最小高度
        self.p.setBackground('w')
        self.p.setXRange(0,900,padding=0)  #设置X轴显示范围
        self.p.plotItem.showAxis('left', False)  # 隐藏左侧Y轴
        self.p.plotItem.showAxis('bottom', False)  # 隐藏X轴
        self.center_y = 0.5
        self.p.getPlotItem().vb.wheelEvent = self.wheelEvent
        self.p.hideButtons()
        self.hlayout.addWidget(self.channel_name)
        self.hlayout.addWidget(self.p)
        self.hlayout.setStretch(0, 1)  # 0是索引，3是 3/(3+...)
        self.hlayout.setStretch(1, 25)
    def wheelEvent(self, event):
        # 获取滚轮滚动的方向
        delta = event.delta()
        # 获取当前视图的范围
        x_range, y_range = self.p.getPlotItem().getViewBox().viewRange()
        # 计算缩放的中心点坐标
        y_center = y_range[0] + (y_range[1] - y_range[0]) * self.center_y
        # 设置Y轴缩放因子
        y_scale_factor = 1.1 if delta > 0 else 0.9
        global wavePlotLayout
        for i in range(wavePlotLayout.count()):
            item = wavePlotLayout.itemAt(i)
            item = item.itemAt(1)
            if item.widget():
                widget = item.widget()
                # 进行Y轴缩放
                widget.getPlotItem().getViewBox().scaleBy((1, y_scale_factor), (0, y_center))

    def create_curve(self):
        initData = np.zeros((900,))
        line = self.p.plot(pen='b')
        line.setData(initData)
        return self.hlayout,line

class ChannelLabel(QLabel): #可点击的图片类
    def __init__(self, imgPath=None, text=None,is_impedance=False,index=None):
        super(ChannelLabel, self).__init__()
        self.setMouseTracking(True)
        self.imgPath = imgPath
        self.text = text  # 要显示的文本
        self.setGeometry(0,0,50,50)
        self.index = index
        self.is_impedance = is_impedance
        self.labeltimer = QTimer()
        self.labeltimer.timeout.connect(self.update_label)  # 将 QTimer 的 timeout 信号连接到 update_label 方法
        self.labeltimer.start(1000)  # 每 1000 毫秒（即 1 秒）触发一次 timeout 信号

    def update_label(self):
        global IMPEDANCE_VALUE
    def channelLabel(self):
        # 创建一个 QPixmap 对象
        pixmap = QPixmap(str(self.imgPath))
        self.setPixmap(pixmap)
        vbox_layout = QVBoxLayout()
        if self.is_impedance:
            vbox_layout.addWidget(self, alignment=Qt.AlignCenter)
        else:
            led = MyLed()
            led.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            vbox_layout.addWidget(led, alignment=Qt.AlignCenter)
        if self.text:
            # 在圆下方绘制文本
            font = QFont()
            font.setPixelSize(24)  # 设置字体大小
            if self.is_impedance:
                global IMPEDANCE_VALUE
                self.textLabel = TextLabel(text=self.text,index=self.index)
            else:
                self.textLabel = QLabel()
                self.textLabel.setFont(font)
                self.textLabel.setText(self.text)
            vbox_layout.addWidget(self.textLabel,alignment=Qt.AlignCenter)
        return vbox_layout


class MyLed(QAbstractButton):
    def __init__(self, parent=None):
        super(MyLed, self).__init__(parent)
        self.initUI()

    def initUI(self):
        self.setMinimumSize(50, 50)
        self.setCheckable(True)
        self.scaledSize = 1000.0    #为方便计算，将窗口短边值映射为1000
        self.setLedDefaultOption()
        self.isClicked = False #是否已经点击

    def setLedDefaultOption(self):
        for attr, val in zip(allAttributes, allDefaultVal):
            setattr(self, attr, val)
        self.update()

    def setLedOption(self, opt='colorOnBegin', val=QColor(0,240,0)):
        if hasattr(self, opt):
            setattr(self, opt, val)
            self.update()

    def resizeEvent(self, evt):
        self.update()

    def mousePressEvent(self, evt):
        super().mousePressEvent(evt)
        if self.isChecked():
            self.isClicked = False
        else:
            self.isClicked = True

    def paintEvent(self, evt):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setPen(QPen(Qt.black, 1))

        realSize = min(self.width(), self.height())                         #窗口的短边
        painter.translate(self.width()/2.0, self.height()/2.0)              #原点平移到窗口中心
        painter.scale(realSize/self.scaledSize, realSize/self.scaledSize)   #缩放，窗口的短边值映射为self.scaledSize
        gradient = QRadialGradient(QPointF(0, 0), self.scaledSize/2.0, QPointF(0, 0))   #辐射渐变

        #画边框外圈和内圈
        for color, radius in [(self.colorBorderOut, self.radiusBorderOut),  #边框外圈
                               (self.colorBorderIn, self.radiusBorderIn)]:   #边框内圈
            gradient.setColorAt(1, color)
            painter.setBrush(QBrush(gradient))
            painter.drawEllipse(QPointF(0, 0), radius, radius)

        # 画内圆
        gradient.setColorAt(0, self.colorOnBegin if self.isChecked() else self.colorOffBegin)
        gradient.setColorAt(1, self.colorOnEnd if self.isChecked() else self.colorOffEnd)
        painter.setBrush(QBrush(gradient))
        painter.drawEllipse(QPointF(0, 0), self.radiusCircle, self.radiusCircle)

class TextLabel(QLabel):
    def __init__(self, parent=None,text=None,index=None):
        super(TextLabel, self).__init__(parent)
        font = QFont()
        font.setPixelSize(20)  # 设置字体大小
        self.setFont(font)
        self.text = text
        self.index = index
        # 创建一个 QTimer 对象
        self.texttimer = QTimer()
        self.texttimer.timeout.connect(self.update_label)  # 将 QTimer 的 timeout 信号连接到 update_label 方法
        self.texttimer.start(1000)  # 每 1000 毫秒（即 1 秒）触发一次 timeout 信号

    def update_label(self):
        global IMPEDANCE_VALUE
        if abs(IMPEDANCE_VALUE[self.index])>250 or IMPEDANCE_VALUE[self.index]<0:
            self.setText(self.text+': >250KΩ')
        else:
            self.setText(self.text + ': {}KΩ'.format(str(IMPEDANCE_VALUE[self.index])))


if __name__ == "__main__":


    # global IMPEDANCE_VALUE,is_Admin
    # with open('./Experimental_paradigm/configure.json', 'r') as f1:
    #     # 从文件对象中读取JSON数据，并反序列化为Python对象
    #     init_configure = json.load(f1)
    # is_Admin = init_configure['Admin']
    # #IMPEDANCE_VALUE = [250 for i in range(16)] #各阻抗值，默认250K欧姆
    # IMPEDANCE_VALUE = [250 for i in range(32)]
    # allAttributes = ['colorOnBegin', 'colorOnEnd', 'colorOffBegin', 'colorOffEnd', 'colorBorderIn', 'colorBorderOut',
    #                  'radiusBorderOut', 'radiusBorderIn', 'radiusCircle']
    # allDefaultVal = [QColor(0, 240, 0), QColor(0, 160, 0), QColor(0, 68, 0), QColor(0, 28, 0), QColor(140, 140, 140),
    #                  QColor(100, 100, 100),
    #                  500, 450, 400]
    # allLabelNames = [u'灯亮圆心颜色：', u'灯亮边缘颜色：', u'灯灭圆心颜色：', u'灯灭边缘颜色：', u'边框内测颜色：', u'边框外侧颜色：',
    #                  u'边框外侧半径：', u'边框内侧半径：', u'中间圆灯半径：']

    # 创建一个进程通信管道
    left, right = Pipe()
    # 固定的，PyQt5程序都需要QApplication对象。sys.argv是命令行参数列表，确保程序可以双击运行
    app = QApplication(sys.argv)
    # #初始化
    myWin = MyMainForm()
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
    t.setDaemon(True)  # 守护
    t.start()

    ad_rdy_ev2 = threading.Event()
    ad_rdy_ev2.set()  # 设置线程运行
    t = Thread(target=myWin.get_message, args=(left,))
    t.setDaemon(True)  # 守护
    t.start()

    # #程序运行，sys.exit方法确保程序完整退出。
    sys.exit(app.exec_())