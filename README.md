# Open-AutoGLM-GUI 使用说明

这是一个基于Open-AutoGLM项目创建的图形用户界面，可以方便地运行main.py并自定义参数。

## 🐛 编码问题修复

已修复Windows控制台的Unicode编码问题，将emoji字符替换为普通文本：
- 🔍 → [INFO]
- ✅ → [OK] 
- ❌ → [FAILED]/[ERROR]
- ✓ → [OK]
- ✗ → [ERROR]

## 功能特性

- 🖥️ 友好的图形界面，无需记忆命令行参数
- ⚙️ 可自定义base-url、model、apikey和任务命令
- 💾 支持保存和加载配置
- 📝 实时显示程序输出
- 🔒 API Key密码显示/隐藏功能
- ⏹️ 支持停止正在运行的程序

## 使用方法

### 方法1: 使用Python脚本
```bash
python gui.py   
```

### 方法2: 直接运行GUI   
```bash
PhoneAgentGUI.exe  
```
## 参数说明

- **Base URL**: 模型API的基础URL，默认为 `https://open.bigmodel.cn/api/paas/v4`
- **Model**: 模型名称，默认为 `autoglm-phone`
- **API Key**: 用于身份验证的API密钥，请替换为您的实际密钥
- **任务命令**: 要执行的任务，如"打开美团搜索附近的火锅店"

## 使用步骤

1. **启动程序**: 运行上述任一命令启动GUI

2. **配置参数**: 
   - 填写您的Base URL（默认已填写智谱AI的API地址）
   - 填写模型名称（默认为autoglm-phone）
   - 填写您的API Key（重要！请替换为真实密钥）
   - 输入您要执行的任务命令

3. **运行程序**: 点击"运行"按钮开始执行

4. **查看输出**: 程序运行时会实时显示输出信息

5. **停止程序**: 如需停止，点击"停止"按钮

6. **保存配置**: 点击"保存配置"可将当前参数保存，下次启动时自动加载

## 注意事项

1. **API Key安全**: 请妥善保管您的API Key，不要分享给他人
2. **设备连接**: 确保您的Android设备已连接并开启USB调试
3. **ADB Keyboard**: 确保手机上已安装ADB Keyboard应用
4. **网络连接**: 确保网络连接正常，能够访问API服务器

## 错误处理

- 如果程序运行出错，会在输出区域显示错误信息
- 常见错误包括：
  - API Key无效
  - 网络连接失败
  - 设备未连接
  - ADB工具未安装
  - 设备未开启USB调试
  - 设备未安装ADB Keyboard应用
  - 设备未开启USB调试（安全设置）

## 配置文件

配置会自动保存到 `gui_config.json` 文件中，包含以下信息：
```json
{
  "base_url": "https://open.bigmodel.cn/api/paas/v4",
  "model": "autoglm-phone", 
  "apikey": "your-api-key",
  "task": "打开美团搜索附近的火锅店"
}
```

## 系统要求

- Python 3.7+
- tkinter (通常随Python一起安装)
- 已配置好的Phone Agent环境（包括ADB工具等）

## 快速开始示例

1. 启动GUI
2. 在API Key字段输入您的真实API密钥
3. 在任务命令字段输入你想要执行的任务
4. 点击"运行"按钮
5. 等待程序执行完成

如有问题，请查看原始项目的[README文件](https://github.com/zai-org/Open-AutoGLM/blob/main/README.md)或查看程序输出中的错误信息。
