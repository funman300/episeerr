import getpass
import requests

   username = input("Plex username: ")
   password = getpass.getpass("Plex password: ")

   auth = {
       'user[login]': username,
       'user[password]': password
   }

   response = requests.post('https://plex.tv/users/sign_in.json', data=auth, headers={
       'X-Plex-Client-Identifier': 'OCDarr-TokenFetcher',
       'X-Plex-Product': 'OCDarr',
       'X-Plex-Version': '1.0'
   })

   if response.ok:
       token = response.json()['user']['authToken']
       print(f"Your Plex token: {token}")
   else:
       print(f"Error: {response.status_code} - {response.text}")