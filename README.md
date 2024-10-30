# common-tools
个人用的开发库


## 说明
使用 uv 创建 venv

### 安装 UV
```bash
# With pip.
pip install uv
```

To create a virtual environment:

```
uv venv  # Create a virtual environment at `.venv`.
```
To activate the virtual environment:

###  On macOS and Linux.
```
source .venv/bin/activate
```

### On Windows.
```
.venv\Scripts\activate
```

### 安装依赖
```
uv pip install -r requirements.txt 
```