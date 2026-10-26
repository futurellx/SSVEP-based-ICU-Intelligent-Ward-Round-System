import eventlet
import atexit
import json
import logging
import os
import socket
import statistics
import threading
import csv
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Optional

from fbcca2.FBCCA2 import FBCCA2
from train.test import EEGClassifier
from wordTexts import WordTextS
from runtime_concurrency import SequencedRingBuffer

# 导入封装的类
from train.train import EEGTrainer

logging.basicConfig(format="%(asctime)s | %(levelname)s | %(message)s", level=logging.INFO)
import time
from flask import Flask, request, logging
from flask_socketio import SocketIO, emit

from FBCCA_Online.FBCCA import FBCCA

# ---------------------- 服务端代码 ----------------------····
from flask_socketio import emit
from threading import Lock
import numpy as np


# 客户端连接管理
def get_server_ip():
    hostname = socket.gethostname()
    ip_address = socket.gethostbyname(hostname)
    return ip_address


# 全局状态管理
processing_controls = {
    "authorized_clients": {},  # {eeg_client_sid: ProcessingContext}
    "pending_results": {},  # {doctor_sid: result}
    "lock": Lock(),
}
eeg_lock = Lock()
# 存储所有用户会话 {user_id: sid}
user_sessions = {}
session_lock = Lock()  # 确保线程安全
EEG_DATA = None
EEG_STREAM = SequencedRingBuffer(capacity=4096)
# clients = {}
app = Flask(__name__)
socketio = SocketIO(app, async_mode="eventlet", cors_allowed_origins="*")
status = None  # 放大器状态检测


@dataclass
class DoctorProfile:  # 医生连接的算法模式、患者 ID、阈值和运行状态
    """Configuration owned by one doctor Socket.IO session."""

    mode: str = "cca"
    patient_id: str = ""
    threshold: float = WordTextS.threshold
    running: bool = True
    classifier: EEGClassifier = field(default_factory=EEGClassifier)


@dataclass
class ProcessingContext:
    """All mutable recognition state for one authorized EEG session.
    每次识别授权创建独立 `ProcessingContext`，其中包含医生/EEG SID、任务 ID、目标数、剩余数据块、FBCCA 实例、EEGNet 分类器、算法队列、投票结果、序号统计和上下文锁。"""

    doctor_sid: str
    eeg_sid: str
    mode: str
    patient_id: str
    threshold: float
    stim_num: int
    remaining: int
    task_id: str
    classifier: EEGClassifier
    running: bool = True
    last_sequence: int = -1
    missing_blocks: int = 0
    cca_result: int = 0
    train_result: int = 0
    train_results: list = field(default_factory=list)
    eeg_queue: deque = field(default_factory=lambda: deque(maxlen=15))
    fbcca: FBCCA = field(default_factory=lambda: FBCCA(Nf=3))
    lock: threading.RLock = field(default_factory=threading.RLock)

    def reset_results(self) -> None:
        self.cca_result = 0
        self.train_result = 0
        self.train_results.clear()
        self.eeg_queue.clear()
        self.fbcca.init()


doctor_profiles: Dict[str, DoctorProfile] = {}
shutdown_event = threading.Event()
background_threads = set()
background_threads_lock = threading.Lock()


def _start_managed_thread(target, name: str) -> threading.Thread:
    def run_and_unregister():
        try:
            target()
        finally:
            with background_threads_lock:
                background_threads.discard(threading.current_thread())

    worker = threading.Thread(target=run_and_unregister, name=name, daemon=True)
    with background_threads_lock:
        background_threads.add(worker)
    worker.start()
    return worker


def _shutdown_runtime() -> None:
    shutdown_event.set()
    EEG_STREAM.close()
    with background_threads_lock:
        workers = list(background_threads)
    current = threading.current_thread()
    for worker in workers:
        if worker is not current:
            worker.join(timeout=2.0)


atexit.register(_shutdown_runtime)


def _remove_context(eeg_sid: str, expected: Optional[ProcessingContext] = None) -> None:
    """Remove an authorization exactly once under the registry lock."""

    with processing_controls["lock"]:
        current = processing_controls["authorized_clients"].get(eeg_sid)
        if current is not None and (expected is None or current is expected):
            processing_controls["authorized_clients"].pop(eeg_sid, None)


