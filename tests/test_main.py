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

    def expected_join(self, now):
        selected = []
        for entity in self.entities:
            if entity["created"] < now - main.RECENT_SECONDS:
                continue
            matches = [
                command for command in self.commands
                if command["entity"] == entity["identifier"]
            ]
            arguments = [item["argument"] for item in matches] or [None]
            for argument in arguments:
                selected.append({
                    "argument": argument,
                    "locale": entity["locale"],
                    "user_agent": entity["user_agent"],
                })
        return selected

    def check_entity(self, locale, user_agent):
        entity = self.client.create_entity(locale, user_agent)
        self.entities.append(entity)
        assert self.client.get_all_entities() == self.entities
        selected = self.client.get_recent_commands(entity["created"])
        assert selected == self.expected_join(entity["created"])
        entity = self.client.edit_entity(
            entity["identifier"],
            locale=f"{locale}_new",
        )
        self.entities[-1] = entity
        return entity

    def check_command(self, entity, argument, status):
        command = self.client.create_command(
            entity["identifier"],
            argument=argument,
            status=status,
        )
        self.commands.append(command)
        assert self.client.get_all_commands() == self.commands
        command = self.client.edit_command(
            command["identifier"],
            status="done",
        )
        self.commands[-1] = command
        return command

    def check_result(self, command, response, status):
        result = self.client.create_result(
            command["identifier"],
            response=response,
            status=status,
        )
        self.results.append(result)
        assert self.client.get_all_results() == self.results
        result = self.client.edit_result(
            result["identifier"],
            cache_hit=1,
        )
        self.results[-1] = result

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
        assert selected == self.expected_join(entity["created"])


TestRpc = RpcStateMachine.TestCase
TestRpc.settings = settings(
    deadline=None,
    max_examples=5,
    stateful_step_count=2,
)
