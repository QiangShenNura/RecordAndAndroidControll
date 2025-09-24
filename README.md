# Android 设备控制与录制工具

一个集成的Android设备控制与高帧率视频录制应用程序，支持ADB连接、scrcpy屏幕镜像和240fps摄像头录制功能。

## 📱 功能特点

- **🔗 ADB设备连接**: 通过IP地址连接Android设备
- **📺 实时屏幕镜像**: 集成scrcpy实现Android屏幕实时显示
- **📹 高帧率录制**: 支持240fps摄像头视频录制
- **📊 数据同步**: 自动获取Android设备上的Payload文件
- **🎨 友好界面**: 直观的GUI界面，操作简单易懂
- **⚡ 跨平台支持**: Windows、macOS、Linux全平台兼容
- **🚀 一键安装**: Windows用户可使用批处理文件一键安装和启动

## 🚀 快速开始

### 系统要求

- Python 3.7+
- 支持的操作系统：Windows 10+、macOS 10.14+、Ubuntu 18.04+
- 摄像头设备（用于视频录制）
- Android设备（启用USB调试）

### 📦 Windows 一键安装

**Windows用户推荐使用批处理文件，无需手动配置：**

1. **下载项目**
   ```bash
   git clone https://github.com/QiangShenNura/RecordAndAndroidControll.git
   cd RecordAndAndroidControll
   ```

2. **一键安装** - 双击运行 `setup.bat`
   - 自动创建虚拟环境
   - 自动安装所有依赖包
   - 自动配置运行环境

3. **一键启动** - 双击运行 `start.bat`
   - 自动激活虚拟环境
   - 自动检查依赖是否完整
   - 自动启动应用程序

### 🐧 macOS/Linux 手动安装

**对于macOS和Linux用户：**

1. **克隆项目**
   ```bash
   git clone https://github.com/QiangShenNura/RecordAndAndroidControll.git
   cd RecordAndAndroidControll
   ```

2. **创建并激活虚拟环境**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **安装依赖**
   ```bash
   pip install -r requirements.txt
   ```

4. **启动应用**
   ```bash
   python sync_measure_and_record.py
   ```

### 💡 批处理文件说明（Windows）

项目包含两个便利的批处理文件：

- **`setup.bat`**: 自动化安装脚本
  - ✅ 检查Python环境
  - ✅ 创建虚拟环境
  - ✅ 升级pip到最新版本
  - ✅ 安装所有必需依赖包
  - ✅ 配置运行环境

- **`start.bat`**: 自动化启动脚本
  - ✅ 检查虚拟环境是否存在
  - ✅ 自动激活虚拟环境
  - ✅ 检查并安装缺失的依赖
  - ✅ 启动主程序
  - ✅ 程序退出后显示提示信息

## 🎯 使用指南

### 初次使用设置

1. **配置ADB/scrcpy工具**
   - 首次启动时点击"配置ADB/scrcpy"按钮
   - 程序会自动下载并配置所需工具

2. **Android设备准备**
   - 在Android设备上启用"开发者选项"
   - 开启"USB调试"
   - 确保设备与电脑在同一网络

### 操作步骤

#### ① 连接ADB设备
1. 在"设备IP"输入框中输入Android设备的IP地址
2. 点击"①连接ADB设备"按钮
3. 等待连接成功提示

#### ② 启动摄像头
1. 从摄像头下拉列表中选择要使用的摄像头
2. 点击"②启动摄像头"按钮
3. 等待摄像头初始化完成

#### ③ 开始测量并录制
1. 点击"③开始测量并录制"按钮
2. 程序将同时开始：
   - 启动scrcpy屏幕镜像
   - 开始摄像头录制
   - 获取Android设备数据

## 🛠️ 主要功能详解

### ADB设备管理
- **连接设备**: 通过IP地址连接Android设备
- **断开设备**: 安全断开ADB连接
- **工具配置**: 自动配置ADB和scrcpy工具

### 摄像头管理
- **设备检测**: 自动检测可用摄像头
- **预览功能**: 实时预览摄像头画面
- **录制设置**: 支持高帧率录制（目标240fps）

