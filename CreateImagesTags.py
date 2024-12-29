import logging
import os
import mysql.connector
from mysql.connector import Error
from config import db_config
from CreateThumbnails import calculate_file_hash  # 从 CreateThumbnails 导入计算哈希的函数


def create_and_populate_tag_tables(compressed_directory):
    """
    创建 imageTag 表，并将压缩图片数据插入表中。

    参数:
        compressed_directory (str): 存放压缩图片的目录路径。
    """
    try:
        # 遍历目录，获取所有图片文件路径
        compressed_images = []
        for root, _, files in os.walk(compressed_directory):
            for file in files:
                compressed_path = os.path.join(root, file)
                # 计算文件哈希值
                compressed_hash = calculate_file_hash(compressed_path)
                if compressed_hash:
                    compressed_images.append((compressed_hash, compressed_path))

        # 连接到 MySQL 数据库
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()

        # 创建 imageTag 表（如果不存在）
        cursor.execute('''
           CREATE TABLE IF NOT EXISTS imageTag (
                compressed_path VARCHAR(255) NOT NULL,
                compressed_hash CHAR(64) NOT NULL,
                tags JSON DEFAULT NULL,  -- 将tags字段类型设为JSON
                PRIMARY KEY (compressed_hash)
            )
        ''')

        # 插入数据到 imageTag 表
        for compressed_hash, compressed_path in compressed_images:
            # 转换为相对路径
            relative_compressed_path = os.path.relpath(compressed_path, os.getcwd())

            # 确保路径以 'compressed/' 开头
            if not relative_compressed_path.startswith('compressed/'):
                relative_compressed_path = os.path.join('compressed', relative_compressed_path)

            # 插入或更新 imageTag 表
            cursor.execute('''
                INSERT INTO imageTag (compressed_path, compressed_hash)
                VALUES (%s, %s)
                ON DUPLICATE KEY UPDATE
                    compressed_path = VALUES(compressed_path)
            ''', (relative_compressed_path, compressed_hash))

        # 提交事务
        conn.commit()
        logging.info("成功创建表格并插入数据。")

    except Error as e:
        logging.info("创建表格或插入数据时出错：", e)
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()


# 调用函数创建表并插入数据
if __name__ == "__main__":
    compressed_directory = "compressed"  # 替换为你的压缩图片目录路径
    create_and_populate_tag_tables(compressed_directory)