import logging

import mysql.connector
from mysql.connector import Error
from config import db_config


def get_original_image_path(compressed_path):
    try:
        # 连接到 MySQL 数据库
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()

        # 根据压缩路径查询对应的 ID
        cursor.execute('''
            SELECT id FROM image_compression_index
            WHERE compressed_path = %s
        ''', (compressed_path,))
        result = cursor.fetchone()
        if not result:
            return None

        id = result[0]

        # 使用 ID 查询原图路径
        cursor.execute('''
            SELECT path FROM image_index
            WHERE id = %s
        ''', (id,))
        result = cursor.fetchone()

        return result[0] if result else None

    except Error as e:
        logging.info("连接 MySQL 时出错", e)
        return None
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()