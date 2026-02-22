"""
capture.py
屏幕捕捉子模块

负责：
1. 全屏/区域截图
2. 快捷键触发截图
3. 截图预处理（去噪、增强等）
4. 截图保存与管理

依赖库（均已在requirements.txt中）：
- mss: 高性能屏幕截图
- numpy: 数组操作
- cv2 (opencv-python): 图像处理
- PIL (pillow): 图像格式转换
"""

import os
import time
import logging
import threading
import numpy as np

from typing import Optional, Tuple, Callable
from datetime import datetime

# --- 第三方库导入（均为 requirements.txt 中已有的库）---
try:
    import mss
    import mss.tools
except ImportError:
    raise ImportError("请安装 mss 库: pip install mss")

try:
    import cv2
except ImportError:
    raise ImportError("请安装 opencv-python 库: pip install opencv-python")

try:
    from PIL import Image
except ImportError:
    raise ImportError("请安装 pillow 库: pip install pillow")

try:
    import keyboard  # 用于全局快捷键监听
    _KEYBOARD_AVAILABLE = True
except ImportError:
    _KEYBOARD_AVAILABLE = False

from src.modules.vision.models import VisionConfig, BoundingBox

logger = logging.getLogger(__name__)


class ScreenCapture:
    """
    屏幕捕捉器
    提供全屏截图、区域截图、快捷键触发截图等功能
    """
    
    def __init__(self, config: Optional[VisionConfig] = None):
        """
        初始化屏幕捕捉器
        
        Args:
            config: 视觉模块配置。为None时使用默认配置。
        """
        self.config = config or VisionConfig()
        
        # 快捷键监听器状态
        self._hotkey_registered = False
        self._hotkey_callback: Optional[Callable] = None
        self._capture_lock = threading.Lock()
        
        # 确保截图输出目录存在
        os.makedirs(self.config.screenshot_save_dir, exist_ok=True)
        
        logger.info(f"ScreenCapture 初始化完成, "
                     f"截图保存目录: {self.config.screenshot_save_dir}")
    
    # ==================== 核心截图方法 ====================
    
    def capture_fullscreen(self) -> np.ndarray:
        """
        捕捉全屏截图
        
        Returns:
            np.ndarray: BGR格式的截图 (OpenCV标准格式)
            
        Raises:
            RuntimeError: 截图失败时抛出
        """
        with self._capture_lock:
            try:
                logger.debug("开始全屏截图...")
                
                with mss.mss() as sct:
                    # mss的monitor[0]是所有屏幕的合集，monitor[1]是主屏幕
                    monitor = sct.monitors[1]
                    
                    # 截图 -> mss.ScreenShot对象
                    screenshot = sct.grab(monitor)
                    
                    # 转换为numpy数组 (BGRA格式)
                    img_bgra = np.array(screenshot, dtype=np.uint8)
                    
                    # BGRA -> BGR (去除Alpha通道)
                    img_bgr = cv2.cvtColor(img_bgra, cv2.COLOR_BGRA2BGR)
                
                logger.debug(f"全屏截图完成, 尺寸: {img_bgr.shape[1]}x{img_bgr.shape[0]}")
                return img_bgr
                
            except Exception as e:
                logger.error(f"全屏截图失败: {e}")
                raise RuntimeError(f"全屏截图失败: {e}") from e
    
    def capture_region(self, 
                       x: int, y: int, 
                       width: int, height: int) -> np.ndarray:
        """
        捕捉指定区域截图
        
        Args:
            x: 区域左上角 x 坐标
            y: 区域左上角 y 坐标
            width: 区域宽度
            height: 区域高度
            
        Returns:
            np.ndarray: BGR格式的区域截图
            
        Raises:
            ValueError: 区域参数无效
            RuntimeError: 截图失败时抛出
        """
        if width <= 0 or height <= 0:
            raise ValueError(f"截图区域尺寸无效: width={width}, height={height}")
        
        with self._capture_lock:
            try:
                logger.debug(f"区域截图: ({x},{y}) {width}x{height}")
                
                region = {"left": x, "top": y, "width": width, "height": height}
                
                with mss.mss() as sct:
                    screenshot = sct.grab(region)
                    img_bgra = np.array(screenshot, dtype=np.uint8)
                    img_bgr = cv2.cvtColor(img_bgra, cv2.COLOR_BGRA2BGR)
                
                logger.debug(f"区域截图完成, 实际尺寸: {img_bgr.shape[1]}x{img_bgr.shape[0]}")
                return img_bgr
                
            except Exception as e:
                logger.error(f"区域截图失败: {e}")
                raise RuntimeError(f"区域截图失败: {e}") from e
    
    def capture_bbox(self, bbox: BoundingBox) -> np.ndarray:
        """
        根据BoundingBox截取屏幕区域
        
        Args:
            bbox: 目标区域的边界框
            
        Returns:
            np.ndarray: BGR格式的截图
        """
        return self.capture_region(bbox.x1, bbox.y1, bbox.width, bbox.height)
    
    def capture_with_config(self) -> np.ndarray:
        """
        根据当前配置截图（全屏或配置中指定的区域）
        
        Returns:
            np.ndarray: BGR格式的截图
        """
        # 截图前延迟（等待页面渲染稳定）
        if self.config.capture_delay > 0:
            logger.debug(f"截图前延迟 {self.config.capture_delay}s...")
            time.sleep(self.config.capture_delay)
        
        if self.config.capture_region:
            x, y, w, h = self.config.capture_region
            return self.capture_region(x, y, w, h)
        else:
            return self.capture_fullscreen()
    
    # ==================== 截图预处理 ====================
    
    @staticmethod
    def preprocess(image: np.ndarray,
                   denoise: bool = True,
                   sharpen: bool = False,
                   adjust_contrast: bool = False,
                   contrast_alpha: float = 1.2,
                   contrast_beta: int = 10) -> np.ndarray:
        """
        对截图进行预处理以提升后续识别质量
        
        Args:
            image: 输入图像 (BGR)
            denoise: 是否去噪
            sharpen: 是否锐化
            adjust_contrast: 是否调整对比度
            contrast_alpha: 对比度系数 (>1增强)
            contrast_beta: 亮度偏移
            
        Returns:
            np.ndarray: 预处理后的图像 (BGR)
        """
        result = image.copy()
        
        if denoise:
            # 非局部均值去噪 (h=10为去噪强度, templateWindowSize=7, searchWindowSize=21)
            result = cv2.fastNlMeansDenoisingColored(
                result, None, h=6, hForColorComponents=6,
                templateWindowSize=7, searchWindowSize=21
            )
        
        if sharpen:
            # 使用锐化核
            kernel = np.array([
                [0, -1,  0],
                [-1,  5, -1],
                [0, -1,  0]
            ], dtype=np.float32)
            result = cv2.filter2D(result, -1, kernel)
        
        if adjust_contrast:
            # 线性变换：output = alpha * input + beta
            result = cv2.convertScaleAbs(result, alpha=contrast_alpha, beta=contrast_beta)
        
        return result
    
    @staticmethod
    def to_grayscale(image: np.ndarray) -> np.ndarray:
        """
        将BGR图像转为灰度图
        
        Args:
            image: BGR图像
        Returns:
            np.ndarray: 灰度图
        """
        if len(image.shape) == 2:
            return image  # 已经是灰度图
        return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    
    @staticmethod
    def to_binary(image: np.ndarray,
                  method: str = "otsu",
                  threshold: int = 127,
                  block_size: int = 11,
                  c_value: int = 2) -> np.ndarray:
        """
        将图像二值化，用于OCR预处理
        
        Args:
            image: 输入图像 (灰度或BGR)
            method: 二值化方法 ("otsu" / "adaptive" / "simple")
            threshold: 简单阈值法的阈值
            block_size: 自适应阈值的块大小 (奇数)
            c_value: 自适应阈值的常量
            
        Returns:
            np.ndarray: 二值化图像
        """
        gray = image if len(image.shape) == 2 else cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        if method == "otsu":
            _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        elif method == "adaptive":
            binary = cv2.adaptiveThreshold(
                gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY, block_size, c_value
            )
        elif method == "simple":
            _, binary = cv2.threshold(gray, threshold, 255, cv2.THRESH_BINARY)
        else:
            raise ValueError(f"不支持的二值化方法: {method}")
        
        return binary
    
    # ==================== 截图保存 ====================
    
    def save_screenshot(self, 
                        image: np.ndarray, 
                        filename: Optional[str] = None,
                        subdir: str = "") -> str:
        """
        保存截图到磁盘
        
        Args:
            image: 要保存的图像 (BGR numpy数组)
            filename: 文件名，None则自动生成带时间戳的文件名
            subdir: 子目录名 (在 screenshot_save_dir 下)
            
        Returns:
            str: 保存的文件完整路径
        """
        save_dir = self.config.screenshot_save_dir
        if subdir:
            save_dir = os.path.join(save_dir, subdir)
        os.makedirs(save_dir, exist_ok=True)
        
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            filename = f"screenshot_{timestamp}.png"
        
        filepath = os.path.join(save_dir, filename)
        
        success = cv2.imwrite(filepath, image)
        if success:
            logger.info(f"截图已保存: {filepath}")
        else:
            logger.warning(f"截图保存失败: {filepath}")
        
        return filepath
    
    # ==================== 快捷键触发 ====================
    
    def register_hotkey(self, 
                        callback: Callable[[np.ndarray], None],
                        hotkey: Optional[str] = None) -> bool:
        """
        注册快捷键触发截图
        当用户按下指定快捷键时，自动截图并调用回调函数
        
        Args:
            callback: 截图完成后的回调函数，接收 np.ndarray (BGR) 参数
            hotkey: 快捷键组合字符串 (如 "ctrl+shift+c")，
                    None则使用config中的配置
                    
        Returns:
            bool: 是否注册成功
            
        Note:
            需要安装 keyboard 库: pip install keyboard
            在Windows上可能需要管理员权限
        """
        if not _KEYBOARD_AVAILABLE:
            logger.warning("keyboard 库未安装，无法注册快捷键。"
                          "请运行: pip install keyboard")
            return False
        
        hotkey = hotkey or self.config.hotkey_capture
        
        try:
            # 先取消已有注册
            self.unregister_hotkey()
            
            self._hotkey_callback = callback
            
            def _on_hotkey():
                logger.info(f"快捷键 [{hotkey}] 被触发，正在截图...")
                try:
                    screenshot = self.capture_with_config()
                    if self._hotkey_callback:
                        self._hotkey_callback(screenshot)
                except Exception as e:
                    logger.error(f"快捷键回调执行失败: {e}")
            
            keyboard.add_hotkey(hotkey, _on_hotkey)
            self._hotkey_registered = True
            
            logger.info(f"已注册截图快捷键: [{hotkey}]")
            return True
            
        except Exception as e:
            logger.error(f"注册快捷键失败: {e}")
            return False
    
    def unregister_hotkey(self):
        """取消已注册的快捷键"""
        if self._hotkey_registered and _KEYBOARD_AVAILABLE:
            try:
                keyboard.unhook_all_hotkeys()
                self._hotkey_registered = False
                self._hotkey_callback = None
                logger.info("快捷键已取消注册")
            except Exception as e:
                logger.warning(f"取消快捷键注册时出错: {e}")
    
    # ==================== 工具方法 ====================
    
    @staticmethod
    def get_screen_size() -> Tuple[int, int]:
        """
        获取主屏幕分辨率
        
        Returns:
            Tuple[int, int]: (宽, 高)
        """
        with mss.mss() as sct:
            monitor = sct.monitors[1]
            return (monitor["width"], monitor["height"])
    
    @staticmethod
    def numpy_to_pil(image: np.ndarray) -> Image.Image:
        """
        将BGR numpy数组转换为PIL Image (RGB)

        Args:
            image: BGR格式的numpy数组
        Returns:
            PIL.Image.Image: RGB格式的PIL图像
        """
        rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        return Image.fromarray(rgb)
    
    @staticmethod
    def pil_to_numpy(image: Image.Image) -> np.ndarray:
        """
        将PIL Image (RGB) 转换为BGR numpy数组
        
        Args:
            image: PIL Image (RGB)
        Returns:
            np.ndarray: BGR格式的numpy数组
        """
        rgb = np.array(image)
        return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    
    def __del__(self):
        """析构时清理快捷键"""
        self.unregister_hotkey()
