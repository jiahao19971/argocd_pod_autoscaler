"""This is the main enum for Slackbot

Consist of all static variable in the Slackbot
"""
from enum import Enum


class SCALINGTYPE(Enum):
  DATABASE = "database"
  SERVER = "server"
  INIT = "init"
  TOKEN = "token"
  SYNC = "sync"


class SLACKBOTENUM(Enum):
  ERROR = "error"
  WARNING = "warning"
