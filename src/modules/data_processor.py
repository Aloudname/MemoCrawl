"""
data_processor.py
CSV数据处理模块
清洗、转换、导入CSV数据到数据库
"""

import os, re
import logging
import pandas as pd
from munch import Munch
from datetime import datetime
from typing import List, Dict, Any

from src.database.database import ProductDatabase

class CSVDataProcessor:
    """CSV数据处理器"""
    
    def __init__(self, config: Munch = None):
        """
        初始化数据处理器
        
        Args:
            db_path: 数据库文件路径
            config: 配置字典
        """

        self.config = config
        self.logger = logging.getLogger(__name__)
        self.db = ProductDatabase(self.config)
    
    def do_price(self, price_str: str) -> float:
        """
        清洗价格字符串，转换为浮点数
        
        Args:
            price_str: 价格字符串，如 "¥ 3199", "¥ 3399.00"
        Returns:
            清洗后的价格浮点数
        """
        if not price_str or pd.isna(price_str):
            raise ValueError(f"价格字符串为空!")
            
        # 移除货币符号、空格、逗号
        cleaned = str(price_str).strip()
        cleaned = re.sub(r'[¥$€￡,，\s]', '', cleaned)
        
        # 提取数字部分
        match = re.search(r'(\d+\.?\d*)', cleaned)
        if match:
            try:
                return float(match.group(1))
            except (ValueError, TypeError):
                self.logger.warning(f"价格转换失败: {price_str}")
                return 0.0
        return 0.0
    
    def do_brand(self, product_name: str) -> str:
        """
        从商品名中提取品牌
        
        Args:
            product_name: 商品名称
            
        Returns:
            品牌名称
        """
        if not product_name or pd.isna(product_name):
            return "未知"
            
        # 常见品牌关键词
        brands = self.config.data_processing.brands
        
        product_name = str(product_name)
        for brand in brands:
            if brand in product_name:
                return brand
        return "其他"
    
    def do_specs(self, product_name: str) -> Dict[str, str]:
        """
        从商品名中提取规格信息
        
        Args:
            product_name: 商品名称
            
        Returns:
            规格字典
        """
        if not product_name or pd.isna(product_name):
            return {}
            
        specs = {}
        name = str(product_name)
        
        # 提取容量
        capacity_match = re.search(r'(\d+)\s*[Gg][Bb]?', name)
        if capacity_match:
            specs['capacity'] = f"{capacity_match.group(1)}GB"
        
        # 提取频率
        freq_match = re.search(r'DDR4\s*(\d{4,5})', name) \
                    or re.search(r'DDR5\s*(\d{4,5})', name) \
                    or re.search(r'(\d{4})\s*[Mm]?[Hh]z', name)
                    
        if freq_match:
            specs['frequency'] = f"{freq_match.group(1)}MHz"
        
        # 提取类型
        if any(keyword in name for keyword in ["笔记本", "laptop", "LAPTOP"]):
            specs['type'] = "笔记本内存"
        elif any(keyword in name for keyword in ["台式", "desktop", "DESKTOP"]):
            specs['type'] = "台式机内存"
        else:
            specs['type'] = "内存条"
        
        return specs
    
    def process(self, csv_path: str, category: str = "内存条") -> List[Dict[str, Any]]:
        """
        处理CSV文件，返回清洗后的数据
        
        Args:
            csv_path: CSV文件路径
            category: 商品分类
            
        Returns:
            清洗后的商品数据列表
        """
        try:
            df = pd.read_csv(csv_path, encoding='utf-8')
            self.logger.info(f"成功读取CSV文件: {csv_path}, 共 {len(df)} 条记录")
            
            # 检查必要列
            required_columns = ['商品名', '价格']
            missing_cols = [col for col in required_columns if col not in df.columns]
            if missing_cols:
                raise ValueError(f"CSV文件缺少必要列: {missing_cols}")
            
            # 清洗转换
            processed_data = []
            for _, row in df.iterrows():
                try:
                    product_name = str(row['商品名']).strip()
                    
                    price = self.do_price(row['价格'])
                    
                    brand = self.do_brand(product_name)
                    specs = self.do_specs(product_name)
                    
                    description = row.get('概述', '') if '概述' in df.columns else ''
                    source = row.get('来源', '') if '来源' in df.columns else ''
                    
                    # 创建规格字符串
                    spec_str = ", ".join([f"{k}:{v}" for k, v in specs.items()])
                    
                    # 生成完整商品名
                    full_name = f"{brand} {product_name}"
                    
                    # 构建商品数据
                    product_data = {
                        'name': full_name,
                        'original_name': product_name,
                        'category': category,
                        'brand': brand,
                        'price': price,
                        'specifications': spec_str,
                        'description': str(description) if not pd.isna(description) else '',
                        'source': str(source) if not pd.isna(source) else '京东',
                        'source_url': '',
                        'scraped_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    }
                    
                    # 只处理价格大于0的商品
                    if price > 0:
                        processed_data.append(product_data)
                    
                except Exception as e:
                    self.logger.warning(f"处理商品行失败: {row.get('商品名', 'Unknown')}, 错误: {e}")
                    continue
            
            self.logger.info(f"数据处理完成，有效记录: {len(processed_data)} 条")
            return processed_data
            
        except FileNotFoundError:
            self.logger.error(f"CSV文件不存在: {csv_path}")
            return []
        except pd.errors.EmptyDataError:
            self.logger.error("CSV文件为空")
            return []
        except Exception as e:
            self.logger.error(f"处理CSV文件失败: {e}")
            return []
    
    def to_database(self,
                    processed_data: List[Dict[str, Any]],
                    update_existing: bool = True) -> Dict[str, int]:
        """
        将处理后的数据保存到数据库
        
        Args:
            processed_data: 处理后的商品数据列表
            update_existing: 是否更新已存在的商品
            
        Returns:
            保存结果统计
        """
        stats = {
            'total': len(processed_data),
            'saved': 0,
            'updated': 0,
            'failed': 0
        }
        
        for product in processed_data:
            try:
                # 检查是否已存在同名商品
                existing = self.db.search(
                    name=product['name'],
                    category=product['category'],
                    limit=1
                )
                
                if existing and update_existing:
                    # 更新现有商品价格
                    product_id = existing[0]['id']
                    self.db.insert(
                        name=product['name'],
                        category=product['category'],
                        price=product['price'],
                        source_url=product.get('source_url', '')
                    )
                    stats['updated'] += 1
                else:
                    # 插入新商品
                    self.db.insert(
                        name=product['name'],
                        category=product['category'],
                        price=product['price'],
                        source_url=product.get('source_url', '')
                    )
                    stats['saved'] += 1
                    
            except Exception as e:
                self.logger.error(f"保存商品到数据库失败: {product.get('name', 'Unknown')}, 错误: {e}")
                stats['failed'] += 1
        
        self.logger.info(f"数据库保存完成: 总计{stats['total']}, 新增{stats['saved']}, "
                        f"更新{stats['updated']}, 失败{stats['failed']}")
        return stats
    
    def import2db(self, csv_path: str,
                  category: str = "内存条") -> Dict[str, Any]:
        """
        完整的CSV导入流程
        
        Args:
            csv_path: CSV文件路径
            category: 商品分类
            
        Returns:
            导入结果
        """
        result = {
            'success': False,
            'message': '',
            'stats': {},
            'data': []
        }
        
        try:
            processed_data = self.process(csv_path, category)
            
            if not processed_data:
                result['message'] = '没有有效数据可以导入'
                return result
            
            save_stats = self.to_database(processed_data)
            db_stats = self.db.get_stats()
            
            result.update({
                'success': True,
                'message': f'成功导入 {len(processed_data)} 条商品记录',
                'stats': {
                    'csv_records': len(processed_data),
                    'db_save_stats': save_stats,
                    'database_stats': db_stats
                },
                'data': processed_data[:10]  # 返回前10条作样本
            })
            
        except Exception as e:
            result['message'] = f'导入失败: {str(e)}'
            self.logger.error(f"CSV导入失败: {e}")
        
        return result
    
    def get_price_history_chart(self, product_name: str = None, 
                                    category: str = None, 
                                    days: int = 30) -> Dict[str, Any]:
        """
        获取价格历史图表数据
        
        Args:
            product_name: 商品名称
            category: 商品分类
            days: 查询天数
            
        Returns:
            图表数据
        """
        try:
            # 获取商品列表
            products = self.db.search(
                name=product_name,
                category=category,
                limit=50
            )
            
            chart_data = {
                'products': [],
                'price_history': [],
                'trends': []
            }
            
            for product in products:
                # 获取价格历史
                price_history = self.db.get_price_history(product['id'])
                
                if price_history:
                    # 格式化价格历史数据
                    formatted_history = [
                        {
                            'date': record['recorded_at'].split()[0] if 'recorded_at' in record else '',
                            'price': record['price'],
                            'product_id': product['id'],
                            'product_name': product['name']
                        }
                        for record in price_history[:days]  # 限制天数
                    ]
                    
                    chart_data['products'].append({
                        'id': product['id'],
                        'name': product['name'],
                        'category': product['category'],
                        'current_price': product['price'],
                        'history_count': len(price_history)
                    })
                    
                    chart_data['price_history'].extend(formatted_history)
            
            return chart_data
            
        except Exception as e:
            self.logger.error(f"获取价格历史图表数据失败: {e}")
            return {'products': [], 'price_history': [], 'trends': []}
    
    def cleanup_old_csv(self, csv_path: str, keep_latest: int = 5):
        """
        清理旧的CSV文件，只保留最新的几个
        
        Args:
            csv_path: CSV文件路径模式（可包含通配符）
            keep_latest: 保留最新的文件数量
        """
        try:
            import glob
            from pathlib import Path
            
            # 获取所有匹配的CSV文件
            csv_files = glob.glob(csv_path)
            
            if len(csv_files) > keep_latest:
                # 按修改时间排序
                csv_files.sort(key=os.path.getmtime, reverse=True)
                
                # 删除旧文件
                for old_file in csv_files[keep_latest:]:
                    try:
                        os.remove(old_file)
                        self.logger.info(f"删除旧CSV文件: {old_file}")
                    except Exception as e:
                        self.logger.warning(f"删除文件失败 {old_file}: {e}")
                
        except Exception as e:
            self.logger.error(f"清理CSV文件失败: {e}")

if __name__ == "__main__":
    # 测试代码
    import logging
    logging.basicConfig(level=logging.INFO)
    
    processor = CSVDataProcessor("products.db")
    
    # 测试处理CSV文件
    test_csv = "data.csv"
    if os.path.exists(test_csv):
        result = processor.import2db(test_csv, "内存条")
        print(f"导入结果: {result}")
    else:
        print(f"测试CSV文件不存在: {test_csv}")
