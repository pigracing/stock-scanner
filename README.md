# 股票分析系统 (Stock Analysis System)

## 简介
基于 https://github.com/DR-lin-eng/stock-scanner 二次修改，感谢原作者

## 功能变更
1. 增加html页面，支持浏览器在线使用。
2. 增加港股、美股支持。 
3. 完善Dockerfile、GitHub Actions 支持docker一键部署使用。
4. 支持x86_64 和 ARM64架构镜像
5. 支持流式输出，支持前端传入Key(仅作为本地用户使用，日志等内容不会输出) 感谢@Cassianvale

## docker一键部署
```
docker run -d \
  --name stock-scanner \
  -p 8888:8888 \
  -e API_KEY=替换为你的key \
  -e API_URL=替换为你的api地址 \
  -e API_MODEL=替换为你的模型 \
  -e API_TIMEOUT=60 \
  lanzhihong/stock-scanner:latest

API_TIMEOUT=60   202503040712版本开始 (AI分析发生错误，查看日志是否有timed out类似错误，需要增加你的API超时时间)

注意⚠️： 环境变量名变更，更新版本后需要调整！！！

针对API_URL处理兼容更多的api地址，规则与Cherry Studio一致， /结尾忽略v1版本，#结尾强制使用输入地址。
API_URL 处理逻辑说明：
1. 当 API_URL 以 / 结尾时直接追加 chat/completions，保留原有版本号：
  示例：
   输入: https://ark.cn-beijing.volces.com/api/v3/
   输出: https://ark.cn-beijing.volces.com/api/v3/chat/completions
2. 当 API_URL 以 # 结尾时强制使用当前链接：
  示例：
   输入: https://ark.cn-beijing.volces.com/api/v3/chat/completions#
   输出: https://ark.cn-beijing.volces.com/api/v3/chat/completions
3. 当 API_URL 不以 / 结尾时使用默认版本号 v1：
  示例：
   输入: https://ark.cn-beijing.volces.com/api
   输出: https://ark.cn-beijing.volces.com/api/v1/chat/completions


```
默认8888端口，部署完成后访问  http://127.0.0.1:8888 即可使用。


## 注意事项 (Notes)
- 股票分析仅供参考，不构成投资建议
- 使用前请确保网络连接正常
- 建议在实盘前充分测试

## 贡献 (Contributing)
欢迎提交 issues 和 pull requests！

## 许可证 (License)
[待添加具体许可证信息]

## 免责声明 (Disclaimer)
本系统仅用于学习和研究目的，投资有风险，入市需谨慎。
