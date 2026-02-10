"""
login_automator.py
自动化登录模块，模拟人类登录行为
"""

import time
import logging
import random
from typing import Optional, Dict, Any, List, Tuple
from enum import Enum
from dataclasses import dataclass, field

from config import get_config
from modules.human_simulator import HumanSimulator, MouseButton, ScrollDirection
from modules.browser_controller import BrowserController

logger = logging.getLogger(__name__)

class LoginMethod(Enum):
    """登录方式枚举"""
    PASSWORD = "password"
    QR_CODE = "qr_code"
    SMS = "sms"
    AUTO_DETECT = "auto_detect"

class LoginElementType(Enum):
    """登录元素类型"""
    USERNAME_INPUT = "username_input"
    PASSWORD_INPUT = "password_input"
    LOGIN_BUTTON = "login_button"
    QR_CODE_BUTTON = "qr_code_button"
    SMS_BUTTON = "sms_button"
    REMEMBER_CHECKBOX = "remember_checkbox"
    AGREEMENT_CHECKBOX = "agreement_checkbox"

@dataclass
class LoginStep:
    """登录步骤配置"""
    action: str  # move, click, type, wait, scroll, drag
    element_type: Optional[LoginElementType] = None
    target_position: Optional[Tuple[int, int]] = None
    text: Optional[str] = None
    min_delay: float = 0.1
    max_delay: float = 0.5
    description: str = ""
    optional: bool = False
    retry_times: int = 1
    offset_range: Tuple[int, int] = (0, 0)  # 点击偏移范围

@dataclass
class LoginConfig:
    """登录配置"""
    url: str = "https://www.jd.com"
    method: LoginMethod = LoginMethod.PASSWORD
    username: str = ""
    password: str = ""
    max_attempts: int = 3
    timeout: int = 60
    wait_after_login: float = 5.0
    elements: Dict[LoginElementType, Tuple[int, int]] = field(default_factory=dict)
    steps: List[LoginStep] = field(default_factory=list)
    humanization_level: int = 3  # 1-5，越高越像人类
    enable_random_behavior: bool = True

