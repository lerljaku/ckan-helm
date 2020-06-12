import shutil
import os
import sys
import requests
import json


def check_solr_connection(solr_url, retry=None):
    print('\nCheck_solr_connection...')
    sys.stdout.flush()

    if retry is None:
        retry = 40
    elif retry == 0:
        print('Giving up ...')
        sys.exit(1)

    try:
        requests.get(solr_url)
    except requests.exceptions.RequestException as e:
        print((str(e)))
        print('Unable to connect to solr...retrying.')
        sys.stdout.flush()
        import time
        time.sleep(30)
        check_solr_connection(solr_url, retry=retry - 1)
    else:
        print("OK")


def prepare_configset(cfset_name):
    print("\nPreparing configset...")

    # Copy configset files from configmap volume into rw volume
    # and include schema.xml from ckan src
    shutil.copytree("/srv/solr-configset", "/srv/app/solr-configset")
    shutil.copyfile("/srv/app/src/ckan/ckan/config/solr/schema.xml",
                    "/srv/app/solr-configset/schema.xml")

    # Create zip
    print("Creating Configset ZIP file")
    shutil.make_archive('/srv/app/temp_configset', 'zip', 'solr-configset')

    # Upload configSet
    print("Uploading ZIP file to Zookeeper via Solr")
    data = open('/srv/app/temp_configset.zip', 'rb').read()
    url = solr_url + '/solr/admin/configs?action=UPLOAD&name=' + cfset_name
    print("Trying: " + url)
    try:
        res = requests.post(url,
                            data=data,
                            headers={'Content-Type':
                                     'application/octet-stream'})
    except requests.exceptions.RequestException as e:
        print('HTTP Status: ' + str(res.status_code) +
              ' Reason: ' + res.reason)
        print('HTTP Response: \n' + res.text)
        print((str(e)))
        print("\nConfigset exists - will be used for creating the collection.")

    print("OK")


def create_solr_collection(name, cfset_name, num_shards, repl_factor,
                           max_shards_node):
    print("\nCreating Solr collection based on uploaded configset...")
    url = solr_url + '/solr/admin/collections?action=CREATE&name=' + name
    url = url + '&numShards=' + num_shards
    url = url + '&replicationFactor=' + repl_factor
    url = url + '&maxShardsPerNode=' + max_shards_node
    url = url + '&collection.configName=' + cfset_name
    print("Trying: " + url)
    try:
        res = requests.post(url)
    except requests.exceptions.RequestException as e:
        print('HTTP Status: ' + str(res.status_code) +
              ' Reason: ' + res.reason)
        print('HTTP Response: \n' + res.text)
        print((str(e)))
        print("\nAborting...")
        sys.exit(3)

    print("OK")


def solr_collection_alreadyexists(solr_url):
    print("\nChecking if solr collection already exists")
    url = solr_url + '/solr/admin/collections?action=LIST&wt=json'
    print("Trying: " + url)
    try:
        res = requests.post(url)
    except requests.exceptions.RequestException as e:
        print('HTTP Status: ' + str(res.status_code) +
              ' Reason: ' + res.reason)
        print('HTTP Response: \n' + res.text)
        print((str(e)))
        print("\nAborting...")
        sys.exit(4)

    response_dict = json.loads(res.text)
    if collection_name in response_dict['collections']:
        print('Collection exists. Aborting.')
        sys.exit(5)

    print('Collection does not exist. OK...')


if (os.environ.get('CKAN_SOLR_URL', '') == ''):
    print("Error: CKAN_SOLR_URL env var not defined. Exiting...")
    sys.exit(1)

# Get the values for the initializing Solr from env
collection_name = os.environ.get('CKAN_SOLR_URL', '').split('/')[-1]
protocol = os.environ.get('CKAN_SOLR_URL', '').split('/')[0]
solr_url = protocol + "//" + os.environ.get('CKAN_SOLR_URL', '').split('/')[2]
num_shards = os.environ.get('CKAN_SOLR_INIT_NUMSHARDS', '2')
repl_factor = os.environ.get('CKAN_SOLR_INIT_REPLICATIONFACTOR', '1')
max_shards_node = os.environ.get('CKAN_SOLR_INIT_MAXSHARDSPERNODE', '10')
cfset_name = os.environ.get('CKAN_SOLR_INIT_CONFIGSETNAME', 'ckanConfigSet')

print("Preparing Solr...")
print("Solr host: " + solr_url)
print("Collection name: " + collection_name)

check_solr_connection(solr_url)
solr_collection_alreadyexists(solr_url)
prepare_configset(cfset_name)
create_solr_collection(collection_name, cfset_name, num_shards,
                       repl_factor, max_shards_node)
