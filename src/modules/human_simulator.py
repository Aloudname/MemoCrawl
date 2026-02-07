"""
human_simulator.py
高级人类行为模拟器，用于模拟自然的人类鼠标和键盘操作
"""

import pyautogui
import random
import time
import math
import numpy as np
from typing import Tuple, List, Optional, Union
from dataclasses import dataclass
from enum import Enum
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MouseButton(Enum):
    """鼠标按钮枚举"""
    LEFT = "left"
    RIGHT = "right"
    MIDDLE = "middle"

class ScrollDirection(Enum):
    """滚动方向枚举"""
    UP = "up"
    DOWN = "down"

@dataclass
class HumanDelayConfig:
    """人类延迟配置"""
    min_delay: float = 0.1
    max_delay: float = 0.5
    think_time_min: float = 0.2
    think_time_max: float = 1.0
    reaction_time_min: float = 0.1
    reaction_time_max: float = 0.3

@dataclass
class MouseMoveConfig:
    """鼠标移动配置"""
    speed_min: float = 0.3  # 最小速度（秒）
    speed_max: float = 0.8  # 最大速度（秒）
    curve_factor: float = 0.3  # 曲线因子，0为直线，1为最大弯曲
    jitter_factor: float = 0.05  # 抖动因子

class HumanSimulator:
    """
    高级人类行为模拟器
    提供高度仿真的鼠标和键盘操作，避免被检测为机器人
    """
    
    def __init__(self, 
                 screen_width: Optional[int] = None,
                 screen_height: Optional[int] = None,
                 human_delay: Optional[HumanDelayConfig] = None,
                 mouse_config: Optional[MouseMoveConfig] = None):
        """
        初始化模拟器
        
        Args:
            screen_width: 屏幕宽度，None则自动获取
            screen_height: 屏幕高度，None则自动获取
            human_delay: 人类延迟配置
            mouse_config: 鼠标移动配置
        """
        # 获取屏幕尺寸
        self.screen_width, self.screen_height = pyautogui.size()
        if screen_width and screen_height:
            self.screen_width = screen_width
            self.screen_height = screen_height
            
        # 配置
        self.human_delay = human_delay or HumanDelayConfig()
        self.mouse_config = mouse_config or MouseMoveConfig()
        
        # 设置pyautogui安全参数
        pyautogui.FAILSAFE = True  # 启用安全停止（鼠标移到左上角停止）
        pyautogui.PAUSE = 0  # 禁用pyautogui的默认暂停
        
        # 状态跟踪
        self.last_action_time = time.time()
        self.mouse_history = []  # 鼠标位置历史，用于行为分析
        self.action_counter = 0  # 动作计数器
        
        logger.info(f"HumanSimulator初始化完成，屏幕尺寸: {self.screen_width}x{self.screen_height}")
    
    def _get_random_delay(self, 
                         min_val: Optional[float] = None,
                         max_val: Optional[float] = None) -> float:
        """
        获取随机延迟时间，使用正态分布更接近人类行为
        
        Args:
            min_val: 最小延迟
            max_val: 最大延迟
            
        Returns:
            float: 延迟时间（秒）
        """
        if min_val is None:
            min_val = self.human_delay.min_delay
        if max_val is None:
            max_val = self.human_delay.max_delay
            
        # 使用截断正态分布，更接近人类行为
        mean = (min_val + max_val) / 2
        std = (max_val - min_val) / 6  # 99.7%的值在[min_val, max_val]内
        
        delay = np.random.normal(mean, std)
        delay = max(min_val, min(max_val, delay))  # 截断到[min_val, max_val]
        
        return delay
    
    def _human_delay(self, 
                    min_val: Optional[float] = None,
                    max_val: Optional[float] = None,
                    purpose: str = "thinking") -> None:
        """
        执行人类化的延迟
        
        Args:
            min_val: 最小延迟
            max_val: 最大延迟
            purpose: 延迟目的（thinking, reaction等）
        """
        if purpose == "thinking":
            min_val = min_val or self.human_delay.think_time_min
            max_val = max_val or self.human_delay.think_time_max
        elif purpose == "reaction":
            min_val = min_val or self.human_delay.reaction_time_min
            max_val = max_val or self.human_delay.reaction_time_max
        
        delay = self._get_random_delay(min_val, max_val)
        logger.debug(f"执行{purpose}延迟: {delay:.2f}秒")
        time.sleep(delay)
        
        # 更新最后动作时间
        self.last_action_time = time.time()
    
    def _generate_bezier_curve(self, 
                              start: Tuple[int, int], 
                              end: Tuple[int, int], 
                              control_points: int = 3) -> List[Tuple[int, int]]:
        """
        生成贝塞尔曲线路径
        
        Args:
            start: 起点坐标(x, y)
            end: 终点坐标(x, y)
            control_points: 控制点数量
            
        Returns:
            List[Tuple[int, int]]: 曲线路径点
        """
        # 生成控制点
        ctrl_pts = []
        for i in range(control_points):
            # 在起点和终点之间生成控制点
            t = (i + 1) / (control_points + 1)
            # 添加随机偏移
            offset_x = random.randint(-50, 50)
            offset_y = random.randint(-50, 50)
            x = int(start[0] + (end[0] - start[0]) * t + offset_x)
            y = int(start[1] + (end[1] - start[1]) * t + offset_y)
            ctrl_pts.append((x, y))
        
        # 生成贝塞尔曲线点
        curve_points = []
        num_points = 50  # 曲线上的点数
        
        for i in range(num_points):
            t = i / (num_points - 1)
            
            # 多重贝塞尔曲线插值
            points = [start] + ctrl_pts + [end]
            while len(points) > 1:
                new_points = []
                for j in range(len(points) - 1):
                    x = (1 - t) * points[j][0] + t * points[j + 1][0]
                    y = (1 - t) * points[j][1] + t * points[j + 1][1]
                    new_points.append((x, y))
                points = new_points
            
            curve_points.append((int(points[0][0]), int(points[0][1])))
        
        return curve_points
    
    def _add_jitter_to_path(self, 
                           path: List[Tuple[int, int]], 
                           jitter_factor: float) -> List[Tuple[int, int]]:
        """
        向路径添加微小抖动，模拟人类手部颤抖
        
        Args:
            path: 原始路径
            jitter_factor: 抖动因子
            
        Returns:
            List[Tuple[int, int]]: 添加抖动后的路径
        """
        jittered_path = []
        for x, y in path:
            jitter_x = random.randint(-int(jitter_factor * 10), int(jitter_factor * 10))
            jitter_y = random.randint(-int(jitter_factor * 10), int(jitter_factor * 10))
            jittered_path.append((x + jitter_x, y + jitter_y))
        
        return jittered_path
    
    def move_mouse_human(self, 
                        target_x: int, 
                        target_y: int,
                        speed: Optional[float] = None,
                        curve_factor: Optional[float] = None) -> None:
        """
        以人类化方式移动鼠标到目标位置
        
        Args:
            target_x: 目标x坐标
            target_y: 目标y坐标
            speed: 移动速度（秒），None则使用随机速度
            curve_factor: 曲线因子，None则使用配置值
        """
        # 获取当前鼠标位置
        current_x, current_y = pyautogui.position()
        
        # 检查是否需要移动
        if abs(current_x - target_x) < 2 and abs(current_y - target_y) < 2:
            logger.debug("鼠标已在目标位置附近，跳过移动")
            return
        
        # 添加反应延迟
        self._human_delay(purpose="reaction")
        
        # 生成移动路径
        start_pos = (current_x, current_y)
        end_pos = (target_x, target_y)
        
        # 随机决定是否使用曲线路径（70%概率使用曲线）
        use_curve = random.random() < 0.7
        
        if use_curve:
            curve_factor = curve_factor or self.mouse_config.curve_factor
            path = self._generate_bezier_curve(start_pos, end_pos, control_points=random.randint(2, 4))
            
            # 添加抖动
            path = self._add_jitter_to_path(path, self.mouse_config.jitter_factor)
        else:
            # 直线路径，但也添加一些点来模拟不均匀速度
            distance = math.sqrt((target_x - current_x)**2 + (target_y - current_y)**2)
            num_points = max(5, int(distance / 10))
            path = []
            
            for i in range(num_points + 1):
                t = i / num_points
                # 使用缓动函数使移动更自然
                t_eased = t * t * (3 - 2 * t)  # 平滑的缓动函数
                x = int(current_x + (target_x - current_x) * t_eased)
                y = int(current_y + (target_y - current_y) * t_eased)
                path.append((x, y))
        
        # 确定移动速度
        if speed is None:
            speed = random.uniform(self.mouse_config.speed_min, self.mouse_config.speed_max)
        
        # 计算每点之间的时间间隔
        total_time = speed
        interval = total_time / len(path) if path else total_time
        
        # 执行移动
        for i, (x, y) in enumerate(path):
            pyautogui.moveTo(x, y)
            
            # 非匀速移动，模拟人类行为
            if i < len(path) - 1:
                # 使用随机间隔，但确保总时间大致正确
                actual_interval = interval * random.uniform(0.8, 1.2)
                time.sleep(actual_interval)
        
        # 记录鼠标位置
        self.mouse_history.append((target_x, target_y, time.time()))
        if len(self.mouse_history) > 100:
            self.mouse_history.pop(0)
        
        # 增加动作计数
        self.action_counter += 1
        
        logger.debug(f"鼠标移动到 ({target_x}, {target_y})，使用{'曲线' if use_curve else '直线'}路径")
    
    def click_human(self, 
                   x: Optional[int] = None, 
                   y: Optional[int] = None,
                   button: MouseButton = MouseButton.LEFT,
                   double_click: bool = False,
                   offset: Tuple[int, int] = (0, 0)) -> None:
        """
        以人类化方式点击
        
        Args:
            x: x坐标，None则在当前位置点击
            y: y坐标，None则在当前位置点击
            button: 鼠标按钮
            double_click: 是否双击
            offset: 点击偏移量，模拟点击不精确
        """
        # 如果需要移动到指定位置
        if x is not None and y is not None:
            # 添加随机偏移，模拟点击不精确
            offset_x, offset_y = offset
            if offset_x == 0 and offset_y == 0:
                offset_x = random.randint(-3, 3)
                offset_y = random.randint(-3, 3)
            
            target_x = x + offset_x
            target_y = y + offset_y
            
            self.move_mouse_human(target_x, target_y)
        
        # 点击前的微小延迟，模拟人类反应
        self._human_delay(min_val=0.05, max_val=0.2, purpose="reaction")
        
        # 执行点击
        if double_click:
            # 双击，中间有微小间隔
            pyautogui.click(button=button.value)
            time.sleep(random.uniform(0.1, 0.3))
            pyautogui.click(button=button.value)
        else:
            # 单机
            pyautogui.click(button=button.value)
        
        # 点击后的微小停顿
        self._human_delay(min_val=0.1, max_val=0.3, purpose="thinking")
        
        logger.debug(f"在位置 ({x}, {y}) 执行{button.value}{'双击' if double_click else '单击'}")
    
    def type_human(self, 
                  text: str,
                  min_delay: float = 0.05,
                  max_delay: float = 0.3,
                  error_probability: float = 0.01,
                  error_correction_probability: float = 0.8) -> None:
        """
        以人类化方式输入文本
        
        Args:
            text: 要输入的文本
            min_delay: 字符间最小延迟
            max_delay: 字符间最大延迟
            error_probability: 输错概率
            error_correction_probability: 纠错概率（如果输错）
        """
        logger.debug(f"开始输入文本: '{text[:20]}...' 共{len(text)}字符")
        
        for i, char in enumerate(text):
            # 决定是否模拟输入错误
            make_error = random.random() < error_probability
            error_char = None
            
            if make_error:
                # 选择附近的键作为错误输入
                error_char = self._get_adjacent_key(char)
                if error_char:
                    logger.debug(f"模拟输入错误: '{char}' -> '{error_char}'")
                    pyautogui.press(error_char)
                    
                    # 决定是否纠正错误
                    if random.random() < error_correction_probability:
                        time.sleep(random.uniform(0.1, 0.5))
                        pyautogui.press('backspace')
                        time.sleep(random.uniform(0.1, 0.3))
            
            # 输入正确字符
            if not make_error or error_char is None:
                pyautogui.press(char)
            elif make_error and random.random() < error_correction_probability:
                # 已经纠正了错误，现在输入正确字符
                pyautogui.press(char)
            
            # 字符间延迟（使用正态分布）
            if i < len(text) - 1:  # 最后一个字符后不需要延迟
                delay = np.random.normal(
                    (min_delay + max_delay) / 2,
                    (max_delay - min_delay) / 6
                )
                delay = max(min_delay, min(max_delay, delay))
                time.sleep(delay)
            
            # 偶尔添加额外延迟，模拟思考
            if random.random() < 0.05:  # 5%的概率
                time.sleep(random.uniform(0.2, 0.8))
    
    def _get_adjacent_key(self, char: str) -> Optional[str]:
        """
        获取相邻键（用于模拟输入错误）
        
        Args:
            char: 字符
            
        Returns:
            Optional[str]: 相邻键字符，None表示没有找到
        """
        # 键盘布局（简化版）
        keyboard_layout = {
            'row1': ['`', '1', '2', '3', '4', '5', '6', '7', '8', '9', '0', '-', '='],
            'row2': ['q', 'w', 'e', 'r', 't', 'y', 'u', 'i', 'o', 'p', '[', ']', '\\'],
            'row3': ['a', 's', 'd', 'f', 'g', 'h', 'j', 'k', 'l', ';', "'"],
            'row4': ['z', 'x', 'c', 'v', 'b', 'n', 'm', ',', '.', '/']
        }
        
        char_lower = char.lower()
        
        # 查找字符所在位置
        for row, keys in keyboard_layout.items():
            if char_lower in keys:
                idx = keys.index(char_lower)
                # 随机选择相邻键
                offset = random.choice([-1, 1])
                new_idx = idx + offset
                if 0 <= new_idx < len(keys):
                    return keys[new_idx]
        
        return None
    
    def scroll_human(self, 
                    direction: ScrollDirection = ScrollDirection.DOWN,
                    clicks: int = 1,
                    x: Optional[int] = None,
                    y: Optional[int] = None) -> None:
        """
        以人类化方式滚动
        
        Args:
            direction: 滚动方向
            clicks: 滚动次数
            x: 滚动时鼠标x坐标
            y: 滚动时鼠标y坐标
        """
        # 如果指定了位置，先移动到该位置
        if x is not None and y is not None:
            self.move_mouse_human(x, y)
        
        # 执行滚动
        for i in range(clicks):
            # 随机决定滚动幅度
            scroll_amount = random.randint(-3, -1) if direction == ScrollDirection.DOWN else random.randint(1, 3)
            pyautogui.scroll(scroll_amount)
            
            # 滚动之间的延迟
            if i < clicks - 1:
                delay = random.uniform(0.2, 0.8)
                time.sleep(delay)
        
        logger.debug(f"执行{clicks}次{direction.value}滚动")
    
    def drag_human(self, 
                  start_x: int, 
                  start_y: int, 
                  end_x: int, 
                  end_y: int,
                  duration: Optional[float] = None) -> None:
        """
        以人类化方式拖拽
        
        Args:
            start_x: 起始x坐标
            start_y: 起始y坐标
            end_x: 结束x坐标
            end_y: 结束y坐标
            duration: 拖拽持续时间（秒）
        """
        # 移动到起始位置
        self.move_mouse_human(start_x, start_y)
        
        # 按下鼠标
        time.sleep(random.uniform(0.1, 0.3))
        pyautogui.mouseDown()
        
        # 拖拽到结束位置
        if duration is None:
            duration = random.uniform(0.5, 1.5)
        
        # 使用曲线路径拖拽
        path = self._generate_bezier_curve((start_x, start_y), (end_x, end_y))
        
        interval = duration / len(path) if path else duration
        for x, y in path:
            pyautogui.moveTo(x, y)
            time.sleep(interval * random.uniform(0.8, 1.2))
        
        # 释放鼠标
        time.sleep(random.uniform(0.1, 0.3))
        pyautogui.mouseUp()
        
        logger.debug(f"从 ({start_x}, {start_y}) 拖拽到 ({end_x}, {end_y})")
    
    def press_key_human(self, 
                       key: str,
                       presses: int = 1,
                       interval: Optional[float] = None) -> None:
        """
        以人类化方式按键盘键
        
        Args:
            key: 键名（如'enter', 'tab', 'esc'等）
            presses: 按多少次
            interval: 按键间隔（秒）
        """
        for i in range(presses):
            pyautogui.press(key)
            
            # 按键之间的延迟
            if i < presses - 1:
                if interval is None:
                    interval = random.uniform(0.1, 0.5)
                time.sleep(interval)
        
        logger.debug(f"按下键: {key} {presses}次")
    
    def hotkey_human(self, *keys: str) -> None:
        """
        以人类化方式按快捷键
        
        Args:
            *keys: 键序列（如'ctrl', 'c'）
        """
        # 按下所有修饰键
        for key in keys[:-1]:
            pyautogui.keyDown(key)
            time.sleep(random.uniform(0.05, 0.15))
        
        # 按下最后一个键
        pyautogui.press(keys[-1])
        time.sleep(random.uniform(0.05, 0.15))
        
        # 释放所有修饰键（逆序）
        for key in reversed(keys[:-1]):
            pyautogui.keyUp(key)
            time.sleep(random.uniform(0.05, 0.15))
        
        logger.debug(f"执行快捷键: {'+'.join(keys)}")
    
    def idle_behavior(self, 
                     min_duration: float = 2.0,
                     max_duration: float = 10.0) -> None:
        """
        模拟空闲行为（如鼠标微动、查看其他内容）
        
        Args:
            min_duration: 最小空闲时间
            max_duration: 最大空闲时间
        """
        duration = random.uniform(min_duration, max_duration)
        logger.debug(f"开始空闲行为，持续{duration:.1f}秒")
        
        start_time = time.time()
        while time.time() - start_time < duration:
            # 随机进行一些微小动作
            action = random.choice([
                self._micro_mouse_movement,
                self._look_around,
                self._scroll_randomly,
                self._switch_tabs
            ])
            action()
            
            # 动作间延迟
            time.sleep(random.uniform(0.5, 2.0))
    
    def _micro_mouse_movement(self) -> None:
        """微小鼠标移动"""
        current_x, current_y = pyautogui.position()
        offset_x = random.randint(-20, 20)
        offset_y = random.randint(-20, 20)
        self.move_mouse_human(current_x + offset_x, current_y + offset_y)
    
    def _look_around(self) -> None:
        """查看屏幕其他区域"""
        # 随机选择屏幕一个区域
        target_x = random.randint(100, self.screen_width - 100)
        target_y = random.randint(100, self.screen_height - 100)
        self.move_mouse_human(target_x, target_y)
        
        # 停留一会儿
        time.sleep(random.uniform(0.3, 1.0))
    
    def _scroll_randomly(self) -> None:
        """随机滚动"""
        direction = random.choice([ScrollDirection.UP, ScrollDirection.DOWN])
        clicks = random.randint(1, 3)
        self.scroll_human(direction, clicks)
    
    def _switch_tabs(self) -> None:
        """切换标签页（模拟Ctrl+Tab）"""
        self.hotkey_human('ctrl', 'tab')
        time.sleep(random.uniform(0.5, 1.5))
    
    def get_behavior_pattern(self) -> dict:
        """
        获取当前行为模式数据（可用于分析和优化）
        
        Returns:
            dict: 行为模式数据
        """
        if len(self.mouse_history) < 2:
            return {}
        
        # 计算移动速度模式
        speeds = []
        for i in range(1, len(self.mouse_history)):
            x1, y1, t1 = self.mouse_history[i-1]
            x2, y2, t2 = self.mouse_history[i]
            distance = math.sqrt((x2-x1)**2 + (y2-y1)**2)
            time_diff = t2 - t1
            if time_diff > 0:
                speeds.append(distance / time_diff)
        
        avg_speed = sum(speeds) / len(speeds) if speeds else 0
        
        return {
            'total_actions': self.action_counter,
            'mouse_history_length': len(self.mouse_history),
            'average_speed': avg_speed,
            'last_action_time': self.last_action_time
        }


