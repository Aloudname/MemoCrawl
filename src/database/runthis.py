from database import ProductDatabase
from web_app import app

# 示例 1: 基本使用
class run_db:
    def __init__(self, db_path: str = "products.db"):
        self.db = ProductDatabase(db_path)
    
    def create_db(self, db_path: str = "products.db"):
        self.db = ProductDatabase(db_path)
    
    def insert_data(self, data: list[dict]):
        """
        插入示例数据格式:
                data = [
            {
                "name": "TestA",
                "category": "内存条",
                "price": 7999.00,
                "source_url": "https://example.com/testA"
            },
            {
                "name": "TestB",
                "category": "笔记本电脑",
                "price": 5999.00,
                "source_url": "https://example.com/testB"
            }]
        """
        self.db.insert_from_json(data)
    
    def inquire(self, category=None, **kwargs):
        if category:
            kwargs['category'] = category
            
        items = self.db.search_products(**kwargs)
        for item in items:
            print(f"{item['name']} - ¥{item['price']}")
        # 获取统计信息
        stats = self.db.get_statistics()
        print(f"\n数据库统计:")
        print(f"总商品数: {stats['total_products']}")
        print(f"分类数量: {stats['total_categories']}")
        print(f"平均价格: {stats['avg_price']:.2f}")
    
    def export(self, exp_path: str = "db_products.json"):
        self.db.export_to_json(exp_path)
        print(f"数据已导出到 {exp_path}")

    def backup(self):
        self.db.backup_database()
        print("数据库已备份")
    
    def close(self):
        self.db.close()
        
    def web(self, port = 5050):
        app.run(debug=True, port = port)
        print(f"访问 http://localhost:{port} 使用数据库Web界面")



if __name__ == "__main__":
    
    data = [
    {
        "name": "TestA",
        "category": "内存条",
        "price": 7999.00,
        "source_url": "https://example.com/testA"
    },
    {
        "name": "TestB",
        "category": "笔记本电脑",
        "price": 5999.00,
        "source_url": "https://example.com/testB"
    }]
    db = run_db()
    db.insert_data(data)
    db.close()
    db.web()