# [file name]: src/database/web_app.py
from flask import Flask, render_template, request, jsonify, send_file, redirect
import pandas as pd
import plotly.express as px
import plotly.io as pio
import io
import json
from src.database.database import ProductDatabase
from src.database.visualization import register_visualization

app = Flask(__name__)

# 全局数据库管理器
from src.config.manager import init_config, get_config

init_config()
db = ProductDatabase(get_config())

# 注册可视化蓝图
app = register_visualization(app)

@app.route('/')
def index():
    """主页面"""
    stats = db.get_stats()
    categories = db.get_categories()
    
    # 获取最近添加的商品
    recent_products = db.search(limit=10)
    
    # 获取价格变化最大的商品
    all_products = db.search(limit=100)
    products_with_history = []
    
    for product in all_products:
        history = db.get_price_history(product['id'])
        if len(history) >= 2:
            latest_price = history[0]['price']
            oldest_price = history[-1]['price']
            price_change = latest_price - oldest_price
            percent_change = (price_change / oldest_price * 100) if oldest_price > 0 else 0
            
            product['price_change'] = price_change
            product['percent_change'] = percent_change
            products_with_history.append(product)
    
    # 按价格变化排序
    top_gainers = sorted(products_with_history, key=lambda x: x['price_change'], reverse=True)[:5]
    top_losers = sorted(products_with_history, key=lambda x: x['price_change'])[:5]
    
    return render_template('index.html', 
                         stats=stats, 
                         categories=categories,
                         recent_products=recent_products,
                         top_gainers=top_gainers,
                         top_losers=top_losers)

@app.route('/trends')
def trends():
    """跳转到价格走势页面"""
    return redirect('/viz/price_trends')

@app.route('/api/products', methods=['GET'])
def get_products():
    """获取商品数据API"""
    name = request.args.get('name', '')
    category = request.args.get('category', '')
    min_price = request.args.get('min_price', type=float)
    max_price = request.args.get('max_price', type=float)
    sort_by = request.args.get('sort_by', 'created_at')
    sort_order = request.args.get('sort_order', 'desc')
    limit = request.args.get('limit', 100, type=int)
    
    # 获取所有产品
    products = db.search(
        name=name,
        category=category,
        min_price=min_price,
        max_price=max_price,
        limit=limit * 2  # 获取更多以便排序
    )
    
    # 手动排序（因为数据库查询不支持复杂排序）
    if sort_by == 'price':
        products.sort(key=lambda x: x.get('price', 0), reverse=(sort_order == 'desc'))
    elif sort_by == 'name':
        products.sort(key=lambda x: x.get('name', ''), reverse=(sort_order == 'desc'))
    else:  # created_at
        products.sort(key=lambda x: x.get('created_at', ''), reverse=(sort_order == 'desc'))
    
    return jsonify(products[:limit])

@app.route('/api/add_product', methods=['POST'])
def add_product():
    """添加商品API"""
    data = request.json
    
    try:
        product_id = db.insert(
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
        
        try:
            with open(temp_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if isinstance(data, dict):
                data = [data]
            
            # 批量导入
            success_count = 0
            for item in data:
                try:
                    db.insert(
                        name=item.get('name', ''),
                        category=item.get('category', ''),
                        price=float(item.get('price', 0)),
                        source_url=item.get('source_url', '')
                    )
                    success_count += 1
                except:
                    continue
            
            return jsonify({
                'success': True, 
                'message': f'导入成功 {success_count} 条记录'
            })
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 400
        finally:
            # 清理临时文件
            import os
            if os.path.exists(temp_path):
                os.remove(temp_path)
    
    return jsonify({'success': False, 'error': '仅支持JSON文件'}), 400

@app.route('/api/export')
def export_data():
    """导出数据API"""
    format_type = request.args.get('format', 'json')
    
    if format_type == 'json':
        return jsonify(db.search(limit=10000))
    
    elif format_type == 'csv':
        products = db.search(limit=10000)
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
        products = db.search(limit=10000)
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
    stats = db.get_stats()
    
    # 获取分类统计
    categories = db.get_categories()
    category_stats = []
    
    for category in categories:
        products = db.search(category=category, limit=1000)
        if products:
            avg_price = sum(p['price'] for p in products) / len(products)
            category_stats.append({
                'category': category,
                'count': len(products),
                'avg_price': avg_price
            })
    
    stats['category_stats'] = category_stats
    return jsonify(stats)

@app.route('/api/chart')
def get_chart():
    """生成图表API"""
    chart_type = request.args.get('type', 'category')
    
    products = db.search(limit=1000)
    df = pd.DataFrame(products)
    
    if len(df) > 0:
        if chart_type == 'category':
            # 按分类统计商品数量
            category_counts = df['category'].value_counts().reset_index()
            category_counts.columns = ['category', 'count']
            
            fig = px.bar(category_counts, x='category', y='count', 
                        title='商品分类分布', color='category')
            
        elif chart_type == 'price_distribution':
            # 价格分布直方图
            fig = px.histogram(df, x='price', title='价格分布', 
                             nbins=20, color_discrete_sequence=['#1f77b4'])
            
        elif chart_type == 'price_over_time':
            # 价格随时间变化（需要时间数据）
            df['created_at'] = pd.to_datetime(df['created_at'])
            fig = px.scatter(df, x='created_at', y='price', 
                           title='价格随时间变化', color='category',
                           hover_data=['name'])
            
        else:
            return jsonify({'error': '不支持的图表类型'}), 400
        
        return jsonify({
            'success': True,
            'chart_html': pio.to_json(fig)
        })
    
    return jsonify({'error': '没有足够的数据生成图表'}), 400

@app.route('/api/import_csv', methods=['POST'])
def import_csv():
    """导入CSV文件API"""
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': '没有文件'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'error': '未选择文件'}), 400
    
    if file.filename.endswith('.csv'):
        # 保存临时文件
        temp_path = f"temp_{file.filename}"
        file.save(temp_path)
        
        try:
            # 使用数据处理器处理CSV
            from ..modules.data_processor import CSVDataProcessor
            processor = CSVDataProcessor("products.db")
            
            # 处理CSV并导入数据库
            result = processor.import_csv_to_db(temp_path, "内存条")
            
            return jsonify(result)
            
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 400
        finally:
            # 清理临时文件
            import os
            if os.path.exists(temp_path):
                os.remove(temp_path)
    
    return jsonify({'success': False, 'error': '仅支持CSV文件'}), 400

@app.route('/api/recent_changes')
def get_recent_changes():
    """获取最近价格变化API"""
    days = request.args.get('days', 7, type=int)
    
    # 获取所有商品
    products = db.search(limit=100)
    
    changes = []
    for product in products:
        history = db.get_price_history(product['id'])
        if len(history) >= 2:
            # 获取最近days天的价格
            recent_history = history[:min(days, len(history))]
            if len(recent_history) >= 2:
                latest = recent_history[0]['price']
                oldest = recent_history[-1]['price']
                change = latest - oldest
                percent = (change / oldest * 100) if oldest > 0 else 0
                
                changes.append({
                    'id': product['id'],
                    'name': product['name'],
                    'category': product['category'],
                    'current_price': latest,
                    'old_price': oldest,
                    'change': change,
                    'percent_change': percent,
                    'history_count': len(history)
                })
    
    # 按变化百分比排序
    changes.sort(key=lambda x: abs(x['percent_change']), reverse=True)
    
    return jsonify({
        'success': True,
        'days': days,
        'changes': changes[:20]  # 返回前20个
    })

if __name__ == '__main__':
    app.run(debug=True, port=5050)