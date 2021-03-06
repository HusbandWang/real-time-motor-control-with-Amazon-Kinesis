import argparse
import time
import datetime
import boto3
import random
import json


def create_parser():
    parser = argparse.ArgumentParser("""
Send random data as json objects into a selected stream.
""")
    parser.add_argument("-s", "--stream", dest="stream_name", required=True,
                        help="The stream you'd like to create.", metavar="STREAM_NAME",)
    parser.add_argument("-r", "--regionName", "--region", dest="region", default="us-east-1",
                        help="The region you'd like to make this stream in. Default "
                        "is 'us-east-1'", metavar="REGION_NAME",)
    parser.add_argument("-p", "--period", dest="period", type=int,
                        help="Period to wait between sending json messages. If not set, data will "
                        "be sent as fast as possible.",
                        metavar="MILLISECONDS",)
    parser.add_argument("--silent", dest="silent", action="store_true", help="Use it to mute "
                        "terminal prints every time a message is sent",)
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

    # Now the stream should exist
    n = [0, 0, 0]
    sleep_s = 0.0 if args.period is None else args.period / 1000
    if args.silent:
        print("Sending a json object every {} seconds.".format(sleep_s))
    while True:
        # Create object
        obj = {}
        r = random.randint(1, 501)
        obj["msg_type"] = 0 if r < 401 else (1 if r < 501 else 2)
        if obj["msg_type"] == 1:
            obj["value"] = float(int(random.random() * 256))  # Value in range [0, 255]
        else:
            obj["value"] = random.random() * 2000 - 1000  # Value in range [-1000.0, 1000.0)
        n[obj["msg_type"]] += 1
        obj["sequence"] = n[obj["msg_type"]]
        obj["timestamp"] = str(datetime.datetime.now())

        # Convert to json
        json_str = json.dumps(obj)

        # Send into stream
        try:
            kinesis_client.put_record(StreamName=stream_name, Data=json_str, PartitionKey="123")
            if not args.silent:
                print("{:5}. Sent data '{:+.5f}' with message type '{}' into stream '{}'.".format(
                      obj["sequence"], obj["value"], obj["msg_type"], stream_name))
        except Exception as e:
            print("Encountered an exception while trying to put record '{}'".format(json_str) +
                  " into stream '{}'.".format(stream_name))
            print("Exception: {}.".format(e))

        # print("Sleeping for {} milliseconds.".format(args.period))
        time.sleep(sleep_s)


if __name__ == '__main__':
    main()
