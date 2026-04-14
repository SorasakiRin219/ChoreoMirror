# 🕺 镜影鉴姿-舞蹈动作分析系统 v3.1

基于 MediaPipe + Flask 的双路舞蹈动作实时对比分析工具，支持 AI 姿态评估、C3D 专业动捕数据解析与移动端摄像头推流。

![Python](https://img.shields.io/badge/Python-3.9+-blue)
![Flask](https://img.shields.io/badge/Flask-3.0+-green)
![MediaPipe](https://img.shields.io/badge/MediaPipe-0.10+-orange)

## ✨ 核心特性

- **实时双路对比**：同时分析两位舞者（侧A：被分析者，侧B：参考者），实时查看关节角度差异与对称性评分
- **多源输入支持**：支持本地摄像头、视频文件、C3D 动捕文件，以及移动端摄像头推流
- **AI 智能建议**：集成 Claude、DeepSeek、GPT、通义千问、豆包、智谱、Kimi、Ollama 等主流模型进行姿态评估
- **时序对齐分析**：自定义 DTW 动态时间规整 + 两阶段全局对齐，支持不同速度的舞蹈对比
- **专业动捕支持**：支持 C3D 文件（Vicon PiG、C3D Generic、自定义标记点映射），缺失 `ezc3d` 时提供一键安装
- **Web 可视化**：现代化深色主题界面，实时骨架渲染、时序曲线、帧级缩略图回放

## 🚀 快速开始

### 安装依赖

```bash
pip install -r requirements.txt
```

首次运行会自动检测并下载 MediaPipe 模型文件（`pose_landmarker_lite.task`，约 3MB）。

### 启动服务

**Windows：**
```bash
python main.py
# 或使用批处理
启动.bat
```

**Mac / Linux：**
```bash
bash 启动.sh
```

服务启动后，浏览器将自动打开 `http://127.0.0.1:5000`，局域网内可通过本机 IP 访问。

## 📁 项目结构

```
├── main.py                     # 程序启动入口
├── web/
│   ├── app.py                  # Flask 应用初始化
│   ├── routes.py               # API 路由定义
│   └── streaming.py            # MJPEG 视频流推送
├── processing/
│   ├── app_state.py            # 全局应用状态管理
│   ├── side_state.py           # 单侧状态定义
│   ├── side_processor.py       # 单侧后台处理线程
│   └── mobile_processor.py     # 移动端推帧处理
├── core/
│   ├── geometry.py             # 关节角度计算
│   ├── symmetry.py             # 对称性分析
│   ├── comparison.py           # 双侧实时对比
│   └── scoring.py              # 偏差评分与等级
├── temporal/
│   ├── timeseries.py           # 时序数据对比
│   ├── alignment.py            # 全局对齐算法
│   ├── dtw.py                  # DTW 动态时间规整
│   └── preprocessing.py        # 数据预处理
├── data/
│   └── c3d_loader.py           # C3D 文件加载器
├── pose/
│   └── rendering.py            # 骨架渲染与占位图
├── ai/
│   ├── providers.py            # AI 提供商接口
│   └── prompts.py              # Prompt 构建
├── config/
│   ├── constants.py            # 关节定义、C3D 映射等常量
│   └── model_config.py         # MediaPipe 模型配置与自动下载
├── utils/
│   └── helpers.py              # 工具函数
├── templates/
│   └── index.html              # 前端主页面
├── static/
│   ├── css/style.css           # 样式文件
│   └── js/app.js               # 前端逻辑
├── requirements.txt            # Python 依赖
├── pose_landmarker_lite.task   # MediaPipe 姿态检测模型
├── 启动.bat                    # Windows 启动脚本
└── 启动.sh                     # Linux / Mac 启动脚本
```

## 🔑 配置 AI 功能（可选）

在界面「AI 设置」中填入对应 API Key 以启用 AI 建议功能：

- **Claude**：Anthropic API Key
- **DeepSeek**：DeepSeek API Key
- **OpenAI**：OpenAI API Key
- **通义千问**：DashScope API Key
- **豆包**：火山方舟 API Key
- **智谱 GLM**：Zhipu API Key
- **Kimi**：Moonshot API Key
- **Ollama**：本地部署，无需 API Key

⚠️ **注意**：API Key 仅存储在浏览器本地（`localStorage`），不会上传到服务器。

## 📊 使用流程

1. **选择输入源**
   - **侧A**：选择摄像头 / 上传视频 / 上传 C3D / 移动端摄像头 → 点击「装载数据」→「开始分析」
   - **侧B**：同上，建议上传参考视频或 C3D 标准动作
2. **实时对比**：在「双人对比」标签下查看实时骨架、关节角度差异、对称性评分
3. **AI 建议**：点击「获取 AI 建议」获取基于时序数据的专业训练指导
4. **时序分析**：切换到「时序分析」标签，查看完整动作曲线、DTW 对齐结果与帧级缩略图
5. **导出报告**：点击右上角「导出」按钮下载 JSON 格式分析报告

## 🛠️ 技术栈

- **后端**：Flask, Python 3.9+
- **姿态检测**：MediaPipe Pose Landmarker (Tasks API)
- **图像处理**：OpenCV, Pillow
- **时序分析**：NumPy, 自定义 DTW + 两阶段全局对齐
- **前端**：原生 JavaScript, Canvas API
- **AI 集成**：Anthropic SDK + OpenAI 兼容接口

## 📝 许可证

MIT License
