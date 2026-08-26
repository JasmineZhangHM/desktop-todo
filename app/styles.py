"""集中样式 + 主题色（每个 board 独立配色）。"""

# 6 套主题色：标题栏 / 正文 / 边框 / 主操作色（输入按钮等） / hover / 文字色 / 色板
COLOR_THEMES = {
    "yellow": dict(name="黄色", title_bg="#FFF6C9", body_bg="#FFFDF5",
                   border="#E5E0CC", accent="#FFCF5C", accent_hover="#FFC133",
                   accent_text="#4A3B00", swatch="#FFCF5C"),
    "pink":   dict(name="粉色", title_bg="#FFD1DC", body_bg="#FFF5F7",
                   border="#E8C0CB", accent="#FF7BA0", accent_hover="#FF5C8A",
                   accent_text="#5A1F35", swatch="#FF7BA0"),
    "blue":   dict(name="蓝色", title_bg="#C9E4FF", body_bg="#F5FAFF",
                   border="#B0CFE8", accent="#5C9CE0", accent_hover="#4080CC",
                   accent_text="#0A2E55", swatch="#5C9CE0"),
    "green":  dict(name="绿色", title_bg="#D5F0CA", body_bg="#F8FCF5",
                   border="#B8DDA8", accent="#7FBE6E", accent_hover="#6BAA5A",
                   accent_text="#1F3D14", swatch="#7FBE6E"),
    "purple": dict(name="紫色", title_bg="#E1D9FF", body_bg="#FAF7FF",
                   border="#C8BEEC", accent="#9B86E0", accent_hover="#8470CC",
                   accent_text="#2D1F5C", swatch="#9B86E0"),
    "gray":   dict(name="灰色", title_bg="#E8E8E8", body_bg="#FAFAFA",
                   border="#D0D0D0", accent="#9E9E9E", accent_hover="#888888",
                   accent_text="#333333", swatch="#9E9E9E"),
}


