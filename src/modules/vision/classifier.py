"""
classifier.py
商品图片分类器

负责：
1. 管理参考图片库（已知商品类型的样本图片）
2. 基于特征匹配对商品图片进行分类
3. 支持动态添加新商品类别

分类原理：
- 使用ORB特征检测器提取图片的关键点和描述子
- 将待分类图片与参考图片库中的样本进行特征匹配
- 匹配点数超过阈值且最多的类别即为分类结果
- 所有类别匹配点数都未达阈值则归类为"未知商品"

依赖库：
- cv2 (opencv-python): ORB特征检测与匹配
- numpy: 数组操作
"""

import os
import json
import logging
import numpy as np

from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass

try:
    import cv2
except ImportError:
    raise ImportError("请安装 opencv-python: pip install opencv-python")

from src.modules.vision.models import (
    VisionConfig, ImageRegion, BoundingBox, ProductCategory
)

logger = logging.getLogger(__name__)


@dataclass
class ReferenceImage:
    """参考图片信息"""
    filepath: str           # 图片路径
    category_name: str      # 类别名称
    descriptors: Optional[np.ndarray] = None  # ORB描述子 (缓存)
    keypoints_count: int = 0  # 关键点数量


class ProductClassifier:
    """
    商品图片分类器
    
    基于ORB特征匹配将商品图片分类为已知类型或"未知商品"。
    
    使用方法：
    1. 在 reference_image_dir 目录下按类别名创建子目录
    2. 每个子目录放入该类别商品的几张样本图片
    3. 调用 classify() 方法对新图片进行分类
    
    目录结构示例：
        data/reference_images/
            金士顿_DDR5_32G/
                sample1.jpg
                sample2.jpg
            美商海盗船_DDR5_32G/
                sample1.jpg
            三星_DDR5_32G/
                sample1.jpg
    """
    
    def __init__(self, config: Optional[VisionConfig] = None):
        """
        初始化分类器
        
        Args:
            config: 视觉模块配置
        """
        self.config = config or VisionConfig()
        
        # ORB特征检测器
        # nfeatures: 检测的最大特征点数量
        # ORB (Oriented FAST and Rotated BRIEF) 是一种高效的特征描述子
        self._orb = cv2.ORB_create(nfeatures=500)
        
        # BFMatcher: 暴力匹配器
        # NORM_HAMMING: ORB描述子使用汉明距离
        # crossCheck=True: 双向匹配检查，提高匹配准确性
        self._matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
        
        # 参考图片库
        self._reference_images: Dict[str, List[ReferenceImage]] = {}
        
        # 加载参考图片库
        self._load_reference_images()
        
        total_images = sum(len(imgs) for imgs in self._reference_images.values())
        logger.info(f"ProductClassifier 初始化完成, "
                     f"类别数: {len(self._reference_images)}, "
                     f"参考图片总数: {total_images}")
    
    # ==================== 参考图片库管理 ====================
    
    def _load_reference_images(self):
        """
        从参考图片目录加载所有类别的样本图片
        
        目录结构：reference_image_dir/类别名/图片文件
        """
        ref_dir = self.config.reference_image_dir
        
        if not os.path.exists(ref_dir):
            logger.warning(f"参考图片目录不存在: {ref_dir}，"
                          f"图片分类功能将无法使用。"
                          f"请创建目录并放入参考图片。")
            os.makedirs(ref_dir, exist_ok=True)
            return
        
        supported_formats = {'.jpg', '.jpeg', '.png', '.bmp', '.webp'}
        
        for category_dir in os.listdir(ref_dir):
            category_path = os.path.join(ref_dir, category_dir)
            
            if not os.path.isdir(category_path):
                continue
            
            category_name = category_dir
            self._reference_images[category_name] = []
            
            for filename in os.listdir(category_path):
                ext = os.path.splitext(filename)[1].lower()
                if ext not in supported_formats:
                    continue
                
                filepath = os.path.join(category_path, filename)
                
                # 提取ORB特征
                ref_img = self._load_and_extract_features(filepath, category_name)
                if ref_img:
                    self._reference_images[category_name].append(ref_img)
            
            count = len(self._reference_images[category_name])
            if count > 0:
                logger.debug(f"类别 '{category_name}': 加载了 {count} 张参考图片")
            else:
                del self._reference_images[category_name]
    
    def _load_and_extract_features(self, 
                                    filepath: str, 
                                    category_name: str
                                    ) -> Optional[ReferenceImage]:
        """
        加载图片并提取ORB特征
        
        Args:
            filepath: 图片路径
            category_name: 类别名称
            
        Returns:
            ReferenceImage: 含特征描述子的参考图片对象，失败返回None
        """
        try:
            image = cv2.imread(filepath)
            if image is None:
                logger.warning(f"无法读取图片: {filepath}")
                return None
            
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            
            # detectAndCompute: 同时检测关键点和计算描述子
            # 返回: (keypoints, descriptors)
            # keypoints: List[cv2.KeyPoint], 每个关键点包含位置、大小、角度等
            # descriptors: np.ndarray, shape=(N, 32), 每行是一个256位的描述子
            keypoints, descriptors = self._orb.detectAndCompute(gray, None)
            
            if descriptors is None or len(descriptors) < 5:
                logger.debug(f"图片特征点不足: {filepath} ({len(keypoints) if keypoints else 0} pts)")
                return None
            
            return ReferenceImage(
                filepath=filepath,
                category_name=category_name,
                descriptors=descriptors,
                keypoints_count=len(keypoints)
            )
            
        except Exception as e:
            logger.error(f"加载参考图片失败 {filepath}: {e}")
            return None
    
    def add_reference_image(self, 
                            image: np.ndarray, 
                            category_name: str,
                            save_filename: Optional[str] = None) -> bool:
        """
        动态添加参考图片到指定类别
        
        Args:
            image: 参考图片 (BGR numpy数组)
            category_name: 类别名称
            save_filename: 保存文件名（不含目录），None则自动生成
            
        Returns:
            bool: 是否添加成功
        """
        try:
            # 保存图片到参考目录
            category_dir = os.path.join(self.config.reference_image_dir, category_name)
            os.makedirs(category_dir, exist_ok=True)
            
            if save_filename is None:
                existing = len(os.listdir(category_dir))
                save_filename = f"sample_{existing + 1}.png"
            
            filepath = os.path.join(category_dir, save_filename)
            cv2.imwrite(filepath, image)
            
            # 提取特征
            ref_img = self._load_and_extract_features(filepath, category_name)
            if ref_img is None:
                return False
            
            if category_name not in self._reference_images:
                self._reference_images[category_name] = []
            
            self._reference_images[category_name].append(ref_img)
            
            logger.info(f"已添加参考图片到类别 '{category_name}': {filepath}")
            return True
            
        except Exception as e:
            logger.error(f"添加参考图片失败: {e}")
            return False
    
    def get_categories(self) -> List[str]:
        """获取所有已注册的类别名称"""
        return list(self._reference_images.keys())
    
    # ==================== 分类方法 ====================
    
    def classify(self, image: np.ndarray) -> ImageRegion:
        """
        对商品图片进行分类
        
        匹配流程：
        1. 提取输入图片的ORB特征
        2. 与每个类别的参考图片进行特征匹配
        3. 统计每个类别的好匹配数量
        4. 匹配数最多且超过阈值的类别为分类结果
        
        Args:
            image: 商品图片 (BGR numpy数组)
            
        Returns:
            ImageRegion: 分类结果（含类别名称和匹配分数）
        """
        h, w = image.shape[:2]
        result_bbox = BoundingBox(x1=0, y1=0, x2=w, y2=h)
        
        # 无参考图片时直接返回未知
        if not self._reference_images:
            logger.debug("参考图片库为空，返回'未知商品'")
            return ImageRegion(
                bbox=result_bbox,
                image=image,
                category=ProductCategory.UNKNOWN,
                category_name="未知商品",
                match_score=0.0
            )
        
        # 提取输入图片特征
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        keypoints, descriptors = self._orb.detectAndCompute(gray, None)
        
        if descriptors is None or len(descriptors) < 5:
            logger.debug(f"输入图片特征点不足: {len(keypoints) if keypoints else 0}")
            return ImageRegion(
                bbox=result_bbox,
                image=image,
                category=ProductCategory.UNKNOWN,
                category_name="未知商品",
                match_score=0.0
            )
        
        # 与每个类别的参考图片进行匹配
        category_scores: Dict[str, float] = {}
        
        for category_name, ref_images in self._reference_images.items():
            best_score = 0.0
            
            for ref_img in ref_images:
                if ref_img.descriptors is None:
                    continue
                
                try:
                    # BFMatcher.match: 暴力匹配
                    # 返回: List[cv2.DMatch]
                    # cv2.DMatch 属性: distance(越小越好), queryIdx, trainIdx
                    matches = self._matcher.match(descriptors, ref_img.descriptors)
                    
                    # 按distance排序，选取好的匹配
                    matches = sorted(matches, key=lambda m: m.distance)
                    
                    # 计算好匹配的数量作为分数
                    # 距离小于中位数*0.7的匹配视为好匹配
                    if matches:
                        good_threshold = max(
                            matches[len(matches) // 2].distance * 0.7,
                            30.0
                        )
                        good_matches = [m for m in matches if m.distance < good_threshold]
                        score = len(good_matches)
                        best_score = max(best_score, score)
                        
                except cv2.error as e:
                    logger.debug(f"匹配出错 (category={category_name}): {e}")
                    continue
            
            category_scores[category_name] = best_score
        
        # 找到最佳类别
        if not category_scores:
            best_category = "未知商品"
            best_score = 0.0
        else:
            best_category = max(category_scores, key=category_scores.get)
            best_score = category_scores[best_category]
        
        # 判断是否达到阈值
        threshold = self.config.feature_match_threshold
        
        if best_score >= threshold:
            category = ProductCategory.KNOWN
            category_name = best_category
            logger.debug(f"图片分类结果: '{category_name}' "
                        f"(score={best_score:.0f}, threshold={threshold})")
        else:
            category = ProductCategory.UNKNOWN
            category_name = "未知商品"
            logger.debug(f"图片分类: 未知商品 "
                        f"(best_score={best_score:.0f} < threshold={threshold})")
        
        return ImageRegion(
            bbox=result_bbox,
            image=image,
            category=category,
            category_name=category_name,
            match_score=best_score
        )
    
    def classify_batch(self, images: List[np.ndarray]) -> List[ImageRegion]:
        """
        批量分类商品图片
        
        Args:
            images: 商品图片列表
            
        Returns:
            List[ImageRegion]: 分类结果列表
        """
        results = []
        for i, image in enumerate(images):
            logger.debug(f"分类图片 {i + 1}/{len(images)}")
            result = self.classify(image)
            results.append(result)
        return results
    
    # ==================== 图片库信息 ====================
    
    def get_library_info(self) -> Dict:
        """获取参考图片库概览信息"""
        info = {
            "reference_dir": self.config.reference_image_dir,
            "total_categories": len(self._reference_images),
            "categories": {}
        }
        
        for cat_name, ref_imgs in self._reference_images.items():
            info["categories"][cat_name] = {
                "image_count": len(ref_imgs),
                "avg_keypoints": (
                    sum(r.keypoints_count for r in ref_imgs) / len(ref_imgs)
                    if ref_imgs else 0
                )
            }
        
        return info
