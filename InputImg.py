import logging

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from flask_socketio import SocketIO
import os
from celery import Celery
from run_scripts import run_scripts  # 脚本模块
from get_original_image import get_original_image_path  # 查询原图路径模块
from config import db_config, configure_logging  # 数据库配置模块
import mysql.connector  # 用于连接 MySQL 数据库
from config import CELERY_BROKER_URL, CELERY_RESULT_BACKEND
import json


# 配置日志
configure_logging()

app = Flask(__name__)

# 启用 CORS
CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True)

# 配置上传文件夹
UPLOAD_FOLDER = 'temp'
COMPRESSED_FOLDER = 'compressed'
ORIGINAL_FOLDER = os.path.join(os.getcwd(), 'images')  # 原图文件夹路径
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['COMPRESSED_FOLDER'] = COMPRESSED_FOLDER
app.config['MAX_CONTENT_LENGTH'] = None

# 确保目录存在
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(COMPRESSED_FOLDER, exist_ok=True)
os.makedirs(ORIGINAL_FOLDER, exist_ok=True)  # 确保 images 目录存在

# 初始化 SocketIO
socketio = SocketIO(app, cors_allowed_origins="*")  # 允许所有跨域连接

# 配置 Celery
app.config['CELERY_BROKER_URL'] = CELERY_BROKER_URL
app.config['result_backend'] = CELERY_RESULT_BACKEND

# 初始化 Celery 实例
celery = Celery(
    app.name,
    broker=app.config['CELERY_BROKER_URL'],
    backend=app.config['result_backend']
)

# 自动发现任务模块
celery.conf.update(app.config)
celery.autodiscover_tasks(['InputImg'])

# 异步任务
@celery.task
def process_files():
    try:
        run_scripts()  # 调用脚本处理上传的文件
        return {"status": "success", "message": "Files processed successfully"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


# 处理文件上传
def handle_file_upload(file_key):
    if file_key not in request.files:
        return jsonify({"error": "No files part"}), 400

    files = request.files.getlist(file_key)

    if not files:
        return jsonify({"error": "No files selected"}), 400

    saved_files = []
    # 允许的图片文件扩展名集合
    valid_extensions = {
        'png', 'jpg', 'jpeg', 'gif', 'bmp', 'tiff', 'tif', 'webp', 'ico', 'heic', 'heif', 'jfif', 'pcx', 'ppm', 'pbm',
        'psd'
    }
    try:
        for file in files:
            if file:
                # 获取原始文件名并确保安全
                filename = os.path.basename(file.filename)
                # 检查是否为隐藏文件，隐藏文件名以点开头
                if filename.startswith('.'):
                    logging.info(f"检查到隐藏文件“{filename}”，已跳过")
                    continue

                # 获取文件扩展名
                ext = filename.split('.')[-1].lower()
                if ext not in valid_extensions:
                    logging.info(f"检查到非图片文件“{filename}”，已跳过")
                    continue

                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)

                # 检查文件是否已存在，如果存在则在文件名末尾添加序号
                base_name, ext = os.path.splitext(filename)
                counter = 1
                while os.path.exists(file_path):
                    new_filename = f"{base_name}_{counter}{ext}"
                    file_path = os.path.join(app.config['UPLOAD_FOLDER'], new_filename)
                    counter += 1

                # 创建保存目录并保存文件
                os.makedirs(os.path.dirname(file_path), exist_ok=True)
                file.save(file_path)
                saved_files.append(file_path)

                # 打印已上传文件信息
                #logging.info(f"已上传文件: {file_path}")

        # 调用异步任务处理文件
        task = process_files.apply_async()

        # 文件上传完成后通知前端
        socketio.emit('task_started', {'task_id': task.id, 'message': 'Files uploaded, processing started'})
    except Exception as e:
        return jsonify({"error": f"An error occurred: {str(e)}"}), 500

    return jsonify({"message": "Files uploaded successfully", "files": saved_files}), 200

@app.route('/')
def index():
    # frontend 目录位于 QPM 项目目录下
    # 使用 send_from_directory 来发送 index.html 文件
    return send_from_directory('frontend', 'index.html')

