# Pod Autoscaler
Autoscaling pod via argocd api

## Prerequisite
1. Make to have python >= 3.8.5
2. `pip install -r requirements.txt`
3. `pre-commit install`
4. [Create a .env](#env)
5. [Create a config.yml](#configyml)
6. [Create a secret.yml](#secretyml)

### .env
```diff
+  By default, this file should be stored in ./.env

- The params is case sensitive, please do not change the capitalization

+ URL is a required ENV as it needs to be there to allow argocd api to work
+ Required
URL=ARGOCD API

+ STATUS can be added if you need to overwrite global time
+ Params available is morning | night | work_hours
+ Default changes base on time
# STATUS=morning

+ LOGLEVEL can be added if you want to reduce the amount of logs
+ Params available is DEBUG | INFO | WARNING | ERROR
+ Default is set to DEBUG
# LOGLEVEL=DEBUG

+ DAY can be added if you want to specific the daily behavior (for development purposes only)
+ Params available is Monday | Tuesday | Wednesday | Thursday | Friday | Saturday | Sunday
+ Default is set to the actual day
# DAY=Monday

+ TIME_SCALE_UP and TIME_SCALE_DOWN can be added if you want to change the time that is used to validate scale up and down
+ The timezone is via UTC, so adjust carefully
+ Default time to scale up is 1 AM UTC
+ Default time to scale down is 1 PM UTC
+ The structure of this json should be a string or it will failed
+ Ensure that the format follow as below '{"hours": number, "minutes": number}'
# TIME_SCALE_UP='{"hours":1, "minutes":0}'
# TIME_SCALE_DOWN='{"hours":13, "minutes":0}'

+ TIMEZONE can be added if you want to change the weekend scaling as we are using MYT to validate the specific DAY it is
+ This timezone does not affect the TIME_SCALE_UP and TIME_SCALE_DOWN as it will still be in UTC
+ Params available can refer to pytz: https://gist.github.com/heyalexej/8bf688fd67d7199be4a1682b3eec7568
+ Default is set to Asia/KualaLumpur
# TIMEZONE="Asia/KualaLumpur"

+ The channel you want the slack to sent the message to
# SLACKCHANNEL="#alerts-autoscaler"
+ The redirect url that you want the slack to redirect to
# SLACKREDIRECT="example.com"
```

### Config.yml
```diff
+  By default, this file should be stored in ./config.yml

# This section of the configuration file applies to the global autoscaler

server:
+----------------------------------------------------------------------------------------------------------|
+   name allows one to assign the application that you want the                                            |
+   autoscaler to run                                                                                      |
+----------------------------------------------------------------------------------------------------------|
+   This can be obtain from argocd                                                                         |
+----------------------------------------------------------------------------------------------------------|
+   This field is an array field where we can specify multiple name                                        |
+   with ([] | -)                                                                                          |
+----------------------------------------------------------------------------------------------------------|
  - name: example
+----------------------------------------------------------------------------------------------------------|
+   This field allow user to perform self pod scale up when it is set to False                             |
+   on the required application                                                                            |
+----------------------------------------------------------------------------------------------------------|
+   When set to True, the autoscaler will check based on time or ENV                                       |
+   to perform to scaling up or scaling down                                                               |
+----------------------------------------------------------------------------------------------------------|
+   Set to True by default                                                                                 |
+----------------------------------------------------------------------------------------------------------|
+   If you want to prevent it from scaling down, set it to False                                           |
+----------------------------------------------------------------------------------------------------------|
    autoscaledown: True
+----------------------------------------------------------------------------------------------------------|
+   This field will only work when the autoscaledown is set to True, when autoscaledown is set to False    |
+   make sure to remove this field.                                                                        |
+----------------------------------------------------------------------------------------------------------|
+   The field accept two type of string only (weekdays | weekend)                                          |
+----------------------------------------------------------------------------------------------------------|
+   When set to weekdays, the autoscaler will auto scale down on a daily basis and starting from Friday,   |
+   it will scale down until the next week Monday                                                          |
+----------------------------------------------------------------------------------------------------------|
+   When set to weekend, the autoscaler will not scale down until Saturday night                           |
+   it will automatically scale back up, once it reaches monday morning                                    |
+----------------------------------------------------------------------------------------------------------|
    operate_day: weekdays
+----------------------------------------------------------------------------------------------------------|
+   Optional field where it is only needed if u need extra downscaling of other database                   |
+   If you don't have any other database to shutdown, just remove it as a whole or it will cause error     |
+----------------------------------------------------------------------------------------------------------|
    database: example-db
+----------------------------------------------------------------------------------------------------------|
+   Optional field where you can specify the name of the database without it, it will read base on the name|
+   If you don't have any other database to shutdown, just remove it as a whole or it will cause error     |
+----------------------------------------------------------------------------------------------------------|
database:
+----------------------------------------------------------------------------------------------------------|
+ Works the same as server but the name should be from AWS RDS                                             |
+----------------------------------------------------------------------------------------------------------|
  - name: example-db
    autoscaledown: True
    operate_day: weekdays
+----------------------------------------------------------------------------------------------------------|
```

### Secret.yml
```diff
+  By default, this file should be stored in ./secret.yml

+ This section of the secret file applies to the global autoscaler for authentication
argocd:
+ This field allow user to specify the argocd account that they want to use
+ Default as autoscaler
+ This role have access to get and update all the staging server, httpbin for test
+ and staging, wordpress staging, and magento staging
+ Default as autoscaler
  username: <argocd local account username>
  password: <argocd local account password>


# This section of the secret file is used by the script to access to AWS Account to configure the database instance state.
aws:
# This user have access to describe, stop and start all the RDS instance in the Account.
  aws_access_key_id: <redacted>
  aws_secret_access_key: <redacted>
# The region would be the region that the instance is located, which is ap-southeast-1 by default
  region_name: ap-southeast-1
```

## File directory
Before running autoscaler locally, make sure to have the file directory as below
```
project
│    README.md
|    .dockerignore
|    .env
|    .gitignore
|    .coverage
|    .isort.cfg
|    .pre-commit-config.yaml
|    .pylintrc
|    config.yml
|    config.json
|    secret.yml
|    secret.json
|    time.json
|    docker-compose.yaml
|    Dockerfile
|    requirements.txt
|    test_all.py
|    test_day.py
|    test_db.py
|    test_functional.py
└─── autoscaler
     |   __init__.py
     |   __main__.py
     |   autoscaler_enum.py
     |   autoscaler.py
     |   slack_bot.py
     |   slackbot_enum.py
     |   validator.py
```

## To run this manually
`python -m autoscaler`

## To run the test file [Alpha]
More test case will be added\

### To use with coverage
`coverage run -m unittest discover`

### To generate coverage reports
`coverage report -m`

### Test case for the function of the autoscaler
`python test_functional.py`

### Test case for the expected output in daily scaling
To run this test case, make sure to create a file call `expected.json`
```diff
+ ---------------------------------------------------------------------------------
+ The first layer of the json represent the DAY you want the test case to run
+ [Monday, Tuesday, Wednesday, Thursday, Friday, Saturday, Sunday]
+ ---------------------------------------------------------------------------------
+ The second layer of the json represent the STATUS you want the test case to run
+ [morning, night]
+ ---------------------------------------------------------------------------------
+ The last layer of the json represent the server and the expected result
+ ---------------------------------------------------------------------------------
+ Value is represented with 1 or 0, with 1 being turn on and 0 being turn off
+ ---------------------------------------------------------------------------------
{
    "Monday": {
        "morning": {
            "server": {
                "example": 1,
            }

        },
        "night": {
            "server": {
                "example": 0,
            }
        }
    }
}
```
`python test_day.py`

### Test case for the expected output in daily scaling for pod and database
To run this test case, make sure to create a file call `expected.weekend.json`
```diff
+ ---------------------------------------------------------------------------------
+ The first layer of the json represent the DAY you want the test case to run
+ [Monday, Tuesday, Wednesday, Thursday, Friday, Saturday, Sunday]
+ ---------------------------------------------------------------------------------
+ The second layer of the json represent the STATUS you want the test case to run
+ [morning, night]
+ ---------------------------------------------------------------------------------
+ The third layer of the json represent the type of test you want to check
+ [server, database]
+ ---------------------------------------------------------------------------------
+ The last layer of the json represent the server/database and the expected result
+ ---------------------------------------------------------------------------------
+ Value is represented with 1 or 0, with 1 being turn on and 0 being turn off
+ ---------------------------------------------------------------------------------
{
    "Thursday": {
        "morning": {
            "server": {
                "example": 1,
            },
            "database": {
                "example": 1,
            }
        },
        "night": {
            "server": {
                "example": 1,
            },
            "database": {
                "example": 0,
            }
        }
    },
}
```
`python test_all.py`

### Test case for the expected output in daily scaling for database
To run this test case, make sure to create a file call `expected.json`
```diff
+ ---------------------------------------------------------------------------------
+ The first layer of the json represent the DAY you want the test case to run
+ [Monday, Tuesday, Wednesday, Thursday, Friday, Saturday, Sunday]
+ ---------------------------------------------------------------------------------
+ The second layer of the json represent the STATUS you want the test case to run
+ [morning, night]
+ ---------------------------------------------------------------------------------
+ The last layer of the json represent the database and the expected result
+ ---------------------------------------------------------------------------------
+ Value is represented with 1 or 0, with 1 being turn on and 0 being turn off
+ ---------------------------------------------------------------------------------
{
    "Thursday": {
        "morning": {
            "database": {
                "example": 1
            }
        },
        "night": {
            "database": {
                "example": 0
            }
        }
    },
}
```
`python test_db.py`


## To build image locally [If needed will create a drone.jsonnet to build the image, but for now not needed yet]
In the main directory, run:
```
docker build -t pod-autoscaler .
```

## If you need to sent alerts to Slack
Create a channel name #alerts-autoscaler or you can customize it
