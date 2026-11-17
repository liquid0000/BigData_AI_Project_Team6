import os
import subprocess
from datetime import datetime
from airflow.sdk import dag, task

# 현재 파일(sns_spark_pipeline.py)의 상위 폴더(프로젝트 루트)를 자동으로 잡습니다
PROJECT_DIR = os.getenv(
    "SNS_PROJECT_DIR",
    os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
)
PYTHON_BIN = os.getenv("SNS_PYTHON_BIN", f"{PROJECT_DIR}/.venv/bin/python")
SPARK_SCRIPT = f"{PROJECT_DIR}/preprocess_spark.py"

@dag(
    dag_id="sns_spark_pipeline",
    start_date=datetime(2026, 11, 1),
    schedule="@daily",
    catchup=False,
    tags=["sns", "mongodb", "spark"]
)
def sns_spark_pipeline():

    @task
    def run_spark_analysis():
        subprocess.run(
            [PYTHON_BIN, SPARK_SCRIPT],
            cwd=PROJECT_DIR,
            check=True
        )

    run_spark_analysis()

sns_spark_pipeline()