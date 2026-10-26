class WordTextS:
    # main_ip = "http://172.18.201.201:9999"
    main_ip = "http://127.0.0.1:9999"

    # 训练阶段的参数设置
    turn_count = 1  # 训练轮数
    target_count = 8  # 目标数
    flash_time = 5  # 每个目标闪烁时间，单位：秒
    sample_rate = 250  # 采样率，单位：Hz

    pre_welcome_wait = 1  # 欢迎提示显示时间，单位：秒
    pre_experiment_wait = 3  # 实验开始前提示时间，单位：秒
    pre_flash_wait = 1  # 每个目标闪烁前预热时间，单位：秒
    post_flash_rest = 1  # 每个目标闪烁后休息时间，单位：秒

    refresh_rate = 240
    twoTips_position = [(-0.6, -0.10), (0.6, -0.10)]
    twoStim_position = [(-0.6, -0.25), (0.6, -0.25)]

    threeTips_position = [(-0.6, -0.10), (0, -0.10), (0.6, -0.10)]
    threeStim_position = [(-0.6, -0.25), (0, -0.25), (0.6, -0.25)]

    fourTips_position = [(-0.75, -0.10), (-0.25, -0.10), (0.25, -0.10), (0.75, -0.10)]
    fourStim_position = [(-0.75, -0.25), (-0.25, -0.25), (0.25, -0.25), (0.75, -0.25)]

    fiveTips_position = [(-0.3, 0.01), (0.3, 0.01), (-0.60, -0.27), (0, -0.27), (0.60, -0.27)]
    fiveStim_position = [(-0.3, 0.09), (0.3, 0.09), (-0.60, -0.35), (0, -0.35), (0.60, -0.35)]
    sixTips_position = [(-0.6, 0.01), (0, 0.01), (0.6, 0.01), (-0.60, -0.27), (0, -0.27), (0.6, -0.27)]
    sixStim_position = [(-0.6, 0.09), (0, 0.09), (0.6, 0.09), (-0.60, -0.35), (0, -0.35), (0.6, -0.35)]
    sevenTips_position = [
        (-0.4, 0.01),
        (-0, 0.01),
        (0.4, 0.01),
        (-0.65, -0.27),
        (-0.20, -0.27),
        (0.20, -0.27),
        (0.65, -0.27),
    ]
    sevenStim_positon = [
        (-0.4, 0.09),
        (-0, 0.09),
        (0.4, 0.09),
        (-0.65, -0.35),
        (-0.20, -0.35),
        (0.20, -0.35),
        (0.65, -0.35),
    ]
    eightTips_position = [
        (-0.65, 0.01),
        (-0.22, 0.01),
        (0.22, 0.01),
        (0.65, 0.01),
        (-0.65, -0.27),
        (-0.22, -0.27),
        (0.22, -0.27),
        (0.65, -0.27),
    ]
    eightStim_position = [
        (-0.65, 0.09),
        (-0.22, 0.09),
        (0.22, 0.09),
        (0.65, 0.09),
        (-0.65, -0.35),
        (-0.22, -0.35),
        (0.22, -0.35),
        (0.65, -0.35),
    ]

    frequency_list2 = [35, 37]
    frequency_list3 = [35, 36, 37]
    frequency_list4 = [35, 36, 37, 38]
    frequency_list5 = [35, 35.5, 36, 36.5, 37]
    frequency_list6 = [35, 35.5, 36, 36.5, 37, 37.5]
    frequency_list7 = [35, 35.5, 36, 36.5, 37, 37.5, 38]
    frequency_list8 = [35, 35.5, 36, 36.5, 37, 37.5, 38, 38.5]
    # frequency_list2 = [35, 35.5]
    # frequency_list3 = [35, 35.5, 36]
    # frequency_list4 = [35, 35.5, 36, 36.5]
    # frequency_list5 = [35, 35.5, 36, 36.5, 37]
    # frequency_list6 = [35, 35.5, 36, 36.5, 37, 37.5]
    # frequency_list7 = [35, 35.5, 36, 36.5, 37, 37.5, 38]
    # frequency_list8 = [35, 35.5, 36, 36.5, 37, 37.5, 38, 38.5]
    max_read_time = 600
    threshold = 0.32
    """患者需求端"""
    # 需求主界面
    require_main_text = ["了解病情", "家人朋友", "身体疼痛", "身边环境"]  # 主界面文字
    # require_main_text = ['一号', '二号', '三号', '四号']  # 主界面文字
    require_main_TextPosition = [(-0.54, 0.17), (-0.54, -0.27), (0.54, 0.17), (0.54, -0.27)]  # 主界面文字位置
    require_main_BlockPosition = [
        (-0.54, 0.25),
        (-0.54, -0.18),
        (0.54, 0.25),
        (0.54, -0.18),
    ]  # 主界面闪烁位置

    # 需求子界面
    require_sub_text1 = ["手术成功吗", "什么时候出去", "预后康复情况", "怎么配合治疗?"]
    require_sub_text2 = ["告知密码", "思念家人", "通知朋友", "商量要事"]
    require_sub_text3 = ["需要止痛药", "插管难受", "需要按摩", "需要安眠药"]
    require_sub_text4 = ["太吵", "光线强弱", "时间错乱", "不想被打扰"]
    # require_sub_text1 = ['头痛', '头晕', '颈部难受', '喉咙难受']
    # require_sub_text2 = ['上肢关节痛', '手麻', '肌无力', '手冷']
    # require_sub_text3 = ['肚子疼', '胸闷', '后背痒', '腰疼']
    # require_sub_text4 = ['下肢关节痛', '腿麻', '腿抽筋', '脚冷']
    # require_sub_text1 = ['1.1', '1.2', '1.3', '1.4']
    # require_sub_text2 = ['2.1', '2.2', '2.3', '2.4']
    # require_sub_text3 = ['3.1', '3.2', '3.3', '3.4']
    # require_sub_text4 = ['4.1', '4.2', '4.3', '4.4']
    # require_sub_TextPosition = [(-0.54, 0.15), (-0.54, -0.35),(0.54, 0.15), (0.54, -0.35)]  # 子界面文字位置
    # require_sub_BlockPosition = [(-0.54, 0.25), (-0.54, -0.25),(0.54, 0.25),(0.54, -0.25)]  # 子界面闪烁位置
    require_sub_TextPosition = [(-0.54, 0.15), (-0.54, -0.35), (0.54, 0.15), (0.54, -0.35)]  # 子界面文字位置
    require_sub_BlockPosition = [(-0.54, 0.25), (-0.54, -0.25), (0.54, 0.25), (0.54, -0.25)]  # 子界面闪烁位置

    class SearchBestFrequencies:
        # 频率扫描取值范围（Hz）
        frequency_start = 35
        frequency_end = 35
        frequency_step = 1
        eightTips_position = [
            (-0.65, 0.01),
            (0, -0.09),
            (0.22, 0.01),
            (0.65, 0.01),
            (-0.65, -0.27),
            (-0.22, -0.27),
            (0.22, -0.27),
            (0.65, -0.27),
        ]
        eightStim_position = [
            (-0.65, 0.09),
            (0, 0.0),
            (0.22, 0.09),
            (0.65, 0.09),
            (-0.65, -0.35),
            (-0.22, -0.35),
            (0.22, -0.35),
            (0.65, -0.35),
        ]
        pre_welcome_wait = 1
        pre_experiment_wait = 3
        pre_flash_wait = 1
        post_flash_rest = 1
        flash_duration = 3  # 每个频率闪烁时间，单位：秒
        # 每轮仅闪烁一个刺激块，指定使用的索引（对应 eightStim_position / eightTips_position ）
        single_block_index = 1  # 使用第二个位置，便于与训练模式区分

        # 每个频率的闪烁重复次数
        repetitions = 1  # 可按需调整

        # 单块闪烁默认相位（用于 get_frame 中的正弦相位偏移）
        phase_offsets = [0.45]

        @classmethod
        def frequency_sequence(cls):
            """返回按照指定步长生成的频率序列（包含上限）。"""
            return [
                cls.frequency_start + step * cls.frequency_step
                for step in range(int((cls.frequency_end - cls.frequency_start) / cls.frequency_step) + 1)
            ]

    # # 病情
    # require_sub_text1 = ['手术成功吗', '什么时候出去', '预后康复情况', '怎么配合治疗?', '病情严重吗？', '想放弃治疗']
    # # WORD1 = ['插管难受', '恶心想吐', '环境冷热', '身体疼痛', '有点害怕', '腹部撑胀']
    #
    # # 生理(身体不适)
    # require_sub_text2 = ['冷/热', '饿/口渴', '疼痛', '大小便', '想活动', '想活动']
    #
    # # 隐私x
    # require_sub_text3 = ['穿衣服', '拉帘子', '同性别操作', '盖被子', '上厕所不好意思', '想看手机']
    #
    # # 环境x
    # require_sub_text4 = ['太吵', '光线强弱', '时间错乱', '不想被打扰', '人太多', '躺着不舒服']
    #
    # # 心理（我需要什么、需求）                                           1
    # WORD5 = ['家人陪伴', '担心病情加重', '想回病房', '单位事情没解决', '密码家人不知道', '害怕']
    #
    # # 安全
    # WORD6 = ['解开手套', '气管插管', '气切套管', '尿管', '胃管', '其他引流管']
    #
    # PIC1 = ['imgs/11.png','imgs/12.png','imgs/13.png','imgs/14.png','imgs/15.png','imgs/16.png']
    # PIC2 = ['imgs/sl.png', 'imgs/sl.png', 'imgs/sl.png', 'imgs/sl.png', 'imgs/sl.png', 'imgs/sl.png']
    # PIC3 = ['imgs/sl.png', 'imgs/sl.png', 'imgs/sl.png', 'imgs/sl.png', 'imgs/sl.png', 'imgs/sl.png']
    # PIC4 = ['imgs/sl.png', 'imgs/sl.png', 'imgs/sl.png', 'imgs/sl.png', 'imgs/sl.png', 'imgs/sl.png']
    # PIC5 = ['imgs/sl.png', 'imgs/sl.png', 'imgs/sl.png', 'imgs/sl.png', 'imgs/sl.png', 'imgs/sl.png']
    # PIC6 = ['imgs/sl.png', 'imgs/sl.png', 'imgs/sl.png', 'imgs/sl.png', 'imgs/sl.png', 'imgs/sl.png']
    #
    # CHOICE_TEXT_POSITION = [(-0.61, 0.08), (0.00, 0.08),(0.61, 0.08),
    #                         (-0.61, -0.315),(0.00, -0.315), (0.61, -0.315)]    #控制子菜单文字位置
    #
    # CHOICE_STIM_POSITION = [(-0.61, 0.01), (0.00, 0.01), (0.61, 0.01),
    #                         (-0.61, -0.382), (0.00, -0.382), (0.61, -0.382)]  # 控制子菜单闪烁位置
    #
    # STIM_CIRCLE_POSITION = [(-0.25, 0.02), (0.25, 0.02),(0.75, 0.02),
    #                         (-0.25, -0.33), (0.25, -0.33), (0.75, -0.33)]
    #
    # PIC_POSITION = [(-0.45, 0.2), (0.05, 0.2),(0.55, 0.2),
    #                 (-0.45, -0.16), (0.05, -0.16), (0.55, -0.16)]
    #
    # CHOICE_RECTANGLE_SIZE = [[0.13, 0.03], [-0.13, 0.03], [-0.13, -0.03], [0.13, -0.03]]
    #
    # #需求主界面
    # require_main_text = ['了解病情', '家人朋友', '身体疼痛', '待定']
    # WORD8 = ['手术情况、治疗方案...', '冷热、疼痛、想活动...' ,'上厕所、穿衣服...' , '吵、光线、时间错乱...','担心、家人陪伴...', '医疗设备、引流管...']
    #
    # require_main_text_POSITION = [(-0.54, 0.371), (-0.54, 0.03),(-0.54, -0.31),(0.54, 0.371), (0.54, 0.03), (0.54, -0.31)]  #控制主菜单文字位置
    # WORD8_POSITION = [(-0.6, 0.12), (-0.6, -0.08), (-0.6, -0.28), (0.6, 0.12), (0.6, -0.08), (0.6, -0.28)]
    #
    # RECT_POSITION = [(-0.6, 0.15), (-0.6, -0.05),(-0.6, -0.25),(0.6, 0.15), (0.6, -0.05), (0.6, -0.25)]
    #
    # PIC7 = ['imgs/bq.png', 'imgs/ys.png', 'imgs/xl.png', 'imgs/sl.png', 'imgs/hj.png', 'imgs/aq.png']
    # PIC7_POSITION = [(-0.325, 0.15), (-0.325, -0.05), (-0.325, -0.25), (0.325, 0.15), (0.325, -0.05), (0.325, -0.25)]
    #
    # PIC8 = ['imgs/rect.png', 'imgs/rect.png', 'imgs/rect.png', 'imgs/rect.png', 'imgs/rect.png', 'imgs/rect.png']
    # PIC8_POSITION = [(-0.366, 0.341), (-0.395, -0.000), (-0.366, -0.339), (0.366, 0.341), (0.3975, -0.000), (0.366, -0.339)]   #控制主菜单闪烁位置
