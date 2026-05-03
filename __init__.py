# __init__.py
import os
import sys
import subprocess
import shutil
import hashlib  # 新增：用于计算文件内容的哈希值
import folder_paths
from server import PromptServer
from .routes import get_workflows, read_txt, refresh_models
from .PSWorkflowConfig import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS

# ======================================================================
# 自动复制/更新 example 工作流到 ComfyUI 目录
# ======================================================================
def get_examples_hash(source_dir):
    """计算 source_dir 下所有 json 文件的综合 MD5 值，实现免版本号自动更新"""
    if not os.path.exists(source_dir):
        return "none"
    
    hash_md5 = hashlib.md5()
    try:
        # sorted 保证每次读取文件的顺序一致
        for file_name in sorted(os.listdir(source_dir)):
            if file_name.endswith(".json"):
                file_path = os.path.join(source_dir, file_name)
                # 读取文件内容计算 Hash，多个文件会不断累加计算出唯一的指纹
                with open(file_path, "rb") as f:
                    hash_md5.update(f.read())
        return hash_md5.hexdigest()
    except Exception:
        return "error"

def copy_example_workflows():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    marker_file = os.path.join(current_dir, ".workflows_copied")
    source_dir = os.path.join(current_dir, "example")
    target_dir = os.path.join(folder_paths.base_path, "user", "default", "workflows", "PSflows")
    
    # 1. 获取当前 example 文件夹下所有工作流内容的真实 Hash
    current_hash = get_examples_hash(source_dir)
    if current_hash in ["none", "error"]:
        return  # 如果 example 文件夹不存在或读取出错，直接跳过
        
    # 2. 读取上一次保存的 Hash 或标记内容
    saved_hash = ""
    if os.path.exists(marker_file):
        try:
            with open(marker_file, 'r', encoding='utf-8') as f:
                saved_hash = f.read().strip()
        except:
            pass
            
    # 3. 如果 Hash 完全一致，说明工作流没有任何修改，极速跳过，不占用启动时间
    if current_hash == saved_hash:
        return

    # 4. 如果 Hash 不同（旧用户的标记是纯文本、或者工作流被增删改了），执行复制
    print("\n[PS_Connector] 检测到示例工作流有更新或首次安装：正在为您同步...")
    try:
        os.makedirs(target_dir, exist_ok=True)
        for file_name in os.listdir(source_dir):
            source_file = os.path.join(source_dir, file_name)
            # 只复制文件，且仅限 .json 格式
            if os.path.isfile(source_file) and file_name.endswith(".json"):
                shutil.copy2(source_file, target_dir)
                print(f"[PS_Connector] 已同步: {file_name}")
                
        # 5. 同步成功后，将新的 Hash 值写入标记文件，确保以后不再重复执行
        with open(marker_file, 'w', encoding='utf-8') as f:
            f.write(current_hash)
        print("[PS_Connector] ✅ 示例工作流同步完成！\n")
        
    except Exception as e:
        print(f"[PS_Connector] ❌ 同步工作流失败: {e}\n")

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
