import json
import os
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

  def test_day(self):
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
              ## Get response from api request
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
                f"{os.environ['DAY']} {os.environ['STATUS']} Scaling is incorrect",
              )


if __name__ == "__main__":
  unittest.main()
