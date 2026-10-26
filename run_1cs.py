import decimal
import math
import multiprocessing
import os
import random
import re
import queue
import socket
import struct
import time
from datetime import datetime, timedelta
from functools import partial
from io import BytesIO
from math import floor
from multiprocessing import Process, Pipe
import sys
from queue import Queue
from datetime import datetime
import pandas as pd
import psutil
import socketio
from matplotlib import pyplot as plt, rcParams
from ratelimiter import RateLimiter
from PyQt5.QtGui import QPixmap
from Screen_Click import ScreenController
from wordTexts import WordTextS
from runtime_concurrency import BoundedMessageQueue, QueueClosed
import threading
import sqlite3
from PyQt5 import QtCore, QtWidgets, QtGui
from PyQt5.QtCore import (
    QTimer,
    QTime,
    QDate,
    Qt,
    QMetaObject,
    Q_ARG,
    pyqtSlot,
    pyqtSignal,
    QStringListModel,
    QItemSelectionModel,
)
from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QPushButton,
    QTableWidgetItem,
    QAbstractItemView,
    QFileDialog,
    QMessageBox,
)
from scipy import signal
from collections import deque
from 查房主界面 import Ui_main_ui
from 查房 import Ui_cf_ui
from 认知激活 import Ui_cognition_ui
from 查询病人 import Ui_select_UI
from 问题界面 import Ui_question_UI
from 提示框 import Ui_notice_UI
from 选择框 import Ui_senoctice_UI
from 自动查房 import Ui_auto_cf_UI
from 导出框 import Ui_Results_UI


cf_test = 0  # 查房测试时设置为1，非测试请设置为0
record_time = 12000  # 自动查房每题回答时间（毫秒）
# record_time = 18000  # 自动查房每题回答时间（毫秒）休息
loop_count = 1  # 自动查房时，所有问题的循环次数，默认为1，即每个问题自动查一次
tag_open_eyes = 1  # 睁眼标志，默认睁眼
eeg_count = 150  # EEG数据接收最大次数 0.2s传输一次
# 全局变量，用于保存当前正在运行的线程和停止标志


def show_window_on_appropriate_screen(window):
    # 获取屏幕列表
    screens = QApplication.screens()
    if len(screens) > 1:
        # 选择第二个屏幕
        secondary_screen = screens[0]
        # secondary_screen = screens[0]
        # 获取屏幕的几何信息
        screen_geometry = secondary_screen.geometry()
        # 将窗口移动到副屏幕的中心
        window.move(screen_geometry.center() - window.rect().center())
    else:
        # 如果没有副屏幕，将窗口移动到主屏幕的中心
        primary_screen = screens[0]
        screen_geometry = primary_screen.geometry()
        window.move(screen_geometry.center() - window.rect().center())
    # 显示窗口
    window.show()


class SeDialog(QMainWindow, Ui_senoctice_UI):
    def __init__(self):
        super().__init__()
        self.setupUi(self)  # 初始化UI
        self.setWindowFlag(QtCore.Qt.FramelessWindowHint)  # 不显示窗体边框
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.pushButton_2.clicked.connect(
            lambda: self.onYesButtonClicked(doctorWin)
        )

    def onYesButtonClicked(self, doctorWin):
        try:
            # 如果是删除分类操作
            if doctorWin._is_category_delete:
                doctorWin._do_delete_category()
                return
            # 执行SQL语句
            doctorWin.sqlcursor.execute(doctorWin.sql, doctorWin.val)
            # 提交到数据库执行
            doctorWin.connection.commit()
            doctorWin.question_query()
            doctorWin.msg = NoticeWindow()
            doctorWin.msg.pushButton_3.setText("删除成功")
            show_window_on_appropriate_screen(doctorWin.msg)
            doctorWin.question_query()
            # 取消选中状态
            doctorWin.clear_selected_button()
        except Exception as e:
            # 发生错误时回滚
            doctorWin.connection.rollback()
            print("Error:", e)


class CategoryInputDialog(QMainWindow, Ui_senoctice_UI):
    """添加分类输入对话框，参照 QuestionWindow 风格，直接操作 doctorWin"""
    def __init__(self):
        super().__init__()
        self.setupUi(self)
        self.setWindowFlag(QtCore.Qt.FramelessWindowHint)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)

        # 修改标题
        self.label.setText("添加分类")

        # 隐藏原来的消息文本区，改为输入框
        self.pushButton_3.hide()

        # 创建输入框，宽度与 frame 中 pushButton_3 一致
        self.lineEdit = QtWidgets.QLineEdit(self.frame)
        self.lineEdit.setGeometry(QtCore.QRect(240, 130, 270, 64))
        self.lineEdit.setPlaceholderText("请输入新分类名称")
        self.lineEdit.setStyleSheet(
            "QLineEdit {"
            "    min-width: 300px;"
            "    max-width: 300px;"
            "    min-height: 64px;"
            "    max-height: 64px;"
            "    background: #EEEEEE;"
            "    border-radius: 12px;"
            "    border: none;"
            "    font-family: PingFangSC, PingFang SC;"
            "    font-weight: 400;"
            "    font-size: 24px;"
            "    color: #010408;"
            "    line-height: 40px;"
            "    text-align: left;"
            "    font-style: normal;"
            "    padding: 0 16px;"
            "}"
        )

        # 重新绑定确定按钮，参照 QuestionWindow 通过 doctorWin 操作数据库
        self.pushButton_2.clicked.disconnect()
        self.pushButton_2.clicked.connect(self._on_confirm)

    def _on_confirm(self):
        name = self.lineEdit.text().strip()
        if not name:
            return
        doctorWin.resql()
        doctorWin.sqlcursor.execute(
            "SELECT COALESCE(MAX(sequence), 0) FROM question_categories WHERE type = ?",
            (doctorWin.ty,),
        )
        max_seq = doctorWin.sqlcursor.fetchone()[0]
        doctorWin.sqlcursor.execute(
            "INSERT INTO question_categories (category_name, type, sequence) VALUES (?, ?, ?)",
            (name, doctorWin.ty, max_seq + 1),
        )
        doctorWin.connection.commit()
        doctorWin.question_query()
        self.close()


charge = None


class auto_CF_win(QMainWindow, Ui_auto_cf_UI):
    def __init__(self):
        super().__init__(doctorWin)
        self.setupUi(self)  # 初始化UI
        self.setWindowFlag(QtCore.Qt.FramelessWindowHint)  # 不显示窗体边框
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.doctorWin = doctorWin

        # 创建 QListView 和模型
        model = QStringListModel()
        self.pat_id = doctorWin.lineEdit_id.text()

        # 将结果转换为字符串列表
        data_list = [f"{item[1]}" for item in self.doctorWin.results]
        print(self.doctorWin.results)

        # 设置模型数据
        model.setStringList(data_list)

        # 设置 QListView 的模型
        self.listView_2.setModel(model)
        self.listView_2.setSelectionMode(QAbstractItemView.MultiSelection)  # 设置 QListView 的选择模式为多选

        # 按钮连接
        self.clear_button.clicked.connect(self.clear_selected_listview_item)
        self.clear_button.clicked.connect(self.save_rename)
        self.all_button.clicked.connect(self.select_all)
        self.invert_button.clicked.connect(self.invert_selection)
        self.filter_lineEdit.textChanged.connect(self.filter_listview)
        self.filter_lineEdit.textChanged.connect(self.clear_selected_listview_item)
        self.pushButton_2.clicked.connect(lambda: self.store_selected_primary_keys(0))
        self.pushButton_2.clicked.connect(lambda: self.auto_round(doctorWin.loop_count))  # 自动查房
        self.pushButton_4.clicked.connect(lambda: self.save_select(1, self.pat_id))  # 方案1
        self.pushButton_5.clicked.connect(lambda: self.save_select(2, self.pat_id))  # 方案2
        self.pushButton_6.clicked.connect(lambda: self.save_select(3, self.pat_id))  # 方案3

        self.selected_primary_keys = []

        # 初始化self.Result
        self.Result = []

    def auto_round(self, loop_count):
        listview_selected = len(self.listView_2.selectedIndexes()) > 0

        # 检查 checkBox_1 至 checkBox_5 是否有选中项
        checkboxes = [getattr(self, f"checkBox_{i}") for i in range(1, 6)]
        checkbox_selected = any(checkbox.isChecked() for checkbox in checkboxes)

        if not listview_selected and not checkbox_selected:
            # 若都未选中，调用 doctorWin 的错误弹窗
            self.doctorWin.error_notice("错误，未做任何选择")
            return
        try:
            doctorWin.set_buttons_disabled()
            doctorWin.pushButton_autocf.setText("暂停自动查房")
            self.loop_count = loop_count
            doctorWin.start_from_beginning()
            self.close()
        finally:
            # 在原有的基础上附加新选中的问题
            self.selected_questions = [
                question for question in self.doctorWin.results if question[1] in self.selected_primary_keys
            ]

            # 在这里附加从复选框选择中获取的相关问题
            self.selected_questions.extend(self.Result)  # 把之前查询得到的结果追加到 selected_questions

            # 启动自动执行
            doctorWin.stop_current_operation()
            doctorWin.start_auto_execution(self.loop_count, self.selected_questions)

    def auto_save(self, num):
        try:
            self.num = num
            self.primary_keys_str = (
                ";;;".join(self.selected_primary_keys) if self.selected_primary_keys else None
            )
            self.doctorWin.sqlcursor.execute(
                "SELECT * FROM auto_save WHERE id = ? AND pat_id = ?", (self.num, self.pat_id)
            )
            existing_record = self.doctorWin.sqlcursor.fetchone()
            if existing_record:
                self.doctorWin.sqlcursor.execute(
                    "UPDATE auto_save SET auto_name = ? WHERE id = ? AND pat_id = ?",
                    (self.primary_keys_str, self.num, self.pat_id),
                )
            else:
                self.doctorWin.sqlcursor.execute(
                    "INSERT INTO auto_save (id, pat_id, auto_name) VALUES (?, ?, ?)",
                    (self.num, self.pat_id, self.primary_keys_str),
                )
            self.doctorWin.connection.commit()
        except Exception as e:
            self.doctorWin.connection.rollback()
            print("Error:", e)

    def store_selected_primary_keys(self, num):
        # 检查 listView_2 是否有选中项
        listview_selected = len(self.listView_2.selectedIndexes()) > 0

        # 检查 checkBox_1 至 checkBox_5 是否有选中项
        checkboxes = [getattr(self, f"checkBox_{i}") for i in range(1, 6)]
        checkbox_selected = any(checkbox.isChecked() for checkbox in checkboxes)

        if not listview_selected and not checkbox_selected:
            # 若都未选中，调用 doctorWin 的错误弹窗
            self.doctorWin.error_notice("请至少选择一个列表项或一个复选框")
            return
        self.num = num
        selection_model = self.listView_2.selectionModel()
        selected_indices = selection_model.selectedIndexes()
        model = self.listView_2.model()
        self.selected_primary_keys = []
        for index in selected_indices:
            item = model.data(index, Qt.DisplayRole)
            primary_key = item
            self.selected_primary_keys.append(primary_key)
        self.auto_save(self.num)

        # 获取选中的 checkBox 并附加相应的问题
        self.check_selected_boxes()

    def clear_selected_listview_item(self):
        self.listView_2.clearSelection()

    def save_rename(self):
        self.pushButton_4.setText("展示方案1")
        self.pushButton_5.setText("展示方案2")
        self.pushButton_6.setText("展示方案3")

    def filter_listview(self):
        filter_text = self.filter_lineEdit.text()
        model = self.listView_2.model()
        for index in range(model.rowCount()):
            item = model.data(model.index(index, 0), Qt.DisplayRole)
            if filter_text.lower() in item.lower():
                self.listView_2.setRowHidden(index, False)
            else:
                self.listView_2.setRowHidden(index, True)
        self.pushButton_4.setText("展示方案1")
        self.pushButton_5.setText("展示方案2")
        self.pushButton_6.setText("展示方案3")
        if self.filter_lineEdit.text() != "":
            self.pushButton_4.setEnabled(False)
            self.pushButton_5.setEnabled(False)
            self.pushButton_6.setEnabled(False)
        else:
            self.pushButton_4.setEnabled(True)
            self.pushButton_5.setEnabled(True)
            self.pushButton_6.setEnabled(True)

    def load_selected_states_from_database(self, num, pat_id):
        try:
            self.pat_id = pat_id
            self.num = num
            self.doctorWin.sqlcursor.execute(
                "SELECT auto_name FROM auto_save WHERE id = ? AND pat_id = ?", (self.num, self.pat_id)
            )
            result = self.doctorWin.sqlcursor.fetchone()
            if result:
                primary_keys_str = result[0]
                if primary_keys_str:
                    primary_keys_list = primary_keys_str.split(";;;")  # 以;;;分割问题
                    model = self.listView_2.model()
                    selection_model = self.listView_2.selectionModel()
                    for index in range(model.rowCount()):
                        item_index = model.index(index, 0)
                        item = model.data(item_index, Qt.DisplayRole)
                        primary_key = item
                        if primary_key in primary_keys_list:
                            item_index = model.index(index, 0)
                            selection_model.select(item_index, QItemSelectionModel.Select)
        except Exception as e:
            print("Error loading selected states:", e)

    def select_all(self):
        model = self.listView_2.model()
        selection_model = self.listView_2.selectionModel()
        filter_text = self.filter_lineEdit.text()
        visible_row_indices = []
        for index in range(model.rowCount()):
            item = model.data(model.index(index, 0), Qt.DisplayRole)
            if not filter_text or (filter_text.lower() in item.lower()):
                visible_row_indices.append(index)
        for index in visible_row_indices:
            item_index = model.index(index, 0)
            selection_model.select(item_index, QItemSelectionModel.Select)

    def invert_selection(self):
        model = self.listView_2.model()
        selection_model = self.listView_2.selectionModel()
        filter_text = self.filter_lineEdit.text()
        visible_row_indices = []
        for index in range(model.rowCount()):
            item = model.data(model.index(index, 0), Qt.DisplayRole)
            if not filter_text or (filter_text.lower() in item.lower()):
                visible_row_indices.append(index)
        for index in visible_row_indices:
            item_index = model.index(index, 0)
            is_selected = selection_model.isSelected(item_index)
            if is_selected:
                selection_model.select(item_index, QItemSelectionModel.Deselect)
            else:
                selection_model.select(item_index, QItemSelectionModel.Select)

    def save_select(self, num, pat_id):
        self.pat_id = pat_id
        self.num = num
        if self.num == 1:
            if self.pushButton_4.text() == "展示方案1":
                self.pushButton_4.setText("另存为方案1")
                if self.pushButton_5.text() == "另存为方案2":
                    self.pushButton_5.setText("展示方案2")
                if self.pushButton_6.text() == "另存为方案3":
                    self.pushButton_6.setText("展示方案3")
                self.clear_selected_listview_item()
                self.load_selected_states_from_database(1, self.pat_id)
            elif self.pushButton_4.text() == "另存为方案1":
                self.pushButton_4.setText("展示方案1")
                self.store_selected_primary_keys(1)
        elif self.num == 2:
            if self.pushButton_5.text() == "展示方案2":
                self.pushButton_5.setText("另存为方案2")
                if self.pushButton_6.text() == "另存为方案3":
                    self.pushButton_6.setText("展示方案3")
                if self.pushButton_4.text() == "另存为方案1":
                    self.pushButton_4.setText("展示方案1")
                self.clear_selected_listview_item()
                self.load_selected_states_from_database(2, self.pat_id)
            elif self.pushButton_5.text() == "另存为方案2":
                self.pushButton_5.setText("展示方案2")
                self.store_selected_primary_keys(2)
        elif self.num == 3:
            if self.pushButton_6.text() == "展示方案3":
                self.pushButton_6.setText("另存为方案3")
                if self.pushButton_5.text() == "另存为方案2":
                    self.pushButton_5.setText("展示方案2")
                if self.pushButton_4.text() == "另存为方案1":
                    self.pushButton_4.setText("展示方案1")
                self.clear_selected_listview_item()
                self.load_selected_states_from_database(3, self.pat_id)
            elif self.pushButton_6.text() == "另存为方案3":
                self.pushButton_6.setText("展示方案3")
                self.store_selected_primary_keys(3)

    def check_selected_boxes(self):
        """检查复选框，若选中，则附加相应的问题到 Result 中"""
        checkboxes = {
            self.checkBox_1: 10,
            self.checkBox_2: 11,
            self.checkBox_3: 12,
            self.checkBox_4: 13,
            self.checkBox_5: 14,
        }

        for checkBox, question_type in checkboxes.items():
            if checkBox.isChecked():
                self.ty = question_type
                query = "SELECT * FROM questions WHERE type = ? ORDER BY sequence"
                self.doctorWin.sqlcursor.execute(query, (self.ty,))
                questions = self.doctorWin.sqlcursor.fetchall()
                self.Result.extend(questions)  # 将查询到的问题附加到 self.Result 中
        print(self.Result)


