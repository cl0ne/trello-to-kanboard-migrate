#!/usr/bin/env python3
import os
import sys

from trello import TrelloClient, ResourceUnavailable


def usage():
    print("""Usage: list_trello_boards show

    Shows ids and names of Trello boards that the user specified with
    TRELLO_API_KEY, TRELLO_API_SECRET, TRELLO_TOKEN and TRELLO_TOKEN_SECRET
    environment variables is a member of.""")


def main():
    if len(sys.argv) < 2 or sys.argv[1].lower() != 'show':
        usage()
        return
    api_key = os.getenv('TRELLO_API_KEY')
    api_secret = os.getenv('TRELLO_API_SECRET')
    api_token = os.getenv('TRELLO_TOKEN')
    api_token_secret = os.getenv('TRELLO_TOKEN_SECRET')
    client = TrelloClient(
        api_key=api_key,
        api_secret=api_secret,
        token=api_token,
        token_secret=api_token_secret
    )
    try:
        boards = client.list_boards()
    except ResourceUnavailable as e:
        print('Fail:', e)
        return
    for b in boards:
        print(b.id, b.name)


if __name__ == '__main__':
    main()
