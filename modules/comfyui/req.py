import asyncio
import json
import os
import random
import sys
from random import randint
from datetime import datetime
import io
import time
import uuid
from pathlib import Path
from PIL import Image
from typing import Dict, List, Tuple, Optional

import dotenv
import httpx
from loguru import logger

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from modules.io import load_json
from modules.io.image import load_image_to_base64
from modules.comfyui.redis_client import ComfyUIRedisClient

dotenv.load_dotenv()

prompt = load_json("modules/comfyui/workflows/1216_v1.json")
server_address = os.environ.get("COMFYUI_HOST")
server_port = os.environ.get("COMFYUI_PORT")
redis_client = ComfyUIRedisClient(
    host=os.environ.get("REDIS_HOST", "localhost"),
    port=int(os.environ.get("REDIS_PORT", 6379)),
    db=int(os.environ.get("REDIS_DB", 0)),
)
resize_short_edge = int(os.environ.get("RESIZE_SHORT_EDGE", 1536))


async def queue_prompt(prompt: dict) -> str:
    """Submit a prompt to ComfyUI and return the prompt ID"""
    p = {"prompt": prompt}
    data = json.dumps(p).encode("utf-8")

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"http://{server_address}:{server_port}/prompt", content=data
        )
        result = response.json()
        prompt_id = result.get("prompt_id")

        if prompt_id:
            await redis_client.set_task_status(prompt_id, "PENDING")
            logger.info(f"Task submitted with ID: {prompt_id}")
            return prompt_id
        raise Exception("Failed to get prompt_id from response")


async def get_history(prompt_id: str) -> dict:
    """Get task history from ComfyUI"""
    url = f"http://{server_address}:{server_port}/history/{prompt_id}"
    logger.info(url)
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        return response.json()


async def _get_comfy_image_bytes(image: dict, server_address: str) -> bytes:
    """Download ComfyUI image"""
    params = {
        "filename": image["filename"],
        "subfolder": image.get("subfolder", ""),
        "type": image["type"],
        "rand": random.random(),
    }

    async with httpx.AsyncClient(timeout=60) as client:
        url = f"http://{server_address}/view"
        response = await client.get(url, params=params)
        return response.content


async def get_result(
    prompt_id: str, max_retries: int = 60, retry_delay: int = 5
) -> Tuple[Optional[Dict[str, List[bytes]]], str]:
    """
    Get task result with retries and Redis caching
    Returns: (output_images, status)
    """
    # Check Redis cache first
    task_status = await redis_client.get_task_status(prompt_id)
    if task_status and task_status["status"] == "COMPLETED":
        # 如果任务完成，返回图片路径而不是图片数据
        return task_status["image_paths"], "SUCCESS"

    for attempt in range(max_retries):
        try:
            history = await get_history(prompt_id)
            history = history[prompt_id]

            if "outputs" not in history:
                await asyncio.sleep(retry_delay)
                continue

            outputs = history["outputs"]
            output_images = {}

            # Process images
            tasks = []
            for node_id, node_output in outputs.items():
                if "images" in node_output:
                    for image in node_output["images"]:
                        task = asyncio.ensure_future(
                            _get_comfy_image_bytes(
                                image, server_address=f"{server_address}:{server_port}"
                            )
                        )
                        tasks.append((node_id, task))

            # Process images and save them
            for node_id, task in tasks:
                image_output = await task
                if node_id in output_images:
                    output_images[node_id].append(image_output)
                else:
                    output_images[node_id] = [image_output]

            if output_images:
                # 保存图片到本地并获取路径
                # saved_paths = save_local_images(output_images, f"task_{prompt_id}")
                # 只将路径信息存入Redis
                await redis_client.set_task_status(
                    prompt_id, "COMPLETED", {"image_paths": []}
                )
                return output_images, "SUCCESS"

        except Exception as e:
            logger.error(f"Error getting result: {str(e)}")
            if attempt == max_retries - 1:
                await redis_client.set_task_status(
                    prompt_id, "FAILED", {"error": str(e)}
                )
                return None, "FAILED"

        await asyncio.sleep(retry_delay)

    await redis_client.set_task_status(prompt_id, "TIMEOUT")
    return None, "TIMEOUT"


def save_local_images(
    output_images: Dict[str, List[bytes]], task_name: str, base_path: str = "outputs"
) -> List[str]:
    """Save images to local folder and return paths"""
    if not output_images:
        return []

    saved_paths = []
    current_date = datetime.now().strftime("%Y-%m-%d")
    output_path = Path(base_path) / "daily" / current_date / task_name
    output_path.mkdir(parents=True, exist_ok=True)

    for node_id, images_bytes in output_images.items():
        for idx, image_data in enumerate(images_bytes):
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{timestamp}_{node_id}_{idx}_{str(uuid.uuid4())[:8]}.png"
            file_path = output_path / filename

            image = Image.open(io.BytesIO(image_data))
            image.save(file_path, format="PNG")
            saved_paths.append(str(file_path))

    return saved_paths


async def process_image_task(prompt: dict, task_name: str) -> List[str]:
    """Process a complete image generation task"""
    try:
        # Submit task
        prompt_id = await queue_prompt(prompt)

        # Get results with retries
        output_images, status = await get_result(prompt_id)
        if status != "SUCCESS":
            logger.error(f"Task failed with status: {status}")
            return []

        # Save images
        return save_local_images(output_images, task_name)

    except Exception as e:
        logger.error(f"Error processing task: {str(e)}")
        return []


# async def get_result_test(prompt_id):
#     output_images, status = await get_result(prompt_id)


async def single_task(folder: str, changed_file: str):
    folder_name = Path(folder).name
    folder_path = Path(folder)  # 使用 Path 对象处理路径

    # 使用 Path 对象正确拼接路径
    prompt["5"]["inputs"]["image_base64"] = load_image_to_base64(
        str(folder_path / changed_file), resize_short_edge=resize_short_edge
    )

    # 检查原图1
    for ext in [".jpg", ".png"]:
        orig1_path = folder_path / f"原图1{ext}"
        if orig1_path.exists():
            prompt["12"]["inputs"]["image_base64"] = load_image_to_base64(
                str(orig1_path), resize_short_edge=resize_short_edge
            )
            break

    # 检查原图2
    for ext in [".jpg", ".png"]:
        orig2_path = folder_path / f"原图2{ext}"
        if orig2_path.exists():
            prompt["490"]["inputs"]["image_base64"] = load_image_to_base64(
                str(orig2_path), resize_short_edge=resize_short_edge
            )
            break
    else:  # 如果原图2都不存在
        prompt["523"]["inputs"]["value"] = False

    prompt["42"]["inputs"]["value"] = randint(1, 1000000)
    prompt["306"]["inputs"]["noise_seed"] = randint(1, 1000000)

    async def main():
        saved_paths = await process_image_task(prompt, folder_name)
        logger.info(f"Saved images: {saved_paths}")
        await redis_client.close()

    start = time.perf_counter()
    await main()
    end = time.perf_counter()
    logger.info(f"Time taken: {end - start} seconds")


# Example usage
if __name__ == "__main__":
    ref = r"F:/Work/WCY/base/常用"
    folder = r"F:/Work/WCY/WCY-AI需求12.14/B55031511  牛仔裤N30731511"

    # asyncio.run(get_result_test("f4e04e40-dfba-4afc-af82-b1ea49b9defa"))
