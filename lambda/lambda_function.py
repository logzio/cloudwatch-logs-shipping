import base64
import gzip
import json
import logging
from io import BytesIO
import os

from python3.shipper.shipper import LogzioShipper

# set logger
logger = logging.getLogger()
logger.setLevel(logging.INFO)


def _extract_aws_logs_data(event):
    event_str = event["awslogs"]["data"]
    try:
        logs_data_decoded = base64.b64decode(event_str)
        logs_data_unzipped = gzip.GzipFile(fileobj=BytesIO(logs_data_decoded))
        logs_data_unzipped = logs_data_unzipped.read()
        logs_data_dict = json.loads(logs_data_unzipped)
        return logs_data_dict
    except ValueError as e:
        logger.error("Got exception while loading json, message: {}".format(e))
        raise ValueError("Exception: json loads")


def _extract_log_message(log, new_log):
    message = json.loads(log["message"])

    new_log["type"] = "redis-slow-logs"
    new_log["redisClusterId"] = message["CacheClusterId"]
    new_log["redisNodeId"] = message["CacheNodeId"]
    new_log["durationMicroSec"] = message["Duration (us)"]
    new_log["message"] = message["Command"]
    new_log["clientAddress"] = message["ClientAddress"]
    new_log["region"] = os.getenv("AWS_REGION", "undefined")


def _add_timestamp(log, new_log):
    new_log["@timestamp"] = str(log["timestamp"])


def _parse_cloudwatch_log(log):
    new_log = {}
    _add_timestamp(log, new_log)
    _extract_log_message(log, new_log)
    return new_log


def lambda_handler(event, context):
    aws_logs_data = _extract_aws_logs_data(event)

    shipper = LogzioShipper()
    logger.info("About to send {} logs".format(
        len(aws_logs_data["logEvents"])))
    for log in aws_logs_data["logEvents"]:
        if not isinstance(log, dict):
            raise TypeError(
                "Expected log inside logEvents to be a dict but found another type")
        new_log = _parse_cloudwatch_log(log)
        print(new_log)
        shipper.add(new_log)

    shipper.flush()
    