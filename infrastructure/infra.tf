provider "aws" {
  region = "us-east-1"
}

  # Kinesis Data Stream
  resource "aws_kinesis_stream" "gps_data_stream" {
    name = "GPS-Tracking-Data-Stream"

    stream_mode_details {
      stream_mode = "ON_DEMAND"
    }

    retention_period = 24
  }


  # Firehose Delivery Stream for Kinesis to S3
  resource "aws_kinesis_firehose_delivery_stream" "gps_data_firehose" {
    name        = "gps-data-firehose-stream"
    destination = "extended_s3"

    # Configuring Kinesis as the source for Firehose
    kinesis_source_configuration {
      kinesis_stream_arn = aws_kinesis_stream.gps_data_stream.arn
      role_arn           = aws_iam_role.firehose_iam_role.arn

    }
    extended_s3_configuration {
      role_arn           = aws_iam_role.firehose_iam_role.arn
      bucket_arn         = aws_s3_bucket.gps_data_bucket.arn
      prefix             = "raw_batch_folder/"
      buffering_interval = 120
      buffering_size     = 5
      file_extension     = ".json"
      processing_configuration {
        enabled = "true"
        processors {
          type = "AppendDelimiterToRecord"
        }
      }
    }

    depends_on = [aws_kinesis_stream.gps_data_stream]

  }

  # IAM Role for Firehose to access S3
  resource "aws_iam_role" "firehose_iam_role" {
    name = "firehose-s3-role"
    assume_role_policy = jsonencode({
      Statement = [
        {
          Action = "sts:AssumeRole"
          Effect = "Allow"
          Principal = { Service = "firehose.amazonaws.com" }
        }
      ]
    })
  }

  resource "aws_iam_role_policy_attachment" "firehose_s3_access" {
    role       = aws_iam_role.firehose_iam_role.name
    policy_arn = "arn:aws:iam::aws:policy/AmazonS3FullAccess"
  }

  resource "aws_iam_role_policy_attachment" "firehose_kinesis_access" {
    role       = aws_iam_role.firehose_iam_role.name
    policy_arn = "arn:aws:iam::aws:policy/AmazonKinesisFullAccess"
  }

  resource "aws_sqs_queue" "s3_event_queue" {
    name  = "s3_event_queue"
    receive_wait_time_seconds = 10

  }

  # S3 Bucket for raw and processed data
  resource "aws_s3_bucket" "gps_data_bucket" {
    bucket = "gps-tracking-data-bucket-02122025-sanjay-de"
  }

  # S3 Bucket Notification to SQS
  resource "aws_s3_bucket_notification" "s3_to_sqs" {
    bucket = aws_s3_bucket.gps_data_bucket.id

    queue {
      queue_arn = aws_sqs_queue.s3_event_queue.arn
      events = ["s3:ObjectCreated:*"]
      filter_prefix = "raw_batch_folder/"
      filter_suffix       = ".json"


    }
    depends_on = [aws_sqs_queue.s3_event_queue, aws_s3_bucket.gps_data_bucket]

  }

  resource "aws_sqs_queue_policy" "sqs_policy" {
    queue_url = aws_sqs_queue.s3_event_queue.url

    policy = jsonencode({
      Version = "2012-10-17"
      Statement = [
        {
          Effect   = "Allow"
          Action   = "SQS:SendMessage"
          Resource = aws_sqs_queue.s3_event_queue.arn
          Principal = {
            Service = "s3.amazonaws.com"
          }
          Condition = {
            ArnEquals = {
              "aws:SourceArn" = aws_s3_bucket.gps_data_bucket.arn
            }
          }
        }
      ]
    })
  }



