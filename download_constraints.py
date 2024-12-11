import requests
import zipfile
import io
import json
import os

# Define the URL and headers
url = "https://bas-im.emcs.cornell.edu/api/v4/projects/3/jobs/artifacts/master/download?job=document"
headers = {
    "PRIVATE-TOKEN": os.environ.get('GITLAB-TOKEN'),
}

# Download the ZIP file
response = requests.get(url, headers=headers)

# Check if the request was successful
if response.status_code == 200:
    print("Download successful. Unpacking the ZIP file...")

    # Unpack the ZIP file
    with zipfile.ZipFile(io.BytesIO(response.content)) as z:
        # Extract all files to the current directory or specify a different path
        z.extractall()
        print("Unpacking completed.")

        # Check if 'constraints.json' is in the extracted files
        if 'constraints.json' in z.namelist():
            # Read 'constraints.json'
            with open('constraints.json', 'r') as json_file:
                data = json.load(json_file)
                print("Contents of 'constraints.json':")
                print(json.dumps(data, indent=4))  # Pretty print the JSON data
                # save the json data to a file
                with open('constraints_data.json', 'w') as json_file:
                    json.dump(data, json_file, indent=4)
        else:
            print("'constraints.json' not found in the extracted files.")
else:
    print(f"Failed to download file. Status code: {response.status_code}")
