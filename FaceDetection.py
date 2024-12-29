import os
import cv2
import hashlib
import mysql.connector
from mysql.connector import Error
from tqdm import tqdm
import logging
from config import db_config
from datetime import datetime


# 设置日志记录，同时输出到文件和控制台
def setup_logging():
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # 文件日志处理器
    file_handler = logging.FileHandler('face_detection.log')
    file_handler.setLevel(logging.INFO)
    file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)

    # 控制台日志处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    return logger


# 设置日志记录
logging = setup_logging()


# 连接到MySQL数据库
def connect_to_db():
    try:
        conn = mysql.connector.connect(**db_config)
        logging.info("Database connection established.")
        return conn
    except Error as e:
        logging.error(f"Error connecting to MySQL: {e}")
        return None


# 创建或更新日志表
def create_or_update_log_table(conn):
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS logs (
            id INT AUTO_INCREMENT PRIMARY KEY,
            log_level VARCHAR(10),
            message TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    logging.info("Logs table created or already exists.")


# 将日志记录到数据库
def log_to_db(conn, level, message):
    try:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO logs (log_level, message) VALUES (%s, %s)", (level, message))
        conn.commit()
        logging.info(f"Logged to database: {level} - {message}")
    except mysql.connector.Error as e:
        logging.error(f"Failed to log to database: {e}")


# 获取图片的哈希值
def calculate_hash(image_path):
    return hashlib.sha256(open(image_path, 'rb').read()).hexdigest()


# 检测图片中的人脸
def detect_faces(image_path, face_cascade):
    img = cv2.imread(image_path)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    faces = face_cascade.detectMultiScale(gray, scaleFactor=1.2, minNeighbors=5)
    return len(faces)  # 返回检测到的人脸数量


# 创建数据库表
def create_table(conn):
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS face_detection_index (
            id CHAR(64) NOT NULL,
            num_faces INT,
            last_run_time DATETIME,
            PRIMARY KEY (id)
        )
    ''')
    conn.commit()
    logging.info("Table 'face_detection_index' created or already exists.")


# 将人脸检测结果添加到数据库
def add_face_detection_to_db(image_hash, num_faces, conn, last_run_time):
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO face_detection_index (id, num_faces, last_run_time) VALUES (%s, %s, %s)
        ON DUPLICATE KEY UPDATE num_faces = VALUES(num_faces), last_run_time = VALUES(last_run_time)
    ''', (image_hash, num_faces, last_run_time))
    conn.commit()
    log_to_db(conn, "INFO", f"Inserted {num_faces} faces data into database for image {image_hash} at {last_run_time}.")


# 主函数
def main():
    conn = connect_to_db()
    if conn is None:
        return

    # 创建或更新日志表
    create_or_update_log_table(conn)

    # 创建数据库表
    create_table(conn)

    # 加载Haar级联分类器
    face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

    images_dir = 'images'  # 指定你的images目录路径
    last_run_time = datetime.now()  # 获取上次运行时间并确保是 datetime 对象

    # 检查GPU是否可用
    gpu_available = cv2.cuda.getCudaEnabledDeviceCount() > 0
    if gpu_available:
        logging.info("GPU is available. Using GPU for face detection.")
    else:
        logging.info("GPU is not available. Using CPU for face detection.")

    # 遍历文件夹并检测人脸
    for subdir, dirs, files in tqdm(os.walk(images_dir), desc="Processing images", unit="image"):
        for file in files:
            if file.lower().endswith(('.png', '.jpg', '.jpeg')):
                image_path = os.path.join(subdir, file)
                image_hash = calculate_hash(image_path)

                # 检查图片是否自上次运行以来被修改过
                cursor = conn.cursor()
                cursor.execute('SELECT last_run_time FROM face_detection_index WHERE id = %s', (image_hash,))
                result = cursor.fetchone()

                # 修改此处：直接比较 datetime 对象
                if result and result[0] >= last_run_time:
                    continue  # 如果图片在上次运行后没有被修改过，则跳过

                num_faces = detect_faces(image_path, face_cascade)
                add_face_detection_to_db(image_hash, num_faces, conn, last_run_time)

    # 在关闭连接之前记录日志
    log_to_db(conn, "INFO", "Database connection closed.")
    conn.close()


if __name__ == "__main__":
    main()
