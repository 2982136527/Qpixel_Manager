import logging
import os
import shutil
import hashlib
from datetime import datetime
import mysql.connector
from mysql.connector import Error
from config import db_config

# 计算文件的哈希值
def compute_file_hash(file_path):
    hash_sha256 = hashlib.sha256()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_sha256.update(chunk)
    return hash_sha256.hexdigest()

# 检查文件的哈希值是否已经存在于数据库中
def is_hash_in_db(cursor, image_hash):
    cursor.execute('''SELECT COUNT(*) FROM image_index WHERE id = %s''', (image_hash,))
    result = cursor.fetchone()
    return result[0] > 0

# 创建 image_index 表（如果不存在的话）
def create_image_index_table_if_not_exists():
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS image_index (
            id CHAR(64) NOT NULL,
            path VARCHAR(255) NOT NULL,
            size_in_mb FLOAT,
            PRIMARY KEY (id)
        )
        ''')
        conn.commit()
        logging.info("表 “image_index ”已就绪。")
    except Error as e:
        logging.info(f"连接 MySQL 时出错: {e}")
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()

# 递归移动文件的函数
def move_files_recursively(src, dst, found_non_duplicate=False):
    if os.path.isfile(src):
        file_hash = compute_file_hash(src)
        try:
            conn = mysql.connector.connect(**db_config)
            cursor = conn.cursor()
            if is_hash_in_db(cursor, file_hash):
                os.remove(src)
                logging.info(f"检测到重复文件。已删除: {src}")
            else:
                shutil.move(src, dst)
                logging.info(f"移动文件: {src} 到 {dst}")
                found_non_duplicate = True
            conn.commit()
        except Error as e:
            logging.info(f"连接 MySQL 时出错: {e}")
        finally:
            if conn.is_connected():
                cursor.close()
                conn.close()
    elif os.path.isdir(src):
        os.makedirs(dst, exist_ok=True)
        for item in os.listdir(src):
            src_item = os.path.join(src, item)
            dst_item = os.path.join(dst, item)
            found_non_duplicate = move_files_recursively(src_item, dst_item, found_non_duplicate)
    return found_non_duplicate

# 删除空目录
def delete_empty_directories(path):
    while path != '/':
        if os.path.isdir(path) and not os.listdir(path):
            os.rmdir(path)
            logging.info(f"删除空目录: {path}")
            path = os.path.dirname(path)
        else:
            break

# 创建带时间戳的文件夹并移动文件
def create_timed_folder_and_move_files(temp_dir, images_dir):
    current_time = datetime.now().strftime('%Y%m%d%H%M%S')
    new_folder_name = os.path.join(images_dir, current_time)
    os.makedirs(new_folder_name, exist_ok=True)
    logging.info(f"创建文件夹: {new_folder_name}")

    # 在移动文件时不删除空目录
    found_non_duplicate = move_files_recursively(temp_dir, new_folder_name)

    # 确保所有操作完成后删除空目录
    if found_non_duplicate:
        delete_empty_directories(temp_dir)
    return new_folder_name

# 在执行文件移动操作前，确保 image_index 表已创建
def main():
    create_image_index_table_if_not_exists()

    # temp文件夹路径
    temp_directory_path = 'temp'
    # images文件夹路径
    images_directory_path = 'images'

    # 执行文件移动操作
    new_folder_path = create_timed_folder_and_move_files(temp_directory_path, images_directory_path)
    logging.info(f"Total images processed: {new_folder_path}")
    # 将创建的文件夹路径保存到文件中，供 GetPath.py 使用
    with open('created_folder_path.txt', 'w') as f:
        f.write(new_folder_path)

if __name__ == '__main__':
    main()