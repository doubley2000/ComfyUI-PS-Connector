# __init__.py
import os
import sys
import subprocess
from server import PromptServer
from .routes import get_workflows, read_txt, refresh_models
from .PSWorkflowConfig import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS

# ======================================================================
# 自动安装前置依赖：ComfyUI-Lora-Manager
# ======================================================================
def check_and_install_lora_manager():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    custom_nodes_dir = os.path.dirname(current_dir)
    target_folder = "ComfyUI-Lora-Manager" 
    target_path = os.path.join(custom_nodes_dir, target_folder)
    repo_url = "https://github.com/willmiao/ComfyUI-Lora-Manager.git" 

    if not os.path.exists(target_path):
        print(f"\n[PS_Connector] 检测到缺失核心依赖: {target_folder}。正在自动为您安装...")
        try:
            result = subprocess.run(
                ["git", "clone", repo_url, target_path], 
                check=True, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                text=True
            )
            print(f"[PS_Connector] ✅ 依赖插件 {target_folder} 安装成功！")
            print(f"[PS_Connector] ⚠️ 注意：由于是首次安装依赖，建议重启 ComfyUI 以确保其完全加载。\n")
        except Exception as e:
            print(f"\n[PS_Connector] ❌ 自动安装失败！请手动前往 custom_nodes 目录执行:")
            print(f"git clone {repo_url}")
            print(f"错误详情: {e}\n")

check_and_install_lora_manager()
# ======================================================================

server = PromptServer.instance
server.routes.get("/ps_helper/workflows")(get_workflows)
server.routes.post("/ps_helper/refresh")(refresh_models)
server.routes.get("/ps_helper/read_txt")(read_txt)

# 告诉 ComfyUI 加载当前目录下的 js 文件夹作为前端插件
WEB_DIRECTORY = "./js"

__all__ = ['NODE_CLASS_MAPPINGS', 'NODE_DISPLAY_NAME_MAPPINGS', 'WEB_DIRECTORY']
