########### Python 3.2 #############
import os
import urllib.request, json

try:
    url = "https://data.fingrid.fi/api/datasets/339/data?startTime=2025-10-17T00:00&endTime=2025-10-18T00:00&pageSize=50"
    api_key = os.environ.get("FINGRID_API_KEY")
    if not api_key:
        raise RuntimeError("Set FINGRID_API_KEY before running this script.")

    hdr ={
    # Request headers
    'Cache-Control': 'no-cache',
    'x-api-key': api_key,
    }

    req = urllib.request.Request(url, headers=hdr)

    req.get_method = lambda: 'GET'
    response = urllib.request.urlopen(req)
    print(response.getcode())
    print(response.read())
except Exception as e:
    print(e)
####################################