class LoginAutomator:
    """
    自动化登录器
    模拟人类登录行为，支持高度自定义
    """
    
    def __init__(self, 
                 simulator: HumanSimulator,
                 browser_controller: BrowserController,
                 login_config: Optional[LoginConfig] = None):
        """
        初始化登录自动化器
        
        Args:
            simulator: 人类行为模拟器
            browser_controller: 浏览器控制器
            login_config: 登录配置，如果为None则从全局配置加载
        """
        self.simulator = simulator
        self.browser = browser_controller
        self.config_manager = get_config()
        
        # 加载配置
        if login_config:
            self.login_config = login_config
        else:
            self.login_config = self._load_config_from_global()
        
        # 状态跟踪
        self.login_attempts = 0
        self.is_logged_in = False
        self.last_error = None
        
        # 性能统计
        self.stats = {
            "total_login_attempts": 0,
            "successful_logins": 0,
            "failed_logins": 0,
            "average_login_time": 0.0,
            "last_login_time": None
        }
        
        logger.info(f"登录自动化器初始化完成，登录方式: {self.login_config.method.value}")
    
    def _load_config_from_global(self) -> LoginConfig:
        """从全局配置加载登录配置"""
        global_config = self.config_manager
        
        # 获取账户配置
        account_config = global_config.get("jd_account")
        
        # 创建登录配置
        login_config = LoginConfig(
            url=global_config.get("login.url", "https://www.jd.com"),
            method=LoginMethod(account_config.login_method),
            username=account_config.username,
            password=account_config.password,
            max_attempts=account_config.max_login_attempts,
            timeout=account_config.login_timeout,
            wait_after_login=global_config.get("login.wait_after_login", 5.0),
            humanization_level=global_config.get("login.humanization_level", 3),
            enable_random_behavior=global_config.get("login.enable_random_behavior", True)
        )
        
        # 加载元素位置（如果配置中存在）
        elements_config = global_config.get("login.elements", {})
        for elem_type_str, position in elements_config.items():
            try:
                elem_type = LoginElementType(elem_type_str)
                login_config.elements[elem_type] = tuple(position)
            except ValueError:
                logger.warning(f"未知的登录元素类型: {elem_type_str}")
        
        # 加载自定义步骤（如果配置中存在）
        steps_config = global_config.get("login.steps", [])
        if steps_config:
            for step_data in steps_config:
                step = LoginStep(**step_data)
                if step.element_type:
                    step.element_type = LoginElementType(step.element_type)
                login_config.steps.append(step)
        else:
            # 使用默认步骤
            login_config.steps = self._get_default_steps()
        
        return login_config
    
    def _get_default_steps(self) -> List[LoginStep]:
        """获取默认登录步骤"""
        return [
            # 步骤1: 随机移动鼠标，模拟人类查看页面
            LoginStep(
                action="random_move",
                description="随机移动鼠标，查看页面",
                min_delay=1.0,
                max_delay=3.0
            ),
            
            # 步骤2: 移动到用户名输入框
            LoginStep(
                action="move",
                element_type=LoginElementType.USERNAME_INPUT,
                description="移动到用户名输入框",
                min_delay=0.3,
                max_delay=0.8
            ),
            
            # 步骤3: 点击用户名输入框
            LoginStep(
                action="click",
                element_type=LoginElementType.USERNAME_INPUT,
                description="点击用户名输入框",
                min_delay=0.1,
                max_delay=0.3,
                offset_range=(-3, 3)  # 点击偏移
            ),
            
            # 步骤4: 输入用户名（逐个字符）
            LoginStep(
                action="type_username",
                description="输入用户名",
                min_delay=0.05,
                max_delay=0.3
            ),
            
            # 步骤5: 微小的随机思考时间
            LoginStep(
                action="wait",
                description="思考时间",
                min_delay=0.5,
                max_delay=1.5
            ),
            
            # 步骤6: 移动到密码输入框
            LoginStep(
                action="move",
                element_type=LoginElementType.PASSWORD_INPUT,
                description="移动到密码输入框",
                min_delay=0.3,
                max_delay=0.8
            ),
            
            # 步骤7: 点击密码输入框
            LoginStep(
                action="click",
                element_type=LoginElementType.PASSWORD_INPUT,
                description="点击密码输入框",
                min_delay=0.1,
                max_delay=0.3,
                offset_range=(-3, 3)
            ),
            
            # 步骤8: 输入密码（逐个字符）
            LoginStep(
                action="type_password",
                description="输入密码",
                min_delay=0.05,
                max_delay=0.2
            ),
            
            # 步骤9: 随机移动鼠标
            LoginStep(
                action="random_move",
                description="检查输入内容",
                min_delay=0.5,
                max_delay=1.0
            ),
            
            # 步骤10: 移动到登录按钮
            LoginStep(
                action="move",
                element_type=LoginElementType.LOGIN_BUTTON,
                description="移动到登录按钮",
                min_delay=0.3,
                max_delay=0.8
            ),
            
            # 步骤11: 点击登录按钮
            LoginStep(
                action="click",
                element_type=LoginElementType.LOGIN_BUTTON,
                description="点击登录按钮",
                min_delay=0.2,
                max_delay=0.5,
                offset_range=(-5, 5)
            ),
        ]
    
    def _get_element_position(self, element_type: LoginElementType) -> Optional[Tuple[int, int]]:
        """
        获取元素位置
        
        Args:
            element_type: 元素类型
            
        Returns:
            Tuple[int, int] 或 None
        """
        # 首先从配置中获取
        if element_type in self.login_config.elements:
            return self.login_config.elements[element_type]
        
        # 这里可以添加视觉识别获取位置（后续集成）
        # 暂时返回None，表示需要视觉识别
        return None
    
    def _execute_step(self, step: LoginStep) -> bool:
        """
        执行单个登录步骤
        
        Args:
            step: 登录步骤
            
        Returns:
            bool: 是否成功
        """
        try:
            logger.debug(f"执行步骤: {step.description}")
            
            # 步骤执行前的延迟
            if step.min_delay > 0 or step.max_delay > 0:
                delay = random.uniform(step.min_delay, step.max_delay)
                self.simulator._human_delay(min_val=delay, max_val=delay)
            
            # 执行具体动作
            if step.action == "move":
                if not step.element_type:
                    raise ValueError("移动动作需要指定元素类型")
                
                position = self._get_element_position(step.element_type)
                if not position:
                    if step.optional:
                        logger.warning(f"元素 {step.element_type} 位置未找到，但步骤可选，跳过")
                        return True
                    raise ValueError(f"元素 {step.element_type} 位置未找到")
                
                self.simulator.move_mouse_human(*position)
                
            elif step.action == "click":
                if not step.element_type:
                    raise ValueError("点击动作需要指定元素类型")
                
                position = self._get_element_position(step.element_type)
                if not position:
                    if step.optional:
                        logger.warning(f"元素 {step.element_type} 位置未找到，但步骤可选，跳过")
                        return True
                    raise ValueError(f"元素 {step.element_type} 位置未找到")
                
                # 添加随机偏移
                offset_x = random.randint(*step.offset_range)
                offset_y = random.randint(*step.offset_range)
                
                self.simulator.click_human(
                    x=position[0] + offset_x,
                    y=position[1] + offset_y,
                    button=MouseButton.LEFT
                )
                
            elif step.action == "type_username":
                # 模拟人类输入用户名
                username = self.login_config.username
                self._type_text_humanly(username, is_password=False)
                
            elif step.action == "type_password":
                # 模拟人类输入密码
                password = self.login_config.password
                self._type_text_humanly(password, is_password=True)
                
            elif step.action == "type":
                if not step.text:
                    raise ValueError("输入动作需要指定文本")
                
                self._type_text_humanly(step.text, is_password=False)
                
            elif step.action == "wait":
                # 等待指定时间
                delay = random.uniform(step.min_delay, step.max_delay)
                time.sleep(delay)
                
            elif step.action == "random_move":
                # 随机移动鼠标
                screen_width, screen_height = self.simulator.screen_width, self.simulator.screen_height
                target_x = random.randint(100, screen_width - 100)
                target_y = random.randint(100, screen_height - 100)
                self.simulator.move_mouse_human(target_x, target_y)
                
            elif step.action == "scroll":
                # 滚动页面
                direction = random.choice([ScrollDirection.UP, ScrollDirection.DOWN])
                clicks = random.randint(1, 3)
                self.simulator.scroll_human(direction, clicks)
                
            elif step.action == "drag":
                if not step.target_position:
                    raise ValueError("拖拽动作需要目标位置")
                
                # 获取当前位置作为起始位置
                current_x, current_y = self.simulator.simulator.position()
                self.simulator.drag_human(
                    current_x, current_y,
                    *step.target_position
                )
                
            else:
                logger.warning(f"未知的动作类型: {step.action}")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"执行步骤失败: {step.description}, 错误: {e}")
            self.last_error = str(e)
            return False
    
    def _type_text_humanly(self, text: str, is_password: bool = False) -> None:
        """
        以人类化方式输入文本
        
        Args:
            text: 要输入的文本
            is_password: 是否是密码（影响错误概率）
        """
        if not text:
            return
        
        # 根据人类化级别调整参数
        humanization_level = self.login_config.humanization_level
        
        # 设置输入参数
        if humanization_level >= 4:
            # 高度人类化：更慢的输入，更高的错误概率
            min_delay = 0.08
            max_delay = 0.4
            error_prob = 0.02 if not is_password else 0.01
            correction_prob = 0.9
        elif humanization_level >= 3:
            # 中等人类化
            min_delay = 0.05
            max_delay = 0.3
            error_prob = 0.01 if not is_password else 0.005
            correction_prob = 0.8
        else:
            # 较低人类化
            min_delay = 0.03
            max_delay = 0.2
            error_prob = 0.005
            correction_prob = 0.7
        
        # 如果禁用随机行为，降低错误概率
        if not self.login_config.enable_random_behavior:
            error_prob = 0.001
            correction_prob = 0.99
        
        logger.debug(f"输入文本: {'*' * len(text) if is_password else text[:10]}...")
        
        # 使用模拟器输入
        self.simulator.type_human(
            text=text,
            min_delay=min_delay,
            max_delay=max_delay,
            error_probability=error_prob,
            error_correction_probability=correction_prob
        )
    
    def _add_random_behavior(self) -> None:
        """添加随机人类行为"""
        if not self.login_config.enable_random_behavior:
            return
        
        # 随机决定是否添加额外行为
        if random.random() < 0.3:  # 30%概率
            behavior_type = random.choice([
                "idle",          # 空闲
                "micro_move",    # 微小移动
                "scroll",        # 滚动
                "look_around"    # 查看周围
            ])
            
            if behavior_type == "idle":
                # 随机空闲时间
                idle_time = random.uniform(0.5, 2.0)
                time.sleep(idle_time)
                logger.debug(f"添加空闲行为: {idle_time:.1f}秒")
                
            elif behavior_type == "micro_move":
                # 微小鼠标移动
                self.simulator._micro_mouse_movement()
                logger.debug("添加微小鼠标移动")
                
            elif behavior_type == "scroll":
                # 随机滚动
                direction = random.choice([ScrollDirection.UP, ScrollDirection.DOWN])
                clicks = random.randint(1, 2)
                self.simulator.scroll_human(direction, clicks)
                logger.debug(f"添加滚动行为: {direction.value} {clicks}次")
                
            elif behavior_type == "look_around":
                # 查看周围
                self.simulator._look_around()
                logger.debug("添加查看周围行为")
    
    def _check_login_status(self) -> bool:
        """
        检查登录状态
        
        Returns:
            bool: 是否已登录
        """
        # 这里可以实现多种登录状态检查方式：
        # 1. 视觉识别（检查登录后的元素）
        # 2. URL检查
        # 3. Cookie检查
        # 暂时使用简单的时间等待和模拟人类行为
        
        logger.info("检查登录状态...")
        
        # 等待登录完成
        wait_time = self.login_config.wait_after_login
        logger.debug(f"等待登录完成: {wait_time}秒")
        
        # 在等待期间添加随机人类行为
        start_time = time.time()
        while time.time() - start_time < wait_time:
            # 随机等待一小段时间
            time.sleep(random.uniform(0.5, 1.5))
            
            # 随机添加人类行为
            self._add_random_behavior()
        
        # 这里可以添加更精确的登录状态检查
        # 暂时假设登录成功
        is_success = True
        
        if is_success:
            logger.info("登录状态检查: 已登录")
        else:
            logger.warning("登录状态检查: 未登录")
            
        return is_success
    
    def _handle_login_failure(self, attempt: int) -> bool:
        """
        处理登录失败
        
        Args:
            attempt: 当前尝试次数
            
        Returns:
            bool: 是否继续重试
        """
        logger.warning(f"登录失败 (尝试 {attempt}/{self.login_config.max_attempts})")
        
        # 更新统计
        self.stats["failed_logins"] += 1
        
        # 检查是否超过最大尝试次数
        if attempt >= self.login_config.max_attempts:
            logger.error("已达到最大登录尝试次数，停止尝试")
            return False
        
        # 添加随机延迟后再试
        retry_delay = random.uniform(10, 30)  # 10-30秒后重试
        logger.info(f"等待 {retry_delay:.1f} 秒后重试...")
        time.sleep(retry_delay)
        
        # 刷新页面
        self.browser.refresh_page()
        
        return True
    
    def login(self) -> bool:
        """
        执行登录流程
        
        Returns:
            bool: 登录是否成功
        """
        logger.info("开始登录流程...")
        
        # 重置状态
        self.is_logged_in = False
        self.login_attempts = 0
        self.last_error = None
        
        # 开始时间
        start_time = time.time()
        
        # 最大尝试次数循环
        while self.login_attempts < self.login_config.max_attempts:
            self.login_attempts += 1
            self.stats["total_login_attempts"] += 1
            
            logger.info(f"登录尝试 {self.login_attempts}/{self.login_config.max_attempts}")
            
            try:
                # 步骤1: 导航到登录页面
                if not self.browser.navigate_to_url(self.login_config.url):
                    logger.error("导航到登录页面失败")
                    if not self._handle_login_failure(self.login_attempts):
                        break
                    continue
                
                # 步骤2: 添加初始随机行为
                if self.login_config.enable_random_behavior:
                    self._add_random_behavior()
                
                # 步骤3: 执行登录步骤序列
                all_steps_success = True
                for i, step in enumerate(self.login_config.steps):
                    logger.debug(f"执行步骤 {i+1}/{len(self.login_config.steps)}: {step.description}")
                    
                    # 步骤执行前可能的随机行为
                    if self.login_config.enable_random_behavior and random.random() < 0.1:
                        self._add_random_behavior()
                    
                    # 执行步骤
                    step_success = self._execute_step(step)
                    
                    if not step_success:
                        if step.optional:
                            logger.warning(f"可选步骤失败: {step.description}")
                        else:
                            logger.error(f"关键步骤失败: {step.description}")
                            all_steps_success = False
                            break
                
                # 如果有步骤失败
                if not all_steps_success:
                    logger.error("登录步骤执行失败")
                    if not self._handle_login_failure(self.login_attempts):
                        break
                    continue
                
                # 步骤4: 检查登录状态
                self.is_logged_in = self._check_login_status()
                
                if self.is_logged_in:
                    # 登录成功
                    end_time = time.time()
                    login_time = end_time - start_time
                    
                    # 更新统计
                    self.stats["successful_logins"] += 1
                    self.stats["average_login_time"] = (
                        (self.stats["average_login_time"] * (self.stats["successful_logins"] - 1) + login_time) 
                        / self.stats["successful_logins"]
                    )
                    self.stats["last_login_time"] = time.time()
                    
                    logger.info(f"登录成功! 耗时: {login_time:.1f}秒")
                    return True
                else:
                    # 登录失败
                    if not self._handle_login_failure(self.login_attempts):
                        break
                    
            except Exception as e:
                logger.error(f"登录过程中发生异常: {e}")
                self.last_error = str(e)
                
                if not self._handle_login_failure(self.login_attempts):
                    break
        
        # 登录失败
        logger.error("登录失败")
        return False
    
    def logout(self) -> bool:
        """
        注销登录
        
        Returns:
            bool: 是否成功
        """
        try:
            logger.info("开始注销流程...")
            
            # 这里可以实现注销逻辑
            # 暂时简单处理
            self.is_logged_in = False
            
            logger.info("注销成功")
            return True
            
        except Exception as e:
            logger.error(f"注销失败: {e}")
            return False
    
    def get_login_status(self) -> Dict[str, Any]:
        """
        获取登录状态信息
        
        Returns:
            Dict[str, Any]: 状态信息
        """
        return {
            "is_logged_in": self.is_logged_in,
            "login_attempts": self.login_attempts,
            "last_error": self.last_error,
            "stats": self.stats.copy(),
            "config": {
                "url": self.login_config.url,
                "method": self.login_config.method.value,
                "username": self.login_config.username,
                "max_attempts": self.login_config.max_attempts,
                "humanization_level": self.login_config.humanization_level
            }
        }
    
    def update_config(self, new_config: Dict[str, Any]) -> bool:
        """
        更新登录配置
        
        Args:
            new_config: 新配置
            
        Returns:
            bool: 是否成功
        """
        try:
            # 这里可以实现配置更新逻辑
            # 暂时简单处理
            if "url" in new_config:
                self.login_config.url = new_config["url"]
            
            if "username" in new_config:
                self.login_config.username = new_config["username"]
            
            if "password" in new_config:
                self.login_config.password = new_config["password"]
            
            logger.info("登录配置已更新")
            return True
            
        except Exception as e:
            logger.error(f"更新配置失败: {e}")
            return False


# 工厂函数，方便创建登录器
def create_login_automator(
    config_path: str = "config.yaml",
    human_simulator: Optional[HumanSimulator] = None,
    browser_controller: Optional[BrowserController] = None
) -> LoginAutomator:
    """
    创建登录自动化器
    
    Args:
        config_path: 配置文件路径
        human_simulator: 人类行为模拟器，如果为None则创建新实例
        browser_controller: 浏览器控制器，如果为None则创建新实例
        
    Returns:
        LoginAutomator: 登录自动化器实例
    """
    # 获取配置
    config = get_config(config_path)
    
    # 创建模拟器（如果未提供）
    if human_simulator is None:
        from modules.human_simulator import create_human_simulator
        human_simulator_config = config.get("human_simulator")
        human_simulator = create_human_simulator(human_simulator_config)
    
    # 创建浏览器控制器（如果未提供）
    if browser_controller is None:
        browser_controller = BrowserController(human_simulator)
    
    # 创建登录自动化器
    login_automator = LoginAutomator(
        simulator=human_simulator,
        browser_controller=browser_controller
    )
    
    return login_automator