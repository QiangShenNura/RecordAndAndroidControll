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

class AndroidControlApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Android 设备控制与录制")
        self.root.geometry("800x600")
        
        # 日志队列用于线程间通信
        self.log_queue = queue.Queue()
        
        # 录制子进程
        self.record_process = None
        self.camera_ready = False  # 摄像头是否已准备就绪
        
        # 设置UI
        self.setup_ui()
        
        # 检查依赖
        self.check_dependencies()
        
        # 启动日志更新线程
        self.update_logs()
        
    def setup_ui(self):
        """设置用户界面"""
        # 主框架
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 配置网格权重
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(1, weight=1)
        
        # 标题
        title_label = ttk.Label(main_frame, text="Android 设备控制与录制", 
                               font=("Arial", 16, "bold"))
        title_label.grid(row=0, column=0, pady=(0, 10))
        
        # 日志显示区域
        log_frame = ttk.LabelFrame(main_frame, text="日志输出", padding="5")
        log_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, height=20, width=80)
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 控制按钮区域
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        
        # 按钮
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
        
        # 状态栏
        self.status_var = tk.StringVar()
        self.status_var.set("就绪")
        status_label = ttk.Label(main_frame, textvariable=self.status_var, 
                                relief=tk.SUNKEN, anchor=tk.W)
        status_label.grid(row=3, column=0, sticky=(tk.W, tk.E))
        
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
        
        # 检查 ADB
        if self.check_adb():
            self.log("✓ ADB 已安装")
        else:
            self.log("✗ ADB 未安装")
            self.show_adb_install_instructions()
            
        # 检查录制脚本
        if os.path.exists("record_script.py"):
            self.log("✓ 录制脚本已找到")
        else:
            self.log("✗ 录制脚本 (record_script.py) 未找到")
            
    def check_adb(self):
        """检查 ADB 是否已安装"""
        try:
            result = subprocess.run(['adb', 'version'], 
                                  capture_output=True, text=True, timeout=10)
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False
            
    def show_adb_install_instructions(self):
        """显示 ADB 安装说明"""
        system = platform.system()
        
        if system == "Darwin":  # macOS
            instructions = """
ADB 安装说明 (macOS):

方法1 - 使用 Homebrew (推荐):
brew install android-platform-tools

方法2 - 手动安装:
1. 访问 https://developer.android.com/studio/releases/platform-tools
2. 下载 SDK Platform-Tools for Mac
3. 解压并将路径添加到 PATH 环境变量

安装完成后请重启程序。
"""
        elif system == "Windows":
            instructions = """
ADB 安装说明 (Windows):

方法1 - 使用 Chocolatey:
choco install adb

方法2 - 使用 Scoop:
scoop install adb

方法3 - 手动安装:
1. 访问 https://developer.android.com/studio/releases/platform-tools
2. 下载 SDK Platform-Tools for Windows
3. 解压并将路径添加到系统 PATH 环境变量

安装完成后请重启程序。
"""
        else:  # Linux
            instructions = """
ADB 安装说明 (Linux):

Ubuntu/Debian:
sudo apt update
sudo apt install android-tools-adb

CentOS/RHEL/Fedora:
sudo yum install android-tools
# 或
sudo dnf install android-tools

Arch Linux:
sudo pacman -S android-tools

安装完成后请重启程序。
"""
        
        # 创建安装说明窗口
        install_window = tk.Toplevel(self.root)
        install_window.title("ADB 安装说明")
        install_window.geometry("600x400")
        
        text_widget = scrolledtext.ScrolledText(install_window, wrap=tk.WORD)
        text_widget.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        text_widget.insert(tk.END, instructions)
        text_widget.config(state=tk.DISABLED)
        
    def connect_device(self):
        """连接 Android 设备"""
        self.log("正在搜索 Android 设备...")
        self.status_var.set("连接设备中...")
        
        def connect_thread():
            try:
                # 检查设备连接
                result = subprocess.run(['adb', 'devices'], 
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
            if self.record_process and self.record_process.stdout:
                try:
                    for line in iter(self.record_process.stdout.readline, ''):
                        if line:
                            # 移除换行符并添加前缀
                            clean_line = line.rstrip('\n\r')
                            if clean_line:
                                self.log(f"[录制] {clean_line}")
                                
                                # 检查是否是摄像头就绪的信号
                                if "等待从标准输入接收's'命令" in clean_line:
                                    self.camera_ready = True
                        
                        # 检查进程是否已结束
                        if self.record_process.poll() is not None:
                            break
                except Exception as e:
                    self.log(f"读取子进程输出时发生错误: {str(e)}")
                    
        threading.Thread(target=read_output, daemon=True).start()
            
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
                adb_result = subprocess.run(['adb', 'shell', 'input', 'text', 's'], 
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
                ls_result = subprocess.run([
                    'adb', 'shell', 'ls', '-la', '/sdcard/Download/MagicMirror/'
                ], capture_output=True, text=True, timeout=15)
                
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
                
                pull_result = subprocess.run([
                    'adb', 'pull', '/sdcard/Download/MagicMirror/', local_dir
                ], capture_output=True, text=True, timeout=30)
                
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
        if hasattr(app, 'record_process') and app.record_process:
            try:
                app.record_process.terminate()
                app.log("程序退出，已清理录制进程")
            except:
                pass
        root.destroy()
    
    root.protocol("WM_DELETE_WINDOW", on_closing)
    
    try:
        root.mainloop()
    except KeyboardInterrupt:
        print("\n程序被用户中断")
        on_closing()

if __name__ == "__main__":
    main()