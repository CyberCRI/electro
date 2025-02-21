"""Test Flow example."""

import uvicorn

from electro.app import app
from electro import Flow, MessageFlowStep

from electro.triggers import CommandTrigger

from electro.flow_manager import global_flow_manager



class TestFlow(Flow):
    """Test Flow."""

    _triggers = [CommandTrigger("test_flow")]
    send_test_message = MessageFlowStep("test_flow_message")

global_flow_manager.add_flow(TestFlow())

if __name__ == "__main__":
    uvicorn.run(app=app, loop="asyncio")
