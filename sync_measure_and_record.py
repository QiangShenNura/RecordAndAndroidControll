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
        
        # 配置文件路径
        self.config_file = self.get_config_path()
        
        # 从配置文件加载设置
        self.load_config()
        
        # 自动配置ADB工具
        self.setup_adb_tools()
        
        # 设置UI
        self.setup_ui()
        
        # 检查依赖
        self.check_dependencies()
        
        # 启动日志更新线程
        self.update_logs()
        
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
                    self.log(f"已加载配置: 文件名 = {'-'.join(self.filename_parts)}")
                else:
                    self.log("使用默认文件名配置")
            else:
                self.log("配置文件不存在，使用默认设置")
                # 保存默认配置
                self.save_config()
                
        except Exception as e:
            self.log(f"加载配置文件失败: {str(e)}，使用默认设置")
            
    def save_config(self):
        """保存设置到配置文件"""
        try:
            config = {
                'filename_parts': self.filename_parts,
                'last_updated': datetime.now().isoformat()
            }
            
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
                
            self.log(f"配置已保存: {self.config_file}")
            
        except Exception as e:
            self.log(f"保存配置文件失败: {str(e)}")
            
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
        
        # 控制按钮区域
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        
        # 第一行按钮
        self.start_button = ttk.Button(button_frame, text="开始测量并录制", 
                                      command=self.start_measure_and_record,
                                      style="Accent.TButton")
        self.start_button.grid(row=0, column=0, padx=(0, 10), pady=5, sticky=tk.W)
        self.start_button.config(state=tk.DISABLED)  # 初始状态禁用
        
        self.payload_button = ttk.Button(button_frame, text="获取 Payload", 
                                        command=self.get_payload)
        self.payload_button.grid(row=0, column=1, padx=(0, 10), pady=5, sticky=tk.W)
        
        self.connect_button = ttk.Button(button_frame, text="连接设备", 
                                        command=self.connect_device)
        self.connect_button.grid(row=0, column=2, padx=(0, 10), pady=5, sticky=tk.W)
        
        self.stop_button = ttk.Button(button_frame, text="停止录制", 
                                     command=self.stop_recording)
        self.stop_button.grid(row=0, column=3, padx=(0, 10), pady=5, sticky=tk.W)
        self.stop_button.config(state=tk.DISABLED)  # 初始状态禁用
        
        # 第二行按钮
        self.preview_button = ttk.Button(button_frame, text="测试预览", 
                                        command=self.toggle_preview)
        self.preview_button.grid(row=1, column=0, padx=(0, 10), pady=5, sticky=tk.W)
        
        self.adb_config_button = ttk.Button(button_frame, text="重新配置ADB", 
                                           command=self.reconfigure_adb)
        self.adb_config_button.grid(row=1, column=1, padx=(0, 10), pady=5, sticky=tk.W)
        
        # 状态栏
        self.status_var = tk.StringVar()
        self.status_var.set("就绪")
        status_label = ttk.Label(main_frame, textvariable=self.status_var, 
                                relief=tk.SUNKEN, anchor=tk.W)
        status_label.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E))
        
    def setup_filename_ui(self, parent):
        """设置文件名编辑界面"""
        # 显示当前文件名
        current_name = "-".join(self.filename_parts)
        
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
        
        full_name = "-".join(self.filename_parts)
        self.filename_display_var.set(full_name)
        
        # 自动保存配置（延迟保存，避免频繁写入）
        if hasattr(self, '_save_timer'):
            self.root.after_cancel(self._save_timer)
        self._save_timer = self.root.after(1000, self.save_config)  # 1秒后保存
        
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
            # 检查是否有虚拟环境
            venv_python = "venv/bin/python"
            if os.path.exists(venv_python):
                python_path = "venv/lib/python*/site-packages"
            else:
                python_path = None
                
            # 初始化摄像头
            self.preview_cap = cv2.VideoCapture(0)
            if not self.preview_cap.isOpened():
                self.log("错误: 无法打开摄像头进行预览")
                return
                
            # 设置与录制相同的参数
            self.preview_cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self.preview_cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 400)
            self.preview_cap.set(cv2.CAP_PROP_FPS, 240)
            self.preview_cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.75)
            self.preview_cap.set(cv2.CAP_PROP_EXPOSURE, -8)
            
            actual_width = self.preview_cap.get(cv2.CAP_PROP_FRAME_WIDTH)
            actual_height = self.preview_cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
            actual_fps = self.preview_cap.get(cv2.CAP_PROP_FPS)
            
            self.log(f"预览摄像头已启动: {int(actual_width)}x{int(actual_height)}, {actual_fps:.1f} FPS")
            
            self.preview_active = True
            self.preview_button.config(text="停止预览")
            
            # 启动预览线程
            self.preview_thread = threading.Thread(target=self.preview_loop, daemon=True)
            self.preview_thread.start()
            
        except Exception as e:
            self.log(f"启动预览失败: {str(e)}")
            
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
            
    def connect_device(self):
        """连接 Android 设备"""
        if not self.adb_ready:
            self.log("错误: ADB工具未就绪")
            self.status_var.set("ADB工具未就绪")
            return
            
        self.log("正在搜索 Android 设备...")
        self.status_var.set("连接设备中...")
        
        def connect_thread():
            try:
                # 检查设备连接
                adb_cmd = self.get_adb_command('devices')
                result = subprocess.run(adb_cmd, 
                                      capture_output=True, text=True, timeout=10)
                
                if result.returncode == 0:
                    lines = result.stdout.strip().split('\n')[1:]  # 跳过标题行
                    devices = [line for line in lines if line.strip() and 'device' in line]
                    
                    if devices:
                        self.log(f"找到 {len(devices)} 个设备:")
                        for device in devices:
                            self.log(f"  - {device}")
                        
                        # 设备连接成功，启动摄像头
                        self.log("设备连接成功，正在启动摄像头...")
                        if self.start_camera():
                            self.status_var.set("设备已连接，摄像头就绪")
                            # 启用开始录制按钮
                            self.start_button.config(state=tk.NORMAL)
                            self.stop_button.config(state=tk.NORMAL)
                        else:
                            self.status_var.set("摄像头启动失败")
                    else:
                        self.log("未找到已连接的设备")
                        self.log("请确保:")
                        self.log("1. 设备已开启开发者选项和USB调试")
                        self.log("2. 设备与电脑在同一WiFi网络")
                        self.log("3. 已通过 'adb connect <设备IP>:5555' 连接")
                        self.status_var.set("未找到设备")
                else:
                    self.log(f"ADB 命令执行失败: {result.stderr}")
                    self.status_var.set("连接失败")
                    
            except subprocess.TimeoutExpired:
                self.log("连接超时")
                self.status_var.set("连接超时")
            except Exception as e:
                self.log(f"连接设备时发生错误: {str(e)}")
                self.status_var.set("连接错误")
                
        threading.Thread(target=connect_thread, daemon=True).start()
        
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
            
            # 使用合适的Python解释器启动子进程，捕获输出
            self.record_process = subprocess.Popen(
                [python_executable, record_script_path],
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
            custom_filename = "-".join(self.filename_parts) + ".mp4"
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
                
                # 4. 等待录制完成
                self.log("等待录制完成...")
                self.record_process.wait()
                self.log("✓ 录制完成")
                    
                self.status_var.set("测量录制完成")
                
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
                if self.record_process.stdin and not self.record_process.stdin.closed:
                    self.record_process.stdin.close()
                if self.record_process.poll() is None:
                    self.record_process.terminate()
                    # 给进程一些时间来正常退出
                    try:
                        self.record_process.wait(timeout=5)
                        self.log("✓ 录制进程已正常退出")
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
