import subprocess
import sys
import time

# 定义要启动的录制脚本的路径
# 确保在同一目录下，或者提供完整路径
record_script_path = "record_script.py"

def start_and_trigger_recording():
    """启动录制脚本并发送's'命令"""
    print(f"正在启动 {record_script_path}...")

    # 使用当前解释器 (sys.executable) 启动子进程，保证是 venv 的 Python
    process = subprocess.Popen(
        [sys.executable, record_script_path],
        stdin=subprocess.PIPE,
        text=True
    )

    print("子进程已启动。等待 3 秒以确保它准备就绪...")
    time.sleep(3)

    # 通过管道向子进程发送 's'
    print("正在发送 's' 命令...")
    process.stdin.write('s')
    process.stdin.flush()  # 确保数据立即被发送

    # 关闭管道并等待子进程完成
    process.stdin.close()
    print("命令发送完毕，等待子进程退出...")

    process.wait()  # 等待子进程执行完毕
    print("子进程已完成，主程序退出。")

if __name__ == "__main__":
    start_and_trigger_recording()
