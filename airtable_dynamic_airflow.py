from airflow import DAG
from airflow.providers.http.operators.http import SimpleHttpOperator
from airflow.operators.python import PythonOperator
from airflow.operators.empty import EmptyOperator
from airflow.utils.dates import days_ago
import requests
import json
from more_itertools import chunked  # To split tasks into chunks
from airflow.providers.postgres.operators.postgres import PostgresOperator

# Airtable API Credentials
API_KEY = "your_api_key"
BASE_ID = "your_base_id"
AIRTABLE_API_URL = f"https://api.airtable.com/v0/meta/bases/{BASE_ID}/tables"

# Headers for API request
HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

# Airflow DAG Definition
dag = DAG(
    "airtable_dynamic_tasks",
    default_args={"owner": "airflow"},
    schedule_interval=None,  # Set to None for manual execution
    start_date=days_ago(1),
    catchup=False
)

# Empty Operators for workflow structure
init = EmptyOperator(task_id="start", dag=dag)
final = EmptyOperator(task_id="end", dag=dag)

# Function to fetch Airtable Metadata and Extract Table Names
def get_airtable_tables(**kwargs):
    response = requests.get(AIRTABLE_API_URL, headers=HEADERS)

    if response.status_code == 200:
        tables_metadata = response.json()
        airtable_tasks = [table["name"] for table in tables_metadata.get("tables", [])]
        
        # Push table names to XCom for downstream tasks
        kwargs['ti'].xcom_push(key="airtable_tables", value=airtable_tasks)
    else:
        raise ValueError(f"Failed to fetch Airtable metadata: {response.status_code}, {response.text}")

# Python Operator to retrieve Airtable table names
fetch_airtable_tables = PythonOperator(
    task_id="fetch_airtable_tables",
    python_callable=get_airtable_tables,
    provide_context=True,
    dag=dag
)

# Function to dynamically create tasks based on table names
def create_dynamic_tasks(**kwargs):
    ti = kwargs['ti']
    airtable_tasks = ti.xcom_pull(task_ids="fetch_airtable_tables", key="airtable_tables")

    if not airtable_tasks:
        raise ValueError("No tables found in Airtable metadata")

    # Chunk tasks into groups of 5
    for index, task_group in enumerate(chunked(airtable_tasks, 5)):
        # Create EmptyOperator as a dummy task
        globals()[f"dummy_wait_{index}"] = EmptyOperator(
            task_id=f"dummy_wait_{index}", dag=dag
        )

        # Create tasks dynamically for each table in the group
        for table_name in task_group:
            task = EmptyOperator(task_id=f"process_{table_name}", dag=dag)

            # Link tasks
            if index == 0:
                init >> task >> globals()[f"dummy_wait_{index}"]
            else:
                globals()[f"dummy_wait_{index - 1}"] >> task >> globals()[f"dummy_wait_{index}"]

    # Link final wait task to end
    globals()[f"dummy_wait_{index}"] >> final

# Python Operator to create dynamic tasks
generate_tasks = PythonOperator(
    task_id="generate_tasks",
    python_callable=create_dynamic_tasks,
    provide_context=True,
    dag=dag
)

# Redshift COPY Task
postgres_task = PostgresOperator(
    task_id="run_postgres_query",
    postgres_conn_id="my_postgres_conn",
    sql="Load_S3_redshift.sql",
    dag=dag,
)

# DAG Task Dependencies
init >> fetch_airtable_tables >> generate_tasks >> run_postgres_query >> final
