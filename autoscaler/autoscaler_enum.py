"""This is the main enum for Autoscaler

Consist of all static variable in the autoscaler
"""
from enum import Enum


class STATUS(Enum):
  """This enum consist of the STATUS env parameter

  It is used to validate if the status provided is
  fall into the list below
  """

  MORNING = "morning"
  NIGHT = "night"
  WORKING = "work_hours"

  @classmethod
  def _missing_(cls, value):
    choices = list(cls.__members__.keys())
    raise ValueError(
      f"{value} is not a valid {cls.__name__}, " f"please choose from {choices}"
    )


class DAY(Enum):
  """This enum consist of the DAY env parameter

  It is used to validate if the day provided is
  fall into the list below
  """

  MONDAY = "Monday"
  TUESDAY = "Tuesday"
  WEDNESDAY = "Wednesday"
  THURSDAY = "Thursday"
  FRIDAY = "Friday"
  SATURDAY = "Saturday"
  SUNDAY = "Sunday"

  @classmethod
  def _missing_(cls, value):
    choices = list(cls.__members__.keys())
    raise ValueError(
      f"{value} is not a valid {cls.__name__}, " f"please choose from {choices}"
    )


class DEBUGGER(Enum):
  """This enum consist of the log env parameter

  It is used to validate if the log provided is
  fall into the list below
  """

  DEBUG = "DEBUG"
  INFO = "INFO"
  WARNING = "WARNING"
  ERROR = "ERROR"

  @classmethod
  def _missing_(cls, value):
    choices = list(cls.__members__.keys())
    raise ValueError(
      f"{value} is not a valid {cls.__name__}, " f"please choose from {choices}"
    )


class SYNC(Enum):
  ENABLED = "enabled"
  DISABLED = "disabled"


class OPERATE(Enum):
  WEEKEND = "weekend"
  WEEKDAYS = "weekdays"


class LOGTYPE(Enum):
  DEFAULT = "default"
  DETAILS = "details"


class DBSCALINGCHECK(Enum):
  FAIL = "fail"
  SUCCESS = "success"


class DBSTATUS(Enum):
  STOPPED = "stopped"
  AVAILABLE = "available"
