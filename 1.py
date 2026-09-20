# -*- coding: utf-8 -*-
"""
================================================================================
 《一箭又一箭》 Arrow Escape      —— Python + Pygame 实现
================================================================================
 玩法
 ---------------------------------------------------------------------------
 棋盘上散布着指向 上/下/左/右 的箭头。点击一支箭头，程序检测它"正前方直至
 边界"的这条射线上是否存在其它箭头：
     · 射线畅通  →  该箭头沿所指方向飞出棋盘并消失（有飞行动画）
     · 射线有阻挡 →  发生撞击（抖动 + 变红 + 震屏 + 飘字），并消耗一次失误机会
 清空全部箭头 = 过关；失误机会耗尽 = 失败。

 运行方式~
 ---------------------------------------------------------------------------
   python 1.py            正常开始游戏
   python 1.py --solve    无窗口校验：打印 5 个关卡的通关顺序（验证无死锁）
   python 1.py --test     无窗口自测：校验路径检测 / 胜负判定 / 状态机

 依赖
 ---------------------------------------------------------------------------
   pip install pygame          （本文件在 Python 3.10 + pygame 2.6.1 上通过）

 代码结构（自顶向下）
 ---------------------------------------------------------------------------
   ① 基础常量与配色        ② 关卡数据与可解性校验
   ③ 核心逻辑 Arrow/Level  ④ 绘制辅助（箭头精灵/心形/虚线/文字）
   ⑤ UI 组件 Button        ⑥ 特效 Particle / FloatText
   ⑦ Game 状态机（菜单/游玩/胜利/失败）   ⑧ 程序入口与测试
================================================================================
"""

import math
import os
import random
import sys

import pygame

# =============================================================================
# ① 基础常量与配色
# =============================================================================
TITLE = "一箭又一箭"
WIDTH, HEIGHT = 600, 800          # 窗口尺寸（竖屏，方便网格居中）
FPS = 60

HEADER_H = 150                    # 顶部信息栏
BOTTOM_H = 132                    # 底部控制栏

# ---- 方向编码：与关卡数据中的数字一一对应 ----
UP, DOWN, LEFT, RIGHT = 1, 2, 3, 4
DIR_VEC = {UP: (0, -1), DOWN: (0, 1), LEFT: (-1, 0), RIGHT: (1, 0)}   # (dx, dy)
DIR_NAME = {UP: "↑", DOWN: "↓", LEFT: "←", RIGHT: "→"}

# ---- 动画参数（全部按"秒"计时，与帧率无关） ----
FLY_SPEED = 13.0                  # 飞出速度：格 / 秒
COLLIDE_TIME = 0.40               # 撞击抖动持续时间
FLASH_TIME = 0.30                 # 被撞箭头闪亮时间
SHAKE_TIME = 0.30                 # 屏幕震动时间
LOSE_DELAY = 0.75                 # 失误耗尽后延迟弹出失败面板（让动画播完）

# ---- 状态机 ----
MENU, PLAYING, WIN, LOSE = "MENU", "PLAYING", "WIN", "LOSE"

# ---- 配色 ----
C_BG = (21, 23, 37)               # 背景渐变起
C_BG2 = (33, 36, 58)              # 背景渐变终
C_PANEL = (44, 49, 74)            # 卡片 / 按钮
C_BOARD = (28, 31, 48)            # 棋盘底盘
C_GRID = (54, 59, 86)             # 虚线网格
C_LINE = (62, 69, 100)            # 分隔线
C_TEXT = (233, 237, 250)
C_DIM = (142, 150, 180)
C_ARROW = (94, 198, 255)          # 箭头本体
C_ARROW_EDGE = (196, 240, 255)    # 箭头描边
C_DANGER = (255, 96, 96)          # 撞击红
C_DANGER_EDGE = (255, 205, 205)
C_FLASH = (255, 208, 96)          # 被撞者闪亮
C_FLASH_EDGE = (255, 245, 205)
C_OK = (110, 226, 152)
C_GOLD = (255, 205, 92)
C_BTN = (58, 66, 100)
C_BTN_HOVER = (80, 92, 138)
C_BTN_DOWN = (42, 48, 76)
C_BTN_PRIMARY = (38, 132, 176)
C_BTN_PRIMARY_HOVER = (52, 164, 214)

# ---- 中文字体候选 ----
# 注意：直接按"字体文件路径"加载，而不是用 pygame.font.SysFont / match_font。
#       因为部分 pygame 版本在扫描 Windows 字体注册表时会抛
#       TypeError（sysfont.py 的 initsysfonts_win32），一旦崩了，
#       SysFont 和 match_font 都不可用。按文件加载最稳，三层回退：
#         ① 常见字体文件路径 → ② pygame 系统字体库 → ③ pygame 内置默认字体
CJK_FONT_FILES = [
    ("msyh.ttc", "msyhbd.ttc"),                     # 微软雅黑 / 雅黑粗体
    ("simhei.ttf", None),                           # 黑体
    ("Deng.ttf", None),                             # 等线
    ("simsun.ttc", None),                           # 宋体
    ("NotoSansCJK-Regular.ttc", None),              # Noto（Linux 常见）
    ("wqy-microhei.ttc", None),                     # 文泉驿微米黑
    ("PingFang.ttc", None),                         # 苹方（macOS）
    ("Songti.ttc", None),
]
FONT_DIRS = [
    os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts"),
    "/usr/share/fonts/opentype/noto",
    "/usr/share/fonts/truetype/noto",
    "/usr/share/fonts/truetype/wqy",
    "/System/Library/Fonts",
    os.path.expanduser("~/.fonts"),
]
CJK_FONT_NAMES = [
    "microsoftyaheiui", "microsoftyahei", "msyh", "simhei", "simsun",
    "notosanscjksc", "sourcehansanssc", "pingfangsc", "heiti",
    "wenquanyimicrohei", "arialunicodems",
]
_font_files = []            # 缓存字体解析结果：[常规文件, 粗体文件]
_font_warned = []           # 是否已经提示过"没有中文字体"

