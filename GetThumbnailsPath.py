import logging
import os
import mysql.connector
from mysql.connector import Error
from config import db_config
from CreateThumbnails import compressed_images, calculate_file_hash  # 确保从CreateThumbnails.py导入compressed_images


# 计算文件大小并转换为MB
def get_file_size_in_mb(file_path):
    file_size_bytes = os.path.getsize(file_path)
    file_size_mb = file_size_bytes / (1024 * 1024)
    return round(file_size_mb, 2)


# 生成所有图片的压缩版本并将信息添加到数据库
def generate_image_index(compressed_images):
    try:
        # 连接到MySQL数据库
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()

        # 创建 image_compression_index 表（如果不存在）
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS image_compression_index (
                id CHAR(64) NOT NULL,
                compressed_path VARCHAR(255),
                compressed_hash CHAR(64),
                size FLOAT,  -- 单位MB
                PRIMARY KEY (id)
            )
        ''')

        # 创建 trash 表（如果不存在）
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trash (
                id CHAR(64) NOT NULL,
                compressed_path VARCHAR(255),
                type TINYINT DEFAULT 0,  -- 默认值为0
                PRIMARY KEY (id),
                FOREIGN KEY (id) REFERENCES image_compression_index(id) ON DELETE CASCADE
            )
        ''')

        # 插入压缩图片的哈希值、路径、压缩图哈希值和文件大小
        for image_hash, compressed_path in compressed_images:
            # 获取以 compressed 文件夹为基准的路径
            relative_compressed_path = os.path.relpath(compressed_path, os.getcwd())

            # 确保路径以 'compressed/' 开头
            if not relative_compressed_path.startswith('compressed/'):
                relative_compressed_path = os.path.join('compressed', relative_compressed_path)

            # 计算压缩图的哈希值和大小
            compressed_hash = calculate_file_hash(compressed_path)
            size_mb = get_file_size_in_mb(compressed_path)

            # 插入或更新 image_compression_index 表
            cursor.execute('''
                INSERT INTO image_compression_index (id, compressed_path, compressed_hash, size)
                VALUES (%s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    compressed_path = VALUES(compressed_path),
                    compressed_hash = VALUES(compressed_hash),
                    size = VALUES(size)
            ''', (image_hash, relative_compressed_path, compressed_hash, size_mb))

            # 将数据插入到 trash 表
            cursor.execute('''
                INSERT INTO trash (id, compressed_path, type)
                VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    compressed_path = VALUES(compressed_path),
                    type = VALUES(type)
            ''', (image_hash, relative_compressed_path, 0))

        # 提交事务
        conn.commit()

    except Error as e:
        logging.info("连接 MySQL 时出错:", e)
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()
            logging.info("完成图像处理和数据库更新。")


# 调用函数生成索引
generate_image_index(compressed_images)