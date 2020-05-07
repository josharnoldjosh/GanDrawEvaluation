import sys
import boto3
import uuid
from config import credentials, config
import json

class API:
    def __init__(self):
        # Define keys
        ACCESS_KEY = credentials["Credentials"]["AccessKeyId"]
        SECRET_KEY = credentials["Credentials"]["SecretAccessKey"]
        SESSION_TOKEN = credentials["Credentials"]["SessionToken"]

        # Create hits in Sandbox mode
        create_hits_in_live = config['live']

        # Define environments
        self.environments = {
                "live": {
                    "endpoint": "https://mturk-requester.us-east-1.amazonaws.com",
                    "preview": "https://www.mturk.com/mturk/preview",
                    "manage": "https://requester.mturk.com/mturk/manageHITs",
                    "reward": "0.00"
                },
                "sandbox": {
                    "endpoint": "https://mturk-requester-sandbox.us-east-1.amazonaws.com",
                    "preview": "https://workersandbox.mturk.com/mturk/preview",
                    "manage": "https://requestersandbox.mturk.com/mturk/manageHITs",
                    "reward": "0.11"
                },
        }

        # Load environment
        self.mturk_environment = self.environments["live"] if create_hits_in_live else self.environments["sandbox"]

        # Create session
        session = boto3.Session(
            aws_access_key_id=ACCESS_KEY,
            aws_secret_access_key=SECRET_KEY,
            aws_session_token=SESSION_TOKEN,
        )

        # Create client
        self.client = session.client(
            service_name='mturk',
            region_name='us-east-1',
            endpoint_url=self.mturk_environment['endpoint'],
        )

        # # Test account balance
        user_balance = self.client.get_account_balance()

        # # In Sandbox this always returns $10,000. In live, it will be your acutal balance.
        # print(f"Your account balance is {user_balance['AvailableBalance']}")

        self.hit_data = []

    def clear_hit_data(self):
        with open('./hit_data', 'w') as file:
            json.dump(self.hit_data, file)

    def create_hit(self, question):
        # worker_requirements = [{
        #     'QualificationTypeId': '00000000000000000071',
        #     'Comparator': 'EqualTo',            
        #     'LocaleValues':[{
        #         'Country':"US"
        #     }]
        # }]
        worker_requirements = []

        # Create the HIT
        response = self.client.create_hit(
            MaxAssignments=1,
            LifetimeInSeconds=7200*12, # How long the hits exist for - 2 hours * 12 = 24 hours
            AssignmentDurationInSeconds=1800, # How long you can do each task - 30 minutes
            Reward=config['reward'],
            Title=config['title'],
            Keywords=config['keywords'],
            Description=config['description'],
            Question=question,    
            AutoApprovalDelayInSeconds=60*60*24, # one day delay
            QualificationRequirements=worker_requirements
        )

        try:
            self.hit_data = json.load(open('./hit_data'))
        except:
            pass

        # The response included several fields that will be helpful later
        hit_info = {}
        hit_info["id"] = response['HIT']['HITId']
        hit_info['type'] = response['HIT']['HITTypeId']
        hit_info['preview'] = self.mturk_environment['preview'] + "?groupId={}".format(hit_info['type'])        
        hit_info['manage'] = self.mturk_environment['manage']
        self.hit_data.append(hit_info)

        with open('./hit_data', 'w') as file:
            json.dump(self.hit_data, file)

        print(hit_info['id'], hit_info['preview'])