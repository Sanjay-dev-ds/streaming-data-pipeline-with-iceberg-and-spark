"""
Author : sanjay28.js@gmail.com
"""

import random
import time
import json
import logging
import boto3
from faker import Faker
from utility.cloudwatch_logger import log_exception

# Set up logging
logging.basicConfig(
    # filename="../gps_tracking.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

class VehicleManager:
    vehicles = [Faker().uuid4()[:8] for _ in range(20)]  # Class variable

    @staticmethod
    def get_random_vehicle():
        """Returns a random vehicle ID"""
        return random.choice(VehicleManager.vehicles)


class KinesisGPSStreamer:
    """Class to push GPS data to AWS Kinesis."""

    def __init__(self, stream_name, region="us-east-1"):
        """Initialize the Kinesis client."""
        self.stream_name = stream_name
        self.kinesis_client = boto3.client("kinesis", region_name=region)

    def push_to_kinesis(self, data):
        """Pushes GPS data to AWS Kinesis."""
        try:
            response = self.kinesis_client.put_record(
                StreamName=self.stream_name,
                Data=json.dumps(data),
                PartitionKey=data["vehicle_id"]
            )
            logging.info(f"Pushed to Kinesis: {data} | Response: {response['ResponseMetadata']['HTTPStatusCode']}")
        except Exception as e:
            logging.error(f"Failed to push data to Kinesis: {str(e)}")


def generate_gps_data():
    """Generates real-time GPS tracking data with additional attributes."""

    vehicle_id = VehicleManager.get_random_vehicle()
    latitude = round(random.uniform(-90, 90), 6)
    longitude = round(random.uniform(-180, 180), 6)
    speed = round(random.uniform(0, 120), 2)
    direction = random.choice(["N", "S", "E", "W", "NE", "NW", "SE", "SW"])
    timestamp = time.strftime('%Y-%m-%d %H:%M:%S')

    # Additional attributes
    is_ev = random.choice([True, False])
    fuel_level = None if is_ev else round(random.uniform(5, 100), 1)
    battery_level = round(random.uniform(10, 100), 1)  # If electric vehicle
    seat_belt_status = random.choice(["Fastened", "Unfastened"])
    collision_detected = random.choice([True, False, False, False,False,False])
    sudden_braking = random.choice([True, False, False,False])

    gps_data = {
        "vehicle_id": vehicle_id,
        "latitude": latitude,
        "longitude": longitude,
        "speed_kmh": speed,
        "direction": direction,
        "fuel_level": fuel_level,
        "battery_level": battery_level,
        "seat_belt_status": seat_belt_status,
        "collision_detected": collision_detected,
        "sudden_braking": sudden_braking,
        "timestamp": timestamp
    }

    return gps_data

if __name__ == "__main__":
    stream_name = "GPS-Tracking-Data-Stream"
    gps_streamer = KinesisGPSStreamer(stream_name)

    print("Streaming GPS data to AWS Kinesis...\n")

    try :
        while True:
            gps_update = generate_gps_data()
            gps_streamer.push_to_kinesis(gps_update)
            time.sleep(3)
    except Exception as e :
        print(e)
        # log_exception()