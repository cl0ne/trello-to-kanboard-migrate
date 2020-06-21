# Trello-to-Kanboard migration
Command-line scripts written to automate migration from Trello boards to Kanboard projects.

## Setup

Install dependencies with `pip install -r requirements.txt`.

## Usage

To get started you'll need to:

1. Get an Trello API key and API secret from https://trello.com/app-key.
2. Obtain an Trello OAuth token, there are at least two ways:
    - generate it at https://trello.com/app-key, this token doesn't need token secret;
    - run py-trello package from command line with `TRELLO_API_KEY` and `TRELLO_API_SECRET` environment variables set accordingly:
    
        ```
        python -m trello oauth
        ```

3. Generate Kanboard User API access token (My profile &rarr; API).


### Board-to-project migration

For migration you'll have to specify ids of existing Kanboard project and Trello board (you can get them with helper scripts). You should add member users to Kanboard project beforehand.

Migration logic is implemented via `Migrator` class, it accepts instances Kanboard and Trello clients, board and project ids. There's a `migration_example.py` [script](migration_example.py) that you can use as a starting point for your migration process.
 
Trello labels assigned to cards can be converted to Kanboard task priority, complexity and tags according to their text. `Migrator` will try to preserve link between cards and will create "related to" link between corresponding tasks. Files attached to cards will be uploaded to Kanboard instance if they are less than configured size limit (set to 3 MB by default) otherwise they will be added as external link.

`Migrator` will try to match Kanboard project user to Trello board member by name if no mapping for that user was specified explicitly. This can be done by adding `Trello member name`-`Kanboard user id` pairs to `users_map`. Card with multiple assigned users will be migrated to the task with tag "migration: more than one member", one of the users will be assigned to the task and other users will be mentioned at the end of the task's description. There's [Group_assign](https://github.com/creecros/Group_assign) Kanboard plugin that should provide functionality similar to Trello's multiple assignment but it didn't exist at the time when I was writing migration script.

To migrate dates correctly you have to specify Kanboard instance timezone (due to issues [3653](https://github.com/kanboard/kanboard/issues/3653) and [3654](https://github.com/kanboard/kanboard/issues/3654)).

### Helper scripts

There are two simple scripts for retrieving lists of Trello boards and Kanboard projects that the user is a member of: `list_trello_boards.py` and `list_kanboard_projects.py`. Usage details for them are shown below:


    python list_kanboard_projects.py your_kanboard_instance_url
User is defined by `KANBOARD_USERNAME` and `KANBOARD_TOKEN` environment variables.

    python list_trello_boards.py show
User is defined by `TRELLO_API_KEY`, `TRELLO_API_SECRET`, `TRELLO_TOKEN` and `TRELLO_TOKEN_SECRET` environment variables accordingly.