@app.route('/InputImg')
def InputImg():
    # frontend 目录位于 QPM 项目目录下
    # 使用 send_from_directory 来发送 index.html 文件
    return send_from_directory('frontend', 'InputImg.html')

# 上传文件夹接口
@app.route('/upload_folder', methods=['POST'])
def upload_folder():
    return handle_file_upload('folder')


# 上传图片接口
@app.route('/upload_images', methods=['POST'])
def upload_images():
    return handle_file_upload('images')


# 获取任务状态
@app.route('/api/task_status/<task_id>', methods=['GET'])
def get_task_status(task_id):
    task = process_files.AsyncResult(task_id)
    if task.state == 'PENDING':
        return jsonify({'state': task.state, 'status': 'Task is pending'}), 200
    elif task.state != 'FAILURE':
        return jsonify({'state': task.state, 'status': task.info}), 200
    else:
        return jsonify({'state': task.state, 'status': str(task.info)}), 500


# 提供图片文件
@app.route('/compressed/<path:filename>', methods=['GET'])
def get_image(filename):
    return send_from_directory(app.config['COMPRESSED_FOLDER'], filename)


# 查询原图路径
@app.route('/api/original_image', methods=['GET'])
def get_original_image():
    compressed_path = request.args.get('compressed_path')
    if not compressed_path:
        return jsonify({"error": "compressed_path parameter is required"}), 400

    # 直接使用带有 compressed/ 前缀的路径查询数据库
    original_image_path = get_original_image_path(compressed_path)

    if original_image_path:
        return jsonify({"original_image_path": original_image_path}), 200
    else:
        return jsonify({"error": "Original image not found"}), 404


# 提供原图文件
@app.route('/images/<path:filename>', methods=['GET'])
def serve_original_image(filename):
    full_path = os.path.join(ORIGINAL_FOLDER, filename)  # 拼接完整文件路径

    if not os.path.exists(full_path):
        return "File not found", 404

    # 返回文件
    return send_from_directory(ORIGINAL_FOLDER, filename)


# 删除图片接口
@app.route('/api/delete_image', methods=['POST'])
def delete_image():
    data = request.get_json()
    compressed_path = data.get('path')  # 获取压缩图片路径

    # 打印压缩图片路径，方便调试
    logging.info(f"删除的的压缩图像路径: {compressed_path}")

    if not compressed_path:
        return jsonify({"error": "Image path is required"}), 400

    try:
        # 连接数据库
        connection = mysql.connector.connect(**db_config)
        cursor = connection.cursor()

        # 更新数据库中的 type 字段为 1
        update_query = """
        UPDATE trash
        SET type = 1
        WHERE compressed_path = %s
        """
        cursor.execute(update_query, (compressed_path,))
        connection.commit()

        # 检查是否成功更新
        if cursor.rowcount > 0:
            return jsonify({"success": True, "message": "Image marked as deleted"}), 200
        else:
            return jsonify({"success": False, "message": "Image not found in database"}), 404
    except mysql.connector.Error as err:
        logging.info(f"MySQL error: {err}")
        return jsonify({"error": "Database error occurred"}), 500
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

# 恢复图片接口
@app.route('/api/recover_image', methods=['POST'])
def recover_image():
    data = request.get_json()
    compressed_path = data.get('path')  # 获取压缩图片路径

    # 打印压缩图片路径，方便调试
    logging.info(f"恢复的的压缩图像路径: {compressed_path}")

    if not compressed_path:
        return jsonify({"error": "Image path is required"}), 400

    try:
        # 连接数据库
        connection = mysql.connector.connect(**db_config)
        cursor = connection.cursor()

        # 更新数据库中的 type 字段为 0
        update_query = """
        UPDATE trash
        SET type = 0
        WHERE compressed_path = %s
        """
        cursor.execute(update_query, (compressed_path,))
        connection.commit()

        # 检查是否成功更新
        if cursor.rowcount > 0:
            return jsonify({"success": True, "message": "Image marked as deleted"}), 200
        else:
            return jsonify({"success": False, "message": "Image not found in database"}), 404
    except mysql.connector.Error as err:
        logging.info(f"MySQL error: {err}")
        return jsonify({"error": "Database error occurred"}), 500
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

