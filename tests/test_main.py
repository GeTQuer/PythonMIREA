import threading

from hypothesis import settings
from hypothesis import strategies as st
from hypothesis.stateful import RuleBasedStateMachine
from hypothesis.stateful import rule

from src import main


TEXT = st.text(max_size=10)


def hide_output(*args, **kwargs):
    return None


main.print = hide_output


class RpcStateMachine(RuleBasedStateMachine):
    def __init__(self):
        super().__init__()
        main.entities.clear()
        main.commands.clear()
        main.results.clear()
        self.entities = []
        self.commands = []
        self.results = []
        self.recent_rows = []
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
        self.recent_rows.append({
            "argument": None,
            "locale": locale,
            "user_agent": user_agent,
        })
        assert self.client.get_all_entities() == self.entities
        selected = self.client.get_recent_commands(entity["created"])
        assert selected == self.recent_rows
        entity = {**entity, "locale": f"{locale}_new"}
        actual = self.client.edit_entity(
            entity["identifier"],
            locale=entity["locale"],
        )
        assert actual == entity
        self.entities[-1] = entity
        self.recent_rows[-1]["locale"] = entity["locale"]
        assert self.client.get_all_entities() == self.entities
        return entity

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
        self.recent_rows[-1]["argument"] = argument
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

    @rule(
        argument=TEXT,
        locale=TEXT,
        response=TEXT,
        status=TEXT,
        user_agent=TEXT,
    )
    def check_all_methods(
        self,
        argument,
        locale,
        response,
        status,
        user_agent,
    ):
        entity = self.check_entity(locale, user_agent)
        command = self.check_command(entity, argument, status)
        self.check_result(command, response, status)
        selected = self.client.get_recent_commands(entity["created"])
        assert selected == self.recent_rows


TestRpc = RpcStateMachine.TestCase
TestRpc.settings = settings(
    deadline=None,
    max_examples=5,
    stateful_step_count=2,
)
