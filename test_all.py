import json
import os
import time
import unittest
from unittest import mock

import command
from dotenv import load_dotenv

from autoscaler import AutoScaler

load_dotenv()


class TestAutoscaler(unittest.TestCase):
  def setUp(self):
    self.autoscaler = AutoScaler(
      config_name="test_config.yml", secret_name="test_secret.yml"
    )

  def db_status_checker(self, db_instance):
    if db_instance != None:
      status = self.autoscaler._check_db_status(db_instance)
      while status != "available" and status != "stopped":
        print(
          "This prints check every 1 min to see the db status as current"
          f" status show {status}"
        )
        time.sleep(60)
        status = self.autoscaler._check_db_status(db_instance)
      else:
        print(f"{db_instance}: {status}")
        return status
    else:
      print("No instance found")

  def db_verify(self, server, status, expected, days):
    argo_app_name = server["name"]
    db_instance_list = self.autoscaler._get_db_name_list()
    db_instance = self.autoscaler._get_db_instance_name(
      argo_app_name, db_instance_list
    )
    db_status = self.db_status_checker(db_instance)

    if status == "morning" and db_status == "stopped":
      s = 0
    elif status == "morning" and db_status == "available":
      s = 1
    elif status == "night" and db_status == "available":
      s = 1
    elif status == "night" and db_status == "stopped":
      s = 0
    else:
      print("Skipped")

    if db_instance != None:
      print(
        f"{db_instance} results: {s} vs expected:"
        f" {expected[days][os.environ['STATUS']]['database'][db_instance]}"
      )
      self.assertEqual(
        s,
        expected[days][os.environ["STATUS"]]["database"][db_instance],
        f"{db_instance}, {os.environ['DAY']}-{os.environ['STATUS']}: Database Scaling is incorrect",
      )
    else:
      print("skipped")

  def test_all_day(self):
    with open("expected.json") as f:
      expected = json.load(f)

      for days in expected:
        for status in expected[days]:
          with mock.patch.dict(os.environ, {"DAY": days, "STATUS": status}):
            res = command.run(["python", "-m", "autoscaler"])
            data = res.output
            data = data.decode()
            print(data)
            res.exit

            for server in self.autoscaler.config["server"]:
              # Get response from api request
              response = self.autoscaler._get_application_status(server["name"])

              ## Skip if api response failed
              if response == False:
                continue

              ## Get all the deployment only from resources
              getDeployment = list(
                filter(
                  lambda x: x["kind"] == "Deployment",
                  response["status"]["resources"],
                )
              )

              deploy = []
              rslt = 0

              for item in getDeployment:
                params = self.autoscaler._create_deployment_params(item)
                newResponse = self.autoscaler._get_application_resources(
                  server["name"], params, item["name"]
                )
                if newResponse == False:
                  continue
                params = self.autoscaler._prepare_params_for_scaling(
                  newResponse, params, item
                )
                print(
                  f"{os.environ['DAY']} {os.environ['STATUS']} {item['name']}: {self.autoscaler.replicas}"
                )
                deploy.append(self.autoscaler.replicas)

              if 0 in deploy:
                rslt = 0
              else:
                rslt = 1

              print(
                f"results: {rslt} vs expected: {expected[os.environ['DAY']][os.environ['STATUS']]['server'][server['name']]}"
              )
              self.assertEqual(
                rslt,
                expected[os.environ["DAY"]][os.environ["STATUS"]]["server"][
                  server["name"]
                ],
                f"{os.environ['DAY']}-{os.environ['STATUS']}: Pod Scaling is incorrect",
              )

              self.db_verify(server, status, expected, days)

            if "database" in self.autoscaler.config:
              for database in self.autoscaler.config["database"]:
                self.db_verify(database, status, expected, days)


if __name__ == "__main__":
  unittest.main()