class Select_results_Window(QMainWindow, Ui_Results_UI):
    def __init__(self, doctorWin):
        super().__init__()
        self.setupUi(self)
        self.setWindowFlag(QtCore.Qt.FramelessWindowHint)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.doctorWin = doctorWin

        # 按钮事件绑定
        self.pushButton_2.clicked.connect(self.export_results)
        self.checkBox_9.clicked.connect(self.toggle_questionnaire_checkboxes)
        self.checkBox_10.clicked.connect(self.toggle_record_checkboxes)

        # 子复选框状态监听
        for i in range(1, 6):
            getattr(self, f"checkBox_{i}").stateChanged.connect(
                lambda state, idx=i: self.update_parent_checkbox(idx, 9)
            )
        for i in range(6, 9):
            getattr(self, f"checkBox_{i}").stateChanged.connect(
                lambda state, idx=i: self.update_parent_checkbox(idx, 10)
            )

        # 初始化全选按钮文本
        self.update_checkbox_text(self.checkBox_9)
        self.update_checkbox_text(self.checkBox_10)

        # 问卷类型映射
        self.question_ace = {
            "焦虑问卷": 1,
            "抑郁问卷": 2,
            "睡眠问卷": 3,
            "健康问卷": 4,
            "认知问卷": 5,
        }
        # 问卷类型对应的问题类型ID
        self.q_type_map = {1: 10, 2: 11, 3: 12, 4: 13, 5: 14}

    def toggle_questionnaire_checkboxes(self):
        """全选/取消问卷类复选框"""
        state = self.checkBox_9.isChecked()
        for i in range(1, 6):
            getattr(self, f"checkBox_{i}").setChecked(state)
        self.update_checkbox_text(self.checkBox_9)

    def toggle_record_checkboxes(self):
        """全选/取消记录类复选框"""
        state = self.checkBox_10.isChecked()
        for i in range(6, 9):
            getattr(self, f"checkBox_{i}").setChecked(state)
        self.update_checkbox_text(self.checkBox_10)

    def update_parent_checkbox(self, child_idx, parent_idx):
        """根据子复选框状态更新父全选按钮"""
        if parent_idx == 9:
            checkboxes = [getattr(self, f"checkBox_{i}") for i in range(1, 6)]
        else:
            checkboxes = [getattr(self, f"checkBox_{i}") for i in range(6, 9)]

        all_checked = all(cb.isChecked() for cb in checkboxes)
        parent_checkbox = getattr(self, f"checkBox_{parent_idx}")
        parent_checkbox.setChecked(all_checked)
        self.update_checkbox_text(parent_checkbox)

    def update_checkbox_text(self, checkbox):
        """更新全选按钮文本"""
        checkbox.setText("取消选择" if checkbox.isChecked() else "选择全部")

    def export_results(self):
        # 基础信息校验
        if not self.validate_basic_info():
            return

        # 复选框选择校验
        if not self.has_selected_checkboxes():
            self.doctorWin.error_notice("请至少选择一个数据项进行导出")
            return

        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        query_data = self.collect_query_data()

        # 数据有效性校验
        if not self.has_valid_data(query_data):
            self.doctorWin.error_notice("所有选中的数据项均无有效数据")
            return

        # 计算问卷得分
        questionnaire_scores = self.calculate_questionnaire_scores(query_data)

        all_data = self.prepare_excel_data(query_data, current_time, questionnaire_scores)
        self.export_to_excel(all_data)

    def validate_basic_info(self):
        """校验患者基础信息"""
        patient_id = self.doctorWin.lineEdit_id.text().strip()
        patient_name = self.doctorWin.lineEdit_name.text().strip()

        if not patient_id:
            self.doctorWin.error_notice("患者ID不能为空")
            return False
        if not patient_name:
            self.doctorWin.error_notice("患者姓名不能为空")
            return False
        return True

    def has_selected_checkboxes(self):
        """检查是否有选中的复选框"""
        questionnaire_checked = any(getattr(self, f"checkBox_{i}").isChecked() for i in range(1, 6))
        record_checked = any(getattr(self, f"checkBox_{i}").isChecked() for i in range(6, 9))
        return questionnaire_checked or record_checked

    def collect_query_data(self):
        """收集查询数据"""
        patient_id = self.doctorWin.lineEdit_id.text()
        query_data = {
            "医生查房记录": [],
            "护士查房记录": [],
            "患者需求记录": [],
            "焦虑问卷": [],
            "抑郁问卷": [],
            "睡眠问卷": [],
            "健康问卷": [],
            "认知问卷": [],
        }

        # 记录类数据
        if self.checkBox_6.isChecked():
            query_data["医生查房记录"] = self.query_patient_answer(patient_id, 1)
        if self.checkBox_7.isChecked():
            query_data["护士查房记录"] = self.query_patient_answer(patient_id, 2)
        if self.checkBox_8.isChecked():
            query_data["患者需求记录"] = self.query_patient_requirements(patient_id)

        # 问卷类数据
        for idx in range(1, 6):
            if getattr(self, f"checkBox_{idx}").isChecked():
                q_type = self.q_type_map[idx]
                section = list(self.question_ace.keys())[idx - 1]
                query_data[section] = self.query_patient_answer(patient_id, q_type)

        return query_data

    def calculate_questionnaire_scores(self, query_data):
        """计算问卷得分"""
        scores = {}
        patient_id = self.doctorWin.lineEdit_id.text()

        for section, questions in query_data.items():
            if section not in self.question_ace:
                continue  # 只计算问卷类型

            # 获取问卷类型ID
            questionnaire_type = self.question_ace[section]
            question_type_id = self.q_type_map[questionnaire_type]

            # 获取该问卷的所有问题及其得分映射
            question_score_map = self.get_question_score_map(question_type_id)

            total_score = 0
            valid_questions = 0

            for question in questions:
                patient_name, question_text, answer_text, begin_test_time, test_time = question

                # 查找问题对应的得分映射
                if question_text in question_score_map:
                    score_map = question_score_map[question_text]
                    # 查找回答对应的得分
                    score = score_map.get(answer_text, 0)
                    total_score += score
                    valid_questions += 1

            scores[section] = {"total_score": total_score, "question_count": valid_questions}

        return scores

    def get_question_score_map(self, question_type_id):
        """获取问题及其得分映射"""
        # 查询questions表获取该类型的所有问题
        query = """
            SELECT question_text, answer1_text, answer2_text, answer3_text, answer4_text, answer5_text,
                   score_1, score_2, score_3, score_4, score_5
            FROM questions 
            WHERE type = ?
        """
        try:
            self.doctorWin.sqlcursor.execute(query, (question_type_id,))
            results = self.doctorWin.sqlcursor.fetchall()

            score_map = {}
            for row in results:
                question_text = row[0]
                answers = row[1:6]  # answer1_text 到 answer5_text
                scores = row[6:11]  # score_1 到 score_5

                # 构建答案到得分的映射
                answer_score_map = {}
                for i in range(len(answers)):
                    if answers[i]:  # 只处理非空答案
                        answer_score_map[answers[i]] = scores[i]

                score_map[question_text] = answer_score_map

            return score_map

        except Exception as e:
            print(f"获取问题得分映射失败：{e}")
            self.doctorWin.error_notice("计算得分失败，请检查数据库连接")
            return {}

    def has_valid_data(self, query_data):
        """检查是否有有效数据"""
        section_check_map = {
            "医生查房记录": self.checkBox_6,
            "护士查房记录": self.checkBox_7,
            "患者需求记录": self.checkBox_8,
            "焦虑问卷": self.checkBox_1,
            "抑郁问卷": self.checkBox_2,
            "睡眠问卷": self.checkBox_3,
            "健康问卷": self.checkBox_4,
            "认知问卷": self.checkBox_5,
        }

        for section, data in query_data.items():
            checkbox = section_check_map[section]
            if checkbox.isChecked() and data:
                return True
        return False

    def prepare_excel_data(self, query_data, current_time, questionnaire_scores):
        """准备Excel数据，包括问卷得分"""
        all_data = []
        section_headers = {
            ("医生查房记录", "护士查房记录"): [
                "信息类别",
                "导出时间",
                "患者姓名",
                "问题描述",
                "回答内容",
                "开始答题时间",
                "结束答题时间",
            ],
            ("焦虑问卷", "抑郁问卷", "睡眠问卷", "健康问卷", "认知问卷"): [
                "信息类别",
                "导出时间",
                "患者姓名",
                "问题描述",
                "回答内容",
                "开始测试时间",
                "测试时间",
            ],
            "患者需求记录": ["信息类别", "导出时间", "患者姓名", "需求描述", "处理时间", "结束时间"],
        }

        # 添加问卷得分汇总
        patient_name = self.doctorWin.lineEdit_name.text().strip()
        score_headers = ["信息类别", "患者姓名", "总得分", "题目数量"]
        all_data.append(score_headers)

        for section in self.question_ace.keys():
            if getattr(self, f"checkBox_{self.question_ace[section]}").isChecked():
                if section in questionnaire_scores:
                    score_data = questionnaire_scores[section]
                    all_data.append([
                        f"{section}得分",
                        patient_name,
                        score_data["total_score"],
                        score_data["question_count"],
                    ])
                else:
                    all_data.append([f"{section}得分", patient_name, "无数据", ""])

        all_data.append([])  # 添加空行分隔

        # 添加具体数据
        for section, data in query_data.items():
            if not data and not self.is_section_selected(section):
                continue  # 未选中的部分不显示无数据行

            headers = self.get_section_headers(section, section_headers)
            if data:
                all_data.append(headers)
                for record in data:
                    all_data.append([section, current_time] + list(record))
            else:
                all_data.append([f"{section}：无数据"] + [""] * (len(headers) - 1))

        return [row for row in all_data if any(row)]  # 过滤全空行

    def is_section_selected(self, section):
        """检查该部分是否被选中"""
        checkbox_map = {
            "医生查房记录": self.checkBox_6,
            "护士查房记录": self.checkBox_7,
            "患者需求记录": self.checkBox_8,
            "焦虑问卷": self.checkBox_1,
            "抑郁问卷": self.checkBox_2,
            "睡眠问卷": self.checkBox_3,
            "健康问卷": self.checkBox_4,
            "认知问卷": self.checkBox_5,
        }
        return checkbox_map[section].isChecked()

    def get_section_headers(self, section, section_headers):
        """获取对应部分的表头"""
        for key, headers in section_headers.items():
            if isinstance(key, tuple) and section in key:
                return headers
            elif key == section:
                return headers
        return []

    def export_to_excel(self, data):
        """导出到Excel"""
        if not data:
            self.doctorWin.error_notice("无有效数据可导出")
            return

        patient_name = self.doctorWin.lineEdit_name.text().strip()
        current_time = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        file_name = f"{patient_name}_{current_time}.xlsx"

        file_path, _ = QFileDialog.getSaveFileName(self, "保存报告", file_name, "Excel Files (*.xlsx)")

        if not file_path:
            self.doctorWin.error_notice("未选择保存路径")
            return

        try:
            df = pd.DataFrame(data[0:], columns=None)  # 处理表头
            df.to_excel(file_path, index=False)
            self.doctorWin.cor_notice("文件已保存成功!")
        except Exception as e:
            self.doctorWin.error_notice("文件导出异常!")
            print(f"导出错误：{e}")

    # --------------------- 数据库查询方法 ---------------------
    def query_patient_answer(self, patient_id, question_type):
        query = """
            SELECT patient_name, question_text, answer_text, begin_test_time, test_time
            FROM patient_answer 
            WHERE patient_id = ? AND question_type = ?
        """
        return self.execute_query(query, (patient_id, question_type))

    def query_patient_requirements(self, patient_id):
        query = """
            SELECT patient_name, requirements, handle_time, end_time 
            FROM patient_requirements 
            WHERE patient_id = ?
        """
        return self.execute_query(query, (patient_id,))

    def execute_query(self, query, params):
        try:
            self.doctorWin.sqlcursor.execute(query, params)
            return self.doctorWin.sqlcursor.fetchall()
        except Exception as e:
            print(f"数据库查询错误：{e}")
            self.doctorWin.error_notice("数据查询失败，请检查数据库连接")
            return []


class SeDialog_req(QMainWindow, Ui_senoctice_UI):
    def __init__(self, doctorWin):
        super().__init__()
        self.setupUi(self)  # 初始化UI
        self.setWindowFlag(QtCore.Qt.FramelessWindowHint)  # 不显示窗体边框
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.doctorWin = doctorWin
        self.pushButton_2.clicked.connect(lambda: self.onYesButtonClicked(self.doctorWin))

    def onYesButtonClicked(self, doctorWin):
        global charge
        doctorWin = doctorWin
        # SQLite 文件型数据库无需网络连接检查，直接重连确保连接有效
        try:
            doctorWin.resql()
        except Exception:
            doctorWin.msg = NoticeWindow()
            doctorWin.msg.pushButton_3.setText("处理出现错误，请检查相关设置！")
            show_window_on_appropriate_screen(doctorWin.msg)
            return
        try:
            requirements = doctorWin.update_req()
            # 获取患者ID
            patient_id = doctorWin.lineEdit_id.text()  # 从某个地方获取记录的id，这个需要根据具体情况来
            # 更新数据库中对应记录的字段
            end_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")  # 获取当前时间
            for requirement in requirements:
                doctorWin.resql()
                doctorWin.sqlcursor.execute(
                    "UPDATE patient_requirements SET handle = '是', end_time = ? WHERE patient_id = ? AND handle = '否' AND requirements = ?",
                    (end_time, str(patient_id), requirement),
                )
                doctorWin.connection.commit()
                doctorWin.msg = NoticeWindow()
                doctorWin.msg.pushButton_3.setText("处理成功！")
                doctorWin.label_req.setText("点击'开始闪烁', 患者将继续反馈述求")
                data = {
                    "func_selected": "demand",
                    "question_info": None,
                    "ccaSwitch": None,
                    "selected": None,
                    "shanshuo": 2,
                }
                doctorWin.trigger_message("patient_ui", data)
                doctorWin.pushButton_ready_req.setEnabled(True)
                doctorWin.update_button_styles()
                print(1)
                print("处理后发送的闪烁命令")
                charge = True

                show_window_on_appropriate_screen(doctorWin.msg)
                doctorWin.query_history()
        except Exception as e:
            # 发生错误时回滚
            doctorWin.connection.rollback()
            print("Error:", e)


class MainWindow(QMainWindow, Ui_main_ui):  # 主界面
    def __init__(self, client=None, parent=None):
        super().__init__()
        self.setupUi(self)  # 初始化UI
        self.setWindowFlag(QtCore.Qt.FramelessWindowHint)  # 不显示窗体边框
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.client = client
        self.doctorWin = doctorWin
        self.pushButton.clicked.connect(lambda: self.start(self.doctorWin, 1))  # 开启医生查房界面
        self.pushButton_2.clicked.connect(lambda: self.start(self.doctorWin, 2))  # 开启护士查房界面
        self.pushButton_3.clicked.connect(lambda: self.start(self.doctorWin, 3))  # 开启患者需求界面
        self.Button_cognitive_activation.clicked.connect(self.open_cognition_activation)  # 开启认知激活界面

    def open_cognition_activation(self):
        self.cognitionWin = CognitionWindow(client=self.client, doctorWin=self.doctorWin)
        show_window_on_appropriate_screen(self.cognitionWin)
        self.close()

    def start(self, doctorWin, ty):
        global winSelect
        winSelect = "doctor"
        data = {
            "func_selected": "welcome",
            "question_info": None,
            "ccaSwitch": None,
            "selected": None,
            "shanshuo": 0,
        }
        doctorWin.trigger_message("patient_ui", data)
        print(2)
        doctorWin.ty = ty
        doctorWin.change_main_2()
        if doctorWin.ty == 3:  # 患者需求界面
            doctorWin.update_req()  # 更新需求信息
            doctorWin.stackedWidget_2.setCurrentIndex(1)
            doctorWin.stackedWidget.setCurrentIndex(3)
            doctorWin.question_query()  # 需求查询
            winSelect = "demand"
            self.demandSTime = time.time()
            if doctorWin.pushButton_luru.text() == "清空":
                data = {
                    "func_selected": "demand_entry",
                    "question_info": None,
                    "ccaSwitch": None,
                    "selected": None,
                    "shanshuo": 0,
                }
                doctorWin.trigger_message("patient_ui", data)
                print(3)
                print("1号")
                charge = 1  # 每次进来假装处理过需求的问题了
                doctorWin.question_query()
        else:
            doctorWin.stackedWidget_2.setCurrentIndex(0)
            doctorWin.stackedWidget.setCurrentIndex(2)
            doctorWin.question_query()
            if doctorWin.ty == 1:  # 医生
                if not qq.empty():
                    while not qq.empty():
                        qq.get()  # 取出并删除队列中的元素，直到队列为空
                qq.put(doctorWin.ty)
                winSelect = "doctor"
                # sender.send_data({'func_selected': 'round', 'question_info': None, 'ccaSwitch': None, 'selected': None})
            elif doctorWin.ty == 2:  # 护士
                if not qq.empty():
                    while not qq.empty():
                        qq.get()  # 取出并删除队列中的元素，直到队列为空
                qq.put(doctorWin.ty)
                winSelect = "nurse"
                # sender.send_data({'func_selected': 'round', 'question_info': None, 'ccaSwitch': None, 'selected': None})
        if doctorWin.pushButton_luru.text() == "清空":
            doctorWin.label_req.setText("点击'开始闪烁'，患者将进行一级需求选择")
            doctorWin.query_history()
        elif doctorWin.pushButton_luru.text() == "录入":
            doctorWin.label_req.setText("请录入患者信息！")
        show_window_on_appropriate_screen(doctorWin)
        time.sleep(0.1)
        self.close()


class NoticeWindow(QMainWindow, Ui_notice_UI):  # 提示框
    def __init__(self):
        super().__init__()
        self.setupUi(self)  # 初始化UI
        self.setWindowFlag(QtCore.Qt.FramelessWindowHint)  # 不显示窗体边框
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.isclick = 0
        self.pushButton_2.clicked.connect(self.tem)

    def tem(self):
        self.isclick = 1