# =============================================================================
# ② 关卡数据
#    0 = 空格   1 = ↑   2 = ↓   3 = ←   4 = →
#    以下 5 个关卡均已用 solve_level() 校验过"必定可通关"（见 --solve）。
#    难度递增：初始可点击的箭头越少、依赖链越长，就越难。
# =============================================================================
LEVELS = [
    {
        "name": "热身",
        "mistakes": 3,
        "grid": [
            [4, 2, 0],
            [1, 0, 0],
            [0, 0, 3],
        ],
    },
    {
        "name": "连锁",
        "mistakes": 3,
        "grid": [
            [2, 3, 2, 0],
            [2, 0, 0, 0],
            [2, 1, 3, 0],
            [4, 0, 0, 0],
        ],
    },
    {
        "name": "交错",
        "mistakes": 3,
        "grid": [
            [0, 0, 4, 4, 2],
            [4, 0, 0, 2, 0],
            [1, 0, 0, 4, 4],
            [1, 0, 0, 0, 3],
            [1, 0, 0, 0, 3],
        ],
    },
    {
        "name": "迷宫",
        "mistakes": 4,
        "grid": [
            [0, 0, 2, 2, 3, 0],
            [4, 1, 0, 2, 0, 4],
            [1, 3, 3, 0, 0, 0],
            [0, 2, 0, 3, 0, 0],
            [4, 4, 0, 0, 0, 4],
        ],
    },
    {
        "name": "终章",
        "mistakes": 4,
        "grid": [
            [0, 4, 0, 1, 4, 2],
            [0, 1, 0, 0, 0, 2],
            [0, 2, 3, 1, 0, 0],
            [1, 0, 0, 0, 1, 0],
            [1, 0, 3, 1, 0, 0],
            [1, 3, 1, 0, 0, 3],
        ],
    },
]


# =============================================================================
# ③ 核心逻辑
# =============================================================================
class Arrow:
    """棋盘上的一支箭头。

    逻辑状态只有 removed 一个（被点了/没被点），
    state 专门负责"看起来怎么样"，这样点击判定永远立刻生效，
    不会出现"动画还没播完，别的箭头误判被挡"的问题。
    """

    __slots__ = ("row", "col", "direction", "removed", "state",
                 "offset_x", "offset_y", "alpha", "timer", "flash",
                 "fly_dist", "fly_limit")

    def __init__(self, row, col, direction):
        self.row = row
        self.col = col
        self.direction = direction
        self.removed = False        # 逻辑：是否已消除
        self.state = "IDLE"         # 表现：IDLE / FLYING / COLLIDING / GONE
        self.offset_x = 0.0         # 飞行位移（单位：格）
        self.offset_y = 0.0
        self.alpha = 255            # 透明度（飞行尾段淡出）
        self.timer = 0.0            # 当前动画已播放时长
        self.flash = 0.0            # 被撞后的闪亮倒计时
        self.fly_dist = 0.0         # 已飞行距离（格）
        self.fly_limit = 0.0        # 本次飞行的总距离（格）


class Level:
    """一关：网格 + 箭头集合 + 失误次数。所有判定都是纯逻辑，不依赖界面。"""

    def __init__(self, data, mistakes=3):
        self.rows = len(data)
        self.cols = max(len(r) for r in data)
        # 补零，保证矩形，避免关卡数据写错导致下标越界
        self.grid = [list(r) + [0] * (self.cols - len(r)) for r in data]
        self.max_mistakes = mistakes
        self.reset()

    # ---------------------------------------------------------------- 状态
    def reset(self):
        """重新开始本关：重建全部箭头，恢复失误次数。"""
        self.arrows = {}
        for r, row in enumerate(self.grid):
            for c, v in enumerate(row):
                if v in DIR_VEC:
                    self.arrows[(r, c)] = Arrow(r, c, v)
        self.total = len(self.arrows)
        self.mistakes = self.max_mistakes

    def remaining(self):
        """还剩几支箭头没消除。"""
        return sum(1 for a in self.arrows.values() if not a.removed)

    # ------------------------------------------------- 4.1 路径检测算法
    def blocker_of(self, arrow):
        """从 arrow 往前一格开始，沿它的方向一直扫到边界。

        返回挡路的第一支箭头；射线畅通则返回 None。
        这正是规则里的"正前方至边界之间是否有其它箭头"。
        """
        dx, dy = DIR_VEC[arrow.direction]
        r, c = arrow.row + dy, arrow.col + dx
        while 0 <= r < self.rows and 0 <= c < self.cols:
            other = self.arrows.get((r, c))
            if other is not None and not other.removed:
                return other
            r += dy
            c += dx
        return None

    def is_clear(self, arrow):
        return self.blocker_of(arrow) is None

    def free_arrows(self):
        """当前所有可以安全点击（前方无阻挡）的箭头。"""
        return [a for a in self.arrows.values()
                if not a.removed and self.is_clear(a)]

    def exit_distance(self, arrow):
        """箭头完全飞出棋盘需要走的格数（含多飞一点，保证视觉上飞出去）。"""
        if arrow.direction == RIGHT:
            return (self.cols - arrow.col) + 1.2
        if arrow.direction == LEFT:
            return (arrow.col + 1) + 1.2
        if arrow.direction == DOWN:
            return (self.rows - arrow.row) + 1.2
        return (arrow.row + 1) + 1.2          # UP


