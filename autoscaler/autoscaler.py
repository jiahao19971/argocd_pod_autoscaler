"""This is an module for Pod autoscaler

This class component consist of all the component required for the
Autoscaler to run
"""
import datetime
import json
import logging
import os

import boto3
import pytz
import requests
import yaml
from botocore.exceptions import ClientError
from dotenv import load_dotenv

from .autoscaler_enum import (
  DAY,
  DBSCALINGCHECK,
  DBSTATUS,
  DEBUGGER,
  LOGTYPE,
  OPERATE,
  STATUS,
  SYNC,
)
from .slack_bot import SlackBot
from .slackbot_enum import SCALINGTYPE
from .validator import AutoscalerValidator
from .empty import Empty

logging.basicConfig(format="%(asctime)s - %(levelname)s: %(message)s")

load_dotenv()


class AutoScaler:
  """This is the class component for Autoscaler

  It consist of the entire code base for the
  autoscaler to function
  """

  env_string = (
    "Environment variable %s was not found/have issue, "
    "switching back to default value: %s"
  )


  def __init__(self, config_name="config.yml", secret_name="secret.yml"):
    self.logger = logging.getLogger("pod-autoscaler")
    # Set name of config to config_name
    self.config_name = config_name
    # Set name of secret to secret_name
    self.secret_name = secret_name
    # Load secret.yml to secret variable
    self.secret = self._open_secret()
    # Load secret to slack

    if "slack" in self.secret:
      self.slack = SlackBot(self.secret)
    else:
      self.slack = Empty()
    # Load config.yml to config variable
    self.config = self._open_config()
    # Check for logger env existance
    logs = self._check_logger()
    # Set logger level base on env
    self.logger.setLevel(self._evaluate_logger(logs))
    self.logger.info("AutoScaler Initialize")
    # Get the timezone for day parameter (i.e. Monday, Tuesday and etc.)
    self.timezone = self._get_timezone()
    # Get the time to evaluate the scale up period (UTC only)
    self.time_scale_up = self._get_time_scale_up()
    # Get the time to evaluate the scale down period (UTC only)
    self.time_scale_down = self._get_time_scale_down()
    # Get argocd api
    self.url = self._get_url_env()
    # Get what day is today (i.e. Monday, Tuesday and etc.)
    self.today = self._get_day_env()
    # Get current time of the day (e.g. morning, night or work_hours)
    self.status = self._get_status_env()
    # Get user session token from argocd api
    self._get_user_session()
    # Get aws session from Boto3
    self._aws_session()
    # Set autoscale scale as empty dict, needed for database scaling
    self.pod_autoscale_status = {}
    # Check if all the server provided exist, and added result to config
    self._evaluate_application_permission()

    self.slack.post_fail_message_to_slack(
        SCALINGTYPE.INIT.value, "Environment:TIMEZONE", "test"
    )

  def _get_time_scale_down(self):
    default_value = {"hours": 13, "minutes": 0}
    try:
      time_scale_down = json.loads(os.environ["TIME_SCALE_DOWN"])
      self.logger.info("Environment variable TIME_SCALE_DOWN was found")
      with open("time.json", "r", encoding="utf-8") as validation_rules:
        schema = json.load(validation_rules)
        v = AutoscalerValidator(schema)
        if v.validate(time_scale_down, schema):
          self.logger.debug(
            "Validated TIME_SCALE_DOWN and no issue has been found"
          )
          return time_scale_down
        else:
          raise ValueError(v.errors)
    except KeyError:
      self.logger.warning(self.env_string, "TIME_SCALE_DOWN", default_value)
      return default_value
    except ValueError as er:
      self.logger.warning("Environment variable TIME_SCALE_DOWN error: %s", er)
      self.logger.warning(self.env_string, "TIME_SCALE_DOWN", default_value)
      return default_value

  def _get_time_scale_up(self):
    default_value = {"hours": 1, "minutes": 0}
    try:
      time_scale_up = json.loads(os.environ["TIME_SCALE_UP"])
      self.logger.info("Environment variable TIME_SCALE_UP was found")
      with open("time.json", "r", encoding="utf-8") as validation_rules:
        schema = json.load(validation_rules)
        v = AutoscalerValidator(schema)
        if v.validate(time_scale_up, schema):
          self.logger.debug(
            "Validated TIME_SCALE_UP and no issue has been found"
          )
          return time_scale_up
        else:
          raise ValueError(v.errors)
    except KeyError:
      self.logger.warning(self.env_string, "TIME_SCALE_UP", default_value)
      return default_value
    except ValueError as er:
      self.logger.warning("Environment variable TIME_SCALE_UP error: %s", er)
      self.logger.warning(self.env_string, "TIME_SCALE_UP", default_value)
      return default_value

  def _get_timezone(self) -> str:
    try:
      check = [x for x in pytz.all_timezones if x == os.environ["TIMEZONE"]]
      self.logger.info("Environment variable TIMEZONE was found")

      return check[0]
    except ValueError as e:
      self.logger.error(e)
      self.slack.post_fail_message_to_slack(
        SCALINGTYPE.INIT.value, "Environment:TIMEZONE", e
      )
      raise e
    except (IndexError, KeyError):
      default_value = "Asia/Kuala_Lumpur"
      self.logger.warning(self.env_string, "TIMEZONE", default_value)
      return default_value

  def _get_day_env(self) -> str:
    try:
      day = DAY(os.environ["DAY"])
      self.logger.info("Environment variable DAY was found")

      return day.value
    except ValueError as e:
      self.logger.error(e)
      self.slack.post_fail_message_to_slack(
        SCALINGTYPE.INIT.value, "Environment:DAY", e
      )
      raise e
    except KeyError:
      day = datetime.datetime.now(tz=pytz.timezone(self.timezone)).strftime(
        "%A"
      )
      default_value = str(day)
      self.logger.warning(self.env_string, "DAY", default_value)
      return default_value

  def _aws_session(self):
    try:
      self.logger.info("Creating an AWS session...")
      if "aws" in self.secret:
        session = boto3.Session(
          aws_access_key_id=self.secret["aws"]["aws_access_key_id"],
          aws_secret_access_key=self.secret["aws"]["aws_secret_access_key"],
          region_name=self.secret["aws"]["region_name"],
        )
        self.rds = session.client("rds")
      else:
        self.logger.info("No AWS secret found, disabling database scaling")
        self.rds = None
    except ClientError as error:
      message = f"Failed to create session: {error}"
      self.logger.error(json.dumps({"message": message, "severity": "ERROR"}))
      raise error

  def _check_logger(self) -> str:
    try:
      logger = DEBUGGER(os.environ["LOGLEVEL"])
      self.logger.info("Environment variable LOGLEVEL was found")

      return logger.value
    except ValueError as e:
      self.logger.error(e)
      self.slack.post_fail_message_to_slack(
        SCALINGTYPE.INIT.value, "Environment:LOGLEVEL", e
      )
      raise e
    except KeyError:
      self.logger.warning(self.env_string, "LOGLEVEL", DEBUGGER.DEBUG.value)
      return DEBUGGER.DEBUG.value

  def _evaluate_logger(self, logs):
    if logs == DEBUGGER.ERROR.value:
      return logging.ERROR
    elif logs == DEBUGGER.INFO.value:
      return logging.INFO
    elif logs == DEBUGGER.WARNING.value:
      return logging.WARNING
    else:
      return logging.DEBUG

  def _get_url_env(self):
    url: str = os.environ["URL"]
    self.logger.info("Environment variable URL was found")

    if url:
      return url
    else:
      url_error = "Envionment variable URL not found"
      self.slack.post_fail_message_to_slack(
        SCALINGTYPE.INIT.value, "Environment:URL", url_error
      )
      raise ValueError(url_error)

  def _get_user_session(self):
    try:
      data = {
        "username": self.secret["argocd"]["username"],
        "password": self.secret["argocd"]["password"],
      }
      self.logger.debug("Creating data for argocd session")
      result = requests.post(
        f"{self.url}/session",
        json=data,
        headers={"Content-Type": "application/json"},
        timeout=60,
      )
      self.logger.debug("Getting session for argocd ....")
      if result.status_code == 200:
        self.logger.info("Successfully retrieve argocd token")
        response = result.json()
        self.cookies = {"argocd.token": response["token"]}
        self.logger.info("Set argocd.token to cookies")
      else:
        self.slack.post_fail_message_to_slack(
          SCALINGTYPE.TOKEN.value, "Session Token", result.text
        )
        result.raise_for_status()
    except requests.exceptions.RequestException as reqerr:
      self.logger.error("Failed to authenticate: %s", reqerr)

  def _get_status_env(self):
    try:
      current_time = STATUS(os.environ["STATUS"])
      self.logger.info("Environment variable STATUS was found")

      return current_time.value
    except ValueError as e:
      self.logger.error(e)
      self.slack.post_fail_message_to_slack(
        SCALINGTYPE.INIT.value, "Environment:STATUS", e
      )
      raise e
    except KeyError:
      default_val = self._evaluate_time()
      self.logger.warning(self.env_string, "STATUS", default_val)
      return default_val

  def _evaluate_time(self):
    ct = datetime.datetime.now(tz=pytz.utc).time()
    if ct <= datetime.time(
      self.time_scale_up["hours"], self.time_scale_up["minutes"]
    ):
      return STATUS.MORNING.value
    elif ct >= datetime.time(
      self.time_scale_down["hours"], self.time_scale_down["minutes"]
    ):
      return STATUS.NIGHT.value
    else:
      return STATUS.WORKING.value

  def _open_config(self):
    with open(self.config_name, "r", encoding="utf-8") as stream:
      try:
        data = yaml.safe_load(stream)
        with open("config.json", "r", encoding="utf-8") as validation_rules:
          schema = json.load(validation_rules)
          v = AutoscalerValidator(schema)
          if v.validate(data, schema):
            self.logger.debug(
              "Validated config.yml and no issue has been found"
            )
            return data
          else:
            raise ValueError(v.errors)
      except ValueError as e:
        self.slack.post_fail_message_to_slack(
          SCALINGTYPE.INIT.value, "config.yaml", e
        )
        raise e
      except yaml.YAMLError as yamlerr:
        if hasattr(yamlerr, "problem_mark"):
          pm = yamlerr.problem_mark
          message = "Your file {} has an issue on line {} at position {}"
          format_message = message.format(pm.name, pm.line, pm.column)
          self.slack.post_fail_message_to_slack(
            SCALINGTYPE.INIT.value, "config.yaml", format_message
          )
          raise ValueError(format_message) from yamlerr
        else:
          message = "Something went wrong while parsing config.yaml file"
          self.slack.post_fail_message_to_slack(
            SCALINGTYPE.INIT.value, "config.yaml", message
          )
          raise ValueError(message) from yamlerr

  def _open_secret(self):
    with open(self.secret_name, "r", encoding="utf-8") as stream:
      try:
        data = yaml.safe_load(stream)
        with open("secret.json", "r", encoding="utf-8") as validation_rules:
          schema = json.load(validation_rules)
          v = AutoscalerValidator(schema)
          if v.validate(data, schema):
            self.logger.debug(
              "Validated secrets.yml and no issue has been found"
            )
            return data
          else:
            raise ValueError(v.errors)
      except yaml.YAMLError as yamlerr:
        if hasattr(yamlerr, "problem_mark"):
          pm = yamlerr.problem_mark
          message = "Your file {} has an issue on line {} at position {}"
          raise ValueError(
            message.format(pm.name, pm.line, pm.column)
          ) from yamlerr
        else:
          raise ValueError(
            "Something went wrong while parsing secret.yaml file"
          ) from yamlerr

  def _get_application_status(self, name):
    try:
      result = requests.get(
        f"{self.url}/applications/{name}", cookies=self.cookies, timeout=60
      )
      if result.status_code == 200:
        response = result.json()
        return response
      else:
        self.slack.post_fail_message_to_slack(
          SCALINGTYPE.SERVER.value, name, result.text
        )
        result.raise_for_status()
    except requests.exceptions.RequestException as reqerr:
      self.logger.error("Error occurs when getting app status: %s", reqerr)
      return False

  def _update_application_status(self, name, response):
    try:
      result = requests.put(
        f"{self.url}/applications/{name}",
        cookies=self.cookies,
        json=response,
        timeout=60,
      )
      if result.status_code == 200:
        self.logger.debug("%s autosync for %s", self.syncing, name)
      else:
        self.slack.post_fail_message_to_slack(
          SCALINGTYPE.SYNC.value, name, result.text
        )
        result.raise_for_status()
    except requests.exceptions.RequestException as reqerr:
      message = "Error occurs when updating app: %s"
      self.logger.error(message, reqerr)
      return False

  def _enable_auto_sync(self, server_response):
    self.syncing = SYNC.ENABLED.value
    ## We need to enable it
    server_response["spec"]["syncPolicy"] = {
      "automated": {"prune": False, "selfHeal": False}
    }

    return server_response

  def _disable_auto_sync(self, server_response):
    self.syncing = SYNC.DISABLED.value
    server_response["spec"]["syncPolicy"] = {}

    return server_response

  def _evaluate_sync_scale_period(
    self, server, criteria_scale_up, criteria_scale_down
  ):
    if server["autoscaledown"] is False and criteria_scale_up:
      return True
    elif (
      server["autoscaledown"]
      and self.status == STATUS.MORNING.value
      and (
        self.today == DAY.SUNDAY.value
        or (
          server["operate_day"] == OPERATE.WEEKDAYS.value
          and self.today == DAY.SATURDAY.value
        )
      )
      and criteria_scale_down
    ):
      return False
    elif (
      server["autoscaledown"]
      and self.status == STATUS.MORNING.value
      and self.today != DAY.SATURDAY.value
      and self.today != DAY.SUNDAY.value
      and criteria_scale_up
    ):
      return True
    elif (
      server["autoscaledown"]
      and self.status == STATUS.MORNING.value
      and self.today != DAY.SUNDAY.value
      and (
        (
          server["operate_day"] == OPERATE.WEEKEND.value
          and self.today == DAY.SATURDAY.value
        )
        or (
          server["operate_day"] == OPERATE.WEEKDAYS.value
          and self.today != DAY.SATURDAY.value
        )
      )
      and criteria_scale_up
    ):
      return True
    elif (
      server["autoscaledown"]
      and self.status == STATUS.NIGHT.value
      and self.today != DAY.SUNDAY.value
      and server["operate_day"] == OPERATE.WEEKEND.value
      and self.today != DAY.SATURDAY.value
      and criteria_scale_up
    ):
      return True
    elif (
      server["autoscaledown"]
      and self.status == STATUS.NIGHT.value
      and (
        self.today == DAY.SUNDAY.value
        or (
          server["operate_day"] == OPERATE.WEEKEND.value
          and self.today == DAY.SATURDAY.value
        )
        or (
          server["operate_day"] == OPERATE.WEEKDAYS.value
          and self.today != DAY.SATURDAY.value
          and self.today != DAY.SUNDAY.value
        )
      )
      and criteria_scale_down
    ):
      return False
    else:
      return None

  def _create_application_logging(
    self, server, runner, deployment=None, replicas=0
  ):
    if deployment is None:
      val = {"name": "error", "db_status": "error"}
    else:
      val = deployment
      if "db_status" not in val:
        val["db_status"] = ""
    criteria = " because operation day is set to {d} and today is {t}"
    sync_details: str = "No manual sync needed for {s}"
    scale_details: str = "No scaling needed for {s}"
    db_scale_details: str = "No scaling needed for {n}"
    logging_status = {
      "sync": {
        STATUS.MORNING.value: {
          LOGTYPE.DEFAULT.value: sync_details,
          LOGTYPE.DETAILS.value: sync_details + criteria,
        },
        STATUS.NIGHT.value: {
          LOGTYPE.DEFAULT.value: sync_details,
          LOGTYPE.DETAILS.value: sync_details + criteria,
        },
        STATUS.WORKING.value: "Manual sync for %s "
        "will not run during working hour",
      },
      "scale": {
        STATUS.MORNING.value: {
          LOGTYPE.DEFAULT.value: "No scaling up "
          "needed as replica = {r} for {n}",
          LOGTYPE.DETAILS.value: scale_details + criteria,
        },
        STATUS.NIGHT.value: {
          LOGTYPE.DEFAULT.value: "No scaling down "
          "needed as replica = 0 for {n}",
          LOGTYPE.DETAILS.value: scale_details + criteria,
        },
        STATUS.WORKING.value: "Scaling for %s "
        "will not run during working hour",
      },
      "database": {
        STATUS.MORNING.value: {
          LOGTYPE.DEFAULT.value: "No scaling up "
          "needed for {n} as db status = {db_st}",
          LOGTYPE.DETAILS.value: db_scale_details + criteria,
        },
        STATUS.NIGHT.value: {
          LOGTYPE.DEFAULT.value: "No scaling up "
          "needed for {n} as db status = {db_st}",
          LOGTYPE.DETAILS.value: db_scale_details + criteria,
        },
        STATUS.WORKING.value: "Database scaling for %s "
        "will not run during working hour",
      },
    }

    current_time = self.status
    type_of_logs = LOGTYPE.DEFAULT.value
    if self.status == STATUS.MORNING.value:
      if (
        server["operate_day"] == OPERATE.WEEKDAYS.value
        and (self.today in (DAY.SATURDAY.value, DAY.SUNDAY.value))
      ) or (
        server["operate_day"] == OPERATE.WEEKEND.value
        and self.today == DAY.SUNDAY.value
      ):
        type_of_logs = LOGTYPE.DETAILS.value
    elif self.status == STATUS.NIGHT.value:
      if (
        server["operate_day"] == OPERATE.WEEKEND.value
        and self.today != DAY.SATURDAY.value
      ) or (
        server["operate_day"] == OPERATE.WEEKDAYS.value
        and self.today == DAY.SUNDAY.value
      ):
        type_of_logs = LOGTYPE.DETAILS.value

    if current_time == STATUS.WORKING.value:
      messages: str = f"{logging_status[runner][current_time]}"
      self.logger.warning(messages, server["name"])
    else:
      messages: str = f"{logging_status[runner][current_time][type_of_logs]}"
      self.logger.debug(
        messages.format(
          s=server["name"],
          d=server["operate_day"],
          r=replicas,
          t=self.today,
          n=val["name"],
          db_st=val["db_status"],
        )
      )

  def _evaluate_application_permission(self):
    new_config_file = {"server": []}
    for server in self.config["server"]:
      response = self._get_application_status(server["name"])
      if response is False:
        continue
      else:
        server["application_status"] = response
        new_config_file["server"].append(server)
    if "database" in self.config:
      new_config_file["database"] = self.config["database"]
    self.config = new_config_file

  def evaluate_auto_sync(self):
    try:
      for server in self.config["server"]:
        response = server["application_status"]
        if response is False:
          continue

        criteria_scale_up = "automated" not in response["spec"]["syncPolicy"]
        criteria_scale_down = "automated" in response["spec"]["syncPolicy"]

        check_list = self._evaluate_sync_scale_period(
          server, criteria_scale_up, criteria_scale_down
        )

        if check_list:
          response = self._enable_auto_sync(response)
        elif check_list is False:
          response = self._disable_auto_sync(response)
        else:
          if server["autoscaledown"] is False and criteria_scale_down:
            self.logger.debug("No manual sync needed for %s", server["name"])
          else:
            self._create_application_logging(server, "sync")
          continue
        self._update_application_status(server["name"], response)
      return True
    except TypeError as typeerr:
      self.logger.error("TypeError: %s", typeerr)

  def _scale_deployment_pod(self, name, params, payload):
    try:
      update_replica = requests.post(
        f"{self.url}/applications/{name}/resource",
        cookies=self.cookies,
        params=params,
        data=payload,
        headers={"Content-Type": "application/json"},
        timeout=60,
      )
      if update_replica.status_code == 200:
        self.pod_autoscale_status[name] = DBSCALINGCHECK.SUCCESS.value
        self.logger.info("Scaling is successful for %s", name)
        pass
      else:
        self.pod_autoscale_status[name] = DBSCALINGCHECK.FAIL.value
        self.slack.post_fail_message_to_slack(
          SCALINGTYPE.SERVER.value, name, update_replica.text
        )
        update_replica.raise_for_status()
    except requests.exceptions.RequestException as reqerr:
      self.logger.error("Error occurs when getting app resources: %s", reqerr)

  def _create_deployment_params(self, deployment):
    params = {
      "name": deployment["name"],
      "namespace": deployment["namespace"],
      "resourceName": deployment["name"],
      "kind": deployment["kind"],
      "group": deployment["group"],
      "version": deployment["version"],
    }

    return params

  def _get_application_resources(self, name, params, deployment):
    try:
      result = requests.get(
        f"{self.url}/applications/{name}/resource",
        cookies=self.cookies,
        params=params,
        timeout=60,
      )
      if result.status_code == 200:
        response = result.json()
        return response
      else:
        self.slack.post_fail_message_to_slack(
          SCALINGTYPE.SERVER.value, deployment, result.text
        )
        result.raise_for_status()
    except requests.exceptions.RequestException as reqerr:
      self.logger.error("Error occurs when getting app resources: %s", reqerr)
      return False

  def _prepare_params_for_scaling(self, response, params, deployment):
    jsonify = json.loads(response["manifest"])
    self.replicas = jsonify["spec"]["replicas"]
    params["version"] = deployment["version"]
    params["patchType"] = "application/merge-patch+json"

    return params

  def _sort_scaling_down(self, server):
    if "sidekiq" in server["name"]:
      return 0
    elif "staging" in server["name"]:
      return 1
    else:
      return len(server["name"])

  def _sort_scaling_up(self, server):
    if "sidekiq" not in server["name"] and "staging" in server["name"]:
      return 0
    elif "sidekiq" in server["name"]:
      return 1
    else:
      return len(server["name"])

  def _check_db_status(self, db_instance):
    try:
      response = self.rds.describe_db_instances(
        DBInstanceIdentifier=db_instance
      )
      db_status = response["DBInstances"][0]["DBInstanceStatus"]
      return db_status
    except ClientError as e:
      self.logger.error(e)

  def _stop_database(self, db_instance, staging_name):
    db_status = self._check_db_status(db_instance)
    if db_status == DBSTATUS.AVAILABLE.value:
      try:
        self.rds.stop_db_instance(DBInstanceIdentifier=db_instance)
        self.logger.info(
          "%s: Success in stopping" " database instance", db_instance
        )
      except ClientError as e:
        self.logger.error(e)
    elif db_status == DBSTATUS.STOPPED.value:
      message = (
        f"{db_instance}: Database instance is already {db_status}, stop"
        " database action not needed"
      )
      self.logger.debug(message)
    else:
      message = (
        f"{db_instance}: Database instance status is '{db_status}', stop"
        " database action not executed"
      )
      self.logger.debug(message)
      self.slack.post_warn_message_to_slack(
        SCALINGTYPE.DATABASE.value, staging_name, message
      )

  def _start_database(self, db_instance, staging_name):
    db_status = self._check_db_status(db_instance)
    if db_status == DBSTATUS.STOPPED.value:
      try:
        self.rds.start_db_instance(DBInstanceIdentifier=db_instance)
        self.logger.info(
          "%s: Success in starting" " database instance", db_instance
        )
      except ClientError as e:
        self.logger.error(e)
    elif db_status == DBSTATUS.AVAILABLE.value:
      message = (
        f"{db_instance}: Database instance is already {db_status}, start"
        " database action not needed"
      )
      self.logger.debug(message)
    else:
      message = (
        f"{db_instance}: Database instance status is '{db_status}', start"
        " database action not executed"
      )
      self.logger.debug(message)
      self.slack.post_warn_message_to_slack(
        SCALINGTYPE.DATABASE.value, staging_name, message
      )

  def _get_db_name_list(self):
    response = self.rds.describe_db_instances()
    return response

  def _get_db_instance_name(self, staging_server_name, db_list, custom=False):
    key = staging_server_name
    if custom is False:
      key = staging_server_name.replace(".", "-")
    db_identifier = [
      x["DBInstanceIdentifier"]
      for x in db_list["DBInstances"]
      if key in x["DBInstanceIdentifier"]
    ]
    if len(db_identifier) == 1:
      self.logger.info(
        "Database exists," " database identifier: %s", db_identifier[0]
      )
      return db_identifier[0]
    elif len(db_identifier) > 1:
      exact_identifier = [x for x in db_identifier if x == key]
      if len(exact_identifier) == 1:
        self.logger.info(
          "Database exists," " database identifier: %s", exact_identifier[0]
        )
        return exact_identifier[0]
      else:
        v1_identifier = [x for x in db_identifier if x == f"{key}-v1"]
        if len(v1_identifier) == 1:
          self.logger.info(
            "Database exists," " database identifier: %s", v1_identifier[0]
          )
          return v1_identifier[0]
      self.logger.debug("Database instance not found in AWS")
      return None
    else:
      self.logger.debug("Database instance not found in AWS")
      return None

  def _scale_up_pods(self, params):
    self.logger.debug("Scaling up replicas from 0 to 1 for %s", params["name"])
    payload = json.dumps('{"spec":{"replicas":1}}')
    return payload

  def _scale_down_pods(self, params):
    self.logger.debug(
      "Scaling down replicas from %s to 0 for %s", self.replicas, params["name"]
    )
    payload = json.dumps('{"spec":{"replicas":0}}')
    return payload

  def _evaluate_pods_scaling(self):
    try:
      for server in self.config["server"]:
        self.logger.debug("Running scaling for %s", server["name"])

        ## Get response from _evaluate_application_permission
        response = server["application_status"]

        ## Skip if _evaluate_application_permission.application_status failed
        if response is False:
          continue

        ## Get all the deployment only from resources
        get_server_deployment_list = list(
          filter(
            lambda x: x["kind"] == "Deployment",
            response["status"]["resources"],
          )
        )

        ## Sort deployment order
        if (
          server["autoscaledown"] and self.status == STATUS.MORNING.value
        ) or (server["autoscaledown"] is False):
          get_server_deployment_list.sort(key=self._sort_scaling_up)
        elif server["autoscaledown"] and self.status == STATUS.NIGHT.value:
          get_server_deployment_list.sort(key=self._sort_scaling_down)

        for deployment in get_server_deployment_list:
          self.logger.debug("Scaling resource for %s", deployment["name"])
          params = self._create_deployment_params(deployment)
          application_resources = self._get_application_resources(
            server["name"], params, deployment["name"]
          )
          if application_resources is False:
            continue
          params = self._prepare_params_for_scaling(
            application_resources, params, deployment
          )

          criteria_scale_up = self.replicas == 0

          criteria_scale_down = self.replicas > 0

          check_list = self._evaluate_sync_scale_period(
            server, criteria_scale_up, criteria_scale_down
          )

          if check_list:
            payload = self._scale_up_pods(params)
          elif check_list is False:
            payload = self._scale_down_pods(params)
          else:
            if server["autoscaledown"] is False and criteria_scale_down:
              self.logger.debug(
                "No scaling up needed as replica = %s for %s",
                self.replicas,
                deployment["name"],
              )
            else:
              self._create_application_logging(
                server,
                "scale",
                deployment,
                self.replicas,
              )
            continue
          self._scale_deployment_pod(server["name"], params, payload)
      return True
    except TypeError as typeerr:
      self.logger.error("TypeError: %s", typeerr)

  def _scale_database_instance(self):
    try:
      db_instance_list = self._get_db_name_list()
      new_config = {"server": {}}
      if "database" in self.config:
        new_config["server"] = self.config["server"] + self.config["database"]
      for server in new_config["server"]:
        argo_app_name = server["name"]
        self.logger.info("Beginning database scaling for %s", argo_app_name)

        if (
          argo_app_name in self.pod_autoscale_status
          and self.pod_autoscale_status[argo_app_name]
          == DBSCALINGCHECK.FAIL.value
        ):
          self.logger.debug(
            "Skipping database scaling for %s as pod"
            " autoscaling failed for this server",
            argo_app_name,
          )
          continue

        custom = False
        if "database" in server:
          argo_app_name = server["database"]
          custom = True

        db_instance = self._get_db_instance_name(
          argo_app_name, db_instance_list, custom
        )

        if db_instance is not None:
          db_status = self._check_db_status(db_instance)
          criteria_scale_up = db_status == DBSTATUS.STOPPED.value
          criteria_scale_down = db_status == DBSTATUS.AVAILABLE.value

          check_list = self._evaluate_sync_scale_period(
            server, criteria_scale_up, criteria_scale_down
          )

          if check_list:
            self.logger.info("%s: Starting database instance", db_instance)
            self._start_database(db_instance, argo_app_name)
          elif check_list is False:
            self.logger.info(
              "%s: Proceeding with database shutdown", db_instance
            )
            self._stop_database(db_instance, argo_app_name)
          else:
            if server["autoscaledown"] is False and criteria_scale_down:
              self.logger.debug(
                "No database scaling up needed as db status = %s for %s",
                db_status,
                db_instance,
              )
            else:
              deployment = {"name": db_instance, "db_status": db_status}
              self._create_application_logging(server, "database", deployment)
            continue
        else:
          db_message = (
            "Database scaling not executed"
            " due to database instance not found"
          )
          self.logger.info(db_message)
          self.slack.post_warn_message_to_slack(
            SCALINGTYPE.DATABASE.value,
            argo_app_name,
            db_message,
          )
      return True
    except TypeError as typeerr:
      self.logger.error("TypeError: %s", typeerr)
      self.slack.post_fail_message_to_slack(
        SCALINGTYPE.DATABASE.value, argo_app_name, typeerr
      )

  def priority_checking(self):
    if self.status == STATUS.NIGHT.value:
      autoscale = self._evaluate_pods_scaling()
      if autoscale:
        self.logger.info("Server pods scaling completed")
        if self.rds != None:
          db_scale = self._scale_database_instance()
          if db_scale:
            self.logger.info("Database scaling completed")
          else:
            raise Exception("Database scaling failed")
      else:
        raise Exception("Server pods scaling failed")
    elif self.status == STATUS.MORNING.value:
      if self.rds != None:
        db_scale = self._scale_database_instance()
        if db_scale:
          self.logger.info("Database scaling completed")
        else:
          raise Exception("Database scaling failed")
      autoscale = self._evaluate_pods_scaling()
      if autoscale:
        self.logger.info("Server pods scaling completed")
      else:
        raise Exception("Server pods scaling failed")
    else:
      self.logger.warning("Scaling will not run during working hour")