class CfWindow(QMainWindow, Ui_cf_ui):  # 功能窗口
    search_complete_signal = pyqtSignal()  # 算法个性化校准完成信号，用于跨线程弹窗

    def __init__(self, client, parent=None, right=None):
        super().__init__()
        self.client = client
        # 启动客户端主连接
        self.client_thread = threading.Thread(target=self.client.start, daemon=True)
        self.client_thread.start()
        # 设置算法个性化校准完成回调
        self.client.search_complete_callback = self._on_search_complete
        # 连接信号到弹窗槽函数（确保在主线程中弹窗）
        self.search_complete_signal.connect(self._show_search_complete_popup)
        self.a_notch = None
        self.b_notch = None
        self.word = None
        self.setupUi(self)  # 初始化UI
        self.setWindowFlag(QtCore.Qt.FramelessWindowHint)  # 不显示窗体边框
        # 去除所有widget的边框线
        self.can_send = True
        self.right = right  # 打标签管道（发送）
        self.sqlcursor = self.sqlConnect()
        self.startTime = time.time()
        self.demandSTime = time.time()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_time)
        self.timer.start(1000)  # 更新时间间隔：1000毫秒（1秒）
        self.update_time()  # 初始显示时间
        self.eeg_count = eeg_count  # EEG数据包数量，0.2s一次，默认30秒
        self.record_time = record_time
        global ccaSwitch, winSelect
        self.vepClass = -1
        self.vepOpenCount = 0
        self.answersCount = -1
        self.ty = 1  # tpye,当前类型，1医生，2护士，3患者。
        self.current_index = 0
        self.execution_count = 0
        self.timer = None
        self.loop_count = loop_count  # 自动查房循环次数
        self.is_paused = False
        self.label = None
        self.sp_time = None
        self.test_begin = None
        self.test_end = None
        self.rr = None
        self.curr_index = 0
        self.timer_chafang = None
        self.timer_1 = None
        self.timer_recognize = None
        self.threshold_value = None
        self.eyeQueue = None
        self.PopNum = 0
        self.recognition_timer = QTimer(self)
        self.recognition_timer.setInterval(200)
        self.recognition_timer.timeout.connect(self._poll_recognition_result)
        self._recognition_ticks = 0
        if cf_test != 1:  # 如果不是测试，删除测试备注信息文本框体
            self.lineEdit_name_2.deleteLater()
        if not qq.empty():
            while not qq.empty():
                qq.get()  # 取出并删除队列中的元素，直到队列为空
        qq.put(self.ty)
        self.opensubwindow = 0
        global patient_id, patient_name
        self.WORDS = [
            WordTextS.require_sub_text1,
            WordTextS.require_sub_text2,
            WordTextS.require_sub_text3,
            WordTextS.require_sub_text4,
        ]
        self._is_category_delete = False  # 标记是否正在删除分类
        self._pending_delete_category = None
        # ===== 初始化树状问题列表 =====
        self._setup_question_tree()
        self.question_query()
        self.change_main_2()
        self.tableWidget.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)  # 设置为不可编辑
        self.tableWidget.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)  # 设置为不可选中
        self.tableWidget.setMouseTracking(False)  # 禁用鼠标跟踪
        self.tableWidget.setFocusPolicy(QtCore.Qt.NoFocus)  # 禁用焦点
        self.tableWidget_2.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)  # 设置为不可编辑
        self.tableWidget_2.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)  # 设置为不可选中
        self.tableWidget_2.setMouseTracking(False)  # 禁用鼠标跟踪
        self.tableWidget_2.setFocusPolicy(QtCore.Qt.NoFocus)  # 禁用焦点
        # 禁止用户调整列宽和行高
        self.tableWidget.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Fixed)
        self.tableWidget.verticalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Fixed)
        self.tableWidget_2.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Fixed)
        self.tableWidget_2.verticalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Fixed)

        # 将按钮与槽函数连接
        self.pushButton_begin.clicked.connect(self.on_pushButton_begin_clicked)
        self.pushButton_delete.clicked.connect(self.on_pushButton_delete_clicked)
        self.pushButton_update.clicked.connect(self.on_pushButton_update_clicked)
        self.pushButton_add.clicked.connect(self.on_pushButton_add_clicked)
        # self.pushButton_end.clicked.connect(self.on_pushButton_end_clicked)

        # 初始状态：pushButton_end 不能点击，其他按钮可以点击
        # self.pushButton_end.setEnabled(False)
        self.pushButton_autocf.setEnabled(False)
        self.pushButton_auto_esc.setEnabled(False)
        self.pushButton_begin.setEnabled(True)
        self.pushButton_delete.setEnabled(True)
        self.pushButton_update.setEnabled(True)
        self.pushButton_add.setEnabled(True)
        self.pushButton_ready.setEnabled(False)
        self.pushButton_do.setEnabled(False)
        self.radioButton_cca.setChecked(True)
        self.pushButton_Threshold.setVisible(False)

        self.pushButton_add.clicked.connect(self.Goadd)
        self.pushButton_chaxun.clicked.connect(self.Gochaxun)
        self.pushButton_change.clicked.connect(self.logochange)
        self.pushButton_main.clicked.connect(self.gomain)
        self.pushButton_main_2.clicked.connect(self.gorequire)
        self.pushButton_luru.clicked.connect(self.luru)
        self.pushButton_delete.clicked.connect(self.question_delete)
        self.pushButton_update.clicked.connect(self.question_update)
        self.pushButton_begin_2.clicked.connect(self.query_history)
        self.pushButton_history.clicked.connect(self.query_history)
        self.pushButton_results.clicked.connect(self.query_history)
        self.pushButton_do.clicked.connect(self.doreq)
        self.pushButton_begin.clicked.connect(self.round_start)
        # self.pushButton_end.clicked.connect(self.round_end)
        self.pushButton_autocf.clicked.connect(self.goauto)
        # self.pushButton_auto_stop.clicked.connect(self.pause)
        self.pushButton_auto_esc.clicked.connect(self.esc)
        self.pushButton_subject.clicked.connect(self.get_searchBestFrequencies)  # 搜索最佳频率
        self.pushButton_change_3.clicked.connect(close_current_program)  # 关闭按钮，关闭所有程序
        self.pushButton_ready.clicked.connect(self.ready)  # 控制闪烁的函数
        self.pushButton_ready_req.clicked.connect(self.ready)  # 控制闪烁的函数
        self.pushButton_Threshold.clicked.connect(self.get_Threshold)  # 获取阈值
        self.pushButton_up.clicked.connect(self.move_selected_button_up)  # 上移
        self.pushButton_down.clicked.connect(self.move_selected_button_down)  # 下移
        self.pushButton_CheckList.clicked.connect(self.checklist_open)  # 核查表
        self.pushButton_print.clicked.connect(self.print_table)  # 导出数据
        self.cleartable()
        self.update_button_styles()
        # self.run = Control(sender, qq)

        self.asr_thread = None
        self.consumer_thread = None
        # 初始化窗口控件
        self.progressBar.setRange(0, 20)  # 进度条范围
        self.progressBar.setValue(15)  # 初始值
        self.progressBar.setFormat("%.2f" % (self.progressBar.value() / 100 + 0.2))
        ten_days_ago = datetime.now() - timedelta(days=10)
        self.date_edit_start.setDate(ten_days_ago.date())
        self.date_edit_start.setDisplayFormat("yyyy-MM-dd")  # 日期格式

        self.time_edit_start.setTime(datetime.now().time())  # 默认当前时间

        self.date_edit_end.setDate(datetime.now().date())  # 默认当前日期
        self.date_edit_end.setDisplayFormat("yyyy-MM-dd")  # 日期格式

        self.time_edit_end.setTime(datetime.now().time())  # 默认当前时间
        # 信号与槽
        self.pushButton_add_th.clicked.connect(self.increase_threshold)
        self.pushButton_reduce_th.clicked.connect(self.decrease_threshold)
        self.radioButton_cca.toggled.connect(self.on_radioButton_cca_toggled)
        self.radioButton_train.toggled.connect(self.on_radioButton_train_toggled)
        self.radioButton_cca_train.toggled.connect(self.on_radioButton_cca_train_toggled)

        self._temp_avatar_path = None
        self.frame_8.installEventFilter(self)
        self._load_avatar()

    # ---- 头像相关方法 ----
    def _get_avatar_dir(self):
        avatars_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "imgs", "avatars")
        os.makedirs(avatars_dir, exist_ok=True)
        return avatars_dir

    def _get_default_avatar_path(self):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(base_dir, "多功能智能查房系统", "默认头像.png").replace("\\", "/")

    def eventFilter(self, obj, event):
        if obj == self.frame_8 and event.type() == QtCore.QEvent.MouseButtonPress:
            self.select_avatar()
            return True
        return super().eventFilter(obj, event)

    def select_avatar(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择头像图片", "",
            "图片文件 (*.png *.jpg *.jpeg *.bmp)"
        )
        if not file_path:
            return
        pid = self.lineEdit_id.text().strip()
        avatars_dir = self._get_avatar_dir()
        if pid:
            dest_path = os.path.join(avatars_dir, f"{pid}.png").replace("\\", "/")
        else:
            dest_path = os.path.join(avatars_dir, "_temp_avatar.png").replace("\\", "/")
        import shutil
        shutil.copy(file_path, dest_path.replace("/", os.sep))
        self._temp_avatar_path = dest_path
        self._apply_avatar_style(dest_path)

    def _apply_avatar_style(self, image_path):
        self.frame_8.setStyleSheet(
            f"border-image: url({image_path});"
        )

    def _load_avatar(self):
        pid = self.lineEdit_id.text().strip() if hasattr(self, 'lineEdit_id') else ""
        default_avatar = self._get_default_avatar_path()
        if not pid:
            self._apply_avatar_style(default_avatar)
            self._temp_avatar_path = None
            return
        avatars_dir = self._get_avatar_dir()
        avatar_path = os.path.join(avatars_dir, f"{pid}.png").replace("\\", "/")
        if os.path.exists(avatar_path.replace("/", os.sep)):
            self._apply_avatar_style(avatar_path)
            self._temp_avatar_path = avatar_path
        else:
            self._apply_avatar_style(default_avatar)
            self._temp_avatar_path = None

    def _save_avatar_for_patient(self, pid):
        if not hasattr(self, '_temp_avatar_path') or not self._temp_avatar_path:
            return
        import shutil
        avatars_dir = self._get_avatar_dir()
        dest_path = os.path.join(avatars_dir, f"{pid}.png")
        src = self._temp_avatar_path.replace("/", os.sep)
        if os.path.exists(src) and src != dest_path:
            shutil.copy(src, dest_path)
            self._temp_avatar_path = dest_path.replace("\\", "/")
            self._apply_avatar_style(self._temp_avatar_path)
    # ---- 头像相关方法结束 ----

    def on_radioButton_cca_toggled(self):
        if self.radioButton_cca.isChecked():
            self.progressBar.setVisible(True)
            self.pushButton_add_th.setVisible(True)
            self.pushButton_reduce_th.setVisible(True)
            self.pushButton_Threshold.setVisible(False)
            self.sever_message(
                "model",
                {
                    "mode": "cca",
                    "patient_id": self.lineEdit_id.text().strip(),
                    "threshold": self.get_bar_threshold(),
                },
            )
        else:
            self.progressBar.setVisible(False)
            self.pushButton_add_th.setVisible(False)
            self.pushButton_reduce_th.setVisible(False)
            # self.sever_message("model", {'mode': "train", 'patient_id': self.lineEdit_id.text().strip(), "threshold": self.get_bar_threshold()})

    def on_radioButton_train_toggled(self):
        if self.radioButton_train.isChecked():
            self.pushButton_Threshold.setVisible(True)
            self.progressBar.setVisible(False)
            self.pushButton_add_th.setVisible(False)
            self.pushButton_reduce_th.setVisible(False)
            self.update_button_styles()
            self.sever_message(
                "model",
                {
                    "mode": "train",
                    "patient_id": self.lineEdit_id.text().strip(),
                    "threshold": self.get_bar_threshold(),
                },
            )
        else:
            self.pushButton_Threshold.setVisible(False)
            # self.sever_message("model", {"mode": "cca",'patient_id': self.lineEdit_id.text().strip(), "threshold": self.get_bar_threshold()})

    def on_radioButton_cca_train_toggled(self):
        if self.radioButton_cca_train.isChecked():
            self.progressBar.setVisible(False)
            self.pushButton_add_th.setVisible(False)
            self.pushButton_reduce_th.setVisible(False)
            self.pushButton_Threshold.setVisible(False)
            self.sever_message(
                "model",
                {
                    "mode": "both_cca_train",
                    "patient_id": self.lineEdit_id.text().strip(),
                    "threshold": self.get_bar_threshold(),
                },
            )
        else:
            self.progressBar.setVisible(True)
            self.pushButton_add_th.setVisible(True)
            self.pushButton_reduce_th.setVisible(True)
            self.pushButton_Threshold.setVisible(True)
            self.update_button_styles()

    def trigger_message(self, target, message):
        # Queue insertion is already thread-safe; do not create a thread per message.
        self.client.async_send(target, message)

    def sever_message(self, event_name, message):
        self.client.send_to_server(event_name, message)

    def print_table(self):
        if self.pushButton_luru.text() == "清空":
            self.print_window = Select_results_Window(self)
            self.print_window.show()
        else:
            self.error_notice("请先输入病人信息！")

    def get_patient_requirements_count(self):
        """查询当前病人时间范围内的二级菜单记录并统计一级菜单次数"""
        # 获取当前病人信息
        patient_id = self.lineEdit_id.text().strip()
        patient_name = self.lineEdit_name.text().strip()
        self.resql()
        if not patient_id or not patient_name:
            return None, "请填写完整的病人ID和姓名"

        # 获取选择的开始时间和结束时间
        start_datetime = datetime.combine(
            self.date_edit_start.date().toPyDate(), self.time_edit_start.time().toPyTime()
        )
        end_datetime = datetime.combine(
            self.date_edit_end.date().toPyDate(), self.time_edit_end.time().toPyTime()
        )

        # SQL查询当前病人时间范围内的记录
        query = """
        SELECT requirements 
        FROM patient_requirements 
        WHERE patient_id = ? 
        AND patient_name = ?
        AND end_time BETWEEN ? AND ?
        """

        # 执行查询
        self.sqlcursor.execute(query, (patient_id, patient_name, start_datetime, end_datetime))
        result = self.sqlcursor.fetchall()

        # 一级菜单分类统计字典
        count_dict = {"了解病情": 0, "家人朋友": 0, "身体疼痛": 0, "身边环境": 0}
        # count_dict = {
        #     '头部': 0,
        #     '手部': 0,
        #     '腹部': 0,
        #     '腿部': 0
        # }

        # 二级菜单对应的一级菜单映射
        require_map = {
            "手术成功吗": "了解病情",
            "什么时候出去": "了解病情",
            "预后康复情况": "了解病情",
            "怎么配合治疗?": "了解病情",
            "告知密码": "家人朋友",
            "思念家人": "家人朋友",
            "通知朋友": "家人朋友",
            "商量要事": "家人朋友",
            "需要止痛药": "身体疼痛",
            "插管难受": "身体疼痛",
            "需要按摩": "身体疼痛",
            "需要安眠药": "身体疼痛",
            "太吵": "身边环境",
            "光线强弱": "身边环境",
            "时间错乱": "身边环境",
            "不想被打扰": "身边环境",
            # '头痛': '头部', '头晕': '头部', '颈部难受': '头部', '喉咙难受': '头部',
            # '上肢关节痛': '手部', '手麻': '手部', '肌无力': '手部', '手冷': '手部',
            # '肚子疼': '腹部', '胸闷': '腹部', '后背痒': '腹部', '腰疼': '腹部',
            # '下肢关节痛': '腿部', '腿麻': '腿部', '腿抽筋': '腿部', '脚冷': '腿部'
        }

        # 遍历查询结果并统计一级菜单次数
        for row in result:
            requirements = row[0]
            if requirements in require_map:
                main_requirement = require_map[requirements]
                count_dict[main_requirement] += 1

        return count_dict, ""

    def plot_and_display(self):
        """
        绘制统计图并显示在QLabel上

        此函数用于获取当前病人的需求统计数据，并绘制为柱状图展示在对应的QLabel控件上。
        如果获取数据过程中出现错误，将在QLabel上显示错误信息。
        """
        # 获取当前病人的需求统计
        count_dict, error_message = self.get_patient_requirements_count()

        if error_message:
            self.label_req_plot.setText(error_message)
            return

        # 设置中文字体，解决中文显示和负号显示问题，统一设置字体大小为12号，颜色为白色
        plt.rcParams["font.sans-serif"] = ["SimHei"]
        plt.rcParams["axes.unicode_minus"] = False
        plt.rcParams["font.size"] = 12
        plt.rcParams["text.color"] = "white"

        # 设置图形背景颜色为RGB值(9, 20, 39)，通过自定义背景颜色来实现
        plt.rcParams["axes.facecolor"] = (9 / 255, 20 / 255, 39 / 255)
        plt.rcParams["figure.facecolor"] = (9 / 255, 20 / 255, 39 / 255)

        # 设置图表边框线颜色为白色
        plt.rcParams["axes.edgecolor"] = "white"
        plt.rcParams["figure.edgecolor"] = "white"

        # 使用不同的浅色绘制柱状图，通过调整柱状图宽度使其更"瘦"一些
        bar_width = 0.3  # 柱子宽度变小，可根据实际效果调整此值
        colors = ["#8FA3B1", "#A4C6DD", "#C1D8E6", "#D8E9F1"]

        # 绘制图表
        fig, ax = plt.subplots(figsize=(8, 6))
        ax.bar(count_dict.keys(), count_dict.values(), width=bar_width, color=colors)

        # 添加标题和标签，设置字体颜色为白色，字体大小为12号
        ax.set_title("当前病人需求统计", color="white", fontsize=12)
        ax.set_xlabel("需求项", color="white", fontsize=12)
        ax.set_ylabel("次数", color="white", fontsize=12)

        # 设置坐标轴刻度标签颜色为白色，字体大小为12号
        ax.tick_params(axis="both", colors="white", labelsize=12)

        # 格式化 x 轴标签，使其水平显示，避免倾斜带来的阅读不便
        plt.xticks(rotation=0, ha="center")

        # 获取QLabel的大小，将图表严格按照标签大小来设置尺寸
        label_size = self.label_req_plot.size()
        fig.set_size_inches(label_size.width() / fig.dpi, label_size.height() / fig.dpi)

        # 保存为图片并显示在 QLabel 上
        with BytesIO() as img_buf:
            plt.savefig(img_buf, format="png")
            img_buf.seek(0)

            # 创建QPixmap并设置到标签上，添加异常处理增强健壮性
            try:
                pixmap = QPixmap()
                pixmap.loadFromData(img_buf.read())

                # 直接使用QLabel的大小来设置图片尺寸，不锁定横纵比
                pixmap = pixmap.scaled(label_size)

                self.label_req_plot.setPixmap(pixmap)
            except Exception as e:
                self.label_req_plot.setText(f"图片加载或显示失败: {e}")
                return

        # 清理，关闭图形对象释放资源
        plt.close(fig)

    def get_selected_button(self):
        """获取当前选中的问题树节点（兼容旧接口，返回 QTreeWidgetItem）"""
        return self._get_selected_question_item()

    def get_previous_button(self):
        """获取选中问题节点的上一个兄弟节点"""
        item = self._get_selected_question_item()
        if item is None:
            return None
        parent = item.parent()
        if parent is None:
            return None
        idx = parent.indexOfChild(item)
        if idx <= 0:
            return None
        return parent.child(idx - 1)

    def get_next_button(self):
        """获取选中问题节点的下一个兄弟节点"""
        item = self._get_selected_question_item()
        if item is None:
            return None
        parent = item.parent()
        if parent is None:
            return None
        idx = parent.indexOfChild(item)
        if idx < 0 or idx >= parent.childCount() - 1:
            return None
        return parent.child(idx + 1)

    def swap_buttons(self, item1, item2):
        """交换两个问题节点在树中的位置及数据库 sequence"""
        # item1 和 item2 是 QTreeWidgetItem（问题节点）
        parent = item1.parent()
        if parent is None or item2.parent() is None:
            return
        idx1 = parent.indexOfChild(item1)
        idx2 = parent.indexOfChild(item2)
        if idx1 < 0 or idx2 < 0:
            return

        # 交换数据库 sequence
        seq1 = self._get_sequence_value(item1)
        seq2 = self._get_sequence_value(item2)
        id1 = self._get_record_id(item1)
        id2 = self._get_record_id(item2)
        if seq1 is None or seq2 is None:
            return

        try:
            self.resql()
            self.sqlcursor.execute("UPDATE questions SET sequence = ? WHERE question_id = ?", (seq2, id1))
            self.sqlcursor.execute("UPDATE questions SET sequence = ? WHERE question_id = ?", (seq1, id2))
            self.connection.commit()
        except Exception as e:
            print(f"数据库操作出现错误: {e}")
            self.connection.rollback()
            return

        # 交换树中位置
        text1 = item1.text(0)
        data1 = item1.data(0, QtCore.Qt.UserRole)
        text2 = item2.text(0)
        data2 = item2.data(0, QtCore.Qt.UserRole)
        item1.setText(0, text2)
        item1.setData(0, QtCore.Qt.UserRole, data2)
        item2.setText(0, text1)
        item2.setData(0, QtCore.Qt.UserRole, data1)
        item1.setSelected(False)
        item2.setSelected(True)

    def _get_sequence_value(self, item):
        """根据树节点获取数据库中对应记录的 sequence 值"""
        question_id = item.data(0, QtCore.Qt.UserRole).get("question_id")
        if question_id is None:
            return None
        self.resql()
        self.sqlcursor.execute("SELECT sequence FROM questions WHERE question_id = ?", (question_id,))
        result = self.sqlcursor.fetchone()
        return result[0] if result else None

    def _get_record_id(self, item):
        """根据树节点获取 question_id"""
        return item.data(0, QtCore.Qt.UserRole).get("question_id")

    def get_sequence_value(self, item):
        """兼容旧接口"""
        return self._get_sequence_value(item)

    def get_record_id(self, item):
        """兼容旧接口"""
        return self._get_record_id(item)

    def move_selected_button_up(self):
        self.resql()
        item = self.get_selected_button()
        if item is None:
            return
        prev_item = self.get_previous_button()
        if prev_item is None:
            return
        self.swap_buttons(item, prev_item)

    def move_selected_button_down(self):
        self.resql()
        item = self.get_selected_button()
        if item is None:
            return
        next_item = self.get_next_button()
        if next_item is None:
            return
        self.swap_buttons(item, next_item)

    def increase_threshold(self):
        """增加阈值"""

        current_value = self.progressBar.value()
        if current_value < 20:
            self.progressBar.setValue(current_value + 1)  # 每次增加 1 格
            self.progressBar.setFormat("%.2f" % (self.progressBar.value() / 100 + 0.2))
            self.progressBar.repaint()  # 强制刷新进度条
            # self.update_threshold_label()
        self.sever_message(
            "model",
            {
                "mode": "cca",
                "patient_id": self.lineEdit_id.text().strip(),
                "threshold": self.get_bar_threshold(),
            },
        )

    def decrease_threshold(self):
        """减少阈值"""
        current_value = self.progressBar.value()
        if current_value > 0:
            self.progressBar.setValue(current_value - 1)  # 每次减少 1 格
            self.progressBar.setFormat("%.2f" % (self.progressBar.value() / 100 + 0.2))
            self.progressBar.repaint()  # 强制刷新进度条
            # self.update_threshold_label()
        self.sever_message(
            "model",
            {
                "mode": "cca",
                "patient_id": self.lineEdit_id.text().strip(),
                "threshold": self.get_bar_threshold(),
            },
        )

    def get_bar_threshold(self):
        """根据进度条更新阈值显示"""
        current_value = self.progressBar.value()
        threshold = 0.20 + (current_value / 20) * (0.40 - 0.20)  # 计算阈值
        print("阈值：{:.2f}".format(threshold))
        return threshold

    def set_bar_threshold(self, threshold):
        """根据阈值设置显示"""
        current_value = (threshold - 0.2) * 100 + 1
        self.progressBar.setValue(int(current_value))  # 每次减少 1 格
        self.progressBar.setFormat("%.2f" % (self.progressBar.value() / 100 + 0.2))

    def get_Threshold(self):
        if self.pushButton_luru.text() == "录入":  # 说明没有录入患者信息
            self.error_notice("请先录入患者信息")
            return
        if self.pushButton_begin.text() == "结束查房":  # 说明没有结束查房
            self.error_notice("请先结束查房")
            return
        # 这里写开始训练的代码。
        self.client.start_train(self.lineEdit_id.text())

        # self.threshold = Get_Threshold_From_calm()
        # self.threshold_value = self.threshold.get_threshold()
        # self.set_bar_threshold(self.threshold_value)

    def get_searchBestFrequencies(self):
        print("[DEBUG get_searchBestFrequencies] 按钮'开始'被点击")
        if self.pushButton_luru.text() == "录入":  # 说明没有录入患者信息
            print("[DEBUG get_searchBestFrequencies] 校验失败：未录入患者信息")
            self.error_notice("请先录入患者信息")
            return
        if self.pushButton_begin.text() == "结束查房":  # 说明没有结束查房
            print("[DEBUG get_searchBestFrequencies] 校验失败：查房未结束")
            self.error_notice("请先结束查房")
            return
        print(f"[DEBUG get_searchBestFrequencies] 校验通过，患者ID: {self.lineEdit_id.text()}")
        # 这里写开始训练的代码。
        self.client.start_searchBestFrequencies(self.lineEdit_id.text())

    def send_change_frequencies(self):
        if self.pushButton_luru.text() == "录入":  # 说明没有录入患者信息
            self.error_notice("请先录入患者信息")
            return
        if self.pushButton_begin.text() == "结束查房":  # 说明没有结束查房
            self.error_notice("请先结束查房")
            return
        # 这里写开始训练的代码。
        self.client.change_frequencies(self.lineEdit_id.text())

    def cleartable(self):
        for row in range(self.tableWidget.rowCount()):
            for col in range(self.tableWidget.rowCount()):
                item = self.tableWidget.item(row, col)
                if item is not None:
                    item.setText("")  # 清空文本内容
        for ro in range(self.tableWidget_2.rowCount()):
            for co in range(self.tableWidget_2.rowCount()):
                item = self.tableWidget_2.item(ro, co)
                if item is not None:
                    item.setText("")  # 清空文本内容

    def keyPressEvent(self, event):
        global is_processing
        if not self.pushButton_begin.text() == "结束查房":
            print("按下：" + str(event.key()))

        else:
            return
            # self.pushButton_asr.setText('请在语音查房之前点击"开始查房"按钮')

    def on_pushButton_begin_clicked(self):
        self.round_start()
        self.pushButton_begin.clicked.disconnect()
        try:
            if self.pushButton_begin.text() == "开始查房":
                if self.pushButton_luru.text() != "清空":
                    self.word = "错误，请先输入病人信息！"
                    self.error_notice(self.word)
                    return
                # 点击 pushButton_begin 后的操作
                self.pushButton_begin.setText("结束查房")
                self.pushButton_begin.setStyleSheet(
                    "QPushButton {width: 136px;height: 44px;background: red;border-radius: 8px;}QPushButton{width: 72px; height: 25px;font-family: PingFangSC, PingFang SC;font-weight: 500;font-size: 18px;color: #FFFFFF;line-height: 25px;text-align: center;font-style: normal;}"
                )
                data = {
                    "func_selected": "round",
                    "question_info": None,
                    "ccaSwitch": None,
                    "selected": None,
                    "shanshuo": 0,
                    "running": True,
                }
                self.trigger_message("patient_ui", data)
                print(4)
                # self.sever_message("demo", data)
                self.clear_selected_button()
                self.button_clicked(self.get_selected_button())
                self._set_buttons_state_for_rounding()
                global questionInfo
                questionInfo = None
                self.update_button_styles()

            elif self.pushButton_begin.text() == "结束查房":
                self.pushButton_begin.setStyleSheet(
                    "QPushButton {width: 136px;height: 44px;background: #2864FF;border-radius: 8px;}QPushButton{width: 72px; height: 25px;font-family: PingFangSC, PingFang SC;font-weight: 500;font-size: 18px;color: #FFFFFF;line-height: 25px;text-align: center;font-style: normal;}"
                )
                self.pushButton_begin.setText("开始查房")
                self.pushButton_autocf.setEnabled(False)
                data = {
                    "func_selected": "welcome",
                    "question_info": None,
                    "ccaSwitch": None,
                    "selected": None,
                    "shanshuo": 0,
                    "running": False,
                }
                self.trigger_message("patient_ui", data)
                print(5)
                self._set_buttons_state_after_rounding()
                self.pushButton_asr.setText("提示：点击开始查房后，点击上方问题进行查房")
                self.update_button_styles()
        finally:
            self.pushButton_begin.clicked.connect(self.on_pushButton_begin_clicked)

    def _set_buttons_state_for_rounding(self):
        # 查房开始时设置按钮状态
        self.pushButton_autocf.setEnabled(True)
        self.pushButton_delete.setEnabled(False)
        self.pushButton_update.setEnabled(False)
        self.pushButton_add.setEnabled(False)
        self.pushButton_chaxun.setEnabled(False)
        self.pushButton_luru.setEnabled(False)
        self.pushButton_main.setEnabled(False)
        self.pushButton_main_2.setEnabled(False)

    def _set_buttons_state_after_rounding(self):
        # 查房结束后设置按钮状态
        self.pushButton_begin.setEnabled(True)
        self.pushButton_delete.setEnabled(True)
        self.pushButton_update.setEnabled(True)
        self.pushButton_add.setEnabled(True)
        self.pushButton_chaxun.setEnabled(True)
        self.pushButton_luru.setEnabled(True)
        self.pushButton_main.setEnabled(True)
        self.pushButton_main_2.setEnabled(True)
        self.pushButton_ready.setEnabled(False)

    def on_pushButton_delete_clicked(self):
        # 点击 pushButton_delete 后的操作
        pass  # 在这里实现相应的功能

    def on_pushButton_update_clicked(self):
        # 点击 pushButton_update 后的操作
        pass  # 在这里实现相应的功能

    def on_pushButton_add_clicked(self):
        # 点击 pushButton_add 后的操作
        pass  # 在这里实现相应的功能

    def change_main_2(self):  # 切换按钮 样式显示
        if self.ty == 1 or self.ty == 2:
            self.pushButton_main_2.setStyleSheet(
                "background-image: url(:/多功能智能查房系统/11111编组.png);border:none;"
            )
        elif self.ty == 3:
            self.pushButton_main_2.setStyleSheet(
                "background-image: url(:/多功能智能查房系统/chafang.png);border:none;"
            )

    def _on_search_complete(self, data):
        """算法个性化校准完成后的回调（在socketio后台线程中调用）"""
        print(f"[DEBUG _on_search_complete] 收到校准完成通知: {data}")
        print(f"[DEBUG _on_search_complete] 当前线程: {threading.current_thread().name}")
        # 通过 pyqtSignal 将弹窗操作切换到主线程执行
        print("[DEBUG _on_search_complete] 发射 search_complete_signal 信号...")
        self.search_complete_signal.emit()
        print("[DEBUG _on_search_complete] search_complete_signal 信号已发射")

    def _show_search_complete_popup(self):
        """在主线程中弹出校准完成提示（由信号触发）"""
        print("[DEBUG _show_search_complete_popup] 进入弹窗函数!")
        print(f"[DEBUG _show_search_complete_popup] 当前线程: {threading.current_thread().name}")
        self.calib_notice = NoticeWindow()
        self.calib_notice.pushButton_3.setText("算法个性化校准已完成\n已找到用户最佳刺激")
        show_window_on_appropriate_screen(self.calib_notice)
        print("[DEBUG _show_search_complete_popup] 提示弹窗已弹出")

    def error_notice(self, word):  # 错误提示框
        self.notice_eror = NoticeWindow()
        self.another_style = self.notice_eror.pushButton_3.styleSheet()
        self.notice_eror.pushButton_3.setStyleSheet(
            self.another_style + "color: red;"
        )  # 设置按钮文本颜色为红色
        self.notice_eror.pushButton_3.setText(word)
        self.current_style = self.notice_eror.pushButton_2.styleSheet()
        self.notice_eror.pushButton_2.setStyleSheet(
            self.current_style + "QPushButton {background-color: rgb(170, 0, 0);}"
        )  # 设置按钮背景为红色，警示错误
        show_window_on_appropriate_screen(self.notice_eror)

    def cor_notice(self, word):  # 正确提示框
        self.notice = NoticeWindow()
        self.notice.pushButton_3.setText(word)
        self.notice.show()

    def update_button_styles(self):
        for widget in self.findChildren(QPushButton):
            if widget.objectName() != "pushButton_main":
                if not widget.isEnabled():
                    # 如果按钮不可用，设置样式为原样式加上 line-through 文字装饰
                    style = widget.styleSheet()
                    if "text-decoration: line-through;" not in style:
                        widget.setStyleSheet(style + "QPushButton {text-decoration: line-through;}")
                else:
                    # 如果按钮可用，恢复原样式
                    style = widget.styleSheet()
                    lines = style.split(";")
                    new_style_lines = []
                    found_decoration = False
                    for line in lines:
                        if "text-decoration: line-through" not in line:
                            new_style_lines.append(line)
                        else:
                            found_decoration = True
                    if found_decoration:
                        new_style = ";".join(new_style_lines)
                        widget.setStyleSheet(new_style)

    def ready(self):
        # Recognition result polling is driven by Qt's event loop.  No worker
        # thread is allowed to read or mutate widgets or SQLite connections.
        if self.recognition_timer.isActive():
            self.recognition_timer.stop()
        if self.pushButton_luru.text() == "录入":
            self.word = "错误，请先输入病人信息！"
            self.error_notice(self.word)
            return

        if self.radioButton_cca.isChecked():  # 判断使用哪种算法
            self.sever_message(
                "model",
                {
                    "mode": "cca",
                    "patient_id": self.lineEdit_id.text().strip(),
                    "threshold": self.get_bar_threshold(),
                },
            )
        elif self.radioButton_train.isChecked():
            self.sever_message(
                "model",
                {
                    "mode": "train",
                    "patient_id": self.lineEdit_id.text().strip(),
                    "threshold": self.get_bar_threshold(),
                },
            )
        elif self.radioButton_cca_train.isChecked():
            self.sever_message(
                "model",
                {
                    "mode": "both_cca_train",
                    "patient_id": self.lineEdit_id.text().strip(),
                    "threshold": self.get_bar_threshold(),
                },
            )
        controller.click_secondary_screen_center()
        global questionInfo, stim
        if self.opensubwindow == 0:
            self.label_req.setText("正在等待患者将进行 一级需求菜单 选择")
            stim = 4
        elif self.opensubwindow == 1:
            self.pushButton_do.setEnabled(True)
            self.label_req.setText("正在等待患者进行 具体需求 选择 ")
            stim = 5
        else:
            self.pushButton_do.setEnabled(False)
            self.label_req.setText("正在等待患者进行 继续反馈 选择")
            stim = 2

        self.client.reset_result()
        self._recognition_ticks = 0
        if self.ty in (1, 2):
            self.client.start_processing("EEG", self.eeg_count, questionInfo[2], -1)
        else:
            self.client.start_processing("EEG", self.eeg_count, stim, self.opensubwindow)
            self.pushButton_ready_req.setEnabled(False)
        self.recognition_timer.start()

        global Flash_Ready_tag, Two_Delay, Flash_Ready_tag_req, Two_Delay_req
        self.update_button_styles()
        if self.ty != 3:
            self.pushButton_asr.setText("请等待病人回答...")
            self.pushButton_ready.setEnabled(False)
            self.test_begin = time.time()
            data = {
                "func_selected": "round",
                "question_info": questionInfo,
                "ccaSwitch": ccaSwitch,
                "selected": None,
                "shanshuo": 1,
                "running": True,
            }  # 向患者端发送信息
            self.trigger_message("patient_ui", data)
            print(6)
            self.update_button_styles()
        else:
            print("进入ready函数 需求")
            self.test_begin = time.time()
            data = {
                "func_selected": "demand",
                "question_info": None,
                "ccaSwitch": None,
                "selected": None,
                "shanshuo": 1,
                "running": True,
            }
            self.trigger_message("patient_ui", data)
            self.update_button_styles()

    @pyqtSlot()
    def _poll_recognition_result(self):
        """Poll network-owned result state from the Qt main thread."""
        self._recognition_ticks += 1
        result = int(self.client.consume_result() or 0)
        if result:
            self.recognition_timer.stop()
            self._handle_recognition_result(result)
        elif self._recognition_ticks >= self.eeg_count + 10:
            self.recognition_timer.stop()
            self._handle_recognition_timeout()

    def _demand_message(self, result):
        return {
            "func_selected": "demand",
            "question_info": None,
            "ccaSwitch": ccaSwitch,
            "selected": result - 1,
            "shanshuo": 0,
            "running": True,
        }

    def _handle_recognition_result(self, result):
        """Apply recognition output on the Qt main thread only."""
        global questionInfo
        self.pushButton_ready_req.setEnabled(True)
        self.update_button_styles()
        if self.ty in (1, 2):
            self.trigger_message(
                "patient_ui",
                {
                    "func_selected": "round",
                    "question_info": None,
                    "ccaSwitch": False,
                    "selected": result - 1,
                    "shanshuo": 0,
                    "running": True,
                },
            )
            self.patient_answer(result - 1, questionInfo[2])
            return

        self.trigger_message("patient_ui", self._demand_message(result))
        if self.opensubwindow == 0:
            self.a = result - 1
            self.opensubwindow = 1
            self.label_req.setText("点击'开始闪烁', 患者将进行具体需求选择")
        elif self.opensubwindow == 1:
            if result == 5:
                self.opensubwindow = 0
                self.label_req.setText("点击'开始闪烁', 患者将进行一级需求选择")
            else:
                self.b = result - 1
                self.answersCount += 1
                self.resql()
                now = datetime.now()
                patient_id = self.lineEdit_id.text()
                patient_name = self.lineEdit_name.text()
                self.sqlcursor.execute(
                    "INSERT INTO patient_requirements "
                    "(patient_id, patient_name, requirements, handle, handle_time) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (str(patient_id), patient_name, self.WORDS[self.a][self.b], "否", now),
                )
                self.connection.commit()
                self.label_req.setText(self.WORDS[self.a][self.b])
                self.opensubwindow = 2
                self.pushButton_ready_req.setEnabled(False)
        elif self.opensubwindow == 2:
            if result == 1:
                self.opensubwindow = 0
                self.label_req.setText("点击'开始闪烁', 患者将进行一级需求选择")
            elif result == 2:
                self.opensubwindow = 1
                self.label_req.setText("点击'开始闪烁', 患者将进行具体需求选择")
        self.update_button_styles()

    def _handle_recognition_timeout(self):
        """Finish an unanswered round on the Qt main thread."""
        global questionInfo
        if self.ty not in (1, 2):
            self.pushButton_ready_req.setEnabled(True)
            self.update_button_styles()
            return
        self.patient_answer(-1, questionInfo[2])
        timeout_question = list(questionInfo)
        timeout_question[1] += "（回答超时，请重试）"
        self.pushButton_asr.setText("病人回答超时了，请重新提问")
        self.trigger_message(
            "patient_ui",
            {
                "func_selected": "round",
                "question_info": timeout_question,
                "ccaSwitch": ccaSwitch,
                "selected": None,
                "shanshuo": 0,
                "running": False,
            },
        )

    @pyqtSlot()
    def shutdown_runtime(self):
        self.recognition_timer.stop()
        self.client.shutdown()
        if self.client_thread.is_alive() and self.client_thread is not threading.current_thread():
            self.client_thread.join(timeout=2.0)
    # ===== 树状问题列表相关方法 =====

    def _setup_question_tree(self):
        """初始化 QTreeWidget 替换原来的扁平按钮列表"""
        # 清除 verticalLayout 中已有的 pushButton 控件
        layout = self.verticalLayout
        while layout.count() > 0:
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # 创建分类管理按钮（与 pushButton_add/delete/update 风格统一）
        category_button_style = (
            "QPushButton {\n"
            "    width: 80px;\n"
            "    height: 44px;\n"
            "    background: #FFFFFF;\n"
            "    border-radius: 8px;\n"
            "    font-family: PingFangSC, PingFang SC;\n"
            "    font-weight: 500;\n"
            "    font-size: 18px;\n"
            "    color: #2864FF;\n"
            "    line-height: 25px;\n"
            "    text-align: center;\n"
            "    font-style: normal;\n"
            "}\n"
        )

        self.pushButton_add_category = QtWidgets.QPushButton("添加分类")
        self.pushButton_add_category.setStyleSheet(category_button_style)
        self.pushButton_add_category.clicked.connect(self._on_add_category)

        self.pushButton_delete_category = QtWidgets.QPushButton("删除分类")
        self.pushButton_delete_category.setStyleSheet(category_button_style)
        self.pushButton_delete_category.clicked.connect(self._on_delete_category)

        # 将分类按钮添加到 page_5 上方（使用父控件定位）
        self.pushButton_add_category.setParent(self.page_5)
        self.pushButton_add_category.setGeometry(QtCore.QRect(240, 40, 100, 30))
        self.pushButton_add_category.show()

        self.pushButton_delete_category.setParent(self.page_5)
        self.pushButton_delete_category.setGeometry(QtCore.QRect(350, 40, 100, 30))
        self.pushButton_delete_category.show()

        # 创建 QTreeWidget
        self.question_tree = QtWidgets.QTreeWidget()
        self.question_tree.setHeaderHidden(True)
        self.question_tree.setIndentation(20)
        self.question_tree.setAnimated(True)
        self.question_tree.setRootIsDecorated(True)
        self.question_tree.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.question_tree.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.question_tree.setStyleSheet(
            """
            QTreeWidget {
                background: rgba(9, 20, 39, 230);
                border: none;
                color: white;
                font-family: PingFangSC, PingFang SC;
                font-size: 16px;
            }
            QTreeWidget::item {
                min-height: 36px;
                padding: 4px 8px;
                border-bottom: 1px solid rgba(255,255,255,10);
            }
            QTreeWidget::item:hover {
                background: rgba(40, 100, 255, 60);
            }
            QTreeWidget::item:selected {
                background: rgb(40, 100, 255);
                color: white;
            }
            QTreeWidget::branch:has-children:!has-siblings:closed,
            QTreeWidget::branch:closed:has-children:has-siblings {
                border-image: none;
                image: none;
            }
            QTreeWidget::branch:open:has-children:!has-siblings,
            QTreeWidget::branch:open:has-children:has-siblings {
                border-image: none;
                image: none;
            }
            QScrollBar:vertical {
                width: 8px;
                background: transparent;
            }
            QScrollBar::handle:vertical {
                border-radius: 4px;
                background: rgb(40, 100, 255);
                min-height: 30px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            """
        )
        self.question_tree.itemClicked.connect(self._on_tree_item_clicked)
        # 让 tree 在布局中扩展填充整个滚动区域
        self.question_tree.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding
        )
        # 关键：禁用 scrollArea 对子控件的自动缩放，让树自行决定高度
        self.scrollArea.setWidgetResizable(False)

        layout.addWidget(self.question_tree)

    def _on_add_category(self):
        """添加新分类，参照 Goadd 方式"""
        self._category_dialog = CategoryInputDialog()
        show_window_on_appropriate_screen(self._category_dialog)

    def _on_delete_category(self):
        """删除选中的分类及其下的问题（归入旧分类）"""
        item = self.question_tree.currentItem()
        if item is None:
            self.word = "错误，未选中分类！"
            self.error_notice(self.word)
            return
        if item.parent() is not None:
            self.word = "错误，请选中分类节点而非问题节点！"
            self.error_notice(self.word)
            return
        category_name = item.text(0)
        if category_name == "旧分类":
            self.word = "错误，不能删除'旧分类'！"
            self.error_notice(self.word)
            return

        dialog = SeDialog()
        dialog.pushButton_3.setText(f"确定要删除分类'{category_name}'吗？\n其下的问题将移至'旧分类'")
        show_window_on_appropriate_screen(dialog)

        # 设置标志让 SeDialog 回调走分类删除流程
        self._is_category_delete = True
        self._pending_delete_category = category_name

    def _do_delete_category(self):
        """真正执行分类删除"""
        category_name = getattr(self, '_pending_delete_category', None)
        self._is_category_delete = False
        if not category_name:
            return
        self.resql()
        # 获取旧分类 ID
        self.sqlcursor.execute("SELECT category_id FROM question_categories WHERE category_name = '旧分类'")
        old_cat = self.sqlcursor.fetchone()
        if old_cat:
            old_cat_id = old_cat[0]
            # 获取要删除分类的 ID
            self.sqlcursor.execute(
                "SELECT category_id FROM question_categories WHERE category_name = ?",
                (category_name,),
            )
            del_cat = self.sqlcursor.fetchone()
            if del_cat:
                # 将该分类下的问题移到旧分类
                self.sqlcursor.execute(
                    "UPDATE questions SET category_id = ? WHERE category_id = ?",
                    (old_cat_id, del_cat[0]),
                )
                # 删除分类
                self.sqlcursor.execute(
                    "DELETE FROM question_categories WHERE category_id = ?",
                    (del_cat[0],),
                )
                self.connection.commit()
        self._pending_delete_category = None
        self._is_category_delete = False
        self.question_query()
        self.msg = NoticeWindow()
        self.msg.pushButton_3.setText("分类已删除，问题已移至'旧分类'")
        show_window_on_appropriate_screen(self.msg)
        self.clear_selected_button()

    def _on_tree_item_clicked(self, item, column):
        """树节点点击事件：问题节点触发查房，分类节点展开/折叠"""
        if item.parent() is not None:
            # 这是问题节点（有父节点 = 属于某个分类）
            self._handle_question_click(item)
        # 分类节点点击只展开/折叠，不做其他处理

    def _handle_question_click(self, item):
        """处理问题节点点击（复制原 button_clicked 逻辑）"""
        # 取消其他节点的选中样式
        for i in range(self.question_tree.topLevelItemCount()):
            cat_item = self.question_tree.topLevelItem(i)
            for j in range(cat_item.childCount()):
                child = cat_item.child(j)
                if child is not item:
                    child.setSelected(False)

        # 查找对应的 question_info
        question_text = item.text(0)
        for row in self.results:
            if row[1] == question_text:
                self.question_info = []
                for val in row:
                    if val is not None:
                        self.question_info.append(val)
                # 触发原有点击逻辑
                self.item_select(self.question_info)
                break

    def _get_selected_question_item(self):
        """获取当前选中的问题节点（子节点），返回 QTreeWidgetItem 或 None"""
        item = self.question_tree.currentItem()
        if item and item.parent() is not None:
            return item
        return None

    def question_query(self):
        """用树状结构加载问题列表：分类 → 问题"""
        self.resql()
        tree = self.question_tree
        tree.clear()

        # 1. 查询当前类型的所有分类
        self.sqlcursor.execute(
            "SELECT category_id, category_name FROM question_categories WHERE type = ? ORDER BY sequence",
            (self.ty,),
        )
        categories = self.sqlcursor.fetchall()
        category_map = {cat[0]: cat[1] for cat in categories}

        # 2. 查询当前类型的所有问题
        query = "SELECT * FROM questions WHERE type = ? ORDER BY sequence"
        self.sqlcursor.execute(query, (self.ty,))
        self.results = self.sqlcursor.fetchall()

        # 3. 按分类分组问题
        cat_questions = {}
        for cat_id in category_map:
            cat_questions[cat_id] = []
        uncategorized = []
        for row in self.results:
            cat_id = row[-1] if len(row) > 13 else None
            if cat_id in cat_questions:
                cat_questions[cat_id].append(row)
            else:
                uncategorized.append(row)

        # 4. 构建树节点
        for cat_id, cat_name in category_map.items():
            cat_item = QtWidgets.QTreeWidgetItem(tree)
            cat_item.setText(0, cat_name)
            cat_item.setData(0, QtCore.Qt.UserRole, {"type": "category", "category_id": cat_id})
            cat_item.setForeground(0, QtGui.QBrush(QtCore.Qt.white))
            font = cat_item.font(0)
            font.setBold(True)
            font.setPointSize(12)
            cat_item.setFont(0, font)
            cat_item.setSizeHint(0, QtCore.QSize(0, 38))
            cat_item.setExpanded(True)

            for row in cat_questions.get(cat_id, []):
                child = QtWidgets.QTreeWidgetItem(cat_item)
                child.setText(0, row[1])  # question_text
                child.setForeground(0, QtGui.QBrush(QtCore.Qt.white))
                child.setData(0, QtCore.Qt.UserRole, {
                    "type": "question",
                    "question_id": row[0],
                    "answer_num": row[2],
                })
                child.setSizeHint(0, QtCore.QSize(0, 34))

        # 根据内容量设置最小高度，确保树能完整显示（每项约 36px）
        total_items = len(categories) + len(self.results)
        self.scrollAreaWidgetContents.setMinimumHeight(max(total_items * 38, 400))

    def set_buttons_enabled(self):  # 设置问题树可用
        if hasattr(self, 'question_tree'):
            self.question_tree.setEnabled(True)

    def set_buttons_disabled(self):  # 设置问题树禁用
        if hasattr(self, 'question_tree'):
            self.question_tree.setEnabled(False)

    #  选择样式变换（适配树状结构）
    def button_clicked(self, clicked_item):
        """在树中选中指定的问题节点"""
        if isinstance(clicked_item, QtWidgets.QTreeWidgetItem):
            self.question_tree.setCurrentItem(clicked_item)
            self._handle_question_click(clicked_item)

    def item_select(self, question_info):
        print("item_select")
        sender = self.sender()
        self.startTime = time.time()
        if sender != None:
            name = 1
            if name == 1:
                global ccaSwitch, answerNum, questionInfo
                questionInfo = question_info
                ccaSwitch = True
                answerNum = question_info[2]
                if cf_test == 1:
                    if answerNum <= 1:
                        self.label = 0
                    else:
                        self.curr_index += 1
                        self.label = self.curr_index % 5
                        if self.label == 0:
                            self.label = 5

                    if "    请看" in question_info[1]:
                        print("修改了请看几")
                        index = question_info[1].find("    请看")
                        question_info[1] = question_info[1][:index]
                    question_info[1] = question_info[1] + "    请看" + str(self.label)
                # 更换题目
                global stim
                stim = question_info[2]
                # doctorWin.FBCCA = FBCCA(stim)  # 实例化FBCCA类
                doctorWin.targets_frq = getattr(WordTextS, f"frequency_list{stim}")
                if doctorWin.targets_frq[0] != 34:
                    doctorWin.targets_frq.insert(0, 34)
                print(doctorWin.targets_frq)
                # doctorWin.reference_signals = doctorWin.FBCCA.get_reference_signal(num_harmonics=3,
                #                                                                    targets=self.targets_frq)
                # doctorWin.fb_weight = [math.pow(i, -1.25) + 0.25 for i in
                #                        range(1,
                #                              doctorWin.FBCCA.Nm + 1)]  # Assign a weight to each filter (w),a=1.25,b=0.25
                if "（回答超时，请重试）" in question_info[1]:
                    question_info[1] = question_info[1].replace("（回答超时，请重试）", "")
                data = {
                    "func_selected": "round",
                    "question_info": question_info,
                    "ccaSwitch": ccaSwitch,
                    "selected": None,
                    "shanshuo": 0,
                    "running": False,
                }  # 向左窗口发送信息
                print(123131231312312, question_info)
                self.trigger_message("patient_ui", data)
                print(8)
                self.pushButton_ready.setEnabled(True)
                self.pushButton_asr.setText("当前问题：" + question_info[1])
                self.update_button_styles()
            else:
                self.error_notice("请完善患者信息")
        else:
            pass

    def round_start(self):
        if self.pushButton_begin.text() == "开始查房":
            # 获取QScrollArea中的所有QPushButton
            if self.pushButton_luru.text() == "清空":
                print("kaishichafang")
                self.pushButton_change.setEnabled(False)
                self.question_given()
                # self.start_auto_execution(self.loop_count, self.resultss)  自动查房demo
            else:
                return
        else:
            self.round_end()

    def question_given(self):
        """准备查房：重新加载问题树并准备 question_info 列表"""
        self.resql()
        self.question_query()
        query = "SELECT * FROM questions WHERE type = ? ORDER BY sequence"
        self.sqlcursor.execute(query, (self.ty,))
        results = self.sqlcursor.fetchall()
        self.results = results
        # 树结构中点击问题节点会通过 _on_tree_item_clicked → _handle_question_click 触发 item_select

    def start_auto_execution(self, loop_count, Result):  # 自动查房 loop_count为循环次数
        self.Result = Result
        self.loop_count = loop_count
        self.timer = QTimer()
        self.timer.timeout.connect(lambda: self.auto_execute(self.Result))
        self.execution_count = 0
        self.current_index = 0
        self.is_paused = False
        self.timer.start(self.record_time)  # 10000 毫秒即 10 秒
        self.auto_execute(self.Result)

    def auto_execute(self, Result):  # 自动执行查房函数
        self.Result = Result
        print("result", self.Result)
        if (
            not self.is_paused
            and self.current_index < len(self.Result)
            and self.execution_count < self.loop_count
        ):
            print("自动查房进行中，当前索引：", self.current_index)
            row = self.Result[self.current_index]
            question_info = []
            for i in range(len(row)):
                if row[i] is not None:
                    question_info.append(row[i])
            self.item_select(question_info)
            self.ready()

            self.current_index += 1
            if self.current_index == len(self.Result):
                self.current_index = 0
                self.execution_count += 1
        else:
            if self.execution_count >= self.loop_count:
                print("自动查房结束")
                self.timer.stop()
            self.ready()

    def stop_current_operation(self):  # 自动查房停止
        if self.timer is not None:
            self.timer.stop()

    def start_from_beginning(self):  # 重新开始自动查房
        self.current_index = 0
        self.execution_count = 0
        if self.timer is None:
            try:
                self.start_auto_execution(self.loop_count, self.Result)
            finally:
                return
        else:
            self.timer.start(self.record_time)

    def pause(self):  # 暂停自动查房
        self.is_paused = True

    def esc(self):  # 退出自动查房
        if self.pushButton_auto_esc.text() == "停止":
            self.execution_count = 0
            self.current_index = 0
            self.is_paused = False
            self.clear_selected_button()
            self.set_buttons_enabled()
            data = {
                "func_selected": "welcome",
                "question_info": None,
                "ccaSwitch": None,
                "selected": None,
                "shanshuo": 0,
            }
            self.trigger_message("patient_ui", data)
            print(10)
            self.pushButton_asr.setText("提示：点击开始查房后，按F4或脚踏板进行7秒的语音查房，或点击上方问题")
            self.pushButton_auto_esc.setText("重查")
            self.pushButton_autocf.setText("自动查房")
            self.stop_current_operation()
        elif self.pushButton_auto_esc.text() == "重查":
            self.pushButton_auto_esc.setEnabled(True)
            self.update_button_styles()
            self.set_buttons_disabled()
            self.pushButton_auto_esc.setText("停止")
            self.pushButton_autocf.setText("暂停自动查房")
            self.start_from_beginning()

    def continue_execution(self):  # 继续自动查房
        self.is_paused = False
        if self.execution_count < self.loop_count:
            self.timer.start(self.record_time)

    def round_end(self):
        try:
            self.stop_current_operation()
        finally:
            pass
        self.pushButton_change.setEnabled(True)
        buttons = self.scrollArea.findChildren(QPushButton)
        for button in buttons:
            try:
                button.clicked.disconnect()
            except TypeError:
                # Ignore error if the connection doesn't exist
                pass
        self.pushButton_autocf.setText("自动查房")
        self.pushButton_auto_esc.setText("停止")
        self.pushButton_auto_esc.setEnabled(False)
        self.update_button_styles()
        self.set_buttons_enabled()
        self.question_query()

    def question_delete(self):
        item = self.get_selected_button()  # 获取选中的问题节点（QTreeWidgetItem）
        if item:
            question_text = item.text(0)
            self.sql = "DELETE FROM questions WHERE question_text = ?"
            self.val = (question_text,)
            self.dialog = SeDialog()
            self.dialog.pushButton_3.setText("确定要删除吗？")
            show_window_on_appropriate_screen(self.dialog)
        else:
            self.word = "错误，未选中问题！"
            self.error_notice(self.word)
            return

    def question_update(self):
        self.addq = QuestionWindow()
        self.addq.label.setText("修改问题、答案和数量")
        self.resql()
        self.sqlcursor.execute("SELECT * FROM questions")
        results = self.sqlcursor.fetchall()
        item = self.get_selected_button()  # 获取选中的问题节点
        self.question_id = None
        if item is not None:
            question_text = item.text(0)
            for index, row in enumerate(results):
                if row[1] == question_text:
                    self.question_id = row[0]
                    self.addq.lineEdit.setText(str(row[1]))
                    self.addq.lineEdit_3.setText(str(row[2]))
                    self.addq.textEdit.setText(";".join(row[3 : 3 + int(row[2])]))
                    # 预选分类
                    self.addq._refresh_category_combo()
                    current_cat_id = row[13] if len(row) > 13 else None
                    if current_cat_id is not None:
                        for i in range(self.addq.comboBox_category.count()):
                            if self.addq.comboBox_category.itemData(i) == current_cat_id:
                                self.addq.comboBox_category.setCurrentIndex(i)
                                break
                    break
        if item is None:
            self.word = "错误，未选中问题！"
            self.error_notice(self.word)
            return
        show_window_on_appropriate_screen(self.addq)
        self.what = 1

    def resql(self):  # 重连数据库
        if self.sqlcursor:
            try:
                self.sqlcursor.close()
            except Exception as e:
                print(f"Error occurred while closing the cursor: {e}")
            finally:
                self.sqlcursor = None

        try:
            self.sqlcursor = self.sqlConnect()
        except Exception as e:
            print(f"Failed to reconnect the database cursor: {e}")

    def query_history(self):  # 查询查房、需求历史记录
        patient_id = self.lineEdit_id.text()
        if self.pushButton_luru.text() == "录入":
            if patient_id == "" and self.lineEdit_name.text() == "" and self.lineEdit_age.text() == "":
                return
            self.ac = "错误，请先完善患者信息！"
            self.error_notice(self.ac)
            self.cleartable()
            return
        self.resql()
        if self.stackedWidget_2.currentIndex() == 0:  # 查房结果
            # 获取行数和列数
            rowCount = self.tableWidget.rowCount()
            columnCount = self.tableWidget.columnCount()

            # 遍历所有单元格清除内容
            for row in range(rowCount):
                for col in range(columnCount):
                    item = self.tableWidget.item(row, col)
                    if item is not None:
                        item.setText("")  # 清空文本内容

            self.sqlcursor.execute(
                "WITH ranked_answers AS (SELECT patient_id, question_text, answer_text, test_time, ROW_NUMBER() OVER (PARTITION BY patient_id, question_text ORDER BY test_time DESC) AS row_num FROM patient_answer) SELECT ra.question_text, MAX(CASE WHEN ra.row_num = 1 THEN ra.answer_text END) AS first_result, MAX(CASE WHEN ra.row_num = 2 THEN ra.answer_text END) AS second_result, MAX(CASE WHEN ra.row_num = 3 THEN ra.answer_text END) AS third_result, MAX(CASE WHEN ra.row_num = 4 THEN ra.answer_text END) AS fourth_result FROM ranked_answers ra WHERE ra.patient_id = ? AND ra.row_num <= 4 AND ( (ra.row_num = 1 AND ra.test_time >= datetime('now', '-1 hours')) OR (ra.row_num > 1 AND ra.test_time >= datetime('now', '-3 days')) ) GROUP BY ra.patient_id, ra.question_text ORDER BY ra.patient_id, ra.question_text, ra.row_num",
                (patient_id,),
            )
            query_result = self.sqlcursor.fetchall()

            if not query_result:  # 如果查询结果为空
                self.stackedWidget.setCurrentIndex(0)  # 设置 stackedWidget 为第一个页面，即没有画面
            else:
                self.stackedWidget.setCurrentIndex(2)  # 设置 stackedWidget 为第三个页面，显示表单。

            for i, row in enumerate(query_result):
                self.tableWidget.insertRow(i)
                for j, value in enumerate(row):
                    item = QTableWidgetItem(str(value))
                    self.tableWidget.setItem(i, j, item)
        elif self.stackedWidget_2.currentIndex() == 1:  # 需求结果
            rowCount = self.tableWidget_2.rowCount()
            columnCount = self.tableWidget_2.columnCount()

            # 遍历所有单元格清除内容
            for row in range(rowCount):
                for col in range(columnCount):
                    item = self.tableWidget_2.item(row, col)
                    if item is not None:
                        item.setText("")  # 清空文本内容
            self.resql()
            self.sqlcursor.execute(
                "SELECT  requirements, handle_time ,end_time FROM patient_requirements WHERE patient_id = ? AND handle = '是'",
                (patient_id,),
            )
            query_result = self.sqlcursor.fetchall()
            if not query_result:  # 如果查询结果为空
                self.stackedWidget.setCurrentIndex(1)  # 设置 stackedWidget 为第一个页面
            else:
                self.stackedWidget.setCurrentIndex(3)  # 设置 stackedWidget 为第三个页面
            for i, row in enumerate(query_result):
                self.tableWidget_2.insertRow(i)
                for j, value in enumerate(row):
                    item = QTableWidgetItem(str(value))
                    self.tableWidget_2.setItem(i, j, item)
        self.plot_and_display()

    def clear_selected_button(self):
        """清除树中的选中状态"""
        if hasattr(self, 'question_tree'):
            self.question_tree.clearSelection()
            self.question_tree.setCurrentItem(None)

    def update_time(self):
        current_time = QTime.currentTime().toString("hh:mm:ss")
        self.label_time.setText(current_time)
        current_date = QDate.currentDate().toString("yyyy/MM/dd")
        self.label_date.setText(current_date)
        current_weekday = QDate.currentDate().toString("dddd")
        self.label_week.setText(current_weekday)

    def update_req(self):
        patient_id = self.lineEdit_id.text()
        if patient_id == "":
            self.label_req.setText("请录入患者信息！")
            return
        self.cursor = None
        self.cursor = self.sqlConnect()
        self.cursor.execute(
            "SELECT requirements FROM patient_requirements WHERE patient_id = ? AND handle = '否'",
            (patient_id,),
        )
        query_result = self.cursor.fetchall()
        # 处理查询结果
        requirements = []
        for result in query_result:
            requirements.append(result[0])  # 假设查询结果是一列需求，直接加入列表
        if not requirements:
            requirements = ["请等待患者响应..."]
        self.label_req.setText("\t".join(requirements))
        self.cursor.close()
        return requirements

    def Goadd(self):
        self.question = QuestionWindow()
        self.what = 0
        # self.question.show()
        show_window_on_appropriate_screen(self.question)
        for i in range(self.verticalLayout.count()):
            button = self.verticalLayout.itemAt(i).widget()
            button.setStyleSheet(
                "QPushButton {min-width: 693px; max-width: 693px; min-height: 40px; max-height: 40px; background: rgba(9, 20, 39, 1); opacity: 0.2;}"
            )

    def Gochaxun(self):
        # if self.ty == 1 or 2:
        self.chaxun = SelectPatientWindow(self)
        self.chaxun.patient_query()
        self.chaxun.pushButton_2.clicked.connect(lambda: self.chaxun.on_pushButton_2_clicked())
        # self.chaxun.show()
        show_window_on_appropriate_screen(self.chaxun)

    def logochange(self):  # 切换医生护士查房
        if self.ty == 1:
            self.listView_11.setStyleSheet("background-image: url(:/多功能智能查房系统/护士.png);")
            self.ty = 2
            if not qq.empty():
                while not qq.empty():
                    qq.get()  # 取出并删除队列中的元素，直到队列为空
            qq.put(self.ty)
            doctorWin.question_query()
        elif self.ty == 2:
            self.listView_11.setStyleSheet("background-image: url(:/多功能智能查房系统/医生.png);")
            self.ty = 1
            if not qq.empty():
                while not qq.empty():
                    qq.get()  # 取出并删除队列中的元素，直到队列为空
            qq.put(self.ty)
            doctorWin.question_query()

    def gomain(self):
        self.pushButton_ready_req.setEnabled(True)
        self.opensubwindow == 0
        self.update_button_styles()
        data = {
            "func_selected": "welcome",
            "question_info": None,
            "ccaSwitch": None,
            "selected": None,
            "shanshuo": 0,
        }
        self.trigger_message("patient_ui", data)
        print(11)
        self.close()
        self.stackedWidget_2.setCurrentIndex(2)
        show_window_on_appropriate_screen(window)

    def goauto(self):
        if self.pushButton_autocf.text() == "自动查房":
            auto = auto_CF_win()
            # auto.show()
            show_window_on_appropriate_screen(auto)
            self.pushButton_auto_esc.setEnabled(True)
            self.update_button_styles()
        elif self.pushButton_autocf.text() == "暂停自动查房":
            self.pause()
            self.pushButton_autocf.setText("继续自动查房")
        elif self.pushButton_autocf.text() == "继续自动查房":
            self.continue_execution()
            self.pushButton_autocf.setText("暂停自动查房")
        else:
            return

    def gorequire(self):
        self.pushButton_ready_req.setEnabled(True)
        self.update_button_styles()
        self.opensubwindow == 0
        self.change_main_2()
        global winSelect
        self.question_query()
        if self.stackedWidget_2.currentIndex() == 0:
            self.stackedWidget_2.setCurrentIndex(1)
            self.stackedWidget.setCurrentIndex(3)
            self.ty = 3
            winSelect = "demand"
            self.update_req()
            if doctorWin.ty == 3 and self.pushButton_luru.text() == "清空":
                self.demandSTime = time.time()
                data = {
                    "func_selected": "demand_entry",
                    "question_info": None,
                    "ccaSwitch": None,
                    "selected": None,
                    "shanshuo": 0,
                }
                self.trigger_message("patient_ui", data)
                print(12)
                print("二号")
                charge = 1  # 每次进来假装处理过需求的问题了
                self.query_history()
        elif self.stackedWidget_2.currentIndex() == 1:
            self.opensubwindow = 0
            self.stackedWidget_2.setCurrentIndex(0)
            self.stackedWidget.setCurrentIndex(2)
            self.pushButton_luru.setEnabled(True)
            self.pushButton_chaxun.setEnabled(True)
            self.ty = 1
            winSelect = "doctor"
            data = {
                "func_selected": "welcome",
                "question_info": None,
                "ccaSwitch": None,
                "selected": None,
                "shanshuo": 0,
            }
            self.trigger_message("patient_ui", data)
            print(13)
            self.question_query()
        if self.pushButton_luru.text() == "清空":
            self.label_req.setText("点击'开始闪烁'，患者将进行一级需求选择")
        elif self.pushButton_luru.text() == "录入":
            self.label_req.setText("请录入患者信息！")
        if self.pushButton_luru.text() == "录入":
            data = {
                "func_selected": "welcome",
                "question_info": None,
                "ccaSwitch": None,
                "selected": None,
                "shanshuo": 0,
            }
            self.trigger_message("patient_ui", data)
            print(14)
        self.change_main_2()

    def luru(self):
        self.pushButton_ready_req.setEnabled(True)
        self.update_button_styles()
        self.opensubwindow == 0
        self.resql()
        if self.pushButton_luru.text() == "清空":
            data = {
                "func_selected": "welcome",
                "question_info": None,
                "ccaSwitch": None,
                "selected": None,
                "shanshuo": 0,
            }
            self.trigger_message("patient_ui", data)
            print(15)
            self.opensubwindow = 0
            self.pushButton_luru.setText("录入")
            # 清空lineEdit_name、lineEdit_age、lineEdit_id文本并设置为可编辑
            self.lineEdit_name.clear()
            self.lineEdit_name.setReadOnly(False)
            self.lineEdit_age.clear()
            self.lineEdit_age.setReadOnly(False)
            self.lineEdit_id.clear()
            self.lineEdit_id.setReadOnly(False)
            # 设置radioButton、radioButton_2为未选中，可用
            self.radioButton.setChecked(False)
            self.radioButton.setEnabled(True)
            self.radioButton_2.setChecked(False)
            self.radioButton_2.setEnabled(True)
            self.label_req.setText("请录入患者信息！")
            self.cleartable()
            self.update_req()
            self.query_history()
            self._load_avatar()
        else:
            name = self.lineEdit_name.text()
            age = self.lineEdit_age.text()
            id = self.lineEdit_id.text()
            if name == "" or age == "" or id == "":
                self.word = "错误，填写信息不完整！"
                self.error_notice(self.word)
                return
            if not age.isdigit():
                # 如果年龄不是数字，显示相应的错误提示消息
                self.word = "错误，年龄必须为数字！"
                self.error_notice(self.word)
                return
            try:
                age = int(age)  # 尝试将 age 转换为整数
            except ValueError:
                self.wor = "错误，年龄不是有效的数字！"
                self.error_notice(self.wor)
                return
            if age >= 120 or age < 0:
                self.word = "错误，年龄不符合实际！"
                self.error_notice(self.word)
                return
            # 定义一个正则表达式，用于匹配包含中文字符的字符串
            pattern = re.compile(r"[\u4e00-\u9fa5]")

            # 判断ID是否为空或包含中文字符
            if id is None or pattern.search(id):
                # 如果ID为空或包含中文字符，显示相应的错误提示消息
                self.word = "错误，病历号必须为字母或数字！"
                self.error_notice(self.word)
                return
            if self.radioButton.isChecked():
                gender = "男"
            elif self.radioButton_2.isChecked():
                gender = "女"
            else:
                self.word = "错误，未选中性别！"
                self.error_notice(self.word)
                return  # 跳出函数
            age = self.lineEdit_age.text()
            id = self.lineEdit_id.text()
            # 校验 id 是否包含空格或非英文、数字字符
            if re.search(r"[^a-zA-Z0-9]", id) or " " in id:
                self.word = "错误，病历号只能包含数字和英文字符"
                self.error_notice(self.word)
                return
            self.sqlcursor.execute("SELECT patient_id FROM patients WHERE patient_id = ?", (id,))
            result = self.sqlcursor.fetchone()
            if result:
                self.word = "错误，当前病历号已存在！"
                self.error_notice(self.word)
                return  # 跳出函数
            else:
                self.sqlcursor.execute(
                    "INSERT INTO patients (patient_id, patient_name, patient_gender, patient_age) VALUES (?, ?, ?, ?)",
                    (str(id), name, gender, int(age)),
                )
                self.connection.commit()
                self.notice_error = NoticeWindow()
                self.notice_error.pushButton_3.setText("录入成功！")
                if self.ty == 3:
                    data = {
                        "func_selected": "demand_entry",
                        "question_info": None,
                        "ccaSwitch": None,
                        "selected": None,
                        "shanshuo": 0,
                    }
                    self.trigger_message("patient_ui", data)
                    print(16)
                    print("三号")
                    charge = 1  # 每次进来假装处理过需求的问题了
                self.label_req.setText("点击'开始闪烁'，患者将进行一级需求选择")
                # self.notice_error.show()
                show_window_on_appropriate_screen(self.notice_error)
                # 设置lineEdit_name、lineEdit_age、lineEdit_id为只读
                doctorWin.lineEdit_name.setReadOnly(True)
                doctorWin.lineEdit_age.setReadOnly(True)
                doctorWin.lineEdit_id.setReadOnly(True)
                # 设置radioButton、radioButton_2为不可更改
                doctorWin.radioButton.setEnabled(False)
                doctorWin.radioButton_2.setEnabled(False)
                doctorWin.pushButton_luru.setText("清空")
                self.cleartable()
                self._save_avatar_for_patient(str(id))

    def draw_line_chart(self):
        pass

    def doreq(self):
        self.draw_line_chart()
        if "患者" in self.label_req.text():  # 如果有开始闪烁，说明当前没有需求
            self.w = "错误，请等待患者选择！"
            self.t = self.error_notice(self.w)
            return
        elif self.label_req.text() == "请录入患者信息！":
            self.w = "错误，请录入患者信息！"
            self.t = self.error_notice(self.w)
            return
        else:
            # 获取需求信息
            self.dia = SeDialog_req(doctorWin)
            self.dia.pushButton_3.setText("确定处理完成吗？")
            # self.dia.show()
            show_window_on_appropriate_screen(self.dia)

    def checklist_open(self):
        self.checklist_win = ChecklistWindow(self)
        show_window_on_appropriate_screen(self.checklist_win)

    def sqlConnect(self):
        db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hospital_rounds.db")
        self.connection = sqlite3.connect(db_path)
        cursor = self.connection.cursor()
        cursor.execute(
            """CREATE TABLE IF NOT EXISTS checklist_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id TEXT,
                patient_name TEXT,
                test_time TEXT,
                rass_status TEXT,
                understand_commands TEXT,
                keep_eyes_open TEXT,
                severe_vision_impairment TEXT,
                nystagmus_eyelid TEXT,
                photosensitivity_risk TEXT,
                vital_signs_stable TEXT,
                electrode_signal_quality TEXT,
                excessive_fatigue TEXT,
                screening_result TEXT
            )"""
        )
        self.connection.commit()
        return cursor

    def patient_answer(self, vepClass, answerNum):  # 将患者的选择存入数据库
        global patient_name, patient_id
        patient_name = self.lineEdit_name.text()
        patient_id = self.lineEdit_id.text()
        question_id = questionInfo[0]
        question_text = questionInfo[1]
        answer_text = questionInfo[vepClass + 3]
        if vepClass == -1:
            answer_text = "⚠回答超时⚠"
        begin_test_time = datetime.fromtimestamp(self.test_begin)
        # 获取当前的日期和时间
        now = datetime.now()
        microseconds = now.microsecond
        milliseconds = microseconds
        formatted_date = now.strftime("%Y-%m-%d %H:%M:%S") + ".{:06d}".format(milliseconds)
        self.resql()
        # 先查询 questions 表获取 type
        self.sqlcursor.execute("SELECT type FROM questions WHERE question_id = ?", (int(question_id),))
        result = self.sqlcursor.fetchone()
        if result:
            question_type = result[0]
            # 再执行插入 patient_answer 表操作
            self.sqlcursor.execute(
                "INSERT INTO patient_answer (patient_id, patient_name, question_id, question_text,"
                "answer_text,begin_test_time,test_time,question_type) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (
                    str(patient_id),
                    patient_name,
                    int(question_id),
                    question_text,
                    answer_text,
                    str(begin_test_time),
                    str(formatted_date),
                    question_type,
                ),
            )
            self.connection.commit()
            self.query_history()
            self.pushButton_asr.setText(f"病人已选择：{answer_text}")
        if cf_test == 1:
            self.test_end = time.time()
            self.sp_time = self.test_end - self.test_begin
            print(self.test_begin)
            now = datetime.now()
            microseconds = now.microsecond
            milliseconds = microseconds
            formatted_date = now.strftime("%Y-%m-%d %H:%M:%S") + ".{:06d}".format(milliseconds)
            begin_test_time = datetime.fromtimestamp(self.test_begin)
            print(self.test_begin)
            more_info = self.lineEdit_name_2.text()
            print(patient_name, answerNum, self.label, answer_text, self.sp_time, str(self.rr), self.test_end)
            try:
                self.sqlcursor.execute(
                    "INSERT INTO cf_test (name , class_num, label, result ,"
                    "sp_time, rr, begin_test_time,test_time, more_info) "
                    "VALUES (?,?,?,?,?,?,?,?,?)",
                    (
                        patient_name,
                        answerNum,
                        self.label,
                        answer_text,
                        str(self.sp_time),
                        str(self.rr),
                        str(begin_test_time),
                        str(formatted_date),
                        more_info,
                    ),
                )
                self.connection.commit()
                self.pushButton_asr.setText(f"病人已选择：{answer_text}")
                print("------------------------------------------------------")
            finally:
                # 无论是否发生异常，都会执行这里的代码块
                pass


