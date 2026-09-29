import threading

from hypothesis import settings
from hypothesis import strategies as st
from hypothesis.stateful import Bundle
from hypothesis.stateful import RuleBasedStateMachine
from hypothesis.stateful import rule

from src import main


TEXT = st.text(max_size=10)


def hide_output(*args, **kwargs):
    return None


main.print = hide_output


class RpcStateMachine(RuleBasedStateMachine):
    entity_ids = Bundle("entity_ids")
    command_ids = Bundle("command_ids")

    def __init__(self):
        super().__init__()
        main.entities.clear()
        main.commands.clear()
        main.results.clear()
        self.entities = []
        self.commands = []
        self.results = []
        self.next_created = 1
        self.server = main.Server(("127.0.0.1", 0), main.RequestHandler)
        self.thread = threading.Thread(
            target=self.server.serve_forever,
            daemon=True,
        )
        self.thread.start()
        port = self.server.server_address[1]
        self.client = main.RpcClient(port=port)

    def teardown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def get_created(self):
        created = self.next_created
        self.next_created += 1
        return created

    def get_recent_rows(self, now):
        rows = []
        for entity in self.entities:
            if entity["created"] < now - main.RECENT_SECONDS:
                continue
            matches = [
                command for command in self.commands
                if command["entity"] == entity["identifier"]
            ]
            if not matches:
                rows.append({
                    "argument": None,
                    "locale": entity["locale"],
                    "user_agent": entity["user_agent"],
                })
            for command in matches:
                rows.append({
                    "argument": command["argument"],
                    "locale": entity["locale"],
                    "user_agent": entity["user_agent"],
                })
        return rows

    @rule(target=entity_ids, locale=TEXT, user_agent=TEXT)
    def check_entity(self, locale, user_agent):
        entity = {
            "identifier": len(self.entities),
            "created": self.get_created(),
            "locale": locale,
            "user_agent": user_agent,
        }
        actual = self.client.create_entity(
            locale,
            user_agent,
            created=entity["created"],
        )
        assert actual == entity
        self.entities.append(entity)
        assert self.client.get_all_entities() == self.entities
        selected = self.client.get_recent_commands(entity["created"])
        assert selected == self.get_recent_rows(entity["created"])
        entity = {**entity, "locale": f"{locale}_new"}
        actual = self.client.edit_entity(
            entity["identifier"],
            locale=entity["locale"],
        )
        assert actual == entity
        self.entities[entity["identifier"]] = entity
        assert self.client.get_all_entities() == self.entities
        return entity

    @rule(target=command_ids, entity=entity_ids, argument=TEXT, status=TEXT)
    def check_command(self, entity, argument, status):
        command = {
            "identifier": len(self.commands),
            "created": self.get_created(),
            "argument": argument,
            "entity": entity["identifier"],
            "tags": None,
            "status": status,
            "started": None,
        }
        actual = self.client.create_command(
            entity["identifier"],
            argument=argument,
            status=status,
            created=command["created"],
        )
        assert actual == command
        self.commands.append(command)
        assert self.client.get_all_commands() == self.commands
        command = {**command, "status": "done"}
        actual = self.client.edit_command(
            command["identifier"],
            status=command["status"],
        )
        assert actual == command
        self.commands[-1] = command
        assert self.client.get_all_commands() == self.commands
        return command

    @rule(command=command_ids, response=TEXT, status=TEXT)
    def check_result(self, command, response, status):
        result = {
            "identifier": len(self.results),
            "created": self.get_created(),
            "response": response,
            "status": status,
            "error": None,
            "command": command["identifier"],
            "cache_hit": None,
            "duration": None,
        }
        actual = self.client.create_result(
            command["identifier"],
            response=response,
            status=status,
            created=result["created"],
        )
        assert actual == result
        self.results.append(result)
        assert self.client.get_all_results() == self.results
        result = {**result, "cache_hit": 1}
        actual = self.client.edit_result(
            result["identifier"],
            cache_hit=result["cache_hit"],
        )
        assert actual == result
        self.results[-1] = result
        assert self.client.get_all_results() == self.results

    @rule(entity=entity_ids)
    def check_recent_commands(self, entity):
        selected = self.client.get_recent_commands(entity["created"])
        assert selected == self.get_recent_rows(entity["created"])


TestRpc = RpcStateMachine.TestCase
TestRpc.settings = settings(
    deadline=None,
    max_examples=5,
    stateful_step_count=10,
)