def _map_train_result(raw_result: int, stim_num: int) -> int:
    """Map the eight-class model output to the active target layout."""

    if stim_num == 2:
        return {1: 1, 5: 2}.get(raw_result, 0)
    if stim_num == 3:
        return {1: 1, 3: 2, 5: 3}.get(raw_result, 0)
    if stim_num == 4:
        return {1: 1, 3: 2, 5: 3, 7: 4}.get(raw_result, 0)
    return raw_result if 1 <= raw_result <= stim_num else 0


# 配置参数（平衡性能与可靠性）
WAIT_DATA_TIMEOUT = 10  # 等待EEG数据超时时间（秒）
SOCKET_SLEEP_INTERVAL = 1e-5  # Socket等待间隔
CSV_FMT_PRECISION = "%.6f"  # CSV数据精度


# 原handle_start_processing修改如下
@socketio.on("start_processing")
def handle_start_processing(json_data):
    doctor_sid = request.sid
    target_client_id = json_data.get("target")
    max_count = max(1, int(json_data.get("count", 150)))
    stim_num = int(json_data.get("stim_num", 2))
    task_id = str(json_data.get("task_id") or f"{doctor_sid}:{time.time_ns()}")
    if not 2 <= stim_num <= 8:
        emit("error", {"msg": "刺激目标数必须在2到8之间"}, room=doctor_sid)
        return

    with session_lock:
        profile = doctor_profiles.get(doctor_sid, DoctorProfile())
        target_sid = user_sessions.get(target_client_id)
    if not target_sid:
        emit("error", {"msg": "目标客户端不在线"}, room=doctor_sid)
        return

    context = ProcessingContext(
        doctor_sid=doctor_sid,
        eeg_sid=target_sid,
        mode=profile.mode,
        patient_id=profile.patient_id,
        threshold=profile.threshold,
        stim_num=stim_num,
        remaining=max_count,
        task_id=task_id,
        classifier=profile.classifier,
        running=profile.running,
    )
    context.fbcca.retarget(stim_num)
    with processing_controls["lock"]:
        processing_controls["authorized_clients"][target_sid] = context
    emit("status_update", {"status": f"已授权{max_count}次处理"}, room=doctor_sid)


@socketio.on("eeg")  # 处理采集软件发送的eeg数据
def handle_eeg(data):
    global EEG_DATA
    client_sid = request.sid
    try:
        eeg_data = np.array(data["eeg"]).T
        if eeg_data.ndim != 2 or eeg_data.size == 0:
            raise ValueError("EEG数据必须是非空二维数组")

        raw_sequence = data.get("sequence")
        sequence = int(raw_sequence) if raw_sequence is not None else None
        acquired_at_ns = int(data.get("acquired_at_ns", time.time_ns()))
        stream_block = EEG_STREAM.publish(eeg_data.copy(), sequence, acquired_at_ns)
        with eeg_lock:
            EEG_DATA = eeg_data.copy()

        with processing_controls["lock"]:
            context = processing_controls["authorized_clients"].get(client_sid)
            if context is None or context.remaining <= 0:
                emit("error", {"msg": "未获得处理授权"}, room=client_sid)
                return

        with context.lock:
            if not context.running:
                context.remaining = 0
                context.reset_results()
                _remove_context(client_sid, context)
                return

            # Reject duplicate/out-of-order packets and account for gaps.
            source_sequence = (
                stream_block.source_sequence
                if stream_block.source_sequence is not None
                else stream_block.sequence
            )
            if context.last_sequence >= 0:
                if source_sequence <= context.last_sequence:
                    return
                context.missing_blocks += max(0, source_sequence - context.last_sequence - 1)
            context.last_sequence = source_sequence

            result = -1
            context.remaining -= 1

            if context.mode in ("cca", "both_cca_train"):
                cca_value = context.fbcca.queueOpt(
                    eeg_data,
                    context.threshold,
                    context.mode != "both_cca_train",
                )
                if cca_value is not None and cca_value >= 0:
                    context.cca_result = int(cca_value)

            if context.mode in ("train", "both_cca_train"):
                context.eeg_queue.append(eeg_data)
                if len(context.eeg_queue) == context.eeg_queue.maxlen:
                    raw_train_result = context.classifier.process_data(
                        context.eeg_queue, context.patient_id
                    )
                    mapped = _map_train_result(raw_train_result or 0, context.stim_num)
                    if mapped:
                        context.train_results.append(mapped)
                        context.train_results = context.train_results[-10:]

            finished = False
            if context.mode == "cca" and 1 <= context.cca_result <= context.stim_num:
                result = context.cca_result
                finished = True
            elif len(context.train_results) >= 10:
                voted = int(statistics.mode(context.train_results))
                if context.mode == "train":
                    result = voted
                    finished = True
                elif context.mode == "both_cca_train" and voted == context.cca_result:
                    result = voted
                    finished = True

            if finished:
                context.remaining = 0

            remaining = context.remaining
            doctor_sid = context.doctor_sid
            missing_blocks = context.missing_blocks

        emit(
            "processing_result",
            {
                "result": int(result),
                "remaining": remaining,
                "sequence": source_sequence,
                "missing_blocks": missing_blocks,
                "latency_ms": round(
                    max(0, stream_block.received_at_ns - stream_block.acquired_at_ns) / 1e6,
                    3,
                ),
                "task_id": context.task_id,
            },
            room=doctor_sid,
        )

        if remaining <= 0:
            _remove_context(client_sid, context)
            emit("status_update", {"status": "本次处理完成"}, room=doctor_sid)

    except Exception as e:
        print(f"EEG数据处理失败: {str(e)}")
        with processing_controls["lock"]:
            context = processing_controls["authorized_clients"].get(client_sid)
        if context is not None:
            emit("error", {"msg": f"处理失败: {str(e)}"}, room=context.doctor_sid)
            _remove_context(client_sid, context)
        emit("error", {"msg": "数据处理错误"}, room=client_sid)


