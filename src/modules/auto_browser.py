"""
login_automator.py
自动化登录模块，模拟人类登录行为
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, Tuple

from src.modules.browser_controller import BrowserController
from src.modules.human_simulator import (HumanSimulator, MouseButton,
                                         ScrollDirection)

logger = logging.getLogger(__name__)

@dataclass
class AbstractStep(ABC):
    """
    抽象步骤类, 定义了步骤的接口.
    """
    step: Optional[str] = field(init=True, repr=True)
    kwargs: Dict[str, Any] = field(default_factory=dict, init=True, repr=False)
    _simulator: Optional[HumanSimulator] = None
    
    @classmethod
    def set_simulator(cls, simulator: HumanSimulator):
        cls._simulator = simulator
        
    @property
    def simulator(self) -> 'HumanSimulator':
        """获取模拟器实例"""
        if self._simulator is None:
            raise ValueError("未设置 HumanSimulator 实例，请先调用 set_simulator")
        return self._simulator
    
    @property
    @abstractmethod
    def action_name(self) -> str:
        """获取动作名称"""
        pass
    
    @abstractmethod
    def get_action_args(self) -> Dict[str, Any]:
        """返回调用方法的参数"""
        pass
    
    def __call__(self) -> bool:
        """执行步骤"""
        action = getattr(self.simulator, self.action_name)
        args = self.get_action_args()
        return action(**args, **self.kwargs)
    
@dataclass
class MoveStep(AbstractStep):
    x: Optional[int] = None
    y: Optional[int] = None
    terminate: Optional[Tuple[int, int]] = None
    
    @property
    def action_name(self) -> str:
        return "move"
    
    def __post_init__(self):
        """初始化后处理，设置坐标"""
        if self.terminate is not None:
            self.x, self.y = self.terminate
        elif self.x is None or self.y is None:
            raise ValueError("必须提供 x,y 或 terminate 参数")
    
    def get_action_args(self) -> Dict[str, Any]:
        return {"x": self.x, "y": self.y}
    
@dataclass
class ClickStep(AbstractStep):
    x: Optional[int] = None
    y: Optional[int] = None
    button: MouseButton = MouseButton.LEFT
    terminate: Optional[Tuple[int, int]] = None
    double_click: bool = False
    
    @property
    def action_name(self) -> str:
        return "click"
    
    def __post_init__(self):
        """初始化后处理"""
        if self.terminate is not None:
            self.x, self.y = self.terminate
        elif self.x is None or self.y is None:
            self.x, self.y = HumanSimulator._get_position()
    
    def get_action_args(self) -> Dict[str, Any]:
        return {
            "x": self.x, 
            "y": self.y,
            "button": self.button,
            "double_click": self.double_click}

@dataclass    
class TypeStep(AbstractStep):
    text: Optional[str] = None
    
    @property
    def action_name(self) -> str:
        return "type_in"
    
    def get_action_args(self) -> Dict[str, Any]:
        return {"text": self.text}

@dataclass
class ScrollStep(AbstractStep):
    clicks: int = 1
    x: Optional[int] = None
    y: Optional[int] = None
    coor_0: Optional[Tuple[int, int]] = None
    direction: ScrollDirection = ScrollDirection.DOWN

    @property
    def action_name(self) -> str:
        return "scroll"
    
    def __post_init__(self):
        if self.coor_0 is not None:
            self.x, self.y = self.coor_0
        elif self.x is None or self.y is None:
            raise ValueError("必须提供 x,y 或 coor_0 参数")
    
    def get_action_args(self) -> Dict[str, Any]:
        return {
            "x": self.x,
            "y": self.y,
            "direction": self.direction,
            "clicks": self.clicks
        }
    
@dataclass
class DragStep(AbstractStep):
    start_x: Optional[int] = None
    start_y: Optional[int] = None
    end_x: Optional[int] = None
    end_y: Optional[int] = None
    duration: float = 0.5
    start: Optional[Tuple[int, int]] = None
    terminate: Optional[Tuple[int, int]] = None
    
    @property
    def action_name(self) -> str:
        return "drag"
    
    def __post_init__(self):
        """初始化后处理"""
        if self.start is not None:
            self.start_x, self.start_y = self.start
        if self.terminate is not None:
            self.end_x, self.end_y = self.terminate
        
        if self.start_x is None or self.start_y is None:
            raise ValueError("必须提供 start_x,start_y 或 start 参数")
        if self.end_x is None or self.end_y is None:
            raise ValueError("必须提供 end_x,end_y 或 terminate 参数")
    
    def get_action_args(self) -> Dict[str, Any]:
        return {
            "start_x": self.start_x,
            "start_y": self.start_y,
            "end_x": self.end_x,
            "end_y": self.end_y,
            "duration": self.duration
        }
    
@dataclass
class PressKeyStep(AbstractStep):
    key: Optional[str] = None
    presses: int = 1
    interval: Optional[float] = None
    
    @property
    def action_name(self) -> str:
        return "press_key"
    
    def get_action_args(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "presses": self.presses,
            "interval": self.interval
        }
        
@dataclass
class HotkeyStep(AbstractStep):
    keys: List[str] = field(default_factory=list)
    
    @property
    def action_name(self) -> str:
        return "hotkey"
    
    def get_action_args(self) -> List[str]:
        return self.keys
    
    def __call__(self) -> bool:
        """执行步骤"""
        action = getattr(self.simulator, self.action_name)
        args = self.get_action_args()
        return action(*args)

@dataclass
class ToCenterStep(AbstractStep):
    @property
    def action_name(self) -> str:
        return "to_center"
    
    def get_action_args(self) -> Dict[str, Any]:
        return {}
    
@dataclass
class DelayStep(AbstractStep):
    min_val: float = 0.1
    max_val: float = 5.0
    delay: float = None
    purpose: str = 'custom'
    
    @property
    def action_name(self) -> str:
        return "delay"
    
    def __post_init__(self):
        """初始化后处理"""
        if self.delay is None:
            if self.min_val and (self.max_val is None):
                self.max_val = self.min_val + 1
            
            if self.max_val and (self.min_val is None):
                self.min_val = self.max_val - 1
            if self.min_val is None and self.max_val is None:
                raise ValueError("必须提供 min_val,max_val 参数")
        elif self.delay is not None:
            self.min_val = self.delay
            self.max_val = self.delay

    def get_action_args(self) -> Dict[str, Any]:
        return {"min_val": self.min_val, "max_val": self.max_val, "purpose": self.purpose}
    


class StepQueue:
    """步骤队列"""
    def __init__(self, simulator: HumanSimulator = None):
        self.steps: List[AbstractStep] = []
        AbstractStep.set_simulator(simulator)
        
    def __call__(self) -> bool:
        for i, step in enumerate(self.steps, 1):
            print(f"\n执行步骤 {i}: {step.step}")
            try:
                step()
            except Exception as e:
                print(f"步骤 {i} 执行出错: {e}")
                return False
        return True
        
    def append(self, step: AbstractStep):
        self.steps.append(step)
        step._simulator = AbstractStep._simulator
    
    def clear(self):
        self.steps.clear()
    
    def enqueue(self, *steps: AbstractStep):
        self.steps.extend(steps)
        for step in steps:
            step._simulator = AbstractStep._simulator
        
    def dequeue(self) -> AbstractStep:
        if not self.steps:
            raise IndexError("步骤队列为空")
        return self.steps.pop(0)
    
    def __len__(self) -> int:
        return len(self.steps)
    
    def __repr__(self) -> str:
        return f"StepQueue({len(self)} steps)"
        
class AutoBrowser:
    """
    自动化登录器
    模拟人类登录行为，支持高度自定义
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        初始化登录自动化器
        """
        
        self.config = config
        self.BrCt = BrowserController(self.config)
        self.simu = self.BrCt.simulator
        self.Queue = StepQueue(self.simu)
    
    def _enqueue(self) -> bool:
        try:
            self.Queue.enqueue(
                MoveStep(step='Move to search box',
                        terminate=self.config.browser.coord.search_box),
                DelayStep(step='Waiting 5s',
                        min_val=5, max_val=6),
                ClickStep(step='Click LEFT',
                        terminate=self.config.browser.coord.search_box),
                DelayStep(step='Waiting 2s',
                        min_val=2, max_val=3),
                HotkeyStep(step='Ctrl+A',
                        keys=['ctrl','a']),
                # TypeStep(step='笔记本电脑内存 DDR5 32G',
                #         text=self.config.browser.search.keyword),
                HotkeyStep(step='Ctrl+V',
                        keys=['ctrl','v']),
                PressKeyStep(step='Enter',
                        key='enter'),
                
                DelayStep(step='Waiting 10s',
                        min_val=10, max_val=11),
                MoveStep(step='Move to plug-bar',
                        terminate=self.config.browser.coord.plug_in),
                DelayStep(step='Waiting 2s',
                        min_val=2, max_val=3),
                ClickStep(step='Click plug-in button',
                        terminate=self.config.browser.coord.plug_in),
                
                DelayStep(step='Waiting 2s',
                        min_val=2, max_val=3),
                MoveStep(step='Move to crawl button',
                        terminate=self.config.browser.coord.export),
                DelayStep(step='Waiting 2s',
                        min_val=2, max_val=3),
                ClickStep(step='Click crawl button'),
                
                DelayStep(step='Waiting 5s',
                        min_val=5, max_val=6),
                MoveStep(step='Move to plug-out button',
                        terminate=self.config.browser.coord.plug_out),
                DelayStep(step='Waiting 2s',
                        min_val=2, max_val=3),
                ClickStep(step='Click plug-out button',
                        terminate=self.config.browser.coord.plug_out),
                ToCenterStep(step='Move to center'),
        )
            logger.info(f"{len(self.Queue)} 个步骤队列已加载至队列!")
            return True
        except Exception as e:
            logger.error(f"加载步骤队列失败: {e}")
            return False
    
    def envisit(self) -> bool:
        """
        执行访问流程, 包括:
        启动浏览器进程, 导航到目标URL, 网页中执行访问步骤序列, 检查访问状态.
        Returns:
            bool: 访问是否成功
        """
        logger.info("开始访问流程...")
        try:    # 重置状态
            self.is_logged_in = False
            self.last_error = None
            
            # 开启浏览器进程
            logger.info(f"搜索关键词：{self.config.browser.search.keyword}")
            self.BrCt.open_browser()
            self.BrCt.to_url()
            
            self._enqueue()
            self.Queue()
            return True
        except Exception as e:
            logger.error(f"访问流程失败: {e}")
            return False

    
    def devisit(self) -> bool:
        """
        关闭网页，终止浏览器进程
        
        Returns:
            bool: 是否成功
        """
        try:
            logger.info("浏览器进程开始注销...")
            self.Queue.clear()
            self.BrCt.browser_process.terminate()
            logger.info("浏览器进程注销成功")
            return True
            
        except Exception as e:
            logger.error(f"注销失败: {e}")
            return False
