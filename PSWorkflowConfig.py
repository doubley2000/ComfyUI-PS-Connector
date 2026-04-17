# PSWorkflowConfig.py
import os
import sys
import json
import torch
import torch.nn.functional as F
from PIL import Image
import numpy as np
import folder_paths
import random

class AnyType(str):
    def __ne__(self, __value: object) -> bool:
        return False
any_type = AnyType("*")

class PSGetNode:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                # 节点本身的单行文本，供 PS UI 做 Label 备用
                "ui_label": ("STRING", {"default": ""}),
                # 新增：布尔项，用于定义图像或mask的必要性（前端 JS 会根据连线类型动态显隐）
                "is_required": ("BOOLEAN", {"default": True}),
            },
            "optional": {
                # 接受任意类型的输入（Image, Mask, Int, Float, String 等）
                "get": (any_type,),
            }
        }
    
    RETURN_TYPES = (any_type,)
    RETURN_NAMES = ("get",)
    FUNCTION = "passthrough"
    CATEGORY = "PS_Connector"

    def passthrough(self, ui_label="", is_required=True, get=None):
        # 运行时作为一个纯粹的直通节点，不修改任何数据
        return (get,)

class PSTextReceiver:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "text": ("STRING", {"forceInput": True}),
            }
        }
    
    RETURN_TYPES = ()
    OUTPUT_NODE = True
    FUNCTION = "receive_text"
    CATEGORY = "PS_Connector"

    def receive_text(self, text):
        # 抛出 UI 字典，前端 JS websocket 会自动将其截获并识别
        return {"ui": {"text": [text]}}
# ==========================================

class PSWorkflowConfig:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "model": ("MODEL",),
                "lora": ("MODEL",),
                "prompt": ("STRING", {"forceInput": True}),
                "size_logic": ("BOOLEAN", {"default": True}),
                "width": ("INT", {"default": 512}),
                "height": ("INT", {"default": 512}),
                "long_side_pixels": ("INT", {"default": 1024, "min": 256, "max": 8192, "step": 8}),
                "img1_req": ("BOOLEAN", {"default": True}),
                "msk1_req": ("BOOLEAN", {"default": True}),
                "img2_req": ("BOOLEAN", {"default": True}),
                "msk2_req": ("BOOLEAN", {"default": True}),
                "img3_req": ("BOOLEAN", {"default": True}),
                "msk3_req": ("BOOLEAN", {"default": True}),
                "img4_req": ("BOOLEAN", {"default": True}),
                "msk4_req": ("BOOLEAN", {"default": True}),
            },
            "optional": {
                "image1": ("IMAGE",),
                "mask1": ("MASK",),
                "image2": ("IMAGE",),
                "mask2": ("MASK",),
                "image3": ("IMAGE",),
                "mask3": ("MASK",),
                "image4": ("IMAGE",),
                "mask4": ("MASK",),
                "neg_prompt": ("STRING", {"forceInput": True}),
            }
        }
    RETURN_TYPES = () 
    FUNCTION = "do_nothing"
    CATEGORY = "PS_Connector"
    def do_nothing(self, **kwargs):
        return ()

class PSImageAndMaskScaler:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "width": ("INT", {"default": 512}),
                "height": ("INT", {"default": 512})
            },
            "optional": {
                "image": ("IMAGE",),
                "mask": ("MASK",)
            }
        }
    
    RETURN_TYPES = ("IMAGE", "MASK")
    FUNCTION = "scale"
    CATEGORY = "PS_Connector"
    def scale(self, width, height, image=None, mask=None):
        out_image = image
        out_mask = mask
        
        if image is not None:
            img = image.permute(0, 3, 1, 2)
            img = F.interpolate(img, size=(height, width), mode='bicubic', align_corners=False)
            out_image = img.permute(0, 2, 3, 1).clamp(0, 1)
            
        if mask is not None:
            if len(mask.shape) == 2:
                msk = mask.unsqueeze(0).unsqueeze(0)
            elif len(mask.shape) == 3:
                msk = mask.unsqueeze(1)
            else:
                msk = mask
            msk = F.interpolate(msk, size=(height, width), mode='bicubic', align_corners=False)
            out_mask = msk.squeeze(1).clamp(0, 1)
            
        if out_image is None:
            out_image = torch.zeros((1, height, width, 3), dtype=torch.float32)
        if out_mask is None:
            out_mask = torch.zeros((1, height, width), dtype=torch.float32)
        return (out_image, out_mask)


