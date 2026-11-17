from datetime import datetime
from airflow.sdk import dag, task
import subprocess

@dag(
    dag_id="sns_spark_pipeline",
    start_date=datetime(2026, 11, 1),
    schedule="@daily",
    catchup=False,
tags=["sns", "csv", "spark"]
)
def sns_spark_pipeline():

    @task
    def run_spark_analysis():
        subprocess.run(
            [
                "/home/taehy/sns-psychology-service/.venv/bin/python",
                "/home/taehy/sns-psychology-service/scripts/sns_analysis.py"
            ],
check=True,
cwd="/home/taehy/sns-psychology-service"        )

    run_spark_analysis()

sns_spark_pipeline()
