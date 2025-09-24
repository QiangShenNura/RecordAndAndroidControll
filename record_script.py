import cv2
import time
import datetime
import os
import sys

# --- 配置参数 ---
FRAME_WIDTH = 640
FRAME_HEIGHT = 400
FPS = 240
RECORD_SECONDS = 31
OUTPUT_DIR = "videos"

# 曝光参数（根据相机调试可调整）
AUTO_EXPOSURE_MODE = 0.75   # 0.25=自动，0.75=手动
EXPOSURE_VALUE = -8         # 曝光锁定值（不同摄像头范围不同）

# --- 录制函数 ---
def record_video(cap, actual_fps, actual_width, actual_height):
    """录制视频并保存到文件"""
    print(f"开始录制 {RECORD_SECONDS} 秒视频...", flush=True)

    frames_buffer = []
    start_time = time.time()

    num_frames_to_capture = int(RECORD_SECONDS * actual_fps)

    for i in range(num_frames_to_capture):
        ret, frame = cap.read()
        if ret:
            frames_buffer.append(frame)
        else:
            print("录制过程中丢失一帧。", flush=True)

    end_time = time.time()
    record_duration = end_time - start_time
    actual_recorded_fps = len(frames_buffer) / record_duration if record_duration > 0 else 0

    print(f"录制完成。共捕获 {len(frames_buffer)} 帧。", flush=True)
    print(f"实际录制时长: {record_duration:.2f} 秒, 平均帧率: {actual_recorded_fps:.2f} FPS", flush=True)

    if frames_buffer:
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"Cam240_{timestamp}.mp4"
        filepath = os.path.join(OUTPUT_DIR, filename)

        print(f"正在保存文件到: {filepath}", flush=True)

        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(filepath, fourcc, actual_fps, (int(actual_width), int(actual_height)))

        for f in frames_buffer:
            out.write(f)

        out.release()
        print("文件保存成功。", flush=True)
    else:
        print("缓冲区为空，未保存视频。", flush=True)

# --- 主函数 ---
def main():
    # 检查命令行参数
    camera_index = 0
    if len(sys.argv) > 1:
        try:
            camera_index = int(sys.argv[1])
            print(f"使用指定的摄像头 {camera_index}", flush=True)
        except ValueError:
            print("警告: 摄像头索引参数无效，使用默认摄像头 0", flush=True)
    
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    cap = cv2.VideoCapture(camera_index)

    if not cap.isOpened():
        print(f"错误：无法打开摄像头 {camera_index}。", flush=True)
        return

    # 设置分辨率、帧率
    print(f"请求设置分辨率: {FRAME_WIDTH}x{FRAME_HEIGHT}", flush=True)
    print(f"请求设置帧率: {FPS} FPS", flush=True)
    
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT)
    cap.set(cv2.CAP_PROP_FPS, FPS)

    # 验证设置是否生效
    set_width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
    set_height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
    set_fps = cap.get(cv2.CAP_PROP_FPS)
    
    print(f"设置后分辨率: {int(set_width)}x{int(set_height)}", flush=True)
    print(f"设置后帧率: {set_fps} FPS", flush=True)
    
    # 如果分辨率不匹配，尝试其他方法
    if int(set_width) != FRAME_WIDTH or int(set_height) != FRAME_HEIGHT:
        print(f"警告: 摄像头不支持 {FRAME_WIDTH}x{FRAME_HEIGHT} 分辨率", flush=True)
        print("尝试强制设置...", flush=True)
        
        # 尝试不同的后端
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc('M', 'J', 'P', 'G'))
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_WIDTH)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT)
        
        final_width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
        final_height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
        print(f"最终分辨率: {int(final_width)}x{int(final_height)}", flush=True)

    # --- 锁定曝光 ---
    cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, AUTO_EXPOSURE_MODE)
    cap.set(cv2.CAP_PROP_EXPOSURE, EXPOSURE_VALUE)

    actual_width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
    actual_height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
    actual_fps = cap.get(cv2.CAP_PROP_FPS)
    actual_exposure = cap.get(cv2.CAP_PROP_EXPOSURE)

    print("摄像头初始化完成。", flush=True)
    print(f"实际分辨率: {int(actual_width)}x{int(actual_height)}, 实际帧率: {actual_fps} FPS", flush=True)
    print(f"曝光模式: {AUTO_EXPOSURE_MODE}, 实际曝光值: {actual_exposure}", flush=True)
    print("\n等待从标准输入接收's'命令...", flush=True)

    try:
        # 进入持续录制循环
        while True:
            try:
                # 使用readline()来读取输入，这样更适合管道通信
                char_received = sys.stdin.readline().strip()
                print(f"接收到命令: '{char_received}'", flush=True)

                if char_received == 's':
                    record_video(cap, actual_fps, actual_width, actual_height)
                    # 录制完成后，继续等待下一个命令
                    print("\n等待从标准输入接收's'命令...", flush=True)
                elif char_received == 'q' or char_received == 'quit':
                    print("收到退出命令，程序退出。", flush=True)
                    break
                elif char_received == '':
                    # EOF，退出循环
                    print("输入流已关闭，程序退出。", flush=True)
                    break
                else:
                    print(f"未知命令: '{char_received}'，继续等待...", flush=True)
                    
            except EOFError:
                print("输入流已关闭，程序退出。", flush=True)
                break
            except Exception as e:
                print(f"读取输入时发生错误: {e}", flush=True)
                break
                
    except KeyboardInterrupt:
        print("收到中断信号，程序退出。", flush=True)

    cap.release()
    cv2.destroyAllWindows()
    print("程序已退出。", flush=True)

if __name__ == "__main__":
    main()
