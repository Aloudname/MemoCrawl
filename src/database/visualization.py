"""
数据可视化模块
扩展Web界面，支持价格走势图
"""
from flask import Blueprint, render_template, jsonify, request
import plotly.graph_objects as go
import plotly.io as pio
from datetime import datetime, timedelta
import json
from src.database.database import ProductDatabase

visualization_bp = Blueprint('visualization', __name__, url_prefix='/viz')
db = ProductDatabase("products.db")

@visualization_bp.route('/price_trends')
def price_trends():
    """价格走势图页面"""
    categories = db.get_categories()
    products = db.search_products(limit=50)
    
    return render_template('price_trends.html', 
                         categories=categories, 
                         products=products)

@visualization_bp.route('/api/price_history')
def get_price_history():
    """获取价格历史数据API"""
    product_id = request.args.get('product_id', type=int)
    days = request.args.get('days', 30, type=int)
    
    if not product_id:
        return jsonify({'error': '缺少product_id参数'}), 400
    
    try:
        # 获取价格历史
        history = db.get_price_history(product_id)
        
        if not history:
            return jsonify({'error': '没有找到价格历史'}), 404
        
        # 格式化为图表数据
        dates = []
        prices = []
        
        for record in history[:days]:
            dates.append(record['recorded_at'])
            prices.append(record['price'])
        
        # 计算价格变化
        if len(prices) > 1:
            price_change = prices[0] - prices[-1]
            percent_change = (price_change / prices[-1]) * 100 if prices[-1] > 0 else 0
        else:
            price_change = 0
            percent_change = 0
        
        return jsonify({
            'success': True,
            'product_id': product_id,
            'dates': dates,
            'prices': prices,
            'stats': {
                'current_price': prices[0] if prices else 0,
                'lowest_price': min(prices) if prices else 0,
                'highest_price': max(prices) if prices else 0,
                'average_price': sum(prices) / len(prices) if prices else 0,
                'price_change': price_change,
                'percent_change': percent_change
            }
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@visualization_bp.route('/api/comparison_chart')
def get_comparison_chart():
    """获取商品对比图表"""
    product_ids = request.args.get('product_ids', '')
    days = request.args.get('days', 30, type=int)
    
    if not product_ids:
        return jsonify({'error': '缺少product_ids参数'}), 400
    
    try:
        product_id_list = [int(pid) for pid in product_ids.split(',')]
        
        fig = go.Figure()
        
        for pid in product_id_list[:10]:  # 最多比较10个商品
            # 获取商品信息
            products = db.search_products(limit=1)
            if not products:
                continue
            
            product = products[0]
            
            # 获取价格历史
            history = db.get_price_history(pid)
            if not history:
                continue
            
            dates = []
            prices = []
            
            for record in history[:days]:
                dates.append(record['recorded_at'])
                prices.append(record['price'])
            
            # 添加价格线
            fig.add_trace(go.Scatter(
                x=dates,
                y=prices,
                mode='lines+markers',
                name=f"{product['name']} (当前: ¥{prices[0] if prices else 0})",
                hovertemplate='%{x}<br>¥%{y:.2f}<extra></extra>'
            ))
        
        # 更新图表布局
        fig.update_layout(
            title='商品价格对比',
            xaxis_title='日期',
            yaxis_title='价格 (¥)',
            hovermode='x unified',
            template='plotly_white',
            height=500
        )
        
        return jsonify({
            'success': True,
            'chart_html': pio.to_html(fig, full_html=False)
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@visualization_bp.route('/api/category_stats')
def get_category_stats():
    """获取分类统计图表"""
    try:
        # 获取所有商品
        products = db.search_products(limit=1000)
        
        if not products:
            return jsonify({'error': '没有商品数据'}), 404
        
        # 按分类统计
        category_data = {}
        for product in products:
            category = product['category']
            if category not in category_data:
                category_data[category] = {
                    'count': 0,
                    'total_price': 0,
                    'products': []
                }
            
            category_data[category]['count'] += 1
            category_data[category]['total_price'] += product['price']
            category_data[category]['products'].append(product['name'])
        
        # 创建图表数据
        categories = list(category_data.keys())
        counts = [category_data[cat]['count'] for cat in categories]
        avg_prices = [category_data[cat]['total_price'] / category_data[cat]['count'] 
                     for cat in categories]
        
        # 创建柱状图
        fig = go.Figure(data=[
            go.Bar(name='商品数量', x=categories, y=counts, yaxis='y', offsetgroup=1),
            go.Bar(name='平均价格', x=categories, y=avg_prices, yaxis='y2', offsetgroup=2)
        ])
        
        # 更新布局
        fig.update_layout(
            title='商品分类统计',
            xaxis_title='分类',
            yaxis=dict(
                title='商品数量',
                titlefont=dict(color='#1f77b4'),
                tickfont=dict(color='#1f77b4')
            ),
            yaxis2=dict(
                title='平均价格 (¥)',
                titlefont=dict(color='#ff7f0e'),
                tickfont=dict(color='#ff7f0e'),
                anchor='x',
                overlaying='y',
                side='right'
            ),
            barmode='group',
            template='plotly_white'
        )
        
        return jsonify({
            'success': True,
            'chart_html': pio.to_html(fig, full_html=False),
            'category_data': category_data
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def register_visualization(app):
    """注册可视化蓝图到Flask应用"""
    app.register_blueprint(visualization_bp)
    return app