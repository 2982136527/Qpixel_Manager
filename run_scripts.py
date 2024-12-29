# run_scripts.py
import logging
import subprocess

def run_scripts():
    # 需要执行的 Python 脚本列表
    scripts = [
        "MoveImg.py",
        "rmTemp.py",
        "GetPath.py",
        "GetImgInfo.py",
        "GetThumbnailsPath.py",
        "CreateImagesTags.py",
        "addCompressedPathIndex.py",
        #"FaceDetection.py"
    ]

    for script in scripts:
        try:
            # 执行每个 Python 脚本
            result = subprocess.run(["python", script], capture_output=True, text=True)

            # 打印脚本输出
            logging.info(f"Running {script}...")
            logging.info(f"数据输出: {result.stdout}")
            logging.info(f"错误数据: {result.stderr}")

            # 如果脚本执行失败，抛出异常
            if result.returncode != 0:
                logging.info(f"执行时发生错误 {script}")
                raise Exception(f"执行时发生错误 {script}")
        except Exception as e:
            logging.info(f"运行脚本出错 {script}: {e}")
            raise