class CognitionWindow(QMainWindow, Ui_cognition_ui):
    """独立的认知激活界面"""
    def __init__(self, client=None, doctorWin=None):
        super().__init__()
        self.setupUi(self)
        self.setWindowFlag(QtCore.Qt.FramelessWindowHint)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.client = client
        self.doctorWin = doctorWin
        self.is_activating = False
        self.activation_start_time = None
        self.activation_timer = None
        self.cognition_db_setup()

        self.pushButton_main.clicked.connect(self.gomain)
        self.pushButton_begin.clicked.connect(self.toggle_activation)
        self.pushButton_begin_2.clicked.connect(self.load_activation_history)
        self.pushButton_chaxun.clicked.connect(self.Gochaxun)
        self.pushButton_luru.clicked.connect(self.luru)
        self.pushButton_CheckList.clicked.connect(self.checklist_open)

        # 隐藏"开始闪烁"按钮（认知激活中不使用）
        self.pushButton_ready.hide()
        self.pushButton_ready_req.hide()

        # 默认值设置
        self.radioButton_flower.setChecked(True)
        self.radioButton_boat.setChecked(True)
        self.radioButton_imagine.setChecked(True)
        self.spinBox_cognition_count.setValue(1)

        self.sqlcursor = None
        self._temp_avatar_path = None

        # 头像框点击选择图片
        self.frame_8.installEventFilter(self)
        self._load_avatar()

        # 表格空时背景改为暗色，避免显示白色
        ss = self.tableWidget_2.styleSheet()
        ss = ss.replace(
            "    background-color: #FFFFFF;\n"
            "}",
            "    background-color: #091427;\n"
            "}"
        )
        self.tableWidget_2.setStyleSheet(ss)

    def _get_patient_id(self):
        return self.lineEdit_id.text().strip() if hasattr(self, 'lineEdit_id') else ""

    def _get_patient_name(self):
        return self.lineEdit_name.text().strip() if hasattr(self, 'lineEdit_name') else ""

    def eventFilter(self, obj, event):
        """拦截 frame_8 的鼠标点击事件，打开头像选择"""
        if obj == self.frame_8 and event.type() == QtCore.QEvent.MouseButtonPress:
            self.select_avatar()
            return True
        return super().eventFilter(obj, event)

    def _get_avatar_dir(self):
        avatars_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "imgs", "avatars")
        os.makedirs(avatars_dir, exist_ok=True)
        return avatars_dir

    def select_avatar(self):
        """打开文件对话框选择头像图片"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择头像图片", "",
            "图片文件 (*.png *.jpg *.jpeg *.bmp)"
        )
        if not file_path:
            return
        pid = self._get_patient_id()
        if pid:
            # 已有病历号，直接存为 {patient_id}.png
            avatars_dir = self._get_avatar_dir()
            dest_path = os.path.join(avatars_dir, f"{pid}.png").replace("\\", "/")
        else:
            # 还没录入，先存临时路径
            avatars_dir = self._get_avatar_dir()
            dest_path = os.path.join(avatars_dir, "_temp_avatar.png").replace("\\", "/")

        import shutil
        shutil.copy(file_path, dest_path.replace("/", os.sep))
        self._temp_avatar_path = dest_path
        self._apply_avatar_style(dest_path)

    def _apply_avatar_style(self, image_path):
        """设置 frame_8 的样式显示头像"""
        self.frame_8.setStyleSheet(
            f"border-image: url({image_path});"
        )

    def _get_default_avatar_path(self):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(base_dir, "多功能智能查房系统", "默认头像.png").replace("\\", "/")

    def _load_avatar(self):
        """根据当前病历号加载头像"""
        pid = self._get_patient_id()
        default_avatar = self._get_default_avatar_path()
        if not pid:
            # 恢复默认头像
            self._apply_avatar_style(default_avatar)
            self._temp_avatar_path = None
            return
        avatars_dir = self._get_avatar_dir()
        avatar_path = os.path.join(avatars_dir, f"{pid}.png").replace("\\", "/")
        if os.path.exists(avatar_path.replace("/", os.sep)):
            self._apply_avatar_style(avatar_path)
            self._temp_avatar_path = avatar_path
        else:
            self._apply_avatar_style(default_avatar)
            self._temp_avatar_path = None

    def cognition_db_setup(self):
        """创建认知激活结果表"""
        db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hospital_rounds.db")
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
        conn.commit()
        conn.close()

    def gomain(self):
        if self.is_activating:
            self.stop_activation()
        self.close()
        show_window_on_appropriate_screen(window)

    def toggle_activation(self):
        """切换激活状态"""
        if not self.is_activating:
            self.start_activation()
        else:
            self.stop_activation()

    def start_activation(self):
        """开始激活"""
        patient_id = self._get_patient_id()
        patient_name = self._get_patient_name()

        # 获取选中的激活内容
        selected_videos = []
        if self.radioButton_flower.isChecked():
            selected_videos.append("花")
        if self.radioButton_boat.isChecked():
            selected_videos.append("船")
        if self.radioButton_imagine.isChecked():
            selected_videos.append("运动想象")

        if not selected_videos:
            selected_videos = ["花", "船", "运动想象"]  # 默认全部

        # 修改按钮状态
        self.pushButton_begin.setText("停止激活")
        self.is_activating = True
        self.activation_start_time = datetime.now()
        self._last_cognition_record_count = None  # 重置记录计数，用于检测播放完成

        # 向患者端发送激活指令
        if self.client:
            data = {
                "cognition_activate": 1,
                "video_types": selected_videos,
                "patient_id": patient_id,
                "patient_name": patient_name,
            }
            self.client.async_send("patient_ui", data)
            print(f"[认知激活] 开始激活，视频类型: {selected_videos}")

        # 设置定时器轮询检查
        if self.activation_timer is None:
            self.activation_timer = QtCore.QTimer(self)
            self.activation_timer.timeout.connect(self._check_patient_response)
        self.activation_timer.start(1000)  # 每秒检查一次

    def stop_activation(self):
        """停止激活"""
        self.pushButton_begin.setText("开始激活")
        self.is_activating = False

        # 向患者端发送停止指令
        if self.client:
            self.client.async_send("patient_ui", {"cognition_activate": 0})

        if self.activation_timer:
            self.activation_timer.stop()

        # 延迟加载，等待患者端保存结果到数据库
        QtCore.QTimer.singleShot(1500, self.load_activation_history)
        self.activation_start_time = None
        print("[认知激活] 停止激活")

    def _check_patient_response(self):
        """检查患者端是否已保存结果"""
        if not self.is_activating:
            if self.activation_timer:
                self.activation_timer.stop()
            return
        # 轮询数据库：如果检测到新记录则自动停止激活并刷新表格
        db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hospital_rounds.db")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM cognition_activation_results")
        current_count = cursor.fetchone()[0]
        conn.close()

        if not hasattr(self, '_last_cognition_record_count') or self._last_cognition_record_count is None:
            self._last_cognition_record_count = current_count
        elif current_count > self._last_cognition_record_count:
            # 有新记录，说明患者端播放完成
            self._last_cognition_record_count = current_count
            self.stop_activation()
            return

        self.load_activation_history()

    def _save_activation_result(self, duration):
        """保存认知激活结果到数据库"""
        patient_id = self._get_patient_id()
        patient_name = self._get_patient_name()

        # 获取选中的激活内容
        content_parts = []
        if self.radioButton_flower.isChecked():
            content_parts.append("花朵开放")
        if self.radioButton_boat.isChecked():
            content_parts.append("小船前移")
        if self.radioButton_imagine.isChecked():
            content_parts.append("运动想象")
        activation_content = ",".join(content_parts) if content_parts else "全部"

        # 生成随机指标（模拟正常人数据）
        import random
        effective_duration = round(duration, 1)
        task_completion_rate = 100.0
        response_stability = round(random.uniform(0.80, 0.98), 2)
        fatigue_trends = ["稳定", "轻度上升", "稳定", "轻度上升", "稳定"]
        daily_changes = ["+2%", "+1%", "+3%", "+5%", "+2%"]
        fatigue_trend = random.choice(fatigue_trends)
        daily_change = random.choice(daily_changes)
        train_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hospital_rounds.db")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO cognition_activation_results 
               (patient_id, patient_name, activation_content, train_time, 
                effective_duration, task_completion_rate, response_stability, 
                fatigue_trend, daily_change, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (patient_id, patient_name, activation_content, train_time,
             effective_duration, task_completion_rate, response_stability,
             fatigue_trend, daily_change, datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        )
        conn.commit()
        conn.close()

        # 刷新显示
        self.load_activation_history()
        print(f"[认知激活] 结果已保存 - 时长:{effective_duration}s, 完成率:{task_completion_rate}%, 稳定性:{response_stability}")

    def load_activation_history(self):
        """从数据库加载激活历史到 tableWidget_2"""
        db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hospital_rounds.db")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        patient_id = self.lineEdit_id.text().strip() if hasattr(self, 'lineEdit_id') and self.lineEdit_id.text().strip() else ""
        if patient_id:
            cursor.execute(
                """SELECT train_time, effective_duration, task_completion_rate, 
                          response_stability, fatigue_trend, daily_change
                   FROM cognition_activation_results 
                   WHERE patient_id = ?
                   ORDER BY id DESC LIMIT 19""",
                (patient_id,)
            )
        else:
            conn.close()
            self.tableWidget_2.setRowCount(0)
            return
        results = cursor.fetchall()
        conn.close()

        # 清空表格
        self.tableWidget_2.setRowCount(0)
        self.tableWidget_2.setRowCount(19)

        for i, row in enumerate(results):
            for j, value in enumerate(row):
                item = QtWidgets.QTableWidgetItem(str(value) if value is not None else "")
                self.tableWidget_2.setItem(i, j, item)

    def resql(self):
        """重连数据库"""
        if self.sqlcursor:
            try:
                self.sqlcursor.close()
            except Exception as e:
                print(f"Error closing cursor: {e}")
            finally:
                self.sqlcursor = None
        try:
            db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hospital_rounds.db")
            self.db_conn = sqlite3.connect(db_path)
            self.connection = self.db_conn  # 兼容其他窗口使用 .connection 提交
            self.sqlcursor = self.db_conn.cursor()
        except Exception as e:
            print(f"Failed to reconnect database cursor: {e}")

    def Gochaxun(self):
        """打开患者查询窗口"""
        self.resql()
        self.chaxun = SelectPatientWindow(self)
        self.chaxun.patient_query()
        self.chaxun.pushButton_2.clicked.connect(lambda: self.chaxun.on_pushButton_2_clicked())
        show_window_on_appropriate_screen(self.chaxun)

    def luru(self):
        """录入或清空患者信息"""
        if self.pushButton_luru.text() == "清空":
            # 清空
            self.lineEdit_name.clear()
            self.lineEdit_name.setReadOnly(False)
            self.lineEdit_age.clear()
            self.lineEdit_age.setReadOnly(False)
            self.lineEdit_id.clear()
            self.lineEdit_id.setReadOnly(False)
            if hasattr(self, 'radioButton'):
                self.radioButton.setChecked(False)
                self.radioButton.setEnabled(True)
            if hasattr(self, 'radioButton_2'):
                self.radioButton_2.setChecked(False)
                self.radioButton_2.setEnabled(True)
            self.pushButton_luru.setText("录入")
            self.load_activation_history()
            self._load_avatar()
        else:
            # 录入
            name = self.lineEdit_name.text().strip()
            age = self.lineEdit_age.text().strip()
            pid = self.lineEdit_id.text().strip()
            if not name or not age or not pid:
                self._error_notice("错误，填写信息不完整！")
                return
            if not age.isdigit():
                self._error_notice("错误，年龄必须为数字！")
                return
            age_int = int(age)
            if age_int >= 120 or age_int < 0:
                self._error_notice("错误，年龄不符合实际！")
                return
            import re
            if re.search(r"[\u4e00-\u9fa5]", pid):
                self._error_notice("错误，病历号必须为字母或数字！")
                return
            if re.search(r"[^a-zA-Z0-9]", pid) or " " in pid:
                self._error_notice("错误，病历号只能包含数字和英文字符")
                return
            gender = ""
            if hasattr(self, 'radioButton') and self.radioButton.isChecked():
                gender = "男"
            elif hasattr(self, 'radioButton_2') and self.radioButton_2.isChecked():
                gender = "女"
            else:
                self._error_notice("错误，未选中性别！")
                return

            self.resql()
            self.sqlcursor.execute("SELECT patient_id FROM patients WHERE patient_id = ?", (pid,))
            if self.sqlcursor.fetchone():
                self._error_notice("错误，当前病历号已存在！")
                return

            self.sqlcursor.execute(
                "INSERT INTO patients (patient_id, patient_name, patient_age, patient_gender) VALUES (?, ?, ?, ?)",
                (pid, name, age, gender),
            )
            self.db_conn.commit()

            # 锁定编辑
            self.lineEdit_name.setReadOnly(True)
            self.lineEdit_age.setReadOnly(True)
            self.lineEdit_id.setReadOnly(True)
            if hasattr(self, 'radioButton'):
                self.radioButton.setEnabled(False)
            if hasattr(self, 'radioButton_2'):
                self.radioButton_2.setEnabled(False)
            self.pushButton_luru.setText("清空")
            self.load_activation_history()
            self._save_avatar_for_patient(pid)

    def _save_avatar_for_patient(self, pid):
        """录入时，将临时头像保存为 {pid}.png"""
        if not hasattr(self, '_temp_avatar_path') or not self._temp_avatar_path:
            return
        import shutil
        avatars_dir = self._get_avatar_dir()
        dest_path = os.path.join(avatars_dir, f"{pid}.png")
        src = self._temp_avatar_path.replace("/", os.sep)
        if os.path.exists(src) and src != dest_path:
            shutil.copy(src, dest_path)
            self._temp_avatar_path = dest_path.replace("\\", "/")
            self._apply_avatar_style(self._temp_avatar_path)

    def _error_notice(self, msg):
        """显示错误提示"""
        notice = NoticeWindow()
        notice.pushButton_3.setText(msg)
        show_window_on_appropriate_screen(notice)

    def checklist_open(self):
        """打开CheckList核查表"""
        self.checklist_win = ChecklistWindow(self)
        show_window_on_appropriate_screen(self.checklist_win)

    def send_change_frequencies(self):
        """认知激活界面不需要变更频率，空实现"""
        pass

    def update_button_styles(self):
        """认知激活界面不需要更新按钮样式，空实现"""
        pass

    def error_notice(self, msg):
        """认知激活界面的错误提示"""
        self._error_notice(msg)


class ChecklistWindow(QMainWindow):
    """ICU视觉SSVEP-BCI患者适用性核查表"""

    ITEMS = [
        ("当前RASS状态是否适合：", ["是", "否", "无法判断"]),
        ("能否理解简单指令：", ["能", "不能", "无法判断"]),
        ("能否睁眼并保持注视：", ["能", "不能", "无法判断"]),
        ("是否存在严重视力障碍：", ["是", "否", "无法判断"]),
        ("是否存在明显眼震或眼睑无法开启：", ["是", "否", "无法判断"]),
        ("是否存在光敏风险：", ["是", "否", "无法判断"]),
        ("当前生命体征是否稳定：", ["是", "否", "无法判断"]),
        ("电极接触和脑电信号质量是否合格：", ["是", "否", "无法判断"]),
        ("当前是否存在过度疲劳：", ["是", "否", "无法判断"]),
    ]

    RESULTS = ["推荐视觉SSVEP", "需要调整后重新评估", "暂不适合视觉SSVEP"]

    def __init__(self, doctorWin):
        super().__init__()
        self.doctorWin = doctorWin
        self.setWindowFlag(QtCore.Qt.FramelessWindowHint)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.setFixedSize(960, 800)

        central = QtWidgets.QWidget(self)
        self.setCentralWidget(central)

        # 半透明深色背景框
        bg = QtWidgets.QFrame(central)
        bg.setGeometry(QtCore.QRect(30, 15, 900, 770))
        bg.setStyleSheet(
            "background: rgba(9, 20, 39, 245); border-radius: 14px;"
        )

        # 标题
        title = QtWidgets.QLabel(bg)
        title.setGeometry(QtCore.QRect(100, 18, 700, 42))
        title.setText("ICU视觉SSVEP-BCI患者适用性核查表")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(
            "color: #FFFFFF; font-size: 24px; font-weight: bold;"
        )

        # 关闭按钮
        close_btn = QtWidgets.QPushButton(bg)
        close_btn.setGeometry(QtCore.QRect(840, 18, 42, 42))
        close_btn.setText("✕")
        close_btn.setStyleSheet(
            "QPushButton { color: #8899AA; font-size: 22px; background: transparent; border: none; }"
            "QPushButton:hover { color: #FFFFFF; }"
        )
        close_btn.clicked.connect(self.close)

        # 滚动区域
        scroll = QtWidgets.QScrollArea(bg)
        scroll.setGeometry(QtCore.QRect(25, 70, 850, 690))
        scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
            "QScrollBar:vertical { width: 8px; background: rgba(30, 50, 80, 100); border-radius: 4px; }"
            "QScrollBar::handle:vertical { background: #2864FF; border-radius: 4px; min-height: 30px; }"
            "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }"
        )
        scroll_widget = QtWidgets.QWidget()
        scroll_widget.setStyleSheet("background: transparent;")
        scroll.setWidget(scroll_widget)
        scroll.setWidgetResizable(True)

        layout = QtWidgets.QVBoxLayout(scroll_widget)
        layout.setSpacing(10)
        layout.setContentsMargins(15, 10, 15, 10)

        # 存储所有单选按钮组
        self.radio_groups = []

        # 创建评估项
        for idx, (label_text, options) in enumerate(self.ITEMS):
            item_frame = self._create_item_frame(label_text, options, idx)
            layout.addWidget(item_frame)

        # 分隔线
        sep = QtWidgets.QFrame()
        sep.setFrameShape(QtWidgets.QFrame.HLine)
        sep.setStyleSheet("background: rgba(40, 100, 255, 80); max-height: 2px;")
        layout.addWidget(sep)

        # 筛查结果
        result_label = QtWidgets.QLabel("筛查结果")
        result_label.setStyleSheet(
            "color: #FFAA00; font-size: 20px; font-weight: bold; padding-top: 8px;"
        )
        layout.addWidget(result_label)

        result_frame = QtWidgets.QFrame()
        result_frame.setStyleSheet("background: rgba(40, 100, 255, 30); border-radius: 8px; padding: 10px;")
        result_layout = QtWidgets.QVBoxLayout(result_frame)
        result_layout.setSpacing(8)

        self.result_group = QtWidgets.QButtonGroup(self)
        for r_text in self.RESULTS:
            radio = QtWidgets.QRadioButton(r_text)
            radio.setStyleSheet(self._radio_style())
            self.result_group.addButton(radio)
            result_layout.addWidget(radio)

        layout.addWidget(result_frame)

        # 提交按钮
        submit_btn = QtWidgets.QPushButton("提交核查结果")
        submit_btn.setFixedHeight(46)
        submit_btn.setStyleSheet(
            "QPushButton {"
            "  background: #2864FF; color: #FFFFFF; font-size: 18px; font-weight: bold;"
            "  border-radius: 8px; margin-top: 8px;"
            "}"
            "QPushButton:hover { background: #1a50e0; }"
            "QPushButton:pressed { background: #0f3ecc; }"
        )
        submit_btn.clicked.connect(self.submit_checklist)
        layout.addWidget(submit_btn)

        layout.addStretch()

    def _create_item_frame(self, label_text, options, idx):
        """创建单个评估项的框架"""
        frame = QtWidgets.QFrame()
        frame.setStyleSheet(
            "background: rgba(255, 255, 255, 8); border-radius: 8px; padding: 8px;"
        )

        item_layout = QtWidgets.QVBoxLayout(frame)
        item_layout.setSpacing(5)

        # 问题标签
        label = QtWidgets.QLabel(f"{idx + 1}. {label_text}")
        label.setStyleSheet(
            "color: #CCDDFF; font-size: 16px; font-weight: 500;"
        )
        item_layout.addWidget(label)

        # 单选按钮组
        radio_layout = QtWidgets.QHBoxLayout()
        radio_layout.setSpacing(25)
        radio_layout.setContentsMargins(20, 2, 20, 2)

        group = QtWidgets.QButtonGroup(self)
        for opt in options:
            radio = QtWidgets.QRadioButton(opt)
            radio.setStyleSheet(self._radio_style())
            group.addButton(radio)
            radio_layout.addWidget(radio)

        radio_layout.addStretch()
        item_layout.addLayout(radio_layout)

        self.radio_groups.append((label_text, group))
        return frame

    def _radio_style(self):
        return (
            "QRadioButton {"
            "  color: #BCC8DD; font-size: 15px; spacing: 6px;"
            "}"
            "QRadioButton::indicator {"
            "  width: 18px; height: 18px;"
            "}"
            "QRadioButton::indicator:unchecked {"
            "  border: 2px solid #556688; border-radius: 9px; background: transparent;"
            "}"
            "QRadioButton::indicator:checked {"
            "  border: 2px solid #2864FF; border-radius: 9px;"
            "  background: qradialgradient(cx:0.5, cy:0.5, radius:0.4,"
            "    fx:0.5, fy:0.5, stop:0 #2864FF, stop:0.5 #1a44cc, stop:1 #0f2e99);"
            "}"
            "QRadioButton:hover { color: #FFFFFF; }"
        )

    def submit_checklist(self):
        """提交核查结果到数据库"""
        patient_id = self.doctorWin.lineEdit_id.text().strip()
        patient_name = self.doctorWin.lineEdit_name.text().strip()

        if not patient_id or not patient_name:
            self._show_notice("错误，请先完善患者信息！")
            return

        # 收集评估结果
        values = []
        for label_text, group in self.radio_groups:
            checked = group.checkedButton()
            if checked:
                values.append(checked.text())
            else:
                self._show_notice(f"请选择：「{label_text}」")
                return

        # 筛查结果
        result_checked = self.result_group.checkedButton()
        if not result_checked:
            self._show_notice("请选择筛查结果！")
            return
        screening_result = result_checked.text()

        test_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        try:
            self.doctorWin.resql()
            self.doctorWin.sqlcursor.execute(
                """INSERT INTO checklist_results (
                    patient_id, patient_name, test_time,
                    rass_status, understand_commands, keep_eyes_open,
                    severe_vision_impairment, nystagmus_eyelid, photosensitivity_risk,
                    vital_signs_stable, electrode_signal_quality, excessive_fatigue,
                    screening_result
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    patient_id, patient_name, test_time,
                    values[0], values[1], values[2],
                    values[3], values[4], values[5],
                    values[6], values[7], values[8],
                    screening_result,
                ),
            )
            self.doctorWin.connection.commit()
            self._show_notice("核查结果已提交成功！")
            self.close()
        except Exception as e:
            print(f"提交核查表失败: {e}")
            self._show_notice(f"提交失败: {e}")

    def _show_notice(self, msg):
        from 提示框 import Ui_notice_UI
        notice = NoticeWindow()
        notice.pushButton_3.setText(msg)
        show_window_on_appropriate_screen(notice)


