import sqlite3
import json
import os
from typing import List, Dict, Any, Optional
from datetime import datetime

class ProductDatabase:
    def __init__(self, db_name: str = "products.db"):
        """初始化数据库连接"""
        self.db_name = db_name
        self.conn = None
        self.cursor = None
        self._initialize_database()
    
    def _initialize_database(self):
        """初始化数据库和表结构"""
        try:
            self.conn = sqlite3.connect(self.db_name, check_same_thread=False)
            self.cursor = self.conn.cursor()
            
            # 创建商品表
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS products (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    category TEXT,
                    price REAL,
                    source_url TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    -- 添加索引以提高查询性能
                    UNIQUE(name, category) ON CONFLICT REPLACE
                )
            ''')
            
            # 创建分类表（可选，用于规范化）
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS categories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    description TEXT
                )
            ''')
            
            # 创建价格历史表（记录价格变动）
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS price_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    product_id INTEGER,
                    price REAL,
                    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (product_id) REFERENCES products (id)
                )
            ''')
            
            self.conn.commit()
            print(f"数据库 '{self.db_name}' 初始化成功！")
            
        except sqlite3.Error as e:
            print(f"数据库初始化失败: {e}")
            raise
    
    def insert_product(self, name: str, category: str, price: float, 
                      source_url: Optional[str] = None) -> int:
        """插入单个商品"""
        try:
            # 先插入或获取分类
            self.cursor.execute(
                "INSERT OR IGNORE INTO categories (name) VALUES (?)",
                (category,)
            )
            
            # 插入商品
            self.cursor.execute('''
                INSERT INTO products (name, category, price, source_url, updated_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (name, category, price, source_url, datetime.now()))
            
            product_id = self.cursor.lastrowid
            
            # 记录价格历史
            self.cursor.execute('''
                INSERT INTO price_history (product_id, price)
                VALUES (?, ?)
            ''', (product_id, price))
            
            self.conn.commit()
            return product_id
            
        except sqlite3.Error as e:
            print(f"插入商品失败: {e}")
            return -1
    
    def insert_from_json(self, json_data: List[Dict[str, Any]]):
        """从JSON数据批量插入商品"""
        success_count = 0
        for item in json_data:
            try:
                name = item.get('name', '').strip()
                category = item.get('category', '').strip()
                price = item.get('price', 0)
                
                # 验证数据
                if not name or not category:
                    print(f"跳过无效数据: {item}")
                    continue
                
                # 尝试转换价格为浮点数
                try:
                    if isinstance(price, str):
                        price = float(price.replace('¥', '').replace('$', '').replace(',', ''))
                except:
                    price = 0
                
                self.insert_product(name, category, price, item.get('source_url'))
                success_count += 1
                
            except Exception as e:
                print(f"处理商品失败 {item}: {e}")
        
        print(f"批量插入完成，成功插入 {success_count} 条记录")
    
    def import_json_file(self, filepath: str):
        """从JSON文件导入数据"""
        if not os.path.exists(filepath):
            print(f"文件不存在: {filepath}")
            return
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if isinstance(data, dict):
                data = [data]  # 如果是单个对象，转换为列表
            elif not isinstance(data, list):
                print("JSON格式错误：应为列表或对象")
                return
            
            self.insert_from_json(data)
            
        except json.JSONDecodeError:
            print(f"JSON文件格式错误: {filepath}")
        except Exception as e:
            print(f"导入文件失败: {e}")
    
    def search_products(self, 
                       name: Optional[str] = None,
                       category: Optional[str] = None,
                       min_price: Optional[float] = None,
                       max_price: Optional[float] = None,
                       limit: int = 100) -> List[Dict[str, Any]]:
        """搜索商品"""
        query = "SELECT * FROM products WHERE 1=1"
        params = []
        
        if name:
            query += " AND name LIKE ?"
            params.append(f"%{name}%")
        
        if category:
            query += " AND category LIKE ?"
            params.append(f"%{category}%")
        
        if min_price is not None:
            query += " AND price >= ?"
            params.append(min_price)
        
        if max_price is not None:
            query += " AND price <= ?"
            params.append(max_price)
        
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        
        self.cursor.execute(query, params)
        columns = [desc[0] for desc in self.cursor.description]
        
        results = []
        for row in self.cursor.fetchall():
            results.append(dict(zip(columns, row)))
        
        return results
    
    def get_categories(self) -> List[str]:
        """获取所有分类"""
        self.cursor.execute("SELECT DISTINCT name FROM categories ORDER BY name")
        return [row[0] for row in self.cursor.fetchall()]
    
    def get_price_history(self, product_id: int) -> List[Dict[str, Any]]:
        """获取商品价格历史"""
        self.cursor.execute('''
            SELECT price, recorded_at 
            FROM price_history 
            WHERE product_id = ? 
            ORDER BY recorded_at DESC
        ''', (product_id,))
        
        return [
            {"price": row[0], "recorded_at": row[1]}
            for row in self.cursor.fetchall()
        ]
    
    def export_to_json(self, filepath: str = "products_export.json"):
        """导出数据到JSON文件"""
        products = self.search_products(limit=10000)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(products, f, ensure_ascii=False, indent=2)
        
        print(f"数据已导出到 {filepath}，共 {len(products)} 条记录")
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        stats = {}
        
        # 总商品数
        self.cursor.execute("SELECT COUNT(*) FROM products")
        stats['total_products'] = self.cursor.fetchone()[0]
        
        # 分类数量
        self.cursor.execute("SELECT COUNT(DISTINCT category) FROM products")
        stats['total_categories'] = self.cursor.fetchone()[0]
        
        # 平均价格
        self.cursor.execute("SELECT AVG(price) FROM products WHERE price > 0")
        stats['avg_price'] = self.cursor.fetchone()[0] or 0
        
        # 价格范围
        self.cursor.execute("SELECT MIN(price), MAX(price) FROM products WHERE price > 0")
        min_price, max_price = self.cursor.fetchone()
        stats['min_price'] = min_price or 0
        stats['max_price'] = max_price or 0
        
        return stats
    
    def backup_database(self, backup_path: str = None):
        """备份数据库"""
        if backup_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = f"backup_products_{timestamp}.db"
        
        try:
            backup_conn = sqlite3.connect(backup_path)
            self.conn.backup(backup_conn)
            backup_conn.close()
            print(f"数据库已备份到: {backup_path}")
        except Exception as e:
            print(f"备份失败: {e}")
    
    def close(self):
        """关闭数据库连接"""
        if self.conn:
            self.conn.close()
            print("数据库连接已关闭")
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()