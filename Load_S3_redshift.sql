COPY {self.table}
        FROM 's3://{self.s3_bucket}/{self.s3_key}'
        IAM_ROLE '{self.iam_role}'
        FORMAT AS {self.file_format}
        REGION '{self.region}';
