import boto3
import json
import time
import traceback
import uuid

# AWS CloudWatch Logs client
client = boto3.client("logs", region_name="us-east-1")

# Define log group
LOG_GROUP = "/aws/spark/iceberg-errors"


def create_log_stream():
    """Creates a new log stream with a unique name."""
    log_stream_name = f"log-stream-{uuid.uuid4()}"  # Generate a random name
    try:
        client.create_log_stream(logGroupName=LOG_GROUP, logStreamName=log_stream_name)
        print(f"Created log stream: {log_stream_name}")
        return log_stream_name
    except client.exceptions.ResourceAlreadyExistsException:
        print(f"Log stream already exists: {log_stream_name}")
        return log_stream_name
    except Exception as e:
        print(f"Error creating log stream: {e}")
        return None


def send_log_to_cloudwatch(error_message, log_stream_name):
    """Sends error logs to AWS CloudWatch."""
    try:
        response = client.describe_log_streams(
            logGroupName=LOG_GROUP,
            logStreamNamePrefix=log_stream_name
        )

        sequence_token = response['logStreams'][0].get('uploadSequenceToken', None) if response.get(
            'logStreams') else None

        log_event = {
            'logGroupName': LOG_GROUP,
            'logStreamName': log_stream_name,
            'logEvents': [
                {
                    'timestamp': int(time.time() * 1000),
                    'message': json.dumps(error_message)
                }
            ]
        }

        if sequence_token:
            log_event['sequenceToken'] = sequence_token

        client.put_log_events(**log_event)
        print(f"Error logged in stream: {log_stream_name}")

    except Exception as e:
        print(f"Failed to send logs to CloudWatch: {e}")


def log_exception():
    """Captures exception details and logs them to CloudWatch."""
    log_stream_name = create_log_stream()
    if not log_stream_name:
        print("Failed to create log stream. Skipping logging.")
        return

    try:
        raise  # Reraises the last exception
    except Exception as e:
        error_details = {
            "error_type": str(type(e).__name__),
            "error_message": str(e),
            "stack_trace": traceback.format_exc()
        }
        print("Error Occurred:", error_details)
        send_log_to_cloudwatch(error_details, log_stream_name)
