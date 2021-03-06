import argparse
import boto3
import datetime
import json
import numpy as np
import time


"""
Send fake data like the one sent with motor_encoder_producer.py
"""


def create_parser():
    parser = argparse.ArgumentParser("Send encoder data as json objects into a selected stream.")
    parser.add_argument("-s", "--stream", dest="stream_name", required=True,
                        help="The stream you'd like to create.", metavar="STREAM_NAME",)
    parser.add_argument("-r", "--regionName", "--region", dest="region", default="us-east-1",
                        help="The region you'd like to make this stream in. Default "
                        "is 'us-east-1'", metavar="REGION_NAME",)
    parser.add_argument("-p", "--period", dest="period", type=int,
                        help="Period to wait between every stream transmition. "
                        "If not set, data will be sent as fast as possible.",
                        metavar="MILLISECONDS",)
    parser.add_argument("-opm", "--objects_per_message", metavar="NUMBER_OBJECTS", default=1,
                        help="Default is 1.", type=int,)
    return parser.parse_args()


def wait_for_stream(kinesis_client, stream_name, sleep_seconds=3):
    # Wait for the provided stream to become active
    describe_stream_error = True
    while describe_stream_error:
        try:
            stream_description = kinesis_client.describe_stream(StreamName=stream_name)
            status = stream_description["StreamDescription"]["StreamStatus"]
            describe_stream_error = False
        except KeyError:
            pass
    while status != 'ACTIVE':
        print("Stream '{}' has status {}, sleeping for {} seconds.".format(stream_name, status,
                                                                           sleep_seconds))
        time.sleep(sleep_seconds)
        stream_description = kinesis_client.describe_stream(StreamName=stream_name)
        status = stream_description["StreamDescription"]["StreamStatus"]


def connect_to_stream(kinesis_client, stream_name):
    # Connect to stream, and if it does not exist, create it and wait until it is ACTIVE
    try:
        # The stream does exist already (if no Exception occurs)
        stream_description = kinesis_client.describe_stream(StreamName=stream_name)
        status = stream_description["StreamDescription"]["StreamStatus"]
        if status == "DELETING":
            print("The stream '{}' is being deleted, please rerun the script.".format(stream_name))
            return False
        elif status != "ACTIVE":
            wait_for_stream(kinesis_client, stream_name)
    except:
        # We assume the stream didn't exist so we will try to create it with just one shard
        print("Creating stream '{}'.".format(stream_name))
        kinesis_client.create_stream(StreamName=stream_name, ShardCount=1)
        wait_for_stream(kinesis_client, stream_name)
    return True


def main():
    args = create_parser()

    # Create and connect to stream
    stream_name = args.stream_name
    print("Connecting to stream '{}' in region '{}'.".format(stream_name, args.region))
    kinesis_client = boto3.client('kinesis', region_name=args.region)
    if not connect_to_stream(kinesis_client, stream_name):
        return

    # Create object that will be sent over and over again
    objects = []
    for i in range(args.objects_per_message):
        obj = {}
        obj["msg_type"] = 3
        obj["encoder"] = np.random.randint(-180, 180)
        obj["motor"] = np.random.randint(-255, 256)
        obj["timestamp"] = str(datetime.datetime.now())
        obj["encoder_counter"] = i * 100
        obj["motor_counter"] = i
        objects.append(obj)

    # Send encoder values into stream at args.period rate
    sleep_s = 0.0 if args.period is None or args.period < 0 else args.period / 1000.0
    counter = 0
    while True:
        for i in range(args.objects_per_message):
            objects[i]["timestamp"] = str(datetime.datetime.now())
            objects[i]["motor_counter"] = counter
            counter += 1
        encoder_motor_str = json.dumps(objects)
        try:
            kinesis_client.put_record(StreamName=stream_name, Data=encoder_motor_str,
                                      PartitionKey="SergiRamis")
            # print("Sent encoder message {} into stream '{}'.".format(encoder_motor_str,
            #                                                          stream_name))
        except Exception as e:
            print("Encountered an exception while trying to put sensor data into "
                  "stream '{}'.".format(stream_name))
            print("Exception: {}.".format(e))
        time.sleep(sleep_s)


if __name__ == '__main__':
    main()
