import os
from subprocess import run, PIPE

def create_mockup(input_image, mask_image, flower_image, output_file="mockup.png", 
                 pattern_size=900, start_x=400, start_y=100):
    """
    创建模拟图效果
    
    Args:
        input_image: 主输入图片路径 (例如 t.jpg)
        mask_image: 遮罩图片路径 (例如 t-mask.png)
        flower_image: 花纹图片路径 (例如 flower.jpg)
        output_file: 输出文件名 (默认为 mockup.png)
        pattern_size: 花纹大小 (默认 400)
        start_x: 水平起始位置 (默认 630)
        start_y: 垂直起始位置 (默认 405)
        pattern_size=1250, start_x=400, start_y=150(印花)
    """
    # 修改获取图片尺寸的命令
    size_cmd = f'convert "{input_image}" -format "%[fx:w]x%[fx:h]" info:'
    try:
        result = run(size_cmd, shell=True, capture_output=True, text=True)
        if result.stdout.strip():
            width, height = map(int, result.stdout.strip().split('x'))
        else:
            width, height = 1000, 1000
            print("警告：无法获取图片尺寸，使用默认值 1000x1000")
    except Exception as e:
        width, height = 1000, 1000
        print(f"获取图片尺寸时出错: {str(e)}，使用默认值 1000x1000")
    
    commands = [
        # 首先缩小花纹图片
        f'convert {flower_image} -resize {pattern_size}x{pattern_size} resized_flower_tmp.png',
        
        # 创建调整图
        f'convert {input_image} ( -clone 0 -fill "#f1f1f1" -colorize 100 ) {mask_image} -compose DivideSrc -composite adjustment_map.jpg',
        
        # 创建标准化图
        f'convert {input_image} {mask_image} -alpha off -colorspace gray -compose CopyOpacity -composite normalized_map_tmp.mpc',
        
        # 创建位移图 - 调整这里的百分比可以改变凹凸效果
        'convert normalized_map_tmp.mpc -evaluate subtract 30% -background grey50 -alpha remove -alpha off displacement_map_tmp.mpc',
        # 调整模糊程度可以改变凹凸的柔和度
        'convert displacement_map_tmp.mpc -blur 0x50 displacement_map.png',
        
        # 创建光照图 - 调整这里的百分比可以改变光照强度
        'convert normalized_map_tmp.mpc -evaluate subtract 50% -background grey50 -alpha remove -alpha off lighting_map_tmp.mpc',
        # 调整这里的 grey50 可以改变整体亮度
        'convert lighting_map_tmp.mpc ( -clone 0 -fill grey48 -colorize 100 ) -compose lighten -composite lighting_map.png',
        
        # 创建临时文件
        'convert resized_flower_tmp.png -bordercolor transparent -border 1 tmp.mpc',
        
        # 应用透视变换
        f'convert {input_image} -alpha transparent ( tmp.mpc +distort perspective "\
            0,0,{start_x},{start_y},\
            0,{pattern_size},{start_x},{start_y + pattern_size},\ 
            {pattern_size},{pattern_size},{start_x + pattern_size},{start_y + pattern_size},\
            {pattern_size},0,{start_x + pattern_size},{start_y}\
        " ) -background transparent -layers merge +repage tmp.mpc',
        
        # 应用效果
        'convert tmp.mpc -background transparent -alpha remove tmp.mpc',
        # 位移效果的强度 (20x20)
        'convert tmp.mpc displacement_map.png -compose displace -set option:compose:args 20x20 -composite tmp.mpc',
        # 光照效果的混合模式和强度
        'convert tmp.mpc ( -clone 0 lighting_map.png -compose hardlight -composite ) +swap -compose CopyOpacity -composite tmp.mpc',
        # 调整图的混合强度
        'convert tmp.mpc ( -clone 0 adjustment_map.jpg -compose multiply -composite ) +swap -compose CopyOpacity -composite tmp.mpc',
        
        # 最终合成
        f'convert {input_image} tmp.mpc {mask_image} -compose over -composite {output_file}'
    ]
    
    try:
        # 执行所有命令
        for cmd in commands:
            run(cmd, shell=True, check=True)
            
        # 清理临时文件
        temp_files = [
            'adjustment_map.jpg', 'normalized_map_tmp.mpc', 'displacement_map_tmp.mpc',
            'displacement_map.png', 'lighting_map_tmp.mpc', 'lighting_map.png',
            'tmp.mpc'
        ]
        for file in temp_files:
            if os.path.exists(file):
                os.remove(file)
                
        print(f"模拟图已成功创建: {output_file}")
        
    except Exception as e:
        print(f"处理过程中出错: {str(e)}")

if __name__ == "__main__":
    # 使用示例
    create_mockup("t.jpg", "mask2.png", "output.png")