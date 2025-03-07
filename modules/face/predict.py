import cv2
import numpy as np
from pathlib import Path
from loguru import logger
from ultralytics import YOLO
from huggingface_hub import hf_hub_download

class FaceMaskPredictor:
    def __init__(self):
        self._model = None
        self.model_id = "ultralytics/yolov8"
        self.model_name = "yolov8m-seg.pt"
        self.local_model_path = Path("models/ultralytics/seg/face_yolov8m-seg_60.pt")

    def _ensure_model_loaded(self):
        """Ensure the model is loaded, downloading it if necessary."""
        if self._model is not None:
            return

        if not self.local_model_path.exists():
            logger.info(f"Model not found locally at {self.local_model_path}. Downloading from Hugging Face...")
            self.local_model_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                hf_hub_download(
                    repo_id=self.model_id,
                    filename=self.model_name,
                    local_dir=self.local_model_path.parent,
                    local_dir_use_symlinks=False
                )
                logger.info("Model downloaded successfully")
            except Exception as e:
                logger.error(f"Failed to download model: {e}")
                raise

        try:
            self._model = YOLO(str(self.local_model_path))
            logger.info("Model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            raise

    def predict(self, image_path: str | Path) -> np.ndarray | None:
        """
        Predict face mask from an image.
        
        Args:
            image_path: Path to the input image
            
        Returns:
            np.ndarray | None: Binary mask if face detected, None otherwise
        """
        # Ensure model is loaded
        self._ensure_model_loaded()

        # Read image
        image = cv2.imread(str(image_path))
        if image is None:
            logger.error(f"Failed to read image at {image_path}")
            return None

        try:
            # Perform prediction
            results = self._model(image)
            result = results[0]

            # Process results if face detected
            if len(result.boxes) > 0:
                # Get segmentation mask
                mask = result.masks.data[0].cpu().numpy()
                
                # Resize mask to match input image
                mask = cv2.resize(mask, (image.shape[1], image.shape[0]))
                
                # Convert to binary mask
                mask = (mask > 0.5).astype(np.uint8) * 255
                
                # Save output mask
                output_path = Path("test/output")
                output_path.mkdir(parents=True, exist_ok=True)
                cv2.imwrite(str(output_path / "face_mask.png"), mask)
                
                return mask
            else:
                logger.warning("No face detected in the image")
                return None

        except Exception as e:
            logger.error(f"Error during prediction: {e}")
            return None

# Create a singleton instance
predictor = FaceMaskPredictor()

def predict_face_mask(image_path: str | Path) -> np.ndarray | None:
    """
    Convenience function to predict face mask using the singleton predictor.
    
    Args:
        image_path: Path to the input image
        
    Returns:
        np.ndarray | None: Binary mask if face detected, None otherwise
    """
    return predictor.predict(image_path)


# 使用示例
# mask = predict_face_mask('path/to/your/image.jpg')
# if mask is not None:
#     cv2.imwrite('face_mask.png', mask)