class SelectPatientWindow(QMainWindow, Ui_select_UI):
    def __init__(self, doctor_window):
        super().__init__()
        self.setupUi(self)  # 初始化UI
        self.setWindowFlag(QtCore.Qt.FramelessWindowHint)  # 不显示窗体边框
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.doctor_window = doctor_window
        self.sqlcursor = None

    def patient_query(self):
        doctorWin.resql()
        self.sqlcursor = doctorWin.sqlcursor
        self.sqlcursor.execute("SELECT * FROM patients")
        results = self.sqlcursor.fetchall()
        results.insert(0, ("病历号    ", "姓名    ", "性别", "年龄"))
        self.listWidget.clear()  # 清空列表以便显示新结果
        for i, row in enumerate(results):
            if i == 0:
                item_text = f"{row[0]} | {row[1]} | {row[2]} | {row[3]}"
            else:
                patient_id = self.pad_chinese(str(row[0]), 10)
                patient_name = self.pad_chinese(str(row[1]), 8)
                patient_sex = str(row[2]).ljust(3)
                patient_age = str(row[3]).ljust(4)

                item_text = f"{patient_id} | {patient_name} | {patient_sex} | {patient_age}"
            item = QtWidgets.QListWidgetItem(item_text)

            if i == 0:  # 如果是第一行
                item.setFlags(item.flags() & ~QtCore.Qt.ItemIsSelectable)  # 设置为不可选中
            self.listWidget.addItem(item)

    def pad_chinese(self, text, length):
        chinese_count = sum(1 for char in text if "\u4e00" <= char <= "\u9fff")  # 计算中文字符数
        return text.ljust(length - chinese_count)  # 在字符总数上减去中文字符数，用于填充

    def on_pushButton_2_clicked(self):
        selected_item = self.listWidget.currentItem()
        if (
            not selected_item or self.listWidget.row(selected_item) == 0
        ):  # 如果 selected_item 为空或选择的是第一行
            doctorWin.word = "错误，未做出选择！"
            doctorWin.error_notice(doctorWin.word)
            return  # 跳出函数
        patient_info = selected_item.text().split(" | ")
        doctorWin.lineEdit_id.setText(patient_info[0])
        doctorWin.lineEdit_name.setText(patient_info[1])
        if patient_info[2] == "男  ":
            doctorWin.radioButton.setChecked(True)
        elif patient_info[2] == "女  ":
            doctorWin.radioButton_2.setChecked(True)
        doctorWin.lineEdit_age.setText(patient_info[3])

        # 同步写入当前窗口（CognitionWindow 等）
        dw = self.doctor_window
        dw.lineEdit_id.setText(patient_info[0])
        dw.lineEdit_name.setText(patient_info[1])
        if patient_info[2] == "男  ":
            dw.radioButton.setChecked(True)
        elif patient_info[2] == "女  ":
            dw.radioButton_2.setChecked(True)
        dw.lineEdit_age.setText(patient_info[3])
        dw.lineEdit_name.setReadOnly(True)
        dw.lineEdit_age.setReadOnly(True)
        dw.lineEdit_id.setReadOnly(True)
        dw.radioButton.setEnabled(False)
        dw.radioButton_2.setEnabled(False)
        dw.pushButton_luru.setText("清空")
        if hasattr(dw, '_load_avatar'):
            dw._load_avatar()
        if hasattr(dw, 'load_activation_history'):
            dw.load_activation_history()

        self.notice = NoticeWindow()
        self.notice.pushButton_3.setText("查询录入成功！")
        if doctorWin.ty == 3 and doctorWin.pushButton_luru.text() == "清空":
            data = {
                "func_selected": "demand_entry",
                "question_info": None,
                "ccaSwitch": None,
                "selected": None,
                "shanshuo": 0,
            }
            doctorWin.trigger_message("patient_ui", data)
            print(1)
            print("五号")
            doctorWin.pushButton_ready_req.setEnabled(True)
            doctorWin.update_button_styles()
            doctorWin.opensubwindow == 0
            global Flash_Ready_tag_req, charge
            Flash_Ready_tag_req = 0
            charge = 1  # 每次进来假装处理过需求的问题了

        # self.notice.show()
        show_window_on_appropriate_screen(self.notice)
        # 设置lineEdit_name、lineEdit_age、lineEdit_id为只读（全局 doctorWin）
        doctorWin.lineEdit_name.setReadOnly(True)
        doctorWin.lineEdit_age.setReadOnly(True)
        doctorWin.lineEdit_id.setReadOnly(True)
        # 设置radioButton、radioButton_2为不可更改
        doctorWin.radioButton.setEnabled(False)
        doctorWin.radioButton_2.setEnabled(False)
        doctorWin.pushButton_luru.setText("清空")
        doctorWin.label_req.setText("点击'开始闪烁'，患者将进行一级需求选择")
        dw.send_change_frequencies()

    def checklist_open(self):
        self.checklist_win = ChecklistWindow(self)
        show_window_on_appropriate_screen(self.checklist_win)

    def sqlConnect(self):
        db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hospital_rounds.db")
        self.connection = sqlite3.connect(db_path)
        cursor = self.connection.cursor()
        return cursor


