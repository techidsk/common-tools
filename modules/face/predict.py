import cv2
import numpy as np
from ultralytics import YOLO


def predict_face_mask(image_path):
    # 加载模型
    model = YOLO("models/ultralytics/seg/face_yolov8m-seg_60.pt")

    # 读取图片
    image = cv2.imread(image_path)

    # 进行预测
    results = model(image)

    # 获取第一个检测结果（假设只有一张脸）
    result = results[0]

    # 如果检测到脸部
    if len(result.boxes) > 0:
        # 获取分割mask
        mask = result.masks.data[0].cpu().numpy()

        # 将mask调整为与原图相同的大小
        mask = cv2.resize(mask, (image.shape[1], image.shape[0]))

        # 将mask转换为二值图像
        mask = (mask > 0.5).astype(np.uint8) * 255

        # 保存mask
        cv2.imwrite("test/output/face_mask.png", mask)
        return mask
    else:
        print("No face detected in the image.")
        return None


# 使用示例
# mask = predict_face_mask('path/to/your/image.jpg')
# if mask is not None:
#     cv2.imwrite('face_mask.png', mask)
