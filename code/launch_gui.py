import os
import sys
import subprocess

def main():
    # 获取当前脚本所在目录
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 构建gui.py的完整路径
    gui_path = os.path.join(current_dir, 'gui.py')
    
    # 获取Python解释器路径
    python_executable = sys.executable
    
    # 启动GUI程序
    subprocess.Popen([python_executable, gui_path], 
                    creationflags=subprocess.CREATE_NEW_CONSOLE)

if __name__ == '__main__':
    main() 