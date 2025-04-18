from  poller import Poller
import os
import sys
import json
import time
from pyspark.sql import SparkSession
from pyspark.sql.functions import input_file_name, current_timestamp
from pyspark.sql import functions as F
os.environ['PYSPARK_PYTHON'] = sys.executable
os.environ['PYSPARK_DRIVER_PYTHON'] = sys.executable
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

def load_data_to_iceberg(spark,
                         df,
                         catalog_name,
                         database_name,
                         table_name,
                         partition_cols=None,
                         sql_query=None,
                         compression='snappy'):

    full_table_name = f"{catalog_name}.{database_name}.{table_name}"
    try:
        if sql_query is not None:
            print("IN sql_query")

            # Create a temporary view
            df.createOrReplaceTempView("temp_view")
            print("Created temp view ")
            transformed_df = spark.sql(sql_query)

            print("******transformed_df SCHEMA*********")
            transformed_df.printSchema()

        else:
            transformed_df = df

        transformed_df.show(truncate=False)

        writer = transformed_df.write.format("iceberg")

        writer = writer.option("write.format.default", "parquet")
        writer = writer.option("write.delete.mode", "copy-on-write")
        writer = writer.option("write.update.mode", "copy-on-write")
        writer = writer.option("write.merge.mode", "copy-on-write")
        # Set compression codec
        writer = writer.option("write.parquet.compression-codec", compression)

        if partition_cols:
            writer = writer.partitionBy(partition_cols)

        if spark.catalog.tableExists(full_table_name):
            print(f"Appending data to existing table {full_table_name}")
            writer.mode("append").saveAsTable(full_table_name)
        else:
            print(f"Creating new table {full_table_name}")
            writer.mode("overwrite").saveAsTable(full_table_name)

        print(f"Data successfully written to {full_table_name}")

        if sql_query:
            spark.catalog.dropTempView("temp_view")

        return True

    except Exception as e:
        print(f"Error loading data to Iceberg: {str(e)}")
        raise e


def process_message( messages,
                     spark,
                     catalog_name,
                     namespace,
                     table_name,
                     partition_cols=None,
                     sql_query=None,
                     compression='snappy'):
    try:
        batch_files = []

        for message in messages:
            payload = json.loads(message['Body'])
            # Use .get() to safely access 'Records' and provide a default empty list
            records = payload.get('Records', [])

            if records:  # Process only if records exist
                for record in records:
                    # Process each record
                    print(record)
            else:
                print("No records found in payload, skipping message.")
                continue
            protocol = "s3a"

            if protocol == "s3a":
                s3_files = [f"s3a://{record['s3']['bucket']['name']}/{record['s3']['object']['key']}" for record in
                            records]
            else:
                s3_files = [f"s3://{record['s3']['bucket']['name']}/{record['s3']['object']['key']}" for record in
                            records]

            batch_files.extend(s3_files)
        print("batch_files")
        print(batch_files)

        if batch_files:
            multiline_df = spark.read.option("multiline", "false").json(batch_files)

            load_data_to_iceberg(spark,multiline_df,
                                 catalog_name,
                                 namespace,
                                 table_name,
                                 partition_cols=partition_cols,
                                 sql_query=sql_query,
                                 compression=compression
                                 )


    except Exception as e:
        logging.error(f"Error processing message: {str(e)}")
        raise Exception("Error Processing Message")


def create_spark_session(catalog_name, namespace, s3_bucket_arn, region="us-east-1"):

    spark = SparkSession.builder \
        .appName("iceberg_lab") \
        .config("spark.jars.packages",
                "org.apache.iceberg:iceberg-spark-runtime-3.5_2.12:1.7.0,software.amazon.s3tables:s3-tables-catalog-for-iceberg-runtime:0.1.3,software.amazon.awssdk:glue:2.20.143,software.amazon.awssdk:sts:2.20.143,software.amazon.awssdk:s3:2.20.143,software.amazon.awssdk:dynamodb:2.20.143,software.amazon.awssdk:kms:2.20.143,org.apache.hadoop:hadoop-aws:3.3.4") \
        .config(f"spark.sql.catalog.{catalog_name}", "org.apache.iceberg.spark.SparkCatalog") \
        .config(f"spark.sql.catalog.{catalog_name}.client.region", region) \
        .config(f"spark.sql.catalog.{catalog_name}.warehouse", s3_bucket_arn) \
        .config(f"spark.sql.catalog.{catalog_name}.type", "glue") \
        .config(f"spark.sql.extensions", "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions") \
        .config(f"spark.sql.catalog.dev.io-impl", "org.apache.iceberg.aws.s3.S3FileIO") \
        .config("spark.hadoop.fs.s3a.endpoint", "s3.amazonaws.com") \
        .getOrCreate()

    # .config("spark.hadoop.fs.s3a.access.key", f"{ACCESS_KEY}") \
    # .config("spark.hadoop.fs.s3a.secret.key", f"{SECRET_KEY}") \

    spark.sql(f"CREATE NAMESPACE IF NOT EXISTS {catalog_name}.{namespace}")
    return spark

def main():
    catalog_name = "glue_catalog"
    namespace = "gps_glue_catalog"
    table_name = "gps_tracking_table"
    s3_bucket_arn = "s3://gps-tracking-data-bucket-02122025-sanjay-de/warehouse/"
    sqs_url = "https://sqs.us-east-1.amazonaws.com/058264127733/s3_event_queue"
    # partition_cols = "direction","seat_belt_status"
    partition_cols = None
    compression = "snappy"
    sql_query = """
        SELECT 
        *,
        input_file_name() as input_file,
        current_timestamp as processed_time,
        DATE_FORMAT(current_timestamp, 'yyyy-MM-dd') as processed_date
        FROM 
        temp_view
    """

    poller = Poller(sqs_url)


    spark = create_spark_session(catalog_name=catalog_name, namespace=namespace,
                                 s3_bucket_arn=s3_bucket_arn)

    while True:
        messages = poller.get_messages(10)

        process_message(messages,
                        spark,
                        catalog_name,
                        namespace,
                        table_name,
                        partition_cols,
                        sql_query,
                        compression
                        )
        poller.commit()
        logging.info(f"Waiting 10 seconds before next poll")
        time.sleep(10)

if __name__ == "__main__":
    main()