# # EC2 Instance for Spark processing
# resource "aws_instance" "spark_ec2_server" {
#   ami           = "ami-04b4f1a9cf54c11d0"  #ubuntu AMI
#   instance_type = "t2.medium"
#
#   # Specify the VPC Security Group and Subnet
#   vpc_security_group_ids = ["sg-0236b184f828d82d9"]
#   subnet_id             = "subnet-03270c3fdf727a8be"
#
#   # Specify your key pair for SSH access
#   key_name = "sanjay-2025"
#
#   iam_instance_profile = aws_iam_instance_profile.spark_role_profile.name
#
#   user_data = <<-EOF
#               #!/bin/bash
#               # Sleep for 30 seconds to ensure the system is ready
#               sleep 30
#
#               # Update package lists and install packages non-interactively
#               echo "Updating packages..." >> /tmp/user_data.log
#               export DEBIAN_FRONTEND=noninteractive
#               sudo apt update -y >> /tmp/user_data.log 2>&1
#               echo "Installing Java..." >> /tmp/user_data.log
#               sudo apt install -y default-jdk >> /tmp/user_data.log 2>&1
#
#               # Download and install Spark
#               echo "Downloading and installing Spark..." >> /tmp/user_data.log
#               wget https://dlcdn.apache.org/spark/spark-3.5.4/spark-3.5.4-bin-hadoop3.tgz >> /tmp/user_data.log 2>&1
#               tar xvf spark-3.5.4-bin-hadoop3.tgz >> /tmp/user_data.log 2>&1
#               sudo mv spark-3.5.4-bin-hadoop3 /opt/spark
#
#               # Set Spark environment variables
#               echo "export SPARK_HOME=/opt/spark" | sudo tee -a /home/ubuntu/.bashrc
#               echo "export PATH=\$PATH:\$SPARK_HOME/bin" | sudo tee -a /home/ubuntu/.bashrc
#
#               # Install Python 3.12 and create virtual environment
#               echo "Installing Python and setting up virtual environment..." >> /tmp/user_data.log
#               sudo apt install -y python3.12-venv >> /tmp/user_data.log 2>&1
#               python3 -m venv /home/ubuntu/etl_server_venv
#               source /home/ubuntu/etl_server_venv/bin/activate
#
#               # Install Python dependencies
#               echo "Installing Python dependencies..." >> /tmp/user_data.log
#               echo "
#               pandas
#               faker
#               boto3
#               pyarrow
#               pyspark
#               pyspark[sql]" > /home/ubuntu/requirements.txt
#               pip install -r /home/ubuntu/requirements.txt >> /tmp/user_data.log 2>&1
#               EOF
#
#   tags = {
#     Name = "spark-processing-instance"
#   }
#
#   availability_zone = "us-east-1a"
# }
#
#
# # IAM Role for EC2 to access S3, SQS, and CloudWatch
# resource "aws_iam_role" "spark_role" {
#   name = "spark-processing-role"
#   assume_role_policy = jsonencode({
#     Statement = [{
#       Action = "sts:AssumeRole"
#       Effect = "Allow"
#       Principal = { Service = "ec2.amazonaws.com" }
#     }]
#   })
# }
#
# resource "aws_iam_role_policy_attachment" "spark_s3_access" {
#   role       = aws_iam_role.spark_role.name
#   policy_arn = "arn:aws:iam::aws:policy/AmazonS3FullAccess"
# }
#
# resource "aws_iam_role_policy_attachment" "spark_sqs_access" {
#   role       = aws_iam_role.spark_role.name
#   policy_arn = "arn:aws:iam::aws:policy/AmazonSQSFullAccess"
# }
#
# resource "aws_iam_role_policy_attachment" "spark_cloudwatch_access" {
#   role       = aws_iam_role.spark_role.name
#   policy_arn = "arn:aws:iam::aws:policy/CloudWatchLogsFullAccess"
# }
#
# resource "aws_iam_instance_profile" "spark_role_profile" {
#   name = "spark-instance-profile"
#   role = aws_iam_role.spark_role.name
# }
#
# # CloudWatch Log Group
# resource "aws_cloudwatch_log_group" "spark_logs" {
#   name = "/aws/spark/iceberg-errors"
# }
#
# # CloudWatch Metric Filter for Errors
# resource "aws_cloudwatch_log_metric_filter" "spark_error_filter" {
#   name           = "SparkErrorFilter"
#   log_group_name = aws_cloudwatch_log_group.spark_logs.name
#   pattern        = "Error processing Spark job"
#   metric_transformation {
#     name      = "SparkErrors"
#     namespace = "SparkJobs"
#     value     = "1"
#   }
# }
#
# # CloudWatch Alarm for Spark Failures
# resource "aws_cloudwatch_metric_alarm" "spark_error_alarm" {
#   alarm_name          = "SparkProcessingFailures"
#   metric_name        = "SparkErrors"
#   namespace          = "SparkJobs"
#   statistic          = "Sum"
#   period             = 300
#   evaluation_periods = 1
#   threshold          = 1
#   comparison_operator = "GreaterThanOrEqualToThreshold"
#   alarm_actions      = [aws_sns_topic.spark_alerts.arn]
# }
#
# # SNS Topic for error notifications
# resource "aws_sns_topic" "spark_alerts" {
#   name = "Spark-Processing-Alerts"
# }
#
# # SNS Topic Subscription (Email)
# resource "aws_sns_topic_subscription" "spark_alert_subscription" {
#   topic_arn = aws_sns_topic.spark_alerts.arn
#   protocol  = "email"
#   endpoint  = "sanjay28.js@gmail.com"  # Replace with your email
# }