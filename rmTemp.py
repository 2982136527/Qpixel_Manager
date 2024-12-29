import logging
import os
import shutil

def delete_temp_folder(temp_folder_path):
    if os.path.exists(temp_folder_path):
        try:
            # 删除 temp 文件夹及其所有内容
            shutil.rmtree(temp_folder_path)
            logging.info(f"删除temp成功: {temp_folder_path}")
        except Exception as e:
            logging.info(f"删除temp失败: {e}")
    else:
        logging.info(f"文件夹 {temp_folder_path} 不存在。")

# 指定 temp 文件夹路径
temp_directory_path = 'temp'

# 调用删除函数
delete_temp_folder(temp_directory_path)