def solve_level(data):
    """贪心求解器：反复移除"前方无阻挡"的箭头。

    为什么贪心是对的？——消除箭头只会让别的箭头的射线更通畅（单调性），
    所以"能拆就拆"永远不亏：如果存在通关顺序，那么它的第一步必然也是
    贪心可以选的。因此贪心卡住时，就一定是死锁，可以直接判定无解。
    返回 [(行, 列, 方向), ...]；无解返回 None。
    """
    lv = Level(data)
    order = []
    while True:
        free = lv.free_arrows()
        if not free:
            break
        a = free[0]
        a.removed = True
        order.append((a.row, a.col, DIR_NAME[a.direction]))
    return order if lv.remaining() == 0 else None


# =============================================================================
# ④ 绘制辅助
# =============================================================================
_sprite_cache = {}          # 箭头精灵缓存：避免每帧重复构建多边形


def resolve_font_files():
    """找出「常规 / 粗体」两个中文字体文件路径（找不到则为 None），结果会缓存。"""
    if not _font_files:
        regular = bold = None
        for name, bold_name in CJK_FONT_FILES:
            for folder in FONT_DIRS:
                candidate = os.path.join(folder, name)
                if os.path.isfile(candidate):
                    regular = candidate
                    if bold_name:
                        bold_path = os.path.join(folder, bold_name)
                        if os.path.isfile(bold_path):
                            bold = bold_path
                    break
            if regular:
                break
        _font_files.extend([regular, bold])
    return _font_files[0], _font_files[1]


def find_cjk_font():
    """返回可用的中文字体文件路径，找不到返回 None。"""
    return resolve_font_files()[0]


def fit_font(size, bold=False):
    """按字号取字体。① 字体文件 → ② 系统字体库 → ③ 内置默认字体。"""
    regular, bold_file = resolve_font_files()
    path = bold_file if (bold and bold_file) else regular
    if path:
        try:
            font = pygame.font.Font(path, size)
            if bold and not bold_file:
                font.set_bold(True)          # 没有独立粗体时用合成加粗
            return font
        except Exception:
            pass
    try:                                     # ② 个别 pygame 版本扫描注册表会报错
        return pygame.font.SysFont(",".join(CJK_FONT_NAMES), size, bold=bold)
    except Exception:
        if not _font_warned:
            _font_warned.append(True)
            print("[提示] 未找到中文字体，界面文字可能显示为方块。")
        return pygame.font.Font(None, size)  # ③ 至少不会崩溃


_fonts = {}


def get_font(size, bold=False):
    key = (size, bold)
    if key not in _fonts:
        _fonts[key] = fit_font(size, bold)
    return _fonts[key]


def rotate_point(point, direction):
    """把"指向右"的基准坐标旋转到实际方向（顺时针 90° 的整数倍）。"""
    x, y = point
    if direction == RIGHT:
        return (x, y)
    if direction == LEFT:
        return (-x, y)
    if direction == UP:
        return (y, -x)
    return (-y, x)                       # DOWN