@socketio.on("connect")
def handle_connect():
    print(f"新连接: {request.sid}")


@socketio.on("disconnect")
def handle_disconnect():
    disconnected_sid = request.sid
    with session_lock:
        for cid, sid in list(user_sessions.items()):
            if sid == disconnected_sid:
                user_sessions.pop(cid, None)
                print(f"客户端断开: {cid}")
                break
        doctor_profiles.pop(disconnected_sid, None)
    _remove_context(disconnected_sid)
    with processing_controls["lock"]:
        stale_eeg_sessions = [
            eeg_sid
            for eeg_sid, context in processing_controls["authorized_clients"].items()
            if context.doctor_sid == disconnected_sid
        ]
        for eeg_sid in stale_eeg_sessions:
            processing_controls["authorized_clients"].pop(eeg_sid, None)


@socketio.on("register")
def handle_register(user_id):
    with session_lock:
        user_sessions[user_id] = request.sid  # 保存映射关系
        print(f"用户 {user_id} 已注册，会话ID: {request.sid}")


@socketio.on("private_msg")
def handle_private_msg(data):
    """处理私有消息"""
    target_id = data["target"]
    message = data["message"]
    sender_sid = request.sid
    if "running" in message:
        running = bool(message.pop("running"))
        with session_lock:
            profile = doctor_profiles.setdefault(sender_sid, DoctorProfile())
            profile.running = running
        with processing_controls["lock"]:
            owned_contexts = [
                context
                for context in processing_controls["authorized_clients"].values()
                if context.doctor_sid == sender_sid
            ]
        for context in owned_contexts:
            with context.lock:
                context.running = running
    # 查找发送者ID
    sender_list = [k for k, v in user_sessions.items() if v == sender_sid]
    if not sender_list:
        # 发送者会话已失效（可能已断开），忽略该消息
        return
    sender_id = sender_list[0]

    if target_id in user_sessions:
        # 构造完整消息
        full_msg = {"from": sender_id, "message": message, "timestamp": time.time()}
        # 发送给目标客户端
        emit("private_msg", full_msg, room=user_sessions[target_id])
    else:
        emit("error", {"msg": f"目标客户端 {target_id} 不存在"}, room=sender_sid)


