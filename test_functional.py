## Functional testing for autoscaler
import logging
import os
import unittest
from unittest import mock

import requests_mock

from autoscaler import AutoScaler

MOCK_URL = "http://test.com"


class TestAutoscaler(unittest.TestCase):
  @mock.patch.dict(os.environ, {"URL": MOCK_URL, "LOGLEVEL": "WARNING"})
  def setUp(self):
    tokens = "helloworld"
    with requests_mock.Mocker() as m:
      m.post(f"{MOCK_URL}/session", json={"token": tokens})
      self.autoscaler = AutoScaler(
        config_name="test_config.yml", secret_name="test_secret.yml"
      )
      self.assertEqual(
        self.autoscaler.cookies["argocd.token"],
        tokens,
        "Token is incorrect",
      )

  @mock.patch.dict(os.environ, {"URL": MOCK_URL})
  def test_logger(self):
    variable = [
      {"WARNING": logging.WARNING},
      {"ERROR": logging.ERROR},
      {"DEBUG": logging.DEBUG},
      {"INFO": logging.INFO},
    ]
    for i in variable:
      keys = "".join(list(i.keys()))
      with mock.patch.dict(os.environ, {"LOGLEVEL": keys}):
        log = self.autoscaler._check_logger()
        stat = self.autoscaler._evaluate_logger(log)
        message = f"Logger {log} is incorrect, should be {i}"
      self.assertEqual(log, keys, message)
      self.assertEqual(stat, i[keys], "Logging output is incorrect")

  @mock.patch.dict(os.environ, {"URL": MOCK_URL})
  def test_incorrect_logger(self):
    variable = [
      {"HELLO": logging.DEBUG},
    ]
    for i in variable:
      keys = "".join(list(i.keys()))
      with mock.patch.dict(os.environ, {"LOGLEVEL": keys}):
        log = self.autoscaler._check_logger()
        stat = self.autoscaler._evaluate_logger(log)
        message = f"Logger {log} is incorrect, should be DEBUG"
      self.assertEqual(log, "DEBUG", message)
      self.assertEqual(stat, i[keys], "Logging output is incorrect")

  @mock.patch.dict(os.environ, {"URL": MOCK_URL, "LOGLEVEL": "WARNING"})
  def test_incorrect_session_handling(self):
    with requests_mock.Mocker() as m:
      m.post(f"{MOCK_URL}/session", status_code=400)
      self.autoscaler = AutoScaler()

      self.assertRaises(Exception)

  @mock.patch.dict(os.environ, {"URL": MOCK_URL, "LOGLEVEL": "WARNING"})
  def test_token_missing_from_session(self):
    with requests_mock.Mocker() as m:
      m.post(f"{MOCK_URL}/session", json={"hello", "world"})
      self.autoscaler = AutoScaler()

      self.assertRaises(Exception)

  @mock.patch.dict(os.environ, {"URL": MOCK_URL, "LOGLEVEL": "WARNING"})
  def test_environment(self):
    variable = ["morning", "night"]
    for i in variable:
      with mock.patch.dict(os.environ, {"STATUS": i}):
        stat = self.autoscaler._evaluate_status_env()
        message = f"Status {stat} is incorrect, should be {i}"
      self.assertEqual(stat, i, message)

  @mock.patch.dict(os.environ, {"URL": MOCK_URL, "LOGLEVEL": "WARNING"})
  def test_incorrect_environment(self):
    variable = ["trigger", "work_hours"]
    for i in variable:
      with mock.patch.dict(os.environ, {"STATUS": i}):
        actual = self.autoscaler._evaluate_time()
        stat = self.autoscaler._evaluate_status_env()
        message = f"Status {stat} is incorrect, should be {actual}"
      self.assertEqual(stat, actual, message)

  @mock.patch.dict(os.environ, {"URL": MOCK_URL, "LOGLEVEL": "WARNING"})
  def test_get_app_status(self):
    expectedResult = {"spec": {"syncPolicy": {"automated": {}}}}
    with requests_mock.Mocker() as m:
      for i in self.autoscaler.config["server"]:
        m.get(f"{MOCK_URL}/applications/{i['name']}", json=expectedResult)
        response = self.autoscaler._get_application_status(i["name"])
        self.assertEqual(
          response,
          expectedResult,
          "Incorrect payload from application status",
        )

  @mock.patch.dict(
    os.environ,
    {"URL": MOCK_URL, "LOGLEVEL": "WARNING", "STATUS": "morning"},
  )
  def test_manual_sync(self):
    stat = self.autoscaler._evaluate_status_env()
    self.autoscaler._get_application_status = mock.MagicMock()
    self.autoscaler._update_application_status = mock.MagicMock()

    response = self.autoscaler.evaluate_auto_sync(stat)
    self.assertTrue(self.autoscaler._get_application_status.called)
    self.assertTrue(self.autoscaler._update_application_status.called)
    self.assertTrue(response)


if __name__ == "__main__":
  unittest.main()
