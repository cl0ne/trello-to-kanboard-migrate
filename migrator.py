import base64
from datetime import datetime
from urllib.parse import urlparse

import pytz
import requests


class Migrator:
    kanboard_datetime_format = '%Y-%m-%d %H:%M'
    trello_datetime_format = '%Y-%m-%dT%H:%M:%S.%fZ'

    def __init__(self, trello_client, kanboard_client, board_id, project_id):
        self._kanboard = kanboard_client
        self._trello = trello_client

        self.users_map = {}
        self.complexity_map = {}
        self.priority_map = {}
        self.attachment_max_size = 3 * 1024 * 1024  # bytes

        # Workaround for kanboard issues #3653, #3654
        # (https://github.com/kanboard/kanboard)
        self.kanboard_timezome = pytz.UTC

        self.project_id = project_id
        self.board = self._trello.get_board(board_id)
        self.lists = self.board.get_lists('all')

        self._members2users = {}
        self._migrated_cards = {}
        self._unmigrated_relations = set()

    def run(self):
        lists2columns = self._create_columns_from_lists()
        project_users = self._kanboard.get_project_users(project_id=self.project_id)
        members = self.board.all_members()
        self._members2users = self._map_members2users(members, project_users)

        for list_id, column in lists2columns.items():
            column_id = column['id']
            board_list = column['origin']
            self._migrate_column(board_list, column_id)

        for a, b in self._unmigrated_relations:
            a_id = self._migrated_cards.get(a)
            b_id = self._migrated_cards.get(b)
            if not a_id or not b_id:
                print('Skip relation for tasks {} {} - some of them are not migrated'.format(a, b))
                continue

            self._add_task_relation(a_id, b_id)

    def _create_columns_from_lists(self):
        columns = self._kanboard.get_columns(project_id=self.project_id)
        column_names = {c['title']: c for c in columns}
        mapped = {}

        print('Migrate lists to columns:')
        for board_list in self.lists:
            status = 'done'
            column = None
            name = board_list.name
            if name not in column_names:
                column_id = self._kanboard.add_column(
                    project_id=self.project_id,
                    title=name
                )

                if type(column_id) is int:
                    column = {
                        'id': column_id,
                        'title': name,
                        'origin': board_list
                    }
                else:
                    status = 'failed'
            else:
                status = 'already exists'
                column = column_names[name]
                column['origin'] = board_list

            if column:
                mapped[board_list.id] = column

            print('  "{name}" [{status}]'.format(name=name, status=status))

        print('Removing extra columns...')
        for c in columns:
            if c.get('origin'):
                continue

            success = self._kanboard.remove_column(column_id=c['id'])
            print('  {id} "{title}" - {status}'.format(
                **c,
                status='done' if success else 'failed'
            ))
        print('complete')

        return mapped

    def _map_members2users(self, members, project_users):
        mapped = {}
        for m in members:
            user_id = self.users_map.get(m.username)
            if user_id is None:
                match_names = lambda i, n: m.username == n or m.full_name == n
                matched = list(filter(match_names, project_users.values()))

                if not matched:
                    print(' No match found for member "{}"'.format(m.username))
                    continue

                if len(matched) > 1:
                    print(' More than one match found for member "{}": {}'.format(
                        m.username,
                        ', '.join(n for _, n in matched)
                    ))
                    continue
                user_id, _ = matched
            mapped[m.id] = {'id': user_id, 'username': m.username}
        return mapped

    def _migrate_card_members(self, member_ids):
        if not member_ids:
            return None, []

        owner_id = None
        mentions = []
        for i in member_ids:
            matched = self._members2users.get(i)
            if not matched:
                mentions.append(i)
                continue

            if owner_id:
                mentions.append('@{}'.format(matched['username']))
            else:
                owner_id = matched['id']
        return owner_id, mentions

    def _add_task_relation(self, a_id, b_id):
        task_link_id = self._kanboard.create_task_link(
            task_id=a_id,
            opposite_task_id=b_id,
            link_id=1  # generic "related to", don't blame me for hardcoding this
        )
        if _operation_failed(task_link_id):
            print(' Failed to add related task {} link for task {}'.format(
                a_id, b_id
            ))
            return None
        return task_link_id

    def _migrate_column(self, board_list, column_id):
        cards = board_list.list_cards('all')
        for card in cards:
            card.fetch(eager=False)
            task_id = self._migrate_card(column_id, card)

            if task_id is None:
                print('Failed to create task "{}" in column "{}"'.format(
                    card.name,
                    board_list.name
                ))
                continue

            if card.is_due_complete or card.closed:
                self._kanboard.close_task(task_id=task_id)

            self._migrated_cards[card.id] = task_id
            self._migrate_comments(task_id, card.comments)
            self._migrate_checklists(task_id, card.checklists)
            attachments = card.get_attachments()
            self._migrate_attachments(card.id, task_id, attachments)

    def _migrate_checklists(self, task_id, checklists):
        status_map = {True: 2, False: 0}
        for checklist in checklists:
            for item in checklist.items:
                subtask_id = self._kanboard.create_subtask(
                    task_id=task_id,
                    title=item['name'],
                    status=status_map[item['checked']]
                )
                if type(subtask_id) is bool:
                    print('  Failed to migrate checklist "{}" item "{}"'.format(
                        checklist.name, item.name
                    ))

    def _migrate_card(self, column_id, card):
        priority, score, tags = self._map_labels(card.labels)
        description = card.description
        owner_id, mentions = self._migrate_card_members(card.member_id)
        if mentions:
            description += '\n\nOther members of original card: ' + ' '.join(mentions)
            tags.append('migration: more than one member')

            print(' More than one member on "{}" card'.format(card.name))

        date_due = card.due
        if date_due:
            date_due = _convert_datetimes(
                card.due, Migrator.trello_datetime_format, self.kanboard_timezome
            ).strftime(Migrator.kanboard_datetime_format)

        task_id = self._kanboard.create_task(
            title=card.name,
            project_id=self.project_id,
            column_id=column_id,
            owner_id=owner_id,
            date_due=date_due,
            description=description,
            score=score,
            priority=priority,
            tags=tags
        )

        return None if _operation_failed(task_id) else task_id

    def _migrate_comments(self, task_id, comments_json):
        for c in comments_json:
            author_id = c['idMemberCreator']
            author_id = self._members2users[author_id]['id']
            text = c['data']['text']
            comment_id = self._kanboard.create_comment(
                task_id=task_id,
                user_id=author_id,
                content=text
            )
            if _operation_failed(comment_id):
                print('Failed to migrate comment "{}" by {}'.format(
                    text, c['idMemberCreator']
                ))

    def _get_related_card_id(self, url):
        url_parts = urlparse(url)
        if url_parts.netloc != 'trello.com':
            return None

        path_components = _extract_path_components(url_parts.path)
        if len(path_components) < 2 or path_components[0] != 'c':
            return None

        related_card = self._trello.get_card(card_id=path_components[1])
        if related_card.idBoard == self.board.id:
            return related_card.id

        return None

    def _migrate_attachments(self, card_id, task_id, attachments):
        related_links_set = set()
        for attachment in attachments:
            if attachment.is_upload:
                if not self._try_reupload_attachment(attachment, task_id):
                    self._add_external_link_to_task(attachment, task_id)
                continue

            # handle related cards separately
            related_card_id = self._get_related_card_id(attachment.url)
            if related_card_id:
                if related_card_id == card_id or related_card_id in related_links_set:
                    continue

                related_task = self._migrated_cards.get(related_card_id, None)
                if not related_task:
                    self._unmigrated_relations.add((card_id, related_card_id))
                    continue

                task_link_id = self._add_task_relation(
                    task_id,
                    related_task
                )
                if task_link_id is not None:
                    self._unmigrated_relations.discard((related_card_id, card_id))
                    related_links_set.add(related_card_id)
                continue

            self._add_external_link_to_task(attachment, task_id)

    def _try_reupload_attachment(self, attachment, task_id):
        if self.attachment_max_size < attachment.bytes:
            print(' Attachment "{}" @{} is too big({}), migrated as url'.format(
                attachment.name, task_id, attachment.bytes
            ))
            return False

        r = requests.get(attachment.url)
        file_id = self._kanboard.create_task_file(
            project_id=self.project_id,
            task_id=task_id,
            filename=attachment.name,
            blob=base64.b64encode(r.content).decode('utf-8')
        )
        if _operation_failed(file_id):
            print(' Failed to add file "{}", migrated as url'.format(
                attachment.name
            ))
            return False
        return True

    def _add_external_link_to_task(self, attachment, task_id):
        link_id = self._kanboard.create_external_task_link(
            task_id=task_id,
            url=attachment.url,
            dependency='related',
            title=attachment.name
        )
        if _operation_failed(link_id):
            print(' Failed to add link "{}" for attachment "{}"'.format(
                attachment.url,
                attachment.name
            ))

    def _map_labels(self, labels):
        priority = None
        score = None
        tags = []
        for label in labels:
            if not label.name:  # just label with color, ignore for now
                continue

            name = label.name
            v = _match_name(name, self.complexity_map)
            if v:
                score = v
                continue
            v = _match_name(name, self.priority_map)
            if v:
                priority = v
                continue
            tags.append(name)
        return priority, score, tags


def _extract_path_components(path):
    return list(filter(None, path.split('/')))


def _operation_failed(id_):
    return type(id_) is bool


def _convert_datetimes(datetime_utc_str, utc_format, timezone):
    d = datetime.strptime(datetime_utc_str, utc_format)
    return d.replace(tzinfo=pytz.UTC).astimezone(timezone)


def _match_name(name, mapping):
    for regex, value in mapping:
        if regex.match(name):
            return value
    return None
