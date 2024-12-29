import logging
import os
from PIL import Image
from PIL.ExifTags import TAGS
import hashlib
import mysql.connector
from mysql.connector import Error

from CreateThumbnails import calculate_file_hash
from config import db_config

# 连接到MySQL数据库
def connect_to_db():
    try:
        conn = mysql.connector.connect(**db_config)
        return conn
    except Error as e:
        logging.info("连接 MySQL 时出错", e)
        return None

# 获取图片的EXIF信息
def get_exif_data(image_path):
    exif_data = {}
    try:
        with Image.open(image_path) as img:
            exif = img._getexif()
            if exif is not None:
                for tag, value in exif.items():
                    tag_name = TAGS.get(tag, tag)
                    exif_data[tag_name] = value
    except Exception as e:
        logging.info(f"为以下设备获取 EXIF 数据时出错 {image_path}: {e}")
    return exif_data

# 获取拍摄时间
def get_capture_time(exif_data):
    if 'DateTimeOriginal' in exif_data:
        return exif_data['DateTimeOriginal']
    return None

# 获取GPS信息
def get_gps_info(exif_data):
    gps_info = {}
    if 'GPSInfo' in exif_data:
        for tag, value in exif_data['GPSInfo'].items():
            tag_name = TAGS.get(tag, tag)
            gps_info[tag_name] = value
        # 将GPS信息转换为可读的格式
        if 'GPSLatitude' in gps_info and 'GPSLongitude' in gps_info:
            lat = gps_info['GPSLatitude']
            lng = gps_info['GPSLongitude']
            lat_ref = gps_info.get('GPSLatitudeRef', 'N')
            lng_ref = gps_info.get('GPSLongitudeRef', 'E')
            gps_info['GPSCoordinates'] = f"{lat_ref} {lat[0]}/{lat[1]}/{lat[2]}, {lng_ref} {lng[0]}/{lng[1]}/{lng[2]}"
    return gps_info

# 将EXIF信息添加到数据库
def add_exif_to_db(image_hash, exif_data, conn):
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS image_exif_index (
            id CHAR(64) NOT NULL,
            capture_time DATETIME,
            gps_info TEXT,
            PRIMARY KEY (id)
        )
    ''')
    capture_time = get_capture_time(exif_data)
    gps_info = get_gps_info(exif_data)
    cursor.execute('''
        INSERT INTO image_exif_index (id, capture_time, gps_info) VALUES (%s, %s, %s)
    ''', (image_hash, capture_time, gps_info.get('GPSCoordinates')))
    conn.commit()

# 从文件中获取 MoveImg.py 创建的文件夹路径
def get_created_folder_path_from_file(file_path):
    try:
        with open(file_path, 'r') as f:
            return f.read().strip()
    except FileNotFoundError:
        logging.info("包含创建文件夹路径的文件不存在。")
        return None

# 主函数
def main():
    conn = connect_to_db()
    if conn is None:
        return

    created_folder_path_file = 'created_folder_path.txt'  # MoveImg.py 需要将路径保存在这个文件中
    max_subfolder_path = get_created_folder_path_from_file(created_folder_path_file)
    if not max_subfolder_path:
        logging.info("未找到创建的文件夹路径。")
        return

    for subdir, dirs, files in os.walk(max_subfolder_path):
        for file in files:
            if file.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.gif')):
                image_path = os.path.join(subdir, file)
                image_hash = calculate_file_hash(image_path)
                exif_data = get_exif_data(image_path)
                add_exif_to_db(image_hash, exif_data, conn)

    conn.close()

if __name__ == "__main__":
    main()