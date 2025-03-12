from flask import Flask, render_template, request, jsonify, Response, stream_with_context, send_file
from stock_analyzer import StockAnalyzer
from us_stock_service import USStockService
from fund_service import FundService  # 新增导入
import threading
import os
import traceback
import requests
import json
from logger import get_logger
from utils.api_utils import APIUtils
# 加载环境变量
from dotenv import load_dotenv
import re
from fpdf import FPDF 

load_dotenv()

# 获取日志器
logger = get_logger()

app = Flask(__name__)
analyzer = StockAnalyzer()
us_stock_service = USStockService()
fund_service = FundService()  # 新增服务实例

@app.route('/')
def index():
    announcement = os.getenv('ANNOUNCEMENT_TEXT') or None
    # 获取默认API配置信息
    default_api_url = os.getenv('API_URL', '')
    default_api_model = os.getenv('API_MODEL', 'gpt-3.5-turbo')
    default_api_timeout = os.getenv('API_TIMEOUT', '60')
    # 不传递API_KEY到前端，出于安全考虑
    return render_template('index.html', 
                          announcement=announcement,
                          default_api_url=default_api_url,
                          default_api_model=default_api_model,
                          default_api_timeout=default_api_timeout)

def generate_pdf(text, filename):
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
        # 设置字体，使用支持 UTF-8 的 TTF 字体
    font_path = "NotoSansSC-Regular.ttf" 
    pdf.add_font("NotoSansSC", "", font_path, uni=True)
    pdf.set_font("NotoSansSC", size=12)
    
    pdf.multi_cell(0, 10, text)
    pdf.output(filename)

@app.route('/generate_pdf', methods=['POST'])
def create_pdf():
    data = request.json
    if not data or 'text' not in data:
        return {"error": "Missing text field"}, 400
    
    text = data['text']
    filename = data['filename']+".pdf"
    generate_pdf(text, filename)
    
    return send_file(filename, as_attachment=True)

@app.route('/analyze', methods=['POST'])
def analyze():
    try:
        logger.info("开始处理分析请求")
        data = request.json
        stock_codes = data.get('stock_codes', [])
        market_type = data.get('market_type', 'A')
        stream_output = data.get('stream', True)  # 新增参数，默认为流式输出
        
        logger.debug(f"接收到分析请求: stock_codes={stock_codes}, market_type={market_type}, stream_output={stream_output}")
        
        # 获取自定义API配置
        custom_api_url = data.get('api_url')
        custom_api_key = data.get('api_key')
        custom_api_model = data.get('api_model')
        custom_api_timeout = data.get('api_timeout')
        
        logger.debug(f"自定义API配置: URL={custom_api_url}, 模型={custom_api_model}, API Key={'已提供' if custom_api_key else '未提供'}, Timeout={custom_api_timeout}")
        
        # 创建新的分析器实例，使用自定义配置
        custom_analyzer = StockAnalyzer(
            custom_api_url=custom_api_url,
            custom_api_key=custom_api_key,
            custom_api_model=custom_api_model,
            custom_api_timeout=custom_api_timeout
        )
        
        if not stock_codes:
            logger.warning("未提供股票代码")
            return jsonify({'error': '请输入代码'}), 400
        
        # 根据stream_output参数决定是流式输出还是非流式输出
        if stream_output:
            # 使用流式响应
            def generate():
                if len(stock_codes) == 1:
                    # 单个股票分析流式处理
                    stock_code = stock_codes[0].strip()
                    logger.info(f"开始单股流式分析: {stock_code}")
                    init_message = f'{{"stream_type": "single", "stock_code": "{stock_code}"}}\n'
                    yield init_message
                    
                    logger.debug(f"开始处理股票 {stock_code} 的流式响应")
                    chunk_count = 0
                    for chunk in custom_analyzer.analyze_stock(stock_code, market_type, stream=True):
                        chunk_count += 1
                        yield chunk + '\n'
                    
                    logger.info(f"股票 {stock_code} 流式分析完成，共发送 {chunk_count} 个块")
                else:
                    # 批量分析流式处理
                    logger.info(f"开始批量流式分析: {stock_codes}")
                    init_message = f'{{"stream_type": "batch", "stock_codes": {json.dumps(stock_codes)}}}\n'
                    yield init_message
                    
                    logger.debug(f"开始处理批量股票的流式响应")
                    chunk_count = 0
                    for chunk in custom_analyzer.scan_stocks(
                        [code.strip() for code in stock_codes],
                        min_score=0,
                        market_type=market_type,
                        stream=True
                    ):
                        chunk_count += 1
                        yield chunk + '\n'
                    
                    logger.info(f"批量流式分析完成，共发送 {chunk_count} 个块")
            
            logger.info("成功创建流式响应生成器")
            return Response(stream_with_context(generate()), mimetype='application/json')
        else:
            # 非流式响应
            if len(stock_codes) == 1:
                # 单个股票分析非流式处理
                stock_code = stock_codes[0].strip()
                logger.info(f"开始单股非流式分析: {stock_code}")
                
                full_analysis = ""
                for chunk in custom_analyzer.analyze_stock(stock_code, market_type, stream=True):
                    # 解析JSON获取ai_analysis_chunk并拼接
                    try:
                        chunk_data = json.loads(chunk)
                        if "ai_analysis_chunk" in chunk_data:
                            # 确保将Unicode转换为中文字符
                            analysis_text = chunk_data["ai_analysis_chunk"]
                            full_analysis += analysis_text
                    except json.JSONDecodeError:
                        logger.warning(f"无法解析JSON块: {chunk}")
                
                logger.info(f"股票 {stock_code} 非流式分析完成")

                full_analysis = re.sub(r'</?think>', '', full_analysis)
                full_analysis = full_analysis.replace('\n', '<br>')
                full_analysis = full_analysis.replace('\"', '')
                logger.info(full_analysis)
                
                return Response(
                    json.dumps(full_analysis, ensure_ascii=False),
                    mimetype='application/json; charset=utf-8'
                )
            else:
                # 批量分析非流式处理
                logger.info(f"开始批量非流式分析: {stock_codes}")
                
                results = {}
                current_stock = None
                current_analysis = ""
                
                for chunk in custom_analyzer.scan_stocks(
                    [code.strip() for code in stock_codes],
                    min_score=0,
                    market_type=market_type,
                    stream=True
                ):
                    try:
                        chunk_data = json.loads(chunk)
                        stock_code = chunk_data.get("stock_code")
                        
                        if stock_code:
                            # 如果出现新的股票代码，保存之前的结果
                            if current_stock and current_stock != stock_code:
                                current_analysis = re.sub(r'</?think>', '', current_analysis)
                                current_analysis = current_analysis.replace('\n', '<br>')
                                current_analysis = current_analysis.replace('\"', '')
                                results[current_stock] = current_analysis
                                current_analysis = ""
                            
                            current_stock = stock_code
                        
                        if "ai_analysis_chunk" in chunk_data:
                            # 确保将Unicode转换为中文字符
                            analysis_text = chunk_data["ai_analysis_chunk"]
                            current_analysis += analysis_text
                    except json.JSONDecodeError:
                        logger.warning(f"无法解析JSON块: {chunk}")
                
                # 保存最后一个股票的结果
                if current_stock and current_stock not in results:
                    current_analysis = re.sub(r'</?think>', '', current_analysis)
                    current_analysis = current_analysis.replace('\n', '<br>')
                    current_analysis = current_analysis.replace('\"', '')
                    results[current_stock] = current_analysis
                
                logger.info(f"批量非流式分析完成，共分析 {len(results)} 只股票")
                return Response(
                    json.dumps(results, ensure_ascii=False),
                    mimetype='application/json; charset=utf-8'
                )
    
    except Exception as e:
        error_msg = f"分析时出错: {str(e)}"
        logger.error(error_msg)
        logger.exception(e)
        return jsonify({'error': error_msg}), 500


