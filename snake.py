# -*- coding: utf-8 -*-
"""贪吃蛇小游戏（Snake）

只使用 Python 标准库 tkinter 实现，不需要安装任何第三方依赖。

运行：
    python snake.py

操作：
    方向键 / WASD .... 控制方向（按方向键可直接开始）
    空格 ............. 暂停 / 继续 / 重新开始
    R ................ 重新开始
    Esc .............. 退出
"""

import json
import os
import random
import tkinter as tk
import tkinter.font as tkfont
from collections import deque

# ---------------- 可调参数 ----------------
CELL = 26               # 每格像素
COLS = 20               # 横向格数
ROWS = 20               # 纵向格数

BASE_INTERVAL = 140     # 初始每走一步的间隔（毫秒），越小越快
MIN_INTERVAL = 60       # 最快速度上限
SPEED_STEP = 4          # 每吃一个食物加快的毫秒数

# ---------------- 配色 ----------------
COLOR_WINDOW = "#0d1117"
COLOR_TEXT = "#e6edf3"
COLOR_DIM = "#8b949e"
COLOR_SUB = "#c9d1d9"
COLOR_ACCENT = "#58a6ff"

BOARD_A = "#1b2230"
BOARD_B = "#212a3b"
BOARD_EDGE = "#30363d"

SNAKE_HEAD = "#7ee787"
SNAKE_BODY = "#3fb950"
SNAKE_OUTLINE = "#0d1117"

FOOD_BODY = "#ff7b72"
FOOD_SHINE = "#ffd7d3"
FOOD_LEAF = "#3fb950"

OVERLAY = "#010409"

SCORE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "highscore.json")

# ---------------- 方向 ----------------
UP = (0, -1)
DOWN = (0, 1)
LEFT = (-1, 0)
RIGHT = (1, 0)

KEY_DIRECTIONS = {
    "Up": UP, "w": UP, "W": UP,
    "Down": DOWN, "s": DOWN, "S": DOWN,
    "Left": LEFT, "a": LEFT, "A": LEFT,
    "Right": RIGHT, "d": RIGHT, "D": RIGHT,
}