# 查询主页图片及标签
@app.route('/api/home_images', methods=['GET'])
def get_home_images():
    try:
        # 使用从config.py中导入的配置
        connection = mysql.connector.connect(**db_config)
        cursor = connection.cursor()
        cursor.execute("""
            SELECT ic.compressed_path, it.tags FROM trash
            JOIN image_compression_index ic ON trash.compressed_path = ic.compressed_path
            LEFT JOIN imageTag it ON ic.compressed_path = it.compressed_path
            WHERE trash.type = 0
        """)
        home_images = cursor.fetchall()

        # 提取图片路径和标签，并返回
        image_data = []
        for image, tags in home_images:
            tags = json.loads(tags) if tags else []
            image_data.append({
                "compressed_path": image,
                "tags": tags
            })
        return jsonify(image_data)

    except Exception as e:
        logging.info(f"查询主页图片失败: {e}")
        return jsonify({"error": "加载主页图片失败"}), 500

    finally:
        # 确保资源正确释放
        if cursor:
            cursor.close()
        if connection:
            connection.close()

# 查询搜索图片及标签
@app.route('/api/search_images', methods=['GET'])
def get_search_images():
    try:
        # 从查询参数中获取搜索关键词
        search_query = request.args.get('query', '')  # 默认为空字符串，如果没有提供查询参数

        # 使用从config.py中导入的配置
        connection = mysql.connector.connect(**db_config)
        cursor = connection.cursor()

        # 构建查询语句，同时考虑compressed_path和tags字段
        # 确保这里的表名和字段名与数据库中的实际名称一致
        query = """
            SELECT ic.compressed_path, it.tags 
            FROM image_compression_index ic
            LEFT JOIN imageTag it ON ic.compressed_path = it.compressed_path
            WHERE ic.compressed_path LIKE %s OR it.tags LIKE %s
        """
        cursor.execute(query, ('%' + search_query + '%', '%' + search_query + '%'))
        search_images = cursor.fetchall()

        # 提取图片路径和标签，并返回
        image_data = []
        for compressed_path, tags in search_images:
            tags = json.loads(tags) if tags else []
            image_data.append({
                "compressed_path": compressed_path,
                "tags": tags
            })
        return jsonify(image_data)

    except Exception as e:
        logging.info(f"查询搜索图片失败: {e}")
        return jsonify({"error": "加载搜索图片失败"}), 500

    finally:
        # 确保资源正确释放
        if cursor:
            cursor.close()
        if connection:
            connection.close()

# 查询回收站图片及标签
@app.route('/api/trash_images', methods=['GET'])
def get_trash_images():
    try:
        # 使用从config.py中导入的配置
        connection = mysql.connector.connect(**db_config)
        cursor = connection.cursor()
        cursor.execute("""
            SELECT ic.compressed_path, it.tags FROM trash
            JOIN image_compression_index ic ON trash.compressed_path = ic.compressed_path
            LEFT JOIN imageTag it ON ic.compressed_path = it.compressed_path
            WHERE trash.type = 1
        """)
        trash_images = cursor.fetchall()

        # 提取图片路径和标签，并返回
        image_data = []
        for compressed_path, tags in trash_images:
            tags = json.loads(tags) if tags else []
            image_data.append({
                "compressed_path": compressed_path,
                "tags": tags
            })
        return jsonify(image_data)

    except Exception as e:
        logging.info(f"查询回收站图片失败: {e}")
        return jsonify({"error": "加载回收站图片失败"}), 500

    finally:
        # 确保资源正确释放
        if cursor:
            cursor.close()
        if connection:
            connection.close()


