"""Test Flow example."""

import uvicorn

from electro import Flow, MessageFlowStep
from electro.app import app
from electro.triggers import CommandTrigger
from electro.flow_manager import global_flow_manager
from toolkit.i18n import _


class TestFlow(Flow):
    """Test Flow."""

    _triggers = [
        CommandTrigger("test"),
    ]

    send_test_message_1 = MessageFlowStep(_("test_flow_message"))
    send_test_message_2 = MessageFlowStep(_("test_flow_message_2"))


global_flow_manager.add_flow(TestFlow())


if __name__ == "__main__":
    uvicorn.run(app=app, loop="asyncio", port=8000, host="0.0.0.0")
