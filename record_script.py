import cv2
import time
import datetime
import os
import sys

# --- 配置参数 ---
FRAME_WIDTH = 360
FRAME_HEIGHT = 320
FPS = 240
RECORD_SECONDS = 5
OUTPUT_DIR = "videos"

# 曝光参数（根据相机调试可调整）
AUTO_EXPOSURE_MODE = 0.75   # 0.25=自动，0.75=手动
EXPOSURE_VALUE = -8         # 曝光锁定值（不同摄像头范围不同）

# --- 录制函数 ---
def record_video(cap, actual_fps, actual_width, actual_height):
    """录制视频并保存到文件"""
    print(f"开始录制 {RECORD_SECONDS} 秒视频...")

    frames_buffer = []
    start_time = time.time()

    num_frames_to_capture = int(RECORD_SECONDS * actual_fps)

    for i in range(num_frames_to_capture):
        ret, frame = cap.read()
        if ret:
            frames_buffer.append(frame)
        else:
            print("录制过程中丢失一帧。")

    end_time = time.time()
    record_duration = end_time - start_time
    actual_recorded_fps = len(frames_buffer) / record_duration if record_duration > 0 else 0

    print(f"录制完成。共捕获 {len(frames_buffer)} 帧。")
    print(f"实际录制时长: {record_duration:.2f} 秒, 平均帧率: {actual_recorded_fps:.2f} FPS")

    if frames_buffer:
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"Cam240_{timestamp}.mp4"
        filepath = os.path.join(OUTPUT_DIR, filename)

        print(f"正在保存文件到: {filepath}")

        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(filepath, fourcc, actual_fps, (int(actual_width), int(actual_height)))

        for f in frames_buffer:
            out.write(f)

        out.release()
        print("文件保存成功。")
    else:
        print("缓冲区为空，未保存视频。")

# --- 主函数 ---
def main():
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    cap = cv2.VideoCapture(0)

    if not cap.isOpened():
        print("错误：无法打开摄像头。")
        return

    # 设置分辨率、帧率
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT)
    cap.set(cv2.CAP_PROP_FPS, FPS)

    # --- 锁定曝光 ---
    cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, AUTO_EXPOSURE_MODE)
    cap.set(cv2.CAP_PROP_EXPOSURE, EXPOSURE_VALUE)

    actual_width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
    actual_height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
    actual_fps = cap.get(cv2.CAP_PROP_FPS)
    actual_exposure = cap.get(cv2.CAP_PROP_EXPOSURE)

    print("摄像头初始化完成。")
    print(f"实际分辨率: {int(actual_width)}x{int(actual_height)}, 实际帧率: {actual_fps} FPS")
    print(f"曝光模式: {AUTO_EXPOSURE_MODE}, 实际曝光值: {actual_exposure}")
    print("\n等待从标准输入接收's'命令...")

    char_received = sys.stdin.read(1)

    if char_received == 's':
        record_video(cap, actual_fps, actual_width, actual_height)
    else:
        print("收到非's'命令，程序退出。")

    cap.release()
    cv2.destroyAllWindows()
    print("程序已退出。")

if __name__ == "__main__":
    main()