class QuestionWindow(QMainWindow, Ui_question_UI):
    def __init__(self):
        super().__init__()
        self.setupUi(self)  # 初始化
        self.setWindowFlag(QtCore.Qt.FramelessWindowHint)  # 不显示窗体边框
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)  # 背景消失术
        self.pushButton_2.clicked.connect(lambda: self.add_or_update(doctorWin.what))  # 确定按钮

    def showEvent(self, event):
        """窗口显示时刷新分类下拉列表"""
        super().showEvent(event)
        self._refresh_category_combo()

    def _refresh_category_combo(self):
        """刷新分类下拉框"""
        self.comboBox_category.clear()
        if hasattr(doctorWin, 'sqlcursor'):
            doctorWin.resql()
            doctorWin.sqlcursor.execute(
                "SELECT category_id, category_name FROM question_categories WHERE type = ? ORDER BY sequence",
                (doctorWin.ty,),
            )
            for cat in doctorWin.sqlcursor.fetchall():
                self.comboBox_category.addItem(cat[1], cat[0])

    def _get_selected_category_id(self):
        """获取当前选中的分类ID，如果未选择则使用旧分类"""
        idx = self.comboBox_category.currentIndex()
        if idx >= 0:
            return self.comboBox_category.itemData(idx)
        return None

    def add_or_update(self, what):
        category_id = self._get_selected_category_id()
        if what == 0:  # 添加问题
            if not (self.lineEdit.text() and self.lineEdit_3.text() and self.textEdit.toPlainText()):
                doctorWin.word = "错误，信息不完整！"
                doctorWin.error_notice(doctorWin.word)
                return
            if category_id is None:
                doctorWin.word = "错误，请选择问题所属分类！"
                doctorWin.error_notice(doctorWin.word)
                return

            question = self.lineEdit.text()
            # 检查数据库中是否存在相同的问题文本
            doctorWin.sqlcursor.execute(
                "SELECT question_text FROM questions WHERE question_text = ?", (question,)
            )
            existing_question = doctorWin.sqlcursor.fetchone()
            if existing_question:
                doctorWin.word = "错误，已存在相同的问题文本！"
                doctorWin.error_notice(doctorWin.word)
                return

            answer = self.textEdit.toPlainText()
            answer = re.split(r"[;；]", answer)
            answer = [token.strip() for token in answer if token.strip()]
            if len(answer) == 1:
                doctorWin.word = "错误，问题选项数量不能为 1！"
                doctorWin.error_notice(doctorWin.word)
                return
            if len(answer) > 8:
                doctorWin.word = "错误，答案数目最大为 8！"
                doctorWin.error_notice(doctorWin.word)
                return
            if len(set(answer)) != len(answer):
                doctorWin.word = "错误，存在重复的问题选项！"
                doctorWin.error_notice(doctorWin.word)
                return
            try:
                quantity = int(self.lineEdit_3.text())
            except ValueError:
                quantity = 0
            if len(answer) != quantity:
                doctorWin.word = "错误，答案数目与预设不符！"
                doctorWin.error_notice(doctorWin.word)
                return

            while len(answer) < 8:
                answer.append(None)
            doctorWin.sqlcursor.execute("SELECT MAX(sequence) FROM questions")
            max_sequence = doctorWin.sqlcursor.fetchone()[0]
            sequence = 1 if max_sequence is None else max_sequence + 1
            doctorWin.sqlcursor.execute(
                "INSERT INTO questions (question_text, answer_num, answer1_text, answer2_text,"
                "answer3_text,answer4_text,answer5_text,answer6_text,answer7_text,"
                "answer8_text,type,sequence,category_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    question, quantity,
                    answer[0], answer[1], answer[2], answer[3],
                    answer[4], answer[5], answer[6], answer[7],
                    doctorWin.ty, sequence, category_id,
                ),
            )
            doctorWin.connection.commit()
            self.notice = NoticeWindow()
            self.close()
            self.notice.pushButton_3.setText("添加成功！")
            show_window_on_appropriate_screen(self.notice)
            doctorWin.question_query()
        elif what == 1:  # 修改更新问题
            question = doctorWin.addq.lineEdit.text()
            answer = doctorWin.addq.textEdit.toPlainText()
            answer = re.split(r"[;；]", answer)
            answer = [token.strip() for token in answer if token.strip()]
            if len(answer) == 1:
                doctorWin.word = "错误，问题选项数量不能为 1！"
                doctorWin.error_notice(doctorWin.word)
                return
            if len(answer) > 8:
                doctorWin.word = "错误，答案数目最大为 8！"
                doctorWin.error_notice(doctorWin.word)
                return
            if len(set(answer)) != len(answer):
                doctorWin.word = "错误，存在重复的问题选项！"
                doctorWin.error_notice(doctorWin.word)
                return
            try:
                quantity = int(doctorWin.addq.lineEdit_3.text())
            except ValueError:
                quantity = 0
            if len(answer) != quantity:
                doctorWin.word = "错误，答案数目与预设不符！"
                doctorWin.error_notice(doctorWin.word)
                return
            while len(answer) < 8:
                answer.append(None)
            question_id = doctorWin.question_id
            sql = (
                "UPDATE questions SET question_text=?,answer_num=?,answer1_text=?,answer2_text=?,answer3_text=?,"
                "answer4_text=?,answer5_text=?,answer6_text=?,answer7_text=?,answer8_text=?,category_id=? WHERE question_id = ?"
            )
            val = (
                question, quantity,
                answer[0], answer[1], answer[2], answer[3],
                answer[4], answer[5], answer[6], answer[7],
                category_id if category_id else 1, question_id,
            )
            doctorWin.sqlcursor.execute(sql, val)
            doctorWin.connection.commit()
            doctorWin.notice = NoticeWindow()
            doctorWin.notice.pushButton_3.setText("修改成功！")
            self.close()
            doctorWin.clear_selected_button()
            show_window_on_appropriate_screen(doctorWin.notice)
            doctorWin.question_query()
        else:
            doctorWin.word = "错误，信息不完整！"
            doctorWin.error_notice(doctorWin.word)
            doctorWin.selected_button.setChecked(False)
            return