@socketio.on("train")
def handle_train(data):
    print("开始训练")
    print(data)
    patient_id = data["patient_id"].strip()  # 去除患者 ID 两端的空格
    print("当前患者ID:", patient_id)

    turn_count = WordTextS.turn_count  # 训练轮数
    target_count = WordTextS.target_count  # 目标数
    flash_time = WordTextS.flash_time  # 每个目标闪烁时间，单位：秒
    sample_rate = WordTextS.sample_rate  # 采样率，单位：Hz
    samples_per_flash = int(flash_time * sample_rate)  # 每个目标闪烁的采样点数

    pre_welcome_wait = WordTextS.pre_welcome_wait  # 欢迎提示显示时间，单位：秒
    pre_experiment_wait = WordTextS.pre_experiment_wait  # 实验开始前提示时间，单位：秒
    pre_flash_wait = WordTextS.pre_flash_wait  # 每个目标闪烁前预热时间，单位：秒
    post_flash_rest = WordTextS.post_flash_rest  # 每个目标闪烁后休息时间，单位：秒

    latest_block = EEG_STREAM.latest
    if latest_block is None:
        emit("error", {"msg": "EEG数据流尚未就绪"}, room=request.sid)
        return
    channel_num = latest_block.payload.shape[0]
    capture_after_sequence = latest_block.sequence

    # 计算训练总时长
    total_duration = (
        pre_welcome_wait
        + pre_experiment_wait
        + turn_count * (target_count * (pre_flash_wait + flash_time + post_flash_rest))
    )

    def extract_four_dim_data(full_signal_data):
        """
        依据实验范式从完整信号数据中截取四维训练数据。

        :param full_signal_data: 完整的 EEG 信号数据，格式为采样点数*通道数
        :return: 四维训练数据，格式为通道数*采样点数*目标数*块数
        """
        # 初始化存储训练数据的数组
        all_train_data = np.zeros((channel_num, samples_per_flash, target_count, turn_count))

        # 跳过欢迎提示和实验开始前等待时间对应的采样点
        skip_samples = int((pre_welcome_wait + pre_experiment_wait) * sample_rate)
        index = skip_samples

        for block in range(turn_count):
            for target in range(target_count):
                # 跳过每个目标闪烁前的预热时间对应的采样点
                index += int(pre_flash_wait * sample_rate)

                # 截取当前目标闪烁时间对应的采样点
                end_index = index + samples_per_flash
                current_flash_data = np.array(full_signal_data[index:end_index]).T

                # 将数据存入对应的数组位置
                all_train_data[:, :, target, block] = current_flash_data

                # 更新索引，跳过每个目标闪烁后休息时间对应的采样点
                index = end_index + int(post_flash_rest * sample_rate)

        return all_train_data

    def save_full_signal():
        full_signal_data = []
        start_time = time.time()
        print("记录数据开始时间:", datetime.now().strftime("%H:%M:%S.%f")[:-3])
        target_blocks = int(total_duration) * 5
        last_sequence = capture_after_sequence
        captured_blocks = 0
        deadline = time.monotonic() + total_duration + 15
        while (
            captured_blocks < target_blocks
            and time.monotonic() < deadline
            and not shutdown_event.is_set()
        ):
            blocks = EEG_STREAM.wait_after(last_sequence, timeout=1.0)
            for block in blocks:
                chunk = block.payload.T
                full_signal_data.extend(chunk.tolist())
                last_sequence = block.sequence
                captured_blocks += 1
                if captured_blocks >= target_blocks:
                    break

        if captured_blocks < target_blocks:
            print(f"训练采集超时: 期望{target_blocks}块，实际{captured_blocks}块")
            return

        print("记录数据结束时间:", datetime.now().strftime("%H:%M:%S.%f")[:-3])
        print("总耗时:", time.time() - start_time, "秒")

        # 生成保存文件的路径
        train_data_dir = os.path.join(os.getcwd(), "train_data", patient_id)
        # 确保文件夹存在
        os.makedirs(train_data_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        # 修改 CSV 文件命名，加上训练总时长
        csv_file_name = f"{int(total_duration)}s_{timestamp}_{patient_id}.csv"
        csv_file_path = os.path.join(train_data_dir, csv_file_name)

        # 保存数据到 CSV 文件，确保数据为数值类型
        with open(csv_file_path, "w", newline="") as csvfile:
            writer = csv.writer(csvfile)
            for row in full_signal_data:
                writer.writerow([float(val) for val in row])
        print(f"完整信号数据已保存到 {csv_file_path}")

        # 调用函数截取四维数据
        four_dim_data = extract_four_dim_data(full_signal_data)

        # 保存四维数据到 .npy 文件
        npy_file_name = f"{patient_id}.npy"
        npy_file_path = os.path.join(train_data_dir, npy_file_name)
        np.save(npy_file_path, four_dim_data)
        # 额外输出 npy 数据的维度
        print(f"四维训练数据已保存到 {npy_file_path}，数据维度为 {four_dim_data.shape}")

        # 训练
        trainer = EEGTrainer(DATA_NAME=patient_id, WINDOW_SIZE=750)
        val_acc, _ = trainer.train()
        if val_acc > 0.8:
            print("模型准确率大于0.8,可用，为：", val_acc)
        else:
            print("模型准确率小于0.8,不建议使用，为：", val_acc)

    # 在新线程中启动保存完整信号数据
    _start_managed_thread(save_full_signal, "eeg-training-capture")


@socketio.on("searchBestFrequencies")
def handle_searchBestFrequencies(data):
    print("[DEBUG handle_searchBestFrequencies] 收到搜索最佳频率请求")
    print("[DEBUG handle_searchBestFrequencies] data:", data)
    doctor_sid = request.sid  # 记录医生端 SID，搜索完成后回传通知
    print(f"[DEBUG handle_searchBestFrequencies] doctor_sid: {doctor_sid}")

    config = WordTextS.SearchBestFrequencies
    frequency_sequence = config.frequency_sequence()
    repetitions = max(1, config.repetitions)
    flash_time = config.flash_duration
    sample_rate = WordTextS.sample_rate

    if not frequency_sequence:
        print("frequency_sequence 为空，终止频率搜索流程")
        return

    try:
        patient_id = data.get("patient_id", "").strip() or "anonymous"
    except Exception:
        patient_id = "anonymous"
    print("当前患者ID:", patient_id)

    samples_per_flash = int(flash_time * sample_rate)

    pre_welcome_wait = WordTextS.pre_welcome_wait
    pre_experiment_wait = WordTextS.pre_experiment_wait
    pre_flash_wait = WordTextS.pre_flash_wait
    post_flash_rest = WordTextS.post_flash_rest

    total_trials = len(frequency_sequence) * repetitions
    total_duration = (
        pre_welcome_wait
        + pre_experiment_wait
        + total_trials * (pre_flash_wait + flash_time + post_flash_rest)
    )

    latest_block = EEG_STREAM.latest
    if latest_block is None:
        print("无法获取 EEG 通道数，终止本次频率搜索流程")
        return
    channel_num = latest_block.payload.shape[0]
    capture_after_sequence = latest_block.sequence

    def extract_frequency_data(full_signal_data):
        """按照单块频率扫描范式，将完整信号整理为四维数据。"""

        dataset = np.zeros((channel_num, samples_per_flash, len(frequency_sequence), repetitions))

        skip_samples = int((pre_welcome_wait + pre_experiment_wait) * sample_rate)
        index = skip_samples

        for freq_idx, _ in enumerate(frequency_sequence):
            for rep_idx in range(repetitions):
                index += int(pre_flash_wait * sample_rate)
                end_index = index + samples_per_flash
                current_flash = np.array(full_signal_data[index:end_index]).T
                dataset[:, :, freq_idx, rep_idx] = current_flash
                index = end_index + int(post_flash_rest * sample_rate)

        return dataset

    # 跨线程通信：queue.Queue + eventlet 轮询
    # eventlet.event.Event 从原生线程 send() 无法唤醒 Hub，故用 queue
    import queue

    completion_queue = queue.Queue()

    def save_full_signal():
        full_signal_data = []
        start_time = time.time()
        print("频率搜索数据记录开始:", datetime.now().strftime("%H:%M:%S.%f")[:-3])

        # 记录时长按训练模式的方式放大采样，提升取数成功率
        fetch_counter = int(total_duration) * 5 if total_duration > 0 else 0
        last_sequence = capture_after_sequence
        deadline = time.monotonic() + total_duration + 15
        while fetch_counter > 0 and time.monotonic() < deadline and not shutdown_event.is_set():
            blocks = EEG_STREAM.wait_after(last_sequence, timeout=1.0)
            for block in blocks:
                chunk = block.payload.T
                full_signal_data.extend(chunk.tolist())
                last_sequence = block.sequence
                fetch_counter -= 1
                if fetch_counter <= 0:
                    break

        if fetch_counter > 0:
            print(f"频率搜索采集超时，缺少{fetch_counter}个数据块")
            completion_queue.put((doctor_sid, patient_id, None))
            return

        print("频率搜索数据记录结束:", datetime.now().strftime("%H:%M:%S.%f")[:-3])
        print("总耗时:", time.time() - start_time, "秒")

        base_dir = os.path.join(os.getcwd(), "search_results", patient_id)
        os.makedirs(base_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")

        csv_path = os.path.join(
            base_dir,
            f"freqscan_{int(total_duration)}s_{timestamp}_{patient_id}.csv",
        )
        # with open(csv_path, "w", newline="") as csvfile:
        #     writer = csv.writer(csvfile)
        #     for row in full_signal_data:
        #         writer.writerow([float(val) for val in row])
        # print(f"完整频率搜索信号保存至 {csv_path}")

        freq_data = extract_frequency_data(full_signal_data)
        npy_path = os.path.join(base_dir, f"freqscan_{timestamp}_{patient_id}.npy")
        # np.save(npy_path, freq_data)
        print(f"频率搜索切片数据保存至 {npy_path}，形状为 {freq_data.shape}，频率序列: {frequency_sequence}")

        meta_path = os.path.join(base_dir, f"freqscan_{timestamp}_{patient_id}_meta.json")
        search_result, all_results = search_frequency(frequency_sequence, repetitions, flash_time, freq_data)
        meta = {
            "patient_id": patient_id,
            "timestamp": timestamp,
            "frequency_sequence": frequency_sequence,
            "repetitions": repetitions,
            "flash_time": flash_time,
            "pre_welcome_wait": pre_welcome_wait,
            "pre_experiment_wait": pre_experiment_wait,
            "pre_flash_wait": pre_flash_wait,
            "post_flash_rest": post_flash_rest,
            "sample_rate": sample_rate,
            "all_results": np.array(all_results).tolist(),
        }
        # with open(meta_path, "w", encoding="utf-8") as meta_file:
        #     json.dump(meta, meta_file, ensure_ascii=False, indent=2)

        result_path = os.path.join(base_dir, "frequencies.json")
        # if search_result is not None:
        #     with open(result_path, "w", encoding="utf-8") as result_file:
        #         json.dump({"search_result": search_result}, result_file, ensure_ascii=False, indent=2)
        #     print(f"频率搜索元信息保存至 {meta_path}")
        # else:
        #     print("搜索结果错误，请检查输入信号")
        # 注意：频率搜索只返回最佳频率（如 [35]），不足以填充完整的频率列表
        # reAllTarget 需要完整的频率列表才能正常工作，当前跳过此调用
        # 如需个性化频率，应在后续版本中完善频率搜索逻辑
        # fbcca.reAllTarget(search_result)

        # 线程完成数据采集，通过 queue 通知事件循环
        print("[DEBUG save_full_signal] 数据采集完成，放入 queue 通知事件循环...")
        completion_queue.put((doctor_sid, patient_id, search_result))
        print("[DEBUG save_full_signal] 已放入 queue")

    def _emit_when_done():
        """在主 eventlet 事件循环中轮询 queue，等待数据采集线程完成后 emit"""
        print("[DEBUG _emit_when_done] 开始轮询 queue 等待数据采集完成...")
        while not shutdown_event.is_set():
            eventlet.sleep(0.5)  # 每 500ms 检查一次，不阻塞事件循环
            try:
                doctor_sid, patient_id, search_result = completion_queue.get_nowait()
            except queue.Empty:
                continue
            print("[DEBUG _emit_when_done] 从 queue 收到结果，开始 emit search_complete...")
            print(
                f"[DEBUG _emit_when_done] doctor_sid={doctor_sid}, patient_id={patient_id}, frequencies={search_result}"
            )
            socketio.emit(
                "search_complete",
                {
                    "patient_id": patient_id,
                    "frequencies": search_result,
                    "status": "已找到用户最佳刺激",
                },
                room=doctor_sid,
            )
            print("[DEBUG _emit_when_done] search_complete 已 emit!")
            print(f"已通知医生端算法个性化校准完成，患者ID:{patient_id}，最佳频率:{search_result}")
            break

    # 在 eventlet 协程中启动监听器（等待数据采集完成并 emit）
    socketio.start_background_task(_emit_when_done)
    # 在独立线程中执行数据采集（不阻塞 eventlet 事件循环）
    _start_managed_thread(save_full_signal, "frequency-calibration-capture")


@socketio.on("change_frequencies")
def handle_change_frequencies(data):
    # try:
    #     patient_id = data.get("patient_id").strip()  # 获取病人ID
    #     base_dir = os.path.join(os.getcwd(), "search_results", patient_id)
    #     result_path = os.path.join(base_dir, "frequencies.json")
    #     result = json.load(open(result_path, "r", encoding="utf-8"))["search_result"]
    #     fbcca.reAllTarget(result)
    #     print("算法更改频率为:", result)
    # except Exception as e:
    #     print("错误:", e)
    frequency_list2 = [34] + WordTextS.frequency_list2
    frequency_list3 = [34] + WordTextS.frequency_list3
    frequency_list4 = [34] + WordTextS.frequency_list4
    frequency_list5 = [34] + WordTextS.frequency_list5
    frequency_list6 = [34] + WordTextS.frequency_list6
    frequency_list7 = [34] + WordTextS.frequency_list7
    frequency_list8 = [34] + WordTextS.frequency_list8
    all_targets = [
        frequency_list2,
        frequency_list3,
        frequency_list4,
        frequency_list5,
        frequency_list6,
        frequency_list7,
        frequency_list8,
    ]
    with processing_controls["lock"]:
        contexts = [
            context
            for context in processing_controls["authorized_clients"].values()
            if context.doctor_sid == request.sid
        ]
    for context in contexts:
        with context.lock:
            context.fbcca.all_targets = all_targets


def search_frequency(frequency_sequence, repetitions, flash_time, freq_data):
    # 这里实现具体的频率搜索逻辑
    print("搜索频率:", frequency_sequence)
    print("重复次数:", repetitions)
    print("闪烁时间:", flash_time)
    results = []
    for freq_index, freq in enumerate(frequency_sequence):
        result = []
        for rep in range(repetitions):
            frequencySearchAlgorithm = FBCCA2(
                n_filter_bank=2,
                targets_list=[freq],
                notch_frequency=50,
                window_size=750,
                sample_rate=250,
                notch_quality_factor=30,
                low_cutoff_frequency=95,
            )
            r = frequencySearchAlgorithm.compute_fbcca_correlation(freq_data[:, :, freq_index, rep].T)
            if r is None:
                return None
            result.append(r)

        results.append(np.array(result).mean())
        print("频率搜索完成")
    ranked_pairs = sorted(enumerate(results), key=lambda item: item[1], reverse=True)
    top_pairs = ranked_pairs[: min(8, len(ranked_pairs))]
    top_indices = [idx for idx, _ in top_pairs]
    top_frequencies = [frequency_sequence[idx] for idx in top_indices]
    print("Top 8 frequency values:", top_frequencies)

    return top_frequencies, results


@socketio.on("model")
def get_model(data):
    mode = data.get("mode", "cca")
    if mode not in ("cca", "train", "both_cca_train"):
        emit("error", {"msg": f"不支持的算法模式: {mode}"}, room=request.sid)
        return
    patient_id = (data.get("patient_id") or "").strip()
    threshold = float(data.get("threshold", WordTextS.threshold))
    with session_lock:
        existing = doctor_profiles.get(request.sid)
        doctor_profiles[request.sid] = DoctorProfile(
            mode=mode,
            patient_id=patient_id,
            threshold=threshold,
            running=True,
            classifier=existing.classifier if existing is not None else EEGClassifier(),
        )
    print(f"会话配置已更新: patient={patient_id}, mode={mode}, threshold={threshold}")


if __name__ == "__main__":
    server_ip = get_server_ip()
    print(f"服务器启动在: {server_ip}:9999")
    socketio.run(app, host="0.0.0.0", port=9999)
