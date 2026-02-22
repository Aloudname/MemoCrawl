"""
detector.py
页面元素检测器

负责：
1. 从页面截图中检测商品卡片区域（裁剪）
2. 对每张卡片内部进行区域分割（图片区域 / 文字区域 / 其它区域）
3. 卡片去重与过滤
4. 提供泛用的元素定位API

检测策略：
- 京东/电商搜索结果页的商品卡片通常呈现为网格布局
- 卡片间有明显边界线或背景色差
- 使用轮廓检测、边缘检测、颜色分割等方法

依赖库：
- cv2 (opencv-python): 图像处理与轮廓检测
- numpy: 数组操作
"""

import logging
import numpy as np
from typing import List, Optional, Tuple

try:
    import cv2
except ImportError:
    raise ImportError("请安装 opencv-python: pip install opencv-python")

from src.modules.vision.models import (
    VisionConfig, BoundingBox, ProductCard,
    CardDetectionMethod, RegionType
)

logger = logging.getLogger(__name__)


class ElementDetector:
    """
    页面元素检测器
    
    从电商页面截图中检测并裁剪商品卡片，
    并对卡片内部进行区域分割。
    """
    
    def __init__(self, config: Optional[VisionConfig] = None):
        """
        初始化元素检测器
        
        Args:
            config: 视觉模块配置
        """
        self.config = config or VisionConfig()
        
        # 检测方法映射
        self._method_map = {
            CardDetectionMethod.CONTOUR.value: self._detect_by_contour,
            CardDetectionMethod.EDGE.value: self._detect_by_edge,
            CardDetectionMethod.COLOR.value: self._detect_by_color,
            CardDetectionMethod.GRID.value: self._detect_by_grid,
        }
        
        logger.info(f"ElementDetector 初始化完成, "
                     f"检测方法: {self.config.detection_method}")
    
    # ==================== 商品卡片检测 ====================
    
    def detect_product_cards(self, 
                             image: np.ndarray,
                             method: Optional[str] = None
                             ) -> List[ProductCard]:
        """
        从页面截图中检测所有商品卡片
        
        这是卡片检测的主入口，会根据method选择不同的检测策略。
        
        Args:
            image: 页面截图 (BGR)
            method: 检测方法名，None则使用配置值
                    可选: "contour", "edge", "color", "grid"
                    
        Returns:
            List[ProductCard]: 检测出的商品卡片列表（含对角坐标）
        """
        method = method or self.config.detection_method
        
        if method not in self._method_map:
            logger.warning(f"不支持的检测方法 '{method}'，回退到 'contour'")
            method = CardDetectionMethod.CONTOUR.value
        
        logger.info(f"开始商品卡片检测，方法: {method}, "
                     f"图像尺寸: {image.shape[1]}x{image.shape[0]}")
        
        # 调用对应的检测方法获取候选边界框
        detect_func = self._method_map[method]
        candidate_bboxes = detect_func(image)
        
        logger.debug(f"候选边界框数量 (过滤前): {len(candidate_bboxes)}")
        
        # 过滤无效边界框
        valid_bboxes = self._filter_bboxes(candidate_bboxes)
        logger.debug(f"有效边界框数量 (过滤后): {len(valid_bboxes)}")
        
        # 去重（NMS非极大值抑制）
        final_bboxes = self._non_max_suppression(valid_bboxes)
        logger.info(f"最终检测到 {len(final_bboxes)} 个商品卡片")
        
        # 构建ProductCard对象
        cards = []
        for i, bbox in enumerate(final_bboxes):
            card_image = bbox.crop_from(image)
            card = ProductCard(
                bbox=bbox,
                card_image=card_image,
                card_index=i
            )
            cards.append(card)
        
        return cards
    
    # ==================== 检测策略实现 ====================
    
    def _detect_by_contour(self, image: np.ndarray) -> List[BoundingBox]:
        """
        基于轮廓检测的方法
        
        适用于：卡片有明确边框的页面
        
        流程：灰度 → 边缘检测 → 膨胀连通 → 查找轮廓 → 筛选矩形
        """
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # Canny边缘检测
        edges = cv2.Canny(gray, 30, 120)
        
        # 膨胀操作使边缘更连续
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        dilated = cv2.dilate(edges, kernel, iterations=3)
        
        # 查找轮廓
        # cv2.findContours 返回: (contours, hierarchy)
        # RETR_EXTERNAL: 只查找外轮廓
        # CHAIN_APPROX_SIMPLE: 压缩水平/垂直/对角线段
        contours, _ = cv2.findContours(
            dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        
        bboxes = []
        for contour in contours:
            # 计算轮廓的外接矩形
            x, y, w, h = cv2.boundingRect(contour)
            
            # 计算轮廓面积用于置信度估算
            area = cv2.contourArea(contour)
            rect_area = w * h
            # 填充率 = 轮廓面积 / 外接矩形面积
            fill_ratio = area / rect_area if rect_area > 0 else 0
            
            bbox = BoundingBox(
                x1=x, y1=y,
                x2=x + w, y2=y + h,
                confidence=fill_ratio,
                label="card_contour"
            )
            bboxes.append(bbox)
        
        return bboxes
    
    def _detect_by_edge(self, image: np.ndarray) -> List[BoundingBox]:
        """
        基于边缘检测 + 霍夫变换的方法
        
        适用于：卡片之间有水平/垂直分割线的页面
        
        流程：灰度 → Canny → 霍夫线检测 → 构建网格 → 划分区域
        """
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        h_img, w_img = gray.shape
        
        edges = cv2.Canny(gray, 50, 150)
        
        # 霍夫线检测
        # cv2.HoughLinesP 返回: 线段端点数组 [[x1,y1,x2,y2], ...]
        lines = cv2.HoughLinesP(
            edges, rho=1, theta=np.pi/180, 
            threshold=100, minLineLength=w_img//4, maxLineGap=20
        )
        
        if lines is None:
            logger.debug("边缘检测：未找到足够的线段，回退到轮廓检测")
            return self._detect_by_contour(image)
        
        # 分离水平线和垂直线
        h_lines = []  # y坐标
        v_lines = []  # x坐标
        
        for line in lines:
            x1, y1, x2, y2 = line[0]
            angle = abs(np.arctan2(y2 - y1, x2 - x1) * 180 / np.pi)
            
            if angle < 10:  # 近水平线
                h_lines.append((y1 + y2) // 2)
            elif angle > 80:  # 近垂直线
                v_lines.append((x1 + x2) // 2)
        
        if not h_lines or not v_lines:
            logger.debug("边缘检测：线段不足以构建网格，回退到轮廓检测")
            return self._detect_by_contour(image)
        
        # 去重和排序
        h_lines = sorted(set(self._cluster_values(h_lines, threshold=20)))
        v_lines = sorted(set(self._cluster_values(v_lines, threshold=20)))
        
        # 添加图像边界
        h_lines = [0] + h_lines + [h_img]
        v_lines = [0] + v_lines + [w_img]
        
        # 构建网格区域
        bboxes = []
        for i in range(len(h_lines) - 1):
            for j in range(len(v_lines) - 1):
                bbox = BoundingBox(
                    x1=v_lines[j], y1=h_lines[i],
                    x2=v_lines[j + 1], y2=h_lines[i + 1],
                    confidence=0.7,
                    label="card_edge"
                )
                bboxes.append(bbox)
        
        return bboxes
    
    def _detect_by_color(self, image: np.ndarray) -> List[BoundingBox]:
        """
        基于颜色分割的方法
        
        适用于：卡片与背景色有明显差异的页面
        （如白色卡片在灰色背景上）
        
        流程：转HSV → 提取白色/浅色区域 → 形态学处理 → 查找轮廓
        """
        # 转HSV色彩空间
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        
        # 提取白色/浅色区域
        # 白色区域在HSV中: H任意, S较低, V较高
        lower_white = np.array([0, 0, 180])
        upper_white = np.array([180, 60, 255])
        mask = cv2.inRange(hsv, lower_white, upper_white)
        
        # 形态学操作：闭运算（填充卡片内的小缺口）
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 15))
        closed = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
        
        # 开运算（去除噪声）
        opened = cv2.morphologyEx(closed, cv2.MORPH_OPEN, kernel, iterations=1)
        
        # 查找轮廓
        contours, _ = cv2.findContours(
            opened, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        
        bboxes = []
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            area = cv2.contourArea(contour)
            rect_area = w * h
            fill_ratio = area / rect_area if rect_area > 0 else 0
            
            bbox = BoundingBox(
                x1=x, y1=y,
                x2=x + w, y2=y + h,
                confidence=fill_ratio,
                label="card_color"
            )
            bboxes.append(bbox)
        
        return bboxes
    
    def _detect_by_grid(self, image: np.ndarray) -> List[BoundingBox]:
        """
        基于网格分割的方法（京东搜索结果页专用）
        
        京东搜索结果通常为固定列数的网格布局。
        通过检测水平分割线来确定行边界，再按列数均分。
        
        流程：灰度 → 水平投影 → 检测行边界 → 按列数均分
        """
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        h_img, w_img = gray.shape
        
        # 计算水平投影（每行像素亮度之和）
        # 行间分割线通常是亮度骤变位置
        row_projection = np.mean(gray, axis=1)
        
        # 使用差分检测变化点
        diff = np.abs(np.diff(row_projection))
        threshold = np.mean(diff) + 2 * np.std(diff)
        
        # 找到分割线位置
        split_rows = [0]
        last_split = 0
        min_row_height = self.config.min_card_height
        
        for i in range(len(diff)):
            if diff[i] > threshold and (i - last_split) > min_row_height:
                split_rows.append(i)
                last_split = i
        split_rows.append(h_img)
        
        # 假设京东搜索页通常为4-5列布局（可在config中配置）
        # 通过垂直投影进一步确认列分割
        col_projection = np.mean(gray, axis=0)
        col_diff = np.abs(np.diff(col_projection))
        col_threshold = np.mean(col_diff) + 2 * np.std(col_diff)
        
        split_cols = [0]
        last_split_col = 0
        min_col_width = self.config.min_card_width
        
        for i in range(len(col_diff)):
            if col_diff[i] > col_threshold and (i - last_split_col) > min_col_width:
                split_cols.append(i)
                last_split_col = i
        split_cols.append(w_img)
        
        # 构建网格
        bboxes = []
        for i in range(len(split_rows) - 1):
            for j in range(len(split_cols) - 1):
                bbox = BoundingBox(
                    x1=split_cols[j], y1=split_rows[i],
                    x2=split_cols[j + 1], y2=split_rows[i + 1],
                    confidence=0.6,
                    label="card_grid"
                )
                bboxes.append(bbox)
        
        return bboxes
    
    # ==================== 卡片内部区域分割 ====================
    
    def segment_card_regions(self, 
                             card_image: np.ndarray
                             ) -> List[Tuple[BoundingBox, RegionType]]:
        """
        对单个商品卡片内部进行区域分割
        将卡片分为：商品图片区域、文字区域、其它区域
        
        args:
            card_image: 单个商品卡片的图像 (BGR)
            
        Returns:
            List[Tuple[BoundingBox, RegionType]]: 
                每个元素为 (区域边界框, 区域类型) 的二元组
        """
        h, w = card_image.shape[:2]
        regions = []
        
        gray = cv2.cvtColor(card_image, cv2.COLOR_BGR2GRAY)
        
        # ---- 策略1：基于位置启发式 ----
        # 电商卡片通常布局为：
        #   上半部分 = 商品图片 (约占60%高度)
        #   下半部分 = 文字信息 (约占40%高度)
        
        # 通过边缘密度判断图片和文字区域的分界线
        edges = cv2.Canny(gray, 50, 150)
        
        # 逐行计算边缘密度
        row_density = np.mean(edges > 0, axis=1)
        
        # 查找从"低密度"到"高密度"的转换点（图片→文字的分界）
        # 图片区域通常边缘较少而均匀，文字区域边缘密集
        split_y = h // 2  # 默认分界线在中间
        
        # 使用滑动窗口平滑密度曲线
        window = 20
        if len(row_density) > window * 2:
            smoothed = np.convolve(row_density, np.ones(window)/window, mode='valid')
            
            # 找到密度变化最大的位置
            density_diff = np.diff(smoothed)
            # 在图像中部附近寻找分界线 (上30%到下30%之间)
            search_start = max(0, len(density_diff) // 3)
            search_end = min(len(density_diff), len(density_diff) * 2 // 3)
            
            if search_start < search_end:
                search_region = density_diff[search_start:search_end]
                if len(search_region) > 0:
                    max_change_idx = np.argmax(np.abs(search_region))
                    split_y = search_start + max_change_idx + window // 2
        
        # 图片区域（上半部分）
        regions.append((
            BoundingBox(x1=0, y1=0, x2=w, y2=split_y,
                       confidence=0.8, label="image"),
            RegionType.IMAGE
        ))
        
        # 文字区域（下半部分）
        regions.append((
            BoundingBox(x1=0, y1=split_y, x2=w, y2=h,
                       confidence=0.8, label="text"),
            RegionType.TEXT
        ))
        
        # ---- 策略2：在文字区域中进一步区分TITLE和PRICE ----
        text_region_img = gray[split_y:h, :]
        text_h = h - split_y
        
        if text_h > 30:
            # 价格通常在文字区域的底部，用更大字号显示
            # 通过检测红色区域（京东价格通常为红色）来定位价格
            text_region_color = card_image[split_y:h, :]
            hsv = cv2.cvtColor(text_region_color, cv2.COLOR_BGR2HSV)
            
            # 红色范围在HSV中
            lower_red1 = np.array([0, 100, 100])
            upper_red1 = np.array([10, 255, 255])
            lower_red2 = np.array([160, 100, 100])
            upper_red2 = np.array([180, 255, 255])
            
            mask_red = cv2.inRange(hsv, lower_red1, upper_red1) | \
                       cv2.inRange(hsv, lower_red2, upper_red2)
            
            # 查找红色区域
            red_contours, _ = cv2.findContours(
                mask_red, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
            )
            
            for contour in red_contours:
                x, y, rw, rh = cv2.boundingRect(contour)
                if rw > 20 and rh > 10:  # 最小尺寸过滤
                    regions.append((
                        BoundingBox(
                            x1=x, y1=split_y + y,
                            x2=x + rw, y2=split_y + y + rh,
                            confidence=0.9, label="price"
                        ),
                        RegionType.PRICE
                    ))
        
        logger.debug(f"卡片区域分割完成，分为 {len(regions)} 个子区域")
        return regions
    
    # ==================== 过滤与去重 ====================
    
    def _filter_bboxes(self, bboxes: List[BoundingBox]) -> List[BoundingBox]:
        """
        根据配置的尺寸范围过滤边界框
        
        Args:
            bboxes: 候选边界框列表
            
        Returns:
            List[BoundingBox]: 过滤后的边界框列表
        """
        filtered = []
        min_w = self.config.min_card_width
        min_h = self.config.min_card_height
        max_w = self.config.max_card_width
        max_h = self.config.max_card_height
        ratio_min, ratio_max = self.config.card_aspect_ratio_range
        
        for bbox in bboxes:
            w, h = bbox.width, bbox.height
            
            # 尺寸过滤
            if w < min_w or h < min_h:
                continue
            if w > max_w or h > max_h:
                continue
            
            # 宽高比过滤
            ratio = w / h if h > 0 else 0
            if ratio < ratio_min or ratio > ratio_max:
                continue
            
            filtered.append(bbox)
        
        return filtered
    
    def _non_max_suppression(self, 
                              bboxes: List[BoundingBox],
                              iou_threshold: Optional[float] = None
                              ) -> List[BoundingBox]:
        """
        非极大值抑制(NMS)去除重叠的边界框
        
        Args:
            bboxes: 候选边界框列表
            iou_threshold: IoU阈值，超过此值则认为重叠
            
        Returns:
            List[BoundingBox]: 去重后的边界框列表
        """
        if not bboxes:
            return []
        
        iou_threshold = iou_threshold or self.config.iou_threshold
        
        # 按置信度降序排列
        sorted_bboxes = sorted(bboxes, key=lambda b: b.confidence, reverse=True)
        
        selected = []
        suppressed = set()
        
        for i, bbox_i in enumerate(sorted_bboxes):
            if i in suppressed:
                continue
            
            selected.append(bbox_i)
            
            # 抑制与当前框重叠过多的框
            for j in range(i + 1, len(sorted_bboxes)):
                if j in suppressed:
                    continue
                if bbox_i.overlap_ratio(sorted_bboxes[j]) > iou_threshold:
                    suppressed.add(j)
        
        return selected
    
    # ==================== 泛用API ====================
    
    def locate_element(self,
                       image: np.ndarray,
                       template: np.ndarray,
                       threshold: float = 0.8,
                       multi_match: bool = False
                       ) -> List[BoundingBox]:
        """
        在图像中定位指定模板元素（模板匹配）
        
        这是一个泛用API，可用于定位页面上的任意视觉元素
        （按钮、图标、特定UI组件等）。
        
        Args:
            image: 页面截图 (BGR)
            template: 模板图像 (BGR)
            threshold: 匹配阈值 (0.0-1.0)
            multi_match: 是否返回多个匹配
            
        Returns:
            List[BoundingBox]: 匹配到的元素位置列表
        """
        # 转灰度
        if len(image.shape) == 3:
            img_gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            img_gray = image
            
        if len(template.shape) == 3:
            tpl_gray = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
        else:
            tpl_gray = template
        
        th, tw = tpl_gray.shape[:2]
        
        # cv2.matchTemplate: 模板匹配
        # TM_CCOEFF_NORMED: 归一化互相关系数，结果范围[-1, 1]
        result = cv2.matchTemplate(img_gray, tpl_gray, cv2.TM_CCOEFF_NORMED)
        
        bboxes = []
        
        if multi_match:
            # 找所有超过阈值的匹配位置
            locations = np.where(result >= threshold)
            
            for pt in zip(*locations[::-1]):  # 注意: np.where返回(y,x)
                bbox = BoundingBox(
                    x1=pt[0], y1=pt[1],
                    x2=pt[0] + tw, y2=pt[1] + th,
                    confidence=float(result[pt[1], pt[0]]),
                    label="template_match"
                )
                bboxes.append(bbox)
            
            # NMS去重
            bboxes = self._non_max_suppression(bboxes, iou_threshold=0.5)
        else:
            # 只返回最佳匹配
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
            
            if max_val >= threshold:
                bbox = BoundingBox(
                    x1=max_loc[0], y1=max_loc[1],
                    x2=max_loc[0] + tw, y2=max_loc[1] + th,
                    confidence=float(max_val),
                    label="template_match"
                )
                bboxes.append(bbox)
        
        logger.debug(f"模板匹配: 找到 {len(bboxes)} 个匹配 "
                     f"(threshold={threshold})")
        return bboxes
    
    def locate_colored_region(self,
                              image: np.ndarray,
                              lower_hsv: Tuple[int, int, int],
                              upper_hsv: Tuple[int, int, int],
                              min_area: int = 100
                              ) -> List[BoundingBox]:
        """
        在图像中定位指定颜色范围的区域
        
        泛用API，可用于定位特定颜色的UI元素。
        
        Args:
            image: 页面截图 (BGR)
            lower_hsv: HSV颜色下界 (H, S, V)
            upper_hsv: HSV颜色上界 (H, S, V)
            min_area: 最小区域面积
            
        Returns:
            List[BoundingBox]: 找到的彩色区域列表
        """
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, np.array(lower_hsv), np.array(upper_hsv))
        
        # 形态学处理
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        
        contours, _ = cv2.findContours(
            mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        
        bboxes = []
        for contour in contours:
            area = cv2.contourArea(contour)
            if area < min_area:
                continue
            
            x, y, w, h = cv2.boundingRect(contour)
            bbox = BoundingBox(
                x1=x, y1=y,
                x2=x + w, y2=y + h,
                confidence=min(1.0, area / 10000),
                label="color_region"
            )
            bboxes.append(bbox)
        
        return bboxes
    
    # ==================== 工具方法 ====================
    
    @staticmethod
    def _cluster_values(values: List[int], threshold: int = 20) -> List[int]:
        """
        对一组数值进行聚类（合并相近的值）
        
        Args:
            values: 数值列表
            threshold: 聚类距离阈值
            
        Returns:
            List[int]: 聚类后的代表值列表
        """
        if not values:
            return []
        
        sorted_vals = sorted(values)
        clusters = [[sorted_vals[0]]]
        
        for v in sorted_vals[1:]:
            if v - clusters[-1][-1] <= threshold:
                clusters[-1].append(v)
            else:
                clusters.append([v])
        
        # 返回每个簇的均值
        return [int(np.mean(c)) for c in clusters]