class SnakeGame(object):
    """贪吃蛇主逻辑：状态机 + Canvas 绘制。"""

    def __init__(self, root):
        self.root = root
        self.width = COLS * CELL
        self.height = ROWS * CELL

        self.high_score = self.load_high_score()
        self.over_reason = ""

        # 状态：ready（准备）/ running（进行中）/ paused（暂停）/ over（结束）
        self.state = "ready"
        self.score = 0
        self.interval = BASE_INTERVAL
        self.after_id = None

        self.snake = deque()
        self.direction = RIGHT
        self.pending = deque()
        self.food = None

        self._setup_window()
        self._setup_fonts()
        self._build_ui()
        self._draw_board()

        self.reset()

        root.bind("<Key>", self.on_key)
        root.protocol("WM_DELETE_WINDOW", self.on_close)

    # ------------------------------------------------------------------ 界面

    def _setup_window(self):
        self.root.title("贪吃蛇 · Snake")
        self.root.configure(bg=COLOR_WINDOW)
        self.root.resizable(False, False)

    def _setup_fonts(self):
        family = "Microsoft YaHei UI"
        try:
            families = set(tkfont.families(self.root))
            if family not in families:
                family = "Microsoft YaHei"
            if family not in families:
                family = tkfont.nametofont("TkDefaultFont").actual("family")
        except Exception:
            family = "TkDefaultFont"

        self.font_title = (family, 30, "bold")
        self.font_subtitle = (family, 12)
        self.font_label = (family, 11, "bold")
        self.font_hint = (family, 9)

    def _build_ui(self):
        bar = tk.Frame(self.root, bg=COLOR_WINDOW)
        bar.pack(fill="x", padx=16, pady=(12, 8))

        self.score_var = tk.StringVar()
        self.high_var = tk.StringVar()
        self.speed_var = tk.StringVar()

        tk.Label(bar, textvariable=self.score_var, font=self.font_label,
                 fg=COLOR_TEXT, bg=COLOR_WINDOW).pack(side="left")
        tk.Label(bar, textvariable=self.speed_var, font=self.font_hint,
                 fg=COLOR_ACCENT, bg=COLOR_WINDOW).pack(side="left", padx=(14, 0))
        tk.Label(bar, textvariable=self.high_var, font=self.font_label,
                 fg=COLOR_DIM, bg=COLOR_WINDOW).pack(side="right")

        self.canvas = tk.Canvas(self.root, width=self.width, height=self.height,
                                bg=BOARD_A, highlightthickness=0, bd=0)
        self.canvas.pack(padx=16)

        tk.Label(self.root,
                 text="方向键 / WASD 移动      空格 暂停       R 重开       Esc 退出",
                 font=self.font_hint, fg=COLOR_DIM, bg=COLOR_WINDOW
                 ).pack(pady=(8, 12))

    def _draw_board(self):
        """棋盘背景只画一次，之后每帧只重画会动的东西。"""
        self.canvas.delete("all")
        for y in range(ROWS):
            for x in range(COLS):
                color = BOARD_A if (x + y) % 2 == 0 else BOARD_B
                self.canvas.create_rectangle(
                    x * CELL, y * CELL, (x + 1) * CELL, (y + 1) * CELL,
                    fill=color, outline="", tags="board")
        self.canvas.create_rectangle(1, 1, self.width - 1, self.height - 1,
                                     outline=BOARD_EDGE, width=2, tags="board")

    # ------------------------------------------------------------------ 逻辑

    def reset(self):
        self.cancel_timer()
        mid_x = COLS // 2
        mid_y = ROWS // 2
        self.snake = deque([
            (mid_x, mid_y),
            (mid_x - 1, mid_y),
            (mid_x - 2, mid_y),
        ])
        self.direction = RIGHT
        self.pending = deque()
        self.score = 0
        self.interval = BASE_INTERVAL
        self.state = "ready"
        self.over_reason = ""
        self.food = self.spawn_food()
        self.update_labels()
        self.render()

    def start(self):
        if self.state == "ready":
            self.state = "running"
            self.render()
            self.schedule()

    def tick(self):
        self.after_id = None
        if self.state != "running":
            return

        if self.pending:
            self.direction = self.pending.popleft()

        head_x, head_y = self.snake[0]
        dx, dy = self.direction
        new_head = (head_x + dx, head_y + dy)

        # 撞墙
        if not (0 <= new_head[0] < COLS and 0 <= new_head[1] < ROWS):
            self.game_over("撞到墙了")
            return

        eating = (new_head == self.food)

        # 撞自己：如果这一帧不吃东西，尾巴会让开，所以不算撞
        blocked = set(self.snake)
        if not eating:
            blocked.discard(self.snake[-1])
        if new_head in blocked:
            self.game_over("咬到自己了")
            return

        self.snake.appendleft(new_head)
        if eating:
            self.score += 1
            self.interval = max(MIN_INTERVAL, BASE_INTERVAL - self.score * SPEED_STEP)
            self.update_labels()
            self.food = self.spawn_food()
            if self.food is None:          # 整屏都填满了
                self.game_over("太强了，整个屏幕都填满！")
                return
        else:
            self.snake.pop()

        self.render()
        self.schedule()

    def spawn_food(self):
        occupied = set(self.snake)
        free = [(x, y)
                for y in range(ROWS)
                for x in range(COLS)
                if (x, y) not in occupied]
        if not free:
            return None
        return random.choice(free)

    def game_over(self, reason):
        self.state = "over"
        self.over_reason = reason
        self.cancel_timer()
        if self.score > self.high_score:
            self.high_score = self.score
            self.save_high_score()
        self.update_labels()
        self.render()

    def toggle_pause(self):
        if self.state == "ready":
            self.start()
        elif self.state == "running":
            self.state = "paused"
            self.cancel_timer()
            self.render()
        elif self.state == "paused":
            self.state = "running"
            self.render()
            self.schedule()
        else:                              # 结束后按空格直接重开
            self.reset()
            self.start()

    # ------------------------------------------------------------------ 计时

    def schedule(self):
        self.cancel_timer()
        self.after_id = self.root.after(self.interval, self.tick)

    def cancel_timer(self):
        if self.after_id is not None:
            try:
                self.root.after_cancel(self.after_id)
            except Exception:
                pass
            self.after_id = None

    # ------------------------------------------------------------------ 输入

    def on_key(self, event):
        key = event.keysym
        if key == "Escape":
            self.on_close()
        elif key in ("r", "R"):
            self.reset()
        elif key in ("space", "Return", "KP_Enter"):
            self.toggle_pause()
        elif key in KEY_DIRECTIONS:
            self.queue_direction(KEY_DIRECTIONS[key])

    def queue_direction(self, direction):
        if self.state == "ready":
            self.start()                   # 直接按方向键也能开局
        if self.state != "running":
            return

        last = self.pending[-1] if self.pending else self.direction
        if direction == last:                                       # 同一个方向，忽略
            return
        if direction == (-last[0], -last[1]):                       # 不能 180° 掉头
            return
        if len(self.pending) >= 2:                                  # 最多缓存两个转向
            return
        self.pending.append(direction)

    def on_close(self):
        self.cancel_timer()
        self.save_high_score()
        self.root.destroy()

    # ------------------------------------------------------------------ 存档

    def load_high_score(self):
        try:
            with open(SCORE_FILE, "r", encoding="utf-8") as fp:
                return int(json.load(fp).get("high_score", 0))
        except Exception:
            return 0

    def save_high_score(self):
        try:
            with open(SCORE_FILE, "w", encoding="utf-8") as fp:
                json.dump({"high_score": int(self.high_score)}, fp)
        except Exception:
            pass                           # 目录不可写也不影响游戏

    # ------------------------------------------------------------------ 绘制

    def update_labels(self):
        level = 1 + int(round((BASE_INTERVAL - self.interval) / float(SPEED_STEP)))
        self.score_var.set("得分  %d" % self.score)
        self.high_var.set("最高  %d" % self.high_score)
        self.speed_var.set("速度 x%d" % level)

    def render(self):
        self.canvas.delete("dyn")
        if self.food is not None:
            self.draw_food(*self.food)
        self.draw_snake()
        if self.state != "running":
            self.draw_overlay()

    def draw_snake(self):
        segments = list(self.snake)
        total = len(segments)
        # 从尾巴画到头，头自然压在最上层
        for index in range(total - 1, -1, -1):
            gx, gy = segments[index]
            self.draw_segment(gx, gy,
                              is_head=(index == 0),
                              is_tail=(index == total - 1))

    def draw_segment(self, gx, gy, is_head, is_tail):
        if is_head:
            pad = 1.5
        elif is_tail:
            pad = 5.0
        else:
            pad = 3.0

        x0 = gx * CELL + pad
        y0 = gy * CELL + pad
        x1 = (gx + 1) * CELL - pad
        y1 = (gy + 1) * CELL - pad

        self.canvas.create_rectangle(
            x0, y0, x1, y1,
            fill=SNAKE_HEAD if is_head else SNAKE_BODY,
            outline=SNAKE_OUTLINE, width=1, tags="dyn")

        if is_head:
            self.draw_eyes(x0, y0, x1, y1)

    def draw_eyes(self, x0, y0, x1, y1):
        dx, dy = self.direction
        cx = (x0 + x1) / 2.0
        cy = (y0 + y1) / 2.0

        if dx > 0:
            spots = [(x1 - 5, cy - 4), (x1 - 5, cy + 4)]
        elif dx < 0:
            spots = [(x0 + 5, cy - 4), (x0 + 5, cy + 4)]
        elif dy < 0:
            spots = [(cx - 4, y0 + 5), (cx + 4, y0 + 5)]
        else:
            spots = [(cx - 4, y1 - 5), (cx + 4, y1 - 5)]

        for px, py in spots:
            self.canvas.create_oval(px - 2.4, py - 2.4, px + 2.4, py + 2.4,
                                    fill=SNAKE_OUTLINE, outline="", tags="dyn")

    def draw_food(self, gx, gy):
        cx = gx * CELL + CELL / 2.0
        cy = gy * CELL + CELL / 2.0
        r = CELL / 2.0 - 4.5

        self.canvas.create_oval(cx - r, cy - r, cx + r, cy + r,
                                fill=FOOD_BODY, outline="#b3261e", width=1,
                                tags="dyn")
        self.canvas.create_oval(cx - r * 0.55, cy - r * 0.6,
                                cx - r * 0.1, cy - r * 0.15,
                                fill=FOOD_SHINE, outline="", tags="dyn")
        self.canvas.create_line(cx + 1, cy - r, cx + 5, cy - r - 4,
                                fill=FOOD_LEAF, width=2, capstyle="round",
                                tags="dyn")

    def draw_overlay(self):
        self.canvas.create_rectangle(0, 0, self.width, self.height,
                                     fill=OVERLAY, stipple="gray75",
                                     outline="", tags="dyn")

        if self.state == "ready":
            title = "贪吃蛇"
            lines = ["方向键 / WASD 控制方向", "按 空格 或 方向键 开始"]
        elif self.state == "paused":
            title = "已暂停"
            lines = ["", "按 空格 继续"]
        else:
            title = "游戏结束"
            lines = [self.over_reason, "本局得分 %d · 按 空格 重开" % self.score]

        # 结束后给文字加一块底板，暂停和开局则让画面透出来
        if self.state == "over":
            panel_w = self.width * 0.78
            panel_h = 170.0
            x0 = (self.width - panel_w) / 2.0
            y0 = (self.height - panel_h) / 2.0
            self.canvas.create_rectangle(x0, y0, x0 + panel_w, y0 + panel_h,
                                         fill="#0d1117", outline=BOARD_EDGE,
                                         width=2, tags="dyn")
            center_y = self.height / 2.0
        else:
            center_y = self.height * 0.32

        self.canvas.create_text(self.width / 2.0, center_y - 36,
                                text=title, fill=COLOR_TEXT, font=self.font_title,
                                tags="dyn")

        text_y = center_y + 20
        for index, line in enumerate(lines):
            if line:
                self.canvas.create_text(
                    self.width / 2.0, text_y, text=line,
                    fill=COLOR_SUB if index == 0 else COLOR_DIM,
                    font=self.font_subtitle, tags="dyn")
            text_y += 30


def enable_high_dpi():
    """Windows 高分屏下让界面更清晰（失败了也不影响运行）。"""
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass


def center_window(window):
    window.update_idletasks()
    w = window.winfo_reqwidth()
    h = window.winfo_reqheight()
    x = max(0, (window.winfo_screenwidth() - w) // 2)
    y = max(0, (window.winfo_screenheight() - h) // 3)
    window.geometry("+%d+%d" % (x, y))


def main():
    enable_high_dpi()
    root = tk.Tk()
    SnakeGame(root)
    center_window(root)
    root.mainloop()


if __name__ == "__main__":
    main()
