import requests


url = "https://www.0766cargo.com/logistics/getOne?waybillNumber={0}"

def get_data(id):
    response = requests.get(url.format(id))
    # print(url.format(id))
    # print(response.json())
    if response.status_code == 200:
        return response.json()
    else:
        return {
            "error": f"Request failed with status code {response.status_code}"
        }
