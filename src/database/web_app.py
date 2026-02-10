from flask import Flask, render_template, request, jsonify, send_file
import pandas as pd
import plotly.express as px
import plotly.io as pio
import io
from database import ProductDatabase

app = Flask(__name__)

# 全局数据库管理器
db = ProductDatabase("products.db")

@app.route('/')
def index():
    """主页面"""
    stats = db.get_statistics()
    categories = db.get_categories()
    return render_template('index.html', stats=stats, categories=categories)

@app.route('/api/products', methods=['GET'])
def get_products():
    """获取商品数据API"""
    name = request.args.get('name', '')
    category = request.args.get('category', '')
    min_price = request.args.get('min_price', type=float)
    max_price = request.args.get('max_price', type=float)
    
    products = db.search_products(
        name=name,
        category=category,
        min_price=min_price,
        max_price=max_price,
        limit=100
    )
    
    return jsonify(products)

@app.route('/api/add_product', methods=['POST'])
def add_product():
    """添加商品API"""
    data = request.json
    
    try:
        product_id = db.insert_product(
            name=data['name'],
            category=data['category'],
            price=float(data['price']),
            source_url=data.get('source_url', '')
        )
        
        return jsonify({'success': True, 'id': product_id})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/import', methods=['POST'])
def import_json():
    """导入JSON文件API"""
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': '没有文件'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'error': '未选择文件'}), 400
    
    if file.filename.endswith('.json'):
        # 保存临时文件并导入
        temp_path = f"temp_{file.filename}"
        file.save(temp_path)
        db.import_json_file(temp_path)
        
        return jsonify({'success': True, 'message': '导入成功'})
    
    return jsonify({'success': False, 'error': '仅支持JSON文件'}), 400

@app.route('/api/export')
def export_data():
    """导出数据API"""
    format_type = request.args.get('format', 'json')
    
    if format_type == 'json':
        return jsonify(db.search_products(limit=10000))
    
    elif format_type == 'csv':
        products = db.search_products(limit=10000)
        df = pd.DataFrame(products)
        
        output = io.StringIO()
        df.to_csv(output, index=False)
        output.seek(0)
        
        return send_file(
            io.BytesIO(output.getvalue().encode('utf-8')),
            mimetype='text/csv',
            as_attachment=True,
            download_name='products_export.csv'
        )
    
    elif format_type == 'excel':
        products = db.search_products(limit=10000)
        df = pd.DataFrame(products)
        
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Products')
        
        output.seek(0)
        
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name='products_export.xlsx'
        )

@app.route('/api/stats')
def get_stats():
    """获取统计信息API"""
    return jsonify(db.get_statistics())

@app.route('/api/chart')
def get_chart():
    """生成图表API"""
    products = db.search_products(limit=1000)
    df = pd.DataFrame(products)
    
    if len(df) > 0:
        # 按分类统计商品数量
        category_counts = df['category'].value_counts().reset_index()
        category_counts.columns = ['category', 'count']
        
        fig = px.bar(category_counts, x='category', y='count', title='商品分类分布')
        
        # 价格分布直方图
        fig2 = px.histogram(df, x='price', title='价格分布', nbins=20)
        
        return jsonify({
            'category_chart': pio.to_json(fig),
            'price_chart': pio.to_json(fig2)
        })
    
    return jsonify({'error': '没有足够的数据生成图表'}), 400

if __name__ == '__main__':
    app.run(debug=True, port=5050)