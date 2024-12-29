import logging
import os
from PIL import Image
from tqdm import tqdm
import hashlib

# 设置Pillow库的图像大小限制
Image.MAX_IMAGE_PIXELS = None  # 或者设置为一个足够大的数值

# 指定压缩质量参数
JPEG_QUALITY = 20
PNG_COMPRESSION_LEVEL = 9  # PNG压缩级别，0-9，9为最高压缩

# 获取当前工作目录
current_dir = os.getcwd()


# 计算文件内容的哈希值
def calculate_file_hash(file_path, hash_algorithm='sha256'):
    """
    计算文件本身的哈希值。

    参数:
        file_path (str): 文件路径。
        hash_algorithm (str): 哈希算法，默认为 'sha256'。

    返回:
        str: 文件的哈希值。
    """
    try:
        # 创建指定算法的哈希对象
        hash_func = hashlib.new(hash_algorithm)
        # 以二进制方式打开文件并计算哈希值
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b''):
                hash_func.update(chunk)
        # 返回哈希值的十六进制表示
        return hash_func.hexdigest()
    except Exception as e:
        logging.info(f"计算文件哈希时出错: {e}")
        return None


# 压缩图片并保存
def compress_image(image_path, output_path):
    try:
        with Image.open(image_path) as img:
            # 如果图片是JPEG格式，调整质量参数
            if img.format == 'JPEG':
                img.save(output_path, 'JPEG', quality=JPEG_QUALITY)
            # 如果图片是PNG格式，调整压缩级别
            elif img.format == 'PNG':
                img.save(output_path, 'PNG', compress_level=PNG_COMPRESSION_LEVEL, optimize=True)
            # 对于GIF格式，尝试减少颜色数量
            elif img.format == 'GIF':
                img.save(output_path, 'GIF', optimize=True, colors=256)
            # 对于其他格式，尝试使用默认参数保存
            else:
                img.save(output_path)
            logging.info(f"压缩图像从 {image_path} 到 {output_path}")
    except Exception as e:
        # 捕获异常并返回错误信息
        return f"Error processing {image_path}: {e}"
    return None


# 从 created_folder_path.txt 文件中读取路径
def get_folder_from_txt(txt_path):
    """
    从 created_folder_path.txt 文件中读取路径。

    参数:
        txt_path (str): created_folder_path.txt 文件的路径。

    返回:
        str: 文件中保存的路径，若文件不存在或为空，则返回 None。
    """
    try:
        with open(txt_path, 'r') as file:
            folder_path = file.readline().strip()
            if folder_path:
                return folder_path
            else:
                logging.info(f"{txt_path} 文件为空。")
                return None
    except FileNotFoundError:
        logging.info(f"{txt_path} 文件未找到。")
        return None


# 创建所有图片的压缩版本
def create_compressed_images(directory):
    """
    创建所有图片的压缩版本，并返回原始文件的哈希值和压缩图片路径的列表。

    参数:
        directory (str): 包含图片的根目录。

    返回:
        list: 每个元素是 (原始文件哈希值, 压缩图片路径) 的元组。
    """
    # 从 created_folder_path.txt 获取路径
    txt_file = os.path.join(current_dir, 'created_folder_path.txt')
    max_subfolder_path = get_folder_from_txt(txt_file)
    if not max_subfolder_path:
        logging.info("无法从 created_folder_path.txt 获取有效路径。")
        return []
    else:
        # 获取该路径中所有图片的路径
        from GetPath import get_image_paths  # 确保 get_image_paths 从正确的模块导入
        image_paths = get_image_paths(max_subfolder_path)
        compressed_images = []
        for image_path in tqdm(image_paths, desc="Compressing images", unit="image"):
            # 获取源文件的最后一级目录名
            src_dir_name = os.path.basename(os.path.dirname(image_path))

            # 创建压缩图的目录路径，保存到 'compressed/最后一级文件夹'
            compressed_dir_path = os.path.join(current_dir, 'compressed', src_dir_name)

            # 确保压缩图目录存在
            os.makedirs(compressed_dir_path, exist_ok=True)

            # 获取文件的扩展名
            _, ext = os.path.splitext(os.path.basename(image_path))
            # 创建压缩图的文件名
            compressed_file_name = f"{os.path.splitext(os.path.basename(image_path))[0]}_compressed{ext}"
            # 创建压缩图的完整路径
            compressed_path = os.path.join(compressed_dir_path, compressed_file_name)

            # 压缩图片
            error = compress_image(image_path, compressed_path)
            if error:
                logging.info(error)  # 打印错误信息
                continue  # 跳过当前错误，继续处理下一个图片

            # 计算原始图片文件内容的哈希值
            image_hash = calculate_file_hash(image_path)
            if image_hash is None:
                logging.info(f"跳过文件 {image_path}，因为哈希计算失败。")
                continue  # 跳过当前错误

            # 将哈希值和压缩图片路径添加到结果列表
            compressed_images.append((image_hash, compressed_path))
        return compressed_images


# 指定你的 images 根目录路径
images_dir = 'images'  # 替换为你的实际路径
compressed_images = create_compressed_images(images_dir)