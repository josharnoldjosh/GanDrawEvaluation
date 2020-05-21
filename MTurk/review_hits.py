import json
import xmltodict
from api import API

"""
Remember to download the saved data from the server!
"""

api = API()

data = []
with open('./hit_data', 'r') as file:
    data = json.load(file)

for to_delete_idx, hit_data in enumerate(data):
    try:
        hit_id = hit_data['id']
        hit = api.client.get_hit(HITId=hit_id)
        response = api.client.list_assignments_for_hit(
            HITId=hit_id,
            AssignmentStatuses=['Submitted'],
            MaxResults=100,
        )
        assignments = response['Assignments']
        for assignment in assignments:
            worker_id = assignment['WorkerId']
            assignment_id = assignment['AssignmentId']
            result = xmltodict.parse(str(assignment['Answer']))
            result = dict(dict(result)['QuestionFormAnswers'])
            for idx, i in enumerate(result.items()):
                if idx == 0: continue
                try:
                    # The token generated in the url                
                    covo_id = i[1][1]['FreeText'].split("/")[-2]
                    token = i[1][0]['FreeText']
                
                    # open f"{user_token}.json" to check the code in there
                    with open(f'./saved_data/{covo_id}.json', 'r') as file:
                        retrieved_data = json.load(file)                    

                    # temp
                    print(f"User inputted {token}, correct answer is {retrieved_data['token']}.")
                    if token == retrieved_data['token']:
                        print("Should accept!")
                        api.client.approve_assignment(AssignmentId=assignment_id, RequesterFeedback='good', OverrideRejection=False)
                    else:
                        print("Should reject!")
                        api.client.reject_assignment(AssignmentId=assignment_id, RequesterFeedback='You did not paste in the correct code, which we explicity asked you to do so.')
                except:
                    raise ValueError("Failed to extract data")
    except Exception as error:
        print(error)
        continue