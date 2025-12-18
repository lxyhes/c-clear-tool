"""
C盘清理助手 - 专属图标生成器
"""

from PIL import Image, ImageDraw, ImageFont
import math

def create_professional_icon():
    """创建专业的 C盘清理助手图标"""
    sizes = [16, 32, 48, 64, 128, 256]
    images = []
    
    for size in sizes:
        img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        
        # 参数计算
        margin = max(1, size // 32)
        corner_radius = size // 5
        
        # 绘制圆角矩形背景（渐变蓝色效果）
        for y in range(size):
            # 模拟渐变
            ratio = y / size
            r = int(0 + (0 * ratio))
            g = int(120 - (40 * ratio))
            b = int(212 + (30 * ratio))
            
            for x in range(size):
                # 圆角检测
                in_rect = True
                corners = [
                    (corner_radius, corner_radius),
                    (size - corner_radius - 1, corner_radius),
                    (corner_radius, size - corner_radius - 1),
                    (size - corner_radius - 1, size - corner_radius - 1)
                ]
                
                if x < corner_radius and y < corner_radius:
                    dist = math.sqrt((x - corner_radius) ** 2 + (y - corner_radius) ** 2)
                    in_rect = dist <= corner_radius
                elif x >= size - corner_radius and y < corner_radius:
                    dist = math.sqrt((x - (size - corner_radius - 1)) ** 2 + (y - corner_radius) ** 2)
                    in_rect = dist <= corner_radius
                elif x < corner_radius and y >= size - corner_radius:
                    dist = math.sqrt((x - corner_radius) ** 2 + (y - (size - corner_radius - 1)) ** 2)
                    in_rect = dist <= corner_radius
                elif x >= size - corner_radius and y >= size - corner_radius:
                    dist = math.sqrt((x - (size - corner_radius - 1)) ** 2 + (y - (size - corner_radius - 1)) ** 2)
                    in_rect = dist <= corner_radius
                
                if in_rect:
                    img.putpixel((x, y), (r, g, b, 255))
        
        # 绘制硬盘图标（白色圆角矩形）
        disk_margin = size // 4
        disk_height = size // 3
        disk_top = (size - disk_height) // 2
        
        # 硬盘主体
        draw.rounded_rectangle(
            [disk_margin, disk_top, size - disk_margin, disk_top + disk_height],
            radius=max(2, size // 20),
            fill='white'
        )
        
        # 硬盘细节线条
        line_y = disk_top + disk_height // 4
        line_width = max(1, size // 32)
        for i in range(3):
            line_length = (size - disk_margin * 2) * (0.7 - i * 0.15)
            draw.rounded_rectangle(
                [disk_margin + size // 16, line_y + i * (line_width + max(1, size // 32)),
                 disk_margin + size // 16 + line_length, line_y + i * (line_width + max(1, size // 32)) + line_width],
                radius=max(1, line_width // 2),
                fill='#CCCCCC'
            )
        
        # 指示灯（绿色）
        led_size = max(2, size // 20)
        led_x = size - disk_margin - size // 8
        led_y = disk_top + disk_height // 4
        draw.ellipse([led_x - led_size, led_y - led_size, led_x + led_size, led_y + led_size], fill='#00E676')
        
        # C: 文字
        try:
            font_size = max(8, size // 4)
            font = ImageFont.truetype("arial.ttf", font_size)
        except:
            font = ImageFont.load_default()
        
        text = "C:"
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_x = disk_margin + size // 10
        text_y = disk_top + disk_height - font_size - max(2, size // 20)
        draw.text((text_x, text_y), text, fill='#0078D4', font=font)
        
        # 扫帚/清理图标（右下角）
        broom_size = size // 4
        broom_x = size - broom_size - size // 10
        broom_y = size - broom_size - size // 10
        
        # 扫帚柄
        handle_width = max(2, broom_size // 6)
        draw.rounded_rectangle(
            [broom_x + broom_size // 3, broom_y, 
             broom_x + broom_size // 3 + handle_width, broom_y + broom_size // 2],
            radius=max(1, handle_width // 2),
            fill='#FF9800'
        )
        
        # 扫帚头
        draw.rounded_rectangle(
            [broom_x, broom_y + broom_size // 2,
             broom_x + broom_size, broom_y + broom_size],
            radius=max(1, size // 30),
            fill='#795548'
        )
        
        # 闪光星星
        if size >= 48:
            star_x, star_y = size // 5, size // 5
            star_size = max(3, size // 20)
            draw.polygon([
                (star_x, star_y - star_size),
                (star_x + star_size // 3, star_y - star_size // 3),
                (star_x + star_size, star_y),
                (star_x + star_size // 3, star_y + star_size // 3),
                (star_x, star_y + star_size),
                (star_x - star_size // 3, star_y + star_size // 3),
                (star_x - star_size, star_y),
                (star_x - star_size // 3, star_y - star_size // 3),
            ], fill='white')
        
        images.append(img)
    
    # 保存为 ICO
    images[-1].save('icon.ico', format='ICO', sizes=[(s, s) for s in sizes], append_images=images[:-1])
    print("✅ 专业图标已生成: icon.ico")
    
    # 同时保存 PNG 预览
    images[-1].save('icon_preview.png', format='PNG')
    print("✅ 预览图已生成: icon_preview.png")

if __name__ == "__main__":
    print("🎨 正在生成 C盘清理助手专属图标...")
    create_professional_icon()
    print("\n📌 图标设计说明:")
    print("   - 蓝色渐变背景：代表 Windows 系统风格")
    print("   - 白色硬盘图标：代表 C 盘存储")
    print("   - 绿色指示灯：代表系统健康状态")
    print("   - 扫帚图标：代表清理功能")
    print("   - 闪光星星：代表清理后的干净效果")
