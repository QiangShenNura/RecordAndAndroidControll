import subprocess
import sys
import time
import os
import platform
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import threading
import queue
import glob
import shutil
from datetime import datetime
import cv2
from PIL import Image, ImageTk
import json
import zipfile
import stat

class AndroidControlApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Android 设备控制与录制")
        self.root.geometry("1200x800")  # 增大窗口以容纳预览
        
        # 日志队列用于线程间通信
        self.log_queue = queue.Queue()
        
        # 录制子进程
        self.record_process = None
        self.camera_ready = False  # 摄像头是否已准备就绪
        
        # 预览相关
        self.preview_cap = None
        self.preview_active = False
        self.preview_thread = None
        
        # 文件名组件（先设置默认值，后面会从配置文件读取）
        self.filename_parts = ["AnuraMMA-5-MMA0V7230924002", "0000027", "1"]
        self.last_recorded_video = None  # 最后录制的视频文件路径
        
        # ADB工具路径
        self.adb_path = None
        self.adb_ready = False
        
        # 摄像头选择
        self.available_cameras = []
        self.selected_camera_index = 0
        
        # 配置文件路径
        self.config_file = self.get_config_path()
        
        # 从配置文件加载设置
        self.load_config()
        
        # 自动配置ADB工具
        self.setup_adb_tools()
        
        # 设置UI
        self.setup_ui()
        
        # 检测摄像头并更新列表
        self.detect_cameras()
        self.update_camera_list()
        
        # 检查依赖
        self.check_dependencies()
        
        # 启动日志更新线程
        self.update_logs()
        
        # 设置窗口关闭事件处理
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
    def get_config_path(self):
        """获取配置文件路径，兼容Windows和Mac"""
        system = platform.system()
        
        if system == "Windows":
            # Windows: 使用用户文档目录
            config_dir = os.path.join(os.path.expanduser("~"), "Documents", "AndroidControlApp")
        elif system == "Darwin":  # macOS
            # macOS: 使用用户应用支持目录
            config_dir = os.path.join(os.path.expanduser("~"), "Library", "Application Support", "AndroidControlApp")
        else:  # Linux 和其他
            # Linux: 使用 .config 目录
            config_dir = os.path.join(os.path.expanduser("~"), ".config", "AndroidControlApp")
        
        # 确保配置目录存在
        if not os.path.exists(config_dir):
            os.makedirs(config_dir)
            
        return os.path.join(config_dir, "config.json")
        
    def load_config(self):
        """从配置文件加载设置"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    
                # 加载文件名配置
                if 'filename_parts' in config:
                    self.filename_parts = config['filename_parts']
                    self.log(f"已加载配置: 文件名 = {self.get_formatted_filename()}")
                else:
                    self.log("使用默认文件名配置")
                    
                # 加载设备IP配置
                self.saved_device_ip = config.get('device_ip', '192.168.1.100')
                
                # 加载摄像头索引配置
                self.saved_camera_index = config.get('camera_index', 0)
            else:
                self.log("配置文件不存在，使用默认设置")
                self.saved_device_ip = '192.168.1.100'
                self.saved_camera_index = 0
                # 保存默认配置
                self.save_config()
                
        except Exception as e:
            self.log(f"加载配置文件失败: {str(e)}，使用默认设置")
            
    def save_config(self):
        """保存设置到配置文件"""
        try:
            # 如果设备IP输入框存在，保存当前IP
            device_ip = self.saved_device_ip
            if hasattr(self, 'device_ip_var'):
                current_ip = self.device_ip_var.get().strip()
                if current_ip:
                    device_ip = current_ip
            
            # 保存当前选择的摄像头索引
            camera_index = self.saved_camera_index
            if hasattr(self, 'camera_var') and self.available_cameras:
                camera_index = self.get_selected_camera_index()
            
            config = {
                'filename_parts': self.filename_parts,
                'device_ip': device_ip,
                'camera_index': camera_index,
                'last_updated': datetime.now().isoformat()
            }
            
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
                
            self.log(f"配置已保存: {self.config_file}")
            
        except Exception as e:
            self.log(f"保存配置文件失败: {str(e)}")
            
    def get_formatted_filename(self):
        """获取格式化的文件名：前缀_编号-后缀"""
        if len(self.filename_parts) >= 3:
            # 前缀后面用下划线，其他地方用破折号
            return f"{self.filename_parts[0]}_{self.filename_parts[1]}-{self.filename_parts[2]}"
        else:
            # 兼容旧格式
            return "-".join(self.filename_parts)
            
    def increment_filename_number(self):
        """增加文件名编号并保存配置"""
        try:
            current = int(self.filename_parts[1])
            new_number = f"{current + 1:07d}"  # 保持7位数字格式
            self.filename_parts[1] = new_number
            
            # 更新UI显示
            if hasattr(self, 'number_var'):
                self.number_var.set(new_number)
                self.update_filename_display()
            
            # 保存到配置文件
            self.save_config()
            
            self.log(f"文件名编号已自动递增: {new_number}")
            
        except ValueError:
            self.log("错误: 文件名编号格式无效，无法自动递增")
            
    def setup_adb_tools(self):
        """自动配置ADB工具"""
        self.log("正在配置ADB工具...")
        
        try:
            # 获取当前系统类型
            system = platform.system()
            
            # 确定要使用的压缩包和ADB可执行文件名
            if system == "Darwin":  # macOS
                zip_file = "platform-tools-latest-darwin.zip"
                adb_executable = "adb"
                self.log("检测到macOS系统，使用Darwin平台工具")
            elif system == "Windows":
                zip_file = "platform-tools-latest-windows.zip"
                adb_executable = "adb.exe"
                self.log("检测到Windows系统，使用Windows平台工具")
            else:
                self.log(f"不支持的系统类型: {system}")
                return False
            
            # 检查压缩包是否存在
            if not os.path.exists(zip_file):
                self.log(f"错误: 找不到ADB工具包 {zip_file}")
                return False
            
            # 创建platform-tools目录
            tools_dir = "platform-tools"
            if os.path.exists(tools_dir):
                self.log("platform-tools目录已存在，检查是否需要更新...")
                # 检查ADB是否已经存在且可用
                potential_adb_path = os.path.join(tools_dir, adb_executable)
                if os.path.exists(potential_adb_path) and self.test_adb_executable(potential_adb_path):
                    self.adb_path = os.path.abspath(potential_adb_path)
                    self.adb_ready = True
                    self.log(f"✓ ADB工具已就绪: {self.adb_path}")
                    return True
                else:
                    self.log("现有ADB工具不可用，重新解压...")
                    shutil.rmtree(tools_dir)
            
            # 解压ADB工具包
            self.log(f"正在解压 {zip_file}...")
            with zipfile.ZipFile(zip_file, 'r') as zip_ref:
                zip_ref.extractall('.')
                self.log("✓ ADB工具包解压完成")
            
            # 设置ADB可执行文件路径
            self.adb_path = os.path.abspath(os.path.join(tools_dir, adb_executable))
            
            # 在macOS/Linux上设置执行权限
            if system in ["Darwin", "Linux"]:
                self.log("设置ADB可执行权限...")
                os.chmod(self.adb_path, stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH)
                self.log("✓ 可执行权限设置完成")
            
            # 测试ADB是否可用
            if self.test_adb_executable(self.adb_path):
                self.adb_ready = True
                self.log(f"✓ ADB工具配置成功: {self.adb_path}")
                return True
            else:
                self.log("✗ ADB工具测试失败")
                return False
                
        except Exception as e:
            self.log(f"配置ADB工具时发生错误: {str(e)}")
            return False
            
    def test_adb_executable(self, adb_path):
        """测试ADB可执行文件是否正常工作"""
        try:
            result = subprocess.run([adb_path, 'version'], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                version_info = result.stdout.strip().split('\n')[0]
                self.log(f"ADB版本: {version_info}")
                return True
            else:
                self.log(f"ADB测试失败: {result.stderr}")
                return False
        except Exception as e:
            self.log(f"ADB测试过程中发生错误: {str(e)}")
            return False
            
    def get_adb_command(self, *args):
        """构建ADB命令，使用内置的ADB工具"""
        if not self.adb_ready or not self.adb_path:
            raise RuntimeError("ADB工具未就绪")
        return [self.adb_path] + list(args)
        
    def reconfigure_adb(self):
        """重新配置ADB工具"""
        self.log("开始重新配置ADB工具...")
        
        def reconfigure_thread():
            try:
                # 停止当前ADB服务器
                if self.adb_ready and self.adb_path:
                    try:
                        kill_cmd = self.get_adb_command('kill-server')
                        subprocess.run(kill_cmd, capture_output=True, timeout=5)
                        self.log("已停止现有ADB服务器")
                    except:
                        pass
                
                # 删除现有platform-tools目录
                tools_dir = "platform-tools"
                if os.path.exists(tools_dir):
                    self.log("删除现有ADB工具...")
                    shutil.rmtree(tools_dir)
                
                # 重新配置ADB
                self.adb_ready = False
                self.adb_path = None
                
                if self.setup_adb_tools():
                    self.log("✓ ADB工具重新配置完成")
                else:
                    self.log("✗ ADB工具重新配置失败")
                    
            except Exception as e:
                self.log(f"重新配置ADB时发生错误: {str(e)}")
                
        threading.Thread(target=reconfigure_thread, daemon=True).start()
        
    def detect_cameras(self):
        """检测可用的摄像头设备"""
        self.available_cameras = []
        self.log("正在检测可用摄像头...")
        
        # 尝试不同的后端，但优先使用默认后端（在macOS上通常工作最好）
        backends = [cv2.CAP_ANY, cv2.CAP_AVFOUNDATION, cv2.CAP_V4L2]
        
        for i in range(10):  # 检查0-9号摄像头
            camera_found = False
            
            for backend in backends:
                if camera_found:
                    break
                    
                try:
                    cap = cv2.VideoCapture(i, backend)
                    if cap.isOpened():
                        # 给摄像头更多时间初始化
                        import time
                        time.sleep(0.3)
                        
                        # 尝试多次读取帧，有些摄像头需要预热
                        successful_reads = 0
                        test_frame = None
                        for attempt in range(10):  # 增加尝试次数
                            ret, frame = cap.read()
                            if ret and frame is not None:
                                successful_reads += 1
                                if test_frame is None:
                                    test_frame = frame
                            time.sleep(0.05)  # 短暂延迟
                        
                        # 只要有一次成功读取就认为摄像头可用
                        if successful_reads > 0:
                            # 获取摄像头信息
                            width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
                            height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
                            fps = cap.get(cv2.CAP_PROP_FPS)
                            
                            # 如果获取的值无效，使用实际帧的尺寸
                            if (width <= 0 or height <= 0) and test_frame is not None:
                                height, width = test_frame.shape[:2]
                            elif width <= 0 or height <= 0:
                                width, height = 640, 480  # 默认值
                            
                            if fps <= 0 or fps > 1000:  # 有些设备返回异常高的fps值
                                fps = 30.0  # 默认帧率
                            
                            # 尝试获取摄像头名称
                            camera_name = f"摄像头 {i}"
                            try:
                                backend_name = cap.getBackendName() if hasattr(cap, 'getBackendName') else ""
                                if backend_name:
                                    camera_name = f"摄像头 {i} ({backend_name})"
                            except:
                                pass
                            
                            camera_info = {
                                'index': i,
                                'name': camera_name,
                                'resolution': f"{int(width)}x{int(height)}",
                                'fps': f"{fps:.1f}",
                                'backend': backend,
                                'success_rate': f"{successful_reads}/10"
                            }
                            
                            # 检查是否已经添加了相同索引的摄像头（避免重复）
                            existing = False
                            for existing_cam in self.available_cameras:
                                if existing_cam['index'] == i:
                                    existing = True
                                    break
                            
                            if not existing:
                                self.available_cameras.append(camera_info)
                                backend_name = "默认" if backend == cv2.CAP_ANY else f"后端{backend}"
                                self.log(f"✓ 找到摄像头 {i}: {int(width)}x{int(height)} @ {fps:.1f}fps ({successful_reads}/10 帧, {backend_name})")
                                camera_found = True
                    
                    cap.release()
                    
                except Exception as e:
                    if cap:
                        try:
                            cap.release()
                        except:
                            pass
                    # 继续尝试下一个后端
                    continue
                    
        if not self.available_cameras:
            self.log("⚠ 未找到可用摄像头")
            # 提供更详细的诊断信息
            self.log("摄像头检测诊断：")
            self.log("- 请确保摄像头已正确连接并被系统识别")
            self.log("- 检查摄像头是否被其他应用程序占用")
            self.log("- 在macOS上，请检查系统偏好设置中的摄像头权限")
            self.log("- 尝试重新插拔USB摄像头")
            messagebox.showwarning("摄像头警告", 
                                 "未找到可用摄像头！\n\n可能的解决方案：\n"
                                 "1. 确保摄像头已正确连接\n"
                                 "2. 检查摄像头权限设置\n"
                                 "3. 关闭其他使用摄像头的应用\n"
                                 "4. 重新插拔USB摄像头后点击'刷新摄像头'")
        else:
            self.log(f"✓ 共找到 {len(self.available_cameras)} 个可用摄像头")
            # 显示检测到的摄像头详情
            for camera in self.available_cameras:
                self.log(f"  - 摄像头 {camera['index']}: {camera['resolution']} @ {camera['fps']}fps (成功率: {camera['success_rate']})")
            
            # 从配置中加载上次选择的摄像头
            if hasattr(self, 'saved_camera_index'):
                if 0 <= self.saved_camera_index < len(self.available_cameras):
                    self.selected_camera_index = self.saved_camera_index
        
    def get_selected_camera_index(self):
        """获取当前选择的摄像头索引"""
        if hasattr(self, 'camera_var') and self.available_cameras:
            selected_camera = self.camera_var.get()
            for camera in self.available_cameras:
                if selected_camera.startswith(f"摄像头 {camera['index']}"):
                    return camera['index']
        return 0
        
    def setup_ui(self):
        """设置用户界面"""
        # 主框架
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 配置网格权重
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=3)  # 左侧日志区域
        main_frame.columnconfigure(1, weight=2)  # 右侧预览区域
        main_frame.rowconfigure(1, weight=1)
        
        # 标题
        title_label = ttk.Label(main_frame, text="Android 设备控制与录制", 
                               font=("Arial", 16, "bold"))
        title_label.grid(row=0, column=0, columnspan=2, pady=(0, 10))
        
        # 左侧布局
        left_frame = ttk.Frame(main_frame)
        left_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(0, 10))
        left_frame.columnconfigure(0, weight=1)
        left_frame.rowconfigure(0, weight=1)
        
        # 日志显示区域
        log_frame = ttk.LabelFrame(left_frame, text="日志输出", padding="5")
        log_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, height=20, width=60)
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 右侧预览区域
        right_frame = ttk.Frame(main_frame)
        right_frame.grid(row=1, column=1, sticky=(tk.W, tk.E, tk.N, tk.S))
        right_frame.columnconfigure(0, weight=1)
        right_frame.rowconfigure(1, weight=1)
        
        # 文件名配置区域
        filename_frame = ttk.LabelFrame(right_frame, text="视频文件名配置", padding="5")
        filename_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        
        self.setup_filename_ui(filename_frame)
        
        # 预览区域
        preview_frame = ttk.LabelFrame(right_frame, text="摄像头预览", padding="5")
        preview_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        preview_frame.columnconfigure(0, weight=1)
        preview_frame.rowconfigure(0, weight=1)
        
        self.preview_label = ttk.Label(preview_frame, text="点击'测试预览'开启摄像头预览", 
                                      anchor=tk.CENTER, font=("Arial", 12))
        self.preview_label.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 控制面板区域
        control_frame = ttk.Frame(main_frame)
        control_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(10, 0))
        control_frame.columnconfigure(0, weight=1)
        
        # 主要操作区域
        main_action_frame = ttk.LabelFrame(control_frame, text="主要操作", padding="5")
        main_action_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        
        self.start_button = ttk.Button(main_action_frame, text="开始测量并录制", 
                                      command=self.start_measure_and_record,
                                      style="Accent.TButton")
        self.start_button.grid(row=0, column=0, padx=(0, 10), pady=5)
        self.start_button.config(state=tk.DISABLED)  # 初始状态禁用
        
        self.stop_button = ttk.Button(main_action_frame, text="停止录制", 
                                     command=self.stop_recording)
        self.stop_button.grid(row=0, column=1, padx=(0, 10), pady=5)
        self.stop_button.config(state=tk.DISABLED)  # 初始状态禁用
        
        self.payload_button = ttk.Button(main_action_frame, text="获取 Payload", 
                                        command=self.get_payload)
        self.payload_button.grid(row=0, column=2, padx=(0, 10), pady=5)
        
        # ADB设备管理区域
        adb_frame = ttk.LabelFrame(control_frame, text="ADB设备管理", padding="5")
        adb_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        adb_frame.columnconfigure(1, weight=1)
        
        # 设备IP输入行
        ttk.Label(adb_frame, text="设备IP:").grid(row=0, column=0, sticky=tk.W, padx=(0, 5), pady=2)
        
        self.device_ip_var = tk.StringVar()
        self.device_ip_entry = ttk.Entry(adb_frame, textvariable=self.device_ip_var, width=20)
        self.device_ip_entry.grid(row=0, column=1, padx=(0, 10), pady=2, sticky=(tk.W, tk.E))
        self.device_ip_var.set(self.saved_device_ip)
        self.device_ip_var.trace_add('write', self.on_ip_change)
        
        self.connect_ip_button = ttk.Button(adb_frame, text="连接ADB设备", 
                                           command=self.connect_device_by_ip)
        self.connect_ip_button.grid(row=0, column=2, padx=(0, 10), pady=2)
        
        # ADB操作按钮行
        self.disconnect_button = ttk.Button(adb_frame, text="断开ADB设备", 
                                           command=self.disconnect_device)
        self.disconnect_button.grid(row=1, column=0, padx=(0, 10), pady=2)
        
        self.adb_config_button = ttk.Button(adb_frame, text="重新配置ADB", 
                                           command=self.reconfigure_adb)
        self.adb_config_button.grid(row=1, column=1, padx=(0, 10), pady=2)
        
        # 摄像头管理区域
        camera_frame = ttk.LabelFrame(control_frame, text="摄像头管理", padding="5")
        camera_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        camera_frame.columnconfigure(1, weight=1)
        
        # 摄像头选择行
        ttk.Label(camera_frame, text="摄像头:").grid(row=0, column=0, sticky=tk.W, padx=(0, 5), pady=2)
        
        self.camera_var = tk.StringVar()
        self.camera_combo = ttk.Combobox(camera_frame, textvariable=self.camera_var, 
                                        state="readonly", font=("Arial", 9))
        self.camera_combo.grid(row=0, column=1, padx=(0, 10), pady=2, sticky=(tk.W, tk.E))
        self.camera_combo.bind('<<ComboboxSelected>>', self.on_camera_change)
        
        self.refresh_camera_button = ttk.Button(camera_frame, text="刷新摄像头", 
                                               command=self.refresh_cameras)
        self.refresh_camera_button.grid(row=0, column=2, padx=(0, 10), pady=2)
        
        # 摄像头操作按钮行
        self.connect_button = ttk.Button(camera_frame, text="启动摄像头", 
                                        command=self.start_camera_system)
        self.connect_button.grid(row=1, column=0, padx=(0, 10), pady=2)
        
        self.test_camera_button = ttk.Button(camera_frame, text="测试摄像头", 
                                           command=self.test_selected_camera)
        self.test_camera_button.grid(row=1, column=1, padx=(0, 10), pady=2)
        
        self.preview_button = ttk.Button(camera_frame, text="测试预览", 
                                        command=self.toggle_preview)
        self.preview_button.grid(row=1, column=2, padx=(0, 10), pady=2)
        
        # 状态栏
        self.status_var = tk.StringVar()
        self.status_var.set("就绪")
        status_label = ttk.Label(main_frame, textvariable=self.status_var, 
                                relief=tk.SUNKEN, anchor=tk.W)
        status_label.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E))
        
    def setup_filename_ui(self, parent):
        """设置文件名编辑界面"""
        # 显示当前文件名
        current_name = self.get_formatted_filename()
        
        # 第一部分：前缀
        ttk.Label(parent, text="前缀:").grid(row=0, column=0, sticky=tk.W, padx=(0, 5))
        self.prefix_var = tk.StringVar(value=self.filename_parts[0])
        self.prefix_entry = ttk.Entry(parent, textvariable=self.prefix_var, width=30)
        self.prefix_entry.grid(row=0, column=1, columnspan=3, sticky=(tk.W, tk.E), padx=(0, 5))
        self.prefix_entry.bind('<KeyRelease>', self.update_filename_display)
        
        # 第二部分：数字（带加减按钮）
        ttk.Label(parent, text="编号:").grid(row=1, column=0, sticky=tk.W, padx=(0, 5))
        
        self.decrease_button = ttk.Button(parent, text="-", width=3, 
                                         command=self.decrease_number)
        self.decrease_button.grid(row=1, column=1, padx=(0, 2))
        
        self.number_var = tk.StringVar(value=self.filename_parts[1])
        self.number_entry = ttk.Entry(parent, textvariable=self.number_var, width=15, justify=tk.CENTER)
        self.number_entry.grid(row=1, column=2, padx=2)
        self.number_entry.bind('<KeyRelease>', self.update_filename_display)
        
        self.increase_button = ttk.Button(parent, text="+", width=3, 
                                         command=self.increase_number)
        self.increase_button.grid(row=1, column=3, padx=(2, 0))
        
        # 第三部分：后缀
        ttk.Label(parent, text="后缀:").grid(row=2, column=0, sticky=tk.W, padx=(0, 5))
        self.suffix_var = tk.StringVar(value=self.filename_parts[2])
        self.suffix_entry = ttk.Entry(parent, textvariable=self.suffix_var, width=10)
        self.suffix_entry.grid(row=2, column=1, columnspan=3, sticky=(tk.W, tk.E), padx=(0, 5))
        self.suffix_entry.bind('<KeyRelease>', self.update_filename_display)
        
        # 显示完整文件名
        ttk.Label(parent, text="完整文件名:").grid(row=3, column=0, sticky=tk.W, padx=(0, 5), pady=(10, 0))
        self.filename_display_var = tk.StringVar(value=current_name)
        filename_display_label = ttk.Label(parent, textvariable=self.filename_display_var, 
                                         font=("Arial", 10, "bold"), 
                                         foreground="blue")
        filename_display_label.grid(row=3, column=1, columnspan=3, sticky=(tk.W, tk.E), 
                                  padx=(0, 5), pady=(10, 0))
        
        # 配置列权重
        parent.columnconfigure(1, weight=1)
        
    def update_filename_display(self, event=None):
        """更新文件名显示"""
        self.filename_parts[0] = self.prefix_var.get()
        self.filename_parts[1] = self.number_var.get()
        self.filename_parts[2] = self.suffix_var.get()
        
        full_name = self.get_formatted_filename()
        self.filename_display_var.set(full_name)
        
        # 自动保存配置（延迟保存，避免频繁写入）
        if hasattr(self, '_save_timer'):
            self.root.after_cancel(self._save_timer)
        self._save_timer = self.root.after(1000, self.save_config)  # 1秒后保存
        
    def on_ip_change(self, *args):
        """设备IP变化时的处理函数"""
        # 自动保存IP配置（延迟保存，避免频繁写入）
        if hasattr(self, '_ip_save_timer'):
            self.root.after_cancel(self._ip_save_timer)
        self._ip_save_timer = self.root.after(2000, self.save_config)  # 2秒后保存
        
    def on_camera_change(self, event=None):
        """摄像头选择变化时的处理函数"""
        # 自动保存摄像头配置
        if hasattr(self, '_camera_save_timer'):
            self.root.after_cancel(self._camera_save_timer)
        self._camera_save_timer = self.root.after(1000, self.save_config)  # 1秒后保存
        
        # 更新选择的摄像头索引
        self.selected_camera_index = self.get_selected_camera_index()
        self.log(f"已选择摄像头 {self.selected_camera_index}")
        
    def update_camera_list(self):
        """更新摄像头下拉列表"""
        if not hasattr(self, 'camera_combo'):
            return
            
        camera_options = []
        for camera in self.available_cameras:
            option = f"摄像头 {camera['index']} - {camera['resolution']} @ {camera['fps']}fps"
            camera_options.append(option)
        
        self.camera_combo['values'] = camera_options
        
        # 设置默认选择
        if camera_options:
            # 尝试选择之前保存的摄像头
            selected_option = None
            for option in camera_options:
                if option.startswith(f"摄像头 {self.selected_camera_index}"):
                    selected_option = option
                    break
            
            if selected_option:
                self.camera_var.set(selected_option)
            else:
                # 如果之前选择的摄像头不存在，选择第一个
                self.camera_var.set(camera_options[0])
                self.selected_camera_index = self.available_cameras[0]['index']
                
    def refresh_cameras(self):
        """刷新摄像头列表"""
        self.log("刷新摄像头列表...")
        
        # 停止当前预览（如果正在进行）
        if self.preview_active:
            self.stop_preview()
        
        # 重新检测摄像头
        self.detect_cameras()
        self.update_camera_list()
        
        self.log("摄像头列表已刷新")
        
    def test_selected_camera(self):
        """测试选中的摄像头"""
        if not self.available_cameras:
            self.log("没有可用的摄像头进行测试")
            return
            
        camera_index = self.get_selected_camera_index()
        self.log(f"正在测试摄像头 {camera_index}...")
        
        def test_camera():
            try:
                # 尝试不同的后端
                backends_to_try = [cv2.CAP_ANY]
                
                # 如果检测时记录了后端，优先使用该后端
                for camera in self.available_cameras:
                    if camera['index'] == camera_index and 'backend' in camera:
                        backends_to_try.insert(0, camera['backend'])
                        break
                
                success = False
                for backend in backends_to_try:
                    try:
                        self.log(f"尝试后端 {backend}...")
                        cap = cv2.VideoCapture(camera_index, backend)
                        
                        if cap.isOpened():
                            # 等待摄像头初始化
                            import time
                            time.sleep(0.2)
                            
                            # 尝试读取几帧
                            frames_read = 0
                            for i in range(5):
                                ret, frame = cap.read()
                                if ret:
                                    frames_read += 1
                                time.sleep(0.1)
                            
                            if frames_read > 0:
                                width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
                                height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
                                fps = cap.get(cv2.CAP_PROP_FPS)
                                
                                if width <= 0 or height <= 0:
                                    if frame is not None:
                                        height, width = frame.shape[:2]
                                
                                self.log(f"✓ 摄像头 {camera_index} 测试成功！")
                                self.log(f"  - 分辨率: {int(width)}x{int(height)}")
                                self.log(f"  - 帧率: {fps:.1f}")
                                self.log(f"  - 成功读取 {frames_read}/5 帧")
                                success = True
                            else:
                                self.log(f"✗ 摄像头 {camera_index} 无法读取帧")
                        else:
                            self.log(f"✗ 无法打开摄像头 {camera_index}")
                        
                        cap.release()
                        
                        if success:
                            break
                            
                    except Exception as e:
                        if 'cap' in locals():
                            try:
                                cap.release()
                            except:
                                pass
                        self.log(f"测试摄像头时发生错误: {e}")
                        continue
                
                if not success:
                    self.log(f"✗ 摄像头 {camera_index} 测试失败")
                    self.log("建议：")
                    self.log("- 确保摄像头未被其他程序占用")
                    self.log("- 尝试重新插拔摄像头")
                    self.log("- 点击'刷新摄像头'重新检测")
                    
            except Exception as e:
                self.log(f"测试摄像头时发生错误: {e}")
        
        # 在后台线程中执行测试
        threading.Thread(target=test_camera, daemon=True).start()
        
    def increase_number(self):
        """增加编号"""
        try:
            current = int(self.number_var.get())
            new_number = f"{current + 1:07d}"  # 保持7位数字格式
            self.number_var.set(new_number)
            self.update_filename_display()
        except ValueError:
            messagebox.showerror("错误", "编号必须是数字")
            
    def decrease_number(self):
        """减少编号"""
        try:
            current = int(self.number_var.get())
            if current > 0:
                new_number = f"{current - 1:07d}"  # 保持7位数字格式
                self.number_var.set(new_number)
                self.update_filename_display()
            else:
                messagebox.showwarning("警告", "编号不能小于0")
        except ValueError:
            messagebox.showerror("错误", "编号必须是数字")
            
    def toggle_preview(self):
        """切换预览状态"""
        if not self.preview_active:
            self.start_preview()
        else:
            self.stop_preview()
            
    def start_preview(self):
        """启动预览"""
        try:
            # 获取当前选择的摄像头索引
            camera_index = self.get_selected_camera_index()
            self.log(f"使用摄像头 {camera_index} 进行预览")
            
            # 尝试使用检测时成功的后端（如果有的话）
            selected_backend = cv2.CAP_ANY
            for camera in self.available_cameras:
                if camera['index'] == camera_index and 'backend' in camera:
                    selected_backend = camera['backend']
                    break
                
            # 初始化摄像头
            self.preview_cap = cv2.VideoCapture(camera_index, selected_backend)
            if not self.preview_cap.isOpened():
                # 如果指定后端失败，尝试默认后端
                self.log(f"指定后端失败，尝试默认后端...")
                self.preview_cap = cv2.VideoCapture(camera_index)
                
            if not self.preview_cap.isOpened():
                self.log(f"错误: 无法打开摄像头 {camera_index} 进行预览")
                return
            
            # 先测试摄像头是否真的可用
            ret, test_frame = self.preview_cap.read()
            if not ret:
                self.log(f"错误: 摄像头 {camera_index} 无法读取帧")
                self.preview_cap.release()
                return
                
            # 获取当前分辨率作为基准
            current_width = self.preview_cap.get(cv2.CAP_PROP_FRAME_WIDTH)
            current_height = self.preview_cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
            current_fps = self.preview_cap.get(cv2.CAP_PROP_FPS)
            
            self.log(f"摄像头当前设置: {int(current_width)}x{int(current_height)} @ {current_fps:.1f}fps")
            
            # 尝试设置录制参数，但不强制要求成功
            try:
                self.preview_cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                self.preview_cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 400)
                self.preview_cap.set(cv2.CAP_PROP_FPS, 240)
                
                # 尝试设置曝光参数
                try:
                    self.preview_cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.75)
                    self.preview_cap.set(cv2.CAP_PROP_EXPOSURE, -8)
                except:
                    self.log("注意: 无法设置曝光参数，将使用默认值")
                
            except Exception as e:
                self.log(f"注意: 无法设置某些摄像头参数: {e}")
            
            # 获取实际设置后的参数
            actual_width = self.preview_cap.get(cv2.CAP_PROP_FRAME_WIDTH)
            actual_height = self.preview_cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
            actual_fps = self.preview_cap.get(cv2.CAP_PROP_FPS)
            
            # 如果获取的值无效，使用测试帧的实际尺寸
            if actual_width <= 0 or actual_height <= 0:
                if test_frame is not None:
                    actual_height, actual_width = test_frame.shape[:2]
                    self.log(f"使用测试帧获取实际分辨率: {int(actual_width)}x{int(actual_height)}")
            
            if actual_fps <= 0:
                actual_fps = 30.0
            
            self.log(f"预览摄像头已启动: {int(actual_width)}x{int(actual_height)}, {actual_fps:.1f} FPS")
            
            self.preview_active = True
            self.preview_button.config(text="停止预览")
            
            # 启动预览线程
            self.preview_thread = threading.Thread(target=self.preview_loop, daemon=True)
            self.preview_thread.start()
            
        except Exception as e:
            self.log(f"启动预览失败: {str(e)}")
            if hasattr(self, 'preview_cap') and self.preview_cap:
                self.preview_cap.release()
                self.preview_cap = None
            
    def stop_preview(self):
        """停止预览"""
        self.preview_active = False
        self.preview_button.config(text="测试预览")
        
        if self.preview_cap:
            self.preview_cap.release()
            self.preview_cap = None
            
        # 清空预览区域
        self.preview_label.config(image="", text="点击'测试预览'开启摄像头预览")
        self.log("预览已停止")
        
    def preview_loop(self):
        """预览循环"""
        while self.preview_active and self.preview_cap:
            try:
                ret, frame = self.preview_cap.read()
                if ret:
                    # 转换颜色空间
                    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    
                    # 调整显示尺寸（保持纵横比）
                    height, width = frame_rgb.shape[:2]
                    max_width, max_height = 400, 300
                    
                    # 计算缩放比例
                    scale = min(max_width/width, max_height/height)
                    new_width = int(width * scale)
                    new_height = int(height * scale)
                    
                    # 缩放图像
                    frame_resized = cv2.resize(frame_rgb, (new_width, new_height))
                    
                    # 转换为PIL图像
                    image = Image.fromarray(frame_resized)
                    photo = ImageTk.PhotoImage(image)
                    
                    # 更新显示
                    if self.preview_active:
                        self.preview_label.config(image=photo, text="")
                        self.preview_label.image = photo  # 保持引用
                        
                time.sleep(1/30)  # 30 FPS 显示频率
                
            except Exception as e:
                if self.preview_active:
                    self.log(f"预览更新错误: {str(e)}")
                break
        
    def log(self, message):
        """添加日志消息到队列"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] {message}"
        self.log_queue.put(formatted_message)
        print(formatted_message)  # 同时输出到控制台
        
    def update_logs(self):
        """更新日志显示"""
        try:
            while True:
                message = self.log_queue.get_nowait()
                self.log_text.insert(tk.END, message + "\n")
                self.log_text.see(tk.END)
        except queue.Empty:
            pass
        
        # 每100ms检查一次
        self.root.after(100, self.update_logs)
        
    def check_dependencies(self):
        """检查必要的工具是否已安装"""
        self.log("正在检查依赖工具...")
        
        # 检查内置 ADB
        if self.check_adb():
            self.log("✓ 内置ADB工具已就绪")
        else:
            self.log("✗ 内置ADB工具未就绪")
            self.log("请检查ADB工具包是否正确解压")
            
        # 检查录制脚本
        if os.path.exists("record_script.py"):
            self.log("✓ 录制脚本已找到")
        else:
            self.log("✗ 录制脚本 (record_script.py) 未找到")
            
    def check_adb(self):
        """检查ADB是否已安装（使用内置ADB工具）"""
        return self.adb_ready
            
    def start_camera_system(self):
        """检查已连接的Android设备并启动摄像头系统"""
        if not self.adb_ready:
            self.log("错误: ADB工具未就绪")
            self.status_var.set("ADB工具未就绪")
            return
            
        self.log("正在检查设备连接状态...")
        self.status_var.set("检查设备中...")
        
        def check_thread():
            try:
                # 检查设备连接
                adb_cmd = self.get_adb_command('devices')
                result = subprocess.run(adb_cmd, 
                                      capture_output=True, text=True, timeout=10)
                
                if result.returncode == 0:
                    lines = result.stdout.strip().split('\n')[1:]  # 跳过标题行
                    devices = [line for line in lines if line.strip() and 'device' in line]
                    
                    if devices:
                        self.log(f"✓ 找到 {len(devices)} 个已连接设备:")
                        for device in devices:
                            self.log(f"  - {device}")
                        
                        # 设备连接成功，启动摄像头
                        self.log("设备已连接，正在启动摄像头系统...")
                        if self.start_camera():
                            self.status_var.set("摄像头系统就绪")
                            # 启用开始录制按钮
                            self.start_button.config(state=tk.NORMAL)
                            self.stop_button.config(state=tk.NORMAL)
                            messagebox.showinfo("摄像头系统", f"找到 {len(devices)} 个设备，摄像头系统已启动！")
                        else:
                            self.status_var.set("摄像头启动失败")
                            messagebox.showerror("摄像头错误", "设备已连接，但摄像头启动失败")
                    else:
                        self.log("✗ 未找到已连接的设备")
                        self.log("请先使用'连接ADB设备'功能连接您的Android设备，或确保:")
                        self.log("1. 设备已开启开发者选项和USB调试")
                        self.log("2. 设备与电脑在同一WiFi网络")
                        self.log("3. 设备已通过无线方式连接")
                        self.status_var.set("未找到设备")
                        messagebox.showinfo("设备检查", "未找到已连接的设备。\n\n请先使用'连接ADB设备'功能连接您的Android设备。")
                else:
                    self.log(f"ADB 命令执行失败: {result.stderr}")
                    self.status_var.set("检查失败")
                    
            except subprocess.TimeoutExpired:
                self.log("检查超时")
                self.status_var.set("检查超时")
            except Exception as e:
                self.log(f"检查设备连接时发生错误: {str(e)}")
                self.status_var.set("检查错误")
                
        threading.Thread(target=check_thread, daemon=True).start()
        
    def connect_device_by_ip(self):
        """通过IP地址连接Android设备 - 仅连接ADB，不启动摄像头"""
        if not self.adb_ready:
            self.log("错误: ADB工具未就绪")
            self.status_var.set("ADB工具未就绪")
            return
            
        device_ip = self.device_ip_var.get().strip()
        if not device_ip:
            self.log("错误: 请输入设备IP地址")
            messagebox.showerror("错误", "请输入设备IP地址")
            return
            
        self.log(f"正在连接设备 {device_ip}:5555...")
        self.status_var.set("连接设备中...")
        
        def connect_ip_thread():
            try:
                # 执行 adb connect 命令
                adb_cmd = self.get_adb_command('connect', f'{device_ip}:5555')
                result = subprocess.run(adb_cmd, 
                                      capture_output=True, text=True, timeout=15)
                
                if result.returncode == 0:
                    output = result.stdout.strip()
                    self.log(f"连接结果: {output}")
                    
                    if "connected" in output.lower() or "already connected" in output.lower():
                        self.log("✓ ADB设备连接成功！")
                        self.status_var.set("ADB设备已连接")
                        self.log("提示: 请点击'启动摄像头'按钮启动录制功能")
                    else:
                        self.log(f"✗ 连接失败: {output}")
                        self.status_var.set("连接失败")
                        messagebox.showerror("连接失败", 
                                           f"无法连接到设备 {device_ip}:5555\n\n错误信息: {output}\n\n请确保:\n1. 设备已开启开发者选项和USB调试\n2. 设备已开启无线调试\n3. 设备与电脑在同一WiFi网络\n4. IP地址正确")
                else:
                    error_msg = result.stderr.strip() or "未知错误"
                    self.log(f"✗ ADB连接命令失败: {error_msg}")
                    self.status_var.set("连接失败")
                    messagebox.showerror("连接失败", f"ADB连接失败:\n{error_msg}")
                    
            except subprocess.TimeoutExpired:
                self.log("✗ 连接超时")
                self.status_var.set("连接超时")
                messagebox.showerror("连接超时", "连接设备超时，请检查网络连接和设备状态")
            except Exception as e:
                self.log(f"✗ 连接时发生错误: {str(e)}")
                self.status_var.set("连接错误")
                messagebox.showerror("连接错误", f"连接过程中发生错误:\n{str(e)}")
        
        threading.Thread(target=connect_ip_thread, daemon=True).start()
        
    def verify_and_start_camera(self):
        """验证设备连接并启动摄像头"""
        try:
            # 检查设备连接状态
            adb_cmd = self.get_adb_command('devices')
            result = subprocess.run(adb_cmd, 
                                  capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')[1:]  # 跳过标题行
                devices = [line for line in lines if line.strip() and 'device' in line]
                
                if devices:
                    self.log(f"验证成功：找到 {len(devices)} 个设备")
                    for device in devices:
                        self.log(f"  - {device}")
                    
                    # 设备连接成功，启动摄像头
                    self.log("正在启动摄像头...")
                    if self.start_camera():
                        self.status_var.set("设备已连接，摄像头就绪")
                        # 启用开始录制按钮
                        self.start_button.config(state=tk.NORMAL)
                        self.stop_button.config(state=tk.NORMAL)
                        self.log("✓ 摄像头启动成功，可以开始录制")
                    else:
                        self.status_var.set("摄像头启动失败")
                        messagebox.showerror("摄像头错误", "设备连接成功，但摄像头启动失败")
                else:
                    self.log("设备连接后未在设备列表中找到")
                    self.status_var.set("设备验证失败")
            else:
                self.log(f"验证设备连接失败: {result.stderr}")
                self.status_var.set("设备验证失败")
                
        except Exception as e:
            self.log(f"验证设备连接时发生错误: {str(e)}")
            self.status_var.set("验证失败")
            
    def disconnect_device(self):
        """断开Android设备连接"""
        if not self.adb_ready:
            self.log("错误: ADB工具未就绪")
            return
            
        device_ip = self.device_ip_var.get().strip()
        if not device_ip:
            # 如果没有输入IP，断开所有设备
            self.log("正在断开所有设备连接...")
            self.status_var.set("断开连接中...")
            
            def disconnect_all_thread():
                try:
                    # 先停止录制和预览
                    self.stop_recording()
                    
                    # 执行 adb disconnect 命令
                    adb_cmd = self.get_adb_command('disconnect')
                    result = subprocess.run(adb_cmd, 
                                          capture_output=True, text=True, timeout=10)
                    
                    if result.returncode == 0:
                        self.log("所有设备已断开连接")
                        self.status_var.set("设备已断开")
                        # 禁用录制按钮
                        self.start_button.config(state=tk.DISABLED)
                        self.stop_button.config(state=tk.DISABLED)
                    else:
                        self.log(f"断开连接失败: {result.stderr}")
                        self.status_var.set("断开失败")
                        
                except Exception as e:
                    self.log(f"断开连接时发生错误: {str(e)}")
                    self.status_var.set("断开错误")
                    
            threading.Thread(target=disconnect_all_thread, daemon=True).start()
        else:
            # 断开指定IP设备
            self.log(f"正在断开设备 {device_ip}:5555...")
            self.status_var.set("断开连接中...")
            
            def disconnect_ip_thread():
                try:
                    # 先停止录制和预览
                    self.stop_recording()
                    
                    # 执行 adb disconnect 命令
                    adb_cmd = self.get_adb_command('disconnect', f'{device_ip}:5555')
                    result = subprocess.run(adb_cmd, 
                                          capture_output=True, text=True, timeout=10)
                    
                    if result.returncode == 0:
                        self.log(f"设备 {device_ip}:5555 已断开连接")
                        self.status_var.set("设备已断开")
                        # 禁用录制按钮
                        self.start_button.config(state=tk.DISABLED)
                        self.stop_button.config(state=tk.DISABLED)
                    else:
                        self.log(f"断开连接失败: {result.stderr}")
                        self.status_var.set("断开失败")
                        
                except Exception as e:
                    self.log(f"断开连接时发生错误: {str(e)}")
                    self.status_var.set("断开错误")
                    
            threading.Thread(target=disconnect_ip_thread, daemon=True).start()
        
    def start_camera(self):
        """启动摄像头子进程（在连接设备后调用）"""
        try:
            record_script_path = "record_script.py"
            if not os.path.exists(record_script_path):
                self.log("错误: record_script.py 文件不存在")
                return False
                
            self.log("正在启动摄像头...")
            
            # 检查是否有虚拟环境
            venv_python = "venv/bin/python"
            if os.path.exists(venv_python):
                python_executable = venv_python
                self.log("使用虚拟环境中的 Python")
            else:
                python_executable = sys.executable
                self.log("使用系统 Python")
            
            # 获取当前选择的摄像头索引
            camera_index = self.get_selected_camera_index()
            self.log(f"使用摄像头索引: {camera_index}")
            
            # 使用合适的Python解释器启动子进程，传递摄像头索引，捕获输出
            self.record_process = subprocess.Popen(
                [python_executable, record_script_path, str(camera_index)],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,  # 将stderr重定向到stdout
                text=True,
                bufsize=1,  # 行缓冲
                universal_newlines=True
            )
            
            # 启动线程来读取子进程输出
            self.start_output_reader()
            
            self.log("摄像头进程已启动，等待初始化...")
            
            # 等待摄像头初始化完成的信号
            self.wait_for_camera_ready()
            
            return True
            
        except Exception as e:
            self.log(f"启动摄像头失败: {str(e)}")
            return False
            
    def wait_for_camera_ready(self):
        """等待摄像头初始化完成"""
        def wait_thread():
            timeout = 10  # 10秒超时
            start_time = time.time()
            
            while time.time() - start_time < timeout:
                time.sleep(0.1)
                if self.camera_ready:
                    self.log("✓ 摄像头已就绪")
                    return
                    
                # 检查进程是否还在运行
                if self.record_process and self.record_process.poll() is not None:
                    self.log("✗ 摄像头进程异常退出")
                    return
                    
            self.log("✗ 摄像头初始化超时")
            
        threading.Thread(target=wait_thread, daemon=True).start()
            
    def start_output_reader(self):
        """启动读取子进程输出的线程"""
        def read_output():
            process = self.record_process  # 保存进程引用，避免被外部修改影响
            if process and process.stdout:
                try:
                    for line in iter(process.stdout.readline, ''):
                        if line:
                            # 移除换行符并添加前缀
                            clean_line = line.rstrip('\n\r')
                            if clean_line:
                                self.log(f"[录制] {clean_line}")
                                
                                # 检查是否是摄像头就绪的信号
                                if "等待从标准输入接收's'命令" in clean_line:
                                    self.camera_ready = True
                                    
                                # 检查是否是文件保存完成的信号
                                if "正在保存文件到:" in clean_line:
                                    # 提取文件路径
                                    file_path = clean_line.split("正在保存文件到:")[-1].strip()
                                    self.last_recorded_video = file_path
                                    
                                # 检查是否是文件保存成功的信号
                                if "文件保存成功。" in clean_line and self.last_recorded_video:
                                    # 录制完成，复制文件
                                    self.copy_recorded_video()
                                    # 更新状态为录制完成
                                    self.status_var.set("测量录制完成")
                                    # 自动递增文件名编号
                                    self.increment_filename_number()
                        
                        # 检查进程是否已结束（使用本地进程引用）
                        if process and process.poll() is not None:
                            break
                except Exception as e:
                    self.log(f"读取子进程输出时发生错误: {str(e)}")
                    
        threading.Thread(target=read_output, daemon=True).start()
        
    def copy_recorded_video(self):
        """复制录制的视频到payloads目录"""
        if not self.last_recorded_video or not os.path.exists(self.last_recorded_video):
            self.log("错误: 找不到录制的视频文件")
            return
            
        try:
            # 创建目标目录
            target_dir = "payloads/MagicMirror"
            if not os.path.exists(target_dir):
                os.makedirs(target_dir)
                self.log(f"创建目录: {target_dir}")
            
            # 构建新文件名
            custom_filename = self.get_formatted_filename() + ".mp4"
            target_path = os.path.join(target_dir, custom_filename)
            
            # 复制文件
            shutil.copy2(self.last_recorded_video, target_path)
            self.log(f"✓ 视频已复制到: {target_path}")
            
            # 显示文件信息
            source_size = os.path.getsize(self.last_recorded_video)
            target_size = os.path.getsize(target_path)
            self.log(f"文件大小: {source_size:,} 字节 -> {target_size:,} 字节")
            
        except Exception as e:
            self.log(f"✗ 复制视频文件失败: {str(e)}")
            
    def start_measure_and_record(self):
        """开始测量并录制（摄像头已预先启动）"""
        if not self.camera_ready or not self.record_process:
            self.log("错误: 摄像头未就绪，请先连接设备")
            return
            
        self.log("开始测量并录制...")
        self.status_var.set("测量录制中...")
        
        # 禁用按钮防止重复点击
        self.start_button.config(state=tk.DISABLED)
        
        def measure_thread():
            try:
                # 1. 向 Android 设备发送 's' 键
                self.log("向 Android 设备发送 's' 键...")
                adb_cmd = self.get_adb_command('shell', 'input', 'text', 's')
                adb_result = subprocess.run(adb_cmd, 
                                          capture_output=True, text=True, timeout=10)
                
                # 2. 同时向录制子进程发送 's' 命令
                if self.record_process and self.record_process.stdin:
                    self.log("向录制子进程发送 's' 命令...")
                    try:
                        # 发送's'加换行符，因为子进程使用readline()
                        self.record_process.stdin.write('s\n')
                        self.record_process.stdin.flush()
                        self.log("✓ 录制命令已发送")
                    except BrokenPipeError:
                        self.log("✗ 子进程管道已断开")
                        self.status_var.set("录制失败")
                        return
                    except Exception as e:
                        self.log(f"✗ 发送录制命令失败: {str(e)}")
                        self.status_var.set("录制失败")
                        return
                else:
                    self.log("✗ 录制子进程未正常启动")
                    self.status_var.set("录制失败")
                    return
                
                # 3. 检查ADB命令结果
                if adb_result.returncode == 0:
                    self.log("✓ 成功向设备发送 's' 键")
                else:
                    self.log(f"✗ 发送按键失败: {adb_result.stderr}")
                
                # 4. 录制已开始，更新状态
                self.log("录制已开始，等待完成...")
                self.status_var.set("正在录制...")
                
                # 不等待子进程退出，让它继续运行以便进行下一次录制
                
            except subprocess.TimeoutExpired:
                self.log("操作超时")
                self.status_var.set("操作超时")
            except Exception as e:
                self.log(f"测量录制过程中发生错误: {str(e)}")
                self.status_var.set("操作失败")
            finally:
                # 重新启用按钮（如果摄像头仍然就绪）
                if self.camera_ready and self.record_process and self.record_process.poll() is not None:
                    # 录制完成，需要重新启动摄像头
                    self.camera_ready = False
                    self.record_process = None
                    self.log("录制完成，摄像头已关闭")
                    self.status_var.set("录制完成，可重新连接设备")
                    self.start_button.config(state=tk.DISABLED)
                    self.stop_button.config(state=tk.DISABLED)
                elif self.camera_ready:
                    self.start_button.config(state=tk.NORMAL)
                    
        threading.Thread(target=measure_thread, daemon=True).start()
        
    def stop_recording(self):
        """停止录制并关闭摄像头"""
        self.log("正在停止录制...")
        
        if self.record_process:
            try:
                # 首先尝试发送退出命令
                if self.record_process.stdin and not self.record_process.stdin.closed:
                    try:
                        self.log("发送退出命令到录制进程...")
                        self.record_process.stdin.write('q\n')
                        self.record_process.stdin.flush()
                        # 等待进程正常退出
                        try:
                            self.record_process.wait(timeout=3)
                            self.log("✓ 录制进程已正常退出")
                        except subprocess.TimeoutExpired:
                            self.log("进程未响应退出命令，尝试终止...")
                            self.record_process.terminate()
                            try:
                                self.record_process.wait(timeout=2)
                                self.log("✓ 录制进程已终止")
                            except subprocess.TimeoutExpired:
                                self.record_process.kill()
                                self.log("✓ 录制进程已强制终止")
                    except (BrokenPipeError, OSError):
                        # 管道已断开，直接终止进程
                        if self.record_process.poll() is None:
                            self.record_process.terminate()
                            try:
                                self.record_process.wait(timeout=3)
                                self.log("✓ 录制进程已终止")
                            except subprocess.TimeoutExpired:
                                self.record_process.kill()
                                self.log("✓ 录制进程已强制终止")
                else:
                    # stdin已关闭，直接终止进程
                    if self.record_process.poll() is None:
                        self.record_process.terminate()
                        try:
                            self.record_process.wait(timeout=3)
                            self.log("✓ 录制进程已终止")
                        except subprocess.TimeoutExpired:
                            self.record_process.kill()
                            self.log("✓ 录制进程已强制终止")
                            
            except Exception as e:
                self.log(f"停止录制时发生错误: {str(e)}")
            finally:
                self.record_process = None
                self.camera_ready = False
                
        self.status_var.set("已停止录制")
        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.DISABLED)
        self.log("录制已停止，可重新连接设备启动摄像头")
        
    def on_closing(self):
        """程序关闭时的清理工作"""
        self.log("正在关闭程序...")
        
        # 停止预览
        if self.preview_active:
            self.stop_preview()
        
        # 关闭录制进程
        if self.record_process:
            try:
                if self.record_process.stdin and not self.record_process.stdin.closed:
                    try:
                        self.record_process.stdin.write('q\n')
                        self.record_process.stdin.flush()
                        self.record_process.wait(timeout=2)
                    except:
                        pass
                if self.record_process.poll() is None:
                    self.record_process.terminate()
                    try:
                        self.record_process.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        self.record_process.kill()
            except:
                pass
                
        # 保存配置
        self.save_config()
        
        # 关闭窗口
        self.root.destroy()
        
    def get_payload(self):
        """获取 Payload 文件"""
        if not self.adb_ready:
            self.log("错误: ADB工具未就绪")
            self.status_var.set("ADB工具未就绪")
            return
            
        self.log("开始获取 Payload 文件...")
        self.status_var.set("获取 Payload 中...")
        
        def payload_thread():
            try:
                # 创建本地下载目录
                local_dir = "payloads"
                if not os.path.exists(local_dir):
                    os.makedirs(local_dir)
                    
                # 列出设备上的文件
                self.log("检查设备上的 Payload 文件...")
                ls_cmd = self.get_adb_command('shell', 'ls', '-la', '/sdcard/Download/MagicMirror/')
                ls_result = subprocess.run(ls_cmd, capture_output=True, text=True, timeout=15)
                
                if ls_result.returncode != 0:
                    self.log("无法访问设备上的 MagicMirror 目录")
                    self.log("请确保设备已连接且目录存在")
                    self.status_var.set("获取失败")
                    return
                    
                self.log("设备上的文件:")
                self.log(ls_result.stdout)
                
                # 获取最新的 payload 文件
                # 这里假设我们需要获取所有 payload 文件
                self.log("开始下载 Payload 文件...")
                
                pull_cmd = self.get_adb_command('pull', '/sdcard/Download/MagicMirror/', local_dir)
                pull_result = subprocess.run(pull_cmd, capture_output=True, text=True, timeout=30)
                
                if pull_result.returncode == 0:
                    self.log("✓ Payload 文件下载成功")
                    self.log(f"文件已保存到: {os.path.abspath(local_dir)}")
                    
                    # 显示下载的文件
                    if os.path.exists(local_dir):
                        files = os.listdir(local_dir)
                        if files:
                            self.log("下载的文件:")
                            for file in files:
                                self.log(f"  - {file}")
                        else:
                            self.log("下载目录为空")
                    
                    # 下载成功后自动增加视频文件名编号
                    self.increment_filename_number()
                            
                    self.status_var.set("Payload 获取完成")
                else:
                    self.log(f"✗ 下载失败: {pull_result.stderr}")
                    self.status_var.set("获取失败")
                    
            except subprocess.TimeoutExpired:
                self.log("下载超时")
                self.status_var.set("下载超时")
            except Exception as e:
                self.log(f"获取 Payload 时发生错误: {str(e)}")
                self.status_var.set("获取失败")
                
        threading.Thread(target=payload_thread, daemon=True).start()

def main():
    """主函数"""
    root = tk.Tk()
    app = AndroidControlApp(root)
    
    def on_closing():
        """程序关闭时的清理工作"""
        # 保存最新配置
        app.save_config()
        
        if hasattr(app, 'record_process') and app.record_process:
            try:
                app.record_process.terminate()
                app.log("程序退出，已清理录制进程")
            except:
                pass
        
        # 停止预览
        if hasattr(app, 'preview_active') and app.preview_active:
            app.stop_preview()
            
        root.destroy()
    
    root.protocol("WM_DELETE_WINDOW", on_closing)
    
    try:
        root.mainloop()
    except KeyboardInterrupt:
        print("\n程序被用户中断")
        on_closing()

if __name__ == "__main__":
    main()