### 文件管理
- **文件名配置**: 自定义录制文件名格式
- **自动编号**: 智能递增文件编号
- **文件夹管理**: 一键打开输出文件夹

### 数据同步
- **Payload获取**: 自动从Android设备获取数据文件
- **实时同步**: 录制过程中实时同步数据

## 📁 项目结构

```
RecordAndAndroidControll/
├── setup.bat                   # Windows一键安装脚本  
├── start.bat                   # Windows一键启动脚本
├── sync_measure_and_record.py  # 主程序文件
├── record_script.py            # 录制子进程脚本
├── trigger_script.py           # 触发脚本
├── requirements.txt            # Python依赖
├── platform-tools/           # ADB工具目录
├── payloads/                 # 数据文件输出目录
│   └── MagicMirror/         # Android设备数据
└── videos/                   # 视频录制输出目录
```

## ⚙️ 配置说明

### 文件名格式
程序支持自定义文件名格式，包含三个部分：
- **前缀**: 项目或设备标识
- **编号**: 自动递增的序列号
- **后缀**: 文件版本标识

示例：`AnuraMM-5-MMA0V7230924002_0000035-1`

### 摄像头设置
- 自动检测可用摄像头设备
- 支持分辨率和帧率调整
- 实时预览功能

## 🔧 故障排除

### 常见问题

**Q: ADB连接失败怎么办？**
A: 
- 确保Android设备已启用USB调试
- 检查设备IP地址是否正确
- 确认设备与电脑在同一网络
- 尝试点击"配置ADB/scrcpy"重新配置工具

**Q: 摄像头无法启动？**
A:
- 检查摄像头是否被其他程序占用
- 尝试选择不同的摄像头设备
- 确认摄像头驱动程序正常工作

**Q: scrcpy屏幕镜像无法显示？**
A:
- 确保scrcpy工具已正确安装
- 检查ADB连接是否正常
- 在macOS上确认scrcpy已通过Homebrew安装

**Q: 录制视频找不到？**
A:
- 检查`videos/`目录
- 确认录制过程正常完成
- 查看程序日志了解详细信息

### 系统兼容性

**Windows用户注意事项：**
- 推荐使用 `setup.bat` 和 `start.bat` 进行安装和启动
- 如遇到问题，请以管理员身份运行批处理文件
- 确保安装了Visual C++ Redistributable
- 部分杀毒软件可能误报，请添加程序到白名单

**macOS用户注意事项：**
- 首次运行可能需要授权摄像头访问权限
- 建议通过Homebrew安装scrcpy：`brew install scrcpy`

**Linux用户注意事项：**
- 确保用户在video组中：`sudo usermod -a -G video $USER`
- 安装必要的系统依赖：`sudo apt-get install adb scrcpy`

## 🏗️ 开发说明

### 环境设置
```bash
# 开发环境安装
pip install -e .

# 运行测试
python -m pytest tests/

# 代码格式化
black sync_measure_and_record.py
```

### 构建说明
使用PyInstaller创建可执行文件：
```bash
pyinstaller --windowed --onefile sync_measure_and_record.py
```

## 📄 许可证

本项目采用MIT许可证 - 查看 [LICENSE](LICENSE) 文件了解详细信息。

## 🤝 贡献

欢迎提交Issue和Pull Request！

1. Fork项目
2. 创建功能分支：`git checkout -b feature/AmazingFeature`
3. 提交更改：`git commit -m 'Add some AmazingFeature'`
4. 推送到分支：`git push origin feature/AmazingFeature`
5. 打开Pull Request

## 📞 支持与反馈

- 📧 邮箱：support@nuralogix.com
- 🐛 问题反馈：[GitHub Issues](https://github.com/QiangShenNura/RecordAndAndroidControll/issues)
- 📚 文档：[Wiki](https://github.com/QiangShenNura/RecordAndAndroidControll/wiki)

## 🙏 致谢

- [scrcpy](https://github.com/Genymobile/scrcpy) - Android屏幕镜像工具
- [OpenCV](https://opencv.org/) - 计算机视觉库
- [ADB](https://developer.android.com/studio/command-line/adb) - Android调试桥

---

**🎉 享受使用Android设备控制与录制工具吧！**