def get_arrow_sprite(size, direction, body, edge):
    """生成/取出一个正方形的箭头图片（带透明通道）。"""
    key = (size, direction, body, edge)
    spr = _sprite_cache.get(key)
    if spr is None:
        s = float(size)
        L = 0.34 * s        # 箭头半长
        W = 0.110 * s       # 箭杆半宽
        H = 0.30 * s        # 箭头三角的长度
        HW = 0.215 * s      # 箭头三角的半宽

        # 以"指向右"为基准的多边形（箭杆 + 箭头一体）
        local = [
            (-L, -W), (L - H, -W), (L - H, -HW), (L, 0.0),
            (L - H, HW), (L - H, W), (-L, W),
        ]
        half = s / 2.0
        pts = [(half + x, half + y)
               for x, y in (rotate_point(p, direction) for p in local)]

        spr = pygame.Surface((size, size), pygame.SRCALPHA)
        pygame.draw.polygon(spr, body, pts)
        pygame.draw.polygon(spr, edge, pts, max(2, size // 26))
        _sprite_cache[key] = spr
    return spr


def with_alpha(surface, alpha):
    """返回一个整体透明度被缩放过的副本（在 Surface 上做 alpha 乘法）。"""
    if alpha >= 255:
        return surface
    copy = surface.copy()
    copy.fill((255, 255, 255, max(0, min(255, int(alpha)))),
              special_flags=pygame.BLEND_RGBA_MULT)
    return copy


def draw_dashed_line(surface, color, start, end, dash=7, gap=5, width=2):
    """画虚线（用于网格辅助线）。"""
    x1, y1 = start
    x2, y2 = end
    length = math.hypot(x2 - x1, y2 - y1)
    if length <= 0:
        return
    ux, uy = (x2 - x1) / length, (y2 - y1) / length
    pos = 0.0
    while pos < length:
        seg = min(dash, length - pos)
        a = (x1 + ux * pos, y1 + uy * pos)
        b = (x1 + ux * (pos + seg), y1 + uy * (pos + seg))
        pygame.draw.line(surface, color, a, b, width)
        pos += dash + gap


def draw_arrow_icon(surface, center, size, direction, body=C_ARROW, edge=C_ARROW_EDGE):
    """画一支小箭头（用于标题栏 / 菜单装饰）。"""
    spr = get_arrow_sprite(int(size), direction, body, edge)
    surface.blit(spr, spr.get_rect(center=center))


def draw_heart(surface, center, size, color):
    """用两个圆 + 一个三角拼出实心心形（不依赖字体里的 ♥ 字形）。"""
    cx, cy = center
    r = size * 0.28
    pygame.draw.circle(surface, color, (cx - size * 0.22, cy - size * 0.16), r)
    pygame.draw.circle(surface, color, (cx + size * 0.22, cy - size * 0.16), r)
    pygame.draw.polygon(surface, color, [
        (cx - size * 0.50, cy - size * 0.02),
        (cx + size * 0.50, cy - size * 0.02),
        (cx, cy + size * 0.52),
    ])


# =============================================================================
# ⑤ UI 组件
# =============================================================================
class Button:
    """一个朴素的圆角按钮：自己处理"悬停 / 按下"的配色。"""

    def __init__(self, rect, label, primary=False, size=24):
        self.rect = pygame.Rect(rect)
        self.label = label
        self.primary = primary
        self.size = size

    def hovered(self):
        return self.rect.collidepoint(pygame.mouse.get_pos())

    def draw(self, surface):
        hover = self.hovered()
        if self.primary:
            color = C_BTN_PRIMARY_HOVER if hover else C_BTN_PRIMARY
        else:
            color = C_BTN_HOVER if hover else C_BTN
        pygame.draw.rect(surface, color, self.rect, border_radius=12)
        pygame.draw.rect(surface, C_LINE, self.rect, width=2, border_radius=12)
        text = get_font(self.size, bold=True).render(self.label, True, C_TEXT)
        surface.blit(text, text.get_rect(center=self.rect.center))

    def hit(self, pos):
        return self.rect.collidepoint(pos)


# =============================================================================
# ⑥ 特效：飘字、粒子（满足"明显的反馈"）
# =============================================================================
class FloatText:
    def __init__(self, text, center, color, size=30, life=0.9, rise=70.0):
        self.text = text
        self.x, self.y = center
        self.color = color
        self.size = size
        self.life = life
        self.t = 0.0
        self.rise = rise

    def update(self, dt):
        self.t += dt
        self.y -= self.rise * dt
        return self.t < self.life

    def draw(self, surface):
        p = self.t / self.life
        alpha = 255 if p < 0.55 else int(255 * (1 - (p - 0.55) / 0.45))
        img = get_font(self.size, bold=True).render(self.text, True, self.color)
        surface.blit(with_alpha(img, alpha), img.get_rect(center=(self.x, self.y)))


class Particle:
    def __init__(self, center, color):
        self.x, self.y = center
        self.vx = random.uniform(-260, 260)
        self.vy = random.uniform(-340, -40)
        self.color = color
        self.life = random.uniform(0.55, 1.15)
        self.t = 0.0
        self.r = random.uniform(2.0, 4.5)

    def update(self, dt):
        self.vy += 780 * dt
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.t += dt
        return self.t < self.life

    def draw(self, surface):
        alpha = int(255 * max(0.0, 1 - self.t / self.life))
        r = max(1, int(self.r * (1 - 0.5 * self.t / self.life)))
        pygame.draw.circle(surface, self.color, (int(self.x), int(self.y)), r)


# =============================================================================
# ⑦ 游戏主类：状态机 MENU / PLAYING / WIN / LOSE
# =============================================================================
class Game:
    def __init__(self, headless=False):
        self.headless = headless
        pygame.init()
        pygame.font.init()
        self.clock = pygame.time.Clock()

        if headless:                       # 供自测使用：不创建窗口
            self.screen = pygame.Surface((WIDTH, HEIGHT))
        else:
            try:
                self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
            except pygame.error as exc:    # 没有显示设备时的友好提示
                print("无法创建游戏窗口：", exc)
                raise SystemExit(1)
            pygame.display.set_caption("%s · Arrow Escape" % TITLE)

        self.bg = self.make_background()

        # ---- 运行时状态 ----
        self.state = MENU
        self.running = True
        self.level_index = 0
        self.level = None
        self.board = (40, 200, 60)         # (左上角 x, y, 格子边长)
        self.effects = []
        self.level_time = 0.0
        self.shake_t = 0.0
        self.flash_t = 0.0
        self.pending_win = False           # 已清空，等飞行动画播完再结算
        self.lose_timer = None             # 失误耗尽后的延迟倒计时
        self.overlay_buttons = []

        cx = WIDTH // 2
        self.btns_menu = [
            Button((cx - 110, 430, 220, 58), "开始游戏", True, 26),
            Button((cx - 110, 506, 220, 58), "退出游戏", False, 26),
        ]
        bw, bh, gap = 200, 56, 40
        self.btns_play = [
            Button((cx - (bw * 2 + gap) // 2, HEIGHT - 78, bw, bh), "重新开始", False, 24),
            Button((cx + gap // 2, HEIGHT - 78, bw, bh), "返回主菜单", False, 24),
        ]

    # ------------------------------------------------------------ 背景
    @staticmethod
    def make_background():
        """预渲染一张竖直渐变背景，避免每帧逐行绘制。"""
        bg = pygame.Surface((WIDTH, HEIGHT))
        for y in range(HEIGHT):
            t = y / float(HEIGHT - 1)
            color = tuple(int(C_BG[i] + (C_BG2[i] - C_BG[i]) * t) for i in range(3))
            pygame.draw.line(bg, color, (0, y), (WIDTH, y))
        return bg

    # ------------------------------------------------------- 关卡与布局
    def start_level(self, index=None):
        """载入并开始某一关（index 为 None 表示重开当前关）。"""
        if index is not None:
            self.level_index = index % len(LEVELS)
        conf = LEVELS[self.level_index]
        self.level = Level(conf["grid"], conf["mistakes"])
        self.compute_board()
        self.effects.clear()
        self.pending_win = False
        self.lose_timer = None
        self.level_time = 0.0
        self.shake_t = 0.0
        self.flash_t = 0.0
        self.state = PLAYING

    def compute_board(self):
        """根据行列数算出居中的棋盘区域与格子边长。"""
        lv = self.level
        top = HEADER_H + 8
        bottom = HEIGHT - BOTTOM_H - 8
        avail_w = WIDTH - 80
        avail_h = bottom - top
        cell = int(min(avail_w / lv.cols, avail_h / lv.rows))
        cell = max(40, min(cell, 78))
        bw, bh = cell * lv.cols, cell * lv.rows
        self.board = ((WIDTH - bw) // 2, top + (avail_h - bh) // 2, cell)

    def restart_level(self):
        self.start_level()

    def next_action(self):
        """胜利面板的主按钮：还有下一关就继续，否则从头再玩。"""
        if self.level_index + 1 < len(LEVELS):
            self.start_level(self.level_index + 1)
        else:
            self.start_level(0)

    def goto_menu(self):
        self.state = MENU
        self.effects.clear()

    # ------------------------------------------------------------ 交互
    def cell_at(self, pos):
        """屏幕坐标 → 格子坐标；点在棋盘外返回 None。"""
        if self.level is None:
            return None
        bx, by, cell = self.board
        x, y = pos
        if not (bx <= x < bx + cell * self.level.cols and
                by <= y < by + cell * self.level.rows):
            return None
        return (int((y - by) // cell), int((x - bx) // cell))

    def cell_center(self, row, col):
        bx, by, cell = self.board
        return (bx + (col + 0.5) * cell, by + (row + 0.5) * cell)

    def click_arrow(self, row, col):
        """核心点击逻辑。返回 True 表示成功消除，False 表示撞击或无效点击。"""
        lv = self.level
        if lv is None or self.pending_win or self.lose_timer is not None:
            return False
        arrow = lv.arrows.get((row, col))
        if arrow is None or arrow.removed:
            return False

        blocker = lv.blocker_of(arrow)

        # ---------------- 情况一：射线畅通 → 飞出消除 ----------------
        if blocker is None:
            arrow.removed = True                 # 逻辑立刻生效，避免误判阻挡
            arrow.state = "FLYING"
            arrow.fly_dist = 0.0
            arrow.fly_limit = lv.exit_distance(arrow)
            cx, cy = self.cell_center(row, col)
            for _ in range(6):                   # 起飞的尘屑
                self.effects.append(Particle((cx, cy), C_ARROW))
            if lv.remaining() == 0:
                self.pending_win = True          # 等飞行动画播完再弹胜利面板
            return True

        # ---------------- 情况二：有阻挡 → 撞击反馈 ----------------
        arrow.state = "COLLIDING"
        arrow.timer = 0.0
        blocker.flash = FLASH_TIME               # 被撞的那支闪一下
        self.shake_t = SHAKE_TIME                # 震屏
        self.flash_t = 0.12                      # 红屏闪
        cx, cy = self.cell_center(row, col)
        self.effects.append(FloatText("撞击！", (cx, cy - 34), C_DANGER, 30, 0.9))
        self.effects.append(FloatText("-1", (cx, cy + 6), C_GOLD, 26, 0.9, 55.0))
        for _ in range(10):
            self.effects.append(Particle((cx, cy), C_DANGER))

        lv.mistakes -= 1
        if lv.mistakes <= 0:
            self.lose_timer = LOSE_DELAY
        return False

    def on_win(self):
        self.state = WIN
        bx, by, cell = self.board
        cx = bx + cell * self.level.cols / 2.0
        cy = by + cell * self.level.rows / 2.0
        for _ in range(90):                      # 通关礼花
            self.effects.append(Particle((cx, cy), random.choice([C_GOLD, C_OK, C_ARROW])))

    # ---------------------------------------------------------- 动画更新
    def update(self, dt):
        lv = self.level
        if self.state == PLAYING and lv is not None:
            self.level_time += dt
            for arrow in lv.arrows.values():
                if arrow.flash > 0.0:
                    arrow.flash = max(0.0, arrow.flash - dt)
                if arrow.state == "FLYING":
                    dx, dy = DIR_VEC[arrow.direction]
                    arrow.fly_dist += FLY_SPEED * dt
                    arrow.offset_x = dx * arrow.fly_dist
                    arrow.offset_y = dy * arrow.fly_dist
                    p = arrow.fly_dist / max(0.001, arrow.fly_limit)
                    # 飞过棋盘后开始淡出
                    arrow.alpha = 255 if p < 0.62 else int(255 * max(0.0, (1 - p) / 0.38))
                    if arrow.fly_dist >= arrow.fly_limit:
                        arrow.state = "GONE"
                elif arrow.state == "COLLIDING":
                    arrow.timer += dt
                    if arrow.timer >= COLLIDE_TIME:
                        arrow.state = "IDLE"
                        arrow.timer = 0.0

            flying = any(a.state == "FLYING" for a in lv.arrows.values())
            if self.pending_win and not flying:
                self.pending_win = False
                self.on_win()
            if self.lose_timer is not None:
                self.lose_timer -= dt
                if self.lose_timer <= 0.0:
                    self.lose_timer = None
                    self.state = LOSE

        self.effects = [e for e in self.effects if e.update(dt)]
        if self.shake_t > 0.0:
            self.shake_t = max(0.0, self.shake_t - dt)
        if self.flash_t > 0.0:
            self.flash_t = max(0.0, self.flash_t - dt)

    def shake_offset(self):
        """震屏位移：随时间衰减的正弦抖动。"""
        if self.shake_t <= 0.0:
            return (0.0, 0.0)
        amp = 7.0 * (self.shake_t / SHAKE_TIME)
        return (math.sin(self.shake_t * 92.0) * amp,
                math.cos(self.shake_t * 74.0) * amp * 0.6)

    # ------------------------------------------------------------ 事件
    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                self.on_key(event.key)
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                self.on_click(event.pos)

    def on_key(self, key):
        if key == pygame.K_ESCAPE:
            if self.state == MENU:
                self.running = False
            else:
                self.goto_menu()
        elif key in (pygame.K_SPACE, pygame.K_RETURN):
            if self.state == MENU:
                self.start_level(0)
            elif self.state == WIN:
                self.next_action()
            elif self.state == LOSE:
                self.restart_level()
        elif key == pygame.K_r and self.state == PLAYING:
            self.restart_level()

    def on_click(self, pos):
        if self.state == MENU:
            if self.btns_menu[0].hit(pos):
                self.start_level(0)
            elif self.btns_menu[1].hit(pos):
                self.running = False
            return

        if self.state == PLAYING:
            for btn in self.btns_play:
                if btn.hit(pos):
                    if btn.label == "重新开始":
                        self.restart_level()
                    else:
                        self.goto_menu()
                    return
            cell = self.cell_at(pos)              # 命中棋盘才处理点击
            if cell:
                self.click_arrow(*cell)
            return

        # WIN / LOSE：只响应浮层按钮，点击不会"穿透"到下面的棋盘
        for btn in self.overlay_buttons:
            if btn.hit(pos):
                if btn.label == "返回主菜单":
                    self.goto_menu()
                elif self.state == WIN:
                    self.next_action()
                else:
                    self.restart_level()
                return

    # ------------------------------------------------------------ 渲染
    def text(self, content, size, color, pos, anchor="topleft", bold=False, alpha=255):
        img = get_font(size, bold).render(content, True, color)
        img = with_alpha(img, alpha)
        rect = img.get_rect(**{anchor: pos})
        self.screen.blit(img, rect)
        return rect

    def draw(self):
        self.screen.blit(self.bg, (0, 0))
        if self.state == MENU:
            self.draw_menu()
        else:
            self.draw_header()
            self.draw_board()
            self.draw_bottom()
        for effect in self.effects:
            effect.draw(self.screen)
        if self.flash_t > 0.0:                    # 撞击时的红屏一闪
            flash = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            flash.fill((255, 60, 60, int(70 * (self.flash_t / 0.12))))
            self.screen.blit(flash, (0, 0))
        if self.state in (WIN, LOSE):
            self.draw_overlay()

    # ---- 菜单界面 ----
    def draw_menu(self):
        self.text(TITLE, 66, C_TEXT, (WIDTH // 2, 168), "center", True)
        self.text("点一下箭头，让它朝所指的方向飞出边界", 22, C_DIM,
                  (WIDTH // 2, 226), "center")

        # 装饰：一个"靶心"周围绕着四支箭头
        cx, cy = WIDTH // 2, 330
        pygame.draw.circle(self.screen, (40, 45, 68), (cx, cy), 62)
        pygame.draw.circle(self.screen, C_LINE, (cx, cy), 62, 2)
        pygame.draw.circle(self.screen, C_GOLD, (cx, cy), 22, 3)
        for direction, (ox, oy) in zip([UP, RIGHT, DOWN, LEFT],
                                       [(0, -96), (96, 0), (0, 96), (-96, 0)]):
            draw_arrow_icon(self.screen, (cx + ox, cy + oy), 54, direction)

        for btn in self.btns_menu:
            btn.draw(self.screen)

        tips = [
            "· 正前方没有别的箭头 → 它就会沿方向飞出并消失",
            "· 正前方被挡住 → 撞击，损失一次失误机会",
            "· 清空全部箭头即可过关，失误机会耗尽则失败",
            "快捷键：R 重开本关 ／ ESC 返回菜单 ／ 空格 确认",
        ]
        for i, line in enumerate(tips):
            self.text(line, 19, C_DIM, (WIDTH // 2, 606 + i * 32), "center")

    # ---- 顶部信息栏 ----
    def draw_header(self):
        lv = self.level
        conf = LEVELS[self.level_index]
        self.text("第 %d / %d 关  ·  %s" % (self.level_index + 1, len(LEVELS), conf["name"]),
                  26, C_TEXT, (30, 26), "topleft", True)

        # 右上角：剩余箭头数量（先算宽度，整体右对齐，避免和标签挤在一起）
        label = get_font(21).render("剩余箭头", True, C_DIM)
        count = get_font(30, True).render(str(lv.remaining()), True, C_TEXT)
        count_x = WIDTH - 30 - count.get_width()
        label_x = count_x - 10 - label.get_width()
        self.screen.blit(count, (count_x, 26))
        self.screen.blit(label, (label_x, 35))
        draw_arrow_icon(self.screen, (label_x - 24, 42), 30, RIGHT)

        # 失误机会（心形）—— 已用掉的画成暗色
        self.text("失误机会", 21, C_DIM, (30, 74), "topleft")
        for i in range(lv.max_mistakes):
            alive = i < lv.mistakes
            draw_heart(self.screen, (150 + i * 34, 86), 30,
                       C_DANGER if alive else (66, 60, 78))

        # 本关用时
        self.text("用时 %.1fs" % self.level_time, 21, C_DIM,
                  (WIDTH - 30, 84), "topright")

        pygame.draw.line(self.screen, C_LINE, (24, HEADER_H - 14),
                         (WIDTH - 24, HEADER_H - 14), 2)

    # ---- 棋盘 ----
    def draw_board(self):
        lv = self.level
        if lv is None:
            return
        bx, by, cell = self.board
        ox, oy = self.shake_offset()
        bx, by = bx + ox, by + oy
        gw, gh = cell * lv.cols, cell * lv.rows

        # 底盘
        pygame.draw.rect(self.screen, C_BOARD,
                         pygame.Rect(bx - 10, by - 10, gw + 20, gh + 20),
                         border_radius=18)
        pygame.draw.rect(self.screen, C_LINE,
                         pygame.Rect(bx - 10, by - 10, gw + 20, gh + 20),
                         width=2, border_radius=18)
        # 虚线网格（视觉辅助）
        for c in range(lv.cols + 1):
            x = bx + c * cell
            draw_dashed_line(self.screen, C_GRID, (x, by), (x, by + gh))
        for r in range(lv.rows + 1):
            y = by + r * cell
            draw_dashed_line(self.screen, C_GRID, (bx, y), (bx + gw, y))

        # 箭头
        for arrow in lv.arrows.values():
            if arrow.state == "GONE":
                continue
            cx = bx + (arrow.col + 0.5 + arrow.offset_x) * cell
            cy = by + (arrow.row + 0.5 + arrow.offset_y) * cell

            if arrow.state == "COLLIDING":                 # 抖动
                k = 1.0 - arrow.timer / COLLIDE_TIME
                amp = 6.0 * max(0.0, k)
                cx += math.sin(arrow.timer * 62.0) * amp
                cy += math.cos(arrow.timer * 71.0) * amp * 0.7

            if arrow.state == "COLLIDING":
                body, edge = C_DANGER, C_DANGER_EDGE
            elif arrow.flash > 0.0:
                body, edge = C_FLASH, C_FLASH_EDGE
            else:
                body, edge = C_ARROW, C_ARROW_EDGE

            dxx, dyy = DIR_VEC[arrow.direction]
            if arrow.state == "FLYING":                    # 拖尾
                for k, a in ((0.22, 90), (0.42, 40)):
                    ghost = get_arrow_sprite(cell, arrow.direction, body, edge)
                    self.screen.blit(with_alpha(ghost, a),
                                     (cx - dxx * cell * k - cell / 2,
                                      cy - dyy * cell * k - cell / 2))

            spr = get_arrow_sprite(cell, arrow.direction, body, edge)
            self.screen.blit(with_alpha(spr, arrow.alpha), (cx - cell / 2, cy - cell / 2))

    # ---- 底部控制栏 ----
    def draw_bottom(self):
        line_y = HEIGHT - BOTTOM_H + 6
        pygame.draw.line(self.screen, C_LINE, (24, line_y), (WIDTH - 24, line_y), 2)
        self.text("点击箭头 → 前方无阻挡即可飞出", 19, C_DIM,
                  (WIDTH // 2, line_y + 26), "center")
        for btn in self.btns_play:
            btn.draw(self.screen)

    # ---- 结算浮层 ----
    def panel_rect(self):
        return pygame.Rect((WIDTH - 440) // 2, (HEIGHT - 300) // 2, 440, 300)

    def build_overlay_buttons(self, primary_label):
        panel = self.panel_rect()
        w, h, gap = 168, 52, 24
        x0 = WIDTH // 2 - (w * 2 + gap) // 2
        y = panel.bottom - 88
        self.overlay_buttons = [
            Button((x0, y, w, h), primary_label, True, 23),
            Button((x0 + w + gap, y, w, h), "返回主菜单", False, 23),
        ]

    def draw_overlay(self):
        mask = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        mask.fill((8, 10, 20, 195))
        self.screen.blit(mask, (0, 0))

        panel = self.panel_rect()
        pygame.draw.rect(self.screen, (34, 38, 60), panel, border_radius=20)
        pygame.draw.rect(self.screen, C_LINE, panel, width=2, border_radius=20)

        lv = self.level
        cx = panel.centerx
        if self.state == WIN:
            last = self.level_index + 1 >= len(LEVELS)
            self.text("全部通关！" if last else "过关！", 48,
                      C_GOLD, (cx, panel.y + 58), "center", True)
            self.text("用时 %.1f 秒   剩余机会 %d / %d"
                      % (self.level_time, lv.mistakes, lv.max_mistakes),
                      22, C_TEXT, (cx, panel.y + 124), "center")
            self.text("第 %d 关已经清空" % (self.level_index + 1), 20, C_DIM,
                      (cx, panel.y + 160), "center")
            self.build_overlay_buttons("再玩一次" if last else "下一关")
        else:
            self.text("失败了…", 46, C_DANGER, (cx, panel.y + 58), "center", True)
            self.text("失误机会已经用尽", 22, C_TEXT, (cx, panel.y + 124), "center")
            self.text("先找出正前方没有阻挡的那一支", 20, C_DIM,
                      (cx, panel.y + 160), "center")
            self.build_overlay_buttons("重试本关")

        for btn in self.overlay_buttons:
            btn.draw(self.screen)

    # ------------------------------------------------------------ 主循环
    def run(self):
        while self.running:
            raw = self.clock.tick(FPS) / 1000.0
            dt = min(raw, 0.05)        # 限制单帧步长：卡顿时也不会让箭头瞬移
            self.handle_events()
            self.update(dt)
            self.draw()
            pygame.display.flip()
        pygame.quit()


# =============================================================================
# ⑧ 入口：正常游玩 / 关卡校验 / 自测
# =============================================================================
def cmd_solve():
    """--solve：校验每个关卡是否可通关，并打印一种通关顺序。"""
    print("=" * 60)
    print("关卡可解性校验（贪心求解）")
    print("=" * 60)
    bad = 0
    for i, conf in enumerate(LEVELS, 1):
        order = solve_level(conf["grid"])
        rows, cols = len(conf["grid"]), len(conf["grid"][0])
        head = "第 %d 关 %-4s %dx%d 共 %d 支箭头  " % (
            i, conf["name"], rows, cols,
            sum(1 for row in conf["grid"] for v in row if v))
        if order is None:
            print(head + "[X] 无解（存在互锁死局），请重新设计！")
            bad += 1
            continue
        print(head + "[OK] 可通关（共 %d 支需要依次清理）" % len(order))
        print("      通关顺序：" + " → ".join(
            "(%d,%d)%s" % (r, c, d) for r, c, d in order))
    print("-" * 60)
    print("结论：%d 个关卡，%d 个不可解" % (len(LEVELS), bad))
    return 1 if bad else 0


def cmd_test():
    """--test：无窗口自测核心规则（路径检测 / 边界情况 / 胜负判定）。"""
    checks = []

    def check(name, cond):
        checks.append((name, bool(cond)))
        print(("  [OK] " if cond else "  [X ] ") + name)

    print("=" * 60)
    print("核心规则自测")
    print("=" * 60)

    # ---- 路径检测 ----
    lv = Level([[4, 0, 2]])
    a = lv.arrows[(0, 0)]
    b = lv.blocker_of(a)
    check("路径检测：被同行的箭头挡住", b is not None and (b.row, b.col) == (0, 2))
    check("路径检测：被挡时 is_clear 为假", not lv.is_clear(a))

    lv = Level([[4, 0, 0]])
    check("路径检测：到边界全程为空则畅通", lv.is_clear(lv.arrows[(0, 0)]))

    lv = Level([[0, 0, 3]])
    check("路径检测：反方向有箭头不算阻挡", lv.is_clear(lv.arrows[(0, 2)]))

    lv = Level([[2], [0], [1]])
    down = lv.arrows[(0, 0)]
    check("路径检测：纵向扫描（跨越空格）",
          lv.blocker_of(down) is not None and
          lv.blocker_of(down).row == 2)

    lv = Level([[1]])
    check("边界情况：1x1 棋盘上的箭头畅通", lv.is_clear(lv.arrows[(0, 0)]))

    # ---- 互锁死局 ----
    lv = Level([[4, 0, 3]])
    check("互锁死局：(0,0)→与(0,2)← 互相阻挡",
          lv.blocker_of(lv.arrows[(0, 0)]) is not None and
          lv.blocker_of(lv.arrows[(0, 2)]) is not None)
    check("互锁死局：求解器应判定无解", solve_level([[4, 0, 3]]) is None)

    # ---- 关卡全部可解 ----
    for i, conf in enumerate(LEVELS, 1):
        check("第 %d 关「%s」可通关" % (i, conf["name"]),
              solve_level(conf["grid"]) is not None)

    # ---- 状态机：点击 → 消除 → 胜利 ----
    game = Game(headless=True)
    game.start_level(0)
    lv = game.level
    removed_first = False
    for _ in range(200):
        free = lv.free_arrows()
        if not free:
            break
        removed_first = game.click_arrow(free[0].row, free[0].col)
        break
    check("点击畅通箭头：返回 True 且箭头被标记消除",
          removed_first and game.level.remaining() == lv.total - 1)

    # 把整关点完，检查是否切到 WIN
    guard = 0
    while game.state == PLAYING and guard < 500:
        free = game.level.free_arrows()
        if free:
            game.click_arrow(free[0].row, free[0].col)
        game.update(1 / 60.0)
        guard += 1
    check("清空全部箭头后状态切换到 WIN", game.state == WIN)
    check("WIN 时剩余箭头为 0", game.level.remaining() == 0)

    # ---- 状态机：连撞 3 次 → 失败 ----
    game.start_level(1)
    blocked = [a for a in game.level.arrows.values()
               if not game.level.is_clear(a)]
    check("第 2 关存在会被撞击的箭头（用于测试）", len(blocked) > 0)
    target = blocked[0]
    for _ in range(3):
        game.click_arrow(target.row, target.col)
    check("连续撞击 3 次后失误机会归零", game.level.mistakes <= 0)
    check("撞击后错误箭头进入 COLLIDING 动画状态",
          target.state == "COLLIDING")
    for _ in range(120):
        game.update(1 / 60.0)
    check("动画播完后状态切换到 LOSE", game.state == LOSE)
    check("COLLIDING 动画结束后回到 IDLE", target.state == "IDLE")

    # ---- 重开 ----
    game.restart_level()
    check("重新开始后失误次数与箭头数量均恢复",
          game.level.mistakes == LEVELS[1]["mistakes"] and
          game.level.remaining() == game.level.total)

    # ---- 胜负边界：失误为 1 时撞一次即败 ----
    game.start_level(0)
    game.level.mistakes = 1
    b = [a for a in game.level.arrows.values() if not game.level.is_clear(a)]
    game.click_arrow(b[0].row, b[0].col)
    check("最后 1 次机会撞掉后触发失败倒计时", game.lose_timer is not None)

    pygame.quit()
    ok = sum(1 for _, c in checks if c)
    print("-" * 60)
    print("自测结果：%d / %d 项通过" % (ok, len(checks)))
    return 0 if ok == len(checks) else 1


def main():
    args = [a.lower() for a in sys.argv[1:]]
    if "--solve" in args:
        return cmd_solve()
    if "--test" in args:
        return cmd_test()
    if "--help" in args or "-h" in args:
        print(__doc__)
        return 0
    Game().run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
