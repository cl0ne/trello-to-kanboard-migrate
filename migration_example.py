#!/usr/bin/env python3
#
# This is an example script for migrating single Trello board to already existing
# Kanboard project (you
# NB: for the sake of example all provided identifiers/tokens/keys here are randomly generated
# and you have to provide your own to perform migration. Please consult README for details.
#

import re

import pytz
from kanboard import Client as KanboardClient
from trello import TrelloClient

from migrator import Migrator


def _add_label_mappings(registry, pairs):
    for regex, value in pairs:
        registry[re.compile(regex, re.I)] = value


class MigrateFactory:
    def __init__(self):
        self._trello_client = TrelloClient(
            api_key='73256545e41ez1101a7x1c2280yf4600',
            api_secret='fdfba7d4287279b43f7x60261702c2c19340c6y18178589372d1d69661z6a3c3',
            token='1dd336d2e571ae0d9506620be008xy7543a6360443ff28f0ece033cc7345625b',
            token_secret='f07b4c4eaedda3e3168050xyz9c4eae1'
        )
        self._kanboard_client = KanboardClient(
            url='https://localhost/jsonrpc.php',
            username='user',
            password='4a24bc173c208a6f5512637320309wxf2e03af69eb765ec6016a8d7e9f7f'
        )

    def migrate(self, board_id, project_id):
        m = Migrator(self._trello_client, self._kanboard_client, board_id, project_id)
        # Customize Trello labels handling: use them to determine task priority and complexity
        _add_label_mappings(
            m.complexity_map,
            [('complexity: low', 2), ('complexity: medium', 5), ('complexity: high', 7)]
        )
        _add_label_mappings(
            m.priority_map,
            [('priority: low', 1), ('priority: medium', 3), ('priority: high', 5)]
        )
        # Explicitly map Trello usernames to Kanboard user ids instead of relying
        # on Migrator's attempts to match user by names
        # In any case users have to be added to the project beforehand
        m.users_map.update({'root': 0, 'admin': 1})
        # Workaround for kanboard issues #3653, #3654
        # (https://github.com/kanboard/kanboard)
        m.kanboard_timezome = pytz.timezone('Europe/Kiev')
        # Override attachment size limit
        m.attachment_max_size = 2 * 1024 * 1024
        m.run()


if __name__ == '__main__':
    MigrateFactory().migrate(
        board_id='e787e73314d22x516bf115cb',
        project_id=3
    )
