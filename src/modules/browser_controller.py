"""
browser_controller.py
浏览器控制模块，负责打开和导航浏览器
"""

import webbrowser
import time
import logging
import subprocess
import os

from typing import Optional, Tuple, List
from pathlib import Path
from munch import Munch

from src.config.manager import get_config
from src.modules.human_simulator import HumanSimulator

logger = logging.getLogger(__name__)

class BrowserController:
    """浏览器控制器"""
    
    def __init__(self, simulator: HumanSimulator = HumanSimulator):
        """
        初始化浏览器控制器
        
        Args:
            simulator: 人类行为模拟器
        """
        dict_config = get_config().get_all()
        self.config = Munch.fromDict(dict_config)
        self.simulator = simulator

        
        self.window_width = self.config.browser.physical.window_width
        self.window_height = self.config.browser.physical.window_height
        
        # 浏览器进程
        self.browser_process = None
        
        logger.info("浏览器控制器初始化完成")
    
    def open_browser(self) -> bool:
        """
        打开浏览器
        
        Returns:
            bool: 是否成功
        """
        try:
            logger.info("正在打开浏览器...")
            
            # 检查Chrome路径
            chrome_path = self.config.browser.network.chrome_path
            
            # 构建启动参数
            chrome_args = [
                chrome_path if chrome_path else "chrome",
                f"--window-size={self.window_width},{self.window_height}",
                "--start-maximized",
                "--disable-infobars",
                "--disable-notifications",
            ]
            
            if self.browser_config.disable_images:
                chrome_args.append("--blink-settings=imagesEnabled=false")
            
            if self.browser_config.user_data_dir:
                chrome_args.append(f"--user-data-dir={self.browser_config.user_data_dir}")
            
            # 启动浏览器
            self.browser_process = subprocess.Popen(chrome_args)
            
            # 等待浏览器启动
            self.simulator.idle_behavior(min_duration=3, max_duration=5)
            
            logger.info("浏览器已成功打开")
            return True
            
        except Exception as e:
            logger.error(f"打开浏览器失败: {e}")
            return False
    
    def navigate_to_url(self, url: str) -> bool:
        """
        导航到指定URL
        
        Args:
            url: 目标URL
            
        Returns:
            bool: 是否成功
        """
        try:
            logger.info(f"正在导航到: {url}")
            
            # 模拟人类行为：按Ctrl+L聚焦地址栏
            self.simulator.hotkey_human('ctrl', 'l')
            
            # 等待地址栏聚焦
            self.simulator.idle_behavior(min_duration=0.5, max_duration=1.0)
            
            # 清除当前URL（如果有）
            self.simulator.press_key_human('a', presses=1)  # 全选
            self.simulator.press_key_human('delete', presses=1)
            
            # 输入URL
            self.simulator.type_human(
                url,
                min_delay=0.05,
                max_delay=0.2,
                error_probability=0.01
            )
            
            # 按回车键
            self.simulator.press_key_human('enter')
            
            # 等待页面加载
            self.simulator.idle_behavior(min_duration=3, max_duration=7)
            
            logger.info(f"已导航到: {url}")
            return True
            
        except Exception as e:
            logger.error(f"导航失败: {e}")
            return False
    
    def close_browser(self) -> bool:
        """
        关闭浏览器
        
        Returns:
            bool: 是否成功
        """
        try:
            if self.browser_process:
                logger.info("正在关闭浏览器...")
                
                # 模拟人类行为：按Alt+F4关闭窗口
                self.simulator.hotkey_human('alt', 'f4')
                
                # 等待浏览器关闭
                self.simulator.idle_behavior(min_duration=1, max_duration=2)
                
                # 终止进程
                self.browser_process.terminate()
                self.browser_process.wait(timeout=5)
                
                logger.info("浏览器已关闭")
                return True
                
        except Exception as e:
            logger.error(f"关闭浏览器失败: {e}")
            return False
        
        return False
    
    def get_browser_window_info(self) -> Optional[dict]:
        """
        获取浏览器窗口信息
        
        Returns:
            dict: 窗口信息或None
        """
        try:
            # 这里可以集成第三方库来获取窗口信息
            # 例如使用pygetwindow或win32gui
            # 暂时返回固定信息
            return {
                "width": self.window_width,
                "height": self.window_height,
                "title": "Chrome"
            }
        except:
            return None
    
    def refresh_page(self) -> bool:
        """
        刷新当前页面
        
        Returns:
            bool: 是否成功
        """
        try:
            logger.info("刷新页面...")
            self.simulator.hotkey_human('ctrl', 'r')
            self.simulator.idle_behavior(min_duration=2, max_duration=4)
            return True
        except Exception as e:
            logger.error(f"刷新页面失败: {e}")
            return False
    
    def go_back(self) -> bool:
        """
        返回上一页
        
        Returns:
            bool: 是否成功
        """
        try:
            logger.info("返回上一页...")
            self.simulator.hotkey_human('alt', 'left')
            self.simulator.idle_behavior(min_duration=2, max_duration=4)
            return True
        except Exception as e:
            logger.error(f"返回上一页失败: {e}")
            return False