import logging

import mysql.connector
from config import db_config

def create_or_update_index():
    try:
        # 连接到 MySQL 数据库
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()

        # 检查索引是否存在
        cursor.execute("""
            SELECT COUNT(1)
            FROM INFORMATION_SCHEMA.STATISTICS
            WHERE TABLE_SCHEMA = %s
              AND TABLE_NAME = %s
              AND INDEX_NAME = %s
        """, (db_config['database'], 'trash', 'idx_compressed_path'))
        index_exists = cursor.fetchone()[0]

        # 如果索引不存在，创建索引
        if not index_exists:
            cursor.execute("CREATE INDEX idx_compressed_path ON trash (compressed_path)")
            conn.commit()
            logging.info("索引 'idx_compressed_path' 已创建！")
        else:
            logging.info("索引 'idx_compressed_path' 已存在，准备更新索引...")

            # 删除旧索引
            cursor.execute("DROP INDEX idx_compressed_path ON trash")
            conn.commit()
            logging.info("旧索引 'idx_compressed_path' 已删除！")

            # 重新创建索引
            cursor.execute("CREATE INDEX idx_compressed_path ON trash (compressed_path)")
            conn.commit()
            logging.info("索引 'idx_compressed_path' 已重新创建！")

    except mysql.connector.Error as e:
        logging.info(f"数据库错误: {e}")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

if __name__ == "__main__":
    create_or_update_index()