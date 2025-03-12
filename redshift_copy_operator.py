import boto3
from airflow.models.baseoperator import BaseOperator
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.utils.decorators import apply_defaults

class RedshiftCopyFromS3Operator(BaseOperator):
    """
    Custom Airflow Operator to copy data from S3 to Redshift.
    """

    @apply_defaults
    def __init__(
        self,
        redshift_conn_id: str,
        s3_bucket: str,
        s3_key: str,
        table: str,
        iam_role: str,
        region: str = "us-east-1",
        file_format: str = "PARQUET",
        *args, **kwargs
    ):
        super(RedshiftCopyFromS3Operator, self).__init__(*args, **kwargs)
        self.redshift_conn_id = redshift_conn_id
        self.s3_bucket = s3_bucket
        self.s3_key = s3_key
        self.table = table
        self.iam_role = iam_role
        self.region = region
        self.file_format = file_format

    def execute(self, context):
        """
        Executes the COPY command in Redshift to load data from S3.
        """
        self.log.info(f"Loading data from s3://{self.s3_bucket}/{self.s3_key} into {self.table} in Redshift.")

        # Redshift SQL COPY command
        copy_sql = f"""
        COPY {self.table}
        FROM 's3://{self.s3_bucket}/{self.s3_key}'
        IAM_ROLE '{self.iam_role}'
        FORMAT AS {self.file_format}
        REGION '{self.region}';
        """

        # Execute COPY command using PostgresHook
        redshift = PostgresHook(postgres_conn_id=self.redshift_conn_id)
        redshift.run(copy_sql)

        self.log.info(f"Successfully loaded {self.s3_key} into {self.table}.")