def floating_qss(theme_key: str) -> str:
    t = COLOR_THEMES.get(theme_key, COLOR_THEMES["yellow"])
    return f"""
    #Container {{
        background: {t['body_bg']};
        border: 1px solid {t['border']};
        border-radius: 12px;
    }}
    #TitleBar {{
        background: {t['title_bg']};
        border-top-left-radius: 12px;
        border-top-right-radius: 12px;
    }}
    QLabel#TitleLabel {{
        color: #555;
        font-weight: bold;
        font-size: 13px;
    }}
    QPushButton#IconBtn {{
        border: none;
        background: transparent;
        color: #777;
        font-size: 14px;
        padding: 0;
        border-radius: 4px;
    }}
    QPushButton#IconBtn:hover {{
        background: rgba(0,0,0,0.06);
        color: #222;
    }}

    QLineEdit#Input {{
        border: 1px solid {t['border']};
        border-radius: 6px;
        padding: 6px 8px;
        background: #FFFFFF;
        font-size: 13px;
    }}
    QPushButton#AddBtn {{
        background: {t['accent']};
        color: {t['accent_text']};
        border: none;
        border-radius: 6px;
        padding: 6px 12px;
        font-weight: bold;
    }}
    QPushButton#AddBtn:hover {{ background: {t['accent_hover']}; }}

    QListWidget {{
        border: none;
        background: transparent;
        font-size: 13px;
        outline: 0;
    }}
    QListWidget::item {{ padding: 0; border: none; }}
    QListWidget::item:selected {{ background: transparent; }}

    /* 待完成圆按钮 */
    QPushButton#DoneBtn {{
        background: #FFFFFF;
        color: transparent;
        border: 1.5px solid #BDBDBD;
        border-radius: 11px;
        padding: 0;
        font-size: 12px;
        font-weight: bold;
    }}
    QPushButton#DoneBtn:hover {{
        background: #E8F5E9;
        color: #2E7D32;
        border: 1.5px solid #81C784;
    }}
    QPushButton#DoneBtn:pressed {{
        background: #C8E6C9;
        color: #1B5E20;
    }}

    /* 计时按钮（沙漏） */
    QPushButton#TimerBtn {{
        background: #FFFFFF;
        color: #9E9E9E;
        border: 1.5px solid #BDBDBD;
        border-radius: 11px;
        padding: 0;
        font-size: 11px;
    }}
    QPushButton#TimerBtn:hover {{
        background: #E3F2FD;
        color: #1565C0;
        border: 1.5px solid #64B5F6;
    }}
    QPushButton#TimerBtn:pressed {{
        background: #BBDEFB;
        color: #0D47A1;
    }}

    QPushButton#FooterBtn {{
        background: transparent;
        color: #777;
        border: none;
        font-size: 12px;
    }}
    QPushButton#FooterBtn:hover {{ color: #222; text-decoration: underline; }}

    /* 分栏标题（按紧迫度配色） */
    QLabel#SectionHeaderOverdue {{ color: #C62828; font-weight: bold; font-size: 11px; padding: 6px 12px 2px 12px; }}
    QLabel#SectionHeaderToday   {{ color: #E65100; font-weight: bold; font-size: 11px; padding: 6px 12px 2px 12px; }}
    QLabel#SectionHeader        {{ color: #9E9E9E; font-weight: bold; font-size: 11px; padding: 6px 12px 2px 12px; }}
    QLabel#SectionCount         {{ color: #BDBDBD; font-size: 11px; padding: 6px 12px 2px 0; }}

    /* 行内 meta（取消蓝底 chip，全部用浅灰文本） */
    QLabel#TagInline    {{ color: #888; font-size: 11px; padding: 0 2px; }}
    QLabel#DateNormal   {{ color: #777; font-size: 11px; padding: 0 2px; }}
    QLabel#DateToday    {{ color: #E65100; font-size: 11px; font-weight: bold; padding: 0 2px; }}
    QLabel#DateOverdue  {{ color: #C62828; font-size: 11px; font-weight: bold; padding: 0 2px; }}

    /* 标签筛选 chip */
    QPushButton#TagFilter {{
        background: #F0F0F0; color: #555;
        border: 1px solid transparent; border-radius: 10px;
        padding: 2px 10px; font-size: 11px;
    }}
    QPushButton#TagFilter:hover {{ background: #E0E0E0; }}
    QPushButton#TagFilterActive {{
        background: {t['accent']}; color: {t['accent_text']};
        border: 1px solid {t['accent_hover']}; border-radius: 10px;
        padding: 2px 10px; font-size: 11px; font-weight: bold;
    }}

    /* 待办内容（可点击编辑） */
    QLabel#TodoContent {{ color: #333; padding: 2px 0; }}
    QLabel#TodoContent:hover {{ color: {t['accent_hover']}; }}

    /* 拖动手柄：干净的 6 点阵，无背景；hover 时加深 */
    QLabel#DragHandle {{
        color: #B0B0B0;
        font-size: 14px;
        padding: 0 2px;
        background: transparent;
        border-radius: 3px;
        letter-spacing: -1px;
    }}
    QLabel#DragHandle:hover {{
        color: #444;
        background: rgba(0, 0, 0, 0.06);
    }}

    /* 待办备注预览（输入用 | 分隔后显示在标题下方） */
    QLabel#TodoNotes {{
        color: #888;
        font-size: 11px;
        padding: 0;
    }}

    /* 日期快捷 chip（点击即把对应日期填入输入框） */
    QPushButton#DateChip {{
        background: #FFF3E0;
        color: #E65100;
        border: 1px solid #FFCC80;
        border-radius: 10px;
        padding: 2px 10px;
        font-size: 11px;
    }}
    QPushButton#DateChip:hover {{
        background: #FFE0B2;
        border: 1px solid #FF9800;
    }}
    QPushButton#DateChipActive {{
        background: #FB8C00;
        color: #FFFFFF;
        border: 1px solid #E65100;
        border-radius: 10px;
        padding: 2px 10px;
        font-size: 11px;
        font-weight: bold;
    }}
    QPushButton#DateChipActive:hover {{ background: #F57C00; }}
    """