def consumer():  # 语音控制
    flag = 1
    global is_processing
    while True:
        time.sleep(0.1)
        if flag:
            try:
                doctorWin.pushButton_asr.setText("语音识别中...")
            finally:
                flag = 0
        if not q.empty():
            item = q.get()
            # print("consumer_item：", item)
            global ccaSwitch, answerNum, questionInfo
            questionInfo = item
            ccaSwitch = True
            answerNum = item[2]
            global stim
            stim = item[2]
            # doctorWin.FBCCA = FBCCA(stim)
            doctorWin.targets_frq = getattr(WordTextS, f"frequency_list{stim}")
            doctorWin.targets_frq.insert(0, 34)
            doctorWin.reference_signals = doctorWin.FBCCA.get_reference_signal(
                num_harmonics=3, targets=doctorWin.targets_frq
            )
            doctorWin.fb_weight = [
                math.pow(i, -1.25) + 0.25 for i in range(1, doctorWin.FBCCA.Nm + 1)
            ]  # Assign a weight to each filter (w),a=1.25,b=0.25
            data = {
                "func_selected": "round",
                "question_info": questionInfo,
                "ccaSwitch": ccaSwitch,
                "selected": None,
                "shanshuo": 0,
            }
            doctorWin.trigger_message("patient_ui", data)
            print(18)
            doctorWin.pushButton_asr.setText("当前问题：" + item[1])
            is_processing = False  # 确保无论函数执行如何都重置状态
            break


