#!/usr/bin/env python3
import os
import sys
from urllib.parse import urljoin
from kanboard import Client as KanboardClient, ClientError


def usage():
    print("""Usage: list_kanboard_projects Kanboard_instance_URL

    Shows ids and names of Kanboard projects that the user specified with
    KANBOARD_USERNAME and KANBOARD_TOKEN environment variables is a member of.""")


def main():
    if len(sys.argv) < 2:
        usage()
        return
    instance_url = sys.argv[1]
    api_url = urljoin(instance_url, 'jsonrpc.php')
    api_user = os.getenv('KANBOARD_USERNAME')
    api_token = os.getenv('KANBOARD_TOKEN')
    client = KanboardClient(url=api_url, username=api_user, password=api_token)
    try:
        projects = client.get_my_projects()
    except ClientError as e:
        print('Fail:', e)
        return
    for p in projects:
        print(p['id'], p['name'])


if __name__ == '__main__':
    main()