# 彻底删除图片
@app.route('/api/destroy_image', methods=['POST'])
def destroy_image():
    data = request.get_json()
    image_path = data.get('path')  # 获取图片的路径

    if not image_path:
        return jsonify({"error": "Image path is required"}), 400

    # 打印图片路径，方便调试
    logging.info(f"彻底删除的压缩图像路径: {image_path}")

    try:
        # 连接数据库
        connection = mysql.connector.connect(**db_config)
        cursor = connection.cursor()

        # 1. 获取图片在trash表中的id，根据compressed_path查找
        cursor.execute("SELECT id FROM trash WHERE compressed_path = %s", (image_path,))
        result = cursor.fetchone()

        if not result:
            return jsonify({"error": "Image not found in trash"}), 404

        id = result[0]  # 获取对应的id

        # 2. 获取图片在image_compression_index和image_index表中的路径
        cursor.execute("SELECT compressed_path FROM image_compression_index WHERE id = %s", (id,))
        compressed_path_result = cursor.fetchone()

        cursor.execute("SELECT path FROM image_index WHERE id = %s", (id,))
        original_path_result = cursor.fetchone()

        if not compressed_path_result or not original_path_result:
            return jsonify({"error": "Paths not found in related tables"}), 404

        compressed_path = compressed_path_result[0]
        original_path = original_path_result[0]

        # 3. 删除与该图片相关的所有记录
        delete_queries = {
            "trash": "DELETE FROM trash WHERE id = %s",
            "image_index": "DELETE FROM image_index WHERE id = %s",
            "image_compression_index": "DELETE FROM image_compression_index WHERE id = %s",
            "imageTag": "DELETE FROM imageTag WHERE compressed_path = %s",  # 添加删除imageTag表记录的查询
            "image_exif_index": "DELETE FROM image_exif_index WHERE id = %s"
        }

        # 删除记录
        for table, query in delete_queries.items():
            logging.info(f"从表 {table} 删除id为 {id} 的文件 {compressed_path}")  # 调试删除表的操作
            if table == "imageTag":
                cursor.execute(query, (compressed_path,))  # 对于imageTag表，使用compressed_path
            else:
                cursor.execute(query, (id,))
            connection.commit()

        # 4. 删除图片文件
        # 直接使用数据库返回的相对路径
        compressed_file_path = compressed_path
        original_file_path = original_path

        # 删除压缩图片和原始图片
        if os.path.exists(compressed_file_path):
            os.remove(compressed_file_path)  # 删除压缩图片文件
        if os.path.exists(original_file_path):
            os.remove(original_file_path)  # 删除原始图片文件

        return jsonify({"success": True, "message": "Image and all related records have been permanently deleted"}), 200

    except mysql.connector.Error as err:
        logging.info(f"MySQL error: {err}")
        return jsonify({"error": "Database error occurred"}), 500
    except Exception as e:
        logging.info(f"Error: {e}")
        return jsonify({"error": "An error occurred while deleting the image"}), 500
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

# 添加标签接口
@app.route('/api/add_tag', methods=['POST'])
def add_tag():
    data = request.get_json()
    compressed_path = data.get('path')
    tag = data.get('tag')  # 获取标签

    # 打印信息，方便调试
    logging.info(f"收到图像路径： {compressed_path}, Tag received: {tag}")

    if not compressed_path or not tag:
        return jsonify({"error": "Image path and tag are required"}), 400

    try:
        # 连接数据库
        connection = mysql.connector.connect(**db_config)
        cursor = connection.cursor()

        # 检查图片是否存在于数据库中
        check_query = "SELECT * FROM imageTag WHERE compressed_path = %s"
        cursor.execute(check_query, (compressed_path,))
        image = cursor.fetchone()

        if not image:
            return jsonify({"success": False, "message": "Image not found in database"}), 404

        # 获取现有的标签JSON数组
        existing_tags = image[2] if image[2] else '[]'  # 如果tags字段为空，则默认为空数组
        tags_array = json.loads(existing_tags)

        # 添加新的标签到数组中
        tags_array.append(tag)

        # 更新数据库中的标签
        update_query = """
        UPDATE imageTag
        SET tags = %s
        WHERE compressed_path = %s
        """
        cursor.execute(update_query, (json.dumps(tags_array), compressed_path))
        connection.commit()

        # 检查是否成功更新
        if cursor.rowcount > 0:
            return jsonify({"success": True, "message": "Tag added successfully"}), 200
        else:
            return jsonify({"success": False, "message": "Failed to add tag"}), 500
    except mysql.connector.Error as err:
        logging.info(f"MySQL error: {err}")
        return jsonify({"error": "Database error occurred"}), 500
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()



if __name__ == '__main__':
    # 运行 Flask 和 SocketIO 服务器
    socketio.run(app, debug=True, host='0.0.0.0', port=5001, allow_unsafe_werkzeug=True)