def close_current_program():
    pid = os.getpid()
    os.kill(pid, signal.SIGTERM)


# def run_process():
#     # 在每个进程中重新创建锁对象
#     lock = threading.Lock()  # 重新创建锁对象
#     # 创建patientWindow实例并传递锁对象
#     obj = patientWindow(lock=lock)
#     # 调用justtest方法
#     obj.justtest()


def close_current_program():  # 关闭两个界面函数
    current_process = psutil.Process(os.getpid())
    # 递归关闭当前进程及其所有子进程
    terminate_process_and_children(current_process.pid)

    # 明确关闭psychopy_process进程
    global psychopy_process
    if "psychopy_process" in globals() and psychopy_process.is_alive():
        psychopy_process.terminate()
        psychopy_process.join(timeout=5)  # 等待5秒
        if psychopy_process.is_alive():
            psychopy_process.kill()  # 如果仍然存活，强制杀死

    os.kill(os.getpid(), signal.SIGTERM)


def terminate_process_and_children(pid):  # 用于关闭按钮 关闭两个界面
    process = psutil.Process(pid)
    children = process.children(recursive=True)
    for child in children:
        try:
            child.terminate()
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    process.terminate()


class CLIChatClient:  # CLI 客户端，与服务器main.py进行通信
    def __init__(self, server_url, user_id):
        # 连接配置
        self.server_url = server_url
        self.user_id = user_id
        self.real_result = 0

        # Socket.IO 客户端
        self.sio = socketio.Client(reconnection=True, reconnection_attempts=5, reconnection_delay=1)

        # 线程安全机制
        self.send_lock = threading.RLock()  # 递归锁用于发送操作
        self.conn_lock = threading.Lock()  # 连接状态操作锁
        self.send_queue = BoundedMessageQueue(maxsize=256, overflow="reject")
        self.lock = threading.Lock()

        # 控制参数
        self.max_retries = 3  # 最大重试次数
        self.running = True  # 运行状态标志
        self.stop_event = threading.Event()
        self.worker_threads = []
        self.cca_result = None

        self.result_event = threading.Event()  # 结果等待事件
        self.latest_result = None
        self._next_task_id = 0
        self._active_task_id = None
        self.search_complete_callback = None  # 算法个性化校准完成回调

        # 初始化连接
        self._setup_handlers()
        self._start_workers()

    def _setup_handlers(self):
        """配置Socket.IO事件处理器"""

        @self.sio.event
        def connect():
            print(f"\n[系统] 已连接到服务器 {self.server_url}")
            self.sio.emit("register", self.user_id)

        @self.sio.on("private_msg")
        def on_private_message(data):
            print(f"\n[新消息] 来自 {data['from']}: {data['message']}")

        @self.sio.event
        def disconnect():
            print("\n[系统] 与服务器断开连接")
            if self.running:  # 非主动关闭时尝试重连
                self._safe_connect()

        @self.sio.on("eeg_result")
        def on_processing_result(data):
            print(f"\n[处理结果] {data['result']}")
            self.cca_result = data["result"]

        @self.sio.on("processing_result")
        def on_result(data):
            result = int(data["result"])
            with self.lock:
                if data.get("task_id") != self._active_task_id:
                    return
                self.latest_result = result
                if 1 <= result <= 8:
                    self.real_result = result
            print(f"[处理结果] {result}")
            print(f"本次结果: {result}")
            print(f"剩余可处理次数: {data['remaining']}")
            if 1 <= result <= 8:
                print(result, "得到有效结果")

        @self.sio.on("status_update")
        def on_status(data):
            print(f"\n[系统状态] {data['status']}")

        @self.sio.on("search_complete")
        def on_search_complete(data):
            print(f"\n[DEBUG on_search_complete] 收到服务器 search_complete 事件!")
            print(f"[DEBUG on_search_complete] 患者ID:{data.get('patient_id')}, 最佳频率:{data.get('frequencies')}")
            print(f"[DEBUG on_search_complete] search_complete_callback 是否为 None: {self.search_complete_callback is None}")
            if self.search_complete_callback:
                print("[DEBUG on_search_complete] 调用 search_complete_callback...")
                self.search_complete_callback(data)
                print("[DEBUG on_search_complete] search_complete_callback 调用完成")
            else:
                print("[DEBUG on_search_complete] 警告: search_complete_callback 为 None，无法触发弹窗!")

    def reset_result(self):
        with self.lock:
            self.real_result = 0

    def consume_result(self):
        with self.lock:
            result = self.real_result
            if result:
                self.real_result = 0
            return result

    def start_processing(self, target_client_id, eeg_num, stim_num, require_tag):
        """发送启动指令并等待有效结果（非0/None）"""
        # target_client_id:医生端的id
        # eeg_num:eeg 处理的授权次数，0.2s一次
        # stim_num:分类题目的目标数
        # require_tag:需求界面的菜单索引参数
        self.result_event.clear()
        with self.lock:
            self._next_task_id += 1
            self._active_task_id = f"{self.user_id}-{self._next_task_id}"
            task_id = self._active_task_id

        # 发送处理指令
        return self.send_to_server(
            "start_processing",
            {
                "target": target_client_id,
                "count": eeg_num,
                "stim_num": stim_num,
                "require_tag": require_tag,
                "task_id": task_id,
            },
        )

    def start_train(self, patient_id):
        """发送启动指令并等待有效结果（非0/None）"""
        # target_client_id:医生端的id
        # eeg_num:eeg 处理的授权次数，0.2s一次
        # stim_num:分类题目的目标数
        # require_tag:需求界面的菜单索引参数
        self.result_event.clear()
        # 发送处理指令
        self.send_to_server("train", {"target": 1, "patient_id": patient_id})
        now_time = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        print("范式开始时间：", now_time)
        self.async_send("patient_ui", {"train": 1})
        return self.latest_result

    def start_searchBestFrequencies(self, patient_id):
        """发送启动指令并等待有效结果（非0/None）"""
        # target_client_id:医生端的id
        # eeg_num:eeg 处理的授权次数，0.2s一次
        # stim_num:分类题目的目标数
        # require_tag:需求界面的菜单索引参数
        print(f"[DEBUG start_searchBestFrequencies] 开始，patient_id={patient_id}")
        self.result_event.clear()

        # 发送处理指令
        print("[DEBUG start_searchBestFrequencies] 发送 searchBestFrequencies 到服务器...")
        self.send_to_server("searchBestFrequencies", {"target": 1, "patient_id": patient_id})
        now_time = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        print("[DEBUG start_searchBestFrequencies] 范式开始时间：", now_time)
        print("[DEBUG start_searchBestFrequencies] 发送 patient_ui 到患者端...")
        self.async_send("patient_ui", {"searchBestFrequencies": 1})
        print("[DEBUG start_searchBestFrequencies] 已发送全部指令，等待服务器回调...")
        return self.latest_result

    def change_frequencies(self, patient_id):
        """发送启动指令并等待有效结果（非0/None）"""
        self.result_event.clear()
        print("开始发送改变频率指令...")

        # 发送处理指令
        self.send_to_server(
            "change_frequencies",
            {
                "target": 1,
                "patient_id": patient_id,
            },
        )
        self.async_send("patient_ui", {"change_frequencies": patient_id})

    def _start_workers(self):
        """启动后台工作线程"""
        self.worker_threads = [
            threading.Thread(target=self._process_queue, name="doctor-send", daemon=True),
            threading.Thread(target=self._keepalive, name="doctor-heartbeat", daemon=True),
        ]
        for worker in self.worker_threads:
            worker.start()

    def _keepalive(self):
        """维持连接的心跳检测"""
        while not self.stop_event.wait(5):
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

        try:
            accepted = self.send_queue.put({"target": target, "message": message, "retries": 0})
        except QueueClosed:
            return False
        if not accepted:
            print("发送队列已满，拒绝控制消息")
        return accepted

    def _process_queue(self):
        """消息队列处理核心"""
        while not self.stop_event.is_set():
            try:
                item = self.send_queue.get(timeout=0.5)
            except QueueClosed:
                break
            except queue.Empty:
                continue
            self._send_with_retry(item)

    def send_to_server(self, event_name, data):
        """
        发送自定义事件及数据到服务器
        :param event_name: Socket.IO 事件名称
        :param data: 要发送的数据（字典格式）
        """
        try:
            accepted = self.send_queue.put({"event": event_name, "data": data, "retries": 0})
        except QueueClosed:
            return False
        if not accepted:
            print(f"发送队列已满，拒绝事件: {event_name}")
        return accepted

    def _send_with_retry(self, item):
        """带重试机制的发送逻辑（已适配通用事件）"""
        while item["retries"] <= self.max_retries and not self.stop_event.is_set():
            try:
                with self.send_lock:
                    if not self.sio.connected:
                        self._safe_connect()

                    if self.sio.connected:
                        # 判断是否为通用事件格式
                        if "event" in item and "data" in item:
                            self.sio.emit(item["event"], item["data"])
                            print(f"[成功] 事件 {item['event']}")
                        else:
                            # 原有私聊消息逻辑
                            self.sio.emit(
                                "private_msg",
                                {
                                    "from": self.user_id,
                                    "target": item["target"],
                                    "message": item["message"],
                                    "timestamp": int(time.time()),
                                },
                            )
                            print(f"成功发送至 {item['target']}: {item['message']}")
                        return
            except Exception as e:
                print(f"发送异常: {str(e)}")

            item["retries"] += 1
            if item["retries"] <= self.max_retries:
                if self.stop_event.wait(2 ** item["retries"]):
                    return
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
        if self.stop_event.is_set():
            return
        self.running = False
        self.stop_event.set()
        self.send_queue.close()
        if self.sio.connected:
            self.sio.disconnect()
        current = threading.current_thread()
        for worker in self.worker_threads:
            if worker is not current:
                worker.join(timeout=2.0)


if __name__ == "__main__":
    global ccaSwitch, answerNum, questionInfo, winSelect, Flash_Ready_tag
    ccaSwitch = None
    answerNum = None
    winSelect = None
    global is_processing
    is_processing = False
    # 配置参数
    SERVER_URL = WordTextS.main_ip
    USER_ID = "doctor"

    # 初始化客户端
    client = CLIChatClient(SERVER_URL, USER_ID)

    # 该管道用于点击后传输问题等等
    # sender, connRight = Pipe()
    # 该管道用于发送给放大器打标签用
    left, right = (
        Pipe()
    )  # 要有两个进程的参数分别为left right，这个管道为左收右发，右边发送要打的标签，左边接收
    eegQueue = deque(maxlen=4)
    q = Queue()  # 传递问题的队列
    qq = Queue()  # 用于存储交换是医生or护士问题的队列
    controller = ScreenController()  # 屏幕控制
    # 固定的，PyQt5程序都需要QApplication对象。sys.argv是命令行参数列表，确保程序可以双击运行
    app = QApplication(sys.argv)
    app.aboutToQuit.connect(client.shutdown)

    # #查房端初始化
    doctorWin = CfWindow(client, right=right)  # 医生查房
    app.aboutToQuit.connect(doctorWin.shutdown_runtime)
    window = MainWindow(client=client)  # 开始界面，管道发送进入的是哪个子界面（护士、医生、需求）
    show_window_on_appropriate_screen(window)
    """多进程开启psychopy界面"""
    # psychopy_process = multiprocessing.Process(target=run_process, args=())
    # psychopy_process.start()

    sys.exit(app.exec_())
