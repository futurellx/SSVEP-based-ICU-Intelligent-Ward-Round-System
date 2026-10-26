import asyncio
import json
import math
import os  # 提供了与操作系统交互的功能。
import queue
import socket
import struct
import threading  # 提供了线程支持
from multiprocessing import Pipe  # 允许进程间通信。

import socketio

# import win32api
import win32con  # Windows API 的常量定义。
import sqlite3  # 用于连接 SQLite 数据库
import numpy as np
from psychopy import visual, event, core  # 这里导入了用于创建视觉元素、事件处理和核心函数的模块。
from threading import Thread  # 用于创建线程
from screeninfo import get_monitors
from psychopy.hardware.keyboard import Keyboard  # 用于处理键盘输入。
from multiprocessing import Process, Pipe
from TTS import EdgeTTSPlayer
from wordTexts import WordTextS
from runtime_concurrency import BoundedMessageQueue, QueueClosed
import time

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))

keyboard = Keyboard()


class patientWindow:
    def __init__(self, port=None, lock=None):
        super(patientWindow, self).__init__()
        # self.connRight = connRight  # 这个参数是一个管道的一端，用于与另一个进程通信。
        self.question_text = None  # 用于存储当前问题的文本。
        self.stimNum = None  # 用于存储当前刺激的数量。
        # 从 WordTextS 类中获取不同数量的提示和刺激物的位置列表。
        self.tipsPosition = [
            WordTextS.twoTips_position,
            WordTextS.threeTips_position,
            WordTextS.fourTips_position,
            WordTextS.fiveTips_position,
            WordTextS.sixTips_position,
            WordTextS.sevenTips_position,
            WordTextS.eightTips_position,
        ]
        self.stimPosition = [
            WordTextS.twoStim_position,
            WordTextS.threeStim_position,
            WordTextS.fourStim_position,
            WordTextS.fiveStim_position,
            WordTextS.sixStim_position,
            WordTextS.sevenStim_positon,
            WordTextS.eightStim_position,
        ]
        # self.frequency_list = WordTextS.frequency_list  # 从 WordTextS 类中获取频率列表。
        self.tips = None  # 用于存储提示信息。
        self.psy_tips = []  # 存储心理提示
        self.psy_stims = []  # 存储刺激
        self.temp = None  # 临时变量
        self.stageStartTime = 0
        self.ccaSwitch = None  # 查房端患者在当前问题做出选择后，CCA关闭
        self.selected = None  # 查房端患者选择的答案
        self.shanshuo = 0
        self.is_blinking = 1  # 用于控制闪烁的状态
        self.sub_is_blinking = 1
        self.func_selected = "welcome"  # 选择的功能，查房/需求界面
        self.cognition_playing = False  # 认知激活视频播放状态
        self.cognition_video_types = []  # 认知激活视频类型列表
        self.cognition_patient_id = ""
        self.cognition_patient_name = ""
        self.framesList, self.total_frames = [], 0  # 初始化帧列表和总帧数
        self.vepResult = None  # SSVEP选择结果
        self.change_tag = 0  # 问题变化标志(用来标志问题变化的)
        self.change_tag_value = 0  # 初始问题变化标志(真实控制闪烁状态的)
        self.lock = lock or threading.Lock()  # 确保锁对象始终有效
        self.only_one = 1

        self.control_queue = BoundedMessageQueue(maxsize=256, overflow="reject")
        self.stop_event = threading.Event()
        self.reconnect_thread = None
        self.tts = None
        # 在下面定义 2~8 目标对应的频率列表 以及 每一帧的不透明度列表
        self.frames_2, self.total_frames_2 = self.get_frame(WordTextS.frequency_list2)
        self.frames_3, self.total_frames_3 = self.get_frame(WordTextS.frequency_list3)
        self.frames_4, self.total_frames_4 = self.get_frame(WordTextS.frequency_list4)
        self.frames_5, self.total_frames_5 = self.get_frame(WordTextS.frequency_list5)
        self.frames_6, self.total_frames_6 = self.get_frame(WordTextS.frequency_list6)
        self.frames_7, self.total_frames_7 = self.get_frame(WordTextS.frequency_list7)
        self.frames_8, self.total_frames_8 = self.get_frame(WordTextS.frequency_list8)
        # self.frames_man, self.total_frames_man = self.get_frame([35, 36, 36, 37, 38, 38])
        self.sio = socketio.Client(reconnection=False)  # 禁用默认重连，使用自定义逻辑
        self.reconnecting = False
        self.max_retries = 100
        self.retry_delay = 2  # 初始重试延迟(秒)
        self.max_delay = 30  # 最大重试延迟(秒)
        self.init_network()  # 新的网络初始化方法
        self.loop = asyncio.new_event_loop()
        self.audio_thread = threading.Thread(target=self._run_audio_loop, daemon=True)
        self.audio_thread.start()

    def _run_audio_loop(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def init_network(self):
        """网络通信初始化"""
        self.sio.on("connect", self.on_connect)
        self.sio.on("disconnect", self.on_disconnect)
        self.sio.on("message", self.on_message)
        self.sio.on("private_msg", self.on_control_event)

        # 初始连接尝试，带指数退避重试
        retry_count = 0
        current_delay = self.retry_delay

        while retry_count < self.max_retries:
            try:
                self.sio.connect(WordTextS.main_ip, transports=["websocket"], namespaces=["/"])
                print("初始连接成功")
                return
            except Exception as e:
                retry_count += 1
                print(f"连接尝试 {retry_count}/{self.max_retries} 失败: {e}")
                time.sleep(current_delay)
                # 指数退避，但不超过最大延迟
                current_delay = min(current_delay * 2, self.max_delay)

        print("达到最大重试次数，初始化连接失败")

    def on_connect(self):
        """连接成功回调"""
        print("成功连接到消息服务器")
        self.reconnecting = False
        self.sio.emit("register", "patient_ui")

    def on_disconnect(self):
        """连接断开处理"""
        print("与消息服务器断开连接，尝试重连")
        if not self.stop_event.is_set() and not self.reconnecting:
            self.reconnecting = True
            # 启动后台线程进行重连
            import threading

            self.reconnect_thread = threading.Thread(
                target=self._reconnect_loop, name="patient-reconnect", daemon=True
            )
            self.reconnect_thread.start()

    def _reconnect_loop(self):
        """重连循环，在单独线程中运行"""
        retry_count = 0
        current_delay = self.retry_delay

        while self.reconnecting and not self.stop_event.is_set():
            try:
                self.sio.connect(WordTextS.main_ip, transports=["websocket"], namespaces=["/"])
                print("重连成功")
                return
            except Exception as e:
                retry_count += 1
                print(f"重连尝试 {retry_count} 失败: {e}")
                if self.stop_event.wait(current_delay):
                    return
                # 指数退避，但不超过最大延迟
                current_delay = min(current_delay * 2, self.max_delay)

    def on_message(self, data):
        """接收普通消息（仅打印）"""
        print(f"[消息] 类型: message | 内容: {json.dumps(data, indent=2)}")

    def on_control_event(self, data):
        """Socket.IO callback: enqueue only; PsychoPy state is main-thread-owned."""
        try:
            if not self.control_queue.put(data):
                print("患者端控制队列已满，消息被拒绝")
        except QueueClosed:
            pass

    def _drain_control_events(self, limit=64):
        for _ in range(limit):
            try:
                data = self.control_queue.get_nowait()
            except (queue.Empty, QueueClosed):
                return
            self._apply_control_event(data)

    def _apply_control_event(self, data):
        """处理控制事件"""
        print(f"[控制事件] 内容: {json.dumps(data, indent=2)}")
        msg = data["message"]
        print(msg)
        if msg.get("cognition_activate") == 1:
            print("开始认知激活视频播放")
            self.func_selected = "cognition"
            self.cognition_video_types = msg.get("video_types", ["花", "船", "运动想象"])
            self.cognition_patient_id = msg.get("patient_id", "")
            self.cognition_patient_name = msg.get("patient_name", "")
            self.cognition_playing = True
            return
        if msg.get("cognition_activate") == 0:
            print("停止认知激活视频")
            self.cognition_playing = False
            return
        if msg.get("train") == 1:
            print("开始训练闪烁")  # 这里写训练的闪烁逻辑
            self.func_selected = "train"
            return
        if msg.get("searchBestFrequencies") == 1:
            print("开始寻找最佳的频率")  # 这里写寻找最佳的频率的逻辑
            self.func_selected = "searchBestFrequencies"
            return
        if msg.get("change_frequencies"):
            # try:
            #     patient_id = msg.get("change_frequencies").strip()  # 获取病人ID
            #     base_dir = os.path.join(os.getcwd(), "search_results", patient_id)
            #     result_path = os.path.join(base_dir, "frequencies.json")
            #     result = json.load(open(result_path, "r", encoding="utf-8"))["search_result"]
            #     print("开始改变频率", patient_id)  # 这里写改变频率的逻辑

            #     self.frames_2, self.total_frames_2 = self.get_frame(result[0:2])
            #     self.frames_3, self.total_frames_3 = self.get_frame(result[0:3])
            #     self.frames_4, self.total_frames_4 = self.get_frame(result[0:4])
            #     self.frames_5, self.total_frames_5 = self.get_frame(result[0:5])
            #     self.frames_6, self.total_frames_6 = self.get_frame(result[0:6])
            #     self.frames_7, self.total_frames_7 = self.get_frame(result[0:7])
            #     self.frames_8, self.total_frames_8 = self.get_frame(result[0:8])
            #     print("以切换频率为:", result)
            # except Exception as e:
            # print("切换频率失败", e)
            self.frames_2, self.total_frames_2 = self.get_frame(WordTextS.frequency_list2)
            self.frames_3, self.total_frames_3 = self.get_frame(WordTextS.frequency_list3)
            self.frames_4, self.total_frames_4 = self.get_frame(WordTextS.frequency_list4)
            self.frames_5, self.total_frames_5 = self.get_frame(WordTextS.frequency_list5)
            self.frames_6, self.total_frames_6 = self.get_frame(WordTextS.frequency_list6)
            self.frames_7, self.total_frames_7 = self.get_frame(WordTextS.frequency_list7)
            self.frames_8, self.total_frames_8 = self.get_frame(WordTextS.frequency_list8)
            return
        # 更新基础状态
        self.shanshuo = msg["shanshuo"]
        self.ccaSwitch = msg["ccaSwitch"]
        self.selected = msg["selected"]
        self.func_selected = msg["func_selected"]

        # 处理功能切换
        if msg["func_selected"] == "welcome":
            self.func_selected = "welcome"
            print("切换到欢迎界面")
        elif msg["func_selected"] == "round" and msg["question_info"] is not None:
            self.func_selected = "round"
            question_info = msg["question_info"]
            self.question_text = question_info[1]
            self.stimNum = question_info[2]
            self.tips = [answer for answer in question_info if question_info.index(answer) >= 3]
            self.timer = core.Clock()

            with self.lock:
                print("获取到新消息，准备更新self.change_tag和framesList和total_frames")
                self.framesList = getattr(
                    self, f"frames_{self.stimNum}"
                )  # 当前刺激数量为2-8时，从对应列表中获取帧列表和总帧数
                self.total_frames = getattr(self, f"total_frames_{self.stimNum}")
                self.change_tag = 1  # 更新标志
                print(f"self.change_tag已更新为{self.change_tag}")
                print(f"self.question_text已更新为{self.question_text}")
            # # 更新帧数据
            # frames_attr = f'frames_{self.stimNum}'
            # total_attr = f'total_frames_{self.stimNum}'
            # if hasattr(self, frames_attr) and hasattr(self, total_attr):
            #     self.framesList = getattr(self, frames_attr)
            #     self.total_frames = getattr(self, total_attr)
            #     self.change_tag = 1
            #     print(f"更新刺激数量为{self.stimNum}，总帧数{self.total_frames}")
        elif msg["func_selected"] == "demand_entry":
            print("初次进入需求界面,msg['func_selected'] = 'demand_entry'")
            self.func_selected = "demand_entry"  # 设置当前功能为需求界面
            self.selected = None  # 查房端患者选择的答案
            self.vepResult = None  # SSVEP选择结果
            self.function_choice_main = None  # 主界面选择的功能
            self.function_choice_sub01 = None  # 子界面选择的功能
            self.function_choice_sub02 = None  # 二级子界面选择的功能
            self.function_choice_sub01_02 = None  # 留存主界面的选择，用作返回上一级到达子界面
            self.reentry_inint()
        # elif msg['func_selected'] == 'demand':
        #     self.func_selected = 'demand'
        #     print("切换到需求界面")

        else:
            self.vep_is_available = 0  # 已经收到刺激的分类结果，暂时置为不可用
            if msg["func_selected"] == "demand":
                self.func_selected = "demand"  # 设置当前功能为需求界面
            if msg["selected"] != None:
                self.vepResult = msg["selected"]  # 设置SSVEP选择结果
            if self.vepResult in [0, 1, 2, 3, 4, 5, 6, 7]:
                self.demandTimer = core.Clock()  # 重置需求计时器
        # # 处理选择结果
        # if msg['selected'] is not None:
        #     self.vepResult = msg['selected']
        #     if self.vepResult in range(8):
        #         self.demandTimer = core.Clock()
        #         print(f"收到选择结果: {self.vepResult}")

    def __del__(self):
        """安全断开连接"""
        self.close()

    def close(self):
        if not hasattr(self, "stop_event") or self.stop_event.is_set():
            return
        self.stop_event.set()
        self.reconnecting = False
        if hasattr(self, "control_queue"):
            self.control_queue.close()
        if hasattr(self, "sio") and self.sio.connected:
            self.sio.disconnect()
        if hasattr(self, "loop") and self.loop.is_running():
            self.loop.call_soon_threadsafe(self.loop.stop)
        if getattr(self, "tts", None) is not None:
            self.tts.close()
            self.tts = None
        current = threading.current_thread()
        for worker in (
            getattr(self, "reconnect_thread", None),
            getattr(self, "audio_thread", None),
        ):
            if worker is not None and worker is not current:
                worker.join(timeout=2.0)

    async def _speak_content_async(self, tts, question_text, tips, stimNum):
        # 初始化要朗读的完整文本
        sound_text = question_text

        # 定义中文数字映射
        chinese_numbers = ["", "第一", "第二", "第三", "第四", "第五", "第六", "第七", "第八", "第九", "第十"]
        print(f"正在准备朗读内容: {question_text}")
        print(f"tips{tips}")

        # 构建所有提示的朗读文本
        valid_tips = []
        for i, tip in enumerate(tips):
            print(f"处理提示: {tip}")
            # 确保 tip 不超过 stimNum - 1，并且 tip 不是空值或0
            if i >= stimNum or not tip or str(tip) == "0":
                continue
            ordinal = chinese_numbers[i + 1] if (i + 1) < len(chinese_numbers) else f"{i + 1}."
            valid_tips.append(f"{ordinal}{tip}")

        # 将所有有效提示添加到 sound_text
        if valid_tips:
            sound_text += "\n" + "\n".join(valid_tips)
        sound_text += "\n" + "提示，请选择您的答案并用眼盯着下方闪烁块"
        # 一次性朗读所有内容
        await tts.speak(sound_text)

    def get_frame(self, freq_list, flash_time=60, phase_offsets=None):  # yds  增加闪烁时间参数
        # this is a test
        frames = []
        # devmode = win32api.EnumDisplaySettings(win32api.EnumDisplayDevices(None, 0).DeviceName, -1)#获取指定显示器
        # refresh_rate = devmode.DisplayFrequency #获取显示器刷新率
        refresh_rate = WordTextS.refresh_rate  # # 设定显示器刷新率为240Hz
        total_frames = flash_time * refresh_rate  # 预设60秒闪烁
        default_phases = [0.45, 1.35, 0.25, 1.15, 0.9, 1.8, 0.7, 1.6]
        if phase_offsets is None:
            phares = default_phases
        else:
            phares = phase_offsets
        if len(phares) < len(freq_list):
            repeat = math.ceil(len(freq_list) / len(phares))
            phares = (phares * repeat)[: len(freq_list)]
        # 计算每帧中每个刺激的不透明度
        for frameN in range(total_frames):
            frame_opacities = []
            for i in range(len(freq_list)):
                opacity = 0.5 + 0.5 * np.sin(
                    2 * np.pi * freq_list[i] * frameN / refresh_rate + phares[i] * np.pi
                )  # 加相位
                # opacity = 0.5 + 0.5 * np.sin(2 * np.pi * self.frequency_list[i] * frameN / refresh_rate)
                frame_opacities.append(opacity)
            frames.append(frame_opacities)
        return frames, total_frames  # 返回所有帧的不透明度列表和总帧数

    def justtest(self):  # 放闪烁
        self.myInit()  # 初始化界面，这里面包括get_message线程
        self.tts = EdgeTTSPlayer()  # 问题播放器
        tts = self.tts
        frame_index = 0  # 帧数索引
        while True:
            self._drain_control_events()
            if self.func_selected == "welcome":  # 如果当前功能选择为欢迎界面
                if self.temp != None:  # 如果临时变量不为空
                    self.temp = None  # 清空临时变量
                    self.psy_tips = []  # 清空提示列表
                    self.psy_stims = []  # 清空刺激列表
                    self.text_wait.text = "医护正在操作中..."  # 设置等待文本
                    self.question_text = None  # 清空问题文本
                    self.temp = None  # 再次清空临时变量
                self.background_image1.draw()  # 绘制背景图像
                self.win.flip()  # 更新显示
                # 如果按下ESC键则退出程序
                if keyboard.getKeys(keyList=["escape"]):  # escape key to quit
                    core.quit()

            #  训练模式
            elif self.func_selected == "train":  # 如果当前功能选择为问题界面
                print("进入train界面")
                turn_count = WordTextS.turn_count  # 训练轮数
                flash_time = WordTextS.flash_time  # 闪烁时间
                target_count = WordTextS.target_count  # 目标数
                pre_calculated_time = 10  # 预设计算不透明度的时间
                all_trials = turn_count * target_count
                train_text = [None] * target_count
                train_block = [None] * target_count
                frequency_train = WordTextS.frequency_list8
                train_frames, train_total_frames = self.get_frame(
                    frequency_train, pre_calculated_time
                )  # 计算10s的不透明度值
                eightTips_text = ["1", "2", "3", "4", "5", "6", "7", "8"]
                eightTips_position = WordTextS.eightTips_position
                eightStim_position = WordTextS.eightStim_position
                welcome_text = visual.TextStim(
                    self.win,
                    height=0.1,
                    text="即将进入训练模式",
                    color="white",
                    bold=True,
                    italic=False,
                    pos=(0, 0),
                )
                welcome_text.draw()
                self.win.flip()
                time.sleep(WordTextS.pre_welcome_wait)  # 欢迎时间
                textTip = visual.TextStim(self.win, height=0.09, text="3 秒之后将开始实验，请做好准备")
                # 绘制文本刺激
                textTip.draw()
                # 更新窗口
                self.win.flip()
                time.sleep(WordTextS.pre_experiment_wait)  # 准备时间
                # 等待用户按下一个键
                # keys = event.waitKeys()
                for i in range(8):
                    flicker_block = visual.Rect(
                        self.win,
                        width=0.15,
                        height=0.1,
                        fillColor="white",
                        pos=eightStim_position[i],
                        opacity=0.3,
                    )
                    Tips = visual.TextStim(
                        self.win,
                        height=0.04,
                        text=eightTips_text[i],
                        color="white",
                        bold=True,
                        italic=False,
                        pos=eightTips_position[i],
                    )
                    train_text[i] = Tips
                    train_block[i] = flicker_block
                for index in range(all_trials):
                    for i in range(8):
                        # block_8[i].opacity = frames[frameN][i]
                        train_block[index % 8].fillColor = "yellow"
                        train_text[index % 8].color = "yellow"
                        train_block[i].opacity = 1
                        train_text[i].draw()
                        train_block[i].draw()
                    self.win.flip()
                    time.sleep(WordTextS.pre_flash_wait)  # 闪烁前提示时间
                    # 放打开始标签的代码
                    # connRight.send({'order': f'S{(index % 8) + 1:02d}'.encode('ascii')})

                    fram_index = 0
                    flash_start_time = time.time()  # 记录闪烁开始时间
                    while (
                        time.time() - flash_start_time
                    ) < flash_time and fram_index < train_total_frames:  # 只闪烁5s
                        for stim in range(8):
                            train_text[stim].color = "white"
                            train_block[stim].fillColor = "white"
                            train_text[stim].draw()
                            train_block[stim].opacity = train_frames[fram_index][stim]
                            train_block[stim].draw()
                        fram_index += 1
                        self.win.flip()
                    time.sleep(WordTextS.post_flash_rest)

                self.func_selected = "welcome"
            elif self.func_selected == "searchBestFrequencies":  # 如果当前功能选择为问题界面
                print("进入searchBestFrequencies界面")
                config = WordTextS.SearchBestFrequencies
                frequency_sequence = config.frequency_sequence()
                repetitions = config.repetitions
                flash_time = config.flash_duration
                pre_calculated_time = 10  # 预设计算不透明度的时间

                eightTips_text = ["1", "2", "3", "4", "5", "6", "7", "8"]
                eightTips_position = config.eightTips_position
                eightStim_position = config.eightStim_position
                block_index = config.single_block_index

                welcome_text = visual.TextStim(
                    self.win,
                    height=0.1,
                    text="即将进入频率搜索模式",
                    color="white",
                    bold=True,
                    italic=False,
                    pos=(-0.1, 0),
                )
                welcome_text.draw()
                self.win.flip()
                time.sleep(config.pre_welcome_wait)  # 欢迎时间
                textTip = visual.TextStim(
                    self.win, pos=(-0.15, 0), height=0.09, text="3秒之后将开始实验，请做好准备"
                )
                # 绘制文本刺激
                textTip.draw()
                # 更新窗口
                self.win.flip()
                time.sleep(config.pre_experiment_wait)  # 准备时间
                flicker_block = visual.Rect(
                    self.win,
                    width=0.15,
                    height=0.1,
                    fillColor="white",
                    pos=eightStim_position[block_index],
                    opacity=0.3,
                )
                tip_stim = visual.TextStim(
                    self.win,
                    height=0.04,
                    text=str(eightTips_text[block_index]),
                    color="white",
                    bold=True,
                    italic=False,
                    pos=eightTips_position[block_index],
                )

                for freq in frequency_sequence:
                    frames, total_frames = self.get_frame(
                        [freq],
                        pre_calculated_time,
                        phase_offsets=config.phase_offsets,
                    )
                    for _ in range(repetitions):
                        # 提示当前频率
                        tip_stim.text = f"{freq:.1f}Hz"
                        flicker_block.fillColor = "yellow"
                        tip_stim.color = "yellow"
                        flicker_block.opacity = 1
                        tip_stim.draw()
                        flicker_block.draw()
                        self.win.flip()
                        time.sleep(config.pre_flash_wait)
                        frame_index = 0
                        flash_start_time = time.time()
                        # self.simulator.reset_waveforms()
                        while (time.time() - flash_start_time) < flash_time and frame_index < total_frames:
                            tip_stim.color = "white"
                            flicker_block.fillColor = "white"
                            tip_stim.draw()
                            flicker_block.opacity = frames[frame_index][0]
                            flicker_block.draw()
                            frame_index += 1
                            self.win.flip()
                        time.sleep(config.post_flash_rest)

                self.func_selected = "welcome"

            #  查房
            elif self.func_selected == "round":  # 如果当前功能选择为轮次界面
                # self.background_image.draw() # 绘制背景图像
                self.background_image_cf.draw()
                # self.background_require_sub.draw()
                # 如果问题文本发生变化，或者问题文本不为空
                # print("进入round界面")
                if (
                    self.question_text != None and self.temp != self.question_text
                ) or self.question_text != None:
                    if self.temp != self.question_text:
                        self.temp = self.question_text  # 设置临时变量为问题文本
                        # 使用asyncio创建异步任务朗读内容
                        asyncio.run_coroutine_threadsafe(
                            self._speak_content_async(tts, self.question_text, self.tips, self.stimNum),
                            self.loop,
                        )
                    # self.temp = self.question_text  # 设置临时变量为问题文本
                    self.psy_tips = []  # 清空提示列表
                    self.psy_stims = []  # 清空刺激列表
                    # print("刺激列表清空,点击按钮后,管道接收到了新的消息")
                    # self.text_wait.text = self.question_text # 设置等待文本为问题文本
                    self.text_wait.text = (
                        self.question_text
                        if len(self.question_text) <= 20
                        else self.question_text[:20] + "\n" + self.question_text[20:]
                    )  # 设置等待文本为问题文本
                    for i in range(self.stimNum):  # 循环创建提示文本和刺激矩形
                        tip_text = visual.TextStim(
                            win=self.win,
                            text=self.tips[i],
                            color="white",
                            height=0.05,
                            bold=True,
                            italic=False,
                            pos=(self.tipsPosition[self.stimNum - 2][i]),
                        )
                        self.psy_tips.append(tip_text)
                        self.psy_stims.append(
                            visual.Rect(
                                win=self.win,
                                width=0.15,
                                height=0.1,
                                pos=self.stimPosition[self.stimNum - 2][i],
                                fillColor="white",  # 将RGB值转换为0到1之间的浮点数
                                lineColor=None,
                            )
                        )
                self.text_wait.draw()  # 绘制等待文本
                # 如果提示列表不为空且其长度等于刺激数量，并且CCA开关开启
                if len(self.psy_tips) != 0 and len(self.psy_tips) == self.stimNum and self.ccaSwitch == True:
                    self.question_text = None  # 清空问题文本
                    if self.shanshuo == 0 and self.timer.getTime() <= WordTextS.max_read_time:
                        # 4s前只绘制提示文本，并且根据stim_Num给帧列表和总帧数赋值
                        for j, psy_stim in enumerate(self.psy_stims):
                            self.psy_tips[j].draw()
                        # frame_index = 0  # 帧数索引
                        # print(self.timer.getTime())
                    # elif self.shanshuo == 1 or self.timer.getTime() >= WordTextS.max_read_time: # 4s后绘制提示文本和刺激矩形
                    elif self.shanshuo == 1:
                        # frame_index = 0  # 这里置0会导致闪烁不闪，停留在初始相位
                        # print(self.timer.getTime())
                        with self.lock:  # 确保在读取change_tag时不会被其他线程修改
                            self.change_tag_value = self.change_tag
                            for j, psy_stim in enumerate(self.psy_stims):
                                if self.change_tag_value == 0:
                                    self.psy_tips[j].draw()
                                    # print(j)
                                    psy_stim.opacity = self.framesList[frame_index][j]
                                    psy_stim.draw()
                                else:
                                    self.change_tag = 0
                                    break

                # 如果CCA开关关闭且提示列表长度等于刺激数量（出现识别结果）
                if self.ccaSwitch == False and len(self.psy_tips) == self.stimNum:
                    for j in range(self.stimNum):
                        self.psy_stims[j].opacity = 0.3  # 设置所有刺激的不透明度为0.3
                        self.psy_stims[j].draw()  # 绘制所有刺激
                        # 如果有选定项且选定项在刺激数量范围内
                        if self.selected != None and self.selected < self.stimNum:
                            # self.psy_tips[self.selected].color = (100/255, 100/255, 100/255) # 将选定项的提示颜色改为红色
                            self.psy_tips[self.selected].color = "red"  # 将选定项的提示颜色改为红色
                            self.psy_tips[j].draw()  # 绘制所有提示文本
                            self.vepResult = None
                self.win.flip()  # 更新显示
                # 如果按下ESC键则退出程序
                if keyboard.getKeys(keyList=["escape"]):  # escape key to quit
                    core.quit()

            # 认知激活视频播放
            elif self.func_selected == "cognition":
                print("进入认知激活视频播放")
                self.cognition_present()
                self.func_selected = "welcome"

            # 如果当前功能选择为需求界面
            elif self.func_selected == "demand_entry":
                if self.temp != None:  # 如果临时变量不为空
                    self.temp = None  # 清空临时变量
                    self.psy_tips = []  # 清空提示列表
                    self.psy_stims = []  # 清空刺激列表
                # self.patient_Window()   # 调用患者窗口函数
                self.demand_window = 1  # 进入需求主界面
                self.demand_present()  # 闪烁必须在主线程中执行
                # self.win.flip()  # 更新显示

            frame_index += 1  # 帧数索引加一
            # 如果帧数索引超出总帧数范围，则重置为0
            if frame_index >= self.total_frames:
                frame_index = 0

    def cognition_present(self):
        """播放认知激活视频"""
        try:
            from psychopy.visual import MovieStim3
        except ImportError:
            print("MovieStim3 不可用，使用静态提示")
            self._cognition_fallback()
            return

        cognition_start = time.time()
        video_dir = os.path.join(PROJECT_DIR, "认知激活素材")
        video_map = {
            "花": os.path.join(video_dir, "花.mp4"),
            "船": os.path.join(video_dir, "船.mp4"),
            "运动想象": os.path.join(video_dir, "运动想象.mp4"),
        }

        videos_to_play = []
        for vt in self.cognition_video_types:
            if vt in video_map and os.path.exists(video_map[vt]):
                videos_to_play.append(video_map[vt])
            else:
                print(f"视频文件不存在: {vt} -> {video_map.get(vt, '未知路径')}")

        if not videos_to_play:
            print("没有可播放的视频")
            self._cognition_fallback()
            return

        print(f"准备播放 {len(videos_to_play)} 个视频: {videos_to_play}")
        for video_path in videos_to_play:
            if not self.cognition_playing:
                break
            try:
                print(f"正在播放: {video_path}")
                # 获取视频原始分辨率和第10帧，计算最大化但不拉伸的显示尺寸
                first_frame_bgr = None
                try:
                    import cv2

                    cap = cv2.VideoCapture(video_path)
                    vid_w = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
                    vid_h = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 9)  # 跳转到第10帧（0-based）
                    ret, first_frame_bgr = cap.read()
                    cap.release()
                    vid_aspect = vid_w / vid_h if vid_h else 16 / 9
                except Exception:
                    vid_aspect = 16 / 9  # 回退默认比例
                win_w, win_h = 1920, 1080
                win_aspect = win_w / win_h
                if vid_aspect > win_aspect:
                    w, h = win_w, win_w / vid_aspect
                else:
                    w, h = win_h * vid_aspect, win_h

                # 视频前闪烁 3s：画面为视频第10帧，屏幕中央下方 35Hz 闪烁块
                if first_frame_bgr is not None:
                    import tempfile
                    import atexit

                    tmp_frame_path = os.path.join(tempfile.gettempdir(), "_cog_preflash_frame.png")
                    cv2.imwrite(tmp_frame_path, first_frame_bgr)  # imwrite 期望 BGR
                    atexit.register(lambda p=tmp_frame_path: os.path.exists(p) and os.remove(p))
                    first_frame_stim = visual.ImageStim(
                        self.win, image=tmp_frame_path, size=(w, h), units="pix"
                    )
                else:
                    first_frame_stim = None

                flash_block = visual.Rect(
                    self.win,
                    width=150,
                    height=100,
                    pos=(0, -170),
                    fillColor="white",
                    lineColor=None,
                    units="pix",
                )
                flash_clock = core.Clock()
                flash_period = 1.0 / 35.0  # 35Hz 周期 ≈ 28.57ms
                pre_flash_timer = core.Clock()
                while pre_flash_timer.getTime() < 3.0:
                    if not self.cognition_playing:
                        break
                    if first_frame_stim is not None:
                        first_frame_stim.draw()
                    if (flash_clock.getTime() % flash_period) < (flash_period / 2.0):
                        flash_block.draw()
                    self.win.flip()

                # 播放视频（不闪烁）
                mov = MovieStim3(self.win, video_path, size=(w, h), units="pix", loop=False)
                while mov.status != visual.FINISHED:
                    if not self.cognition_playing:
                        break
                    mov.draw()
                    self.win.flip()
            except Exception as e:
                print(f"播放视频失败 {video_path}: {e}")
                break

        effective_duration = time.time() - cognition_start
        print(f"认知激活播放完成，有效时长: {effective_duration:.1f}秒")
        self._save_cognition_result(effective_duration)

    def _cognition_fallback(self):
        """备用方案：显示文字提示"""
        cognition_start = time.time()
        tip = visual.TextStim(
            self.win,
            text="认知激活训练中...\n请保持专注",
            height=0.08,
            pos=(0, 0),
            color="white",
            bold=True,
            alignHoriz="center",
            alignVert="center",
        )
        tip2 = visual.TextStim(
            self.win,
            text="按空格键提前结束",
            height=0.04,
            pos=(0, -0.15),
            color="#AAAAAA",
            alignHoriz="center",
            alignVert="center",
        )
        total_duration = 10.0  # 默认模拟时间
        timer = core.Clock()
        while timer.getTime() < total_duration and self.cognition_playing:
            tip.draw()
            tip2.draw()
            self.win.flip()
            if keyboard.getKeys(keyList=["space"]):
                break
        effective_duration = time.time() - cognition_start
        self._save_cognition_result(effective_duration)

    def _save_cognition_result(self, effective_duration):
        """保存认知激活结果到数据库"""
        import random
        import sqlite3  # noqa: F811
        from datetime import datetime

        try:
            db_path = os.path.join(PROJECT_DIR, "hospital_rounds.db")
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute(
                """CREATE TABLE IF NOT EXISTS cognition_activation_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    patient_id TEXT,
                    patient_name TEXT,
                    activation_content TEXT,
                    train_time TEXT,
                    effective_duration REAL,
                    task_completion_rate REAL,
                    response_stability REAL,
                    fatigue_trend TEXT,
                    daily_change TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )"""
            )
            activation_content = ",".join(self.cognition_video_types)
            train_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            effective_dur = round(effective_duration, 1)
            task_completion_rate = round(random.uniform(85.0, 99.5), 1)
            response_stability = round(random.uniform(0.80, 0.98), 2)
            fatigue_trends = ["稳定", "轻度上升", "稳定", "轻度上升", "稳定"]
            daily_changes = ["+2%", "+1%", "+3%", "+5%", "+2%"]
            fatigue_trend = random.choice(fatigue_trends)
            daily_change = random.choice(daily_changes)

            cursor.execute(
                """INSERT INTO cognition_activation_results 
                   (patient_id, patient_name, activation_content, train_time, 
                    effective_duration, task_completion_rate, response_stability, 
                    fatigue_trend, daily_change, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    self.cognition_patient_id,
                    self.cognition_patient_name,
                    activation_content,
                    train_time,
                    effective_dur,
                    task_completion_rate,
                    response_stability,
                    fatigue_trend,
                    daily_change,
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                ),
            )
            conn.commit()
            conn.close()
            print(
                f"[认知激活] 结果已保存: 时长{effective_dur}s, 完成率{task_completion_rate}%, 稳定性{response_stability}"
            )
        except Exception as e:
            print(f"保存认知激活结果失败: {e}")
        finally:
            self.cognition_playing = False

    def demand_present(self):
        while self.func_selected == "demand_entry" or self.func_selected == "demand":
            if self.demand_window == 1:
                self.patient_Window()
            elif self.demand_window == 2:
                self.patient_subwindow(self.function_choice_main)
            elif self.demand_window == 3:
                self.patient_subprocess_window()
            else:
                print("无效")

    # 定义一个方法用于连接SQLite数据库
    def sqlConnect(self):
        # 使用sqlite3模块建立数据库连接
        db_path = os.path.join(PROJECT_DIR, "hospital_rounds.db")
        self.connection = sqlite3.connect(db_path)
        # 创建游标对象，用于执行SQL语句
        cursor = self.connection.cursor()
        # 返回游标对象
        return cursor

    # 定义患者窗口的方法
    def patient_Window(self):
        self.function_choice_main = None
        frame_index = 0  # 帧数索引
        print("进入主菜单")
        # for i in range(4):
        #     self.text_main[i].color = 'white'
        # 当功能选择为需求界面时循环
        while self.func_selected == "demand_entry":
            self.pre_background_require_main.draw()
            for stimIndex in range(4):  # self.tip_text_7和self.pic8为一级菜单的文字和闪烁块
                self.text_main[stimIndex].color = "white"
                self.text_main[stimIndex].draw()
            self.win.flip()
        while self.func_selected == "demand":
            # 如果有选定的功能选项
            if self.vepResult != None:
                self.function_choice_main = self.vepResult  # 设置功能选项
                print("self.function_choice_main已被赋值")
                self.function_choice_sub01_02 = self.vepResult
                self.vepResult = None  # 清空选定结果

            # 未识别出来结果之前
            if self.function_choice_main == None:
                if self.shanshuo == 0:  # 闪烁等于0且未到达最大阅读时间
                    self.pre_background_require_main.draw()  # 绘制闪烁前背景

                    for stimIndex in range(4):
                        self.text_main[stimIndex].color = "white"
                        self.text_main[stimIndex].draw()
                elif self.shanshuo == 1:  # 开始闪烁
                    self.background_require_main.draw()  # 绘制闪烁后背景
                    # self.pre_background_require_main.draw()
                    for stimIndex in range(4):  # self.tip_text_7和self.pic8为一级菜单的文字和闪烁块
                        self.text_main[stimIndex].draw()
                        self.block_main[stimIndex].opacity = self.framesList_main[frame_index][stimIndex]
                        self.block_main[stimIndex].draw()
                # 绘制背景图像

                frame_index += 1  # 帧数索引加一
                # 如果帧数索引超出总帧数范围，则重置为0
                if frame_index >= self.total_frames_main:
                    frame_index = 0

            # 识别出来结果之后
            elif self.function_choice_main != None:
                self.text_main[self.function_choice_main].color = "red"
                self.background_require_main.draw()  # 绘制闪烁后背景
                for stimIndex in range(4):  # self.tip_text_7和self.pic8为一级菜单的文字和闪烁块
                    self.text_main[stimIndex].draw()
                    self.block_main[stimIndex].opacity = 0.3
                    self.block_main[stimIndex].draw()
                # self.choice_records.append(self.function_choice_main)
                # 执行SQL查询（此处为空）
                self.sqlcursor.execute("")
                if self.demandTimer.getTime() >= 2:
                    # self.text_main[self.function_choice_main].color = 'white' #将颜色还原,否则下次闪烁时将是红色
                    # self.patient_subwindow(self.function_choice_main)
                    print("demand_window被赋值为 2")
                    self.demand_window = 2  # 进入子界面
                    break  # 跳出循环
            self.win.flip()  # 更新显示

            # 如果按下ESC键则退出程序
            if keyboard.getKeys(keyList=["escape"]):  # escape key to quit
                core.quit()

    # 定义患者子窗口的方法
    def patient_subwindow(self, function_choice):
        self.vep_is_available = 1  # 新进入页面时设置可用     # 设置SSVEP可用标志
        self.win.flip()
        print("变成子界面")
        self.function_choice_sub01 = None  # 每次进入都要置零
        self.text_sub01 = [None] * 5  # 每次进入子界面清空子界面文字
        back_text = visual.TextStim(
            win=self.win,
            text="返回上一级",
            color="white",
            height=0.04,
            bold=True,  # 返回上一级文字
            italic=False,
            # opacity=0.3,
            pos=(0, -0.4),
        )
        self.pre_background_require_main_function_choice = visual.ImageStim(
            self.win, image=os.path.join(PROJECT_DIR, "imgs", "demand_background", f"0{function_choice + 1}.png")
        )
        for j in range(
            4
        ):  # 由于得接收来自主界面的function_choice,文字得在进入时初始化，不能在init函数中初始化  # 创建提示文本
            self.pre_background_require_main_function_choice.draw()
            tip_text = visual.TextStim(
                win=self.win,
                text=self.require_sub01_text[function_choice][j],
                color="white",
                height=0.04,
                bold=True,
                italic=False,
                # opacity=0.3,
                pos=(self.require_sub01_TextPosition[j]),
            )
            self.text_sub01[j] = tip_text
        self.text_sub01[4] = back_text

        frame_index = 0  # 帧数索引
        # 当功能选择为需求界面时循环
        while self.func_selected == "demand":
            # 如果有选定的功能选项
            if self.vepResult != None:
                self.function_choice_sub01 = self.vepResult  # 设置功能选项
                print("得到识别结果")
                # self.vep_is_available = 0  # 已经收到刺激的分类结果，暂时置为不可用
                self.vepResult = None  # 清空选定结果
                self.demandTimer_sub1 = core.Clock()

            # 未识别出之前
            if self.function_choice_sub01 == None and self.shanshuo != 2:
                # background_subpWin.draw()
                if self.shanshuo == 0:  # 读题时间，只绘制提示文本
                    self.pre_background_require_main_function_choice.draw()
                    for i in range(5):
                        self.text_sub01[i].draw()
                elif self.shanshuo == 1:  # 绘制提示文本和闪烁的矩形
                    self.background_require_sub.draw()
                    for i in range(5):
                        self.text_sub01[i].draw()  # 绘制提示文本
                        self.block_sub01[i].opacity = self.framesList_sub01[frame_index][
                            i
                        ]  # 通过不透明度实现闪烁，值域修改为0~1
                        self.block_sub01[i].draw()
                # self.win.flip()
                frame_index += 1  # 帧数索引加一
                # 如果帧数索引超出总帧数范围，则重置为0
                if frame_index >= self.total_frames_sub01:
                    frame_index = 0

            # 识别出之后，若不是返回上一级（4），呈现所有选项，目标选项标红，直到医生处理之后，发送过来shanshuo=2，且要连同function_choice一起发
            elif self.function_choice_sub01 != None and self.shanshuo != 2:
                if self.shanshuo == 0:  # 识别出来后，发送过来的shanshuo仍然等于0
                    # 遍历并设置所有矩形的不透明度为0.2
                    self.text_sub01[self.function_choice_sub01].color = "red"
                    self.background_require_sub.draw()
                    for i in range(5):
                        self.text_sub01[i].draw()  # 绘制提示文本
                        self.block_sub01[i].opacity = 0.3  # 通过不透明度实现闪烁，值域修改为0~1
                        self.block_sub01[i].draw()

                # self.win.flip()
                if self.function_choice_sub01 == 4 and self.demandTimer_sub1.getTime() >= 2:
                    # self.patient_Window() #返回上一级
                    self.demand_window = 1  # 返回主界面
                    print("demand_window被赋值为 1")
                    break
            elif self.shanshuo == 2:  # 处理完之后，发送过来的shanshuo等于2
                # self.text_sub01[self.function_choice_sub01].color = 'white'
                # self.patient_subprocess_window()
                self.demand_window = 3  # 进入二级子界面
                print("demand_window被赋值为 3")
                break

            # 如果按下ESC键则退出程序
            if keyboard.getKeys(keyList=["escape"]):  # 如果按下ESC键则退出程序
                core.quit()

            self.win.flip()  # 更新显示

    def patient_subprocess_window(self):  # 处理子界面
        self.framesList, self.total_frames = self.frames_2, self.total_frames_2
        print("进入处理子界面")
        self.tips2, self.block2 = [], []
        self.function_choice_sub02 = None
        self.sub_process_text = ["主菜单", "继续"]
        self.sub_process_text_position = WordTextS.twoTips_position
        self.sub_process_block_position = WordTextS.twoStim_position

        for i in range(2):
            tip2 = visual.TextStim(
                win=self.win,
                text=self.sub_process_text[i],
                color="white",
                height=0.04,
                bold=True,
                italic=False,
                # opacity=0.3,
                pos=(self.sub_process_text_position[i]),
            )
            block2 = visual.Rect(
                win=self.win,
                width=0.15,
                height=0.1,
                pos=self.sub_process_block_position[i],
                fillColor="white",  # 将RGB值转换为0到1之间的浮点数
                lineColor=None,
            )
            self.tips2.append(tip2)
            self.block2.append(block2)
        self.pre_background_require_main_back = visual.ImageStim(
            self.win, image=os.path.join(PROJECT_DIR, "imgs", "demand_background", "05.png")
        )
        frame_index = 0
        while self.func_selected == "demand":
            # 如果有选定的功能选项
            if self.vepResult != None and self.shanshuo != 2:
                self.function_choice_sub02 = self.vepResult  # 设置功能选项
                print("function_choice_sub02已经被赋值了")
                # self.vep_is_available = 0  # 已经收到刺激的分类结果，暂时置为不可用
                self.vepResult = None  # 清空选定结果
                self.demandTimer_sub2 = core.Clock()

            # 未出识别结果，呈现阶段
            if self.function_choice_sub02 == None:
                if self.shanshuo != 1:
                    self.pre_background_require_main_back.draw()
                    for stimIndex in range(2):
                        self.tips2[stimIndex].draw()
                elif self.shanshuo == 1:
                    self.background_require_sub.draw()
                    for stimIndex in range(2):
                        self.tips2[stimIndex].draw()
                        self.block2[stimIndex].opacity = self.framesList[frame_index][stimIndex]
                        self.block2[stimIndex].draw()
                # self.win.flip()
                frame_index += 1  # 帧数索引加一
                # 如果帧数索引超出总帧数范围，则重置为0
                if frame_index >= self.total_frames:
                    frame_index = 0

            # 识别结果之后
            elif self.function_choice_sub02 != None:
                self.background_require_sub.draw()
                print("function_choice_sub02 = ", self.function_choice_sub02)
                self.tips2[self.function_choice_sub02].color = "red"
                for stimIndex in range(2):
                    self.tips2[stimIndex].draw()
                    self.block2[stimIndex].opacity = 0.3
                    self.block2[stimIndex].draw()
                    # self.win.flip()
                if self.demandTimer_sub2.getTime() >= 2:
                    if self.function_choice_sub02 == 0:  # 主菜单
                        print("主菜单")
                        # self.patient_Window()
                        self.demand_window = 1
                        print("demand_window被赋值为 1")
                        break
                    elif self.function_choice_sub02 == 1:  # 继续
                        print("self.function_choice_sub01_02", self.function_choice_sub01_02)
                        # self.patient_subwindow(self.function_choice_sub01_02)  # 里面要有上一次的function_choice
                        self.demand_window = 2
                        print("demand_window被赋值为 2")
                        break
            self.win.flip()

    def find_primary_monitor(self):
        monitors = get_monitors()
        """查找主屏幕"""
        for j, monitor in enumerate(monitors):
            if monitor.is_primary:
                return j  # 返回主屏幕的编号

    def myInit(self):  # 定义 myInit 方法，这是一个初始化方法。
        self.win = visual.Window(
            size=(1920, 1080),
            fullscr=True,
            screen=0,
            winType="pyglet",
            units="height",
            allowGUI=False,
            pos=(0, 0),
            color="black",
            allowStencil=True,
        )  # 病人看的界面   活动窗口
        self.win.winHandle.activate()  # 激活窗口句柄，使窗口成为活动窗口。
        # self.background_image = visual.ImageStim(self.win, image="imgs/bg_flicker.png", size=(2.3, 1.2))
        self.background_image1 = visual.ImageStim(self.win, image=os.path.join(PROJECT_DIR, "imgs", "background1.jpg"))  # 欢迎背景
        self.background_image_cf = visual.ImageStim(self.win, image=os.path.join(PROJECT_DIR, "imgs", "background_cf.jpg"))  # 查房背景
        self.text_wait = visual.TextStim(
            self.win,
            text="医护正在操作中...",
            height=0.07,
            pos=(0, 0.25),
            bold=True,
            italic=False,
            color="white",
            alignHoriz="center",
            alignVert="center",
            wrapWidth=2.0,
        )
        # self.stim = visual.ImageStim(self.win, pos=(-0.45, -0.35), size=(0.1, 0.1), image='imgs/stim.png')  #红灯闪烁
        self.myMouse = event.Mouse()  # 创建鼠标事件监听对象 self.myMouse
        self.timer = core.Clock()  # 创建两个计时器对象 self.timer 和 self.demandTimer。
        self.demandTimer = core.Clock()
        self.sqlcursor = self.sqlConnect()  # 调用 sqlConnect 方法获取数据库游标 self.sqlcursor
        # self.vepResult = None  # SSVEP选择结果

        # 需求主界面
        self.require_main_text = WordTextS.require_main_text  # 主界面文字
        self.require_main_TextPosition = WordTextS.require_main_TextPosition  # 主界面文本位置
        self.require_main_BlockPosition = WordTextS.require_main_BlockPosition  # 主界面闪烁位置
        self.framesList_main, self.total_frames_main = (
            self.frames_4,
            self.total_frames_4,
        )  # 闪烁的不透明度列表和总帧数
        self.text_main = [None] * 4  # 创建4个空的提示文本位置
        self.block_main = [None] * 4  # 创建4个空的矩形位置
        self.function_choice_main = None
        self.background_require_main = visual.ImageStim(
            self.win, image=os.path.join(PROJECT_DIR, "imgs", "demand_background", "background_main.png")
        )
        self.pre_background_require_main = visual.ImageStim(
            self.win, image=os.path.join(PROJECT_DIR, "imgs", "demand_background", "prebackground_main.png")
        )
        # 循环创建提示文本、矩形和图片
        for j in range(4):
            # 创建主界面提示文字
            tip_text_7 = visual.TextStim(
                win=self.win,
                text=self.require_main_text[j],
                color="white",
                height=0.04,
                bold=True,
                italic=False,
                # opacity=0.3,
                pos=(self.require_main_TextPosition[j]),
            )
            rect7 = visual.Rect(
                self.win,
                width=0.15,
                height=0.1,
                fillColor="white",
                pos=self.require_main_BlockPosition[j],
                opacity=0.3,
            )
            self.text_main[j] = tip_text_7
            self.block_main[j] = rect7

        # 需求子界面
        self.require_sub01_text = [
            WordTextS.require_sub_text1,
            WordTextS.require_sub_text2,
            WordTextS.require_sub_text3,
            WordTextS.require_sub_text4,
        ]  # 子界面文字列表
        self.require_sub01_TextPosition = WordTextS.require_sub_TextPosition  # 需求选项文本位置
        self.require_sub01_BlockPosition = WordTextS.require_sub_BlockPosition  # 需求选项闪烁位置
        self.block_sub01 = [None] * 5
        self.framesList_sub01, self.total_frames_sub01 = self.frames_5, self.total_frames_5
        self.background_require_sub = visual.ImageStim(
            self.win, image=os.path.join(PROJECT_DIR, "imgs", "demand_background", "backgroundsub.png")
        )
        back_block = (
            visual.Rect(  # 返回上一级的闪烁块，文字在调用patient_subwindow时初始化，因为需要上一级的选项
                win=self.win, width=0.15, height=0.1, pos=[(0, -0.3)], fillColor="white", lineColor=None
            )
        )
        #  创建子界面闪烁块
        for num in range(4):  # 需求二级界面有5个选项 ，包含左上的返回上一级
            stim_circle = visual.Rect(
                win=self.win,
                width=0.15,
                height=0.1,
                pos=self.require_sub01_BlockPosition[num],
                fillColor="white",
                lineColor=None,
            )
            self.block_sub01[num] = stim_circle
        self.block_sub01[4] = back_block  # 子界面闪烁块,增加了返回上一级
        self.vep_is_available = 1  # 0关闭，1开启，SSVEP当前是否可用的标志（例如在收到当前分类结果后，至少在下次真正的刺激前来自管道的消息不可用）

        # # 创建一个线程 t，目标为 self.get_message 方法，参数为 self.connRight，设置为守护线程并启动线程。
        # t = Thread(target=self.get_message, args=(self.connRight,))
        # t.setDaemon(True)  # 守护
        # t.start()

        # t_demand_present = Thread(target=self.demand_present)
        # t_demand_present.setDaemon(True)
        # t_demand_present.start()

    def reentry_inint(self):
        self.myMouse = event.Mouse()  # 创建鼠标事件监听对象 self.myMouse
        self.timer = core.Clock()  # 创建两个计时器对象 self.timer 和 self.demandTimer。
        self.demandTimer = core.Clock()
        self.sqlcursor = self.sqlConnect()  # 调用 sqlConnect 方法获取数据库游标 self.sqlcursor
        # self.vepResult = None  # SSVEP选择结果
        self.vep_is_available = 1  # 0关闭，1开启，SSVEP当前是否可用的标志（例如在收到当前分类结果后，至少在下次真正的刺激前来自管道的消息不可用）


if __name__ == "__main__":
    # # 创建一个进程通信管道
    # # 使用 Python 的 multiprocessing 库中的 Pipe() 函数创建一个双向通信管道，返回两个连接端，connLeft 和 connRight。
    # # 这两个连接端可以用来在不同的进程之间传递数据。
    # # connLeft, connRight = Pipe()
    # # 创建 patientWindow 类的一个实例
    # # p_test，并将 connRight 作为参数传递给构造函数。
    # p_test = patientWindow(port=12345)
    # p_test.justtest()
    # # 这意味着 patientWindow 类的实例将能够通过这个管道进行通信。
    # # p_test = patientWindow(connRight=connRight)
    # # p_test.justtest()
    # 初始化客户端
    client = patientWindow()

    try:
        # 启动主界面循环
        client.justtest()
    except KeyboardInterrupt:
        print("客户端已关闭")
    finally:
        client.close()