HISTORY_QSS = """
QWidget#HistoryRoot { background: #FAFAFA; }
QListWidget {
    border: 1px solid #E0E0E0;
    background: #FFFFFF;
    font-size: 13px;
    outline: 0;
}
QListWidget::item { padding: 0; border-bottom: 1px solid #F0F0F0; }
QListWidget::item:hover    { background: #F8F8F8; }
QListWidget::item:selected { background: transparent; }

QPushButton#ArchiveBtn {
    background: #E8F0FE;
    color: #1A56DB;
    border: 1px solid #C3D4F8;
    border-radius: 6px;
    padding: 6px 12px;
    font-size: 12px;
}
QPushButton#ArchiveBtn:hover { background: #D6E2FB; }

QPushButton#AnalyzeBtn {
    background: #F0FDF4;
    color: #15803D;
    border: 1px solid #BBF7D0;
    border-radius: 6px;
    padding: 6px 12px;
    font-size: 12px;
}
QPushButton#AnalyzeBtn:hover { background: #DCFCE7; }

QLabel#HistTitle { color: #333; font-size: 13px; padding: 2px 0; }
QLabel#HistTitle:hover { color: #1A56DB; }
QLabel#HistMeta { color: #888; font-size: 11px; }
QLabel#NotePreview {
    color: #5C5036; font-size: 11px;
    background: #FFF9E6; border-left: 3px solid #FFCF5C;
    padding: 4px 8px; border-radius: 2px;
}

QPushButton#RestoreBtn {
    background: #FFFFFF;
    color: #888;
    border: 1px solid #DDD;
    border-radius: 11px;
    font-size: 12px;
    padding: 0;
}
QPushButton#RestoreBtn:hover {
    background: #FFF3E0;
    color: #E65100;
    border: 1px solid #FFB74D;
}
QPushButton#RestoreBtn:pressed {
    background: #FFE0B2;
    color: #BF360C;
}

QPushButton#EditDateBtn {
    background: #FFFFFF;
    color: #888;
    border: 1px solid #DDD;
    border-radius: 11px;
    font-size: 11px;
    padding: 0;
}
QPushButton#EditDateBtn:hover {
    background: #E8F0FE;
    color: #1A56DB;
    border: 1px solid #A5C0F5;
}
QPushButton#EditDateBtn:pressed {
    background: #D2E3FC;
    color: #174EA6;
}

QLabel#PathLabel { color: #666; font-size: 12px; }
QLabel#PathValue {
    color: #333; font-size: 12px;
    background: #F5F5F5;
    border: 1px solid #E0E0E0;
    border-radius: 4px;
    padding: 2px 6px;
}
QPushButton#PathBtn {
    background: #FFFFFF;
    color: #1A56DB;
    border: 1px solid #C3D4F8;
    border-radius: 4px;
    padding: 2px 8px;
    font-size: 12px;
}
QPushButton#PathBtn:hover { background: #E8F0FE; }
"""


TIMER_QSS = """
QWidget#TimerRoot { background: #2B2B33; border: 1px solid #44444F; border-radius: 12px; }
QFrame#TimerBar { background: #34343E; border-top-left-radius: 12px; border-top-right-radius: 12px; }
QLabel#TimerTitle { color: #DDD; font-size: 12px; font-weight: bold; }
QPushButton#TimerClose {
    border: none; background: transparent; color: #999; font-size: 14px; border-radius: 4px;
}
QPushButton#TimerClose:hover { background: rgba(255,255,255,0.1); color: #FFF; }

QLabel#TimerBound { color: #9AB7E0; font-size: 12px; }
QLabel#TimerDisplay { color: #FFFFFF; font-size: 44px; font-weight: bold; }

QPushButton#ModeBtn {
    background: transparent; color: #AAA; border: 1px solid #55555F;
    border-radius: 6px; padding: 3px 12px; font-size: 12px;
}
QPushButton#ModeBtn:hover { color: #FFF; border: 1px solid #7788AA; }
QPushButton#ModeBtnActive {
    background: #5C9CE0; color: #FFFFFF; border: 1px solid #4080CC;
    border-radius: 6px; padding: 3px 12px; font-size: 12px; font-weight: bold;
}

QPushButton#PresetBtn {
    background: #3A3A45; color: #CCC; border: 1px solid #55555F;
    border-radius: 6px; padding: 3px 10px; font-size: 12px;
}
QPushButton#PresetBtn:hover { background: #45454F; color: #FFF; }
QPushButton#PresetBtnActive {
    background: #45454F; color: #FFF; border: 1px solid #7788AA;
    border-radius: 6px; padding: 3px 10px; font-size: 12px; font-weight: bold;
}

QPushButton#CtrlBtn {
    background: #5C9CE0; color: #FFFFFF; border: none;
    border-radius: 8px; padding: 8px 0; font-size: 14px; font-weight: bold;
}
QPushButton#CtrlBtn:hover { background: #4080CC; }
QPushButton#CtrlBtnGhost {
    background: transparent; color: #BBB; border: 1px solid #55555F;
    border-radius: 8px; padding: 8px 0; font-size: 14px;
}
QPushButton#CtrlBtnGhost:hover { color: #FFF; border: 1px solid #7788AA; }
QLabel#TimerHint { color: #888; font-size: 11px; }
"""
