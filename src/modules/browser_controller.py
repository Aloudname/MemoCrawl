"""
browser_controller.py
浏览器控制模块，负责打开和导航浏览器
"""

import webbrowser
import time
import logging
import subprocess
import os

from typing import Optional, Tuple, List, Any, Dict
from pathlib import Path
from munch import Munch

from src.config.manager import init_config, get_dict_config
from src.modules.human_simulator import HumanSimulator

logger = logging.getLogger(__name__)

class BrowserController:
    """浏览器控制器"""
    
    def __init__(self, simulator: HumanSimulator = None, config: Dict[str, Any] = None):
        """
        初始化浏览器控制器
        
        Args:
            simulator: 人类行为模拟器
        """
        init_config()
        config = get_dict_config()
        self.config = Munch.fromDict(config)
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
            chrome_path = self.config.browser.path.chrome_path
            
            # 构建启动参数
            chrome_args = [
                chrome_path if chrome_path else "chrome",
                f"--window-size={self.window_width},{self.window_height}",
                "--start-maximized",
                "--disable-infobars",
                "--disable-notifications",
            ]
            
            if self.config.browser.network.disable_images:
                chrome_args.append("--blink-settings=imagesEnabled=false")
            else:
                pass
            
            if self.config.browser.network.user_data_dir:
                chrome_args.append(f"--user-data-dir={self.config.browser.network.user_data_dir}")
            else:
                pass
            
            # 启动浏览器
            self.browser_process = subprocess.Popen(chrome_args)
            
            # 等待浏览器启动
            self.simulator.delay(3, 5)
            
            logger.info("浏览器已成功打开")
            
        except Exception as e:
            logger.error(f"打开浏览器失败: {e}")
    
    def to_url(self) -> bool:
        """
        导航到指定URL
        
        Args:
            url: 目标URL
            
        Returns:
            bool: 是否成功
        """
        
        url = self.config.browser.path.url
        try:
            logger.info(f"正在导航到: {url}")
            self.simulator.delay(4, 5)
            
            # 模拟人类行为：按Ctrl+L聚焦地址栏
            self.simulator.hotkey('ctrl', 'l')
            
            # 等待地址栏聚焦
            self.simulator.delay(2, 3)
        
            # 输入URL
            self.simulator.hotkey('ctrl', 'a')
            
            self.simulator.type_in(url, min_delay=0.05, max_delay=0.2)
            
            # 按回车键
            self.simulator.press_key('enter')
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
                self.simulator.hotkey('alt', 'f4')
                
                # 等待浏览器关闭
                self.simulator.delay(2, 3)
                
                # 终止进程
                self.browser_process.terminate()
                self.browser_process.wait(timeout=5)
                
                logger.info("浏览器已关闭")
                
        except Exception as e:
            logger.error(f"关闭浏览器失败: {e}")
    
    def get_browser_window_info(self) -> Optional[dict]:
        """
        获取浏览器窗口信息
        
        Returns:
            dict: 窗口信息或None
        """
        try:
            # 集成第三方库pygetwindow/win32gui获取窗口信息(WIP)
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
            self.simulator.hotkey('ctrl', 'r')
        except Exception as e:
            logger.error(f"刷新页面失败: {e}")
    
    def go_back(self) -> bool:
        """
        返回上一页
        
        Returns:
            bool: 是否成功
        """
        try:
            logger.info("返回上一页...")
            self.simulator.hotkey('alt', 'left')
        except Exception as e:
            logger.error(f"返回上一页失败: {e}")
            
def elementTuple() -> Tuple[HumanSimulator, BrowserController]:
    init_config()
    config = get_dict_config()
    hs = HumanSimulator()
    browser_controller = BrowserController(simulator=hs, config=config)
    return (hs, browser_controller)
