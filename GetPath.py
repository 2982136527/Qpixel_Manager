import os
import mysql.connector
from mysql.connector import Error
import hashlib
import logging
from tqdm import tqdm
from config import db_config

# 常见的图片格式，包括RAW格式
image_extensions = ['.png', '.jpg', '.jpeg', '.bmp', '.gif', '.cr2', '.nef', '.dng', '.crw', '.raw']

# 配置日志
logging.basicConfig(
    filename='image_processing.log',  # 日志文件名
    level=logging.INFO,  # 记录INFO级别及以上的日志
    format='%(asctime)s - %(levelname)s - %(message)s',  # 日志格式
)

# 递归遍历文件夹，获取所有图片路径
def get_image_paths(directory):
    image_paths = []
    for root, dirs, files in os.walk(directory):
        for file in files:
            if any(file.lower().endswith(ext) for ext in image_extensions):
                image_paths.append(os.path.join(root, file))
    return image_paths

# 计算文件的哈希值
def compute_file_hash(file_path):
    hash_sha256 = hashlib.sha256()
    with open(file_path, 'rb') as f:
        # 分块读取文件内容并更新哈希值
        for chunk in iter(lambda: f.read(4096), b""):
            hash_sha256.update(chunk)
    return hash_sha256.hexdigest()

# 创建图片索引并记录文件大小（以MB为单位）
def create_image_index(directory, db_config):
    image_paths = get_image_paths(directory)

    # 初始化计数器
    total_processed = 0

    try:
        # 连接到MySQL数据库
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()

        # 创建表，使用哈希值作为id
        cursor.execute(''' 
            CREATE TABLE IF NOT EXISTS image_index (
                id CHAR(64) NOT NULL,
                path VARCHAR(255),
                size_in_mb FLOAT,
                PRIMARY KEY (id)
            )
        ''')

        # 使用tqdm显示进度条
        with tqdm(total=len(image_paths), desc="Processing images", unit="image") as pbar:
            for path in image_paths:
                # 获取文件大小，并转换为MB
                size_in_bytes = os.path.getsize(path)
                size_in_mb = size_in_bytes / (1024 * 1024)

                # 计算文件的哈希值
                file_hash = compute_file_hash(path)

                # 将哈希值和大小插入数据库
                cursor.execute(''' 
                    INSERT INTO image_index (id, path, size_in_mb) VALUES (%s, %s, %s)
                ''', (file_hash, path, size_in_mb))
                total_processed += 1  # 增加成功处理的数量
                logging.info(f"Processed and added to DB: {path}")
                pbar.update(1)  # 更新进度条

        # 提交事务
        conn.commit()

    except Error as e:
        logging.error(f"Error while connecting to MySQL: {e}")
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()
            logging.info("Completed processing images and updating database.")

    return total_processed

# 从文件中获取 MoveImg.py 创建的文件夹路径
def get_created_folder_path_from_file(file_path):
    try:
        with open(file_path, 'r') as f:
            return f.read().strip()
    except FileNotFoundError:
        logging.error("The file containing the created folder path does not exist.")
        return None

# 指定你的images目录路径
images_dir = 'images'
created_folder_path_file = 'created_folder_path.txt'  # MoveImg.py 需要将路径保存在这个文件中
new_folder_path = get_created_folder_path_from_file(created_folder_path_file)

if new_folder_path:
    logging.info(f"Using created folder: {new_folder_path}")
    total_processed = create_image_index(new_folder_path, db_config)
    logging.info(f"Total images processed: {total_processed}")
else:
    logging.warning("Failed to get the created folder path.")