@app.route('/search_us_stocks', methods=['GET'])
def search_us_stocks():
    try:
        keyword = request.args.get('keyword', '')
        if not keyword:
            return jsonify({'error': '请输入搜索关键词'}), 400
            
        results = us_stock_service.search_us_stocks(keyword)
        return jsonify({'results': results})
        
    except Exception as e:
        print(f"搜索美股代码时出错: {str(e)}")
        return jsonify({'error': str(e)}), 500

# 添加基金搜索路由
@app.route('/search_funds', methods=['GET'])
def search_funds():
    try:
        keyword = request.args.get('keyword', '')
        market_type = request.args.get('market_type', '')
        if not keyword:
            return jsonify({'error': '请输入搜索关键词'}), 400
            
        results = fund_service.search_funds(keyword, market_type)
        return jsonify({'results': results})
        
    except Exception as e:
        logger.error(f"搜索基金代码时出错: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/test_api_connection', methods=['POST'])
def test_api_connection():
    """测试API连接"""
    try:
        logger.info("开始测试API连接")
        data = request.json
        api_url = data.get('api_url')
        api_key = data.get('api_key')
        api_model = data.get('api_model')
        api_timeout = data.get('api_timeout', 10)  # 默认测试连接超时为10秒
        
        logger.debug(f"测试API连接: URL={api_url}, 模型={api_model}, API Key={'已提供' if api_key else '未提供'}, Timeout={api_timeout}")
        
        if not api_url:
            logger.warning("未提供API URL")
            return jsonify({'error': '请提供API URL'}), 400
            
        if not api_key:
            logger.warning("未提供API Key")
            return jsonify({'error': '请提供API Key'}), 400
            
        # 构建API URL
        test_url = APIUtils.format_api_url(api_url)
        logger.debug(f"完整API测试URL: {test_url}")
        
        # 发送测试请求
        response = requests.post(
            test_url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": api_model or "gpt-3.5-turbo",
                "messages": [
                    {"role": "user", "content": "Hello, this is a test message. Please respond with 'API connection successful'."}
                ],
                "max_tokens": 20
            },
            timeout=int(api_timeout)
        )
        
        # 检查响应
        if response.status_code == 200:
            logger.info(f"API 连接测试成功: {response.status_code}")
            return jsonify({'success': True, 'message': 'API 连接测试成功'})
        else:
            error_message = response.json().get('error', {}).get('message', '未知错误')
            logger.warning(f"API连接测试失败: {response.status_code} - {error_message}")
            return jsonify({'success': False, 'message': f'API 连接测试失败: {error_message}', 'status_code': response.status_code}), 400
            
    except requests.exceptions.RequestException as e:
        logger.error(f"API 连接请求错误: {str(e)}")
        return jsonify({'success': False, 'message': f'请求错误: {str(e)}'}), 400
    except Exception as e:
        logger.error(f"测试 API 连接时出错: {str(e)}")
        logger.exception(e)
        return jsonify({'success': False, 'message': f'API 测试连接时出错: {str(e)}'}), 500

if __name__ == '__main__':
    logger.info("AI股票分析系统启动")
    app.run(host='0.0.0.0', port=8888, debug=True)
