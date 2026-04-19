# __init__.py
import os
import sys
import subprocess
import shutil
import folder_paths
from server import PromptServer
from .routes import get_workflows, read_txt, refresh_models
from .PSWorkflowConfig import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS

# ======================================================================
# 自动复制 example 工作流到 ComfyUI 目录（仅首次运行）
# ======================================================================
def copy_example_workflows():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    marker_file = os.path.join(current_dir, ".workflows_copied")
    
    # 只要标记文件存在，就直接跳过，完全不占用后续启动时间
    if not os.path.exists(marker_file):
        source_dir = os.path.join(current_dir, "example")
        target_dir = os.path.join(folder_paths.base_path, "user", "default", "workflows", "PSflows")
        
        if os.path.exists(source_dir):
            print("\n[PS_Connector] 首次安装：正在为您复制示例工作流...")
            try:
                os.makedirs(target_dir, exist_ok=True)
                for file_name in os.listdir(source_dir):
                    source_file = os.path.join(source_dir, file_name)
                    # 只复制文件，通常工作流是 .json 格式
                    if os.path.isfile(source_file) and file_name.endswith(".json"):
                        shutil.copy2(source_file, target_dir)
                        print(f"[PS_Connector] 已复制: {file_name}")
                        
                # 无论成功与否，都写入标记文件，确保以后不再执行
                with open(marker_file, 'w', encoding='utf-8') as f:
                    f.write("Workflows copied successfully.")
                print("[PS_Connector] ✅ 示例工作流复制完成！\n")
            except Exception as e:
                print(f"[PS_Connector] ❌ 复制工作流失败: {e}\n")
        else:
            # 如果没找到 example 文件夹，也生成标记文件，避免以后每次启动都报警
            with open(marker_file, 'w', encoding='utf-8') as f:
                f.write("No example folder found.")

copy_example_workflows()
# ======================================================================

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
