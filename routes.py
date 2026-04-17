import os
import json
import folder_paths
from aiohttp import web

def scan_folder(folder_name):
    base_paths = folder_paths.get_folder_paths(folder_name)
    if not base_paths: return []
    valid_exts = {".safetensors", ".ckpt", ".pt", ".pth", ".gguf", ".bin"}
    results = []
    for bp in base_paths:
        if not os.path.exists(bp): continue
        for root, dirs, files in os.walk(bp):
            for file in files:
                ext = os.path.splitext(file)[1].lower()
                if ext not in valid_exts: continue
                full_path = os.path.join(root, file)
                full_path_norm = os.path.normpath(full_path).replace("\\", "/")
                rel_path = os.path.relpath(full_path, bp).replace("\\", "/")
                base_path_no_ext, _ = os.path.splitext(full_path)
                json_path = base_path_no_ext + ".metadata.json" if os.path.exists(base_path_no_ext + ".metadata.json") else (base_path_no_ext + ".json" if os.path.exists(base_path_no_ext + ".json") else None)
                model_name, base_model, trained_words = "-", "-", "-"
                if json_path:
                    try:
                        with open(json_path, "r", encoding="utf-8") as f:
                            meta = json.load(f)
                            base_model = meta.get("base_model") or (meta.get("civitai", {}).get("baseModel") if "civitai" in meta else None) or "-"
                            model_name = meta.get("model_name") or (meta.get("civitai", {}).get("model", {}).get("name") if "civitai" in meta else None) or "-"
                            tw = meta.get("trainedWords") or (meta.get("civitai", {}).get("trainedWords") if "civitai" in meta else None)
                            trained_words = ",".join([str(w) for w in tw]) if isinstance(tw, list) else (str(tw).strip() if isinstance(tw, str) and tw.strip() else "-")
                    except: pass
                results.append({"file_name": rel_path, "model_name": model_name, "file_path": full_path_norm, "base_model": base_model, "trained_words": trained_words})
    return results

def update_txt(path, new_items, is_lora=False):
    # 1. 读取旧 TXT 数据，以相对路径(file_name)为 Key 建立索引
    existing_map = {}
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line: continue
                
                # 提取干扰符号，但要记住用户的特殊标记
                has_star = line.startswith("*")
                has_amp = line.startswith("&")
                
                clean_line = line.lstrip("*&")
                parts = clean_line.replace("｜", "|").split("|")
                
                if len(parts) >= 3:
                    rel_path = parts[0].strip()
                    old_base = parts[3].strip() if len(parts) > 3 else "-"
                    existing_map[rel_path] = {
                        "raw_line": line,      # 核心：完整保留用户原来的那一行！
                        "has_star": has_star,
                        "has_amp": has_amp,
                        "old_base": old_base
                    }

    # 2. 核心修复：基于绝对物理路径(file_path)对新扫描的数据进行去重！
    # 解决 ComfyUI scan_folder 扫描 overlapping 文件夹导致的天生重复问题
    unique_new_items = {}
    for item in new_items:
        unique_new_items[item["file_path"]] = item

    final_lines = []
    
    # 3. 构建最终写入的数据
    for item in unique_new_items.values():
        rel_path = item["file_name"]
        new_base = str(item["base_model"]).strip()
        is_new_unknown = (new_base == "-" or new_base.lower() == "unknown")

        if rel_path in existing_map:
            # 如果是老文件，检查是否需要“智能更新底模信息”
            old_data = existing_map[rel_path]
            old_raw_line = old_data["raw_line"]
            old_base = old_data["old_base"]
            old_is_unknown = (old_base == "-" or old_base.lower() == "unknown" or old_data["has_amp"])

            if old_is_unknown and not is_new_unknown:
                # 触发修复逻辑：以前不知道底模，现在扫到了同名 JSON 知道了底模
                prefix = "*" if old_data["has_star"] else "" # 继承用户的隐藏标记
                line = f"{prefix}{item['file_name']}｜{item['model_name']}｜{item['file_path']}｜{item['base_model']}"
                if is_lora:
                    tw = item['trained_words'] if item['trained_words'] else "-"
                    line += f"｜{tw}"
                final_lines.append(line)
            else:
                # 正常情况：原封不动地保留老数据！（完美保护你在 TXT 里手动写的内容和标记）
                final_lines.append(old_raw_line)
        else:
            # 这是一个全新下载的文件
            prefix = "&" if is_new_unknown else ""
            line = f"{prefix}{item['file_name']}｜{item['model_name']}｜{item['file_path']}｜{item['base_model']}"
            if is_lora:
                tw = item['trained_words'] if item['trained_words'] else "-"
                line += f"｜{tw}"
            final_lines.append(line)

    # 4. 覆写到磁盘
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(final_lines) + "\n")

async def get_workflows(request):
    base_dir = os.path.join(folder_paths.base_path, "user", "default", "workflows", "PSflows")
    workflows = []
    if os.path.exists(base_dir):
        for root, _, files in os.walk(base_dir):
            for file in files:
                if file.endswith(".json") and (file.startswith("(") or file.startswith("（")):
                    try:
                        with open(os.path.join(root, file), "r", encoding="utf-8") as f:
                            workflows.append({"name": file[:-5], "json": json.load(f)})
                    except: pass
    return web.json_response({"workflows": sorted(workflows, key=lambda x: x["name"])})

async def read_txt(request):
    psdate_dir = os.path.join(folder_paths.base_path, "user", "default", "PSdate")
    res = {"model_txt": "", "lora_txt": ""}
    for k in ["model", "lora"]:
        p = os.path.join(psdate_dir, f"{k}.txt")
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f: res[f"{k}_txt"] = f.read()
    return web.json_response(res)

async def refresh_models(request):
    psdate_dir = os.path.join(folder_paths.base_path, "user", "default", "PSdate")
    os.makedirs(psdate_dir, exist_ok=True)
    models = scan_folder("checkpoints") + scan_folder("diffusion_models") + scan_folder("unet")
    update_txt(os.path.join(psdate_dir, "model.txt"), models, False)
    update_txt(os.path.join(psdate_dir, "lora.txt"), scan_folder("loras"), True)
    return web.json_response({"status": "ok"})