"""
This module contains SlackBot class
"""

import json, os
import time
from dotenv import load_dotenv
import requests

from .slackbot_enum import SLACKBOTENUM

load_dotenv()

class SlackBot:
  """
  This class is used to send message to Slack channel
  """

  def __init__(self, secret):
    self.secret = secret
    self.token = self.secret["slack"]["token"]
    self.channel = self._get_slack_channel()
    self.footer_icon = (
      "https://cncf-branding.netlify.app/img/"
      "projects/argo/stacked/color/argo-stacked-color.png"
    )
    self.title_link = (
      f"{self._get_slack_redirect()}"
    )
    self.time = time.time()

  def _get_slack_channel(self) -> str:
    try:
      slack_channel = os.environ['SLACKCHANNEL']

      return slack_channel
    except KeyError:
      slack_channel = "#alerts-autoscaler"
      return slack_channel

  def _get_slack_redirect(self) -> str:
    try:
      slack_redirect = os.environ['SLACKREDIRECT']

      return slack_redirect
    except KeyError:
      slack_redirect = "example.com"
      return slack_redirect

  def message_creator(self, current_status, server_type):
    error_text_message = "The {t} scaling for staging {s} was not executed"
    warn_text_message = "The {t} scaling for staging {s} is skipped"
    message_criteria = {
      SLACKBOTENUM.ERROR.value: {
        "database": {
          "title": "ERROR: Database scaling failed for: {s}",
          "text": error_text_message + "\n\nDetails:\n{m}",
        },
        "server": {
          "title": "ERROR: Pod scaling failed for: {s}",
          "text": error_text_message + "\n\nDetails:\n{m}",
        },
        "init": {
          "title": "ERROR: Pod autoscaler failed to run due to {s}",
          "text": "\n\nDetails:\n{m}",
        },
        "token": {
          "title": "ERROR: Failed to retrieve session token due to {s}",
          "text": "\n\nDetails:\n{m}",
        },
        "sync": {
          "title": "ERROR: Syncing failed for: {s}",
          "text": "\n\nDetails:\n{m}",
        },
      },
      SLACKBOTENUM.WARNING.value: {
        "database": {
          "title": "WARN: Database scaling skipped for: {s}",
          "text": warn_text_message + "\n\nDetails:\n{m}",
        },
        "server": {
          "title": "WARN: Pod scaling failed for: {s}",
          "text": warn_text_message + "\n\nDetails:\n{m}",
        },
      },
    }

    return message_criteria[current_status][server_type]

  def get_fail_message(self, server_type, server, message):
    fail = [
      {
        "color": "#DC143C",
        "title": self.message_creator(SLACKBOTENUM.ERROR.value, server_type)[
          "title"
        ].format(t=server_type, s=server, m=message),
        "title_link": self.title_link,
        "text": self.message_creator(SLACKBOTENUM.ERROR.value, server_type)[
          "text"
        ].format(t=server_type, s=server, m=message),
        "footer": "Pod Autoscaler",
        "footer_icon": self.footer_icon,
        "ts": self.time,
      }
    ]
    return fail

  def get_warn_message(self, server_type, server, message):
    warn = [
      {
        "color": "#F4BB44",
        "title": self.message_creator(SLACKBOTENUM.WARNING.value, server_type)[
          "title"
        ].format(t=server_type, s=server, m=message),
        "title_link": self.title_link,
        "text": self.message_creator(SLACKBOTENUM.WARNING.value, server_type)[
          "text"
        ].format(t=server_type, s=server, m=message),
        "footer": "Pod Autoscaler",
        "footer_icon": self.footer_icon,
        "ts": self.time,
      }
    ]
    return warn

  def post_warn_message_to_slack(self, server_type, staging, message):
    return requests.post(
      "https://slack.com/api/chat.postMessage",
      {
        "token": self.token,
        "channel": self.channel,
        "text": None,
        "attachments": json.dumps(
          self.get_warn_message(server_type, staging, message)
        ),
      },
      timeout=5,
    ).json()

  def post_fail_message_to_slack(self, server_type, staging, message):
    return requests.post(
      "https://slack.com/api/chat.postMessage",
      {
        "token": self.token,
        "channel": self.channel,
        "text": None,
        "attachments": json.dumps(
          self.get_fail_message(server_type, staging, message)
        ),
      },
      timeout=5,
    ).json()
