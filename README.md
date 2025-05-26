# electro - bot's development made easy

A framework for building bots, made for humans.

# How to run?

1. Install the `poetry` environment:
   ```shell
   poetry install
   ```

2. Go to the `./examples` directory:
    ```shell
    cd ./examples
    ```

3. Make sure you have all the required configs in `.env` file:
    ```shell
    cp .env.example .env
    # vi .env
    ```

4. Run the `TestFlow`:
   ```shell
   poetry run python ./test_flow.py
   ```

5. Check the API server @ http://localhost:8000/docs.
6. Use one of the clients to connect the platforms: [Discord](https://github.com/CyberCRI/ikigai-discord-client).

---

# How does the `electro` framework work?

The core idea behind the framework is to simplify the flow of users' conversations by allowing you to group dialogs into
Python classes.
These classes are then called Flows, and class members are called Flow Steps.
When a Flow represents a full dialog, the Flow Steps are the individual messages.

## Flows

The Flow is created when you inherit from the `electro.Flow` class.
It automatically gathers all the members of the child class that are Flow Steps and keeps an ordered list of all those
Flow Steps internally.

In practice, it looks like this:

```python
from electro import Flow, MessageFlowStep
from electro.triggers import CommandTrigger


class TestFlow(Flow):
    """Test Flow."""

    _triggers = [
        CommandTrigger("test"),
    ]

    send_test_message_1 = MessageFlowStep("test_flow_message")
    send_test_message_2 = MessageFlowStep("test_flow_message_2")
```

### Triggering a Flow

In the example above, we see this line:

```python
    _triggers = [
    CommandTrigger("test"),
]
```

This is, in essence, how you _trigger_ a Flow.
Why trigger?
Imagine you have multiple Flows, and only one can be run at a time.
A trigger is something that allows you to "enter"
that specific Flow, and proceed from there. Usually a Trigger is a command. However, it can be almost anything that
inherits from the `electro.triggers.BaseFlowTrigger` class and implements the `._check(...)` method.

### Registering a Flow

The Flow keeps track of all its Flow Steps. But who keeps track of all the Flows? That's the job of the FlowManager.
**There's only one FlowManager in the Project** (and it hooks to the FastAPI to send/receive messages).

To register your Flow, you have to:

```python
from electro.flow_manager import global_flow_manager  # import the Global Flow Manager

global_flow_manager.add_flow(YourFlow)
```

## Flow Steps

Each Flow Step is responsible for two things:

- sending a text/photo/buttons (or do nothing).
- receiving and processing the response (or don't).

It works like that to give you more control over the flow of the conversation (because usually you _ask a question_ and
_listen to the response_ within the same entity), unlike the usual "handlers" approach.

## Under the hood

The Flow class knows all of its steps, indexes them, and keeps track of which Step every User is currently at.
When a message is sent, the Flow Step index is still N.
When a message is received from the user, Flow gets the Flow Step with index N, calls the
`FlowStep().process_response()` method. If that method raises `FlowStepDone`, the N becomes N+1 and we move to the next
Flow Step. The cycle continues until there are no more Steps in the Flow. 