# ======= 新增/修改：并列预览节点 =======
class PSImagePreview:
    def __init__(self):
        self.output_dir = folder_paths.get_temp_directory()
        self.type = "temp"
        self.prefix_append = "_temp_" + ''.join(random.choice("abcdefghijklmnopqrstupvxyz") for x in range(5))

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {},
            "optional": {
                "image1": ("IMAGE",),
                "image2": ("IMAGE",),
                "mask": ("MASK",),
            }
        }
    
    RETURN_TYPES = ()
    OUTPUT_NODE = True
    FUNCTION = "preview"
    CATEGORY = "PS_Connector"

    def scale_tensor(self, tensor_img, target_width, target_height, is_mask=False):
        if is_mask:
            if len(tensor_img.shape) == 2:
                msk = tensor_img.unsqueeze(0).unsqueeze(0)
            elif len(tensor_img.shape) == 3:
                msk = tensor_img.unsqueeze(1)
            else:
                msk = tensor_img
            msk = F.interpolate(msk, size=(target_height, target_width), mode='bicubic', align_corners=False)
            return msk.squeeze(1).clamp(0, 1)
        else:
            img = tensor_img.permute(0, 3, 1, 2)
            img = F.interpolate(img, size=(target_height, target_width), mode='bicubic', align_corners=False)
            return img.permute(0, 2, 3, 1).clamp(0, 1)

    def preview(self, image1=None, image2=None, mask=None):
        if image1 is None and image2 is None and mask is None:
            return {"ui": {"images": []}}
            
        target_width = None
        target_height = None
        
        # 尺寸逻辑判定
        if image2 is not None:
            target_height = image2.shape[1]
            target_width = image2.shape[2]
        elif image1 is not None:
            target_height = image1.shape[1]
            target_width = image1.shape[2]
        elif mask is not None:
            if len(mask.shape) == 2:
                target_height, target_width = mask.shape
            else:
                target_height, target_width = mask.shape[1], mask.shape[2]

        processed_images = []
        
        # 处理 image1
        if image1 is not None:
            if image1.shape[1] != target_height or image1.shape[2] != target_width:
                img1_scaled = self.scale_tensor(image1, target_width, target_height, is_mask=False)
            else:
                img1_scaled = image1
            processed_images.append(("img1", img1_scaled))
            
        # 处理 image2
        if image2 is not None:
            processed_images.append(("img2", image2))
            
        # 处理 mask
        if mask is not None:
            if len(mask.shape) == 2:
                h, w = mask.shape
            else:
                h, w = mask.shape[1], mask.shape[2]
            
            if h != target_height or w != target_width:
                mask_scaled = self.scale_tensor(mask, target_width, target_height, is_mask=True)
            else:
                mask_scaled = mask
                
            # 将 mask 转为 3 通道图以便正常显示
            if len(mask_scaled.shape) == 2:
                mask_scaled = mask_scaled.unsqueeze(0).unsqueeze(-1).repeat(1, 1, 1, 3)
            elif len(mask_scaled.shape) == 3:
                mask_scaled = mask_scaled.unsqueeze(-1).repeat(1, 1, 1, 3)
            processed_images.append(("mask", mask_scaled))

        if not processed_images:
            return {"ui": {"images": []}}

        results = []
        
        # 分别保存每张图片，而不是拼合成一张。返回的多个图片会在 UI 中并列展示。
        for img_idx, (name, img_tensor) in enumerate(processed_images):
            for batch_number, image in enumerate(img_tensor):
                i = 255. * image.cpu().numpy()
                img_pil = Image.fromarray(np.clip(i, 0, 255).astype(np.uint8))
                
                # 文件名包含原输入标识(img1/img2/mask)保证不会相互覆盖
                filename = f"_{name}.png"
                full_path = os.path.join(self.output_dir, filename)
                img_pil.save(full_path, compress_level=4)
                
                results.append({
                    "filename": filename,
                    "subfolder": "",
                    "type": self.type
                })

        return {"ui": {"images": results}}

# ======= 新增：获取图像尺寸及逻辑控制节点 =======
class PSGetImageSize:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "image": ("IMAGE",),
                "width": ("INT", {"default": 512, "min": 1, "max": 16384, "step": 1}),
                "height": ("INT", {"default": 512, "min": 1, "max": 16384, "step": 1}),
                # 逻辑判断项：默认开启，开启时输出图像尺寸，关闭时输出输入框尺寸
                "use_image_size": ("BOOLEAN", {"default": True, "label": "Use Image Size"}),
            }
        }
    
    RETURN_TYPES = ("INT", "INT")
    RETURN_NAMES = ("width", "height")
    FUNCTION = "get_size"
    CATEGORY = "PS_Connector"

    def get_size(self, image, width, height, use_image_size):
        if use_image_size:
            # ComfyUI 的图像 tensor 形状通常为 (batch, height, width, channels)
            img_height = image.shape[1]
            img_width = image.shape[2]
            return (int(img_width), int(img_height))
        else:
            return (int(width), int(height))

# ===============================================
# 注册字典追加修改
NODE_CLASS_MAPPINGS = {
    "PSWorkflowConfig": PSWorkflowConfig,
    "PSImageAndMaskScaler": PSImageAndMaskScaler,
    "PSTextReceiver": PSTextReceiver,
    "PSGetNode": PSGetNode,
    "PSImagePreview": PSImagePreview,
    "PSGetImageSize": PSGetImageSize  # 注册新节点
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "PSWorkflowConfig": "PS Workflow Config (PS)",
    "PSImageAndMaskScaler": "PS Auto Scaler (Hidden)",
    "PSTextReceiver": "PS Text Receiver (LLM)",
    "PSGetNode": "PS Get (Custom UI)",
    "PSImagePreview": "PS Image Preview",
    "PSGetImageSize": "PS Get Image Size" # 注册新节点显示名称
}
