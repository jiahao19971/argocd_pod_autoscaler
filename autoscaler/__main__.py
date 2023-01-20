"""This is the main module for Pod autoscaler

This is where the pod autoscaler module run
"""
import sys

from .autoscaler import AutoScaler

if __name__ == "__main__":
  autoscaler = AutoScaler()
  try:
    status: bool = autoscaler.evaluate_auto_sync()
    if status:
      autoscaler.priority_checking()
    else:
      raise Exception("Failed to enable/disable autosync")
  # pylint: disable=broad-except
  except Exception as exc:
    autoscaler.logger.error("Oops something went wrong: %s", repr(exc))
    sys.exit(1)  # Retry Job Task by exiting the process
