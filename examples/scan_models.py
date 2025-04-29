from pathlib import Path
from src.model_scanner import ModelScanner, ModelType

def main():
    workflow_path = Path("workflows/flux-i2i/wf-0108.json")
    scanner = ModelScanner(workflow_path)
    
    # 扫描所有模型
    result = scanner.scan()
    
    # 按类型分组打印
    models_by_type = {}
    for model in result.models:
        if model.model_type not in models_by_type:
            models_by_type[model.model_type] = []
        models_by_type[model.model_type].append(model)
    
    for model_type, models in models_by_type.items():
        print(f"\n{model_type.value}:")
        for model in models:
            print(f"  - {model}")
            print(f"    Full path: {model.full_path}")


if __name__ == "__main__":
    main() 