# 快捷函数接口
def create_human_simulator(config: Optional[dict] = None) -> HumanSimulator:
    """
    创建人类模拟器实例
    
    Args:
        config: 配置字典
        
    Returns:
        HumanSimulator: 人类模拟器实例
    """
    if config is None:
        config = {}
    
    human_delay = HumanDelayConfig(
        min_delay=config.get('min_delay', 0.1),
        max_delay=config.get('max_delay', 0.5),
        think_time_min=config.get('think_time_min', 0.2),
        think_time_max=config.get('think_time_max', 1.0)
    )
    
    mouse_config = MouseMoveConfig(
        speed_min=config.get('speed_min', 0.3),
        speed_max=config.get('speed_max', 0.8),
        curve_factor=config.get('curve_factor', 0.3)
    )
    
    return HumanSimulator(
        human_delay=human_delay,
        mouse_config=mouse_config
    )


# 测试代码
if __name__ == "__main__":
    # 创建模拟器
    simulator = create_human_simulator()
    
    print("测试人类行为模拟器...")
    print("5秒后开始测试，请将鼠标移开避免干扰...")
    time.sleep(5)
    
    # 测试鼠标移动
    print("测试鼠标移动...")
    simulator.move_mouse_human(500, 300)
    
    # 测试点击
    print("测试点击...")
    simulator.click_human(600, 400)
    
    # 测试输入
    print("测试文本输入...")
    simulator.type_human("Hello, World!")
    
    # 测试滚动
    print("测试滚动...")
    simulator.scroll_human(ScrollDirection.DOWN, clicks=3)
    
    # 测试空闲行为
    print("测试空闲行为...")
    simulator.idle_behavior(min_duration=2, max_duration=3)
    
    print("测试完成！")
    print(f"行为模式: {simulator.get_behavior_pattern()}")