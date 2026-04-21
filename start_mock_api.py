"""
启动脚本 - 同时启动Mock API和主服务
"""
import subprocess
import sys
import os
import time

def install_requirements():
    """安装依赖"""
    print("正在安装依赖...")

    # 安装后端依赖
    backend_dir = os.path.join(os.path.dirname(__file__), "backend")
    req_file = os.path.join(backend_dir, "requirements.txt")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", req_file])

    print("依赖安装完成！")

def start_mock_api():
    """启动Mock CRM API"""
    print("正在启动Mock CRM API (端口8001)...")
    mock_api_path = os.path.join(os.path.dirname(__file__), "mock-api", "server.py")
    return subprocess.Popen(
        [sys.executable, mock_api_path],
        cwd=os.path.dirname(__file__)
    )

def start_main_api():
    """启动主API服务"""
    print("正在启动CRM营业受理智能体API (端口8000)...")
    main_path = os.path.join(os.path.dirname(__file__), "backend", "main.py")
    return subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "main:app", "--reload", "--port", "8000"],
        cwd=os.path.join(os.path.dirname(__file__), "backend")
    )

def main():
    # 安装依赖
    install_requirements()

    # 启动服务
    mock_api = start_mock_api()
    time.sleep(2)  # 等待Mock API启动

    main_api = start_main_api()

    try:
        print("\n服务已启动！")
        print("- Mock API: http://localhost:8001")
        print("- 主API: http://localhost:8000")
        print("- 前端页面: http://localhost:8000")
        print("\n按Ctrl+C停止服务...")

        # 保持运行
        main_api.wait()

    except KeyboardInterrupt:
        print("\n正在停止服务...")
        mock_api.terminate()
        main_api.terminate()
        print("服务已停止！")

if __name__ == "__main__":
    main()
