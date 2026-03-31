# 🕺 舞蹈动作分析系统 v3.1

基于 MediaPipe + Flask 的双路舞蹈动作实时对比分析工具，支持 AI 姿态评估与 C3D 动捕数据。

![Python](https://img.shields.io/badge/Python-3.9+-blue)
![Flask](https://img.shields.io/badge/Flask-3.0+-green)
![MediaPipe](https://img.shields.io/badge/MediaPipe-0.10+-orange)

## ✨ 核心特性

- **实时双路对比**：同时分析两位舞者（侧A：被分析者，侧B：参考者）
- **AI 智能建议**：集成 Claude/DeepSeek/GPT 进行姿态评估
- **时序对齐分析**：DTW 动态时间规整，支持不同速度的舞蹈对比
- **专业动捕支持**：支持 C3D 文件（Vicon PiG 格式）
- **Web 可视化**：现代化深色主题界面，实时骨架渲染

## 🚀 快速开始

### 安装依赖

    pip install -r requirements.txt

首次运行会自动下载 MediaPipe 模型（约3MB）。

### 启动服务

**Windows:**
    python Dance_Analyser.py

**Mac/Linux:**
    bash 启动.sh

浏览器将自动打开 `http://127.0.0.1:5000`

## 📁 项目结构

    ├── Dance_Analyser.py      # 主程序（Flask后端 + MediaPipe处理）
    ├── templates/
    │   └── index.html         # 前端主页面
    ├── static/
    │   ├── css/style.css      # 样式文件
    │   └── js/app.js          # 前端逻辑
    ├── requirements.txt       # Python依赖
    └── 启动.sh                # 启动脚本

## 🔑 配置 AI 功能（可选）

在界面中填入 API Key 以启用 AI 建议功能：
- **Claude**：填入 Anthropic API Key
- **DeepSeek**：填入 DeepSeek API Key  
- **本地模型**：使用 Ollama 无需 API Key

⚠️ **注意**：API Key 仅存储在浏览器本地，不会上传到服务器。

## 📊 使用流程

1. **侧A**：选择输入源（摄像头/视频/C3D）→ 点击"装载数据"→"开始分析"
2. **侧B**：同上，建议上传参考视频或 C3D 标准动作
3. **对比**：实时查看关节角度差异、对称性评分
4. **AI建议**：点击"获取 AI 建议"获取专业训练指导
5. **时序分析**：切换到"时序分析"标签，查看完整动作曲线

## 🛠️ 技术栈

- **后端**：Flask, Python 3.9+
- **姿态检测**：MediaPipe Pose Landmarker (Tasks API)
- **时序分析**：NumPy, 自定义 DTW 算法
- **前端**：原生 JavaScript, Canvas API
- **AI 集成**：OpenAI/Anthropic SDK 兼容接口

## 📝 许可证

MIT License