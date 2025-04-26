import boto3
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
class Poller:
    def __init__(self, queue_url):
        self.queue_url = queue_url
        self.sqs_client = boto3.client('sqs', region_name='us-east-1')
        self.messages_to_delete = []

    def get_messages(self, batch_size):
        logging.info("Polling messages from SQS queue")
        # if there is no messages it will wait for 20 seconds

        response = self.sqs_client.receive_message(
            QueueUrl=self.queue_url,
            MaxNumberOfMessages=batch_size,
            WaitTimeSeconds=20
        )

        if 'Messages' in response:
            messages = response['Messages']
            for message in messages:
                self.messages_to_delete.append({
                    'ReceiptHandle': message['ReceiptHandle'],
                    'Body': message['Body']
                })
            logging.info(f"Retrieved {len(messages)} messages from the queue.")
            return messages
        else:
            logging.info("No messages retrieved from the queue.")
            return []

    def commit(self):
        for message in self.messages_to_delete:
            logging.info(f"Deleting message: {message['Body']}")
            self.sqs_client.delete_message(
                QueueUrl=self.queue_url,
                ReceiptHandle=message['ReceiptHandle']
            )
        logging.info(f"Deleted {len(self.messages_to_delete)} messages from the queue.")
        self.messages_to_delete = []
