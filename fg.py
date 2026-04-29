import requests
#import pip._vendor.requests
import pandas as pd
import os
from datetime import datetime, timedelta

#msg = "Roll a dice!"
#print(msg)


# Fingrid API endpoint for aFRR activation
#url = "https://api.fingrid.fi/v1/variable/246/events/json"

#url = "https://data.fingrid.fi/api/datasets/246/events/json" #404

#url = "https://data.fingrid.fi/api/datasets/246"

url = "https://data.fingrid.fi/api/datasets/1/data"

api_key = os.environ.get("FINGRID_API_KEY")
if not api_key:
    raise RuntimeError("Set FINGRID_API_KEY before running this script.")

headers = {"x-api-key": api_key}  # Register at https://data.fingrid.fi/

# Get last 24 hours of aFRR activation data
response = requests.get(url, headers=headers, params={
    "start_time": (datetime.now() - timedelta(hours=24)).isoformat(),
    "end_time": datetime.now().isoformat()
})

if response.status_code == 200:
    data = response.json()

    '''
    df = pd.DataFrame(data)
    
    # Check if there were any activations
    recent_activations = df[df['value'] != 0]
    
    if len(recent_activations) > 0:
        print(f"aFRR activations detected: {len(recent_activations)} events")
        print("Recent activations:")
        print(recent_activations[['start_time', 'end_time', 'value']].head())
    else:
        print("No aFRR activations in the last 24 hours")
        '''


    print(data)    
else:
    print(f"API Error: {response.status_code}")